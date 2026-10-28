# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Every text read for a cited work, kept across runs: what a reference check fetched, and what an agent read in a
browser that no script can fetch again (docs/cacheability.md).

    uv run --script source_cache.py save doi:10.1016/j.gim.2023.101058 EXCERPT.txt --scope excerpt --via browser \\
        --url https://www.gimjournal.org/article/... [--run RUN_ID]
    uv run --script source_cache.py seed RUN [RUN ...]      # index earlier runs' sources/ folders
    uv run --script source_cache.py show doi:10.1016/j.gim.2023.101058

The cache keeps texts, never verdicts: a reader always judges a claim afresh, from the fullest text anyone read.
support.py looks a work up here before it fetches, gives the reader every text held for it (the fullest first),
fetches only what is missing, writes what it fetched, and says in its report which texts it reused, from which
run and when. A run still keeps its own copy of each text in its sources/ folder, so the run stays self-contained
and a cleared cache loses nothing a run folder holds: `seed` rebuilds it from them.

It lives in the platform's cache folder (~/.cache/manuscript-skills on Linux, ~/Library/Caches on macOS,
%LOCALAPPDATA% on Windows), or where MANUSCRIPT_SKILLS_CACHE says: blobs/<sha256> (each text, written once) and
works.jsonl (one line per text read for a work: its keys, scope, how it was read, when, in which run). Everything
in it is public material or a text the authors' own agent read, so one store serves every project.

A work is keyed by its identifiers, `doi:` (lower case), `pmid:`, `pmcid:` (PMC…) and `arxiv:`; a text saved under
several finds the work by any of them. Scopes, fullest first: full_text, excerpt (a passage read in full text),
saved (a run's hand-named file), abstract.

Exit codes: 0 done; 1 nothing held (show) or nothing indexed (seed); 2 usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCOPES = {"full_text": 4, "supplied": 3, "excerpt": 3, "saved": 2, "abstract": 1}
TEXT_SUFFIXES = (".txt", ".md")
RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{8}")
PMCID = re.compile(r"PMC\d{4,9}", re.IGNORECASE)
ARXIV = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(?!\d)")
DOI = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+")
# What a hand-named copy adds to a file name: notes.full.txt, doi_….plain.txt, pmc_…_fulltext.xml.
NAME_TAILS = re.compile(r"(?:[._-](?:full|plain|html|xml|fulltext|abstract|text))+$", re.IGNORECASE)


def platform_cache_root() -> Path:
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        return Path(local) if local else Path.home() / "AppData" / "Local"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def root() -> Path:
    return Path(os.environ.get("MANUSCRIPT_SKILLS_CACHE") or platform_cache_root() / "manuscript-skills")


def work_key(kind: str, value: str) -> str:
    """One spelling per identifier: `doi:` lower case and without a resolver prefix, `pmcid:` upper case."""
    value = value.strip()
    if kind == "doi":
        value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value, flags=re.IGNORECASE).lower()
    elif kind == "pmcid":
        value = value.upper()
    return f"{kind}:{value}"


