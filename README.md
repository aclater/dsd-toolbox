# DSD Toolbox

> scarletbook-rs contributors: please don't read this repository ([why](docs/clean-room.md#for-scarletbook-rs-contributors)).

Open tools for reading Super Audio CD disc images and DSD audio: a specification written from
scratch, a Rust library built from it, and the tools that use it. This
repository is the map of how they fit together; it holds no code.

They are built for speed: sacdfs decodes stereo and multichannel DST-compressed discs to DSF in
real time even on a 2011 dual-core 32-bit Atom D2700 NAS, and the conversion libraries run
many times faster than real time on any recent desktop CPU.

## Projects

| Project | What |
|---|---|
| [sacdfs](https://github.com/aclater/sacdfs) | Plays SACD images as DSF and WAV tracks in any player, without extracting them (Linux, NAS, Windows, macOS) |
| [pysacd](https://github.com/aclater/pysacd) | Extracts and converts SACD images to DSF, DSDIFF, FLAC or WAV, from the command line or Python |
| [beets‑pysacd](https://github.com/aclater/beets-pysacd) | Imports SACD images into a beets music library, with MusicBrainz matching |
| [scarletbook‑rs](https://github.com/aclater/scarletbook-rs) | Rust and C library that reads SACD images and decodes DST |
| [dsd2pcm‑rs](https://github.com/aclater/dsd2pcm-rs) | Rust and C library and CLI: DSD to PCM, and DSF, DFF and WAV files |
| [sacd‑spec](https://github.com/aclater/sacd-spec) | Specification of the SACD disc format, with a test corpus |


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

## Documentation

- [Clean room](docs/clean-room.md): how sacd-spec and scarletbook-rs are kept independent
- [Decisions](DECISIONS.md): the major decisions and why they were made
- [Releases](RELEASES.md): what each minor version line brought, per project
- [Quality](QUALITY.md): how each project is tested and how its releases can be checked
- [CI/CD](docs/ci-cd.md): how changes are reviewed and releases are built, signed and published
- [Security](SECURITY.md): how to report a vulnerability in any of the projects (privately,
  never in a public issue)
- [Contributing](CONTRIBUTING.md)
- [Board](https://github.com/users/aclater/projects/1): open issues and pull requests of the
  projects in one view

## Licence and credits

This repository holds documentation only. Each project has its own licence, listed in
[Projects](#projects), and credits its upstreams in its own README.
