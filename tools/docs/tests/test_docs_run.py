import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import docs_run as R  # noqa: E402

DOC = """# T

```sh run
echo hello
echo version 1.2.3
```

<!-- docs-run: expect="version {version}" drop="xdg-open" -->
```sh
echo version 1.2.3
xdg-open nothing
```

<!-- docs-run: skip="needs root" -->
```sh
sudo reboot
```

```sh
rm -rf /
```

```console
$ echo from-console
output line
```

```powershell
Get-Date
```

```python
print("not a command block")
```
"""


class T(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "README.md").write_text(DOC)

    def test_extract_and_coverage(self):
        bs = R.collect(self.d)
        self.assertEqual([b.status for b in bs], ["run", "run", "skip", "unmarked", "unmarked", "unmarked"])
        self.assertEqual(R.coverage(bs)["percent"], 33.3)
        self.assertEqual(bs[1].dropped, ["xdg-open nothing"])
        self.assertNotIn("xdg-open", bs[1].code)

    def test_list_never_runs(self):
        self.assertEqual(R.main(["list", "--root", str(self.d)]), 0)

    def test_local_run_pass_and_unmarked_fail(self):
        # the console block is unmarked, so only blocks 1 and 2 run
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d), "--version", "1.2.3"]), 0)
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d), "--version", "1.2.3",
                                 "--fail-unmarked"]), 1)
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d), "--version", "1.2.3",
                                 "--require-coverage", "90"]), 1)

    def test_expect_fails_on_wrong_version(self):
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d), "--version", "9.9.9"]), 1)

    def test_failure_stops_group(self):
        (self.d / "README.md").write_text("```sh run\nfalse\n```\n\n```sh run\necho later\n```\n")
        bs = R.collect(self.d)
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d)]), 1)

    def test_bad_markers(self):
        for doc in ('<!-- docs-run: skip="" -->\n```sh\nx\n```\n', '<!-- docs-run: bogus=1 -->\n```sh\nx\n```\n',
                    '<!-- docs-run: image=x -->\n```powershell\nx\n```\n'):
            (self.d / "README.md").write_text(doc)
            self.assertEqual(R.main(["list", "--root", str(self.d)]), 2, doc)

    def test_group_shares_working_folder_across_files(self):
        (self.d / "README.md").write_text("<!-- docs-run: group=g -->\n```sh\ntouch state.txt\n```\n")
        (self.d / "docs").mkdir()
        (self.d / "docs" / "a.md").write_text("<!-- docs-run: group=g -->\n```sh\ntest -f state.txt\n```\n")
        (self.d / "docs" / "b.md").write_text("```sh run\ntest -f state.txt\n```\n")   # own group: must fail
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d), "--only", "docs/a.md"]), 1)
        (self.d / "docs" / "b.md").unlink()
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d)]), 0)


