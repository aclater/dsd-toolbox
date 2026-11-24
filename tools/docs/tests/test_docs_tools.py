"""Tests for the docs tools. Run: python3 -I tools/docs/tests/test_docs_tools.py"""

from __future__ import annotations

import http.server
import io
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import docs_audit  # noqa: E402
import docs_lint  # noqa: E402
import docs_links  # noqa: E402
import docs_touched  # noqa: E402
import docslib as dl  # noqa: E402

FOOTER = dl.FOOTER
BLOCK = (HERE.parent / "release-step.md").read_text().strip()

FILES = {
    "README.md": f"""<img src="https://raw.githubusercontent.com/dsd-toolbox/demo/main/docs/assets/icon-96.png" alt="" width="96">

# demo

[![Version](https://img.shields.io/github/v/release/dsd-toolbox/demo)](https://github.com/dsd-toolbox/demo/releases)
[![Licence: MIT](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

Plays discs for people who like quiet rooms. It is fast and small.

## Platforms

| System | How | Guide |
|---|---|---|
| Linux | package | [Linux](docs/user-guide.md) |

## Quick start

```sh
demo --version
```

More ways to install are in the [user guide](docs/user-guide.md).

## Documentation

- [Documentation index](docs/README.md)
- [User guide](docs/user-guide.md)

## Licence and credits

Code: MIT. Text and data: CC BY 4.0. Thanks to everyone upstream.

{FOOTER}
""",
    "CHANGELOG.md": "# Changelog\n\n## [Unreleased]\n\n## [1.1.0] - 2026-11-02\n\n### Added\n\n- A thing.\n\n## [1.0.0] - 2026-10-01\n\n### Fixed\n\n- Another.\n",
    "CONTRIBUTING.md": "# Contributing\n\nSend a change.\n",
    "SECURITY.md": "# Security\n\nTell us privately.\n",
    "LICENSE": "MIT\n",
    "CITATION.cff": "cff-version: 1.2.0\ntitle: demo\n",
    ".docs.toml": 'name = "demo"\nmoved_repos = ["demo"]\n',
    "docs/assets/icon-96.png": "png\n",
    "docs/README.md": f"""[demo](../README.md) › Documentation

# Documentation

Every document about demo.

## Use

- [User guide](user-guide.md): a tour

## Release

- [Releasing](release.md#after-the-release-run-the-docs-audit)

## See also

- [demo](../README.md): the project
- [Changelog](../CHANGELOG.md): what changed

{FOOTER}
""",
    "docs/user-guide.md": f"""[demo](../README.md) › [Documentation](README.md) › User guide

# User guide

How to use demo.

## Quick tour

Run it.

## See also

- [Documentation](README.md): the index
- [Changelog](../CHANGELOG.md): what changed

{FOOTER}
""",
    "docs/release.md": f"""[demo](../README.md) › [Documentation](README.md) › Releasing

# Releasing

The steps for a release.

{BLOCK}

## See also

- [Documentation](README.md): the index
- [Changelog](../CHANGELOG.md): what changed

{FOOTER}
""",
}


def make_repo(extra: dict[str, str | None] | None = None) -> Path:
    root = Path(tempfile.mkdtemp(prefix="docs-tools-test-")) / "demo"
    files = dict(FILES)
    for k, v in (extra or {}).items():
        if v is None:
            files.pop(k, None)
        else:
            files[k] = v
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return root


def lint(root: Path, **kw) -> list[str]:
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        docs_lint.main([str(root), "--name", "demo"])
    return re.findall(r"^\S+?:\d+: \[([\w-]+)\]", out.getvalue(), re.M)


class Base(unittest.TestCase):
    def setUp(self):
        self.dirs: list[Path] = []

    def tearDown(self):
        for d in self.dirs:
            shutil.rmtree(d.parent, ignore_errors=True)

    def repo(self, extra=None) -> Path:
        r = make_repo(extra)
        self.dirs.append(r)
        return r


