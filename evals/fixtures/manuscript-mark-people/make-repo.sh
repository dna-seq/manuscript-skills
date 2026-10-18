#!/bin/sh
# Build the case's repository in DIR (default: ./mark-people-repo): a paper with revision marks, two
# people, an AI co-author trailer, a bot commit and an unexplained by= handle. A git repository cannot be
# a fixture file, so the case builds one.
set -eu
dir=${1:-mark-people-repo}
mkdir -p "$dir" && cd "$dir"
git init -q -b main
cat > paper.md <<'MD'
---
title: Variant annotation at scale
authors:
  - Anna Smith
  - Tom Okafor
---

<!-- @rev C1 rounds=2 by=claude:2026-10-01,anna:2026-10-02 -->
We annotated 4.2 million variants.
<!-- @/rev C1 -->

<!-- @rev C2 rounds=1 by=robi:2026-10-03 -->
Runtime was 41 minutes per genome.
<!-- @/rev C2 -->

<!-- @rev C3 rounds=1 by=grok:2026-10-04 -->
The method generalises to other cohorts.
<!-- @/rev C3 -->
MD
git add paper.md
GIT_AUTHOR_NAME="Anna Smith" GIT_AUTHOR_EMAIL="anna.smith@example.org" GIT_COMMITTER_NAME="Anna Smith" \
  GIT_COMMITTER_EMAIL="anna.smith@example.org" git commit -q -m "Draft

Co-authored-by: Claude Opus 5.5 <noreply@anthropic.com>"
GIT_AUTHOR_NAME="Tom Okafor" GIT_AUTHOR_EMAIL="t.okafor@example.org" GIT_COMMITTER_NAME="Tom Okafor" \
  GIT_COMMITTER_EMAIL="t.okafor@example.org" git commit -q --allow-empty -m "Methods notes"
GIT_AUTHOR_NAME="renovate[bot]" GIT_AUTHOR_EMAIL="29139614+renovate[bot]@users.noreply.github.com" \
  GIT_COMMITTER_NAME="renovate[bot]" GIT_COMMITTER_EMAIL="29139614+renovate[bot]@users.noreply.github.com" \
  git commit -q --allow-empty -m "Bump deps"
echo "built $(pwd)"
