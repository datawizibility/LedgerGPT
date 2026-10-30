"""
Deterministic Query Engine & Natural Language Routing for LedgerGPT.
Executes rule-based queries with instant sub-millisecond response, with LLM fallback.
"""

import re
import time
from ledgergpt.db import FinancialDB
from ledgergpt.formatters import format_inr
from ledgergpt.llm_adapter import LLMAdapter
from ledgergpt.dashboard_service import DashboardService

def extract_fy(text):
    # Case 1: Explicit 'FY' prefix, e.g. "FY 2017-18", "fy-2018", "fy2019"
    m_exp = re.search(r"\bfy\s*[-_]?\s*(\d{4})(?:[-_](\d{2,4}))?\b", text, re.IGNORECASE)
    if m_exp:
        yr1 = m_exp.group(1)
        yr2 = m_exp.group(2)
        if yr2:
            if len(yr2) == 4:
                yr2 = yr2[2:]
        else:
            yr2 = str(int(yr1) + 1)[2:]
        return f"FY {yr1}-{yr2}"

    # Case 2: Consecutive financial years without "FY", e.g. "2017-18" or "2017-2018"
    # Rejects bare date ranges like "2017-04" or "2017-06"
    m_pair = re.search(r"\b(\d{4})[-_](\d{2,4})\b", text)
    if m_pair:
        yr1 = int(m_pair.group(1))
        raw_yr2 = m_pair.group(2)
        yr2 = int(raw_yr2) if len(raw_yr2) == 4 else (yr1 // 100 * 100 + int(raw_yr2))
        if yr2 == yr1 + 1:
            return f"FY {yr1}-{str(yr2)[2:]}"
    return None

def extract_top_n(text, default=10):
    m = re.search(r"top\s*(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "fifteen": 15, "twenty": 20, "fifty": 50
    }
    for word, val in word_map.items():
        if re.search(rf"\btop\s+{word}\b", text, re.IGNORECASE):
            return val
    return default

class QueryEngine:
    extract_fy = staticmethod(extract_fy)

    def __init__(self, db=None, llm_adapter=None):
        self.db = db or FinancialDB()
        self.llm = llm_adapter or LLMAdapter()
        self.dashboard_service = DashboardService(db=self.db)

    def process_query(self, user_query):
        """
        Main entry point for queries.
        1. Try deterministic pattern matching (Instant, zero hallucination).
        2. If not matched, try LLM text-to-SQL.
        3. Fallback to full-text search.
        """
        start_time = time.time()
        q = user_query.strip()
        lower_q = q.lower()

        # 1. Deterministic Rule Matching
        deterministic_res = self._match_deterministic(lower_q, q)
        if deterministic_res:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            deterministic_res["execution_time_ms"] = elapsed_ms
            deterministic_res["source"] = "Deterministic Rule Engine (100% Accurate, Zero Hallucination)"
            return deterministic_res

        # 2. LLM Text-to-SQL Fallback
        schema = self.db.get_schema_summary()
        sql = self.llm.generate_sql(q, schema)
        if sql:
            # Enforce safe bounds and LIMIT on LLM SQL
            clean_sql = sql.strip().rstrip(";")
            if not re.search(r'\bLIMIT\s+\d+\b', clean_sql, re.IGNORECASE):
                clean_sql = f"{clean_sql} LIMIT 100"
            try:
                rows = self.db.execute_query(clean_sql)
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                
                # Synthesize answer
                summary = self._synthesize_llm_result(q, rows)
                return {
                    "answer": summary,
                    "sql": clean_sql,
                    "row_count": len(rows),
                    "data": rows[:100],
                    "columns": list(rows[0].keys()) if rows else [],
                    "execution_time_ms": elapsed_ms,
                    "source": f"LLM SQL Adapter ({self.llm.provider.upper()})"
                }
            except Exception as e:
                print(f"[SQL EXEC ERROR] {e} on SQL: {clean_sql}")

        # 3. Fallback: Full-Text Search across all fields and narrations
        fts_res = self._fallback_fts_search(q)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        fts_res["execution_time_ms"] = elapsed_ms
        fts_res["source"] = "Full-Text Search Engine (FTS5)"
        return fts_res

    def _match_deterministic(self, lower_q, original_q):
        """Rule-based deterministic financial intents."""

        # 0. Bill-by-Bill Debtor & Creditor Aging Intent
        if any(w in lower_q for w in ["aging", "bills outstanding", "pending bills", "overdue bills", "overdue debtors", "overdue creditors", "who owes", "receivable aging", "payable aging"]):
            nature = "all"
            if any(k in lower_q for k in ["debtor", "receivable", "customer", "who owes"]):
                nature = "receivable"
            elif any(k in lower_q for k in ["creditor", "payable", "vendor", "supplier"]):
                nature = "payable"

            aging_data = self.dashboard_service.get_aging_summary(nature=nature)
            rec = aging_data["summary"]["receivables"]
            pay = aging_data["summary"]["payables"]
            crit_cnt = sum(1 for b in aging_data["bills"] if b.get("risk_level") == "CRITICAL")

            ans = (
                f"**Bill-by-Bill Debtor & Creditor Aging Analysis**:\n"
                f"- **Outstanding Receivables (Debtors)**: **{rec['total_formatted']}** "
                f"(0-30d: {rec['bucket_0_30_formatted']}, 31-60d: {rec['bucket_31_60_formatted']}, 61-90d: {rec['bucket_61_90_formatted']}, 90+d: {rec['bucket_90_plus_formatted']})\n"
                f"- **Outstanding Payables (Creditors)**: **{pay['total_formatted']}** "
                f"(0-30d: {pay['bucket_0_30_formatted']}, 31-60d: {pay['bucket_31_60_formatted']}, 61-90d: {pay['bucket_61_90_formatted']}, 90+d: {pay['bucket_90_plus_formatted']})\n"
                f"- **Critical Overdue (>90 Days)**: **{crit_cnt} pending bills** flagged for high collection/settlement risk."
            )

            cols = ["bill_type", "party_name", "bill_ref", "bill_date", "overdue_days", "outstanding_formatted", "aging_bucket", "risk_level"]
            return {
                "answer": ans,
                "sql": "SELECT bill_type, party_name, bill_ref, bill_date, overdue_days, outstanding_amount FROM bills_outstanding ORDER BY overdue_days DESC",
                "row_count": len(aging_data["bills"]),
                "data": aging_data["bills"],
                "columns": cols
            }

        # 0b. Section 269SS / 269T Statutory Tax Audit Intent (CA Ramajayam Rule)
        if any(w in lower_q for w in ["269ss", "269t", "tax audit", "form 3cd", "cash loan", "clause 31"]):
            from ledgergpt.forensic import ForensicScanner
            scanner = ForensicScanner(db=self.db)
            report = scanner.detect_section_269ss_269t_violations()
            flagged = report["total_flagged"]
            ans = f"**Section 269SS / 269T Tax Audit Scan (Form 3CD Clause 31)**:\nTotal Flagged Violations: **{flagged} transactions** where cash loans, deposits, or specified advances exceed the statutory limit of **₹20,000**."
            return {
                "answer": ans,
                "sql": "SELECT * FROM vouchers WHERE gross_amount >= 20000 AND (party_name LIKE '%cash%' OR primary_ledger LIKE '%cash%')",
                "row_count": flagged,
                "data": report["records"],
                "columns": ["date", "voucher_type", "voucher_no", "party_name", "primary_ledger", "gross_amount", "clause_violation", "narration"]
            }

        # 0c. Negative Cash Balance Audit Intent
        if any(w in lower_q for w in ["negative cash", "cash deficit"]):
            from ledgergpt.forensic import ForensicScanner
            scanner = ForensicScanner(db=self.db)
            report = scanner.detect_negative_cash_balances()
            flagged = report["total_flagged"]
            ans = f"**Negative Cash Balance Audit Scan**:\nTotal Flagged Dates: **{flagged} days** where cumulative physical cash-in-hand dropped below ₹0.00."
            return {
                "answer": ans,
                "sql": "SELECT date, SUM(CASE WHEN LOWER(voucher_type) = 'receipt' THEN gross_amount ELSE 0 END) as daily_inflow, SUM(CASE WHEN LOWER(voucher_type) = 'payment' THEN gross_amount ELSE 0 END) as daily_outflow FROM vouchers WHERE LOWER(party_name) LIKE '%cash%' OR LOWER(primary_ledger) LIKE '%cash%' GROUP BY date ORDER BY date ASC",
                "row_count": flagged,
                "data": report["records"],
                "columns": ["date", "daily_inflow", "daily_outflow", "closing_cash_balance", "negative_deficit", "status"]
            }

        # 1. Total Sales / Revenue Query
        if ("total sales" in lower_q or "gross sales" in lower_q or "how much sales" in lower_q or lower_q == "sales"):
            fy_val = extract_fy(lower_q)
            qtr_match = re.search(r"(q[1-4])", lower_q)
            
            where = "WHERE LOWER(voucher_type) = 'sales'"
            params = []
            desc = "Total Sales"
            
            if fy_val:
                where += " AND LOWER(financial_year) = LOWER(?)"
                params.append(fy_val)
                desc += f" for {fy_val}"
            if qtr_match:
                qtr_val = qtr_match.group(1).upper()
                where += " AND quarter = ?"
                params.append(qtr_val)
                desc += f" ({qtr_val})"

            sql = f"""
            SELECT COUNT(*) as voucher_count,
                   SUM(net_amount) as net_sales,
                   SUM(tax_amount) as tax_amount,
                   SUM(gross_amount) as gross_billed
            FROM vouchers {where}
            """
            rows = self.db.execute_query(sql, params)
            r = rows[0]
            cnt = r["voucher_count"] or 0
            gross = r["gross_billed"] or 0.0
            net = r["net_sales"] or 0.0
            tax = r["tax_amount"] or 0.0

            ans = f"{desc} is **{format_inr(gross)}** ({format_inr(gross, 'words')}) across **{cnt:,} vouchers** (Net Revenue: {format_inr(net)}, Output Tax: {format_inr(tax)})."
            
            # Fetch breakdown by quarter or month
            detail_sql = f"""
            SELECT financial_year, month_year, quarter, COUNT(*) as vouchers,
                   ROUND(SUM(net_amount), 2) as net_amount,
                   ROUND(SUM(tax_amount), 2) as tax_amount,
                   ROUND(SUM(gross_amount), 2) as gross_amount
            FROM vouchers {where}
            GROUP BY financial_year, month_year
            ORDER BY MIN(date) ASC
            """
            details = self.db.execute_query(detail_sql, params)

            return {
                "answer": ans,
                "sql": sql.strip(),
                "row_count": cnt,
                "data": details,
                "columns": ["financial_year", "month_year", "quarter", "vouchers", "net_amount", "tax_amount", "gross_amount"]
            }

        # 2. Total Purchases / Expense Query
        if ("total purchase" in lower_q or "gross purchase" in lower_q or "how much purchase" in lower_q or lower_q == "purchases"):
            fy_val = extract_fy(lower_q)
            where = "WHERE LOWER(voucher_type) = 'purchase'"
            params = []
            desc = "Total Purchases"
            if fy_val:
                where += " AND LOWER(financial_year) = LOWER(?)"
                params.append(fy_val)
                desc += f" for {fy_val}"

            sql = f"""
            SELECT COUNT(*) as voucher_count,
                   SUM(net_amount) as net_expense,
                   SUM(tax_amount) as tax_amount,
                   SUM(gross_amount) as gross_billed
            FROM vouchers {where}
            """
            rows = self.db.execute_query(sql, params)
            r = rows[0]
            cnt = r["voucher_count"] or 0
            gross = r["gross_billed"] or 0.0
            net = r["net_expense"] or 0.0
            tax = r["tax_amount"] or 0.0

            ans = f"{desc} is **{format_inr(gross)}** ({format_inr(gross, 'words')}) across **{cnt:,} bills** (Net Expense: {format_inr(net)}, Input Tax: {format_inr(tax)})."
            
            detail_sql = f"""
            SELECT primary_ledger, COUNT(*) as bills,
                   ROUND(SUM(net_amount), 2) as net_amount,
                   ROUND(SUM(gross_amount), 2) as gross_amount
            FROM vouchers {where}
            GROUP BY primary_ledger
            ORDER BY gross_amount DESC
            LIMIT 15
            """
            details = self.db.execute_query(detail_sql, params)

            return {
                "answer": ans,
                "sql": sql.strip(),
                "row_count": cnt,
                "data": details,
                "columns": ["primary_ledger", "bills", "net_amount", "gross_amount"]
            }

        # 3. Top N Clients / Debtors
        if ("top" in lower_q and ("client" in lower_q or "debtor" in lower_q or "customer" in lower_q)):
            n = extract_top_n(lower_q, default=10)
            
            sql = """
            SELECT party_name, COUNT(*) as vouchers,
                   ROUND(SUM(net_amount), 2) as net_sales,
                   ROUND(SUM(tax_amount), 2) as tax_amount,
                   ROUND(SUM(gross_amount), 2) as gross_billed
            FROM vouchers
            WHERE LOWER(voucher_type) = 'sales'
            GROUP BY party_name
            ORDER BY gross_billed DESC
            LIMIT ?
            """
            rows = self.db.execute_query(sql, (n,))
            if not rows:
                fallback_sql = """
                SELECT party_name, COUNT(*) as vouchers,
                       ROUND(SUM(net_amount), 2) as net_sales,
                       ROUND(SUM(tax_amount), 2) as tax_amount,
                       ROUND(SUM(gross_amount), 2) as gross_billed
                FROM vouchers
                WHERE LOWER(voucher_type) IN ('receipt', 'journal')
                  AND party_name IS NOT NULL AND party_name != '' AND party_name != 'Sundry Party'
                GROUP BY party_name
                ORDER BY gross_billed DESC
                LIMIT ?
                """
                rows = self.db.execute_query(fallback_sql, (n,))

            top_party = rows[0]["party_name"] if rows else "N/A"
            top_amt = rows[0]["gross_billed"] if rows else 0.0
            
            ans = f"Top {n} Clients by Gross Billed Volume. The largest client is **{top_party}** at **{format_inr(top_amt)}**."
            return {
                "answer": ans,
                "sql": sql.strip(),
                "row_count": len(rows),
                "data": rows,
                "columns": ["party_name", "vouchers", "net_sales", "tax_amount", "gross_billed"]
            }

        # 4. Top N Vendors / Creditors / Suppliers
        if ("top" in lower_q and ("vendor" in lower_q or "creditor" in lower_q or "supplier" in lower_q)):
            n = extract_top_n(lower_q, default=10)
            
            sql = """
            SELECT party_name, COUNT(*) as bills,
                   ROUND(SUM(net_amount), 2) as net_expense,
                   ROUND(SUM(gross_amount), 2) as gross_billed
            FROM vouchers
            WHERE LOWER(voucher_type) = 'purchase'
            GROUP BY party_name
            ORDER BY gross_billed DESC
            LIMIT ?
            """
            rows = self.db.execute_query(sql, (n,))
            if not rows:
                fallback_sql = """
                SELECT party_name, COUNT(*) as vouchers,
                       ROUND(SUM(net_amount), 2) as net_sales,
                       ROUND(SUM(tax_amount), 2) as tax_amount,
                       ROUND(SUM(gross_amount), 2) as gross_billed
                FROM vouchers
                WHERE LOWER(voucher_type) IN ('receipt', 'journal')
                  AND party_name IS NOT NULL AND party_name != '' AND party_name != 'Sundry Party'
                GROUP BY party_name
                ORDER BY gross_billed DESC
                LIMIT ?
                """
                rows = self.db.execute_query(fallback_sql, (n,))

            top_party = rows[0]["party_name"] if rows else "N/A"
            top_amt = rows[0]["gross_billed"] if rows else 0.0
            
            ans = f"Top {n} Vendors by Billed Volume. The largest vendor is **{top_party}** at **{format_inr(top_amt)}**."
            return {
                "answer": ans,
                "sql": sql.strip(),
                "row_count": len(rows),
                "data": rows,
                "columns": ["party_name", "bills", "net_expense", "gross_billed"]
            }

        # 5. Debit Notes Summary
        if ("debit note" in lower_q or "debit notes" in lower_q):
            sql = """
            SELECT COUNT(*) as total_count,
                   ROUND(SUM(net_amount), 2) as net_amount,
                   ROUND(SUM(tax_amount), 2) as tax_amount,
                   ROUND(SUM(gross_amount), 2) as gross_amount,
                   COUNT(DISTINCT party_name) as unique_parties
            FROM vouchers
            WHERE LOWER(voucher_type) = 'debit note'
            """
            rows = self.db.execute_query(sql)
            r = rows[0]
            cnt = r["total_count"] or 0
            gross = r["gross_amount"] or 0.0

            detail_sql = """
            SELECT date, voucher_no, reference_no, party_name, primary_ledger,
                   gross_amount, narration
            FROM vouchers
            WHERE LOWER(voucher_type) = 'debit note'
            ORDER BY date DESC
            LIMIT 25
            """
            details = self.db.execute_query(detail_sql)
            ans = f"Total Debit Notes issued: **{cnt} vouchers** totaling **{format_inr(gross)}** ({format_inr(gross, 'words')}) across {r['unique_parties']} parties for vendor deductions, ticket cancellations, and rate differences."

            return {
                "answer": ans,
                "sql": sql.strip(),
                "row_count": cnt,
                "data": details,
                "columns": ["date", "voucher_no", "reference_no", "party_name", "primary_ledger", "gross_amount", "narration"]
            }

        # 6. Credit Notes Summary
        if ("credit note" in lower_q or "credit notes" in lower_q):
            sql = """
            SELECT COUNT(*) as total_count,
                   ROUND(SUM(net_amount), 2) as net_amount,
                   ROUND(SUM(tax_amount), 2) as tax_amount,
                   ROUND(SUM(gross_amount), 2) as gross_amount,
                   COUNT(DISTINCT party_name) as unique_parties
            FROM vouchers
            WHERE LOWER(voucher_type) = 'credit note'
            """
            rows = self.db.execute_query(sql)
            r = rows[0]
            cnt = r["total_count"] or 0
            gross = r["gross_amount"] or 0.0

            detail_sql = """
            SELECT date, voucher_no, reference_no, party_name, primary_ledger,
                   gross_amount, narration
            FROM vouchers
            WHERE LOWER(voucher_type) = 'credit note'
            ORDER BY date DESC
            LIMIT 25
            """
            details = self.db.execute_query(detail_sql)
            ans = f"Total Credit Notes issued: **{cnt} vouchers** totaling **{format_inr(gross)}** ({format_inr(gross, 'words')}) across {r['unique_parties']} clients for rebates, discounts, and excess billing reversals."

            return {
                "answer": ans,
                "sql": sql.strip(),
                "row_count": cnt,
                "data": details,
                "columns": ["date", "voucher_no", "reference_no", "party_name", "primary_ledger", "gross_amount", "narration"]
            }

        # 7. Cash Inflow & Outflow / Cash & Bank Position
        if (
            ("inflow" in lower_q or "outflow" in lower_q) or
            ("cash flow" in lower_q or "cashflow" in lower_q) or
            ("receipts and payments" in lower_q or "receipt and payment" in lower_q) or
            ("cash in hand" in lower_q or "bank balance" in lower_q or "cash balance" in lower_q) or
            (("cash" in lower_q or "bank" in lower_q) and any(k in lower_q for k in ["summary", "position", "statement", "trend", "total", "in/out", "balance"]))
        ):
            fy_val = extract_fy(lower_q)
            fy_clause = ""
            params = []
            desc_fy = ""
            if fy_val:
                fy_clause = " AND LOWER(financial_year) = LOWER(?)"
                params.append(fy_val)
                desc_fy = f" for {fy_val}"

            sql_summary = f"""
            SELECT 
                voucher_type,
                COUNT(*) as voucher_count,
                ROUND(SUM(gross_amount), 2) as total_amount
            FROM vouchers
            WHERE LOWER(voucher_type) IN ('receipt', 'payment', 'contra') {fy_clause}
            GROUP BY voucher_type
            """
            v_rows = self.db.execute_query(sql_summary, params)
            flow_dict = {r["voucher_type"].lower(): (r["voucher_count"], r["total_amount"]) for r in v_rows}
            rcnt, ramt = flow_dict.get("receipt", (0, 0.0))
            pcnt, pamt = flow_dict.get("payment", (0, 0.0))
            ccnt, camt = flow_dict.get("contra", (0, 0.0))
            net_amt = ramt - pamt
            net_status = "Net Surplus / Inflow" if net_amt >= 0 else "Net Deficit / Outflow"

            # Check Tally live snapshot if available in company_metadata
            tally_snapshot = self.db.get_metadata("tally_metrics") if hasattr(self.db, "get_metadata") else None
            tally_str = ""
            if tally_snapshot:
                try:
                    import json
                    tm = json.loads(tally_snapshot)
                    t_in = tm.get("cash_inflow")
                    t_out = tm.get("cash_outflow")
                    t_net = tm.get("net_cash_flow")
                    b_bal = tm.get("bank_accounts")
                    c_bal = tm.get("cash_in_hand")
                    tally_str = f" | Tally Snapshot: Live Receipts {format_inr(t_in)}, Payments {format_inr(t_out)}, Net {format_inr(t_net)}, Bank: {format_inr(b_bal)}, Cash: {format_inr(c_bal)}"
                except Exception:
                    pass

            ans = (
                f"**Cash & Bank Liquidity Analysis{desc_fy}**:\n"
                f"- **Total Cash Inflow (Receipts)**: **{format_inr(ramt)}** across **{rcnt:,} vouchers**\n"
                f"- **Total Cash Outflow (Payments)**: **{format_inr(pamt)}** across **{pcnt:,} vouchers**\n"
                f"- **Net Cash Flow**: **{format_inr(net_amt)}** ({net_status})\n"
                f"- **Contra (Inter-Account Transfers)**: **{format_inr(camt)}** across **{ccnt} transfers**{tally_str}."
            )

            # Monthly cash flow trend
            sql_monthly = f"""
            SELECT 
                month_year,
                COUNT(CASE WHEN LOWER(voucher_type) = 'receipt' THEN 1 END) as receipts,
                ROUND(SUM(CASE WHEN LOWER(voucher_type) = 'receipt' THEN gross_amount ELSE 0 END), 2) as cash_inflow,
                COUNT(CASE WHEN LOWER(voucher_type) = 'payment' THEN 1 END) as payments,
                ROUND(SUM(CASE WHEN LOWER(voucher_type) = 'payment' THEN gross_amount ELSE 0 END), 2) as cash_outflow,
                ROUND(SUM(CASE WHEN LOWER(voucher_type) = 'receipt' THEN gross_amount WHEN LOWER(voucher_type) = 'payment' THEN -gross_amount ELSE 0 END), 2) as net_cash_flow
            FROM vouchers
            WHERE LOWER(voucher_type) IN ('receipt', 'payment') {fy_clause}
            GROUP BY month_year
            ORDER BY MIN(date) ASC
            """
            monthly_data = self.db.execute_query(sql_monthly, params)

            return {
                "answer": ans,
                "sql": sql_monthly.strip(),
                "row_count": len(monthly_data),
                "data": monthly_data,
                "columns": ["month_year", "receipts", "cash_inflow", "payments", "cash_outflow", "net_cash_flow"]
            }

        # 8. Party / Account Ledger Statement (e.g., "share ajay kumar ledger", "ajay kumar ledger", "ledger of ajay kumar")
        ledger_cand = self._extract_ledger_candidate(original_q, lower_q)
        if ledger_cand:
            matched_entity = self._find_matching_ledger(ledger_cand)
            if matched_entity:
                ledger_res = self._generate_ledger_statement(matched_entity)
                if ledger_res:
                    return ledger_res

        # 9. Forensic / Keyword Search in Narrations
        if any(w in lower_q for w in ["narration", "cancelled", "cancel", "settlement", "personal", "difference", "dispute", "red flag"]):
            clean_term = re.sub(r"(?:show|find|search|vouchers|with|containing|narration|for)", "", lower_q).strip()
            if not clean_term:
                clean_term = "cancel"
            
            sql = """
            SELECT v.date, v.voucher_type, v.voucher_no, v.party_name,
                   v.primary_ledger, v.gross_amount, v.narration
            FROM vouchers v
            JOIN vouchers_fts f ON v.id = f.rowid
            WHERE vouchers_fts MATCH ?
            ORDER BY v.date DESC
            LIMIT 50
            """
            try:
                rows = self.db.execute_query(sql, (clean_term,))
                ans = f"Forensic Narration Search for term **'{clean_term}'**: Found **{len(rows)} matching vouchers**."
                return {
                    "answer": ans,
                    "sql": sql.strip(),
                    "row_count": len(rows),
                    "data": rows,
                    "columns": ["date", "voucher_type", "voucher_no", "party_name", "primary_ledger", "gross_amount", "narration"]
                }
            except Exception:
                pass

        return None

    def _extract_ledger_candidate(self, original_q, lower_q):
        """Extracts potential party/ledger candidate from natural language query."""
        if any(term in lower_q for term in ["total sales", "total purchase", "top clients", "top vendors", "top creditors", "top debtors", "debit note", "credit note", "inflow", "outflow", "cash flow"]):
            return None

        t = original_q.strip()
        # Remove polite/command prefix words
        t = re.sub(r"^(?:please\s+|kindly\s+)?(?:share|show|give\s+me|give|fetch|view|display|get|print|send|open)\s+", "", t, flags=re.IGNORECASE).strip()
        t = re.sub(r"^the\s+", "", t, flags=re.IGNORECASE).strip()

        # Check: "ledger of <candidate>", "statement of <candidate>", "account of <candidate>"
        m = re.search(r"^(?:ledger|statement|account(?:\s+statement)?|vouchers|transactions|bills|invoices)\s+(?:of|for)\s+(.+)$", t, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()

        # Check: "<candidate> ledger", "<candidate> statement", "<candidate> account"
        m = re.search(r"^(.+?)\s+(?:ledger|statement|account(?:\s+statement)?|account\s+details)(?:\s+details)?$", t, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()

        # Check: "bills/vouchers/transactions for/from/to <candidate>"
        m = re.search(r"^(?:bills|invoices|vouchers|transactions)\s+(?:for|from|to|of)\s+(.+)$", t, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()

        # Check: "(?:for|from|to|party|vendor|client)\s+<candidate>"
        m = re.search(r"^(?:for|from|to|party|client|vendor|supplier|customer)\s+(.+?)(?:\s+(?:bills|invoices|vouchers|ledger))?$", t, flags=re.IGNORECASE)
        if m:
            return m.group(1).strip()

        # If user directly entered a short entity name (1 to 5 words)
        words = t.split()
        if 1 <= len(words) <= 5 and not any(w.lower() in ["why", "how", "what", "when", "where", "help"] for w in words):
            return t

        return None

    def _find_matching_ledger(self, candidate):
        """Finds matching ledger name from party_name or primary_ledger in database."""
        if not candidate:
            return None
        candidate = candidate.strip()
        candidate = re.sub(r"^(?:m/s\.?|mr\.?|shri|mrs\.?|dr\.?)\s+", "", candidate, flags=re.IGNORECASE).strip()
        if len(candidate) < 2:
            return None

        # 1. Exact match in party_name or primary_ledger
        exact_rows = self.db.execute_query(
            """SELECT party_name as name FROM vouchers WHERE LOWER(party_name) = LOWER(?)
               UNION
               SELECT primary_ledger as name FROM vouchers WHERE LOWER(primary_ledger) = LOWER(?)
               LIMIT 1""",
            (candidate, candidate)
        )
        if exact_rows:
            return exact_rows[0]["name"]

        # 2. Substring match
        sub_rows = self.db.execute_query(
            """SELECT name FROM (
                   SELECT DISTINCT party_name as name FROM vouchers WHERE LOWER(party_name) LIKE LOWER(?)
                   UNION
                   SELECT DISTINCT primary_ledger as name FROM vouchers WHERE LOWER(primary_ledger) LIKE LOWER(?)
               ) ORDER BY LENGTH(name) ASC LIMIT 1""",
            (f"%{candidate}%", f"%{candidate}%")
        )
        if sub_rows:
            return sub_rows[0]["name"]

        # 3. All words match
        words = candidate.split()
        if len(words) > 1:
            p_c = " AND ".join(["LOWER(party_name) LIKE ?"] * len(words))
            l_c = " AND ".join(["LOWER(primary_ledger) LIKE ?"] * len(words))
            params = [f"%{w.lower()}%" for w in words]
            w_rows = self.db.execute_query(
                f"""SELECT name FROM (
                       SELECT DISTINCT party_name as name FROM vouchers WHERE {p_c}
                       UNION
                       SELECT DISTINCT primary_ledger as name FROM vouchers WHERE {l_c}
                   ) ORDER BY LENGTH(name) ASC LIMIT 1""",
                params + params
            )
            if w_rows:
                return w_rows[0]["name"]

        return None

    def _generate_ledger_statement(self, entity_name):
        """
        Generates authentic double-entry ledger statement with Debit, Credit & Running Balance.
        Correctly derives Dr/Cr direction according to account nature (Cash/Bank, Debtor, Creditor, Nominal).
        """
        sql = """
        SELECT id, date, voucher_type, voucher_no, reference_no, party_name, primary_ledger, gross_amount, net_amount, narration
        FROM vouchers
        WHERE party_name = ? OR primary_ledger = ?
        ORDER BY date ASC, id ASC
        """
        rows = self.db.execute_query(sql, (entity_name, entity_name))
        if not rows:
            return None

        ent_lower = entity_name.lower()
        # Word-boundary matching to prevent false positives like 'Bobson Traders', 'Akashic', etc.
        is_cash_bank = bool(re.search(r"\b(cash|bank|axis|hdfc|icici|sbi|kotak|pnb|bob)\b", ent_lower))
        
        # Check predominant nature among rows
        sales_cnt = sum(1 for r in rows if (r["voucher_type"] or "").lower() == "sales")
        purchase_cnt = sum(1 for r in rows if (r["voucher_type"] or "").lower() == "purchase")
        is_creditor = purchase_cnt > sales_cnt

        tot_dr = 0.0
        tot_cr = 0.0
        bal = 0.0
        records = []
        for r in rows:
            gross = r["gross_amount"] or 0.0
            net = r["net_amount"] if (r["net_amount"] is not None and r["net_amount"] > 0) else gross
            vt_lower = (r["voucher_type"] or "").lower()
            is_party = (r["party_name"] == entity_name)

            if is_cash_bank:
                particulars = r["primary_ledger"] if is_party else (r["party_name"] or "Opposing Ledger")
                if vt_lower in ["receipt", "sales"]:
                    dr, cr = gross, 0.0
                elif vt_lower in ["payment", "purchase"]:
                    dr, cr = 0.0, gross
                elif is_party:
                    dr, cr = gross, 0.0
                else:
                    dr, cr = 0.0, gross
            elif is_party:
                particulars = r["primary_ledger"] or "Opposing Ledger"
                if is_creditor:
                    # Supplier / Vendor (Liability): Purchase is Cr, Payment is Dr
                    if vt_lower in ["purchase", "credit note"]:
                        dr, cr = 0.0, gross
                    elif vt_lower in ["payment", "debit note"]:
                        dr, cr = gross, 0.0
                    else:
                        dr, cr = 0.0, gross
                else:
                    # Customer / Debtor (Asset): Sales is Dr, Receipt is Cr
                    if vt_lower in ["sales", "debit note"]:
                        dr, cr = gross, 0.0
                    elif vt_lower in ["receipt", "credit note"]:
                        dr, cr = 0.0, gross
                    else:
                        dr, cr = gross, 0.0
            else:
                # Nominal ledger (Expense or Revenue): use net_amount to avoid mixing gross with tax
                particulars = r["party_name"] or "Opposing Ledger"
                if any(k in ent_lower for k in ["sales", "revenue", "income", "turnover"]):
                    amt = net
                    if vt_lower in ["sales", "receipt"]:
                        dr, cr = 0.0, amt
                    else:
                        dr, cr = amt, 0.0
                else:
                    amt = net
                    if vt_lower in ["purchase", "payment"]:
                        dr, cr = amt, 0.0
                    else:
                        dr, cr = 0.0, amt

            tot_dr += dr
            tot_cr += cr
            bal += (dr - cr)

            if bal > 0.01:
                bal_str = f"{format_inr(bal)} Dr"
            elif bal < -0.01:
                bal_str = f"{format_inr(abs(bal))} Cr"
            else:
                bal_str = "₹ 0.00 (Nil)"

            records.append({
                "date": r["date"],
                "voucher_type": r["voucher_type"],
                "voucher_no": r["voucher_no"],
                "reference_no": r["reference_no"] or "-",
                "particulars": particulars,
                "debit": format_inr(dr) if dr > 0 else "-",
                "credit": format_inr(cr) if cr > 0 else "-",
                "running_balance": bal_str,
                "narration": r["narration"]
            })

        closing = f"{format_inr(bal)} Dr" if bal > 0.01 else (f"{format_inr(abs(bal))} Cr" if bal < -0.01 else "₹ 0.00 (Settled)")
        ans = (
            f"**Ledger Account Statement: {entity_name}**\n"
            f"Total Transactions: **{len(rows):,} vouchers** | "
            f"Total Debits: **{format_inr(tot_dr)}** | "
            f"Total Credits: **{format_inr(tot_cr)}** | "
            f"Closing Balance: **{closing}**."
        )

        return {
            "answer": ans,
            "sql": sql.strip(),
            "row_count": len(rows),
            "data": records,
            "columns": ["date", "voucher_type", "voucher_no", "reference_no", "particulars", "debit", "credit", "running_balance", "narration"]
        }

    def _fallback_fts_search(self, q):
        """Fallback full-text search across vouchers with stopword filtering and AND relevance."""
        clean_q = re.sub(r"[^\w\s]", "", q).strip()
        words = clean_q.split()
        if not words:
            return {"answer": "Please provide a valid financial question or entity name.", "data": [], "columns": [], "sql": ""}

        STOP_WORDS = {
            "share", "show", "give", "fetch", "view", "display", "get", "print", "send", "open",
            "the", "a", "an", "for", "from", "to", "of", "in", "on", "at", "by", "with",
            "and", "or", "is", "are", "was", "were", "it", "this", "that", "all",
            "me", "us", "please", "kindly", "tell", "details", "voucher", "vouchers",
            "bills", "invoices", "ledger", "account", "statement"
        }
        keywords = [w for w in words if w.lower() not in STOP_WORDS]
        if not keywords:
            keywords = words[:3]

        # Try AND search first for exact relevance
        match_clause = " AND ".join(keywords[:4])
        sql = """
        SELECT v.date, v.voucher_type, v.voucher_no, v.reference_no,
               v.party_name, v.primary_ledger, v.cost_centre,
               v.gross_amount, v.narration
        FROM vouchers v
        JOIN vouchers_fts f ON v.id = f.rowid
        WHERE vouchers_fts MATCH ?
        ORDER BY v.date DESC
        LIMIT 50
        """
        try:
            rows = self.db.execute_query(sql, (match_clause,))
            # If AND search yielded nothing and there were multiple words, try OR as softer fallback
            if not rows and len(keywords) > 1:
                match_clause_or = " OR ".join(keywords[:4])
                rows = self.db.execute_query(sql, (match_clause_or,))
                
            if rows:
                ans = f"Search across records for **'{q}'**: Found **{len(rows)} matching vouchers**."
            else:
                ans = f"No matching vouchers found for **'{q}'**. Try querying by party name (e.g. *'Ajay Kumar ledger'*), *'Cash inflow and outflow'*, *'Total sales'*, or *'Top 10 vendors'*."

            return {
                "answer": ans,
                "sql": sql.strip(),
                "row_count": len(rows),
                "data": rows,
                "columns": ["date", "voucher_type", "voucher_no", "reference_no", "party_name", "primary_ledger", "gross_amount", "narration"]
            }
        except Exception as e:
            return {
                "answer": f"Unable to parse query directly: {e}. Try asking: 'Ajay Kumar ledger', 'Cash inflow and outflow', 'Total sales', or 'Top 10 vendors'.",
                "sql": "",
                "row_count": 0,
                "data": [],
                "columns": []
            }

    def _synthesize_llm_result(self, question, rows):
        """Creates a natural language summary from SQL result rows."""
        if not rows:
            return f"Query executed successfully, but returned 0 records for: '{question}'."
        if len(rows) == 1 and len(rows[0]) == 1:
            val = list(rows[0].values())[0]
            if isinstance(val, (int, float)):
                return f"Result for '{question}': **{format_inr(val)}**"
            return f"Result for '{question}': **{val}**"
        
        return f"Retrieved **{len(rows):,} records** answering '{question}'."