class LintTests(Base):
    def test_good_repo_is_clean(self):
        self.assertEqual(lint(self.repo()), [])

    def rule_fires(self, rule: str, extra: dict, good_text: str | None = None):
        self.assertIn(rule, lint(self.repo(extra)), rule)

    def test_licence_citation_notice(self):
        self.rule_fires("readme-licence", {"README.md": FILES["README.md"].replace("Text and data: CC BY 4.0. ", "")})
        self.rule_fires("required-file", {"CITATION.cff": None})
        self.rule_fires("required-file", {"LICENSE": "Apache License\nVersion 2.0, January 2004\n", "NOTICE": None, "Cargo.toml": '[package]\nlicense = "MIT OR Apache-2.0"\n'})
        self.assertNotIn("required-file", lint(self.repo({"Cargo.toml": '[package]\nlicense = "MIT OR Apache-2.0"\n', "NOTICE": "demo\n"})))

    def test_page_shape(self):
        ug = FILES["docs/user-guide.md"]
        self.rule_fires("breadcrumb", {"docs/user-guide.md": ug.replace("› User guide", "› Guide")})
        self.rule_fires("breadcrumb", {"docs/user-guide.md": ug.replace("(README.md)", "(index.md)")})
        self.rule_fires("h1", {"docs/user-guide.md": ug + "\n# Another\n"})
        self.rule_fires("lead", {"docs/user-guide.md": ug.replace("How to use demo.\n\n", "")})
        self.rule_fires("lead", {"docs/user-guide.md": ug.replace("How to use demo.", "One. Two. Three. Four.")})
        self.rule_fires("heading-depth", {"docs/user-guide.md": ug.replace("Run it.", "#### Deep\n\nRun it.")})
        self.rule_fires("heading-case", {"docs/user-guide.md": ug.replace("## Quick tour", "## Quick Tour")})
        self.rule_fires("see-also", {"docs/user-guide.md": ug.replace("## See also", "## Related")})
        self.rule_fires("see-also", {"docs/user-guide.md": ug.replace("- [Changelog](../CHANGELOG.md): what changed\n", "")})
        self.rule_fires("footer", {"docs/user-guide.md": ug.replace(FOOTER, "")})

    def test_nested_pages_and_icons(self):
        page = FILES["docs/user-guide.md"].replace("[demo](../README.md) › [Documentation](README.md) › User guide",
                                                   "[demo](../../README.md) › [Documentation](../README.md) › [Install](README.md) › Install demo")
        page = page.replace("# User guide", "# Install demo").replace("(README.md): the index", "(../README.md): the index").replace("(../CHANGELOG.md)", "(../../CHANGELOG.md)")
        idx = FILES["docs/README.md"].replace("- [User guide](user-guide.md): a tour", "- [User guide](user-guide.md): a tour\n- [Install](install/README.md): install demo")
        folder = page.replace("› Install demo", "› Install", 1).replace("[Install](README.md) › Install", "Install")
        folder = folder.replace("[demo](../../README.md) › [Documentation](../README.md) › Install", "[demo](../../README.md) › [Documentation](../README.md) › Install")
        extra = {"docs/install/README.md": folder, "docs/install/linux.md": page.replace("(../README.md): the index", "(../README.md): the index"),
                 "docs/README.md": idx.replace("install/README.md): install demo", "install/README.md): install demo")}
        self.assertEqual(lint(self.repo(extra)), ["index-unlisted"])      # linux.md is not in the install index
        folder_listing = folder.replace("## Quick tour\n\nRun it.", "## Pages\n\n- [Linux](linux.md): Linux install")
        extra["docs/install/README.md"] = folder_listing
        self.assertEqual(lint(self.repo(extra)), [])
        icon = FILES["docs/README.md"].replace("[demo](../README.md) › Documentation", '<img src="assets/icon-96.png" alt="" width="96">\n\n[demo](../README.md) › Documentation')
        self.assertEqual(lint(self.repo({"docs/README.md": icon})), [])

    def test_index(self):
        self.rule_fires("index-unlisted", {"docs/extra.md": FILES["docs/user-guide.md"].replace("User guide", "Extra")})
        self.rule_fires("index-missing", {"docs/README.md": None})
        idx = FILES["docs/README.md"]
        self.rule_fires("index-group", {"docs/README.md": idx.replace("## Use", "## Guides")})
        self.rule_fires("index-group", {"docs/README.md": idx.replace("## Use", "## Release2").replace("## Release\n", "## Use\n")})

    def test_readme(self):
        rd = FILES["README.md"]
        self.rule_fires("readme-sections", {"README.md": rd.replace("## Platforms", "## Systems")})
        self.rule_fires("readme-sections", {"README.md": rd.replace("## Documentation", "## Extra\n\ntext\n\n## Documentation")})
        self.rule_fires("readme-title", {"README.md": rd.replace("# demo", "# Demo")})
        self.rule_fires("readme-badges", {"README.md": rd.replace("[![Licence: MIT]", "[![License: MIT]")})
        self.rule_fires("readme-badges", {"README.md": "\n".join(l for l in rd.splitlines() if "Licence: MIT" not in l)})
        self.rule_fires("old-owner", {"README.md": rd.replace("dsd-toolbox/demo)", "aclater/demo)", 1)})
        self.rule_fires("readme-pitch", {"README.md": rd.replace("It is fast and small.", "It is fast. It is small.")})
        self.rule_fires("readme-quickstart", {"README.md": rd.replace("```sh\ndemo --version\n```", "Run demo.")})
        self.rule_fires("readme-docs", {"README.md": rd.replace("- [Documentation index](docs/README.md)\n- [User guide](docs/user-guide.md)", "Read the docs.")})
        self.rule_fires("footer", {"README.md": rd.replace(FOOTER, "")})

    def test_badge_set_follows_the_workflows(self):
        rd = FILES["README.md"]
        extra = {".github/workflows/ci.yml": "name: ci\n", "README.md": rd}
        self.assertIn("readme-badges", lint(self.repo(extra)))      # ci.yml exists, no CI badge
        ci = "[![CI](https://github.com/dsd-toolbox/demo/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dsd-toolbox/demo/actions/workflows/ci.yml)\n"
        fixed = rd.replace("[![Version]", ci + "[![Version]")
        self.assertEqual(lint(self.repo({".github/workflows/ci.yml": "name: ci\n", "README.md": fixed})), [])
        wrong_order = rd.replace("[![Version]", "[![Version]", 1).replace("[![Licence", ci + "[![Licence")
        self.assertIn("readme-badges", lint(self.repo({".github/workflows/ci.yml": "name: ci\n", "README.md": wrong_order})))

    def test_licence_badge_matches_manifest(self):
        extra = {"Cargo.toml": '[package]\nname = "demo"\nlicense = "Apache-2.0"\n'}
        self.assertIn("readme-badges", lint(self.repo(extra)))

    def test_files_and_changelog(self):
        self.rule_fires("required-file", {"SECURITY.md": None})
        self.rule_fires("changelog-format", {"CHANGELOG.md": "# Changelog\n\n## [1.0.0] - 2026-10-01\n"})
        self.rule_fires("changelog-format", {"CHANGELOG.md": FILES["CHANGELOG.md"].replace("### Fixed", "### Bugs")})
        self.rule_fires("changelog-format", {"CHANGELOG.md": FILES["CHANGELOG.md"].replace("2026-11-02", "02/11/2026")})
        self.rule_fires("changelog-format", {"CHANGELOG.md": FILES["CHANGELOG.md"].replace("[1.1.0]", "[0.9.0]")})

    def test_release_step(self):
        self.rule_fires("release-step", {"docs/release.md": FILES["docs/release.md"].replace(BLOCK, "")})
        self.rule_fires("release-step", {"docs/release.md": FILES["docs/release.md"].replace("Do it once", "Do it when")})

    def test_text_rules(self):
        def with_line(line: str) -> dict:
            return {"CONTRIBUTING.md": f"# Contributing\n\n{line}\n"}
        for rule, line in [
            ("spelling", "The behavior of the tool, and its color."),
            ("spelling", "We normalize the input and analyze it."),
            ("terminology", "Plays sacd discs."),
            ("terminology", "Writes DSD 64 and dsf files."),
            ("terminology", "Samples at 44.1 KHz."),
            ("terminology", "The output is byte identical."),
            ("terminology", "Runs in realtime."),
            ("emoji", "Done \U0001F389"),
            ("text-art", "+-----+\n| box |\n+-----+"),
            ("date-format", "Released on 02/11/2026."),
            ("date-format", "Released on 2 November 2026."),
            ("old-owner", "See https://github.com/aclater/demo for more."),
            ("old-owner", "Clone aclater/pysacd now."),
            ("private-info", "Host 192.168.1.20 is the NAS."),
            ("private-info", "Look in /home/alice/music."),
            ("private-info", "See https://claude.ai/code/session_abc."),
            ("fence-lang", "```\nplain\n```"),
            ("placeholder", "```sh\necho $HOME\n```"),
            ("placeholder", "```sh\ncp <file> out\n```"),
            
        ]:
            with self.subTest(rule=rule, line=line):
                self.assertIn(rule, lint(self.repo(with_line(line))))

    def test_cited_source_must_be_linked(self):
        rd = FILES["README.md"]
        self.assertIn("cited-source", lint(self.repo({"README.md": rd.replace("CC BY 4.0. Thanks", "CC BY 4.0. Measured like Archimago does. Thanks")})))
        ok = rd.replace("CC BY 4.0. Thanks", "CC BY 4.0. Measured like [Archimago](https://archimago.blogspot.com/) does. Thanks")
        self.assertEqual(lint(self.repo({"README.md": ok})), [])

    def test_text_rules_leave_code_and_names_alone(self):
        ok = ("Use `--color` and `sacd-extract`, see [sacd-spec](https://github.com/aclater/sacd-spec), "
              "the file `a.iso`, and https://example.org/sacd/ISO. The SACD image (ISO) is byte-identical.\n\n"
              "```sh\nsacdfs --color /mnt/iso\n```\n")
        self.assertEqual(lint(self.repo({"CONTRIBUTING.md": "# Contributing\n\n" + ok})), [])

    def test_scarletbook_and_sacd_spec_stay_under_aclater(self):
        line = "See https://github.com/aclater/scarletbook-rs and https://github.com/aclater/sacd-spec."
        self.assertEqual(lint(self.repo({"CONTRIBUTING.md": f"# Contributing\n\n{line}\n"})), [])

    def test_suppression_needs_a_reason(self):
        text = "# Contributing\n\n<!-- docs-lint: ignore terminology -- quoted from the vendor -->\nPlays sacd discs.\n"
        self.assertEqual(lint(self.repo({"CONTRIBUTING.md": text})), [])
        bad = "# Contributing\n\n<!-- docs-lint: ignore terminology -->\nPlays sacd discs.\n"
        self.assertIn("suppression", lint(self.repo({"CONTRIBUTING.md": bad})))

    def test_title_case_heuristic(self):
        f = docs_lint.is_title_case
        self.assertTrue(f("Quick Start", set()))
        self.assertTrue(f("Install the Package", set()))
        self.assertFalse(f("Quick start", set()))
        self.assertFalse(f("Install on Windows", set()))
        self.assertFalse(f("Using the CLI", set()))
        self.assertFalse(f("Licence and credits", set()))


