import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledgergpt.db import FinancialDB
from ledgergpt.dashboard_service import DashboardService
from ledgergpt.query_engine import QueryEngine
from ledgergpt.forensic import ForensicScanner

class TestAgingAndCfoMIS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = FinancialDB(":memory:")
        test_records = [
            {
                "guid": "v1", "voucher_type": "Purchase", "voucher_no": "101", "reference_no": "BILL-001",
                "date": "2026-06-01", "financial_year": "FY 2026-27", "month_year": "Jun 2026", "quarter": "Q1",
                "party_name": "Supplier A", "primary_ledger": "Raw Materials", "cost_centre": "Site Latehar",
                "net_amount": 100000.0, "tax_amount": 18000.0, "gross_amount": 118000.0,
                "narration": "Material supply", "day_of_week": "Monday", "is_weekend": 0, "is_round_sum": 0
            },
            {
                "guid": "v2", "voucher_type": "Payment", "voucher_no": "201", "reference_no": "PAY-001",
                "date": "2026-06-15", "financial_year": "FY 2026-27", "month_year": "Jun 2026", "quarter": "Q1",
                "party_name": "Cash", "primary_ledger": "Director Loan A/C", "cost_centre": "Corporate",
                "net_amount": 25000.0, "tax_amount": 0.0, "gross_amount": 25000.0,
                "narration": "Loan repaid in cash to director", "day_of_week": "Monday", "is_weekend": 0, "is_round_sum": 0
            }
        ]
        cls.db.insert_vouchers_batch(test_records)

        test_bills = [
            {
                "bill_type": "Payable", "bill_date": "2026-06-30", "bill_ref": "REF-101",
                "party_name": "Fuel Supplier", "outstanding_amount": 500000.0,
                "overdue_days": 110, "cost_centre": "Site Latehar"
            },
            {
                "bill_type": "Receivable", "bill_date": "2026-10-15", "bill_ref": "INV-201",
                "party_name": "Client Infra", "outstanding_amount": 300000.0,
                "overdue_days": 15, "cost_centre": "Corporate"
            }
        ]
        cls.db.insert_bills_batch(test_bills)
        cls.dash = DashboardService(db=cls.db)
        cls.engine = QueryEngine(db=cls.db)
        cls.scanner = ForensicScanner(db=cls.db)

    def test_cost_centres(self):
        ccs = self.dash.get_available_cost_centres()
        self.assertIn("Site Latehar", ccs)

    def test_aging_summary(self):
        res = self.dash.get_aging_summary()
        self.assertEqual(res["summary"]["payables"]["total"], 500000.0)
        self.assertEqual(res["summary"]["receivables"]["total"], 300000.0)
        self.assertEqual(res["summary"]["payables"]["bucket_90_plus"], 500000.0)
        self.assertEqual(res["summary"]["receivables"]["bucket_0_30"], 300000.0)

    def test_cfo_mis_pack(self):
        pack = self.dash.get_cfo_mis_pack()
        self.assertIn("report_title", pack)
        self.assertIn("executive_summary", pack)
        self.assertIn("aging_overview", pack)
        self.assertEqual(len(pack["critical_overdue_bills"]), 1)

    def test_sec_269ss_violation_detection(self):
        res = self.scanner.detect_section_269ss_269t_violations()
        self.assertEqual(res["total_flagged"], 1)
        self.assertIn("Section 269T", res["records"][0]["clause_violation"])

    def test_aging_query(self):
        res_cred = self.engine.process_query("Show creditors aging")
        self.assertIn("Debtor & Creditor Aging Analysis", res_cred["answer"])
        self.assertEqual(res_cred["row_count"], 1)

        res_all = self.engine.process_query("Show bills outstanding aging")
        self.assertEqual(res_all["row_count"], 2)

    def test_sec_269_query(self):
        res = self.engine.process_query("Scan Section 269SS and 269T violations")
        self.assertIn("Section 269SS / 269T Tax Audit Scan", res["answer"])
        self.assertEqual(res["row_count"], 1)

if __name__ == "__main__":
    unittest.main()
