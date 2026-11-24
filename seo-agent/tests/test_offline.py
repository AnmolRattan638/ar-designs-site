"""Offline end-to-end test: stubbed LLM + stubbed keyword source. Run: python -I tests/test_offline.py"""
import json, re, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from agent import run, factcheck, choose, writer, keywords, analyst, gsc, indexnow  # noqa

GOOD = {
    "slug": "website-for-hotel-in-manali", "title": "Website for a Hotel in Manali: Cost and What You Get",
    "meta_description": "What a hotel website in Manali costs and what is included, with delivery times and real package prices.",
    "h1": "Website for a Hotel in Manali: Cost and What You Get",
    "intro": "A simple hotel website starts at Rs 1,499 and is delivered in 24 hours. Bigger sites with up to 5 pages start at Rs 2,299.",
    "key_takeaways": ["Basic hotel website: Rs 1,499, delivered in 24 hours.", "Standard hotel website: Rs 2,299, delivered in 48 hours.", "Every package includes a WhatsApp button."],
    "comparison_table": {"caption": "Hotel website packages", "headers": ["Package", "Price", "Delivery"], "rows": [["Basic", "Rs 1,499", "24 hours"], ["Standard", "Rs 2,299", "48 hours"]]},
    "sections": [{"h2": "Packages", "paragraphs": ["Basic is Rs 1,499 with 30 days of free edits.", "Standard is Rs 2,299 and takes 48 hours."], "bullets": ["Mobile responsive", "WhatsApp button"]}] + [
        {"h2": "Section %d" % i, "paragraphs": ["Helpful plain advice for a hotel owner."]} for i in range(3)],
    "faq": [{"q": "Question %d?" % i, "a": "Answer %d." % i} for i in range(4)],
    "cta_text": "Tell me about your hotel on WhatsApp."}

class FakeLLM:
    def __init__(self, draft=None, check_ok=True): self.draft = draft or GOOD; self.check_ok = check_ok; self.calls = []
    def json(self, system, user, **kw):
        self.calls.append(system[:20])
        if "SEO strategist" in system:
            first = user.split("Keywords:\n- ", 1)[1].split("\n")[0].split(" (own")[0]
            return {"keyword": first, "page_type": "landing", "reason": "clear local intent"}
        if "fact-checker" in system: return {"ok": self.check_ok, "issues": [] if self.check_ok else ["unsupported claim"]}
        return self.draft

def fake_fetch(q): return [q + " price", q + " cost", "unrelated thing entirely"]

def sandbox():
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(HERE.parent, tmp / "r", ignore=shutil.ignore_patterns("__pycache__", "out"))
    (tmp / "r/seo-agent/out").mkdir(exist_ok=True)
    return tmp / "r"

def test_happy_path():
    r = sandbox(); llm = FakeLLM()
    code = run.main(["--root", str(r), "--force"], llm=llm, fetch=fake_fetch)
    assert code == 0, code
    page = (r / "site/blog/website-for-hotel-in-manali/index.html").read_text()
    assert '<link rel="canonical" href="https://anmolrattan.netlify.app/blog/website-for-hotel-in-manali/"' in page
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S): json.loads(m.replace("<\\/", "</"))
    assert "FAQPage" in page and "BreadcrumbList" in page and "Article" in page
    sm = (r / "site/sitemap.xml").read_text()
    assert "/blog/website-for-hotel-in-manali/" in sm and "<loc>https://anmolrattan.netlify.app/blog/</loc>" in sm
    assert "website-for-hotel-in-manali" in (r / "site/llms.txt").read_text()
    assert 'href="/blog/"' in (r / "site/index.html").read_text()
    assert "website-for-hotel-in-manali" in (r / "site/blog/index.html").read_text()
    assert json.loads((r / "seo-agent/state/published.json").read_text())[0]["keyword"]
    assert "clear local intent" in (r / "seo-agent/out/pr_body.md").read_text()   # the LLM's pick was used, not the fallback
    assert (r / "seo-agent/out/pr_body.md").exists()
    # second run right after: skipped by cadence
    assert run.main(["--root", str(r)], llm=llm, fetch=fake_fetch) == 0
    assert json.loads((r / "seo-agent/out/summary.json").read_text()).get("skipped") is True
    print("ok happy path + cadence skip")

