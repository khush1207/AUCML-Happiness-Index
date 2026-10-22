# AUCML — Antigravity Frontend Implementation Brief

## Goal

Create a polished, responsive **Employee Happiness Intelligence System** frontend called **AUCML** using **HTML, CSS, and JavaScript**, integrated into the existing project. The design should feel like a premium enterprise HR analytics product: calm, credible, readable, and action-oriented.

**Important:** inspect the existing project before editing. Preserve useful functionality, existing backend/API contracts, model logic, and data pipelines. Do not unnecessarily rebuild the application or invent features/data.

## Existing project structure

The current repository root contains:

```text
.idea/
.venv/
data/
models/
src/
README.md
```

Interpret these folders cautiously and inspect their contents:
- `.idea/`: IDE configuration; generally do not modify.
- `.venv/`: Python virtual environment; do not edit or commit its contents.
- `data/`: datasets and possibly processed data. Inspect filenames/schema, but do not modify source data unnecessarily or expose sensitive records.
- `models/`: saved models or model artifacts. Preserve these and inspect how the existing application loads them.
- `src/`: likely application/source code. Inspect entry points, existing frontend/backend files, prediction logic, and API routes.
- `README.md`: read first for project setup, architecture, data definitions, and run instructions.

Do not assume the project is frontend-only. If an existing Python backend (for example, Flask/FastAPI/Streamlit) serves the model or data, retain it and integrate the HTML/CSS/JS frontend using the project's existing architecture. If no backend exists, implement only what is appropriate and clearly document any integration boundary.

## Required working method

1. Read `README.md` and inspect the full `src/` structure before making changes.
2. Identify the existing stack, application entry point, available data files, employee/company identifiers, date fields, confirmed feedback fields, employment-status fields, and prediction outputs.
3. Map the requirements below to actual available fields. Do not guess column meanings.
4. Preserve existing working features and model inference.
5. Implement the frontend in the existing architecture. Prefer semantic HTML, modular CSS, and plain JavaScript unless the repository already uses a framework.
6. Separate data access/normalization from UI rendering. Reuse real API/data sources.
7. If backend data is unavailable, show a useful empty/unavailable state. Do not silently replace missing values with zero or create fake employee records.
8. Test navigation, filters, sorting, pagination, date logic, responsive layout, empty states, and browser console errors. Document any features blocked by unavailable backend fields.

## Visual design

Use a restrained enterprise visual system:
- Main workspace: warm off-white / very light beige.
- Cards and tables: white or warm white.
- Primary navigation and headings: dark navy.
- Accent: muted gold / warm amber.
- Positive indicators: muted green.
- Warnings/risks: soft orange or red.
- Borders: light grey/beige.
- Rounded corners and subtle shadows.
- Generous but efficient whitespace.

Avoid neon colors, strong gradients, heavy shadows, thick borders, oversized KPI cards, large decorative illustrations, excessive animation, cramped tables, and excessive competing colors.

Typography must be highly readable, with clear hierarchy for page title, section heading, KPI value, table headers, employee ID/name, metadata, and warning labels. Use consistent spacing, card padding, radius, button/input heights, icon sizing, and row heights. Optimize for desktop and smaller laptop screens, with sensible mobile behavior.

## Application shell and navigation

Build a persistent left sidebar with:
1. **Overview** — company summary, happiness metrics, employee overview, attention list.
2. **Employees** — searchable/filterable employee directory and employee details.
3. **Insights** — historical happiness trends, risk patterns, feedback completion/staleness.
4. **Settings** — dashboard preferences and configurable thresholds where supported.

Clearly highlight the active navigation item with a restrained navy treatment. At the sidebar bottom, show a user/profile area with role (e.g. HR Manager) only if actual identity/role information exists. Otherwise omit it or use a neutral non-personal workspace label; do not invent a signed-in user.

Top header:
- Current page title.
- Company selector, populated from real company data.
- Refresh action.
- Notification/attention indicator only if it can be backed by real calculated attention items.
- Changing the company must update every metric, chart, list, filter, and employee detail context.

## Overview page

### KPI cards

Use a compact responsive grid for:
- **Total Active Employees** — only records classified active using defensible employment-status rules. Exclude confirmed former employees. If status cannot be determined, do not silently classify all records as active.
- **Average Current HI** — average valid current Happiness Index for the active population; ignore missing/invalid values and show unavailable when no valid values exist.
- **Employees Requiring Attention** — unique active employees meeting one or more configured attention rules.
- **Low HI Employees** — active employees whose predicted HI is in the configured low range.
- **Feedback Overdue** — active employees with a confirmed feedback date older than the configured threshold.
- **Potentially Inactive / No Longer Employed** — count records meeting the six-calendar-month stale-feedback review rule, clearly distinguishing inferred inactivity from confirmed termination.

