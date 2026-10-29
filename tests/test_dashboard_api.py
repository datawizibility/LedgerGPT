"""
Unit tests for DashboardService and Web Dashboard API endpoints.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledgergpt.db import FinancialDB
from ledgergpt.dashboard_service import DashboardService
from ledgergpt.web.app import app

class TestDashboardService(unittest.TestCase):
    def setUp(self):
        self.db = FinancialDB(":memory:")
        self.service = DashboardService(db=self.db)
        
        # Insert sample vouchers
        vouchers = [
            {
                "voucher_type": "Sales", "voucher_no": "S01", "date": "2017-05-10",
                "party_name": "FICCI", "gross_amount": 1000000.0, "net_amount": 900000.0,
                "tax_amount": 100000.0, "cost_centre": "Event A", "narration": "Sales bill"
            },
            {
                "voucher_type": "Purchase", "voucher_no": "P01", "date": "2017-05-15",
                "party_name": "Bennett Coleman", "gross_amount": 600000.0, "net_amount": 550000.0,
                "tax_amount": 50000.0, "cost_centre": "Event A", "narration": "Media print"
            },
            {
                "voucher_type": "Debit Note", "voucher_no": "DN01", "date": "2017-06-01",
                "party_name": "Bennett Coleman", "gross_amount": 25000.0, "net_amount": 25000.0,
                "tax_amount": 0.0, "cost_centre": "Event A", "narration": "Shortage debit"
            }
        ]
        self.db.insert_vouchers_batch(vouchers)

    def test_executive_summary(self):
        summary = self.service.get_executive_summary()
        self.assertEqual(summary["total_vouchers"], 3)
        self.assertEqual(summary["sales_gross"], 1000000.0)
        self.assertEqual(summary["purchase_gross"], 600000.0)
        self.assertEqual(summary["gross_margin"], 400000.0)
        self.assertEqual(summary["gross_margin_pct"], 40.0)
        self.assertEqual(summary["debit_notes_gross"], 25000.0)

    def test_monthly_trend(self):
        trend = self.service.get_monthly_trend()
        self.assertIn("May 2017", trend["labels"])
        self.assertEqual(trend["sales"][0], 1000000.0)
        self.assertEqual(trend["purchases"][0], 600000.0)

    def test_rankings(self):
        rankings = self.service.get_rankings(top_n=5)
        self.assertEqual(len(rankings["top_debtors"]), 1)
        self.assertEqual(rankings["top_debtors"][0]["party_name"], "FICCI")
        self.assertEqual(len(rankings["top_creditors"]), 1)
        self.assertEqual(rankings["top_creditors"][0]["party_name"], "Bennett Coleman")
        self.assertEqual(len(rankings["top_cost_centres"]), 1)
        self.assertEqual(rankings["top_cost_centres"][0]["margin"], 400000.0)

    def test_vouchers_grid(self):
        grid = self.service.get_vouchers_grid(page=1, page_size=10)
        self.assertEqual(grid["total_rows"], 3)
        self.assertEqual(len(grid["items"]), 3)

class TestDashboardWebAPI(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()

    def test_dashboard_summary_api(self):
        res = self.app.get("/api/dashboard/summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("sales_gross", data)
        self.assertIn("purchase_gross", data)

    def test_dashboard_monthly_trend_api(self):
        res = self.app.get("/api/dashboard/monthly-trend")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("labels", data)
        self.assertIn("sales", data)

    def test_dashboard_rankings_api(self):
        res = self.app.get("/api/dashboard/rankings?top_n=5")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("top_debtors", data)
        self.assertIn("top_creditors", data)

    def test_dashboard_vouchers_grid_api(self):
        res = self.app.get("/api/dashboard/vouchers-grid?page=1&page_size=10")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("items", data)
        self.assertIn("total_rows", data)

if __name__ == "__main__":
    unittest.main()