def test_bad_price_is_blocked():
    r = sandbox()
    bad = json.loads(json.dumps(GOOD)); bad["intro"] = "A hotel website costs Rs 999 and we guarantee page one rankings."
    llm = FakeLLM(draft=bad)
    code = run.main(["--root", str(r), "--force"], llm=llm, fetch=fake_fetch)
    assert code == 3, code
    assert not (r / "site/blog/website-for-hotel-in-manali").exists()
    assert llm.calls.count(llm.calls[1]) >= 1 and sum(1 for c in llm.calls if not c.startswith(("You are an SEO", "You are a strict"))) == 2  # exactly one regeneration
    print("ok bad price + guarantee blocked, only one regeneration")

def test_llm_check_blocks():
    r = sandbox()
    code = run.main(["--root", str(r), "--force"], llm=FakeLLM(check_ok=False), fetch=fake_fetch)
    assert code == 3
    print("ok LLM fact-check can block")

def test_rules():
    facts = json.loads((HERE / "facts.json").read_text())
    ok = json.loads(json.dumps(GOOD))
    assert factcheck.deterministic(ok, facts) == []
    ok["intro"] = "Delivered in 72 hours for $17 (₹1,499) or $299, from 850+ clients."
    iss = factcheck.deterministic(ok, facts)
    assert any("72" in i for i in iss) and any("850" in i for i in iss) and not any("$17" in i or "1,499" in i or "$299" in i for i in iss), iss
    assert writer.validate({"slug": "x"}) and not writer.validate(GOOD)
    c = choose.choose([{"keyword": "a b c", "priority": 1}], ["a b c"] , None) if False else None
    print("ok rule checks")

def test_dedupe_and_fallback():
    cands = [{"keyword": "website for cafe in shimla", "priority": 1}, {"keyword": "ai chatbot for hotel", "priority": 1}]
    p = choose.choose(cands, ["Website for Cafe in Shimla"], None)
    assert p["keyword"] == "ai chatbot for hotel" and p["page_type"] == "guide"
    print("ok dedupe + fallback")

CFG = json.loads((HERE / "config.json").read_text())

def test_aeo_page_elements():
    r = sandbox()
    assert run.main(["--root", str(r), "--force"], llm=FakeLLM(), fetch=fake_fetch) == 0
    page = (r / "site/blog/website-for-hotel-in-manali/index.html").read_text()
    assert "Key takeaways" in page and "<table>" in page and "Hotel website packages" in page
    assert "SpeakableSpecification" in page and 'class="byline"' in page and "<time datetime=" in page
    assert (r / "seo-agent/state/drafts/website-for-hotel-in-manali.json").exists()
    exps = json.loads((r / "seo-agent/state/experiments.json").read_text())
    assert exps[0]["mode"] == "new" and exps[0]["results"] == [] and exps[0]["industry"] == "restaurant" and exps[0]["city"] == "palampur"   # the fake LLM picked the top-scored keyword
    bad = json.loads(json.dumps(GOOD)); bad["key_takeaways"] = ["only one"]
    assert any("key_takeaways" in i for i in writer.validate(bad))
    bad = json.loads(json.dumps(GOOD)); bad["comparison_table"]["rows"][0] = ["too", "short"]
    assert "bad comparison_table" in writer.validate(bad)
    # table cells are fact-checked too
    bad = json.loads(json.dumps(GOOD)); bad["comparison_table"]["rows"][0][1] = "Rs 999"
    assert any("999" in i for i in factcheck.deterministic(bad, json.loads((HERE / "facts.json").read_text())))
    print("ok AEO page elements, stored draft, experiment logged, table fact-checked")

