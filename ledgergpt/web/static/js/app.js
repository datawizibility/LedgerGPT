// LedgerGPT Enterprise Financial Dashboard & Copilot Engine

let trendChartInstance = null;
let debtorsChartInstance = null;
let creditorsChartInstance = null;
let currentGridPage = 1;
let currentGridTotalPages = 1;
let gridSearchTimer = null;
let currentQueryData = null;
let activeFinancialYear = 'All';
let activeCostCentre = 'All';

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    initDashboard();
});

function initDashboard() {
    loadAvailablePeriods();
    loadAvailableCostCentres();
    refreshDashboardViews();
    loadVouchersGrid(1);
}

function refreshDashboardViews() {
    loadDashboardSummary(activeFinancialYear, activeCostCentre);
    loadMonthlyTrend(activeFinancialYear, activeCostCentre);
    loadRankings(activeFinancialYear, activeCostCentre);
    loadAgingSummary(activeFinancialYear, activeCostCentre);
}

function loadAvailablePeriods() {
    fetch('/api/dashboard/periods')
        .then(res => res.json())
        .then(periods => {
            const globalSelect = document.getElementById('globalPeriodSelect');
            const gridSelect = document.getElementById('gridFilterFY');

            let optionsHtml = '<option value="All">All Fiscal Years</option>';
            if (periods && periods.length > 0) {
                optionsHtml += periods.map(p => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join('');
            }

            if (globalSelect) {
                globalSelect.innerHTML = optionsHtml;
                globalSelect.value = activeFinancialYear;
            }
            if (gridSelect) {
                gridSelect.innerHTML = optionsHtml;
                gridSelect.value = activeFinancialYear;
            }
        })
        .catch(err => console.error('Failed to load periods:', err));
}

function loadAvailableCostCentres() {
    fetch('/api/dashboard/cost-centres')
        .then(res => res.json())
        .then(ccs => {
            const ccSelect = document.getElementById('globalCostCentreSelect');
            if (!ccSelect) return;
            let optHtml = '<option value="All">All Sites / Cost Centres</option>';
            if (ccs && ccs.length > 0) {
                optHtml += ccs.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
            }
            ccSelect.innerHTML = optHtml;
            ccSelect.value = activeCostCentre;
        })
        .catch(err => console.error('Failed to load cost centres:', err));
}

function applyGlobalFilters() {
    const selPeriod = document.getElementById('globalPeriodSelect');
    const selCC = document.getElementById('globalCostCentreSelect');
    activeFinancialYear = selPeriod ? selPeriod.value : 'All';
    activeCostCentre = selCC ? selCC.value : 'All';

    // Sync grid filter FY
    const gridSel = document.getElementById('gridFilterFY');
    if (gridSel) gridSel.value = activeFinancialYear;

    refreshDashboardViews();
    loadVouchersGrid(1);
}

function applyGlobalPeriod() {
    applyGlobalFilters();
}

// ==================== VIEW MODE SWITCHER ====================
function setViewMode(mode) {
    document.body.className = `view-${mode}`;
    
    document.querySelectorAll('.switch-btn').forEach(btn => btn.classList.remove('active'));
    if (mode === 'split') document.getElementById('btnViewSplit').classList.add('active');
    if (mode === 'dashboard') document.getElementById('btnViewDash').classList.add('active');
    if (mode === 'chat') document.getElementById('btnViewChat').classList.add('active');

    setTimeout(() => {
        if (trendChartInstance) trendChartInstance.resize();
        if (debtorsChartInstance) debtorsChartInstance.resize();
        if (creditorsChartInstance) creditorsChartInstance.resize();
    }, 150);
}

// ==================== EXECUTIVE DASHBOARD DATA ====================
function loadDashboardSummary(fy = 'All', cc = 'All') {
    const url = `/api/dashboard/summary?fy=${encodeURIComponent(fy)}&cost_centre=${encodeURIComponent(cc)}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            // Active Company Banner
            const coElem = document.getElementById('headerActiveCompany');
            if (coElem) coElem.innerText = data.active_company || 'Active Company';

            // Top Financial Cards
            document.getElementById('kpiDashSales').innerText = data.sales_gross_formatted || '₹ 0.00';
            document.getElementById('kpiDashSalesNet').innerText = `Net: ₹ ${(data.sales_net / 10000000).toFixed(2)} Cr`;

            document.getElementById('kpiDashPurch').innerText = data.purchase_gross_formatted || '₹ 0.00';
            document.getElementById('kpiDashPurchNet').innerText = `Net: ₹ ${(data.purchase_net / 10000000).toFixed(2)} Cr`;

            document.getElementById('kpiDashMargin').innerText = data.gross_margin_formatted || '₹ 0.00';
            document.getElementById('kpiDashMarginPct').innerText = `Margin: ${data.gross_margin_pct}%`;

            document.getElementById('kpiDashDebit').innerText = data.debit_notes_formatted || '₹ 0.00';
            document.getElementById('kpiDashDebitCount').innerText = `${data.debit_notes_count.toLocaleString()} vouchers`;

            document.getElementById('kpiDashCredit').innerText = data.credit_notes_formatted || '₹ 0.00';
            document.getElementById('kpiDashCreditCount').innerText = `${data.credit_notes_count.toLocaleString()} vouchers`;

            document.getElementById('kpiDashVouchers').innerText = (data.total_vouchers || 0).toLocaleString();
            document.getElementById('kpiDashParties').innerText = `${data.unique_parties.toLocaleString()} Parties | ${data.unique_cost_centres} CCs`;

            // TALLY LIQUIDITY & BALANCE SHEET COCKPIT TILES
            // Tile 1: Cash & Bank
            const cashElem = document.getElementById('tallyCashInHand');
            if (cashElem) cashElem.innerText = `${data.cash_in_hand_formatted} Dr`;

            const bankElem = document.getElementById('tallyBankBalance');
            if (bankElem) bankElem.innerText = `${data.bank_balance_formatted} Dr`;

            const bankLabel = document.getElementById('tallyBankLabel');
            if (bankLabel && data.bank_name) bankLabel.innerText = `${data.bank_name}:`;

            const liquidElem = document.getElementById('tallyTotalLiquid');
            if (liquidElem) liquidElem.innerText = `${data.total_liquid_funds_formatted} Dr`;

            // Tile 2: Cash Flow Velocity
            const inElem = document.getElementById('tallyCashInflow');
            if (inElem) inElem.innerText = `${data.cash_inflow_formatted} Dr`;

            const outElem = document.getElementById('tallyCashOutflow');
            if (outElem) outElem.innerText = `${data.cash_outflow_formatted} Cr`;

            const netElem = document.getElementById('tallyNetCashFlow');
            if (netElem) {
                netElem.innerText = `${data.net_cash_flow_formatted} ${data.net_cash_flow >= 0 ? 'Dr' : 'Cr'}`;
                netElem.style.color = data.net_cash_flow >= 0 ? 'var(--green)' : 'var(--maroon)';
            }

            // Tile 3: Working Capital & Ratios
            const assetsLiabElem = document.getElementById('tallyAssetsLiab');
            if (assetsLiabElem) {
                assetsLiabElem.innerText = `${data.current_assets_formatted} / ${data.current_liabilities_formatted}`;
            }

            const payablesElem = document.getElementById('tallyPayables');
            if (payablesElem) payablesElem.innerText = data.payables_formatted;

            const ratiosElem = document.getElementById('tallyRatios');
            if (ratiosElem) {
                ratiosElem.innerText = `${data.current_ratio} : 1 | ${data.receivable_turnover_days} Days`;
            }
        })
        .catch(err => console.error('Failed to load dashboard summary:', err));
}

function loadAgingSummary(fy = 'All', cc = 'All') {
    const url = `/api/dashboard/aging?fy=${encodeURIComponent(fy)}&cost_centre=${encodeURIComponent(cc)}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            const s = data.summary;
            if (!s) return;
            // Receivables
            const r030 = document.getElementById('agingRec030');
            if (r030) r030.innerText = s.receivables.bucket_0_30_formatted || '₹ 0.00';
            const r3160 = document.getElementById('agingRec3160');
            if (r3160) r3160.innerText = s.receivables.bucket_31_60_formatted || '₹ 0.00';
            const r6190 = document.getElementById('agingRec6190');
            if (r6190) r6190.innerText = s.receivables.bucket_61_90_formatted || '₹ 0.00';
            const r90p = document.getElementById('agingRec90Plus');
            if (r90p) r90p.innerText = s.receivables.bucket_90_plus_formatted || '₹ 0.00';
            const rtot = document.getElementById('agingRecTotal');
            if (rtot) rtot.innerText = `${s.receivables.total_formatted} (${s.receivables.count} bills)`;

            // Payables
            const p030 = document.getElementById('agingPay030');
            if (p030) p030.innerText = s.payables.bucket_0_30_formatted || '₹ 0.00';
            const p3160 = document.getElementById('agingPay3160');
            if (p3160) p3160.innerText = s.payables.bucket_31_60_formatted || '₹ 0.00';
            const p6190 = document.getElementById('agingPay6190');
            if (p6190) p6190.innerText = s.payables.bucket_61_90_formatted || '₹ 0.00';
            const p90p = document.getElementById('agingPay90Plus');
            if (p90p) p90p.innerText = s.payables.bucket_90_plus_formatted || '₹ 0.00';
            const ptot = document.getElementById('agingPayTotal');
            if (ptot) ptot.innerText = `${s.payables.total_formatted} (${s.payables.count} bills)`;
        })
        .catch(err => console.error('Failed to load aging summary:', err));
}

