"""Fact-check: deterministic rules first (cheap, strict), then an LLM claim check."""
import json, re

MONEY = re.compile(r"(?:₹|rs\.?\s?|inr\s?|\$|usd\s?)\s?(\d[\d,]*(?:\.\d+)?)", re.I)
HOURS = re.compile(r"(\d+)\s*[- ]?\s*hours?\b", re.I)
BANNED = [r"guarantee", r"#\s?1\b", r"number one", r"top[- ]rated", r"\baward", r"testimonial",
          r"our clients include", r"thousands of", r"\b\d{3,}\+?\s+(?:clients|customers|businesses|leads)",
          r"rank(?:s|ing)?\s+(?:#|number|first|on page one)", r"overnight", r"instantly rank",
          r"our (?:office|team of)", r"visit (?:us|our office)"]

def flatten(d):
    parts = [d["title"], d["meta_description"], d["h1"], d["intro"], d["cta_text"]]
    for s in d["sections"]:
        parts += [s["h2"]] + list(s.get("paragraphs", [])) + list(s.get("bullets", []) or [])
    for f in d["faq"]:
        parts += [f["q"], f["a"]]
    parts += list(d.get("key_takeaways") or [])
    t = d.get("comparison_table")
    if t:
        parts += [t.get("caption", "")] + list(t.get("headers", [])) + [c for r in t.get("rows", []) for c in r]
    return "\n".join(str(p) for p in parts)

def deterministic(d, facts):
    text = flatten(d)
    issues = []
    allowed = {float(x) for x in facts["allowed_amounts"]}
    for m in MONEY.finditer(text):
        v = float(m.group(1).replace(",", ""))
        if v not in allowed:
            issues.append("price not in facts: " + m.group(0))
    for m in HOURS.finditer(text):
        if int(m.group(1)) not in facts["allowed_delivery_hours"]:
            issues.append("delivery time not in facts: " + m.group(0))
    for pat in BANNED:
        m = re.search(pat, text, re.I)
        if m:
            issues.append("banned claim: " + m.group(0))
    return issues

CHECK_SYSTEM = ("You are a strict fact-checker. Compare the DRAFT to FACTS. List every claim in the draft that is not "
                "supported by FACTS or is a guarantee, invented statistic, invented client or result. General advice "
                "that makes no factual claim about the studio is fine. Reply JSON: {\"ok\": true|false, \"issues\": [..]}.")

def llm_check(llm, d, facts):
    if llm is None:
        return []
    res = llm.json(CHECK_SYSTEM, "FACTS:\n%s\n\nDRAFT:\n%s" % (
        json.dumps({k: facts[k] for k in ("business", "services", "must_not_claim")}, ensure_ascii=False), flatten(d)),
        temperature=0.0, max_tokens=500)
    return [] if res.get("ok") else [str(i) for i in res.get("issues", [])][:8] or ["LLM check failed"]

def check(d, facts, llm=None):
    return deterministic(d, facts) + llm_check(llm, d, facts)