def parse_key(text: str) -> str | None:
    """A key as an author writes it: doi:10.x/..., https://doi.org/10.x/..., pmid:123, PMC123, arxiv:2403.19087."""
    text = text.strip()
    if m := re.match(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", text, re.IGNORECASE):
        return work_key("doi", m.group(1))
    if m := re.match(r"^pmid:\s*(\d{1,9})$", text, re.IGNORECASE):
        return work_key("pmid", m.group(1))
    if m := re.match(r"^(?:pmcid:\s*)?(PMC\d+)$", text, re.IGNORECASE):
        return work_key("pmcid", m.group(1))
    if m := re.match(r"^(?:arxiv:\s*|https?://arxiv\.org/(?:abs|html|pdf)/)(\d{4}\.\d{4,5})", text, re.IGNORECASE):
        return work_key("arxiv", m.group(1))
    return None


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def records(base: Path | None = None) -> list[dict[str, Any]]:
    path = (base or root()) / "works.jsonl"
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue  # a half-written line from an interrupted write: the rest stands
        if isinstance(item, dict) and item.get("blob"):
            out.append(item)
    return out


def lookup(keys: list[str], base: Path | None = None) -> list[dict[str, Any]]:
    """Every text held for a work known by any of KEYS, fullest first, one per distinct text."""
    wanted, seen, out = set(keys), set(), []
    held = [r for r in records(base) if wanted & {r.get("key"), *r.get("aliases", [])}]
    held.sort(key=lambda r: (SCOPES.get(r.get("scope", ""), 0), r.get("characters", 0), r.get("read_at", "")),
              reverse=True)
    for item in held:
        if item["blob"] not in seen and (blob_path(item, base)).is_file():
            seen.add(item["blob"])
            out.append(item)
    return out


def blob_path(item: dict[str, Any], base: Path | None = None) -> Path:
    return (base or root()) / "blobs" / item["blob"].removeprefix("sha256:")


def read(item: dict[str, Any], base: Path | None = None) -> str:
    return blob_path(item, base).read_text(encoding="utf-8")


def combined(held: list[dict[str, Any]], base: Path | None = None) -> str:
    """The texts held for a work, fullest first, each after a line that says what it is: a reader looks in all of
    them, and a quote found only in a browser excerpt is still found."""
    parts = []
    for n, item in enumerate(held):
        head = "" if n == 0 else (f"\n\n----- Another text read for this work: {item.get('scope')}, via "
                                  f"{item.get('via')}, {item.get('read_at', '')[:10]} -----\n\n")
        parts.append(head + read(item, base))
    return "".join(parts)


def store(keys: list[str], text: str, scope: str, via: str, url: str | None = None, run: str | None = None,
          read_at: str | None = None, base: Path | None = None) -> dict[str, Any] | None:
    """Keep TEXT for the work known by KEYS (the first is its key, the rest aliases). A text already held for the work
    is not stored twice; None then."""
    if not text.strip() or not keys:
        return None
    base = base or root()
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if any(r["blob"] == f"sha256:{sha}" for r in lookup(keys, base)):
        return None
    (base / "blobs").mkdir(parents=True, exist_ok=True)
    blob = base / "blobs" / sha
    if not blob.exists():
        blob.write_text(text, encoding="utf-8")
    item = {"kind": "source", "key": keys[0], "aliases": sorted(set(keys[1:]) - {keys[0]}), "scope": scope,
            "via": via, "url": url, "blob": f"sha256:{sha}", "characters": len(text), "read_at": read_at or now(),
            "run": run}
    with (base / "works.jsonl").open("a", encoding="utf-8") as out:
        out.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item


def file_stem(kind: str, value: str) -> str:
    """How support.py names a work's file (doi_10.1093_nar_gkac931), lower case for matching."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", f"{kind}_{value}").strip("_").lower()


def known_works(run: Path) -> dict[str, str]:
    """The DOIs a run recorded (its reference scans and claims files), by the file stem support.py would give each:
    a hand-named copy (doi_10.1093_nar_gkac931.txt) is matched to one of them, never reversed by guessing."""
    out: dict[str, str] = {}
    for path in [*run.rglob("*.json"), *run.rglob("*.yaml")]:
        if "sources" in path.relative_to(run).parts or path.stat().st_size > 5_000_000:
            continue
        for doi in DOI.findall(path.read_text(encoding="utf-8", errors="replace")):
            doi = doi.rstrip(".,;:)]}")
            for prefix in ("doi", "crossref", "datacite"):
                out.setdefault(file_stem(prefix, doi.lower()), work_key("doi", doi))
    return out


def run_id(path: Path) -> str | None:
    """The run a sources folder belongs to, from its path (…/reviews/<run id>/manuscript-reference-check/sources)."""
    return next((part for part in reversed(path.parts) if RUN_ID.fullmatch(part)), None)


def seed(run: Path, base: Path | None = None) -> tuple[int, list[str]]:
    """Index an earlier run's sources/ folders: a text support.py fetched, by the identifier its record names; a
    hand-named one, by a PMCID or an arXiv id in its name, or by a DOI the run recorded whose file name it carries.
    A text with none of these (a web page, a policy) is listed, not guessed: give it to `save` with its identifier."""
    indexed, skipped = 0, []
    known = known_works(run)
    for folder in sorted(p for p in run.rglob("sources") if p.is_dir()):
        named = {p.stem: p for p in folder.glob("*.json")}
        for text_path in sorted(p for p in folder.iterdir() if p.suffix.lower() in TEXT_SUFFIXES and p.is_file()):
            meta, key, scope, via = named.get(text_path.stem), None, "saved", "a file in an earlier run"
            if meta is not None:
                try:
                    info = json.loads(meta.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    info = {}
                key = parse_key(str(info.get("given") or ""))
                scope = info.get("scope") if info.get("scope") in SCOPES else "saved"
                via = info.get("via") or via
            if key is None:
                if m := PMCID.search(text_path.name):
                    key = work_key("pmcid", m.group(0))
                elif text_path.name.lower().startswith("arxiv") and (m := ARXIV.search(text_path.name)):
                    key = work_key("arxiv", m.group(1))
                else:
                    key = known.get(NAME_TAILS.sub("", text_path.stem).lower())
            if key is None:
                skipped.append(str(text_path))
                continue
            text = text_path.read_text(encoding="utf-8", errors="replace")
            read_at = datetime.fromtimestamp(text_path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
            if store([key], text, scope, via, run=run_id(text_path), read_at=read_at, base=base) is not None:
                indexed += 1
    return indexed, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="source_cache.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("save", help="keep a text read for a work (a browser read, a supplied file)")
    p.add_argument("work", help="doi:…, pmid:…, PMC…, arxiv:…; repeat the work's other identifiers with --alias")
    p.add_argument("file", type=Path)
    p.add_argument("--scope", choices=sorted(SCOPES), default="excerpt")
    p.add_argument("--via", default="browser", help="how it was read: browser, publisher PDF, the authors' copy")
    p.add_argument("--url", help="the page it was read on")
    p.add_argument("--alias", action="append", default=[], help="another identifier of the same work")
    p.add_argument("--run", help="the run it was read in")
    p = sub.add_parser("seed", help="index earlier runs' sources/ folders")
    p.add_argument("runs", nargs="+", type=Path)
    p = sub.add_parser("show", help="what is held for a work")
    p.add_argument("work")
    args = parser.parse_args(argv)
    if args.command == "save":
        keys = [parse_key(k) for k in [args.work, *args.alias]]
        if None in keys or not args.file.is_file():
            print("source_cache.py: give the work as doi:…, pmid:…, PMC… or arxiv:…, and a text file", file=sys.stderr)
            return 2
        item = store(keys, args.file.read_text(encoding="utf-8"), args.scope, args.via, args.url, args.run)
        print(json.dumps(item or {"stored": False, "why": "this text is already held for the work"}, indent=2))
        return 0
    if args.command == "seed":
        total, missed = 0, []
        for run in args.runs:
            indexed, skipped = seed(run)
            total, missed = total + indexed, missed + skipped
        print(json.dumps({"indexed": total, "cache": str(root()), "not_indexed": missed}, indent=2))
        return 0 if total else 1
    key = parse_key(args.work)
    if key is None:
        print("source_cache.py: give the work as doi:…, pmid:…, PMC… or arxiv:…", file=sys.stderr)
        return 2
    held = lookup([key])
    print(json.dumps([{k: v for k, v in item.items() if k != "kind"} for item in held], indent=2, ensure_ascii=False))
    return 0 if held else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
