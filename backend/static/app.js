/* ═══════════════════════════════════════════════════════════
   Contractor Invoice Management - Main Application JS
   ═══════════════════════════════════════════════════════════ */

const API = 'http://localhost:8000/api';

// ─── State ────────────────────────────────────────────────
let currentPage = 'dashboard';
let invoicePage = 1;
let invoiceFilters = {};

// ─── Settings (localStorage) ─────────────────────────────
function getSettings() {
    return {
        defaultGstPct: parseFloat(localStorage.getItem('setting_gst_pct') || '18'),
        defaultTdsPct: parseFloat(localStorage.getItem('setting_tds_pct') || '10'),
        defaultRetPct: parseFloat(localStorage.getItem('setting_ret_pct') || '5'),
    };
}

function saveSettings(gstPct, tdsPct, retPct) {
    localStorage.setItem('setting_gst_pct', gstPct);
    localStorage.setItem('setting_tds_pct', tdsPct);
    localStorage.setItem('setting_ret_pct', retPct);
}

// ─── Indian Currency Formatting ───────────────────────────
function formatINR(amount) {
    if (amount === null || amount === undefined) return '\u20B90.00';
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR',
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(amount);
}

function formatINRCompact(amount) {
    if (!amount) return '\u20B90';
    const abs = Math.abs(amount);
    const sign = amount < 0 ? '-' : '';
    if (abs >= 10000000) return sign + '\u20B9' + (abs / 10000000).toFixed(2) + ' Cr';
    if (abs >= 100000) return sign + '\u20B9' + (abs / 100000).toFixed(2) + ' L';
    if (abs >= 1000) return sign + '\u20B9' + (abs / 1000).toFixed(1) + ' K';
    return formatINR(amount);
}

function formatIndianNumber(num) {
    if (num === null || num === undefined) return '0';
    return new Intl.NumberFormat('en-IN').format(num);
}

// ─── API Helpers ──────────────────────────────────────────
async function api(path, options = {}) {
    try {
        const res = await fetch(`${API}${path}`, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Request failed');
        }
        return await res.json();
    } catch (e) {
        console.error('API Error:', e);
        throw e;
    }
}

// ─── Toast Notifications ──────────────────────────────────
function showToast(message, type = 'success') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="material-icons-round" style="font-size:20px;color:var(--${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'warning'})">
            ${type === 'success' ? 'check_circle' : type === 'error' ? 'error' : 'warning'}
        </span>
        <span class="toast-message">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">
            <span class="material-icons-round" style="font-size:16px">close</span>
        </button>
    `;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ─── Navigation ───────────────────────────────────────────
function navigate(page) {
    currentPage = page;
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.page === page);
    });

    const content = document.getElementById('pageContent');
    content.style.opacity = '0';
    setTimeout(() => {
        switch (page) {
            case 'dashboard': renderDashboard(); break;
            case 'companies': renderCompanies(); break;
            case 'invoices': renderInvoices(); break;
            case 'payments': renderPayments(); break;
            case 'reconciliation': renderReconciliation(); break;
            case 'reconciliation-aging': renderAgingReport(); break;
            case 'reconciliation-ledger': renderLedgerPage(); break;
            case 'reports': renderReports(); break;
            case 'settings': renderSettings(); break;
        }
        content.style.opacity = '1';
    }, 150);
}

// ─── Sidebar Toggle ───────────────────────────────────────
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('collapsed');
}

// ─── Modal ────────────────────────────────────────────────
function openModal(html) {
    const overlay = document.getElementById('modalOverlay');
    const content = document.getElementById('modalContent');
    content.innerHTML = html;
    overlay.classList.add('show');
    document.body.style.overflow = 'hidden';
}

function closeModal(event) {
    if (event && event.target !== document.getElementById('modalOverlay')) return;
    document.getElementById('modalOverlay').classList.remove('show');
    document.body.style.overflow = '';
}

function forceCloseModal() {
    document.getElementById('modalOverlay').classList.remove('show');
    document.body.style.overflow = '';
}

// ─── Status Badge ─────────────────────────────────────────
function statusBadge(status) {
    const cls = status === 'Paid' ? 'badge-paid' :
                status === 'Partially Paid' ? 'badge-partial' : 'badge-unpaid';
    return `<span class="badge ${cls}">${status}</span>`;
}

// ─── Date Formatting ──────────────────────────────────────
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function updateCurrentDate() {
    const d = new Date();
    document.getElementById('currentDate').textContent =
        d.toLocaleDateString('en-IN', { weekday: 'short', day: 'numeric', month: 'long', year: 'numeric' });
}

// ═══════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════
async function renderDashboard() {
    const content = document.getElementById('pageContent');
    content.innerHTML = `
        <div class="page-header">
            <div>
                <h1 class="page-title">Dashboard</h1>
                <p class="page-subtitle">Overview of your invoicing activity</p>
            </div>
        </div>
        <div class="stats-grid" id="dashStats">
            ${Array(8).fill('<div class="stat-card"><div class="skeleton skeleton-card" style="width:100%;height:60px"></div></div>').join('')}
        </div>
        <div class="charts-grid" id="dashCharts">
            <div class="chart-card"><div class="skeleton skeleton-card" style="height:240px"></div></div>
            <div class="chart-card"><div class="skeleton skeleton-card" style="height:240px"></div></div>
        </div>
        <div class="two-col-grid">
            <div class="table-container" id="recentInvoices">
                <div class="table-header"><span class="table-title">Recent Invoices</span></div>
                <div style="padding:20px"><div class="skeleton skeleton-card" style="height:200px"></div></div>
            </div>
            <div class="table-container" id="upcomingDues">
                <div class="table-header"><span class="table-title">Upcoming Dues</span></div>
                <div style="padding:20px"><div class="skeleton skeleton-card" style="height:200px"></div></div>
            </div>
        </div>
    `;

    try {
        const [stats, recent, upcoming, trend] = await Promise.all([
            api('/dashboard/stats'),
            api('/dashboard/recent-invoices'),
            api('/dashboard/upcoming-dues'),
            api('/dashboard/revenue-trend'),
        ]);

        // Stats Grid
        document.getElementById('dashStats').innerHTML = `
            ${statCard('business', 'Total Companies', stats.total_companies, 'blue')}
            ${statCard('description', 'Total Invoices', stats.total_invoices, 'blue')}
            ${statCard('check_circle', 'Paid Invoices', stats.paid_invoices, 'green')}
            ${statCard('pending', 'Pending Invoices', stats.pending_invoices, 'orange')}
            ${statCard('account_balance', 'Total Revenue', formatINR(stats.total_revenue), 'green', true)}
            ${statCard('hourglass_top', 'Pending Revenue', formatINR(stats.pending_revenue), 'orange', true)}
            ${statCard('calendar_month', 'This Month', formatINR(stats.this_month_revenue), 'blue', true)}
            ${statCard('currency_rupee', 'TDS Deducted', formatINR(stats.tds_deducted), 'red', true)}
        `;

        // Charts
        document.getElementById('dashCharts').innerHTML = `
            <div class="chart-card">
                <div class="chart-header">
                    <h3 class="chart-title">Monthly Revenue Trend (${new Date().getFullYear()})</h3>
                </div>
                <div class="bar-chart" id="revenueTrendChart"></div>
            </div>
            <div class="chart-card">
                <div class="chart-header">
                    <h3 class="chart-title">Revenue Distribution</h3>
                </div>
                <div class="donut-container" id="revenueDonut"></div>
            </div>
        `;

        renderBarChart('revenueTrendChart', trend);
        renderDonutChart('revenueDonut', stats);

        // Recent Invoices Table
        document.getElementById('recentInvoices').innerHTML = `
            <div class="table-header">
                <span class="table-title">Recent Invoices</span>
                <button class="btn btn-ghost btn-sm" onclick="navigate('invoices')">View All</button>
            </div>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Invoice #</th>
                            <th>Company</th>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${recent.length ? recent.map(inv => `
                            <tr style="cursor:pointer" onclick="navigate('invoices')">
                                <td style="font-weight:600;color:var(--primary)">${inv.invoice_number}</td>
                                <td>${inv.company_name}</td>
                                <td>${formatDate(inv.invoice_date)}</td>
                                <td style="font-weight:600">${formatINR(inv.net_receivable)}</td>
                                <td>${statusBadge(inv.invoice_status)}</td>
                            </tr>
                        `).join('') : '<tr><td colspan="5" class="table-empty">No invoices yet</td></tr>'}
                    </tbody>
                </table>
            </div>
        `;

        // Upcoming Dues
        document.getElementById('upcomingDues').innerHTML = `
            <div class="table-header">
                <span class="table-title">Upcoming Dues</span>
            </div>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Invoice #</th>
                            <th>Company</th>
                            <th>Due Date</th>
                            <th>Pending</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${upcoming.length ? upcoming.map(inv => `
                            <tr>
                                <td style="font-weight:600">${inv.invoice_number}</td>
                                <td>${inv.company_name}</td>
                                <td>
                                    ${formatDate(inv.due_date)}
                                    ${inv.is_overdue ? '<span class="badge badge-overdue" style="margin-left:6px">Overdue</span>' : ''}
                                </td>
                                <td style="font-weight:600;color:var(--danger)">${formatINR(inv.pending_amount)}</td>
                                <td>${statusBadge(inv.invoice_status)}</td>
                            </tr>
                        `).join('') : '<tr><td colspan="5" class="table-empty">No pending dues</td></tr>'}
                    </tbody>
                </table>
            </div>
        `;

    } catch (e) {
        showToast('Failed to load dashboard data', 'error');
    }
}

function statCard(icon, label, value, color, isCurrency = false) {
    return `
        <div class="stat-card">
            <div class="stat-icon ${color}">
                <span class="material-icons-round">${icon}</span>
            </div>
            <div class="stat-info">
                <div class="stat-label">${label}</div>
                <div class="stat-value ${isCurrency ? 'currency' : ''}">${value}</div>
            </div>
        </div>
    `;
}

function renderBarChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const maxVal = Math.max(...data.map(d => d.revenue), 1);

    container.innerHTML = data.map(d => `
        <div class="bar-group">
            <div class="bar-value">${d.revenue > 0 ? formatINRCompact(d.revenue) : ''}</div>
            <div class="bar primary" style="height: ${(d.revenue / maxVal) * 170}px" title="${formatINR(d.revenue)}"></div>
            <div class="bar-label">${d.month}</div>
        </div>
    `).join('');
}

function renderDonutChart(containerId, stats) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const paid = stats.paid_revenue || 0;
    const pending = stats.pending_revenue || 0;
    const total = paid + pending || 1;
    const paidPct = (paid / total) * 100;
    const pendingPct = (pending / total) * 100;

    container.innerHTML = `
        <div class="donut" style="background: conic-gradient(var(--success) 0% ${paidPct}%, var(--warning) ${paidPct}% 100%)">
            <div class="donut-center">
                <div class="donut-center-value">${paidPct.toFixed(0)}%</div>
                <div class="donut-center-label">Collected</div>
            </div>
        </div>
        <div class="donut-legend">
            <div class="legend-item">
                <div class="legend-dot" style="background:var(--success)"></div>
                <span class="legend-label">Paid</span>
                <span class="legend-value">${formatINRCompact(paid)}</span>
            </div>
            <div class="legend-item">
                <div class="legend-dot" style="background:var(--warning)"></div>
                <span class="legend-label">Pending</span>
                <span class="legend-value">${formatINRCompact(pending)}</span>
            </div>
            <div class="legend-item" style="margin-top:8px;padding-top:8px;border-top:1px solid var(--border)">
                <span class="legend-label" style="font-weight:600">Total</span>
                <span class="legend-value">${formatINRCompact(total)}</span>
            </div>
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════
// COMPANIES
// ═══════════════════════════════════════════════════════════
async function renderCompanies() {
    const content = document.getElementById('pageContent');
    content.innerHTML = `
        <div class="page-header">
            <div>
                <h1 class="page-title">Companies</h1>
                <p class="page-subtitle">Manage your client companies</p>
            </div>
            <button class="btn btn-primary" onclick="openCompanyModal()">
                <span class="material-icons-round">add</span> Add Company
            </button>
        </div>
        <div class="table-container">
            <div class="table-header">
                <div style="display:flex;align-items:center;gap:12px">
                    <span class="table-title" id="companyCount">Companies</span>
                </div>
                <input type="text" class="form-input" style="max-width:280px" placeholder="Search companies..." oninput="searchCompanies(this.value)">
            </div>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Company Name</th>
                            <th>GST Number</th>
                            <th>Contact Person</th>
                            <th>Mobile</th>
                            <th>Invoices</th>
                            <th>Revenue</th>
                            <th>Pending</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="companiesTableBody">
                        <tr><td colspan="8" class="table-empty"><span class="material-icons-round">hourglass_empty</span>Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;
    loadCompanies();
}

async function loadCompanies(search = '') {
    try {
        const q = search ? `?search=${encodeURIComponent(search)}` : '';
        const companies = await api(`/companies${q}`);
        const tbody = document.getElementById('companiesTableBody');
        document.getElementById('companyCount').textContent = `Companies (${companies.length})`;

        if (!companies.length) {
            tbody.innerHTML = `<tr><td colspan="8" class="table-empty">
                <span class="material-icons-round">business</span>
                No companies found. Add your first company!</td></tr>`;
            return;
        }

        tbody.innerHTML = companies.map(c => `
            <tr>
                <td style="font-weight:600">${c.company_name}</td>
                <td><code style="font-size:0.8rem;background:var(--bg-secondary);padding:2px 6px;border-radius:4px">${c.gst_number}</code></td>
                <td>${c.contact_person || '-'}</td>
                <td>${c.mobile || '-'}</td>
                <td style="text-align:center">${c.total_invoices}</td>
                <td style="font-weight:600">${formatINR(c.total_revenue)}</td>
                <td style="font-weight:600;color:${c.pending_amount > 0 ? 'var(--danger)' : 'var(--success)'}">${formatINR(c.pending_amount)}</td>
                <td>
                    <div class="action-row">
                        <button class="btn btn-ghost btn-icon" title="Edit" onclick="openCompanyModal('${c.gst_number}')">
                            <span class="material-icons-round" style="font-size:18px">edit</span>
                        </button>
                        <button class="btn btn-ghost btn-icon" title="Delete" onclick="deleteCompany('${c.gst_number}', '${c.company_name}')">
                            <span class="material-icons-round" style="font-size:18px;color:var(--danger)">delete</span>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        showToast('Failed to load companies', 'error');
    }
}