class ResultFiles(unittest.TestCase):
    """The container writes rc/timing/output/setup.log; the host must not trust or follow them."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def test_regular_file_is_read(self):
        (self.d / "o0.log").write_text("hi\n")
        self.assertEqual(R.read_result(self.d / "o0.log"), "hi\n")

    def test_symlink_is_refused(self):
        (self.d / "secret").write_text("0\n")
        os.symlink(self.d / "secret", self.d / "rc0")
        with self.assertRaises(R.UnsafeResult):
            R.read_rc(self.d / "rc0")
        os.symlink(self.d / "nowhere", self.d / "dangling")
        with self.assertRaises(R.UnsafeResult):
            R.read_result(self.d / "dangling")

    def test_fifo_and_directory_are_refused_without_blocking(self):
        os.mkfifo(self.d / "fifo")
        with self.assertRaises(R.UnsafeResult):
            R.read_result(self.d / "fifo")
        (self.d / "dir").mkdir()
        with self.assertRaises(R.UnsafeResult):
            R.read_result(self.d / "dir")

    def test_non_numeric_rc_is_refused(self):
        for bad in ("", "abc", "0 ; x", "-1", "1e3", "0000", "99999"):
            (self.d / "rc").write_text(bad)
            with self.assertRaises(R.UnsafeResult, msg=repr(bad)):
                R.read_rc(self.d / "rc")
        for good, want in (("0\n", 0), ("1", 1), ("137\n", 137)):
            (self.d / "rc").write_text(good)
            self.assertEqual(R.read_rc(self.d / "rc"), want)

    def test_block_that_symlinks_its_rc_file_fails(self):
        # local engine: the block can reach the work folder (parent of its home) and plant a symlink
        target = self.d / "elsewhere"
        target.write_text("0\n")
        doc = self.d / "README.md"
        doc.write_text(f"```sh run\nrm -f \"$HOME/../rc0\"; ln -s {target} \"$HOME/../rc0\"\n```\n")
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d)]), 1)


class RunExclude(unittest.TestCase):
    """[run] exclude keeps files (CLAUDE.md, AGENTS.md, ...) out of every docs tool."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "README.md").write_text("```sh run\necho ok\n```\n")
        (self.d / "CLAUDE.md").write_text("```sh run\nfalse\n```\n")
        (self.d / "docs").mkdir()
        (self.d / "docs" / "AGENTS.md").write_text("```sh run\nfalse\n```\n")
        (self.d / ".docs.toml").write_text('[run]\nexclude = ["CLAUDE.md", "**/AGENTS.md"]\n')

    def test_collect_and_run_skip_excluded(self):
        self.assertEqual({b.file for b in R.collect(self.d, R.load_run(self.d)["exclude"])}, {"README.md"})
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d)]), 0)

    def test_without_the_list_nothing_is_excluded(self):
        (self.d / ".docs.toml").write_text("")
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d)]), 1)

    def test_bad_values_refused(self):
        for bad in ('exclude = "CLAUDE.md"', 'exclude = [1]', 'exclude = ["/etc/x.md"]', 'exclude = ["../x.md"]',
                    'exclude = [""]'):
            (self.d / ".docs.toml").write_text(f"[run]\n{bad}\n")
            self.assertEqual(R.main(["list", "--root", str(self.d)]), 2, bad)

    def test_exclude_comes_from_the_allowlist_ref(self):
        # a branch cannot hide a failing block by excluding it: with --allowlist-ref the base list applies
        git(self.d, "init", "-q", "-b", "main")
        (self.d / ".docs.toml").write_text("")
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "base")
        (self.d / ".docs.toml").write_text('[run]\nexclude = ["CLAUDE.md", "**/AGENTS.md"]\n')
        self.assertEqual(R.main(["list", "--root", str(self.d), "--allowlist-ref", "HEAD"]), 0)
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d), "--allowlist-ref", "HEAD"]), 1)


