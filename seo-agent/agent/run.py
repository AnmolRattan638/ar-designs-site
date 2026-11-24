"""Entry point. Weekly: learn from Search Console -> write a new page OR refresh an old one -> fact-check ->
render -> publish files (the workflow opens a PR; merge = approve)."""
import argparse, json, os, sys
from datetime import date, datetime
from pathlib import Path

from . import keywords, choose as chooser, writer, factcheck, render, publish as pub, analyst, gsc as gscmod

def _read(p, default):
    try:
        t = Path(p).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return default
    return json.loads(t) if t else default

def _generate(llm, facts, keyword, page_type, refresh=None):
    """Draft + fact-check, with ONE regeneration only (protects free-tier credits)."""
    def once(issues=None):
        d, problems = writer.draft(llm, facts, keyword, page_type, issues, refresh)
        if refresh and isinstance(d, dict):
            d["slug"] = refresh["slug"]
        return d, problems
    draft, problems = once()
    issues = problems or factcheck.check(draft, facts, llm)
    if issues:
        print("Regenerating once. Issues:", issues)
        draft, problems = once(issues)
        issues = problems or factcheck.check(draft, facts, llm)
    return draft, issues

def main(argv=None, llm=None, fetch=None, gsc_rows=None, page_rows=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="..", help="repo root (contains site/ and seo-agent/)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--mode", choices=["auto", "new", "refresh"], default="auto")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    here = root / "seo-agent"
    cfg = json.loads((here / "config.json").read_text(encoding="utf-8"))
    facts = json.loads((here / "facts.json").read_text(encoding="utf-8"))
    state = here / "state"; out = here / "out"; out.mkdir(exist_ok=True)
    (state / "drafts").mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    force = a.force or os.environ.get("FORCE") == "true"

    last = _read(state / "last_run.json", {})
    if last.get("date") and not force and (date.today() - datetime.strptime(last["date"], "%Y-%m-%d").date()).days < cfg["min_days_between_runs"]:
        print("Skipped: last run %s is under %d days ago" % (last["date"], cfg["min_days_between_runs"]))
        (out / "summary.json").write_text(json.dumps({"skipped": True}))
        return 0

    if llm is None and os.environ.get("GROQ_API_KEY"):
        from .llm import GroqLLM
        llm = GroqLLM(cfg.get("model"))
    if llm is None:
        print("GROQ_API_KEY missing: cannot write a page"); return 2

    published = _read(state / "published.json", [])

    # ---- 1. LEARN: real Search Console data -> score past pages -> lessons
    have_gsc = page_rows is not None
    if page_rows is None and os.environ.get("GSC_SITE") and (os.environ.get("GSC_SA_JSON") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")):
        try:
            page_rows = gscmod.fetch_pages(os.environ["GSC_SITE"], os.environ.get("GSC_SA_JSON") or None)
            have_gsc = True
        except Exception as ex:
            print("Search Console skipped:", ex)
    exps = analyst.load(state)
    if page_rows is not None:
        exps = analyst.evaluate(exps, page_rows, today)
    lessons = analyst.build_lessons(exps, today)
    if gsc_rows is None and page_rows:
        gsc_rows = gscmod.striking_queries(page_rows, [p["slug"] for p in published])

    # ---- 2. DECIDE: new page or refresh
    cand = analyst.refresh_candidate(published, page_rows, today, cfg) if published else None
    mode = a.mode
    if mode == "auto":
        mode = "refresh" if cand and last.get("mode") != "refresh" else "new"
    if mode == "refresh" and not (cand and (state / "drafts" / (cand["slug"] + ".json")).exists()):
        print("No page is ready to refresh; writing a new page instead"); mode = "new"

    # ---- 3a. REFRESH an existing page
    if mode == "refresh":
        entry = next(p for p in published if p["slug"] == cand["slug"])
        prev = json.loads((state / "drafts" / (entry["slug"] + ".json")).read_text(encoding="utf-8"))
        print("Refreshing:", entry["slug"], "|", cand["reason"])
        draft, issues = _generate(llm, facts, entry["keyword"], entry["page_type"],
                                  {"slug": entry["slug"], "previous": prev, "queries": cand["queries"]})
        if issues:
            (out / "summary.json").write_text(json.dumps({"failed": True, "keyword": entry["keyword"], "issues": issues}, indent=1))
            print("ABORT: refresh failed fact-check:", issues); return 3
        page = render.render_page(draft, cfg, facts, today, entry["date"], keywords.related(published, entry["keyword"], cfg, entry["slug"]))
        site, blog = root / "site", root / "site" / "blog"
        url = pub.refresh_finish(draft, page, site, blog, cfg, today, state, facts)
        analyst.log_experiment(exps, entry["slug"], url, entry["keyword"], entry["page_type"], "refresh", cfg, today)
        head = ("## Page refresh for approval\n\n**Page:** %s\n\n**Why now:** %s\n\n**Real queries targeted:** %s\n\n**New title:** %s\n\n**URL:** %s\n\n"
                % (entry["slug"], cand["reason"], ", ".join(cand["queries"]) or "none (freshness pass)", draft["title"], url))
        title = draft["title"]
    # ---- 3b. WRITE a new page
    else:
        cands = keywords.discover(cfg, today, fetch=fetch or keywords.autocomplete, lessons=lessons)
        cands = (gsc_rows or []) + cands
        pick = chooser.choose(cands, [p["keyword"] for p in published], llm, cfg=cfg, published=published, lessons=lessons)
        print("Keyword:", pick["keyword"], "|", pick["page_type"], "|", pick["reason"])
        draft, issues = _generate(llm, facts, pick["keyword"], pick["page_type"])
        if issues:
            (out / "summary.json").write_text(json.dumps({"failed": True, "keyword": pick["keyword"], "issues": issues}, indent=1))
            print("ABORT: draft failed fact-check:", issues); return 3
        slug, site, blog = pub.publish(draft, "", root, cfg, today, state)
        page = render.render_page(draft, cfg, facts, today, today, keywords.related(published, pick["keyword"], cfg))
        url = pub.finish(draft, page, site, blog, cfg, today, state, pick["keyword"], pick["page_type"], facts)
        analyst.log_experiment(exps, slug, url, pick["keyword"], pick["page_type"], "new", cfg, today)
        head = ("## New page for approval\n\n**Keyword:** %s (%s, score %s)\n\n**Why:** %s\n\n**Title:** %s\n\n**URL after merge:** %s\n\n"
                % (pick["keyword"], pick["source"], pick.get("priority"), pick["reason"], draft["title"], url))
        title = draft["title"]

    analyst.save(state, exps, lessons)
    (state / "last_run.json").write_text(json.dumps({"date": today, "mode": mode}))
    body = head + "Review the Netlify deploy preview below, then **Merge = approve**, **Close = reject**.\n\n" + analyst.report_md(exps, lessons, have_gsc) + "\n"
    (out / "pr_body.md").write_text(body, encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({"mode": mode, "title": title, "url": url}))
    print("Drafted (%s): %s" % (mode, url)); return 0

if __name__ == "__main__":
    sys.exit(main())
