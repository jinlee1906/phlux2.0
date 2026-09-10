# Claude Code Kickoff Prompt — Chemical Engineering Job Tracker

> **How to use this:** save this file into the root of your fork as `PROJECT_BRIEF.md`, then
> open Claude Code in that directory and paste the "Kickoff message" section below. Claude Code
> will read the brief from disk and work through the phases. Do not paste the whole file as a
> chat message — it works better as a file Claude Code can re-read between phases.

---

## Kickoff message (paste this into Claude Code)

```
Read PROJECT_BRIEF.md in the repo root. Then:

1. Run Phase 0 and stop. Show me the diff before committing.
2. After I approve Phase 0, work through Phases 1-9 in order.
3. At the end of each phase: run `pytest`, show me what changed, commit with a
   conventional-commit message, and wait for my go-ahead before the next phase.
4. Anything on the ASK ME FIRST list: stop and ask. Do not guess.
5. If you cannot verify a URL or an API endpoint actually works, do not write it into
   a config file. Put it in `unverified.md` with a note on what you tried.

Start with Phase 0.
```

---

## Context

This repo is a fork of `Ph1so/phlux2.0`, a job scraper built for software engineering
internships at ~210 tech companies. I am a chemical engineering student and I am converting
it into a tracker for chemical engineering roles: process engineering, manufacturing,
R&D, bioprocess, refining, and adjacent work.

The bones are good — the scrape/dedupe/notify/publish loop is sound. What does not transfer
is the company registry, the keyword logic, and the per-company CSS selector approach. Most
of your work is replacing those three things.

### Existing architecture you are inheriting

| Component | File | What it does |
|---|---|---|
| Company registry | `companies.csv` | `Name, Link, ClassName` — ClassName is actually a DSL string |
| Action DSL | `phlux/scraping.py` (`Actions` class) | `CSS:sel`, `CLICK:sel[:pointer]`, `FILTER:kw`, `UNDETECTED`, joined by `->` |
| Extractor | `phlux/scraping.py` (`get_jobs_headless`) | Selenium Chrome, `tenacity` retry, 5 attempts |
| Orchestrator | `phlux/scraping.py` (`ScrapeManager`) | `ProcessPoolExecutor` across companies |
| Dedupe store | `storage.json` | `{"companies": {"Name": [{"title": str, "date": "M/D"}]}}` |
| Classifier | `phlux/utils.py` | `is_internship()` — substring match on a 5-item tuple |
| Notifier | `main.py` | Gmail SMTP, HTML digest, BCC list from `config.json` |
| Publisher | `generate_readme.py` | Renders `storage.json` into a giant HTML table README |
| CI | `.github/workflows/job-scraper.yml` | Cron `0 10-23,0 * * *`, commits results back to main |
| Tests | `tests/` | 740 lines of pytest, mostly mocking Selenium |

---

## GROUND RULES

These apply to every phase.

1. **Never fabricate a URL, an ATS tenant ID, or a CSS selector.** If you write a careers URL
   into `companies.yaml`, you must have actually fetched it and confirmed it returns postings.
   Unverified entries go in `unverified.md`, not in the config.
2. **No secrets in tracked files.** Every credential reads from an environment variable.
   `config.json` holds shape and preferences only — never an email address, never a key,
   never a spreadsheet ID.
3. **Scrape politely.** Minimum 2s between requests to the same host, a real descriptive
   User-Agent that identifies this as a personal job tracker, respect `robots.txt`, and never
   more than 4 concurrent workers. This is a personal tool hitting employers I want to work
   for — getting IP-banned by Dow is a self-inflicted wound.
4. **Prefer official JSON endpoints over browser automation.** Selenium is the fallback, not
   the default. See Phase 3.
5. **Tests before behavior changes.** If you are changing `is_internship`, write the test for
   the new behavior first.
6. **Small commits.** One phase, one commit, conventional-commit format.
7. **When my domain judgment is needed, ask.** You know software; I know which job titles a
   chemical engineer actually wants. Do not guess at the keyword taxonomy alone — draft it and
   have me correct it.

