// LedgerGPT Frontend Engine

let currentQueryData = null;

function handleChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('userInput');
    const q = input.value.trim();
    if (!q) return;

    appendUserMessage(q);
    input.value = '';
    input.disabled = true;
    document.getElementById('sendBtn').innerText = 'Computing...';

    // Call API
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
        document.getElementById('sendBtn').innerText = 'Ask LedgerGPT ↵';
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
            <div style="margin-top: 12px; display: flex; gap: 10px;">
                <button class="btn btn-outline" style="background: #27AE60; color:#fff;" onclick="downloadCurrentData()">📥 Export Result (${data.row_count} Rows) as CSV</button>
            </div>
        `;

        const cols = data.columns || Object.keys(data.data[0]);
        let ths = cols.map(c => `<th>${formatHeader(c)}</th>`).join('');
        let trs = data.data.slice(0, 50).map(r => {
            let tds = cols.map(c => {
                let val = r[c] !== null && r[c] !== undefined ? r[c] : '';
                let isNum = typeof val === 'number' || (!isNaN(parseFloat(val)) && (c.includes('amount') || c.includes('gross') || c.includes('net') || c.includes('tax') || c.includes('balance') || c.includes('billed') || c.includes('expense') || c.includes('sales')));
                if (isNum && typeof val === 'number') {
                    return `<td class="num-cell">₹ ${val.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>`;
                }
                return `<td>${escapeHtml(String(val))}</td>`;
            }).join('');
            return `<tr>${tds}</tr>`;
        }).join('');

        tableHtml = `
            <div class="table-container">
                <table class="data-table">
                    <thead><tr>${ths}</tr></thead>
                    <tbody>${trs}</tbody>
                </table>
            </div>
            ${data.data.length > 50 ? `<small style="color:#6c757d; display:block; margin-top:4px;">Showing top 50 preview rows of ${data.row_count} total records. Click export to download all.</small>` : ''}
        `;
    }

    let auditHtml = '';
    if (data.sql) {
        auditHtml = `
            <details class="audit-details">
                <summary class="audit-summary">
                    <span>🔍 Verified SQL & Audit Trail</span>
                    <span style="font-size: 11px; color: #6c757d;">${data.execution_time_ms || 5} ms | ${data.source || 'Deterministic'}</span>
                </summary>
                <div class="audit-code">${escapeHtml(data.sql)}</div>
            </details>
        `;
    }

    bubble.innerHTML = `
        <div class="msg-avatar">🤖</div>
        <div class="msg-body">
            <div class="msg-header">
                <strong>LedgerGPT Response</strong>
                <span class="msg-tag">${data.source ? data.source.split(' ')[0] : 'Verified'}</span>
            </div>
            <div>${formattedAnswer}</div>
            ${tableHtml}
            ${exportBtnHtml}
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
            filename: `LedgerGPT_Export_${Date.now()}.csv`
        })
    })
    .then(res => res.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `LedgerGPT_Export_${Date.now()}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
    });
}

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
    const s = data.summary;

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
                <h4>1. Benford's Law First-Digit Conformity Analysis</h4>
                <p style="font-size:12px; color:#555;">Overall Status: <strong>${data.benford_analysis.overall_conformity}</strong> (Max deviation: ${data.benford_analysis.max_deviation_pct}%)</p>
                <table class="data-table" style="margin-top:8px;">
                    <thead>
                        <tr><th>Digit</th><th class="num-cell">Observed %</th><th class="num-cell">Expected %</th><th class="num-cell">Deviation</th><th>Status</th></tr>
                    </thead>
                    <tbody>${bRows}</tbody>
                </table>
            </div>
        `;
    }

    let suspiciousHtml = '';
    if (data.suspicious_narrations && data.suspicious_narrations.records) {
        let rows = data.suspicious_narrations.records.slice(0, 15).map(r => `
            <tr>
                <td>${r.date}</td>
                <td>${r.voucher_type}</td>
                <td><strong>${escapeHtml(r.party_name)}</strong></td>
                <td class="num-cell">₹ ${r.gross_amount.toLocaleString('en-IN', {minimumFractionDigits:2})}</td>
                <td style="color:#800000; font-size:11px;">${escapeHtml(r.narration)}</td>
            </tr>
        `).join('');

        suspiciousHtml = `
            <div style="margin-top: 24px;">
                <h4>2. Flagged Suspicious Narrations (${data.suspicious_narrations.total_flagged} Found)</h4>
                <table class="data-table" style="margin-top:8px;">
                    <thead><tr><th>Date</th><th>Type</th><th>Party</th><th class="num-cell">Amount</th><th>Narration</th></tr></thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    body.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 20px;">
            <div style="background:#FDEDEC; padding:12px; border-radius:6px; border:1px solid #F5B7B1;">
                <div style="font-size:11px; color:#78281F; font-weight:600;">SUSPICIOUS NARRATIONS</div>
                <div style="font-size:20px; font-weight:700; color:#922B21;">${s.suspicious_narrations_count}</div>
            </div>
            <div style="background:#FEF9E7; padding:12px; border-radius:6px; border:1px solid #F9E79F;">
                <div style="font-size:11px; color:#7D6608; font-weight:600;">ROUND-SUM PAYMENTS (≥₹1L)</div>
                <div style="font-size:20px; font-weight:700; color:#B7950B;">${s.round_sum_vouchers_count}</div>
            </div>
            <div style="background:#EBF5FB; padding:12px; border-radius:6px; border:1px solid #AED6F1;">
                <div style="font-size:11px; color:#1B4F72; font-weight:600;">WEEKEND DATED VOUCHERS</div>
                <div style="font-size:20px; font-weight:700; color:#2874A6;">${s.weekend_vouchers_count}</div>
            </div>
            <div style="background:#EAFAF1; padding:12px; border-radius:6px; border:1px solid #A9DFBF;">
                <div style="font-size:11px; color:#145A32; font-weight:600;">DUPLICATE BILL GROUPS</div>
                <div style="font-size:20px; font-weight:700; color:#1E8449;">${s.duplicate_bill_groups}</div>
            </div>
        </div>
        ${benfordHtml}
        ${suspiciousHtml}
    `;
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatHeader(str) {
    return str.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function formatMarkdownText(text) {
    let html = escapeHtml(text);
    // Bold **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    // Bullet points
    html = html.replace(/\n- (.*?)/g, '<br>• $1');
    html = html.replace(/\n/g, '<br>');
    return html;
}
