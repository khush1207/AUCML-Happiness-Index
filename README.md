# Predicting the Next HI Level

## Overview

This project predicts an employee's **next available HI observation** from information that was available beforehand. HI is the daily Happyforce question, “How do you feel today?” and has four classes (HI 1–HI 4).

The work combines employee, company, HI, and workplace Score data; builds time-aware features; evaluates multiple classification models; and explains the selected model with SHAP. The final model is **Tuned XGBoost**.

> **In brief:** On an untouched chronological test set of 449,778 observations, the final model achieved **82.35% accuracy** and **79.16% Macro F1**. Recent HI history was the strongest predictive signal in the SHAP analysis.

## Results at a Glance

| Final model | Primary metric | Test result | Evaluation set |
|---|---|---:|---|
| Tuned XGBoost | Macro F1 | **79.16%** | Untouched temporal test set (449,778 observations) |

| Metric | Score |
|---|---:|
| Accuracy | **82.35%** |
| Macro Precision | **81.63%** |
| Macro Recall | **77.37%** |
| Macro F1 | **79.16%** |
| Weighted F1 | **82.04%** |

Macro F1 is the primary metric because the four HI classes are unevenly distributed. Unlike accuracy alone, it gives each class equal weight.

## Dataset

The project uses the Happyforce dataset, a collection of employee-engagement responses across companies. In addition to the daily HI question, the dataset includes workplace **Score** responses. Scores cover six themes: Motivation, Relationships, Feedback, Alignment, Wellness, and Reward and Recognition. Employees also receive an eNPS question every three months.

The raw dataset is composed of five files:

| File | Purpose |
|---|---|
| `companyMetadata.csv` | Company identifiers, industry, and timezone metadata |
| `employees.csv` | Employee metadata, including available hiring date, birth date, gender, and status fields |
| `hiVotes.csv` | Daily HI responses |
| `scoreVotes.csv` | Workplace Score responses |
| `scoreMetadata.csv` | Score, factor, and question metadata |

The project creates `combined_employee_engagement.csv` by merging these sources. `step1_employees_company.csv` is an intermediate file created while combining employee and company data.

### Data notes

- Not every company has Scores enabled, and not every employee has available demographic or hiring-date data.
- An employee deletion field does not necessarily indicate that the employee left the company.
- Identifiers and deletion-related fields are excluded from the final feature matrix.

## Project Files and Workflow

Run the notebooks from the project directory so that their relative file paths resolve correctly.

| Order | Notebook | Role |
|---:|---|---|
| 1 | `combine.ipynb` | Merges source data and creates `combined_employee_engagement.csv` |
| 2 | `EDA.ipynb` | Examines structure, missingness, HI distributions, Score coverage, dates, and data quality |
| 3 | `preprocess.ipynb` | Builds features, performs the temporal split and validation checks, trains and compares models, evaluates the final model, and runs SHAP analysis |

The notebooks use Python with `pandas`, `numpy`, `matplotlib`, `seaborn`, scikit-learn, XGBoost, CatBoost, imbalanced-learn, and SHAP. The archive does not provide a pinned dependency file, so package versions are not specified here.

## Modeling Approach

### How the data was prepared

Before training the models, the project turned the raw employee records into a prediction-ready dataset without using information from the future.

In plain language, the process was:

1. **Put each employee’s responses in time order.** Records were ordered by company, employee, and date.
2. **Define the prediction task.** For each HI response, the model’s target was that employee’s next available HI response. Records without a later HI response were removed because there was nothing to predict.
3. **Summarize recent HI history.** The model received the previous HI value, the average of the previous three HI values, and the difference between the previous HI value and that recent average. This lets it recognize recent engagement patterns without seeing the future answer.
4. **Add useful context.** The dataset includes the month, day of week, year, employee tenure, gender, industry, timezone, the workplace Score-question responses, and whether a recent Score response was available.
5. **Keep Score responses current.** A Score response was retained only when it was within 30 days of the HI record. Older Score values were treated as unavailable, preventing stale survey responses from being used as current information.
6. **Handle missing values and categories.** Categories were converted into model-ready indicator columns. Missing Score and numerical values were filled with median values calculated from the training data.
7. **Separate past from future.** The data was split by date: older observations trained the models and later observations were reserved for final testing.

