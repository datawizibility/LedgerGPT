# LedgerGPT How-To Guide & Recipes 🛠️
> **Practical, step-by-step guides for everyday accounting, audit, and engineering workflows.**

---

## Index of Recipes
1. [How to Sync Live Data from Tally Prime](#recipe-1-how-to-sync-live-data-from-tally-prime)
2. [How to Ingest CSV / Excel Registers](#recipe-2-how-to-ingest-csv--excel-registers)
3. [How to Perform Section 269SS & 269T Tax Audit Checks (Form 3CD Clause 31)](#recipe-3-how-to-perform-section-269ss--269t-tax-audit-checks-form-3cd-clause-31)
4. [How to Detect and Audit Negative Cash Balances](#recipe-4-how-to-detect-and-audit-negative-cash-balances)
5. [How to Generate a Complete Party Ledger Statement](#recipe-5-how-to-generate-a-complete-party-ledger-statement)
6. [How to Export a CFO MIS Board Pack to Excel / CSV](#recipe-6-how-to-export-a-cfo-mis-board-pack-to-excel--csv)
7. [How to Use the Interactive Command-Line Interface (CLI)](#recipe-7-how-to-use-the-interactive-command-line-interface-cli)
8. [How to Configure LLM Providers (Gemini / OpenAI / Ollama)](#recipe-8-how-to-configure-llm-providers-gemini--openai--ollama)
9. [How to Automate Forensic Scans in Python Scripts](#recipe-9-how-to-automate-forensic-scans-in-python-scripts)

---

## Recipe 1: How to Sync Live Data from Tally Prime

### Step 1: Prepare Tally Prime
1. Start **Tally Prime** on your workstation or LAN server.
2. Open the company you want to inspect (e.g. `BHARAT VANIJYA EASTERN PRIVATE LIMITED (LATEHAR)`).
3. Ensure Tally's XML/ODBC port is active on port **9000**:
   * Navigate to `F1: Help` -> `Settings` -> `Connectivity`.
   * Under **Client/Server Configuration**, verify:
     * *TallyPrime acts as*: **Both**
     * *Enable ODBC*: **Yes**
     * *Port*: **9000**

### Step 2: Sync via Web Cockpit
1. Open `http://127.0.0.1:5000` in your browser.
2. Click **`⚡ Sync Tally`** in the navigation header.
3. Select your active company from the dropdown.
4. Click **`Start Sync`**.
5. Once complete, click **`Reload Dashboard`**. All KPIs, aging buckets, liquidity cards, and vouchers will refresh immediately.

### Step 3: Sync via Python Script
```python
from ledgergpt.tally_sync import TallySyncClient
from ledgergpt.db import FinancialDB

db = FinancialDB("ledgergpt.db")
client = TallySyncClient(port=9000)

# Check connection
status = client.check_connection()
print("Connection:", status)

# Run full sync for company
result = client.sync(db, company_name="BHARAT VANIJYA EASTERN PRIVATE LIMITED (LATEHAR)")
print(f"Synced {result['vouchers_synced']} vouchers and {result['bills_synced']} outstanding bills!")
```

---

## Recipe 2: How to Ingest CSV / Excel Registers

LedgerGPT includes an **intelligent fuzzy column normalizer** that automatically maps variations of column headers from any ERP or accounting software.

### From Command Line:
```powershell
python cli.py --ingest "path\to\Sales_Register_2024_25.csv"
```
Or for Excel files:
```powershell
python cli.py --ingest "path\to\Purchase_Register.xlsx"
```

### Supported Header Synonyms:
* **Date**: `Date`, `Invoice Date`, `Bill Date`, `Vch Date`, `Voucher Date`
* **Voucher Type**: `Type`, `Vch Type`, `Voucher Type`, `Transaction Type`
* **Party Name**: `Party`, `Party Name`, `Customer Name`, `Vendor Name`, `Supplier`, `Particulars`
* **Amount**: `Amount`, `Gross Amount`, `Net Amount`, `Debit Amount`, `Credit Amount`, `Total Value`
* **Reference**: `Bill No`, `Invoice No`, `Ref No`, `Reference`, `Challan No`
* **Narration**: `Narration`, `Remarks`, `Description`, `Particulars`

---

## Recipe 3: How to Perform Section 269SS & 269T Tax Audit Checks (Form 3CD Clause 31)

Under Sections 269SS and 269T of the Indian Income Tax Act, accepting or repaying loans, deposits, or specified advances in cash of **₹ 20,000 or more** is prohibited and attracts penalty under Section 271D / 271E.

### Method A: Via Web Cockpit
1. Click **`🔍 Forensic Scanner`** in the top navigation bar.
2. Scroll to the **Section 269SS & 269T Violations** card.
3. Review flagged cash transactions (Date, Voucher Number, Party Name, Loan/Advance Account, Amount, and Narration).

### Method B: Via Natural Language Query
In the copilot chat box, type:
```text
Scan Section 269SS and 269T cash loan violations
```
Or:
```text
Form 3CD Clause 31
```
LedgerGPT executes deterministic scanning and renders the violation table instantly with a 1-click CSV download.

---

## Recipe 4: How to Detect and Audit Negative Cash Balances

A negative cash balance indicates unrecorded cash receipts, omitted transfers, or backdated payments, creating substantial tax audit exposure.

### In the Web Copilot:
Type:
```text
Negative cash balance
```
Or:
```text
Show negative cash balance days
```
LedgerGPT chronologically reconstructs the running balance of all cash-in-hand accounts day-by-day and flags every instance where cash dropped below ₹ 0.00.

---

## Recipe 5: How to Generate a Complete Party Ledger Statement

To view an authentic, double-entry ledger account statement for any vendor, customer, or employee:

### Example Inquiries:
```text
Ajay Kumar ledger
```
```text
Show Bennett Coleman statement
```
```text
Arun Automobiles ledger account
```

### What You Receive:
1. **Summary Banner**: Total Transactions, Total Debits, Total Credits, and Net Closing Balance (with Dr/Cr indicator).
2. **Chronological Transaction Schedule**:
   * Date
   * Voucher Type
   * Voucher No & Reference
   * Particulars (Contra Ledger)
   * Debit Amount (₹)
   * Credit Amount (₹)
   * Cumulative Running Balance (₹)
   * Narration Trace
3. **1-Click CSV Export**: Download the statement for reconciliation or dispatch to the client/vendor.

---

## Recipe 6: How to Export a CFO MIS Board Pack to Excel / CSV

To generate a comprehensive management information digest for board meetings or executive reviews:

1. Click the **`📑 CFO MIS Pack`** button located at the top right of the navigation header.
2. The browser immediately downloads a file named:
   ```
   CFO_MIS_Board_Pack_YYYYMMDD_HHMMSS.csv
   ```
3. Open the file in Microsoft Excel or Google Sheets. It contains pre-organized sections:
   * **Executive Summary & Margin Overview**
   * **Liquidity & Working Capital Cockpit**
   * **Receivables & Payables Aging Buckets (0-30, 31-60, 61-90, 90+ days)**
   * **Top 10 Debtors (Gross Revenue)**
   * **Top 10 Creditors (Total Procurements)**
   * **Critical Overdue Invoices (> 90 Days)**

---

## Recipe 7: How to Use the Interactive Command-Line Interface (CLI)

For system administrators, auditors, or automated shell pipelines:

### Launch Interactive Mode:
```powershell
python cli.py
```
```
LedgerGPT CLI Interactive Mode
Type your financial inquiry in plain English, or 'exit' to quit.

ledgergpt> Top 5 clients by revenue
ledgergpt> Show creditors aging
ledgergpt> Cash inflow and outflow
ledgergpt> Scan Section 269SS cash loans
```

### Single-Command Mode:
```powershell
python cli.py -q "What is our total sales in FY 2024-25?"
```

### Quick KPI Report:
```powershell
python cli.py --kpis
```

### Full Forensic Scan:
```powershell
python cli.py --forensic
```

---

## Recipe 8: How to Configure LLM Providers (Gemini / OpenAI / Ollama)

While common queries run deterministically in $<5$ ms without any API key, you can activate LLM-powered Text-to-SQL for unstructured, complex inquiries.

### Step 1: Create `.env` file in the project root:
```ini
# Choose provider: gemini | openai | anthropic | ollama
LLM_PROVIDER=gemini

# For Google Gemini:
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# For OpenAI:
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini

# For Local Offline Ollama (Zero Cloud API):
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
```

### Step 2: Safety & Security
* LedgerGPT wraps all generated SQL queries in a **Read-Only SQL Validator**.
* Any query containing `UPDATE`, `DELETE`, `DROP`, `ALTER`, or `INSERT` is automatically blocked.

---

## Recipe 9: How to Automate Forensic Scans in Python Scripts

You can incorporate LedgerGPT's audit checks into scheduled nightly batch jobs:

```python
from ledgergpt.db import FinancialDB
from ledgergpt.forensic import ForensicScanner

db = FinancialDB("ledgergpt.db")
scanner = ForensicScanner(db)

# 1. Check Section 269SS violations
sec269 = scanner.detect_section_269ss_269t_violations(threshold=20000)
if sec269["violations_found"]:
    print(f"ALERT: {sec269['total_violations']} cash loan violations detected!")
    for v in sec269["violations"]:
        print(f" - {v['date']}: {v['party_name']} ₹ {v['amount']}")

# 2. Check Negative Cash
neg_cash = scanner.detect_negative_cash_balances()
if neg_cash["violations_found"]:
    print(f"ALERT: {neg_cash['total_negative_days']} days with negative cash balance!")

# 3. Check High-Value Round-Sum Payments
round_sum = scanner.detect_round_sum_transactions(threshold=100000)
print(f"Flagged {round_sum['count']} round-sum transactions.")
```

---
*For questions or enterprise customization, contact the Datawizibility engineering team.*
