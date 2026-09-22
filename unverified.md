# Unverified ATS entries

Entries here are hypotheses that failed verification, or that couldn't be verified at all.
Nothing here goes into `employers.yaml` until it's actually confirmed.

## COSMETICS_FRAGRANCE batch — 17 of 18 unverified (Church & Dwight confirmed Workday)

All of the following loaded their real careers page (static HTML, no JS execution) and were
checked for Greenhouse/Workday/Lever/SuccessFactors/Ashby/iCIMS/Oracle Cloud/SmartRecruiters/
Workable/Jobvite/Phenom/Taleo/BambooHR/Recruitee/Breezy references — none found, so presumably
JS-rendered job boards:

- **Givaudan** — `givaudan.com/careers`
- **dsm-firmenich** — `dsm-firmenich.com/corporate/careers.html`
- **Mane** — `mane.com/careers`
- **Robertet** — `robertet.com/en/careers`
- **L'Oreal** — `lorealusa.com/careers`
- **Estee Lauder** — `elcompanies.com/en/careers`
- **Kao** — `kao.com/global/en/careers/`
- **Beiersdorf** — `beiersdorf.com/careers`
- **Croda** — `croda.com/en-gb/careers`
- **Elementis** — `elementis.com/en/careers/`
- **Shiseido** — `shiseidogroup.com/careers/` (75KB HTML, no match)

**Sensient Technologies** — `sensient.com/careers/` — detected **Oracle Cloud HCM**
(`eour.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/...`), not one of this project's five
supported ATSes.

**e.l.f. Beauty** (seed hypothesis: GREENHOUSE) — checked `elfbeauty.com/work-with-us` and
`elfcosmetics.com/careers/careers` (same content, likely a redirect) — no ATS reference found.
A web search surfaced `jobs.lever.co/elfbeauty`, but that link doesn't appear anywhere on the
current live page — possibly a stale/historical ATS (companies do migrate), not confirmed.

**International Flavors & Fragrances** (seed hypothesis: WORKDAY), **Symrise**, **Takasago**,
**Coty** — all failed to fetch entirely (bot-blocked) at `iff.com/careers/`,
`symrise.com/careers`, `takasago.com/en/company/careers`, `coty.com/careers/` respectively.

## Solid Power (ENERGY_STORAGE)

- **Seed hypothesis:** GREENHOUSE (unverified, from `employers_seed.csv`)
- **What was tried:** Loaded `solidpowerbattery.com/careers/` directly (curl, with and without a
  browser user-agent) and via WebFetch.
- **Result:** The page is Cloudflare-protected (curl gets a Cloudflare bot-block page) and,
  where content did come back (WebFetch), the "Current Job Openings" section renders with no
  job links or ATS references in the static HTML — the actual listing appears to be loaded
  client-side by JavaScript that isn't visible to a non-JS fetch.
- **Status:** Not verified. No Greenhouse (or any other ATS) reference was found on the page
  itself. Do not assume GREENHOUSE for this employer without re-checking by another method
  (e.g. a headless browser that executes JS, or a manual check).

## Tesla (ENERGY_STORAGE)

- **Seed hypothesis:** GREENHOUSE (unverified)
- **What was tried:** `tesla.com/careers/search/` via direct fetch (Akamai bot protection, 403)
  and via WebFetch (same 403).
- **Status:** Not verified — site blocks automated fetches outright. Would need a different
  verification method (e.g. a real headless browser) to check.

## Form Energy (ENERGY_STORAGE)

- **Seed hypothesis:** GREENHOUSE (unverified)
- **What was tried:** `formenergy.com/careers/` — loaded successfully via WebFetch earlier
  (Phase 3), which showed job links carrying `ashby_location_id` query parameters (e.g.
  `?ashby_location_id=332fd20d-...`) rather than any Greenhouse reference. A later re-fetch via
  direct request failed (site now blocks the plain browser UA used here, or is rate-limiting).