This is important because an engagement prediction model should be evaluated as it would be used in practice: predicting a future HI level using only information already available at that point in time.

### Technical preprocessing details

The preprocessing notebook sorts records by `companyId`, `employeeId`, and `date`, then creates `target_hi` by shifting `hiVote` one observation forward within each employee-company group. The historical HI features are created with lagged values and a shifted rolling average over the previous three HI observations.

`tenure_years` is calculated from the HI record date and `hiringDate`. Tenure values below zero or above 50 years are set to missing. Score response dates are tracked per employee-company group; Score values with `score_age_days` greater than 30 are set to missing, and `has_recent_score` identifies records with at least one remaining Score value.

The final feature matrix excludes the target, current HI value, identifiers, and deletion-related fields. Gender, industry, and timezone are one-hot encoded. The training and test feature matrices are aligned to the same columns; missing Score values and remaining numerical values are imputed using medians from the training data.

### Target and features

The target is the **next available HI observation** for the same employee and company. Rows without a future HI observation are excluded.

The final feature set includes:

- Historical HI features: `previous_hi`, `previous_hi_avg_3`, and `previous_hi_change`
- Time features: month, day of week, and year
- Employee tenure in years
- Categorical context: gender, industry, and timezone
- Workplace Score-question features and `has_recent_score`

### Temporal split

The data is split chronologically so that all training observations occur before test observations.

| Set | Date range | Rows |
|---|---|---:|
| Training | 2016-02-01 to 2021-01-06 | 1,804,056 |
| Testing | 2021-01-07 to 2021-08-10 | 449,778 |

## Temporal Validation and Leakage Prevention

The preprocessing pipeline was checked to confirm that features use only information available before the outcome being predicted.

### Target validation

| Check | Result |
|---|---:|
| Future target observations checked | 2,253,834 |
| Target-date violations | 0 |

Every target HI observation occurs after its corresponding feature observation.

### Historical HI feature validation

The historical HI features were independently reconstructed and compared with their final preprocessing values.

| Feature | Rows checked | Mismatches |
|---|---:|---:|
| `previous_hi` | 2,235,338 | 0 |
| `previous_hi_avg_3` | 2,235,338 | 0 |
| `previous_hi_change` | 2,235,338 | 0 |

### Score feature validation

| Check | Result |
|---|---:|
| Score responses checked | 146,880 |
| Future Score-response violations | 0 |
| Previous Score observations checked | 618,007 |
| Future `last_score_date` violations | 0 |
| Score-age calculation mismatches | 0 |
| Rows with Score age > 30 days | 178,965 |
| Score values remaining after 30-day cutoff | 0 |
| `has_recent_score` mismatches | 0 |

The final feature matrix was also checked to confirm that `hiVote`, `target_hi`, `companyId`, `employeeId`, `deleted`, and `deletionDate` were absent from `X_train`.

**Verification result: PASSED.** All automated temporal-validity and data-leakage checks passed, and no data or model objects were modified during verification.

## Model Comparison

Multiple baseline models and experimental configurations were evaluated on the untouched temporal test set.

