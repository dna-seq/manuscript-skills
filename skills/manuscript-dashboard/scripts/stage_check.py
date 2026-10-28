# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Check a stage's findings.json against the stage-findings contract (../references/stage-findings.md) while the
stage that wrote it can still fix it.

    uv run --script stage_check.py RUN --skill SKILL [--file FINDINGS]

collect.py reads every stage's findings.json only when the run is assembled, hours after the stage agent that
wrote it has gone; a record it cannot read then stops the whole inventory. runs.py finish runs the same check on
the stage's newest findings.json, so the stage fixes its own records, and collect runs the part it cannot do
without (`fatal`) on every stage, naming each record and field instead of failing on the first.

What is checked:

- the shape collect needs: a `findings` list; every record with its `id` and `summary`; evidence as a list of
  {path, quote}; every change with `id`, `kind`, `section`, `summary`, `status` (applied or proposed), evidence,
  a before- or after-text, and an anchor only for an addition (`fatal`);
- IDs that start with the stage's prefix and are unique in the file;
- each evidence quote verbatim in its file (a web page is a source and is not opened);
- each finding's `quote` verbatim in the manuscript or another input as the run took it, or as it is now: one
  found only once the revision marks are stripped has a mark inside it, and is shortened to a stretch without
  one;
- each proposal's before-text, or an addition's anchor, exactly once in the clean text of the file it changes,
  and a proposal for another file than the manuscript (a supplement) naming that file in `document`.

Prints one line per problem; exit 0 when there is none, 1 otherwise, 2 for a usage error. Stdlib only, so
runs.py and collect.py load it as it is.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

# Each stage's finding and proposal prefix (stage-findings.md, Rules).
PREFIX = {"manuscript-integrity-check": "IC", "manuscript-reference-check": "RF", "manuscript-reporting-check": "RP",
          "manuscript-peer-review": "PR", "manuscript-policy-fit": "PF", "manuscript-journal-select": "JS",
          "manuscript-journal-adapt": "JA", "manuscript-prose-edit": "PE", "manuscript-deslop": "DS",
          "manuscript-story": "ST", "manuscript-figures": "FG", "manuscript-improve": "IM", "manuscript-reviewer-response": "RR",
          "manuscript-revision-marks": "RM", "manuscript-mark-people": "MP", "manuscript-coauthors": "CA"}
CHANGE_TEXT = ("id", "kind", "section", "summary")
FINDINGS_FILE = re.compile(r"findings(?:\.(\d{1,3}))?\.json$")  # findings.json, findings.2.json; never findings.draft.json
REV_MARKS = Path(__file__).resolve().parents[2] / "manuscript-revision-marks" / "scripts" / "rev_marks.py"
URL = re.compile(r"^[a-z][a-z0-9+.-]*://")


def text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def evidence_problems(items: Any, where: str) -> list[str]:
    if not isinstance(items, list):
        kind = "a sentence" if isinstance(items, str) else type(items).__name__
        return [f"{where}: evidence is {kind}; it must be a list of {{\"path\": FILE, \"quote\": \"a verbatim sentence "
                f"of that file\"}} (for the report's sentence, path stage-report.md)"]
    return [f"{where}: evidence item {n} must be {{\"path\": ..., \"quote\": ...}}, both non-empty"
            for n, item in enumerate(items, 1)
            if not isinstance(item, dict) or not text(item.get("path")) or not text(item.get("quote"))]


def fatal(doc: Any) -> list[str]:
    """What collect.py cannot read at all: the shape of the file and of each record."""
    if not isinstance(doc, dict) or not isinstance(doc.get("findings"), list):
        return ["no `findings` list (an empty list is valid)"]
    out = []
    for n, record in enumerate(doc["findings"], 1):
        if not isinstance(record, dict):
            out.append(f"finding {n} is not an object")
            continue
        where = f"finding {record.get('id') or n}"
        out += [f"{where}: no {field}" for field in ("id", "summary") if not text(record.get(field))]
        if record.get("evidence") is not None:
            out += evidence_problems(record["evidence"], where)
        if not record.get("evidence") and not text(record.get("quote")):
            out.append(f"{where}: neither evidence nor a quote, so nothing shows where it comes from")
    for n, change in enumerate(doc.get("changes") or [], 1):
        if not isinstance(change, dict):
            out.append(f"change {n} is not an object")
            continue
        where = f"change {change.get('id') or n}"
        out += [f"{where}: no {field}" for field in CHANGE_TEXT if not text(change.get(field))]
        if change.get("status") not in ("applied", "proposed"):
            out.append(f"{where}: status is {change.get('status')!r}; it must be \"proposed\" (or \"applied\")")
        out += evidence_problems(change.get("evidence"), where) if change.get("evidence") is not None else [
            f"{where}: no evidence; give the report's sentence that states its reason as "
            "[{\"path\": \"stage-report.md\", \"quote\": ...}]"]
        if not text(change.get("before")) and not text(change.get("after")):
            out.append(f"{where}: neither a before- nor an after-text")
        if change.get("anchor") is not None and change.get("before") is not None:
            out.append(f"{where}: an anchor belongs only to an addition (before: null)")
    for n, record in enumerate(doc.get("dismissed") or [], 1):
        if not isinstance(record, dict) or not text(record.get("summary")):
            out.append(f"dismissed {n}: no summary")
    for n, record in enumerate(doc.get("not_checked") or [], 1):
        if not isinstance(record, dict) or not text(record.get("check")) or not text(record.get("why")):
            out.append(f"not_checked {n}: it needs `check` and `why`")
    return out


def rev_marks() -> Any:
    if "stage_check_rev_marks" not in sys.modules:
        spec = importlib.util.spec_from_file_location("stage_check_rev_marks", REV_MARKS)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["stage_check_rev_marks"] = module  # dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
    return sys.modules["stage_check_rev_marks"]


