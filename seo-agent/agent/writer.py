"""Draft one page with the LLM, grounded only in facts.json."""
import json

SYSTEM = """You write SEO pages for AR Designs, a one-person freelance studio. Rules:
- Use ONLY the FACTS provided for prices, delivery times, services and contact. Never invent numbers, clients, results, awards, testimonials, rankings or locations of an office. The studio works remotely.
- Answer-first: the intro (max 60 words) must directly answer the keyword's question.
- Plain, specific, helpful language. No hype, no guarantees, no "best in". Write for a small business owner.
- Prices: quote INR for Indian services as "Rs 1,499" style numbers exactly as in FACTS; agent systems in USD exactly as in FACTS.
- Do not mention competitors by name.
- Write short, quotable sentences. Define each term where it first appears. AI assistants and voice search lift answers from pages like this one.
- key_takeaways: exactly 3 standalone facts (max 22 words each) a reader or an AI assistant could quote on their own.
- comparison_table is OPTIONAL. Use it only to compare packages, options or costs that appear in FACTS. Never invent rows.
Return JSON only with keys: slug (lowercase-hyphens, max 60 chars), title (max 62 chars), meta_description (max 155 chars), h1,
intro, key_takeaways (3 strings), sections (4 to 6 items of {h2, paragraphs: [1-3 strings], bullets: [] optional}),
comparison_table (optional: {caption, headers: [2-4 strings], rows: [2-5 lists, each as long as headers]}),
faq (4 to 6 items of {q, a}), cta_text (max 120 chars)."""

REQUIRED = ["slug", "title", "meta_description", "h1", "intro", "key_takeaways", "sections", "faq", "cta_text"]

def validate(d):
    p = []
    for k in REQUIRED:
        if k not in d:
            p.append("missing " + k)
    if p:
        return p
    if len(d["title"]) > 70: p.append("title too long")
    if len(d["meta_description"]) > 165: p.append("meta_description too long")
    if len(str(d["intro"]).split()) > 70: p.append("intro over 60 words")
    kt = d["key_takeaways"]
    if not (isinstance(kt, list) and len(kt) == 3 and all(isinstance(x, str) and x.strip() for x in kt)):
        p.append("need exactly 3 key_takeaways")
    t = d.get("comparison_table")
    if t:
        ok = (isinstance(t, dict) and t.get("caption") and isinstance(t.get("headers"), list) and 2 <= len(t["headers"]) <= 4
              and isinstance(t.get("rows"), list) and 2 <= len(t["rows"]) <= 5
              and all(isinstance(r, list) and len(r) == len(t["headers"]) for r in t["rows"]))
        if not ok: p.append("bad comparison_table")
    if not (4 <= len(d["sections"]) <= 6): p.append("need 4-6 sections")
    if not (4 <= len(d["faq"]) <= 6): p.append("need 4-6 faq items")
    for s in d["sections"]:
        if not isinstance(s, dict) or "h2" not in s or not s.get("paragraphs"):
            p.append("bad section"); break
    for f in d["faq"]:
        if not isinstance(f, dict) or "q" not in f or "a" not in f:
            p.append("bad faq"); break
    return p

def draft(llm, facts, keyword, page_type, issues=None, refresh=None):
    user = ("FACTS:\n%s\n\nKEYWORD: %s\nPAGE TYPE: %s (landing = service page for a specific business type or city; guide = how-to or explainer)\n"
            % (json.dumps({k: facts[k] for k in ("business", "contact", "services", "samples")}, ensure_ascii=False), keyword, page_type))
    if refresh:
        user += ("\nREFRESH MODE: improve the existing page below. Keep the slug \"%s\". Keep what is accurate, tighten the intro, "
                 "and add or sharpen a section or FAQ for each real search query listed, using only FACTS.\nREAL QUERIES: %s\nEXISTING PAGE JSON:\n%s\n"
                 % (refresh["slug"], "; ".join(refresh.get("queries") or ["(none: refresh for freshness and clarity)"]),
                    json.dumps(refresh["previous"], ensure_ascii=False)))
    if issues:
        user += "\nFix these problems from the previous draft: " + "; ".join(issues)
    d = llm.json(SYSTEM, user, temperature=0.5, max_tokens=4200)
    return d, validate(d)