function loadMonthlyTrend(fy = 'All', cc = 'All') {
    const url = `/api/dashboard/monthly-trend?fy=${encodeURIComponent(fy)}&cost_centre=${encodeURIComponent(cc)}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            renderMonthlyTrendChart(data);
        })
        .catch(err => console.error('Failed to load monthly trend:', err));
}

function renderMonthlyTrendChart(data) {
    const ctx = document.getElementById('monthlyTrendChart');
    if (!ctx) return;

    if (trendChartInstance) {
        trendChartInstance.destroy();
    }

    const salesInCr = data.sales.map(v => Number((v / 10000000).toFixed(2)));
    const purchInCr = data.purchases.map(v => Number((v / 10000000).toFixed(2)));
    const marginsInCr = data.margins.map(v => Number((v / 10000000).toFixed(2)));

    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [
                {
                    label: 'Gross Sales Billed (₹ Cr)',
                    data: salesInCr,
                    backgroundColor: 'rgba(39, 174, 96, 0.85)',
                    borderRadius: 4,
                    order: 2
                },
                {
                    label: 'Vendor Outflows (₹ Cr)',
                    data: purchInCr,
                    backgroundColor: 'rgba(230, 126, 34, 0.85)',
                    borderRadius: 4,
                    order: 3
                },
                {
                    type: 'line',
                    label: 'Gross Margin (₹ Cr)',
                    data: marginsInCr,
                    borderColor: '#16A085',
                    backgroundColor: '#16A085',
                    borderWidth: 2.5,
                    fill: false,
                    tension: 0.2,
                    order: 1
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.dataset.label}: ₹ ${context.parsed.y.toLocaleString()} Cr`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { font: { size: 10 } }
                },
                y: {
                    grid: { color: '#F0F2F5' },
                    ticks: {
                        callback: function(val) { return `₹ ${val} Cr`; },
                        font: { size: 10 }
                    }
                }
            }
        }
    });
}

