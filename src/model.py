from pathlib import Path
from xml.parsers.expat import model
import shap

import numpy as np
import pandas as pd
import xgboost as xgb


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = BASE_DIR / "models"

COMBINED_FILE = PROCESSED_DIR / "combined_employee_engagement.zip"
MODEL_FILE = MODEL_DIR / "tuned_xgboost_no_calendar.ubj"

SCORE_METADATA_FILE = DATA_DIR / "scoreMetadata.csv"

# ============================================================
# LOAD MODEL
# ============================================================

def load_model():
    """
    Load the trained Tuned XGBoost models.
    """
    with open(MODEL_FILE, "rb") as file:
        model = xgb.XGBClassifier()
        model.load_model(MODEL_FILE)

        print("Model loaded successfully.")

    return model


# ============================================================
# LOAD DATA
# ============================================================

def load_data():
    """
    Load the combined employee engagement dataset.
    """
    df = pd.read_csv(COMBINED_FILE, low_memory=False)

    df["date"] = pd.to_datetime(df["date"])

    df = df.sort_values(
        ["companyId", "employeeId", "date"]
    ).reset_index(drop=True)

    return df


# ============================================================
# CREATE MODEL FEATURES
# ============================================================

def create_features(df):
    """
    Recreate the same feature engineering used during training.
    """

    df = df.copy()

    # --------------------------------------------------------
    # Past HI features
    # --------------------------------------------------------

    df["previous_hi"] = (
        df.groupby(
            ["companyId", "employeeId"]
        )["hiVote"]
        .shift(1)
    )

    df["previous_hi_avg_3"] = (
        df.groupby(
            ["companyId", "employeeId"]
        )["hiVote"]
        .transform(
            lambda x:
            x.shift(1)
             .rolling(3, min_periods=1)
             .mean()
        )
    )

    df["previous_hi_change"] = (
        df["previous_hi"] -
        df["previous_hi_avg_3"]
    )

    # --------------------------------------------------------
    # Time features
    # --------------------------------------------------------

    df["month"] = df["date"].dt.month
    df["day_of_week"] = df["date"].dt.dayofweek
    df["year"] = df["date"].dt.year

    # --------------------------------------------------------
    # Employee tenure
    # --------------------------------------------------------

    df["hiringDate"] = pd.to_datetime(
        df["hiringDate"],
        errors="coerce"
    )

    df["tenure_years"] = (
        (df["date"] - df["hiringDate"]).dt.days
        / 365.25
    )

    # Remove unrealistic values
    df.loc[
        (df["tenure_years"] < 0) |
        (df["tenure_years"] > 50),
        "tenure_years"
    ] = np.nan

    # --------------------------------------------------------
    # Identify Score columns
    # --------------------------------------------------------

    excluded_columns = [
        "companyId",
        "employeeId",
        "gender",
        "hiringDate",
        "birthDate",
        "deleted",
        "deletionDate",
        "industry",
        "timezone",
        "departmentId",
        "date",
        "hiVote",
        "target_hi",
        "previous_hi",
        "previous_hi_avg_3",
        "previous_hi_change",
        "month",
        "day_of_week",
        "year",
        "tenure_years",
        "score_response_date",
        "last_score_date",
        "score_age_days",
        "has_recent_score",
    ]

    score_columns = [
        col for col in df.columns
        if col not in excluded_columns
    ]

    # --------------------------------------------------------
    # Score response dates
    # --------------------------------------------------------

    score_available = (
        df[score_columns]
        .notna()
        .any(axis=1)
    )

    df["score_response_date"] = (
        df["date"].where(score_available)
    )

    # --------------------------------------------------------
    # Last Score response date
    # --------------------------------------------------------

    df["last_score_date"] = (
        df.groupby(
            ["companyId", "employeeId"]
        )["score_response_date"]
        .ffill()
    )

    # --------------------------------------------------------
    # Score age
    # --------------------------------------------------------

    df["score_age_days"] = (
        df["date"] -
        df["last_score_date"]
    ).dt.days

    # --------------------------------------------------------
    # Keep Score information from previous 30 days
    # --------------------------------------------------------

    for col in score_columns:
        df.loc[
            df["score_age_days"] > 30,
            col
        ] = np.nan

    # --------------------------------------------------------
    # Recent Score flag
    # --------------------------------------------------------

    df["has_recent_score"] = (
        df[score_columns]
        .notna()
        .any(axis=1)
        .astype(int)
    )

    # --------------------------------------------------------
    # Final feature definitions
    # --------------------------------------------------------

    categorical_features = [
        "gender",
        "industry",
        "timezone"
    ]

    numerical_features = [
        "previous_hi",
        "previous_hi_avg_3",
        "previous_hi_change",
        "tenure_years",
        "month",
        "day_of_week",
        "year"
    ]

    feature_columns = (
        numerical_features
        + categorical_features
        + score_columns
        + ["has_recent_score"]
    )

    X = df[feature_columns].copy()

    # --------------------------------------------------------
    # One-hot encoding
    # --------------------------------------------------------

    X = pd.get_dummies(
        X,
        columns=categorical_features,
        drop_first=True
    )

    return df, X