def test_scoring_and_diversity():
    a = keywords.score("how much does a website cost for a hotel in manali", CFG)
    b = keywords.score("website templates free", CFG)
    assert a > b + 3, (a, b)
    boosted = keywords.score("website for hotel in shimla", CFG, {"bonus": {"industry:hotel": 1.5}})
    assert boosted == keywords.score("website for hotel in shimla", CFG) + 1.5
    cands = [{"keyword": "website for hotel in shimla", "priority": 5.0}, {"keyword": "website for gym in mandi", "priority": 4.5}]
    pub = [{"keyword": "website for hotel in manali", "slug": "x", "date": "2026-01-01"}] * 2
    p = choose.choose(cands, [], None, cfg=CFG, published=pub)
    assert p["keyword"] == "website for gym in mandi", p      # two hotel pages already: spread out
    rel = keywords.related([{"keyword": "seo for hotel in kullu", "slug": "a", "date": "2026-01-01"}, {"keyword": "ai chatbot for gym", "slug": "b", "date": "2026-01-02"}],
                           "website for hotel in manali", CFG)
    assert [x["slug"] for x in rel] == ["a"]
    cs = keywords.discover(dict(CFG, seeds_per_run=2, question_seeds_per_run=3), "2026-11-24", fetch=lambda q: [], sleep=0)
    assert any(c["source"] == "question" for c in cs)
    print("ok scoring, diversity, related links, question seeds")

def test_learning_loop():
    exps = analyst.log_experiment([], "website-for-hotel-in-manali", "u", "website for hotel in manali", "landing", "new", CFG, "2026-10-01")
    analyst.log_experiment(exps, "seo-for-gym-in-mandi", "u2", "seo for gym in mandi", "landing", "new", CFG, "2026-10-01")
    rows = [{"page": "https://x/blog/website-for-hotel-in-manali/", "query": "hotel website manali", "clicks": 3, "impressions": 40, "position": 6.2}]
    analyst.evaluate(exps, rows, "2026-10-10")
    assert exps[0]["results"] == []                               # too early
    analyst.evaluate(exps, rows, "2026-10-20")
    assert exps[0]["results"][-1]["label"] == "winning" and exps[1]["results"][-1]["label"] == "no_impressions"
    assert len(exps[0]["results"]) == 1                          # day-28 not due yet
    analyst.evaluate(exps, rows, "2026-11-01")
    assert [r["checkpoint"] for r in exps[0]["results"]] == [14, 28]
    L = analyst.build_lessons(exps, "2026-11-01")
    assert L["bonus"]["industry:hotel"] > 0 > L["bonus"]["industry:gym"] and L["notes"]
    pubs = [{"slug": "website-for-hotel-in-manali", "date": "2026-09-01", "keyword": "k"}, {"slug": "new-one", "date": "2026-11-01", "keyword": "k2"}]
    sq = [{"page": "https://x/blog/website-for-hotel-in-manali/", "query": "hotel website cost manali", "clicks": 0, "impressions": 30, "position": 14.0}]
    c = analyst.refresh_candidate(pubs, sq, "2026-11-10", CFG)
    assert c["slug"] == "website-for-hotel-in-manali" and c["queries"] == ["hotel website cost manali"]
    assert analyst.refresh_candidate(pubs[1:], sq, "2026-11-10", CFG) is None   # too young
    assert "winning" in analyst.report_md(exps, L, True)
    sr = gsc.striking_queries(sq + [{"page": "https://x/", "query": "web design shimla", "clicks": 0, "impressions": 12, "position": 12.0}], ["website-for-hotel-in-manali"])
    assert [x["keyword"] for x in sr] == ["web design shimla"]
    print("ok learning loop: checkpoints, lessons, refresh candidate, striking queries")

