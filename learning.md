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

### 2026-10-29: SQLite Authorizer & FTS5 Internal Reflection
- **Lesson**: When setting `conn.set_authorizer` to block write operations, SQLite's FTS5 virtual table engine executes internal schema checks on `sqlite_master` which Python maps to action code 23 (`SQLITE_UPDATE`). Blithely blocking all action code 23 updates broke FTS5 query initialization with `vtable constructor failed: vouchers_fts`.
- **Solution**: Check the target table name in authorizer callbacks. If `action == sqlite3.SQLITE_UPDATE` and target is `sqlite_master` or `sqlite_schema`, permit it; deny write actions strictly on all user application tables.

### 2026-10-29: Double-Entry Dr/Cr Derivation for Asset vs Party Ledgers
- **Lesson**: In naive ledger statement generators, mapping voucher types without checking account classification causes Cash/Bank accounts to invert Dr and Cr (treating Cash inflows as Credit and outflows as Debit).
- **Solution**: Explicitly branch Dr/Cr derivation by account class: for Cash/Bank asset accounts, Inflows (Receipts/Sales) are always Debits and Outflows (Payments/Purchases) are always Credits.

### 2026-10-29: Zero Fabricated Metrics Principle
- **Lesson**: Hardcoding demo defaults in analytics fallback functions (e.g., ₹89,468 cash or ₹38.9 Cr turnover) undermines client trust and violates financial auditability rules.
- **Solution**: Return strictly computed values or clean zeroes / "N/A" indicators. Never substitute fabricated numbers for missing source data.
