from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import shap
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Supports both `uvicorn src.main:app` from the project root and
# `uvicorn main:app` when the working directory is src/.
try:
    from . import model as model_service
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import model as model_service

app = FastAPI(
    title="AUCML — Employee Happiness Intelligence System API",
    version="2.0.0",
    description="Enterprise HR analytics, workforce summaries, and employee HI predictions.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"


def _as_id(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    try:
        return pd.Timestamp(value).date().isoformat()
    except (TypeError, ValueError):
        return None


def _format_age_label(days: int | None) -> str:
    if days is None:
        return "No confirmed feedback date"
    if days == 0:
        return "On latest data date"
    if days < 30:
        return f"{days} days since feedback"
    months = round(days / 30.4375, 1)
    if months == int(months):
        return f"{int(months)} months since feedback"
    return f"{months:.1f} months since feedback"


@lru_cache(maxsize=1)
def _snapshot() -> dict[str, Any]:
    """Build a single latest-record-per-employee prediction snapshot.

    Respects the exact business rules from the specification:
    - latest_data_date = max date in dataset
    - prediction_date = exactly 1 calendar day after latest_data_date
    - six_month_cutoff = exactly 6 calendar months before latest_data_date
    - employment status:
        deleted==True or deletionDate not null -> Confirmed Former Employee
        deleted==False -> Active
        deleted is null -> Status Unknown
    - last confirmed feedback = latest valid score response date
    - feedback age = calendar days between latest_data_date and last confirmed feedback
    - potentially inactive = active employee with last feedback > 6 calendar months ago
    """
    try:
        model = model_service.load_model()
        raw = model_service.load_data()
        processed, features = model_service.create_features(raw)

        if processed.empty:
            raise RuntimeError("The combined employee dataset is empty.")

        cutoff = pd.to_datetime(processed["date"]).max()
        prediction_date = cutoff + pd.Timedelta(days=1)
        six_month_cutoff = cutoff - pd.DateOffset(months=6)

        latest = (
            processed.sort_values("date")
            .groupby(["companyId", "employeeId"], dropna=False, sort=False)
            .tail(1)
            .copy()
        )
        latest_indices = latest.index
        X_latest = features.loc[latest_indices].copy()
        X_latest = model_service.align_features(X_latest, model)
        X_latest = model_service.impute_features(X_latest, raw)

        pred0 = model.predict(X_latest).astype(int)
        predicted = pred0 + 1  # model classes encoded 0..3 during training
        probs = model.predict_proba(X_latest) if hasattr(model, "predict_proba") else None

        # Pre-initialize TreeExplainer for fast individual employee explanations
        explainer = shap.TreeExplainer(model)

        employees: list[dict[str, Any]] = []
        employee_map: dict[tuple[str, str], dict[str, Any]] = {}
        latest_index_map: dict[tuple[str, str], int] = {}

        for position, (idx, row) in enumerate(latest.iterrows()):
            company_id = _as_id(row["companyId"])
            employee_id = _as_id(row["employeeId"])
            predicted_hi = int(predicted[position])

            # Employment status classification
            deleted_val = row.get("deleted")
            deletion_date = row.get("deletionDate")
            has_deletion_date = pd.notna(deletion_date) and str(deletion_date).strip() != ""

            if deleted_val is True or has_deletion_date:
                is_active = False
                is_confirmed_former = True
                is_unknown_status = False
                employment_status = "Confirmed Former"
            elif deleted_val is False:
                is_active = True
                is_confirmed_former = False
                is_unknown_status = False
                employment_status = "Active"
            else:
                is_active = False
                is_confirmed_former = False
                is_unknown_status = True
                employment_status = "Status Unknown"

            # Confirmed feedback submission
            last_feedback = row.get("last_score_date")
            age_days = None
            last_feedback_iso = None
            is_potentially_inactive = False

            if pd.notna(last_feedback):
                feedback_timestamp = pd.Timestamp(last_feedback)
                last_feedback_iso = feedback_timestamp.date().isoformat()
                age_days = max(0, int((cutoff - feedback_timestamp).days))
                # Six calendar month rule (calendar arithmetic)
                if is_active and feedback_timestamp < six_month_cutoff:
                    is_potentially_inactive = True

            feedback_age_label = _format_age_label(age_days)

            prob_map = {}
            if probs is not None:
                prob_map = {
                    str(int(class_label) + 1): round(float(prob), 6)
                    for class_label, prob in zip(model.classes_, probs[position])
                }

            # Standard risk rules for active workforce
            risk_flag = is_active and (predicted_hi <= 2)
            feedback_overdue = is_active and (age_days is not None and age_days > 30)
            needs_attention = is_active and (risk_flag or feedback_overdue or is_potentially_inactive)

            reasons: list[str] = []
            if risk_flag:
                reasons.append(f"Predicted HI is Low (HI {predicted_hi})")
            if feedback_overdue:
                reasons.append(f"Feedback overdue ({age_days} days)")
            if is_potentially_inactive:
                reasons.append("Stale feedback > 6 calendar months (verify employment)")

            emp_data: dict[str, Any] = {
                "company_id": company_id,
                "employee_id": employee_id,
                "current_hi": int(row["hiVote"]) if pd.notna(row.get("hiVote")) else None,
                "predicted_hi": predicted_hi,
                "prediction_date": _iso(prediction_date),
                "latest_employee_data": _iso(row.get("date")),
                "last_feedback_date": last_feedback_iso,
                "days_since_feedback": age_days,
                "feedback_age_label": feedback_age_label,
                "probabilities": prob_map,
                "confidence": max(prob_map.values()) if prob_map else None,
                "tenure_years": round(float(row["tenure_years"]), 1) if pd.notna(row.get("tenure_years")) else None,
                "gender": str(row["gender"]) if pd.notna(row.get("gender")) else None,
                "industry": str(row["industry"]) if pd.notna(row.get("industry")) else None,
                "timezone": str(row["timezone"]) if pd.notna(row.get("timezone")) else None,
                "department_id": _as_id(row.get("departmentId")),
                "deleted": True if deleted_val is True else (False if deleted_val is False else None),
                "deletion_date": _iso(deletion_date) if has_deletion_date else None,
                "is_active": is_active,
                "is_confirmed_former": is_confirmed_former,
                "is_unknown_status": is_unknown_status,
                "employment_status": employment_status,
                "is_potentially_inactive": is_potentially_inactive,
                "risk_flag": risk_flag,
                "feedback_overdue": feedback_overdue,
                "needs_attention": needs_attention,
                "attention_reasons": reasons,
                "attention_reason": " · ".join(reasons) if reasons else "",
                "row_index": idx,
            }

            employees.append(emp_data)
            key = (company_id, employee_id)
            employee_map[key] = emp_data
            latest_index_map[key] = idx

        # Group employees by company for fast lookup
        company_employees: dict[str, list[dict[str, Any]]] = {}
        for emp in employees:
            company_employees.setdefault(emp["company_id"], []).append(emp)

        # Company metadata summary
        companies_meta: list[dict[str, Any]] = []
        for company_id, rows in sorted(company_employees.items()):
            active_rows = [r for r in rows if r["is_active"]]
            valid_his = [r["current_hi"] for r in active_rows if r["current_hi"] is not None]
            ind = next((r["industry"] for r in rows if r["industry"]), None)
            tz = next((r["timezone"] for r in rows if r["timezone"]), None)
            companies_meta.append({
                "id": company_id,
                "name": f"Company {company_id[:8]}",
                "industry": ind or "Industry Unspecified",
                "timezone": tz or "Timezone Unspecified",
                "total_employees": len(rows),
                "active_employees": len(active_rows),
                "former_employees": sum(1 for r in rows if r["is_confirmed_former"]),
                "unknown_employees": sum(1 for r in rows if r["is_unknown_status"]),
                "attention_count": sum(1 for r in active_rows if r["needs_attention"]),
                "average_hi": round(float(np.mean(valid_his)), 2) if valid_his else None,
            })

        return {
            "latest_data_date": _iso(cutoff),
            "prediction_date": _iso(prediction_date),
            "six_month_cutoff": _iso(six_month_cutoff),
            "companies": sorted(company_employees.keys()),
            "companies_meta": companies_meta,
            "company_employees": company_employees,
            "employees": employees,
            "employee_map": employee_map,
            "latest_index_map": latest_index_map,
            "processed": processed,
            "X_latest": X_latest,
            "model": model,
            "explainer": explainer,
        }
    except Exception as exc:
        raise RuntimeError(f"Could not build prediction snapshot: {exc}") from exc


# -----------------------------------------------------------------------------
# Frontend Routes
# -----------------------------------------------------------------------------

if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_index() -> FileResponse:
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=404, detail="Frontend index.html not found.")
    return FileResponse(str(index_file))


# -----------------------------------------------------------------------------
# API Routes
# -----------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "Happiness Intelligence API", "version": "2.0.0"}


@app.get("/api/companies")
def companies() -> dict[str, Any]:
    try:
        snap = _snapshot()
        return {
            "companies": snap["companies_meta"],
            "latest_data_date": snap["latest_data_date"],
            "prediction_date": snap["prediction_date"],
            "six_month_cutoff": snap["six_month_cutoff"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/dashboard")
def dashboard(
    company_id: str = Query(...),
    low_hi_threshold: int = Query(default=2, ge=1, le=3),
    feedback_overdue_days: int = Query(default=30, ge=1),
    inactivity_months: int = Query(default=6, ge=1),
) -> dict[str, Any]:
    try:
        snap = _snapshot()
        company_rows = snap["company_employees"].get(company_id)
        if not company_rows:
            raise HTTPException(status_code=404, detail="Company not found or has no employees.")

        cutoff = pd.Timestamp(snap["latest_data_date"])
        inactivity_cutoff = cutoff - pd.DateOffset(months=inactivity_months)

        active_rows = [e for e in company_rows if e["is_active"]]
        former_rows = [e for e in company_rows if e["is_confirmed_former"]]
        unknown_rows = [e for e in company_rows if e["is_unknown_status"]]

        # Re-evaluate attention & thresholds dynamically based on user preferences
        evaluated_active: list[dict[str, Any]] = []
        for e in active_rows:
            e_copy = dict(e)
            age = e["days_since_feedback"]
            last_fb = pd.Timestamp(e["last_feedback_date"]) if e["last_feedback_date"] else None

            is_low_hi = e["predicted_hi"] <= low_hi_threshold
            is_overdue = age is not None and age > feedback_overdue_days
            is_inactive = last_fb is not None and last_fb < inactivity_cutoff

            reasons: list[str] = []
            if is_low_hi:
                reasons.append(f"Predicted HI <= {low_hi_threshold} (HI {e['predicted_hi']})")
            if is_overdue:
                reasons.append(f"Feedback overdue ({age} days)")
            if is_inactive:
                reasons.append(f"Stale feedback > {inactivity_months} mos (verify employment)")

            needs_att = is_low_hi or is_overdue or is_inactive
            e_copy["risk_flag"] = is_low_hi
            e_copy["feedback_overdue"] = is_overdue
            e_copy["is_potentially_inactive"] = is_inactive
            e_copy["needs_attention"] = needs_att
            e_copy["attention_reasons"] = reasons
            e_copy["attention_reason"] = " · ".join(reasons)
            evaluated_active.append(e_copy)

        valid_his = [e["current_hi"] for e in evaluated_active if e["current_hi"] is not None]
        attention_rows = [e for e in evaluated_active if e["needs_attention"]]
        low_hi_rows = [e for e in evaluated_active if e["risk_flag"]]
        overdue_rows = [e for e in evaluated_active if e["feedback_overdue"]]
        stale_review_rows = [e for e in evaluated_active if e["is_potentially_inactive"]]

        # Current HI distribution (Active population)
        hi_counts = {str(i): sum(e["current_hi"] == i for e in evaluated_active) for i in range(1, 5)}
        # Predicted HI distribution (Active population)
        pred_hi_counts = {str(i): sum(e["predicted_hi"] == i for e in evaluated_active) for i in range(1, 5)}

        # Historical trend (monthly averages)
        processed = snap["processed"]
        company_frame = processed[processed["companyId"].astype(str) == company_id].copy()
        company_frame["date"] = pd.to_datetime(company_frame["date"], errors="coerce")
        trend_frame = company_frame.dropna(subset=["date", "hiVote"]).copy()
        trend_frame["month"] = trend_frame["date"].dt.to_period("M").dt.to_timestamp()

        trend = (
            trend_frame.groupby("month")
            .agg(average_hi=("hiVote", "mean"), observation_count=("hiVote", "count"))
            .tail(12)
            .reset_index()
        )

        trend_data = [
            {
                "month": _iso(r["month"]),
                "average_hi": round(float(r["average_hi"]), 3),
                "observation_count": int(r["observation_count"]),
                "is_prediction": False,
            }
            for _, r in trend.iterrows()
        ]

        # Add prediction point clearly distinguished from observed history
        if evaluated_active:
            avg_pred = round(float(np.mean([e["predicted_hi"] for e in evaluated_active])), 3)
            trend_data.append({
                "month": snap["prediction_date"],
                "average_hi": avg_pred,
                "observation_count": len(evaluated_active),
                "is_prediction": True,
            })

        # Company metadata
        meta = next((m for m in snap["companies_meta"] if m["id"] == company_id), {})

        return {
            "company_id": company_id,
            "company_name": meta.get("name", f"Company {company_id[:8]}"),
            "industry": meta.get("industry", "Unspecified"),
            "timezone": meta.get("timezone", "Unspecified"),
            "latest_data_date": snap["latest_data_date"],
            "prediction_date": snap["prediction_date"],
            "six_month_cutoff": _iso(inactivity_cutoff),
            # KPIs for active workforce
            "total_active_employees": len(evaluated_active),
            "total_former_employees": len(former_rows),
            "total_unknown_employees": len(unknown_rows),
            "total_employees": len(company_rows),
            "average_hi": round(float(np.mean(valid_his)), 2) if valid_his else None,
            "attention_count": len(attention_rows),
            "attention_percent": round(100 * len(attention_rows) / len(evaluated_active), 1) if evaluated_active else None,
            "low_hi_count": len(low_hi_rows),
            "feedback_overdue_count": len(overdue_rows),
            "potentially_inactive_count": len(stale_review_rows),
            # Distributions & Trends
            "hi_distribution": [{"hi": int(k), "count": v} for k, v in hi_counts.items()],
            "predicted_hi_distribution": [{"hi": int(k), "count": v} for k, v in pred_hi_counts.items()],
            "trend": trend_data,
            # Top attention employees (first 10)
            "attention_employees": sorted(
                attention_rows,
                key=lambda e: (
                    e["predicted_hi"],
                    -(e["days_since_feedback"] or 0),
                    e["employee_id"],
                )
            )[:15],
            # All employees for backward compatibility
            "employees": sorted(evaluated_active, key=lambda e: (not e["needs_attention"], e["employee_id"])),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/employees")
def list_employees(
    company_id: str = Query(...),
    search: str = Query(default=""),
    status: str = Query(default="all"),
    risk: str = Query(default="all"),
    attention: str = Query(default="all"),
    feedback_status: str = Query(default="all"),
    sort_by: str = Query(default="attention_priority"),
    sort_dir: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=5, le=200),
    low_hi_threshold: int = Query(default=2, ge=1, le=3),
    feedback_overdue_days: int = Query(default=30, ge=1),
    inactivity_months: int = Query(default=6, ge=1),
) -> dict[str, Any]:
    try:
        snap = _snapshot()
        company_rows = snap["company_employees"].get(company_id)
        if company_rows is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        cutoff = pd.Timestamp(snap["latest_data_date"])
        inactivity_cutoff = cutoff - pd.DateOffset(months=inactivity_months)

        # Dynamic threshold evaluation
        evaluated: list[dict[str, Any]] = []
        for e in company_rows:
            e_copy = dict(e)
            if e["is_active"]:
                age = e["days_since_feedback"]
                last_fb = pd.Timestamp(e["last_feedback_date"]) if e["last_feedback_date"] else None
                is_low_hi = e["predicted_hi"] <= low_hi_threshold
                is_overdue = age is not None and age > feedback_overdue_days
                is_inactive = last_fb is not None and last_fb < inactivity_cutoff

                reasons: list[str] = []
                if is_low_hi:
                    reasons.append(f"Predicted HI <= {low_hi_threshold} (HI {e['predicted_hi']})")
                if is_overdue:
                    reasons.append(f"Feedback overdue ({age} days)")
                if is_inactive:
                    reasons.append(f"Stale feedback > {inactivity_months} mos (verify employment)")

                e_copy["risk_flag"] = is_low_hi
                e_copy["feedback_overdue"] = is_overdue
                e_copy["is_potentially_inactive"] = is_inactive
                e_copy["needs_attention"] = is_low_hi or is_overdue or is_inactive
                e_copy["attention_reasons"] = reasons
                e_copy["attention_reason"] = " · ".join(reasons)
            evaluated.append(e_copy)

        # Filtering
        filtered = evaluated

        # Search by real Employee ID
        if search.strip():
            s = search.strip().lower()
            filtered = [e for e in filtered if s in e["employee_id"].lower()]

        # Status filter
        if status == "active":
            filtered = [e for e in filtered if e["is_active"]]
        elif status == "potentially_inactive":
            filtered = [e for e in filtered if e["is_potentially_inactive"]]
        elif status == "former":
            filtered = [e for e in filtered if e["is_confirmed_former"]]
        elif status == "unknown":
            filtered = [e for e in filtered if e["is_unknown_status"]]

        # Risk filter
        if risk == "low":
            filtered = [e for e in filtered if e["predicted_hi"] <= 2]
        elif risk == "moderate":
            filtered = [e for e in filtered if e["predicted_hi"] == 3]
        elif risk == "high":
            filtered = [e for e in filtered if e["predicted_hi"] == 4]

        # Attention filter
        if attention == "needs_attention":
            filtered = [e for e in filtered if e["needs_attention"]]
        elif attention == "normal":
            filtered = [e for e in filtered if not e["needs_attention"]]

        # Feedback status filter
        if feedback_status == "confirmed":
            filtered = [e for e in filtered if e["last_feedback_date"] is not None]
        elif feedback_status == "unverified":
            filtered = [e for e in filtered if e["last_feedback_date"] is None]
        elif feedback_status == "overdue":
            filtered = [e for e in filtered if e["feedback_overdue"]]
        elif feedback_status == "stale":
            filtered = [e for e in filtered if e["is_potentially_inactive"]]

        # Sorting
        reverse = (sort_dir.lower() == "desc")

        def sort_key(emp: dict[str, Any]) -> Any:
            if sort_by == "employee_id":
                # Natural sort if numeric ID
                eid = emp["employee_id"]
                return (0, int(eid)) if eid.isdigit() else (1, eid)
            elif sort_by == "current_hi":
                val = emp["current_hi"]
                return (1, 0) if val is None else (0, val)
            elif sort_by == "predicted_hi":
                return (0, emp["predicted_hi"])
            elif sort_by == "prediction_date":
                return (0, emp["prediction_date"] or "")
            elif sort_by == "last_feedback_date":
                val = emp["last_feedback_date"]
                return (1, "") if val is None else (0, val)
            elif sort_by == "feedback_age":
                val = emp["days_since_feedback"]
                return (1, 0) if val is None else (0, val)
            elif sort_by == "employment_status":
                return (0, emp["employment_status"])
            elif sort_by == "attention_priority":
                # High priority: needs attention, lower predicted HI, oldest feedback
                return (
                    not emp["needs_attention"],
                    emp["predicted_hi"],
                    -(emp["days_since_feedback"] or 0),
                    emp["employee_id"],
                )
            return emp["employee_id"]

        sorted_rows = sorted(filtered, key=sort_key, reverse=reverse)

        # Pagination
        total_filtered = len(sorted_rows)
        total_pages = max(1, (total_filtered + page_size - 1) // page_size)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_rows = sorted_rows[start_idx:end_idx]

        return {
            "company_id": company_id,
            "total_count": len(company_rows),
            "filtered_count": total_filtered,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "employees": paged_rows,
            "latest_data_date": snap["latest_data_date"],
            "prediction_date": snap["prediction_date"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/employees/{employee_id}")
def employee_detail(employee_id: str, company_id: str = Query(...)) -> dict[str, Any]:
    try:
        snap = _snapshot()
        key = (company_id, employee_id)
        emp = snap["employee_map"].get(key)
        if emp is None:
            raise HTTPException(status_code=404, detail="Employee not found for this company.")

        # Fast SHAP explanation using cached feature row and TreeExplainer
        shap_explanation: list[dict[str, Any]] = []
        if key in snap["latest_index_map"]:
            row_idx = snap["latest_index_map"][key]
            if row_idx in snap["X_latest"].index:
                X_emp = snap["X_latest"].loc[[row_idx]]
                shap_explanation = model_service.explain_prediction(
                    snap["model"],
                    X_emp,
                    emp["predicted_hi"],
                    top_n=10,
                    explainer=snap["explainer"],
                )

        # Employee's historical records in chronological order
        processed = snap["processed"]
        hist_frame = processed[
            (processed["companyId"].astype(str) == company_id)
            & (processed["employeeId"].astype(str) == employee_id)
        ].sort_values("date")

        history: list[dict[str, Any]] = []
        for _, r in hist_frame.iterrows():
            record_date = _iso(r.get("date"))
            score_date = _iso(r.get("score_response_date"))
            history.append({
                "date": record_date,
                "hi_vote": int(r["hiVote"]) if pd.notna(r.get("hiVote")) else None,
                "has_feedback": bool(score_date is not None),
                "feedback_date": score_date,
            })

        return {
            **emp,
            "shap_explanation": shap_explanation,
            "history": history,
            "latest_data_date": snap["latest_data_date"],
            "prediction_date": snap["prediction_date"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/insights")
def insights(company_id: str = Query(...)) -> dict[str, Any]:
    try:
        snap = _snapshot()
        company_rows = snap["company_employees"].get(company_id)
        if not company_rows:
            raise HTTPException(status_code=404, detail="Company not found.")

        active_rows = [e for e in company_rows if e["is_active"]]

        # Attention reason breakdown
        reasons_breakdown = {
            "low_predicted_hi": sum(1 for e in active_rows if e["risk_flag"]),
            "feedback_overdue": sum(1 for e in active_rows if e["feedback_overdue"]),
            "potentially_inactive": sum(1 for e in active_rows if e["is_potentially_inactive"]),
        }

        # Feedback staleness buckets (Active workforce)
        buckets = {
            "fresh_under_30d": 0,
            "moderate_30_90d": 0,
            "stale_90_180d": 0,
            "inactive_over_180d": 0,
            "no_confirmed_feedback": 0,
        }

        for e in active_rows:
            age = e["days_since_feedback"]
            if age is None:
                buckets["no_confirmed_feedback"] += 1
            elif age <= 30:
                buckets["fresh_under_30d"] += 1
            elif age <= 90:
                buckets["moderate_30_90d"] += 1
            elif age <= 180:
                buckets["stale_90_180d"] += 1
            else:
                buckets["inactive_over_180d"] += 1

        # Potentially inactive review records (for HR audit)
        stale_review_list = [
            {
                "employee_id": e["employee_id"],
                "last_feedback_date": e["last_feedback_date"],
                "days_since_feedback": e["days_since_feedback"],
                "current_hi": e["current_hi"],
                "predicted_hi": e["predicted_hi"],
                "latest_employee_data": e["latest_employee_data"],
            }
            for e in active_rows if e["is_potentially_inactive"]
        ]

        # Multi-company benchmark (top 15 companies by active employee count)
        top_companies = sorted(
            snap["companies_meta"],
            key=lambda c: c["active_employees"],
            reverse=True,
        )[:15]

        return {
            "company_id": company_id,
            "total_active_employees": len(active_rows),
            "reasons_breakdown": reasons_breakdown,
            "feedback_staleness": buckets,
            "potentially_inactive_review_list": stale_review_list[:50],
            "potentially_inactive_count": len(stale_review_list),
            "top_companies_benchmark": top_companies,
            "latest_data_date": snap["latest_data_date"],
            "prediction_date": snap["prediction_date"],
            "six_month_cutoff": snap["six_month_cutoff"],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/cache/refresh")
def refresh_cache() -> dict[str, str]:
    _snapshot.cache_clear()
    return {"status": "cleared", "message": "Prediction snapshot will rebuild on next request."}
