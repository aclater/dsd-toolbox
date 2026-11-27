"""Shared helpers for the DSD Toolbox docs tools (docs_lint, docs_links, docs_touched, docs_audit).

Standard library only, Python 3.11 or later. Each tool adds this folder to sys.path itself, so
`python3 -I tools/docs/<tool>.py` works.
"""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_NAME = ".docs.toml"
FOOTER = "Part of the [DSD Toolbox](https://github.com/dsd-toolbox/dsd-toolbox)."
ORG = "dsd-toolbox"
# Repositories that moved from the aclater account to the dsd-toolbox organisation. scarletbook-rs
# and sacd-spec stay under aclater and are deliberately not listed. Add more in .docs.toml (moved_repos).
MOVED_REPOS = ["sacdfs", "pysacd", "beets-pysacd", "dsd2pcm-rs", "dsd-measure", "dsd-toolbox"]
SKIP_DIRS = {".git", ".docs-tools", ".base", "node_modules", "target", "venv", ".venv", "__pycache__", "build", "dist"}
AGENT_FILES = {"AGENTS.md", "CLAUDE.md"}


@dataclass
class Config:
    root: Path
    name: str = ""
    kind: str = "app"            # app | library | overview | spec
    default_branch: str = "main"
    org: str = ORG
    footer: bool = True
    moved_repos: list[str] = field(default_factory=lambda: list(MOVED_REPOS))
    raw: dict = field(default_factory=dict)

    def section(self, name: str) -> dict:
        v = self.raw.get(name, {})
        return v if isinstance(v, dict) else {}


def load_config(root: Path, name: str | None = None) -> Config:
    path = root / CONFIG_NAME
    raw: dict = {}
    if path.exists():
        with path.open("rb") as fh:
            raw = tomllib.load(fh)
    cfg = Config(root=root, raw=raw)
    cfg.name = name or raw.get("name") or root.resolve().name
    cfg.kind = raw.get("kind", cfg.kind)
    cfg.default_branch = raw.get("default_branch", cfg.default_branch)
    cfg.org = raw.get("org", cfg.org)
    cfg.footer = bool(raw.get("footer", cfg.footer))
    cfg.moved_repos = sorted(set(cfg.moved_repos) | set(raw.get("moved_repos", [])))
    return cfg


def parse_run_exclude(raw: dict, where: str = CONFIG_NAME) -> list[str]:
    """`[run] exclude`: repo-relative globs of Markdown files that no docs tool looks at (CLAUDE.md, AGENTS.md, ...)."""
    run = raw.get("run", {})
    ex = run.get("exclude", []) if isinstance(run, dict) else []
    if not isinstance(ex, list) or not all(isinstance(x, str) and x and len(x) <= 200 for x in ex):
        raise ConfigError(f"{where}: [run] exclude must be a list of path globs")
    for x in ex:
        if x.startswith("/") or ".." in Path(x).parts or any(ord(c) < 32 or ord(c) == 127 for c in x):
            raise ConfigError(f"{where}: [run] exclude {x!r}: use a repo-relative glob without '..'")
    return list(ex)


class ConfigError(Exception):
    pass


def glob_to_re(pattern: str) -> re.Pattern[str]:
    """Glob with `**` (any depth) and `*` (within one folder), matched against a repo-relative path."""
    out, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pattern.startswith("**", i):
            out += ".*"
            i += 2
        elif pattern[i] == "*":
            out += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pattern[i])
            i += 1
    return re.compile(out + r"\Z")


def matches(path: str, patterns: list[str]) -> bool:
    return any(glob_to_re(p).match(path) for p in patterns)


def markdown_files(root: Path, exclude: list[str] | None = None) -> list[Path]:
    """Every Markdown file: tracked by git when this is a checkout, else found by walking.
    Files matching `[run] exclude` of .docs.toml (or the `exclude` argument) are left out."""
    if exclude is None:
        exclude = parse_run_exclude(load_config(root).raw)
    return [p for p in _markdown_files(root) if not matches(rel(root, p), exclude)]


