# LedgerGPT Technical Walkthrough 🏗️

## 1. System Overview
LedgerGPT is an on-premise, zero-hallucination conversational AI and deterministic financial query engine for ERP and Tally Prime databases. It bridges the gap between natural language user inquiries and rigid double-entry accounting data without arithmetic hallucination.

---

## 2. Directory Structure
```
D:\AAAA_MYPROJECT\LedgerGPT\
├── ledgergpt/
│   ├── __init__.py           # Package exports
│   ├── config.py             # Config & environment settings
│   ├── db.py                 # SQLite connection, schema, bills_outstanding, & FTS5 full-text search
│   ├── formatters.py         # Indian numbering system (format_inr) & date utilities
│   ├── ingestor.py           # Intelligent fuzzy register reader & Tally XML importer
│   ├── tally_sync.py         # Tally Prime live XML client (port 9000), multi-company sync, bills extraction
│   ├── dashboard_service.py  # Dashboard analytics, aging buckets, CFO MIS pack generator
│   ├── query_engine.py       # Deterministic rule engine & LLM text-to-SQL adapter
│   ├── forensic.py           # 7-part forensic audit (Benford's, Section 269SS/269T, Negative Cash, etc.)
│   ├── llm_adapter.py        # Pluggable REST adapter for Gemini, OpenAI, Claude, Ollama
│   └── web/
│       ├── app.py            # Flask API & REST server endpoints
│       ├── templates/index.html # Modern executive UI & aging cockpit
│       └── static/           # CSS & JS application logic
├── sample_data/              # Preloaded 50,102-voucher Genesis audited dataset
├── tests/                    # Automated test suite (27 unit tests across all engines)
│   ├── test_aging_and_mis.py # Aging buckets, cost centres, CFO MIS pack, Section 269SS tests
│   ├── test_dashboard_api.py # Dashboard service and web API tests
│   ├── test_query_engine.py  # Query engine deterministic matching tests
│   ├── test_tally_sync.py    # Tally sync client connection and mock sync tests
│   └── test_web_api.py       # Flask endpoints and chat routing tests
├── docs/                     # Architecture & technical documentation
├── USER_MANUAL.md            # Comprehensive user manual for CFOs and auditors
├── HOW_TO_GUIDE.md           # Step-by-step developer and end-user recipes
├── cli.py                    # Terminal CLI interface
├── run_web.py                # 1-click web launcher
├── run.bat                   # Windows 1-click batch launcher
├── requirements.txt          # Python dependencies
├── setup.py                  # Package installer
└── README.md                 # Complete GitHub guide
```

---

## 3. End-to-End Execution Flow

### A. Data Ingestion & Live Sync Pipeline
1. **Live Tally XML Extraction**:
   - `TallySyncClient` connects to Tally Prime on `http://localhost:9000`.
   - Fetches open companies via `<TYPE>Company</TYPE>`.
   - Extracts all vouchers via `<COLLECTION NAME="ExportVouchers">` with escaped XML envelopes.
   - Extracts live outstanding bills via `<COLLECTION NAME="BillsOutstanding"><TYPE>Bills</TYPE>...`.
   - Extracts dashboard metrics (Cash, Bank, Current Assets, Liabilities, Working Capital).
2. **Storage & Indexing**:
   - Vouchers are stored in the SQLite `vouchers` table with an auto-increment primary key to preserve multi-cost-centre line items.
   - All narrations and text tokens are indexed in `vouchers_fts` (SQLite FTS5).
   - Outstanding bills are stored in `bills_outstanding` with indexing on `party_name`, `bill_type`, and `overdue_days`.

### B. Query Resolution & Intent Routing
```
User Query -> QueryEngine.process_query()
                   │
                   ├──> Deterministic Matching? (<5ms)
                   │         ├── Aging Query? -> dashboard_service.get_aging_summary()
                   │         ├── Section 269SS? -> forensic.detect_section_269ss_269t_violations()
                   │         ├── Negative Cash? -> forensic.detect_negative_cash_balances()
                   │         ├── Cash Flow? -> Compute receipts/payments/contra + monthly series
                   │         ├── Party Statement? -> Build chronological double-entry ledger
                   │         └── Sales / Purchases / Notes? -> Parameterized SQL execution
                   │
                   ├──> Complex Ad-Hoc Inquiry?
                   │         ├── LLMAdapter (Gemini/OpenAI/Ollama) -> Generate SQL
                   │         └── Read-Only SQL Validator -> Execute verified SELECT
                   │
                   └──> Fallback? -> FTS5 Narration & Keyword Search
```

### C. Synthesis & Formatting
- All numbers formatted with `format_inr()` (e.g., `₹ 77,55,247.00` or `₹ 326.06 Cr`).
- Results delivered with:
  1. CFO-ready answer summary.
  2. Data table with pagination and sorting.
  3. 1-Click UTF-8 BOM CSV export.
  4. Collapsible SQL trace with execution latency.
