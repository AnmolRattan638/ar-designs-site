"""Render a page that matches the main site's palette, with Article + FAQ + Breadcrumb schema."""
import html, json
from urllib.parse import quote

CSS = """:root{--black:#06080d;--navy:#0a1220;--navy-card:#0d182b;--gold:#c9a84c;--gold-bright:#f0c040;--text:#e8ebf2;--muted:#9aa3b2;--border:rgba(201,168,76,.28)}
*{box-sizing:border-box;margin:0;padding:0}html{scroll-behavior:smooth}
body{font-family:'Inter',system-ui,-apple-system,sans-serif;color:var(--text);background:var(--black);line-height:1.7;-webkit-font-smoothing:antialiased}
body::before{content:"";position:fixed;inset:0;z-index:-1;background:radial-gradient(1200px 800px at 80% -10%,rgba(27,42,74,.65),transparent 60%),radial-gradient(800px 600px at 50% 110%,rgba(201,168,76,.1),transparent 60%),#06080d}
h1,h2,h3{font-family:'Playfair Display',serif;letter-spacing:.3px}a{color:var(--gold-bright)}
.top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 24px;border-bottom:1px solid rgba(201,168,76,.2);background:rgba(6,8,13,.92)}
.top a.logo{font-family:'Playfair Display',serif;font-weight:900;font-size:1.25rem;text-decoration:none;background:linear-gradient(135deg,var(--gold-bright),var(--gold));-webkit-background-clip:text;background-clip:text;color:transparent}
.wa{padding:10px 18px;border-radius:999px;background:linear-gradient(135deg,var(--gold-bright),var(--gold));color:#000;font-weight:800;text-decoration:none;font-size:.85rem;min-height:44px;display:inline-flex;align-items:center}
main{max-width:820px;margin:0 auto;padding:44px 20px 70px}
.crumbs{font-size:.8rem;color:var(--muted);margin-bottom:18px}.crumbs a{color:var(--muted)}
h1{font-size:clamp(1.9rem,4.5vw,2.8rem);line-height:1.2;margin-bottom:18px;background:linear-gradient(135deg,#fff 0%,var(--gold-bright) 55%,var(--gold) 100%);-webkit-background-clip:text;background-clip:text;color:transparent}
.intro{font-size:1.08rem;color:#e8ebf2;padding:16px 20px;border-left:3px solid var(--gold-bright);background:rgba(10,18,32,.7);border-radius:0 12px 12px 0;margin-bottom:30px}
h2{font-size:1.45rem;color:var(--gold-bright);margin:34px 0 10px}p{color:#cbd5e1;margin-bottom:12px}ul{margin:0 0 14px 22px;color:#cbd5e1}li{margin-bottom:6px}
.faq details{background:linear-gradient(150deg,var(--navy),var(--navy-card));border:1px solid var(--border);border-radius:14px;margin-bottom:10px}
.faq summary{cursor:pointer;padding:14px 18px;font-weight:700;color:var(--gold-bright);min-height:44px}.faq details p{padding:0 18px 14px;margin:0}
.cta{margin-top:38px;padding:26px;text-align:center;border:1px solid var(--border);border-radius:20px;background:linear-gradient(150deg,var(--navy),var(--navy-card))}
.cta p{color:var(--text);margin-bottom:16px}
.more{margin-top:26px;font-size:.92rem}.more a{margin-right:14px}
footer{text-align:center;padding:24px;color:var(--muted);font-size:.82rem;border-top:1px solid rgba(201,168,76,.15)}
.list a.card{display:block;text-decoration:none;padding:18px 20px;margin-bottom:12px;border:1px solid var(--border);border-radius:16px;background:linear-gradient(150deg,var(--navy),var(--navy-card))}
.byline{font-size:.85rem;color:var(--muted);margin:-6px 0 18px}.byline a{color:var(--muted)}
.takeaways{margin:0 0 28px;padding:16px 20px;border:1px solid var(--border);border-radius:14px;background:rgba(13,24,43,.7)}
.takeaways b{color:var(--gold-bright);font-family:'Playfair Display',serif}.takeaways ul{margin:8px 0 0 20px}
.tablewrap{overflow-x:auto;margin:0 0 18px}table{border-collapse:collapse;width:100%;min-width:420px;font-size:.95rem}
th,td{padding:10px 12px;border:1px solid var(--border);text-align:left;color:#cbd5e1}th{color:var(--gold-bright);background:rgba(13,24,43,.9)}
.list a.card b{color:var(--gold-bright);display:block;font-size:1.05rem}.list a.card span{color:var(--muted);font-size:.9rem}"""

FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;600;700&display=swap" />'

def e(x): return html.escape(str(x), quote=True)
def ld(obj): return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False).replace("</", "<\\/") + "</script>"

