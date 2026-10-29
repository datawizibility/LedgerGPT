"""
Financial Formatters & Indian Numbering Utilities.
"""

from datetime import datetime
from ledgergpt.config import CURRENCY_SYMBOL

def format_inr(val, format_type="auto"):
    """
    Format a number into Indian Currency (₹ Lakhs, Crores, or comma-separated).
    Examples:
      format_inr(907227064) -> '₹ 90.72 Cr'
      format_inr(5007718)   -> '₹ 50.08 L'
      format_inr(45000, 'full') -> '₹ 45,000.00'
    """
    if val is None:
        return f"{CURRENCY_SYMBOL} 0.00"
    try:
        num = float(val)
    except (ValueError, TypeError):
        return str(val)

    is_negative = num < 0
    abs_num = abs(num)

    if format_type == "auto":
        if abs_num >= 10000000: # 1 Crore+
            cr_val = abs_num / 10000000
            s = f"{CURRENCY_SYMBOL} {cr_val:,.2f} Cr"
        elif abs_num >= 100000: # 1 Lakh+
            l_val = abs_num / 100000
            s = f"{CURRENCY_SYMBOL} {l_val:,.2f} L"
        else:
            s = f"{CURRENCY_SYMBOL} {indian_number_format(abs_num)}"
    elif format_type == "words":
        if abs_num >= 10000000:
            s = f"{CURRENCY_SYMBOL} {abs_num / 10000000:,.2f} Crores"
        elif abs_num >= 100000:
            s = f"{CURRENCY_SYMBOL} {abs_num / 100000:,.2f} Lakhs"
        else:
            s = f"{CURRENCY_SYMBOL} {indian_number_format(abs_num)}"
    else: # 'full'
        s = f"{CURRENCY_SYMBOL} {indian_number_format(abs_num)}"

    return f"-{s}" if is_negative else s

def indian_number_format(num):
    """Formats a float/int into Indian numbering (e.g. 12,34,567.89)."""
    parts = f"{num:.2f}".split(".")
    int_part = parts[0]
    dec_part = parts[1]

    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted_int = ",".join(groups) + "," + last3

    return f"{formatted_int}.{dec_part}"

def get_financial_year(dt_obj):
    """Returns 'FY 2017-18' given a datetime or date object."""
    year = dt_obj.year
    if dt_obj.month >= 4:
        return f"FY {year}-{str(year + 1)[-2:]}"
    else:
        return f"FY {year - 1}-{str(year)[-2:]}"

def get_financial_quarter(dt_obj):
    """Returns 'Q1' (Apr-Jun), 'Q2' (Jul-Sep), 'Q3' (Oct-Dec), 'Q4' (Jan-Mar)."""
    m = dt_obj.month
    if 4 <= m <= 6:
        return "Q1"
    elif 7 <= m <= 9:
        return "Q2"
    elif 10 <= m <= 12:
        return "Q3"
    else:
        return "Q4"

def parse_date(date_str):
    """Flexibly parse multiple date formats commonly found in Tally/ERP."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d",
        "%d-%b-%Y", "%d-%b-%y", "%b %Y", "%B %Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None
