"""Write the page, then keep sitemap.xml, llms.txt, the guides index and the home footer link in sync."""
import json, re
from pathlib import Path
from .render import render_index

def slugify(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:60].strip("-") or "page"

def unique_slug(blog_dir, slug):
    cand, n = slug, 2
    while (blog_dir / cand).exists():
        cand = "%s-%d" % (slug, n); n += 1
    return cand

def update_sitemap(path, loc, today):
    xml = path.read_text(encoding="utf-8")
    if "<loc>%s</loc>" % loc in xml:
        return
    entry = "  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>\n" % (loc, today)
    path.write_text(xml.replace("</urlset>", entry + "</urlset>"), encoding="utf-8")

def touch_lastmod(path, loc, today):
    xml = path.read_text(encoding="utf-8")
    new = re.sub(r"(<loc>%s</loc>\s*<lastmod>)[^<]*(</lastmod>)" % re.escape(loc), r"\g<1>%s\g<2>" % today, xml)
    if new != xml:
        path.write_text(new, encoding="utf-8")

def update_llms(path, title, url, desc):
    t = path.read_text(encoding="utf-8")
    line = "- [%s](%s): %s\n" % (title, url, desc)
    if url in t:
        return
    if "## Guides" not in t:
        t = t.replace("## Notes for AI systems", "## Guides\n\n## Notes for AI systems") if "## Notes for AI systems" in t else t + "\n## Guides\n"
    t = t.replace("## Guides\n", "## Guides\n" + line, 1)
    path.write_text(t, encoding="utf-8")

def ensure_footer_link(index_path):
    s = index_path.read_text(encoding="utf-8")
    if 'href="/blog/"' in s:
        return
    old = "Crafted for local business growth.</p>"
    if old in s:
        s = s.replace(old, 'Crafted for local business growth. · <a href="/blog/" style="text-decoration:underline">Guides</a></p>', 1)
        index_path.write_text(s, encoding="utf-8")

def publish(draft, page_html, root, cfg, today, state):
    site = Path(root) / "site"
    blog = site / "blog"
    slug = unique_slug(blog, slugify(draft["slug"] or draft["title"]))
    draft["slug"] = slug
    return slug, site, blog

def _store_draft(state_dir, draft):
    dd = Path(state_dir) / "drafts"; dd.mkdir(parents=True, exist_ok=True)
    (dd / (draft["slug"] + ".json")).write_text(json.dumps(draft, indent=1, ensure_ascii=False), encoding="utf-8")

def rerender_others(pub, skip_slug, blog, cfg, facts, state_dir):
    """Keep every page's 'Related guides' block current (two-way internal links). Only rewrites pages that changed."""
    from .render import render_page
    from .keywords import related
    for p in pub:
        dp = Path(state_dir) / "drafts" / (p["slug"] + ".json")
        if p["slug"] == skip_slug or not dp.exists():
            continue
        d = json.loads(dp.read_text(encoding="utf-8"))
        page = render_page(d, cfg, facts, p.get("modified") or p["date"], p["date"], related(pub, p["keyword"], cfg, p["slug"]))
        f = blog / p["slug"] / "index.html"
        if not f.exists() or f.read_text(encoding="utf-8") != page:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(page, encoding="utf-8")

def finish(draft, page_html, site, blog, cfg, today, state_dir, keyword, page_type, facts=None):
    slug = draft["slug"]
    (blog / slug).mkdir(parents=True, exist_ok=True)
    (blog / slug / "index.html").write_text(page_html, encoding="utf-8")
    url = "%s/blog/%s/" % (cfg["site_url"], slug)
    update_sitemap(site / "sitemap.xml", url, today)
    update_sitemap(site / "sitemap.xml", cfg["site_url"] + "/blog/", today)
    touch_lastmod(site / "sitemap.xml", cfg["site_url"] + "/blog/", today)
    update_llms(site / "llms.txt", draft["title"], url, draft["meta_description"])
    ensure_footer_link(site / "index.html")
    sp = Path(state_dir) / "published.json"
    pub = json.loads(sp.read_text(encoding="utf-8") or "[]")
    pub.append({"slug": slug, "title": draft["title"], "keyword": keyword, "page_type": page_type,
                "date": today, "modified": today, "description": draft["meta_description"]})
    sp.write_text(json.dumps(pub, indent=1, ensure_ascii=False), encoding="utf-8")
    _store_draft(state_dir, draft)
    (blog / "index.html").write_text(render_index(pub, cfg), encoding="utf-8")
    if facts:
        rerender_others(pub, slug, blog, cfg, facts, state_dir)
    return url

def refresh_finish(draft, page_html, site, blog, cfg, today, state_dir, facts=None):
    slug = draft["slug"]
    (blog / slug / "index.html").write_text(page_html, encoding="utf-8")
    url = "%s/blog/%s/" % (cfg["site_url"], slug)
    touch_lastmod(site / "sitemap.xml", url, today)
    touch_lastmod(site / "sitemap.xml", cfg["site_url"] + "/blog/", today)
    sp = Path(state_dir) / "published.json"
    pub = json.loads(sp.read_text(encoding="utf-8") or "[]")
    for p in pub:
        if p["slug"] == slug:
            p.update(title=draft["title"], description=draft["meta_description"], modified=today)
    sp.write_text(json.dumps(pub, indent=1, ensure_ascii=False), encoding="utf-8")
    _store_draft(state_dir, draft)
    (blog / "index.html").write_text(render_index(pub, cfg), encoding="utf-8")
    if facts:
        rerender_others(pub, slug, blog, cfg, facts, state_dir)
    return url