class Hostile(unittest.TestCase):
    """A marker is text from a file that may not be ours: it may never reach podman as an option."""

    DIGEST = "a" * 64

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def write(self, marker: str, body: str = "echo x\n") -> None:
        (self.d / "README.md").write_text(f"<!-- docs-run: {marker} -->\n```sh\n{body}```\n")

    def test_hostile_values_refused(self):
        for marker in ('image="--privileged x"', "image=--privileged", 'image="-v /:/host"', "image=-v",
                       "image=registry.example/evil:1", "image=fedora@sha256:" + self.DIGEST,
                       "image=Fedora", "image=a/b", 'image="fedora x"', "image=fedora;id",
                       "group=-x", "group=a/b", "packages=-y", "packages=a,--installroot=/x", "packages=a;b",
                       "setup=--foo", "timeout=abc", "timeout=0", "timeout=-5", "timeout=99999", "timeout=1e3",
                       "drop=[", "expect=-x", "skip=-x"):
            self.write(marker)
            self.assertEqual(R.main(["list", "--root", str(self.d)]), 2, marker)

    def test_control_characters_refused(self):
        for k in ("image", "group", "packages", "setup", "expect", "drop", "skip", "timeout"):
            for bad in ("a\nb", "a\rb", "a\x00b", "a\x1bb"):
                with self.assertRaises(R.MarkerError, msg=(k, bad)):
                    R.parse_directive(f"{k}={bad}", "t")

    def test_length_limits(self):
        with self.assertRaises(R.MarkerError):
            R.parse_directive("image=" + "a" * 40, "t")
        with self.assertRaises(R.MarkerError):
            R.parse_directive("drop=" + "a" * 300, "t")

    def test_unknown_alias_refused(self):
        self.write("image=nosuch")
        (self.d / "README.md").write_text("<!-- docs-run: image=nosuch -->\n```sh run\necho x\n```\n")
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(self.d)]), 2)

    def test_allowlist_needs_digest(self):
        for ref in ("registry.example/a/b:1", "--privileged", "example/a@sha256:abc", "a/b@sha256:" + "A" * 64,
                    "../x@sha256:" + self.DIGEST):
            (self.d / ".docs.toml").write_text(f'[run.images.ok]\nref = "{ref}"\n')
            with self.assertRaises(R.MarkerError, msg=ref):
                R.load_images(self.d)
        (self.d / ".docs.toml").write_text(f'[run.images.ok]\nref = "example.org/a/b:1@sha256:{self.DIGEST}"\n')
        imgs = R.load_images(self.d)
        self.assertFalse(imgs["ok"]["network"])
        self.assertIn(R.DEFAULT_ALIAS, imgs)

    def test_builtin_image_is_pinned(self):
        self.assertRegex(R.BUILTIN_IMAGES[R.DEFAULT_ALIAS]["ref"], R.REF_RE)

    def _cmd(self, extra=None, rootless=False, **settings):
        class A:
            memory, cpus, keep_going, unprivileged = "4g", "4", False, False
        s = {"image": "ok", "ref": f"example.org/a/b@sha256:{self.DIGEST}", "network": False,
             "packages": "", "setup": "", "timeout": "60"} | settings
        return R.podman_command(s, Path("/w"), "n", "rid", A, rootless)

    def test_podman_command_shape(self):
        cmd = self._cmd()
        i = cmd.index("--")
        self.assertEqual(cmd[i + 1:], [f"example.org/a/b@sha256:{self.DIGEST}", "bash", "/docs-run/driver.sh"])
        for flag in ("--cap-drop=ALL", "--security-opt=no-new-privileges", "--network=none", "--read-only",
                     "--pids-limit=512", "--timeout=60", "--memory=4g"):
            self.assertIn(flag, cmd[:i])
        self.assertEqual([c for c in cmd if c.startswith(("-v", "--privileged", "--volume", "--device"))], ["-v"])
        self.assertEqual(cmd.count("-v"), 1)

    def test_default_is_unchanged_v2_root_command(self):
        cmd = self._cmd()
        self.assertFalse([c for c in cmd if c.startswith(("--user", "--userns"))])

    def test_unprivileged_without_installs_runs_the_whole_container_as_uid_1000(self):
        cmd = self._cmd(unprivileged=True)
        i = cmd.index("--")
        self.assertIn("--userns=keep-id:uid=1000,gid=1000", cmd[:i])
        self.assertIn("--user=1000:1000", cmd[:i])
        self.assertIn("--cap-drop=ALL", cmd[:i])
        self.assertFalse([c for c in cmd if c.startswith("--cap-add")])

    def test_unprivileged_with_installs_starts_as_root_for_setup_only(self):
        cmd = self._cmd(unprivileged=True, packages="jq")
        self.assertIn("--user=0:0", cmd)
        self.assertTrue([c for c in cmd if c.startswith("--cap-add")])   # setup needs them; blocks get none (see driver)

    def test_unprivileged_install_under_rootless_keeps_both_rules(self):
        cmd = self._cmd(unprivileged=True, packages="jq", rootless=True)
        self.assertIn("--user=0:0", cmd)                              # root only for the install step
        self.assertIn("--userns=keep-id:uid=1000,gid=1000", cmd)
        self.assertEqual(cmd.count("--cap-add=DAC_READ_SEARCH"), 1)   # rootless install capability still granted
        self.assertNotIn("--cap-add=DAC_READ_SEARCH", self._cmd(unprivileged=True, packages="jq"))

    def test_driver_drops_privileges_for_blocks_only_after_a_root_setup(self):
        from unittest import mock
        d = Path(tempfile.mkdtemp())
        (d / "README.md").write_text('<!-- docs-run: packages=jq -->\n```sh run\njq --version\n```\n')
        (d / ".docs.toml").write_text('[run]\nunprivileged = true\npackages = ["jq"]\n')
        seen = {}

        def fake_run(cmd, **kw):
            if not any(c.endswith(":/docs-run:Z") for c in cmd):   # podman ps / rm during cleanup
                return subprocess.CompletedProcess(cmd, 0, stdout=b"" if not kw.get("text") else "")
            work = next(Path(c.split(":")[0]) for c in cmd if c.endswith(":/docs-run:Z"))
            seen["driver"] = (work / "driver.sh").read_text()
            seen["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0)

        with mock.patch.object(R.subprocess, "run", fake_run), mock.patch.object(R.shutil, "which", lambda x: "/bin/podman"):
            R.main(["run", "--engine", "podman", "--root", str(d)])
        drv = seen["driver"]
        self.assertIn("setpriv --reuid=1000 --regid=1000 --clear-groups --bounding-set=-all --inh-caps=-all --no-new-privs bash", drv)
        self.assertLess(drv.index("setup.log"), drv.index("setpriv"))   # setup runs first, as root
        self.assertIn("--user=0:0", seen["cmd"])
        # without unprivileged mode nothing changes
        (d / ".docs.toml").write_text('[run]\npackages = ["jq"]\n')
        with mock.patch.object(R.subprocess, "run", fake_run), mock.patch.object(R.shutil, "which", lambda x: "/bin/podman"):
            R.main(["run", "--engine", "podman", "--root", str(d)])
        self.assertNotIn("setpriv", seen["driver"])

    def test_unprivileged_config_value_is_checked(self):
        d = Path(tempfile.mkdtemp())
        (d / ".docs.toml").write_text('[run]\nunprivileged = "yes"\n')
        with self.assertRaises(R.MarkerError):
            R.load_run(d)

    def test_network_only_when_allowlisted_and_installs_not_read_only(self):
        cmd = self._cmd(network=True, packages="jq")
        self.assertIn("--network=private", cmd)
        self.assertNotIn("--network=none", cmd)
        self.assertNotIn("--read-only", cmd)
        self.assertIn("--cap-drop=ALL", cmd)
        self.assertNotIn("--cap-add=SYS_ADMIN", cmd)
        self.assertTrue(all(c.split("=")[1] in R.INSTALL_CAPS for c in cmd if c.startswith("--cap-add")))
        self.assertNotIn("--cap-add=DAC_READ_SEARCH", cmd)   # rootful, or not known to be rootless
        self.assertIn("--network=none", self._cmd(packages="jq"))   # an image not allowed network gets none

    def test_dac_read_search_only_when_rootless(self):
        rootful = self._cmd(network=True, packages="jq")
        self.assertNotIn("--cap-add=DAC_READ_SEARCH", rootful)
        rootless = self._cmd(network=True, packages="jq", rootless=True)
        self.assertIn("--cap-add=DAC_READ_SEARCH", rootless)
        self.assertEqual(rootless.count("--cap-add=DAC_READ_SEARCH"), 1)
        # no packages= or setup=: no capability added at all, rootless or not
        self.assertFalse([c for c in self._cmd(network=True, rootless=True) if c.startswith("--cap-add")])

    def test_rootless_comes_from_podman_info_and_a_doubt_is_not_rootless(self):
        import unittest.mock as mock
        def info(out, rc=0):
            return mock.Mock(stdout=out, returncode=rc)
        for out, want in (("true\n", True), ("false\n", False), ("", False), ("maybe", False)):
            R.podman_rootless.cache_clear()
            with mock.patch.object(R.subprocess, "run", return_value=info(out)):
                self.assertIs(R.podman_rootless(), want, out)
        R.podman_rootless.cache_clear()
        with mock.patch.object(R.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIs(R.podman_rootless(), False)
        R.podman_rootless.cache_clear()

    def test_marker_text_never_in_command(self):
        cmd = self._cmd(setup="curl evil", packages="jq,git")
        self.assertFalse(any("evil" in c or "jq" in c for c in cmd))

    def test_redirect_drops_authorization_across_hosts(self):
        import urllib.request
        req = urllib.request.Request("https://api.github.com/x", headers={"Authorization": "Bearer t"})
        h = R._DropAuthOnRedirect()
        other = h.redirect_request(req, None, 302, "Found", {}, "https://example.org/y")
        same = h.redirect_request(req, None, 302, "Found", {}, "https://api.github.com/z")
        self.assertFalse(other.has_header("Authorization"))
        self.assertTrue(same.has_header("Authorization"))


def git(d: Path, *args: str) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org", "GIT_CONFIG_GLOBAL": "/dev/null"}
    return subprocess.run(["git", "-C", str(d), *args], env=env, check=True, capture_output=True, text=True).stdout


class Checkout(unittest.TestCase):
    """Checkout mode: the group starts in a COPY of `git archive HEAD`."""

    DIGEST = "b" * 64

    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        git(self.d, "init", "-q", "-b", "main")
        (self.d / "data.txt").write_text("committed\n")
        (self.d / "README.md").write_text(
            "<!-- docs-run: checkout=1 -->\n```sh\n"
            "test -f data.txt\ntest ! -e untracked.txt\ntest ! -e ignored.txt\ntest ! -e .git\n"
            "echo built > built.txt\n```\n")
        (self.d / ".gitignore").write_text("ignored.txt\n")
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "x")
        (self.d / "untracked.txt").write_text("u\n")
        (self.d / "ignored.txt").write_text("i\n")
        (self.d / "data.txt").write_text("uncommitted edit\n")

    def run_local(self, *extra):
        return R.main(["run", "--engine", "local", "--root", str(self.d), *extra])

    def test_block_starts_in_a_copy_of_head(self):
        self.assertEqual(self.run_local(), 0)
        self.assertFalse((self.d / "built.txt").exists(), "the real checkout must not be written to")

    def test_content_is_head_not_the_working_tree(self):
        (self.d / "README.md").write_text(
            "<!-- docs-run: checkout=1 -->\n```sh\ngrep -x committed data.txt\n```\n")
        git(self.d, "commit", "-q", "-am", "readme")   # data.txt edit is committed too: restore it first
        (self.d / "data.txt").write_text("worktree only\n")
        self.assertEqual(self.run_local(), 1)   # HEAD now holds the edit, the work tree something else

    def test_without_the_marker_the_block_is_not_in_the_checkout(self):
        (self.d / "README.md").write_text("```sh run\ntest -f data.txt\n```\n")
        self.assertEqual(self.run_local(), 1)

    def test_config_default_and_per_block_opt_out(self):
        (self.d / ".docs.toml").write_text("[run]\ncheckout = true\n")
        (self.d / "README.md").write_text("```sh run\ntest -f data.txt\n```\n\n"
                                          "<!-- docs-run: checkout=0 group=plain -->\n```sh\ntest ! -f data.txt\n```\n")
        self.assertEqual(self.run_local(), 0)

    def test_marker_values_checked(self):
        for v in ("2", "yes", "-1", "true"):
            with self.assertRaises(R.MarkerError, msg=v):
                R.parse_directive(f"checkout={v}", "t")

    def test_needs_a_git_checkout_root(self):
        sub = self.d / "sub"
        sub.mkdir()
        (sub / "README.md").write_text("<!-- docs-run: checkout=1 -->\n```sh\ntrue\n```\n")
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(sub)]), 2)
        bare = Path(tempfile.mkdtemp())
        (bare / "README.md").write_text("<!-- docs-run: checkout=1 -->\n```sh\ntrue\n```\n")
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(bare)]), 2)

    def test_podman_command_has_no_checkout_mount(self):
        class A:
            memory, cpus, keep_going = "4g", "4", False
        s = {"image": "ok", "ref": f"example.org/a/b@sha256:{self.DIGEST}", "network": False, "packages": "",
             "setup": "", "timeout": "60", "checkout": True}
        cmd = R.podman_command(s, Path("/w"), "n", "rid", A)
        self.assertEqual(cmd.count("-v"), 1)
        self.assertEqual(cmd[cmd.index("-v") + 1], "/w:/docs-run:Z")   # only the work folder, which holds the copy
        self.assertIn("--cap-drop=ALL", cmd)
        self.assertIn("--network=none", cmd)

    def test_toolchain_alias_and_package_allowlist(self):
        (self.d / ".docs.toml").write_text(
            f'[run]\npackages = ["jq"]\n[run.images.rust]\nref = "example.org/rust/rust:1@sha256:{self.DIGEST}"\n'
            'network = true\npackages = ["gcc"]\n')
        imgs = R.load_images(self.d)
        self.assertEqual(imgs["rust"]["packages"], ["gcc"])
        cfg = R.load_run(self.d)
        def gs(marker):
            (self.d / "README.md").write_text(f"<!-- docs-run: {marker} -->\n```sh run\ntrue\n```\n")
            return R.group_settings(R.collect(self.d)[:1], cfg["images"], cfg)
        self.assertEqual(gs("image=rust packages=gcc,jq")["ref"], f"example.org/rust/rust:1@sha256:{self.DIGEST}")
        for bad in ("image=rust packages=gcc,curl", "packages=gcc", "packages=jq,evil"):
            with self.assertRaises(R.MarkerError, msg=bad):
                gs(bad)
        (self.d / ".docs.toml").write_text('[run]\npackages = ["--installroot=/x"]\n')
        with self.assertRaises(R.MarkerError):
            R.load_run(self.d)

    def test_allowlist_is_read_from_the_base_revision(self):
        base = git(self.d, "rev-parse", "HEAD").strip()
        (self.d / ".docs.toml").write_text(
            f'[run.images.evil]\nref = "example.org/x/y@sha256:{self.DIGEST}"\nnetwork = true\n')
        (self.d / "README.md").write_text("<!-- docs-run: image=evil -->\n```sh run\ntrue\n```\n")
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "pr adds an image")
        # from the work tree the PR's own alias works; read from the base it does not exist
        self.assertEqual(R.main(["list", "--root", str(self.d)]), 0)
        self.assertEqual(R.main(["list", "--root", str(self.d), "--allowlist-ref", base]), 2)
        # an unreadable ref fails closed
        self.assertEqual(R.main(["list", "--root", str(self.d), "--allowlist-ref", "nosuchref"]), 2)
        self.assertEqual(R.main(["list", "--root", str(self.d), "--allowlist-ref=--x"]), 2)
        with self.assertRaises(R.MarkerError):
            R.load_run(self.d, "-x")

    def test_first_adoption_pr_cannot_use_its_own_config_so_config_lands_first(self):
        # The adopting PR adds .docs.toml (checkout default on) AND the workflow: its base has no .docs.toml,
        # so the base-read configuration is empty and the checkout default is not applied: the block fails.
        base = git(self.d, "rev-parse", "HEAD").strip()
        (self.d / "README.md").write_text("```sh run\ntest -f data.txt\n```\n")
        (self.d / ".docs.toml").write_text("[run]\ncheckout = true\n")
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "adopt: config and workflow together")
        self.assertEqual(self.run_local(), 0)                              # head's own config: would pass
        self.assertEqual(self.run_local("--allowlist-ref", base), 1)       # base has no config: red, by design
        # step 2 (workflow only): the base now holds .docs.toml and the same README passes
        head = git(self.d, "rev-parse", "HEAD").strip()
        self.assertEqual(self.run_local("--allowlist-ref", head), 0)

    def test_base_allowlist_still_works_when_the_pr_changes_the_file(self):
        (self.d / ".docs.toml").write_text(
            f'[run.images.ok]\nref = "example.org/x/y@sha256:{self.DIGEST}"\n')
        git(self.d, "add", ".docs.toml")
        git(self.d, "commit", "-q", "-m", "base config")
        base = git(self.d, "rev-parse", "HEAD").strip()
        (self.d / ".docs.toml").write_text("")   # the PR deletes the alias
        (self.d / "README.md").write_text("<!-- docs-run: image=ok -->\n```sh run\ntrue\n```\n")
        self.assertEqual(R.main(["list", "--root", str(self.d)]), 2)
        self.assertEqual(R.main(["list", "--root", str(self.d), "--allowlist-ref", base]), 0)


