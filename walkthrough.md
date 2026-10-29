# LedgerGPT Technical Walkthrough

## 1. System Overview
LedgerGPT is an on-premise, zero-hallucination conversational AI and deterministic query engine for ERP and Tally Prime databases. It bridges the gap between natural language user inquiries and rigid double-entry accounting data.

## 2. Directory Structure
```
D:\AAAA_MYPROJECT\LedgerGPT\
├── ledgergpt/
│   ├── __init__.py           # Package exports
│   ├── config.py             # Config & environment settings
│   ├── db.py                 # SQLite connection & FTS5 full-text search schema
│   ├── formatters.py         # Indian numbering system (format_inr) & date utilities
│   ├── ingestor.py           # Intelligent fuzzy register reader & Tally XML importer
│   ├── query_engine.py       # Deterministic rule engine & LLM text-to-SQL adapter
│   ├── forensic.py           # 5-part forensic audit & Benford's Law anomaly scanner
│   ├── llm_adapter.py        # Pluggable REST adapter for Gemini, OpenAI, Claude, Ollama
│   └── web/
│       ├── app.py            # Flask API & server endpoints
│       ├── templates/index.html # Modern executive UI
│       └── static/           # CSS & JS application logic
├── sample_data/              # Preloaded 50,102-voucher Genesis audited dataset
├── tests/                    # Automated test suite (Engine & Web API)
├── docs/                     # Architecture & technical documentation
├── cli.py                    # Terminal CLI interface
├── run_web.py                # 1-click web launcher
├── requirements.txt          # Python dependencies
├── setup.py                  # Package installer
└── README.md                 # Complete GitHub guide
```

## 3. Execution Flow
1. **Ingestion**: When data is loaded (via CSV, Excel, or live Tally XML), `DataIngestor` normalizes column names, parses dates into Indian financial quarters/years, flags round-sum amounts, and extracts day-of-week indicators.
2. **Indexing**: Records are inserted into `vouchers` table in SQLite, and `vouchers_fts` (FTS5 virtual table) indexes the text.
3. **Query Resolution**:
   - `QueryEngine.process_query()` checks deterministic regex rules. If matched, it constructs parameterized SQL and executes in $<5$ ms.
   - If unmatched, `LLMAdapter` constructs an audited `SELECT` query using the database schema context.
   - If SQL is unavailable, `QueryEngine` executes a full-text search across all voucher fields.
4. **Synthesis & Formatting**: Output values are formatted using `format_inr()` (e.g. `₹ 90.72 Cr` or `₹ 50,07,718.56`), and results are displayed with an interactive table, export button, and collapsible SQL audit trace.
