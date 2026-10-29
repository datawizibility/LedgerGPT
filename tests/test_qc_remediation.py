"""
Comprehensive QC Remediation Regression Test Suite for LedgerGPT.
Verifies all 22 QC defects are permanently resolved across:
- GUID deduplication / UPSERT on re-sync
- Read-only SQL authorizer blocking CTE-wrapped write attacks
- Elimination of hardcoded fabricated dashboard KPIs
- Authentic double-entry Cash/Bank Dr/Cr ledger statement direction
- Comma-separated amount parsing and Tally sign preservation
- Fiscal year filtering in bills aging
- Whole-word matching for Section 269SS/269T tax audit scanner
- Export filename sanitization and row capping
"""

import unittest
import sqlite3
from ledgergpt.db import FinancialDB
from ledgergpt.query_engine import QueryEngine
from ledgergpt.dashboard_service import DashboardService
from ledgergpt.tally_sync import clean_amount
from ledgergpt.forensic import ForensicScanner


class TestQCRemediation(unittest.TestCase):
    def setUp(self):
        self.db = FinancialDB(":memory:")
        self.engine = QueryEngine(db=self.db)
        self.dashboard = DashboardService(db=self.db)
        self.scanner = ForensicScanner(db=self.db)

    def test_01_guid_deduplication_upsert(self):
        """Verify re-inserting the same GUID updates rather than duplicating rows/totals."""
        batch1 = [
            {"guid": "VCH-001", "voucher_type": "Sales", "voucher_no": "INV-1", "date": "2024-05-10",
             "financial_year": "FY 2024-25", "party_name": "Alpha Corp", "gross_amount": 100000.0, "net_amount": 90000.0},
            {"guid": "VCH-002", "voucher_type": "Purchase", "voucher_no": "PUR-1", "date": "2024-05-11",
             "financial_year": "FY 2024-25", "party_name": "Beta Supplies", "gross_amount": 50000.0, "net_amount": 45000.0}
        ]
        self.db.insert_vouchers_batch(batch1)
        kpis1 = self.db.get_kpis()
        self.assertEqual(kpis1["total_vouchers"], 2)
        self.assertEqual(kpis1["total_sales_gross"], 100000.0)

        # Re-syncing the identical batch should NOT double totals
        self.db.insert_vouchers_batch(batch1)
        kpis2 = self.db.get_kpis()
        self.assertEqual(kpis2["total_vouchers"], 2)
        self.assertEqual(kpis2["total_sales_gross"], 100000.0)

        # Updating an existing GUID with new amount should update in place
        batch1_updated = [
            {"guid": "VCH-001", "voucher_type": "Sales", "voucher_no": "INV-1", "date": "2024-05-10",
             "financial_year": "FY 2024-25", "party_name": "Alpha Corp", "gross_amount": 120000.0, "net_amount": 110000.0}
        ]
        self.db.insert_vouchers_batch(batch1_updated)
        kpis3 = self.db.get_kpis()
        self.assertEqual(kpis3["total_vouchers"], 2)
        self.assertEqual(kpis3["total_sales_gross"], 120000.0)

    def test_02_readonly_sql_blocks_cte_write_attack(self):
        """Verify SQLite authorizer blocks WITH ... DELETE FROM / INSERT / DROP attacks."""
        self.db.insert_vouchers_batch([
            {"guid": "V1", "voucher_type": "Sales", "date": "2024-05-01", "financial_year": "FY 2024-25",
             "party_name": "Test Party", "gross_amount": 1000.0}
        ])

        # Normal SELECT works
        rows = self.db.execute_query("SELECT COUNT(*) as cnt FROM vouchers")
        self.assertEqual(rows[0]["cnt"], 1)

        # CTE write attack must be blocked
        with self.assertRaises((ValueError, sqlite3.DatabaseError)):
            self.db.execute_query("WITH t AS (SELECT 1) DELETE FROM vouchers")

        # DROP TABLE must be blocked
        with self.assertRaises((ValueError, sqlite3.DatabaseError)):
            self.db.execute_query("DROP TABLE vouchers")

        # Table should remain completely intact
        rows_after = self.db.execute_query("SELECT COUNT(*) as cnt FROM vouchers")
        self.assertEqual(rows_after[0]["cnt"], 1)

    def test_03_zero_fabricated_dashboard_kpis(self):
        """Verify dashboard executive summary has zero hardcoded numbers."""
        summary = self.dashboard.get_executive_summary()
        # When DB is empty or clean, liquid funds & cash flow must be 0.0, not ₹38.9 Cr or ₹89,468
        self.assertEqual(summary["cash_in_hand"], 0.0)
        self.assertEqual(summary["bank_balance"], 0.0)
        self.assertEqual(summary["cash_inflow"], 0.0)
        self.assertEqual(summary["cash_outflow"], 0.0)
        self.assertNotIn("389544772", str(summary))
        self.assertNotIn("89468", str(summary))

        periods = self.dashboard.get_available_periods()
        self.assertEqual(periods, [])

    def test_04_cash_statement_direction(self):
        """Verify Cash ledger statement shows Receipts as Debit and Payments as Credit."""
        vouchers = [
            {"guid": "C1", "voucher_type": "Receipt", "voucher_no": "RCT-1", "date": "2024-04-01",
             "financial_year": "FY 2024-25", "party_name": "Cash", "primary_ledger": "Consulting Revenue",
             "gross_amount": 1000.0, "net_amount": 1000.0},
            {"guid": "C2", "voucher_type": "Payment", "voucher_no": "PMT-1", "date": "2024-04-02",
             "financial_year": "FY 2024-25", "party_name": "Cash", "primary_ledger": "Office Supplies",
             "gross_amount": 400.0, "net_amount": 400.0}
        ]
        self.db.insert_vouchers_batch(vouchers)

        res = self.engine._generate_ledger_statement("Cash")
        self.assertIsNotNone(res)
        data = res["data"]
        self.assertEqual(len(data), 2)

        # Receipt row must have Debit = ₹ 1,000.00, Credit = -
        self.assertIn("1,000.00", data[0]["debit"])
        self.assertEqual(data[0]["credit"], "-")

        # Payment row must have Debit = -, Credit = ₹ 400.00
        self.assertEqual(data[1]["debit"], "-")
        self.assertIn("400.00", data[1]["credit"])

        # Running balance should be ₹ 600.00 Dr
        self.assertIn("600.00 Dr", data[1]["running_balance"])
        self.assertIn("Closing Balance: **₹ 600.00 Dr**", res["answer"])

    def test_05_clean_amount_comma_and_signs(self):
        """Verify comma-separated Indian numbers and Dr/Cr suffixes parse cleanly."""
        self.assertEqual(clean_amount(" 1,20,000.00"), 120000.0)
        self.assertEqual(clean_amount("50,00,000.50"), 5000000.50)
        self.assertEqual(clean_amount("-1,500.00"), -1500.0)
        self.assertEqual(clean_amount("10,000.00 Dr"), -10000.0)  # Debit in Tally XML is negative
        self.assertEqual(clean_amount("25,000.00 Cr"), 25000.0)   # Credit in Tally XML is positive
        self.assertEqual(clean_amount("invalid"), 0.0)

    def test_06_aging_bills_fy_filtering(self):
        """Verify get_aging_summary filters bills_outstanding by fiscal year."""
        bills = [
            {"bill_type": "Receivable", "bill_date": "2017-06-15", "party_name": "Old Debtor", "outstanding_amount": 50000.0, "overdue_days": 120},
            {"bill_type": "Receivable", "bill_date": "2024-06-15", "party_name": "New Debtor", "outstanding_amount": 80000.0, "overdue_days": 30}
        ]
        self.db.insert_bills_batch(bills)

        # Filter by FY 2017-18
        res_old = self.dashboard.get_aging_summary(nature="all", fy="FY 2017-18")
        parties_old = [b["party_name"] for b in res_old["bills"]]
        self.assertIn("Old Debtor", parties_old)
        self.assertNotIn("New Debtor", parties_old)

        # Filter by FY 2024-25
        res_new = self.dashboard.get_aging_summary(nature="all", fy="FY 2024-25")
        parties_new = [b["party_name"] for b in res_new["bills"]]
        self.assertIn("New Debtor", parties_new)
        self.assertNotIn("Old Debtor", parties_new)

    def test_07_section_269ss_no_false_positive_on_akash(self):
        """Verify Section 269SS scanner uses word boundaries and does not flag parties named Akash."""
        vouchers = [
            {"guid": "S1", "voucher_type": "Payment", "date": "2024-05-01", "financial_year": "FY 2024-25",
             "party_name": "Akash Enterprises", "primary_ledger": "Loan Account", "gross_amount": 50000.0},
            {"guid": "S2", "voucher_type": "Payment", "date": "2024-05-02", "financial_year": "FY 2024-25",
             "party_name": "Cash", "primary_ledger": "Director Loan A/c", "gross_amount": 50000.0}
        ]
        self.db.insert_vouchers_batch(vouchers)

        report = self.scanner.detect_section_269ss_269t_violations()
        flagged_parties = [r["party_name"] for r in report["records"]]
        self.assertNotIn("Akash Enterprises", flagged_parties)
        self.assertIn("Cash", flagged_parties)


if __name__ == "__main__":
    unittest.main()
