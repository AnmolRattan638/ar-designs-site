"""Offline end-to-end tests: stubbed LLM + stubbed keyword source. Run: python -I tests/test_offline.py"""
import json, re, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from agent import run, factcheck, choose, writer, keywords, analyst, gsc, indexnow, quality, research  # noqa

CFG = json.loads((HERE / "config.json").read_text())
FACTS = json.loads((HERE / "facts.json").read_text())

def para(seed, n=7):
    return " ".join("Owner %d reviews checklist item %d, notes the result under heading %d and moves to the next task calmly." % (seed, i, seed * 10 + i) for i in range(n))

TITLES = ["The short answer", "Step by step process", "What it costs", "Common mistakes", "Checklist before you start",
          "How AR Designs approaches it", "Local considerations", "Next steps"]

def fake_section(h2, thin=False, filler=False):
    k = TITLES.index(h2) + 1 if h2 in TITLES else 9
    s = {"h2": h2, "paragraphs": [para(k * 3 + j, 2 if thin else 7) for j in range(1 if thin else 3)]}
    if filler: s["paragraphs"][0] += " This will unlock the full potential of the business."
    if k == 2: s["steps"] = ["Step %d: do the task and write the result down." % i for i in range(5)]
    else: s["bullets"] = ["Point %d for section %d, kept short" % (i, k) for i in range(4)]
    if k == 3: s["example"] = "For example, a homestay owner compares the Basic and Standard packages before choosing one."
    return s

def fake_frame(keyword, bad=False):
    intro = ("A simple website starts at Rs 1,499 and is delivered in 24 hours. Bigger sites with up to 5 pages start at Rs 2,299. "
             "This guide explains the steps, the costs and the common mistakes so you can decide calmly before you spend anything.")
    if bad:
        intro = "A website costs Rs 999 and we guarantee page one rankings. This guide explains the steps and costs for every owner reading it today."
    return {"intro": intro,
            "key_takeaways": ["Basic website: Rs 1,499, delivered in 24 hours.", "Standard website: Rs 2,299, delivered in 48 hours.", "Every package includes a WhatsApp button."],
            "comparison_table": {"caption": "Website packages", "headers": ["Package", "Price", "Delivery"], "rows": [["Basic", "Rs 1,499", "24 hours"], ["Standard", "Rs 2,299", "48 hours"]]},
            "faq": [{"q": "Question number %d about this topic?" % i, "a": " ".join("Answer %d sentence %d explains one useful point clearly." % (i, j) for j in range(5))} for i in range(8)],
            "cta_text": "Tell me about your business on WhatsApp."}

def fake_outline(keyword):
    slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-")[:60]
    title = ("%s: Costs, Steps and Mistakes" % keyword.title())[:62]
    return {"slug": slug, "title": title, "meta_description": "A plain-language guide to the steps, costs and common mistakes, with real package prices and delivery times from AR Designs.",
            "h1": title, "search_intent": "commercial",
            "sections": [{"h2": t, "goal": "g", "must_cover": ["a", "b"], "format": "steps" if "Step" in t else "explainer"} for t in TITLES],
            "faq_questions": ["Question number %d about this topic?" % i for i in range(8)]}

def make_draft(keyword, bad=False):
    o = fake_outline(keyword); f = fake_frame(keyword, bad)
    return writer.assemble(o, [fake_section(t) for t in TITLES], f)

class FakeLLM:
    def __init__(self, bad=False, check_ok=True, thin=False, filler=False):
        self.bad, self.check_ok, self.thin, self.filler = bad, check_ok, thin, filler
        self.calls, self.refresh_seen, self.fixed = [], False, False
    def json(self, system, user, **kw):
        m = re.search(r"Stage: (\w+)", system)
        stage = m.group(1) if m else ("pick" if "SEO strategist" in system else "check" if "fact-checker" in system else "?")
        self.calls.append(stage)
        if stage == "pick":
            first = user.split("Keywords:\n- ", 1)[1].split("\n")[0].split(" (own")[0]
            return {"keyword": first, "page_type": "landing", "reason": "clear local intent"}
        if stage == "check":
            return {"ok": self.check_ok, "issues": [] if self.check_ok else ["unsupported claim"]}
        kw = re.search(r"KEYWORD: (.+)", user).group(1).strip()
        if stage == "outline":
            if "REFRESH MODE" in user: self.refresh_seen = "hotel website cost manali" in user
            return fake_outline(kw)
        if stage == "section":
            h2 = re.search(r"SECTION: (.+)", user).group(1).strip()
            expanding = "PREVIOUS VERSION" in user
            return fake_section(h2, thin=self.thin and not expanding, filler=self.filler and not expanding)
        if stage == "frame":
            return fake_frame(kw, bad=self.bad)
        raise AssertionError(stage)

