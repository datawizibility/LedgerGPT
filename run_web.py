#!/usr/bin/env python3
"""
1-Click Web Application Launcher for LedgerGPT.
"""

import sys
import io
import os

# Ensure current directory is on python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from ledgergpt.web.app import run

if __name__ == "__main__":
    run()
