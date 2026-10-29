import unittest
import json
import sys
import os

sys.path.insert(0, r"D:\AAAA_MYPROJECT\LedgerGPT")

from ledgergpt.web.app import app

class TestWebAPI(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_index_route(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"LedgerGPT", res.data)
        self.assertIn(b"Total Audited Vouchers", res.data)

    def test_kpis_api(self):
        res = self.client.get("/api/kpis")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertGreater(data["total_vouchers"], 0)
        self.assertIn("sales_formatted", data)

    def test_chat_api(self):
        res = self.client.post("/api/chat", json={"query": "Top 5 clients"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("Top 5 Clients", data["answer"])
        self.assertGreater(len(data["data"]), 0)

    def test_forensic_api(self):
        res = self.client.get("/api/forensic")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("summary", data)
        self.assertIn("benford_analysis", data)

if __name__ == "__main__":
    unittest.main()
