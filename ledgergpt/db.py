"""
Financial Database Manager & Schema Engine for LedgerGPT.
Uses high-performance SQLite with FTS5 Full-Text Search.
"""

import sqlite3
import os
from pathlib import Path
from ledgergpt.config import DB_PATH

class FinancialDB:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self._shared_conn = None
        
        # If in-memory, keep a single persistent connection
        if self.db_path == ":memory:":
            self._shared_conn = sqlite3.connect(":memory:")
            self._shared_conn.row_factory = sqlite3.Row
        else:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            
        self.init_schema()

    def get_connection(self):
        if self._shared_conn:
            return self._shared_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
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

        # Core Financial Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_type ON vouchers(voucher_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_date ON vouchers(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_fy ON vouchers(financial_year)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_qtr ON vouchers(quarter)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_party ON vouchers(party_name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_ledger ON vouchers(primary_ledger)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_cc ON vouchers(cost_centre)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vch_gross ON vouchers(gross_amount)")

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

        # Metadata Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sys_metadata (
            key TEXT PRIMARY KEY,
            val TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

    def insert_vouchers_batch(self, vouchers_list):
        """High-speed batch insertion of vouchers."""
        if not vouchers_list:
            return 0
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
        """
        cursor.executemany(sql, vouchers_list)
        conn.commit()
        if not self._shared_conn:
            conn.close()
            
        self.rebuild_fts()
        return len(vouchers_list)

    def execute_query(self, sql, params=()):
        """Execute a read-only SQL query and return rows as dicts."""
        forbidden = ["DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE"]
        first_word = sql.strip().split()[0].upper()
        if first_word in forbidden:
            raise ValueError(f"Write operation '{first_word}' is forbidden in financial query engine.")

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        result = [dict(r) for r in rows]
        if not self._shared_conn:
            conn.close()
        return result

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