def test_refresh_run():
    r = sandbox()
    cfgp = r / "seo-agent/config.json"; c = json.loads(cfgp.read_text()); c["refresh_min_age_days"] = 0; cfgp.write_text(json.dumps(c))
    assert run.main(["--root", str(r), "--force"], llm=FakeLLM(), fetch=fake_fetch) == 0
    slug = "website-for-hotel-in-manali"
    rows = [{"page": "https://anmolrattan.netlify.app/blog/%s/" % slug, "query": "hotel website cost manali", "clicks": 0, "impressions": 30, "position": 14.0}]
    class SpyLLM(FakeLLM):
        def json(self, system, user, **kw):
            if "REFRESH MODE" in user: self.refresh_seen = "hotel website cost manali" in user
            return FakeLLM.json(self, system, user, **kw)
    spy = SpyLLM()
    assert run.main(["--root", str(r), "--force"], llm=spy, fetch=fake_fetch, page_rows=rows) == 0      # auto: last run was 'new' -> refresh
    assert getattr(spy, "refresh_seen", False)
    assert json.loads((r / "seo-agent/state/last_run.json").read_text())["mode"] == "refresh"
    assert len(json.loads((r / "seo-agent/state/published.json").read_text())) == 1                      # refreshed, not duplicated
    assert "## Page refresh for approval" in (r / "seo-agent/out/pr_body.md").read_text()
    page = (r / ("site/blog/%s/index.html" % slug)).read_text()
    assert '"datePublished": "%s"' % __import__("datetime").date.today().isoformat() in page
    print("ok refresh run: real queries sent to the writer, page updated in place")

def test_internal_links_and_indexnow():
    from agent import publish as pub
    r = sandbox()
    assert run.main(["--root", str(r), "--force"], llm=FakeLLM(), fetch=fake_fetch) == 0
    state = r / "seo-agent/state"
    pubs = json.loads((state / "published.json").read_text())
    kw = pubs[0]["keyword"]                                   # e.g. "seo for restaurant in palampur price"
    second = json.loads(json.dumps(GOOD)); second["slug"] = "second-guide"; second["title"] = "Second Guide"
    pubs.append({"slug": "second-guide", "title": "Second Guide", "keyword": kw + " cost", "page_type": "guide", "date": "2026-11-25", "modified": "2026-11-25", "description": "d"})
    (state / "drafts" / "second-guide.json").write_text(json.dumps(second))
    facts = json.loads((r / "seo-agent/facts.json").read_text()); cfg = json.loads((r / "seo-agent/config.json").read_text())
    pub.rerender_others(pubs, "second-guide", r / "site/blog", cfg, facts, state)
    first_page = (r / "site/blog/website-for-hotel-in-manali/index.html").read_text()
    assert "Related guides" in first_page and "/blog/second-guide/" in first_page      # old page now links to the new one
    urls = indexnow.urls_from_paths(["site/blog/x-y/index.html", "site/index.html", "site/blog/index.html", "seo-agent/state/published.json"], CFG)
    assert urls == [CFG["site_url"] + "/blog/x-y/", CFG["site_url"] + "/blog/"]
    pl = indexnow.payload(urls, CFG)
    assert pl["host"] == "anmolrattan.netlify.app" and pl["keyLocation"].endswith(CFG["indexnow_key"] + ".txt")
    assert (HERE.parent / "site" / (CFG["indexnow_key"] + ".txt")).read_text() == CFG["indexnow_key"]
    print("ok two-way internal links, IndexNow payload + key file")

if __name__ == "__main__":
    for t in (test_rules, test_dedupe_and_fallback, test_happy_path, test_bad_price_is_blocked, test_llm_check_blocks,
              test_aeo_page_elements, test_scoring_and_diversity, test_learning_loop, test_refresh_run, test_internal_links_and_indexnow): t()
    print("ALL PASSED")
