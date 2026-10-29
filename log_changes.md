# LedgerGPT Change Log

## [1.5.0] - 2026-10-29
### Remediated & Hardened - Comprehensive 22-Point QC Resolution
- **Critical #1 - GUID Re-Sync Deduplication (`ledgergpt/db.py`)**:
  - Implemented `idx_vouchers_guid` partial unique index on non-null/non-empty GUIDs.
  - Replaced plain INSERT with `INSERT INTO vouchers ... ON CONFLICT(guid) DO UPDATE SET ...` preventing book doubling on re-sync.
- **Critical #2 - Read-Only SQL Validator Hardening (`ledgergpt/db.py`)**:
  - Implemented SQLite `set_authorizer` strictly denying all write actions (INSERT, UPDATE, DELETE, DROP, ALTER, ATTACH) regardless of CTE wrapping (`WITH t AS (...) DELETE FROM ...`).
  - Added regex defense in depth and safe authorizer reset in `finally`.
- **Critical #3 - Zero Fabricated Dashboard KPIs (`ledgergpt/dashboard_service.py`, `ledgergpt/tally_sync.py`)**:
  - Removed all hardcoded synthetic figures (`₹89,468`, `₹64,927.02`, `₹21.05 Cr`, `₹21.13 Cr`, `₹38.9 Cr`, `2.64` turnover days, `AXIS BANK (INDIA)`).
  - Derived liquidity, turnover days, and cash flows purely from actual database records and authentic parsed Tally XML data.
  - Returns `[]` for periods if no vouchers are loaded.
- **Critical #4 & High #5 - Double-Entry Ledger Statement & Tally Sign Preservation (`ledgergpt/query_engine.py`, `ledgergpt/tally_sync.py`)**:
  - Implemented authentic accounting Dr/Cr logic for Cash/Bank asset accounts: Inflows/Receipts $\to$ Debit, Outflows/Payments $\to$ Credit.
  - Customer/Debtor: Sales $\to$ Dr, Receipts $\to$ Cr. Vendor/Creditor: Purchases $\to$ Cr, Payments $\to$ Dr.
  - Used `net_amount` for nominal tax-bearing accounts to prevent double-counting tax.
  - Preserved Tally Prime XML convention where negative amounts represent Debit entries.
- **High #6 - Lakh-Comma Amount Parsing & Unparseable Date Defense (`ledgergpt/tally_sync.py`)**:
  - Implemented `clean_amount()` stripping Indian commas, handling Dr/Cr suffixes, and eliminating `ValueError` 0.0 zeroing.
  - Prevented silent fabrication of today's date for bad dates; recorded unparseable dates into `self.rejected_records`.
- **High #7 - Aging Filter by Fiscal Year (`ledgergpt/dashboard_service.py`)**:
  - Added fiscal year date range boundary filter on `bills_outstanding` query.
- **High #8 - LLM SQL Guardrails (`ledgergpt/query_engine.py`)**:
  - Injected mandatory `LIMIT 100` on LLM-generated SQL statements.
