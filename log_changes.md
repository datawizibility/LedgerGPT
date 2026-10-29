# LedgerGPT Change Log

## [1.0.0] - 2026-10-29
### Initial Production Release
- **Core Database Engine**: Implemented `FinancialDB` with SQLite schema, indexes, and FTS5 full-text search.
- **Data Ingestor**: Implemented `DataIngestor` supporting fuzzy column matching across diverse ERP / Tally export conventions.
- **Deterministic Query Engine**: Implemented `QueryEngine` with sub-5ms rule routing and pluggable LLM fallback (`LLMAdapter`).
- **Forensic Suite**: Built `ForensicScanner` featuring Benford's Law analysis, suspicious narration hunter, round-sum payment detector, weekend voucher identifier, and duplicate bill matcher.
- **Web UI & REST API**: Built responsive executive web application using Flask, Segoe UI design system, real-time KPI banner, SQL audit accordion, and CSV export streaming.
- **Terminal CLI**: Implemented interactive chat loop and single-shot command-line interface (`cli.py`).
- **Preloaded Sample Data**: Bundled 50,102 audited vouchers from the Genesis dataset (Sales, Purchases, Debit & Credit Notes).
- **Automated Test Suite**: Added unit tests for database, query engine, forensic scanner, and web REST API endpoints.