class LinkTests(Base):
    def run_links(self, root: Path, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            rc = docs_links.main([str(root), "--name", "demo", *args])
        return rc, out.getvalue()

    def test_good_repo(self):
        self.assertEqual(self.run_links(self.repo())[0], 0)

    def test_broken_relative_and_anchor(self):
        ug = FILES["docs/user-guide.md"]
        rc, out = self.run_links(self.repo({"docs/user-guide.md": ug.replace("Run it.", "See [x](missing.md), [y](README.md#nope) and [z](#quick-tour) and [w](../README.md#quick-start).")}))
        self.assertEqual(rc, 1)
        self.assertIn("link-missing", out)
        self.assertIn("anchor-missing", out)
        self.assertEqual(out.count("[anchor-missing]"), 1)

    def test_own_repository_urls_are_resolved_offline(self):
        ug = FILES["docs/user-guide.md"]
        good = "[a](https://github.com/dsd-toolbox/demo/blob/main/docs/README.md) [b](https://github.com/aclater/demo/blob/main/CHANGELOG.md)"
        bad = "[a](https://github.com/dsd-toolbox/demo/blob/main/docs/nope.md)"
        self.assertEqual(self.run_links(self.repo({"docs/user-guide.md": ug.replace("Run it.", good)}))[0], 0)
        self.assertEqual(self.run_links(self.repo({"docs/user-guide.md": ug.replace("Run it.", bad)}))[0], 1)

    def test_code_is_not_checked(self):
        ug = FILES["docs/user-guide.md"].replace("Run it.", "`[x](nope.md)`\n\n```md\n[x](nope.md)\n```")
        self.assertEqual(self.run_links(self.repo({"docs/user-guide.md": ug}))[0], 0)

    def test_external(self):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(404 if self.path.startswith("/gone") else 200)
                self.end_headers()
                self.wfile.write(b"x")

            def log_message(self, *a):
                pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            ug = FILES["docs/user-guide.md"].replace("Run it.", f"[ok]({base}/ok) [gone]({base}/gone) [walled]({base}/walled/x).")
            toml = f'name = "demo"\n[links]\nexclude = []\n[[links.allow]]\nurl = "{base}/walled"\nreason = "test"\n'
            root = self.repo({"docs/user-guide.md": ug, ".docs.toml": toml})
            # 127.0.0.1 is excluded by default; the test lifts that with an empty default via a custom pattern
            orig = docs_links.DEFAULT_EXCLUDE
            docs_links.DEFAULT_EXCLUDE = []
            try:
                rc, out = self.run_links(root, "--external", "--retries", "0", "--delay", "0")
            finally:
                docs_links.DEFAULT_EXCLUDE = orig
        finally:
            srv.shutdown()
        self.assertEqual(rc, 1)
        self.assertIn("/gone", out)
        self.assertNotIn("/ok", out)
        self.assertNotIn("/walled", out)


def git(root: Path, *a: str) -> str:
    return subprocess.run(["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.org", *a],
                          check=True, capture_output=True, text=True).stdout


class TouchedTests(Base):
    def setUp(self):
        super().setUp()
        self.root = self.repo({"src/a.rs": "fn a() {}\n"})
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "start")

    def commit(self, files: dict[str, str], msg: str) -> str:
        for k, v in files.items():
            p = self.root / k
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(v)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", msg)
        return git(self.root, "rev-parse", "HEAD").strip()

    def run_t(self, *args: str, body: str = "") -> int:
        bf = self.root.parent / "body.txt"
        bf.write_text(body)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return docs_touched.main([str(self.root), "--name", "demo", "--body-file", str(bf), *args])

    def test_code_without_docs_fails(self):
        git(self.root, "checkout", "-q", "-b", "feat")
        self.commit({"src/a.rs": "fn a() { 1; }\n"}, "change a")
        self.assertEqual(self.run_t("--base", "main", "--head", "feat"), 1)

    def test_code_with_docs_passes(self):
        git(self.root, "checkout", "-q", "-b", "feat")
        self.commit({"src/a.rs": "fn a() { 1; }\n", "CHANGELOG.md": FILES["CHANGELOG.md"] + "\n"}, "change a")
        self.assertEqual(self.run_t("--base", "main", "--head", "feat"), 0)

    def test_opt_out_in_body_and_in_commit(self):
        git(self.root, "checkout", "-q", "-b", "feat")
        self.commit({"src/a.rs": "fn a() { 1; }\n"}, "change a")
        self.assertEqual(self.run_t("--base", "main", "--head", "feat", body="Docs: none needed — an internal rename"), 0)
        self.assertEqual(self.run_t("--base", "main", "--head", "feat", body="Docs: none needed"), 1)
        self.assertEqual(self.run_t("--base", "main", "--head", "feat", body="Docs: none needed — x"), 1)  # reason too short
        git(self.root, "checkout", "-q", "main")
        git(self.root, "checkout", "-q", "-b", "feat2")
        self.commit({"src/a.rs": "fn a() { 2; }\n"}, "change a again\n\nDocs: none needed - no behaviour change")
        self.assertEqual(self.run_t("--base", "main", "--head", "feat2"), 0)

    def test_tests_and_ci_do_not_count(self):
        git(self.root, "checkout", "-q", "-b", "feat")
        self.commit({"tests/t.rs": "x\n", ".github/workflows/x.yml": "x\n"}, "tests only")
        self.assertEqual(self.run_t("--base", "main", "--head", "feat"), 0)

    def test_each_commit_of_a_batch(self):
        git(self.root, "checkout", "-q", "-b", "batch/1")
        self.commit({"src/a.rs": "fn a() { 1; }\n"}, "code only")
        self.commit({"CHANGELOG.md": FILES["CHANGELOG.md"] + "\n"}, "docs only")
        # as a whole the batch passes, commit by commit it does not
        self.assertEqual(self.run_t("--base", "main", "--head", "batch/1"), 0)
        self.assertEqual(self.run_t("--range", "main..batch/1", "--each"), 1)

    def test_each_merge_commit_uses_the_merged_messages(self):
        git(self.root, "checkout", "-q", "-b", "change")
        self.commit({"src/a.rs": "fn a() { 3; }\n"}, "inner\n\nDocs: none needed — pure refactor")
        git(self.root, "checkout", "-q", "main")
        git(self.root, "checkout", "-q", "-b", "batch/2")
        git(self.root, "merge", "-q", "--no-ff", "-m", "Merge change", "change")
        self.assertEqual(self.run_t("--range", "main..batch/2", "--each"), 0)

    def test_base_dir_mode(self):
        base = self.root.parent / "base"
        shutil.copytree(self.root, base, ignore=shutil.ignore_patterns(".git"))
        (self.root / "src/a.rs").write_text("fn a() { 9; }\n")
        self.assertEqual(self.run_t("--base-dir", str(base)), 1)
        self.assertEqual(self.run_t("--base-dir", str(base), body="Docs: none needed — an internal change"), 0)
        (self.root / "CHANGELOG.md").write_text(FILES["CHANGELOG.md"] + "\n")
        self.assertEqual(self.run_t("--base-dir", str(base)), 0)

    def test_commit_mode(self):
        git(self.root, "checkout", "-q", "-b", "feat")
        sha = self.commit({"src/a.rs": "fn a() { 5; }\n"}, "change")
        self.assertEqual(self.run_t("--commit", sha), 1)


