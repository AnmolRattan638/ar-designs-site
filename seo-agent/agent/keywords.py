"""Keyword discovery from free sources: Google autocomplete (+ optional Search Console)."""
import itertools, random, re, time
import requests

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

def discover(cfg, today_iso, fetch=autocomplete, sleep=0.4):
    cands, seen = [], set()
    terms = [t.lower() for t in cfg["relevant_terms"]]
    for seed in build_seeds(cfg, today_iso):
        for kw in [seed] + _safe(fetch, seed)[: cfg["suggestions_per_seed"]]:
            n = normalize(kw)
            if n in seen or len(n.split()) < 3 or not any(t in n for t in terms):
                continue
            seen.add(n)
            cands.append({"keyword": n, "source": "autocomplete" if kw != seed else "seed", "priority": 1})
        time.sleep(sleep)
    return cands

def _safe(fetch, q):
    try:
        return fetch(q)
    except Exception:
        return []
