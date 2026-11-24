[dsd-toolbox](../../README.md) › [Tools](.) › Docs tooling

# Docs tooling

Two small tools keep a project's documentation true: `docs_facts.py` generates and checks the facts that change with each release, and `docs_run.py` runs the documented commands against the published release. Python standard library only; each has a reusable GitHub workflow and a command line for local CI.

## docs-facts: facts that must not drift

A fact is a marked region in Markdown. In prose, tables and around fenced blocks:

```text
<!-- facts:release repo=dsd-toolbox/sacdfs fmt="{version} ({date})" -->0.7.2 (2026-11-22)<!-- /facts -->
```

Inside a fenced block the markers are shell comments, so the block still runs:

```text
# facts:install kind=pipx-git repo=dsd-toolbox/dsd-measure
pipx install git+https://github.com/dsd-toolbox/dsd-measure@v0.1.1
# /facts
```

| Key | Arguments | Gives |
|---|---|---|
| `release` | `repo=OWNER/REPO` or `source=pypi name=` or `source=crates name=`; `tag=` (default latest); `fmt=` with `{version} {tag} {date} {url} {repo}`; `empty=TEXT` when there is no release | latest release version and date; `{repo}` is the canonical owner and name |
| `latest-date` | `repos=a/b,c/d` | the newest release date of several repositories |
| `assets` | release arguments; `match=` and `exclude=` regexes; `fmt=` with `{name} {platform} {size_mb} {tag} {version}`; `unique=1` | one line per release asset: the platform and asset lists |
| `ci-matrix` | `file=` workflow, `job=`, `key=`; `fmt=` (`{v}`), `sep=` | a job's `strategy.matrix` list |
| `msrv` | `file=` (default `Cargo.toml`) | `rust-version` |
| `python-min` | `file=` (default `pyproject.toml`); `fmt=` with `{v} {spec}` | the minimum of `requires-python` |
| `install` | `kind=pipx-git` (`ref=none` for no tag), `pip`, `cargo` (`pin=1` pins the version), or `download` (`asset=` regex, exactly one match) | one install line with the canonical owner and repository and the released tag |

<!-- docs-run: skip="runs the tool from a checkout of this repository" -->
```sh
python3 -I tools/docs/docs_facts.py check              # CI: exit 1 and a diff when a region is stale, 2 when it cannot be evaluated
python3 -I tools/docs/docs_facts.py generate           # rewrite every region
python3 -I tools/docs/docs_facts.py list               # where the regions are
```

`GITHUB_TOKEN` raises GitHub's rate limit. `--data FILE` answers every web request from a snapshot (`--dump-data FILE` writes one), so tests and local CI run offline.

## docs-run: commands that must work

Fenced command blocks in README.md and docs/ are run in a fresh container that holds only the extracted blocks, never the checkout. What they install is therefore the published release. Mark a block:

| Marker | Meaning |
|---|---|
| ` ```sh run ` | runs, must exit 0 |
| `<!-- docs-run: key=value ... -->` on the line before the fence | runs, with options below |
| `<!-- docs-run: skip="reason" -->` | does not run; the reason is required and shown in the report |
| no marker | listed as "not run" and counted against coverage |

Options: `image=` (default `registry.fedoraproject.org/fedora:43`), `packages=a,b` (dnf), `setup=` (a command instead), `expect=` (a regex the output must match; repeat for more; `{version}` is `--version`), `drop=` (a regex; matching lines are removed and listed, for a line that opens a browser), `group=` (blocks of any file with the same name share one container and one working folder, in README-first order; default one group per file), `timeout=`.

<!-- docs-run: skip="runs the tool from a checkout of this repository" -->
```sh
python3 -I tools/docs/docs_run.py list --classify          # coverage and a guess why each unmarked block cannot run
python3 -I tools/docs/docs_run.py run --version 0.1.1      # needs Podman
```

Coverage is the share of command blocks that run; "run or skipped with a reason" shows how much is accounted for. `--require-coverage N` and `--fail-unmarked` turn either into a failure. A block that cannot run in a container (root, a GPU, real hardware, credentials, Windows or macOS) is skipped with an explicit reason, never faked.

## Adopt it in a project

Call the reusable workflows, pinned to a full commit SHA of this repository, and pass the same SHA as `tools-ref`:

```text
jobs:
  facts:
    uses: dsd-toolbox/dsd-toolbox/.github/workflows/docs-facts.yml@COMMIT-SHA
    with:
      tools-ref: COMMIT-SHA
      mode: check
  commands:
    uses: dsd-toolbox/dsd-toolbox/.github/workflows/docs-run.yml@COMMIT-SHA
    with:
      tools-ref: COMMIT-SHA
      version: 0.1.1
```

A weekly or after-release job with `mode: generate` opens the pull request `docs/facts-update` with the regenerated regions. This repository runs both tools on itself in `.github/workflows/docs.yml`; the tests are in `tools/docs/tests`.

## See also

- [Continuous integration and release process](../../docs/ci-cd.md)
- [Quality and how to check it](../../QUALITY.md)
- [Releases by major version](../../RELEASES.md)

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
