#!/usr/bin/env python3
"""docs-run: run the command blocks of README.md and docs/ in a fresh container.

    python3 -I tools/docs/docs_run.py list [--root DIR]            # coverage only, runs nothing
    python3 -I tools/docs/docs_run.py run  [--root DIR] [--version X.Y.Z] [--require-coverage N]

The blocks run in a container that holds ONLY the extracted blocks, never the checkout, so
whatever they install is the PUBLISHED release (the install line in the docs is what installs it).

Marking a fenced command block (sh, bash, shell, zsh, console, powershell, cmd):
    ```sh run                                  runs, must exit 0
    <!-- docs-run: key=value ... -->           on the line(s) before the fence: runs with options
    <!-- docs-run: skip="needs a GPU" -->      not run, with a reason (required)
    an unmarked block is reported "not run" (it counts against coverage).

The container is a user's shell: $HOME/.local/bin is on PATH, as in a Fedora login shell.

Keys: image= (default registry.fedoraproject.org/fedora:43), packages= (comma list, dnf),
setup= (shell command instead of dnf), expect= (regex that must match the output; repeat the
key for more; {version} becomes --version), drop= (regex; matching lines are removed from the
block and reported, for example a line that opens a browser), group= (blocks with the same group name, from any file, share one container and one working
folder, in README-first path order; default: one group per file),
timeout= (seconds per group, default 1800), skip= (reason).

Exit: 0 all marked blocks passed (and coverage met), 1 a block failed or coverage too low,
2 a marker is malformed. Standard library only; needs podman for `run`. `--engine local` runs
the blocks on this host without a container: for the tool's own tests, and for a CI job that is
already a disposable container (add --run-setup there).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

CMD_LANGS = {"sh", "bash", "shell", "zsh", "console", "powershell", "ps1", "pwsh", "cmd", "bat"}
RUNNABLE_LANGS = {"sh", "bash", "shell", "console"}
DEFAULT_IMAGE = "registry.fedoraproject.org/fedora:43"
FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([A-Za-z0-9_+-]*)\s*(.*)$")
DIRECTIVE_RE = re.compile(r"^\s*<!--\s*docs-run:(.*?)-->\s*$")
SKIP_DIRS = {".git", ".docs-tools", "node_modules", "target", ".venv", "venv"}


class MarkerError(Exception):
    pass


@dataclass
class Block:
    file: str
    line: int          # 1-based line of the opening fence
    lang: str
    code: str
    status: str        # run | skip | unmarked
    opts: dict = field(default_factory=dict)
    expects: list = field(default_factory=list)
    reason: str = ""
    dropped: list = field(default_factory=list)
    # results
    result: str = ""   # PASS | FAIL | NOT-REACHED | (empty = not run)
    rc: int | None = None
    seconds: float = 0.0
    output: str = ""
    problems: list = field(default_factory=list)
    untagged: bool = False   # a fence with no language tag that reads as a command


def parse_directive(text: str, where: str) -> tuple[dict, list]:
    try:
        tokens = shlex.split(text.strip())
    except ValueError as e:
        raise MarkerError(f"{where}: cannot parse docs-run marker: {e}") from e
    opts: dict = {}
    expects: list = []
    for t in tokens:
        if "=" not in t:
            raise MarkerError(f"{where}: marker argument {t!r} is not key=value")
        k, v = t.split("=", 1)
        if k == "expect":
            expects.append(v)
        elif k in {"image", "packages", "setup", "drop", "group", "timeout", "skip"}:
            opts[k] = v
        else:
            raise MarkerError(f"{where}: unknown docs-run key {k!r}")
    if "skip" in opts and not opts["skip"].strip():
        raise MarkerError(f"{where}: skip= needs a reason")
    return opts, expects


CMD_START = re.compile(r"^(\$ |sudo |curl |wget |tar |cd |mkdir |git |cargo |pip3? |pipx |python3? |dnf |apt(-get)? |brew |"
                       r"gh |podman |docker |make |sh |bash |\./|~/|export |\w[\w.-]* (-{1,2}\w|\w+\.\w))")


def looks_like_command(code: str) -> bool:
    """An untagged fence whose first non-blank line reads as a shell command."""
    for l in code.splitlines():
        if l.strip():
            return bool(CMD_START.match(l.strip()))
    return False


CLASSES = [  # (label, regex over the block text); first match wins
    ("windows", r"(?i)\b(powershell|winget|choco|\.exe|\.msi|C:\\)"),
    ("macos", r"\b(brew |xcode-select|launchctl|hdiutil|pkgutil|open -a|\.dmg|\.pkg)\b"),
    ("needs-root-system", r"\b(systemctl|mount |umount|modprobe|udevadm|firewall-cmd|setsebool|nfs|smbd|/dev/|fusermount)"),
    ("needs-container-engine", r"\b(podman|docker)\b"),
    ("needs-credentials", r"(?i)(GITHUB_TOKEN|GH_TOKEN|api[_ -]?key|\bgh (release|attestation|auth|api)|passw|secret)"),
    ("needs-hardware-or-gpu", r"(?i)\b(cuda|nvidia|gpu|dac|usb|aplay|arecord|alsa)\b"),
    ("needs-user-files", r"(?i)(\.iso\b|\.dsf\b|\.dff\b|\bdisc\b|/mnt/|/srv/|~/Music|album)"),
    ("source-build", r"\b(cargo (build|test|run|install --path)|make\b|cmake|git clone|maturin|pytest|ruff|mypy)"),
    ("placeholders", r"(<[A-Za-z][^>\n]*>|\$\{?[A-Z_]{3,}\}?)"),
]


def classify(b: "Block") -> str:
    """A rough guess why a block cannot run in a plain container, or `candidate` if it looks runnable."""
    for label, rx in CLASSES:
        if re.search(rx, b.code):
            return label
    return "candidate"


def commands_of(lang: str, code: str) -> str:
    """The shell text of a block. A console block keeps only its `$ ` lines."""
    if lang != "console":
        return code
    out = []
    for l in code.splitlines():
        if l.startswith("$ "):
            out.append(l[2:])
        elif l.startswith("> ") and out:   # continuation of the previous command
            out.append(l[2:])
    return "\n".join(out) + "\n"


def extract(path: Path, rel: str) -> list[Block]:
    lines = path.read_text().splitlines()
    blocks: list[Block] = []
    i = 0
    pending: tuple[dict, list, int] | None = None
    while i < len(lines):
        l = lines[i]
        d = DIRECTIVE_RE.match(l)
        if d:
            pending = (*parse_directive(d.group(1), f"{rel}:{i + 1}"), i)
            i += 1
            continue
        m = FENCE_RE.match(l)
        if not m:
            if l.strip() and pending and i - pending[2] > 2:
                pending = None
            i += 1
            continue
        indent, fence, lang, info = m.groups()
        j = i + 1
        body = []
        while j < len(lines) and not re.match(rf"^\s*{fence[0]}{{{len(fence)},}}\s*$", lines[j]):
            body.append(lines[j][len(indent):] if lines[j].startswith(indent) else lines[j])
            j += 1
        # the directive applies to the next fence only, and only if close by
        directive = pending if pending and i - pending[2] <= 2 else None
        pending = None
        lang_l = lang.lower()
        untagged = False
        if lang_l == "" and not info.strip() and looks_like_command("\n".join(body)):
            lang_l, untagged = "sh", True
        if lang_l in CMD_LANGS:
            opts, expects = (directive[0], directive[1]) if directive else ({}, [])
            tokens = info.split()
            run_flag = "run" in tokens
            code = "\n".join(body) + "\n"
            if "skip" in opts:
                status = "skip"
            elif (run_flag or directive) and lang_l in RUNNABLE_LANGS:
                status = "run"
            elif run_flag or directive:
                raise MarkerError(f"{rel}:{i + 1}: a {lang_l} block cannot run in a Linux container; "
                                  f"mark it skip=\"reason\"")
            else:
                status = "unmarked"
            b = Block(rel, i + 1, lang_l, code, status, opts, expects, opts.get("skip", ""))
            b.untagged = untagged
            if status == "run" and "drop" in opts:
                keep = []
                rx = re.compile(opts["drop"])
                text = commands_of(lang_l, code)
                for ln in text.splitlines():
                    (b.dropped if rx.search(ln) else keep).append(ln)
                b.code = "\n".join(keep) + "\n"
                b.lang = "sh"
            elif status == "run":
                b.code = commands_of(lang_l, code)
                b.lang = "sh"
            blocks.append(b)
        i = j + 1
    return blocks


def collect(root: Path) -> list[Block]:
    files = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS)
        files += [Path(dp) / f for f in sorted(fn) if f.endswith(".md")]
    # README.md first, then docs/ in path order
    files.sort(key=lambda p: (p.relative_to(root).parts != ("README.md",), str(p.relative_to(root))))
    out: list[Block] = []
    for p in files:
        out += extract(p, str(p.relative_to(root)))
    return out


def groups_of(blocks: list[Block]) -> dict[tuple[str, str], list[Block]]:
    g: dict[tuple[str, str], list[Block]] = {}
    for b in blocks:
        if b.status == "run":
            name = b.opts.get("group")
            g.setdefault(("group", name) if name else ("file", b.file), []).append(b)
    return g


def group_settings(bs: list[Block]) -> dict:
    s = {"image": DEFAULT_IMAGE, "packages": "", "setup": "", "timeout": "1800"}
    for b in bs:
        for k in s:
            if k in b.opts:
                if s[k] not in ("", DEFAULT_IMAGE, "1800") and s[k] != b.opts[k]:
                    raise MarkerError(f"{b.file}:{b.line}: group has conflicting {k}= "
                                      f"({s[k]!r} and {b.opts[k]!r})")
                s[k] = b.opts[k]
    return s


# --------------------------------------------------------------------------- running


def run_group(key, bs: list[Block], args, run_id: str) -> None:
    s = group_settings(bs)
    work = Path(tempfile.mkdtemp(prefix="docs-run-", dir=args.tmpdir))
    try:
        setup = s["setup"]
        if not setup and s["packages"]:
            setup = "dnf -y -q --setopt=install_weak_deps=False install " + " ".join(s["packages"].split(","))
        driver = ["#!/bin/bash", "set -u",
                  "export PATH=\"$HOME/.local/bin:$PATH\"   # what a Fedora login shell gives a user",
                  f"cd \"${{DOCS_RUN_HOME:-$HOME}}\""]
        if setup and (args.engine == "podman" or args.run_setup):
            d = "/docs-run" if args.engine == "podman" else str(work)
            driver += [f"( {setup} ) > {d}/setup.log 2>&1 || {{ echo 99 > {d}/setup.rc; exit 0; }}"]
        for n, b in enumerate(bs):
            (work / f"b{n}.sh").write_text("set -eo pipefail\n" + b.code)
            driver += [
                f"echo 'DOCS-RUN-START {n}'",
                f"S=$(date +%s%N); bash {{D}}/b{n}.sh > {{D}}/o{n}.log 2>&1; echo $? > {{D}}/rc{n}; "
                f"E=$(date +%s%N); echo $(( (E - S) / 1000000 )) > {{D}}/t{n}",
                f"[ \"$(cat {{D}}/rc{n})\" = 0 ] || [ -n \"${{DOCS_RUN_KEEP_GOING:-}}\" ] || exit 0",
            ]
        script = "\n".join(driver) + "\n"
        if args.engine == "local":
            home = work / "home"
            home.mkdir()
            (work / "driver.sh").write_text(script.replace("{D}", str(work)))
            env = {**os.environ, "DOCS_RUN_HOME": str(home), "HOME": str(home)}
            if args.keep_going:
                env["DOCS_RUN_KEEP_GOING"] = "1"
            cmd = ["bash", str(work / "driver.sh")]
        else:
            (work / "driver.sh").write_text(script.replace("{D}", "/docs-run"))
            env = None
            cmd = ["podman", "run", "--rm", "--label", f"docs-run={run_id}", "--name", f"docs-run-{run_id}-{abs(hash(key)) % 10**6}",
                   "--memory", args.memory, "--memory-swap", args.memory, "--cpus", args.cpus,
                   "-v", f"{work}:/docs-run:Z", "-w", "/root"]
            if args.keep_going:
                cmd += ["-e", "DOCS_RUN_KEEP_GOING=1"]
            cmd += [s["image"], "bash", "/docs-run/driver.sh"]
        try:
            subprocess.run(cmd, env=env, timeout=int(s["timeout"]), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, check=False)
        except subprocess.TimeoutExpired:
            for b in bs:
                b.problems.append(f"group timed out after {s['timeout']} s")
        setup_rc = work / "setup.rc"
        if setup_rc.exists():
            log = (work / "setup.log").read_text()[-2000:]
            for b in bs:
                b.result, b.problems = "FAIL", [f"container setup failed: {log.strip().splitlines()[-1:]}"]
            return
        for n, b in enumerate(bs):
            rcf = work / f"rc{n}"
            if not rcf.exists():
                b.result = "NOT-REACHED" if not b.problems else "FAIL"
                continue
            b.rc = int(rcf.read_text().strip() or 1)
            b.output = (work / f"o{n}.log").read_text(errors="replace")
            try:
                b.seconds = float((work / f"t{n}").read_text().strip() or 0) / 1000.0
            except (OSError, ValueError):
                b.seconds = 0.0
            if b.rc != 0:
                b.problems.append(f"exit status {b.rc}")
            for rx in b.expects:
                pat = rx.replace("{version}", re.escape(args.version)) if args.version else rx
                if "{version}" in rx and not args.version:
                    b.problems.append("expect= uses {version} but --version was not given")
                elif not re.search(pat, b.output, re.M):
                    b.problems.append(f"output does not match expect= {pat!r}")
            b.result = "FAIL" if b.problems else "PASS"
    finally:
        if not args.keep_work:
            shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------- report


def coverage(blocks: list[Block]) -> dict:
    n = len(blocks)
    c = {s: sum(1 for b in blocks if b.status == s) for s in ("run", "skip", "unmarked")}
    c["total"] = n
    c["percent"] = round(100.0 * c["run"] / n, 1) if n else 100.0
    c["accounted_percent"] = round(100.0 * (c["run"] + c["skip"]) / n, 1) if n else 100.0
    return c


def report(blocks: list[Block], executed: bool) -> str:
    c = coverage(blocks)
    out = []
    for b in blocks:
        tag = {"run": b.result or "WILL-RUN", "skip": "SKIP", "unmarked": "NOT RUN"}[b.status]
        extra = ""
        if b.status == "skip":
            extra = f"  ({b.reason})"
        elif b.status == "unmarked":
            extra = "  (no marker)"
        elif b.problems:
            extra = "  (" + "; ".join(b.problems) + ")"
        elif b.seconds:
            extra = f"  ({b.seconds:.1f} s)"
        out.append(f"{tag:11} {b.file}:{b.line} [{b.lang}]{extra}")
        for d in b.dropped:
            out.append(f"{'':11}   dropped line: {d}")
    out.append("")
    out.append(f"docs-run: {c['total']} command block(s): {c['run']} run, {c['skip']} skipped with a reason, "
               f"{c['unmarked']} not run (unmarked); coverage {c['percent']}% run, "
               f"{c['accounted_percent']}% run or skipped with a reason")
    if executed:
        passed = sum(1 for b in blocks if b.result == "PASS")
        failed = sum(1 for b in blocks if b.result in ("FAIL", "NOT-REACHED"))
        out.append(f"docs-run: {passed} passed, {failed} failed or not reached")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", choices=["list", "run"])
    ap.add_argument("--root", default=".")
    ap.add_argument("--version", default="", help="value for {version} in expect=")
    ap.add_argument("--version-of", metavar="OWNER/REPO",
                    help="use that repository's latest GitHub release version for {version} (needs the network)")
    ap.add_argument("--require-coverage", type=float, default=0.0, help="fail below this percentage")
    ap.add_argument("--fail-unmarked", action="store_true", help="fail when any command block is unmarked")
    ap.add_argument("--engine", choices=["podman", "local"], default="podman")
    ap.add_argument("--run-setup", action="store_true",
                    help="with --engine local: also run packages=/setup= here (only inside a disposable container, as root)")
    ap.add_argument("--memory", default="4g")
    ap.add_argument("--cpus", default="4")
    ap.add_argument("--keep-going", action="store_true", help="run the rest of a group after a failure")
    ap.add_argument("--keep-work", action="store_true")
    ap.add_argument("--tmpdir", default=None)
    ap.add_argument("--json", help="write the results to this file")
    ap.add_argument("--only", help="run only blocks from this file")
    ap.add_argument("--classify", action="store_true", help="list: guess why each unmarked block cannot run")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if a.version_of:
        import urllib.request
        req = urllib.request.Request(f"https://api.github.com/repos/{a.version_of}/releases/latest",
                                     headers={"User-Agent": "docs-run (dsd-toolbox)"})
        if os.environ.get("GITHUB_TOKEN"):
            req.add_header("Authorization", "Bearer " + os.environ["GITHUB_TOKEN"])
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                a.version = json.load(r)["tag_name"].lstrip("v")
        except Exception as e:   # noqa: BLE001 - any failure to learn the version is fatal
            print(f"ERROR cannot read the latest release of {a.version_of}: {e}", file=sys.stderr)
            return 2
    try:
        blocks = collect(root)
        if a.only:
            blocks = [b for b in blocks if b.file == a.only]
        groups = groups_of(blocks)
        for bs in groups.values():
            group_settings(bs)
    except MarkerError as e:
        print(f"ERROR {e}", file=sys.stderr)
        return 2
    executed = False
    if a.mode == "run":
        if a.engine == "podman" and not shutil.which("podman"):
            print("ERROR podman not found", file=sys.stderr)
            return 2
        run_id = uuid.uuid4().hex[:8]
        executed = True
        try:
            for key, bs in groups.items():
                run_group(key, bs, a, run_id)
        finally:
            if a.engine == "podman":   # remove anything this run left behind
                ids = subprocess.run(["podman", "ps", "-aq", "--filter", f"label=docs-run={run_id}"],
                                     capture_output=True, text=True).stdout.split()
                if ids:
                    subprocess.run(["podman", "rm", "-f", *ids], capture_output=True)
    text = report(blocks, executed)
    print(text)
    if a.classify:
        from collections import Counter
        cnt = Counter(classify(b) for b in blocks if b.status == "unmarked")
        print("docs-run: unmarked blocks by guess: " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())))
        print(f"docs-run: untagged command fences (docs-style wants a language tag): {sum(b.untagged for b in blocks)}")
    for b in blocks:
        if b.result == "FAIL":
            print(f"\n--- output of {b.file}:{b.line} (last 40 lines)", file=sys.stderr)
            print("\n".join(b.output.splitlines()[-40:]), file=sys.stderr)
    if a.json:
        Path(a.json).write_text(json.dumps({
            "coverage": coverage(blocks),
            "blocks": [{k: getattr(b, k) for k in ("file", "line", "lang", "status", "reason", "result",
                                                   "rc", "seconds", "problems", "dropped", "untagged")}
                       | ({"guess": classify(b)} if b.status == "unmarked" else {}) for b in blocks],
        }, indent=1))
    c = coverage(blocks)
    rc = 0
    if any(b.result in ("FAIL", "NOT-REACHED") for b in blocks):
        rc = 1
    if c["percent"] < a.require_coverage:
        print(f"docs-run: coverage {c['percent']}% is below the required {a.require_coverage}%", file=sys.stderr)
        rc = 1
    if a.fail_unmarked and c["unmarked"]:
        print(f"docs-run: {c['unmarked']} unmarked command block(s)", file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