- **Status:** Not GREENHOUSE — uses **Ashby**, which isn't one of the five ATSes this project
  builds adapters for (WORKDAY/GREENHOUSE/LEVER/SUCCESSFACTORS/SELENIUM). Can't be added to
  employers.yaml until an Ashby adapter exists (out of current scope) or a Selenium fallback is
  built and pointed at it.

## Redwood Materials (ENERGY_STORAGE)

- **Seed hypothesis:** LEVER (unverified)
- **What was tried:** `redwoodmaterials.com/` root — loads (121KB HTML), but no Greenhouse,
  Lever, Workday, SuccessFactors, Ashby, iCIMS, SmartRecruiters, Workable, Jobvite, or Phenom
  reference anywhere in the static HTML.
- **Status:** Not verified. Job board is presumably rendered client-side by JavaScript with no
  static trace of the ATS it calls.

## QuantumScape (ENERGY_STORAGE)

- **Seed hypothesis:** GREENHOUSE (unverified)
- **What was tried:** `quantumscape.com/careers/` — loads (259KB HTML), no known ATS reference
  found in static HTML (same pattern-scan as Redwood Materials above).
- **Status:** Not verified — likely JS-rendered job board.

## ESS Inc (ENERGY_STORAGE)

- **Seed hypothesis:** GREENHOUSE (unverified)
- **What was tried:** `essinc.com/ess-careers/` (confirmed correct URL via search — the seed's
  implied `/careers/` path doesn't exist) — loads (143KB HTML), no known ATS reference found.
- **Status:** Not verified — likely JS-rendered job board.

## 24M Technologies (ENERGY_STORAGE)

- **Seed hypothesis:** GREENHOUSE (unverified)
- **What was tried:** `24-m.com/culture-careers` (confirmed correct domain via search — company
  uses "24-m.com", not "24m.com") — loads (45KB HTML), no known ATS reference found.
- **Status:** Not verified — likely JS-rendered job board.

## Natron Energy (ENERGY_STORAGE)

- **Not investigated for ATS.** A web search indicates Natron Energy became defunct/shut down
  around September 2025 (per a Wikipedia-referenced search snippet — not independently
  confirmed further). Recommend dropping this employer from the seed list entirely rather than
  spending verification effort on a company that may no longer be hiring. Flagging for the
  user's decision rather than silently removing it from `employers_seed.csv`.

## Rivian (ENERGY_STORAGE)

- **Seed hypothesis:** GREENHOUSE (unverified)
- **What was tried:** `rivian.com/careers` — loads (412KB HTML). Found a real reference:
  `us-careers-rivian.icims.com` (a login link).
- **Status:** Confirmed ATS is **iCIMS**, not Greenhouse — but iCIMS isn't one of the five ATSes
  this project has adapters for. Per PROJECT_BRIEF.md Phase 3, iCIMS is meant to be handled by
  the Selenium fallback adapter (not yet built) using verified CSS selectors — and per CLAUDE.md,
  an unverified selector can never go into a config file. Cannot be added to employers.yaml
  until the Selenium adapter exists and real selectors are found and tested against this page.

## Lucid Motors (ENERGY_STORAGE)

- **Seed hypothesis:** GREENHOUSE (unverified)
- **What was tried:** `lucidmotors.com/careers` — loads (209KB HTML), no known ATS reference
  (checked Greenhouse/Lever/Workday/iCIMS/SuccessFactors/SmartRecruiters/Workable/Ashby/Jobvite/
  Phenom/Taleo/BambooHR/Recruitee/Breezy).
- **Status:** Not verified — likely JS-rendered job board.

## Urban Electric Power (ENERGY_STORAGE)

- **Seed hypothesis:** UNKNOWN
- **What was tried:** `urbanelectricpower.com/careers` — loads (985KB HTML, unusually large), no
  known ATS reference found in the same broad pattern scan as above.
- **Status:** Not verified — likely JS-rendered job board, or an ATS not in the current pattern
  list.

## Panasonic Energy (ENERGY_STORAGE)

- **Seed hypothesis:** UNKNOWN
- **What was tried:** `careers.na.panasonic.com/energy/kansas` — loads (494KB HTML). Found one
  iCIMS reference (`fremployees-napanasonic.icims.com`), but it's explicitly labeled "Internal"
  in the surrounding text — likely an employee-only portal, not the external candidate-facing
  one, so not a usable lead even if iCIMS were in scope.
- **Status:** Not verified.

## LG Energy Solution (ENERGY_STORAGE)

- **Seed hypothesis:** UNKNOWN
- **What was tried:** The seed note ("US cell plants in MI OH TN") doesn't map to one legal
  entity — LG Energy Solution operates separate regional subsidiaries with separate ATSes.
  **LG Energy Solution Arizona** (Queen Creek, AZ — not actually one of the MI/OH/TN plants
  named in the seed note, but the one that turned out verifiable) is confirmed on **Greenhouse**
  (`board_token: lgenergyaz`, `company_name` in the API response literally reads "LG Energy
  Solution Arizona", location "Queen Creek, Arizona") and has been added to employers.yaml under
  that specific name. **LG Energy Solution Michigan** (`lgenergymi.com/careers/`, the plant
  actually referenced in the seed note) loads (73KB HTML) but has no known ATS reference —
  not verified. The Ohio and Tennessee entities haven't been investigated at all yet.
- **Status:** Partially verified — Arizona only, and it's a different facility than the one the
  seed note called out. Revisit MI/OH/TN separately if you want full US coverage.

## SK On / SK Battery America (ENERGY_STORAGE)

- **Seed hypothesis:** UNKNOWN
- **What was tried:** The seed note says "SK On, Commerce GA," but the Commerce, GA plant
  operates under the name "SK Battery America." A search surfaced a specific Workday URL
  (`skba.wd1.myworkdayjobs.com/en-US/SK_battery_America`), but I could not find it referenced on
  any real page I could fetch — `skbatteryamerica.com/careers` loaded (25KB HTML) with no ATS
  reference, and I did not independently confirm the Workday URL is real (only a search-engine
  snippet, not something I traced from the company's own page).
- **Status:** Not verified. The Workday tenant/site above is a specific, sourced candidate (not
  a guess) if you want me to try confirming it a different way — e.g. by finding the actual page
  that links to it.

## SPECIALTY_CHEM batch — 14 of 18 unverified (Air Products/Dow/Huntsman/Albemarle confirmed Workday)

**Eastman Chemical** — `eastman.com/en/careers` loads (216KB), no known ATS reference — the one
"greenhouse" hit in a broad scan was a false positive from a "Greenhouse gas emissions"
navigation link, not the ATS.

**Chemours** (seed: WORKDAY) — `chemours.com/en/careers` blocked every fetch attempt; a search
surfaced `chemours.wd5.myworkdayjobs.com/Chemours` but I couldn't load that page directly either
(unlike Dow's equivalent page, which did load) — sourced candidate, not independently confirmed.

**Celanese** (seed: WORKDAY) — actually confirmed as **iCIMS** (`career-celanese.icims.com`),
not Workday. Out of scope until the Selenium fallback exists.

**BASF** (seed: SUCCESSFACTORS), **LyondellBasell**, **Westlake** — real careers pages load, no
known ATS reference found (JS-rendered).

**Olin, Ashland, Lubrizol, Ecolab, Linde** — fetch failed entirely (bot-blocked) at
`olin.com/en/careers`, `ashland.com/careers`, `lubrizol.com/en/Careers`, `ecolab.com/careers`,
and `lindecareers.com/en/search-jobs` (this one loaded, 489KB, but no ATS reference).

**Honeywell** (seed: SUCCESSFACTORS) — `careers.honeywell.com/us/en` shows an Oracle Cloud HCM
reference (`ibqbjb.fa.ocs.oraclecloud.com`) embedded in a 404-page fallback link, not a
confirmed live reference. Not SuccessFactors as hypothesized; Oracle Cloud isn't in scope
either way.

**DuPont, Corteva** — both use **Phenom People** (`cdn.phenompeople.com`), not one of the five
supported ATSes.

## PHARMA_BIOTECH batch — 5 of 10 unverified (5 confirmed via Workday: Merck, Pfizer, Amgen, Moderna, Bristol Myers Squibb)

**Genentech, Eli Lilly** — both use **Phenom People**, same as DuPont/Corteva above.

**AbbVie** — `careers.abbvie.com/` loads (95KB), no known ATS reference.

**Johnson & Johnson** — `careers.jnj.com/` fetch failed entirely (bot-blocked).

**Incyte** — `careers.incyte.com/` shows an `icims.com` mention, but only inside a generic
privacy-policy disclaimer (a `privacy@icims.com` contact + a `jibe.com` privacy-policy link) —
not confirmed as their actual ATS, just legal boilerplate that happens to mention iCIMS.

One bug this batch caught: my Workday board-link regex had an overly permissive "optional
locale" group that matched *any* all-letter path segment, not just real locale codes like
"en-US" — so for a tenant with no locale prefix (Pfizer's
`pfizer.wd1.myworkdayjobs.com/PfizerCareers/page/<job-id>`), it swallowed the real site name
("PfizerCareers") and wrongly captured the next segment ("page") as if it were the site. Fixed
to require the optional segment look like an actual locale (`[a-z]{2}-[a-z]{2}`); this
immediately unlocked correct detection for both Pfizer (582 postings) and Merck (1110 postings,
tenant `msd`, site `SearchJobs`).

## SEMICONDUCTOR batch — 7 of 7 unverified (none confirmed)

**Texas Instruments** (seed: UNKNOWN) — confirmed **Oracle Cloud HCM**
(`edbz.fa.us2.oraclecloud.com`, a clear API base URL this time, not a stray link) — not in scope.

**Micron, Lam Research, GlobalFoundries** — real careers pages load (306KB/436KB/341KB), no
known ATS reference found.

**Intel** — `jobs.intel.com` blocked every fetch attempt. A search surfaced
`intel.wd1.myworkdayjobs.com/External/...` (tenant `intel`, wd_host `wd1`, site `External`) —
sourced candidate, not independently confirmed since I couldn't load any Intel page directly.

**Applied Materials** — `jobs.appliedmaterials.com/search-jobs` loads but is enormous (2.98MB)
and shows no known ATS reference — likely a heavily client-side-rendered bespoke portal.

**TSMC Arizona** — `tsmc.com/careers/en/az/` blocked every fetch attempt; not retried further.

## OIL_GAS batch — 7 of 9 unverified (bp, ConocoPhillips confirmed via Workday)

**Valero** (seed: ICIMS — wrong) — actually confirmed **Taleo**
(`valero.taleo.net/careersection/...`), not iCIMS. Out of scope either way.

**ExxonMobil, Chevron, Phillips 66, Koch Industries** — real careers pages load
(153KB/53KB/199KB/80KB), no known ATS reference found even after full browser rendering (see
the Selenium re-check note below). **Shell** was in this group too, until the re-check —
see below, it's now resolved.

**Marathon Petroleum** — `marathonpetroleum.com/Careers/` fetch failed entirely.

## FOOD_CPG batch — 8 of 9 unverified (General Mills confirmed Workday)

**Colgate-Palmolive** (seed: UNKNOWN) — see the SuccessFactors false-positive bug writeup below.
`jobs.colgate.com/` loads jQuery from `performancemanager4.successfactors.com`, but that's a
shared SAP asset host, not evidence Colgate's own career site runs on SuccessFactors. No genuine
ATS reference found after fixing the detector.

**Procter & Gamble** — uses **Phenom People**, same family as DuPont/Corteva/Genentech/Eli
Lilly above.

**PepsiCo** — `pepsicojobs.com/` shows an `icims` string, but only inside an `appcast.io`
ad-tracking pixel URL parameter — not a genuine ATS reference, just analytics. Not confirmed.

**Unilever, Kimberly-Clark, Kraft Heinz, Cargill** — fetch failed entirely (bot-blocked).

**ADM** — `adm.com/en-us/careers/` loads (391KB), no known ATS reference.

## EPC batch — 7 of 7 unverified

**KBR** — uses **Phenom People**, same family as several above.

**Fluor, Burns & McDonnell** — real careers pages load (345KB/285KB), no known ATS reference.

**Bechtel, Jacobs** — pages load with **zero bytes of content** (fully client-side rendered,
nothing in the initial HTML response at all).

**Worley, Wood** — fetch failed entirely (bot-blocked).

## NATIONAL_LAB batch — 5 of 5 unverified (none confirmed)

**Oak Ridge National Laboratory** — initially mis-detected as SuccessFactors
(`rmkcdn.successfactors.com`), but that turned out to be a shared SAP CDN hostname serving a
CSS file, not a real career-site link — see the detect.py fix below. No genuine ATS reference
found after the fix.

**NREL, Pacific Northwest National Laboratory, Idaho National Laboratory** — fetch failed
entirely (bot-blocked).

**Sandia National Laboratories** — `sandia.gov/careers/` loads (232KB), no known ATS reference.

## ENVIRONMENTAL batch — 2 of 3 unverified (Xylem confirmed Workday, 554 postings)

**Veolia** — `veolianorthamerica.com/careers` loads (182KB), no known ATS reference.

**Clean Harbors** — `careers.cleanharbors.com/` loads (447KB), no known ATS reference.

## Bug: SuccessFactors and Workday detection false positives/negatives

Two real bugs found and fixed together in `catalyst/detect.py`:

1. **SuccessFactors false positives** — the original regex matched *any* `X.successfactors.com`
   reference, including shared SAP platform infrastructure (asset CDNs, jQuery includes) that
   has nothing to do with whether the employer's own career site runs on SuccessFactors.
   Confirmed false positives: **Colgate-Palmolive** (`performancemanager4.successfactors.com`
   was loading a jQuery library, not linking to a career page — the bad entry was removed from
   `employers.yaml` after being caught) and **Oak Ridge National Laboratory** (a CSS asset CDN).
   Fixed to require an actual `/career` or `/sfcareer` path plus a `company=` query parameter,
   which is how real SuccessFactors applicant-facing links are structured (the subdomain, e.g.
   "career5", is a shared numbered SAP instance — the real tenant is in the query param, not the
   subdomain).
2. **Workday site names with hyphens truncated** — the site-capture character class didn't
   include `-`, so **Xylem**'s real site name `xylem-careers` was truncated to `xylem`, which
   then 404'd against the real API. Fixed; Xylem is now confirmed (554 postings).

## Selenium re-check of all 44 "JS-rendered, no ATS found" entries

Added `fetch_rendered_page()` to `catalyst/detect.py` — loads a URL with a real headless Chrome
via Selenium (executing JS), then runs the same literal-evidence `detect_ats()` patterns against
the fully rendered DOM instead of the pre-render HTTP response. Re-ran it against every employer
above that was previously logged as "loads fine, no ATS reference found" (i.e. the "JS-rendered"
group, 44 employers).

**Result: all 44 pages rendered successfully (zero failures), but only 1 of 44 resolved.**

- **Shell** — now confirmed **WORKDAY** (`tenant: shell`, `wd_host: wd3`, `site: ShellCareers`,
  evidence `shell.wd3.myworkdayjobs.com/ShellCareers`). Not yet added to `employers.yaml` per
  instruction to not build more employers this pass — ready to add whenever wanted.
- **All other 43** (Givaudan, dsm-firmenich, Mane, Robertet, L'Oreal, Estee Lauder, Kao,
  Beiersdorf, Croda, Elementis, Shiseido, Eastman Chemical, BASF, LyondellBasell, Westlake,
  Linde, AbbVie, Micron, Lam Research, GlobalFoundries, Applied Materials, ExxonMobil, Chevron,
  Phillips 66, Koch Industries, ADM, Fluor, Burns & McDonnell, Bechtel, Jacobs, Sandia National
  Laboratories, Veolia, Clean Harbors, Colgate-Palmolive, Oak Ridge National Laboratory, Redwood
  Materials, QuantumScape, ESS Inc, 24M Technologies, Lucid Motors, Urban Electric Power,
  Panasonic Energy, LG Energy Solution Michigan) **still show no known ATS reference even in the
  fully-rendered DOM.** Their real ATS call is presumably issued as a genuinely dynamic
  XHR/fetch request that never lands as a literal string anywhere in the page source — visible
  in a browser's network tab, but not in `driver.page_source`. Resolving these would need actual
  network-traffic inspection (e.g. Selenium's performance/CDP logging) or a user click to
  trigger the job search, both meaningfully bigger asks than a one-shot render. Not pursued
  further this pass, per instruction to stop escalating and move to Phase 6.

## 35-employer seed backlog re-check — 12 of 35 verified (materials/robotics/aerospace batch)

Re-ran verification against every seed employer that had never been attempted before (see
`employers_seed.csv`). 12 verified into `employers.yaml` (Cabot, 3M, Samsung, Boston Dynamics,
Boeing — all WORKDAY; Anduril, Figure AI, Path Robotics, Archer Aviation — all GREENHOUSE;
Shield AI, Toyota Research Institute — LEVER; Sierra Space — WORKDAY). Notably, two seed
hypotheses turned out wrong on real evidence: **Anduril** was hypothesized LEVER but is actually
GREENHOUSE (`andurilindustries`, 2348 postings), and **Shield AI** was hypothesized GREENHOUSE
but its own primary board is actually LEVER (`shieldai`, 508 postings) — a second, unrelated
company's Greenhouse board (`aechelontechnology`, an acquired subsidiary kept as a separate
brand) is also linked from the same page and was correctly rejected as a distinct entity.

### Astrobotic — real ATS reference found, but rejected as a false positive

`astrobotic.com/careers/` embeds `boards.greenhouse.io/embed/job_board/js?for=voyagertechnologiesinc`
— a literal reference, not guessed. But the returned postings (Denver/Pueblo, CO — "Analytical
Chemist," "Agentic GEOINT Mission Management Lead") are generic corporate roles with no
Astrobotic/Pittsburgh/lunar-lander connection. Voyager Technologies holds a majority stake in
Astrobotic and Astrobotic's site pulls from Voyager's shared multi-subsidiary Greenhouse board,
not an Astrobotic-specific feed. Adding this would mislabel unrelated Voyager Technologies
postings as "Astrobotic" — same class of problem as the Colgate-Palmolive SuccessFactors false
positive. Not added.

### Joby Aviation — real ATS reference found, but unsupported ATS

`jobyaviation.com/careers` (rendered) links to `careers-jobyaviation.icims.com/jobs` — literal
evidence, but iCIMS isn't one of this project's five supported ATSes (Workday, Greenhouse,
Lever, SuccessFactors) and has no adapter.

### PPG, Sherwin-Williams, Meta Reality Labs, Skild AI, Near Earth Autonomy, Carnegie Robotics, Apptronik, 1X Technologies, Sanctuary AI, Dexterity, Soft Robotics Inc, Beta Technologies, Rocket Lab, Relativity Space, Lockheed Martin, Northrop Grumman, RTX

All fetched successfully (or were bot-blocked on the plain HTTP request but rendered fine via
Selenium), and were checked against the fully-rendered DOM — no known ATS reference (Workday,
Greenhouse, Lever, SuccessFactors, Ashby) found in any of them, including a second attempt at a
deeper "open-roles"/"careers/open-roles" path for several (Aurora Innovation, 1X Technologies,
Beta Technologies, Rocket Lab, Relativity Space). Their real job-search call is presumably a
dynamic XHR that never lands as a literal string in `driver.page_source` — same unresolved class
as the 43-employer "JS-rendered" group already logged above.

### Apple, SpaceX, Blue Origin — bespoke in-house career portal

All three fetched and rendered successfully but show no third-party ATS reference of any kind —
job listings are served from the company's own domain via a proprietary system (e.g.
`jobs.apple.com`'s own path structure, `spacex.com/careers/jobs`, `blueorigin.com/careers/...`
per-role subpaths), not one of the five supported ATSes.

## Adjacent-industry expansion batch — 13 of 80 verified

User approved a ~80-company candidate list drawn from industries adjacent to their background
(battery/electrochemistry, fragrance/beauty, soft robotics, propulsion/rocketry, power/solar,
and broad specialty chemicals), plus larger established companies at their request. 13 verified
into `employers.yaml`: Solid Power, Group14 Technologies (GREENHOUSE); Array Technologies, Bloom
Energy, GE Vernova, Duke Energy, IFF, Chemours, Ecolab, Air Liquide (WORKDAY); Bright Machines,
ispace (LEVER); Varda Space Industries (GREENHOUSE). Each was confirmed via a real API call
returning plausible, employer-relevant postings (e.g. Solid Power: "Cell Slurry Engineering
Intern," Louisville/Thornton CO — matches its real HQ; Chemours: Parkersburg WV / Wilmington DE
— matches its real plant/HQ locations).

### ABL Space Systems — literal reference found, but the ATS itself is inactive

`ablspacesystems.com/careers/` has a real, current "View All Available Jobs" button linking to
`jobs.lever.co/ablspacesystems` — not guessed, confirmed by inspecting the HTML context around
the link directly. But calling the actual Lever API (`api.lever.co/v0/postings/ablspacesystems`)
returns a 404, meaning that board is empty or deactivated even though the company's own site
still links to it. Not added — the evidence is genuine but there's no live data to verify
against. Worth rechecking later in case they reactivate it.

### Unsupported ATS platform found (literal reference, no adapter exists)

- **American Battery Technology Company, Amprius Technologies** — Workable
- **KORE Power** — Ashby
- **Duracell, First Solar** — Oracle Cloud HCM
- **Energizer Holdings, Schneider Electric, Celanese, Trinseo** — iCIMS
- **Enphase Energy** — Jobvite

### Bot-blocked even via Selenium rendering

Natron Energy, ONE (Our Next Energy), Freyr Battery, EnPower, Lanxess.

### No known ATS reference found, even in the fully-rendered DOM

Same unresolved class as the earlier JS-rendered groups above (dynamic XHR job search, nothing
static to find): A123 Systems, Aerojet Rocketdyne, Ambri, Amorepacific, Arkema, Ascend Elements,
Ashland, Avient, BYD, Berkshire Grey, CATL, Clariant, Clarins, Corteva, Coty, Covariant,
Eastman Chemical, Ekso Bionics, Element Solutions, EnerSys, Evonik, Firefly Aerospace,
Formlabs, Impulse Space, Kenvue, L3Harris, LG Chem, Li-Cycle, Maxeon Solar, NextEra Energy,
Panasonic Energy of North America, Physical Intelligence, Puig, Qcells, RIOS Intelligent
Machines, Revlon, SK On, Samsung SDI, Siemens Energy, SolarEdge, Solvay, Stoke Space, Symrise,
T. Hasegawa, Takasago, Textron, Ursa Major, Vast, Vestas, Wacker Chemie.

### Correction: Covestro was actually verifiable (moved to employers.yaml)

An independent re-check found what the bulk pass above missed: `covestro.com/en/career`'s
static HTML contains a literal `covestro.wd3.myworkdayjobs.com/cov_external` link, confirmed via
a real fetch returning 179 postings (e.g. "Mechanical Maintenance Technician," Baytown, TX — a
real Covestro plant site). Added to `employers.yaml` as WORKDAY/tenant=covestro/wd_host=wd3/
site=cov_external. Left as a note here rather than silently deleted, since the original miss is
worth knowing about: a single bulk verification pass can miss real evidence that a second,
independent pass catches — the same lesson as this project's live-testing-before-shipping habit.
