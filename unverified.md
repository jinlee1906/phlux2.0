# Unverified ATS entries

Entries here are hypotheses that failed verification, or that couldn't be verified at all.
Nothing here goes into `employers.yaml` until it's actually confirmed.

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