let companySearchTimeout;
function searchCompanies(query) {
    clearTimeout(companySearchTimeout);
    companySearchTimeout = setTimeout(() => loadCompanies(query), 300);
}

function openCompanyModal(gstNumber = null) {
    const isEdit = !!gstNumber;
    const title = isEdit ? 'Edit Company' : 'Add New Company';

    openModal(`
        <div class="modal-header">
            <h2 class="modal-title">${title}</h2>
            <button class="modal-close" onclick="forceCloseModal()"><span class="material-icons-round">close</span></button>
        </div>
        <div class="modal-body">
            <form id="companyForm" onsubmit="submitCompany(event, '${gstNumber || ''}')">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Company Name <span class="required">*</span></label>
                        <input type="text" class="form-input" id="companyName" required maxlength="255">
                    </div>
                    <div class="form-group">
                        <label class="form-label">GST Number <span class="required">*</span></label>
                        <input type="text" class="form-input" id="companyGst" required maxlength="15" minlength="15"
                            pattern="[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}"
                            style="text-transform:uppercase" ${isEdit ? 'disabled' : ''}
                            placeholder="e.g. 27AAACT2727Q1ZV">
                        <div class="form-hint">15-character GSTIN (e.g., 27AAACT2727Q1ZV)</div>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Contact Person</label>
                        <input type="text" class="form-input" id="companyContact" maxlength="255">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Mobile</label>
                        <input type="text" class="form-input" id="companyMobile" maxlength="15" placeholder="e.g. 9876543210">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Email</label>
                    <input type="email" class="form-input" id="companyEmail" maxlength="255">
                </div>
                <div class="form-group">
                    <label class="form-label">Address</label>
                    <textarea class="form-textarea" id="companyAddress" rows="2"></textarea>
                </div>
            </form>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="forceCloseModal()">Cancel</button>
            <button class="btn btn-primary" onclick="document.getElementById('companyForm').requestSubmit()">
                ${isEdit ? 'Update' : 'Save'} Company
            </button>
        </div>
    `);

    if (isEdit) loadCompanyForEdit(gstNumber);
}

async function loadCompanyForEdit(gstNumber) {
    try {
        const company = await api(`/companies/${gstNumber}`);
        document.getElementById('companyName').value = company.company_name;
        document.getElementById('companyGst').value = company.gst_number;
        document.getElementById('companyContact').value = company.contact_person || '';
        document.getElementById('companyMobile').value = company.mobile || '';
        document.getElementById('companyEmail').value = company.email || '';
        document.getElementById('companyAddress').value = company.address || '';
    } catch (e) {
        showToast('Failed to load company', 'error');
    }
}

