#!/usr/bin/env python3
"""
LedgerGPT Command Line Interface (CLI).
Interactive Terminal Chat & Deterministic Financial Querying.
Packaged as module for setuptools console_scripts support.
"""

import sys
import io
import argparse
from ledgergpt import __version__
from ledgergpt.db import FinancialDB
from ledgergpt.query_engine import QueryEngine
from ledgergpt.forensic import ForensicScanner
from ledgergpt.ingestor import DataIngestor
from ledgergpt.formatters import format_inr
from ledgergpt.config import SAMPLE_DATA_DIR
from ledgergpt.tally_sync import TallySyncEngine

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def print_banner():
    print("=" * 80)
    print("  LEDGERGPT — Zero-Hallucination Conversational Finance Engine")
    print(f"  Deterministic ERP & Tally Prime Intelligence | Version {__version__}")
    print("=" * 80)

def interactive_chat():
    db = FinancialDB()
    engine = QueryEngine(db=db)
    print_banner()
    
    kpis = db.get_kpis()
    print(f"Connected Database: {kpis.get('total_vouchers', 0):,} Vouchers")
    print(f"Sales: {format_inr(kpis.get('total_sales_gross', 0))} | Purchases: {format_inr(kpis.get('total_purchase_gross', 0))}")
    print("\nType your question in natural English (or 'exit' / 'quit' to leave):")
    print("Example: 'Total sales FY 2017-18', 'Top 5 clients', 'Debit notes', 'Purchases'\n")

    while True:
        try:
            q = input("\nLedgerGPT > ").strip()
            if not q:
                continue
            if q.lower() in ("exit", "quit", "q"):
                print("Exiting LedgerGPT. Goodbye!")
                break

            res = engine.process_query(q)
            print("-" * 80)
            print(f"ANSWER: {res['answer']}")
            print(f"ENGINE: {res.get('source', 'Deterministic')} ({res.get('execution_time_ms', 0)} ms)")
            if res.get("sql"):
                print(f"SQL:    {res['sql']}")
            
            data = res.get("data", [])
            if data:
                print(f"\nBreakdown (Showing top {min(10, len(data))} of {len(data)} rows):")
                cols = res.get("columns", list(data[0].keys()))[:6] # display up to 6 cols in CLI
                hdr_str = " | ".join(f"{c:>18}" for c in cols)
                print(hdr_str)
                print("-" * len(hdr_str))
                for row in data[:10]:
                    vals = []
                    for c in cols:
                        v = row.get(c, "")
                        if isinstance(v, (int, float)):
                            vals.append(f"{v:>18,.2f}")
                        else:
                            vals.append(f"{str(v)[:18]:>18}")
                    print(" | ".join(vals))
            print("-" * 80)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting LedgerGPT.")
            break

def main():
    parser = argparse.ArgumentParser(description="LedgerGPT Financial Query CLI")
    parser.add_argument("--query", "-q", type=str, help="Single query to execute")
    parser.add_argument("--kpis", action="store_true", help="Display top-level financial KPIs")
    parser.add_argument("--forensic", action="store_true", help="Run full forensic audit scanner")
    parser.add_argument("--ingest", type=str, help="Ingest a CSV register into the database")
    parser.add_argument("--init-sample", "--seed-sample", dest="init_sample", action="store_true", help="Ingest preloaded sample data")
    parser.add_argument("--sync-tally", action="store_true", help="Sync vouchers live from active Tally Prime company")
    parser.add_argument("--company", type=str, help="Specify company name for Tally sync")
    parser.add_argument("--clear", action="store_true", help="Clear existing vouchers before sync or sample init")

    args = parser.parse_args()

    db = FinancialDB()

    if args.kpis:
        kpis = db.get_kpis()
        print("\n--- LEDGERGPT FINANCIAL METRICS ---")
        for k, v in kpis.items():
            if "gross" in k or "net" in k:
                print(f"  {k:30}: {format_inr(v)} ({v:,.2f})")
            else:
                print(f"  {k:30}: {v}")
        return

    if args.forensic:
        scanner = ForensicScanner(db=db)
        print("\nRunning Forensic Audit Scanner...")
        report = scanner.run_full_forensic_suite()
        s = report["summary"]
        print("\n--- FORENSIC FINDINGS SUMMARY ---")
        print(f"  Suspicious Narrations Flagged : {s['suspicious_narrations_count']}")
        print(f"  Round-Sum Payments (>=1L)     : {s['round_sum_vouchers_count']}")
        print(f"  Weekend-Dated Vouchers        : {s['weekend_vouchers_count']}")
        print(f"  Duplicate Bill Groups         : {s['duplicate_bill_groups']}")
        print(f"  Benford's Law Conformity      : {s['benford_conformity']}")
        return

    if args.ingest:
        ingestor = DataIngestor(db=db)
        cnt = ingestor.ingest_register_csv(args.ingest)
        print(f"[SUCCESS] Ingested {cnt:,} vouchers from {args.ingest}")
        return

    if args.init_sample:
        if args.clear:
            db.clear_vouchers()
            print("[INFO] Cleared existing vouchers.")
        ingestor = DataIngestor(db=db)
        cnt = ingestor.ingest_sample_dataset(SAMPLE_DATA_DIR)
        print(f"[SUCCESS] Ingested sample dataset: {cnt:,} total vouchers.")
        return

    if args.sync_tally:
        print("\nConnecting to Tally Prime on port 9000...")
        sync_engine = TallySyncEngine(db=db)
        res = sync_engine.sync(company_name=args.company, clear_existing=args.clear)
        if res.get("success"):
            print(f"[SUCCESS] {res.get('message')}")
            k = res.get("kpis", {})
            print(f"Total Vouchers in DB: {k.get('total_vouchers', 0):,}")
            print(f"Sales: {format_inr(k.get('total_sales_gross', 0))} | Purchases: {format_inr(k.get('total_purchase_gross', 0))}")
        else:
            print(f"[ERROR] {res.get('error')}")
        return

    if args.query:
        engine = QueryEngine(db=db)
        res = engine.process_query(args.query)
        print(f"\nQuery:  {args.query}")
        print(f"Answer: {res['answer']}")
        if res.get("sql"):
            print(f"SQL:    {res['sql']}")
        print(f"Time:   {res.get('execution_time_ms', 0)} ms")
        return

    # Default to interactive chat
    interactive_chat()

if __name__ == "__main__":
    main()
