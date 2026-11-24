"""Tell Bing / IndexNow search engines about new or changed pages right after a merge (Bing feeds ChatGPT search and Copilot)."""
import argparse, json, subprocess, sys
from pathlib import Path

ENDPOINT = "https://api.indexnow.org/indexnow"

def urls_from_paths(paths, cfg):
    base = cfg["site_url"].rstrip("/")
    urls = []
    for p in paths:
        p = p.strip()
        if p.startswith("site/blog/") and p.endswith("/index.html"):
            rel = p[len("site/"):-len("index.html")]          # blog/<slug>/ or blog/
            u = "%s/%s" % (base, rel)
            if u not in urls:
                urls.append(u)
    return urls

def payload(urls, cfg):
    base = cfg["site_url"].rstrip("/")
    host = base.split("://", 1)[1]
    key = cfg["indexnow_key"]
    return {"host": host, "key": key, "keyLocation": "%s/%s.txt" % (base, key), "urlList": urls}

def changed_paths(before, after, root):
    if not before or set(before) == {"0"}:
        before = after + "~1"
    out = subprocess.run(["git", "diff", "--name-only", before, after], cwd=root, capture_output=True, text=True)
    return out.stdout.splitlines() if out.returncode == 0 else []

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="..")
    ap.add_argument("--before", default="")
    ap.add_argument("--after", default="HEAD")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    cfg = json.loads((root / "seo-agent" / "config.json").read_text(encoding="utf-8"))
    urls = urls_from_paths(changed_paths(a.before, a.after, root), cfg)
    if not urls:
        print("No guide pages changed; nothing to submit."); return 0
    import requests
    try:
        r = requests.post(ENDPOINT, json=payload(urls, cfg), headers={"Content-Type": "application/json; charset=utf-8"}, timeout=30)
        print("IndexNow:", r.status_code, "for", len(urls), "URL(s)")
    except Exception as ex:                     # never fail the workflow over a ping
        print("IndexNow ping skipped:", ex)
    return 0

if __name__ == "__main__":
    sys.exit(main())