---

## ASK ME FIRST

Stop and ask before:
- Adding any company to the registry that I did not put on the list
- Sending any real email (test mode only, to my own address, until I say otherwise)
- Enabling the GitHub Actions cron schedule
- Any `git push --force`, history rewrite, or `git filter-repo`
- Committing anything larger than 1 MB
- Adding a dependency not already in `requirements.txt`

---

## PHASE 0 — Purge and secure

Do this before touching any logic.

1. **Truncate inherited data.**
   - `README.md` is ~9 MB of the upstream author's tech job listings. Replace with a real
     README (see Phase 9) — for now, a stub is fine.
   - `storage.json` is ~2 MB of stale postings. Replace with `{"companies": {}}`.
   - `storage_yc.json`, `prev_years/2025_internships.json`, `icons.json` — delete.
   - Delete `.DS_Store`, `__pycache__/`, and add both to `.gitignore`.

2. **Delete the auto-apply machinery.** Remove `auto_apply.py`,
   `.github/workflows/auto-apply.yml`, and the `autoApply()` function plus its call sites in
   `phlux/scraping.py`. Remove `GH_TOKEN` from the workflow env. I am not auto-submitting
   applications — it violates careers-portal terms and I want targeted applications, not volume.

3. **Scrub inherited PII and secrets.**
   - `config.json` contains the upstream author's Gmail and four other people's personal email
     addresses. Remove all of them.
   - `phlux/config.py` has `phiwe3296@gmail.com` hardcoded three times in `DEFAULT_EMAIL_CONFIG`.
     Replace with `os.environ.get("ALERT_EMAIL")` and fail loudly if unset.
   - `main.py` has a hardcoded Google Sheet key `1pZMYgV4GJZJIwyTSG4-...` in
     `update_internship_tracker()`. Remove the function entirely — Phase 7 replaces it.
   - Remove the Brandfetch icon system (`update_icons`, `ICONS_ID`, `ICONS_API`). It needs an
     API key I don't have and logos add nothing.
   - `grep -ri "gmail\|@.*\.com\|secret\|token\|key" --include="*.py" --include="*.json"` and
     report anything else you find.

4. **Fix the `.github/CODEOWNERS`** — it points at the upstream author.

5. Report: what you deleted, repo size before and after, anything you found that I should know about.

**Stop here. Show me the diff.**

---

## PHASE 1 — Rename and re-theme

Rename the package `phlux` to something I'll choose — ask me for the name, and offer 5
suggestions with a ChemE flavor. Update all imports, `pytest.ini`, and the workflow.
Keep the module structure; this is a rename, not a restructure.

---

## PHASE 2 — Domain model

Rewrite `phlux/models.py`. The current `Company(name, link, selector)` and
`ScrapeResult(name, jobs, link)` are too thin.

```python
@dataclass(frozen=True)
class Employer:
    name: str
    sector: Sector              # enum, see below
    ats: ATS                    # enum: WORKDAY | GREENHOUSE | LEVER | SUCCESSFACTORS | SELENIUM
    careers_url: str
    ats_config: dict            # tenant/site for Workday, board token for Greenhouse, DSL for Selenium
    hq_region: str | None
    enabled: bool = True

@dataclass
class Posting:
    employer: str
    title: str
    url: str | None             # deep link to the specific posting where the ATS gives us one
    location: str | None
    posted_date: date | None    # what the ATS says, when available
    first_seen: date            # when WE first saw it
    sector: Sector
    level: Level                # INTERNSHIP | CO_OP | NEW_GRAD | EXPERIENCED | UNKNOWN
    score: float
    tags: list[str]             # matched keywords, for explainability
    raw: dict                   # untouched ATS payload
```

