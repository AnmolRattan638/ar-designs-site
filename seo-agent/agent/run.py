"""Entry point. Biweekly: discover -> choose -> draft -> fact-check -> render -> publish files (a PR is opened by the workflow)."""
import argparse, json, os, sys
from datetime import date, datetime
from pathlib import Path

from . import keywords, choose as chooser, writer, factcheck, render, publish as pub

def main(argv=None, llm=None, fetch=None, gsc_rows=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="..", help="repo root (contains site/ and seo-agent/)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    here = root / "seo-agent"
    cfg = json.loads((here / "config.json").read_text(encoding="utf-8"))
    facts = json.loads((here / "facts.json").read_text(encoding="utf-8"))
    state = here / "state"; out = here / "out"; out.mkdir(exist_ok=True)
    today = date.today().isoformat()
    force = a.force or os.environ.get("FORCE") == "true"

    last = json.loads((state / "last_run.json").read_text() or "{}").get("date")
    if last and not force and (date.today() - datetime.strptime(last, "%Y-%m-%d").date()).days < cfg["min_days_between_runs"]:
        print("Skipped: last run %s is under %d days ago" % (last, cfg["min_days_between_runs"]))
        (out / "summary.json").write_text(json.dumps({"skipped": True}))
        return 0

    if llm is None and os.environ.get("GROQ_API_KEY"):
        from .llm import GroqLLM
        llm = GroqLLM(cfg.get("model"))
    if llm is None:
        print("GROQ_API_KEY missing: cannot write a page"); return 2

    cands = keywords.discover(cfg, today, fetch=fetch or keywords.autocomplete)
    if gsc_rows is None and os.environ.get("GSC_SA_JSON") and os.environ.get("GSC_SITE"):
        try:
            from . import gsc
            gsc_rows = gsc.fetch(os.environ["GSC_SITE"], os.environ["GSC_SA_JSON"])
        except Exception as ex:
            print("Search Console skipped:", ex)
    cands = (gsc_rows or []) + cands
    published = json.loads((state / "published.json").read_text() or "[]")
    pick = chooser.choose(cands, [p["keyword"] for p in published], llm)
    print("Keyword:", pick["keyword"], "|", pick["page_type"], "|", pick["reason"])

    draft, problems = writer.draft(llm, facts, pick["keyword"], pick["page_type"])
    issues = problems or factcheck.check(draft, facts, llm)
    if issues:                                   # ONE regeneration only, to protect free-tier credits
        print("Regenerating once. Issues:", issues)
        draft, problems = writer.draft(llm, facts, pick["keyword"], pick["page_type"], issues)
        issues = problems or factcheck.check(draft, facts, llm)
    if issues:
        (out / "summary.json").write_text(json.dumps({"failed": True, "keyword": pick["keyword"], "issues": issues}, indent=1))
        print("ABORT: draft failed fact-check:", issues); return 3

    slug, site, blog = pub.publish(draft, "", root, cfg, today, state)
    page = render.render_page(draft, cfg, facts, today)
    url = pub.finish(draft, page, site, blog, cfg, today, state, pick["keyword"], pick["page_type"])
    (state / "last_run.json").write_text(json.dumps({"date": today}))
    body = ("## New page for approval\n\n**Keyword:** %s (%s)\n\n**Why:** %s\n\n**Title:** %s\n\n**URL after merge:** %s\n\n"
            "Review the Netlify deploy preview below, then **Merge = approve**, **Close = reject**.\n"
            % (pick["keyword"], pick["source"], pick["reason"], draft["title"], url))
    (out / "pr_body.md").write_text(body, encoding="utf-8")
    (out / "summary.json").write_text(json.dumps({"keyword": pick["keyword"], "title": draft["title"], "url": url}))
    print("Drafted:", url); return 0

if __name__ == "__main__":
    sys.exit(main())
