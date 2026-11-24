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


## v2: weekly, scored, answer-engine ready, and it learns

- **Cadence:** weekly. Runs alternate between a **new page** and a **refresh** of an existing page (`--mode auto|new|refresh`).
- **Keywords:** Google autocomplete plus question-style seeds ("how much does...", "is ... worth it"). Every candidate gets a transparent intent score (buying words, city, industry, question form), and the pick is spread across industries and cities.
- **AEO/GEO page format:** answer-first intro, 3 quotable key takeaways, optional fact-checked comparison table, FAQ + FAQPage schema, Article/Person/Breadcrumb schema, speakable markup, visible byline and "Updated" date, and two-way "Related guides" links. Set `same_as` in `config.json` (LinkedIn, Instagram, etc.) to add entity links to the schema.
- **Learning loop:** `state/experiments.json` logs every page. At 14 and 28 days `agent/analyst.py` scores it against Search Console (needs `GSC_SITE` + the Google login), writes `state/lessons.json`, and those lessons nudge the next keyword score. Each PR includes a learning report.
- **Refresh:** pages whose queries sit at positions 8-30, or that have not changed for 60 days, are rewritten (same fact-check rules) with the real queries added.
- **IndexNow:** after a merge, `.github/workflows/indexnow.yml` pings Bing/IndexNow with the changed guide URLs. The key file lives in `site/`.

Offline tests: `cd seo-agent && python -I tests/test_offline.py`

### Content depth (long, detailed pages)

Each page is built in passes, not in one call:
1. **Research:** real questions people type about the keyword (Google autocomplete).
2. **Outline:** 7-8 sections with distinct purposes (answer, process, costs from `facts.json`, mistakes, checklist, how AR Designs works, next steps).
3. **Sections:** one LLM call per section (220-340 words, steps/bullets/examples, optional H3s).
4. **Frame:** direct-answer intro, 3 key takeaways, optional comparison table, 8-question FAQ.
5. **Quality gates** (`seo-agent/agent/quality.py`): at least 1,500 words, 7+ sections, no thin sections, keyword in title/H1/intro, no filler phrases or repeated sentences. Thin or flawed parts get **one** rewrite.
6. **Fact-check:** prices, hours, invented statistics/percentages, guarantees. Hard problems block the page; soft ones are listed in the PR.

Set the optional repo secret `ANTHROPIC_API_KEY` to write with Claude instead of the free Groq model (better prose, paid per run).
