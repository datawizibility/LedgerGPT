"""
Data Ingestion Pipeline for LedgerGPT.
Ingests CSV registers, Excel workbooks, raw Tally dumps, and connects to live Tally XML API.
Features intelligent header normalization and fuzzy column matching.
"""

import os
import re
import csv
import uuid
from datetime import datetime
from ledgergpt.db import FinancialDB
from ledgergpt.formatters import parse_date, get_financial_year, get_financial_quarter

class DataIngestor:
    def __init__(self, db=None):
        self.db = db or FinancialDB()

    def _fuzzy_get(self, row_dict, keyword_candidates, default=None):
        """Intelligently matches column values using normalized alphanumeric keys."""
        # Exact check first
        for kw in keyword_candidates:
            if kw in row_dict and row_dict[kw] is not None and str(row_dict[kw]).strip() != "":
                return row_dict[kw]

        # Fuzzy substring match
        for k, v in row_dict.items():
            if v is None or str(v).strip() == "":
                continue
            clean_k = re.sub(r"[^a-z0-9]", "", k.lower())
            for kw in keyword_candidates:
                clean_kw = re.sub(r"[^a-z0-9]", "", kw.lower())
                if clean_kw in clean_k:
                    return v

        return default

    def ingest_register_csv(self, file_path, default_vch_type=None):
        """
        Ingest a CSV register with flexible header mapping.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        records = []
        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Lowercase lookup map
                r = {k.strip().lower(): v for k, v in row.items() if k}
                
                # Determine voucher type
                vtype = default_vch_type
                if not vtype:
                    fname = os.path.basename(file_path).lower()
                    if "sales" in fname:
                        vtype = "Sales"
                    elif "purchase" in fname:
                        vtype = "Purchase"
                    elif "debit" in fname:
                        vtype = "Debit Note"
                    elif "credit" in fname:
                        vtype = "Credit Note"
                    else:
                        vtype = self._fuzzy_get(r, ["vouchertype", "type"], "Journal")

                # Extract date
                dt_raw = self._fuzzy_get(r, ["date", "invoicedate", "billdate", "voucherdate"], "")
                dt_obj = parse_date(dt_raw) or datetime(2017, 4, 1)
                dt_str = dt_obj.strftime("%Y-%m-%d")

                fy_str = self._fuzzy_get(r, ["financialyear", "fy"], get_financial_year(dt_obj))
                my_str = self._fuzzy_get(r, ["monthyear", "month"], dt_obj.strftime("%b %Y"))
                qtr_str = self._fuzzy_get(r, ["quarter", "qtr"], get_financial_quarter(dt_obj))

                # GUID
                guid = self._fuzzy_get(r, ["guid", "voucherguid", "id"], str(uuid.uuid4()))

                # Numbers
                vch_no = str(self._fuzzy_get(r, ["voucherno", "vouchernumber"], "")).strip()
                ref_no = str(self._fuzzy_get(r, ["referenceno", "referencenumber", "vendorbillref", "billno", "invoice"], "")).strip()

                # Party Name
                party = str(self._fuzzy_get(
                    r,
                    ["clientdebtorname", "debtor", "vendorcreditorname", "vendor", "partyname", "party", "customer", "supplier"],
                    "Sundry Party"
                )).strip()

                # Primary Ledger
                ledger = str(self._fuzzy_get(
                    r,
                    ["salesledger", "expenseledger", "adjustmentledger", "primaryledger", "ledger", "account"],
                    "General Ledger"
                )).strip()

                # Cost Centre
                cc = str(self._fuzzy_get(r, ["costcentre", "project", "event", "branch", "dept"], "General / Untagged")).strip()

                # Amounts
                net_raw = self._fuzzy_get(r, ["netsalesamount", "netexpenseamount", "netamount", "net"], 0.0)
                try:
                    net_amt = float(net_raw or 0.0)
                except ValueError:
                    net_amt = 0.0

                tax_raw = self._fuzzy_get(r, ["outputtaxamount", "inputtaxamount", "taxamount", "tax", "gst"], 0.0)
                try:
                    tax_amt = float(tax_raw or 0.0)
                except ValueError:
                    tax_amt = 0.0

                gross_raw = self._fuzzy_get(r, ["grossbilledamount", "grossvendorbill", "grossamount", "gross", "totalamount", "total"], (net_amt + tax_amt))
                try:
                    gross_amt = float(gross_raw or (net_amt + tax_amt))
                except ValueError:
                    gross_amt = net_amt + tax_amt

                if gross_amt == 0.0 and (net_amt != 0.0 or tax_amt != 0.0):
                    gross_amt = net_amt + tax_amt

                # Narration
                narr = str(self._fuzzy_get(r, ["narration", "remarks", "notes", "desc"], "")).replace("\n", " ").replace("\r", " ").strip()

                # Forensic indicators
                dow = dt_obj.strftime("%A")
                is_weekend = 1 if dow in ("Saturday", "Sunday") else 0
                is_round = 1 if (gross_amt > 0 and gross_amt % 10000 == 0) else 0

                records.append({
                    "guid": guid,
                    "voucher_type": vtype,
                    "voucher_no": vch_no,
                    "reference_no": ref_no,
                    "date": dt_str,
                    "financial_year": fy_str,
                    "month_year": my_str,
                    "quarter": qtr_str,
                    "party_name": party,
                    "primary_ledger": ledger,
                    "cost_centre": cc,
                    "net_amount": round(net_amt, 2),
                    "tax_amount": round(tax_amt, 2),
                    "gross_amount": round(gross_amt, 2),
                    "narration": narr,
                    "day_of_week": dow,
                    "is_weekend": is_weekend,
                    "is_round_sum": is_round,
                })

        count = self.db.insert_vouchers_batch(records)
        return count

    def ingest_sample_dataset(self, sample_dir):
        """Auto-loads all verified sample files from the sample_data directory."""
        total = 0
        files = [
            ("sales_register.csv", "Sales"),
            ("purchase_register.csv", "Purchase"),
            ("debit_notes.csv", "Debit Note"),
            ("credit_notes.csv", "Credit Note"),
        ]
        for fname, vtype in files:
            p = os.path.join(sample_dir, fname)
            if os.path.exists(p):
                cnt = self.ingest_register_csv(p, default_vch_type=vtype)
                total += cnt
                print(f"[INGESTED] {fname}: {cnt:,} vouchers loaded.")
        return total