Each KPI should show a concise explanation/tooltip or supporting label describing its population and calculation. Avoid misleading zero values: unavailable data must render as “—” / “Unavailable”, not zero.

### Happiness distribution

Display the distribution of valid HI scores for the selected company and active population. Label HI categories, show employee counts and exact values/tooltips, and use restrained colors. Define category boundaries in one place and show them in Settings or supporting help text.

### Historical happiness trend

Show the historical average HI over time, ordered chronologically. Label axes/date ticks. Do not manufacture missing months or interpolate absent data in a way that implies observations exist. Visually distinguish observed historical values from model predictions. If historical records are unavailable, show a helpful empty state.

### Employees requiring attention

Show a compact table/list with:
- Employee ID.
- Current HI.
- Predicted HI.
- Last feedback date.
- Feedback age.
- Attention reason.
- Employment status.

Rows should open the real employee detail view. Provide a clear link to the complete directory.

## Employees directory

Columns:
1. Employee ID.
2. Current HI.
3. Predicted HI.
4. Prediction Date.
5. Last Feedback.
6. Feedback Age or Form Status.
7. Employment Status.
8. Attention Status.
9. View details action.

Provide:
- Search by real employee ID and employee name if present. Never create names if only IDs exist.
- Combined filters for company, employment status, HI/risk category, attention status, feedback status, missing feedback dates, and potentially inactive employees.
- Reset filters action.
- Sorting by employee ID, current HI, predicted HI, prediction date, last feedback date, feedback age, employment status, and attention priority.
- Explicit, consistent handling of missing values and dates.
- Pagination or another efficient browsing method for large datasets.
- Result count and visible filter context.
- Horizontal scrolling or responsive column handling on smaller screens.

Filters must compose together and update displayed rows and relevant counts. Sorting must be stable and must not treat missing feedback as a date from the distant past. Missing dates should be an explicit “Unknown” state; if sorted, keep missing values in a documented, consistent position.

## Prediction and cutoff date rules — critical

Maintain one backend/data-service source of truth for these values:
- `latest_data_date`
- `prediction_date`

Definitions:
- `latest_data_date` = maximum valid date in the actual combined employee dataset used for this analysis.
- `prediction_date` = exactly one calendar day after `latest_data_date`.

Example only: latest dataset date 10 Aug 2021 → prediction date 11 Aug 2021. Never hardcode this example or use today's real-world date as the prediction date.

The backend should calculate and return both clearly named values. The frontend must display those returned values and must not independently recalculate or hardcode them.

Use one date format everywhere, preferably `11 Aug 2021`. Clearly label:
- **Latest Dataset Date** — last date actually present in source data.
- **Prediction Date** — one calendar day after latest dataset date.
- **Employee Latest Data Date** — each employee's own latest record date, if useful.

Do not confuse these dates. Do not calculate feedback age relative to prediction date. When data is refreshed, refresh cached data and predictions together so the displayed dates cannot silently become stale. Show a refresh timestamp only if the system can provide a real timestamp.

## Last confirmed feedback rules

“Last Feedback” must mean the latest **valid, confirmed feedback submission date**, not simply the latest employee record date.

For each `(company_id, employee_id)`:
1. Identify actual feedback question columns or confirmed submission records from schema/metadata.
2. Determine which rows contain valid feedback according to the actual data definition.
3. Reject nulls, empty/whitespace strings, and known invalid placeholders.
4. Find the latest qualifying feedback date.
5. Group by both company ID and employee ID to avoid collisions between companies.
6. Display the same result in the directory and employee detail page.

Do not treat unrelated metadata as proof of submission. If the source does not establish that a form was submitted, display “No confirmed feedback date” / “Unverified” rather than fabricating a date. Keep this logic in the existing backend/data service when possible, not duplicated in frontend code.

## Feedback age

Calculate from the **latest actual dataset date**:

`Feedback Age = latest_data_date - last_confirmed_feedback_date`

Use actual calendar dates. Display readable labels such as:
- “On latest data date”
- “12 days since feedback”
- “4 months since feedback”

The exact display wording can be compact, but calculations must be correct. Unknown feedback dates must remain unknown, not become overdue by default.

## Six-calendar-month inactivity rule

An employee with last confirmed feedback **more than six calendar months before `latest_data_date`** should be flagged for employment-status review.

Use calendar-month arithmetic, not a fixed 180-day approximation. Implement a well-tested six-month cutoff. For example, with latest data date 10 Aug 2021:
- Feedback 15 Mar 2021 → older than six months, flag for review.
- Feedback 15 Apr 2021 → not older than six months, do not flag by this rule.

