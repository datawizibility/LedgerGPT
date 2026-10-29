"""
Dashboard Analytics Service for LedgerGPT.
Computes executive CFO metrics, monthly trends, party rankings,
and project profitability from the local database.
"""

from ledgergpt.db import FinancialDB
from ledgergpt.formatters import format_inr


class DashboardService:
    def __init__(self, db=None):
        self.db = db or FinancialDB()

    def get_executive_summary(self):
        """Computes top-level financial health KPIs."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Sales aggregate
            cursor.execute("""
                SELECT 
                    COUNT(*), 
                    COALESCE(SUM(gross_amount), 0), 
                    COALESCE(SUM(net_amount), 0), 
                    COALESCE(SUM(tax_amount), 0)
                FROM vouchers WHERE voucher_type = 'Sales'
            """)
            s_cnt, s_gross, s_net, s_tax = cursor.fetchone()

            # Purchase aggregate
            cursor.execute("""
                SELECT 
                    COUNT(*), 
                    COALESCE(SUM(gross_amount), 0), 
                    COALESCE(SUM(net_amount), 0), 
                    COALESCE(SUM(tax_amount), 0)
                FROM vouchers WHERE voucher_type = 'Purchase'
            """)
            p_cnt, p_gross, p_net, p_tax = cursor.fetchone()

            # Debit Notes
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) FROM vouchers WHERE voucher_type = 'Debit Note'")
            dn_cnt, dn_gross = cursor.fetchone()

            # Credit Notes
            cursor.execute("SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) FROM vouchers WHERE voucher_type = 'Credit Note'")
            cn_cnt, cn_gross = cursor.fetchone()

            # Distinct counts & date ranges
            cursor.execute("""
                SELECT 
                    COUNT(*),
                    COUNT(DISTINCT party_name), 
                    COUNT(DISTINCT cost_centre),
                    MIN(date),
                    MAX(date)
                FROM vouchers
            """)
            total_vch, total_parties, total_ccs, min_date, max_date = cursor.fetchone()

            gross_margin = s_gross - p_gross
            margin_pct = (gross_margin / s_gross * 100) if s_gross > 0 else 0.0

            return {
                "total_vouchers": total_vch,
                "sales_vouchers": s_cnt,
                "purchase_vouchers": p_cnt,
                "debit_notes_count": dn_cnt,
                "credit_notes_count": cn_cnt,
                "unique_parties": total_parties,
                "unique_cost_centres": total_ccs,
                "min_date": min_date,
                "max_date": max_date,
                # Raw numbers
                "sales_gross": round(s_gross, 2),
                "sales_net": round(s_net, 2),
                "sales_tax": round(s_tax, 2),
                "purchase_gross": round(p_gross, 2),
                "purchase_net": round(p_net, 2),
                "purchase_tax": round(p_tax, 2),
                "debit_notes_gross": round(dn_gross, 2),
                "credit_notes_gross": round(cn_gross, 2),
                "gross_margin": round(gross_margin, 2),
                "gross_margin_pct": round(margin_pct, 2),
                # Human formatted
                "sales_gross_formatted": format_inr(s_gross),
                "purchase_gross_formatted": format_inr(p_gross),
                "gross_margin_formatted": format_inr(gross_margin),
                "debit_notes_formatted": format_inr(dn_gross),
                "credit_notes_formatted": format_inr(cn_gross),
            }

    def get_monthly_trend(self):
        """Returns monthly time series of Sales vs Purchases and Margin."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Group by year-month
            query = """
                SELECT 
                    strftime('%Y-%m', date) as ym,
                    MAX(month_year) as month_label,
                    SUM(CASE WHEN voucher_type = 'Sales' THEN gross_amount ELSE 0 END) as sales,
                    SUM(CASE WHEN voucher_type = 'Purchase' THEN gross_amount ELSE 0 END) as purchase,
                    COUNT(*) as total_vouchers
                FROM vouchers
                WHERE date IS NOT NULL AND date != ''
                GROUP BY strftime('%Y-%m', date)
                ORDER BY ym ASC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            months = []
            sales = []
            purchases = []
            margins = []
            vouchers = []

            for ym, label, s, p, cnt in rows:
                s = round(s or 0.0, 2)
                p = round(p or 0.0, 2)
                m = round(s - p, 2)
                
                display_label = label
                if not display_label or display_label.strip() == "":
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(ym, "%Y-%m")
                        display_label = dt.strftime("%b %Y")
                    except Exception:
                        display_label = ym

                months.append(display_label)
                sales.append(s)
                purchases.append(p)
                margins.append(m)
                vouchers.append(cnt)

            return {
                "labels": months,
                "sales": sales,
                "purchases": purchases,
                "margins": margins,
                "vouchers": vouchers
            }

    def get_rankings(self, top_n=10):
        """Returns Top Debtors, Top Creditors, and Top Cost Centres."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Top 10 Clients (Sales)
            cursor.execute("""
                SELECT party_name, SUM(gross_amount) as total_val, COUNT(*) as vch_count
                FROM vouchers
                WHERE voucher_type = 'Sales' AND party_name != 'Sundry Party' AND party_name != ''
                GROUP BY party_name
                ORDER BY total_val DESC
                LIMIT ?
            """, (top_n,))
            debtors = [
                {
                    "party_name": r[0],
                    "amount": round(r[1], 2),
                    "amount_formatted": format_inr(r[1]),
                    "voucher_count": r[2]
                }
                for r in cursor.fetchall()
            ]

            # Top 10 Vendors (Purchases)
            cursor.execute("""
                SELECT party_name, SUM(gross_amount) as total_val, COUNT(*) as vch_count
                FROM vouchers
                WHERE voucher_type = 'Purchase' AND party_name != 'Sundry Party' AND party_name != ''
                GROUP BY party_name
                ORDER BY total_val DESC
                LIMIT ?
            """, (top_n,))
            creditors = [
                {
                    "party_name": r[0],
                    "amount": round(r[1], 2),
                    "amount_formatted": format_inr(r[1]),
                    "voucher_count": r[2]
                }
                for r in cursor.fetchall()
            ]

            # Top Cost Centres (Revenue & Profitability)
            cursor.execute("""
                SELECT 
                    cost_centre,
                    SUM(CASE WHEN voucher_type = 'Sales' THEN gross_amount ELSE 0 END) as s_val,
                    SUM(CASE WHEN voucher_type = 'Purchase' THEN gross_amount ELSE 0 END) as p_val,
                    COUNT(*) as vch_count
                FROM vouchers
                WHERE cost_centre IS NOT NULL AND cost_centre != '' AND cost_centre != 'General / Untagged'
                GROUP BY cost_centre
                HAVING s_val > 0 OR p_val > 0
                ORDER BY s_val DESC
                LIMIT ?
            """, (top_n,))
            cost_centres = []
            for r in cursor.fetchall():
                cc_name, s_val, p_val, cnt = r
                s_val = round(s_val or 0.0, 2)
                p_val = round(p_val or 0.0, 2)
                margin = round(s_val - p_val, 2)
                m_pct = round((margin / s_val * 100), 1) if s_val > 0 else 0.0
                cost_centres.append({
                    "cost_centre": cc_name,
                    "sales": s_val,
                    "sales_formatted": format_inr(s_val),
                    "purchase": p_val,
                    "purchase_formatted": format_inr(p_val),
                    "margin": margin,
                    "margin_formatted": format_inr(margin),
                    "margin_pct": m_pct,
                    "voucher_count": cnt
                })

            return {
                "top_debtors": debtors,
                "top_creditors": creditors,
                "top_cost_centres": cost_centres
            }

    def get_vouchers_grid(self, page=1, page_size=50, vtype=None, search=None, fy=None):
        """Returns paginated, filterable voucher records for table drilldown."""
        offset = (page - 1) * page_size
        where_clauses = ["1=1"]
        params = []

        if vtype and vtype != "All":
            where_clauses.append("voucher_type = ?")
            params.append(vtype)

        if fy and fy != "All":
            where_clauses.append("financial_year = ?")
            params.append(fy)

        if search and search.strip():
            # Use FTS or LIKE
            where_clauses.append("(party_name LIKE ? OR narration LIKE ? OR cost_centre LIKE ? OR voucher_no LIKE ?)")
            s_param = f"%{search.strip()}%"
            params.extend([s_param, s_param, s_param, s_param])

        where_str = " AND ".join(where_clauses)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Count
            cursor.execute(f"SELECT COUNT(*) FROM vouchers WHERE {where_str}", params)
            total_rows = cursor.fetchone()[0]

            # Fetch paginated rows
            cursor.execute(f"""
                SELECT 
                    id, voucher_type, voucher_no, reference_no, date,
                    financial_year, party_name, primary_ledger, cost_centre,
                    net_amount, tax_amount, gross_amount, narration
                FROM vouchers
                WHERE {where_str}
                ORDER BY date DESC, id DESC
                LIMIT ? OFFSET ?
            """, params + [page_size, offset])

            rows = cursor.fetchall()
            items = []
            for r in rows:
                items.append({
                    "id": r[0],
                    "voucher_type": r[1],
                    "voucher_no": r[2] or "-",
                    "reference_no": r[3] or "-",
                    "date": r[4],
                    "financial_year": r[5],
                    "party_name": r[6],
                    "primary_ledger": r[7],
                    "cost_centre": r[8],
                    "net_amount": r[9],
                    "tax_amount": r[10],
                    "gross_amount": r[11],
                    "narration": r[12] or ""
                })

            return {
                "page": page,
                "page_size": page_size,
                "total_rows": total_rows,
                "total_pages": (total_rows + page_size - 1) // page_size if total_rows > 0 else 1,
                "items": items
            }
