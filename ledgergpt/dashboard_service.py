"""
Dashboard Analytics Service for LedgerGPT.
Computes executive CFO metrics, monthly trends, party rankings,
project profitability, and Tally liquidity/ratio benchmarks.
"""

import json
from datetime import datetime
from ledgergpt.db import FinancialDB
from ledgergpt.formatters import format_inr


class DashboardService:
    def __init__(self, db=None):
        self.db = db or FinancialDB()

    def get_available_periods(self):
        """Returns distinct financial years present in vouchers."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT financial_year 
                FROM vouchers 
                WHERE financial_year IS NOT NULL AND TRIM(financial_year) != ''
                ORDER BY financial_year DESC
            """)
            periods = [r[0] for r in cursor.fetchall()]
            return periods if periods else []

    def get_available_cost_centres(self):
        """Returns distinct cost centres/projects present in vouchers."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT cost_centre 
                FROM vouchers 
                WHERE cost_centre IS NOT NULL AND TRIM(cost_centre) != ''
                ORDER BY cost_centre ASC
            """)
            ccs = [r[0] for r in cursor.fetchall()]
            return ccs if ccs else ["General / Untagged"]

    def get_executive_summary(self, fy=None, cost_centre=None):
        """Computes top-level financial health KPIs, Tally liquidity, and balance sheet metrics."""
        where_clauses = []
        params = []
        if fy and fy != "All":
            where_clauses.append("financial_year = ?")
            params.append(fy)
        if cost_centre and cost_centre != "All":
            where_clauses.append("cost_centre = ?")
            params.append(cost_centre)

        filter_str = (" AND " + " AND ".join(where_clauses)) if where_clauses else ""

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Sales aggregate
            cursor.execute(f"""
                SELECT 
                    COUNT(*), 
                    COALESCE(SUM(gross_amount), 0), 
                    COALESCE(SUM(net_amount), 0), 
                    COALESCE(SUM(tax_amount), 0)
                FROM vouchers WHERE voucher_type = 'Sales' {filter_str}
            """, params)
            s_cnt, s_gross, s_net, s_tax = cursor.fetchone()

            # Purchase aggregate
            cursor.execute(f"""
                SELECT 
                    COUNT(*), 
                    COALESCE(SUM(gross_amount), 0), 
                    COALESCE(SUM(net_amount), 0), 
                    COALESCE(SUM(tax_amount), 0)
                FROM vouchers WHERE voucher_type = 'Purchase' {filter_str}
            """, params)
            p_cnt, p_gross, p_net, p_tax = cursor.fetchone()

            # Debit Notes
            cursor.execute(f"SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) FROM vouchers WHERE voucher_type = 'Debit Note' {filter_str}", params)
            dn_cnt, dn_gross = cursor.fetchone()

            # Credit Notes
            cursor.execute(f"SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) FROM vouchers WHERE voucher_type = 'Credit Note' {filter_str}", params)
            cn_cnt, cn_gross = cursor.fetchone()

            # Cash Inflow (Receipts) & Cash Outflow (Payments)
            cursor.execute(f"SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) FROM vouchers WHERE voucher_type = 'Receipt' {filter_str}", params)
            rec_cnt, cash_inflow = cursor.fetchone()

            cursor.execute(f"SELECT COUNT(*), COALESCE(SUM(gross_amount), 0) FROM vouchers WHERE voucher_type = 'Payment' {filter_str}", params)
            pay_cnt, cash_outflow = cursor.fetchone()

            net_cash_flow = cash_inflow - cash_outflow

            # Distinct counts & date ranges
            where_all = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            cursor.execute(f"""
                SELECT 
                    COUNT(*),
                    COUNT(DISTINCT party_name), 
                    COUNT(DISTINCT cost_centre),
                    MIN(date),
                    MAX(date)
                FROM vouchers
                {where_all}
            """, params)
            total_vch, total_parties, total_ccs, min_date, max_date = cursor.fetchone()

            gross_margin = s_gross - p_gross
            margin_pct = (gross_margin / s_gross * 100) if s_gross > 0 else 0.0

            # Fetch active company & snapshot metrics from metadata
            active_company = self.db.get_metadata("active_company")
            if not active_company:
                cursor.execute("SELECT party_name FROM vouchers WHERE party_name IS NOT NULL AND party_name != '' LIMIT 1")
                first_row = cursor.fetchone()
                active_company = first_row[0] if first_row else "LedgerGPT Company"

            raw_metrics = self.db.get_metadata("tally_metrics", "{}")
            try:
                t_metrics = json.loads(raw_metrics) if raw_metrics else {}
            except Exception:
                t_metrics = {}

            # Tally Balance Sheet & Cash Balances (strictly authentic, zero hardcoded fabrication)
            bank_bal = float(t_metrics.get("bank_balance", 0.0) or 0.0)
            cash_bal = float(t_metrics.get("cash_in_hand", 0.0) or 0.0)
            total_liquid = bank_bal + cash_bal
            current_assets = float(t_metrics.get("current_assets", 0.0) or 0.0)
            current_liabilities = float(t_metrics.get("current_liabilities", 0.0) or 0.0)
            working_capital = current_assets - current_liabilities
            current_ratio = round(current_assets / current_liabilities, 2) if current_liabilities > 0 else 0.0

            # Computed Cash Inflow and Outflow directly from vouchers
            display_inflow = round(cash_inflow, 2)
            display_outflow = round(cash_outflow, 2)
            display_net_flow = round(display_inflow - display_outflow, 2)

            sundry_debtors = float(t_metrics.get("sundry_debtors", 0.0) or 0.0)
            sundry_creditors = float(t_metrics.get("sundry_creditors", 0.0) or 0.0)
            turnover_days = round((sundry_debtors / s_gross) * 365, 2) if s_gross > 0 and sundry_debtors > 0 else 0.0

            return {
                "active_company": active_company,
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
                # Tally Specific Liquidity & Cash Flow
                "cash_in_hand": cash_bal,
                "cash_in_hand_formatted": format_inr(cash_bal),
                "bank_balance": bank_bal,
                "bank_balance_formatted": format_inr(bank_bal),
                "bank_name": t_metrics.get("bank_name", "Primary Bank"),
                "total_liquid_funds_formatted": format_inr(total_liquid),
                "cash_inflow": display_inflow,
                "cash_inflow_formatted": format_inr(display_inflow),
                "cash_outflow": display_outflow,
                "cash_outflow_formatted": format_inr(display_outflow),
                "net_cash_flow": display_net_flow,
                "net_cash_flow_formatted": format_inr(display_net_flow),
                # Balance Sheet & Ratios
                "current_assets": current_assets,
                "current_assets_formatted": format_inr(current_assets),
                "current_liabilities": current_liabilities,
                "current_liabilities_formatted": format_inr(current_liabilities),
                "working_capital_formatted": format_inr(working_capital),
                "current_ratio": current_ratio,
                "receivable_turnover_days": turnover_days,
                "receivables_formatted": format_inr(sundry_debtors),
                "payables_formatted": format_inr(sundry_creditors),
            }

    def get_monthly_trend(self, fy=None, cost_centre=None):
        """Returns monthly time series of Sales vs Purchases and Margin."""
        where_clauses = ["date IS NOT NULL AND date != ''"]
        params = []
        if fy and fy != "All":
            where_clauses.append("financial_year = ?")
            params.append(fy)
        if cost_centre and cost_centre != "All":
            where_clauses.append("cost_centre = ?")
            params.append(cost_centre)

        where_str = " AND ".join(where_clauses)

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            query = f"""
                SELECT 
                    strftime('%Y-%m', date) as ym,
                    MAX(month_year) as month_label,
                    SUM(CASE WHEN voucher_type = 'Sales' THEN gross_amount ELSE 0 END) as sales,
                    SUM(CASE WHEN voucher_type = 'Purchase' THEN gross_amount ELSE 0 END) as purchase,
                    COUNT(*) as total_vouchers
                FROM vouchers
                WHERE {where_str}
                GROUP BY strftime('%Y-%m', date)
                ORDER BY ym ASC
            """
            cursor.execute(query, params)
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

    def get_rankings(self, top_n=10, fy=None, cost_centre=None):
        """Returns Top Debtors, Top Creditors, and Top Cost Centres."""
        where_clauses_base = []
        params_base = []
        if fy and fy != "All":
            where_clauses_base.append("financial_year = ?")
            params_base.append(fy)
        if cost_centre and cost_centre != "All":
            where_clauses_base.append("cost_centre = ?")
            params_base.append(cost_centre)

        filter_base = (" AND " + " AND ".join(where_clauses_base)) if where_clauses_base else ""

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Top Clients (Sales)
            cursor.execute(f"""
                SELECT party_name, SUM(gross_amount) as total_val, COUNT(*) as vch_count
                FROM vouchers
                WHERE voucher_type = 'Sales' AND party_name != 'Sundry Party' AND party_name != '' {filter_base}
                GROUP BY party_name
                ORDER BY total_val DESC
                LIMIT ?
            """, params_base + [top_n])
            debtors = [
                {
                    "party_name": r[0],
                    "amount": round(r[1], 2),
                    "amount_formatted": format_inr(r[1]),
                    "voucher_count": r[2]
                }
                for r in cursor.fetchall()
            ]

            # Top Vendors (Purchases)
            cursor.execute(f"""
                SELECT party_name, SUM(gross_amount) as total_val, COUNT(*) as vch_count
                FROM vouchers
                WHERE voucher_type = 'Purchase' AND party_name != 'Sundry Party' AND party_name != '' {filter_base}
                GROUP BY party_name
                ORDER BY total_val DESC
                LIMIT ?
            """, params_base + [top_n])
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
            cursor.execute(f"""
                SELECT 
                    cost_centre,
                    SUM(CASE WHEN voucher_type = 'Sales' THEN gross_amount ELSE 0 END) as s_val,
                    SUM(CASE WHEN voucher_type = 'Purchase' THEN gross_amount ELSE 0 END) as p_val,
                    COUNT(*) as vch_count
                FROM vouchers
                WHERE cost_centre IS NOT NULL AND cost_centre != '' AND cost_centre != 'General / Untagged' {filter_base}
                GROUP BY cost_centre
                HAVING s_val > 0 OR p_val > 0
                ORDER BY s_val DESC
                LIMIT ?
            """, params_base + [top_n])
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

    def get_vouchers_grid(self, page=1, page_size=50, vtype=None, search=None, fy=None, cost_centre=None):
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

        if cost_centre and cost_centre != "All":
            where_clauses.append("cost_centre = ?")
            params.append(cost_centre)

        if search and search.strip():
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

    def get_aging_summary(self, nature="all", cost_centre=None, fy=None):
        """
        Computes Bill-by-Bill Debtor & Creditor Aging Buckets:
        - 0-30 Days (Current)
        - 31-60 Days
        - 61-90 Days
        - 90+ Days (Critical / High Risk)
        Uses live bills_outstanding table if populated, with fallback to vouchers.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM bills_outstanding")
            has_bills = cursor.fetchone()[0] > 0

            if has_bills:
                where_clauses = ["1=1"]
                params = []
                if nature and nature.lower() in ["receivable", "payable"]:
                    where_clauses.append("LOWER(bill_type) = LOWER(?)")
                    params.append(nature)
                if cost_centre and cost_centre != "All":
                    where_clauses.append("cost_centre = ?")
                    params.append(cost_centre)
                if fy and fy != "All":
                    import re
                    m = re.search(r"(\d{4})[-_](\d{2,4})", fy)
                    if m:
                        start_yr = int(m.group(1))
                        end_yr = start_yr + 1 if len(m.group(2)) == 2 else int(m.group(2))
                        where_clauses.append("bill_date >= ? AND bill_date <= ?")
                        params.extend([f"{start_yr:04d}-04-01", f"{end_yr:04d}-03-31"])

                where_str = " AND ".join(where_clauses)
                cursor.execute(f"""
                    SELECT bill_type, bill_date, bill_ref, party_name, outstanding_amount, overdue_days, cost_centre
                    FROM bills_outstanding
                    WHERE {where_str}
                    ORDER BY overdue_days DESC, outstanding_amount DESC
                """, params)
                raw_bills = cursor.fetchall()
            else:
                raw_bills = self._calculate_fallback_aging(cost_centre=cost_centre, fy=fy)

            rec_buckets = {"0_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0, "total": 0.0, "count": 0}
            pay_buckets = {"0_30": 0.0, "31_60": 0.0, "61_90": 0.0, "90_plus": 0.0, "total": 0.0, "count": 0}
            detailed_list = []

            for r in raw_bills:
                b_type, b_date, b_ref, party, amt, days, cc = r[0], r[1], r[2], r[3], float(r[4] or 0), int(r[5] or 0), r[6]
                if days <= 30:
                    bucket = "0-30 Days"
                    key = "0_30"
                    risk = "LOW"
                elif days <= 60:
                    bucket = "31-60 Days"
                    key = "31_60"
                    risk = "MODERATE"
                elif days <= 90:
                    bucket = "61-90 Days"
                    key = "61_90"
                    risk = "ELEVATED"
                else:
                    bucket = "90+ Days"
                    key = "90_plus"
                    risk = "CRITICAL"

                if b_type.lower() == "receivable":
                    rec_buckets[key] += amt
                    rec_buckets["total"] += amt
                    rec_buckets["count"] += 1
                else:
                    pay_buckets[key] += amt
                    pay_buckets["total"] += amt
                    pay_buckets["count"] += 1

                detailed_list.append({
                    "bill_type": b_type,
                    "bill_date": b_date,
                    "bill_ref": b_ref or "-",
                    "party_name": party,
                    "outstanding_amount": amt,
                    "outstanding_formatted": format_inr(amt),
                    "overdue_days": days,
                    "aging_bucket": bucket,
                    "risk_level": risk,
                    "cost_centre": cc or "General"
                })

            return {
                "summary": {
                    "receivables": {
                        "total": rec_buckets["total"],
                        "total_formatted": format_inr(rec_buckets["total"]),
                        "count": rec_buckets["count"],
                        "bucket_0_30": rec_buckets["0_30"],
                        "bucket_0_30_formatted": format_inr(rec_buckets["0_30"]),
                        "bucket_31_60": rec_buckets["31_60"],
                        "bucket_31_60_formatted": format_inr(rec_buckets["31_60"]),
                        "bucket_61_90": rec_buckets["61_90"],
                        "bucket_61_90_formatted": format_inr(rec_buckets["61_90"]),
                        "bucket_90_plus": rec_buckets["90_plus"],
                        "bucket_90_plus_formatted": format_inr(rec_buckets["90_plus"]),
                    },
                    "payables": {
                        "total": pay_buckets["total"],
                        "total_formatted": format_inr(pay_buckets["total"]),
                        "count": pay_buckets["count"],
                        "bucket_0_30": pay_buckets["0_30"],
                        "bucket_0_30_formatted": format_inr(pay_buckets["0_30"]),
                        "bucket_31_60": pay_buckets["31_60"],
                        "bucket_31_60_formatted": format_inr(pay_buckets["31_60"]),
                        "bucket_61_90": pay_buckets["61_90"],
                        "bucket_61_90_formatted": format_inr(pay_buckets["61_90"]),
                        "bucket_90_plus": pay_buckets["90_plus"],
                        "bucket_90_plus_formatted": format_inr(pay_buckets["90_plus"]),
                    }
                },
                "bills": detailed_list
            }

    def _calculate_fallback_aging(self, cost_centre=None, fy=None):
        """Fallback aging calculation from vouchers when bills_outstanding is empty."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            where_clauses = ["party_name IS NOT NULL AND party_name != '' AND party_name != 'Sundry Party'"]
            params = []
            if fy and fy != "All":
                where_clauses.append("financial_year = ?")
                params.append(fy)
            if cost_centre and cost_centre != "All":
                where_clauses.append("cost_centre = ?")
                params.append(cost_centre)

            where_str = " AND ".join(where_clauses)
            cursor.execute(f"""
                SELECT party_name,
                       SUM(CASE WHEN LOWER(voucher_type) IN ('sales', 'payment', 'debit note') THEN gross_amount ELSE 0 END) as dr,
                       SUM(CASE WHEN LOWER(voucher_type) IN ('purchase', 'receipt', 'credit note') THEN gross_amount ELSE 0 END) as cr,
                       MAX(date) as last_date,
                       cost_centre
                FROM vouchers
                WHERE {where_str}
                GROUP BY party_name
            """, params)
            rows = cursor.fetchall()

            as_of = datetime.now()
            fallback_bills = []
            for party, dr, cr, ldate, cc in rows:
                diff = (dr or 0) - (cr or 0)
                days = 0
                if ldate:
                    try:
                        days = (as_of - datetime.strptime(ldate, "%Y-%m-%d")).days
                    except Exception:
                        days = 0

                if diff > 10.0:
                    fallback_bills.append(("Receivable", ldate or "2026-10-01", "AUTO-REC", party, diff, max(days, 0), cc))
                elif diff < -10.0:
                    fallback_bills.append(("Payable", ldate or "2026-10-01", "AUTO-PAY", party, abs(diff), max(days, 0), cc))

            return fallback_bills

    def get_cfo_mis_pack(self, fy=None, cost_centre=None):
        """Assembles comprehensive executive CFO MIS board pack."""
        summary = self.get_executive_summary(fy=fy, cost_centre=cost_centre)
        aging = self.get_aging_summary(nature="all", cost_centre=cost_centre, fy=fy)
        rankings = self.get_rankings(top_n=10, fy=fy, cost_centre=cost_centre)
        monthly = self.get_monthly_trend(fy=fy, cost_centre=cost_centre)
        active_co = self.db.get_metadata("active_company") or "LedgerGPT Operating Entity"

        return {
            "report_title": f"CFO Executive MIS Report - {active_co}",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "company_name": active_co,
            "period": fy or "All Fiscal Periods",
            "cost_centre": cost_centre or "All Sites",
            "executive_summary": summary,
            "aging_overview": aging["summary"],
            "top_debtors": rankings["top_debtors"],
            "top_creditors": rankings["top_creditors"],
            "monthly_performance": monthly,
            "critical_overdue_bills": [b for b in aging["bills"] if b["risk_level"] == "CRITICAL"][:15]
        }
