# DSD Toolbox

> **Clean-room note:** this repository is outside the clean room. scarletbook-rs agents must not
> read it or follow its links; the clean side gets requirements only through scarletbook-rs
> issues. (An owner-directed read on 2026-11-01 is recorded in scarletbook-rs#155.)

Open tools for reading Super Audio CD disc images and DSD audio: a specification written from
scratch, a clean-room Rust library built only from it, and the tools that use it. This
repository is the map of how they fit together; it holds no code.

## Projects

| Project | What | Licence | Side of the wall | Links |
|---|---|---|---|---|
| sacd-spec | Implementation-free specification of SACD disc images, a synthetic conformance corpus, and the benchmark method and results | CC BY 4.0 (corpus CC0 1.0) | the wall itself | [repo](https://github.com/aclater/sacd-spec) |
| scarletbook-rs | Clean-room Rust library: TOC, audio, DST decoding, C ABI; written only from sacd-spec | MIT OR Apache-2.0 | clean | [repo](https://github.com/aclater/scarletbook-rs) |
| dsd2pcm-rs | DSD to PCM conversion and DSF, DFF and WAV reading and writing, as a Rust crate, a C library and a command-line tool | MIT OR Apache-2.0 | not clean | [repo](https://github.com/aclater/dsd2pcm-rs) |
| sacdfs | Shows a folder of SACD images as DSF and WAV tracks to any player, without extracting them. Runs on Linux, including NAS systems; Windows 10 and 11, x64 (a read-only drive letter, with WinFsp); macOS 11 or later (Apple Silicon and Intel). Any other system can play the discs over SMB or NFS from a NAS or Linux computer that runs sacdfs | GPL-3.0-or-later | not clean | [repo](https://github.com/aclater/sacdfs) |
| pysacd | Python toolkit and `sacd_extract`-compatible extractor (DSF, DSDIFF, FLAC, WAV) with a C engine. Python 3.10 or later; wheels for Linux x86_64 and aarch64 (glibc 2.28 or later; musl on x86_64), macOS (Intel 10.13 or later, Apple Silicon 11 or later) and Windows x64 | GPL-2.0-or-later | not clean | [repo](https://github.com/aclater/pysacd) · [PyPI](https://pypi.org/project/pysacd/) |
| beets-pysacd | beets plugin: imports SACD images into a music library, MusicBrainz matching, DVD and Blu-ray audio cataloguing | GPL-2.0-or-later | not clean | [repo](https://github.com/aclater/beets-pysacd) · [PyPI](https://pypi.org/project/beets-pysacd/) |

```
                    sacd-spec  (specification + corpus)
                        │  read only by the clean side
                        ▼
                  scarletbook-rs  (clean Rust library)
                   │            │
         Rust API  │            │  C ABI (scarletbook-ffi)
                   ▼            ▼
                sacdfs        pysacd
                                │
                                ▼
                          beets-pysacd
```

## Quick start

Which project do you need?

- **Play your SACD images** without extracting them:
  [sacdfs](https://github.com/aclater/sacdfs#quick-start). It runs on Linux, including NAS
  systems; Windows 10 and 11, x64, as a read-only drive letter with WinFsp; and macOS 11 or
  later, Apple Silicon and Intel. Any other system can play the discs over SMB or NFS from a
  NAS or Linux computer that runs sacdfs.
- **Extract or convert images**, from the command line, Python or a beets library:
  [pysacd](https://github.com/aclater/pysacd#quick-start) and
  [beets-pysacd](https://github.com/aclater/beets-pysacd#quick-start). pysacd needs Python 3.10
  or later and has wheels for Linux (x86_64 and aarch64), macOS (Intel and Apple Silicon) and
  Windows x64.
- **Build your own software**: the Rust library [scarletbook-rs](https://github.com/aclater/scarletbook-rs)
  for SACD images, [dsd2pcm-rs](https://github.com/aclater/dsd2pcm-rs#quick-start) for DSD to PCM
  and DSF/DFF/WAV files, or [sacd-spec](https://github.com/aclater/sacd-spec#quick-start) to
  write or test a reader of your own.

## The clean-room wall

scarletbook-rs is permissively licensed, so it must not be derived from GPL code. It is
written in an isolated environment by agents that have read **only** sacd-spec, and the
specification side is written without looking at implementations' code. Every spec PR records
its sources in [PROVENANCE.md](https://github.com/aclater/sacd-spec/blob/main/PROVENANCE.md), and
scarletbook-rs records its research in
[CLEANROOM.md](https://github.com/aclater/scarletbook-rs/blob/main/CLEANROOM.md).

Rules that keep it intact:

- Information may flow from the clean side to everyone else (its code is MIT/Apache).
- Nothing flows the other way. Requirements from pysacd or sacdfs reach scarletbook-rs as
  issues stating needs and measurements, never code, internals or links to non-clean code.
- Benchmarks of scarletbook are black-box: its released binaries are measured; numbers only are
  published in sacd-spec.
- This repository is a description, not an input to the clean side.

## Documentation

- [Decisions](DECISIONS.md): the major decisions and why they were made
- [Releases](RELEASES.md): what each minor version line brought, per project
- [Quality](QUALITY.md): the checks against bugs, regressions, leaks and supply-chain problems,
  and the known gaps
- [Security](SECURITY.md): how to report a vulnerability in any of the projects (privately,
  never in a public issue)
- [Contributing](CONTRIBUTING.md)
- [Board](https://github.com/users/aclater/projects/1): open issues and pull requests of the
  projects in one view

## Licence and credits

This repository holds documentation only. Each project has its own licence, listed in
[Projects](#projects), and credits its upstreams in its own README.