def shell(title, desc, canonical, body, schema, cfg):
    return ("<!doctype html>\n<html lang=\"en-IN\"><head><meta charset=\"UTF-8\" /><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n"
            "<title>%s | %s</title><meta name=\"description\" content=\"%s\" /><link rel=\"canonical\" href=\"%s\" />\n"
            "<meta name=\"robots\" content=\"index, follow, max-snippet:-1, max-image-preview:large\" />\n"
            "<meta property=\"og:title\" content=\"%s\" /><meta property=\"og:description\" content=\"%s\" /><meta property=\"og:url\" content=\"%s\" /><meta property=\"og:type\" content=\"article\" /><meta property=\"og:locale\" content=\"en_IN\" />\n"
            "%s<style>%s</style>%s</head><body>\n"
            "<div class=\"top\"><a class=\"logo\" href=\"/\">%s</a><a class=\"wa\" href=\"%s\" target=\"_blank\" rel=\"noopener noreferrer\">Chat on WhatsApp</a></div>\n"
            "%s\n<footer>© %s — %s. <a href=\"/\">Home</a> · <a href=\"/blog/\">Guides</a></footer></body></html>\n"
            ) % (e(title), e(cfg["brand"]), e(desc), e(canonical), e(title), e(desc), e(canonical), FONTS, CSS, schema,
                 e(cfg["brand"]), e(cfg["whatsapp"]), body, str(__import__("datetime").date.today().year), e(cfg["author"]) + " (" + e(cfg["brand"]) + ")")

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

def _fmt(iso):
    y, m, d = iso.split("-")
    return "%d %s %s" % (int(d), MONTHS[int(m) - 1], y)

def render_page(d, cfg, facts, date_iso, published_iso=None, related=None):
    published_iso = published_iso or date_iso
    url = "%s/blog/%s/" % (cfg["site_url"], d["slug"])
    secs = ""
    for s in d["sections"]:
        secs += "<h2>%s</h2>" % e(s["h2"]) + "".join("<p>%s</p>" % e(p) for p in s["paragraphs"])
        if s.get("bullets"):
            secs += "<ul>" + "".join("<li>%s</li>" % e(b) for b in s["bullets"]) + "</ul>"
    take = ""
    if d.get("key_takeaways"):
        take = '<div class="takeaways"><b>Key takeaways</b><ul>%s</ul></div>' % "".join("<li>%s</li>" % e(x) for x in d["key_takeaways"])
    table = ""
    t = d.get("comparison_table")
    if t:
        table = ('<h2>%s</h2><div class="tablewrap"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
                 % (e(t["caption"]), "".join("<th>%s</th>" % e(h) for h in t["headers"]),
                    "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % e(c) for c in r) for r in t["rows"])))
    rel = ""
    if related:
        rel = '<h2>Related guides</h2><div class="list">%s</div>' % "".join(
            '<a class="card" href="/blog/%s/"><b>%s</b><span>%s</span></a>' % (e(p["slug"]), e(p["title"]), e(p["description"])) for p in related)
    faq = "".join("<details><summary>%s</summary><p>%s</p></details>" % (e(f["q"]), e(f["a"])) for f in d["faq"])
    wa = cfg["whatsapp"] + "?text=" + quote("Hi Anmol, I read your page: " + d["title"])
    samples = "".join('<a href="%s" target="_blank" rel="noopener noreferrer">%s</a>' % (e(s["url"]), e(s["name"])) for s in facts["samples"])
    byline = '<div class="byline">By <a href="/">%s</a> &middot; Updated <time datetime="%s">%s</time></div>' % (e(cfg["author"]), e(date_iso), _fmt(date_iso))
    body = ('<main><div class="crumbs"><a href="/">Home</a> / <a href="/blog/">Guides</a> / %s</div><h1>%s</h1>%s<div class="intro">%s</div>%s%s%s'
            '<h2>Frequently asked questions</h2><div class="faq">%s</div>%s'
            '<div class="cta"><p>%s</p><a class="wa" href="%s" target="_blank" rel="noopener noreferrer">Chat on WhatsApp</a></div>'
            '<div class="more"><a href="/#services">See all packages</a><a href="/#agents">AI agent systems</a><a href="/#faq">More FAQs</a></div>'
            '<div class="more">Live samples: %s</div></main>') % (e(d["h1"]), e(d["h1"]), byline, e(d["intro"]), take, secs, table, faq, rel, e(d["cta_text"]), e(wa), samples)
    same_as = [u for u in cfg.get("same_as", []) if u]
    author = {"@type": "Person", "name": cfg["author"], "url": cfg["site_url"] + "/"}
    publisher = {"@type": "Organization", "name": cfg["brand"], "url": cfg["site_url"] + "/"}
    if same_as:
        author["sameAs"] = same_as; publisher["sameAs"] = same_as
    schema = ld({"@context": "https://schema.org", "@graph": [
        {"@type": "Article", "headline": d["title"], "description": d["meta_description"], "datePublished": published_iso,
         "dateModified": date_iso, "inLanguage": "en-IN", "mainEntityOfPage": url, "author": author, "publisher": publisher,
         "speakable": {"@type": "SpeakableSpecification", "cssSelector": [".intro", ".takeaways"]}},
        {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": f["q"], "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in d["faq"]]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": cfg["site_url"] + "/"},
            {"@type": "ListItem", "position": 2, "name": "Guides", "item": cfg["site_url"] + "/blog/"},
            {"@type": "ListItem", "position": 3, "name": d["h1"], "item": url}]}]})
    return shell(d["title"], d["meta_description"], url, body, schema, cfg)

def render_index(published, cfg):
    cards = "".join('<a class="card" href="/blog/%s/"><b>%s</b><span>%s</span></a>' % (e(p["slug"]), e(p["title"]), e(p["description"]))
                    for p in sorted(published, key=lambda p: p["date"], reverse=True))
    body = '<main><h1>Guides</h1><p>Practical answers on websites, AI chatbots, AI animation and lead generation for small businesses.</p><div class="list">%s</div></main>' % cards
    return shell("Guides", "Practical guides on websites, AI chatbots, AI animation and lead generation for small businesses.",
                 cfg["site_url"] + "/blog/", body, "", cfg)
