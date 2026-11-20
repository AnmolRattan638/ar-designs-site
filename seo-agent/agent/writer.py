"""Draft one page with the LLM, grounded only in facts.json."""
import json

SYSTEM = """You write SEO pages for AR Designs, a one-person freelance studio. Rules:
- Use ONLY the FACTS provided for prices, delivery times, services and contact. Never invent numbers, clients, results, awards, testimonials, rankings or locations of an office. The studio works remotely.
- Answer-first: the intro (max 60 words) must directly answer the keyword's question.
- Plain, specific, helpful language. No hype, no guarantees, no "best in". Write for a small business owner.
- Prices: quote INR for Indian services as "Rs 1,499" style numbers exactly as in FACTS; agent systems in USD exactly as in FACTS.
- Do not mention competitors by name.
Return JSON only with keys: slug (lowercase-hyphens, max 60 chars), title (max 62 chars), meta_description (max 155 chars), h1,
intro, sections (4 to 6 items of {h2, paragraphs: [1-3 strings], bullets: [] optional}), faq (4 to 6 items of {q, a}), cta_text (max 120 chars)."""

REQUIRED = ["slug", "title", "meta_description", "h1", "intro", "sections", "faq", "cta_text"]

def validate(d):
    p = []
    for k in REQUIRED:
        if k not in d:
            p.append("missing " + k)
    if p:
        return p
    if len(d["title"]) > 70: p.append("title too long")
    if len(d["meta_description"]) > 165: p.append("meta_description too long")
    if not (4 <= len(d["sections"]) <= 6): p.append("need 4-6 sections")
    if not (4 <= len(d["faq"]) <= 6): p.append("need 4-6 faq items")
    for s in d["sections"]:
        if not isinstance(s, dict) or "h2" not in s or not s.get("paragraphs"):
            p.append("bad section"); break
    for f in d["faq"]:
        if not isinstance(f, dict) or "q" not in f or "a" not in f:
            p.append("bad faq"); break
    return p

def draft(llm, facts, keyword, page_type, issues=None):
    user = ("FACTS:\n%s\n\nKEYWORD: %s\nPAGE TYPE: %s (landing = service page for a specific business type or city; guide = how-to or explainer)\n"
            % (json.dumps({k: facts[k] for k in ("business", "contact", "services", "samples")}, ensure_ascii=False), keyword, page_type))
    if issues:
        user += "\nFix these problems from the previous draft: " + "; ".join(issues)
    d = llm.json(SYSTEM, user, temperature=0.5, max_tokens=3800)
    return d, validate(d)