| Experiment | Model | Accuracy | Macro Precision | Macro Recall | Macro F1 | Weighted F1 |
|---|---|---:|---:|---:|---:|---:|
| Baseline | HistGradientBoosting | 82.31% | 81.42% | 77.48% | **79.16%** | 82.03% |
| **Final model** | **Tuned XGBoost** | **82.35%** | **81.63%** | 77.37% | **79.16%** | **82.04%** |
| Baseline | XGBoost | 82.35% | 81.53% | 77.42% | 79.15% | 82.04% |
| TF-IDF + Tuned XGBoost | XGBoost | 82.34% | 81.70% | 77.31% | 79.14% | 82.02% |
| Tuned XGBoost + SMOTETomek | XGBoost | 82.27% | 80.92% | 77.80% | 79.13% | 81.99% |
| Baseline | CatBoost | 82.37% | 81.47% | 77.46% | 79.12% | 82.03% |
| Untuned XGBoost + SMOTETomek | XGBoost | 82.15% | 80.37% | 78.08% | 79.09% | 81.94% |
| Baseline | Random Forest | 80.71% | 79.71% | 75.51% | 77.29% | 80.40% |
| Baseline | Logistic Regression | 80.00% | 78.28% | 72.83% | 73.78% | 78.82% |
| Baseline | Decision Tree | 73.24% | 70.34% | 69.86% | 70.07% | 73.28% |
| Baseline | Linear SVM | 75.61% | 83.01% | 64.26% | 60.73% | 70.02% |
| Baseline | Naive Bayes | 40.91% | 40.40% | 43.22% | 37.99% | 37.74% |

Tree-based ensemble models performed best overall. XGBoost, HistGradientBoosting, and CatBoost produced very similar results.

### Hyperparameter tuning

XGBoost, CatBoost, and HistGradientBoosting were tuned using a validation split from the training data. The selected XGBoost configuration was:

```text
n_estimators = 400
max_depth = 5
learning_rate = 0.07
min_child_weight = 5
subsample = 0.8
colsample_bytree = 0.8
gamma = 0.1
reg_lambda = 5
```

This configuration achieved **80.76% Macro F1** on the validation split. On the untouched temporal test set, baseline XGBoost achieved **79.15% Macro F1** and tuned XGBoost achieved **79.16%**. The validation improvement therefore did not materially generalize to the final test set; this is reported as an experimental finding, not as a substantial gain from tuning.

Tuned XGBoost was retained as the final model because it matched the best observed Macro F1, had strong overall precision, recall, and accuracy, and was used for the SHAP analysis.

### Additional experiments

**SMOTETomek.** To address class imbalance, SMOTETomek was evaluated on a 500,000-row stratified subset of the training data because applying it to the full training set was computationally costly. Tuned XGBoost with SMOTETomek achieved 82.27% accuracy and 79.13% Macro F1. It did not materially improve Macro F1 and was not included in the final pipeline. This subset-based experiment is not a full-training-data comparison with the final model.

**TF-IDF.** TF-IDF representations of the 55 Score-question texts were added to the existing numerical and categorical features. The resulting model achieved 82.34% accuracy and 79.14% Macro F1. TF-IDF did not improve Macro F1 and was excluded from the final pipeline.

## Final Model Evaluation

The selected Tuned XGBoost model was evaluated on the untouched temporal test set.

### Per-class performance

| Class | Precision | Recall | F1-score |
|---|---:|---:|---:|
| HI 1 | 84.53% | 77.07% | 80.63% |
| HI 2 | 72.91% | 57.62% | 64.37% |
| HI 3 | 80.38% | 89.80% | 84.83% |
| HI 4 | 88.69% | 85.00% | 86.80% |

The model performs most strongly on HI 3 and HI 4. HI 2 is the most difficult class to predict, with the lowest recall (57.62%) and F1-score (64.37%).

### Confusion matrix

| Actual / Predicted | HI 1 | HI 2 | HI 3 | HI 4 |
|---|---:|---:|---:|---:|
| **HI 1** | 40,191 | 4,913 | 5,526 | 1,520 |
| **HI 2** | 4,358 | 36,637 | 20,337 | 2,252 |
| **HI 3** | 1,984 | 7,780 | 180,143 | 10,689 |
| **HI 4** | 1,011 | 917 | 18,096 | 113,424 |

Most predictions fall on the main diagonal, indicating correct classification. The largest cross-class confusion is between HI 2 and HI 3, consistent with HI 2’s lower recall.

## Explainability with SHAP