class AuditTests(Base):
    def test_sync_release_step_inserts_before_see_also_and_is_idempotent(self):
        root = self.repo({"docs/release.md": FILES["docs/release.md"].replace(BLOCK, "")})
        with redirect_stdout(io.StringIO()):
            docs_audit.main([str(root), "--sync-release-step", "docs/release.md"])
        text = (root / "docs/release.md").read_text()
        self.assertEqual(text, FILES["docs/release.md"])
        self.assertLess(text.index("docs-audit:begin"), text.index("## See also"))
        with redirect_stdout(io.StringIO()):
            docs_audit.main([str(root), "--sync-release-step", "docs/release.md"])
        self.assertEqual((root / "docs/release.md").read_text(), text)
        self.assertEqual(lint(root), [])

    def test_checklist_lists_versions_options_and_platforms(self):
        ug = FILES["docs/user-guide.md"].replace("Run it.", "Version 0.9.0 is the latest.\n\n```sh\ndemo --fast\n```\n\nWorks on Linux and Windows.")
        root = self.repo({"docs/user-guide.md": ug})
        out = io.StringIO()
        with redirect_stdout(out):
            docs_audit.main([str(root), "--name", "demo", "--release", "1.2.0"])
        text = out.getvalue()
        self.assertIn("0.9.0", text)
        self.assertIn("`--fast`", text)
        self.assertIn("Linux, Windows", text)
        self.assertIn("'Latest' and 'current'", text)

    def test_check_fails_when_lint_fails_and_passes_when_clean(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = docs_audit.main([str(self.repo()), "--name", "demo", "--check", "--no-external"])
        self.assertEqual(rc, 0)
        bad = self.repo({"CONTRIBUTING.md": "# Contributing\n\nPlays sacd discs.\n"})
        with redirect_stdout(io.StringIO()):
            rc = docs_audit.main([str(bad), "--name", "demo", "--check", "--no-external"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
