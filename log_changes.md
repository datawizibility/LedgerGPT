# LedgerGPT Change Log

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
