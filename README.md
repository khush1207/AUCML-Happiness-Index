<div align="center">

# 🌟 AUCML Happiness Index 

**Employee Happiness Intelligence & Predictive Analytics System**

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg?style=for-the-badge&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-success.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg?style=for-the-badge)]()

*Predicting daily employee engagement, preventing burnout, and driving HR interventions using Machine Learning and Explainable AI.*

---
</div>

## 📖 Overview

The **AUCML Happiness Index** is a robust, end-to-end Machine Learning pipeline and web dashboard designed to predict an employee's daily **Happiness Index (HI 1-4)**. Built on a massive dataset of **2.27 Million engagement logs**, this system helps HR departments move from reactive surveys to proactive intervention.

By leveraging historical mood momentum, contextual features, and 55 distinct workplace survey factors (like eNPS, Autonomy, and Management), the deployed **Tuned XGBoost classifier** identifies employees who are thriving and those who need immediate attention. 

## ✨ Key Features

*   🎯 **High-Accuracy Predictions:** Achieves **82.35% Accuracy** and **79.16% Macro F1 Score** using a finely-tuned XGBoost model.
*   🧠 **Explainable AI (XAI):** Integrated `shap.TreeExplainer` generates dynamic feature attributions, explaining *why* an employee received a specific prediction in real-time.
*   🛡️ **Leakage-Free Architecture:** Strict chronological train/test split (80th percentile) ensures future data never bleeds into historical training sets.
*   📊 **Interactive Dashboard:** A clean, responsive HTML/JS/CSS frontend served via FastAPI to visualize company KPIs, HI distributions, and individual employee timelines.
*   🚨 **Dynamic HR Audits:** Configurable business rules flag employees needing attention (e.g., consecutive low HI votes, overdue feedback, extended inactivity).

---

## 🛠️ Tech Stack

| Category | Technologies |
| :--- | :--- |
| **Machine Learning** | XGBoost, scikit-learn, Pandas, NumPy, SHAP |
| **Backend API** | Python, FastAPI, Uvicorn |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript, Chart.js / D3 (optional) |
| **Data Processing** | Jupyter Notebooks (EDA, Preprocessing) |

---

## 🔬 Data Strategy & Preprocessing

Handling 2.27M rows of human behavioral data requires rigorous preprocessing to avoid biases and data leakage:

1.  **Chronological Ordering & Target Shifting:** Data is sorted sequentially by employee and time. The target is created by shifting the `hiVote` forward by one observation (`shift(1)`), teaching the model to predict *tomorrow's* mood based on *today's* context.
2.  **Historical Momentum:** Features like `previous_hi`, `previous_hi_avg_3`, and `previous_hi_change` capture engagement trajectories.
3.  **Score Decay (30-Day Rule):** Workplace survey scores are forward-filled but strictly masked as missing (`NaN`) if they are older than 30 days, preventing reliance on stale sentiment.
4.  **Leakage-Free Median Filling:** Missing numerical and score data are imputed using median values calculated **exclusively from the training set**.
5.  **One-Hot Encoding:** Categorical variables (`gender`, `industry`, `timezone`) are encoded using `drop_first=True` to prevent multicollinearity, resulting in an 87-column feature matrix.

---

## 📈 Model Performance

The champion model is a hyperparameter-tuned **XGBoost Classifier**. During evaluation, it demonstrated exceptional ability to capture daily engagement patterns:

*   **Accuracy:** `82.35%`
*   **Macro F1-Score:** `79.16%`
*   *Note: The deployed model (`tuned_xgboost_no_calendar.ubj`) intentionally drops calendar features (month, year, day of week) to generalize better across future timeframes without seasonal overfitting.*

---

## 🚀 Installation & Setup

Get the Happiness Index system running locally in just a few steps.

### Prerequisites
* Python 3.9+
* pip package manager

### 1. Clone the Repository
```bash
git clone https://github.com/khush1207/AUCML-Happiness-Index.git
cd AUCML-Happiness-Index
```

### 2. Create a Virtual Environment (Recommended)
```bash
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the FastAPI Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
*The dashboard will be available at `http://localhost:8000`*

---

## 📡 API Endpoints

The FastAPI backend powers the frontend with lightning-fast endpoints:

*   `GET /`: Serves the main UI.
*   `GET /api/dashboard`: Aggregates overall company KPIs and predicted trends.
*   `GET /api/employees`: Returns a searchable, paginated directory of employees.
*   `GET /api/employees/{employee_id}`: Fetches individual timelines, raw survey data, and dynamic SHAP values.
*   `POST /api/cache/refresh`: Clears the LRU cache and forces a recalculation of active state predictions.

---

## 📂 Repository Structure

```text
AUCML-Happiness-Index/
│
├── data/                   # (Ignored) Raw and processed datasets
├── models/                 
│   └── tuned_xgboost_no_calendar.ubj  # Deployed XGBoost model file
├── app/                    # FastAPI Backend Application
│   ├── main.py             # Server and endpoint definitions
│   └── model.py            # Feature builder, imputation, and inference logic
├── static/                 # Frontend Assets
│   ├── index.html
│   ├── style.css
│   └── script.js
├── notebooks/              
│   └── preprocess.ipynb    # Original EDA and pipeline engineering
├── retrain_without_calendar.py # Script for dropping time variables
├── requirements.txt        # Python dependencies
└── README.md               # You are here
```

---

## 📝 License

This project is licensed under the **MIT License**. See the `LICENSE` file for more details.

---
<div align="center">
  <b>Built with ❤️ by <a href="https://github.com/khush1207">Khush</a> for the AUCML Project</b>
</div>
