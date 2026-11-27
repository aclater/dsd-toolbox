[DSD Toolbox](../README.md) › [Documentation](README.md) › Documentation tooling

# Documentation tooling

The shared tools that hold every project's documentation to one standard, and how a project adopts them. They live in `tools/docs/` of this repository, use only the Python standard library (3.11 or later), and run as reusable workflows, from the command line and in each project's local CI.

## The tools

| Tool | What it checks | Workflow |
|---|---|---|
| `docs_links.py` | Every link in every Markdown file: relative links, `#anchors`, links into the repository itself, and (weekly) every external URL | `docs-links.yml` |
| `docs_lint.py` | Page shape, README shape and badges, repository files (including `CITATION.cff`, and `NOTICE` for Apache-2.0 code), a README licence section that names the documentation licence (CC BY 4.0) apart from the code licence, CHANGELOG format, British spelling, terminology, no emoji, no placeholders, no links to the old owner, no private details, the release step | `docs-lint.yml` |
| `docs_touched.py` | A change to code, options or behaviour files also changes the README, `docs/` or CHANGELOG, or says `Docs: none needed — <reason>` | `docs-touched.yml` |
| `docs_audit.py` | After a release: the checklist of versions, options and platforms to compare. Monthly: lint, links and facts for every project | `docs-audit.yml`, `docs-monthly.yml` |

## Adopt them in a project

Add one job per tool to the project's workflow, with the commit of this repository whose tools you want (the same commit twice):

```yaml
jobs:
  docs-lint:
    uses: dsd-toolbox/dsd-toolbox/.github/workflows/docs-lint.yml@677b0384600338c241ce9415ea5d45914fae233c
    with:
      tools_ref: 677b0384600338c241ce9415ea5d45914fae233c
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

Land `.docs.toml` in its own pull request first and add the workflow calls in a second one: `docs-run` reads its allowlists from the base commit, so one combined pull request can be red. See [the tools README](../tools/docs/README.md#first-adoption-two-pull-requests-in-this-order). Where `docs-links.yml` covers a project's links, remove its lychee job.

## Settings

All keys in `.docs.toml` are optional.

| Key | Meaning | Default |
|---|---|---|
| `name`, `display_name` | Repository name (links, URLs) and the name shown in breadcrumbs and the README title | the folder name |
| `kind` | `app`, `library` (also needs a docs.rs badge) or `overview` (a Projects table, Scorecard badge only) | `app` |
| `default_branch` | Branch named in badge URLs | `main` |
| `footer` | Require the "Part of the DSD Toolbox" line | `true` |
| `moved_repos` | Repositories, besides the toolbox projects, whose `aclater/` links fail | none |
| `[lint] exclude`, `allow_words`, `proper_nouns` | Files skipped by the style rules, words the spelling and terminology lists accept, words a heading may capitalise | none |
| `[lint] index_exclude`, `required_files`, `release_files`, `ignore` | Pages the index need not list, the repository files that must exist, the release documents that carry the audit block, and `{path, rule, reason}` waivers | the standard lists |
| `[lint] citation`, `notice`, `docs_licence` | Require `CITATION.cff`, require `NOTICE` for Apache-2.0 code, and the documentation licence the README must name | `true`, `true`, `CC BY 4.0` |
| `[readme] badges`, `title`, `sections`, `allow_extra`, `pitch_max` | Override the badge set derived from the workflows and manifests, the title, the section list, extra sections allowed, and the pitch length | derived |
| `[links] exclude`, `exclude_files`, `[[links.allow]]` | URL patterns and files not checked, and URLs not fetched because the site blocks scripts (with a reason) | the shared list in `tools/docs/links-allow.toml` |
| `[run] checkout`, `packages`, `[run.images.<alias>]` | Checkout mode for every docs-run block, the package names a block may install, and extra digest-pinned images (see [tools/docs](../tools/docs/README.md)) | `false`, none, the built-in image |
| `[run] exclude`, `unprivileged` | Markdown files no docs tool reads (`CLAUDE.md`, `AGENTS.md`), and running docs-run blocks as an unprivileged user (see [tools/docs](../tools/docs/README.md#unprivileged-blocks-and-fixtures)) | none, `false` |
| `[touched] code`, `docs`, `ignore` | Path globs: a change to `code` needs a change to `docs`; `ignore` never counts as code | source folders, README, `docs/` |
| `[audit] help_command`, `history` | A command whose output lists the options the docs may name; files that keep history (version mentions there are not flagged) | none |

The clean-room projects keep their own docs; these tools are not run on them.

## Run them locally

<!-- docs-run: skip="runs the tools from a checkout of this repository" -->
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
