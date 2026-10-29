# LedgerGPT Engineering Learnings

### 2026-10-29: Deterministic-First Financial AI Architecture
- **Lesson**: Standard LLMs cannot be trusted for financial math, as they will hallucinate numbers and corrupt financial reconciliation.
- **Solution**: Decouple intent recognition from arithmetic execution. Use the language model *only* to interpret user intent and write standard SQLite `SELECT` statements; let the database engine perform exact sums, groupings, and counts.

### 2026-10-29: SQLite FTS5 External Content Rebuild Directive
- **Lesson**: When creating an FTS5 virtual table with `content='vouchers'`, executing `DELETE FROM vouchers_fts` corrupts virtual table shadow structures (`database disk image is malformed`).
- **Solution**: Use SQLite's official rebuild command:
  ```sql
  INSERT INTO vouchers_fts(vouchers_fts) VALUES('rebuild');
  ```
  This cleanly resynchronizes the FTS index from the underlying content table.

### 2026-10-29: Multi-Cost-Centre Voucher Deduplication
- **Lesson**: In Tally Prime, a single voucher number or invoice often has multiple allocations to different cost centres or expense ledgers. Enforcing a `UNIQUE` constraint on `voucher_guid` caused multi-line vouchers to overwrite previous cost-centre allocations during batch ingestion.
- **Solution**: Rely on an auto-increment integer primary key `id` for row-level integrity and allow multiple lines with the same `guid`.
