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

After a release, a `release`, `latest-date` or `install` region that follows the latest release is stale until the next regeneration. `check` reports it as a warning (exit 0) for 7 days after the newest release it reads, and as an error after that; regions with a pinned `tag=` and every other kind of region fail at once. `--today YYYY-MM-DD` sets the date for tests. Each project runs `docs-facts-generate` on a weekly schedule and after each release (`workflow_dispatch` or a `release` trigger on the default branch); it pushes the branch `docs/facts-update` and the project's session or the Orchestrator opens the pull request. No organisation setting changes and no bot holds a write token.

`GITHUB_TOKEN` raises GitHub's rate limit; the workflows pass the job's read-only token to every step that calls the API (`docs-facts`, `docs-audit`, `docs-monthly`, `docs-run` with `version-of`). `--data FILE` answers every web request from a snapshot (`--dump-data FILE` writes one), so tests and local CI run offline.

## docs-run: commands that must work

Fenced command blocks in README.md and docs/ are run in a fresh container that holds only the extracted blocks, never the checkout. What they install is therefore the published release. Mark a block:

| Marker | Meaning |
|---|---|
| ` ```sh run ` | runs, must exit 0 |
| `<!-- docs-run: key=value ... -->` on the line before the fence | runs, with options below |
| `<!-- docs-run: skip="reason" -->` | does not run; the reason is required and shown in the report |
| no marker | listed as "not run" and counted against coverage |

Options: `image=` (the name of an allowed image, default `default`; see below), `packages=a,b` (dnf, plain package names), `setup=` (a command instead), `expect=` (a regex the output must match; repeat for more; `{version}` is `--version`), `drop=` (a regex; matching lines are removed and listed, for a line that opens a browser), `group=` (blocks of any file with the same name share one container and one working folder, in README-first order; default one group per file), `timeout=` (seconds, 1 to 7200, default 1800), `checkout=1` (start in a copy of the repository, see below).

`packages=` accepts only names the repository allows: `[run] packages = [...]` for every image, and `packages = [...]` inside `[run.images.<alias>]` for one. Any other name is a marker error.

A marker is text from a file that may not be yours, so every value is checked strictly (no control characters, no leading `-`, length limits, fixed character sets) and a bad marker exits 2. A marker never names an image reference, a volume, a privilege, a network or an environment variable. Images come only from the allowlist in `.docs.toml`, each a full reference pinned by digest. Without an entry the built-in `default` (Fedora 43, pinned by digest) is used:

```toml
[run.images.fedora]
ref = "registry.fedoraproject.org/fedora@sha256:59be9ed15831f74e408c5f3d59fc77fc8371f4642de2673c16c37e880b4dd937"
network = true      # only an entry that sets this gets a network (dnf, pip and pipx need one)
```

Every container runs with `--network=none` unless its image entry sets `network = true`, `--cap-drop=ALL` (a few capabilities are added back only when `packages=` or `setup=` installs software), `--security-opt=no-new-privileges`, a read-only root (not when installing), and memory, CPU and process limits and a timeout. The blocks themselves still run what the Markdown says, so run docs-run on text you trust or in CI on a disposable runner.

A toolchain image is one more alias, for example a digest-pinned Rust image for build and test blocks:

```toml
[run]
checkout = false             # true: every block starts in a copy of the checkout (checkout=0 opts a block out)
packages = ["jq"]            # dnf package names a block may install, on any image

[run.images.rust]
ref = "docker.io/library/rust@sha256:<64 hex digits of the image>"
network = true
packages = ["gcc", "make"]
```

### Checkout mode

Build, test, fuzz and C-example commands need the repository. With `checkout=1` on a block (or `[run] checkout = true`) the group starts in `$HOME/checkout`, a copy of `git archive HEAD` made on the host: no `.git`, no untracked or ignored files, no uncommitted edits. The real checkout is never mounted, so a block cannot change it. `--root` must be the top of the Git checkout. All other hardening is unchanged: only allowlisted, digest-pinned images, no Markdown-controlled podman option, `--cap-drop=ALL`, and a network only for an image whose entry says so.

Trust boundary: checkout mode runs the repository's own code. That is fine in that repository's CI, on a disposable runner with a read-only token. Outside CI, run `docs_run.py` only on Markdown and a checkout you wrote. On a pull request, CI reads `[run]` (images, packages, checkout default) from the base commit with `--allowlist-ref BASE_SHA`, so a change cannot widen its own allowlist; it is merged first, then used. The workflow does this by itself.

<!-- docs-run: skip="runs the tool from a checkout of this repository" -->
```sh
python3 -I tools/docs/docs_run.py list --classify          # coverage and a guess why each unmarked block cannot run
python3 -I tools/docs/docs_run.py run --version 0.1.1      # needs Podman
```

Coverage is the share of command blocks that run; "run or skipped with a reason" shows how much is accounted for. `--require-coverage N` and `--fail-unmarked` turn either into a failure. The workflow's `fail_unmarked` input (a boolean, default true) passes `--fail-unmarked`, so a new unmarked command block fails CI and "100% marked" stays true; set it to `false` while a project is still marking its blocks. A block that cannot run in a container (root, a GPU, real hardware, credentials, Windows or macOS) is skipped with an explicit reason, never faked.

## Adopt it in a project

Call the reusable workflows, pinned to a full commit SHA of this repository, and pass the same SHA as `tools-ref`:

```text
jobs:
  facts:
    uses: dsd-toolbox/dsd-toolbox/.github/workflows/docs-facts.yml@COMMIT-SHA
    with:
      tools-ref: COMMIT-SHA
  commands:
    uses: dsd-toolbox/dsd-toolbox/.github/workflows/docs-run.yml@COMMIT-SHA
    with:
      tools-ref: COMMIT-SHA
      version: 0.1.1
      fail_unmarked: true
```

`docs-facts.yml` only checks and needs `contents: read`. To refresh the regions, call `docs-facts-generate.yml` from a schedule or `workflow_dispatch` job that grants `contents: write`, never from `pull_request`. It pushes the branch `docs/facts-update` and fails naming it; it does not open the pull request, because the organisation keeps "Actions can create pull requests" off (the setting also lets workflows approve pull requests). A person opens the pull request. This repository runs both tools on itself in `.github/workflows/docs.yml`; the tests are in `tools/docs/tests`.

## See also

- [Continuous integration and release process](../../docs/ci-cd.md)
- [Quality and how to check it](../../QUALITY.md)
- [Releases by major version](../../RELEASES.md)

Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox).