SHAP (SHapley Additive exPlanations) was applied to the final Tuned XGBoost model to quantify how features contributed to its predictions. A random sample of 10,000 observations from the untouched test set was used only for interpretability; it did not affect model training or final evaluation.

| Parameter | Value |
|---|---:|
| Test observations | 449,778 |
| SHAP sample | 10,000 |
| Features | 87 |
| Output classes | 4 |
| SHAP output shape | `(10,000, 87, 4)` |
| Explainer | TreeExplainer |

### Global feature importance

Global importance is the mean absolute SHAP value across the sampled observations and all four HI classes.

| Rank | Feature | Mean \|SHAP\| |
|---:|---|---:|
| 1 | `previous_hi_avg_3` | 0.939364 |
| 2 | `previous_hi` | 0.344793 |
| 3 | `year` | 0.089632 |
| 4 | `previous_hi_change` | 0.087665 |
| 5 | `tenure_years` | 0.044939 |
| 6 | `day_of_week` | 0.036708 |
| 7 | `industry_MANUFACTURING` | 0.029342 |
| 8 | `month` | 0.028628 |
| 9 | `industry_FINANCIAL_SERVICES_INSURANCE` | 0.025921 |
| 10 | `timezone_Europe/Madrid` | 0.023133 |
| 11 | `gender_Male` | 0.022346 |
| 12 | `industry_HEALTH_CARE_SOCIAL_ASSISTANCE` | 0.019346 |
| 13 | `gender_Mujer` | 0.019199 |
| 14 | `timezone_Europe/Warsaw` | 0.016934 |
| 15 | `has_recent_score` | 0.013488 |

Recent historical HI features are the dominant inputs to the model. In particular, `previous_hi_avg_3` has the largest contribution, followed by `previous_hi`.

### HI 2-specific analysis

Because HI 2 had the lowest F1-score, a class-specific SHAP analysis was performed.

| Rank | Feature | Mean \|SHAP\| |
|---:|---|---:|
| 1 | `previous_hi_avg_3` | 0.841838 |
| 2 | `previous_hi` | 0.230649 |
| 3 | `day_of_week` | 0.045149 |
| 4 | `previous_hi_change` | 0.040898 |
| 5 | `timezone_Europe/Madrid` | 0.039434 |
| 6 | `tenure_years` | 0.036769 |
| 7 | `year` | 0.032639 |
| 8 | `industry_COMPUTER_SOFTWARE_IT_SERVICES` | 0.031404 |
| 9 | `month` | 0.029232 |
| 10 | `gender_Mujer` | 0.023404 |

The same pattern holds for HI 2: recent historical HI features have substantially larger SHAP contributions than the other feature groups.

### Workplace Score questions

The 55 workplace Score-question features were also assessed separately using the Score metadata.

| Rank | Factor | Question | Mean \|SHAP\| |
|---:|---|---|---:|
| 1 | eNPS | Employee Net Promoter Score (eNPS) | 0.003095 |
| 2 | Active Listening | Company values my opinions and suggestions | 0.001911 |
| 3 | Environment | I have all the information I need to make decisions | 0.001376 |
| 4 | Mastery | My manager encourages my development | 0.001323 |
| 5 | Compensation | I would rate the processes for determining pay | 0.001138 |
| 6 | Recognition | Company encourages us to give recognition | 0.001110 |
| 7 | Freedom of Opinion | I feel like I can voice my opinion regarding issues | 0.001089 |
| 8 | Managers | My manager helps bring the best out of people | 0.001045 |
| 9 | Peers | Company is the kind of place where I have workplace friends | 0.001006 |
| 10 | Values & Ethics | The values of the company are aligned with my values | 0.000935 |

eNPS had the highest importance among workplace Score questions (0.003095), but this is much smaller than the strongest historical HI feature, `previous_hi_avg_3` (0.939364). Historical engagement patterns are therefore much more influential to this model than individual workplace survey variables.

![SHAP Summary Plot](image.png)

### Interpreting these results

