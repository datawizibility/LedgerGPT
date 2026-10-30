#!/usr/bin/env python3
"""
LedgerGPT CLI Root Launcher.
Delegates to packaged `ledgergpt.cli.main`.
"""

import sys
import os

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ledgergpt.cli import main, print_banner

if __name__ == "__main__":
    main()