async function submitCompany(event, gstNumber) {
    event.preventDefault();
    const data = {
        company_name: document.getElementById('companyName').value,
        gst_number: document.getElementById('companyGst').value.toUpperCase(),
        contact_person: document.getElementById('companyContact').value || null,
        mobile: document.getElementById('companyMobile').value || null,
        email: document.getElementById('companyEmail').value || null,
        address: document.getElementById('companyAddress').value || null,
    };

    try {
        if (gstNumber) {
            await api(`/companies/${gstNumber}`, { method: 'PUT', body: JSON.stringify(data) });
            showToast('Company updated successfully');
        } else {
            await api('/companies', { method: 'POST', body: JSON.stringify(data) });
            showToast('Company added successfully');
        }
        forceCloseModal();
        renderCompanies();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteCompany(gstNumber, name) {
    if (!confirm(`Delete "${name}" and all its invoices? This cannot be undone.`)) return;
    try {
        await api(`/companies/${gstNumber}`, { method: 'DELETE' });
        showToast('Company deleted');
        renderCompanies();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════
// INVOICES
// ═══════════════════════════════════════════════════════════
async function renderInvoices() {
    const content = document.getElementById('pageContent');
    content.innerHTML = `
        <div class="page-header">
            <div>
                <h1 class="page-title">Invoices</h1>
                <p class="page-subtitle">Manage and track all your invoices</p>
            </div>
            <button class="btn btn-primary" onclick="openCreateInvoiceModal()">
                <span class="material-icons-round">add</span> New Invoice
            </button>
        </div>
        <div class="filters-bar">
            <div class="filter-group">
                <label class="filter-label">Status</label>
                <select class="filter-select" id="filterStatus" onchange="applyInvoiceFilters()">
                    <option value="">All</option>
                    <option value="Unpaid">Unpaid</option>
                    <option value="Partially Paid">Partially Paid</option>
                    <option value="Paid">Paid</option>
                </select>
            </div>
            <div class="filter-group">
                <label class="filter-label">Year</label>
                <select class="filter-select" id="filterYear" onchange="applyInvoiceFilters()">
                    <option value="">All</option>
                    ${[2026, 2025, 2024].map(y => `<option value="${y}" ${y === new Date().getFullYear() ? 'selected' : ''}>${y}</option>`).join('')}
                </select>
            </div>
            <div class="filter-group">
                <label class="filter-label">Month</label>
                <select class="filter-select" id="filterMonth" onchange="applyInvoiceFilters()">
                    <option value="">All</option>
                    ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'].map((m, i) => `<option value="${i + 1}">${m}</option>`).join('')}
                </select>
            </div>
            <input type="text" class="form-input" style="max-width:250px" placeholder="Search invoices..." id="invoiceSearch" oninput="applyInvoiceFilters()">
        </div>
        <div class="table-container">
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Invoice #</th>
                            <th>Company</th>
                            <th>Date</th>
                            <th>Due Date</th>
                            <th>Invoice Amt</th>
                            <th>GST</th>
                            <th>TDS</th>
                            <th>Net Receivable</th>
                            <th>Paid</th>
                            <th>Pending</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="invoicesTableBody">
                        <tr><td colspan="12" class="table-empty"><span class="material-icons-round">hourglass_empty</span>Loading...</td></tr>
                    </tbody>
                </table>
            </div>
            <div class="table-pagination" id="invoicePagination"></div>
        </div>
    `;
    applyInvoiceFilters();
}

async function applyInvoiceFilters() {
    const status = document.getElementById('filterStatus')?.value || '';
    const year = document.getElementById('filterYear')?.value || '';
    const month = document.getElementById('filterMonth')?.value || '';
    const search = document.getElementById('invoiceSearch')?.value || '';

    let params = `?page=${invoicePage}&page_size=15`;
    if (status) params += `&status=${encodeURIComponent(status)}`;
    if (year) params += `&year=${year}`;
    if (month) params += `&month=${month}`;
    if (search) params += `&search=${encodeURIComponent(search)}`;

    try {
        const data = await api(`/invoices${params}`);
        renderInvoiceTable(data);
    } catch (e) {
        showToast('Failed to load invoices', 'error');
    }
}

function renderInvoiceTable(data) {
    const tbody = document.getElementById('invoicesTableBody');
    if (!data.items.length) {
        tbody.innerHTML = `<tr><td colspan="12" class="table-empty">
            <span class="material-icons-round">description</span>
            No invoices found</td></tr>`;
        document.getElementById('invoicePagination').innerHTML = '';
        return;
    }

    tbody.innerHTML = data.items.map(inv => `
        <tr>
            <td><a href="#" onclick="viewInvoiceDetail('${inv.invoice_number}');return false;" style="font-weight:600;color:var(--primary);text-decoration:none">${inv.invoice_number}</a></td>
            <td>${inv.company_name}</td>
            <td>${formatDate(inv.invoice_date)}</td>
            <td>${formatDate(inv.due_date)}</td>
            <td>${formatINR(inv.invoice_amount)}</td>
            <td>${formatINR(inv.gst_amount)}</td>
            <td style="color:var(--danger)">${formatINR(inv.tds_amount)}</td>
            <td style="font-weight:600">${formatINR(inv.net_receivable)}</td>
            <td style="color:var(--success)">${formatINR(inv.total_paid)}</td>
            <td style="font-weight:600;color:${inv.pending_amount > 0 ? 'var(--danger)' : 'var(--success)'}">${formatINR(inv.pending_amount)}</td>
            <td>${statusBadge(inv.invoice_status)}</td>
            <td>
                <div class="action-row">
                    <button class="btn btn-ghost btn-icon" title="Record Payment" onclick="openPaymentModal('${inv.invoice_number}')">
                        <span class="material-icons-round" style="font-size:18px;color:var(--success)">payments</span>
                    </button>
                    <button class="btn btn-ghost btn-icon" title="Delete" onclick="deleteInvoice('${inv.invoice_number}')">
                        <span class="material-icons-round" style="font-size:18px;color:var(--danger)">delete</span>
                    </button>
                </div>
            </td>
        </tr>
    `).join('');

    // Pagination
    const pagEl = document.getElementById('invoicePagination');
    pagEl.innerHTML = `
        <div class="pagination-info">Showing ${(data.page - 1) * data.page_size + 1}-${Math.min(data.page * data.page_size, data.total)} of ${data.total} invoices</div>
        <div class="pagination-controls">
            <button class="pagination-btn" ${data.page <= 1 ? 'disabled' : ''} onclick="invoicePage=${data.page - 1};applyInvoiceFilters()">Prev</button>
            ${Array.from({ length: Math.min(data.total_pages, 5) }, (_, i) => {
                const p = i + 1;
                return `<button class="pagination-btn ${p === data.page ? 'active' : ''}" onclick="invoicePage=${p};applyInvoiceFilters()">${p}</button>`;
            }).join('')}
            <button class="pagination-btn" ${data.page >= data.total_pages ? 'disabled' : ''} onclick="invoicePage=${data.page + 1};applyInvoiceFilters()">Next</button>
        </div>
    `;
}

async function viewInvoiceDetail(invoiceNumber) {
    try {
        const inv = await api(`/invoices/${invoiceNumber}`);
        openModal(`
            <div class="modal-header">
                <h2 class="modal-title">Invoice ${inv.invoice_number}</h2>
                <button class="modal-close" onclick="forceCloseModal()"><span class="material-icons-round">close</span></button>
            </div>
            <div class="modal-body">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
                    <div>
                        <div style="font-size:0.82rem;color:var(--text-tertiary)">Company</div>
                        <div style="font-weight:600;font-size:1.05rem">${inv.company_name}</div>
                        <div style="font-size:0.8rem;color:var(--text-tertiary)">GST: ${inv.gst_number}</div>
                    </div>
                    ${statusBadge(inv.invoice_status)}
                </div>

                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Invoice Date</div>
                        <div class="detail-value">${formatDate(inv.invoice_date)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Due Date</div>
                        <div class="detail-value">${formatDate(inv.due_date)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Site Location</div>
                        <div class="detail-value">${inv.site_location || '-'}</div>
                    </div>
                </div>

                ${inv.work_description ? `<div style="margin-bottom:16px"><div class="detail-label">Work Description</div><div style="font-size:0.9rem;color:var(--text-secondary)">${inv.work_description}</div></div>` : ''}

                <div class="amount-breakdown">
                    <div class="calc-preview-title">Amount Breakdown</div>
                    <div class="calc-row"><span class="calc-label">Invoice Amount</span><span class="calc-value">${formatINR(inv.invoice_amount)}</span></div>
                    <div class="calc-row"><span class="calc-label">GST (${inv.gst_percentage}%)</span><span class="calc-value">+ ${formatINR(inv.gst_amount)}</span></div>
                    <div class="calc-row" style="border-top:1px dashed var(--border);padding-top:6px;margin-top:4px"><span class="calc-label" style="font-weight:600">Total Amount</span><span class="calc-value">${formatINR(inv.total_amount)}</span></div>
                    <div class="calc-row"><span class="calc-label">TDS Deduction (${inv.tds_percentage}%)</span><span class="calc-value deduction">- ${formatINR(inv.tds_amount)}</span></div>
                    <div class="calc-row"><span class="calc-label">Retention (${inv.retention_percentage}%)</span><span class="calc-value deduction">- ${formatINR(inv.retention_amount)}</span></div>
                    <div class="calc-row total"><span class="calc-label">Net Receivable</span><span class="calc-value highlight">${formatINR(inv.net_receivable)}</span></div>
                    <div class="calc-row" style="margin-top:8px"><span class="calc-label">Total Paid</span><span class="calc-value" style="color:var(--success)">${formatINR(inv.total_paid)}</span></div>
                    <div class="calc-row"><span class="calc-label" style="font-weight:700">Pending Amount</span><span class="calc-value" style="color:var(--danger);font-weight:700">${formatINR(inv.pending_amount)}</span></div>
                </div>

                ${inv.payments.length ? `
                    <div style="margin-top:16px">
                        <div class="detail-label" style="margin-bottom:8px">Payment History</div>
                        <table style="width:100%">
                            <thead><tr><th>Date</th><th>Amount</th><th>Mode</th><th>Reference</th></tr></thead>
                            <tbody>
                                ${inv.payments.map(p => `
                                    <tr>
                                        <td>${formatDate(p.payment_date)}</td>
                                        <td style="font-weight:600;color:var(--success)">${formatINR(p.amount_received)}</td>
                                        <td>${p.payment_mode}</td>
                                        <td>${p.reference_number || '-'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                ` : ''}
            </div>
            <div class="modal-footer">
                <button class="btn btn-secondary" onclick="forceCloseModal()">Close</button>
                <button class="btn btn-success" onclick="forceCloseModal();openPaymentModal('${inv.invoice_number}')">
                    <span class="material-icons-round">payments</span> Record Payment
                </button>
            </div>
        `);
    } catch (e) {
        showToast('Failed to load invoice details', 'error');
    }
}

async function openCreateInvoiceModal() {
    let companies = [];
    try { companies = await api('/companies'); } catch (e) { /* */ }

    const settings = getSettings();

    openModal(`
        <div class="modal-header">
            <h2 class="modal-title">Create New Invoice</h2>
            <button class="modal-close" onclick="forceCloseModal()"><span class="material-icons-round">close</span></button>
        </div>
        <div class="modal-body">
            <form id="invoiceForm" onsubmit="submitInvoice(event)">
                <div class="form-section-title">Invoice Details</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Invoice Number <span class="required">*</span></label>
                        <div class="input-group">
                            <span class="input-prefix" id="invPrefix">INV-${new Date().getFullYear()}-</span>
                            <input type="text" class="form-input" id="invNumber" required style="text-transform:uppercase" placeholder="007">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Company <span class="required">*</span></label>
                        <select class="form-select" id="invCompany" required>
                            <option value="">Select Company</option>
                            ${companies.map(c => `<option value="${c.gst_number}">${c.company_name} (${c.gst_number})</option>`).join('')}
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Invoice Date <span class="required">*</span></label>
                        <input type="date" class="form-input" id="invDate" required value="${new Date().toISOString().split('T')[0]}" onchange="updateInvoicePrefix()">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Due Date <span class="required">*</span></label>
                        <input type="date" class="form-input" id="invDueDate" required value="${new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0]}">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Work Description</label>
                    <textarea class="form-textarea" id="invDescription" rows="2" placeholder="Brief description of work done"></textarea>
                </div>
                <div class="form-group">
                    <label class="form-label">Site Location</label>
                    <input type="text" class="form-input" id="invLocation" placeholder="e.g. Mumbai Office">
                </div>

                <div class="form-section-title">Financial Details</div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Invoice Amount (\u20B9) <span class="required">*</span></label>
                        <input type="number" class="form-input" id="invAmount" required min="1" step="0.01" placeholder="e.g. 500000" oninput="updateCalcPreview()">
                    </div>
                    <div class="form-group">
                        <label class="form-label">GST %</label>
                        <select class="form-select" id="invGstPct" onchange="updateCalcPreview()">
                            ${[0, 5, 12, 18, 28].map(v => `<option value="${v}" ${v === settings.defaultGstPct ? 'selected' : ''}>${v}%</option>`).join('')}
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">TDS %</label>
                        <input type="number" class="form-input" id="invTdsPct" value="${settings.defaultTdsPct}" min="0" max="100" step="0.01" oninput="updateCalcPreview()">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Retention %</label>
                        <input type="number" class="form-input" id="invRetPct" value="${settings.defaultRetPct}" min="0" max="100" step="0.01" oninput="updateCalcPreview()">
                    </div>
                </div>

                <div class="calc-preview" id="calcPreview">
                    <div class="calc-preview-title">Calculation Preview</div>
                    <div class="calc-row"><span class="calc-label">Enter invoice amount to see preview</span></div>
                </div>
            </form>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="forceCloseModal()">Cancel</button>
            <button class="btn btn-primary" onclick="document.getElementById('invoiceForm').requestSubmit()">
                <span class="material-icons-round">save</span> Create Invoice
            </button>
        </div>
    `);
}

function updateCalcPreview() {
    const amount = parseFloat(document.getElementById('invAmount')?.value) || 0;
    const gstPct = parseFloat(document.getElementById('invGstPct')?.value) || 0;
    const tdsPct = parseFloat(document.getElementById('invTdsPct')?.value) || 0;
    const retPct = parseFloat(document.getElementById('invRetPct')?.value) || 0;

    if (amount <= 0) return;

    const gstAmt = amount * (gstPct / 100);
    const totalAmt = amount + gstAmt;
    const tdsAmt = totalAmt * (tdsPct / 100);
    const retAmt = totalAmt * (retPct / 100);
    const netRec = totalAmt - tdsAmt - retAmt;

    document.getElementById('calcPreview').innerHTML = `
        <div class="calc-preview-title">Calculation Preview</div>
        <div class="calc-row"><span class="calc-label">Invoice Amount</span><span class="calc-value">${formatINR(amount)}</span></div>
        <div class="calc-row"><span class="calc-label">GST (${gstPct}%)</span><span class="calc-value">+ ${formatINR(gstAmt)}</span></div>
        <div class="calc-row" style="border-top:1px dashed var(--border);padding-top:6px;margin-top:4px"><span class="calc-label" style="font-weight:600">Total Amount</span><span class="calc-value">${formatINR(totalAmt)}</span></div>
        <div class="calc-row"><span class="calc-label">TDS Deduction (${tdsPct}%)</span><span class="calc-value deduction">- ${formatINR(tdsAmt)}</span></div>
        <div class="calc-row"><span class="calc-label">Retention (${retPct}%)</span><span class="calc-value deduction">- ${formatINR(retAmt)}</span></div>
        <div class="calc-row total"><span class="calc-label">Net Receivable</span><span class="calc-value highlight">${formatINR(netRec)}</span></div>
    `;
}

function updateInvoicePrefix() {
    const dateVal = document.getElementById('invDate')?.value;
    if (dateVal) {
        const year = dateVal.split('-')[0];
        const prefix = document.getElementById('invPrefix');
        if (prefix) prefix.textContent = 'INV-' + year + '-';
    }
}

async function submitInvoice(event) {
    event.preventDefault();
    const data = {
        invoice_number: (document.getElementById('invPrefix')?.textContent || 'INV-' + new Date().getFullYear() + '-') + document.getElementById('invNumber').value.toUpperCase(),
        gst_number: document.getElementById('invCompany').value,
        invoice_date: document.getElementById('invDate').value,
        due_date: document.getElementById('invDueDate').value,
        work_description: document.getElementById('invDescription').value || null,
        site_location: document.getElementById('invLocation').value || null,
        invoice_amount: parseFloat(document.getElementById('invAmount').value),
        gst_percentage: parseFloat(document.getElementById('invGstPct').value),
        tds_percentage: parseFloat(document.getElementById('invTdsPct').value),
        retention_percentage: parseFloat(document.getElementById('invRetPct').value),
    };

    try {
        await api('/invoices', { method: 'POST', body: JSON.stringify(data) });
        showToast('Invoice created successfully');
        forceCloseModal();
        if (currentPage === 'invoices') renderInvoices();
        else if (currentPage === 'dashboard') renderDashboard();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deleteInvoice(invoiceNumber) {
    if (!confirm(`Delete invoice ${invoiceNumber}? This cannot be undone.`)) return;
    try {
        await api(`/invoices/${invoiceNumber}`, { method: 'DELETE' });
        showToast('Invoice deleted');
        renderInvoices();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════
// PAYMENTS
// ═══════════════════════════════════════════════════════════
async function renderPayments() {
    const content = document.getElementById('pageContent');
    content.innerHTML = `
        <div class="page-header">
            <div>
                <h1 class="page-title">Payments</h1>
                <p class="page-subtitle">Track all payment transactions</p>
            </div>
        </div>
        <div class="table-container">
            <div class="table-header">
                <span class="table-title">All Payments</span>
                <input type="text" class="form-input" style="max-width:250px" placeholder="Search payments..." oninput="loadPayments(this.value)">
            </div>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Invoice #</th>
                            <th>Company</th>
                            <th>Date</th>
                            <th>Amount</th>
                            <th>Mode</th>
                            <th>Reference</th>
                            <th>Remarks</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="paymentsTableBody">
                        <tr><td colspan="9" class="table-empty"><span class="material-icons-round">hourglass_empty</span>Loading...</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    `;
    loadPayments();
}

async function loadPayments(search = '') {
    try {
        const q = search ? `?search=${encodeURIComponent(search)}` : '';
        const payments = await api(`/payments${q}`);
        const tbody = document.getElementById('paymentsTableBody');

        if (!payments.length) {
            tbody.innerHTML = `<tr><td colspan="9" class="table-empty"><span class="material-icons-round">payments</span>No payments recorded yet</td></tr>`;
            return;
        }

        tbody.innerHTML = payments.map(p => `
            <tr>
                <td>${p.payment_id}</td>
                <td style="font-weight:600;color:var(--primary)">${p.invoice_number}</td>
                <td>${p.company_name}</td>
                <td>${formatDate(p.payment_date)}</td>
                <td style="font-weight:600;color:var(--success)">${formatINR(p.amount_received)}</td>
                <td><span class="badge" style="background:var(--primary-50);color:var(--primary)">${p.payment_mode}</span></td>
                <td>${p.reference_number || '-'}</td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">${p.remarks || '-'}</td>
                <td>
                    <button class="btn btn-ghost btn-icon" title="Delete" onclick="deletePayment(${p.payment_id})">
                        <span class="material-icons-round" style="font-size:18px;color:var(--danger)">delete</span>
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        showToast('Failed to load payments', 'error');
    }
}

function openPaymentModal(invoiceNumber) {
    openModal(`
        <div class="modal-header">
            <h2 class="modal-title">Record Payment</h2>
            <button class="modal-close" onclick="forceCloseModal()"><span class="material-icons-round">close</span></button>
        </div>
        <div class="modal-body">
            <div style="background:var(--primary-50);padding:12px 16px;border-radius:var(--radius-md);margin-bottom:16px">
                <span style="font-size:0.82rem;color:var(--text-secondary)">Invoice:</span>
                <span style="font-weight:700;color:var(--primary)">${invoiceNumber}</span>
            </div>
            <form id="paymentForm" onsubmit="submitPayment(event, '${invoiceNumber}')">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Payment Date <span class="required">*</span></label>
                        <input type="date" class="form-input" id="payDate" required value="${new Date().toISOString().split('T')[0]}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Amount Received (\u20B9) <span class="required">*</span></label>
                        <input type="number" class="form-input" id="payAmount" required min="1" step="0.01">
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Payment Mode <span class="required">*</span></label>
                        <select class="form-select" id="payMode" required>
                            <option value="NEFT/RTGS">NEFT/RTGS</option>
                            <option value="Bank Transfer">Bank Transfer</option>
                            <option value="UPI">UPI</option>
                            <option value="Cheque">Cheque</option>
                            <option value="Cash">Cash</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Reference Number</label>
                        <input type="text" class="form-input" id="payRef" placeholder="e.g. UTR number">
                    </div>
                </div>
                <div class="form-group">
                    <label class="form-label">Remarks</label>
                    <textarea class="form-textarea" id="payRemarks" rows="2" placeholder="Any notes about this payment"></textarea>
                </div>
            </form>
        </div>
        <div class="modal-footer">
            <button class="btn btn-secondary" onclick="forceCloseModal()">Cancel</button>
            <button class="btn btn-success" onclick="document.getElementById('paymentForm').requestSubmit()">
                <span class="material-icons-round">check</span> Record Payment
            </button>
        </div>
    `);
}

async function submitPayment(event, invoiceNumber) {
    event.preventDefault();
    const data = {
        payment_date: document.getElementById('payDate').value,
        amount_received: parseFloat(document.getElementById('payAmount').value),
        payment_mode: document.getElementById('payMode').value,
        reference_number: document.getElementById('payRef').value || null,
        remarks: document.getElementById('payRemarks').value || null,
    };

    try {
        await api(`/invoices/${invoiceNumber}/payments`, { method: 'POST', body: JSON.stringify(data) });
        showToast('Payment recorded successfully');
        forceCloseModal();
        if (currentPage === 'payments') renderPayments();
        else if (currentPage === 'invoices') renderInvoices();
        else if (currentPage === 'dashboard') renderDashboard();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

async function deletePayment(paymentId) {
    if (!confirm('Delete this payment?')) return;
    try {
        await api(`/payments/${paymentId}`, { method: 'DELETE' });
        showToast('Payment deleted');
        if (currentPage === 'payments') renderPayments();
        else if (currentPage === 'invoices') renderInvoices();
    } catch (e) {
        showToast(e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════
// REPORTS
// ═══════════════════════════════════════════════════════════
let activeReportTab = 'monthly';

async function renderReports() {
    const content = document.getElementById('pageContent');
    content.innerHTML = `
        <div class="page-header">
            <div>
                <h1 class="page-title">Reports</h1>
                <p class="page-subtitle">Financial reports and analytics</p>
            </div>
        </div>
        <div class="tabs">
            <button class="tab active" data-tab="monthly" onclick="switchReportTab('monthly')">Monthly</button>
            <button class="tab" data-tab="yearly" onclick="switchReportTab('yearly')">Yearly</button>
            <button class="tab" data-tab="company" onclick="switchReportTab('company')">Company-wise</button>
        </div>
        <div id="reportContent"></div>
    `;
    switchReportTab('monthly');
}

function switchReportTab(tab) {
    activeReportTab = tab;
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
    switch (tab) {
        case 'monthly': renderMonthlyReport(); break;
        case 'yearly': renderYearlyReport(); break;
        case 'company': renderCompanyReport(); break;
    }
}

async function renderMonthlyReport() {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1;

    const container = document.getElementById('reportContent');
    container.innerHTML = `
        <div class="filters-bar">
            <div class="filter-group">
                <label class="filter-label">Year</label>
                <select class="filter-select" id="rptMonthYear" onchange="loadMonthlyReport()">
                    ${[2026, 2025, 2024].map(y => `<option value="${y}" ${y === year ? 'selected' : ''}>${y}</option>`).join('')}
                </select>
            </div>
            <div class="filter-group">
                <label class="filter-label">Month</label>
                <select class="filter-select" id="rptMonth" onchange="loadMonthlyReport()">
                    ${['January','February','March','April','May','June','July','August','September','October','November','December'].map((m, i) =>
                        `<option value="${i + 1}" ${i + 1 === month ? 'selected' : ''}>${m}</option>`).join('')}
                </select>
            </div>
        </div>
        <div id="monthlyReportData"><div class="skeleton skeleton-card" style="height:300px"></div></div>
    `;
    loadMonthlyReport();
}

async function loadMonthlyReport() {
    const year = document.getElementById('rptMonthYear').value;
    const month = document.getElementById('rptMonth').value;
    try {
        const data = await api(`/reports/monthly?year=${year}&month=${month}`);
        const months = ['','January','February','March','April','May','June','July','August','September','October','November','December'];
        document.getElementById('monthlyReportData').innerHTML = `
            <div class="report-summary">
                <div class="report-stat"><div class="report-stat-label">Total Invoices</div><div class="report-stat-value">${data.total_invoices}</div></div>
                <div class="report-stat"><div class="report-stat-label">Total Revenue</div><div class="report-stat-value">${formatINR(data.total_revenue)}</div></div>
                <div class="report-stat"><div class="report-stat-label">Paid</div><div class="report-stat-value" style="color:var(--success)">${formatINR(data.total_paid)}</div></div>
                <div class="report-stat"><div class="report-stat-label">Pending</div><div class="report-stat-value" style="color:var(--danger)">${formatINR(data.pending_revenue)}</div></div>
                <div class="report-stat"><div class="report-stat-label">TDS Deducted</div><div class="report-stat-value">${formatINR(data.tds_deducted)}</div></div>
                <div class="report-stat"><div class="report-stat-label">Retention</div><div class="report-stat-value">${formatINR(data.retention_amount)}</div></div>
            </div>
            ${data.invoices.length ? `
                <div class="table-container">
                    <div class="table-header"><span class="table-title">${months[month]} ${year} - Invoice Details</span></div>
                    <div class="table-wrapper">
                        <table>
                            <thead><tr><th>Invoice #</th><th>Company</th><th>Date</th><th>Invoice Amt</th><th>GST</th><th>TDS</th><th>Net Receivable</th><th>Paid</th><th>Pending</th><th>Status</th></tr></thead>
                            <tbody>
                                ${data.invoices.map(inv => `
                                    <tr>
                                        <td style="font-weight:600">${inv.invoice_number}</td>
                                        <td>${inv.company_name}</td>
                                        <td>${formatDate(inv.invoice_date)}</td>
                                        <td>${formatINR(inv.invoice_amount)}</td>
                                        <td>${formatINR(inv.gst_amount)}</td>
                                        <td style="color:var(--danger)">${formatINR(inv.tds_amount)}</td>
                                        <td style="font-weight:600">${formatINR(inv.net_receivable)}</td>
                                        <td style="color:var(--success)">${formatINR(inv.total_paid)}</td>
                                        <td style="color:var(--danger)">${formatINR(inv.pending)}</td>
                                        <td>${statusBadge(inv.status)}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            ` : '<div class="empty-state"><span class="material-icons-round">assessment</span><h3>No Data</h3><p>No invoices found for this month</p></div>'}
        `;
    } catch (e) {
        showToast('Failed to load monthly report', 'error');
    }
}

async function renderYearlyReport() {
    const container = document.getElementById('reportContent');
    container.innerHTML = `
        <div class="filters-bar">
            <div class="filter-group">
                <label class="filter-label">Year</label>
                <select class="filter-select" id="rptYear" onchange="loadYearlyReport()">
                    ${[2026, 2025, 2024].map(y => `<option value="${y}" ${y === new Date().getFullYear() ? 'selected' : ''}>${y}</option>`).join('')}
                </select>
            </div>
        </div>
        <div id="yearlyReportData"><div class="skeleton skeleton-card" style="height:300px"></div></div>
    `;
    loadYearlyReport();
}

async function loadYearlyReport() {
    const year = document.getElementById('rptYear').value;
    try {
        const data = await api(`/reports/yearly?year=${year}`);
        document.getElementById('yearlyReportData').innerHTML = `
            <div class="report-summary">
                <div class="report-stat"><div class="report-stat-label">Total Invoices</div><div class="report-stat-value">${data.total_invoices}</div></div>
                <div class="report-stat"><div class="report-stat-label">Annual Revenue</div><div class="report-stat-value">${formatINR(data.total_revenue)}</div></div>
                <div class="report-stat"><div class="report-stat-label">Total Paid</div><div class="report-stat-value" style="color:var(--success)">${formatINR(data.total_paid)}</div></div>
                <div class="report-stat"><div class="report-stat-label">Total Pending</div><div class="report-stat-value" style="color:var(--danger)">${formatINR(data.total_pending)}</div></div>
                <div class="report-stat"><div class="report-stat-label">Total TDS</div><div class="report-stat-value">${formatINR(data.total_tds)}</div></div>
                <div class="report-stat"><div class="report-stat-label">Total Retention</div><div class="report-stat-value">${formatINR(data.total_retention)}</div></div>
            </div>
            <div class="table-container">
                <div class="table-header"><span class="table-title">Month-wise Breakdown - ${year}</span></div>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Month</th><th>Invoices</th><th>Revenue</th><th>Paid</th><th>Pending</th><th>TDS</th><th>Retention</th></tr></thead>
                        <tbody>
                            ${data.monthly_data.map(m => `
                                <tr ${m.invoice_count === 0 ? 'style="opacity:0.4"' : ''}>
                                    <td style="font-weight:600">${m.month}</td>
                                    <td style="text-align:center">${m.invoice_count}</td>
                                    <td style="font-weight:600">${formatINR(m.revenue)}</td>
                                    <td style="color:var(--success)">${formatINR(m.paid)}</td>
                                    <td style="color:var(--danger)">${formatINR(m.pending)}</td>
                                    <td>${formatINR(m.tds)}</td>
                                    <td>${formatINR(m.retention)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                        <tfoot>
                            <tr style="font-weight:700;background:var(--bg-secondary)">
                                <td>TOTAL</td>
                                <td style="text-align:center">${data.total_invoices}</td>
                                <td>${formatINR(data.total_revenue)}</td>
                                <td style="color:var(--success)">${formatINR(data.total_paid)}</td>
                                <td style="color:var(--danger)">${formatINR(data.total_pending)}</td>
                                <td>${formatINR(data.total_tds)}</td>
                                <td>${formatINR(data.total_retention)}</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </div>
        `;
    } catch (e) {
        showToast('Failed to load yearly report', 'error');
    }
}

async function renderCompanyReport() {
    const container = document.getElementById('reportContent');
    container.innerHTML = `<div id="companyReportData"><div class="skeleton skeleton-card" style="height:300px"></div></div>`;
    try {
        const data = await api('/reports/company');
        document.getElementById('companyReportData').innerHTML = `
            <div class="table-container">
                <div class="table-header"><span class="table-title">Company-wise Financial Summary</span></div>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Company</th><th>GST Number</th><th>Invoices</th><th>Total Revenue</th><th>Paid</th><th>Pending</th><th>TDS Deducted</th><th>Retention Held</th></tr></thead>
                        <tbody>
                            ${data.map(c => `
                                <tr>
                                    <td style="font-weight:600">${c.company_name}</td>
                                    <td><code style="font-size:0.8rem;background:var(--bg-secondary);padding:2px 6px;border-radius:4px">${c.gst_number}</code></td>
                                    <td style="text-align:center">${c.total_invoices}</td>
                                    <td style="font-weight:600">${formatINR(c.total_revenue)}</td>
                                    <td style="color:var(--success)">${formatINR(c.total_paid)}</td>
                                    <td style="font-weight:600;color:var(--danger)">${formatINR(c.total_pending)}</td>
                                    <td>${formatINR(c.tds_deducted)}</td>
                                    <td>${formatINR(c.retention_held)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    } catch (e) {
        showToast('Failed to load company report', 'error');
    }
}

// ═══════════════════════════════════════════════════════════
// RECONCILIATION CENTER
// ═══════════════════════════════════════════════════════════
let reconTab = 'all';
let reconSummaryData = null;

async function renderReconciliation() {
    document.getElementById('pageContent').innerHTML = `
        <div class="page-header">
            <div>
                <h1 class="page-title">Reconciliation Center</h1>
                <p class="page-subtitle">Import bank statements & auto-match payments</p>
            </div>
            <div style="display:flex;gap:8px">
                <button class="btn btn-secondary" onclick="navigate('reconciliation-aging')">
                    <span class="material-icons-round">schedule</span> Aging Report
                </button>
                <button class="btn btn-secondary" onclick="navigate('reconciliation-ledger')">
                    <span class="material-icons-round">menu_book</span> Company Ledger
                </button>
            </div>
        </div>

        <!-- Upload Section -->
        <div class="card" style="margin-bottom:20px">
            <div class="card-header"><h3 class="card-title">Upload Bank Statement</h3></div>
            <div style="display:flex;gap:16px;margin-bottom:16px;flex-wrap:wrap">
                <div class="form-group" style="min-width:200px;flex:1">
                    <label class="form-label">Bank</label>
                    <select class="form-input" id="bankSelect">
                        <option value="">Select Bank...</option>
                    </select>
                </div>
            </div>
            <div class="upload-zone" id="uploadZone"
                 onclick="document.getElementById('stmtFile').click()"
                 ondragover="event.preventDefault();this.classList.add('drag-over')"
                 ondragleave="this.classList.remove('drag-over')"
                 ondrop="handleStatementDrop(event)">
                <span class="material-icons-round upload-icon">cloud_upload</span>
                <div class="upload-text">Drag & drop your bank statement here</div>
                <div class="upload-hint">Supports PDF, CSV, XLSX, XLS</div>
                <input type="file" id="stmtFile" accept=".pdf,.csv,.xlsx,.xls" style="display:none" onchange="handleStatementUpload(this)">
            </div>
            <div id="uploadProgress" style="display:none">
                <div class="upload-progress"><div class="upload-progress-bar" style="width:100%"></div></div>
                <p style="text-align:center;font-size:0.85rem;color:var(--text-secondary);margin-top:8px">Processing statement...</p>
            </div>
        </div>

        <!-- Summary Cards -->
        <div class="recon-summary" id="reconSummary">
            <div class="recon-stat"><div class="recon-stat-value">-</div><div class="recon-stat-label">Total Credits</div></div>
            <div class="recon-stat"><div class="recon-stat-value">-</div><div class="recon-stat-label">Matched</div></div>
            <div class="recon-stat"><div class="recon-stat-value">-</div><div class="recon-stat-label">Needs Review</div></div>
            <div class="recon-stat"><div class="recon-stat-value">-</div><div class="recon-stat-label">Unmatched</div></div>
            <div class="recon-stat"><div class="recon-stat-value">-</div><div class="recon-stat-label">Matched Amount</div></div>
        </div>

        <!-- Tabs + Transactions -->
        <div class="card">
            <div class="recon-tabs" id="reconTabs"></div>
            <div id="reconTransactions"><div style="text-align:center;padding:40px;color:var(--text-tertiary)">Loading transactions...</div></div>
        </div>
    `;

    // Load bank list
    try {
        const banks = await api('/bank-statements/banks');
        const select = document.getElementById('bankSelect');
        banks.forEach(b => {
            const opt = document.createElement('option');
            opt.value = b; opt.textContent = b;
            select.appendChild(opt);
        });
    } catch(e) {}

    loadReconSummary();
    loadReconTransactions();
}

async function loadReconSummary() {
    try {
        const s = await api('/reconciliation/summary');
        reconSummaryData = s;
        document.getElementById('reconSummary').innerHTML = `
            <div class="recon-stat"><div class="recon-stat-value">${s.total_transactions}</div><div class="recon-stat-label">Total Credits</div></div>
            <div class="recon-stat" style="border-left:3px solid var(--success)"><div class="recon-stat-value">${s.matched}</div><div class="recon-stat-label">Matched</div></div>
            <div class="recon-stat" style="border-left:3px solid var(--warning)"><div class="recon-stat-value">${s.needs_review}</div><div class="recon-stat-label">Needs Review</div></div>
            <div class="recon-stat" style="border-left:3px solid var(--text-tertiary)"><div class="recon-stat-value">${s.unmatched}</div><div class="recon-stat-label">Unmatched</div></div>
            <div class="recon-stat"><div class="recon-stat-value">${formatINRCompact(s.total_matched_amount)}</div><div class="recon-stat-label">Matched Amount</div></div>
        `;
        renderReconTabs(s);
    } catch(e) {}
}

function renderReconTabs(s) {
    const tabs = document.getElementById('reconTabs');
    if (!tabs) return;
    const counts = {
        all: s.total_transactions,
        Matched: s.matched,
        Needs_Review: s.needs_review,
        Unmatched: s.unmatched,
        Rejected: s.rejected,
    };
    tabs.innerHTML = ['all','Matched','Needs_Review','Unmatched','Rejected'].map(t => {
        const label = t === 'all' ? 'All' : t.replace('_', ' ');
        return `<button class="recon-tab ${reconTab===t?'active':''}" onclick="reconTab='${t}';renderReconTabs(reconSummaryData);loadReconTransactions()">
            ${label} <span class="tab-count">${counts[t]||0}</span>
        </button>`;
    }).join('');
}

async function loadReconTransactions() {
    const container = document.getElementById('reconTransactions');
    if (!container) return;
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-tertiary)"><span class="material-icons-round" style="font-size:24px;animation:spin 1s linear infinite">autorenew</span><br>Loading...</div>';

    try {
        const status = reconTab === 'all' ? '' : reconTab;
        const url = '/reconciliation/transactions' + (status ? `?status=${status}` : '');
        const data = await api(url);

        if (!data.items || data.items.length === 0) {
            container.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-tertiary)">
                <span class="material-icons-round" style="font-size:40px;opacity:0.3;display:block;margin-bottom:8px">search_off</span>
                No transactions found${reconTab !== 'all' ? ' in this category' : ''}
            </div>`;
            return;
        }

        container.innerHTML = `
            <div style="overflow-x:auto">
                <table class="data-table">
                    <thead><tr>
                        <th>Date</th><th>Description</th><th>Amount</th><th>UTR/Ref</th>
                        <th>Status</th><th>Invoice</th><th>Confidence</th><th>Actions</th>
                    </tr></thead>
                    <tbody>
                        ${data.items.map(t => renderReconRow(t)).join('')}
                    </tbody>
                </table>
            </div>
        `;
    } catch(e) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--danger)">Failed to load transactions</div>';
    }
}

function renderReconRow(t) {
    const statusClass = t.match_status === 'Matched' ? 'status-matched' :
                        t.match_status === 'Needs_Review' ? 'status-needs-review' :
                        t.match_status === 'Rejected' ? 'status-rejected' : 'status-unmatched';
    const confClass = t.confidence_score >= 90 ? 'confidence-high' :
                      t.confidence_score >= 80 ? 'confidence-medium' : 'confidence-low';

    let actions = '';
    if (t.match_status === 'Needs_Review') {
        actions = `<div class="txn-actions">
            <button class="btn btn-primary" onclick="approveMatch(${t.transaction_id})">Approve</button>
            <button class="btn btn-secondary" onclick="rejectMatch(${t.transaction_id})">Reject</button>
        </div>`;
    } else if (t.match_status === 'Unmatched') {
        actions = `<button class="btn btn-secondary" onclick="openManualMatchModal(${t.transaction_id}, ${t.credit_amount})">Match</button>`;
    } else if (t.match_status === 'Matched' && t.confidence_score && t.confidence_score < 100) {
        actions = `<div class="txn-actions">
            <button class="btn btn-primary" onclick="approveMatch(${t.transaction_id})">Confirm</button>
            <button class="btn btn-secondary" onclick="rejectMatch(${t.transaction_id})">Reject</button>
        </div>`;
    }

    const desc = (t.description || '').length > 50 ? t.description.substring(0, 50) + '...' : (t.description || '-');

    return `<tr>
        <td>${t.transaction_date || '-'}</td>
        <td title="${t.description || ''}" style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${desc}</td>
        <td style="font-weight:600;color:var(--success)">${formatINR(t.credit_amount)}</td>
        <td style="font-size:0.8rem">${t.utr_number || t.reference_number || '-'}</td>
        <td><span class="badge ${statusClass}" style="padding:3px 10px;border-radius:12px;font-size:0.75rem">${t.match_status.replace('_',' ')}</span></td>
        <td>${t.matched_invoice_number ? `<a href="#" onclick="navigate('invoices');return false" style="color:var(--primary);font-weight:500">${t.matched_invoice_number}</a>` : '-'}</td>
        <td>${t.confidence_score ? `<span class="confidence-badge ${confClass}">${t.confidence_score}%</span>` : '-'}</td>
        <td>${actions}</td>
    </tr>`;
}

// Upload handlers
function handleStatementDrop(event) {
    event.preventDefault();
    event.currentTarget.classList.remove('drag-over');
    const file = event.dataTransfer.files[0];
    if (file) uploadStatement(file);
}

function handleStatementUpload(input) {
    const file = input.files[0];
    if (file) uploadStatement(file);
    input.value = '';
}

async function uploadStatement(file) {
    const bankName = document.getElementById('bankSelect').value;
    if (!bankName) { showToast('Please select a bank first', 'error'); return; }

    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf','csv','xlsx','xls'].includes(ext)) {
        showToast('Unsupported file format. Use PDF, CSV, XLSX, or XLS.', 'error');
        return;
    }

    document.getElementById('uploadProgress').style.display = 'block';
    document.getElementById('uploadZone').style.display = 'none';

    const formData = new FormData();
    formData.append('file', file);
    formData.append('bank_name', bankName);

    try {
        const resp = await fetch(API + '/bank-statements/upload', {
            method: 'POST', body: formData,
        });
        const result = await resp.json();
        if (!resp.ok) throw new Error(result.detail || 'Upload failed');

        showToast(`Statement processed! ${result.total_transactions} transactions found. ${result.reconciliation.matched} auto-matched.`);
        document.getElementById('uploadProgress').style.display = 'none';
        document.getElementById('uploadZone').style.display = '';
        loadReconSummary();
        loadReconTransactions();
    } catch(e) {
        showToast('Upload failed: ' + e.message, 'error');
        document.getElementById('uploadProgress').style.display = 'none';
        document.getElementById('uploadZone').style.display = '';
    }
}

async function approveMatch(txnId) {
    try {
        await api(`/reconciliation/approve/${txnId}`, { method: 'POST' });
        showToast('Match approved — payment recorded');
        loadReconSummary();
        loadReconTransactions();
    } catch(e) { showToast('Approve failed: ' + e.message, 'error'); }
}

async function rejectMatch(txnId) {
    try {
        await api(`/reconciliation/reject/${txnId}`, { method: 'POST' });
        showToast('Match rejected');
        loadReconSummary();
        loadReconTransactions();
    } catch(e) { showToast('Reject failed: ' + e.message, 'error'); }
}

async function openManualMatchModal(txnId, amount) {
    try {
        const invoices = await api('/reconciliation/invoices');
        const rows = invoices.map(i => `
            <tr onclick="manualMatch(${txnId}, '${i.invoice_number}')" style="cursor:pointer" class="hover-row">
                <td style="font-weight:600">${i.invoice_number}</td>
                <td>${i.company_name}</td>
                <td>${formatINR(i.remaining)}</td>
                <td><span class="badge">${i.invoice_status}</span></td>
            </tr>
        `).join('');

        openModal(`
            <div class="modal-header">
                <h2 class="modal-title">Manual Match — ${formatINR(amount)}</h2>
                <button class="modal-close" onclick="forceCloseModal()"><span class="material-icons-round">close</span></button>
            </div>
            <div class="modal-body">
                <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:16px">Select an invoice to match this transaction to:</p>
                <div style="overflow-x:auto">
                    <table class="data-table">
                        <thead><tr><th>Invoice</th><th>Company</th><th>Remaining</th><th>Status</th></tr></thead>
                        <tbody>${rows || '<tr><td colspan="4" style="text-align:center;padding:20px;color:var(--text-tertiary)">No outstanding invoices</td></tr>'}</tbody>
                    </table>
                </div>
            </div>
        `);
    } catch(e) { showToast('Failed to load invoices', 'error'); }
}

async function manualMatch(txnId, invoiceNumber) {
    try {
        await api('/reconciliation/manual-match', {
            method: 'POST',
            body: JSON.stringify({ transaction_id: txnId, invoice_number: invoiceNumber }),
        });
        forceCloseModal();
        showToast('Manually matched & payment created');
        loadReconSummary();
        loadReconTransactions();
    } catch(e) { showToast('Match failed: ' + e.message, 'error'); }
}

// ═══════════════════════════════════════════════════════════
// PAYMENT AGING REPORT
// ═══════════════════════════════════════════════════════════
async function renderAgingReport() {
    document.getElementById('pageContent').innerHTML = `
        <div class="page-header">
            <div>
                <h1 class="page-title">Payment Aging Report</h1>
                <p class="page-subtitle">Outstanding invoices grouped by age</p>
            </div>
            <div style="display:flex;gap:8px">
                <a href="${API}/reconciliation/export/aging" class="btn btn-secondary" download>
                    <span class="material-icons-round">download</span> Export CSV
                </a>
                <button class="btn btn-secondary" onclick="navigate('reconciliation')">
                    <span class="material-icons-round">arrow_back</span> Back
                </button>
            </div>
        </div>
        <div id="agingContent"><div style="text-align:center;padding:60px;color:var(--text-tertiary)">Loading...</div></div>
    `;

    try {
        const data = await api('/reconciliation/aging');
        if (!data.length) {
            document.getElementById('agingContent').innerHTML = '<div class="card" style="text-align:center;padding:60px;color:var(--text-tertiary)"><span class="material-icons-round" style="font-size:40px;opacity:0.3;display:block;margin-bottom:8px">check_circle</span>No outstanding invoices!</div>';
            return;
        }

        // Group by bucket
        const buckets = {};
        data.forEach(r => {
            if (!buckets[r.bucket]) buckets[r.bucket] = { items: [], total: 0 };
            buckets[r.bucket].items.push(r);
            buckets[r.bucket].total += r.outstanding;
        });

        const bucketOrder = ['0-30 Days', '31-60 Days', '61-90 Days', '91-180 Days', '180+ Days'];
        const bucketClasses = { '0-30 Days': 'aging-0-30', '31-60 Days': 'aging-31-60', '61-90 Days': 'aging-61-90', '91-180 Days': 'aging-91-180', '180+ Days': 'aging-180-plus' };

        let html = '<div class="recon-summary" style="margin-bottom:24px">';
        bucketOrder.forEach(b => {
            const count = buckets[b]?.items?.length || 0;
            const total = buckets[b]?.total || 0;
            html += `<div class="recon-stat ${bucketClasses[b]}"><div class="recon-stat-value">${count}</div><div class="recon-stat-label">${b}</div><div style="font-size:0.8rem;color:var(--text-secondary);margin-top:4px">${formatINRCompact(total)}</div></div>`;
        });
        html += '</div>';

        html += '<div class="card"><div style="overflow-x:auto"><table class="data-table"><thead><tr><th>Invoice</th><th>Company</th><th>Due Date</th><th>Outstanding</th><th>Days Pending</th><th>Bucket</th></tr></thead><tbody>';
        data.forEach(r => {
            const rowClass = r.days_pending > 90 ? 'style="background:#fff5f5"' : '';
            html += `<tr ${rowClass}>
                <td style="font-weight:600">${r.invoice_number}</td>
                <td>${r.company_name}</td>
                <td>${r.due_date || '-'}</td>
                <td style="font-weight:600">${formatINR(r.outstanding)}</td>
                <td>${r.days_pending > 0 ? `<span style="color:var(--danger);font-weight:600">${r.days_pending}d overdue</span>` : `${Math.abs(r.days_pending)}d remaining`}</td>
                <td><span class="badge" style="font-size:0.75rem">${r.bucket}</span></td>
            </tr>`;
        });
        html += '</tbody></table></div></div>';

        document.getElementById('agingContent').innerHTML = html;
    } catch(e) {
        document.getElementById('agingContent').innerHTML = '<div class="card" style="text-align:center;padding:40px;color:var(--danger)">Failed to load aging report</div>';
    }
}

// ═══════════════════════════════════════════════════════════
// COMPANY LEDGER
// ═══════════════════════════════════════════════════════════
async function renderLedgerPage() {
    const companies = await api('/companies').catch(() => []);
    document.getElementById('pageContent').innerHTML = `
        <div class="page-header">
            <div>
                <h1 class="page-title">Company Ledger</h1>
                <p class="page-subtitle">Detailed transaction history per company</p>
            </div>
            <button class="btn btn-secondary" onclick="navigate('reconciliation')">
                <span class="material-icons-round">arrow_back</span> Back
            </button>
        </div>
        <div class="card" style="margin-bottom:20px">
            <div class="form-group" style="max-width:400px">
                <label class="form-label">Select Company</label>
                <select class="form-input" id="ledgerCompanySelect" onchange="loadLedger(this.value)">
                    <option value="">Choose a company...</option>
                    ${companies.map(c => `<option value="${c.gst_number}">${c.company_name} (${c.gst_number})</option>`).join('')}
                </select>
            </div>
        </div>
        <div id="ledgerContent"></div>
    `;
}

async function loadLedger(gstNumber) {
    if (!gstNumber) { document.getElementById('ledgerContent').innerHTML = ''; return; }
    const container = document.getElementById('ledgerContent');
    container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-tertiary)">Loading ledger...</div>';

    try {
        const data = await api(`/reconciliation/ledger/${gstNumber}`);

        let html = `
        <div class="card" style="margin-bottom:16px">
            <div class="card-header">
                <h3 class="card-title">${data.company.company_name}</h3>
                <a href="${API}/reconciliation/export/ledger?gst_number=${gstNumber}" class="btn btn-secondary btn-sm" download>
                    <span class="material-icons-round" style="font-size:16px">download</span> Export CSV
                </a>
            </div>
            <div class="detail-grid" style="grid-template-columns:repeat(auto-fit,minmax(140px,1fr))">
                <div class="detail-item"><div class="detail-label">Total Invoiced</div><div class="detail-value">${formatINR(data.summary.total_invoiced)}</div></div>
                <div class="detail-item"><div class="detail-label">TDS Deducted</div><div class="detail-value">${formatINR(data.summary.total_tds)}</div></div>
                <div class="detail-item"><div class="detail-label">Retention Held</div><div class="detail-value">${formatINR(data.summary.total_retention)}</div></div>
                <div class="detail-item"><div class="detail-label">Net Receivable</div><div class="detail-value">${formatINR(data.summary.total_net_receivable)}</div></div>
                <div class="detail-item"><div class="detail-label">Total Received</div><div class="detail-value" style="color:var(--success)">${formatINR(data.summary.total_paid)}</div></div>
                <div class="detail-item"><div class="detail-label">Outstanding</div><div class="detail-value" style="color:var(--danger);font-weight:700">${formatINR(data.summary.outstanding)}</div></div>
            </div>
        </div>

        <div class="card">
            <div class="card-header"><h3 class="card-title">Transaction History</h3></div>
            <div style="overflow-x:auto">
                <table class="data-table">
                    <thead><tr>
                        <th>Date</th><th>Type</th><th>Reference</th><th>Description</th>
                        <th>Invoiced</th><th>TDS</th><th>Retention</th><th>Payment</th><th>Balance</th>
                    </tr></thead>
                    <tbody>
                        ${data.entries.map(e => `
                            <tr class="${e.type === 'Invoice' ? 'ledger-entry-invoice' : 'ledger-entry-payment'}">
                                <td>${e.date || '-'}</td>
                                <td><span class="badge ${e.type === 'Invoice' ? '' : 'status-matched'}" style="font-size:0.75rem">${e.type}</span></td>
                                <td style="font-weight:500;font-size:0.85rem">${e.reference}</td>
                                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${e.description}">${e.description || '-'}</td>
                                <td>${e.invoice_amount ? formatINR(e.invoice_amount) : ''}</td>
                                <td>${e.tds_deducted ? formatINR(e.tds_deducted) : ''}</td>
                                <td>${e.retention_held ? formatINR(e.retention_held) : ''}</td>
                                <td style="color:var(--success);font-weight:600">${e.payment_received ? formatINR(e.payment_received) : ''}</td>
                                <td style="font-weight:700">${formatINR(e.running_balance)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>`;

        container.innerHTML = html;
    } catch(e) {
        container.innerHTML = `<div class="card" style="text-align:center;padding:40px;color:var(--danger)">Failed to load ledger: ${e.message}</div>`;
    }
}

// ═══════════════════════════════════════════════════════════
// SETTINGS
// ═══════════════════════════════════════════════════════════
function renderSettings() {
    const settings = getSettings();
    document.getElementById('pageContent').innerHTML = `
        <div class="page-header">
            <div>
                <h1 class="page-title">Settings</h1>
                <p class="page-subtitle">Application preferences</p>
            </div>
        </div>
        <div class="card" style="max-width:600px">
            <div class="card-header"><h3 class="card-title">Application Info</h3></div>
            <div class="detail-grid" style="grid-template-columns:1fr 1fr">
                <div class="detail-item"><div class="detail-label">App Name</div><div class="detail-value">Contractor Invoice Management</div></div>
                <div class="detail-item"><div class="detail-label">Version</div><div class="detail-value">1.0.0</div></div>
                <div class="detail-item"><div class="detail-label">Backend</div><div class="detail-value">FastAPI + SQLite</div></div>
                <div class="detail-item"><div class="detail-label">Currency</div><div class="detail-value">INR (\u20B9)</div></div>
            </div>
        </div>
        <div class="card" style="max-width:600px;margin-top:16px;padding-bottom:0">
            <div class="card-header"><h3 class="card-title">Default Invoice Settings</h3></div>
            <form id="settingsForm" onsubmit="saveSettingsForm(event)">
                <div class="form-row">
                    <div class="form-group">
                        <label class="form-label">Default GST %</label>
                        <input type="number" class="form-input" id="settingGstPct" value="${settings.defaultGstPct}" min="0" max="100" step="0.01">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Default TDS %</label>
                        <input type="number" class="form-input" id="settingTdsPct" value="${settings.defaultTdsPct}" min="0" max="100" step="0.01">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Default Retention %</label>
                        <input type="number" class="form-input" id="settingRetPct" value="${settings.defaultRetPct}" min="0" max="100" step="0.01">
                    </div>
                </div>
                <div style="display:flex;justify-content:flex-end;padding:12px 0 20px;border-top:1px solid var(--border-light);margin-top:4px">
                    <button type="submit" class="btn btn-primary">
                        <span class="material-icons-round">save</span> Save Settings
                    </button>
                </div>
            </form>
        </div>

        <div class="card" style="max-width:600px;margin-top:16px">
            <div class="card-header">
                <h3 class="card-title">Backup & Restore</h3>
            </div>
            <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:16px">
                Protect your data by exporting backups. Auto-backups are created every time the server starts.
            </p>

            <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:20px">
                <button class="btn btn-primary" onclick="exportBackup()">
                    <span class="material-icons-round">download</span> Export JSON
                </button>
                <label class="btn btn-secondary" style="cursor:pointer">
                    <span class="material-icons-round">upload</span> Import JSON
                    <input type="file" accept=".json" style="display:none" onchange="importBackup(this)">
                </label>
                <button class="btn btn-secondary" onclick="createManualBackup()">
                    <span class="material-icons-round">backup</span> Create Backup Now
                </button>
            </div>

            <div style="border-top:1px solid var(--border-light);padding-top:16px">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
                    <span style="font-size:0.85rem;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.03em">Auto-Backups</span>
                    <button class="btn btn-ghost btn-sm" onclick="loadBackupList()">
                        <span class="material-icons-round" style="font-size:16px">refresh</span> Refresh
                    </button>
                </div>
                <div id="backupList">
                    <div style="text-align:center;padding:16px;color:var(--text-tertiary);font-size:0.85rem">Loading...</div>
                </div>
            </div>
        </div>
    `;
    loadBackupList();
}

function saveSettingsForm(event) {
    event.preventDefault();
    const gstPct = document.getElementById('settingGstPct').value;
    const tdsPct = document.getElementById('settingTdsPct').value;
    const retPct = document.getElementById('settingRetPct').value;
    saveSettings(gstPct, tdsPct, retPct);
    showToast('Settings saved successfully');
}

// ─── Backup Functions ─────────────────────────────────────
async function exportBackup() {
    try {
        const resp = await fetch(API + '/backup/export');
        if (!resp.ok) throw new Error('Export failed');
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `invoice_backup_${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        showToast('Backup exported successfully');
    } catch (e) {
        showToast('Export failed: ' + e.message, 'error');
    }
}

async function importBackup(input) {
    const file = input.files[0];
    if (!file) return;
    if (!file.name.endsWith('.json')) {
        showToast('Please select a .json backup file', 'error');
        return;
    }
    if (!confirm('WARNING: Importing will replace ALL existing data with the backup data. This cannot be undone.\\n\\nAre you sure you want to continue?')) {
        input.value = '';
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const resp = await fetch(API + '/backup/import', {
            method: 'POST',
            body: formData,
        });
        const result = await resp.json();
        if (!resp.ok) throw new Error(result.detail || 'Import failed');
        showToast(`Data restored! ${result.counts.companies} companies, ${result.counts.invoices} invoices, ${result.counts.payments} payments imported.`);
        input.value = '';
    } catch (e) {
        showToast('Import failed: ' + e.message, 'error');
        input.value = '';
    }
}

async function createManualBackup() {
    try {
        const result = await api('/backup/create', { method: 'POST' });
        showToast('Backup created: ' + result.filename);
        loadBackupList();
    } catch (e) {
        showToast('Backup failed: ' + e.message, 'error');
    }
}

async function loadBackupList() {
    try {
        const backups = await api('/backup/list');
        const container = document.getElementById('backupList');
        if (!container) return;

        if (!backups.length) {
            container.innerHTML = '<div style="text-align:center;padding:16px;color:var(--text-tertiary);font-size:0.85rem"><span class="material-icons-round" style="font-size:32px;display:block;margin-bottom:4px;opacity:0.3">cloud_off</span>No backups yet</div>';
            return;
        }

        container.innerHTML = backups.map(b => {
            const date = new Date(b.created);
            const sizeKB = (b.size / 1024).toFixed(1);
            const timeAgo = getTimeAgo(date);
            return `
                <div style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-radius:var(--radius);margin-bottom:4px;background:var(--bg-secondary);transition:background 0.15s" onmouseenter="this.style.background='var(--primary-50)'" onmouseleave="this.style.background='var(--bg-secondary)'">
                    <div style="display:flex;align-items:center;gap:10px">
                        <span class="material-icons-round" style="font-size:20px;color:var(--primary)">storage</span>
                        <div>
                            <div style="font-size:0.85rem;font-weight:600">${b.filename}</div>
                            <div style="font-size:0.75rem;color:var(--text-tertiary)">${sizeKB} KB · ${timeAgo}</div>
                        </div>
                    </div>
                    <a href="${API}/backup/download/${b.filename}" class="btn btn-ghost btn-sm" title="Download" style="color:var(--primary)">
                        <span class="material-icons-round" style="font-size:18px">download</span>
                    </a>
                </div>
            `;
        }).join('');
    } catch (e) {
        const container = document.getElementById('backupList');
        if (container) container.innerHTML = '<div style="text-align:center;padding:16px;color:var(--danger);font-size:0.85rem">Failed to load backups</div>';
    }
}

function getTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    if (seconds < 60) return 'Just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + 'm ago';
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + 'h ago';
    const days = Math.floor(hours / 24);
    if (days < 7) return days + 'd ago';
    return date.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ═══════════════════════════════════════════════════════════
// GLOBAL SEARCH
// ═══════════════════════════════════════════════════════════
let searchTimeout;
async function handleGlobalSearch(query) {
    const dropdown = document.getElementById('searchResults');
    if (!query || query.length < 2) {
        dropdown.classList.remove('show');
        return;
    }

    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(async () => {
        try {
            const results = await api(`/search?q=${encodeURIComponent(query)}`);
            let html = '';

            if (results.companies.length) {
                html += `<div class="search-group">
                    <div class="search-group-title">Companies</div>
                    ${results.companies.map(c => `
                        <div class="search-item" onclick="navigate('companies');document.getElementById('searchResults').classList.remove('show')">
                            <span class="material-icons-round search-item-icon">business</span>
                            <div class="search-item-text">
                                <div class="search-item-title">${c.company_name}</div>
                                <div class="search-item-sub">${c.gst_number}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>`;
            }

            if (results.invoices.length) {
                html += `<div class="search-group">
                    <div class="search-group-title">Invoices</div>
                    ${results.invoices.map(i => `
                        <div class="search-item" onclick="viewInvoiceDetail('${i.invoice_number}');document.getElementById('searchResults').classList.remove('show')">
                            <span class="material-icons-round search-item-icon">description</span>
                            <div class="search-item-text">
                                <div class="search-item-title">${i.invoice_number}</div>
                                <div class="search-item-sub">${i.company_name} - ${formatINR(i.total_amount)}</div>
                            </div>
                            ${statusBadge(i.invoice_status)}
                        </div>
                    `).join('')}
                </div>`;
            }

            if (results.payments.length) {
                html += `<div class="search-group">
                    <div class="search-group-title">Payments</div>
                    ${results.payments.map(p => `
                        <div class="search-item" onclick="navigate('payments');document.getElementById('searchResults').classList.remove('show')">
                            <span class="material-icons-round search-item-icon">payments</span>
                            <div class="search-item-text">
                                <div class="search-item-title">${p.invoice_number}</div>
                                <div class="search-item-sub">${formatINR(p.amount_received)} via ${p.payment_mode}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>`;
            }

            if (!html) {
                html = '<div class="search-group"><div style="padding:16px;text-align:center;color:var(--text-tertiary)">No results found</div></div>';
            }

            dropdown.innerHTML = html;
            dropdown.classList.add('show');
        } catch (e) { /* ignore */ }
    }, 300);
}

// Close search dropdown on click outside
document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-container')) {
        document.getElementById('searchResults')?.classList.remove('show');
    }
});

// ═══════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    updateCurrentDate();
    setInterval(updateCurrentDate, 60000);
    navigate('dashboard');
});