class Fixtures(Checkout):
    """fixtures=PATH runs a script of the checkout copy before the group's blocks."""

    def doc(self, marker, fixture, block="test -f made-by-fixture.txt"):
        (self.d / "tools").mkdir(exist_ok=True)
        (self.d / "tools" / "fx.sh").write_text(fixture)
        (self.d / "README.md").write_text(f"<!-- docs-run: checkout=1 {marker} -->\n```sh\n{block}\n```\n")
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "fixtures")

    def test_fixture_runs_from_the_copy_before_the_blocks(self):
        self.doc("fixtures=tools/fx.sh", "touch made-by-fixture.txt\n")
        self.assertEqual(self.run_local(), 0)
        self.assertFalse((self.d / "made-by-fixture.txt").exists(), "the real checkout must not be written to")

    def test_a_failing_fixture_fails_the_group_and_no_block_runs(self):
        self.doc("fixtures=tools/fx.sh", "exit 3\n", block="touch ran.txt")
        self.assertEqual(self.run_local("--json", str(self.d / "r.json")), 1)
        import json
        res = json.loads((self.d / "r.json").read_text())
        self.assertIn("fixtures tools/fx.sh failed", json.dumps(res))

    def test_without_the_fixture_the_block_fails(self):
        self.doc("", "touch made-by-fixture.txt\n")
        self.assertEqual(self.run_local(), 1)

    def test_bad_paths_refused(self):
        for bad in ("/etc/x", "../x.sh", "a/../b.sh", "-x.sh", "a//b.sh", "a b.sh", "$(id).sh", "a;b.sh", "a" * 101):
            with self.assertRaises(R.MarkerError, msg=bad):
                R.parse_directive(f'fixtures="{bad}"', "t")

    def test_needs_checkout_mode(self):
        (self.d / "README.md").write_text('<!-- docs-run: checkout=0 fixtures=tools/fx.sh -->\n```sh\ntrue\n```\n')
        self.assertEqual(R.main(["list", "--root", str(self.d)]), 2)

    def test_fixture_is_dropped_to_the_unprivileged_user_after_root_setup(self):
        from unittest import mock
        self.doc("packages=jq fixtures=tools/fx.sh", "true\n", block="true")
        (self.d / ".docs.toml").write_text('[run]\nunprivileged = true\npackages = ["jq"]\n')
        git(self.d, "add", "-A")
        git(self.d, "commit", "-q", "-m", "cfg")
        seen = {}

        def fake_run(cmd, **kw):
            if not any(c.endswith(":/docs-run:Z") for c in cmd):
                if cmd[0] == "git":   # export_checkout and config reads are real
                    return real_run(cmd, **kw)
                return subprocess.CompletedProcess(cmd, 0, stdout="" if kw.get("text") else b"")
            work = next(Path(c.split(":")[0]) for c in cmd if c.endswith(":/docs-run:Z"))
            seen["driver"] = (work / "driver.sh").read_text()
            return subprocess.CompletedProcess(cmd, 0)

        real_run = subprocess.run
        with mock.patch.object(R.subprocess, "run", fake_run), mock.patch.object(R.shutil, "which", lambda x: "/bin/podman"):
            R.main(["run", "--engine", "podman", "--root", str(self.d)])
        line = next(l for l in seen["driver"].splitlines() if "fx.sh" in l)
        self.assertTrue(line.startswith("setpriv --reuid=1000"), line)
        self.assertLess(seen["driver"].index("setup.log"), seen["driver"].index("fx.sh"))


class FailUnmarked(unittest.TestCase):
    def test_new_unmarked_block_fails(self):
        d = Path(tempfile.mkdtemp())
        (d / "README.md").write_text("```sh run\ntrue\n```\n")
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(d), "--fail-unmarked"]), 0)
        (d / "README.md").write_text("```sh run\ntrue\n```\n\n```sh\nmake\n```\n")
        self.assertEqual(R.main(["run", "--engine", "local", "--root", str(d), "--fail-unmarked"]), 1)
        self.assertEqual(R.main(["list", "--root", str(d), "--fail-unmarked"]), 1)
        (d / "README.md").write_text("```sh run\ntrue\n```\n\n<!-- docs-run: skip=\"needs root\" -->\n```sh\nmake\n```\n")
        self.assertEqual(R.main(["list", "--root", str(d), "--fail-unmarked"]), 0)


if __name__ == "__main__":
    unittest.main()
