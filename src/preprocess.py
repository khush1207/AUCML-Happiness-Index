from pathlib import Path

import pandas as pd
import numpy as np

# Project directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"

# Combined dataset created by combine.py
COMBINED_FILE = PROCESSED_DIR / "combined_employee_engagement.csv"

# ===== ORIGINAL NOTEBOOK CELL 24 =====
# Cell 25 — Reload original dataset for corrected preprocessing

df = pd.read_csv(COMBINED_FILE)

df["date"] = pd.to_datetime(df["date"])

df = df.sort_values(
    ["companyId", "employeeId", "date"]
).reset_index(drop=True)

print("Dataset reloaded.")
print("Shape:", df.shape)

# ===== ORIGINAL NOTEBOOK CELL 25 =====
# Cell 26 — Create future HI target

df["target_hi"] = (
    df.groupby(["companyId", "employeeId"])["hiVote"]
    .shift(-1)
)

# Remove rows with no future HI response
df = df.dropna(subset=["target_hi"]).copy()

print("Rows:", len(df))
print("Missing targets:", df["target_hi"].isna().sum())

# ===== ORIGINAL NOTEBOOK CELL 26 =====
# Cell 27 — Create past HI features

df["previous_hi"] = (
    df.groupby(["companyId", "employeeId"])["hiVote"]
    .shift(1)
)

df["previous_hi_avg_3"] = (
    df.groupby(["companyId", "employeeId"])["hiVote"]
    .transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
)

df["previous_hi_change"] = (
        df["previous_hi"] - df["previous_hi_avg_3"]
)

print("Past HI features created.")

# ===== ORIGINAL NOTEBOOK CELL 27 =====
# Cell 28 — Create time features

df["month"] = df["date"].dt.month
df["day_of_week"] = df["date"].dt.dayofweek
df["year"] = df["date"].dt.year

print(df[["date", "month", "day_of_week", "year"]].head())

# ===== ORIGINAL NOTEBOOK CELL 28 =====
# Cell 29 — Create employee tenure

df["hiringDate"] = pd.to_datetime(df["hiringDate"], errors="coerce")

df["tenure_years"] = (
        (df["date"] - df["hiringDate"]).dt.days / 365.25
)

# Remove unrealistic values
df.loc[
    (df["tenure_years"] < 0) | (df["tenure_years"] > 50),
    "tenure_years"
] = np.nan

print(df["tenure_years"].describe())

# ===== ORIGINAL NOTEBOOK CELL 29 =====
# Cell 30 — Identify Score features

score_columns = [
    col for col in df.columns
    if col not in [
        "companyId", "employeeId", "gender", "hiringDate",
        "birthDate", "deleted", "deletionDate", "industry",
        "timezone", "departmentId", "date", "hiVote",
        "target_hi", "previous_hi", "previous_hi_avg_3",
        "previous_hi_change", "month", "day_of_week",
        "year", "tenure_years"
    ]
]

print("Number of Score features:", len(score_columns))

# ===== ORIGINAL NOTEBOOK CELL 30 =====
# Cell 31 — Identify actual Score response dates

score_available = df[score_columns].notna().any(axis=1)

df["score_response_date"] = df["date"].where(score_available)

print("Rows with Score responses:", score_available.sum())

# ===== ORIGINAL NOTEBOOK CELL 31 =====
# Cell 32 — Find the last Score response date

df["last_score_date"] = (
    df.groupby(["companyId", "employeeId"])["score_response_date"]
    .ffill()
)

print(df[["date", "score_response_date", "last_score_date"]].head(10))

# ===== ORIGINAL NOTEBOOK CELL 32 =====
# Cell 33 — Calculate how old the previous Score response is

df["score_age_days"] = (
        df["date"] - df["last_score_date"]
).dt.days

print(df["score_age_days"].describe())

# ===== ORIGINAL NOTEBOOK CELL 33 =====
# Cell 34 — Keep Score information from the previous 30 days

for col in score_columns:
    df.loc[df["score_age_days"] > 30, col] = np.nan

