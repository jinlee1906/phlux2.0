#!/bin/bash
# Local scheduled run: fetch, classify, email, regenerate README, commit back.
#
# Exists because GitHub Actions' native `schedule:` trigger proved unreliable
# on this account/repo (consistently several hours late, worsening day to
# day -- not something fixable from the workflow file). This script mirrors
# exactly what .github/workflows/job-scraper.yml's "run" job does, invoked
# instead by a local launchd job at a precise time. See
# ~/Library/LaunchAgents/com.jinlee.phlux2-scraper.plist.
#
# The git commit step uses the same fetch+soft-reset+recommit+push pattern
# as the CI workflow (not `git pull --rebase`) for the same reason: storage
# .json/README.md/data/ are fully regenerated every run, not hand-edited --
# there's nothing to line-merge between two runs' versions of them.
# IMPORTANT: this is meant to run from a SEPARATE, dedicated clone of this
# repo (e.g. ~/phlux2.0-scheduled), never from a working copy also used for
# interactive development -- it checks out and force-syncs `main` on every
# run, which would fight with whatever branch/uncommitted work is active in
# a dev checkout. See the setup notes where this script is referenced.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

LOG_FILE="$REPO_DIR/scripts/run_scheduled.log"
exec >> "$LOG_FILE" 2>&1
echo "=== $(date -u +"%Y-%m-%dT%H:%M:%SZ") starting scheduled run ==="

# At 9am the Mac is often in a brief battery "DarkWake", or just woke and
# hasn't rejoined Wi-Fi/hotspot yet -- runs were dying on DNS failures and
# the Mac was dropping back to sleep mid-scrape. So: hold off idle sleep for
# as long as this script runs, then wait for the network before starting.
/usr/bin/caffeinate -i -w $$ &

NETWORK_WAIT_SECONDS=1200  # 20 min
wait_for_network() {
    local waited=0
    until /usr/bin/curl -sS -o /dev/null --max-time 10 https://github.com \
        && /usr/bin/curl -sS -o /dev/null --max-time 10 https://www.google.com; do
        if (( waited >= NETWORK_WAIT_SECONDS )); then
            echo "Network still unreachable after ${NETWORK_WAIT_SECONDS}s, giving up"
            return 1
        fi
        echo "Network not ready, waiting 30s (waited ${waited}s so far)"
        sleep 30
        waited=$((waited + 30))
    done
}

# retry <attempts> <cmd...>: re-run a command with 30s/60s/... backoff.
retry() {
    local attempts=$1; shift
    local n=1
    until "$@"; do
        if (( n >= attempts )); then
            echo "Failed after $attempts attempts: $*"
            return 1
        fi
        echo "Attempt $n failed: $* -- retrying in $((n * 30))s"
        sleep $((n * 30))
        n=$((n + 1))
    done
}

wait_for_network

git checkout main
retry 4 git fetch origin main
git reset --hard origin/main

.venv/bin/python main.py
.venv/bin/python generate_readme.py

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3; do
    retry 4 git fetch origin main
    git reset --soft origin/main
    git add storage.json README.md data/
    if git diff --cached --quiet; then
        echo "No changes to commit"
        break
    fi
    git commit -m "Update storage.json and readme [local scheduler]"
    if git push origin HEAD:main; then
        break
    fi
    echo "Push race on attempt $attempt, retrying..."
    git reset --soft HEAD^
    sleep 5
done

echo "=== $(date -u +"%Y-%m-%dT%H:%M:%SZ") finished scheduled run ==="
