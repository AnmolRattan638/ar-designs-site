"""Groq client (OpenAI-compatible). Free tier friendly: few calls, retry on 429."""
import json, os, time
import requests

class GroqLLM:
    def __init__(self, model=None, api_key=None):
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.key = api_key or os.environ["GROQ_API_KEY"]

    def json(self, system, user, temperature=0.4, max_tokens=3500):
        last = None
        for attempt in range(4):
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": "Bearer " + self.key},
                json={"model": self.model,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                      "temperature": temperature, "max_tokens": max_tokens,
                      "response_format": {"type": "json_object"}},
                timeout=90)
            if r.status_code == 429 or r.status_code >= 500:
                last = r.status_code
                time.sleep(6 * (attempt + 1))
                continue
            r.raise_for_status()
            return json.loads(r.json()["choices"][0]["message"]["content"])
        raise RuntimeError("Groq unavailable after retries (last status %s)" % last)
