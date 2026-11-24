#!/usr/bin/env python3
"""docs-facts: generate and check marked regions in Markdown from the sources of truth.

    python3 -I tools/docs/docs_facts.py check    [--root DIR] [FILE ...]
    python3 -I tools/docs/docs_facts.py generate [--root DIR] [FILE ...]
    python3 -I tools/docs/docs_facts.py list     [--root DIR] [FILE ...]

A region is text between two markers. In prose, tables and fenced blocks' surroundings:

    <!-- facts:release repo=dsd-toolbox/sacdfs fmt="{version} ({date})" -->0.7.2 (2026-11-22)<!-- /facts -->

and inside a fenced block (the markers are shell comments, so the block still runs):

    # facts:install kind=pipx-git repo=dsd-toolbox/dsd-measure
    pipx install git+https://github.com/dsd-toolbox/dsd-measure@v0.1.1
    # /facts

`generate` rewrites every region. `check` exits 1 and prints a diff when a region is stale,
and 2 when a region cannot be evaluated (unknown key, missing argument, source unreachable).
The tool reads only public release data and files in --root. Standard library only.
See tools/docs/README.md for every key.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shlex
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class _DropAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Never send the Authorization header to another host than the one it was meant for."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            for h in ("Authorization", "authorization"):
                new.headers.pop(h, None)
                new.unredirected_hdrs.pop(h, None)
        return new


_OPENER = urllib.request.build_opener(_DropAuthOnRedirect)

HTML_RE = re.compile(r"<!-- facts:([a-z][a-z0-9-]*)((?:\s[^>]*?)?) -->(.*?)<!-- /facts -->", re.S)
SHELL_RE = re.compile(
    r"^([ \t]*)# facts:([a-z][a-z0-9-]*)((?:[ \t][^\n]*)?)\n(.*?)^[ \t]*# /facts[ \t]*$",
    re.S | re.M,
)
SKIP_DIRS = {".git", ".docs-tools", "node_modules", "target", ".venv", "venv"}


class FactError(Exception):
    """A region that cannot be evaluated (exit status 2)."""


# --------------------------------------------------------------------------- sources


class Source:
    """Public data from GitHub, crates.io and PyPI.

    `snapshot` (a dict url -> JSON, or a file name) answers instead of the network, so the
    tool runs offline in tests and in localci. `record` collects every answer for --dump-data.
    """

    def __init__(self, snapshot: dict | None = None, token: str | None = None):
        self.snapshot = snapshot
        self.token = token
        self.record: dict[str, object] = {}

    def get(self, url: str):
        if url in self.record:   # one request per URL per run
            return self.record[url]
        if self.snapshot is not None:
            if url not in self.snapshot:
                raise FactError(f"no snapshot data for {url}")
            data = self.snapshot[url]
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "docs-facts (dsd-toolbox)",
                                                       "Accept": "application/json"})
            if self.token and url.startswith("https://api.github.com/"):
                req.add_header("Authorization", f"Bearer {self.token}")
            try:
                with _OPENER.open(req, timeout=30) as r:
                    data = json.load(r)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    data = {"__status__": 404}
                elif e.code in (403, 429):
                    raise FactError(f"{url}: HTTP {e.code} (rate limited? set GITHUB_TOKEN)") from e
                else:
                    raise FactError(f"{url}: HTTP {e.code}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                raise FactError(f"{url}: {e}") from e
        self.record[url] = data
        return data

    # -- GitHub
    def repo(self, repo: str) -> dict:
        d = self.get(f"https://api.github.com/repos/{repo}")
        if d.get("__status__") == 404:
            raise FactError(f"repository {repo} not found")
        return d

    def github_release(self, repo: str, tag: str = "latest") -> dict | None:
        canon = self.repo(repo)["full_name"]
        path = "latest" if tag == "latest" else f"tags/{tag}"
        d = self.get(f"https://api.github.com/repos/{canon}/releases/{path}")
        if d.get("__status__") == 404:
            return None
        return {
            "repo": canon,
            "tag": d["tag_name"],
            "version": d["tag_name"].lstrip("v"),
            "date": d["published_at"][:10],
            "url": d["html_url"],
            "assets": [{"name": a["name"], "size": a["size"]} for a in d.get("assets", [])],
        }

    # -- registries
    def crates_release(self, name: str) -> dict | None:
        d = self.get(f"https://crates.io/api/v1/crates/{name}")
        if d.get("__status__") == 404:
            return None
        ver = d["crate"]["max_stable_version"] or d["crate"]["newest_version"]
        created = next((v["created_at"] for v in d["versions"] if v["num"] == ver), "")
        return {"repo": name, "tag": ver, "version": ver, "date": created[:10],
                "url": f"https://crates.io/crates/{name}/{ver}", "assets": []}

    def pypi_release(self, name: str) -> dict | None:
        d = self.get(f"https://pypi.org/pypi/{name}/json")
        if d.get("__status__") == 404:
            return None
        ver = d["info"]["version"]
        files = d["releases"].get(ver) or d.get("urls") or []
        date = files[0]["upload_time"][:10] if files else ""
        return {"repo": name, "tag": ver, "version": ver, "date": date,
                "url": f"https://pypi.org/project/{name}/{ver}/",
                "assets": [{"name": f["filename"], "size": f["size"]} for f in files]}

    def release(self, a: dict) -> dict | None:
        src = a.get("source", "github")
        if src == "github":
            return self.github_release(need(a, "repo"), a.get("tag", "latest"))
        if src == "crates":
            return self.crates_release(need(a, "name"))
        if src == "pypi":
            return self.pypi_release(need(a, "name"))
        raise FactError(f"unknown source {src!r} (github, crates, pypi)")


# --------------------------------------------------------------------------- helpers


def need(a: dict, key: str) -> str:
    if key not in a:
        raise FactError(f"missing argument {key}=")
    return a[key]


def parse_args(text: str) -> dict:
    out = {}
    try:
        parts = shlex.split(text.strip())
    except ValueError as e:
        raise FactError(f"cannot parse arguments {text.strip()!r}: {e}") from e
    for t in parts:
        if "=" not in t:
            raise FactError(f"argument {t!r} is not key=value")
        k, v = t.split("=", 1)
        out[k] = v
    return out


def unescape(s: str) -> str:
    return s.replace("\\n", "\n").replace("\\t", "\t")


def platform_of(name: str) -> str:
    """A short platform label guessed from an asset file name (for {platform})."""
    n = name.lower()
    os_ = next((label for key, label in (
        ("linux", "Linux"), ("macos", "macOS"), ("darwin", "macOS"), ("apple", "macOS"),
        ("windows", "Windows"), ("win64", "Windows"), ("win32", "Windows"), (".msi", "Windows"),
        (".exe", "Windows"), (".rpm", "Linux"), (".deb", "Linux"), (".apk", "Linux")) if key in n), "")
    arch = next((label for key, label in (
        ("x86_64", "x86-64"), ("amd64", "x86-64"), ("x64", "x86-64"), ("aarch64", "aarch64"),
        ("arm64", "aarch64"), ("i686", "i686"), ("i386", "i686"), ("armv7", "armv7")) if key in n), "")
    return " ".join(p for p in (os_, arch) if p) or "any"


# --------------------------------------------------------------------------- evaluators


def f_release(a: dict, ctx: "Ctx") -> str:
    rel = ctx.src.release(a)
    if rel is None:
        if "empty" in a:
            return unescape(a["empty"])
        raise FactError("no release found (add empty=TEXT to allow that)")
    fmt = unescape(a.get("fmt", "{version} ({date})"))
    return fmt.format(**{k: v for k, v in rel.items() if k != "assets"})


def f_latest_date(a: dict, ctx: "Ctx") -> str:
    dates = []
    for spec in need(a, "repos").split(","):
        rel = ctx.src.release({"repo": spec})
        if rel:
            dates.append(rel["date"])
    if not dates:
        raise FactError("none of the repositories has a release")
    return max(dates)


def f_assets(a: dict, ctx: "Ctx") -> str:
    rel = ctx.src.release(a)
    if rel is None:
        raise FactError("no release found")
    pat = re.compile(a.get("match", "."))
    skip = re.compile(a["exclude"]) if "exclude" in a else None
    fmt = unescape(a.get("fmt", "- `{name}`"))
    lines = []
    for x in sorted(rel["assets"], key=lambda x: x["name"]):
        if not pat.search(x["name"]) or (skip and skip.search(x["name"])):
            continue
        lines.append(fmt.format(name=x["name"], size_mb=f"{x['size'] / 1e6:.1f}",
                                platform=platform_of(x["name"]), tag=rel["tag"], version=rel["version"]))
    if "unique" in a:  # collapse repeated lines (for example one row per platform)
        lines = list(dict.fromkeys(lines))
    if not lines:
        raise FactError("no release asset matches")
    return "\n".join(lines)


def _workflow_matrix(path: Path, job: str) -> dict[str, list[str]]:
    """The strategy.matrix lists of one job, read without a YAML library.

    Handles `key: [a, b]`, `key:` followed by `- item` lines, and `include:` entries as
    `- k: v` maps (their values are collected under the key `include.k`). Enough for the
    matrices this project writes; anything else raises FactError rather than guessing.
    """
    lines = path.read_text().splitlines()
    jobs_i = next((i for i, l in enumerate(lines) if re.match(r"^jobs:\s*$", l)), None)
    if jobs_i is None:
        raise FactError(f"{path}: no jobs: section")
    start = next((i for i in range(jobs_i + 1, len(lines)) if re.match(rf"^  {re.escape(job)}:\s*$", lines[i])), None)
    if start is None:
        raise FactError(f"{path}: no job {job!r}")
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"^  \S", lines[i])), len(lines))
    body = lines[start + 1:end]
    m_i = next((i for i, l in enumerate(body) if re.match(r"^      matrix:\s*$", l)), None)
    if m_i is None:
        raise FactError(f"{path}: job {job!r} has no strategy.matrix block")
    out: dict[str, list[str]] = {}
    key = None
    for l in body[m_i + 1:]:
        if l.strip() == "" or l.lstrip().startswith("#"):
            continue
        ind = len(l) - len(l.lstrip())
        if ind <= 6:
            break
        text = re.sub(r"\s+#.*$", "", l.strip())
        if ind == 8 and not text.startswith("-"):
            k, _, v = text.partition(":")
            key = k.strip()
            v = v.strip()
            if v.startswith("["):
                out[key] = [x.strip().strip("'\"") for x in v.strip("[]").split(",") if x.strip()]
            elif v == "":
                out[key] = []
            else:
                out[key] = [v.strip("'\"")]
        elif text.startswith("- ") and key and key != "include" and key != "exclude":
            out[key].append(text[2:].strip().strip("'\""))
        elif key in ("include", "exclude"):
            t = text[2:] if text.startswith("- ") else text
            k, _, v = t.partition(":")
            out.setdefault(f"{key}.{k.strip()}", []).append(v.strip().strip("'\""))
        else:
            raise FactError(f"{path}: cannot read matrix line {l.strip()!r}")
    return out


def f_ci_matrix(a: dict, ctx: "Ctx") -> str:
    m = _workflow_matrix(ctx.root / need(a, "file"), need(a, "job"))
    key = need(a, "key")
    if key not in m:
        raise FactError(f"matrix has no {key!r} (has: {', '.join(m) or 'nothing'})")
    fmt = unescape(a.get("fmt", "`{v}`"))
    sep = unescape(a.get("sep", ", "))
    return sep.join(fmt.format(v=v) for v in m[key])


def f_msrv(a: dict, ctx: "Ctx") -> str:
    d = tomllib.loads((ctx.root / a.get("file", "Cargo.toml")).read_text())
    v = d.get("package", {}).get("rust-version") or d.get("workspace", {}).get("package", {}).get("rust-version")
    if not v:
        raise FactError("no rust-version in the manifest")
    return unescape(a.get("fmt", "{v}")).format(v=v)


def f_python_min(a: dict, ctx: "Ctx") -> str:
    d = tomllib.loads((ctx.root / a.get("file", "pyproject.toml")).read_text())
    spec = d.get("project", {}).get("requires-python", "")
    m = re.search(r">=\s*(\d+\.\d+)", spec)
    if not m:
        raise FactError(f"requires-python {spec!r} has no >= minimum")
    return unescape(a.get("fmt", "{v}")).format(v=m.group(1), spec=spec)


def f_install(a: dict, ctx: "Ctx") -> str:
    """One install line with the canonical owner and repository, and the released tag."""
    kind = need(a, "kind")
    if kind in ("pip", "cargo"):
        name = need(a, "name")
        rel = ctx.src.release({"source": "pypi" if kind == "pip" else "crates", "name": name})
        if rel is None:
            raise FactError(f"{name} is not published")
        pin = f"=={rel['version']}" if kind == "pip" else f"@{rel['version']}"
        if "pin" not in a:
            pin = ""
        return f"{'pip install' if kind == 'pip' else 'cargo install'} {name}{pin}"
    rel = ctx.src.release({"repo": need(a, "repo")})
    if rel is None:
        raise FactError("no release found")
    if kind == "pipx-git":
        ref = f"@{rel['tag']}" if a.get("ref", "tag") == "tag" else ""
        return f"pipx install git+https://github.com/{rel['repo']}{ref}"
    if kind == "download":
        hits = [x["name"] for x in rel["assets"] if re.search(need(a, "asset"), x["name"])]
        if len(hits) != 1:
            raise FactError(f"asset= matches {len(hits)} files, need exactly 1: {hits[:5]}")
        return f"curl -LO https://github.com/{rel['repo']}/releases/download/{rel['tag']}/{hits[0]}"
    raise FactError(f"unknown install kind {kind!r} (pip, cargo, pipx-git, download)")


EVALUATORS = {
    "release": f_release, "latest-date": f_latest_date, "assets": f_assets,
    "ci-matrix": f_ci_matrix, "msrv": f_msrv, "python-min": f_python_min, "install": f_install,
}


class Ctx:
    def __init__(self, root: Path, src: Source):
        self.root, self.src = root, src
        self.dry = False


# --------------------------------------------------------------------------- regions


def evaluate(key: str, argtext: str, ctx: Ctx) -> str:
    if key not in EVALUATORS:
        raise FactError(f"unknown fact {key!r} (known: {', '.join(sorted(EVALUATORS))})")
    return EVALUATORS[key](parse_args(argtext), ctx)


EXAMPLE_FENCE_RE = re.compile(r"^(`{3,}|~{3,})[ \t]*(?:text|md|markdown)[ \t]*\n.*?^\1[ \t]*$", re.S | re.M)


def process(text: str, ctx: Ctx, name: str, errors: list[str]) -> tuple[str, int]:
    """Return the text with every region regenerated, and the number of regions.

    Fences tagged text, md or markdown hold examples of the markers, not regions: they are skipped.
    """
    count = 0
    examples = [m.span() for m in EXAMPLE_FENCE_RE.finditer(text)]

    def in_example(pos: int) -> bool:
        return any(a <= pos < b for a, b in examples)

    def lineno(pos: int) -> int:
        return text.count("\n", 0, pos) + 1

    def html(m: re.Match) -> str:
        nonlocal count
        if in_example(m.start()):
            return m.group(0)
        count += 1
        if ctx.dry:
            return m.group(0)
        key, argtext, body = m.group(1), m.group(2), m.group(3)
        try:
            out = evaluate(key, argtext, ctx)
        except (FactError, KeyError, IndexError, ValueError) as e:
            errors.append(f"{name}:{lineno(m.start())}: facts:{key}: {e}")
            return m.group(0)
        if body.startswith("\n") and body.endswith("\n"):
            out = "\n" + out + "\n"
        head = m.group(0)[: m.start(3) - m.start(0)]
        return f"{head}{out}<!-- /facts -->"

    def shell(m: re.Match) -> str:
        nonlocal count
        if in_example(m.start()):
            return m.group(0)
        count += 1
        if ctx.dry:
            return m.group(0)
        indent, key, argtext = m.group(1), m.group(2), m.group(3)
        try:
            out = evaluate(key, argtext, ctx)
        except (FactError, KeyError, IndexError, ValueError) as e:
            errors.append(f"{name}:{lineno(m.start())}: facts:{key}: {e}")
            return m.group(0)
        body = "".join(f"{indent}{l}\n" for l in out.split("\n"))
        return f"{indent}# facts:{key}{argtext}\n{body}{indent}# /facts"

    new = HTML_RE.sub(html, text)
    examples[:] = [m.span() for m in EXAMPLE_FENCE_RE.finditer(new)]   # offsets moved if a region changed size
    new = SHELL_RE.sub(shell, new)
    return new, count


def iter_files(root: Path, files: list[str]) -> list[Path]:
    if files:
        return [Path(f) if Path(f).is_absolute() else root / f for f in files]
    out = []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS)
        out += [Path(dp) / f for f in sorted(fn) if f.endswith(".md")]
    return out


def run(mode: str, root: Path, files: list[str], src: Source, out=sys.stdout) -> int:
    ctx = Ctx(root, src)
    ctx.dry = mode == "list"   # count regions without evaluating them
    errors: list[str] = []
    stale = 0
    total = 0
    for p in iter_files(root, files):
        text = p.read_text()
        if "facts:" not in text:
            continue
        rel = str(p.relative_to(root)) if p.is_relative_to(root) else str(p)
        new, n = process(text, ctx, rel, errors)
        total += n
        if mode == "list":
            print(f"{rel}: {n} region(s)", file=out)
        elif new != text:
            if mode == "generate":
                p.write_text(new)
                print(f"updated {rel}", file=out)
            else:
                stale += 1
                diff = difflib.unified_diff(text.splitlines(), new.splitlines(), f"{rel} (committed)",
                                            f"{rel} (from the sources)", lineterm="", n=0)
                print("\n".join(diff), file=out)
    for e in errors:
        print(f"ERROR {e}", file=sys.stderr)
    if mode == "check":
        print(f"docs-facts: {total} region(s), {stale} file(s) stale, {len(errors)} error(s)", file=out)
    elif mode == "generate":
        print(f"docs-facts: {total} region(s) generated, {len(errors)} error(s)", file=out)
    if errors:
        return 2
    return 1 if stale else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", choices=["check", "generate", "list"])
    ap.add_argument("files", nargs="*", help="Markdown files (default: every .md under --root)")
    ap.add_argument("--root", default=".", help="repository root (default: .)")
    ap.add_argument("--data", help="JSON snapshot answering every web request (offline mode)")
    ap.add_argument("--dump-data", help="write the web answers used to this JSON file")
    a = ap.parse_args(argv)
    snap = json.loads(Path(a.data).read_text()) if a.data else None
    src = Source(snap, os.environ.get("GITHUB_TOKEN"))
    try:
        rc = run(a.mode, Path(a.root).resolve(), a.files, src)
    finally:
        if a.dump_data:
            Path(a.dump_data).write_text(json.dumps(src.record, indent=1, sort_keys=True))
    return rc


if __name__ == "__main__":
    sys.exit(main())