def fake_fetch(q): return [q + " price", q + " cost", "unrelated thing entirely"]

def sandbox():
    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(HERE.parent, tmp / "r", ignore=shutil.ignore_patterns("__pycache__", "out", ".git"))
    (tmp / "r/seo-agent/out").mkdir(exist_ok=True)
    c = json.loads((tmp / "r/seo-agent/config.json").read_text()); c["llm_pause_seconds"] = 0
    (tmp / "r/seo-agent/config.json").write_text(json.dumps(c))
    return tmp / "r"

def published(r): return json.loads((r / "seo-agent/state/published.json").read_text())

def test_rules():
    d = make_draft("website for hotel in manali")
    assert factcheck.deterministic(d, FACTS) == []
    d["sections"][0]["paragraphs"][0] = "Delivered in 72 hours for $17 (Rs 1,499) or $299, from 850+ clients, and 70% of owners agree."
    iss = factcheck.deterministic(d, FACTS)
    assert any("72" in i for i in iss) and any("850" in i for i in iss) and any("70%" in i for i in iss) and not any("$17" in i or "1,499" in i or "$299" in i for i in iss), iss
    assert writer.validate({"slug": "x"}) and not writer.validate(make_draft("website for hotel in manali"), CFG)
    print("ok rule checks (prices, hours, invented stats)")

def test_dedupe_and_fallback():
    cands = [{"keyword": "website for cafe in shimla", "priority": 1}, {"keyword": "ai chatbot for hotel", "priority": 1}]
    p = choose.choose(cands, ["Website for Cafe in Shimla"], None)
    assert p["keyword"] == "ai chatbot for hotel" and p["page_type"] == "guide"
    print("ok dedupe + fallback")

def test_happy_path():
    r = sandbox(); llm = FakeLLM()
    assert run.main(["--root", str(r), "--force"], llm=llm, fetch=fake_fetch) == 0
    slug = published(r)[0]["slug"]
    page = (r / ("site/blog/%s/index.html" % slug)).read_text()
    assert ('<link rel="canonical" href="https://anmolrattan.netlify.app/blog/%s/"' % slug) in page
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S): json.loads(m.replace("<\\/", "</"))
    assert "FAQPage" in page and "BreadcrumbList" in page and "Article" in page
    assert "/blog/%s/" % slug in (r / "site/sitemap.xml").read_text() and slug in (r / "site/llms.txt").read_text()
    assert 'href="/blog/"' in (r / "site/index.html").read_text() and slug in (r / "site/blog/index.html").read_text()
    body = (r / "seo-agent/out/pr_body.md").read_text()
    assert "clear local intent" in body and "Quality gates" in body
    assert llm.calls.count("outline") == 1 and llm.calls.count("section") == 8 and llm.calls.count("frame") == 1
    assert run.main(["--root", str(r)], llm=llm, fetch=fake_fetch) == 0
    assert json.loads((r / "seo-agent/out/summary.json").read_text()).get("skipped") is True
    print("ok happy path: outline + 8 sections + frame, quality report in PR, cadence skip")

def test_detailed_page_elements():
    r = sandbox()
    assert run.main(["--root", str(r), "--force"], llm=FakeLLM(), fetch=fake_fetch) == 0
    slug = published(r)[0]["slug"]
    page = (r / ("site/blog/%s/index.html" % slug)).read_text()
    assert 'class="toc"' in page and 'id="step-by-step-process"' in page and 'href="#what-it-costs"' in page
    assert '<ol class="steps">' in page and 'class="example"' in page and "<table>" in page and "Key takeaways" in page
    assert "SpeakableSpecification" in page and "min read" in page and '"wordCount"' in page and "<time datetime=" in page
    wc = int(re.search(r'"wordCount": (\d+)', page).group(1))
    assert wc >= 1500, wc
    assert (r / ("seo-agent/state/drafts/%s.json" % slug)).exists()
    exps = json.loads((r / "seo-agent/state/experiments.json").read_text())
    assert exps[0]["mode"] == "new" and exps[0]["results"] == []
    bad = make_draft("website for hotel in manali"); bad["comparison_table"]["rows"][0][1] = "Rs 999"
    assert any("999" in i for i in factcheck.deterministic(bad, FACTS))
    print("ok detailed page: TOC, steps, example, table, %d words, stored draft, experiment logged" % wc)

