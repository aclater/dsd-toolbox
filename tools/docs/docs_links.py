#!/usr/bin/env python3
"""docs-links (T4): check every link in every Markdown file of a repository.

    python3 -I tools/docs/docs_links.py                 # offline: relative links, anchors, own-repo URLs
    python3 -I tools/docs/docs_links.py --external      # also fetch every external URL

Offline mode checks that each relative link points at a file or folder that exists, that a
#fragment names a heading (or an id) in the target Markdown file, and that absolute links into
the repository itself (github.com/ORG/NAME/blob/BRANCH/..., raw.githubusercontent.com/...)
resolve to files in the working tree. External mode fetches each http(s) URL once, with retries,
a polite per-host delay and a User-Agent; URLs of bot-walled sites go in the allow list of
.docs.toml ([[links.allow]], each with a reason) or in tools/docs/links-allow.toml (shared) and
are reported as skipped, not fetched.

Exit status 1 on any broken link.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import re
import sys
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docslib as dl  # noqa: E402

SKIP_SCHEMES = ("mailto:", "tel:", "data:", "javascript:", "ssh:", "git:", "file:")
# Generated on request; the status of the image says nothing about the repository.
DEFAULT_EXCLUDE = [r"^https://img\.shields\.io/", r"^https?://localhost", r"^https?://127\.0\.0\.1",
                   r"^https?://example\.(com|org|net)"]
USER_AGENT = "dsd-toolbox-docs-links/1 (+https://github.com/dsd-toolbox/dsd-toolbox)"


def collect(path: Path, text: str):
    """Yield (line number, destination) for every link in a Markdown file, skipping code."""
    for ln in dl.scan(text):
        if ln.kind != "prose":
            continue
        s = dl.blank_code_spans(ln.text)
        seen: set[str] = set()
        for m in dl.INLINE_DEST_RE.finditer(s):
            seen.add(m[3])
            yield ln.no, m[3]
        m = dl.REFDEF_RE.match(s)
        if m:
            seen.add(m[2])
            yield ln.no, m[2]
        for m in dl.HTML_ATTR_RE.finditer(s):
            seen.add(m[1])
            yield ln.no, m[1]
        for m in dl.URL_RE.finditer(s):
            url = m[0].rstrip(".,;:!?")
            if not any(url in d for d in seen):
                yield ln.no, url


def own_repo_path(cfg: dl.Config, url: str) -> str | None:
    """The repo-relative path an absolute link into this repository names, else None."""
    owners = "|".join(re.escape(o) for o in {cfg.org, "aclater"})
    name = re.escape(cfg.name)
    m = re.match(rf"https://github\.com/(?:{owners})/{name}/(?:blob|tree)/([^/]+)/([^#?]*)", url)
    if not m:
        m = re.match(rf"https://raw\.githubusercontent\.com/(?:{owners})/{name}/([^/]+)/([^#?]*)", url)
    if m and m[1] in (cfg.default_branch, "main", "master"):
        return urllib.parse.unquote(m[2])
    return None


def check_offline(cfg: dl.Config, files: list[Path], externals: dict[str, list[tuple[str, int]]]) -> list[dl.Finding]:
    root = cfg.root.resolve()
    findings: list[dl.Finding] = []
    anchor_cache: dict[Path, set[str]] = {}

    def anchors(p: Path) -> set[str]:
        if p not in anchor_cache:
            anchor_cache[p] = dl.anchors_of(p.read_text(errors="replace"))
        return anchor_cache[p]

    for f in files:
        rp = dl.rel(root, f)
        for no, dest in collect(f, f.read_text(errors="replace")):
            dest = dest.strip()
            if not dest or dest.startswith(SKIP_SCHEMES):
                continue
            target: Path | None = None
            frag = ""
            if re.match(r"https?://", dest):
                own = own_repo_path(cfg, dest.split("#")[0])
                if own is None:
                    externals.setdefault(dest, []).append((rp, no))
                    continue
                target, frag = root / own, urllib.parse.urlsplit(dest).fragment
            elif dest.startswith("//"):
                externals.setdefault("https:" + dest, []).append((rp, no))
                continue
            else:
                parts = urllib.parse.urlsplit(dest)
                path, frag = urllib.parse.unquote(parts.path), parts.fragment
                if not path:
                    target = f
                elif path.startswith("/"):
                    target = root / path.lstrip("/")
                else:
                    target = f.parent / path
            try:
                resolved = target.resolve()
                resolved.relative_to(root)
            except (ValueError, OSError):
                findings.append(dl.Finding(rp, no, "link-outside", f"{dest} points outside the repository"))
                continue
            if not resolved.exists():
                findings.append(dl.Finding(rp, no, "link-missing", f"{dest} does not exist"))
                continue
            if frag and resolved.is_file() and resolved.suffix.lower() == ".md":
                if urllib.parse.unquote(frag).lower() not in anchors(resolved):
                    findings.append(dl.Finding(rp, no, "anchor-missing",
                                               f"{dest}: no heading or id #{frag} in {dl.rel(root, resolved)}"))
    return findings


def load_allow(cfg: dl.Config) -> list[tuple[str, str]]:
    allow: list[tuple[str, str]] = []
    shared = Path(__file__).resolve().parent / "links-allow.toml"
    sources = []
    if shared.exists():
        sources.append(tomllib.loads(shared.read_text()).get("allow", []))
    sources.append(cfg.section("links").get("allow", []))
    for entries in sources:
        for e in entries:
            allow.append((e["url"], e.get("reason", "")))
    return allow


class HostGate:
    """At most `per_host` requests at once per host, and a minimum delay between starts."""

    def __init__(self, per_host: int, delay: float):
        self.per_host, self.delay = per_host, delay
        self.lock = threading.Lock()
        self.sems: dict[str, threading.Semaphore] = {}
        self.last: dict[str, float] = {}

    def __call__(self, host: str):
        with self.lock:
            sem = self.sems.setdefault(host, threading.Semaphore(self.per_host))
        return _Gate(self, host, sem)


class _Gate:
    def __init__(self, gate: HostGate, host: str, sem: threading.Semaphore):
        self.gate, self.host, self.sem = gate, host, sem

    def __enter__(self):
        self.sem.acquire()
        with self.gate.lock:
            wait = self.gate.last.get(self.host, 0) + self.gate.delay - time.monotonic()
            self.gate.last[self.host] = time.monotonic() + max(wait, 0)
        if wait > 0:
            time.sleep(wait)

    def __exit__(self, *a):
        self.sem.release()


def fetch(url: str, gate: HostGate, retries: int, timeout: float) -> str | None:
    """None when the URL resolves, else a short reason."""
    host = urllib.parse.urlsplit(url).netloc
    reason = "no attempt"
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(min(2 ** attempt * 2, 30))
        req = urllib.request.Request(url.split("#")[0], headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
        try:
            with gate(host), urllib.request.urlopen(req, timeout=timeout) as r:
                r.read(1)
                return None
        except urllib.error.HTTPError as e:
            reason = f"HTTP {e.code}"
            if e.code == 429:
                try:
                    time.sleep(min(int(e.headers.get("Retry-After", "10")), 60))
                except ValueError:
                    pass
            elif e.code == 404 and host == "github.com" and attempt < 1:
                continue            # github.com answers 404 for pages that exist when it is under load; ask once more
            elif e.code < 500 and e.code != 408:
                return reason
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            reason = f"{type(e).__name__}: {getattr(e, 'reason', e)}"
    return reason


def check_external(cfg: dl.Config, externals: dict[str, list[tuple[str, int]]], args) -> tuple[list[dl.Finding], list[str]]:
    exclude = [re.compile(p) for p in DEFAULT_EXCLUDE + cfg.section("links").get("exclude", [])]
    allow = load_allow(cfg)
    skipped: list[str] = []
    todo: dict[str, list[tuple[str, int]]] = {}
    for url, where in externals.items():
        if any(x.search(url) for x in exclude):
            continue
        hit = next((a for a in allow if url.startswith(a[0])), None)
        if hit:
            skipped.append(f"{url} ({hit[1] or 'allow list'})")
            continue
        todo[url.split("#")[0]] = todo.get(url.split("#")[0], []) + where
    gate = HostGate(args.per_host, args.delay)
    findings: list[dl.Finding] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(fetch, u, gate, args.retries, args.timeout): u for u in todo}
        for fut in concurrent.futures.as_completed(futs):
            url = futs[fut]
            why = fut.result()
            if why:
                for path, no in todo[url][:3]:
                    findings.append(dl.Finding(path, no, "url-broken", f"{url}: {why}"))
    return findings, sorted(skipped)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".", help="repository root (default: .)")
    ap.add_argument("--name", help="repository name (default: .docs.toml name, else the folder name)")
    ap.add_argument("--external", action="store_true", help="also fetch external URLs")
    ap.add_argument("--external-only", action="store_true", help="skip the offline checks")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--per-host", type=int, default=2)
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests to one host")
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--timeout", type=float, default=25)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    cfg = dl.load_config(root, args.name)
    excl = cfg.section("links").get("exclude_files", [])
    files = [f for f in dl.markdown_files(root) if not dl.matches(dl.rel(root, f), excl)]
    externals: dict[str, list[tuple[str, int]]] = {}
    findings = check_offline(cfg, files, externals)
    if args.external_only:
        findings = []
    skipped: list[str] = []
    if args.external or args.external_only:
        more, skipped = check_external(cfg, externals, args)
        findings += more
    for s in skipped:
        print(f"skipped (allow list): {s}", file=sys.stderr)
    print(f"docs-links: {len(files)} file(s), {len(externals)} external URL(s)"
          + (" checked" if args.external or args.external_only else " (not fetched; use --external)"), file=sys.stderr)
    return dl.report(findings, args.json, "docs-links")


if __name__ == "__main__":
    sys.exit(main())
