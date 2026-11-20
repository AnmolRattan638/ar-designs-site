# AR Designs: site + biweekly SEO agent

Everything is in this one repo:
- `site/` is your website (Netlify publishes this folder).
- `seo-agent/` finds a keyword every 2 weeks, drafts a page, fact-checks it against `facts.json`, and opens a **pull request**.
- **Merge the PR = approve and publish. Close it = reject.** Nothing goes live without you.

## One-time setup (about 30 minutes)

### 1. Put it on GitHub
Create a new GitHub repo (private is fine), then upload everything in this folder. Keep the structure exactly as it is (including the hidden `.github` folder).

### 2. Connect Netlify to the repo
Netlify -> Add new site -> Import from Git -> pick the repo. `netlify.toml` already sets the publish folder to `site`. Netlify will also build a **preview link for every PR**, which is how you review each new page before approving.
(If you already have a site on `anmolrattan.netlify.app`, open it in Netlify -> Site configuration -> Build & deploy -> Link repository, instead of making a new site.)

### 3. GitHub settings and secrets
- Repo -> Settings -> Actions -> General -> Workflow permissions: **Read and write**, and tick **Allow GitHub Actions to create and approve pull requests**.
- Repo -> Settings -> Secrets and variables -> Actions -> add:
  - `GROQ_API_KEY` (required)
  - `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (optional, for the "new page ready" message)
  - `GSC_SA_JSON` and `GSC_SITE` (optional, see step 4)

### 4. Google Search Console (free)
1. search.google.com/search-console -> Add property -> **URL prefix** -> your site address.
2. Verify with the HTML tag method and paste the tag into `site/index.html` inside `<head>`, then deploy. (Send me the tag and I'll place it.)
3. Sitemaps -> submit `sitemap.xml`.
4. Optional but best: let the agent read your real queries, with no key file. In Google Cloud create a service account, set up Workload Identity Federation for this GitHub repo, and add the service account's email as a **user** in Search Console (Settings -> Users). Put the provider path in the repo *variable* `GCP_WIF_PROVIDER`, the service account email in the variable `GCP_SERVICE_ACCOUNT`, and your property address in the secret `GSC_SITE` (for URL prefix it looks like `https://anmolrattan.netlify.app/`). If your organization allows keys you can instead put a JSON key in the `GSC_SA_JSON` secret.

Also add the site in **Bing Webmaster Tools** and submit the sitemap. Bing feeds ChatGPT search and Copilot.

### 5. First run
GitHub -> Actions -> "SEO Agent (biweekly)" -> Run workflow -> tick **force**. A pull request appears in a minute or two. Open the Netlify preview, read the page, then merge or close.

After that it runs every Monday morning and skips itself unless 13+ days have passed.

## What to edit
- `seo-agent/config.json`: cities, industries, keyword seeds, how often.
- `seo-agent/facts.json`: **the only source the agent may use for prices and claims.** When your prices change, change them here too (and in the site). The fact-check blocks any draft with a price or delivery time that is not in this file.

## Safety rules built in
- Prices, delivery times and banned claims (guarantees, awards, client counts, testimonials, office locations) are checked in code, then by a second LLM pass.
- One regeneration per draft only, then it stops and the run shows as failed (GitHub will email you). Nothing is published.
- Pages are added to `sitemap.xml` and `llms.txt` automatically, and a "Guides" link appears in the site footer after the first page.

## Test locally (no keys needed)
`cd seo-agent && python3 -I tests/test_offline.py`