def test_bad_price_is_blocked():
    r = sandbox(); llm = FakeLLM(bad=True)
    assert run.main(["--root", str(r), "--force"], llm=llm, fetch=fake_fetch) == 3
    assert not published(r)
    assert llm.calls.count("frame") == 2 and llm.calls.count("outline") == 1 and llm.calls.count("section") == 8   # one fix pass, frame only
    print("ok bad price + guarantee blocked, one fix pass that rewrites only the frame")

def test_llm_check_blocks():
    r = sandbox()
    assert run.main(["--root", str(r), "--force"], llm=FakeLLM(check_ok=False), fetch=fake_fetch) == 3
    print("ok LLM fact-check can block")

def test_thin_and_filler_content_is_fixed():
    r = sandbox(); llm = FakeLLM(thin=True)          # first draft too thin; the expansion pass fixes it
    assert run.main(["--root", str(r), "--force"], llm=llm, fetch=fake_fetch) == 0
    assert llm.calls.count("section") == 16, llm.calls.count("section")
    r = sandbox(); llm = FakeLLM(filler=True)
    assert run.main(["--root", str(r), "--force"], llm=llm, fetch=fake_fetch) == 0
    assert "unlock the" not in (r / ("site/blog/%s/index.html" % published(r)[0]["slug"])).read_text().lower()
    q = quality.report(make_draft("website for hotel in manali"), "website for hotel in manali", CFG)
    assert not q["problems"] and all(q["checks"].values()), q["problems"]
    thin = writer.assemble(fake_outline("website for hotel in manali"), [fake_section(t, thin=True) for t in TITLES], fake_frame("x"))
    q = quality.report(thin, "website for hotel in manali", CFG)
    assert not q["checks"]["enough_words"] and q["hard"] and len(q["thin"]) == 8
    print("ok quality gates: thin sections expanded, filler rewritten, hard vs soft problems")

def test_research_questions():
    qs = research.questions_for("website for hotel in manali", fetch=lambda q: [q + " price", "totally unrelated query here", "how to make a website for hotel in manali"])
    assert qs and all("manali" in x or "hotel" in x for x in qs) and "totally unrelated query here" not in qs
    print("ok research: %d on-topic real questions" % len(qs))

def test_scoring_and_diversity():
    a = keywords.score("how much does a website cost for a hotel in manali", CFG)
    b = keywords.score("website templates free", CFG)
    assert a > b + 3, (a, b)
    boosted = keywords.score("website for hotel in shimla", CFG, {"bonus": {"industry:hotel": 1.5}})
    assert boosted == keywords.score("website for hotel in shimla", CFG) + 1.5
    cands = [{"keyword": "website for hotel in shimla", "priority": 5.0}, {"keyword": "website for gym in mandi", "priority": 4.5}]
    pub = [{"keyword": "website for hotel in manali", "slug": "x", "date": "2026-01-01"}] * 2
    assert choose.choose(cands, [], None, cfg=CFG, published=pub)["keyword"] == "website for gym in mandi"
    rel = keywords.related([{"keyword": "seo for hotel in kullu", "slug": "a", "date": "2026-01-01"}, {"keyword": "ai chatbot for gym", "slug": "b", "date": "2026-01-02"}], "website for hotel in manali", CFG)
    assert [x["slug"] for x in rel] == ["a"]
    cs = keywords.discover(dict(CFG, seeds_per_run=2, question_seeds_per_run=3), "2026-11-24", fetch=lambda q: [], sleep=0)
    assert any(c["source"] == "question" for c in cs)
    print("ok scoring, diversity, related links, question seeds")

