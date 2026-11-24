"""LLM clients. Groq (free tier) by default; Claude if ANTHROPIC_API_KEY is set (stronger writing, paid)."""
import json, os, re, time
import requests

def _loads(text):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            raise
        return json.loads(m.group(0))

class GroqLLM:
    def __init__(self, model=None, api_key=None):
        self.model = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.key = api_key or os.environ["GROQ_API_KEY"]

    def json(self, system, user, temperature=0.4, max_tokens=3500):
        last = None
        for attempt in range(6):
            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": "Bearer " + self.key},
                json={"model": self.model,
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                      "temperature": temperature, "max_tokens": max_tokens,
                      "response_format": {"type": "json_object"}},
                timeout=120)
            if r.status_code == 429 or r.status_code >= 500:
                last = r.status_code
                time.sleep(min(60, 10 * (attempt + 1)))      # free tier is rate limited per minute: wait it out
                continue
            r.raise_for_status()
            return _loads(r.json()["choices"][0]["message"]["content"])
        raise RuntimeError("Groq unavailable after retries (last status %s)" % last)

class ClaudeLLM:
    def __init__(self, model=None, api_key=None):
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        self.key = api_key or os.environ["ANTHROPIC_API_KEY"]

    def json(self, system, user, temperature=0.4, max_tokens=3500):
        last = None
        for attempt in range(5):
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": self.model, "max_tokens": max(max_tokens, 1500), "temperature": temperature,
                      "system": system + "\nReply with a single JSON object only, no prose and no code fences.",
                      "messages": [{"role": "user", "content": user}]},
                timeout=180)
            if r.status_code in (429, 500, 502, 503, 529):
                last = r.status_code
                time.sleep(min(60, 8 * (attempt + 1)))
                continue
            r.raise_for_status()
            return _loads("".join(b.get("text", "") for b in r.json()["content"] if b.get("type") == "text"))
        raise RuntimeError("Claude API unavailable after retries (last status %s)" % last)

def make_llm(cfg):
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeLLM(cfg.get("anthropic_model"))
    if os.environ.get("GROQ_API_KEY"):
        return GroqLLM(cfg.get("model"))
    return None
