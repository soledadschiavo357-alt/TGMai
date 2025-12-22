#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"/..
if ! git rev-parse --git-dir >/dev/null 2>&1; then git init; fi
if ! git config user.name >/dev/null 2>&1; then git config user.name "TGMai"; fi
if ! git config user.email >/dev/null 2>&1; then git config user.email "support@tgmai.top"; fi
git add -A
git commit -m "deploy: push to GitHub" || true
git branch -M main
if git remote | grep -q "^origin$"; then git remote remove origin; fi
if [ -n "${GITHUB_TOKEN:-}" ]; then
  REMOTE="https://${GITHUB_TOKEN}@github.com/MetaCraft-Dev/tgmai-top.git"
else
  REMOTE="git@github.com:MetaCraft-Dev/tgmai-top.git"
fi
git remote add origin "$REMOTE"
git push -u origin main
