"""Multi-pass page writer: outline -> one call per section -> frame (intro, takeaways, table, FAQ) -> assemble.
Everything is grounded only in facts.json. Depth comes from specific, useful advice, never from invented numbers."""
import json, re

RULES = """Rules (non-negotiable):
- Use ONLY the FACTS provided for prices, delivery times, services, samples and contact. Never invent numbers, clients, results, awards, testimonials, rankings, statistics, percentages, survey data, or an office. The studio works remotely.
- Quote INR for Indian services as "Rs 1,499" style numbers exactly as in FACTS; agent systems in USD exactly as in FACTS.
- No hype or filler. Never write: "in today's digital world", "unlock", "game-changer", "seamless", "elevate", "delve", "next level", "in conclusion".
- No guarantees, no "best in", no competitor names.
- Short, quotable sentences. Define each term where it first appears. Write for a small business owner."""

OUTLINE_SYSTEM = """You are a senior SEO content strategist for AR Designs, a one-person freelance studio in Himachal Pradesh, India that works remotely. Plan ONE long, genuinely useful page that fully satisfies the search intent of the keyword and beats thin competitor pages by being more specific and more practical.
""" + RULES + """
Plan 7 to 8 sections (H2). Cover: the direct answer and context; a step-by-step process; a cost or pricing section built only from FACTS (when money is relevant); common mistakes; a checklist or how-to-choose section; how AR Designs approaches it (truthful, from FACTS); next steps. Cover the real questions provided. Every H2 must differ in purpose.
Stage: outline
Return JSON only: {slug (lowercase-hyphens, max 60 chars), title (max 62 chars, contains the keyword), meta_description (110-155 chars), h1, search_intent, sections: [{h2, goal, must_cover: [2-4 strings], format: "steps"|"checklist"|"comparison"|"explainer"|"mistakes"}], faq_questions: [8 strings, use the real questions where sensible]}."""

SECTION_SYSTEM = """You are a specialist section writer for AR Designs, a one-person freelance studio in Himachal Pradesh, India that works remotely across India and worldwide. Write ONE section of a long guide for a small business owner.
""" + RULES + """
- Depth: 220 to 340 words in this section. Be concrete: name the exact steps, what to prepare, what to check, typical mistakes, what good looks like. Include one short illustration ("for example, a homestay owner who...") marked as an illustration with no invented numbers.
- General local observations are fine without numbers (mobile-first travellers, WhatsApp-first customers, seasonal demand, Google Maps habits).
- Do not repeat points that belong to other sections.
Stage: section
Return JSON only: {h2, paragraphs: [2-4 strings of 50-110 words], bullets: [optional, 4-7 short items], steps: [optional, 4-8 imperative steps, only for how-to sections], subsections: [optional, up to 2 of {h3, paragraphs: [1-2 strings]}], example: optional single illustrative paragraph}."""

FRAME_SYSTEM = """You write the frame of an SEO page for AR Designs: the direct-answer intro, key takeaways, an optional comparison table and the FAQ. AI assistants and voice search lift answers from these parts, so make them precise and self-contained.
""" + RULES + """
- intro: 30-60 words that directly answer the keyword's question in the first sentence.
- key_takeaways: exactly 3 standalone facts (max 22 words each).
- comparison_table: OPTIONAL; only to compare packages, options or costs that appear in FACTS. Never invent rows.
- faq: 8 items, one per given question; each answer 40-90 words, direct first sentence, no repeats of the intro.
- cta_text: max 120 chars.
Stage: frame
Return JSON only: {intro, key_takeaways: [3], comparison_table: optional {caption, headers: [2-4], rows: [2-5 lists as long as headers]}, faq: [{q, a}], cta_text}."""

def facts_view(facts):
    return json.dumps({k: facts[k] for k in ("business", "contact", "services", "samples")}, ensure_ascii=False)

def validate(d, cfg=None):
    cfg = cfg or {}
    req = ["slug", "title", "meta_description", "h1", "intro", "key_takeaways", "sections", "faq", "cta_text"]
    p = [("missing " + k) for k in req if k not in d]
    if p:
        return p
    if len(d["title"]) > 70: p.append("title too long")
    if len(d["meta_description"]) > 165: p.append("meta_description too long")
    kt = d["key_takeaways"]
    if not (isinstance(kt, list) and len(kt) == 3 and all(isinstance(x, str) and x.strip() for x in kt)):
        p.append("need exactly 3 key_takeaways")
    t = d.get("comparison_table")
    if t:
        ok = (isinstance(t, dict) and t.get("caption") and isinstance(t.get("headers"), list) and 2 <= len(t["headers"]) <= 4
              and isinstance(t.get("rows"), list) and 2 <= len(t["rows"]) <= 5
              and all(isinstance(r, list) and len(r) == len(t["headers"]) for r in t["rows"]))
        if not ok: p.append("bad comparison_table")
    if not (cfg.get("min_sections", 4) <= len(d["sections"]) <= 10): p.append("section count out of range")
    if not (cfg.get("min_faq", 4) <= len(d["faq"]) <= 10): p.append("faq count out of range")
    for s in d["sections"]:
        if not isinstance(s, dict) or "h2" not in s or len(s.get("paragraphs") or []) < 1:
            p.append("bad section"); break
    for f in d["faq"]:
        if not isinstance(f, dict) or "q" not in f or "a" not in f:
            p.append("bad faq"); break
    return p