`Sector` enum: `OIL_GAS`, `SPECIALTY_CHEM`, `PHARMA_BIOTECH`, `SEMICONDUCTOR`,
`ENERGY_STORAGE`, `COSMETICS_FRAGRANCE`, `ROBOTICS`, `AEROSPACE`, `FOOD_CPG`,
`EPC` (engineering/procurement/construction), `ENVIRONMENTAL`, `NATIONAL_LAB`,
`MATERIALS`, `OTHER`.

Note on the last four sectors: `ROBOTICS` and `AEROSPACE` employers post very few titles that
read as chemical engineering, so most of their postings will legitimately score below zero and
get dropped. That is correct behavior, not a bug — the signal there is materials, cells,
elastomers, coatings, and process, not the word "robotics." Do not loosen the scoring to make
those sectors produce more hits.

Deep-linking each posting is a real upgrade over the upstream, which only ever links to the
careers page. Workday and Greenhouse both return a per-posting URL — use it.

**Migrate `storage.json` to a new schema.** Key postings by a stable hash of
`(employer, normalized_title, location)` rather than by raw title string, so a title that gets
re-worded slightly doesn't show up as new. Normalize by lowercasing, collapsing whitespace,
and stripping trailing req IDs.

---

## PHASE 3 — ATS adapters (the core rewrite)

Replace the per-company CSS selector approach. Create `phlux/adapters/` with a common protocol:

```python
class Adapter(Protocol):
    def fetch(self, employer: Employer) -> list[Posting]: ...
```

Implement, in this order:

1. **`workday.py`** — Highest priority. Most large chemical and energy employers use Workday.
   `POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` with a JSON
   body of `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}`. Paginate on
   `offset` until `total` is reached. Returns structured JSON — title, `externalPath`,
   `locationsText`, `postedOn`. Confirm the exact request shape against a live tenant before
   building on it; do not assume my description is current.
2. **`greenhouse.py`** — `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`.
   Trivial, well documented, no auth. Covers the climate-tech and battery startups.
3. **`lever.py`** — `https://api.lever.co/v0/postings/{company}?mode=json`. Same story.
4. **`successfactors.py`** — Used by BASF, Honeywell, Linde. Harder; may need HTML parsing.
   Attempt the OData endpoint first.
5. **`selenium_adapter.py`** — Port the existing `get_jobs_headless` and the `Actions` DSL here
   verbatim as the fallback for anything the above four don't cover (iCIMS, Phenom, bespoke).
   Keep it working — don't rewrite it, just wrap it.

An adapter that fails must degrade gracefully: log, return `[]`, and let the run continue.
One broken employer must never take down the whole scrape. The existing `tenacity` retry
pattern is fine; keep it.

For each employer I give you, **determine the ATS empirically** — fetch the careers page and
look at where it redirects, what's in the network requests, what the URL structure is. Report
which ATS each one uses. Do not assume.

---

## PHASE 4 — Classification and scoring

New module `phlux/classify.py`. This is the domain heart of the project.

### 4a. Relevance scoring

Implement the additive log-odds score:

```
S = 3·(core matches) + 1·(sector matches) - 5·(veto matches) + 2·(location bonus) - 0.0495·(days since first_seen)
```

The `0.0495` is `ln(2)/14` — a 14-day half-life. Make the half-life configurable.
Drop anything with `S < 0`. Store matched keywords in `Posting.tags` so I can see *why*
something scored the way it did — I need to be able to debug the taxonomy.

The veto weight must exceed any single positive weight so that "Software Engineer, Process
Control" cannot pass on the word "process."

### 4b. Draft the keyword taxonomy, then have me correct it

Draft these lists and **present them to me for review before wiring them in.** I will correct
them — you should not be the final authority on which titles a chemical engineer wants.

- **Core (weight 3):** process engineer, chemical engineer, distillation, reactor, catalysis,
  separations, unit operations, heat transfer, mass transfer, HAZOP, process safety, PSM,
  scale-up, pilot plant, bioprocess, fermentation, downstream processing, upstream processing,
  drug substance, formulation, polymer, refining, petrochemical, process development,
  process control, DCS, plant engineer, production engineer, manufacturing engineer, tech service
