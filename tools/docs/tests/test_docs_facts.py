import datetime
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import docs_facts as F  # noqa: E402

REL = {
    "https://api.github.com/repos/old/proj": {"full_name": "new/proj"},
    "https://api.github.com/repos/new/proj/releases/latest": {
        "tag_name": "v1.2.3", "published_at": "2026-11-20T10:00:00Z",
        "html_url": "https://github.com/new/proj/releases/tag/v1.2.3",
        "assets": [{"name": "proj-1.2.3-x86_64-unknown-linux-gnu.tar.gz", "size": 3_000_000},
                   {"name": "proj-1.2.3-aarch64-apple-darwin.tar.gz", "size": 2_000_000},
                   {"name": "proj-1.2.3-x86_64-pc-windows-msvc.zip", "size": 4_000_000},
                   {"name": "SHA256SUMS", "size": 10}]},
    "https://api.github.com/repos/none/spec": {"full_name": "none/spec"},
    "https://api.github.com/repos/none/spec/releases/latest": {"__status__": 404},
    "https://pypi.org/pypi/pkg/json": {"info": {"version": "0.5.5"},
                                       "releases": {"0.5.5": [{"upload_time": "2026-11-23T09:00:00", "filename": "pkg-0.5.5.whl", "size": 5}]}},
    "https://crates.io/api/v1/crates/cr": {"crate": {"max_stable_version": "0.2.0", "newest_version": "0.2.0"},
                                            "versions": [{"num": "0.2.0", "created_at": "2026-11-01T00:00:00Z"}]},
}

WORKFLOW = """name: ci
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]  # comment
        python:
          - "3.11"
          - "3.13"
  other:
    runs-on: ubuntu-latest
"""


