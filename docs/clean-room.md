# Clean room

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

## For scarletbook-rs contributors

This repository is outside the clean room. scarletbook-rs contributors must not read it or follow its links; the clean side gets requirements only through scarletbook-rs issues. An owner-directed read on 2026-11-01 is recorded in scarletbook-rs#155.