def test_learning_loop():
    exps = analyst.log_experiment([], "website-for-hotel-in-manali", "u", "website for hotel in manali", "landing", "new", CFG, "2026-10-01")
    analyst.log_experiment(exps, "seo-for-gym-in-mandi", "u2", "seo for gym in mandi", "landing", "new", CFG, "2026-10-01")
    rows = [{"page": "https://x/blog/website-for-hotel-in-manali/", "query": "hotel website manali", "clicks": 3, "impressions": 40, "position": 6.2}]
    analyst.evaluate(exps, rows, "2026-10-10")
    assert exps[0]["results"] == []
    analyst.evaluate(exps, rows, "2026-10-20")
    assert exps[0]["results"][-1]["label"] == "winning" and exps[1]["results"][-1]["label"] == "no_impressions" and len(exps[0]["results"]) == 1
    analyst.evaluate(exps, rows, "2026-11-01")
    assert [r["checkpoint"] for r in exps[0]["results"]] == [14, 28]
    L = analyst.build_lessons(exps, "2026-11-01")
    assert L["bonus"]["industry:hotel"] > 0 > L["bonus"]["industry:gym"] and L["notes"]
    pubs = [{"slug": "website-for-hotel-in-manali", "date": "2026-09-01", "keyword": "k"}, {"slug": "new-one", "date": "2026-11-01", "keyword": "k2"}]
    sq = [{"page": "https://x/blog/website-for-hotel-in-manali/", "query": "hotel website cost manali", "clicks": 0, "impressions": 30, "position": 14.0}]
    c = analyst.refresh_candidate(pubs, sq, "2026-11-10", CFG)
    assert c["slug"] == "website-for-hotel-in-manali" and c["queries"] == ["hotel website cost manali"]
    assert analyst.refresh_candidate(pubs[1:], sq, "2026-11-10", CFG) is None
    assert "winning" in analyst.report_md(exps, L, True)
    sr = gsc.striking_queries(sq + [{"page": "https://x/", "query": "web design shimla", "clicks": 0, "impressions": 12, "position": 12.0}], ["website-for-hotel-in-manali"])
    assert [x["keyword"] for x in sr] == ["web design shimla"]
    print("ok learning loop: checkpoints, lessons, refresh candidate, striking queries")

def test_refresh_run():
    r = sandbox()
    cfgp = r / "seo-agent/config.json"; c = json.loads(cfgp.read_text()); c["refresh_min_age_days"] = 0; cfgp.write_text(json.dumps(c))
    assert run.main(["--root", str(r), "--force"], llm=FakeLLM(), fetch=fake_fetch) == 0
    slug = published(r)[0]["slug"]
    rows = [{"page": "https://anmolrattan.netlify.app/blog/%s/" % slug, "query": "hotel website cost manali", "clicks": 0, "impressions": 30, "position": 14.0}]
    spy = FakeLLM()
    assert run.main(["--root", str(r), "--force"], llm=spy, fetch=fake_fetch, page_rows=rows) == 0
    assert spy.refresh_seen
    assert json.loads((r / "seo-agent/state/last_run.json").read_text())["mode"] == "refresh"
    assert len(published(r)) == 1 and published(r)[0]["slug"] == slug
    assert "## Page refresh for approval" in (r / "seo-agent/out/pr_body.md").read_text()
    print("ok refresh run: real queries reach the outline, page updated in place")

def test_internal_links_and_indexnow():
    from agent import publish as pub
    r = sandbox()
    assert run.main(["--root", str(r), "--force"], llm=FakeLLM(), fetch=fake_fetch) == 0
    state = r / "seo-agent/state"; pubs = published(r); slug, kw = pubs[0]["slug"], pubs[0]["keyword"]
    second = make_draft(kw + " cost"); second["slug"] = "second-guide"
    pubs.append({"slug": "second-guide", "title": "Second Guide", "keyword": kw + " cost", "page_type": "guide", "date": "2026-11-25", "modified": "2026-11-25", "description": "d"})
    (state / "drafts" / "second-guide.json").write_text(json.dumps(second))
    pub.rerender_others(pubs, "second-guide", r / "site/blog", json.loads((r / "seo-agent/config.json").read_text()), FACTS, state)
    first_page = (r / ("site/blog/%s/index.html" % slug)).read_text()
    assert "Related guides" in first_page and "/blog/second-guide/" in first_page
    urls = indexnow.urls_from_paths(["site/blog/x-y/index.html", "site/index.html", "site/blog/index.html", "seo-agent/state/published.json"], CFG)
    assert urls == [CFG["site_url"] + "/blog/x-y/", CFG["site_url"] + "/blog/"]
    pl = indexnow.payload(urls, CFG)
    assert pl["host"] == "anmolrattan.netlify.app" and pl["keyLocation"].endswith(CFG["indexnow_key"] + ".txt")
    assert (HERE.parent / "site" / (CFG["indexnow_key"] + ".txt")).read_text() == CFG["indexnow_key"]
    print("ok two-way internal links, IndexNow payload + key file")

if __name__ == "__main__":
    for t in (test_rules, test_dedupe_and_fallback, test_happy_path, test_detailed_page_elements, test_bad_price_is_blocked, test_llm_check_blocks,
              test_thin_and_filler_content_is_fixed, test_research_questions, test_scoring_and_diversity, test_learning_loop, test_refresh_run,
              test_internal_links_and_indexnow): t()
    print("ALL PASSED")
