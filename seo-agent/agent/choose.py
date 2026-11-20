"""Pick ONE keyword for this run. LLM picks among a shortlist; deterministic fallback."""
from .keywords import normalize

SYSTEM = ("You are an SEO strategist for a small freelance studio in Himachal Pradesh, India that sells websites, "
          "AI cartoon animations, chatbots, SEO writing and AI agent systems. Pick the single best keyword to write "
          "a new page for. Prefer clear buying or local-service intent, specific long-tail phrases a small site can "
          "win, and topics the studio can answer truthfully. Avoid keywords that need claims about experience the "
          "studio does not have. Reply JSON: {\"keyword\": <exactly one from the list>, \"page_type\": "
          "\"landing\"|\"guide\", \"reason\": <one sentence>}.")

def shortlist(cands, published_keywords, limit=40):
    seen = {normalize(k) for k in published_keywords}
    out = []
    for c in cands:
        n = normalize(c["keyword"])
        if n in seen:
            continue
        seen.add(n)
        out.append(c)
    out.sort(key=lambda c: -c.get("priority", 0))
    return out[:limit]

def choose(cands, published_keywords, llm=None):
    short = shortlist(cands, published_keywords)
    if not short:
        raise RuntimeError("No new keyword candidates found")
    pick = None
    if llm is not None:
        lines = "\n".join("- %s%s" % (c["keyword"], " (own Search Console query, position %s)" % c["position"] if c.get("position") else "") for c in short)
        try:
            res = llm.json(SYSTEM, "Keywords:\n" + lines, temperature=0.2, max_tokens=300)
            kw = normalize(res.get("keyword", ""))
            match = next((c for c in short if normalize(c["keyword"]) == kw), None)
            if match:
                pick = dict(match, page_type=res.get("page_type") if res.get("page_type") in ("landing", "guide") else None,
                            reason=str(res.get("reason", ""))[:300])
        except Exception:
            pick = None
    if pick is None:
        pick = dict(short[0], page_type=None, reason="Fallback: highest-priority unused keyword")
    if not pick.get("page_type"):
        pick["page_type"] = "landing" if " in " in pick["keyword"] or "cost" in pick["keyword"] else "guide"
    return pick
