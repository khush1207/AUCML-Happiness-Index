"""
One-time patch for src/main.py so the app can run on Vercel (2 GB RAM).

What it changes:
  * The heavy snapshot builder is renamed _build_snapshot().
  * A new _snapshot() loads a small precomputed file (data/snapshot.pkl.gz)
    when it exists, and otherwise builds one the old way.
  * The dashboard trend and the employee history no longer need the full
    2.3-million-row table; they use small precomputed structures instead.

Run from the project root:   python patch_main.py
Then delete this file. It stops without changing anything if the expected
code is not found.
"""
import re
import sys
from pathlib import Path

MAIN = Path("src/main.py")
if not MAIN.is_file():
    sys.exit("Run this from the project root (src/main.py not found).")

raw = MAIN.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")

if "_build_snapshot" in text:
    sys.exit("src/main.py already looks patched. Nothing to do.")

NEW_BLOCK = '''# -----------------------------------------------------------------------------
# Precomputed snapshot (keeps memory small on hosts with little RAM)
# -----------------------------------------------------------------------------

SNAPSHOT_FILE = Path(__file__).resolve().parent.parent / "data" / "snapshot.pkl.gz"


def _slim_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    """Replace the huge `processed` table with small lookup structures."""
    processed = snap.pop("processed")

    # Monthly average HI per company (last 12 months) for the dashboard trend
    trend_src = processed[["companyId", "date", "hiVote"]].dropna(subset=["date", "hiVote"]).copy()
    trend_src["month"] = pd.to_datetime(trend_src["date"]).dt.to_period("M").dt.to_timestamp()
    monthly = (
        trend_src.groupby(["companyId", "month"])
        .agg(average_hi=("hiVote", "mean"), observation_count=("hiVote", "count"))
        .reset_index()
    )
    company_trend: dict[str, list[dict[str, Any]]] = {}
    for company_id, grp in monthly.groupby("companyId"):
        grp = grp.sort_values("month").tail(12)
        company_trend[str(company_id)] = [
            {
                "month": _iso(r.month),
                "average_hi": round(float(r.average_hi), 3),
                "observation_count": int(r.observation_count),
                "is_prediction": False,
            }
            for r in grp.itertuples()
        ]
    del trend_src, monthly

    # Per-employee history: rows are already sorted by company, employee, date,
    # so each employee is one contiguous slice of the small history table.
    codes = processed.groupby(["companyId", "employeeId"], sort=False, dropna=False).ngroup()
    sizes = processed.groupby(["companyId", "employeeId"], sort=False, dropna=False).size()
    runs = int((codes.diff().fillna(1) != 0).sum())
    if runs != len(sizes):
        raise RuntimeError("Employee rows are not contiguous; cannot build history index.")
    ends = sizes.to_numpy().cumsum()
    starts = ends - sizes.to_numpy()
    history_index = {
        (_as_id(c), _as_id(e)): (int(s), int(t))
        for (c, e), s, t in zip(sizes.index, starts, ends)
    }
    history = processed[["date", "hiVote", "score_response_date"]].copy()
    history["hiVote"] = history["hiVote"].astype("float32")
    history = history.reset_index(drop=True)

    snap["company_trend"] = company_trend
    snap["history_index"] = history_index
    snap["history"] = history
    return snap


@lru_cache(maxsize=1)
def _snapshot() -> dict[str, Any]:
    """Load the precomputed snapshot if present, otherwise build it."""
    try:
        if SNAPSHOT_FILE.is_file():
            snap = pd.read_pickle(SNAPSHOT_FILE)
            model = model_service.load_model()
            snap["model"] = model
            snap["explainer"] = shap.TreeExplainer(model)
            return snap
        return _slim_snapshot(_build_snapshot())
    except Exception as exc:
        raise RuntimeError(f"Could not load prediction snapshot: {exc}") from exc


'''

NEW_TREND = '''        # Historical trend (monthly averages), precomputed per company
        trend_data = list(snap["company_trend"].get(company_id, []))
'''

NEW_HISTORY = '''        span = snap["history_index"].get((company_id, employee_id))
        hist_frame = (
            snap["history"].iloc[span[0]:span[1]].sort_values("date")
            if span
            else snap["history"].iloc[0:0]
        )
'''

def once(pattern, repl, s, flags=0):
    new, n = re.subn(pattern, lambda m: repl, s, count=0, flags=flags)
    if n != 1:
        sys.exit(f"Patch stopped: expected 1 match, found {n} for: {pattern[:60]}...")
    return new

text = once(
    r"@lru_cache\(maxsize=1\)\ndef _snapshot\(\) -> dict\[str, Any\]:\n",
    "def _build_snapshot() -> dict[str, Any]:\n",
    text,
)
text = once(
    r"# -{70,}\n# Frontend Routes\n",
    NEW_BLOCK + "# -----------------------------------------------------------------------------\n# Frontend Routes\n",
    text,
)
text = once(
    r"        # Historical trend \(monthly averages\)\n.*?for _, r in trend\.iterrows\(\)\n        \]\n",
    NEW_TREND,
    text,
    flags=re.DOTALL,
)
text = once(
    r'        processed = snap\["processed"\]\n        hist_frame = processed\[.*?\.sort_values\("date"\)\n',
    NEW_HISTORY,
    text,
    flags=re.DOTALL,
)

if 'snap["processed"]' in text:
    sys.exit("Patch stopped: a leftover use of snap['processed'] remains.")

MAIN.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
print("src/main.py patched. Next: python build_snapshot.py")