def _markdown_files(root: Path) -> list[Path]:
    files: list[Path] = []
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others",
                              "--exclude-standard", "--", "*.md"],
                             capture_output=True, check=True).stdout.decode()
        files = [root / p for p in out.split("\0") if p and (root / p).is_file()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    if not files:
        files = [p for p in root.rglob("*.md") if not (set(p.relative_to(root).parts) & SKIP_DIRS)]
    return sorted(p for p in files if not (set(p.relative_to(root).parts) & SKIP_DIRS))


def rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


# ---- Markdown scanning ----------------------------------------------------------------------

FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*([^`\s]*)\s*(.*)$")


@dataclass
class Line:
    no: int            # 1-based
    text: str
    kind: str          # prose | fence-open | fence | fence-close | comment
    lang: str = ""     # for fence lines: the info-string language


BADGE_REGION_RE = re.compile(r"^<!-- facts:[a-z][a-z0-9-]*(?:\s[^>]*?)? -->\s*\[?!\[.*<!-- /facts -->$")


def scan(text: str) -> list[Line]:
    """Classify each line: prose, code fence (open/body/close) or HTML comment."""
    lines: list[Line] = []
    fence = ""
    lang = ""
    in_comment = False
    for no, raw in enumerate(text.splitlines(), 1):
        if fence:
            m = FENCE_RE.match(raw)
            if m and m[2][0] == fence[0] and len(m[2]) >= len(fence) and not m[3] and not m[4]:
                lines.append(Line(no, raw, "fence-close", lang))
                fence = ""
            else:
                lines.append(Line(no, raw, "fence", lang))
            continue
        if in_comment:
            lines.append(Line(no, raw, "comment"))
            if "-->" in raw:
                in_comment = False
            continue
        m = FENCE_RE.match(raw)
        if m:
            fence, lang = m[2], m[3].lower()
            lines.append(Line(no, raw, "fence-open", lang))
            continue
        stripped = raw.strip()
        if BADGE_REGION_RE.match(stripped):   # a badge generated by a facts region is a badge, not a comment
            lines.append(Line(no, raw, "prose"))
            continue
        if stripped.startswith("<!--"):
            lines.append(Line(no, raw, "comment"))
            if "-->" not in stripped:
                in_comment = True
            continue
        lines.append(Line(no, raw, "prose"))
    return lines


URL_RE = re.compile(r"https?://(?:[^\s<>\"'()\[\]]|\([^\s<>\"'()]*\))+")
INLINE_DEST_RE = re.compile(r"(!?)\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*<?((?:[^()\s>]|\([^()\s]*\))+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
REFDEF_RE = re.compile(r"^\s{0,3}\[([^\]]+)\]:\s*<?(\S+?)>?(?:\s+.*)?$")
HTML_ATTR_RE = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")


MAX_SPAN_LINE = 4000   # a longer line is not scanned for code spans (and docs-lint reports it as too long)
_TICKS_RE = re.compile(r"`+")


def code_spans(line: str) -> list[tuple[int, int]]:
    """(start, end) of each inline code span, by the CommonMark rule in linear time: a run of n backticks is
    closed by the NEXT run of exactly n backticks; a run with no closer is literal text."""
    if len(line) > MAX_SPAN_LINE:
        return []
    runs = [(m.start(), m.end()) for m in _TICKS_RE.finditer(line)]
    nxt: list[int | None] = [None] * len(runs)
    last: dict[int, int] = {}
    for i in range(len(runs) - 1, -1, -1):          # next run of the same length, one pass from the right
        n = runs[i][1] - runs[i][0]
        nxt[i] = last.get(n)
        last[n] = i
    spans, i = [], 0
    while i < len(runs):
        j = nxt[i]
        if j is None:
            i += 1
        else:
            spans.append((runs[i][0], runs[j][1]))
            i = j + 1
    return spans


def blank_code_spans(line: str) -> str:
    out, pos = [], 0
    for a, b in code_spans(line):
        out += [line[pos:a], " " * (b - a)]
        pos = b
    out.append(line[pos:])
    return "".join(out)


def prose_text(line: str) -> str:
    """A prose line with code spans, link destinations, HTML tags and bare URLs blanked out."""
    s = blank_code_spans(line)
    s = INLINE_DEST_RE.sub(lambda m: f"{m.group(1)}[{m.group(2)}]" + " " * (len(m.group(0)) - len(m.group(2)) - len(m.group(1)) - 2), s)
    s = HTML_TAG_RE.sub(lambda m: " " * len(m.group(0)), s)
    s = URL_RE.sub(lambda m: " " * len(m.group(0)), s)
    return s


def slug(heading: str, seen: dict[str, int]) -> str:
    """GitHub's heading anchor: lower case, punctuation dropped, spaces to hyphens, -N for repeats."""
    text = re.sub(r"<[^>]+>", "", heading)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*]|(?<!\w)_|_(?!\w)", "", text).strip().lower()
    s = re.sub(r"[^\w\- ]", "", text).replace(" ", "-")
    n = seen.get(s, 0)
    seen[s] = n + 1
    return s if n == 0 else f"{s}-{n}"


def plain(heading: str) -> str:
    """Heading text without Markdown formatting."""
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"[`*]", "", t).strip()


@dataclass
class Heading:
    level: int
    text: str
    no: int
    anchor: str


def headings(lines: list[Line]) -> list[Heading]:
    out: list[Heading] = []
    seen: dict[str, int] = {}
    for ln in lines:
        if ln.kind != "prose":
            continue
        m = re.match(r"(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$", ln.text)
        if m:
            out.append(Heading(len(m[1]), plain(m[2]), ln.no, slug(m[2], seen)))
    return out


def anchors_of(text: str) -> set[str]:
    lines = scan(text)
    found = {h.anchor for h in headings(lines)}
    for ln in lines:
        if ln.kind == "prose":
            for m in re.finditer(r"""\b(?:id|name)\s*=\s*["']([^"']+)["']""", ln.text):
                found.add(m[1])
    return {a.lower() for a in found}


# ---- findings -------------------------------------------------------------------------------

@dataclass
class Finding:
    path: str
    line: int
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.message}"


def report(findings: list[Finding], as_json: bool, tool: str, out=None) -> int:
    out = out or sys.stdout
    findings = sorted(findings, key=lambda f: (f.path, f.line, f.rule))
    if as_json:
        json.dump({"tool": tool, "ok": not findings, "count": len(findings),
                   "findings": [f.__dict__ for f in findings]}, out, indent=1)
        out.write("\n")
    else:
        for f in findings:
            print(f, file=out)
        by_rule: dict[str, int] = {}
        for f in findings:
            by_rule[f.rule] = by_rule.get(f.rule, 0) + 1
        summary = ", ".join(f"{r} {n}" for r, n in sorted(by_rule.items()))
        print(f"{tool}: {len(findings)} finding(s)" + (f" ({summary})" if summary else ""), file=out)
    return 1 if findings else 0


def git(root: Path, *args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout
