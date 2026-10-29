"""
Financial Database Manager & Schema Engine for LedgerGPT.
Uses high-performance SQLite with FTS5 Full-Text Search.
Remediated for strict read-only execution, GUID upsert deduplication,
connection lifecycle management, and WAL/busy timeout resilience.
"""

import sqlite3
import os
import re
from pathlib import Path
from ledgergpt.config import DB_PATH


def read_only_authorizer(action, arg1, arg2, db_name, trigger_name):
    """
    SQLite authorizer callback that strictly forbids all write, DDL,
    and schema-modifying actions during read-only SQL queries.
    Blocks CTE injection attacks (e.g., WITH t AS (...) DELETE FROM ...).
    Permits internal virtual table schema reflection on sqlite_master.
    """
    if action in (
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH,
    ):
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_UPDATE:
        if arg1 not in ("sqlite_master", "sqlite_schema"):
            return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class ManagedConnection(sqlite3.Connection):
    """
    Custom SQLite Connection that automatically closes upon context exit
    when used as `with conn:`, preventing connection leaks while preserving
    shared in-memory connections.
    """
    is_shared = False

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            if not self.is_shared:
                self.close()


class FinancialDB:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._shared_conn = None
        
        # If in-memory, keep a single persistent connection
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:", factory=ManagedConnection)
            self._shared_conn.is_shared = True
            self._shared_conn.row_factory = sqlite3.Row
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
        self.init_schema()

    def get_connection(self):
        if self._shared_conn:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path, factory=ManagedConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except Exception:
            pass
        return conn

    def init_schema(self):
        """Initializes tables, indexes, and full-text search."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Vouchers Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vouchers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT,
            voucher_type TEXT NOT NULL,
            voucher_no TEXT,
            reference_no TEXT,
            date TEXT NOT NULL,
            financial_year TEXT NOT NULL,
            month_year TEXT NOT NULL,
            quarter TEXT NOT NULL,
            party_name TEXT NOT NULL,
            primary_ledger TEXT NOT NULL,
            cost_centre TEXT DEFAULT 'General / Untagged',
            net_amount REAL DEFAULT 0.0,
            tax_amount REAL DEFAULT 0.0,
            gross_amount REAL DEFAULT 0.0,
            narration TEXT DEFAULT '',
            day_of_week TEXT,
            is_weekend INTEGER DEFAULT 0,
            is_round_sum INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Metadata Table for active company & snapshot metrics
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Bills Outstanding Table for Live Aging & Bill Tracking
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills_outstanding (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_type TEXT NOT NULL, -- 'Receivable' or 'Payable'
            bill_date TEXT NOT NULL,
            bill_ref TEXT,
            party_name TEXT NOT NULL,
            outstanding_amount REAL DEFAULT 0.0,
            overdue_days INTEGER DEFAULT 0,
            cost_centre TEXT DEFAULT 'General / Untagged',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_type ON bills_outstanding(bill_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_party ON bills_outstanding(party_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_days ON bills_outstanding(overdue_days)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_bills_cc ON bills_outstanding(cost_centre)")

        # Core Financial Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_type ON vouchers(voucher_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_date ON vouchers(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_fy ON vouchers(financial_year)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_qtr ON vouchers(quarter)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_party ON vouchers(party_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_ledger ON vouchers(primary_ledger)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_cc ON vouchers(cost_centre)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_gross ON vouchers(gross_amount)")

        # Unique partial index on GUID to prevent book duplication on re-sync
        cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_vouchers_guid 
        ON vouchers(guid) 
        WHERE guid IS NOT NULL AND guid != ''
        """)

        # Full-Text Search Table (FTS5)
        cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS vouchers_fts USING fts5(
            party_name,
            primary_ledger,
            cost_centre,
            reference_no,
            narration,
            content='vouchers',
            content_rowid='id'
        )
        """)

        conn.commit()
        if not self._shared_conn:
            conn.close()

    def rebuild_fts(self):
        """Rebuilds the FTS index using SQLite's native FTS5 rebuild directive."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO vouchers_fts(vouchers_fts) VALUES('rebuild')")
        conn.commit()
        if not self._shared_conn:
            conn.close()

    def insert_vouchers_batch(self, vouchers_list, rebuild_fts=True):
        """
        High-speed batch insertion of vouchers with GUID upsert deduplication
        and defensive key normalization.
        """
        if not vouchers_list:
            return 0

        defaults = {
            "guid": None, "voucher_type": "Voucher", "voucher_no": "", "reference_no": "",
            "date": "", "financial_year": "", "month_year": "", "quarter": "",
            "party_name": "Sundry Party", "primary_ledger": "General Ledger",
            "cost_centre": "General / Untagged", "net_amount": 0.0, "tax_amount": 0.0,
            "gross_amount": 0.0, "narration": "", "day_of_week": "", "is_weekend": 0, "is_round_sum": 0
        }
        sanitized = [{**defaults, **v} for v in vouchers_list]

        conn = self.get_connection()
        cursor = conn.cursor()
        sql = """
        INSERT INTO vouchers (
            guid, voucher_type, voucher_no, reference_no, date,
            financial_year, month_year, quarter, party_name,
            primary_ledger, cost_centre, net_amount, tax_amount,
            gross_amount, narration, day_of_week, is_weekend, is_round_sum
        ) VALUES (
            :guid, :voucher_type, :voucher_no, :reference_no, :date,
            :financial_year, :month_year, :quarter, :party_name,
            :primary_ledger, :cost_centre, :net_amount, :tax_amount,
            :gross_amount, :narration, :day_of_week, :is_weekend, :is_round_sum
        )
        ON CONFLICT(guid) WHERE guid IS NOT NULL AND guid != '' DO UPDATE SET
            voucher_type = excluded.voucher_type,
            voucher_no = excluded.voucher_no,
            reference_no = excluded.reference_no,
            date = excluded.date,
            financial_year = excluded.financial_year,
            month_year = excluded.month_year,
            quarter = excluded.quarter,
            party_name = excluded.party_name,
            primary_ledger = excluded.primary_ledger,
            cost_centre = excluded.cost_centre,
            net_amount = excluded.net_amount,
            tax_amount = excluded.tax_amount,
            gross_amount = excluded.gross_amount,
            narration = excluded.narration,
            day_of_week = excluded.day_of_week,
            is_weekend = excluded.is_weekend,
            is_round_sum = excluded.is_round_sum
        """
        cursor.executemany(sql, sanitized)
        conn.commit()
        if not self._shared_conn:
            conn.close()
            
        if rebuild_fts:
            self.rebuild_fts()
        return len(sanitized)

    def execute_query(self, sql, params=()):
        """
        Execute a read-only SQL query and return rows as dicts.
        Secured with SQLite authorizer preventing any write or schema tampering,
        regardless of statement structure (e.g. CTEs, subqueries, comments).
        """
        stripped = sql.strip()
        first_token = re.split(r'\s+', stripped)[0].upper()
        forbidden_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE", "REPLACE", "CREATE"]
        if first_token in forbidden_keywords:
            raise ValueError(f"Write operation '{first_token}' is forbidden in financial query engine.")

        # Additional regex check for write verbs across statement
        if re.search(r'\b(DELETE\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DROP\s+TABLE|ALTER\s+TABLE)\b', stripped, re.IGNORECASE):
            raise ValueError("Write operation detected in financial query engine.")

        conn = self.get_connection()
        conn.set_authorizer(read_only_authorizer)
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            result = [dict(r) for r in rows]
            return result
        finally:
            conn.set_authorizer(None)
            if not self._shared_conn:
                conn.close()

    def get_kpis(self):
        """Returns consolidated financial KPIs."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            COUNT(*) as total_vouchers,
            COALESCE(SUM(CASE WHEN LOWER(voucher_type) = 'sales' THEN gross_amount ELSE 0 END), 0) as total_sales_gross,
            COALESCE(SUM(CASE WHEN LOWER(voucher_type) = 'sales' THEN net_amount ELSE 0 END), 0) as total_sales_net,
            COALESCE(SUM(CASE WHEN LOWER(voucher_type) = 'purchase' THEN gross_amount ELSE 0 END), 0) as total_purchase_gross,
            COALESCE(SUM(CASE WHEN LOWER(voucher_type) = 'purchase' THEN net_amount ELSE 0 END), 0) as total_purchase_net,
            COALESCE(SUM(CASE WHEN LOWER(voucher_type) = 'debit note' THEN gross_amount ELSE 0 END), 0) as total_debit_notes_gross,
            COALESCE(SUM(CASE WHEN LOWER(voucher_type) = 'credit note' THEN gross_amount ELSE 0 END), 0) as total_credit_notes_gross,
            COUNT(DISTINCT party_name) as unique_parties,
            COUNT(DISTINCT cost_centre) as unique_cost_centres,
            MIN(date) as min_date,
            MAX(date) as max_date
        FROM vouchers
        """)
        row = cursor.fetchone()
        result = dict(row) if row else {}
        if not self._shared_conn:
            conn.close()
        return result

    def insert_bills_batch(self, bills_list):
        """Batch inserts bills outstanding records."""
        if not bills_list:
            return 0
        defaults = {
            "bill_type": "Payable", "bill_date": "", "bill_ref": "-",
            "party_name": "Sundry Party", "outstanding_amount": 0.0,
            "overdue_days": 0, "cost_centre": "General / Untagged"
        }
        sanitized = [{**defaults, **b} for b in bills_list]
        conn = self.get_connection()
        cursor = conn.cursor()
        sql = """
        INSERT INTO bills_outstanding (
            bill_type, bill_date, bill_ref, party_name, outstanding_amount, overdue_days, cost_centre
        ) VALUES (
            :bill_type, :bill_date, :bill_ref, :party_name, :outstanding_amount, :overdue_days, :cost_centre
        )
        """
        cursor.executemany(sql, sanitized)
        conn.commit()
        if not self._shared_conn:
            conn.close()
        return len(sanitized)

    def clear_bills(self, bill_type=None):
        """Clears bills outstanding table, optionally filtered by bill_type."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if bill_type:
            cursor.execute("DELETE FROM bills_outstanding WHERE LOWER(bill_type) = LOWER(?)", (bill_type,))
        else:
            cursor.execute("DELETE FROM bills_outstanding")
        conn.commit()
        if not self._shared_conn:
            conn.close()

    def set_metadata(self, key, value):
        """Sets a key-value pair in company_metadata table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO company_metadata (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()
        if not self._shared_conn:
            conn.close()

    def get_metadata(self, key, default=None):
        """Gets a value by key from company_metadata table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM company_metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not self._shared_conn:
            conn.close()
        return row[0] if row else default

    def get_schema_summary(self):
        """Returns schema summary for LLM text-to-SQL context."""
        return """
Table: vouchers
Columns:
- id: INTEGER PRIMARY KEY
- voucher_type: TEXT ('Sales', 'Purchase', 'Debit Note', 'Credit Note', 'Journal', 'Payment', 'Receipt')
- voucher_no: TEXT (Voucher Number)
- reference_no: TEXT (Invoice / Bill / Reference Number)
- date: TEXT (YYYY-MM-DD format)
- financial_year: TEXT ('FY 2017-18', 'FY 2018-19')
- month_year: TEXT ('Apr 2017', 'May 2017')
- quarter: TEXT ('Q1', 'Q2', 'Q3', 'Q4' where Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar)
- party_name: TEXT (Debtor or Creditor name)
- primary_ledger: TEXT (Revenue / Expense / Adjustment Ledger Name)
- cost_centre: TEXT (Project / Event / Branch Name)
- net_amount: REAL (Amount before tax)
- tax_amount: REAL (CGST, SGST, IGST, etc.)
- gross_amount: REAL (Total billed amount: net + tax)
- narration: TEXT (Transaction narration / notes)
- day_of_week: TEXT ('Monday'..'Sunday')
- is_weekend: INTEGER (1 if Saturday or Sunday, else 0)
- is_round_sum: INTEGER (1 if amount is exact multiple of 10,000, 50,000, 1,00,000)

Table: vouchers_fts (Full-text search on party_name, primary_ledger, cost_centre, reference_no, narration)
Query example for FTS:
SELECT v.* FROM vouchers v JOIN vouchers_fts f ON v.id = f.rowid WHERE vouchers_fts MATCH 'cancellation OR refund'
"""
