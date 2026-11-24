"""Learning loop: every page is logged as an experiment, scored against real Search Console data at
14 and 28 days, and the results become lessons that bias the next keyword choice."""
import json
from datetime import date
from pathlib import Path
from . import keywords

CHECKPOINTS = (14, 28)
SCORE = {"winning": 1.0, "gaining": 0.3, "no_impressions": -1.0}

def _read(p, default):
    try:
        t = Path(p).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return default
    return json.loads(t) if t else default

def load(state_dir):
    return _read(Path(state_dir) / "experiments.json", [])

def save(state_dir, exps, lessons):
    sd = Path(state_dir)
    (sd / "experiments.json").write_text(json.dumps(exps, indent=1, ensure_ascii=False), encoding="utf-8")
    (sd / "lessons.json").write_text(json.dumps(lessons, indent=1, ensure_ascii=False), encoding="utf-8")

def load_lessons(state_dir):
    return _read(Path(state_dir) / "lessons.json", {})

def log_experiment(exps, slug, url, keyword, page_type, mode, cfg, today):
    c = keywords.classify(keyword, cfg)
    exps.append({"id": "%s@%s" % (slug, today), "slug": slug, "url": url, "keyword": keyword, "page_type": page_type,
                 "mode": mode, "date": today, "industry": c["industry"], "city": c["city"], "topic": c["topic"],
                 "hypothesis": ("Refresh answers the real queries and lifts position" if mode == "refresh"
                                else "A page for this keyword earns impressions within 4 weeks"),
                 "results": []})
    return exps

def evaluate(exps, page_rows, today_iso):
    today = date.fromisoformat(today_iso)
    for e in exps:
        done = {r["checkpoint"] for r in e["results"]}
        age = (today - date.fromisoformat(e["date"])).days
        for cp in CHECKPOINTS:
            if cp in done or age < cp:
                continue
            rows = [r for r in page_rows if "/blog/%s/" % e["slug"] in r["page"]]
            imp = sum(r["impressions"] for r in rows); clk = sum(r["clicks"] for r in rows)
            pos = sum(r["position"] * r["impressions"] for r in rows) / imp if imp else None
            top = max(rows, key=lambda r: r["impressions"])["query"] if rows else None
            label = "no_impressions" if imp == 0 else ("winning" if (clk > 0 or (pos is not None and pos <= 10)) else "gaining")
            e["results"].append({"checkpoint": cp, "checked": today_iso, "impressions": imp, "clicks": clk,
                                 "position": round(pos, 1) if pos is not None else None, "label": label, "top_query": top})
    return exps

def build_lessons(exps, today_iso):
    vals = {}
    scored = 0
    for e in exps:
        if not e["results"]:
            continue
        scored += 1
        last = e["results"][-1]
        s = SCORE[last["label"]]
        if last["label"] == "no_impressions" and last["checkpoint"] < 28:
            s = -0.3                                  # too early to call it a failure
        for dim in ("industry", "city", "topic"):
            if e.get(dim): vals.setdefault("%s:%s" % (dim, e[dim]), []).append(s)
        vals.setdefault("page_type:%s" % e["page_type"], []).append(s)
    bonus, notes = {}, []
    for k in sorted(vals):
        v = vals[k]; avg = sum(v) / len(v)
        if not k.startswith("page_type"):
            bonus[k] = round(max(-2.0, min(2.0, 1.5 * avg)), 2)
        if avg >= 0.5:
            notes.append("%s is working (%d page(s), score %.1f): write more like it" % (k, len(v), avg))
        elif avg <= -0.5:
            notes.append("%s is not working yet (%d page(s), score %.1f): try a different angle or pause it" % (k, len(v), avg))
    return {"updated": today_iso, "pages_scored": scored, "bonus": bonus, "notes": notes[:10]}

def refresh_candidate(published, page_rows, today_iso, cfg):
    """Best existing page to refresh: striking-distance queries first, otherwise the stalest page."""
    today = date.fromisoformat(today_iso)
    min_age = cfg.get("refresh_min_age_days", 21); stale = cfg.get("refresh_stale_days", 60)
    best = None
    for p in published:
        age = (today - date.fromisoformat(p.get("modified") or p["date"])).days
        if age < min_age:
            continue
        rows = [r for r in (page_rows or []) if "/blog/%s/" % p["slug"] in r["page"]]
        qs = sorted([r for r in rows if 8 <= r["position"] <= 30 and r["impressions"] >= 3], key=lambda r: -r["impressions"])
        if qs:
            sc, reason = sum(r["impressions"] for r in qs), "%d queries sit at positions 8-30" % len(qs)
        elif age >= stale:
            sc, reason = 0.1 + age / 1000.0, "not updated for %d days" % age
        else:
            continue
        if best is None or sc > best["score"]:
            best = {"slug": p["slug"], "queries": [r["query"] for r in qs[:6]], "reason": reason, "score": sc}
    return best

def report_md(exps, lessons, have_gsc):
    lines = ["### Learning report", ""]
    if not have_gsc:
        lines.append("No Search Console data was available this run, so results could not be scored. "
                     "Set `GSC_SITE` and the Google login to switch the learning loop on.")
    rows = [e for e in exps if e["results"]][-8:]
    if rows:
        lines += ["", "| Page | Published | Check | Impressions | Clicks | Position | Verdict |", "|---|---|---|---|---|---|---|"]
        for e in rows:
            r = e["results"][-1]
            lines.append("| %s | %s | %dd | %s | %s | %s | %s |" % (e["slug"], e["date"], r["checkpoint"], r["impressions"], r["clicks"], r["position"] or "-", r["label"]))
    for n in lessons.get("notes", []):
        lines.append("- " + n)
    pending = len([e for e in exps if not e["results"]])
    lines.append("\n%d page(s) waiting for their first 14-day check." % pending)
    return "\n".join(lines)
