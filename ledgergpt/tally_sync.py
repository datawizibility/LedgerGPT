"""
Tally Prime Live XML Sync Engine for LedgerGPT.
Connects directly to Tally Prime on port 9000 (or custom URL),
detects active companies, and extracts vouchers into the local database.
"""

import os
import re
import uuid
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from ledgergpt.config import TALLY_HOST, TALLY_PORT
from ledgergpt.db import FinancialDB
from ledgergpt.formatters import parse_date, get_financial_year, get_financial_quarter


class TallySyncEngine:
    def __init__(self, host=None, port=None, db=None):
        self.host = host or TALLY_HOST
        self.port = port or TALLY_PORT
        self.url = f"http://{self.host}:{self.port}"
        self.db = db or FinancialDB()

    def check_connection(self):
        """Pings Tally Prime HTTP interface to check availability."""
        test_xml = """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>$$SysName:TallyVersion</ID>
  </HEADER>
  <BODY><DESC></DESC></BODY>
</ENVELOPE>"""
        try:
            req = urllib.request.Request(
                self.url,
                data=test_xml.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
            )
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    return True, "Connected to Tally Prime"
        except Exception as e:
            return False, f"Could not reach Tally Prime on {self.url}: {str(e)}"
        return False, f"Unexpected response from {self.url}"

    def get_open_companies(self):
        """Fetches list of currently loaded companies in Tally Prime."""
        xml_req = """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>List of Companies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="List of Companies" ISMODIFY="No">
            <TYPE>Company</TYPE>
            <FETCH>Name, StartingFrom, Guid</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""
        try:
            req = urllib.request.Request(
                self.url,
                data=xml_req.encode("utf-8"),
                headers={"Content-Type": "text/xml; charset=utf-8"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw_bytes = resp.read()
                # Tally can respond in UTF-16LE or UTF-8
                if len(raw_bytes) >= 4 and raw_bytes[1] == 0 and raw_bytes[3] == 0:
                    text = raw_bytes.decode("utf-16le", errors="ignore")
                else:
                    text = raw_bytes.decode("utf-8", errors="ignore")
                
                # Cleanup XML headers if needed
                text = re.sub(r"^[^<]+", "", text)
                root = ET.fromstring(text)
                
                companies = []
                for comp in root.findall(".//COMPANY"):
                    name_tag = comp.find("NAME") or comp.get("NAME")
                    name = comp.get("NAME") or (name_tag.text if name_tag is not None else "")
                    if name and name not in companies:
                        companies.append(name.strip())
                return companies
        except Exception as e:
            print(f"[TALLY ERROR] Failed to fetch companies: {e}")
            return []

    def fetch_vouchers(self, company_name=None):
        """Fetches all vouchers for the specified company (or default open company)."""
        static_var = ""
        if company_name:
            static_var = f"<SVCURRENTCOMPANY>{company_name}</SVCURRENTCOMPANY>"

        xml_req = f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>LedgerGPTVouchers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        {static_var}
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="LedgerGPTVouchers" ISMODIFY="No">
            <TYPE>Voucher</TYPE>
            <FETCH>Date, VoucherTypeName, VoucherNumber, Reference, PartyLedgerName, Narration, Guid, AllLedgerEntries.List, AllInventoryEntries.List</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>"""

        req = urllib.request.Request(
            self.url,
            data=xml_req.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
        )
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_bytes = resp.read()
            if len(raw_bytes) >= 4 and raw_bytes[1] == 0 and raw_bytes[3] == 0:
                text = raw_bytes.decode("utf-16le", errors="ignore")
            else:
                text = raw_bytes.decode("utf-8", errors="ignore")
            
            text = re.sub(r"^[^<]+", "", text)
            root = ET.fromstring(text)

        parsed_records = []
        for vch in root.findall(".//VOUCHER"):
            # Date
            dt_raw = (vch.findtext("DATE") or "").strip()
            # Tally dates are typically YYYYMMDD
            if len(dt_raw) == 8 and dt_raw.isdigit():
                try:
                    dt_obj = datetime.strptime(dt_raw, "%Y%m%d")
                except ValueError:
                    dt_obj = datetime.now()
            else:
                dt_obj = parse_date(dt_raw) or datetime.now()

            dt_str = dt_obj.strftime("%Y-%m-%d")
            fy_str = get_financial_year(dt_obj)
            my_str = dt_obj.strftime("%b %Y")
            qtr_str = get_financial_quarter(dt_obj)

            vtype = (vch.findtext("VOUCHERTYPENAME") or "Voucher").strip()
            vno = (vch.findtext("VOUCHERNUMBER") or "").strip()
            ref_no = (vch.findtext("REFERENCE") or "").strip()
            party = (vch.findtext("PARTYLEDGERNAME") or "").strip()
            narr = (vch.findtext("NARRATION") or "").replace("\n", " ").strip()
            vguid = (vch.findtext("GUID") or str(uuid.uuid4())).strip()

            # Ledger & Amount parsing
            ledgers = []
            gross_amt = 0.0
            net_amt = 0.0
            tax_amt = 0.0
            primary_ledger = ""
            cost_centre = "General / Untagged"

            for lentry in vch.findall(".//ALLLEDGERENTRIES.LIST") + vch.findall(".//LEDGERENTRIES.LIST"):
                lname = (lentry.findtext("LEDGERNAME") or "").strip()
                amt_str = (lentry.findtext("AMOUNT") or "0").strip()
                try:
                    amt_val = float(amt_str)
                except ValueError:
                    amt_val = 0.0

                ledgers.append((lname, amt_val))

                # Check Cost Centres
                cc_tag = lentry.find(".//CATEGORYALLOCATIONS.LIST//COSTCENTREALLOCATIONS.LIST//NAME")
                if cc_tag is not None and cc_tag.text:
                    cost_centre = cc_tag.text.strip()

                # Categorize Amounts
                l_lower = lname.lower()
                if any(t in l_lower for t in ["gst", "tax", "vat", "service tax", "cess", "cst"]):
                    tax_amt += abs(amt_val)
                elif party and lname == party:
                    # In Tally, party line amount represents gross transaction value
                    gross_amt = max(gross_amt, abs(amt_val))
                else:
                    if not primary_ledger and not any(t in l_lower for t in ["gst", "tax", "vat", "round"]):
                        primary_ledger = lname
                    net_amt += abs(amt_val)

            if not party and ledgers:
                party = ledgers[0][0]
            if not primary_ledger:
                primary_ledger = ledgers[1][0] if len(ledgers) > 1 else "General Ledger"
            if gross_amt == 0.0:
                gross_amt = net_amt if net_amt > 0 else (net_amt + tax_amt)
            if net_amt == 0.0:
                net_amt = max(0.0, gross_amt - tax_amt)

            # Weekend & Round-sum check
            dow = dt_obj.strftime("%A")
            is_weekend = 1 if dow in ("Saturday", "Sunday") else 0
            is_round = 1 if (gross_amt >= 10000 and gross_amt % 10000 == 0) else 0

            parsed_records.append({
                "guid": vguid,
                "voucher_type": vtype,
                "voucher_no": vno,
                "reference_no": ref_no,
                "date": dt_str,
                "financial_year": fy_str,
                "month_year": my_str,
                "quarter": qtr_str,
                "party_name": party or "Sundry Party",
                "primary_ledger": primary_ledger,
                "cost_centre": cost_centre,
                "net_amount": round(net_amt, 2),
                "tax_amount": round(tax_amt, 2),
                "gross_amount": round(gross_amt, 2),
                "narration": narr,
                "day_of_week": dow,
                "is_weekend": is_weekend,
                "is_round_sum": is_round,
            })

        return parsed_records

    def sync(self, company_name=None, clear_existing=False):
        """
        Executes full sync pipeline:
        1. Checks Tally connection
        2. Detects company
        3. Extracts vouchers
        4. Ingests into DB and updates full-text index
        """
        ok, msg = self.check_connection()
        if not ok:
            return {"success": False, "error": msg}

        open_companies = self.get_open_companies()
        target_company = company_name or (open_companies[0] if open_companies else None)

        if not target_company:
            return {"success": False, "error": "Tally Prime is open, but no active company was detected. Please load a company in Tally."}

        vouchers = self.fetch_vouchers(company_name=target_company)
        if not vouchers:
            return {"success": False, "error": f"Connected to '{target_company}', but zero vouchers were returned."}

        if clear_existing:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM vouchers")
                conn.commit()

        count = self.db.insert_vouchers_batch(vouchers)
        self.db.rebuild_fts()
        kpis = self.db.get_kpis()

        return {
            "success": True,
            "company_name": target_company,
            "vouchers_synced": count,
            "kpis": kpis,
            "message": f"Successfully synced {count:,} vouchers from '{target_company}'."
        }