SHAP describes feature importance within this trained model. It does **not** establish that a feature causes an employee’s engagement to increase or decrease.

## Key Findings

- Tuned XGBoost achieved **82.35% accuracy** and **79.16% Macro F1** on the untouched temporal test set.
- Tree-based ensemble models were the strongest overall performers, with XGBoost, HistGradientBoosting, and CatBoost producing similar results.
- Hyperparameter tuning made only a marginal difference to final test Macro F1.
- Neither SMOTETomek nor TF-IDF features materially improved Macro F1, so neither was included in the final pipeline.
- HI 2 was the most challenging class to predict; HI 3 had the highest recall (89.80%).
- Historical HI features were far more influential than individual workplace Score-question features in the SHAP analysis.

## Project Status

The data pipeline, model comparison, final temporal evaluation, and SHAP-based explainability analysis are complete. The reported final model is **Tuned XGBoost**, evaluated on an untouched temporal test set.

---

## AUCML — Employee Happiness Intelligence System (Frontend & API)

An enterprise HR analytics web dashboard powered by FastAPI and the Tuned XGBoost prediction pipeline.

### Running the Application

1. **Activate the environment and start the server:**

   ```bash
   # From the project root
   python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
   ```

2. **Access the application:**
   - Open your web browser and navigate to: **`http://127.0.0.1:8000`**
   - The interactive dashboard will load directly.
   - Interactive API documentation is available at **`http://127.0.0.1:8000/docs`**.

### Frontend Structure

```text
src/
├── main.py               # FastAPI backend, prediction snapshot caching, API endpoints
├── model.py              # XGBoost loading, feature engineering, and SHAP explanation
├── preprocess.py         # Pipeline data transformation reference
└── frontend/             # Single-page enterprise frontend
    ├── index.html        # Semantic HTML5 layout (Overview, Employees, Insights, Settings, Drawer)
    ├── styles.css        # Enterprise design system (Navy, warm off-white, muted gold, status badges)
    └── app.js            # Reactive state management, client API connector, charts, filters, export
```

### Business Rules Implemented

- **Prediction & Dataset Dates:** Sourced directly from the dataset. `latest_data_date` is the maximum date in the dataset (`2021-08-11`). `prediction_date` is strictly one calendar day after (`2021-08-12`).
- **Active Workforce Population:** Calculated using authoritative `deleted` and `deletionDate` fields. Records with `deleted == True` or `deletionDate` present are classified as **Confirmed Former Employees** and excluded from active workforce metrics and risk counts. Records with `deleted is null` are marked as **Status Unknown** and also excluded from active workforce calculations.
- **Confirmed Feedback Date:** Grouped by `(companyId, employeeId)`. Only rows with valid workplace survey score submissions (`score_response_date` / `last_score_date`) qualify as confirmed feedback. Records without survey submissions are displayed as `Unverified` / `No confirmed feedback date` and never defaulted to overdue.
- **Feedback Age:** Computed strictly relative to the dataset cutoff date (`latest_data_date - last_feedback_date`), never today's real-world date.
- **Six-Calendar-Month Inactivity Rule:** Implemented via calendar-month arithmetic (`cutoff - pd.DateOffset(months=6)`, resulting in `2021-02-11`). Active employees whose last confirmed feedback is older than this date are flagged as **Potentially Inactive — Verify Employment Status** for HR audit, without assuming termination.
- **Model Explainability:** Employee detail drawer displays local feature attribution via SHAP TreeExplainer, clearly disclaimed as statistical model attribution rather than causal claims.

### Limitations & Unavailable Dataset Fields

- **Employee & Department Names:** The underlying dataset provides anonymized numeric `employeeId` and alphanumeric `departmentId`. No personal names or plain-text department labels are fabricated; real IDs are used throughout.
- **Identity/Role Information:** No authenticated user profile or personal identity exists in the dataset; a neutral workspace label (`AUCML HR Analytics Workspace`) is displayed rather than inventing a signed-in user.