# ============================================================
# ALIGN FEATURES WITH TRAINED MODEL
# ============================================================

def align_features(X, model):
    """
    Make sure prediction data has exactly the same
    columns/order as the trained models.
    """

    # Depending on the XGBoost version, loaded UBJ models may expose
    # feature names through the sklearn wrapper or the underlying Booster.
    expected_columns = None
    if hasattr(model, "feature_names_in_"):
        expected_columns = list(model.feature_names_in_)
    else:
        try:
            expected_columns = model.get_booster().feature_names
        except Exception:
            expected_columns = None

    if expected_columns:
        X = X.reindex(columns=list(expected_columns), fill_value=0)

    return X


# ============================================================
# IMPUTE MISSING VALUES
# ============================================================

def impute_features(X, reference_df):

    X = X.copy()
    reference_df = reference_df.copy()

    reference_df["hiringDate"] = pd.to_datetime(
    reference_df["hiringDate"],
    errors="coerce"
    )

    reference_df["tenure_years"] = (
        (reference_df["date"] - reference_df["hiringDate"]).dt.days
        / 365.25
    )

    reference_df.loc[
        (reference_df["tenure_years"] < 0) |
        (reference_df["tenure_years"] > 50),
        "tenure_years"
    ] = np.nan

    # Same 80% split used during training
    split_date = reference_df["date"].quantile(0.80)

    train_reference = reference_df[
        reference_df["date"] <= split_date
    ].copy()

    # Numerical features
    numerical_columns = [
        "tenure_years",
        "previous_hi",
        "previous_hi_avg_3",
        "previous_hi_change"
    ]

    # Score columns
    excluded_columns = [
        "companyId", "employeeId",
        "gender", "hiringDate", "birthDate",
        "deleted", "deletionDate",
        "industry", "timezone",
        "departmentId", "date", "hiVote",
        "target_hi",
        "previous_hi", "previous_hi_avg_3",
        "previous_hi_change",
        "month", "day_of_week", "year",
        "tenure_years"
    ]

    score_columns = [
        col for col in reference_df.columns
        if col not in excluded_columns
    ]

    # Use TRAINING medians
    for col in numerical_columns + score_columns:

        if col in X.columns and col in train_reference.columns:

            median_value = train_reference[col].median()

            X[col] = X[col].fillna(median_value)

    return X


# ============================================================
# SCORE QUESTION MAPPING
# ============================================================

def load_score_question_mapping():

    """
    Load Score metadata and create a mapping from
    questionId to human-readable question information.
    """

    metadata = pd.read_csv(
        SCORE_METADATA_FILE,
        low_memory=False
    )

    metadata = metadata[
        [
            "questionId",
            "name",
            "factor",
            "question"
        ]
    ].drop_duplicates("questionId")

    mapping = {}

    for _, row in metadata.iterrows():

        mapping[str(row["questionId"])] = {
            "name": str(row["name"]),
            "factor": str(row["factor"]),
            "question": str(row["question"])
        }

    return mapping