def _clean_section(s, fallback_h2):
    s = dict(s) if isinstance(s, dict) else {}
    s["h2"] = str(s.get("h2") or fallback_h2)
    s["paragraphs"] = [str(x) for x in (s.get("paragraphs") or []) if str(x).strip()]
    for k in ("bullets", "steps"):
        if s.get(k): s[k] = [str(x) for x in s[k] if str(x).strip()]
        else: s.pop(k, None)
    subs = []
    for sub in (s.get("subsections") or [])[:2]:
        if isinstance(sub, dict) and sub.get("h3") and sub.get("paragraphs"):
            subs.append({"h3": str(sub["h3"]), "paragraphs": [str(x) for x in sub["paragraphs"]]})
    if subs: s["subsections"] = subs
    else: s.pop("subsections", None)
    if s.get("example"): s["example"] = str(s["example"])
    else: s.pop("example", None)
    return s

def make_outline(call, facts, keyword, page_type, questions, refresh=None, issues=None):
    user = ("FACTS:\n%s\n\nKEYWORD: %s\nPAGE TYPE: %s (landing = service page for a business type or city; guide = how-to or explainer)\n"
            "REAL QUESTIONS PEOPLE TYPE:\n%s\n" % (facts_view(facts), keyword, page_type, "\n".join("- " + q for q in questions) or "- (none found)"))
    if refresh:
        old = [s["h2"] for s in refresh["previous"].get("sections", [])]
        user += ("\nREFRESH MODE: this improves an existing page. Keep the slug \"%s\". Existing sections: %s. Keep what is accurate, "
                 "add depth, and make sure these real search queries are clearly answered: %s\n"
                 % (refresh["slug"], "; ".join(old), "; ".join(refresh.get("queries") or ["(freshness and clarity pass)"])))
    if issues:
        user += "\nFix these problems from the previous attempt: " + "; ".join(issues)
    return call(OUTLINE_SYSTEM, user, temperature=0.4, max_tokens=1500)

def make_section(call, facts, keyword, spec, titles, issues=None, previous=None, min_words=None):
    user = ("FACTS:\n%s\n\nKEYWORD: %s\nALL SECTIONS OF THE PAGE (for coherence, do not repeat them): %s\n\nSECTION: %s\nGOAL: %s\nMUST COVER: %s\nFORMAT: %s\n"
            % (facts_view(facts), keyword, " | ".join(titles), spec["h2"], spec.get("goal", ""), "; ".join(spec.get("must_cover") or []), spec.get("format", "explainer")))
    if previous:
        user += "\nPREVIOUS VERSION (too thin or flawed):\n%s\n" % json.dumps(previous, ensure_ascii=False)
    if min_words:
        user += "\nWrite at least %d words: add a concrete example, a checklist or the common mistakes detail. Do not pad.\n" % min_words
    if issues:
        user += "\nFix these problems: " + "; ".join(issues)
    return _clean_section(call(SECTION_SYSTEM, user, temperature=0.6, max_tokens=1600), spec["h2"])

def make_frame(call, facts, keyword, outline, digest, issues=None):
    user = ("FACTS:\n%s\n\nKEYWORD: %s\nTITLE: %s\nFAQ QUESTIONS: %s\nSECTION DIGEST (do not repeat verbatim):\n%s\n"
            % (facts_view(facts), keyword, outline["title"], json.dumps(outline.get("faq_questions", []), ensure_ascii=False), digest))
    if issues:
        user += "\nFix these problems: " + "; ".join(issues)
    return call(FRAME_SYSTEM, user, temperature=0.4, max_tokens=2600)

def assemble(outline, sections, frame):
    d = {"slug": outline["slug"], "title": outline["title"], "meta_description": outline["meta_description"], "h1": outline["h1"],
         "intro": frame.get("intro", ""), "key_takeaways": frame.get("key_takeaways", []), "sections": sections,
         "faq": [{"q": str(f["q"]), "a": str(f["a"])} for f in frame.get("faq", []) if isinstance(f, dict) and "q" in f and "a" in f],
         "cta_text": frame.get("cta_text", "")}
    if frame.get("comparison_table"): d["comparison_table"] = frame["comparison_table"]
    return d

def digest_of(sections):
    return "\n".join("- %s: %s" % (s["h2"], (s["paragraphs"][0] if s["paragraphs"] else "")[:140]) for s in sections)

def suspect_sections(draft, issues):
    """Which sections contain the text an issue points at? Falls back to all of them."""
    frags = []
    for i in issues:
        m = re.search(r": (.+)$", i)
        frags.append((m.group(1) if m else i).lower())
    from .quality import section_text
    hit = set()
    for idx, s in enumerate(draft["sections"]):
        text = section_text(s).lower()
        for f in frags:
            words = re.findall(r"[a-z]{5,}", f)
            if (len(f) >= 3 and f in text) or (len(words) >= 2 and sum(w in text for w in words) >= max(2, len(words) // 2)):
                hit.add(idx)
    return sorted(hit)
