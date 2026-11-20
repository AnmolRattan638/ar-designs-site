"""Offline end-to-end test: stubbed LLM + stubbed keyword source. Run: python -I tests/test_offline.py"""
import json, re, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from agent import run, factcheck, choose, writer  # noqa

GOOD = {
    "slug": "website-for-hotel-in-manali", "title": "Website for a Hotel in Manali: Cost and What You Get",
    "meta_description": "What a hotel website in Manali costs and what is included, with delivery times and real package prices.",
    "h1": "Website for a Hotel in Manali: Cost and What You Get",
    "intro": "A simple hotel website starts at Rs 1,499 and is delivered in 24 hours. Bigger sites with up to 5 pages start at Rs 2,299.",
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

if __name__ == "__main__":
    for t in (test_rules, test_dedupe_and_fallback, test_happy_path, test_bad_price_is_blocked, test_llm_check_blocks): t()
    print("ALL PASSED")
