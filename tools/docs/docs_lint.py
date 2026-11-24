#!/usr/bin/env python3
"""docs-lint (T3): hold every Markdown file of a repository to the DSD Toolbox documentation standard.

    python3 -I tools/docs/docs_lint.py [ROOT] [--name NAME] [--json] [--list-rules]

Rules come from the owner's docs-style and README standards (see docs/documentation-standard.md):
page shape (breadcrumb, one H1, lead, heading depth, See also, footer, a docs index that lists
every page), README shape (sections, badge set and order, pitch, tested Quick start block),
repository files, CHANGELOG format, the release step, British spelling, terminology, no emoji,
text art, placeholders or untagged code blocks, ISO dates, cited sources linked, and two hard
failures: links to the old owner (aclater) for repositories that moved to dsd-toolbox, and
private details (private addresses, home folders, session links).

A rule is switched off for one place with a comment on the line above, and a reason:

    <!-- docs-lint: ignore terminology -- quoted from the vendor's page -->

Per-repository settings are in .docs.toml (see tools/docs/README.md). Exit status 1 on any finding.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docslib as dl  # noqa: E402

RULES = {
    "breadcrumb": "docs page: first line is the breadcrumb, with the right links and the page title",
    "h1": "exactly one # heading",
    "lead": "1-3 sentence lead under the H1",
    "heading-depth": "no heading deeper than ###",
    "heading-case": "headings in sentence case",
    "see-also": "docs page ends with a See also list of 2-5 links",
    "footer": "the toolbox footer line ends the page",
    "index-missing": "docs/README.md exists",
    "index-unlisted": "docs/README.md (or an index it links) lists every docs page",
    "index-group": "docs index groups: Install, Use, Reference, Internals, Project, Release",
    "readme-sections": "README sections, in the standard order",
    "readme-title": "README H1 is the project name",
    "readme-badges": "README badge set, order and URLs",
    "readme-pitch": "README pitch of at most two sentences",
    "readme-quickstart": "README Quick start has a command block (or links, for an overview)",
    "readme-docs": "README Documentation is a link list into docs/",
    "readme-licence": "README Licence and credits section",
    "required-file": "the standard repository files exist",
    "changelog-format": "CHANGELOG follows Keep a Changelog",
    "release-step": "a release document carries the post-release docs audit block",
    "spelling": "British spelling in prose",
    "terminology": "terminology list (SACD, DSF, DFF, ISO, kHz, byte-identical ...)",
    "emoji": "no emoji",
    "text-art": "no ASCII or box-drawing diagrams",
    "placeholder": "no $VARIABLES or <placeholders> in shell blocks",
    "fence-lang": "every code block has a language tag",
    "date-format": "dates as YYYY-MM-DD",
    "cited-source": "Archimago, ASR, Stereophile, RMAA are linked where cited",
    "own-repo-link": "docs link to their own repository with relative links",
    "old-owner": "no links to github.com/aclater/<repo> for moved repositories",
    "private-info": "no private addresses, home folders, session links or private names",
    "suppression": "an ignore comment names a rule and gives a reason",
}

SENTENCE_END = re.compile(r"[.!?](?=\s+[A-Z`\[(\"“*]|\s*$)")
ABBREV = re.compile(r"\b(e\.g|i\.e|etc|vs|approx|cf|incl|no)\.", re.I)
SMALL = {"a", "an", "the", "of", "on", "in", "to", "and", "or", "for", "with", "from", "by", "at", "as", "is",
         "vs", "via", "per", "you", "your", "it", "its", "not", "no", "do", "does", "are", "be", "that", "this",
         "when", "how", "what", "why", "which", "if", "can", "my", "our", "into", "over", "up", "off", "out"}
PROPER = set("""Linux Windows Python Rust Docker Podman Fedora Debian Ubuntu RHEL Red Hat Synology QNAP ASUSTOR TerraMaster
UGREEN Plex Roon Jellyfin Kodi Sonos Volumio Apple Silicon Intel Homebrew Flatpak Snap Nix Arch Alpine GitHub Forgejo
MusicBrainz Discogs Beets Mac Archimago Stereophile FFmpeg VLC Android Gatekeeper Xcode Cargo Clippy Rustup Unix POSIX
Wayland Copr Samba Raspberry Pi Armbian OpenWrt Ubiquiti Atom Zen Ryzen Core Xeon Apple Homebrew Chocolatey Scoop
Winget PyPI Codecov CodeQL Scorecard OpenSSF Dependabot Fuse FUSE Keep Changelog Semantic Versioning Beets Harmony Python
Rocky Alma AlmaLinux CentOS SUSE openSUSE Gentoo Void Android Pixel Dolby Sony Philips Marantz Denon Oppo Pioneer
Quick Tidal Qobuz Spotify Bluetooth Wi-Fi WiFi Thunderbolt Ethernet Gigabit Brew Nginx Caddy Traefik Kubernetes Helm
TrueNAS Unraid OpenMediaVault Proxmox Hummingbird UBI""".split())
SHELL_LANGS = {"sh", "shell", "bash", "zsh", "console", "fish"}
PS_LANGS = {"powershell", "ps1", "pwsh", "cmd", "bat"}
INDEX_GROUPS = ["Install", "Use", "Reference", "Internals", "Project", "Release", "See also"]
CHANGELOG_KINDS = {"Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"}
BADGE_ORDER = ["ci", "coverage", "codeql", "scorecard", "version", "docsrs", "msrv", "licence"]
CITED = [
    ("Archimago", r"\bArchimago\b", "archimago.blogspot.com", "https://archimago.blogspot.com/"),
    ("Audio Science Review", r"\bAudio Science Review\b|\bASR\b", "audiosciencereview.com", "https://www.audiosciencereview.com/"),
    ("Stereophile", r"\bStereophile\b", "stereophile.com", "https://www.stereophile.com/content/measurements-maps-precision"),
    ("RMAA", r"\bRMAA\b|\bRightMark\b", "audio.rightmark.org", "http://audio.rightmark.org/"),
]

# American spelling -> British. Only words that are always wrong in British prose (no verb/noun
# split such as licence/license, no unit names such as "meter").
_Z_STEMS = ("normali organi optimi recogni initiali seriali synchroni utili minimi maximi customi summari authori "
            "finali prioriti emphasi categori standardi visuali characteri generali reali capitali materiali "
            "parameteri memori digiti notari").split()
SPELLING: list[tuple[re.Pattern[str], str]] = []


def _sp(pattern: str, british: str) -> None:
    SPELLING.append((re.compile(rf"(?<![\w./_`-])({pattern})(?![\w_-])", re.I), british))


for _stem in _Z_STEMS:
    _sp(rf"{_stem}z(?:e|es|ed|ing|ation|ations|er|ers)", "-ise, -isation")
_sp(r"analy(?:ze|zes|zed|zing|zer|zers)", "analyse")
_sp(r"behavior(?:s|al)?", "behaviour")
_sp(r"colors?|colored|coloring|colorful", "colour")
_sp(r"favorites?", "favourite")
_sp(r"honor(?:s|ed|ing)?", "honour")
_sp(r"neighbors?|neighboring", "neighbour")
_sp(r"centers?|centered|centering", "centre")
_sp(r"catalogs?|cataloged|cataloging", "catalogue")
_sp(r"analogs?", "analogue")
_sp(r"gray", "grey")
_sp(r"defense|offense", "defence, offence")
_sp(r"fulfill(?:s|ed|ing)?", "fulfil")
_sp(r"model(?:ed|ing)", "modelled, modelling")
_sp(r"label(?:ed|ing)", "labelled, labelling")
_sp(r"cancel(?:ed|ing)|cancelation", "cancelled, cancelling, cancellation")
_sp(r"travel(?:ed|ing|er)", "travelled, travelling")
_sp(r"signal(?:ed|ing)", "signalled, signalling")
_sp(r"tunnel(?:ed|ing)", "tunnelled, tunnelling")
_sp(r"acknowledgments?", "acknowledgement")
_sp(r"skeptic(?:s|al)?", "sceptic")
_sp(r"fibers?", "fibre")
_sp(r"aluminum|sulfur", "aluminium, sulphur")
_sp(r"theaters?|liters?|calibers?", "theatre, litre, calibre")
_sp(r"maneuvers?", "manoeuvre")
_sp(r"notarized|notarizing|notarization", "notarised, notarising, notarisation")

_T = r"(?<![\w./_\u2010-\u2015-])"          # not part of a file name, option or identifier
_E = r"(?![\w_/\u2010-\u2015-]|\.\w)"        # ...and not followed by one (a full stop that ends a sentence is fine)
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
TERMS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(_T + r"([Ss]acd)" + _E), "SACD"),
    (re.compile(r"\bDSD[ -](?:64|128|256|512|1024|2048)\b"), "DSD64, DSD128, DSD256, DSD512, DSD1024 (no space or hyphen)"),
    (re.compile(_T + r"(Dsd|dsd)" + _E), "DSD"),
    (re.compile(_T + r"([Dd]sf)" + _E), "DSF"),
    (re.compile(_T + r"([Dd]ff)" + _E), "DFF"),
    (re.compile(_T + r"(DSDiff|Dsdiff|dsdiff|DSDIff)" + _E), "DSDIFF"),
    (re.compile(_T + r"([Ii]so)" + _E), "ISO (and SACD image)"),
    (re.compile(_T + r"(Flac|flac)" + _E), "FLAC"),
    (re.compile(_T + r"(Wav|wav)" + _E), "WAV"),
    (re.compile(_T + r"(Pcm|pcm)" + _E), "PCM"),
    (re.compile(_T + r"(Dst|dst)" + _E), "DST"),
    (re.compile(r"(?<=\d)\s?(KHz|Khz|khz|KHZ|kHZ)\b"), "kHz"),
    (re.compile(r"\bSACD ISOs?\b"), "SACD image"),
    (re.compile(r"\b[Bb]yte identical\b|\b[Bb]it[- ]identical\b|\b[Bb]yteidentical\b"), "byte-identical"),
    (re.compile(r"\b[Rr]ealtime\b|\b\d+(?:\.\d+)?\s?[x×]\s?RT\b|×RT\b|\bxRT\b"), "real time (and \"× real time\")"),
    (re.compile(r"\b[Mm]ulti[- ]channel\b"), "multichannel"),
    (re.compile(r"\bMac OS X?\b|\bMacOS\b|\bOSX\b|\bOS X\b"), "macOS"),
    (re.compile(r"\bGithub\b"), "GitHub"),
    (re.compile(_T + r"(linux)" + _E), "Linux"),
]
DATE_PATTERNS = [
    (re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"), "dates are YYYY-MM-DD"),
    (re.compile(rf"\b(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b"), "dates are YYYY-MM-DD"),
    (re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\s+\d{{4}}\b"), "dates are YYYY-MM-DD"),
]
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-⛿✅❌✨❗❤⭐⭕️]")
BOX_RE = re.compile("[─-╿]|\\+[-=]{3,}\\+")
PRIVATE_RES = [
    (re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"),
     "private IP address"),
    (re.compile(r"(?<![\w.])/home/(?!user\b|you\b|example\b|me\b|username\b|runner\b)[a-z][\w-]*"), "home folder of a real account"),
    (re.compile(r"/Users/(?!user\b|you\b|example\b|me\b|username\b|runner\b|Shared\b)[A-Za-z][\w-]*"), "home folder of a real account"),
    (re.compile(r"\.home\.arpa\b"), "private host name"),
    (re.compile(r"claude\.ai/(?:code|chat|share)/|Claude-Session|claude-session", re.I), "session link"),
]
PLACEHOLDER_SH = re.compile(r"\$\(|\$\{|\$[A-Za-z_]\w*")
PLACEHOLDER_ANGLE = re.compile(r"(?<![<\w])<[A-Za-z][\w-]*>")
SUPPRESS_RE = re.compile(r"<!--\s*docs-lint:\s*(ignore|ignore-file)\s+([\w,\s*-]+?)\s*(?:--\s*(.*?))?\s*-->")


class File:
    def __init__(self, cfg: dl.Config, path: Path):
        self.cfg, self.path = cfg, path
        self.rel = dl.rel(cfg.root, path)
        self.text = path.read_text(errors="replace")
        self.lines = dl.scan(self.text)
        self.heads = dl.headings(self.lines)
        self.findings: list[dl.Finding] = []
        self.suppressed: dict[int, set[str]] = {}
        self.file_rules: set[str] = set()
        self._parse_suppressions()

    def _parse_suppressions(self) -> None:
        by_no = {ln.no: ln for ln in self.lines}
        for ln in self.lines:
            if ln.kind != "comment":
                continue
            m = SUPPRESS_RE.search(ln.text)
            if not m:
                continue
            rules = {r.strip() for r in re.split(r"[,\s]+", m[2]) if r.strip()}
            if not m[3] or len(m[3].strip()) < 4:
                self.findings.append(dl.Finding(self.rel, ln.no, "suppression", "an ignore comment needs a reason after --"))
                continue
            unknown = rules - set(RULES) - {"*"}
            if unknown:
                self.findings.append(dl.Finding(self.rel, ln.no, "suppression", f"unknown rule {', '.join(sorted(unknown))}"))
            if m[1] == "ignore-file":
                self.file_rules |= rules
                continue
            targets = {ln.no}
            nxt = ln.no + 1
            while nxt in by_no and not by_no[nxt].text.strip():
                nxt += 1
            if nxt in by_no:
                targets.add(nxt)
                if by_no[nxt].kind == "fence-open":
                    j = nxt + 1
                    while j in by_no and by_no[j].kind in ("fence",):
                        targets.add(j)
                        j += 1
                    if j in by_no:
                        targets.add(j)
            for t in targets:
                self.suppressed.setdefault(t, set()).update(rules)

    def add(self, rule: str, no: int, msg: str) -> None:
        rules = self.suppressed.get(no, set()) | self.file_rules
        if rule in rules or "*" in rules:
            return
        self.findings.append(dl.Finding(self.rel, no, rule, msg))

    @property
    def prose(self):
        return [ln for ln in self.lines if ln.kind == "prose"]

    def section(self, title: str, level: int = 2) -> tuple[int, list[dl.Line]] | None:
        """(heading line number, lines up to the next heading of the same or higher level)."""
        for i, h in enumerate(self.heads):
            if h.level == level and h.text == title:
                end = next((x.no for x in self.heads[i + 1:] if x.level <= level), 10 ** 9)
                return h.no, [ln for ln in self.lines if h.no < ln.no < end]
        return None


def sentences(paragraph: str) -> int:
    t = ABBREV.sub(lambda m: m[0].replace(".", ""), dl.prose_text(paragraph))
    t = re.sub(r"(?<=\d)\.(?=\d)", "", t)
    return max(len(SENTENCE_END.findall(t.strip())), 1 if t.strip() else 0)


def is_title_case(text: str, extra: set[str]) -> bool:
    t = dl.blank_code_spans(text)
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", t)
    rest = words[1:]
    sig = [w for w in rest if w.lower() not in SMALL and w not in PROPER and w not in extra
           and not w.isupper() and not any(c.isupper() for c in w[1:]) and len(w) > 1]
    return bool(sig) and all(w[0].isupper() for w in sig) and (len(sig) >= 2 or len(rest) <= 2)


# ---- rule groups ----------------------------------------------------------------------------

def hard_rules(f: File, private_res: list[re.Pattern[str]]) -> None:
    moved = "|".join(re.escape(r) for r in f.cfg.moved_repos)
    old = re.compile(rf"\baclater/({moved})(?![\w-])")
    for ln in f.lines:
        m = old.search(ln.text)
        if m:
            f.add("old-owner", ln.no, f"aclater/{m[1]} moved to {dl.ORG}/{m[1]}: update the link")
        for rx, what in PRIVATE_RES:
            if rx.search(ln.text):
                f.add("private-info", ln.no, f"{what} in public text")
        for rx in private_res:
            if rx.search(ln.text):
                f.add("private-info", ln.no, "matches the private name list")


def text_rules(f: File, allow: set[str]) -> None:
    for ln in f.lines:
        if ln.kind in ("fence", "fence-open", "fence-close"):
            continue
        if ln.kind == "comment":
            continue
        s = dl.prose_text(ln.text)
        if re.match(r"^\s{0,3}\[[^\]]+\]:", ln.text):
            continue
        for rx, british in SPELLING:
            for m in rx.finditer(s):
                if m[1].lower() in allow:
                    continue
                f.add("spelling", ln.no, f"'{m[1]}': British spelling ({british})")
        for rx, want in TERMS:
            for m in rx.finditer(s):
                grp = m[1] if m.groups() else m[0]
                if grp.lower() in allow:
                    continue
                f.add("terminology", ln.no, f"'{m[0].strip()}': write {want}")
        for rx, msg in DATE_PATTERNS:
            if rx.search(s):
                f.add("date-format", ln.no, msg)
    for ln in f.lines:
        if ln.kind == "comment":
            continue
        if EMOJI_RE.search(ln.text):
            f.add("emoji", ln.no, "emoji")
        text_block = ln.kind == "fence" and ln.lang in ("", "text", "txt", "ascii", "diagram")
        if BOX_RE.search(ln.text) and (ln.kind == "prose" or text_block):
            f.add("text-art", ln.no, "ASCII or box-drawing diagram (use Mermaid if a diagram truly helps)")
    for ln in f.lines:
        if ln.kind == "fence-open" and not ln.lang:
            f.add("fence-lang", ln.no, "code block without a language tag (sh, powershell, toml, text ...)")
        if ln.kind == "fence" and (ln.lang in SHELL_LANGS or ln.lang == ""):
            body = ln.text
            if ln.lang == "console":
                body = re.sub(r"^\s*[$#>]\s", "", body)
            if PLACEHOLDER_SH.search(body):
                f.add("placeholder", ln.no, "variable or $(...) in a shell block: write the literal value")
            if PLACEHOLDER_ANGLE.search(body):
                f.add("placeholder", ln.no, "<placeholder> in a shell block: write the literal value")
        if ln.kind == "fence" and ln.lang in PS_LANGS and PLACEHOLDER_ANGLE.search(ln.text):
            f.add("placeholder", ln.no, "<placeholder> in a command block: write the literal value")


def cited_rules(f: File) -> None:
    name = f.path.name.lower()
    if not (f.rel == "README.md" or "measure" in name or "quality" in name):
        return
    for label, mention, host, url in CITED:
        rx = re.compile(mention)
        first = next((ln.no for ln in f.prose if rx.search(dl.blank_code_spans(ln.text))), None)
        if first and host not in f.text:
            f.add("cited-source", first, f"{label} is cited but not linked (use {url})")


def own_link_rules(f: File) -> None:
    rx = re.compile(rf"https://github\.com/(?:{re.escape(f.cfg.org)}|aclater)/{re.escape(f.cfg.name)}/(?:blob|tree)/")
    for ln in f.prose:
        if rx.search(ln.text):
            f.add("own-repo-link", ln.no, "link to this repository with a relative path")


def first_prose(f: File, start: int = 0) -> dl.Line | None:
    return next((ln for ln in f.lines if ln.no > start and ln.kind == "prose" and ln.text.strip()), None)


def page_rules(f: File) -> None:
    cfg = f.cfg
    h1 = [h for h in f.heads if h.level == 1]
    if len(h1) != 1:
        f.add("h1", h1[1].no if len(h1) > 1 else 1, f"{len(h1)} H1 headings (need exactly one)")
    for h in f.heads:
        if h.level > 3:
            f.add("heading-depth", h.no, f"'{'#' * h.level} {h.text}' is deeper than ###")
        if h.level in (1, 2) and is_title_case(h.text, set(cfg.section("lint").get("proper_nouns", []))):
            f.add("heading-case", h.no, f"'{h.text}': sentence case")
    depth = f.rel.count("/") - 1                      # docs/x.md -> 0, docs/install/x.md -> 1
    up = "../" * (depth + 1)
    display = cfg.raw.get("display_name", cfg.name)
    first = next((ln for ln in f.lines if ln.kind == "prose" and ln.text.strip()
                  and not re.match(r"\s*<(img|picture|a |/a)", ln.text)), None)
    is_index = f.rel == "docs/README.md"
    title = h1[0].text if h1 else ""
    folder_index = f.rel.endswith("/README.md") and depth >= 1
    folder_title = f.rel.split("/")[-2].replace("-", " ").capitalize()
    if is_index:
        want = f"[{display}]({up}README.md) › Documentation"
    else:
        want = f"[{display}]({up}README.md) › [Documentation]({'../' * depth}README.md) › {title}"
    if not first:
        f.add("breadcrumb", 1, "empty page")
    else:
        got = first.text.strip()
        parts = [x.strip() for x in got.split("›")]
        ok = got == want
        if not ok and len(parts) >= 3 and not is_index:
            # extra middle crumbs are folder indexes (docs/install/x.md: ... › [Install](README.md) › Title);
            # a folder's own README may end in the folder name instead of its H1
            middle_ok = all(re.fullmatch(r"\[[^\]]+\]\((?:\.\./)*README\.md\)", m) for m in parts[2:-1])
            last_ok = parts[-1] == title or (folder_index and parts[-1] in (folder_title, title))
            ok = (parts[0] == f"[{display}]({up}README.md)" and parts[1] == f"[Documentation]({'../' * depth}README.md)"
                  and middle_ok and last_ok and len(parts) - 3 <= depth)
        if not ok:
            f.add("breadcrumb", first.no, f"first line should be: {want}")
    if h1:
        para: list[str] = []
        started = False
        nxt = [ln for ln in f.lines if ln.no > h1[0].no]
        for ln in nxt:
            if ln.kind == "comment" or (not started and not ln.text.strip()):
                continue
            if ln.kind != "prose" or re.match(r"\s*(#|[-*+]\s|\d+\.\s|\||>|<img|<picture|!\[)", ln.text) and not para:
                break
            if not ln.text.strip():
                break
            started = True
            para.append(ln.text)
        if not para:
            f.add("lead", h1[0].no, "no lead paragraph under the H1")
        elif sentences(" ".join(para)) > 3:
            f.add("lead", h1[0].no, f"lead has {sentences(' '.join(para))} sentences (1-3)")
    h2 = [h for h in f.heads if h.level == 2]
    if not h2 or h2[-1].text != "See also":
        f.add("see-also", h2[-1].no if h2 else len(f.lines), "the last ## section should be 'See also'")
    else:
        sec = f.section("See also")
        links = [ln for ln in (sec[1] if sec else []) if re.match(r"\s*[-*]\s", ln.text) and "](" in ln.text]
        if not 2 <= len(links) <= 5:
            f.add("see-also", h2[-1].no, f"See also has {len(links)} links (2-5)")
    if cfg.footer:
        last = next((ln for ln in reversed(f.lines) if ln.text.strip()), None)
        if not last or last.text.strip() != dl.FOOTER:
            f.add("footer", last.no if last else 1, f"last line should be: {dl.FOOTER}")


def index_rules(cfg: dl.Config, files: dict[str, File]) -> list[dl.Finding]:
    out: list[dl.Finding] = []
    docs = sorted(r for r in files if r.startswith("docs/"))
    pages = [r for r in docs if r != "docs/README.md"
             and not dl.matches(r, cfg.section("lint").get("index_exclude", []))]
    if not pages and "docs/README.md" not in files:
        return out
    idx = files.get("docs/README.md")
    if not idx:
        return [dl.Finding("docs/README.md", 1, "index-missing", "docs/README.md (the documentation index) does not exist")]
    reach: set[str] = set()
    queue = ["docs/README.md"]
    while queue:
        cur = queue.pop()
        f = files.get(cur)
        if not f:
            continue
        for ln in f.prose:
            for m in dl.INLINE_DEST_RE.finditer(dl.blank_code_spans(ln.text)):
                dest = m[3].split("#")[0]
                if not dest or re.match(r"[a-z]+:", dest):
                    continue
                target = os.path.normpath(os.path.join(os.path.dirname(cur), dest)).replace("\\", "/")
                if target.endswith("/") or target in files or target + "/README.md" in files:
                    t = target if target in files else target.rstrip("/") + "/README.md"
                    if t not in reach and t != cur:
                        reach.add(t)
                        if t.endswith("/README.md"):
                            queue.append(t)
    for r in pages:
        if r not in reach:
            out.append(dl.Finding(r, 1, "index-unlisted", "not linked from docs/README.md (or an index it links)"))
    seen_groups = []
    for h in idx.heads:
        if h.level == 2:
            if h.text not in INDEX_GROUPS:
                idx.add("index-group", h.no, f"'{h.text}' is not an index group ({', '.join(INDEX_GROUPS[:-1])})")
            else:
                seen_groups.append(h.text)
    order = [INDEX_GROUPS.index(g) for g in seen_groups]
    if order != sorted(order):
        idx.add("index-group", 1, f"groups out of order (expected {', '.join(INDEX_GROUPS)})")
    return out


def read_text_file(root: Path, name: str) -> str:
    p = root / name
    return p.read_text(errors="replace") if p.exists() else ""


def derive_spdx(root: Path) -> str | None:
    cargo = read_text_file(root, "Cargo.toml")
    m = re.search(r'^license\s*=\s*"([^"]+)"', cargo, re.M)
    if m:
        return m[1]
    py = read_text_file(root, "pyproject.toml")
    m = re.search(r'^license\s*=\s*(?:\{\s*(?:text|expression)\s*=\s*)?"([^"]+)"', py, re.M)
    return m[1] if m else None


def expected_badges(cfg: dl.Config) -> list[str]:
    conf = cfg.section("readme").get("badges")
    if conf is not None:
        return list(conf)
    root = cfg.root
    wf = root / ".github" / "workflows"
    has = lambda n: (wf / n).exists()          # noqa: E731
    out: list[str] = []
    if cfg.kind == "overview":
        return ["scorecard"] if has("scorecard.yml") else []
    if has("ci.yml"):
        out.append("ci")
    if wf.is_dir() and any("codecov" in p.read_text(errors="replace") for p in wf.glob("*.y*ml")):
        out.append("coverage")
    if has("codeql.yml"):
        out.append("codeql")
    if has("scorecard.yml"):
        out.append("scorecard")
    out.append("version")
    if cfg.kind == "library":
        out.append("docsrs")
    cargo, py = read_text_file(root, "Cargo.toml"), read_text_file(root, "pyproject.toml")
    if "rust-version" in cargo or "requires-python" in py:
        out.append("msrv")
    out.append("licence")
    return out


def classify_badge(line: str) -> tuple[str, str, str]:
    """(kind, alt, url) of a badge line."""
    m = re.search(r"!\[([^\]]*)\]\(([^)\s]+)", line)
    alt, url = (m[1], m[2]) if m else ("", "")
    if re.search(r"/actions/workflows/ci\.ya?ml/badge\.svg", url):
        k = "ci"
    elif "codecov.io" in url:
        k = "coverage"
    elif "workflows/codeql" in url:
        k = "codeql"
    elif "scorecard.dev" in url:
        k = "scorecard"
    elif re.search(r"img\.shields\.io/(crates/v|pypi/v|github/v/release)", url):
        k = "version"
    elif "docs.rs" in url:
        k = "docsrs"
    elif "img.shields.io/badge/" in url and re.match(r"(?i)licen[cs]e", alt) or re.search(r"img\.shields\.io/badge/licen[cs]e-", url, re.I):
        k = "licence"
    elif "img.shields.io/badge/" in url and re.search(r"(?i)\b(msrv|rust|python)\b", alt + url):
        k = "msrv"
    else:
        k = "unknown"
    return k, alt, url


def shields_text(url: str) -> str:
    m = re.search(r"img\.shields\.io/badge/[^-]+-(.+?)-[A-Za-z0-9]+(?:\?|$)", url)
    if not m:
        return ""
    t = m[1].replace("--", "\0").replace("__", "\1").replace("_", " ").replace("%20", " ")
    return t.replace("\0", "-").replace("\1", "_")


def readme_rules(f: File) -> None:
    cfg = f.cfg
    rc = cfg.section("readme")
    h1 = [h for h in f.heads if h.level == 1]
    title = rc.get("title", cfg.raw.get("display_name", cfg.name))
    if not h1:
        f.add("readme-title", 1, "no H1")
        return
    if h1[0].text != title:
        f.add("readme-title", h1[0].no, f"H1 is '{h1[0].text}', expected '{title}'")
    # sections
    if "sections" in rc:
        expected = list(rc["sections"])
    elif cfg.kind == "overview":
        expected = ["Projects", "Quick start", "Documentation", "Licence and credits"]
    else:
        expected = ["Platforms", "Quick start", "Documentation", "Licence and credits"]
    extra = set(rc.get("allow_extra", []))
    h2 = [h for h in f.heads if h.level == 2]
    actual = [h for h in h2 if h.text not in extra]
    names = [h.text for h in actual]
    for e in expected:
        if e not in names:
            f.add("readme-sections", 1, f"missing section '## {e}'")
    for h in actual:
        if h.text not in expected:
            f.add("readme-sections", h.no, f"unexpected section '## {h.text}' (standard: {', '.join(expected)})")
    present = [n for n in names if n in expected]
    if present != [e for e in expected if e in present]:
        f.add("readme-sections", 1, f"sections out of order (expected {', '.join(expected)})")
    for h in h2:
        if is_title_case(h.text, set(cfg.section("lint").get("proper_nouns", []))):
            f.add("heading-case", h.no, f"'{h.text}': sentence case")
    # badges and pitch
    badge_lines: list[dl.Line] = []
    intro: list[dl.Line] = []
    first_h2 = h2[0].no if h2 else 10 ** 9
    for ln in f.lines:
        if ln.no <= h1[0].no or ln.no >= first_h2 or ln.kind != "prose" or not ln.text.strip():
            continue
        if re.match(r"\s*\[?!\[", ln.text):
            badge_lines.append(ln)
        elif not re.match(r"\s*(>|<img|<picture|<a |</)", ln.text):
            intro.append(ln)
    kinds: list[str] = []
    for ln in badge_lines:
        if len(re.findall(r"!\[", ln.text)) > 1:
            f.add("readme-badges", ln.no, "one badge per line")
        k, alt, url = classify_badge(ln.text)
        if k == "unknown":
            f.add("readme-badges", ln.no, "badge not in the standard set (CI, Coverage, CodeQL, Scorecard, version, docs.rs, MSRV or Python, Licence)")
            continue
        kinds.append(k)
        if k == "ci" and f"branch={cfg.default_branch}" not in url:
            f.add("readme-badges", ln.no, f"CI badge should use ?branch={cfg.default_branch}")
        if k == "coverage" and f"/branch/{cfg.default_branch}/" not in url:
            f.add("readme-badges", ln.no, f"Coverage badge should use /branch/{cfg.default_branch}/")
        if k == "ci" and alt != "CI":
            f.add("readme-badges", ln.no, "CI badge alt text should be 'CI'")
        if k == "licence":
            if not alt.startswith("Licence: "):
                f.add("readme-badges", ln.no, "Licence badge alt text should be 'Licence: SPDX' (British spelling)")
            spdx = derive_spdx(cfg.root)
            shown = shields_text(url)
            if spdx and shown and re.sub(r"\s+", " ", shown).lower() != re.sub(r"\s+", " ", spdx).lower():
                f.add("readme-badges", ln.no, f"Licence badge shows '{shown}' but the manifest says '{spdx}'")
    want = expected_badges(cfg)
    for k in want:
        if k not in kinds:
            f.add("readme-badges", h1[0].no, f"missing {k} badge")
    for k in dict.fromkeys(kinds):
        if k not in want:
            f.add("readme-badges", h1[0].no, f"{k} badge does not apply to this repository (see readme-template.md)")
        if kinds.count(k) > 1:
            f.add("readme-badges", h1[0].no, f"two {k} badges")
    ordered = [k for k in kinds if k in BADGE_ORDER]
    if ordered != sorted(ordered, key=BADGE_ORDER.index):
        f.add("readme-badges", h1[0].no, f"badge order should be {', '.join(BADGE_ORDER)}")
    # pitch: all non-badge intro text before the first section
    text = " ".join(ln.text.strip() for ln in intro)
    pmax = rc.get("pitch_max", 2)
    if not intro:
        f.add("readme-pitch", h1[0].no, "no pitch between the badges and the first section")
    elif sentences(text) > pmax:
        f.add("readme-pitch", intro[0].no, f"pitch has {sentences(text)} sentences (the standard is {pmax}); move the rest into a section or docs/")
    # quick start
    qs = f.section("Quick start")
    if qs:
        body = qs[1]
        fences = [ln for ln in body if ln.kind == "fence-open" and ln.lang in SHELL_LANGS | PS_LANGS]
        links = [ln for ln in body if ln.kind == "prose" and "](" in ln.text]
        if cfg.kind in ("overview",):
            if not links:
                f.add("readme-quickstart", qs[0], "Quick start has no links")
        else:
            if not fences:
                f.add("readme-quickstart", qs[0], "Quick start has no tested command block (```sh or ```powershell)")
            if not links:
                f.add("readme-quickstart", qs[0], "Quick start has no link to more install options")
    docs = f.section("Documentation")
    if docs:
        items = [ln for ln in docs[1] if re.match(r"\s*[-*]\s", ln.text)]
        if len(items) < 2 or not all(re.match(r"\s*[-*]\s+\*{0,2}\[", ln.text) for ln in items):
            f.add("readme-docs", docs[0], "Documentation should be a bullet list of links")
        if not any("docs/" in ln.text for ln in items):
            f.add("readme-docs", docs[0], "Documentation links nothing under docs/")
    lic = f.section("Licence and credits")
    if lic and not any(ln.text.strip() for ln in lic[1] if ln.kind == "prose"):
        f.add("readme-licence", lic[0], "Licence and credits is empty")
    if cfg.footer:
        last = next((ln for ln in reversed(f.lines) if ln.text.strip()), None)
        if not last or last.text.strip() != dl.FOOTER:
            f.add("footer", last.no if last else 1, f"last line should be: {dl.FOOTER}")


def changelog_rules(f: File) -> None:
    ver_re = re.compile(r"^\[?v?(\d+)\.(\d+)\.(\d+)(?:[-+][\w.]+)?\]?\s*(?:[-–—(]\s*(\S+?)\)?\s*(?:\[YANKED\])?)?$")
    h2 = [h for h in f.heads if h.level == 2]
    if not h2 or h2[0].text.strip("[]").lower() != "unreleased":
        f.add("changelog-format", h2[0].no if h2 else 1, "the first ## section should be [Unreleased]")
    prev: tuple[int, int, int] | None = None
    prev_date = None
    for h in h2[1:] if h2 and h2[0].text.strip("[]").lower() == "unreleased" else h2:
        m = ver_re.match(h.text)
        if not m:
            f.add("changelog-format", h.no, f"'{h.text}': expected '## [x.y.z] - YYYY-MM-DD'")
            continue
        v = (int(m[1]), int(m[2]), int(m[3]))
        try:
            d = datetime.date.fromisoformat(m[4] or "")
        except ValueError:
            f.add("changelog-format", h.no, f"'{h.text}': date must be YYYY-MM-DD")
            d = None
        if prev and v >= prev:
            f.add("changelog-format", h.no, "versions must run newest first")
        if prev_date and d and d > prev_date:
            f.add("changelog-format", h.no, "dates must not increase down the file")
        prev, prev_date = v, d or prev_date
    for h in f.heads:
        if h.level == 3 and h.text not in CHANGELOG_KINDS:
            f.add("changelog-format", h.no, f"'### {h.text}': use Added, Changed, Deprecated, Removed, Fixed or Security")


def release_rules(cfg: dl.Config, files: dict[str, File]) -> list[dl.Finding]:
    block_file = Path(__file__).resolve().parent / "release-step.md"
    block = block_file.read_text().strip() if block_file.exists() else ""
    primary = cfg.section("lint").get("release_files") or [
        "docs/release.md", "docs/release-test-plan.md", "docs/test-plan.md", "RELEASING.md"]
    fallback = ["docs/development.md"]      # existing repos may keep release steps there (docs-style.md, clarification 6)
    present = [c for c in primary if (cfg.root / c).exists()] or [c for c in fallback if (cfg.root / c).exists()]
    if not present:
        return [dl.Finding("docs/release.md", 1, "release-step", "no release document found (docs/release.md, docs/release-test-plan.md, RELEASING.md ...)")]
    out = []
    for c in present:
        text = (cfg.root / c).read_text(errors="replace")
        m = re.search(r"<!-- docs-audit:begin -->\n(.*?)\n<!-- docs-audit:end -->", text, re.S)
        if not m:
            out.append(dl.Finding(c, 1, "release-step",
                                  "missing the post-release docs audit block (run: python3 tools/docs/docs_audit.py --sync-release-step " + c + ")"))
        elif block and m[0].strip() != block:
            out.append(dl.Finding(c, text[:m.start()].count("\n") + 1, "release-step", "the docs audit block differs from the shared text (run docs_audit.py --sync-release-step)"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--name", help="repository name (default: .docs.toml, else the folder name)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-rules", action="store_true")
    args = ap.parse_args(argv)
    if args.list_rules:
        for k, v in RULES.items():
            print(f"{k:18} {v}")
        return 0
    root = Path(args.root).resolve()
    cfg = dl.load_config(root, args.name)
    lc = cfg.section("lint")
    allow = {w.lower() for w in lc.get("allow_words", [])}
    private_res: list[re.Pattern[str]] = []
    pf = os.environ.get("DOCS_LINT_PRIVATE_FILE")
    if pf and Path(pf).is_file():
        for line in Path(pf).read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    private_res.append(re.compile(line, re.I))
                except re.error:
                    pass
    excl = lc.get("exclude", [])
    files: dict[str, File] = {}
    for p in dl.markdown_files(root):
        r = dl.rel(root, p)
        files[r] = File(cfg, p)
    findings: list[dl.Finding] = []
    for r, f in files.items():
        hard_rules(f, private_res)
        if dl.matches(r, excl) or f.path.name in dl.AGENT_FILES:
            findings += f.findings
            continue
        text_rules(f, allow)
        cited_rules(f)
        if r.startswith("docs/"):
            page_rules(f)
            own_link_rules(f)
        if r == "README.md":
            readme_rules(f)
        if r == "CHANGELOG.md":
            changelog_rules(f)
        findings += f.findings
    pages = {r: f for r, f in files.items() if not dl.matches(r, excl)}
    findings += index_rules(cfg, pages)
    for pat in lc.get("required_files", ["README.md", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md", "LICENSE*", "docs/README.md"]):
        pats = ["LICENSE*", "LICENCE*", "COPYING*"] if pat == "LICENSE*" else [pat]
        ok = any((root / q).exists() if "*" not in q else any(root.glob(q)) for q in pats)
        if not ok:
            findings.append(dl.Finding(pat, 1, "required-file", f"{pat} does not exist"))
    if lc.get("release_step", True):
        findings += release_rules(cfg, files)
    # later findings from index_rules/add() may have been suppressed in-file; index_rules adds
    # through File.add for groups, so merge those too
    for f in files.values():
        for x in f.findings:
            if x not in findings:
                findings.append(x)
    for ig in lc.get("ignore", []):
        findings = [x for x in findings if not (x.rule == ig["rule"] and dl.matches(x.path, [ig["path"]]))]
    return dl.report(findings, args.json, "docs-lint")


if __name__ == "__main__":
    sys.exit(main())
