/**
 * AUCML — Employee Happiness Intelligence System
 * Frontend Application Controller
 */

(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // Global Application State
  // ---------------------------------------------------------------------------
  const state = {
    activePage: 'overview',
    selectedCompany: '',
    companies: [],
    dates: {
      latestDataDate: '',
      predictionDate: '',
      sixMonthCutoff: '',
    },
    dashboard: null,
    insights: null,
    directory: {
      search: '',
      status: 'active',
      risk: 'all',
      attention: 'all',
      feedbackStatus: 'all',
      sortBy: 'attention_priority',
      sortDir: 'asc',
      page: 1,
      pageSize: 25,
      totalCount: 0,
      filteredCount: 0,
      totalPages: 1,
      employees: [],
    },
    settings: {
      lowHiThreshold: 2,
      feedbackOverdueDays: 30,
      inactivityMonths: 6,
      dateFormat: 'DD Mon YYYY',
    },
    distributionMode: 'current', // 'current' or 'predicted'
    isLoading: false,
    activeEmployeeModal: null,
  };

  // ---------------------------------------------------------------------------
  // Date Formatting Utilities
  // ---------------------------------------------------------------------------
  const MONTH_NAMES_SHORT = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
  ];

  function formatDate(isoStr) {
    if (!isoStr || isoStr === 'null' || isoStr === 'undefined') {
      return '—';
    }
    const parts = isoStr.split('-');
    if (parts.length !== 3) return isoStr;
    const year = parseInt(parts[0], 10);
    const monthIndex = parseInt(parts[1], 10) - 1;
    const day = parseInt(parts[2], 10);

    if (isNaN(year) || isNaN(monthIndex) || isNaN(day)) return isoStr;

    if (state.settings.dateFormat === 'YYYY-MM-DD') {
      return isoStr;
    }
    if (state.settings.dateFormat === 'MM/DD/YYYY') {
      const mm = String(monthIndex + 1).padStart(2, '0');
      const dd = String(day).padStart(2, '0');
      return `${mm}/${dd}/${year}`;
    }
    // Default: 'DD Mon YYYY' e.g. 11 Aug 2021
    const monthName = MONTH_NAMES_SHORT[monthIndex] || parts[1];
    return `${day} ${monthName} ${year}`;
  }

  function formatFeedbackAge(days) {
    if (days === null || days === undefined) {
      return 'Not applicable';
    }
    if (days === 0) {
      return 'On latest data date';
    }
    if (days === 1) {
      return '1 day since feedback';
    }
    if (days < 30) {
      return `${days} days since feedback`;
    }
    const months = Math.round(days / 30.4375 * 10) / 10;
    if (Number.isInteger(months)) {
      return `${months} months since feedback`;
    }
    return `${months.toFixed(1)} months since feedback`;
  }

  function getHiLabel(hi) {
    switch (Number(hi)) {
      case 1: return 'HI 1: Very Low (Critical)';
      case 2: return 'HI 2: Low (At Risk)';
      case 3: return 'HI 3: Moderate (Satisfied)';
      case 4: return 'HI 4: High (Thriving)';
      default: return 'HI Unknown';
    }
  }

  function getHiBadgeClass(hi) {
    switch (Number(hi)) {
      case 1: return 'hi-1-badge';
      case 2: return 'hi-2-badge';
      case 3: return 'hi-3-badge';
      case 4: return 'hi-4-badge';
      default: return 'badge-neutral';
    }
  }

  // ---------------------------------------------------------------------------
  // API Calls
  // ---------------------------------------------------------------------------
  async function fetchCompanies() {
    setLoading(true, 'Loading company workforce data...');
    try {
      const res = await fetch('/api/companies');
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load companies`);
      const data = await res.json();
      state.companies = data.companies || [];
      state.dates.latestDataDate = data.latest_data_date;
      state.dates.predictionDate = data.prediction_date;
      state.dates.sixMonthCutoff = data.six_month_cutoff;

      updateReferenceDates();
      renderCompanySelector();

      if (state.companies.length > 0 && !state.selectedCompany) {
        state.selectedCompany = state.companies[0].id;
        document.getElementById('company-select').value = state.selectedCompany;
      }

      if (state.selectedCompany) {
        await reloadAllData();
      }
    } catch (err) {
      console.error('fetchCompanies error:', err);
      showToast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  }

  async function fetchDashboard() {
    if (!state.selectedCompany) return;
    try {
      const q = new URLSearchParams({
        company_id: state.selectedCompany,
        low_hi_threshold: String(state.settings.lowHiThreshold),
        feedback_overdue_days: String(state.settings.feedbackOverdueDays),
        inactivity_months: String(state.settings.inactivityMonths),
      });
      const res = await fetch(`/api/dashboard?${q.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load dashboard`);
      state.dashboard = await res.json();
      renderDashboard();
    } catch (err) {
      console.error('fetchDashboard error:', err);
      showToast(err.message, 'error');
    }
  }

  async function fetchEmployees() {
    if (!state.selectedCompany) return;
    try {
      const q = new URLSearchParams({
        company_id: state.selectedCompany,
        search: state.directory.search,
        status: state.directory.status,
        risk: state.directory.risk,
        attention: state.directory.attention,
        feedback_status: state.directory.feedbackStatus,
        sort_by: state.directory.sortBy,
        sort_dir: state.directory.sortDir,
        page: String(state.directory.page),
        page_size: String(state.directory.pageSize),
        low_hi_threshold: String(state.settings.lowHiThreshold),
        feedback_overdue_days: String(state.settings.feedbackOverdueDays),
        inactivity_months: String(state.settings.inactivityMonths),
      });
      const res = await fetch(`/api/employees?${q.toString()}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load employees`);
      const data = await res.json();
      state.directory.totalCount = data.total_count;
      state.directory.filteredCount = data.filtered_count;
      state.directory.page = data.page;
      state.directory.pageSize = data.page_size;
      state.directory.totalPages = data.total_pages;
      state.directory.employees = data.employees || [];

      renderDirectoryTable();
      renderPagination();
      renderActiveFilterTags();
    } catch (err) {
      console.error('fetchEmployees error:', err);
      showToast(err.message, 'error');
    }
  }

  async function fetchInsights() {
    if (!state.selectedCompany) return;
    try {
      const res = await fetch(`/api/insights?company_id=${encodeURIComponent(state.selectedCompany)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load insights`);
      state.insights = await res.json();
      renderInsights();
    } catch (err) {
      console.error('fetchInsights error:', err);
      showToast(err.message, 'error');
    }
  }

  async function fetchEmployeeDetail(employeeId) {
    if (!state.selectedCompany || !employeeId) return null;
    try {
      const res = await fetch(`/api/employees/${encodeURIComponent(employeeId)}?company_id=${encodeURIComponent(state.selectedCompany)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to load employee details`);
      return await res.json();
    } catch (err) {
      console.error('fetchEmployeeDetail error:', err);
      showToast(err.message, 'error');
      return null;
    }
  }

  async function refreshCache() {
    const btn = document.getElementById('btn-refresh');
    btn.classList.add('refreshing');
    btn.disabled = true;
    setLoading(true, 'Refreshing dataset snapshot and model predictions...');
    try {
      const res = await fetch('/api/cache/refresh', { method: 'POST' });
      if (!res.ok) throw new Error('Failed to refresh cache');
      showToast('Cache cleared. Rebuilding predictions snapshot...', 'success');
      await fetchCompanies();
      showToast('Workforce predictions successfully updated.', 'success');
    } catch (err) {
      console.error('refreshCache error:', err);
      showToast(err.message, 'error');
    } finally {
      btn.classList.remove('refreshing');
      btn.disabled = false;
      setLoading(false);
    }
  }

  async function reloadAllData() {
    if (!state.selectedCompany) return;
    setLoading(true, 'Loading company analytics...');
    try {
      await Promise.all([
        fetchDashboard(),
        fetchEmployees(),
        fetchInsights(),
      ]);
    } finally {
      setLoading(false);
    }
  }

  // ---------------------------------------------------------------------------
  // UI Renderers: Reference Dates & Company Selector
  // ---------------------------------------------------------------------------
  function updateReferenceDates() {
    const latestFormatted = formatDate(state.dates.latestDataDate);
    const predFormatted = formatDate(state.dates.predictionDate);
    const cutoffFormatted = formatDate(state.dates.sixMonthCutoff);

    document.getElementById('banner-latest-date').textContent = latestFormatted;
    document.getElementById('banner-pred-date').textContent = predFormatted;
    document.getElementById('banner-cutoff-date').textContent = cutoffFormatted;

    document.getElementById('sidebar-latest-date').textContent = latestFormatted;
    document.getElementById('sidebar-pred-date').textContent = predFormatted;
  }

  function renderCompanySelector() {
    const select = document.getElementById('company-select');
    select.innerHTML = '';

    if (state.companies.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = 'No companies available';
      select.appendChild(opt);
      return;
    }

    state.companies.forEach((comp) => {
      const opt = document.createElement('option');
      opt.value = comp.id;
      opt.textContent = `${comp.name} (${comp.active_employees} active · avg HI ${comp.average_hi ?? '—'})`;
      select.appendChild(opt);
    });

    if (state.selectedCompany) {
      select.value = state.selectedCompany;
    }
  }

  // ---------------------------------------------------------------------------
  // UI Renderers: Overview Page & KPIs
  // ---------------------------------------------------------------------------
  function renderDashboard() {
    const d = state.dashboard;
    if (!d) return;

    // Header & Banner updates
    document.getElementById('header-attention-count').textContent = d.attention_count ?? 0;
    document.getElementById('banner-industry').textContent = d.industry || 'Unspecified';
    document.getElementById('banner-timezone').textContent = d.timezone || 'Unspecified';

    // Sidebar counter
    document.getElementById('sidebar-employee-count').textContent = d.total_active_employees ?? '—';

    // KPI 1: Total Active Employees
    document.getElementById('kpi-active-employees').textContent = (d.total_active_employees !== null && d.total_active_employees !== undefined)
      ? d.total_active_employees.toLocaleString()
      : '—';
    document.getElementById('kpi-former-employees').textContent =
      `Former: ${d.total_former_employees ?? 0} · Unknown: ${d.total_unknown_employees ?? 0}`;

    // KPI 2: Average Current HI
    const avgHiEl = document.getElementById('kpi-average-hi');
    if (d.average_hi !== null && d.average_hi !== undefined) {
      avgHiEl.textContent = d.average_hi.toFixed(2);
      const hiScore = Number(d.average_hi);
      const qualityEl = document.getElementById('kpi-hi-quality');
      if (hiScore >= 3.5) qualityEl.textContent = 'High Engagement Baseline';
      else if (hiScore >= 2.8) qualityEl.textContent = 'Moderate Engagement Baseline';
      else qualityEl.textContent = 'At-Risk Engagement Baseline';
    } else {
      avgHiEl.textContent = '—';
      document.getElementById('kpi-hi-quality').textContent = 'No recorded HI votes';
    }

    // KPI 3: Requiring Attention
    const attCountEl = document.getElementById('kpi-attention-count');
    attCountEl.textContent = d.attention_count !== null ? d.attention_count.toLocaleString() : '—';
    const attPctEl = document.getElementById('kpi-attention-percent');
    attPctEl.textContent = (d.attention_percent !== null && d.attention_percent !== undefined)
      ? `${d.attention_percent}% of active`
      : '—% of active';

    // KPI 4: Low Predicted HI
    document.getElementById('kpi-low-hi-count').textContent = d.low_hi_count !== null ? d.low_hi_count.toLocaleString() : '—';

    // KPI 5: Feedback Overdue
    document.getElementById('kpi-overdue-count').textContent = d.feedback_overdue_count !== null ? d.feedback_overdue_count.toLocaleString() : '—';
    document.getElementById('kpi-overdue-threshold').textContent = `> ${state.settings.feedbackOverdueDays} days`;

    // KPI 6: Potentially Inactive / 6-Month Review
    document.getElementById('kpi-inactive-count').textContent = d.potentially_inactive_count !== null ? d.potentially_inactive_count.toLocaleString() : '—';

    // Render Distribution & Trend
    renderHappinessDistribution();
    renderHistoricalTrendChart();
    renderOverviewAttentionTable();
  }

  function renderHappinessDistribution() {
    const container = document.getElementById('distribution-bars');
    const d = state.dashboard;
    if (!container || !d) return;

    const data = state.distributionMode === 'predicted' ? d.predicted_hi_distribution : d.hi_distribution;
    if (!data || data.length === 0) {
      container.innerHTML = '<div class="text-muted text-center py-4">No distribution data available for active population.</div>';
      return;
    }

    const totalActive = d.total_active_employees || 1;
    let html = '';

    data.forEach((item) => {
      const count = item.count;
      const pct = Math.round((count / totalActive) * 1000) / 10;
      const label = getHiLabel(item.hi);
      const bgClass = `hi-${item.hi}-bg`;

      html += `
        <div class="dist-row">
          <div class="dist-label">${label.split(':')[0]} (${label.split(':')[1].trim()})</div>
          <div class="dist-bar-track" title="${count} active employees (${pct}%)">
            <div class="dist-bar-fill ${bgClass}" style="width: ${Math.max(pct, 2)}%;"></div>
          </div>
          <div class="dist-meta">${count} <span class="text-muted">(${pct}%)</span></div>
        </div>
      `;
    });

    container.innerHTML = html;
  }

  function renderHistoricalTrendChart() {
    const container = document.getElementById('trend-chart-container');
    const d = state.dashboard;
    if (!container || !d) return;

    const trend = d.trend || [];
    if (trend.length === 0) {
      container.innerHTML = '<div class="text-muted text-center py-4">No chronological HI trend records for this company.</div>';
      return;
    }

    // SVG Line Chart Dimensions
    const width = container.clientWidth || 500;
    const height = 210;
    const padLeft = 40;
    const padRight = 30;
    const padTop = 20;
    const padBottom = 35;

    const chartW = width - padLeft - padRight;
    const chartH = height - padTop - padBottom;

    // HI scale is 1.0 to 4.0
    const minY = 1.0;
    const maxY = 4.0;

    function getX(index) {
      if (trend.length === 1) return padLeft + chartW / 2;
      return padLeft + (index / (trend.length - 1)) * chartW;
    }

    function getY(val) {
      const clamped = Math.max(minY, Math.min(maxY, val));
      return padTop + chartH - ((clamped - minY) / (maxY - minY)) * chartH;
    }

    // Grid Lines (1.0, 2.0, 3.0, 4.0)
    let gridSvg = '';
    [1.0, 2.0, 3.0, 4.0].forEach((level) => {
      const yPos = getY(level);
      gridSvg += `
        <line x1="${padLeft}" y1="${yPos}" x2="${width - padRight}" y2="${yPos}" class="chart-grid-line" />
        <text x="${padLeft - 8}" y="${yPos + 4}" text-anchor="end" class="chart-axis-text">HI ${level.toFixed(0)}</text>
      `;
    });

    // Build Paths
    const historicalPoints = [];
    let predictionPoint = null;

    trend.forEach((pt, idx) => {
      const x = getX(idx);
      const y = getY(pt.average_hi);
      if (pt.is_prediction) {
        predictionPoint = { x, y, pt, idx };
      } else {
        historicalPoints.push({ x, y, pt, idx });
      }
    });

    let histPathD = '';
    historicalPoints.forEach((p, idx) => {
      histPathD += (idx === 0 ? `M ${p.x} ${p.y}` : ` L ${p.x} ${p.y}`);
    });

    let predPathD = '';
    if (predictionPoint && historicalPoints.length > 0) {
      const lastHist = historicalPoints[historicalPoints.length - 1];
      predPathD = `M ${lastHist.x} ${lastHist.y} L ${predictionPoint.x} ${predictionPoint.y}`;
    }

    // Dots and Labels
    let dotsSvg = '';
    historicalPoints.forEach((p) => {
      const dateLabel = formatDate(p.pt.month);
      dotsSvg += `
        <circle cx="${p.x}" cy="${p.y}" r="4.5" class="chart-dot">
          <title>${dateLabel}: Average HI ${p.pt.average_hi} (${p.pt.observation_count} observations)</title>
        </circle>
      `;
    });

    if (predictionPoint) {
      const predDateLabel = formatDate(predictionPoint.pt.month);
      dotsSvg += `
        <polygon points="${predictionPoint.x},${predictionPoint.y - 7} ${predictionPoint.x + 6},${predictionPoint.y} ${predictionPoint.x},${predictionPoint.y + 7} ${predictionPoint.x - 6},${predictionPoint.y}" class="chart-dot-pred">
          <title>Prediction Date (${predDateLabel}): Forecast Mean HI ${predictionPoint.pt.average_hi}</title>
        </polygon>
      `;
    }

    // X Axis Ticks
    let xAxisSvg = '';
    // Select evenly spaced ticks to avoid label crowding
    const step = Math.max(1, Math.floor(trend.length / 5));
    for (let i = 0; i < trend.length; i += step) {
      const pt = trend[i];
      const x = getX(i);
      const dateLabel = pt.is_prediction ? 'Next (Pred)' : formatDate(pt.month).split(' ').slice(1).join(' ');
      xAxisSvg += `
        <text x="${x}" y="${height - 10}" text-anchor="middle" class="chart-axis-text">${dateLabel}</text>
      `;
    }

    container.innerHTML = `
      <svg class="chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
        ${gridSvg}
        ${histPathD ? `<path d="${histPathD}" class="chart-trend-path" />` : ''}
        ${predPathD ? `<path d="${predPathD}" class="chart-pred-path" />` : ''}
        ${dotsSvg}
        ${xAxisSvg}
      </svg>
    `;
  }

  function renderOverviewAttentionTable() {
    const tbody = document.getElementById('tbody-overview-attention');
    const d = state.dashboard;
    if (!tbody || !d) return;

    const list = d.attention_employees || [];
    if (list.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" class="text-center py-4 text-muted">
            No active employees currently meet attention risk criteria. All active records are within normal bounds.
          </td>
        </tr>
      `;
      return;
    }

    let html = '';
    list.forEach((emp) => {
      const currentHi = emp.current_hi !== null ? `<span class="badge ${getHiBadgeClass(emp.current_hi)}">HI ${emp.current_hi}</span>` : '<span class="text-muted">—</span>';
      const predHi = `<span class="badge ${getHiBadgeClass(emp.predicted_hi)}">HI ${emp.predicted_hi}</span>`;
      const lastFb = emp.last_feedback_date ? formatDate(emp.last_feedback_date) : '<span class="text-muted">No survey response</span>';
      const ageLabel = formatFeedbackAge(emp.days_since_feedback);
      const reasons = emp.attention_reasons && emp.attention_reasons.length > 0
        ? emp.attention_reasons.map(r => `<span class="badge badge-warning" style="font-size:10.5px;">${r}</span>`).join(' ')
        : '<span class="text-muted">Review Required</span>';

      let statusBadge = '<span class="badge badge-active">Active</span>';
      if (emp.is_potentially_inactive) {
        statusBadge = '<span class="badge badge-stale" title="Feedback > 6 mos stale. Verify employment.">Audit Review</span>';
      }

      html += `
        <tr class="row-attention">
          <td class="emp-id-cell">${emp.employee_id}</td>
          <td>${currentHi}</td>
          <td>${predHi}</td>
          <td>${lastFb}</td>
          <td class="text-muted">${ageLabel}</td>
          <td>${reasons}</td>
          <td>${statusBadge}</td>
          <td class="text-right">
            <button type="button" class="btn btn-secondary btn-sm btn-open-detail" data-emp-id="${emp.employee_id}">
              View Details
            </button>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    bindDetailButtons(tbody);
  }

  // ---------------------------------------------------------------------------
  // UI Renderers: Employee Directory & Filters
  // ---------------------------------------------------------------------------
  function renderDirectoryTable() {
    const tbody = document.getElementById('tbody-employees');
    if (!tbody) return;

    const employees = state.directory.employees;
    document.getElementById('filter-result-count').textContent = state.directory.filteredCount.toLocaleString();
    document.getElementById('filter-total-count').textContent = state.directory.totalCount.toLocaleString();

    if (employees.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" class="text-center py-4 text-muted">
            No employees match the selected search and filter criteria. Try clearing filters.
          </td>
        </tr>
      `;
      return;
    }

    let html = '';
    employees.forEach((emp) => {
      const currentHi = emp.current_hi !== null
        ? `<span class="badge ${getHiBadgeClass(emp.current_hi)}">HI ${emp.current_hi}</span>`
        : '<span class="text-muted">—</span>';
      const predHi = `<span class="badge ${getHiBadgeClass(emp.predicted_hi)}">HI ${emp.predicted_hi}</span>`;
      const predDate = formatDate(emp.prediction_date);
      const lastFb = emp.last_feedback_date ? formatDate(emp.last_feedback_date) : '<span class="text-muted">No survey response</span>';
      const ageLabel = formatFeedbackAge(emp.days_since_feedback);

      // Employment Status Badge
      let statusBadge = '<span class="badge badge-active">Active</span>';
      if (emp.is_confirmed_former) {
        statusBadge = '<span class="badge badge-former" title="Confirmed former employee">Former</span>';
      } else if (emp.is_potentially_inactive) {
        statusBadge = '<span class="badge badge-stale" title="Last feedback > 6 calendar months ago. Verify employment.">Audit Review</span>';
      } else if (emp.is_unknown_status) {
        statusBadge = '<span class="badge badge-unknown" title="Employment status cannot be verified from records">Unknown</span>';
      }

      // Attention Status Badge
      let attentionBadge = '<span class="text-muted" style="font-size:12px;">Normal</span>';
      if (emp.needs_attention) {
        const titleText = emp.attention_reasons ? emp.attention_reasons.join(' · ') : 'Attention required';
        attentionBadge = `<span class="badge badge-warning" title="${titleText}">Attention</span>`;
      }

      const rowClass = emp.needs_attention ? 'row-attention' : '';

      html += `
        <tr class="${rowClass}">
          <td class="emp-id-cell">${emp.employee_id}</td>
          <td>${currentHi}</td>
          <td>${predHi}</td>
          <td>${predDate}</td>
          <td>${lastFb}</td>
          <td class="text-muted">${ageLabel}</td>
          <td>${statusBadge}</td>
          <td>${attentionBadge}</td>
          <td class="text-right">
            <button type="button" class="btn btn-secondary btn-sm btn-open-detail" data-emp-id="${emp.employee_id}">
              View Details
            </button>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    bindDetailButtons(tbody);
  }

  function renderPagination() {
    const page = state.directory.page;
    const totalPages = state.directory.totalPages;
    const info = document.getElementById('pagination-info');
    const prevBtn = document.getElementById('btn-prev-page');
    const nextBtn = document.getElementById('btn-next-page');
    const pagesContainer = document.getElementById('pagination-pages');

    info.textContent = `Page ${page} of ${totalPages} (${state.directory.filteredCount.toLocaleString()} total)`;
    prevBtn.disabled = page <= 1;
    nextBtn.disabled = page >= totalPages;

    // Render numbered page buttons (show max 5 buttons)
    pagesContainer.innerHTML = '';
    const maxBtns = 5;
    let startPage = Math.max(1, page - Math.floor(maxBtns / 2));
    let endPage = Math.min(totalPages, startPage + maxBtns - 1);
    if (endPage - startPage + 1 < maxBtns) {
      startPage = Math.max(1, endPage - maxBtns + 1);
    }

    for (let p = startPage; p <= endPage; p++) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `page-btn ${p === page ? 'active' : ''}`;
      btn.textContent = String(p);
      btn.addEventListener('click', () => {
        state.directory.page = p;
        fetchEmployees();
      });
      pagesContainer.appendChild(btn);
    }
  }

  function renderActiveFilterTags() {
    const container = document.getElementById('active-filter-tags');
    if (!container) return;

    const tags = [];
    const dir = state.directory;

    if (dir.search) {
      tags.push({ label: `ID: "${dir.search}"`, clear: () => { dir.search = ''; document.getElementById('emp-search').value = ''; } });
    }
    if (dir.status !== 'all') {
      const map = { active: 'Active Only', potentially_inactive: 'Potentially Inactive', former: 'Former Employees', unknown: 'Status Unknown' };
      tags.push({ label: `Status: ${map[dir.status] || dir.status}`, clear: () => { dir.status = 'all'; document.getElementById('filter-status').value = 'all'; } });
    }
    if (dir.risk !== 'all') {
      const map = { low: 'Low HI (1–2)', moderate: 'Moderate HI (3)', high: 'High HI (4)' };
      tags.push({ label: `Risk: ${map[dir.risk] || dir.risk}`, clear: () => { dir.risk = 'all'; document.getElementById('filter-risk').value = 'all'; } });
    }
    if (dir.attention !== 'all') {
      tags.push({ label: dir.attention === 'needs_attention' ? 'Attention Only' : 'Normal Only', clear: () => { dir.attention = 'all'; document.getElementById('filter-attention').value = 'all'; } });
    }
    if (dir.feedbackStatus !== 'all') {
      const map = { confirmed: 'Has Confirmed Feedback', unverified: 'No Survey Response', overdue: 'Overdue Feedback', stale: 'Stale > 6 Mos' };
      tags.push({ label: `Feedback: ${map[dir.feedbackStatus] || dir.feedbackStatus}`, clear: () => { dir.feedbackStatus = 'all'; document.getElementById('filter-feedback').value = 'all'; } });
    }

    if (tags.length === 0) {
      container.innerHTML = '';
      return;
    }

    container.innerHTML = tags.map((t, idx) => `
      <span class="filter-tag" data-idx="${idx}">
        ${t.label}
        <span class="filter-tag-close" data-idx="${idx}">&times;</span>
      </span>
    `).join('');

    container.querySelectorAll('.filter-tag-close').forEach((closeBtn) => {
      closeBtn.addEventListener('click', (e) => {
        const idx = Number(e.target.dataset.idx);
        if (tags[idx]) {
          tags[idx].clear();
          dir.page = 1;
          fetchEmployees();
        }
      });
    });
  }

  // ---------------------------------------------------------------------------
  // UI Renderers: Insights Page
  // ---------------------------------------------------------------------------
  function renderInsights() {
    const data = state.insights;
    if (!data) return;

    document.getElementById('insights-cutoff-label').textContent = formatDate(data.six_month_cutoff);

    // Reasons Breakdown
    const reasonContainer = document.getElementById('insights-reason-breakdown');
    if (reasonContainer && data.reasons_breakdown) {
      const rb = data.reasons_breakdown;
      reasonContainer.innerHTML = `
        <div class="reason-card">
          <div>
            <div class="reason-title">Low Predicted HI Forecast</div>
            <div class="reason-sub">Next observation forecast is HI 1 or HI 2</div>
          </div>
          <div class="reason-val text-danger">${rb.low_predicted_hi ?? 0}</div>
        </div>
        <div class="reason-card">
          <div>
            <div class="reason-title">Confirmed Feedback Overdue</div>
            <div class="reason-sub">Older than configured threshold (> ${state.settings.feedbackOverdueDays} days)</div>
          </div>
          <div class="reason-val text-warning">${rb.feedback_overdue ?? 0}</div>
        </div>
        <div class="reason-card">
          <div>
            <div class="reason-title">Inactivity Review / Stale Feedback</div>
            <div class="reason-sub">Last confirmed feedback > 6 calendar months ago</div>
          </div>
          <div class="reason-val text-navy">${rb.potentially_inactive ?? 0}</div>
        </div>
      `;
    }

    // Feedback Staleness Breakdown
    const staleContainer = document.getElementById('insights-staleness-bars');
    if (staleContainer && data.feedback_staleness) {
      const fs = data.feedback_staleness;
      const total = data.total_active_employees || 1;

      const buckets = [
        { label: 'Fresh (< 30 days)', count: fs.fresh_under_30d ?? 0, color: 'var(--status-green)' },
        { label: 'Moderate (30–90 days)', count: fs.moderate_30_90d ?? 0, color: '#0d9488' },
        { label: 'Stale (90–180 days)', count: fs.stale_90_180d ?? 0, color: 'var(--status-amber)' },
        { label: 'Inactive Review (> 6 Mos)', count: fs.inactive_over_180d ?? 0, color: 'var(--status-red)' },
        { label: 'No Survey Response', count: fs.no_confirmed_feedback ?? 0, color: 'var(--status-slate)' },
      ];

      staleContainer.innerHTML = buckets.map(b => {
        const pct = Math.round((b.count / total) * 1000) / 10;
        return `
          <div class="stale-row">
            <div class="stale-label">${b.label}</div>
            <div class="stale-bar-wrap" title="${b.count} employees (${pct}%)">
              <div class="stale-fill" style="width: ${Math.max(pct, 2)}%; background-color: ${b.color};"></div>
            </div>
            <div class="stale-val">${b.count} <span class="text-muted">(${pct}%)</span></div>
          </div>
        `;
      }).join('');
    }

    // Potentially Inactive Audit Table
    const tbodyStale = document.getElementById('tbody-stale-review');
    const badgeStale = document.getElementById('insights-stale-badge');
    const staleList = data.potentially_inactive_review_list || [];

    badgeStale.textContent = `${staleList.length} flagged for review`;

    if (staleList.length === 0) {
      tbodyStale.innerHTML = `
        <tr>
          <td colspan="7" class="text-center py-4 text-muted">
            No active employees meet the 6-calendar-month stale feedback criteria for this company.
          </td>
        </tr>
      `;
    } else {
      tbodyStale.innerHTML = staleList.map(emp => `
        <tr>
          <td class="emp-id-cell">${emp.employee_id}</td>
          <td>${formatDate(emp.last_feedback_date)}</td>
          <td class="text-muted">${formatFeedbackAge(emp.days_since_feedback)}</td>
          <td>${formatDate(emp.latest_employee_data)}</td>
          <td>${emp.current_hi !== null ? `<span class="badge ${getHiBadgeClass(emp.current_hi)}">HI ${emp.current_hi}</span>` : '—'}</td>
          <td><span class="badge ${getHiBadgeClass(emp.predicted_hi)}">HI ${emp.predicted_hi}</span></td>
          <td class="text-right">
            <button type="button" class="btn btn-secondary btn-sm btn-open-detail" data-emp-id="${emp.employee_id}">
              Audit
            </button>
          </td>
        </tr>
      `).join('');
      bindDetailButtons(tbodyStale);
    }

    // Benchmark Table
    const tbodyBench = document.getElementById('tbody-company-benchmark');
    const topComps = data.top_companies_benchmark || [];
    if (topComps.length > 0) {
      tbodyBench.innerHTML = topComps.map(c => {
        const attPct = c.active_employees > 0 ? Math.round((c.attention_count / c.active_employees) * 1000) / 10 : 0;
        const isCurrent = c.id === state.selectedCompany;
        return `
          <tr class="${isCurrent ? 'row-attention' : ''}">
            <td><strong>${c.name}</strong> ${isCurrent ? '<span class="badge badge-accent">Selected</span>' : ''}</td>
            <td class="text-muted">${c.industry}</td>
            <td class="text-muted">${c.timezone}</td>
            <td><strong>${c.active_employees.toLocaleString()}</strong></td>
            <td><strong class="text-navy">${c.average_hi ?? '—'}</strong> / 4.0</td>
            <td><span class="text-warning font-weight-bold">${c.attention_count}</span></td>
            <td>${attPct}%</td>
            <td class="text-right">
              ${isCurrent ? '<span class="text-muted" style="font-size:12px;">Active</span>' : `<button type="button" class="btn btn-secondary btn-sm btn-switch-company" data-comp-id="${c.id}">View</button>`}
            </td>
          </tr>
        `;
      }).join('');

      tbodyBench.querySelectorAll('.btn-switch-company').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const compId = e.target.dataset.compId;
          if (compId) {
            state.selectedCompany = compId;
            document.getElementById('company-select').value = compId;
            reloadAllData();
            switchPage('overview');
          }
        });
      });
    }
  }

  // ---------------------------------------------------------------------------
  // UI Renderers: Employee Detail Modal / Drawer
  // ---------------------------------------------------------------------------
  async function openEmployeeDrawer(employeeId) {
    const modal = document.getElementById('employee-detail-modal');
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');

    document.getElementById('modal-employee-title').textContent = `Employee ID: ${employeeId}`;
    document.getElementById('modal-company-title').textContent = `Company: ${state.selectedCompany}`;
    document.getElementById('modal-status-badge').textContent = 'Loading...';

    const emp = await fetchEmployeeDetail(employeeId);
    if (!emp) return;

    // Header Status Badge
    const statusBadge = document.getElementById('modal-status-badge');
    if (emp.is_confirmed_former) {
      statusBadge.className = 'badge badge-former';
      statusBadge.textContent = 'Confirmed Former Employee';
    } else if (emp.is_potentially_inactive) {
      statusBadge.className = 'badge badge-stale';
      statusBadge.textContent = 'Potentially Inactive (Verify Employment)';
    } else if (emp.is_unknown_status) {
      statusBadge.className = 'badge badge-unknown';
      statusBadge.textContent = 'Status Unknown';
    } else {
      statusBadge.className = 'badge badge-active';
      statusBadge.textContent = 'Active Employee';
    }

    // Key Metrics
    document.getElementById('modal-current-hi').textContent = emp.current_hi !== null ? `HI ${emp.current_hi}` : '—';
    const curBadge = document.getElementById('modal-current-hi-badge');
    if (emp.current_hi !== null) {
      curBadge.className = `metric-badge ${getHiBadgeClass(emp.current_hi)}`;
      curBadge.textContent = getHiLabel(emp.current_hi).split(':')[1].trim();
      curBadge.style.display = 'inline-block';
    } else {
      curBadge.style.display = 'none';
    }

    document.getElementById('modal-predicted-hi').textContent = `HI ${emp.predicted_hi}`;
    const predBadge = document.getElementById('modal-predicted-hi-badge');
    predBadge.className = `metric-badge ${getHiBadgeClass(emp.predicted_hi)}`;
    predBadge.textContent = getHiLabel(emp.predicted_hi).split(':')[1].trim();

    document.getElementById('modal-prediction-date').textContent = formatDate(emp.prediction_date);
    document.getElementById('modal-latest-employee-date').textContent = formatDate(emp.latest_employee_data);
    document.getElementById('modal-last-feedback-date').textContent = emp.last_feedback_date ? formatDate(emp.last_feedback_date) : 'No survey response';
    document.getElementById('modal-feedback-age-label').textContent = formatFeedbackAge(emp.days_since_feedback);
    document.getElementById('modal-tenure').textContent = emp.tenure_years !== null ? `${emp.tenure_years} years` : 'Unspecified';

    // Attention Alert Box
    const alertBox = document.getElementById('modal-attention-alert');
    const reasonsBox = document.getElementById('modal-attention-reasons');
    if (emp.needs_attention && emp.attention_reasons && emp.attention_reasons.length > 0) {
      alertBox.style.display = 'block';
      reasonsBox.innerHTML = emp.attention_reasons.map(r => `<div>&bull; ${r}</div>`).join('');
    } else {
      alertBox.style.display = 'none';
    }

    // Class Probabilities
    const probContainer = document.getElementById('modal-prob-bars');
    if (emp.probabilities && Object.keys(emp.probabilities).length > 0) {
      let probHtml = '';
      for (let cls = 1; cls <= 4; cls++) {
        const p = emp.probabilities[String(cls)] || 0;
        const pct = (p * 100).toFixed(1);
        const isPred = cls === emp.predicted_hi;
        probHtml += `
          <div class="prob-row">
            <div class="prob-label">${getHiLabel(cls).split(':')[0]}</div>
            <div class="prob-bar-wrap">
              <div class="prob-fill ${isPred ? 'is-predicted' : ''}" style="width: ${Math.max(p * 100, 2)}%;"></div>
            </div>
            <div class="prob-pct ${isPred ? 'text-accent' : 'text-muted'}">${pct}%</div>
          </div>
        `;
      }
      probContainer.innerHTML = probHtml;
    } else {
      probContainer.innerHTML = '<div class="text-muted text-center py-2">Class probabilities unavailable.</div>';
    }

    // SHAP Explainability
    const shapContainer = document.getElementById('modal-shap-features');
    if (emp.shap_explanation && emp.shap_explanation.length > 0) {
      const maxShap = Math.max(...emp.shap_explanation.map(f => Math.abs(f.shap_value)), 0.001);
      shapContainer.innerHTML = emp.shap_explanation.map((f) => {
        const isPositive = f.direction === 'towards_prediction';
        const barPct = Math.round((Math.abs(f.shap_value) / maxShap) * 100);
        const sign = f.shap_value > 0 ? '+' : '';
        const directionText = isPositive ? 'Towards predicted level' : 'Away from predicted level';

        return `
          <div class="shap-item">
            <div class="shap-top">
              <span class="shap-name">${f.name}</span>
              <span class="shap-factor">${f.factor}</span>
            </div>
            ${f.question ? `<div class="shap-question">"${f.question}"</div>` : ''}
            <div class="shap-bar-container">
              <div class="shap-bar-track">
                <div class="shap-bar-value ${isPositive ? 'positive' : 'negative'}" style="width: ${Math.max(barPct, 4)}%;"></div>
              </div>
              <span class="shap-impact ${isPositive ? 'positive' : 'negative'}" title="${directionText}">
                ${sign}${f.shap_value.toFixed(4)}
              </span>
            </div>
          </div>
        `;
      }).join('');
    } else {
      shapContainer.innerHTML = `
        <div class="text-muted text-center py-3">
          Feature-level prediction explanation is unavailable for this employee record.
        </div>
      `;
    }

    // Historical Records Timeline
    const histTbody = document.getElementById('modal-history-tbody');
    const history = emp.history || [];
    if (history.length === 0) {
      histTbody.innerHTML = '<tr><td colspan="4" class="text-center py-3 text-muted">No chronological history records found.</td></tr>';
    } else {
      histTbody.innerHTML = history.slice(-20).reverse().map((h) => {
        const hiBadge = h.hi_vote !== null ? `<span class="badge ${getHiBadgeClass(h.hi_vote)}">HI ${h.hi_vote}</span>` : '—';
        const surveySubmitted = h.has_feedback ? `<span class="badge badge-active">Submitted (${formatDate(h.feedback_date)})</span>` : '<span class="text-muted">None</span>';
        return `
          <tr>
            <td>${formatDate(h.date)}</td>
            <td>${hiBadge}</td>
            <td>${surveySubmitted}</td>
            <td class="text-muted">Observed Record</td>
          </tr>
        `;
      }).join('');
    }
  }

  function closeEmployeeDrawer() {
    const modal = document.getElementById('employee-detail-modal');
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
  }

  function bindDetailButtons(parent) {
    parent.querySelectorAll('.btn-open-detail').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const empId = e.currentTarget.dataset.empId;
        if (empId) openEmployeeDrawer(empId);
      });
    });
  }

  // ---------------------------------------------------------------------------
  // Page Navigation & Event Listeners
  // ---------------------------------------------------------------------------
  function switchPage(pageName) {
    state.activePage = pageName;

    // Nav Items
    document.querySelectorAll('.nav-item').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.page === pageName);
    });

    // Page Views
    document.querySelectorAll('.page-view').forEach((view) => {
      view.classList.toggle('active', view.id === `view-${pageName}`);
    });

    // Titles & Subtitles
    const titleEl = document.getElementById('page-title');
    const subtitleEl = document.getElementById('page-subtitle');

    switch (pageName) {
      case 'overview':
        titleEl.textContent = 'Overview';
        subtitleEl.textContent = 'Workforce happiness distribution, KPI summary, and high-priority alerts.';
        break;
      case 'employees':
        titleEl.textContent = 'Employees Directory';
        subtitleEl.textContent = 'Searchable, filterable workforce records with prediction forecasts and audit flags.';
        fetchEmployees();
        break;
      case 'insights':
        titleEl.textContent = 'Insights';
        subtitleEl.textContent = 'Historical trends, survey freshness diagnostics, and cross-company benchmarks.';
        fetchInsights();
        break;
      case 'settings':
        titleEl.textContent = 'Settings';
        subtitleEl.textContent = 'Configure attention thresholds, review cutoffs, and application display preferences.';
        break;
    }
  }

  function exportFilteredEmployeesCSV() {
    const rows = state.directory.employees;
    if (rows.length === 0) {
      showToast('No employees available to export.', 'error');
      return;
    }

    const headers = ['Employee ID', 'Current HI', 'Predicted HI', 'Prediction Date', 'Last Confirmed Feedback', 'Days Since Feedback', 'Employment Status', 'Attention Required', 'Attention Reasons'];
    const csvRows = [headers.join(',')];

    rows.forEach((e) => {
      const vals = [
        `"${e.employee_id}"`,
        e.current_hi ?? '',
        e.predicted_hi,
        `"${formatDate(e.prediction_date)}"`,
        `"${e.last_feedback_date ? formatDate(e.last_feedback_date) : 'No survey response'}"`,
        e.days_since_feedback ?? '',
        `"${e.employment_status}"`,
        e.needs_attention ? 'YES' : 'NO',
        `"${(e.attention_reasons || []).join('; ')}"`,
      ];
      csvRows.push(vals.join(','));
    });

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `AUCML_${state.selectedCompany}_employees.csv`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`Exported ${rows.length} employee records to CSV.`, 'success');
  }

  function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function setLoading(loading, text = 'Loading...') {
    state.isLoading = loading;
    const overlay = document.getElementById('loading-overlay');
    const textEl = document.getElementById('loading-text');
    if (textEl) textEl.textContent = text;
    if (overlay) overlay.classList.toggle('active', loading);
  }

  // ---------------------------------------------------------------------------
  // App Initialization
  // ---------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', () => {
    // Navigation Buttons
    document.querySelectorAll('.nav-item').forEach((btn) => {
      btn.addEventListener('click', () => switchPage(btn.dataset.page));
    });

    // Company Selector
    document.getElementById('company-select').addEventListener('change', (e) => {
      state.selectedCompany = e.target.value;
      state.directory.page = 1;
      reloadAllData();
    });

    // Refresh Button
    document.getElementById('btn-refresh').addEventListener('click', refreshCache);

    // Distribution Toggle (Current vs Predicted)
    document.getElementById('btn-dist-current').addEventListener('click', (e) => {
      e.target.classList.add('active');
      document.getElementById('btn-dist-predicted').classList.remove('active');
      state.distributionMode = 'current';
      renderHappinessDistribution();
    });

    document.getElementById('btn-dist-predicted').addEventListener('click', (e) => {
      e.target.classList.add('active');
      document.getElementById('btn-dist-current').classList.remove('active');
      state.distributionMode = 'predicted';
      renderHappinessDistribution();
    });

    // Overview "View All in Directory" Link
    document.getElementById('btn-view-all-attention').addEventListener('click', () => {
      state.directory.attention = 'needs_attention';
      document.getElementById('filter-attention').value = 'needs_attention';
      state.directory.page = 1;
      switchPage('employees');
    });

    // Employee Search (with debounce)
    let searchTimeout = null;
    document.getElementById('emp-search').addEventListener('input', (e) => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        state.directory.search = e.target.value;
        state.directory.page = 1;
        fetchEmployees();
      }, 300);
    });

    // Directory Filter Dropdowns
    document.getElementById('filter-status').addEventListener('change', (e) => {
      state.directory.status = e.target.value;
      state.directory.page = 1;
      fetchEmployees();
    });

    document.getElementById('filter-risk').addEventListener('change', (e) => {
      state.directory.risk = e.target.value;
      state.directory.page = 1;
      fetchEmployees();
    });

    document.getElementById('filter-attention').addEventListener('change', (e) => {
      state.directory.attention = e.target.value;
      state.directory.page = 1;
      fetchEmployees();
    });

    document.getElementById('filter-feedback').addEventListener('change', (e) => {
      state.directory.feedbackStatus = e.target.value;
      state.directory.page = 1;
      fetchEmployees();
    });

    document.getElementById('select-page-size').addEventListener('change', (e) => {
      state.directory.pageSize = parseInt(e.target.value, 10);
      state.directory.page = 1;
      fetchEmployees();
    });

    // Reset Filters Button
    document.getElementById('btn-reset-filters').addEventListener('click', () => {
      state.directory.search = '';
      state.directory.status = 'all';
      state.directory.risk = 'all';
      state.directory.attention = 'all';
      state.directory.feedbackStatus = 'all';
      state.directory.page = 1;

      document.getElementById('emp-search').value = '';
      document.getElementById('filter-status').value = 'all';
      document.getElementById('filter-risk').value = 'all';
      document.getElementById('filter-attention').value = 'all';
      document.getElementById('filter-feedback').value = 'all';

      fetchEmployees();
    });

    // Directory Table Sort Headers
    document.querySelectorAll('#table-employees th.sortable').forEach((th) => {
      th.addEventListener('click', () => {
        const sortKey = th.dataset.sort;
        if (state.directory.sortBy === sortKey) {
          state.directory.sortDir = state.directory.sortDir === 'asc' ? 'desc' : 'asc';
        } else {
          state.directory.sortBy = sortKey;
          state.directory.sortDir = 'asc';
        }

        document.querySelectorAll('#table-employees th.sortable').forEach(h => {
          h.classList.remove('sorted-asc', 'sorted-desc');
        });
        th.classList.add(state.directory.sortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');

        state.directory.page = 1;
        fetchEmployees();
      });
    });

    // Pagination Buttons
    document.getElementById('btn-prev-page').addEventListener('click', () => {
      if (state.directory.page > 1) {
        state.directory.page--;
        fetchEmployees();
      }
    });

    document.getElementById('btn-next-page').addEventListener('click', () => {
      if (state.directory.page < state.directory.totalPages) {
        state.directory.page++;
        fetchEmployees();
      }
    });

    // Export CSV
    document.getElementById('btn-export-csv').addEventListener('click', exportFilteredEmployeesCSV);

    // Modal Drawer Close
    document.getElementById('btn-close-modal').addEventListener('click', closeEmployeeDrawer);
    document.getElementById('employee-detail-modal').addEventListener('click', (e) => {
      if (e.target.id === 'employee-detail-modal') closeEmployeeDrawer();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') closeEmployeeDrawer();
    });

    // Settings Form
    document.getElementById('btn-save-settings').addEventListener('click', () => {
      state.settings.lowHiThreshold = parseInt(document.getElementById('setting-low-hi').value, 10);
      state.settings.feedbackOverdueDays = parseInt(document.getElementById('setting-feedback-overdue').value, 10);
      state.settings.inactivityMonths = parseInt(document.getElementById('setting-inactivity-months').value, 10);
      state.settings.dateFormat = document.getElementById('setting-date-format').value;

      updateReferenceDates();
      reloadAllData();
      showToast('Settings saved. All dashboard metrics recalculated.', 'success');
    });

    document.getElementById('btn-reset-settings').addEventListener('click', () => {
      state.settings.lowHiThreshold = 2;
      state.settings.feedbackOverdueDays = 30;
      state.settings.inactivityMonths = 6;
      state.settings.dateFormat = 'DD Mon YYYY';

      document.getElementById('setting-low-hi').value = '2';
      document.getElementById('setting-feedback-overdue').value = '30';
      document.getElementById('setting-inactivity-months').value = '6';
      document.getElementById('setting-date-format').value = 'DD Mon YYYY';

      updateReferenceDates();
      reloadAllData();
      showToast('Settings reset to system defaults.', 'info');
    });

    // Initial Load
    fetchCompanies();
  });

})();
