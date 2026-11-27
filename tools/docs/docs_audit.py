#!/usr/bin/env python3
"""docs-audit (T6): the standing docs audit, after a release and every month.

    python3 -I tools/docs/docs_audit.py --release [VERSION]    # the checklist: what to compare with the release
    python3 -I tools/docs/docs_audit.py --check [--no-external] [--out DIR]   # lint + links + facts; exit 1 on failure
    python3 -I tools/docs/docs_audit.py --sync-release-step docs/release.md  # put the shared release-step text in

--release lists every place the docs make a claim the release can falsify: version numbers other
than the new one, command-line options (compared with `help_command` output when .docs.toml gives
one), platform and architecture names, and links to tags and release pages. The list is the work;
nothing in it is wrong by itself.

--check runs docs_lint, docs_links (offline, then external unless --no-external) and, when
tools/docs/docs_facts.py exists, `docs_facts.py --check`. It prints a dated summary, writes it to
--out when given, and exits 1 on any failure. It never opens an issue or posts anything: the run
failing is the signal.
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docslib as dl  # noqa: E402

HERE = Path(__file__).resolve().parent
PLATFORMS = ["Linux", "Windows", "macOS", "aarch64", "arm64", "x86_64", "x64", "i686", "Intel", "Apple Silicon",
             "FreeBSD", "NAS", "Synology", "QNAP", "TrueNAS", "Docker", "Podman", "Raspberry Pi", "musl", "glibc",
             "Python 3", "Rust 1"]
HISTORY = {"CHANGELOG.md", "RELEASES.md", "DECISIONS.md"}


def latest_version(root: Path) -> str:
    out = dl.git(root, "describe", "--tags", "--abbrev=0", check=False).strip()
    return out.lstrip("v") if out else ""


def checklist(root: Path, cfg: dl.Config, version: str) -> str:
    history = HISTORY | set(cfg.section("audit").get("history", []))
    files = [f for f in dl.markdown_files(root) if f.name not in history and f.name not in dl.AGENT_FILES]
    out = [f"# Docs audit checklist for {cfg.name} {version or '(no tag found)'}", "",
           f"Generated {datetime.date.today().isoformat()}. Compare each item with the published release; tick it, fix it, or note why it is right.", ""]
    ver_re = re.compile(r"(?<![\w.])v?(\d+\.\d+\.\d+)(?![\w.]*\d)")
    out += ["## Versions", "", f"Mentions of a version other than {version or 'the new release'} (history belongs in CHANGELOG.md and RELEASES.md):", ""]
    n = 0
    for f in files:
        for ln in dl.scan(f.read_text(errors="replace")):
            if ln.kind == "comment":
                continue
            found = sorted({m[1] for m in ver_re.finditer(ln.text) if m[1] != version})
            if found:
                n += 1
                out.append(f"- [ ] `{dl.rel(root, f)}:{ln.no}`: {', '.join(found)}")
    out += ([] if n else ["- none"]) + [""]
    claims = re.compile(r"\b(latest|current release|newest|current version|since version)\b", re.I)
    out += ["## 'Latest' and 'current' claims", ""]
    n = 0
    for f in files:
        for ln in dl.scan(f.read_text(errors="replace")):
            if ln.kind == "prose" and claims.search(dl.blank_code_spans(ln.text)):
                n += 1
                out.append(f"- [ ] `{dl.rel(root, f)}:{ln.no}`")
    out += ([] if n else ["- none"]) + [""]
    helptext = ""
    hc = cfg.section("audit").get("help_command")
    if hc:
        r = subprocess.run(hc, shell=True, capture_output=True, text=True, cwd=root)
        helptext = r.stdout + r.stderr
    opts: dict[str, set[str]] = {}
    for f in files:
        for ln in dl.scan(f.read_text(errors="replace")):
            if ln.kind in ("fence", "prose"):
                src = ln.text if ln.kind == "fence" else " ".join(ln.text[a:b] for a, b in dl.code_spans(ln.text))
                for m in re.finditer(r"(?<![\w-])--[a-z][a-z0-9]*(?:-[a-z0-9]+)*", src):
                    opts.setdefault(m[0], set()).add(dl.rel(root, f))
    out += ["## Command-line options", "",
            "Options named in the docs" + (f", checked against `{hc}`:" if hc else " (set audit.help_command in .docs.toml to check them automatically):"), ""]
    for o in sorted(opts):
        flag = "" if not helptext else ("" if o in helptext else " **not in the help output**")
        out.append(f"- [ ] `{o}`{flag}: {', '.join(sorted(opts[o])[:4])}")
    out += ([] if opts else ["- none"]) + [""]
    out += ["## Platforms and architectures", "", "Pages that name a platform; compare with the release's assets and the CI matrix:", ""]
    for f in files:
        text = dl.prose_text(f.read_text(errors="replace"))
        hit = [p for p in PLATFORMS if re.search(rf"(?<![\w-]){re.escape(p)}(?![\w-])", text)]
        if hit:
            out.append(f"- [ ] `{dl.rel(root, f)}`: {', '.join(hit)}")
    out += [""]
    out += ["## Release and tag links", ""]
    n = 0
    for f in files:
        for ln in dl.scan(f.read_text(errors="replace")):
            if ln.kind != "comment" and re.search(r"/releases/|/tag/|/compare/v?\d", ln.text):
                n += 1
                out.append(f"- [ ] `{dl.rel(root, f)}:{ln.no}`")
    out += ([] if n else ["- none"]) + [""]
    out += ["## Then", "", "- [ ] `docs_audit.py --check` passes (it is what the docs-audit workflow runs)", ""]
    return "\n".join(out)


def run(args: list[str], root: Path) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-I", *args], cwd=root, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr).strip()


def check(root: Path, name: str | None, external: bool, outdir: Path | None) -> int:
    nm = ["--name", name] if name else []
    steps: list[tuple[str, int, str]] = []
    rc, text = run([str(HERE / "docs_lint.py"), str(root), *nm], root)
    steps.append(("docs-lint", rc, text))
    rc, text = run([str(HERE / "docs_links.py"), str(root), *nm, *(["--external"] if external else [])], root)
    steps.append(("docs-links" + (" (offline and external)" if external else " (offline)"), rc, text))
    facts = HERE / "docs_facts.py"
    if facts.exists():
        rc, text = run([str(facts), "check", "--root", str(root)], root)
        steps.append(("docs-facts --check", rc, text))
    else:
        steps.append(("docs-facts --check", 0, "docs_facts.py is not in this copy of the tools: not run"))
    date = datetime.date.today().isoformat()
    report = [f"# Docs audit {date}", ""]
    for label, rc, text in steps:
        report += [f"## {label}: {'ok' if rc == 0 else 'FAILED'}", "", "```text", text[-6000:], "```", ""]
    body = "\n".join(report)
    print(body)
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / f"docs-audit-{date}.md").write_text(body)
    bad = [label for label, rc, _ in steps if rc]
    print(f"docs-audit: {'FAILED: ' + ', '.join(bad) if bad else 'ok'}")
    return 1 if bad else 0


def sync_release_step(root: Path, target: str) -> int:
    block = (HERE / "release-step.md").read_text().strip() + "\n"
    p = root / target
    text = p.read_text() if p.exists() else f"# Release\n\nThe steps for a release.\n"
    pat = re.compile(r"<!-- docs-audit:begin -->\n.*?\n<!-- docs-audit:end -->\n", re.S)
    if pat.search(text):
        new = pat.sub(lambda m: block, text)
    else:
        m = re.search(r"^## See also\s*$", text, re.M)
        if m:
            new = text[:m.start()] + block + "\n" + text[m.start():]
        else:
            footer = dl.FOOTER
            i = text.rfind(footer)
            new = (text[:i].rstrip() + "\n\n" + block + "\n" + text[i:]) if i >= 0 else text.rstrip() + "\n\n" + block
    new = re.sub(r"\n{2,}(<!-- docs-audit:begin -->)", r"\n\n\1", new)
    new = re.sub(r"(<!-- docs-audit:end -->)\n{2,}", r"\1\n\n", new)
    if new != text:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(new)
        print(f"updated {target}")
    else:
        print(f"{target} is up to date")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--name")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--release", nargs="?", const="", metavar="VERSION")
    g.add_argument("--check", action="store_true")
    g.add_argument("--sync-release-step", metavar="FILE")
    ap.add_argument("--no-external", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    cfg = dl.load_config(root, args.name)
    if args.sync_release_step:
        return sync_release_step(root, args.sync_release_step)
    if args.check:
        return check(root, args.name, not args.no_external, args.out)
    version = (args.release or latest_version(root)).lstrip("v")
    text = checklist(root, cfg, version)
    print(text)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / f"docs-audit-checklist-{datetime.date.today().isoformat()}.md").write_text(text + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