A stale feedback date does **not** prove employment termination:
- If an authoritative termination/employment-status field exists, use it to establish confirmed status.
- Otherwise label as **Potentially Inactive — Verify Employment Status**.
- Keep confirmed employment status separate from inferred inactivity.
- Missing feedback dates should be **Feedback Status Unknown / No Confirmed Feedback Date**, not automatically treated as former employees.
- Confirmed former employees must be excluded from active-workforce KPIs and current active employee risk counts, except explicitly labelled historical analyses.
- Potentially inactive records must remain clearly flagged for review and must not be silently reclassified as terminated.

## Employee detail view

Provide a detail page, drawer, or modal reachable from all employee rows. Use actual available fields only. Include:
- Employee/company identifier and authoritative employment status, if available.
- Current HI and predicted HI.
- Prediction date.
- Employee's latest data date.
- Last confirmed feedback date and feedback age.
- Attention reasons and applicable rules.
- Historical HI/feedback records when available.
- Prediction explanation only if the existing model or data pipeline can support one.

For “Why did the model make this prediction?”:
- Use existing explainability outputs if available (e.g. feature contributions).
- If no explainability method exists, state that a feature-level explanation is unavailable. Do not invent causes or present correlations as model reasoning.
- Clearly distinguish actual historical observations from predicted values.

## Insights page

Include useful, decision-oriented analyses supported by actual data:
- HI trend over time.
- Distribution by HI/risk category.
- Attention counts and reason breakdown.
- Feedback completion, missingness, and staleness.
- Company comparisons only where multiple valid companies exist.
- Potentially inactive review list.
- Historical versus predicted values clearly separated.

All charts must have meaningful labels, accessible colors, visible values/tooltips, and clear empty states. Do not create decorative charts or fabricated time-series points.

## Settings page

Where supported, allow configuration of:
- Low-HI threshold/range.
- Feedback-overdue threshold.
- Six-calendar-month inactivity rule (default six months, clearly documented).
- HI category boundaries.
- Date format or display preferences, if useful.

If settings are not persisted by the existing application, clearly label them as session-only or do not offer nonfunctional controls. Never display a control that appears to save changes if it cannot.

## Data integrity, privacy, and accessibility

- Use real dataset fields and preserve identifiers accurately.
- Do not generate mock employees, fake names, fake feedback dates, invented company data, or fabricated predictions.
- Do not expose unnecessary sensitive employee data.
- Prefer aggregate summaries and role-appropriate detail.
- Use semantic HTML, keyboard-accessible navigation and controls, visible focus states, sufficient contrast, and accessible names for icon-only buttons.
- Use responsive layout and respect reduced-motion preferences.
- Avoid unsafe HTML injection when rendering data.
- Keep secrets, environment files, and `.venv/` out of source control.
- Provide clear loading, empty, error, and unavailable states.
- Make date and risk rules understandable to HR users.

## Suggested implementation structure

Adapt this to the existing codebase rather than forcing a new structure:

```text
project-root/
├── README.md
├── data/
├── models/
└── src/
    ├── ... existing backend and model code ...
    └── frontend/              # only if appropriate for existing architecture
        ├── index.html
        ├── styles.css
        ├── app.js
        └── assets/
```

If the existing app uses templates/static assets, integrate with those instead of creating a separate frontend folder. Keep code maintainable and avoid duplicating business rules across layers.

## Definition of done

Before finishing:
- [ ] Existing project architecture and README were inspected.
- [ ] Existing features and model/data pipeline remain functional.
- [ ] Overview, Employees, Insights, and Settings navigation work.
- [ ] Company selector updates all relevant views.
- [ ] KPI calculations use consistent population rules.
- [ ] Missing/invalid metrics show unavailable states, not misleading zeros.
- [ ] Latest dataset date and prediction date are correctly sourced and consistently labelled.
- [ ] Prediction date is exactly one calendar day after latest dataset date.
- [ ] Last Feedback uses confirmed feedback evidence and groups by company + employee.
- [ ] Feedback age uses latest dataset date as its reference.
- [ ] Six-month cutoff uses calendar-month arithmetic.
- [ ] Stale feedback is not mislabeled as confirmed termination.
- [ ] Missing feedback is not automatically classified as inactive/former.
- [ ] Search, combined filters, sorting, reset, pagination, and detail navigation work.
- [ ] Charts use actual data and distinguish observations from predictions.
- [ ] Employee-level explanations are shown only when supported.
- [ ] Responsive layout, keyboard accessibility, and empty/error states are checked.
- [ ] README documents how to run the application and any unavailable integrations.

## Final deliverables

1. Implement the frontend in the existing project.
2. Keep all changes focused and explain which files were created or modified.
3. Provide exact local run instructions for the current project environment.
4. Summarize how the frontend obtains real data and predictions.
5. List any requirements that could not be implemented because the dataset/backend lacks the necessary fields.
6. Do not claim that a feature works unless it was implemented and tested.
