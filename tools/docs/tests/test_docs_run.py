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

if __name__ == "__main__":
    unittest.main()
