"""
LedgerGPT Configuration and Environment Settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Database Path
DB_PATH = os.getenv("LEDGERGPT_DB_PATH", str(BASE_DIR / "ledgergpt.db"))

# Sample Data Directory
SAMPLE_DATA_DIR = os.getenv("LEDGERGPT_SAMPLE_DIR", str(BASE_DIR / "sample_data"))

# Tally Prime Defaults
TALLY_HOST = os.getenv("TALLY_HOST", "localhost")
TALLY_PORT = int(os.getenv("TALLY_PORT", "9000"))
TALLY_URL = f"http://{TALLY_HOST}:{TALLY_PORT}"

# LLM Configuration
LLM_PROVIDER = os.getenv("LEDGERGPT_LLM_PROVIDER", "rule_only").lower() # rule_only, gemini, openai, anthropic, ollama
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

# Web Server Configuration
WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
WEB_PORT = int(os.getenv("WEB_PORT", "5000"))
WEB_DEBUG = os.getenv("WEB_DEBUG", "False").lower() in ("true", "1", "t")

# Financial & Number Format Preferences
CURRENCY_SYMBOL = "₹"
FY_START_MONTH = 4  # April (Indian Financial Year standard)
DEFAULT_PAGE_SIZE = 100
