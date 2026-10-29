# LedgerGPT Enterprise User Manual 📘
> **Comprehensive Operating Manual for Promoters, CFOs, Controllers, Chartered Accountants, and Statutory Auditors.**

---

## Table of Contents
1. [Introduction & Core Philosophy](#1-introduction--core-philosophy)
2. [System Requirements & Architecture](#2-system-requirements--architecture)
3. [Launching & Accessing LedgerGPT](#3-launching--accessing-ledgergpt)
4. [Live Tally Prime Integration](#4-live-tally-prime-integration)
5. [Navigating the Executive Dashboard](#5-navigating-the-executive-dashboard)
6. [Dynamic Period & Project Site Filters](#6-dynamic-period--project-site-filters)
7. [Debtor & Creditor Aging Intelligence Cockpit](#7-debtor--creditor-aging-intelligence-cockpit)
8. [1-Click CFO MIS Board Pack](#8-1-click-cfo-mis-board-pack)
9. [Forensic Audit & Statutory Scanner (Form 3CD Suite)](#9-forensic-audit--statutory-scanner-form-3cd-suite)
10. [Conversational Financial Copilot (NL Query Engine)](#10-conversational-financial-copilot-nl-query-engine)
11. [Voucher Ledger Grid & Deep Drill-Down](#11-voucher-ledger-grid--deep-drill-down)
12. [Troubleshooting & FAQ](#12-troubleshooting--faq)

---

## 1. Introduction & Core Philosophy

Standard Large Language Models (LLMs) hallucinate arithmetic, round off figures unpredictably, and pose grave privacy risks when transmitting enterprise financial statements to cloud servers.

**LedgerGPT** is built on a **Deterministic-First AI Architecture**:
* **100% On-Premise Privacy**: Runs locally on your machine or private LAN. No financial data leaves your firewall.
* **Zero Math Hallucination**: Natural language inquiries are compiled into verified, parameterized SQL `SELECT` queries executed directly against local SQLite tables. Arithmetic is executed by the database engine, not an LLM.
* **Sub-Millisecond Response**: Common financial queries (sales totals, aging buckets, cash flows, party statements) respond in **under 5 milliseconds**.
* **Traceable & Audited**: Every answer provides an audit trail: exact SQL query executed, execution latency, formatted table, and 1-click CSV export.

---

## 2. System Requirements & Architecture

* **Operating System**: Windows 10/11, Windows Server 2016+, macOS, or Linux.
* **Python**: Python 3.9 or higher.
* **Tally Prime Compatibility**: Tally Prime (any release), Tally.ERP 9 with ODBC/XML Server enabled on port 9000.
* **Browsers**: Chrome, Edge, Firefox, Brave, Safari.
* **Database**: Local SQLite 3 with FTS5 (Full-Text Search) extension.

---

## 3. Launching & Accessing LedgerGPT

### Option A: 1-Click Desktop Launcher (Windows)
Double-click the **`run.bat`** file in `D:\AAAA_MYPROJECT\LedgerGPT` or your Desktop shortcut **`LedgerGPT Enterprise`**.

### Option B: Command-Line Web Server
Open PowerShell or Command Prompt:
```powershell
cd D:\AAAA_MYPROJECT\LedgerGPT
python run_web.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

### Option C: Interactive CLI Terminal
```powershell
python cli.py
```
Run single commands directly from the shell:
```powershell
python cli.py -q "Creditors aging"
python cli.py --forensic
python cli.py --kpis
```

---

## 4. Live Tally Prime Integration

LedgerGPT integrates with Tally Prime in real time via Tally's native XML port (`9000`).

### Connecting Tally Prime:
1. Ensure Tally Prime is running on the same machine.
2. Verify Tally's XML Server is enabled (`F1: Help` -> `Settings` -> `Connectivity` -> `Client/Server Configuration` -> `TallyPrime acts as: Both`, `Port: 9000`).
3. In LedgerGPT's top navigation bar, click the **`⚡ Sync Tally`** button.
4. If multiple companies are open in Tally, LedgerGPT's dynamic selector lists all open companies.
5. Select your desired company (e.g., `BHARAT VANIJYA EASTERN PRIVATE LIMITED (LATEHAR)`).
6. Click **`Start Sync`**. LedgerGPT streams:
   * Master Chart of Accounts & Ledgers
   * All Vouchers (Sales, Purchases, Receipts, Payments, Contra, Journals, Debit/Credit Notes)
   * Live Outstanding Bills (`BillsOutstanding` collection)
   * Group closing balances (Cash, Bank, Current Assets, Current Liabilities, Working Capital)

---

## 5. Navigating the Executive Dashboard

Upon launching the web cockpit, you are presented with:

```
+-----------------------------------------------------------------------------------------+
| [⚡ Sync Tally]  [📑 CFO MIS Pack]  [🔍 Forensic Scanner]  [Site: Latehar ▼]  [FY: All ▼]  |
+-----------------------------------------------------------------------------------------+
| 💰 Total Billed   | 🛒 Total Expenses | 📑 Net Debit Notes | 📜 Total Vouchers          |
|    ₹ 326.06 Cr    |    ₹ 267.43 Cr    |    ₹ 14.85 L       |    50,102 Transactions     |
+-----------------------------------------------------------------------------------------+
| 🏦 Cash-in-Hand   | 🏛️ Bank Balances  | 📦 Current Assets  | ⚖️ Current Liabilities     |
|    ₹ 89,468.00    |    ₹ 64,927.02    |    ₹ 21.06 Cr      |    ₹ 21.13 Cr              |
+-----------------------------------------------------------------------------------------+
| 📊 Bill-by-Bill Aging Cockpit (Receivables & Payables Buckets: 0-30, 31-60, 61-90, 90+)  |
+-----------------------------------------------------------------------------------------+
| 📈 Monthly Trend Chart (Revenue vs Expense) | 🏆 Top 10 Clients & Vendors Spend        |
+-----------------------------------------------------------------------------------------+
| 💬 Conversational Copilot (Natural Language Query Box & Quick Inquiry Pills)           |
+-----------------------------------------------------------------------------------------+
| 📋 Comprehensive Live Vouchers Grid (Search, Filter by Type, Full Narration Trace)     |
+-----------------------------------------------------------------------------------------+
```

---

## 6. Dynamic Period & Project Site Filters

Located at the top right of the navigation header:

1. **Project Site / Cost Centre Filter (`Select Site / Cost Centre`)**:
   * Automatically scans all voucher postings and extracts distinct project sites/cost centres.
   * Selecting a site (e.g. `Latehar`) instantly re-aggregates KPIs, monthly trends, vendor spend, aging buckets, and voucher grids exclusively for that site.
2. **Fiscal Year Filter (`Select Fiscal Year`)**:
   * Auto-populates all fiscal years present in the ledger database (e.g., `FY 2024-25`, `FY 2025-26`).
   * Selecting a year isolates performance trends and eliminates cross-year distortion.
3. **Synchronized Global State**: Changing either filter updates all dashboard cards seamlessly without full page reloads.

---

## 7. Debtor & Creditor Aging Intelligence Cockpit

The aging cockpit provides institutional-grade visibility into working capital exposure.

### 4 Aging Buckets & Risk Classification:
* **0 - 30 Days (`Low Risk` - Emerald)**: Current bills within normal credit terms.
* **31 - 60 Days (`Moderate Risk` - Amber)**: Due bills requiring standard payment follow-up.
* **61 - 90 Days (`Elevated Risk` - Orange)**: Overdue bills requiring formal vendor/customer escalation.
* **90+ Days (`Critical Risk` - Crimson)**: High-risk overdue debt triggering liquidity warnings or bad-debt provisions.

### Features:
* **Tally Native Matching**: Reflects live `BillsOutstanding` tracking from Tally Prime.
* **Overdue Bill Identification**: Directly flags chronic overdue suppliers (e.g., Jai Maa Durga ₹ 9.90 L overdue >120 days).
* **Automated Fallback**: For ledgers without explicit bill-by-bill tagging, the fallback engine computes aging from historical voucher dates.

---

## 8. 1-Click CFO MIS Board Pack

Click the **`📑 CFO MIS Pack`** button in the header bar. LedgerGPT instantly compiles and downloads a formatted CSV digest containing:

1. **Executive Summary**: Total revenue, expenses, net margins, voucher counts, and active period.
2. **Liquidity & Working Capital**: Cash-in-hand, bank balances, liquid assets, short-term liabilities, and net working capital.
3. **Receivables & Payables Aging Summary**: Bucketed breakdown across 0-30, 31-60, 61-90, and 90+ days with risk ratings.
4. **Top 10 Debtors (Receivables)**: Major customers sorted by revenue contribution.
5. **Top 10 Creditors (Payables)**: Major vendors sorted by procurement volume.
6. **Critical Overdue Bills (> 90 Days)**: Detailed line-item schedule of high-risk overdue invoices with party names, bill numbers, and exact aging days.

---

## 9. Forensic Audit & Statutory Scanner (Form 3CD Suite)

Click the **`🔍 Forensic Scanner`** button to open the audit cockpit. LedgerGPT runs 7 automated forensic engines:

| Engine | Regulatory / Audit Standard | What It Detects |
| :--- | :--- | :--- |
| **Section 269SS & 269T Violations** | **Income Tax Act (Form 3CD Clause 31)** | Cash loans, deposits, and repayments $\ge$ ₹ 20,000 across borrowing and advance accounts. |
| **Daily Negative Cash Scanner** | **ICAI Technical Guidance & Income Tax** | Dates where the cash-in-hand ledger dipped below ₹ 0.00, indicating unrecorded cash receipts or backdated entries. |
| **Benford's Law Analysis** | **Forensic Accounting Standard (Nigrini)** | Logarithmic distribution of first digits (1-9) to identify fabricated invoices or artificial payment amounts. |
| **Suspicious Narration Hunter** | **Statutory Audit Risk Assessment** | Fast FTS5 search for terms like *dispute, cancel, refund, cash adjust, settlement, commission, kickback*. |
| **High-Value Round-Sum Payments** | **Fraud & Money Laundering Risk** | Round payments $\ge$ ₹ 1,00,000 that are exact multiples of ₹ 10,000. |
| **Weekend / Holiday Vouchers** | **Internal Control Review** | Transactions booked on Saturdays and Sundays outside regular banking/business operations. |
| **Potential Duplicate Invoices** | **Working Capital Leakage** | Identical vendor bill reference numbers or duplicate amounts on the same date. |

Every detected exception is displayed in a clean tabular view with full date, voucher number, party, and amount details.

---

## 10. Conversational Financial Copilot (NL Query Engine)

Type natural inquiries into the copilot chat box or click any quick-inquiry pill:

### Common Questions & Phrasings:
* **Creditors & Debtors Aging**:
  * *"Show creditors aging"*
  * *"Show debtors aging"*
  * *"Bills outstanding summary"*
* **Statutory Compliance**:
  * *"Scan Section 269SS and 269T cash loan violations"*
  * *"Negative cash balance"*
* **Party Statements & Double-Entry Ledgers**:
  * *"Ajay Kumar ledger"*
  * *"Bennett Coleman account statement"*
  * *(Renders chronological Date, Type, Particulars, Debit, Credit, Running Balance, and Settlement summary)*
* **Liquidity & Cash Flows**:
  * *"Show cash inflow and outflow"*
  * *(Renders total receipts, payments, net cash flow, and month-by-month time series)*
* **Sales & Revenue**:
  * *"Top 10 clients by gross billed volume"*
  * *"Total sales in FY 2024-25"*
* **Purchases & Expenses**:
  * *"Top 10 vendors by net expense"*
  * *"Purchases in Q2"*
* **Debit & Credit Notes**:
  * *"Total debit notes issued"*
  * *"Credit notes issued for rate difference"*

---

## 11. Voucher Ledger Grid & Deep Drill-Down

The bottom section of the web interface provides a full-featured ledger grid:
* **Multi-Voucher Filtering**: Filter by `All`, `Sales`, `Purchase`, `Receipt`, `Payment`, `Contra`, `Journal`, `Debit Note`, `Credit Note`.
* **Instant Text Search**: Filter across voucher numbers, party names, and narration keywords in real time.
* **Pagination**: Browse records in sets of 50 per page with pagination controls.
* **Narration Tooltips**: Hover over or view complete audit narrations for any entry.

---

## 12. Troubleshooting & FAQ

### Q1: Tally sync returns "Connection refused" on port 9000.
* **Fix**: Ensure Tally Prime is running and ODBC/XML Server is enabled on port 9000 (`F1: Help` -> `Settings` -> `Connectivity`).

### Q2: Why is the aging showing ₹ 0.00 for receivables?
* **Explanation**: Many site-expense companies (such as construction project site accounts) only incur purchases, contractor expenses, and head-office fund receipts. For such sites, Creditors (Payables) will reflect data, while Receivables are zero.

### Q3: How do I export data to Excel?
* **Options**:
  1. Click **`📑 CFO MIS Pack`** for the complete board report.
  2. In any chat copilot response table, click the **`📥 Export CSV`** button to download that specific inquiry as an Excel-compatible UTF-8 BOM CSV.

---
*LedgerGPT is developed by Datawizibility. Copyright © 2026. All rights reserved.*