def clean(raw: str, path: Path) -> str:
    """The text without its revision marks; one whose marks do not parse is taken as it is (lint reports them)."""
    if "@rev" not in raw:
        return raw
    marks = rev_marks()
    try:
        return marks.strip_marks(raw, marks.syntax_for(path))
    except marks.MarkErrors:
        return raw


def input_texts(run: Path, data: dict) -> list[dict]:
    """Each text input of the run: its file name, and its text as the run took it and as it is now, marked and
    clean. The manuscript comes first."""
    out = []
    for item in data.get("inputs") or []:
        copy, original = run / item["snapshot"], Path(item["original"])
        if not copy.is_file():
            continue
        try:
            taken = copy.read_text(encoding="utf-8")
            now = original.read_text(encoding="utf-8") if original.is_file() else taken
        except UnicodeDecodeError:  # a Word or PDF input has no text to quote here
            continue
        out.append({"name": original.name, "marked": [taken, now], "clean": [clean(taken, copy), clean(now, original)]})
    return out


def placement(doc: dict, skill: str, folder: Path, inputs: list[dict]) -> list[str]:
    """IDs, evidence quotes in their files, finding quotes in the manuscript, proposals' before-texts in theirs."""
    out, seen = [], set()
    prefix = PREFIX.get(skill)
    records = [("finding", r) for r in doc["findings"]] + [("change", c) for c in doc.get("changes") or []]
    for kind, record in records:
        rid = str(record.get("id") or "")
        if rid in seen:
            out.append(f"{kind} {rid}: the id is used twice in this file")
        seen.add(rid)
        if prefix and rid and not rid.startswith(prefix):
            out.append(f"{kind} {rid}: ids of {skill} start with {prefix} ({prefix}-1, {prefix}-C1)")
        for item in record.get("evidence") or []:
            if URL.match(item["path"]):
                continue
            path = Path(item["path"]) if Path(item["path"]).is_absolute() else folder / item["path"]
            if not path.is_file():
                out.append(f"{kind} {rid}: its evidence file {item['path']} is not there")
            elif item["quote"] not in path.read_text(encoding="utf-8", errors="replace"):
                out.append(f"{kind} {rid}: its evidence quote is not word for word in {item['path']}: "
                           f"{item['quote'][:80]!r}")
    if not inputs:
        return out
    for record in doc["findings"]:
        quote = record.get("quote")
        if not text(quote):
            continue
        rid = record.get("id")
        if len(quote.split()) < 3:
            out.append(f"finding {rid}: its quote has fewer than three words; quote enough to find the passage once")
        if any(quote in t for i in inputs for t in i["marked"]):
            continue
        if any(quote in t for i in inputs for t in i["clean"]):
            out.append(f"finding {rid}: a revision mark sits inside its quote; shorten it to a stretch without one: "
                       f"{quote[:80]!r}")
        else:
            out.append(f"finding {rid}: its quote is not word for word in the manuscript: {quote[:80]!r}")
    names = {i["name"] for i in inputs}
    for change in doc.get("changes") or []:
        target = change.get("before") if change.get("before") is not None else change.get("anchor")
        if change.get("status") != "proposed" or not text(target):
            if change.get("status") == "proposed" and change.get("before") is None and not text(change.get("anchor")):
                out.append(f"change {change.get('id')}: an addition names no anchor, the passage it goes after")
            continue
        field = "before-text" if change.get("before") is not None else "anchor"
        named = change.get("document")
        if named and named not in names:
            out.append(f"change {change.get('id')}: document {named!r} is not one of the run's inputs "
                       f"({', '.join(sorted(names))})")
            continue
        counts = {i["name"]: max(t.count(target) for t in i["clean"]) for i in inputs}
        holding = [name for name, count in counts.items() if count]
        main = inputs[0]["name"]
        where = named or main
        if counts.get(where, 0) == 1:
            continue
        if counts.get(where, 0) > 1:
            out.append(f"change {change.get('id')}: its {field} occurs {counts[where]} times in {where}; lengthen it "
                       f"until it occurs once")
        elif not named and holding:
            out.append(f"change {change.get('id')}: its {field} is in {holding[0]}, not the manuscript; add "
                       f"\"document\": \"{holding[0]}\"")
        else:
            out.append(f"change {change.get('id')}: its {field} is not word for word in {where} (copy it from the "
                       f"clean working copy): {target[:80]!r}")
    return out


def problems(doc: Any, skill: str, folder: Path, inputs: list[dict]) -> list[str]:
    """Every problem in one stage's findings.json; the shape first, since nothing else can be read without it."""
    return fatal(doc) or placement(doc, skill, folder, inputs)


def newest(folder: Path) -> Path | None:
    found = [(int(m.group(1) or 1), p) for p in folder.glob("findings*.json") if (m := FINDINGS_FILE.fullmatch(p.name))]
    return max(found)[1] if found else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("run", type=Path)
    parser.add_argument("--skill", required=True)
    parser.add_argument("--file", type=Path, help="default: the stage's newest findings.json")
    args = parser.parse_args(argv)
    run, folder = args.run.resolve(), args.run.resolve() / args.skill
    path = args.file or newest(folder)
    if path is None or not path.is_file():
        print(f"No findings.json in {folder}.", file=sys.stderr)
        return 2
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"{path.name}: not valid JSON ({exc})")
        return 1
    found = problems(doc, args.skill, path.parent, input_texts(run, data))
    for line in found:
        print(f"{path.name}: {line}")
    print(f"{len(found)} problem(s) in {path.name}" if found else f"{path.name} meets the stage-findings contract.")
    return 1 if found else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
