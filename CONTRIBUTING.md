# Contributing to LedgerGPT

Thank you for considering contributing! LedgerGPT is built for the Indian accounting and finance community — every contribution makes trustworthy AI-assisted auditing more accessible.

## How to Contribute

### 🐛 Report Bugs
Open an issue with:
- What you asked LedgerGPT (the exact query)
- What it returned vs what your books show
- Your environment (OS, Python version, Tally Prime version if relevant)

### 💡 Suggest Features
Open an issue tagged `enhancement`. Check the [Roadmap](README.md#%EF%B8%8F-roadmap) first — if it's listed, add a 👍 to the tracking issue instead.

### 🔧 Code Contributions
1. Fork the repo and create a branch: `git checkout -b feature/your-feature`
2. Follow the **Deterministic-First principle**: LLM output must never invent numbers — every figure comes from a verified SQLite query
3. Add tests in `tests/` for any new query pattern or scanner rule
4. Run the existing test suite before submitting
5. Submit a Pull Request with a clear description of what and why

### 📜 Code of Conduct
Be respectful. This is a community of accountants, auditors, and developers — many are new to open source.

## Areas That Need Help
- More deterministic query patterns (regional business phrasings, Hindi/Hinglish finance terms)
- Additional statutory scanner rules (TDS, GST, MCA filings)
- Documentation translations
- Test data generators (anonymized sample ledgers)

---

*By contributing, you agree your contributions are licensed under the MIT License.*
