"""Quality gates: is this page detailed, on-topic and free of filler? Pure functions, no LLM."""
import re
from collections import Counter
from .factcheck import flatten
from .research import tokens

FILLER = ["in today's digital", "in the ever-evolving", "unlock the", "unlock your", "game-changer", "game changer", "seamless",
          "delve", "elevate your", "next level", "cutting-edge", "revolutionize", "in conclusion", "it's important to note",
          "it is important to note", "look no further", "fast-paced", "in the digital age", "digital landscape", "tailored solutions"]

def count_words(text):
    return len(re.findall(r"[A-Za-z0-9\u20b9$][A-Za-z0-9,.'\u2019$\u20b9-]*", text))

def section_text(s):
    parts = [s.get("h2", "")] + list(s.get("paragraphs", [])) + list(s.get("bullets") or []) + list(s.get("steps") or [])
    if s.get("example"): parts.append(s["example"])
    for sub in s.get("subsections") or []:
        parts += [sub.get("h3", "")] + list(sub.get("paragraphs", [])) + list(sub.get("bullets") or [])
    return "\n".join(str(p) for p in parts)

def coverage(keyword, text):
    k = tokens(keyword)
    return (len(k & tokens(text)) / len(k)) if k else 1.0

def report(d, keyword, cfg):
    """Returns {"words", "checks", "thin": [section idx], "problems": [...]} ; problems are human-readable fixes."""
    text = flatten(d)
    words = count_words(text)
    min_words = cfg.get("min_words", 1500)
    secs = d["sections"]
    sec_words = [count_words(section_text(s)) for s in secs]
    low = text.lower()
    sentences = [x.strip().lower() for x in re.split(r"(?<=[.!?])\s+", text) if len(x.split()) > 6]
    dupes = [s for s, n in Counter(sentences).items() if n > 1]
    h2s = [s["h2"].strip().lower() for s in secs]
    checks = {
        "enough_words": words >= min_words,
        "enough_sections": len(secs) >= cfg.get("min_sections", 7),
        "no_thin_sections": all(w >= cfg.get("min_section_words", 170) for w in sec_words),
        "title_has_keyword": coverage(keyword, d["title"]) >= 0.75,
        "h1_has_keyword": coverage(keyword, d["h1"]) >= 0.75,
        "intro_answers_keyword": coverage(keyword, d["intro"] + " " + d["title"]) >= 0.6,
        "intro_is_short": 20 <= count_words(d["intro"]) <= 70,
        "meta_length_ok": 90 <= len(d["meta_description"]) <= 160,
        "faq_depth": len(d["faq"]) >= cfg.get("min_faq", 7),
        "has_steps_or_checklist": any(s.get("steps") or s.get("bullets") for s in secs),
        "unique_headings": len(set(h2s)) == len(h2s),
        "no_repeated_sentences": not dupes,
        "no_filler_phrases": not any(f in low for f in FILLER),
    }
    problems, thin = [], [i for i, w in enumerate(sec_words) if w < cfg.get("min_section_words", 170)]
    if not checks["enough_words"]: problems.append("page has %d words; needs at least %d" % (words, min_words))
    if not checks["enough_sections"]: problems.append("needs at least %d sections" % cfg.get("min_sections", 7))
    if thin: problems.append("thin sections: " + ", ".join(secs[i]["h2"] for i in thin))
    if not checks["title_has_keyword"]: problems.append("title does not cover the keyword: " + keyword)
    if not checks["h1_has_keyword"]: problems.append("h1 does not cover the keyword: " + keyword)
    if not checks["intro_answers_keyword"]: problems.append("intro does not answer the keyword directly")
    if not checks["intro_is_short"]: problems.append("intro must be 20-65 words")
    if not checks["meta_length_ok"]: problems.append("meta_description must be 90-160 characters")
    if not checks["faq_depth"]: problems.append("needs at least %d FAQ items" % cfg.get("min_faq", 7))
    if not checks["unique_headings"]: problems.append("duplicate section headings")
    if dupes: problems.append("repeated sentence: " + dupes[0][:80])
    for f in FILLER:
        if f in low: problems.append("filler phrase: " + f); break
    hard = [m for m in problems if m.startswith(("page has", "needs at least %d sections" % cfg.get("min_sections", 7), "repeated sentence", "filler phrase"))]
    return {"words": words, "checks": checks, "thin": thin, "problems": problems, "hard": hard, "section_words": sec_words}

def summary_md(q):
    ok = sum(1 for v in q["checks"].values() if v)
    lines = ["**Quality gates:** %d/%d passed | **%d words** | sections: %s" % (ok, len(q["checks"]), q["words"], ", ".join(str(w) for w in q["section_words"]))]
    fails = [k.replace("_", " ") for k, v in q["checks"].items() if not v]
    if fails: lines.append("Needs a human look: " + ", ".join(fails))
    return "\n\n".join(lines)