print("Score values remaining after 30-day cutoff:",
      df[score_columns].notna().sum().sum())

# ===== ORIGINAL NOTEBOOK CELL 34 =====
# Cell 35 — Create recent Score availability flag

df["has_recent_score"] = (
    df[score_columns].notna().any(axis=1).astype(int)
)

print(df["has_recent_score"].value_counts())

# ===== ORIGINAL NOTEBOOK CELL 35 =====
# Cell 36 — Select final features

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

# Keep Score questions as features
feature_columns = (
        numerical_features
        + categorical_features
        + score_columns
        + ["has_recent_score"]
)

print("Total features:", len(feature_columns))

# ===== ORIGINAL NOTEBOOK CELL 36 =====
# Cell 37 — Create feature matrix and target

X = df[feature_columns].copy()
y = df["target_hi"].astype(int)

print("X shape:", X.shape)
print("y shape:", y.shape)
print("\nTarget distribution:")
print(y.value_counts().sort_index())

# ===== ORIGINAL NOTEBOOK CELL 37 =====
# Cell 38 — Time-based train/test split

split_date = df["date"].quantile(0.80)

train_mask = df["date"] <= split_date
test_mask = df["date"] > split_date

X_train = X.loc[train_mask]
X_test = X.loc[test_mask]

y_train = y.loc[train_mask]
y_test = y.loc[test_mask]

print("Split date:", split_date)
print("Training rows:", len(X_train))
print("Testing rows:", len(X_test))

# ===== ORIGINAL NOTEBOOK CELL 38 =====
# Cell 39 — Encode categorical features

X_train = pd.get_dummies(
    X_train,
    columns=categorical_features,
    drop_first=True
)

X_test = pd.get_dummies(
    X_test,
    columns=categorical_features,
    drop_first=True
)

# Make sure both sets have the same columns
X_train, X_test = X_train.align(
    X_test,
    join="left",
    axis=1,
    fill_value=0
)

print("X_train shape:", X_train.shape)
print("X_test shape:", X_test.shape)

# ===== ORIGINAL NOTEBOOK CELL 39 =====
# Cell 40 — Check final missing values

print("Missing values in X_train:", X_train.isna().sum().sum())
print("Missing values in X_test:", X_test.isna().sum().sum())

# ===== ORIGINAL NOTEBOOK CELL 40 =====
# Cell 41 — Impute remaining Score values

for col in score_columns:
    median_value = X_train[col].median()

    X_train[col] = X_train[col].fillna(median_value)
    X_test[col] = X_test[col].fillna(median_value)

print("Missing values in X_train:", X_train.isna().sum().sum())
print("Missing values in X_test:", X_test.isna().sum().sum())

# ===== ORIGINAL NOTEBOOK CELL 41 =====
# Cell 42 — Find remaining missing values

missing_train = X_train.isna().sum()

print(
    missing_train[missing_train > 0]
    .sort_values(ascending=False)
)

# ===== ORIGINAL NOTEBOOK CELL 42 =====
# Cell 43 — Impute remaining numerical features

remaining_numeric = [
    "tenure_years",
    "previous_hi",
    "previous_hi_avg_3",
    "previous_hi_change"
]

for col in remaining_numeric:
    median_value = X_train[col].median()

    X_train[col] = X_train[col].fillna(median_value)
    X_test[col] = X_test[col].fillna(median_value)

print("Missing values in X_train:", X_train.isna().sum().sum())
print("Missing values in X_test:", X_test.isna().sum().sum())

# ===== ORIGINAL NOTEBOOK CELL 43 =====
# Cell 44 — Final preprocessing check

print("X_train:", X_train.shape)
print("X_test:", X_test.shape)
print("y_train:", y_train.shape)
print("y_test:", y_test.shape)

print("\nMissing values:")
print("X_train:", X_train.isna().sum().sum())
print("X_test:", X_test.isna().sum().sum())

print("\nTarget classes:")
print(sorted(y_train.unique()))
