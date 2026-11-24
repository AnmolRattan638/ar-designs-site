"""Pick ONE keyword for this run. Scored shortlist (diversified, lesson-aware); LLM picks; deterministic fallback."""
from collections import Counter
from .keywords import normalize, classify

SYSTEM = ("You are an SEO strategist for a small freelance studio in Himachal Pradesh, India that sells websites, "
          "AI cartoon animations, chatbots, SEO writing and AI agent systems. Pick the single best keyword to write "
          "a new page for. Prefer clear buying or local-service intent, specific long-tail phrases a small site can "
          "win, question-style phrases an AI assistant would be asked, and topics the studio can answer truthfully. "
          "Avoid keywords that need claims about experience the studio does not have. Use the lessons, if given, "
          "to favour what has worked. Reply JSON: {\"keyword\": <exactly one from the list>, \"page_type\": "
          "\"landing\"|\"guide\", \"reason\": <one sentence>}.")

def shortlist(cands, published_keywords, limit=40, cfg=None, published=None):
    seen = {normalize(k) for k in published_keywords}
    out = []
    for c in cands:
        n = normalize(c["keyword"])
        if n in seen:
            continue
        seen.add(n)
        out.append(c)
    counts = Counter()
    if cfg and published:                      # spread pages across industries and cities
        for p in published:
            pc = classify(p["keyword"], cfg)
            for d in ("industry", "city"):
                if pc[d]: counts[(d, pc[d])] += 1
    def adjusted(c):
        pen = 0.0
        if counts:
            cl = classify(c["keyword"], cfg)
            pen = sum(0.6 * counts[(d, cl[d])] for d in ("industry", "city") if cl[d])
        return c.get("priority", 0) - pen
    out.sort(key=lambda c: -adjusted(c))
    return out[:limit]

def choose(cands, published_keywords, llm=None, cfg=None, published=None, lessons=None):
    short = shortlist(cands, published_keywords, cfg=cfg, published=published)
    if not short:
        raise RuntimeError("No new keyword candidates found")
    pick = None
    if llm is not None:
        lines = "\n".join("- %s%s" % (c["keyword"], " (own Search Console query, position %s)" % c["position"] if c.get("position") else "") for c in short)
        notes = "\n".join("- " + n for n in (lessons or {}).get("notes", [])[:6])
        user = ("Lessons from real results so far:\n%s\n\n" % notes if notes else "") + "Keywords:\n" + lines
        try:
            res = llm.json(SYSTEM, user, temperature=0.2, max_tokens=300)
            kw = normalize(res.get("keyword", ""))
            match = next((c for c in short if normalize(c["keyword"]) == kw), None)
            if match:
                pick = dict(match, page_type=res.get("page_type") if res.get("page_type") in ("landing", "guide") else None,
                            reason=str(res.get("reason", ""))[:300])
        except Exception:
            pick = None
    if pick is None:
        pick = dict(short[0], page_type=None, reason="Fallback: highest-scoring unused keyword")
    if not pick.get("page_type"):
        pick["page_type"] = "landing" if " in " in pick["keyword"] or "cost" in pick["keyword"] else "guide"
    return pick