# ============================================================
# LOCAL SHAP EXPLANATION
# ============================================================

def explain_prediction(
    model,
    X_employee,
    predicted_class,
    top_n=10,
    explainer=None
):

    """
    Generate a local SHAP explanation for one employee.

    Explains why the model predicted the given HI class
    for this specific employee.
    """

    if explainer is None:
        explainer = shap.TreeExplainer(model)

    shap_values = explainer.shap_values(
        X_employee
    )

    # --------------------------------------------------------
    # Handle multiclass SHAP output
    # --------------------------------------------------------

    if isinstance(shap_values, list):

        class_shap = shap_values[
            predicted_class - 1
        ][0]

    else:

        shap_values = np.asarray(
            shap_values
        )

        if shap_values.ndim == 3:

            class_shap = shap_values[
                0,
                :,
                predicted_class - 1
            ]

        elif shap_values.ndim == 2:

            class_shap = shap_values[0]

        else:

            raise ValueError(
                f"Unexpected SHAP output shape: "
                f"{shap_values.shape}"
            )

    # --------------------------------------------------------
    # Load Score question mapping
    # --------------------------------------------------------

    question_mapping = (
        load_score_question_mapping()
    )

    # --------------------------------------------------------
    # Build explanations
    # --------------------------------------------------------

    feature_names = list(
        X_employee.columns
    )

    feature_values = (
        X_employee.iloc[0].values
    )

    explanations = []

    for feature, value, shap_value in zip(
        feature_names,
        feature_values,
        class_shap
    ):

        shap_value = float(shap_value)

        # Ignore negligible contributions
        if abs(shap_value) < 1e-6:
            continue

        # ----------------------------------------------------
        # Determine direction
        # ----------------------------------------------------

        if shap_value > 0:
            direction = "towards_prediction"
        else:
            direction = "away_from_prediction"

        # ----------------------------------------------------
        # Score question
        # ----------------------------------------------------

        if feature in question_mapping:

            question_info = (
                question_mapping[feature]
            )

            explanation = {

                "feature": feature,

                "feature_type": "workplace_score",

                "name": question_info["name"],

                "factor": question_info["factor"],

                "question": question_info["question"],

                "value": float(value),

                "shap_value": shap_value,

                "direction": direction
            }

        # ----------------------------------------------------
        # Historical HI features
        # ----------------------------------------------------

        elif feature == "previous_hi":

            explanation = {

                "feature": feature,

                "feature_type": "historical_hi",

                "name": "Previous HI",

                "factor": "Engagement History",

                "question": (
                    "Employee's previous Happiness "
                    "Index value"
                ),

                "value": float(value),

                "shap_value": shap_value,

                "direction": direction
            }

        elif feature == "previous_hi_avg_3":

            explanation = {

                "feature": feature,

                "feature_type": "historical_hi",

                "name": "Previous 3 HI Average",

                "factor": "Engagement History",

                "question": (
                    "Average HI across the employee's "
                    "previous three available observations"
                ),

                "value": float(value),

                "shap_value": shap_value,

                "direction": direction
            }

        elif feature == "previous_hi_change":

            explanation = {

                "feature": feature,

                "feature_type": "historical_hi",

                "name": "Previous HI Change",

                "factor": "Engagement History",

                "question": (
                    "Difference between the previous HI "
                    "and the previous 3-observation average"
                ),

                "value": float(value),

                "shap_value": shap_value,

                "direction": direction
            }

        elif feature == "tenure_years":

            explanation = {

                "feature": feature,

                "feature_type": "employee_context",

                "name": "Employee Tenure",

                "factor": "Employee Context",

                "question": (
                    "Employee tenure in years"
                ),

                "value": float(value),

                "shap_value": shap_value,

                "direction": direction
            }

        elif feature == "has_recent_score":

            explanation = {

                "feature": feature,

                "feature_type": "workplace_score",

                "name": "Recent Workplace Feedback",

                "factor": "Score Availability",

                "question": (
                    "Whether recent workplace Score "
                    "feedback is available"
                ),

                "value": float(value),

                "shap_value": shap_value,

                "direction": direction
            }

        # ----------------------------------------------------
        # Other features
        # ----------------------------------------------------

        else:

            explanation = {

                "feature": feature,

                "feature_type": "other",

                "name": feature,

                "factor": "Model Feature",

                "question": (
                    "Feature used by the prediction model"
                ),

                "value": float(value),

                "shap_value": shap_value,

                "direction": direction
            }

        explanations.append(
            explanation
        )

    # --------------------------------------------------------
    # Sort by contribution magnitude
    # --------------------------------------------------------

    explanations.sort(
        key=lambda x: abs(
            x["shap_value"]
        ),
        reverse=True
    )

    return explanations[:top_n]