class T(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        self.src = F.Source(dict(REL))

    def run_mode(self, mode, text, name="a.md", today=datetime.date(2026, 12, 31)):
        p = self.d / name
        p.write_text(text)
        out = io.StringIO()
        rc = F.run(mode, self.d, [name], self.src, out, today=today)
        return rc, p.read_text(), out.getvalue()

    def test_release_inline_canonical_owner(self):
        t = "x <!-- facts:release repo=old/proj fmt=\"[{version}]({url}) ({date})\" -->stale<!-- /facts --> y\n"
        rc, new, _ = self.run_mode("generate", t)
        self.assertEqual(rc, 0)
        self.assertEqual(new, "x <!-- facts:release repo=old/proj fmt=\"[{version}]({url}) ({date})\" -->[1.2.3](https://github.com/new/proj/releases/tag/v1.2.3) (2026-11-20)<!-- /facts --> y\n")
        rc, _, out = self.run_mode("check", new)
        self.assertEqual(rc, 0)

    def test_check_detects_stale_and_generate_is_idempotent(self):
        t = "<!-- facts:release repo=old/proj -->0.0.1 (2026-01-01)<!-- /facts -->\n"
        rc, _, out = self.run_mode("check", t)
        self.assertEqual(rc, 1)
        self.assertIn("-<!-- facts:release repo=old/proj -->0.0.1", out)
        _, once, _ = self.run_mode("generate", t)
        _, twice, _ = self.run_mode("generate", once)
        self.assertEqual(once, twice)

    def test_stale_release_is_a_warning_for_seven_days_then_an_error(self):
        # the newest release (REL: 2026-11-20) shipped; the committed text still names the previous one
        for key_text in ["<!-- facts:release repo=old/proj -->0.0.1 (2026-01-01)<!-- /facts -->\n",
                         "<!-- facts:latest-date repos=old/proj -->2026-01-01<!-- /facts -->\n",
                         "# facts:install kind=pipx-git repo=old/proj\npipx install git+https://github.com/new/proj@v0.0.1\n# /facts\n"]:
            t = key_text if key_text.startswith("<") else "```sh\n" + key_text + "```\n"
            with self.subTest(region=key_text[:30]):
                for day, rc, warn in [(datetime.date(2026, 11, 20), 0, True), (datetime.date(2026, 11, 27), 0, True),
                                      (datetime.date(2026, 11, 28), 1, False)]:
                    out = io.StringIO()
                    (self.d / "w.md").write_text(t)
                    err = io.StringIO()
                    old, sys.stderr = sys.stderr, err
                    try:
                        got = F.run("check", self.d, ["w.md"], self.src, out, today=day)
                    finally:
                        sys.stderr = old
                    self.assertEqual(got, rc, (day, out.getvalue()))
                    self.assertEqual("WARNING" in err.getvalue(), warn, (day, err.getvalue()))

    def test_other_stale_regions_and_pinned_tags_are_never_warnings(self):
        (self.d / "Cargo.toml").write_text('[package]\nrust-version = "1.80"\n')
        day = datetime.date(2026, 11, 21)
        self.src.snapshot["https://api.github.com/repos/new/proj/releases/tags/v1.2.3"] = \
            self.src.snapshot["https://api.github.com/repos/new/proj/releases/latest"]
        for t in ["<!-- facts:msrv -->1.70<!-- /facts -->\n",
                  "<!-- facts:release repo=old/proj tag=v1.2.3 -->0.0.1<!-- /facts -->\n"]:
            with self.subTest(t=t):
                self.assertEqual(self.run_mode("check", t, today=day)[0], 1)

    def test_generate_clears_the_warning(self):
        t = "<!-- facts:release repo=old/proj -->0.0.1 (2026-01-01)<!-- /facts -->\n"
        _, new, _ = self.run_mode("generate", t, today=datetime.date(2026, 11, 21))
        self.assertEqual(self.run_mode("check", new, today=datetime.date(2026, 11, 21))[0], 0)

    def test_empty_release_needs_opt_in(self):
        rc, _, _ = self.run_mode("check", "<!-- facts:release repo=none/spec -->x<!-- /facts -->\n")
        self.assertEqual(rc, 2)
        rc, new, _ = self.run_mode("generate", "<!-- facts:release repo=none/spec empty=\"no release yet\" -->x<!-- /facts -->\n")
        self.assertEqual(rc, 0)
        self.assertIn(">no release yet<", new)

    def test_block_region_assets(self):
        t = ("<!-- facts:assets repo=old/proj match=\"\\.(tar\\.gz|zip)$\" fmt=\"| {platform} | `{name}` |\" -->\n"
             "old\n<!-- /facts -->\n")
        rc, new, _ = self.run_mode("generate", t)
        self.assertEqual(rc, 0)
        self.assertIn("| Linux x86-64 | `proj-1.2.3-x86_64-unknown-linux-gnu.tar.gz` |", new)
        self.assertIn("| macOS aarch64 |", new)
        self.assertIn("| Windows x86-64 |", new)
        self.assertNotIn("SHA256SUMS", new)
        self.assertTrue(new.endswith("-->\n"))

    def test_shell_region_in_fence(self):
        t = "```sh\nsudo dnf install -y git\n# facts:install kind=pipx-git repo=old/proj\nstale\n# /facts\nproj init\n```\n"
        rc, new, _ = self.run_mode("generate", t)
        self.assertEqual(rc, 0)
        self.assertIn("\npipx install git+https://github.com/new/proj@v1.2.3\n# /facts\nproj init\n", new)

    def test_install_kinds(self):
        for kind, expect in (("pip name=pkg", "pip install pkg"), ("pip name=pkg pin=1", "pip install pkg==0.5.5"),
                             ("cargo name=cr", "cargo install cr"),
                             ("download repo=old/proj asset=linux", "curl -LO https://github.com/new/proj/releases/download/v1.2.3/proj-1.2.3-x86_64-unknown-linux-gnu.tar.gz")):
            rc, new, _ = self.run_mode("generate", f"<!-- facts:install kind={kind} -->x<!-- /facts -->\n")
            self.assertEqual(rc, 0, kind)
            self.assertIn(f">{expect}<", new)

    def test_pypi_and_latest_date(self):
        rc, new, _ = self.run_mode("generate", "<!-- facts:release source=pypi name=pkg fmt=\"{version} {date}\" -->x<!-- /facts -->"
                                   "<!-- facts:latest-date repos=old/proj,none/spec -->x<!-- /facts -->\n")
        self.assertEqual(rc, 0)
        self.assertIn(">0.5.5 2026-11-23<", new)
        self.assertIn(">2026-11-20<", new)

    def test_manifests_and_matrix(self):
        (self.d / "Cargo.toml").write_text('[package]\nname="x"\nrust-version = "1.85"\n')
        (self.d / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.11"\n')
        (self.d / "ci.yml").write_text(WORKFLOW)
        t = ("<!-- facts:msrv -->x<!-- /facts --> <!-- facts:python-min -->x<!-- /facts --> "
             "<!-- facts:ci-matrix file=ci.yml job=test key=os -->x<!-- /facts --> "
             "<!-- facts:ci-matrix file=ci.yml job=test key=python fmt=\"{v}\" sep=\" and \" -->x<!-- /facts -->\n")
        rc, new, _ = self.run_mode("generate", t)
        self.assertEqual(rc, 0)
        self.assertIn(">1.85<", new)
        self.assertIn(">3.11<", new)
        self.assertIn(">`ubuntu-latest`, `macos-latest`<", new)
        self.assertIn(">3.11 and 3.13<", new)

    def test_python_max_from_classifiers(self):
        (self.d / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.10"\nclassifiers = [\n'
                                               '"Programming Language :: Python :: 3",\n"Programming Language :: Python :: 3.9",\n'
                                               '"Programming Language :: Python :: 3.13",\n"Programming Language :: Python :: 3.10",\n'
                                               '"Programming Language :: Python :: Implementation :: CPython"]\n')
        rc, new, _ = self.run_mode("generate", "<!-- facts:python-max -->x<!-- /facts --> <!-- facts:python-max fmt=\"{v}+\" -->x<!-- /facts -->\n")
        self.assertEqual(rc, 0)
        self.assertIn(">3.13<", new)   # numeric, not lexical: 3.13 > 3.9
        self.assertIn(">3.13+<", new)
        (self.d / "pyproject.toml").write_text('[project]\nclassifiers = ["Programming Language :: Python :: 3"]\n')
        self.assertEqual(self.run_mode("check", new)[0], 2)

    def test_dep_min_pyproject(self):
        (self.d / "pyproject.toml").write_text(
            '[project]\ndependencies = ["PyYAML>=6.0.1,<7", "requests[socks] ~= 2.31", "old==1.0", "loose", "up<3"]\n'
            '[project.optional-dependencies]\ndev = ["pytest>=8.2"]\n[dependency-groups]\ntest = ["pytest>=8.0"]\n')
        t = ("<!-- facts:dep-min name=pyyaml -->x<!-- /facts --> <!-- facts:dep-min name=requests -->x<!-- /facts --> "
             "<!-- facts:dep-min name=old fmt=\"{name} {v}\" -->x<!-- /facts --> <!-- facts:dep-min name=pytest group=dev -->x<!-- /facts -->\n")
        rc, new, _ = self.run_mode("generate", t)
        self.assertEqual(rc, 0)
        for want in (">6.0.1<", ">2.31<", ">old 1.0<", ">8.2<"):
            self.assertIn(want, new)
        # one name with two different floors is ambiguous without group=
        self.assertEqual(self.run_mode("check", "<!-- facts:dep-min name=pytest -->x<!-- /facts -->\n")[0], 2)
        for bad in ("loose", "up", "missing"):   # no lower bound, upper bound only, absent
            self.assertEqual(self.run_mode("check", f"<!-- facts:dep-min name={bad} -->x<!-- /facts -->\n")[0], 2, bad)

    def test_dep_min_cargo(self):
        (self.d / "Cargo.toml").write_text('[package]\nname="x"\n[dependencies]\nserde = "1.0.190"\n'
                                           'clap = { version = "^4.5", features = ["derive"] }\ngit-only = { git = "https://example.org/x" }\n'
                                           '[dev-dependencies]\ntempfile = ">=3.8, <4"\n')
        t = ("<!-- facts:dep-min name=serde -->x<!-- /facts --> <!-- facts:dep-min name=clap -->x<!-- /facts --> "
             "<!-- facts:dep-min name=tempfile -->x<!-- /facts -->\n")
        rc, new, _ = self.run_mode("generate", t)
        self.assertEqual(rc, 0)
        for want in (">1.0.190<", ">4.5<", ">3.8<"):
            self.assertIn(want, new)
        self.assertEqual(self.run_mode("check", "<!-- facts:dep-min name=git-only -->x<!-- /facts -->\n")[0], 2)

    def test_region_builds_a_whole_badge_with_the_version_in_its_url(self):
        # A marker cannot sit inside a URL (its spaces would break the link), so the region wraps the whole badge.
        (self.d / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.11"\n')
        badge = ('<!-- facts:python-min fmt="[![Python {v}+](https://img.shields.io/badge/python-{v}%2B-blue)]'
                 '(https://www.python.org/)" -->x<!-- /facts -->\n')
        rc, new, _ = self.run_mode("generate", badge)
        self.assertEqual(rc, 0)
        self.assertIn("[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)<!-- /facts -->", new)
        self.assertEqual(self.run_mode("check", new)[0], 0)
        (self.d / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.12"\n')
        self.assertEqual(self.run_mode("check", new)[0], 1)

    def test_missing_manifest_is_exit_2_not_a_traceback(self):
        for k in ("msrv", "python-min", "python-max", "dep-min name=x"):
            self.assertEqual(self.run_mode("check", f"<!-- facts:{k} -->x<!-- /facts -->\n")[0], 2, k)

    def test_file_cannot_leave_the_checkout(self):
        import os
        outside = self.d.parent / "outside.toml"
        outside.write_text('[package]\nrust-version = "9.9"\n')
        (self.d / "link.toml").symlink_to(outside)
        for f in (str(outside), "../outside.toml", "link.toml", "sub/../../outside.toml"):
            for key in ("msrv", "python-min", "python-max", "dep-min name=x"):
                rc, _, out = self.run_mode("check", f'<!-- facts:{key} file="{f}" -->x<!-- /facts -->\n')
                self.assertEqual(rc, 2, (key, f))
        rc, _, _ = self.run_mode("check", f'<!-- facts:ci-matrix file="../outside.toml" job=a key=b -->x<!-- /facts -->\n')
        self.assertEqual(rc, 2)
        (self.d / "Cargo.toml").write_text('[package]\nrust-version = "1.80"\n')
        self.assertEqual(self.run_mode("generate", '<!-- facts:msrv file="Cargo.toml" -->x<!-- /facts -->\n')[0], 0)

    def test_repo_tag_and_name_are_shape_checked_before_any_request(self):
        urls = []

        class Spy(F.Source):
            def get(self, url):
                urls.append(url)
                return {"__status__": 404}

        self.src = Spy({})
        for bad in ("../x", "x/../../user", "a/b/c", "a/b?x=1", "a", "a/..", "./b", "a/b#f", "a b/c", "a/b%2f..", ""):
            rc, _, out = self.run_mode("check", f'<!-- facts:release repo="{bad}" -->x<!-- /facts -->\n')
            self.assertEqual(rc, 2, bad)
        for bad in ("../x", "a/b", "v1?x=1", "a..", "-x"):
            self.run_mode("check", f'<!-- facts:release repo=new/proj tag="{bad}" -->x<!-- /facts -->\n')
        for src in ("pypi", "crates"):
            for bad in ("../x", "a/b", "a?b", "-x"):
                rc, _, _ = self.run_mode("check", f'<!-- facts:release source={src} name="{bad}" -->x<!-- /facts -->\n')
                self.assertEqual(rc, 2, (src, bad))
        self.assertEqual([u for u in urls if ".." in u or "?" in u or "user" in u], [], urls)
        self.assertFalse([u for u in urls if u.count("/") > 6], urls)
        # a good value still reaches the API
        urls.clear()
        self.run_mode("check", '<!-- facts:release repo=old/proj -->x<!-- /facts -->\n')
        self.assertTrue(urls and urls[0] == "https://api.github.com/repos/old/proj")

    def test_a_trailing_newline_does_not_pass_the_shape_checks(self):
        for fn, ok in ((F.check_repo, "a/b"), (F.check_pkg, "pkg")):
            fn(ok)
            with self.assertRaises(F.FactError):
                fn(ok + "\n")
        with self.assertRaises(F.FactError):
            F.Source(dict(REL)).github_release("old/proj", "v1\n")

    def test_bad_tag_is_refused_after_a_valid_repo(self):
        src = F.Source(dict(REL))
        for bad in ("../x", "a/b", "v1?x=1", "-x", "a b"):
            with self.assertRaises(F.FactError, msg=bad):
                src.github_release("old/proj", bad)
        self.assertEqual(src.github_release("old/proj", "latest")["tag"], "v1.2.3")

    def test_errors_are_exit_2(self):
        for t in ("<!-- facts:nope -->x<!-- /facts -->", "<!-- facts:release -->x<!-- /facts -->",
                  "<!-- facts:ci-matrix file=ci.yml job=ghost key=os -->x<!-- /facts -->"):
            (self.d / "ci.yml").write_text(WORKFLOW)
            rc, _, _ = self.run_mode("check", t + "\n")
            self.assertEqual(rc, 2, t)

    def test_example_fences_are_not_regions(self):
        t = "```text\n<!-- facts:nope -->x<!-- /facts -->\n# facts:nope2\nx\n# /facts\n```\n"
        rc, new, _ = self.run_mode("check", t)
        self.assertEqual((rc, new), (0, t))

    def test_list_does_not_evaluate(self):
        rc, _, out = self.run_mode("list", "<!-- facts:nope -->x<!-- /facts -->\n")
        self.assertEqual(rc, 0)
        self.assertIn("1 region", out)

    def test_unrelated_text_untouched(self):
        t = "no regions here, only the word facts: and <!-- a comment -->\n"
        rc, new, _ = self.run_mode("generate", t)
        self.assertEqual((rc, new), (0, t))


if __name__ == "__main__":
    unittest.main()
