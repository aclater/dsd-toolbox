# Quality

The standard the DSD Toolbox projects are held to, and how anyone can check it. The aim is that
other projects adopt these libraries because they are correct, accurate, secure and stable, and
this page shows where the evidence is rather than asking for trust. Each project's own
documents have the detail and win over this page. The shared process is in
[docs/ci-cd.md](docs/ci-cd.md).

## The standard

Careless code does not ship. Every release has a written test plan that is run end to end, with
byte-identity and golden checks against the previous release and against reference output,
fuzzing, sanitizers and leak soaks, and corpora of real files. Every Quick start and every
command in the documentation is run on the release it describes. Audio measurements can be
reproduced with [dsd-measure](https://github.com/dsd-toolbox/dsd-measure), whose own accuracy is
documented. An independent security review can stop a release. Known limits are written down,
not hidden.

## Evidence by project

"Being added" means the page does not exist yet. A dash means the check does not apply.

| Project | Release test plan | CI checks | Fuzzing | Performance | Audio quality | Security |
|---|---|---|---|---|---|---|
| [sacdfs](https://github.com/dsd-toolbox/sacdfs) | [test plan](https://github.com/dsd-toolbox/sacdfs/blob/main/docs/test-plan.md) | [ci.yml](https://github.com/dsd-toolbox/sacdfs/blob/main/.github/workflows/ci.yml) | yes: [fuzz/README.md](https://github.com/dsd-toolbox/sacdfs/blob/main/fuzz/README.md) | [performance](https://github.com/dsd-toolbox/sacdfs/blob/main/docs/performance.md) | [PCM quality](https://github.com/dsd-toolbox/sacdfs/blob/main/docs/pcm-quality.md) | [SECURITY.md](https://github.com/dsd-toolbox/sacdfs/blob/main/SECURITY.md) |
| [pysacd](https://github.com/dsd-toolbox/pysacd) | being added | [ci.yml](https://github.com/dsd-toolbox/pysacd/blob/master/.github/workflows/ci.yml), [development](https://github.com/dsd-toolbox/pysacd/blob/master/docs/development.md) | yes: [fuzz.yml](https://github.com/dsd-toolbox/pysacd/blob/master/.github/workflows/fuzz.yml) | [performance](https://github.com/dsd-toolbox/pysacd/blob/master/docs/performance.md) | – | [SECURITY.md](https://github.com/dsd-toolbox/pysacd/blob/master/SECURITY.md) |
| [beets‑pysacd](https://github.com/dsd-toolbox/beets-pysacd) | being added | [ci.yml](https://github.com/dsd-toolbox/beets-pysacd/blob/main/.github/workflows/ci.yml) | yes: [fuzz.yml](https://github.com/dsd-toolbox/beets-pysacd/blob/main/.github/workflows/fuzz.yml) | – | – | [SECURITY.md](https://github.com/dsd-toolbox/beets-pysacd/blob/main/SECURITY.md) |
| [scarletbook‑rs](https://github.com/aclater/scarletbook-rs) | being added | [ci.yml](https://github.com/aclater/scarletbook-rs/blob/main/.github/workflows/ci.yml) | yes: [fuzz/README.md](https://github.com/aclater/scarletbook-rs/blob/main/fuzz/README.md) | [performance](https://github.com/aclater/scarletbook-rs/blob/main/docs/performance.md) | – | [SECURITY.md](https://github.com/aclater/scarletbook-rs/blob/main/SECURITY.md) |
| [dsd2pcm‑rs](https://github.com/dsd-toolbox/dsd2pcm-rs) | being added; [testing](https://github.com/dsd-toolbox/dsd2pcm-rs/blob/main/docs/testing.md) covers soaks, leaks, Miri and TSan | [ci.yml](https://github.com/dsd-toolbox/dsd2pcm-rs/blob/main/.github/workflows/ci.yml) | yes: [fuzzing](https://github.com/dsd-toolbox/dsd2pcm-rs/blob/main/docs/fuzzing.md) | [performance](https://github.com/dsd-toolbox/dsd2pcm-rs/blob/main/docs/performance.md) | being added | [SECURITY.md](https://github.com/dsd-toolbox/dsd2pcm-rs/blob/main/SECURITY.md) |
| [dsd‑measure](https://github.com/dsd-toolbox/dsd-measure) | being added | being added | no | – | [footprint](https://github.com/dsd-toolbox/dsd-measure/blob/main/docs/footprint.md), [examples](https://github.com/dsd-toolbox/dsd-measure/blob/main/examples/README.md) | [SECURITY.md](https://github.com/dsd-toolbox/dsd-measure/blob/main/SECURITY.md) |
| [sacd‑spec](https://github.com/aclater/sacd-spec) | – (no code; [corpus](https://github.com/aclater/sacd-spec/blob/main/corpus/README.md)) | [docs-links.yml](https://github.com/aclater/sacd-spec/blob/main/.github/workflows/docs-links.yml) | – | – | – | [SECURITY.md](https://github.com/aclater/sacd-spec/blob/main/SECURITY.md) |

dsd-measure follows the published practice of
[Archimago](https://archimago.blogspot.com/),
[Audio Science Review](https://www.audiosciencereview.com/) and
[Stereophile](https://www.stereophile.com/content/measurements-maps-precision), and shows its own
measurement floor next to every result, so a good device is not hidden by the tool.

## Check it yourself

1. **A release is what the project built.** Download a file and verify its checksum and build
   attestation. This example is dsd2pcm-rs 0.1.1; `--deny-self-hosted-runners` rejects anything
   not built on a GitHub-hosted runner.

   <!-- docs-run: skip="gh needs a signed-in GitHub token, which docs-run never passes to a container" -->
   ```sh
   gh release download v0.1.1 -R dsd-toolbox/dsd2pcm-rs -p 'dsd2pcm-0.1.1-x86_64-linux.tar.gz*'
   sha256sum -c dsd2pcm-0.1.1-x86_64-linux.tar.gz.sha256
   gh attestation verify dsd2pcm-0.1.1-x86_64-linux.tar.gz -R dsd-toolbox/dsd2pcm-rs \
     --signer-workflow dsd-toolbox/dsd2pcm-rs/.github/workflows/release.yml \
     --source-ref refs/tags/v0.1.1 --deny-self-hosted-runners
   ```

2. **Reproduce the measurements.** dsd-measure's Quick start measures its reference decoder and
   modulator and writes a report with its own floor shown:

   <!-- docs-run: packages=sudo,gcc,git,python3-pip,pipx expect="^Finished in" expect="dsd-measure {version}" -->
   ```sh
   sudo dnf install -y gcc git python3-pip pipx
   # facts:install kind=pipx-git repo=dsd-toolbox/dsd-measure
   pipx install git+https://github.com/dsd-toolbox/dsd-measure@v0.1.3
   # /facts
   dsd-measure --version
   dsd-measure init
   dsd-measure run suite.toml
   ```

3. **Run a project's tests.** For example dsd2pcm-rs, which checks its output against its
   reference filters at every SIMD level:

   <!-- docs-run: skip="builds and tests a whole project; that project's own CI runs it" -->
   ```sh
   git clone https://github.com/dsd-toolbox/dsd2pcm-rs
   cd dsd2pcm-rs
   cargo test --release --workspace
   ```

4. **Read the plan, then the CI.** Each plan in the table says what is run before a release;
   the workflow links show what runs on every change.

## Known limits

Each project says what it does not do and how it behaves at the edges:

- [sacdfs limits](https://github.com/dsd-toolbox/sacdfs/blob/main/docs/limits.md) and
  [PCM quality](https://github.com/dsd-toolbox/sacdfs/blob/main/docs/pcm-quality.md)
- [pysacd security and hostile images](https://github.com/dsd-toolbox/pysacd/blob/master/docs/security.md)
- [scarletbook-rs stability](https://github.com/aclater/scarletbook-rs/blob/main/docs/stability.md)
- [dsd2pcm-rs robustness](https://github.com/dsd-toolbox/dsd2pcm-rs/blob/main/docs/design.md#robustness)
- [dsd-measure reference floor](https://github.com/dsd-toolbox/dsd-measure/blob/main/docs/footprint.md#the-reference-floor)
- [sacd-spec validation and limits](https://github.com/aclater/sacd-spec/blob/main/spec/07-validation-and-limits.md)

## See also

- [CI/CD](docs/ci-cd.md): how changes are reviewed and releases are built and published
- [Security](SECURITY.md): how to report a vulnerability
- [Releases](RELEASES.md): what each version line brought