- **Sector (weight 1):** refinery, GMP, cGMP, cleanroom, fab, wafer, etch, deposition, CVD, ALD,
  battery, electrolyzer, carbon capture, wastewater, emissions, FDA, validation, six sigma, lean

### 4b-ii. Profile-specific keywords

My background is battery cell fabrication and electrochemistry (Ni-Zn coin cells, electrode
coating, EIS, galvanostatic cycling, failure analysis on dendrites and HER), fragrance
formulation and analysis (GC-MS, 200+ aromachemicals, IFRA), and upcoming soft robotics
research. Add these to the taxonomy at the indicated weights:

- **Core (3):** electrochemistry, electrochemical, cell engineering, electrode, anode, cathode,
  electrolyte, cell design, cell manufacturing, battery engineer, coating engineer, calendering,
  slurry, failure analysis, materials engineer, aromachemical, flavor and fragrance, perfumery
- **Sector (1):** EIS, impedance, galvanostatic, cycling, dendrite, separator, pouch cell,
  coin cell, solid-state, sodium-ion, zinc, lithium, elastomer, silicone, liquid metal,
  actuator, hydrogel, encapsulation, adhesive, thin film, compounding, emulsion, surfactant,
  rheology, stability testing, IFRA, GC-MS, HPLC, Aspen, COMSOL

Two of these need judgment rather than substring matching. "Zinc" and "lithium" appear in
mining and logistics postings that are not engineering roles, so gate them behind at least one
other positive match. And "formulation" is already core, which is correct for both the pharma
and the cosmetics sectors — don't duplicate it.
- **Veto (weight -5):** software engineer, frontend, backend, full stack, data scientist,
  machine learning, sales, account executive, accounting, recruiter, HR, marketing, paralegal,
  truck driver, warehouse associate, retail

### 4c. Fix the inherited level detection

The upstream `is_internship()` matches on the substring `"ship"`, which also matches
"Shipping Coordinator," "Membership," and "Relationship Manager." Replace with word-boundary
regex over `intern`, `internship`, `co-op`, `coop`, `summer analyst`, and add a separate
`NEW_GRAD` detector (`new grad`, `entry level`, `university`, `campus`, `rotational`,
`graduate program`, `EIT`, `engineer i`, `associate engineer`).

Rotational development programs matter a lot in this industry — Dow, ExxonMobil, and P&G all
run them and they're a primary entry path. Make sure `rotational` and `development program`
are detected as `NEW_GRAD`.

### 4d. Location handling

Chemical engineering jobs are geographically concentrated in ways software jobs are not — the
Gulf Coast, the Delaware Valley, Michigan, and Louisiana. Parse location out of the ATS payload,
normalize to `City, ST`, and support a configurable list of target regions in `config.json`
for the `+2` location bonus. **Ask me for my target regions.**

---

## PHASE 5 — Employer registry

Migrate `companies.csv` to `employers.yaml`. CSV cannot hold the nested `ats_config` cleanly and
the URLs contain commas and quotes that already make the current CSV fragile.

```yaml
- name: Dow
  sector: SPECIALTY_CHEM
  ats: WORKDAY
  careers_url: https://corporate.dow.com/en-us/careers.html
  ats_config:
    tenant: dow
    site: External
  hq_region: Midland, MI
  enabled: true
```

Write a one-shot migration script and delete `add_company.py` (it edits the old CSV format).
Replace with `scripts/add_employer.py` that takes a careers URL, auto-detects the ATS, verifies
it returns postings, and appends a verified entry.

I will supply the employer list — see the seed list I'm giving you separately. **Verify every
single one before it goes in the file.** Anything you cannot verify goes in `unverified.md`
with a note on what failed.

---

## PHASE 6 — Outputs

1. **Email digest** (`main.py`): keep the Gmail SMTP approach, drop the icons. Group by sector,
   sort by score descending within each group, show title / location / score / matched tags,
   and deep-link each posting. Cap at 40 postings with a "+N more" line — the upstream sends
   everything and it's unreadable. Single recipient from `ALERT_EMAIL`, no BCC list.

