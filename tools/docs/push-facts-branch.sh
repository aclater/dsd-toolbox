#!/bin/sh
# Commit the regenerated facts regions to the branch docs/facts-update and push it. Does NOT
# open a pull request: the organisation keeps "Actions can create pull requests" off (the same
# setting lets a workflow approve pull requests), so a person opens the PR from the branch.
# Needs a checkout whose credentials may push (contents: write). Used by docs-facts-generate
# after `docs_facts.py generate`; does nothing when no region changed. Exits 1 after pushing,
# on purpose: the failed run is the notice that a branch is waiting for a pull request.
set -eu
if git diff --quiet; then
  echo "Every facts region is current."
  exit 0
fi
branch=docs/facts-update
git config user.name "docs-facts"
git config user.email "docs-facts@users.noreply.github.com"
git checkout -B "$branch"
git add -u
git commit -q -m "Docs: refresh generated facts"
git push --force origin "$branch"
echo "::error title=docs-facts::The generated facts regions changed. Branch $branch is pushed; open a pull request from it into ${BASE:-the default branch} (this workflow cannot)."
exit 1
