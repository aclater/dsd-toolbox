# CI/CD

How changes reach the DSD Toolbox projects and how their releases are built and published. What
each project tests is in [QUALITY.md](../QUALITY.md); each project's own documents have the detail.

## Changes

- **Pull requests only.** Each default branch is protected by a ruleset with no bypass: changes
  arrive by pull request, with no force-push and no deletion.
- **Required checks,** which must pass on a branch that is up to date with the default branch, so
  green checks describe the code that merges. Common ones: format and lint with warnings as errors,
  tests, the minimum Rust version, cargo-deny (Rust) or hash-locked installs (Python), and CodeQL.
  Slower jobs (other systems, fuzzing, benchmarks, docs links) run on pull
  requests as well but are not all required; see the table below.
- **Workflow checks:** zizmor audits the workflows themselves in every project with code.
- **Security review:** changes that touch parsing of untrusted input, unsafe code, workflows or
  release paths get an independent security review before they merge.

## Testing depth

- **Reference output:** byte identity against a reference (pysacd against `sacd_extract`,
  dsd2pcm-rs against scarletbook-pcm 0.7.0, sacdfs against its previous release) and the
  conformance corpus of sacd-spec, with expected hashes for every case.
- **Real discs** before releases, in sacdfs and pysacd.
- **Fuzzing:** a short run on pull requests that touch parsing code, and a longer run weekly.
- **Memory:** sanitizers (pysacd), Miri (scarletbook-rs), leak checks and memory soaks (sacdfs,
  scarletbook-rs).
- **Performance:** timings compared with the previous release, published per release.

## Releases

1. A pull request bumps the version and dates the changelog; it merges when its checks pass.
2. An annotated `v*` tag on that commit. Tag rulesets forbid moving or deleting a release tag; a
   release that went wrong is followed by a new version.
3. The release workflow runs on the tag. It refuses a tag that does not match the package version
   (and, in most projects, is not on the default branch), builds every platform, and tests the
   packed files before anything is published. In sacdfs, scarletbook-rs and dsd2pcm-rs, pull
   requests that change release files run it as a dry run that publishes nothing.
4. Every published file gets a build provenance attestation, signed through GitHub with Sigstore;
   archives get a `.sha256` file, and some projects a `SHA256SUMS` file.
5. Packages reach crates.io and PyPI through trusted publishing (GitHub OIDC), with no stored
   token.
6. In sacdfs, pysacd, beets-pysacd and dsd2pcm-rs the workflow verifies every attestation it made
   before the release goes out.

## Hygiene

- Actions are pinned by their full commit SHA, and workflows default to read-only permissions,
  granting write, signing or publishing rights only to the jobs that need them (checked in
  sacdfs, pysacd, beets-pysacd and dsd2pcm-rs; Scorecard reports it for every project).
- Dependabot proposes dependency and action updates.
- sacdfs and dsd2pcm-rs pin the Rust toolchain CI uses; pysacd runs its tests in a container
  pinned by digest.

## Per project

| | sacdfs | pysacd | beets‑pysacd | scarletbook‑rs | dsd2pcm‑rs | sacd‑spec |
|---|---|---|---|---|---|---|
| Required status checks | 12 | 16 | 13 | 7 | 12 | none |
| Tests on macOS and Windows required | – | – | ✓ | – | ✓ | – |
| Tag creation restricted | – | – | – | – | ✓ | – |
| Release environment with required approval | – | – | – | – | ✓ | – |
| `SHA256SUMS` | ✓ | – | – | – | ✓ | – |
| macOS signing and notarisation | – | – | – | – | ✓ from 0.1.1 | – |
| Published to | crates.io, GHCR | PyPI | PyPI | crates.io | crates.io | – |
| AI review of pull requests | – | ✓ | ✓ | – | – | – |

sacd-spec holds no code and has no releases; implementations cite the commit they follow.

## Verifying a release

Download the file and its `.sha256`, check the checksum, then check the attestation, naming the
project's release workflow and the tag:

```sh
gh release download v0.1.1 -R aclater/dsd2pcm-rs -p 'dsd2pcm-0.1.1-x86_64-linux.tar.gz*'
sha256sum -c dsd2pcm-0.1.1-x86_64-linux.tar.gz.sha256
gh attestation verify dsd2pcm-0.1.1-x86_64-linux.tar.gz -R aclater/dsd2pcm-rs \
  --signer-workflow aclater/dsd2pcm-rs/.github/workflows/release.yml \
  --source-ref refs/tags/v0.1.1 --deny-self-hosted-runners
```

The checksum detects a damaged download; the attestation shows the file was built by that
workflow, from that tag, on a GitHub-hosted runner. `gh attestation verify` exits non-zero on
failure. For a Python package, `gh attestation verify` works the same on the wheel or sdist from
the GitHub release; PyPI also shows its own attestations for each file.