2. **README** (`generate_readme.py`): the upstream writes every posting ever seen into the
   README, which is how it reached 9 MB. Cap it at the 200 highest-scoring active postings.
   Add a `data/` directory holding the full history as newline-delimited JSON instead — greppable,
   diffable, and it doesn't bloat the rendered page.

3. **CSV export** (`scripts/export.py`): dump active postings to
   `data/postings.csv` with columns `employer, title, location, sector, level, score, url,
   first_seen`. This replaces the hardcoded Google Sheets integration — I can import the CSV
   into whatever tracker I actually use.

---

## PHASE 7 — Configuration

Rewrite `config.json` to hold only preferences:

```json
{
  "scoring": { "half_life_days": 14, "min_score": 0.0,
               "weights": { "core": 3, "sector": 1, "veto": -5, "location": 2 } },
  "targets": { "regions": [], "sectors": [], "levels": ["INTERNSHIP", "CO_OP", "NEW_GRAD"] },
  "digest": { "max_postings": 40, "group_by": "sector" },
  "scraping": { "max_workers": 4, "per_host_delay_seconds": 2.0, "timeout_seconds": 30 }
}
```

Environment variables only: `ALERT_EMAIL`, `GMAIL_APP_PASSWORD`. Nothing else.
Add `.env.example` documenting both. Keep `phlux/config.py`'s defaults-merge pattern — it's
good — but strip the hardcoded addresses.

---

## PHASE 8 — Tests

The existing 740 lines of tests are a real asset. Keep the ones that still apply, update the
rest, and add:

- One test per adapter against a **recorded fixture** of a real ATS response (save real JSON
  into `tests/fixtures/`; do not hit live endpoints in tests)
- Scoring tests: a known title produces a known score, veto beats core, decay math is correct
- The `"ship"` substring bug: assert "Shipping Coordinator" is not classified as an internship
- Dedupe: same posting with a slightly reworded title does not re-alert
- Schema migration: old `storage.json` format loads without crashing

`pytest` must pass green at the end of every phase.

---

## PHASE 9 — CI and docs

**Workflow:** drop the cron from ~15 runs/day to `0 13 * * 1-5` (once each weekday morning).
Chemical engineering postings do not turn over hourly, and 210 Selenium sessions per run is
inconsiderate to the employers and slow. Keep `workflow_dispatch`. Keep the retry job. Add a
concurrency group so overlapping runs can't race on the commit-back step. **Leave the schedule
commented out until I say to enable it.**

**README:** what it does, how to add an employer, how the scoring works (include the derivation
of the log-odds formula — I want to be able to explain this if someone asks about it),
how to run locally, how to configure. Credit the upstream `Ph1so/phlux2.0` and preserve the
original license.

**`notes.md`:** replace the upstream author's notes with a running changelog of what you did.

---

## ACCEPTANCE CRITERIA

Done means all of these are true:

- [ ] `pytest` passes
- [ ] `python main.py --dry-run` completes without sending mail and prints a scored digest
- [ ] No email address, API key, or spreadsheet ID appears in any tracked file
- [ ] Repo is under 5 MB
- [ ] At least 3 ATS adapters work against real, verified endpoints
- [ ] Every employer in `employers.yaml` was verified to return postings
- [ ] "Software Engineer Intern" at a chemical company scores below zero and is dropped
- [ ] "Shipping Coordinator" is not classified as an internship
- [ ] Every surfaced posting deep-links to the posting, not just the careers page
- [ ] `auto_apply` is gone from the codebase entirely
- [ ] Cron is committed but disabled

---

## A NOTE ON SCOPE

If a phase turns out bigger than it looks, tell me and propose a split rather than doing a
rushed version. I would rather have Phases 0-4 done properly than all nine done shallowly —
the classification taxonomy in Phase 4 is what makes this tool worth anything, and it's the
part I most need to get right.
