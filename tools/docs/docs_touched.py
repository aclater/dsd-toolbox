#!/usr/bin/env python3
"""docs-touched (T5): a change to code, options, configuration or behaviour must touch the docs.

    python3 -I tools/docs/docs_touched.py --base origin/main --head HEAD            # a whole PR or branch
    python3 -I tools/docs/docs_touched.py --range origin/main..HEAD --each          # every commit of a batch
    python3 -I tools/docs/docs_touched.py --commit SHA
    python3 -I tools/docs/docs_touched.py --base-dir DIR       # a tree against a copy of the base (no git history)

A change passes when it touches no code path, or touches a docs path (README, docs/, CHANGELOG,
man pages ...), or says why none is needed, on a line of the PR body or of a commit message:

    Docs: none needed — a typo in a test helper

(an em dash, en dash, hyphen or double hyphen before the reason; the reason must be a few words).

--each checks every first-parent commit of the range on its own (a merge commit is one change:
its diff against its first parent, its message and the messages of the commits it brings in).
The PR body comes from --body-file, or from the PR_BODY environment variable. --base-dir is for
runners that only have a snapshot of the change (local CI): the changed files are those that
differ from the copy of the base branch in DIR, and the opt-out line can only come from PR_BODY.

Paths are set in .docs.toml:

    [touched]
    code   = ["src/**", "csrc/**"]          # a change here needs docs
    docs   = ["README.md", "docs/**", "CHANGELOG.md", "man/**"]
    ignore = ["tests/**", ".github/**"]     # never counts as code

Exit status 1 when a change needs docs and has neither.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docslib as dl  # noqa: E402

DEFAULT_CODE = ["src/**", "csrc/**", "include/**", "crates/**", "lib/**", "cli/**", "bin/**", "app/**",
                "**/*.rs", "**/*.c", "**/*.h", "**/*.py", "**/*.go", "**/*.toml.in", "config/**", "man/**",
                "packaging/**", "deploy/**", "Containerfile", "Dockerfile"]
DEFAULT_DOCS = ["README.md", "CHANGELOG.md", "CONTRIBUTING.md", "docs/**", "man/**", "**/README.md", "RELEASES.md"]
DEFAULT_IGNORE = ["tests/**", "test/**", "**/tests/**", "fuzz/**", "benches/**", "examples/**", ".github/**",
                  "scripts/**", "tools/**", "**/test_*.py", "**/*_test.py", "**/conftest.py"]
# A path in both lists counts as docs (man pages are code and documentation at once); to require
# a docs change for them, remove them from docs in .docs.toml.
OPT_OUT = re.compile(r"^\s*Docs:\s*none needed\s*(?:—|–|--|-)\s*(\S.{6,})$", re.I | re.M)


def paths_of(cfg: dl.Config) -> tuple[list[str], list[str], list[str]]:
    t = cfg.section("touched")
    return (t.get("code", DEFAULT_CODE), t.get("docs", DEFAULT_DOCS), t.get("ignore", DEFAULT_IGNORE))


def classify(cfg: dl.Config, changed: list[str]) -> tuple[list[str], list[str]]:
    code, docs, ignore = paths_of(cfg)
    c = [p for p in changed if dl.matches(p, code) and not dl.matches(p, ignore) and not dl.matches(p, docs)]
    d = [p for p in changed if dl.matches(p, docs)]
    return c, d


def judge(cfg: dl.Config, label: str, changed: list[str], messages: str) -> tuple[bool, str]:
    code, docs = classify(cfg, changed)
    if not code:
        return True, f"{label}: no code, option or behaviour path changed"
    if docs:
        return True, f"{label}: {len(code)} code path(s) and {len(docs)} docs path(s) changed"
    m = OPT_OUT.search(messages)
    if m:
        return True, f"{label}: no docs change, opted out: {m[1].strip()}"
    shown = ", ".join(code[:5]) + (" ..." if len(code) > 5 else "")
    return False, (f"{label}: changes {shown} but no README, docs/ or CHANGELOG file. Update the docs, or add a line "
                   f"'Docs: none needed — <reason>' to the PR body or the commit message.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--name")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--base", help="PR base; with --head, diff base...head")
    g.add_argument("--range", help="commit range A..B")
    g.add_argument("--commit")
    g.add_argument("--base-dir", help="a copy of the base tree; the changed files are those that differ from it")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--each", action="store_true", help="with --range: check each first-parent commit separately")
    ap.add_argument("--body-file", help="file holding the PR body (default: $PR_BODY)")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    cfg = dl.load_config(root, args.name)
    body = Path(args.body_file).read_text() if args.body_file else os.environ.get("PR_BODY", "")
    ok_all, lines = True, []

    def files_of(*a: str) -> list[str]:
        return [p for p in dl.git(root, "diff", "--name-only", "--no-renames", *a).splitlines() if p]

    def msgs(rev_range: str) -> str:
        return dl.git(root, "log", "--format=%B%n", rev_range)

    if args.base_dir:
        base = Path(args.base_dir).resolve()
        skip = dl.SKIP_DIRS | {base.name}

        def walk(top: Path) -> dict[str, bytes]:
            out = {}
            for p in top.rglob("*"):
                parts = p.relative_to(top).parts
                if p.is_file() and not (set(parts) & skip) and not (top == root and parts[0] == base.name):
                    out[p.relative_to(top).as_posix()] = p.read_bytes()
            return out
        a_files, b_files = walk(base), walk(root)
        changed = sorted(k for k in a_files.keys() | b_files.keys() if a_files.get(k) != b_files.get(k))
        ok, line = judge(cfg, f"tree against {base.name}", changed, body)
        ok_all &= ok
        lines.append((ok, line))
    elif args.base:
        span = f"{args.base}...{args.head}"
        ok, line = judge(cfg, f"{args.base}..{args.head}", files_of(span), body + "\n" + msgs(f"{args.base}..{args.head}"))
        ok_all &= ok
        lines.append((ok, line))
    elif args.commit:
        sha = dl.git(root, "rev-parse", args.commit).strip()
        parents = dl.git(root, "rev-list", "--parents", "-n1", sha).split()[1:]
        base = parents[0] if parents else "4b825dc642cb6eb9a060e54bf8d69288fbd2e5b"
        text = dl.git(root, "log", "-1", "--format=%B", sha)
        if len(parents) > 1:
            text += "\n" + msgs(f"{parents[0]}..{parents[1]}")
        ok, line = judge(cfg, sha[:12], files_of(base, sha), text)
        ok_all &= ok
        lines.append((ok, line))
    else:
        a, b = args.range.split("..", 1)
        if args.each:
            shas = dl.git(root, "rev-list", "--first-parent", "--reverse", args.range).split()
            for sha in shas:
                parents = dl.git(root, "rev-list", "--parents", "-n1", sha).split()[1:]
                if not parents:
                    continue
                text = dl.git(root, "log", "-1", "--format=%B", sha)
                if len(parents) > 1:
                    text += "\n" + msgs(f"{parents[0]}..{parents[1]}")
                subject = dl.git(root, "log", "-1", "--format=%s", sha).strip()[:60]
                ok, line = judge(cfg, f"{sha[:12]} {subject}", files_of(parents[0], sha), text)
                ok_all &= ok
                lines.append((ok, line))
            if not shas:
                lines.append((True, "no commits in range"))
        else:
            ok, line = judge(cfg, args.range, files_of(f"{a}...{b}"), body + "\n" + msgs(args.range))
            ok_all &= ok
            lines.append((ok, line))
    for ok, line in lines:
        print(("ok    " if ok else "FAIL  ") + line)
    print(f"docs-touched: {'ok' if ok_all else 'failed'}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
