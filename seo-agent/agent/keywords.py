"""Keyword discovery from free sources (Google autocomplete + optional Search Console), with intent scoring."""
import itertools, random, re, time
import requests

BUY_WORDS = ("cost", "price", "pricing", "hire", "agency", "freelancer", "package", "packages", "how much",
             "near me", "affordable", "cheap", "quote", "charges")
QUESTION_WORDS = ("how", "what", "why", "can", "does", "do", "is", "should", "which", "are")

def normalize(k):
    return re.sub(r"\s+", " ", k.lower().strip())

def autocomplete(q, hl="en", gl="in"):
    r = requests.get("https://suggestqueries.google.com/complete/search",
                     params={"client": "firefox", "q": q, "hl": hl, "gl": gl},
                     headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    r.raise_for_status()
    return [s for s in r.json()[1] if isinstance(s, str)]

def build_seeds(cfg, today_iso):
    combos = []
    for t in cfg["seed_templates"]:
        if "{city}" in t:
            combos += [t.format(industry=i, city=c) for i, c in itertools.product(cfg["industries"], cfg["cities"])]
        elif "{industry}" in t:
            combos += [t.format(industry=i) for i in cfg["industries"]]
        else:
            combos.append(t)
    rnd = random.Random(today_iso)          # deterministic per day, varies between runs
    rnd.shuffle(combos)
    return combos[: cfg["seeds_per_run"]]

def question_seeds(cfg, today_iso):
    """Question-style seeds (how much / is it worth it / vs): the phrasing AI assistants and voice search get asked."""
    combos = [t.format(industry=i, topic=tp) for t in cfg.get("question_templates", [])
              for i, tp in itertools.product(cfg["industries"], cfg.get("question_topics", []))]
    random.Random(today_iso + "q").shuffle(combos)
    return combos[: cfg.get("question_seeds_per_run", 0)]

def classify(kw, cfg):
    n = normalize(kw)
    topics = cfg.get("topics") or cfg["relevant_terms"]
    return {"city": next((c.lower() for c in cfg.get("cities", []) if c.lower() in n), None),
            "industry": next((i.lower() for i in cfg.get("industries", []) if i.lower() in n), None),
            "topic": next((t.lower() for t in topics if t.lower() in n), None),
            "question": bool(n) and n.split()[0] in QUESTION_WORDS,
            "buy": any(b in n for b in BUY_WORDS)}

def score(kw, cfg, lessons=None):
    """Transparent intent score. Lessons (from real results) nudge it up or down per industry / city / topic."""
    n = normalize(kw); c = classify(n, cfg); words = len(n.split())
    s = 1.0
    if c["buy"]: s += 2.0
    if c["city"]: s += 1.5
    if c["industry"]: s += 1.0
    if c["question"]: s += 1.0
    if 4 <= words <= 8: s += 0.5
    if words > 9: s -= 1.0
    bonus = (lessons or {}).get("bonus", {})
    for dim in ("city", "industry", "topic"):
        if c[dim]: s += bonus.get("%s:%s" % (dim, c[dim]), 0.0)
    return round(s, 2)

def related(published, keyword, cfg, exclude_slug=None, n=3):
    """Existing pages that share industry, city or topic with this keyword (for internal links)."""
    c = classify(keyword, cfg); out = []
    for p in published:
        if p["slug"] == exclude_slug:
            continue
        pc = classify(p["keyword"], cfg)
        m = sum(1 for d in ("industry", "city", "topic") if c[d] and c[d] == pc[d])
        if m:
            out.append((m, p["date"], p))
    out.sort(key=lambda x: x[1], reverse=True)
    out.sort(key=lambda x: -x[0])
    return [x[2] for x in out][:n]

def discover(cfg, today_iso, fetch=autocomplete, sleep=0.4, lessons=None):
    cands, seen = [], set()
    terms = [t.lower() for t in cfg["relevant_terms"]]
    qseeds = set(question_seeds(cfg, today_iso))
    for seed in build_seeds(cfg, today_iso) + sorted(qseeds):
        for kw in [seed] + _safe(fetch, seed)[: cfg["suggestions_per_seed"]]:
            n = normalize(kw)
            if n in seen or len(n.split()) < 3 or not any(t in n for t in terms):
                continue
            seen.add(n)
            src = "question" if seed in qseeds else ("autocomplete" if kw != seed else "seed")
            cands.append({"keyword": n, "source": src, "priority": score(n, cfg, lessons)})
        time.sleep(sleep)
    return cands

def _safe(fetch, q):
    try:
        return fetch(q)
    except Exception:
        return []
