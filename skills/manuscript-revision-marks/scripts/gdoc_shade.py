# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Shade the passages no person has reviewed in a round's Google Doc, and clear the shading once they are
(manuscript-revision-marks). The Doc is the co-authors' reading copy; the master in the repository keeps the
marks, and this script only says which ranges of the Doc to colour.

    uv run --script gdoc_shade.py plan PAPER.md READ_DOC.json [--tab t.0] [--config rev-marks.toml] [--out REQUESTS.json]
    uv run --script gdoc_shade.py verify PAPER.md READ_DOC.json [--tab t.0] [--config rev-marks.toml]
    uv run --script gdoc_shade.py clear READ_DOC.json [--colour shade|diff|all] [--tab t.0] [--out REQUESTS.json]
    uv run --script gdoc_shade.py diff OLD.txt READ_DOC.json [--tab t.0] [--out REQUESTS.json] [--verify]

READ_DOC.json is the Google Docs connector's read_doc answer for the Doc, saved as JSON (the client saves a large
one to a file; write a small one out). `plan` finds each unreviewed segment of PAPER.md (the same rule and
rev-marks.toml as `rev_marks.py report --unreviewed`) in the Doc's text, word by word, and prints the
documents.batchUpdate requests that colour exactly those ranges in the shading colour and clear it wherever the
Doc carries it on text that is no longer unreviewed: after a review pass (a person's `bump`), the same command
clears what was reviewed. The agent sends `requests` with the connector's update_doc, as direct edits, never in
suggestion mode, then reads the Doc again and runs `verify`. `clear` removes the shading everywhere.

`diff` colours what changed in the Doc since an older version of it, in a second colour, for a co-author who
wants to see what a round changed: OLD.txt is that version as plain text (a revision of the Doc, fetched by its id
with the Drive connector's download_file_content and exportMimeType text/plain, or Codex's fetch_file_revision; or
the previous round's master, its clean twin). Inserted and rewritten words are coloured, the colour is cleared
where the text no longer differs, and deleted passages, which the Doc no longer holds, are listed with the place
they were cut from. `diff --verify` checks the readback instead.

Both colours are reserved: shading rgb(255, 236, 179), revision differences rgb(204, 229, 255), read back within
1/255 (Google returns colours as floats rounded to 1/255). Only text in exactly one of them is ever cleared, so a
co-author's own highlights stay.

A segment is found in the Doc by its words (letters and digits, lowercase; Markdown and LaTeX markup, link
targets and citation keys left out): the whole sequence once, else its first and last eight words once each with
about the segment's length between them (a citation or a co-author's suggestion inside it). One the Doc does not
hold, or holds more than once, is listed under `not_found` and left alone, never guessed at: the copy and the
master have drifted there.

EXIT STATUS 0 done (verify: the Doc's shading is exactly the plan's) · 1 verify found a difference · 2 usage, a
bad rev-marks.toml or not a read_doc answer · 3 could not run (a file unreadable)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

REV_MARKS = Path(__file__).resolve().parent / "rev_marks.py"
SHADE = {"red": 1.0, "green": 236 / 255, "blue": 179 / 255}  # unreviewed: amber
DIFF = {"red": 204 / 255, "green": 229 / 255, "blue": 1.0}  # changed since an older version: light blue
COLOURS = {"shade": SHADE, "diff": DIFF}
TOLERANCE = 1 / 255 + 1e-6
ENDS = 8  # words at each end that place a segment whose middle differs in the Doc
SPREAD = 0.3  # how much longer or shorter than the segment the span between its ends may be


class Failure(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def rev_marks():
    if "shade_rev_marks" not in sys.modules:
        spec = importlib.util.spec_from_file_location("shade_rev_marks", REV_MARKS)
        module = importlib.util.module_from_spec(spec)
        sys.modules["shade_rev_marks"] = module
        spec.loader.exec_module(module)
    return sys.modules["shade_rev_marks"]


# --- the Doc ----------------------------------------------------------------------------------------------------


def read_doc(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise Failure(f"{path}: cannot read: {exc}", 3) from None
    except json.JSONDecodeError as exc:
        raise Failure(f"{path}: not JSON ({exc})") from None
    doc = data.get("content", data) if isinstance(data, dict) else None
    if not isinstance(doc, dict) or not isinstance(doc.get("tabs"), list):
        raise Failure(f"{path}: not a Google Docs read_doc answer (no tabs).")
    return doc


def runs_of(doc: dict, tab: str | None) -> tuple[str, list[dict]]:
    """The tab's id and its text runs in document order: index range, text, background colour, suggested insertion."""
    tabs = doc["tabs"]
    chosen = next((x for x in tabs if (x.get("tabProperties") or {}).get("tabId") == tab), None) if tab else tabs[0]
    if chosen is None:
        raise Failure(f"no tab {tab!r} in the Doc")
    runs: list[dict] = []

    def walk(elements) -> None:
        for el in elements or []:
            for part in ((el or {}).get("paragraph") or {}).get("elements", []):
                run = part.get("textRun")
                if run and "startIndex" in part:
                    colour = (((run.get("textStyle") or {}).get("backgroundColor") or {}).get("color") or {}).get("rgbColor")
                    runs.append({"start": part["startIndex"], "end": part.get("endIndex", part["startIndex"]),
                                 "text": run.get("content", ""), "colour": colour,
                                 "inserted": bool(run.get("suggestedInsertionIds"))})
            for row in ((el or {}).get("table") or {}).get("tableRows", []):
                for cell in row.get("tableCells", []):
                    walk(cell.get("content", []))

    walk(((chosen.get("documentTab") or {}).get("body") or {}).get("content", []))
    return str((chosen.get("tabProperties") or {}).get("tabId") or ""), sorted(runs, key=lambda r: r["start"])


def ours(colour, which: dict = SHADE) -> bool:
    """Is this the given reserved colour (a channel Google leaves out is 0)?"""
    return isinstance(colour, dict) and all(abs(float(colour.get(k, 0)) - v) <= TOLERANCE for k, v in which.items())


def doc_words(runs: list[dict]) -> list[tuple[str, int, int]]:
    """The Doc's words with their index ranges in UTF-16 code units, as Google counts; a suggested insertion is
    not text the master has, so it is left out."""
    words: list[tuple[str, int, int]] = []
    for run in runs:
        if run["inserted"]:
            continue
        at, units = run["start"], []
        for ch in run["text"]:
            units.append(at)
            at += len(ch.encode("utf-16-le")) // 2
        units.append(at)
        for m in re.finditer(r"[^\W_]+", run["text"]):
            word = m.group().lower()
            if words and words[-1][2] == units[m.start()] and run["start"] == units[m.start()]:
                prev = words.pop()  # a word split across two runs (a style change inside it)
                words.append((prev[0] + word, prev[1], units[m.end()]))
            else:
                words.append((word, units[m.start()], units[m.end()]))
    return words


def shaded(runs: list[dict], which: dict = SHADE) -> list[tuple[int, int]]:
    return merge([(r["start"], r["end"]) for r in runs if ours(r["colour"], which)])


# --- the master -------------------------------------------------------------------------------------------------

LINK_TARGET = re.compile(r"\]\([^)]*\)")
CITATION = re.compile(r"\[@[^\]]*\]|\[\^[^\]]*\]|\\(?:cite[tp]?|ref|eqref|label|autoref)\{[^}]*\}")
COMMAND = re.compile(r"\\[A-Za-z]+\*?")


def words_of(text: str) -> list[str]:
    plain = COMMAND.sub(" ", CITATION.sub(" ", LINK_TARGET.sub("] ", text)))
    return [w.lower() for w in re.findall(r"[^\W_]+", plain)]


def unreviewed_pieces(paper: Path, config: Path | None) -> list[tuple[str, list[str]]]:
    """Each unreviewed segment's own text (its nested segments left out, as each counts on its own), in pieces."""
    rm = rev_marks()
    try:
        text = rm.read_source(paper)
    except OSError as exc:
        raise Failure(f"{paper}: cannot read: {exc}", 3) from None
    found = rm.parse(text, rm.Syntax.TEX if paper.suffix.lower() == ".tex" else rm.Syntax.MARKDOWN)
    try:
        people = rm.load_people(paper, config)
    except rm.ConfigError as exc:
        raise Failure(str(exc)) from None
    out = []
    for s in rm.unreviewed(found, people):
        cuts = rm.merged([*found.removals, *((c.open.start, c.close.end) for c in rm.nested_in(found, s))])
        pieces = [found.text[a:b] for a, b in rm.kept(s.open.end, s.close.start, cuts)]
        out.append((s.id, [p for p in pieces if words_of(p)]))
    return out


# --- finding a segment in the Doc ------------------------------------------------------------------------------


def occurrences(haystack: list[str], needle: list[str]) -> list[int]:
    n = len(needle)
    if not n:
        return []
    first = needle[0]
    return [i for i in range(len(haystack) - n + 1) if haystack[i] == first and haystack[i:i + n] == needle]


def locate(words: list[str], doc: list[tuple[str, int, int]]) -> tuple[tuple[int, int] | None, str]:
    """The Doc's index range of these words, and how it was found (or why not)."""
    seq = [w for w, _, _ in doc]
    whole = occurrences(seq, words)
    if len(whole) == 1:
        i = whole[0]
        return (doc[i][1], doc[i + len(words) - 1][2]), "exact"
    if len(whole) > 1:
        return None, f"its text is in the Doc {len(whole)} times"
    if len(words) < 2 * ENDS:
        return None, "its text is not in the Doc"
    heads, tails = occurrences(seq, words[:ENDS]), occurrences(seq, words[-ENDS:])
    if len(heads) != 1 or len(tails) != 1:
        return None, "its text is not in the Doc" if not heads or not tails else "its ends are in the Doc more than once"
    first, last = heads[0], tails[0] + ENDS - 1
    span = last - first + 1
    if not (1 - SPREAD) * len(words) <= span <= (1 + SPREAD) * len(words):
        return None, "its first and last words are in the Doc, but too far apart"
    return (doc[first][1], doc[last][2]), "ends"


# --- ranges ---------------------------------------------------------------------------------------------------


def merge(ranges) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a, b in sorted(ranges):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        elif b > a:
            out.append((a, b))
    return out


def minus(ranges: list[tuple[int, int]], cuts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out = []
    for a, b in ranges:
        pieces = [(a, b)]
        for c, d in cuts:
            pieces = [p for x, y in pieces for p in ((x, min(y, c)), (max(x, d), y)) if p[1] > p[0]]
        out += pieces
    return merge(out)


def request(a: int, b: int, tab: str, on: bool, which: dict = SHADE) -> dict:
    style = {"backgroundColor": {"color": {"rgbColor": which}}} if on else {}
    return {"updateTextStyle": {"range": {"startIndex": a, "endIndex": b, **({"tabId": tab} if tab else {})},
                                "textStyle": style, "fields": "backgroundColor"}}


def wanted(paper: Path, doc: dict, tab: str | None, config: Path | None) -> tuple[str, list[dict], list[dict], list]:
    tab_id, runs = runs_of(doc, tab)
    words = doc_words(runs)
    shade, missing = [], []
    for sid, pieces in unreviewed_pieces(paper, config):
        for piece in pieces:
            where, how = locate(words_of(piece), words)
            if where:
                shade.append({"id": sid, "range": list(where), "found": how})
            else:
                missing.append({"id": sid, "why": how, "starts": " ".join(piece.split())[:80]})
    return tab_id, shade, missing, runs


def plan(paper: Path, doc: dict, tab: str | None, config: Path | None) -> dict:
    tab_id, shade, missing, runs = wanted(paper, doc, tab, config)
    want = merge([tuple(s["range"]) for s in shade])
    have = shaded(runs)
    clear, add = minus(have, want), minus(want, have)
    return {"tab": tab_id, "colour": SHADE,
            "requests": [request(a, b, tab_id, False) for a, b in clear] + [request(a, b, tab_id, True) for a, b in add],
            "shade": shade, "clear": [list(r) for r in clear], "already_shaded": [list(r) for r in minus(want, add)],
            "not_found": missing,
            "send": "update_doc with these requests as direct edits (no writeMode SUGGEST); then read_doc and verify"}


# --- what changed since an older version -------------------------------------------------------------------------


def changes(old: str, doc: dict, tab: str | None) -> tuple[str, list[dict], list[dict], list[dict]]:
    """The Doc's words that are new or rewritten since *old* (each with its range), and the passages *old* had that
    the Doc no longer has (each with the Doc index it was cut at)."""
    tab_id, runs = runs_of(doc, tab)
    words = doc_words(runs)
    before = words_of(old)
    now = [w for w, _, _ in words]
    matcher = SequenceMatcher(None, before, now, autojunk=False)
    added, removed = [], []
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op in ("replace", "insert") and j2 > j1:
            added.append({"range": [words[j1][1], words[j2 - 1][2]], "was": " ".join(before[i1:i2])[:200],
                          "now": " ".join(now[j1:j2])[:200]})
        if op == "delete":
            at = words[j1][1] if j1 < len(words) else (words[-1][2] if words else 1)
            removed.append({"at": at, "words": " ".join(before[i1:i2])[:300]})
    return tab_id, added, removed, runs


def diff(old: str, doc: dict, tab: str | None) -> dict:
    tab_id, added, removed, runs = changes(old, doc, tab)
    want, have = merge([tuple(a["range"]) for a in added]), shaded(runs, DIFF)
    clear, add = minus(have, want), minus(want, have)
    return {"tab": tab_id, "colour": DIFF,
            "requests": [request(a, b, tab_id, False, DIFF) for a, b in clear]
                        + [request(a, b, tab_id, True, DIFF) for a, b in add],
            "changed": added, "deleted": removed, "clear": [list(r) for r in clear],
            "send": "update_doc with these requests as direct edits (no writeMode SUGGEST); then read_doc and diff --verify"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gdoc_shade.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("plan", "verify", "clear", "diff"):
        s = sub.add_parser(name)
        if name == "diff":
            s.add_argument("old", type=Path, help="the older version as plain text (a Doc revision, or the previous master)")
            s.add_argument("--verify", action="store_true", help="check the readback's colouring instead of planning it")
        elif name != "clear":
            s.add_argument("paper", type=Path, help="the marked master the Doc was built from")
        else:
            s.add_argument("--colour", choices=("shade", "diff", "all"), default="all", help="which colour to clear")
        s.add_argument("doc", type=Path, help="the Doc's read_doc answer, saved as JSON")
        s.add_argument("--tab", help="the Doc tab's id (default: the first tab)")
        if name in ("plan", "verify"):
            s.add_argument("--config", type=Path, help="the rev-marks.toml (default: the nearest one, as rev_marks.py finds it)")
        if name != "verify":
            s.add_argument("--out", type=Path, help="write the requests here instead of printing them")
    args = ap.parse_args(argv)
    try:
        doc = read_doc(args.doc)
        if args.command == "clear":
            tab_id, runs = runs_of(doc, args.tab)
            ranges = merge([r for name, which in COLOURS.items() if args.colour in (name, "all")
                            for r in shaded(runs, which)])
            result = {"tab": tab_id, "requests": [request(a, b, tab_id, False) for a, b in ranges],
                      "clear": [list(r) for r in ranges]}
        elif args.command == "diff":
            try:
                old = args.old.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise Failure(f"{args.old}: cannot read: {exc}", 3) from None
            result = diff(old, doc, args.tab)
            if args.verify:
                want = merge([tuple(a["range"]) for a in result["changed"]])
                have = shaded(runs_of(doc, args.tab)[1], DIFF)
                result = {"tab": result["tab"], "missing_colour": [list(r) for r in minus(want, have)],
                          "stray_colour": [list(r) for r in minus(have, want)], "deleted": result["deleted"]}
                result["ok"] = not result["missing_colour"] and not result["stray_colour"]
        elif args.command == "plan":
            result = plan(args.paper, doc, args.tab, args.config)
        else:
            tab_id, shade, missing, runs = wanted(args.paper, doc, args.tab, args.config)
            want, have = merge([tuple(s["range"]) for s in shade]), shaded(runs)
            result = {"tab": tab_id, "missing_shade": [list(r) for r in minus(want, have)],
                      "stray_shade": [list(r) for r in minus(have, want)], "not_found": missing}
            result["ok"] = not result["missing_shade"] and not result["stray_shade"]
    except Failure as exc:
        print(f"gdoc_shade.py: {exc}", file=sys.stderr)
        return exc.code
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if getattr(args, "out", None):
        args.out.write_text(text + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k != "requests"}
                         | {"requests": len(result.get("requests", [])), "out": str(args.out)}, ensure_ascii=False))
    else:
        print(text)
    return 1 if "ok" in result and not result["ok"] else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
