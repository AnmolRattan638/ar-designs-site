"""Optional: real queries from Google Search Console ("striking distance": position 8-30)."""
import json
from datetime import date, timedelta
from urllib.parse import quote

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

def fetch(site, sa_json=None, days=28):
    """sa_json=None -> keyless login (Workload Identity Federation / Application Default Credentials).
    sa_json given -> legacy service-account key."""
    from google.auth.transport.requests import AuthorizedSession
    if sa_json:
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_info(json.loads(sa_json), scopes=SCOPES)
    else:
        import google.auth
        creds, _ = google.auth.default(scopes=SCOPES)
    s = AuthorizedSession(creds)
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
