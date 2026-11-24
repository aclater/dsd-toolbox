<!-- docs-audit:begin -->
## After the release: run the docs audit

After the release: run the docs audit. Do it once the tag, the packages and the release notes are public, and before the release is announced.

1. Run the `docs-audit` workflow from the Actions tab of the repository (Run workflow). It runs the docs lint, the link check with external URLs and the docs facts check, and fails if any of them does.
2. Open the checklist it prints: every page that mentions a version, a command-line option or a platform, to compare with the release just published. Fix each mismatch in a docs-only change, or write down why it is right.
3. Record the result in the release notes or the release checklist: the workflow run, and how many checklist items were fixed.

Every project also runs this audit each month (the `docs-monthly` workflow in the DSD Toolbox repository), so a missed audit shows up within a month.
<!-- docs-audit:end -->
