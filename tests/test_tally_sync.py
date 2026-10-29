"""
Unit tests for TallySyncEngine.
"""

import unittest
from unittest.mock import patch, MagicMock
from ledgergpt.db import FinancialDB
from ledgergpt.tally_sync import TallySyncEngine

class TestTallySync(unittest.TestCase):
    def setUp(self):
        self.db = FinancialDB(":memory:")
        self.sync_engine = TallySyncEngine(db=self.db)

    def test_check_connection_offline(self):
        # Point to an unused port
        engine = TallySyncEngine(port=59999, db=self.db)
        ok, msg = engine.check_connection()
        self.assertFalse(ok)
        self.assertIn("Could not reach Tally Prime", msg)

    @patch("urllib.request.urlopen")
    def test_get_open_companies_mock(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"""<ENVELOPE>
  <BODY>
    <DATA>
      <COLLECTION>
        <COMPANY NAME="Bharat Vanijya Eastern Pvt Ltd"></COMPANY>
        <COMPANY NAME="Genesis Advertising Pvt Ltd"></COMPANY>
      </COLLECTION>
    </DATA>
  </BODY>
</ENVELOPE>"""
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        comps = self.sync_engine.get_open_companies()
        self.assertEqual(len(comps), 2)
        self.assertIn("Bharat Vanijya Eastern Pvt Ltd", comps)
        self.assertIn("Genesis Advertising Pvt Ltd", comps)

if __name__ == "__main__":
    unittest.main()
