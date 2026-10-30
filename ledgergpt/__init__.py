"""
LedgerGPT — Enterprise Conversational AI & Deterministic Query Engine for ERP & Tally Prime.
Zero-Hallucination | Audit-First | Institutional Financial Intelligence.
"""

__version__ = "1.4.0"
__author__ = "Amit Rathi (Datawizibility)"
__license__ = "MIT"

from ledgergpt.db import FinancialDB
from ledgergpt.query_engine import QueryEngine
from ledgergpt.ingestor import DataIngestor
from ledgergpt.forensic import ForensicScanner

__all__ = ["FinancialDB", "QueryEngine", "DataIngestor", "ForensicScanner"]
