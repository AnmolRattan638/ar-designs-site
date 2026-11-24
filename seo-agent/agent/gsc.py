"""Optional: real queries from Google Search Console ("striking distance": position 8-30)."""
import json
from datetime import date, timedelta
from urllib.parse import quote

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

def _session(sa_json=None):
    """sa_json=None -> keyless login (Workload Identity Federation / Application Default Credentials).
    sa_json given -> legacy service-account key."""
    from google.auth.transport.requests import AuthorizedSession
    if sa_json:
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(json.loads(sa_json), scopes=SCOPES)
    else:
        import google.auth
        creds, _ = google.auth.default(scopes=SCOPES)
    return AuthorizedSession(creds)

def fetch_pages(site, sa_json=None, days=28):
    """Per page + query rows for the last `days` days: [{page, query, clicks, impressions, position}]."""
    s = _session(sa_json)
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days)
    url = "https://searchconsole.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query" % quote(site, safe="")
    r = s.post(url, json={"startDate": start.isoformat(), "endDate": end.isoformat(),
                          "dimensions": ["page", "query"], "rowLimit": 1000}, timeout=30)
    r.raise_for_status()
    return [{"page": x["keys"][0], "query": x["keys"][1].lower(), "clicks": x["clicks"],
             "impressions": x["impressions"], "position": x["position"]} for x in r.json().get("rows", [])]

def striking_queries(page_rows, slugs):
    """Queries (not already owned by one of our guide pages) that sit at position 8-30: new-page candidates."""
    agg = {}
    for r in page_rows:
        if any("/blog/%s/" % s in r["page"] for s in slugs):
            continue
        a = agg.setdefault(r["query"], {"imp": 0, "pos": 0.0})
        a["imp"] += r["impressions"]; a["pos"] += r["position"] * r["impressions"]
    out = []
    for q, a in agg.items():
        pos = a["pos"] / a["imp"] if a["imp"] else 99
        if 8 <= pos <= 30 and a["imp"] >= 5:
            out.append({"keyword": q, "source": "gsc", "priority": 100 + a["imp"], "position": round(pos, 1), "impressions": a["imp"]})
    return out

def fetch(site, sa_json=None, days=28):
    """Query-level striking-distance rows (kept for backwards compatibility)."""
    s = _session(sa_json)
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=days)
    url = "https://searchconsole.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query" % quote(site, safe="")
    r = s.post(url, json={"startDate": start.isoformat(), "endDate": end.isoformat(),
                          "dimensions": ["query"], "rowLimit": 250}, timeout=30)
    r.raise_for_status()
    out = []
    for x in r.json().get("rows", []):
        if 8 <= x["position"] <= 30 and x["impressions"] >= 5:
            out.append({"keyword": x["keys"][0].lower(), "source": "gsc",
                        "priority": 100 + x["impressions"], "position": round(x["position"], 1),
                        "impressions": x["impressions"]})
    return out
