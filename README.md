<img src="https://raw.githubusercontent.com/dsd-toolbox/dsd-toolbox/main/docs/assets/icon-256.png" alt="" width="96">

# DSD Toolbox

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/dsd-toolbox/dsd-toolbox/badge)](https://scorecard.dev/viewer/?uri=github.com/dsd-toolbox/dsd-toolbox)

> Contributing to sacd-spec or scarletbook-rs (the clean room)? Please work from sacd-spec only and don't read this repository: [how the clean room works](https://github.com/aclater/scarletbook-rs/blob/main/CLEANROOM.md).

Open tools for reading Super Audio CD disc images and DSD audio: a specification written from
scratch, a Rust library built from it, and the tools that use it. This
repository is the map of how they fit together; it holds no code.

## Projects

They are built for speed, and measured: on a 2011 dual-core 32-bit Atom D2700 NAS, sacdfs plays
stereo discs, and multichannel DST was too slow there until the decoder got about 1.7 times
faster (not yet measured again on that NAS); the conversion libraries publish their speed, in
times real time, with the commands to reproduce it.

|  | Project | What | Latest |
|---|---|---|---|
| <img src="https://raw.githubusercontent.com/dsd-toolbox/sacdfs/main/docs/assets/icon-64.png" alt="" width="32"> | [sacdfs](https://github.com/dsd-toolbox/sacdfs) | Plays SACD images as DSF and WAV tracks in any player, without extracting them (Linux, NAS, Windows, macOS) | <!-- facts:release repo=dsd-toolbox/sacdfs fmt="[{version}]({url})" -->[0.9.0](https://github.com/dsd-toolbox/sacdfs/releases/tag/v0.9.0)<!-- /facts --> |
| <img src="https://raw.githubusercontent.com/dsd-toolbox/pysacd/master/docs/assets/icon-64.png" alt="" width="32"> | [pysacd](https://github.com/dsd-toolbox/pysacd) | Extracts and converts SACD images to DSF, DSDIFF, FLAC or WAV, from the command line or Python | <!-- facts:release repo=dsd-toolbox/pysacd fmt="[{version}]({url})" -->[0.6.0](https://github.com/dsd-toolbox/pysacd/releases/tag/v0.6.0)<!-- /facts --> |
| <img src="https://raw.githubusercontent.com/dsd-toolbox/beets-pysacd/main/docs/assets/icon-64.png" alt="" width="32"> | [beets‑pysacd](https://github.com/dsd-toolbox/beets-pysacd) | Imports SACD images into a beets music library, with MusicBrainz matching | <!-- facts:release repo=dsd-toolbox/beets-pysacd fmt="[{version}]({url})" -->[0.2.3](https://github.com/dsd-toolbox/beets-pysacd/releases/tag/v0.2.3)<!-- /facts --> |
| <img src="https://raw.githubusercontent.com/dsd-toolbox/dsd-measure/main/docs/assets/icon-64.png" alt="" width="32"> | [dsd‑measure](https://github.com/dsd-toolbox/dsd-measure) | Measures DSD and PCM converters the way audiophile reviewers do, and writes one readable report | <!-- facts:release repo=dsd-toolbox/dsd-measure fmt="[{version}]({url})" -->[0.1.3](https://github.com/dsd-toolbox/dsd-measure/releases/tag/v0.1.3)<!-- /facts --> |
| <img src="https://raw.githubusercontent.com/dsd-toolbox/dsd2pcm-rs/main/docs/assets/icon-64.png" alt="" width="32"> | [dsd2pcm‑rs](https://github.com/dsd-toolbox/dsd2pcm-rs) | Rust and C library and CLI: DSD to PCM, and DSF, DFF and WAV files | <!-- facts:release repo=dsd-toolbox/dsd2pcm-rs fmt="[{version}]({url})" -->[0.2.0](https://github.com/dsd-toolbox/dsd2pcm-rs/releases/tag/v0.2.0)<!-- /facts --> |
| <img src="https://raw.githubusercontent.com/dsd-toolbox/dsd-upsample-rs/main/docs/assets/icon-64.png" alt="" width="32"> | [dsd‑upsample‑rs](https://github.com/dsd-toolbox/dsd-upsample-rs) | Converts DSF, DFF, WAV and FLAC files to DSD128 or DSD256, and PCM to DSD64, with output designed to be byte-identical across platforms and thread counts within a release (Linux x86_64 library and CLI; plug-ins and other systems follow) | <!-- facts:release repo=dsd-toolbox/dsd-upsample-rs fmt="[{version}]({url})" empty="not yet released" -->[0.1.0](https://github.com/dsd-toolbox/dsd-upsample-rs/releases/tag/v0.1.0)<!-- /facts --> |
| <img src="https://raw.githubusercontent.com/dsd-toolbox/dsdup-gst/main/docs/assets/icon-64.png" alt="" width="32"> | [dsdup‑gst](https://github.com/dsd-toolbox/dsdup-gst) | GStreamer plug-in for dsd-upsample: PCM or DSD64 to DSD256 in, DSD64, DSD128 or DSD256 out, with DSF and DFF file elements (Linux x86_64, built from source) | <!-- facts:release repo=dsd-toolbox/dsdup-gst fmt="[{version}]({url})" empty="not yet released" -->[0.1.0](https://github.com/dsd-toolbox/dsdup-gst/releases/tag/v0.1.0)<!-- /facts --> |
| <img src="https://raw.githubusercontent.com/dsd-toolbox/ffmpeg-dsf/main/docs/assets/icon-64.png" alt="" width="32"> | [ffmpeg‑dsf](https://github.com/dsd-toolbox/ffmpeg-dsf) | Patches for FFmpeg: a PCM to DSD64, DSD128 or DSD256 encoder (`libdsdupsample`, through dsd-upsample) and a DSF muxer (Linux x86_64, source patches, built from source) | <!-- facts:release repo=dsd-toolbox/ffmpeg-dsf fmt="[{version}]({url})" empty="not yet released" -->[0.1.0](https://github.com/dsd-toolbox/ffmpeg-dsf/releases/tag/v0.1.0)<!-- /facts --> |

### Clean room

sacd-spec and scarletbook-rs are DSD Toolbox projects inside the clean-room wall; their contributors read only sacd-spec. They live under the aclater account by design: the wall keeps them apart from the other repositories.

|  | Project | What | Latest |
|---|---|---|---|
| <img src="https://raw.githubusercontent.com/dsd-toolbox/dsd-toolbox/main/docs/assets/projects/scarletbook-rs-64.png" alt="" width="32"> | [scarletbook‑rs](https://github.com/aclater/scarletbook-rs) | Rust and C library that reads SACD images and decodes DST | <!-- facts:release repo=aclater/scarletbook-rs fmt="[{version}]({url})" -->[1.3.0](https://github.com/aclater/scarletbook-rs/releases/tag/v1.3.0)<!-- /facts --> |
| <img src="https://raw.githubusercontent.com/dsd-toolbox/dsd-toolbox/main/docs/assets/projects/sacd-spec-64.png" alt="" width="32"> | [sacd‑spec](https://github.com/aclater/sacd-spec) | Specification of the SACD disc format, with a test corpus | <!-- facts:release repo=aclater/sacd-spec fmt="[{version}]({url})" empty="none: cite the commit" -->none: cite the commit<!-- /facts --> |

## Quick start

Which project do you need?

- **Play your SACD images** without extracting them:
  [sacdfs](https://github.com/dsd-toolbox/sacdfs#quick-start). It runs on Linux, including NAS
  systems; Windows 10 and 11, x64, as a read-only drive letter with WinFsp; and macOS 11 or
  later, Apple Silicon and Intel. Any other system can play the discs over SMB or NFS from a
  NAS or Linux computer that runs sacdfs.
- **Extract or convert images**, from the command line, Python or a beets library:
  [pysacd](https://github.com/dsd-toolbox/pysacd#quick-start) and
  [beets-pysacd](https://github.com/dsd-toolbox/beets-pysacd#quick-start). pysacd needs Python 3.10
  or later and has wheels for Linux (x86_64 and aarch64), macOS (Intel and Apple Silicon) and
  Windows x64.
- **Measure a DSD-to-PCM converter's accuracy**, with readings like those published by
  [Archimago](https://archimago.blogspot.com/), [ASR](https://www.audiosciencereview.com/) and
  [Stereophile](https://www.stereophile.com/content/measurements-maps-precision):
  [dsd-measure](https://github.com/dsd-toolbox/dsd-measure#quick-start). It needs Python 3.11 or
  later and installs from GitHub with pipx.
- **Upconvert to DSD128 or DSD256** as files:
  [dsd-upsample-rs](https://github.com/dsd-toolbox/dsd-upsample-rs#quick-start). The first release
  is the Linux x86_64 library and command line, installed with Cargo or from a release archive. For GStreamer pipelines there is the plug-in
  [dsdup-gst](https://github.com/dsd-toolbox/dsdup-gst#quick-start), built from source on Linux x86_64. For FFmpeg there are the
  patches [ffmpeg-dsf](https://github.com/dsd-toolbox/ffmpeg-dsf#quick-start), also built from source on Linux x86_64. A foobar2000
  component and macOS recipes are planned, and Windows and macOS follow in a later release.
- **Build your own software**: the Rust library [scarletbook-rs](https://github.com/aclater/scarletbook-rs)
  for SACD images, [dsd2pcm-rs](https://github.com/dsd-toolbox/dsd2pcm-rs#quick-start) for DSD to PCM
  and DSF/DFF/WAV files, or [sacd-spec](https://github.com/aclater/sacd-spec#quick-start) to
  write or test a reader of your own.

## Documentation

- [Documentation index](docs/README.md): every document in this repository
- [Clean room](docs/clean-room.md): how sacd-spec and scarletbook-rs are kept independent
- [Decisions](DECISIONS.md): the major decisions and why they were made
- [Releases](RELEASES.md): what each minor version line brought, per project
- [Quality](QUALITY.md): how each project is tested and how its releases can be checked
- [CI/CD](docs/ci-cd.md): how changes are reviewed and releases are built, signed and published
- [Security](SECURITY.md): how to report a vulnerability in any of the projects (privately,
  never in a public issue)
- [Documentation tooling](docs/docs-tooling.md): the shared checks that keep every project's documentation to one standard
- [Contributing](CONTRIBUTING.md)
- [Board](https://github.com/users/aclater/projects/1): open issues and pull requests of the
  projects in one view

## Licence and credits

This repository holds documentation only.

Text and data: [CC BY 4.0](LICENSE). Reuse freely with attribution: "DSD Toolbox,
https://github.com/dsd-toolbox". Code: none here; each project has its own licence, listed in
[Projects](#projects), and credits its upstreams in its own README.
