# Quality

How the quality of each DSD Toolbox project is assured today: what is tested, where, and how a
release can be checked. Each project's own documents have the detail and win over this page.
The shared change and release process is in [docs/ci-cd.md](docs/ci-cd.md).

## Summary

✓ the project does this; – it does not, or it does not apply.

| Check | sacdfs | pysacd | beets‑pysacd | scarletbook‑rs | dsd2pcm‑rs | sacd‑spec |
|---|---|---|---|---|---|---|
| Tests on every pull request | ✓ | ✓ | ✓ | ✓ | ✓ | – |
| Conformance corpus | ✓ | – | – | ✓ | – | provides it |
| Byte identity against reference output | ✓ | ✓ | – | ✓ | ✓ | – |
| Linux, macOS and Windows in CI | ✓ | ✓ | ✓ | ✓ | ✓ | – |
| Fuzzing | ✓ | ✓ | ✓ | ✓ | ✓ | – |
| Sanitizers, Miri or leak checks | ✓ | ✓ | – | ✓ | – | – |
| Memory soak | ✓ | – | – | ✓ | – | – |
| Timings compared by release | ✓ | ✓ | – | ✓ | – | – |
| CodeQL | ✓ | ✓ | ✓ | ✓ | ✓ | – |
| OpenSSF Scorecard | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Build provenance attestations | ✓ | ✓ | ✓ | ✓ | ✓ | – |
| `SHA256SUMS` file | ✓ | – | – | – | ✓ | – |
| Trusted publishing (crates.io or PyPI) | ✓ | ✓ | ✓ | ✓ | ✓ | – |
| macOS builds signed and notarised | – | – | – | – | ✓ | – |

## Applications

### sacdfs

- **Tests:** unit and integration tests on every pull request, with the FUSE mount tests
  required (a missing FUSE fails the run). The 136-case conformance corpus from sacd-spec is read
  through the tree, the readers and a real mount. The container serves the corpus over SMB and NFS
  on x86-64 and arm64, and a Windows job checks the WinFsp mount byte for byte against Linux.
- **Platforms in CI:** Linux x86-64, arm64 and 32-bit x86; Windows; macOS on Apple Silicon and
  Intel. Minimum Rust version 1.85.