function loadRankings(fy = 'All', cc = 'All') {
    const url = `/api/dashboard/rankings?top_n=10&fy=${encodeURIComponent(fy)}&cost_centre=${encodeURIComponent(cc)}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            renderDebtorsChart(data.top_debtors);
            renderCreditorsChart(data.top_creditors);
            renderCostCentresTable(data.top_cost_centres);
        })
        .catch(err => console.error('Failed to load rankings:', err));
}

function renderDebtorsChart(debtors) {
    const ctx = document.getElementById('topDebtorsChart');
    if (!ctx) return;
    if (debtorsChartInstance) debtorsChartInstance.destroy();

    const labels = debtors.map(d => d.party_name.length > 22 ? d.party_name.substring(0, 20) + '...' : d.party_name);
    const fullNames = debtors.map(d => d.party_name);
    const valuesInCr = debtors.map(d => Number((d.amount / 10000000).toFixed(2)));

    debtorsChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                data: valuesInCr,
                backgroundColor: 'rgba(41, 128, 185, 0.85)',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => fullNames[items[0].dataIndex],
                        label: (item) => `Total Billed: ₹ ${item.parsed.x} Cr`
                    }
                }
            },
            onClick: (e, elements) => {
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    askCopilotAboutParty(fullNames[idx]);
                }
            },
            scales: {
                x: {
                    ticks: {
                        callback: val => `₹ ${val} Cr`,
                        font: { size: 9.5 }
                    }
                },
                y: { ticks: { font: { size: 10 } } }
            }
        }
    });
}

function renderCreditorsChart(creditors) {
    const ctx = document.getElementById('topCreditorsChart');
    if (!ctx) return;
    if (creditorsChartInstance) creditorsChartInstance.destroy();

    const labels = creditors.map(c => c.party_name.length > 22 ? c.party_name.substring(0, 20) + '...' : c.party_name);
    const fullNames = creditors.map(c => c.party_name);
    const valuesInCr = creditors.map(c => Number((c.amount / 10000000).toFixed(2)));

    creditorsChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                data: valuesInCr,
                backgroundColor: 'rgba(230, 126, 34, 0.85)',
                borderRadius: 4
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => fullNames[items[0].dataIndex],
                        label: (item) => `Total Vendor Outflow: ₹ ${item.parsed.x} Cr`
                    }
                }
            },
            onClick: (e, elements) => {
                if (elements.length > 0) {
                    const idx = elements[0].index;
                    askCopilotAboutParty(fullNames[idx]);
                }
            },
            scales: {
                x: {
                    ticks: {
                        callback: val => `₹ ${val} Cr`,
                        font: { size: 9.5 }
                    }
                },
                y: { ticks: { font: { size: 10 } } }
            }
        }
    });
}

function renderCostCentresTable(ccs) {
    const tbody = document.getElementById('costCentresTableBody');
    if (!tbody) return;

    if (!ccs || ccs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:15px; color:#777;">No cost centre / project allocations found for selected period.</td></tr>';
        return;
    }

    tbody.innerHTML = ccs.map(cc => `
        <tr>
            <td><strong>${escapeHtml(cc.cost_centre)}</strong></td>
            <td class="num-cell">${cc.sales_formatted}</td>
            <td class="num-cell" style="color:var(--orange);">${cc.purchase_formatted}</td>
            <td class="num-cell" style="color:${cc.margin >= 0 ? 'var(--green)' : 'red'};">${cc.margin_formatted}</td>
            <td class="num-cell"><strong>${cc.margin_pct}%</strong></td>
            <td style="text-align:center;">
                <button class="btn-table-action" onclick="askCopilotAboutProject('${escapeForJs(cc.cost_centre)}')">🔍 Ask Copilot</button>
            </td>
        </tr>
    `).join('');
}

// ==================== VOUCHER EXPLORER GRID ====================
function loadVouchersGrid(page = 1) {
    currentGridPage = page;
    const vtype = document.getElementById('gridFilterType').value;
    const fy = document.getElementById('gridFilterFY').value;
    const search = document.getElementById('gridSearchInput').value.trim();

    const tbody = document.getElementById('vouchersGridBody');
    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 20px;">Fetching records...</td></tr>';

    const url = `/api/dashboard/vouchers-grid?page=${page}&page_size=50&type=${encodeURIComponent(vtype)}&fy=${encodeURIComponent(fy)}&cost_centre=${encodeURIComponent(activeCostCentre)}&search=${encodeURIComponent(search)}`;

    fetch(url)
        .then(res => res.json())
        .then(data => {
            currentGridTotalPages = data.total_pages || 1;
            renderVouchersGrid(data.items, data.total_rows);
            updateGridPagination(data.page, data.total_pages, data.total_rows);
        })
        .catch(err => {
            tbody.innerHTML = `<tr><td colspan="8" style="color:red; text-align:center;">Failed to load vouchers: ${err.message}</td></tr>`;
        });
}

function renderVouchersGrid(items, totalRows) {
    const tbody = document.getElementById('vouchersGridBody');
    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; padding: 20px; color:#777;">No matching vouchers found for current filter.</td></tr>';
        return;
    }

    tbody.innerHTML = items.map(r => `
        <tr>
            <td style="white-space:nowrap;">${r.date}</td>
            <td><span class="badge-${(r.voucher_type || '').toLowerCase().replace(/\s+/g, '-')}">${r.voucher_type}</span></td>
            <td>${escapeHtml(r.voucher_no)}</td>
            <td>${escapeHtml(r.reference_no)}</td>
            <td><strong>${escapeHtml(r.party_name)}</strong></td>
            <td><small>${escapeHtml(r.cost_centre)}</small></td>
            <td class="num-cell">₹ ${Number(r.gross_amount).toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 11px; color:#555;" title="${escapeHtml(r.narration)}">${escapeHtml(r.narration || '-')}</td>
        </tr>
    `).join('');
}

function updateGridPagination(page, totalPages, totalRows) {
    document.getElementById('gridPageInfo').innerText = `Showing Page ${page} of ${totalPages} (${totalRows.toLocaleString()} Total Records)`;
    document.getElementById('gridPrevBtn').disabled = page <= 1;
    document.getElementById('gridNextBtn').disabled = page >= totalPages;
}

function changeGridPage(delta) {
    const targetPage = currentGridPage + delta;
    if (targetPage >= 1 && targetPage <= currentGridTotalPages) {
        loadVouchersGrid(targetPage);
    }
}

function debounceGridSearch() {
    clearTimeout(gridSearchTimer);
    gridSearchTimer = setTimeout(() => {
        loadVouchersGrid(1);
    }, 350);
}

function exportVouchersGrid() {
    const vtype = document.getElementById('gridFilterType').value;
    const fy = document.getElementById('gridFilterFY').value;
    const search = document.getElementById('gridSearchInput').value.trim();

    const url = `/api/dashboard/vouchers-grid?page=1&page_size=5000&type=${encodeURIComponent(vtype)}&fy=${encodeURIComponent(fy)}&search=${encodeURIComponent(search)}`;
    
    fetch(url)
        .then(res => res.json())
        .then(data => {
            if (!data.items || data.items.length === 0) {
                alert('No data to export.');
                return;
            }

            fetch('/api/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    data: data.items,
                    columns: ['date', 'voucher_type', 'voucher_no', 'reference_no', 'party_name', 'cost_centre', 'net_amount', 'tax_amount', 'gross_amount', 'narration'],
                    filename: `LedgerGPT_Voucher_Export_${Date.now()}.csv`
                })
            })
            .then(res => res.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `LedgerGPT_Voucher_Export_${Date.now()}.csv`;
                document.body.appendChild(a);
                a.click();
                a.remove();
            });
        });
}

// ==================== BIDIRECTIONAL COPILOT BINDING ====================
function askCopilotAboutParty(partyName) {
    if (document.body.classList.contains('view-dashboard')) {
        setViewMode('split');
    }

    const query = `Analyze all vouchers, gross volume, and transaction history for ${partyName}`;
    document.getElementById('userInput').value = query;
    handleChatSubmit(new Event('submit'));
}

function askCopilotAboutProject(projectName) {
    if (document.body.classList.contains('view-dashboard')) {
        setViewMode('split');
    }

    const query = `Analyze revenue, direct subcontract expenses, and profit margin for project ${projectName}`;
    document.getElementById('userInput').value = query;
    handleChatSubmit(new Event('submit'));
}

// ==================== CONVERSATIONAL CHAT COPILOT ====================
function handleChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('userInput');
    const q = input.value.trim();
    if (!q) return;

    appendUserMessage(q);
    input.value = '';
    input.disabled = true;
    document.getElementById('sendBtn').innerText = 'Thinking...';

    fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q })
    })
    .then(res => res.json())
    .then(data => {
        appendAssistantMessage(data);
    })
    .catch(err => {
        appendAssistantMessage({
            answer: `❌ Error connecting to LedgerGPT backend: ${err.message}`,
            data: [],
            sql: ''
        });
    })
    .finally(() => {
        input.disabled = false;
        document.getElementById('sendBtn').innerText = 'Ask Copilot ↵';
        input.focus();
    });
}

function sendQuickQuery(q) {
    document.getElementById('userInput').value = q;
    handleChatSubmit(new Event('submit'));
}

function appendUserMessage(text) {
    const stream = document.getElementById('chatStream');
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble user';
    bubble.innerHTML = `
        <div class="msg-avatar">👤</div>
        <div class="msg-body">
            <div>${escapeHtml(text)}</div>
        </div>
    `;
    stream.appendChild(bubble);
    stream.scrollTop = stream.scrollHeight;
}

function appendAssistantMessage(data) {
    const stream = document.getElementById('chatStream');
    const bubble = document.createElement('div');
    bubble.className = 'msg-bubble assistant';

    let formattedAnswer = formatMarkdownText(data.answer || 'Query processed.');
    let tableHtml = '';
    let exportBtnHtml = '';

    if (data.data && data.data.length > 0) {
        currentQueryData = data;
        exportBtnHtml = `
            <div style="margin-top: 10px; display: flex; gap: 8px;">
                <button class="btn btn-outline" style="background: #27AE60; color:#fff; font-size:11px; padding: 4px 10px;" onclick="downloadCurrentData()">📥 Export Result (${data.row_count} Rows) as CSV</button>
            </div>
        `;

        const cols = data.columns || Object.keys(data.data[0]);
        let ths = cols.map(c => `<th>${formatHeader(c)}</th>`).join('');
        let trs = data.data.slice(0, 50).map(r => {
            let tds = cols.map(c => {
                let val = r[c] !== null && r[c] !== undefined ? r[c] : '';
                if (typeof val === 'number') {
                    return `<td class="num-cell">${val.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>`;
                }
                return `<td>${escapeHtml(String(val))}</td>`;
            }).join('');
            return `<tr>${tds}</tr>`;
        }).join('');

        tableHtml = `
            <div class="table-container" style="max-height: 250px; margin-top: 10px;">
                <table class="data-table">
                    <thead><tr>${ths}</tr></thead>
                    <tbody>${trs}</tbody>
                </table>
            </div>
            ${exportBtnHtml}
        `;
    }

    let auditHtml = '';
    if (data.sql) {
        auditHtml = `
            <details class="audit-details">
                <summary class="audit-summary">
                    <span>🔍 View Deterministic SQL & Audit Execution</span>
                    <span>${data.execution_time_ms || 0} ms</span>
                </summary>
                <pre class="audit-code"><code>${escapeHtml(data.sql)}</code></pre>
            </details>
        `;
    }

    bubble.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-body">
            <div class="msg-header">
                <strong>LedgerGPT Response</strong>
                <span class="msg-tag">${data.source || 'Deterministic'}</span>
            </div>
            <div>${formattedAnswer}</div>
            ${tableHtml}
            ${auditHtml}
        </div>
    `;

    stream.appendChild(bubble);
    stream.scrollTop = stream.scrollHeight;
}

function downloadCurrentData() {
    if (!currentQueryData || !currentQueryData.data) return;

    fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            data: currentQueryData.data,
            columns: currentQueryData.columns,
            filename: `LedgerGPT_QueryResult_${Date.now()}.csv`
        })
    })
    .then(res => res.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `LedgerGPT_QueryResult_${Date.now()}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
    });
}

// ==================== TALLY SYNC ENGINE ====================
function openSyncModal() {
    document.getElementById('syncModal').style.display = 'flex';
    const msg = document.getElementById('syncStatusMsg');
    msg.style.display = 'none';

    const select = document.getElementById('syncCompanySelect');
    if (select) {
        select.innerHTML = '<option value="">Detecting open companies from Tally...</option>';
        select.disabled = true;

        fetch('/api/tally-companies')
            .then(res => res.json())
            .then(data => {
                if (data.connected && data.companies && data.companies.length > 0) {
                    select.disabled = false;
                    select.innerHTML = data.companies.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
                    
                    const latehar = data.companies.find(c => c.toUpperCase().includes('LATEHAR'));
                    if (latehar) {
                        select.value = latehar;
                    }
                } else {
                    select.innerHTML = `<option value="">⚠️ No companies detected (${data.error || 'Check Tally'})</option>`;
                }
            })
            .catch(err => {
                select.innerHTML = `<option value="">⚠️ Error communicating with Tally: ${escapeHtml(err.message)}</option>`;
            });
    }

    document.getElementById('startSyncBtn').disabled = false;
    document.getElementById('startSyncBtn').innerText = 'Start Live Sync';
}

function closeSyncModal() {
    document.getElementById('syncModal').style.display = 'none';
}

function executeTallySync() {
    const btn = document.getElementById('startSyncBtn');
    const msg = document.getElementById('syncStatusMsg');
    const clearDb = document.getElementById('syncClearDb').checked;
    const select = document.getElementById('syncCompanySelect');
    const chosenCompany = select ? select.value : '';

    if (!chosenCompany) {
        alert('Please select an active company from the dropdown before starting sync.');
        return;
    }

    btn.disabled = true;
    btn.innerText = 'Connecting to Tally...';
    msg.style.display = 'block';
    msg.style.background = '#EBF5FB';
    msg.style.color = '#154360';
    msg.style.border = '1px solid #AED6F1';
    msg.innerHTML = `⏳ <strong>Querying Tally Prime for '${escapeHtml(chosenCompany)}'...</strong> Extracting vouchers across all periods.`;

    fetch('/api/sync-tally', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            company_name: chosenCompany,
            clear_existing: clearDb 
        })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || 'Failed to sync with Tally');
        }
        return data;
    })
    .then(data => {
        msg.style.background = '#EAFAF1';
        msg.style.color = '#145A32';
        msg.style.border = '1px solid #A9DFBF';
        msg.innerHTML = `✅ <strong>${escapeHtml(data.message)}</strong>`;

        // Refresh entire dashboard with new company data!
        initDashboard();

        appendAssistantMessage({
            answer: `🎉 **Tally Sync Complete!** Successfully synced **${data.vouchers_synced.toLocaleString()} vouchers** from company: **${escapeHtml(data.company_name)}**.\n- Total Vouchers in DB: **${(data.kpis.total_vouchers || 0).toLocaleString()}**\n- Gross Sales: **${data.kpis.sales_formatted}**\n- Gross Purchases: **${data.kpis.purchase_formatted}**\n\nAll dashboard cards, liquidity tiles, and tables have been updated for ${escapeHtml(data.company_name)}!`,
            data: [],
            sql: ''
        });

        setTimeout(() => {
            closeSyncModal();
        }, 1800);
    })
    .catch(err => {
        msg.style.background = '#FDEDEC';
        msg.style.color = '#78281F';
        msg.style.border = '1px solid #F5B7B1';
        msg.innerHTML = `⚠️ <strong>Sync Error:</strong> ${escapeHtml(err.message)}<br><small style="display:block; margin-top:4px;">Check: 1) Is Tally Prime open? 2) Is ODBC/Server enabled on port 9000?</small>`;
    })
    .finally(() => {
        btn.disabled = false;
        btn.innerText = 'Start Live Sync';
    });
}

// ==================== FORENSIC AUDIT SCANNER (ALL 5 TABLES) ====================
function openForensicModal() {
    document.getElementById('forensicModal').style.display = 'flex';
}

function closeForensicModal() {
    document.getElementById('forensicModal').style.display = 'none';
}

function loadForensicScan() {
    const body = document.getElementById('forensicModalBody');
    body.innerHTML = '<div style="text-align:center; padding: 40px;">⏳ Running full statistical & forensic scan across all vouchers...</div>';

    fetch('/api/forensic')
    .then(res => res.json())
    .then(data => {
        renderForensicResults(data);
    })
    .catch(err => {
        body.innerHTML = `<div style="color:red; padding:20px;">Failed to run scan: ${err.message}</div>`;
    });
}

function renderForensicResults(data) {
    const body = document.getElementById('forensicModalBody');
    const s = data.summary || {};

    // 1. BENFORD'S LAW TABLE
    let benfordHtml = '';
    if (data.benford_analysis && data.benford_analysis.digits) {
        let bRows = data.benford_analysis.digits.map(d => `
            <tr>
                <td style="text-align:center; font-weight:700;">${d.digit}</td>
                <td class="num-cell">${d.observed_pct}% (${d.observed_count.toLocaleString()})</td>
                <td class="num-cell">${d.expected_pct}%</td>
                <td class="num-cell" style="color: ${d.deviation_pct > 5 ? 'red' : 'inherit'};">${d.deviation_pct}%</td>
                <td style="text-align:center;"><strong>${d.anomaly_flag}</strong></td>
            </tr>
        `).join('');

        benfordHtml = `
            <div style="margin-top: 20px;">
                <h4 style="color:#1B365D;">1. Benford's Law First-Digit Conformity Analysis</h4>
                <p style="font-size:12px; color:#555;">Overall Status: <strong>${data.benford_analysis.overall_conformity}</strong> (Max deviation: ${data.benford_analysis.max_deviation_pct}%)</p>
                <div class="table-container" style="max-height:220px; margin-top:8px;">
                    <table class="data-table">
                        <thead>
                            <tr><th>Digit</th><th class="num-cell">Observed %</th><th class="num-cell">Expected %</th><th class="num-cell">Deviation</th><th>Status</th></tr>
                        </thead>
                        <tbody>${bRows}</tbody>
                    </table>
                </div>
            </div>
        `;
    }

    // 2. SUSPICIOUS NARRATIONS TABLE
    let suspiciousHtml = '';
    if (data.suspicious_narrations && data.suspicious_narrations.records) {
        let rows = data.suspicious_narrations.records.slice(0, 50).map(r => `
            <tr>
                <td>${r.date}</td>
                <td>${r.voucher_type}</td>
                <td><strong>${escapeHtml(r.party_name)}</strong></td>
                <td class="num-cell">₹ ${Number(r.gross_amount).toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
                <td style="color:#800000; font-size:11px;">${escapeHtml(r.narration)}</td>
            </tr>
        `).join('');

        suspiciousHtml = `
            <div style="margin-top: 24px;">
                <h4 style="color:#922B21;">2. Flagged Suspicious Narrations (${data.suspicious_narrations.total_flagged} Detected)</h4>
                <div class="table-container" style="max-height:220px; margin-top:8px;">
                    <table class="data-table">
                        <thead><tr><th>Date</th><th>Type</th><th>Party</th><th class="num-cell">Amount</th><th>Narration</th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `;
    }

    // 3. ROUND-SUM PAYMENTS (>=1L) TABLE
    let roundSumHtml = '';
    if (data.round_sum_transactions && data.round_sum_transactions.records) {
        let rows = data.round_sum_transactions.records.slice(0, 50).map(r => `
            <tr>
                <td>${r.date}</td>
                <td>${r.voucher_type}</td>
                <td><strong>${escapeHtml(r.party_name)}</strong></td>
                <td><small>${escapeHtml(r.primary_ledger || '-')}</small></td>
                <td class="num-cell" style="color:var(--orange);">₹ ${Number(r.gross_amount).toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
                <td style="font-size:11px; color:#555;">${escapeHtml(r.narration || '-')}</td>
            </tr>
        `).join('');

        roundSumHtml = `
            <div style="margin-top: 24px;">
                <h4 style="color:#B7950B;">3. High-Value Round-Sum Transactions (≥₹50K / ₹1L) (${data.round_sum_transactions.total_flagged} Found)</h4>
                <p style="font-size:12px; color:#555;">Transactions matching round multiples without fractional currency amounts.</p>
                <div class="table-container" style="max-height:220px; margin-top:8px;">
                    <table class="data-table">
                        <thead><tr><th>Date</th><th>Type</th><th>Party</th><th>Primary Ledger</th><th class="num-cell">Amount</th><th>Narration</th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `;
    }

    // 4. WEEKEND-DATED VOUCHERS TABLE
    let weekendHtml = '';
    if (data.weekend_entries && data.weekend_entries.records) {
        let rows = data.weekend_entries.records.slice(0, 50).map(r => `
            <tr>
                <td>${r.date}</td>
                <td><span class="badge-pro" style="background:#EBF5FB; color:#1B4F72;">${r.day_of_week}</span></td>
                <td>${r.voucher_type}</td>
                <td><strong>${escapeHtml(r.party_name)}</strong></td>
                <td class="num-cell">₹ ${Number(r.gross_amount).toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
                <td style="font-size:11px; color:#555;">${escapeHtml(r.narration || '-')}</td>
            </tr>
        `).join('');

        weekendHtml = `
            <div style="margin-top: 24px;">
                <h4 style="color:#2874A6;">4. Weekend-Dated Vouchers (${data.weekend_entries.total_flagged} Found)</h4>
                <p style="font-size:12px; color:#555;">Entries booked on Saturdays or Sundays warranting segregation-of-duties review.</p>
                <div class="table-container" style="max-height:220px; margin-top:8px;">
                    <table class="data-table">
                        <thead><tr><th>Date</th><th>Day</th><th>Type</th><th>Party</th><th class="num-cell">Amount</th><th>Narration</th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `;
    }

    // 5. DUPLICATE BILL GROUPS TABLE
    let duplicateHtml = '';
    if (data.duplicate_bills && data.duplicate_bills.records) {
        let rows = data.duplicate_bills.records.slice(0, 50).map(r => `
            <tr>
                <td><strong>${escapeHtml(r.party_name)}</strong></td>
                <td><code style="background:#F2F4F4; padding:2px 6px; border-radius:3px;">${escapeHtml(r.reference_no)}</code></td>
                <td style="text-align:center; font-weight:700; color:red;">${r.duplicate_count}</td>
                <td><small>${escapeHtml(r.dates || '-')}</small></td>
                <td><small>${escapeHtml(r.voucher_numbers || '-')}</small></td>
                <td class="num-cell" style="font-weight:700;">₹ ${Number(r.total_amount).toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
            </tr>
        `).join('');

        duplicateHtml = `
            <div style="margin-top: 24px;">
                <h4 style="color:#1E8449;">5. Potential Duplicate Billing References (${data.duplicate_bills.total_flagged} Groups)</h4>
                <p style="font-size:12px; color:#555;">Multiple entries sharing identical Party Name and Bill Reference Number.</p>
                <div class="table-container" style="max-height:220px; margin-top:8px;">
                    <table class="data-table">
                        <thead><tr><th>Party Name</th><th>Bill / Reference #</th><th style="text-align:center;">Count</th><th>Voucher Dates</th><th>Voucher Numbers</th><th class="num-cell">Total Amount</th></tr></thead>
                        <tbody>${rows}</tbody>
                    </table>
                </div>
            </div>
        `;
    }

    // 6. SECTION 269SS / 269T CASH VIOLATIONS (CA RAMAJAYAM TAX AUDIT RULE)
    let sec269Html = '';
    if (data.section_269ss && data.section_269ss.records) {
        let rows = data.section_269ss.records.slice(0, 50).map(r => `
            <tr>
                <td>${r.date}</td>
                <td>${r.voucher_type}</td>
                <td><strong>${escapeHtml(r.party_name)}</strong></td>
                <td>${escapeHtml(r.primary_ledger)}</td>
                <td class="num-cell" style="color:red; font-weight:700;">₹ ${Number(r.gross_amount).toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
                <td><span class="badge-pro" style="background:#FADBD8; color:#78281F;">${escapeHtml(r.clause_violation)}</span></td>
                <td style="font-size:11px; color:#555;">${escapeHtml(r.narration || '-')}</td>
            </tr>
        `).join('');

        sec269Html = `
            <div style="margin-top: 24px;">
                <h4 style="color:#C0392B;">6. Section 269SS & 269T Cash Loan Violations (${data.section_269ss.total_flagged} Flagged)</h4>
                <p style="font-size:12px; color:#555;">Form 3CD Clause 31 audit check: Cash loans, deposits, or advances ≥ ₹20,000 attracting 100% penalty under Sec 271D/271E.</p>
                <div class="table-container" style="max-height:220px; margin-top:8px;">
                    <table class="data-table">
                        <thead><tr><th>Date</th><th>Type</th><th>Party</th><th>Ledger</th><th class="num-cell">Amount</th><th>Clause</th><th>Narration</th></tr></thead>
                        <tbody>${rows || '<tr><td colspan="7" style="text-align:center; color:green; padding:12px;">✅ Clean: Zero cash loan violations ≥ ₹20,000 detected.</td></tr>'}</tbody>
                    </table>
                </div>
            </div>
        `;
    }

    // 7. NEGATIVE CASH BALANCE AUDIT ALERT
    let negCashHtml = '';
    if (data.negative_cash && data.negative_cash.records) {
        let rows = data.negative_cash.records.slice(0, 50).map(r => `
            <tr>
                <td><strong>${r.date}</strong></td>
                <td class="num-cell">₹ ${Number(r.daily_inflow).toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
                <td class="num-cell">₹ ${Number(r.daily_outflow).toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
                <td class="num-cell" style="color:red; font-weight:700;">₹ ${Number(r.closing_cash_balance).toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
                <td style="text-align:center;"><span class="badge-pro" style="background:#F2D7D5; color:#922B21;">NEGATIVE CASH</span></td>
            </tr>
        `).join('');

        negCashHtml = `
            <div style="margin-top: 24px;">
                <h4 style="color:#922B21;">7. Negative Cash Balance Audit Alert (${data.negative_cash.total_flagged} Flagged Dates)</h4>
                <p style="font-size:12px; color:#555;">Form 3CD audit test: Days where physical cumulative cash-in-hand dropped below ₹0.00.</p>
                <div class="table-container" style="max-height:220px; margin-top:8px;">
                    <table class="data-table">
                        <thead><tr><th>Date</th><th class="num-cell">Daily Receipts</th><th class="num-cell">Daily Payments</th><th class="num-cell">Closing Balance</th><th style="text-align:center;">Audit Alert</th></tr></thead>
                        <tbody>${rows || '<tr><td colspan="5" style="text-align:center; color:green; padding:12px;">✅ Clean: Zero negative cash balance days detected.</td></tr>'}</tbody>
                    </table>
                </div>
            </div>
        `;
    }

    body.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 14px;">
            <div style="background:#FDEDEC; padding:12px; border-radius:6px; border:1px solid #F5B7B1;">
                <div style="font-size:11px; color:#78281F; font-weight:600;">SUSPICIOUS NARRATIONS</div>
                <div style="font-size:20px; font-weight:700; color:#922B21;">${s.suspicious_narrations_count || 0}</div>
            </div>
            <div style="background:#FEF9E7; padding:12px; border-radius:6px; border:1px solid #F9E79F;">
                <div style="font-size:11px; color:#7D6608; font-weight:600;">ROUND-SUM PAYMENTS (≥₹1L)</div>
                <div style="font-size:20px; font-weight:700; color:#B7950B;">${s.round_sum_vouchers_count || 0}</div>
            </div>
            <div style="background:#EBF5FB; padding:12px; border-radius:6px; border:1px solid #AED6F1;">
                <div style="font-size:11px; color:#1B4F72; font-weight:600;">WEEKEND VOUCHERS</div>
                <div style="font-size:20px; font-weight:700; color:#2874A6;">${s.weekend_vouchers_count || 0}</div>
            </div>
            <div style="background:#EAFAF1; padding:12px; border-radius:6px; border:1px solid #A9DFBF;">
                <div style="font-size:11px; color:#145A32; font-weight:600;">DUPLICATE BILL GROUPS</div>
                <div style="font-size:20px; font-weight:700; color:#1E8449;">${s.duplicate_bill_groups || 0}</div>
            </div>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;">
            <div style="background:#FADBD8; padding:12px; border-radius:6px; border:1px solid #E6B0AA;">
                <div style="font-size:11px; color:#78281F; font-weight:600;">SEC 269SS/269T CASH LOAN VIOLATIONS (≥₹20K)</div>
                <div style="font-size:20px; font-weight:700; color:#922B21;">${s.section_269ss_violations_count || 0} Flagged</div>
            </div>
            <div style="background:#EDBB99; padding:12px; border-radius:6px; border:1px solid #DC7633;">
                <div style="font-size:11px; color:#6E2C00; font-weight:600;">NEGATIVE CASH BALANCE DAYS</div>
                <div style="font-size:20px; font-weight:700; color:#A04000;">${s.negative_cash_days_count || 0} Days</div>
            </div>
        </div>
        ${benfordHtml}
        ${suspiciousHtml}
        ${roundSumHtml}
        ${weekendHtml}
        ${duplicateHtml}
        ${sec269Html}
        ${negCashHtml}
    `;
}

// ==================== UTILITY HELPERS ====================
function escapeHtml(text) {
    if (!text) return '';
    return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeForJs(text) {
    if (!text) return '';
    return String(text).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function formatHeader(str) {
    return str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function formatMarkdownText(text) {
    let html = escapeHtml(text);
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\n- (.*?)/g, '<br>• $1');
    html = html.replace(/\n/g, '<br>');
    return html;
}


function downloadCfoMisPack() {
    const url = `/api/dashboard/cfo-mis-pack?fy=${encodeURIComponent(activeFinancialYear)}&cost_centre=${encodeURIComponent(activeCostCentre)}`;
    fetch(url)
        .then(res => res.json())
        .then(data => {
            let csv = "\ufeff";
            csv += `=== ${data.report_title} ===\n`;
            csv += `Generated At,${data.generated_at}\n`;
            csv += `Company Name,${data.company_name}\n`;
            csv += `Financial Period,${data.period}\n`;
            csv += `Cost Centre / Site,${data.cost_centre}\n\n`;

            const es = data.executive_summary;
            csv += `=== EXECUTIVE FINANCIAL SUMMARY ===\n`;
            csv += `Metric,Value\n`;
            csv += `Gross Sales,${es.sales_gross_formatted}\n`;
            csv += `Gross Purchases,${es.purchase_gross_formatted}\n`;
            csv += `Gross Operating Margin,${es.gross_margin_formatted} (${es.gross_margin_pct}%)\n`;
            csv += `Cash Inflow (Receipts),${es.cash_inflow_formatted}\n`;
            csv += `Cash Outflow (Payments),${es.cash_outflow_formatted}\n`;
            csv += `Nett Cash Flow,${es.net_cash_flow_formatted}\n`;
            csv += `Active Bank Balance,${es.bank_balance_formatted} (${es.bank_name})\n`;
            csv += `Cash-in-Hand Balance,${es.cash_in_hand_formatted}\n`;
            csv += `Current Assets,${es.current_assets_formatted}\n`;
            csv += `Current Liabilities,${es.current_liabilities_formatted}\n`;
            csv += `Current Ratio,${es.current_ratio}x\n`;
            csv += `Debtor Turnover Days,${es.receivable_turnover_days} Days\n\n`;

            const ag = data.aging_overview;
            csv += `=== DEBTOR & CREDITOR AGING OVERVIEW ===\n`;
            csv += `Bucket,Receivables (Debtors),Payables (Creditors)\n`;
            csv += `0 to 30 Days (Current),${ag.receivables.bucket_0_30_formatted},${ag.payables.bucket_0_30_formatted}\n`;
            csv += `31 to 60 Days,${ag.receivables.bucket_31_60_formatted},${ag.payables.bucket_31_60_formatted}\n`;
            csv += `61 to 90 Days,${ag.receivables.bucket_61_90_formatted},${ag.payables.bucket_61_90_formatted}\n`;
            csv += `Above 90 Days (Critical),${ag.receivables.bucket_90_plus_formatted},${ag.payables.bucket_90_plus_formatted}\n`;
            csv += `Total Outstanding,${ag.receivables.total_formatted},${ag.payables.total_formatted}\n\n`;

            if (data.critical_overdue_bills && data.critical_overdue_bills.length > 0) {
                csv += `=== CRITICAL OVERDUE BILLS (>90 DAYS) ===\n`;
                csv += `Type,Party Name,Bill Ref,Bill Date,Overdue Days,Outstanding Amount,Site\n`;
                data.critical_overdue_bills.forEach(b => {
                    csv += `"${b.bill_type}","${b.party_name}","${b.bill_ref}","${b.bill_date}",${b.overdue_days},"${b.outstanding_amount}","${b.cost_centre}"\n`;
                });
                csv += `\n`;
            }

            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement("a");
            link.href = URL.createObjectURL(blob);
            link.setAttribute("download", `CFO_MIS_Board_Pack_${Date.now()}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        })
        .catch(err => alert("Error generating CFO MIS Pack: " + err.message));
}