# ============================================================
# PREDICT EMPLOYEE HI
# ============================================================

def predict_employee_hi(company_id, employee_id):
    """
    Predict the next HI value for an existing employee.

    A single prediction cutoff date is determined from the
    latest date available in the dataset.

    Each employee uses their latest available data on or
    before that common cutoff date.
    """

    model = load_model()

    df = load_data()

    # --------------------------------------------------------
    # Global prediction cutoff
    # --------------------------------------------------------

    latest_data_date = df["date"].max()
    prediction_date = latest_data_date + pd.Timedelta(days=1)

    # --------------------------------------------------------
    # Check employee
    # --------------------------------------------------------

    employee_df = df[
        (df["companyId"].astype(str) == str(company_id)) &
        (df["employeeId"].astype(str) == str(employee_id))
    ].copy()

    if employee_df.empty:
        raise ValueError(
            "Employee not found for the given companyId "
            "and employeeId."
        )

    # --------------------------------------------------------
    # Create features for complete dataset
    # --------------------------------------------------------

    processed_df, X = create_features(df)

    # --------------------------------------------------------
    # Find employee's latest available record
    # on or before the global cutoff
    # --------------------------------------------------------

    employee_rows = processed_df[
        (processed_df["companyId"].astype(str) == str(company_id)) &
        (processed_df["employeeId"].astype(str) == str(employee_id)) &
        (processed_df["date"] <= latest_data_date)
    ]

    if employee_rows.empty:
        raise ValueError(
            "Employee has no available data on or before "
            "the prediction cutoff date."
        )

    latest_index = (
        employee_rows["date"]
        .idxmax()
    )

    # --------------------------------------------------------
    # Select same row from feature matrix
    # --------------------------------------------------------

    X_employee = X.loc[
        [latest_index]
    ].copy()

    # --------------------------------------------------------
    # Align with trained model
    # --------------------------------------------------------

    X_employee = align_features(
        X_employee,
        model
    )

    # --------------------------------------------------------
    # Fill missing values
    # --------------------------------------------------------

    X_employee = impute_features(
        X_employee,
        df
    )

    # --------------------------------------------------------
    # Prediction
    # --------------------------------------------------------

    prediction = model.predict(
        X_employee
    )[0] + 1

    prediction = int(prediction)

    # --------------------------------------------------------
    # SHAP explanation for this employee
    # --------------------------------------------------------

    shap_explanation = explain_prediction(
        model,
        X_employee,
        prediction,
        top_n=10
    )

    # --------------------------------------------------------
    # Probability
    # --------------------------------------------------------

    probabilities = None

    if hasattr(model, "predict_proba"):

        proba = model.predict_proba(
            X_employee
        )[0]

        probabilities = {
            int(class_label) + 1: float(prob)
            for class_label, prob
            in zip(model.classes_, proba)
        }

    # --------------------------------------------------------
    # Employee information
    # --------------------------------------------------------

    employee_record = processed_df.loc[
        latest_index
    ]

    latest_employee_data = str(
        employee_record["date"].date()
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    result = {

    "companyId": company_id,

    "employeeId": employee_id,

    "latest_data_date": str(
        latest_data_date.date()
    ),

    "prediction_date": str(
        prediction_date.date()
    ),

    "latest_employee_data": latest_employee_data,

    "predicted_hi": prediction,

    "probabilities": probabilities,

    "shap_explanation": shap_explanation
    }


    return result