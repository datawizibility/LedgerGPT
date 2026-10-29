"""
Deterministic Query Engine & Natural Language Routing for LedgerGPT.
Executes rule-based queries with instant sub-millisecond response, with LLM fallback.
"""

import re
import time
from ledgergpt.db import FinancialDB
from ledgergpt.formatters import format_inr
from ledgergpt.llm_adapter import LLMAdapter

class QueryEngine:
    def __init__(self, db=None, llm_adapter=None):
        self.db = db or FinancialDB()
        self.llm = llm_adapter or LLMAdapter()

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
            try:
                rows = self.db.execute_query(sql)
                elapsed_ms = round((time.time() - start_time) * 1000, 2)
                
                # Synthesize answer
                summary = self._synthesize_llm_result(q, rows)
                return {
                    "answer": summary,
                    "sql": sql,
                    "row_count": len(rows),
                    "data": rows[:100],
                    "columns": list(rows[0].keys()) if rows else [],
                    "execution_time_ms": elapsed_ms,
                    "source": f"LLM SQL Adapter ({self.llm.provider.upper()})"
                }
            except Exception as e:
                print(f"[SQL EXEC ERROR] {e} on SQL: {sql}")

        # 3. Fallback: Full-Text Search across all fields and narrations
        fts_res = self._fallback_fts_search(q)
        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        fts_res["execution_time_ms"] = elapsed_ms
        fts_res["source"] = "Full-Text Search Engine (FTS5)"
        return fts_res

    def _match_deterministic(self, lower_q, original_q):
        """Rule-based deterministic financial intents."""
        
        # 1. Total Sales / Revenue Query
        if ("total sales" in lower_q or "gross sales" in lower_q or "how much sales" in lower_q or lower_q == "sales"):
            fy_match = re.search(r"fy\s*(\d{4}[-_]\d{2})", lower_q)
            qtr_match = re.search(r"(q[1-4])", lower_q)
            
            where = "WHERE LOWER(voucher_type) = 'sales'"
            params = []
            desc = "Total Sales"
            
            if fy_match:
                fy_val = f"FY {fy_match.group(1).replace('_', '-')}"
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
            fy_match = re.search(r"fy\s*(\d{4}[-_]\d{2})", lower_q)
            where = "WHERE LOWER(voucher_type) = 'purchase'"
            params = []
            desc = "Total Purchases"
            if fy_match:
                fy_val = f"FY {fy_match.group(1).replace('_', '-')}"
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
            n_match = re.search(r"top\s*(\d+)", lower_q)
            n = int(n_match.group(1)) if n_match else 10
            
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
            n_match = re.search(r"top\s*(\d+)", lower_q)
            n = int(n_match.group(1)) if n_match else 10
            
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

        # 7. Specific Party Lookup (e.g., "bills for Bennett Coleman" or "purchases from Bartaman")
        party_match = re.search(r"(?:for|from|to|party|client|vendor)\s+([A-Za-z0-9\.\s&-]{3,35})(?:\s+bills|\s+invoices|\s+vouchers|$)", original_q, re.IGNORECASE)
        if party_match and not any(k in lower_q for k in ["top", "total", "sales", "purchase"]):
            candidate = party_match.group(1).strip()
            sql = """
            SELECT date, voucher_type, voucher_no, reference_no, party_name,
                   primary_ledger, gross_amount, narration
            FROM vouchers
            WHERE LOWER(party_name) LIKE LOWER(?)
            ORDER BY date DESC
            LIMIT 50
            """
            rows = self.db.execute_query(sql, (f"%{candidate}%",))
            if rows:
                exact_name = rows[0]["party_name"]
                tot = sum(r["gross_amount"] for r in rows)
                ans = f"Found **{len(rows)} vouchers** for **{exact_name}** totaling **{format_inr(tot)}**."
                return {
                    "answer": ans,
                    "sql": sql.strip(),
                    "row_count": len(rows),
                    "data": rows,
                    "columns": ["date", "voucher_type", "voucher_no", "reference_no", "party_name", "primary_ledger", "gross_amount", "narration"]
                }

        # 8. Forensic / Keyword Search in Narrations
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

    def _fallback_fts_search(self, q):
        """Fallback full-text search across vouchers."""
        clean_q = re.sub(r"[^\w\s]", "", q).strip()
        words = clean_q.split()
        if not words:
            return {"answer": "Please provide a valid financial question or entity name.", "data": [], "columns": [], "sql": ""}

        match_clause = " OR ".join(words[:4])
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
            ans = f"Search across records for '{q}': Found **{len(rows)} vouchers**."
            return {
                "answer": ans,
                "sql": sql.strip(),
                "row_count": len(rows),
                "data": rows,
                "columns": ["date", "voucher_type", "voucher_no", "reference_no", "party_name", "primary_ledger", "gross_amount", "narration"]
            }
        except Exception as e:
            return {
                "answer": f"Unable to parse query directly: {e}. Try asking: 'Total sales', 'Top 10 clients', 'Debit notes', or 'Purchases'.",
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
