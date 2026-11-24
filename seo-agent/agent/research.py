"""Pre-writing research: real questions people type about the chosen keyword (free Google autocomplete)."""
import re
from .keywords import autocomplete, normalize

PREFIXES = ("how", "what", "why", "can", "is", "does", "should", "which", "how much", "best")
STOP = {"a", "an", "the", "for", "in", "of", "to", "and", "is", "do", "does", "how", "what", "much", "my", "on", "with", "near", "me"}

def tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP and len(t) > 2}

def questions_for(keyword, fetch=autocomplete, limit=14):
    base = tokens(keyword)
    seen, out = {normalize(keyword)}, []
    queries = ["%s %s" % (p, keyword) for p in PREFIXES] + [keyword + " vs", keyword + " for beginners", keyword + " checklist"]
    for q in queries:
        try:
            got = fetch(q)
        except Exception:
            got = []
        for g in got:
            n = normalize(g)
            if n in seen or len(n.split()) < 4:
                continue
            if len(tokens(n) & base) < max(1, min(2, len(base))):
                continue
            seen.add(n); out.append(n)
    return out[:limit]
