[DSD Toolbox](../README.md) › [Documentation](README.md) › Documentation tooling

# Documentation tooling

The shared tools that hold every project's documentation to one standard, and how a project adopts them. They live in `tools/docs/` of this repository, use only the Python standard library (3.11 or later), and run as reusable workflows, from the command line and in each project's local CI.

## The tools

| Tool | What it checks | Workflow |
|---|---|---|
| `docs_links.py` | Every link in every Markdown file: relative links, `#anchors`, links into the repository itself, and (weekly) every external URL | `docs-links.yml` |
| `docs_lint.py` | Page shape, README shape and badges, repository files, CHANGELOG format, British spelling, terminology, no emoji, no placeholders, no links to the old owner, no private details, the release step | `docs-lint.yml` |
| `docs_touched.py` | A change to code, options or behaviour files also changes the README, `docs/` or CHANGELOG, or says `Docs: none needed — <reason>` | `docs-touched.yml` |
| `docs_audit.py` | After a release: the checklist of versions, options and platforms to compare. Monthly: lint, links and facts for every project | `docs-audit.yml`, `docs-monthly.yml` |

## Adopt them in a project

Add one job per tool to the project's workflow, with the commit of this repository whose tools you want (the same commit twice):

```yaml
jobs:
  docs-lint:
    uses: dsd-toolbox/dsd-toolbox/.github/workflows/docs-lint.yml@ff8c7230120e55a4126cc7b3c42697ff6eadfe56
    with:
      tools_ref: ff8c7230120e55a4126cc7b3c42697ff6eadfe56
```

Use the same shape for `docs-links.yml` (pull requests offline, weekly with `external: true`), `docs-touched.yml` (pull requests only) and `docs-audit.yml` (after each release and monthly). Then add a `.docs.toml` at the repository root:

```toml
name = "pysacd"
kind = "app"                 # app, library or overview
default_branch = "master"

[touched]
code = ["src/**", "csrc/**"]
docs = ["README.md", "docs/**", "CHANGELOG.md"]
ignore = ["tests/**", ".github/**"]

[[links.allow]]
url = "https://www.example.org/"
reason = "bot wall: opened by hand"
```

Every key is optional. A project without `.docs.toml` is checked with the defaults and the name of its folder.

## Run them locally

```sh
python3 -I tools/docs/docs_lint.py
python3 -I tools/docs/docs_links.py
python3 -I tools/docs/docs_links.py --external
python3 -I tools/docs/docs_touched.py --base origin/main --head HEAD
python3 -I tools/docs/docs_audit.py --release
python3 -I tools/docs/docs_audit.py --check
```

Each prints `path:line: [rule] message` and exits 1 on any finding. `docs_lint.py --list-rules` lists the rules. A rule is switched off in one place with a comment on the line above and a reason:

```markdown
<!-- docs-lint: ignore terminology -- quoted from the vendor's page -->
```

## The release step

Every project's release document (`docs/release.md`, the release test plan or `RELEASING.md`) carries the same block, [After the release: run the docs audit](ci-cd.md#after-the-release-run-the-docs-audit). `docs_audit.py --sync-release-step docs/release.md` puts it in or brings it up to date, and `docs_lint.py` fails when it is missing or differs.

## See also

- [CI/CD](ci-cd.md): how changes are reviewed and releases are built
- [Quality](../QUALITY.md): how each project is tested
- [Contributing](../CONTRIBUTING.md): how to contribute to any of the projects
