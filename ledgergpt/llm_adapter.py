"""
Multi-Model LLM Adapter for LedgerGPT.
Supports Offline Rule-Only, Google Gemini, OpenAI, Anthropic Claude, and Local Ollama.
Uses lightweight direct HTTP requests to avoid heavy external SDK dependencies.
"""

import json
import requests
from ledgergpt.config import (
    LLM_PROVIDER, GEMINI_API_KEY, OPENAI_API_KEY,
    ANTHROPIC_API_KEY, OLLAMA_URL, OLLAMA_MODEL
)

class LLMAdapter:
    def __init__(self, provider=None, api_key=None):
        self.provider = (provider or LLM_PROVIDER).lower()
        self.api_key = api_key or self._get_default_key()

    def _get_default_key(self):
        if self.provider == "gemini":
            return GEMINI_API_KEY
        elif self.provider == "openai":
            return OPENAI_API_KEY
        elif self.provider == "anthropic":
            return ANTHROPIC_API_KEY
        return ""

    def generate_sql(self, natural_query, schema_context):
        """
        Translates a natural language question into a read-only SQLite query.
        Returns the raw SQL string or None.
        """
        if self.provider == "rule_only" or not self.api_key and self.provider != "ollama":
            return None

        prompt = f"""You are a specialized Text-to-SQL engine for an Indian ERP / Tally accounting SQLite database.
Your job is to convert the user's natural language question into a single, valid, read-only SQLite SELECT query.

{schema_context}

CRITICAL RULES:
1. ONLY return a raw SQLite query. DO NOT wrap with markdown code blocks (no ```sql). DO NOT provide explanations.
2. Only generate SELECT queries. NEVER generate INSERT, UPDATE, DELETE, or DROP.
3. For amounts, use net_amount or gross_amount according to context (gross_amount includes tax).
4. For Indian Financial Years, remember Q1 is Apr-Jun, Q2 is Jul-Sep, Q3 is Oct-Dec, Q4 is Jan-Mar.
5. In SQLite, use LIKE with '%' for case-insensitive partial string matching on party_name, primary_ledger, cost_centre, narration.
6. Use LIMIT 100 by default unless the user asks for 'all' or a specific count.

Question: {natural_query}
SQL Query:"""

        try:
            if self.provider == "gemini":
                return self._call_gemini(prompt)
            elif self.provider == "openai":
                return self._call_openai(prompt)
            elif self.provider == "anthropic":
                return self._call_anthropic(prompt)
            elif self.provider == "ollama":
                return self._call_ollama(prompt)
        except Exception as e:
            print(f"[LLM ERROR] {self.provider}: {e}")
            return None

        return None

    def _call_gemini(self, prompt):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 300}
        }
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return self._clean_sql(text)
        return None

    def _call_openai(self, prompt):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 300
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            return self._clean_sql(text)
        return None

    def _call_anthropic(self, prompt):
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0.0
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            text = data["content"][0]["text"].strip()
            return self._clean_sql(text)
        return None

    def _call_ollama(self, prompt):
        url = f"{OLLAMA_URL}/api/generate"
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0}
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            text = data.get("response", "").strip()
            return self._clean_sql(text)
        return None

    def _clean_sql(self, text):
        """Cleans markdown fencing from LLM SQL output."""
        clean = text.strip()
        if clean.startswith("```sql"):
            clean = clean[6:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip().rstrip(";")