- **Before a release:** real-disc tests, a byte-for-byte comparison of the whole tree with the
  previous release, and a soak of 2 hours or more whenever shipped code changed
  ([test plan](https://github.com/aclater/sacdfs/blob/main/docs/test-plan.md)).
- **Fuzzing:** 11 targets, 60 s each on pull requests and 20 minutes each weekly, also as 32-bit
  programs ([fuzz/README.md](https://github.com/aclater/sacdfs/blob/main/fuzz/README.md)).
- **Leaks:** a no-growth test on every pull request; valgrind memcheck of the test suite and a
  20-minute corpus soak weekly.
- **Performance:** by-release tables and an informational benchmark job; a stall gate replays real
  players' read patterns at a slow NAS CPU's speed
  ([performance](https://github.com/aclater/sacdfs/blob/main/docs/performance.md)).
- **Security:** CodeQL, cargo-deny, dependency review, zizmor, Scorecard, and a weekly scan of the
  published container image.
- **Releases:** binaries, packages, the installer and the container image each carry a `.sha256`
  file and a build provenance attestation, with a `SHA256SUMS` file for the release; crates.io
  through trusted publishing. macOS and Windows builds are not signed.

### pysacd

- **Tests:** unit and integration tests on Python 3.10 to 3.15. A CI job builds `sacd_extract`
  from a pinned upstream commit and checks that `pysacd-extract` writes the same files, names and
  bytes on generated discs. Before each release, real discs are compared with the previous release
  and with `sacd_extract`, and the counts go in the changelog
  ([development](https://github.com/aclater/pysacd/blob/master/docs/development.md#ci)).
- **Hostile images:** about 95 crafted images through every mode and output format
  ([security](https://github.com/aclater/pysacd/blob/master/docs/security.md#hostile-images)).
- **Platforms:** Linux in CI; macOS and Windows on engine changes and weekly. Wheels for Linux
  x86_64 and aarch64 (glibc and musl), macOS arm64 and x86_64, and Windows x64, each installed
  and smoke-tested before release.
- **Fuzzing:** libFuzzer on the C engine under ASan and UBSan: 2 minutes on pull requests that touch
  the engine, 30 minutes weekly.
- **Sanitizers:** the whole test suite under ASan + UBSan and under TSan, and an engine leak check
  with LeakSanitizer and valgrind, all required.
- **Performance:** timings per release in
  [docs/performance.md](https://github.com/aclater/pysacd/blob/master/docs/performance.md) and the
  changelog; an informational benchmark job.
- **Security:** CodeQL (Python, C, Actions), semgrep, zizmor, dependency review, Scorecard, and
  hash-locked installs in CI.
- **Releases:** every wheel and the sdist has a build provenance attestation; PyPI through
  trusted publishing, with PyPI's own attestations.

### beets-pysacd

- **Tests:** Python 3.11 to 3.15, the oldest and latest supported beets, against pysacd's release
  and its development branch, on Linux, macOS and Windows. One job reads tags through a real sacdfs
  container mount built from sacdfs `main`.
- **Fuzzing:** Atheris on the disc-image identifier, on relevant pull requests and 20 minutes
  weekly.
- **Security:** CodeQL, semgrep, zizmor, dependency review, Scorecard, hash-locked installs.
- **Releases:** the wheel is installed in a clean environment before release; wheel and sdist carry
  build provenance attestations; PyPI through trusted publishing.

## Libraries

### scarletbook-rs

Summarised from its README, release notes and crates.io only.

- **Tests:** written from sacd-spec, with its conformance corpus in the tests. Every release passes
  a correctness gate (every corpus case, one thread and all threads) on the very builds it
  publishes; the C header and ABI are checked against the previous release.
- **Platforms:** Linux x86_64 and aarch64 (glibc and musl), macOS on Apple silicon and Intel,
  Windows x86_64, and 32-bit x86 for the Rust crates.
- **Fuzzing, Miri and soak:** a scheduled long fuzz run, Miri (slices, and the full suite on a
  schedule) and a memory soak workflow.
- **Performance:** release notes compare each release's timings with the previous one.
- **Security:** CodeQL, cargo-deny, dependency review, zizmor, Scorecard.
- **Releases:** every asset has a `.sha256` file and a build provenance attestation; crates.io
  through trusted publishing.

### dsd2pcm-rs

- **Tests:** output is checked to be identical to scarletbook-pcm 0.7.0 for every rate, cutoff and
  gain, and to pysacd's reference filter at every SIMD level. CI runs the tests once per SIMD level
  on Linux x86_64, aarch64 and 32-bit x86, macOS on Apple silicon and Windows x86_64; minimum Rust
  version 1.83.
- **Fuzzing:** 5 targets (DSF, DSDIFF, WAV and FLAC readers, and a round trip), 60 s each on pull
  requests and 10 minutes each weekly ([fuzzing](https://github.com/aclater/dsd2pcm-rs/blob/main/docs/fuzzing.md)).
- **Performance:** measured against scarletbook-pcm 0.7.0
  ([performance](https://github.com/aclater/dsd2pcm-rs/blob/main/docs/performance.md)).
- **Security:** CodeQL, cargo-deny, dependency review, zizmor, Scorecard.
- **Releases:** the packed archives must give byte-identical output on all five platforms before
  release; every archive has a `.sha256` file and a build provenance attestation, with a
  `SHA256SUMS` file; from 0.1.1 the macOS tool and C library are signed with a Developer ID and
  notarised by Apple, and crates.io is published through trusted publishing
  ([release](https://github.com/aclater/dsd2pcm-rs/blob/main/docs/release.md)).

## Specification

### sacd-spec

- **Conformance corpus:** 136 synthetic images (33 valid, 103 malformed), each with its expected
  outcome, warnings, TOC and per-channel audio hashes, for any reader to test against
  ([corpus](https://github.com/aclater/sacd-spec/blob/main/corpus/README.md)).
- **Limits:** [specification 7](https://github.com/aclater/sacd-spec/blob/main/spec/07-validation-and-limits.md)
  sets the limits and required behaviour for hostile input, so readers reject the same images the
  same way.
- **Changes:** by pull request only; every change records its sources in PROVENANCE.md
  ([clean room](docs/clean-room.md)). CI checks links and runs Scorecard.

## Verifying a download

Each release's notes give the command for its files. For example, for dsd2pcm-rs 0.1.1:

```sh
gh release download v0.1.1 -R aclater/dsd2pcm-rs -p 'dsd2pcm-0.1.1-x86_64-linux.tar.gz*'
sha256sum -c dsd2pcm-0.1.1-x86_64-linux.tar.gz.sha256
gh attestation verify dsd2pcm-0.1.1-x86_64-linux.tar.gz -R aclater/dsd2pcm-rs \
  --signer-workflow aclater/dsd2pcm-rs/.github/workflows/release.yml \
  --source-ref refs/tags/v0.1.1 --deny-self-hosted-runners
```

`gh attestation verify` checks that the file was built by the project's release workflow from that
tag, on a GitHub-hosted runner. More in [docs/ci-cd.md](docs/ci-cd.md#verifying-a-release).
