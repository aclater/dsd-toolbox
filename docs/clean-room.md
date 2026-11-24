[DSD Toolbox](../README.md) › [Documentation](README.md) › Clean room

# Clean room

scarletbook-rs, the library that reads SACD images and decodes DST, is permissively licensed
(MIT OR Apache-2.0), so it must not be derived from GPL implementations of the SACD format. It is
written by contributors who have read **only** sacd-spec, and the specification is written
without looking at implementations' code. Every specification change records its sources in
[PROVENANCE.md](https://github.com/aclater/sacd-spec/blob/main/PROVENANCE.md), and scarletbook-rs
records its research in [CLEANROOM.md](https://github.com/aclater/scarletbook-rs/blob/main/CLEANROOM.md).

## What is inside the wall

| Project | Inside the clean room |
|---|---|
| sacd-spec | Yes: the source the clean side reads |
| scarletbook-rs | Yes: written from sacd-spec only |
| dsd2pcm-rs | No: DSD-to-PCM conversion and DSD files carry no SACD-format licence risk; it uses filter code relicensed MIT OR Apache-2.0 by its copyright holder |
| sacdfs, pysacd, beets-pysacd | No: applications that use scarletbook-rs through its public interface and released builds |

The wall covers SACD disc-format and DST-decoder code only. It was narrowed to that on 2026-11-23,
when DSD-to-PCM conversion moved out of scarletbook-rs into dsd2pcm-rs
([DECISIONS.md](../DECISIONS.md)).

## Rules

- Information may flow from the clean side to everyone else (its code is MIT OR Apache-2.0).
- Nothing flows the other way. Needs of the other projects reach scarletbook-rs as issues that
  state requirements and measurements, never code, internals or links to non-clean code.
- Benchmarks of scarletbook-rs are black-box: its released builds are measured, and only the
  numbers are published.
- scarletbook-rs takes no code from dsd2pcm-rs or the applications.
- This repository is a description, not an input to the clean side.

## For clean-room contributors

sacd-spec and scarletbook-rs are DSD Toolbox projects inside the wall; contributors to them read only sacd-spec.
This repository is outside the clean room. Clean-room contributors must not read it or
follow its links; the clean side gets requirements only through scarletbook-rs issues. An
owner-directed read on 2026-11-01 is recorded in scarletbook-rs#155.

## See also

- [Decisions](../DECISIONS.md): the decisions behind the wall and why they were made
- [CI/CD](ci-cd.md): how changes are reviewed and released
- [Contributing](../CONTRIBUTING.md): how to contribute to any of the projects
