"""
Forensic Audit & Anomaly Detection Engine for LedgerGPT.
Detects red flags, suspicious narrations, weekend entries, duplicate bills, and Benford's Law deviations.
"""

import math
from collections import Counter
from ledgergpt.db import FinancialDB
from ledgergpt.formatters import format_inr

class ForensicScanner:
    def __init__(self, db=None):
        self.db = db or FinancialDB()

    def scan_suspicious_narrations(self, keywords=None, limit=100):
        """Scan narrations for red-flag forensic audit keywords."""
        if not keywords:
            keywords = [
                "cancellation", "cancel", "settlement", "personal", "difference",
                "dispute", "cash", "round off", "rebate", "adjusted", "penalty",
                "director", "advance", "tcs", "reversal"
            ]
        
        # Use FTS5 for instant sub-millisecond retrieval
        fts_query = " OR ".join(keywords)
        sql = """
        SELECT v.id, v.date, v.voucher_type, v.voucher_no, v.reference_no,
               v.party_name, v.gross_amount, v.narration
        FROM vouchers v
        JOIN vouchers_fts f ON v.id = f.rowid
        WHERE vouchers_fts MATCH ?
        ORDER BY v.date DESC
        LIMIT ?
        """
        rows = self.db.execute_query(sql, (fts_query, limit))
        return {
            "scanner": "Suspicious Narration Detector",
            "keywords_scanned": keywords,
            "total_flagged": len(rows),
            "records": rows
        }

    def detect_round_sum_transactions(self, min_amount=50000, limit=100):
        """Flags transactions that are exact round multiples (e.g. ₹50k, ₹1L, ₹5L)."""
        sql = """
        SELECT id, date, voucher_type, voucher_no, reference_no, party_name,
               primary_ledger, gross_amount, narration
        FROM vouchers
        WHERE gross_amount >= ?
          AND is_round_sum = 1
        ORDER BY gross_amount DESC
        LIMIT ?
        """
        rows = self.db.execute_query(sql, (min_amount, limit))
        return {
            "scanner": "Round-Sum Transaction Detector",
            "criteria": f"Gross Amount >= {format_inr(min_amount)} and exact multiple of ₹10,000",
            "total_flagged": len(rows),
            "records": rows
        }

    def detect_weekend_entries(self, limit=100):
        """Flags vouchers entered or dated on Saturday or Sunday."""
        sql = """
        SELECT id, date, day_of_week, voucher_type, voucher_no, party_name,
               primary_ledger, gross_amount, narration
        FROM vouchers
        WHERE is_weekend = 1
        ORDER BY date DESC
        LIMIT ?
        """
        rows = self.db.execute_query(sql, (limit,))
        return {
            "scanner": "Weekend Voucher Detector",
            "criteria": "Vouchers dated on Saturday or Sunday",
            "total_flagged": len(rows),
            "records": rows
        }

    def detect_duplicate_bills(self, limit=100):
        """Flags potential duplicate bills by party_name and reference_no."""
        sql = """
        SELECT party_name, reference_no, COUNT(*) as duplicate_count,
               SUM(gross_amount) as total_amount,
               GROUP_CONCAT(voucher_no, ', ') as voucher_numbers,
               GROUP_CONCAT(date, ', ') as dates
        FROM vouchers
        WHERE reference_no IS NOT NULL AND TRIM(reference_no) != ''
        GROUP BY party_name, reference_no
        HAVING COUNT(*) > 1
        ORDER BY duplicate_count DESC, total_amount DESC
        LIMIT ?
        """
        rows = self.db.execute_query(sql, (limit,))
        return {
            "scanner": "Duplicate Bill / Reference Detector",
            "criteria": "Same Party Name + Same Bill/Reference Number appearing multiple times",
            "total_flagged": len(rows),
            "records": rows
        }

    def analyze_benford_law(self, voucher_type=None):
        """
        Performs Benford's Law first-digit analysis on gross amounts.
        Theoretical: P(d) = log10(1 + 1/d)
        """
        params = ()
        filter_clause = "WHERE gross_amount >= 10"
        if voucher_type:
            filter_clause += " AND LOWER(voucher_type) = LOWER(?)"
            params = (voucher_type,)

        sql = f"SELECT gross_amount FROM vouchers {filter_clause}"
        rows = self.db.execute_query(sql, params)

        first_digits = []
        for r in rows:
            amt = r["gross_amount"]
            if amt and amt >= 10:
                s = str(amt).replace(".", "").lstrip("0")
                if s:
                    first_digits.append(int(s[0]))

        n = len(first_digits)
        if n == 0:
            return {"error": "Insufficient data for Benford's Law analysis"}

        counts = Counter(first_digits)
        distribution = []
        max_deviation = 0.0

        for d in range(1, 10):
            observed_cnt = counts.get(d, 0)
            observed_pct = round((observed_cnt / n) * 100, 2)
            expected_pct = round(math.log10(1 + 1 / d) * 100, 2)
            diff = round(abs(observed_pct - expected_pct), 2)
            if diff > max_deviation:
                max_deviation = diff
            distribution.append({
                "digit": d,
                "observed_count": observed_cnt,
                "observed_pct": observed_pct,
                "expected_pct": expected_pct,
                "deviation_pct": diff,
                "anomaly_flag": "HIGH ANOMALY" if diff > 5.0 else ("MODERATE" if diff > 3.0 else "NORMAL")
            })

        return {
            "scanner": "Benford's Law First-Digit Conformity",
            "sample_size": n,
            "max_deviation_pct": max_deviation,
            "overall_conformity": "Low Conformity (Review Advised)" if max_deviation > 7.0 else "Normal Statistical Distribution",
            "digits": distribution
        }

    def run_full_forensic_suite(self):
        """Runs the complete suite and aggregates findings into an executive report."""
        suspicious = self.scan_suspicious_narrations(limit=25)
        round_sums = self.detect_round_sum_transactions(min_amount=100000, limit=25)
        weekends = self.detect_weekend_entries(limit=25)
        duplicates = self.detect_duplicate_bills(limit=25)
        benford = self.analyze_benford_law()

        return {
            "summary": {
                "suspicious_narrations_count": suspicious["total_flagged"],
                "round_sum_vouchers_count": round_sums["total_flagged"],
                "weekend_vouchers_count": weekends["total_flagged"],
                "duplicate_bill_groups": duplicates["total_flagged"],
                "benford_conformity": benford.get("overall_conformity", "N/A"),
            },
            "suspicious_narrations": suspicious,
            "round_sum_transactions": round_sums,
            "weekend_entries": weekends,
            "duplicate_bills": duplicates,
            "benford_analysis": benford,
        }
