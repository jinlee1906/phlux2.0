# Chemical engineering job tracker

Fork of Ph1so/phlux2.0. Full plan in @PROJECT_BRIEF.md — read it before starting a phase.

## Rules
- Never write an unverified URL, ATS tenant, or selector into a config file.
  Unverified entries go to unverified.md.
- No email addresses, API keys, or spreadsheet IDs in tracked files. Env vars only.
- Scraping: max 4 workers, 2s per-host delay, respect robots.txt.
- Prefer ATS JSON endpoints over Selenium.
- pytest must pass before any commit.
- Stop and ask before: adding an employer I didn't list, sending real email,
  enabling the cron, force-pushing, or adding a dependency.
- Default branch is main (verified against the GitHub remote).
- Employer seed list is in employers_seed.csv. The Likely_ATS_UNVERIFIED column
  is a hypothesis to test, never an answer to trust.
- Never use multi-line `python -c "..."` for scratch checks — it keeps coming out
  malformed. Write a temp `.py` file and run that instead.