- **Medium & Low Cleanups (#9-#22)**:
  - FTS5 multi-word phrase quotation (`" OR ".join(f'"{k}"' for k in keywords)`).
  - Whole-word matching for Section 269SS scanner (`' ' || LOWER(party) || ' ' LIKE '% cash %'`), preventing false positives on *Akash*.
  - Benford's Law formatted float representation avoiding scientific notation noise.
  - Web export endpoint capping at 50,000 rows and filename path traversal sanitization.
  - Route alias `/api/tally-sync` matching README.
  - Setup.py packaging fix with `py_modules=["cli"]` and entry point `ledgergpt=ledgergpt.cli:main`.
  - Replaced `sys.stdout = io.TextIOWrapper(...)` with `sys.stdout.reconfigure(encoding='utf-8')`.
  - Escaped `'` as `&#39;` in `escapeHtml()` and sanitized `err.message` in web modal DOM.
- **Regression Suite**: Added `tests/test_qc_remediation.py` (7 tests). All 34 tests passing (`34/34 OK`).
- **Audit Workbook**: Delivered `LedgerGPT_QC_Audit_and_Remediation_Plan.xlsx` (3 sheets).

## [1.4.0] - 2026-10-29
### Added & Delivered - Option A External Intelligence Integration (EasyReports & CA Ramajayam Benchmark)
- **Bill-by-Bill Debtor & Creditor Aging Intelligence Cockpit**:
  - Live Tally XML collection extraction from `BillsOutstanding` collection querying exact overdue days, bill dates, bill ref, party name, and balance.
  - Categorized into institutional aging buckets: `0-30 Days` (Low Risk), `31-60 Days` (Moderate Risk), `61-90 Days` (Elevated Risk), and `90+ Days (Critical)`.
  - Fallback dynamic aging engine calculating overdue days from voucher history when offline.
  - Interactive visual card on web dashboard displaying Total Receivables & Payables with high-risk alerts.
- **Dynamic Project Site / Cost Centre Filtering**:
  - Extracted distinct cost centres dynamically from voucher postings (`get_available_cost_centres`).
  - Added Site / Cost Centre selector in top header alongside Fiscal Year filter.
  - Filter cascades across Executive Summary, Monthly Trends, Rankings, Aging, and Voucher Grid.
- **1-Click CFO MIS Board Pack Export**:
  - Added dedicated `/api/dashboard/cfo-mis-pack` endpoint consolidating Executive Summary, Liquidity Cockpit, Aging Overview, Top 10 Debtors & Creditors, and Critical Overdue Bills into a single CFO-ready CSV download.
- **Statutory Audit Forensics (CA J Ramajayam Benchmark)**:
  - **Section 269SS & 269T Violations (Form 3CD Clause 31)**: Scans for cash loans, deposits, and repayments $\ge$ ₹ 20,000 across Loan, Advance, and Unsecured borrowing accounts.
  - **Negative Cash Balance Scanner**: Reconstructs day-by-day cash ledger running balance, flagging any transaction driving cash into negative.
- **Deterministic Natural Language Query Routing**:
  - Mapped queries like *"Show creditors aging"*, *"Show bills outstanding"*, *"Scan Section 269SS cash loans"*, and *"Negative cash balance"* to deterministic handlers.
- **Documentation**:
  - Created `USER_MANUAL.md` for CFOs, controllers, and statutory auditors.
  - Created `HOW_TO_GUIDE.md` with practical recipes for live Tally sync, CSV ingestion, Section 269SS checks, and CLI automation.
  - Updated `README.md` and `walkthrough.md`.
- **Test Suite**: Added `tests/test_aging_and_mis.py`. All 27 unit tests passing (`27/27 OK`).

## [1.2.1] - 2026-10-29
### Fixed & Delivered - Deterministic Party Ledger & Cash Flow Intent Routing
- **Party Ledger Account Statement Routing**:
  - Added dedicated deterministic parser extracting party/ledger candidate and resolving against database party_name and primary_ledger.
  - Generates authentic double-entry Ledger Statement for the party (chronological transactions, summary banner, net balance).
- **Cash Inflow & Outflow Liquidity Routing**:
  - Added dedicated deterministic handler computing Total Cash Inflow, Total Outflow, Net Cash Flow, and Contra transfers alongside monthly time-series.
- **Improved FTS Fallback**:
  - Filtered conversational and command stopwords ('share', 'show', 'ledger', 'statement', 'vouchers').
  - Changed default FTS matching from broad 'OR' to strict 'AND' relevance with automatic fallback.

## [1.2.0] - 2026-10-29
### Added & Delivered - Complete Tally Liquidity Cockpit, Dynamic Periods & Forensic Suite
- **Tally Group Extraction Engine**:
  - Implemented `fetch_tally_dashboard_metrics` in `tally_sync.py` extracting exact closing ledger balances from Tally Prime XML collections: Cash-in-hand, Bank Accounts, Current Assets, Current Liabilities, Working Capital, Net Cash Flow.
- **Dynamic Company & Period Filters**:
  - Active company header badge.
  - Dynamic Fiscal Year filter dropdown based on actual voucher dates in the database.
- **5-Table Forensic Anomaly Suite**:
  - Benford's Law distribution, Suspicious narrations, Round-sum payments, Weekend-dated vouchers, Duplicate billing groups.

## [1.0.0] - 2026-10-29
### Initial Production Release
- **Core Database Engine**: SQLite schema with `vouchers`, indexes, and FTS5 full-text search.
- **Data Ingestor**: Intelligent fuzzy register reader & Tally XML importer.
- **Deterministic Query Engine**: Sub-5ms rule routing and pluggable LLM fallback (`LLMAdapter`).
- **Web UI & REST API**: Responsive executive web application using Flask, Segoe UI design system, real-time KPI banner, SQL audit accordion, and CSV export streaming.
- **Preloaded Sample Data**: Bundled 50,102 audited vouchers from Genesis dataset.
