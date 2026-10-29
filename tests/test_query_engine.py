import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ledgergpt.db import FinancialDB
from ledgergpt.ingestor import DataIngestor
from ledgergpt.query_engine import QueryEngine
from ledgergpt.forensic import ForensicScanner

class TestLedgerGPTEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create in-memory test database
        cls.db = FinancialDB(":memory:")
        cls.ingestor = DataIngestor(db=cls.db)
        
        # Insert small verified test batch
        test_records = [
            {
                "guid": "g1", "voucher_type": "Sales", "voucher_no": "1", "reference_no": "R001",
                "date": "2017-05-10", "financial_year": "FY 2017-18", "month_year": "May 2017", "quarter": "Q1",
                "party_name": "Alpha Corp Ltd", "primary_ledger": "Advertising Services", "cost_centre": "Event 1",
                "net_amount": 100000.0, "tax_amount": 18000.0, "gross_amount": 118000.0,
                "narration": "Being event billing for May", "day_of_week": "Wednesday", "is_weekend": 0, "is_round_sum": 0
            },
            {
                "guid": "g2", "voucher_type": "Sales", "voucher_no": "2", "reference_no": "R002",
                "date": "2017-06-15", "financial_year": "FY 2017-18", "month_year": "Jun 2017", "quarter": "Q1",
                "party_name": "Beta Industries", "primary_ledger": "Print Media", "cost_centre": "Event 2",
                "net_amount": 50000.0, "tax_amount": 9000.0, "gross_amount": 59000.0,
                "narration": "Print media release advance", "day_of_week": "Thursday", "is_weekend": 0, "is_round_sum": 0
            },
            {
                "guid": "g3", "voucher_type": "Purchase", "voucher_no": "101", "reference_no": "P001",
                "date": "2017-05-20", "financial_year": "FY 2017-18", "month_year": "May 2017", "quarter": "Q1",
                "party_name": "Gamma Suppliers", "primary_ledger": "Printing Charges", "cost_centre": "Event 1",
                "net_amount": 60000.0, "tax_amount": 10800.0, "gross_amount": 70800.0,
                "narration": "Printing leaflets for project", "day_of_week": "Saturday", "is_weekend": 1, "is_round_sum": 0
            },
            {
                "guid": "g4", "voucher_type": "Debit Note", "voucher_no": "D1", "reference_no": "DR01",
                "date": "2017-07-01", "financial_year": "FY 2017-18", "month_year": "Jul 2017", "quarter": "Q2",
                "party_name": "Gamma Suppliers", "primary_ledger": "Printing Charges", "cost_centre": "General",
                "net_amount": 5000.0, "tax_amount": 0.0, "gross_amount": 5000.0,
                "narration": "Cancellation charge deducted", "day_of_week": "Saturday", "is_weekend": 1, "is_round_sum": 0
            },
            {
                "guid": "g5", "voucher_type": "Payment", "voucher_no": "P501", "reference_no": "PAY01",
                "date": "2017-07-15", "financial_year": "FY 2017-18", "month_year": "Jul 2017", "quarter": "Q2",
                "party_name": "Gamma Suppliers", "primary_ledger": "Bank of Baroda", "cost_centre": "General",
                "net_amount": 65800.0, "tax_amount": 0.0, "gross_amount": 65800.0,
                "narration": "Final payment against printing bills", "day_of_week": "Saturday", "is_weekend": 1, "is_round_sum": 0
            },
            {
                "guid": "g6", "voucher_type": "Receipt", "voucher_no": "R101", "reference_no": "REC01",
                "date": "2017-07-20", "financial_year": "FY 2017-18", "month_year": "Jul 2017", "quarter": "Q2",
                "party_name": "Alpha Corp Ltd", "primary_ledger": "Bank of Baroda", "cost_centre": "General",
                "net_amount": 118000.0, "tax_amount": 0.0, "gross_amount": 118000.0,
                "narration": "Received on account via RTGS", "day_of_week": "Thursday", "is_weekend": 0, "is_round_sum": 0
            }
        ]
        cls.db.insert_vouchers_batch(test_records)
        cls.engine = QueryEngine(db=cls.db)
        cls.scanner = ForensicScanner(db=cls.db)

    def test_total_sales_query(self):
        res = self.engine.process_query("Total sales in FY 2017-18")
        self.assertIn("1.77 L", res["answer"])
        self.assertEqual(res["row_count"], 2)

    def test_top_clients_query(self):
        res = self.engine.process_query("Top 5 clients")
        self.assertEqual(len(res["data"]), 2)
        self.assertEqual(res["data"][0]["party_name"], "Alpha Corp Ltd")

    def test_debit_notes_query(self):
        res = self.engine.process_query("Show all Debit Notes")
        self.assertEqual(res["row_count"], 1)
        self.assertIn("5,000.00", res["answer"])

    def test_party_ledger_statement_query(self):
        res = self.engine.process_query("share Gamma Suppliers ledger")
        self.assertIn("Ledger Account Statement: Gamma Suppliers", res["answer"])
        self.assertEqual(res["row_count"], 3)
        self.assertEqual(res["columns"], ["date", "voucher_type", "voucher_no", "reference_no", "particulars", "debit", "credit", "running_balance", "narration"])

    def test_cash_inflow_outflow_query(self):
        res = self.engine.process_query("Show cash inflow and outflow")
        self.assertIn("Cash & Bank Liquidity Analysis", res["answer"])
        self.assertIn("1.18 L", res["answer"])
        self.assertIn("65,800.00", res["answer"])

    def test_forensic_narration_search(self):
        res = self.scanner.scan_suspicious_narrations(keywords=["cancellation"])
        self.assertEqual(res["total_flagged"], 1)
        self.assertIn("Cancellation charge", res["records"][0]["narration"])

    def test_forensic_weekend_entries(self):
        res = self.scanner.detect_weekend_entries()
        self.assertEqual(res["total_flagged"], 3)

if __name__ == "__main__":
    unittest.main()
