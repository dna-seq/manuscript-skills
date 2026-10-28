# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "pyyaml>=6", "httpx>=0.27"]
# ///
"""Draft the dashboard inventory from a manuscript-skills run, so nothing the run recorded is dropped.

    uv run --script collect.py RUN --output RUN/manuscript-dashboard/findings.draft.json
    uv run --script collect.py RUN --output RUN/manuscript-dashboard/findings.json \
        --merge RUN/manuscript-dashboard/merges.json [--reference RUN/manuscript-dashboard/reference.json]

The first command writes the draft (`findings.draft.json`), unmerged; the second the adjudicated inventory
(`findings.json`) that revise.py, dashboard.py and export_docx.py read. With a reference review, give
`--merge` and `--reference` together, once, before the corrected version is built.

It reads run.json for coverage, the manuscript snapshot for its title and sections, every skill's
findings.json (../references/stage-findings.md; the newest attempt, findings.2.json, when a stage reran),
the check outputs as raw signal counts, the reader reports, the reviewers' recommendations, concerns,
suggestions and strengths, journal selection's ladders, the co-authors' comments with how this release answers
each (manuscript-coauthors), the authors' to-do marks (STEM.todo.json beside the manuscript, which the dashboard's
To-do tab saves; --todo names another), and the recorded before/after changes.

The marks carry over: every mark, from every run, goes into the inventory's `todo`, and the output lists, for each
earlier mark, this run's problems and changes that say word for word what its item said (`todo.restated`), so the
adjudication dismisses what the authors marked redundant, with their reason, and the next run does what they approved.

Applied or proposed: the changes recorded with runs.py change are replayed on the reviewed text, in the order
the skills recorded them, each on the file it changed (the manuscript, or a supplement the run also read), and
on clean copies: a manuscript that keeps revision marks is read without them, as the records were written.
When the replay ends on the revised file, every change that found its before-text counts as applied, including
an edit a later stage edited again. Otherwise a change counts as applied only when the revised file holds its
after-text and no longer holds its before-text; the rest are listed as recorded changes not in the revision. A
change to another file than the manuscript carries that file's name (`document`), so the corrected version,
built from the manuscript, leaves it alone.

The merge file is the adjudication: which records describe one problem, which a reviewer verified,
corrected or dismissed, and the decisions for the authors. Collect never makes those calls; it applies
them, keeps every source ID and refuses an inventory that does not validate. Without --merge it warns when
a merge file lies beside the output, since that inventory then has no adjudication.

No output is overwritten: an existing one is refused, and the message names the next attempt
(findings.json, then findings.2.json).
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

import dashboard as viz
import stage_check

# Every skill's and script's severity words, onto the one scale (stage-findings.md): `optional` is a
# possible improvement (info, shown as "Optional"), `uncertain` and `not_assessed` could not be checked.
SEVERITY = {"blocker": "blocker", "serious": "blocker", "major": "major", "important": "major", "minor": "minor",
            "optional": "info", "info": "info", "uncertain": "unknown", "not_assessed": "unknown", "unknown": "unknown"}
TERMINAL = {"completed", "partial", "blocked", "not_run", "reused"}
STATUS_WORDS = {"not_run": "not run", "running": "in progress", "in_progress": "in progress"}
# The coordinator of a whole run: it is still running while it collects, so it has no coverage of its own.
COORDINATOR = "manuscript-improve"
DEFENCE = {"premise not supported", "answered", "partly answered", "not answered"}
PREFIX = stage_check.PREFIX
# A stage's findings and the adjudication are records, not raw signals; neither are their later attempts.
SKIP = re.compile(r"^(?:findings|merges)(?:\.\d+)?\.json$")
# Peer review keeps every finding three times (merged, adjudicated, and the check of each): the merged file is
# what the referees proposed, so it alone counts as raw signals.
PEER_SIGNALS = re.compile(r"^findings\.merged(?:\.\d+)?\.json$")
OWN = {"manuscript-dashboard", "manuscript-visualize"}  # this skill, and its name before 0.10.0 in older runs
CHANGE_FIELDS = ("id", "kind", "section", "summary", "status", "finding_ids", "before", "after", "anchor", "why", "comment",
                 "evidence", "document")
REV_MARKS = Path(__file__).resolve().parents[2] / "manuscript-revision-marks" / "scripts" / "rev_marks.py"
app = typer.Typer(add_completion=False)


def relative(path: Path, out_dir: Path) -> str:
    return os.path.relpath(path.resolve(), out_dir.resolve())


def rev_marks() -> Any:
    """manuscript-revision-marks' rev_marks.py, whose strip_marks wrote the clean copies the change records come from."""
    if "collect_rev_marks" not in sys.modules:
        spec = importlib.util.spec_from_file_location("collect_rev_marks", REV_MARKS)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["collect_rev_marks"] = module  # dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
    return sys.modules["collect_rev_marks"]


def clean_copy(text: str, path: Path) -> str:
    """The text as an editor reads it. Change records are written from clean copies, so a manuscript that keeps
    revision marks is compared without them; one without marks is returned as it is."""
    if "@rev" not in text:
        return text
    marks = rev_marks()
    try:
        return marks.strip_marks(text, marks.syntax_for(path))
    except marks.MarkErrors as exc:
        raise ValueError(f"{path.name} has {len(exc.issues)} revision-mark error(s), so its clean copy cannot be made "
                         f"and the recorded changes cannot be compared with it. Fix them first: "
                         f"uv run --script {REV_MARKS} lint {path}") from exc


def heading(line: str) -> str | None:
    if match := re.match(r"^#{1,4}\s+(.+?)\s*#*\s*$", line):
        return re.sub(r"[*_`]", "", match.group(1)).strip()
    if match := re.match(r"^\\(?:sub)*section\*?\{(.+)\}", line):
        return match.group(1).strip()
    return None


def manuscript(snapshot: Path, original: str, sha256: str, version: str, out_dir: Path) -> dict:
    names = [name for line in snapshot.read_text(encoding="utf-8").splitlines() if (name := heading(line))]
    return {"title": names[0] if names else Path(original).name, "version": version,
            "sha256": sha256, "sections": names[1:], "path": relative(snapshot, out_dir)}


def coverage(run: Path, data: dict, out_dir: Path, skip: set[str] = frozenset()) -> list[dict]:
    """What each skill covered, from run.json and the skill's generated README. A stage still running is "in
    progress"; its README's status line changes when it finishes, so its evidence quotes the README's title."""
    rows = []
    for name, seat in data["skills"].items():
        if name in OWN or name in skip:
            continue
        status = seat["status"]
        readme = relative(run / name / "README.md", out_dir)
        if status in TERMINAL:
            rows.append({"skill": name, "status": status, "note": seat.get("reason") or f"{STATUS_WORDS.get(status, status).capitalize()}.",
                         "evidence": [{"path": readme, "quote": f"Status: **{status}**."}]})
        else:
            rows.append({"skill": name, "status": "in_progress",
                         "note": seat.get("reason") or "Still in progress when this inventory was collected.",
                         "evidence": [{"path": readme, "quote": f"# {name}"}]})
    return rows


def newest_findings(folder: Path) -> Path | None:
    """A stage's findings.json, or its newest attempt (findings.2.json) when the stage reran."""
    return viz.newest_attempt(folder / "findings.json", folder=False)


def stage_records(run: Path, out_dir: Path, snapshot: Path) -> dict[str, list]:
    """Every skill's findings.json, with evidence paths rebased onto the inventory's folder."""
    found: dict[str, list] = {"findings": [], "dismissed": [], "not_checked": [], "changes": []}
    seen: set[str] = set()
    for path in [p for folder in sorted(run.glob("manuscript-*")) if folder.is_dir() and (p := newest_findings(folder))]:
        skill, folder = path.parent.name, path.parent
        if skill in OWN:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))

        def rebase(items: list[dict], record: dict | None = None) -> list[dict]:
            out = []
            for item in items:
                if re.match(r"^[a-z][a-z0-9+.-]*://", item["path"]):  # a web page is a source, not local evidence
                    if record is not None:
                        record.setdefault("_web", []).append(f"{item['path']} (“{item['quote'][:160]}”)")
                    continue
                target = Path(item["path"]) if Path(item["path"]).is_absolute() else folder / item["path"]
                out.append({"path": relative(target, out_dir), "quote": item["quote"]})
            return out

        ids = [record["id"] for record in doc.get("findings", [])]
        # Two skills chose the same IDs: keep both, and namespace every ID of the later skill so names stay predictable.
        prefix = f"{PREFIX.get(skill, skill.removeprefix('manuscript-'))}." if seen & set(ids) else ""
        for record in doc.get("findings", []):
            fid = prefix + record["id"]
            seen.add(fid)
            evidence = rebase(record.get("evidence") or [], record)
            if not evidence and record.get("quote"):
                evidence = [{"path": relative(snapshot, out_dir), "quote": record["quote"]}]
            web = " Sources read: " + "; ".join(record["_web"]) + "." if record.get("_web") else ""
            if record.get("looked_in"):  # an absence says where the skill searched
                web += " Looked in: " + "; ".join(map(str, record["looked_in"])) + "."
            found["findings"].append({
                "id": fid, "category": record.get("category") or "Uncategorised",
                "section": record.get("section") or "Whole manuscript", "summary": record["summary"],
                "severity": severity(record.get("severity")),
                "assessment": "confirmed" if record.get("confidence") == "confirmed" else "candidate",
                "resolution": "open", "skills": [skill], "evidence": evidence,
                "stage": record.get("stage") if record.get("stage") in viz.STAGES else "unknown",
                "quote": record.get("quote"), "detail": record.get("detail", "") + web, "action": record.get("action", ""),
                "decision": bool(record.get("decision")), "sources": [{"skill": skill, "id": record["id"]}]})
        for record in doc.get("dismissed", []):
            found["dismissed"].append({"skill": skill, "summary": record["summary"], "why": record.get("why") or "No reason recorded."})
        for record in doc.get("not_checked", []):
            found["not_checked"].append({"skill": skill, "check": record["check"], "why": record["why"],
                                         "leaves_open": record.get("leaves_open", "")})
        for record in doc.get("changes", []):
            # Keep the change contract's fields; anything else a skill added (the journal it is for) joins the summary.
            # A field written as null is left out, so it takes its default: a null comment means no question.
            known = {k: record[k] for k in CHANGE_FIELDS if record.get(k) is not None}
            extra = [f"{k.replace('_', ' ')}: {v}" for k, v in record.items() if k not in CHANGE_FIELDS and v not in (None, "", False, [])]
            if extra:
                known["summary"] = f"{known.get('summary', '')} ({'; '.join(map(str, extra))})".strip()
            found["changes"].append({**known, "evidence": rebase(record.get("evidence") or [])})
    return found


def contract_errors(run: Path) -> list[str]:
    """What in the stages' newest findings files collect could not read at all (stage_check.fatal), every record
    named, so one pass fixes them instead of a traceback on the first."""
    out = []
    for path in [p for folder in sorted(run.glob("manuscript-*")) if folder.is_dir() and folder.name not in OWN
                 and (p := newest_findings(folder))]:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            out.append(f"{path.parent.name}/{path.name}: not valid JSON ({exc})")
            continue
        out += [f"{path.parent.name}/{path.name}: {problem}" for problem in stage_check.fatal(doc)]
    return out


def severity(value: Any) -> str:
    """A skill's own severity word on the one scale; anything unknown could not be checked."""
    return SEVERITY.get(re.sub(r"[\s-]+", "_", str(value or "unknown").strip().lower()), "unknown")


def signals(run: Path) -> list[dict]:
    """Raw output counts: scanner and checker hits by check, referee proposals (the merged file only, its newest
    attempt in each folder), reader concerns."""
    rows = []
    for path in sorted(run.glob("manuscript-*/**/*.json")):
        if SKIP.match(path.name) or "commands" in path.parts or path.relative_to(run).parts[0] in OWN:
            continue
        if path.relative_to(run).parts[0] == "manuscript-peer-review" and (
                not PEER_SIGNALS.match(path.name) or path != viz.newest_attempt(path.with_name("findings.merged.json"), folder=False)):
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        skill = path.relative_to(run).parts[0]
        items = doc.get("findings") if isinstance(doc, dict) else None
        if isinstance(items, list) and items and isinstance(items[0], dict):
            key = "check" if "check" in items[0] else "seat"
            tally: dict[str, int] = {}
            for item in items:
                name = str(item.get(key) or "finding")
                tally[name] = tally.get(name, 0) + 1
            rows += [{"skill": skill, "check": check, "count": count, "note": path.name} for check, count in sorted(tally.items())]
        elif isinstance(doc, dict) and isinstance(doc.get("smell_totals"), dict):
            total = sum(v for v in doc["smell_totals"].values() if isinstance(v, int))
            rows.append({"skill": skill, "check": "style patterns", "count": total, "note": path.name})
    for path in sorted(run.glob("manuscript-story/readers*/*.md")):
        reader = parse_reader(path)
        if reader:
            rows.append({"skill": "manuscript-story", "check": f"reader concerns: {reader['seat']}",
                         "count": len(reader.get("stumbles") or []) + len(reader.get("wanted") or []),
                         "note": f"{path.parent.name}/{path.name}"})
    return rows


def parse_reader(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    block = re.search(r"```ya?ml\s*\n(.*?)```", text, re.S)
    try:
        doc = yaml.safe_load(block.group(1) if block else text)
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) and doc.get("seat") else None


def story(run: Path) -> dict | None:
    """The story stage's direction, tests and options, when its findings.json gives them."""
    path = newest_findings(run / "manuscript-story")
    try:
        doc = json.loads(path.read_text(encoding="utf-8")).get("story") if path else None
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return None
    return doc if isinstance(doc, dict) else None


def figures(run: Path, out_dir: Path) -> dict | None:
    """The figures stage's verdicts, recommendations and new figures, with its image paths made relative to the
    inventory, so the dashboard can embed them."""
    path = newest_findings(run / "manuscript-figures")
    try:
        doc = json.loads(path.read_text(encoding="utf-8")).get("figures") if path else None
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return None
    if not isinstance(doc, dict):
        return None
    for item in doc.get("items") or []:
        for key in ("image", "proposed_image"):
            if item.get(key):
                item[key] = relative(Path(item[key]) if Path(item[key]).is_absolute() else path.parent / item[key], out_dir)
    return doc


def coauthors(run: Path) -> dict | None:
    """The co-authors' comments on the previous release and how this one answers each, when the coauthors stage's
    findings.json gives them; its ledger is kept by name, never by where it lives."""
    path = newest_findings(run / "manuscript-coauthors")
    try:
        doc = json.loads(path.read_text(encoding="utf-8")).get("coauthors") if path else None
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return None
    if not isinstance(doc, dict):
        return None
    if isinstance(doc.get("source"), str):
        doc["source"] = re.split(r"[\\/]", doc["source"])[-1]
    return doc


def relink(inventory: dict, skill: str, records: list[dict]) -> None:
    """A stage record's problems follow a merged record to the one kept; a dismissed one is dropped."""
    final = {(source["skill"], source["id"]): finding["id"] for finding in inventory["findings"]
             for source in finding.get("sources") or []}
    for record in records:
        ids = [final.get((skill, fid)) for fid in record.get("finding_ids") or []]
        record["finding_ids"] = list(dict.fromkeys(fid for fid in ids if fid))


def link_figures(inventory: dict) -> None:
    """A figure's problems follow a merged record to the one kept; a dismissed one is dropped."""
    figures = inventory["figures"] or {}
    relink(inventory, "manuscript-figures", [*figures.get("items", []), *figures.get("new", [])])


def link_coauthors(inventory: dict) -> None:
    """A co-author comment's problems follow a merged record to the one kept; a dismissed one is dropped."""
    relink(inventory, "manuscript-coauthors", (inventory["coauthors"] or {}).get("items", []))


def isolation(data: dict | None) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """How each reader (by its file) and each referee (by its seat) ran, as runs.py recorded it: a fresh agent, or
    one agent reading as every seat in turn, and the model that read it when the run recorded one."""
    by_path, by_seat = {}, {}
    for name in ("manuscript-story", "manuscript-peer-review"):
        for item in ((data or {}).get("skills", {}).get(name) or {}).get("artifacts", []):
            if item.get("isolation") and item.get("role") in {"reader", "referee", "seat"}:
                ran = {"isolation": item["isolation"], "model": str(item.get("model") or "")}
                by_path[item["path"]] = ran
                if item.get("seat"):
                    by_seat[item["seat"]] = ran
    return by_path, by_seat


def panel(run: Path, data: dict | None = None) -> dict:
    by_path, by_seat = isolation(data)
    readers = []
    for path in sorted(run.glob("manuscript-story/readers*/*.md")):
        if not (doc := parse_reader(path)):
            continue
        # The funnel format records where the reader would leave; the older one only where attention dropped.
        left = doc.get("left") if isinstance(doc.get("left"), dict) else None
        stop = left or doc.get("stopped_at") or {}
        where = stop if isinstance(stop, str) else ": ".join(str(stop[k]) for k in ("section", "why") if stop.get(k))
        dips = [str(d.get("section")) for d in doc.get("dips") or [] if isinstance(d, dict) and d.get("section")]
        path_steps = [{"section": str(step["section"]), "how": step.get("how") if step.get("how") in {"read", "skimmed", "skipped"} else "read"}
                      for step in doc.get("path") or [] if isinstance(step, dict) and step.get("section")]
        readers.append({"seat": str(doc["seat"]), "takeaway": str(doc.get("takeaway") or "No takeaway given."),
                        "stopped_at": where or "Finished", "next": str(doc.get("next") or ""),
                        "left": str(left.get("section") or "") if left else "", "dips": dips, "path": path_steps,
                        "round": path.parent.name if path.parent.name != "readers" else "",
                        **by_path.get(path.relative_to(run).as_posix(), {})})
    recommendations, reviewers = [], []
    bound = criteria(run)
    # The adjudicated file carries each concern's verdict; earlier stages of the same review lack it.
    candidates = sorted(run.glob("manuscript-peer-review/**/*.json"),
                        key=lambda p: (p.name != "findings.adjudicated.json", p.name != "findings.merged.json", str(p)))
    for path in candidates:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("reports"), list):
            continue
        concerns = [c for c in doc.get("findings") or [] if isinstance(c, dict) and c.get("seat") and c.get("concern")]
        strengths = [s for s in doc.get("strengths") or [] if isinstance(s, dict) and s.get("seat")]
        for report in doc["reports"]:
            seat = report.get("seat", "reviewer")
            for rec in report.get("recommendations", []):
                if rec.get("recommendation") in {"accept", "minor-revision", "major-revision", "reject"}:
                    recommendations.append({"seat": seat, "venue": rec["venue"],
                                            "recommendation": rec["recommendation"], "reason": rec.get("reason") or "No reason given."})
            reviewers.append({"seat": seat, "summary": str(report.get("summary") or ""), **by_seat.get(seat, {}),
                              "strengths": [str(s.get("note") or s.get("quote")) for s in strengths if s["seat"] == seat],
                              "concerns": [{"id": str(c.get("id") or f"{seat}-{n}"), "severity": str(c.get("severity") or "").strip().lower(),
                                            "location": str(c.get("location") or ""), "concern": str(c["concern"]),
                                            "suggestion": str(c.get("change_my_mind") or ""),
                                            "route": token(c.get("route") or c.get("proposed_route")),
                                            "placement": str(c.get("placement") or ""), "cost": str(c.get("cost") or ""),
                                            "defence": defence(c), "verdict": str(c.get("verdict") or "").strip().lower(),
                                            "verdict_evidence": str(c.get("verdict_evidence") or ""),
                                            "criterion": criterion_ids(c.get("criterion")),
                                            "off_criterion": str(c.get("off_criterion") or ""),
                                            "norm_source": str(c.get("norm_source") or "")}
                                           for n, c in enumerate((c for c in concerns if c["seat"] == seat), 1)],
                              "criteria": bound.get(seat, [])})
        if reviewers:  # the first file with the reports (the adjudicated one when it exists); the others repeat it
            break
    return {"readers": readers, "recommendations": recommendations, "reviewers": reviewers}


def criterion_ids(value: Any) -> list[str]:
    """A concern's `criterion`, one id or a list ("C2", ["C1", "C3"]), in one spelling."""
    return [str(x).strip().upper() for x in (value if isinstance(value, list) else [value]) if str(x or "").strip()]


def criteria(run: Path) -> dict[str, list[dict]]:
    """Each reviewer's criteria, written before reading, from the finding check run with --criteria (check_findings.py
    keeps, per seat, each criterion's concerns and the line saying what was checked). The adjudicated check, when there
    is one, has the last word."""
    out: dict[str, list[dict]] = {}
    files = sorted(run.glob("manuscript-peer-review/**/check*.json"), key=lambda p: ("adjudicated" in p.name, str(p)))
    for path in files:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        bound = doc.get("criteria") if isinstance(doc, dict) else None
        if not isinstance(bound, dict):
            continue
        for seat, entry in bound.items():
            items = (entry or {}).get("criteria") or []
            out[seat] = [{"id": str(c["id"]), "text": str(c["text"]), "concerns": [str(f) for f in c.get("findings") or []],
                          "checked": str(c.get("checked") or "")} for c in items if c.get("id") and c.get("text")]
    return out


# The worst state of a reference, as the dashboard's reference strip shows it, most serious first.
REFERENCE_STATES = ("retracted", "wrong", "corrected", "unverified", "not-checked", "fine")


def reference_list(run: Path, inputs: list[dict] | None = None) -> list[dict]:
    """The manuscript's reference list as the reference check left it (scan.py's JSON in the reference-check or
    integrity-check folder, the reference check's own first): per entry its worst state, a link to its record and
    what the scanner found, in its words. A scan names the file it read (`path`): with the run's `inputs`, the
    manuscript's scan comes first and a scan of another input (a supplement, with a list of its own) is never drawn
    as the paper's, whatever its file sorts before."""
    names = [{Path(item[key]).name for key in ("original", "snapshot") if item.get(key)} for item in inputs or []]
    main, others = (names[0], set().union(*names[1:])) if names else (set(), set())

    def read(path: Path) -> dict | None:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        refs = doc.get("references") if isinstance(doc, dict) else None
        if not isinstance(refs, list) or not refs or not all(isinstance(r, dict) and "status" in r for r in refs):
            return None
        return doc

    scans = [(path, doc) for folder in ("manuscript-reference-check", "manuscript-integrity-check")
             for path in sorted(run.glob(f"{folder}/**/*.json")) if (doc := read(path)) is not None]
    scanned = [Path(str(doc.get("path") or "")).name for _, doc in scans]
    scans = [scan for scan, name in zip(scans, scanned) if name not in others or name in main]
    scans.sort(key=lambda scan: Path(str(scan[1].get("path") or "")).name not in main)  # stable: folder order kept
    for path, doc in scans:
        refs = doc["references"]
        notes: dict[tuple[int, str], list[tuple[str, str]]] = {}
        for f in doc.get("findings") or []:
            if isinstance(f, dict) and f.get("check") == "references" and f.get("severity") != "info":
                notes.setdefault((int(f.get("line") or 0), str(f.get("excerpt") or "")[:60]), []).append(
                    (str(f.get("severity")), str(f.get("message") or "")))
        out = []
        for n, ref in enumerate(refs, 1):
            text = " ".join(str(ref.get("text") or "").split())
            said = notes.get((int(ref.get("line") or 0), text[:60]), [])
            status, serious = ref.get("status"), any(sev in ("blocker", "major") for sev, _ in said)
            state = ("retracted" if status in ("retracted", "concern") or ref.get("retraction") in ("retracted", "concern")
                     else "wrong" if status in ("mismatch", "unresolved") or serious
                     else "unverified" if status == "no_identifier"
                     else "corrected" if said
                     else "not-checked" if status in ("lookup_failed", "not_checked") else "fine")
            doi, pmid, arxiv = ref.get("doi"), ref.get("pmid"), ref.get("arxiv")
            link = (f"https://arxiv.org/abs/{arxiv}" if arxiv else f"https://doi.org/{doi}" if doi and status != "no_identifier"
                    else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
            out.append({"n": n, "line": int(ref.get("line") or 0), "text": text[:300] or f"Entry {n}", "state": state,
                        "link": link, "notes": [message for _, message in said]})
        return out
    return []


def token(value: Any) -> str:
    """A route as peer review writes it ("Fixable in text", "author_required") in its one spelling."""
    return re.sub(r"[\s_]+", "-", str(value or "").strip().lower())


def defence(concern: dict) -> str:
    """How far the defence answered a concern, in peer review's words: premise not supported, answered, partly
    answered or not answered. Another spelling is normalised; an unknown value is kept as written."""
    raw = concern.get("defence_outcome") or (concern.get("defence") if isinstance(concern.get("defence"), str) else "")
    words = re.sub(r"[\s_-]+", " ", str(raw or "")).strip().lower()
    return words if words in DEFENCE or not words else str(raw).strip()


# A concern ID: a seat's prefix of two or three capitals (SK-3; another model's seat SKX-3, or SKx-3 in older runs).
CONCERN_ID = re.compile(r"\b[A-Z]{2,3}x?-\d+\b")


def concern_mentions(findings: list[dict]) -> dict[str, set[str]]:
    """Which stage records cite each reviewer concern: the peer-review stage names the concern IDs it groups."""
    out: dict[str, set[str]] = {}
    for finding in findings:
        text = " ".join(str(finding.get(k) or "") for k in ("detail", "summary", "action"))
        for cid in CONCERN_ID.findall(text):
            out.setdefault(cid, set()).add(finding["id"])
    return out


def link_concerns(inventory: dict, mentions: dict[str, set[str]]) -> None:
    """Each reviewer concern to the problems that carry it, following a merged record to the one kept."""
    final = {}
    for finding in inventory["findings"]:
        for sid in {finding["id"], *(source["id"] for source in finding.get("sources") or [])}:
            final[sid] = finding["id"]
    for reviewer in (inventory.get("panel") or {}).get("reviewers", []):
        for concern in reviewer["concerns"]:
            concern["finding_ids"] = sorted({final[x] for x in mentions.get(concern["id"], set()) if x in final})


def number(text: str | None) -> float | None:
    try:
        return float(text) if text not in (None, "") else None
    except ValueError:
        return None


ASPECTS = ("drafting", "prompts", "records", "detection", "declaration", "counted", "extra")


# What manuscript-journal-select leaves for the dashboard: its two ladders (paper.journal-ladder.csv,
# paper.preprint-ladder.csv, or a later attempt paper.journal-ladder.2.csv), top3.json and the shared record
# (manuscript-record.yaml, or <stem>.record.yaml where several manuscripts share a folder).
LADDER = re.compile(r"^.+\.(?P<kind>journal|preprint)-ladder(?:\.(?P<n>\d+))?\.csv$")
TOP = re.compile(r"^top3(?:\.(?P<n>\d+))?\.json$")
RECORD = re.compile(r"^(?:manuscript-record|.+\.record)(?:\.(?P<n>\d+))?\.ya?ml$")


def selection_files(run: Path, data: dict | None = None) -> dict[str, Path | None]:
    """Journal selection's files: in its run folder (or a subfolder) first, then wherever run.json says a skill
    registered them; the record, failing both, beside the manuscript. The newest attempt wins."""
    folder = run / "manuscript-journal-select"
    candidates = sorted((p for p in folder.rglob("*") if p.is_file()), key=lambda p: (len(p.parts), str(p))) if folder.is_dir() else []
    registered = [run / item["path"] for seat in (data or {}).get("skills", {}).values() for item in seat.get("artifacts") or []
                  if isinstance(item, dict) and item.get("path")]
    candidates += [p for p in registered if p.is_file() and p not in candidates]

    def best(pattern: re.Pattern, kind: str | None = None) -> Path | None:
        found = [(int(m["n"] or 1), -k, p) for k, p in enumerate(candidates)
                 if (m := pattern.match(p.name)) and (kind is None or m["kind"] == kind)]
        return max(found)[2] if found else None

    record = best(RECORD)
    for source in (data or {}).get("inputs") or []:
        original = Path(source.get("original", ""))
        for name in ("manuscript-record.yaml", f"{original.stem}.record.yaml"):
            if record is None and (original.parent / name).is_file():
                record = original.parent / name
    return {"journals": best(LADDER, "journal"), "preprints": best(LADDER, "preprint"), "top3": best(TOP), "record": record}


def catalogue_policies(record: Path | None) -> tuple[Any, dict[str, dict]]:
    """For a ladder written before it carried the AI-policy columns: the venue catalogue with the facts the
    run's record holds, laid over it as the ladder itself did."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "manuscript-journal-adapt" / "scripts"))
    import venues as catalogue

    checked, resolved = catalogue.load_venues()
    if record is not None:
        resolved = catalogue.with_facts(resolved, catalogue.load_record(record)[1])
    return catalogue, {"checked": str(checked), "venues": resolved}


def ai_policy(row: dict, key: str, record: Path | None, cache: dict) -> dict | None:
    if row.get("ai_drafting"):
        aspects = {a: dict(zip(("level", "text"), (row.get(f"ai_{a}") or "unknown: not recorded").split(": ", 1))) for a in ASPECTS}
        return {"aspects": aspects, "reasons": [row["ai_reasons"]] if row.get("ai_reasons") else [],
                "url": row.get("ai_policy_url") or "", "source": "the run's ladder"}
    if "catalogue" not in cache:
        try:
            cache["catalogue"] = catalogue_policies(record)
        except (OSError, ValueError, yaml.YAMLError, typer.BadParameter) as exc:  # show none rather than a guess
            cache["catalogue"] = (None, {"error": str(exc)})
    catalogue, data = cache["catalogue"]
    venue = (data.get("venues") or {}).get(key)
    if catalogue is None or venue is None:
        return None
    flags = catalogue.ai_flags(venue)
    return {"aspects": {a: {"level": level, "text": text} for a, (level, text) in flags.items()},
            "reasons": catalogue.friction(venue)[1], "url": catalogue.policy_page(venue) or "",
            "source": f"the venue catalogue (checked {data['checked']}) with this run's record"}


def top_choices(path: Path | None) -> list[dict]:
    """top3.json: the journals the selection recommends, each with key, name, article_type, why and url (a list, or
    a mapping that holds it under `journals` or `top3`)."""
    if path is None:
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    if isinstance(doc, dict):
        doc = doc.get("journals") or doc.get("top3") or []
    return [entry for entry in doc if isinstance(entry, dict)] if isinstance(doc, list) else []


def venues(run: Path, data: dict | None = None) -> list[dict]:
    """The journal and preprint ladders manuscript-journal-select wrote, in the order it chose."""
    files = selection_files(run, data)
    chosen = {entry.get("key") or entry.get("name"): entry for entry in top_choices(files["top3"])}
    rows, cache = [], {}
    for ladder in ("journals", "preprints"):
        if files[ladder] is None:
            continue
        with files[ladder].open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                pick = chosen.get(row.get("key")) or chosen.get(row.get("name"))
                rung = int(number(row.get("chosen_rung")) or number(row.get("rung")) or len(rows) + 1)
                fee = " ".join(x for x in (row.get("fee_amount"), row.get("fee_currency")) if x)
                rows.append({"ladder": ladder, "rung": rung, "tool_rung": int(number(row.get("rung")) or rung),
                             "name": row.get("name") or row.get("key") or "unnamed", "key": row.get("key") or "",
                             "article_type": (pick or {}).get("article_type", ""), "chosen": bool(pick) and ladder == "journals",
                             "fits": row.get("fits") or "", "fits_reason": row.get("fits_reason") or "",
                             "impact_factor": number(row.get("jif")), "impact_factor_year": row.get("jif_year") or "",
                             "first_decision_days": number(row.get("first_decision_days")), "speed_measure": row.get("speed_measure") or "",
                             "ai_points": int(number(row.get("ai_points"))) if number(row.get("ai_points")) is not None else None,
                             "ai_tier": row.get("ai_tier") or "", "ai_for_this_use": row.get("ai_for_this_use") or "",
                             "ai_policy": ai_policy(row, row.get("key") or "", files["record"], cache), "fee": fee,
                             "preprint_rule": row.get("preprint_rule") or "", "why": (pick or {}).get("why", ""),
                             "url": row.get("guidelines_url") or (pick or {}).get("url", "")})
    return rows


def ladder_gaps(run: Path, data: dict) -> list[dict]:
    """When journal selection ran but left no ladder the dashboard can find, say so rather than show nothing."""
    if "manuscript-journal-select" not in data.get("skills", {}):
        return []
    files = selection_files(run, data)
    missing = [words for ladder, words in (("journals", "journal"), ("preprints", "preprint")) if files[ladder] is None]
    if not missing:
        return []
    which = " and ".join(missing) + (" ladders" if len(missing) > 1 else " ladder")
    return [{"skill": "manuscript-journal-select", "check": f"The {which} in the dashboard",
             "why": f"The journal selection stage did not record its {which} in the run, so the Journals tab cannot "
                    + ("show them." if len(missing) > 1 else "show it."),
             "leaves_open": "The order of the venues and their AI policies, which the stage's report still gives."}]


def document_of(entry: dict, section: str, before: str | None, after: str | None,
                documents: list[tuple[str, str, str]], main_name: str) -> str:
    """The file a recorded change edited, by its name in `documents` ("" for the manuscript): the one runs.py change
    named; for a record from before changes named their file, the only file whose reviewed or revised text holds
    its before- or after-text, else, for a section named "Supplement ...", the supplement, else the manuscript.
    The order matters: an edit to a sentence the supplement repeats from the manuscript names a Supplement
    section, and replaying it on the manuscript would change the wrong copy."""
    names = {name for name, _, _ in documents}
    if (named := entry.get("document")) is not None:
        named = "" if named == main_name else named
        if named not in names:
            raise ValueError(f"A change record names the file {named!r}, which is not one of the run's inputs "
                             f"({', '.join(sorted(n or main_name for n in names))}).")
        return named
    texts = [text for text in (before, after) if text]
    holding = [name for name, start, current in documents if any(t in start or t in current for t in texts)]
    if len(holding) == 1:
        return holding[0]
    others = [name for name, _, _ in documents if name]
    if section.strip().lower().startswith("supplement") and others:
        return next((name for name in others if "suppl" in name.lower()), others[0])
    return ""


def replay(out: list[dict], indexes: list[int], start: str) -> tuple[list[int], str]:
    """Replay the change records at `indexes` on `start` in their order. Each must find its before-text; one that
    does not yet is tried again after the others, so the coordinator's own follow-up edit, recorded last under
    manuscript-improve, still replays after the stage edits it changed."""
    pending, text, took = list(indexes), start, []
    while pending:
        waiting = []
        for index in pending:
            before, after = out[index]["before"], out[index]["after"]
            if before is not None and before in text:
                text = text.replace(before, after or "", 1)
                took.append(index)
            elif before is not None:
                waiting.append(index)
        if len(waiting) == len(pending):
            break
        pending = waiting
    return took, text


def blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def reaches(replayed: str, current: str, additions: list[str]) -> bool:
    """Whether the replay ended on the revised text. An addition recorded without a before-text cannot be placed
    by the replay, so the revised text is compared without it."""
    if replayed == current:
        return True
    for addition in additions:
        if addition not in current:
            return False
        current = current.replace(addition, "", 1)
    return bool(additions) and blank_lines(replayed) == blank_lines(current)


def recorded_changes(run: Path, data: dict, out_dir: Path, current: str, start: str,
                     others: list[tuple[str, str, str]] | tuple = (), main_name: str = "") -> list[dict]:
    """runs.py change records, replayed on the reviewed text in the order they were recorded (by their time; a run
    from before changes had one goes skill by skill), each on the file it changed (`document_of`): `current` and
    `start` are the manuscript's revised and reviewed clean texts, `others` the (name, reviewed, revised) clean
    texts of the run's other inputs, a supplement among them. When the replay of a file ends on its revised text,
    every one of its changes that took is applied, including an edit a later stage edited again. Otherwise a change
    counts as applied only when the revised file holds its after-text and not its before-text."""
    documents = [("", start, current), *others]
    out, order = [], []
    for skill, seat in data["skills"].items():
        for number, change in enumerate(seat["changes"], 1):
            path = run / change["path"]
            parts = re.match(r"# (.*?)\n\nReason: (.*?)\n\n(?:Comment: (.*?)\n\n)?## Before\n\n(.*)\n\n## After\n\n(.*)\Z",
                             path.read_text(encoding="utf-8"), re.S)
            if not parts:
                continue
            section, reason, comment, before, after = parts.groups()
            before = None if before.strip() == "(No previous block.)" else before.strip()
            after = None if after.strip() == "(Block removed.)" else after.strip()
            # The recorded reason is the edit's reasoning; its first sentence is the summary.
            first = re.match(r"(.+?[.!?])(?:\s|$)", reason.strip())
            summary = first.group(1) if first else reason.strip()
            order.append((change.get("recorded_at") or "", len(out)))
            out.append({"id": f"{skill.removeprefix('manuscript-')}.C{number}", "section": section,
                        "summary": summary, "why": reason.strip() if reason.strip() != summary else "", "comment": (comment or "").strip(),
                        "finding_ids": [], "before": before, "after": after,
                        "document": document_of(change, section, before, after, documents, main_name),
                        "evidence": [{"path": relative(path, out_dir), "quote": reason.strip() or (after or before)[:200]}]})
    # By time only when every record has one; a run recorded before changes carried a time replays skill by skill.
    if all(time for time, _ in order):
        order.sort(key=lambda item: item[0])
    took: list[int] = []
    for name, begin, end in documents:
        mine = [index for _, index in order if out[index]["document"] == name]
        took_here, text = replay(out, mine, begin)
        took += took_here
        replayed = reaches(text, end, [out[i]["after"] for i in mine if out[i]["before"] is None and out[i]["after"]])
        for index in mine:
            before, after = out[index]["before"], out[index]["after"]
            if replayed:
                applied = index in took_here or (before is None and after is not None and after in end)
            else:
                applied = (after is None or after in end) and (before is None or before not in end)
            out[index].update(kind="Applied edit" if applied else "Recorded change, not in the revision",
                              status="applied" if applied else "proposed")
    # Listed in the order they replayed, so revise.py, which undoes the applied edits newest first, meets each
    # edit's after-text before a later edit changed it.
    return [out[index] for index in [*took, *(i for i in range(len(out)) if i not in took)]]


TEXT_INPUTS = {".md", ".markdown", ".qmd", ".rmd", ".tex", ".txt"}


def clean_texts(run: Path, data: dict, snapshot: Path, original: Path, current: str,
                from_copy: bool = False) -> tuple[str, str, list[tuple[str, str, str]], str]:
    """recorded_changes' texts: the manuscript as revised and as reviewed, each other text input of the run (a
    supplement) as (file name, reviewed, revised), and the manuscript's file name; every one a clean copy. A file
    the run read that is gone since is taken as it was reviewed."""
    others = []
    for item in [] if from_copy else data.get("inputs", [])[1:]:
        source, copy = Path(item["original"]), run / item["snapshot"]
        if copy.suffix.lower() not in TEXT_INPUTS or not copy.is_file():
            continue
        reviewed = copy.read_text(encoding="utf-8")
        revised = source.read_text(encoding="utf-8") if source.is_file() else reviewed
        others.append((source.name, clean_copy(reviewed, copy), clean_copy(revised, source)))
    return (clean_copy(current, original), clean_copy(snapshot.read_text(encoding="utf-8"), snapshot), others,
            original.name)


def apply_merges(inventory: dict, merges: dict, out_dir: Path, base: Path) -> None:
    """Merge duplicates, apply verified corrections, dismiss flags, link edits and mark what the revision addressed."""
    findings = {f["id"]: f for f in inventory["findings"]}
    named = [m["keep"] for m in merges.get("merge", [])] + [i for m in merges.get("merge", []) for i in m["ids"]]
    named += [u["id"] for u in merges.get("update", [])] + [d["id"] for d in merges.get("dismiss", [])] + merges.get("addressed", [])
    if unknown := sorted(set(named) - set(findings)):
        raise ValueError(f"The merge file names IDs the run does not have: {', '.join(unknown)}")

    def rebase(items: list[dict]) -> list[dict]:
        return [{"path": relative(Path(e["path"]) if Path(e["path"]).is_absolute() else base / e["path"], out_dir),
                 "quote": e["quote"]} for e in items]

    alias: dict[str, str] = {}
    for merge in merges.get("merge", []):
        keep = findings[merge["keep"]]
        for other_id in merge["ids"]:
            alias[other_id] = merge["keep"]
            other = findings.pop(other_id)
            keep["skills"] = sorted(set(keep["skills"]) | set(other["skills"]))
            keep["evidence"] += [e for e in other["evidence"] if e not in keep["evidence"]]
            keep["sources"] += [s for s in other["sources"] if s not in keep["sources"]]
            if viz.SEVERITIES.index(other["severity"]) < viz.SEVERITIES.index(keep["severity"]):
                keep["severity"] = other["severity"]
            if other["assessment"] == "confirmed":
                keep["assessment"] = "confirmed"
            if other["stage"] != "unknown" and (keep["stage"] == "unknown" or viz.STAGES.index(other["stage"]) < viz.STAGES.index(keep["stage"])):
                keep["stage"] = other["stage"]
            keep["decision"] = keep["decision"] or other["decision"]
        for key in ("summary", "category", "section", "severity", "stage", "detail", "action", "assessment", "quote"):
            if key in merge:
                keep[key] = merge[key]
    for update in merges.get("update", []):
        record = findings[update["id"]]
        for key, value in update.items():
            if key == "evidence":
                record["evidence"] += rebase(value)
            elif key != "id":
                record[key] = value
    for dismissal in merges.get("dismiss", []):
        alias[dismissal["id"]] = ""
        record = findings.pop(dismissal["id"])
        inventory["dismissed"].append({"skill": record["skills"][0], "summary": f"{record['id']}: {record['summary']}",
                                       "why": dismissal["why"]})
    inventory["findings"] = list(findings.values())

    def resolve(ids: list[str]) -> list[str]:
        """A link to a merged record follows it to the record kept; a link to a dismissed flag is dropped."""
        out = []
        for fid in ids:
            while fid in alias and alias[fid]:
                fid = alias[fid]
            if fid in findings and fid not in out:
                out.append(fid)
        return out

    inventory["decisions"] = [{**d, "finding_ids": resolve(d.get("finding_ids", []))} for d in merges.get("decisions", [])]
    links = {link["change"]: link["finding_ids"] for link in merges.get("change_links", [])}
    for change in inventory["changes"]:
        change["finding_ids"] = resolve(links.get(change["id"], change.get("finding_ids", [])))
    for fid in merges.get("addressed", []):
        findings[fid]["resolution"] = "addressed"


def marks_path(data: dict, manuscript_copy: Path | None) -> Path | None:
    """Where the To-do tab's marks are kept: STEM.todo.json beside the manuscript, where runs.py handover puts the
    dashboard (a connected manuscript's in the project folder, named after its reading copy); for an older run with
    no snapshot, beside the reading copy given."""
    if data.get("inputs"):
        source = data["inputs"][0]
        original = Path(source["original"])
        root = data.get("context", {}).get("project_root")
        folder = Path(root) if source.get("remote") and root else original.parent
        return folder / f"{original.stem}.todo.json"
    return manuscript_copy.resolve().with_name(f"{manuscript_copy.stem}.todo.json") if manuscript_copy else None


def read_todo(path: Path | None, manuscript_name: str) -> dict | None:
    """The marks file as the inventory's `todo`: its name, never its folder, and its marks; no marks while the authors
    have saved none."""
    if path is None:
        return None
    if not path.is_file():
        return {"schema_version": 1, "manuscript": manuscript_name, "marks": [], "file": path.name}
    found = viz.MarksFile.model_validate_json(path.read_text(encoding="utf-8"))
    return {**found.model_dump(mode="json"), "manuscript": found.manuscript or manuscript_name, "file": path.name}


def restated(inventory: viz.Inventory) -> list[dict]:
    """For each mark of an earlier run, this run's items that say word for word what its item said: the problems and
    decisions the adjudication dismisses when the mark is redundant, the proposals revise.py holds, and the items the
    next run does when it is approved. A reworded one is for the adjudication to find."""
    if inventory.todo is None:
        return []
    items = viz.todo_items(inventory)
    out = []
    for mark in inventory.todo.marks:
        if mark.run_id == inventory.run_id:
            continue
        same = [f"{item['kind']} {item['id']}" for item in items if viz.restates(mark, item)]
        if same:
            out.append({"mark": viz.mark_key(mark.run_id, mark.kind, mark.id), "is": mark.mark, "reason": mark.reason,
                        "summary": mark.summary, "this_run": same})
    return out


def warnings_for(output: Path, merge: Path | None) -> list[str]:
    """An inventory collected without the adjudication that lies beside it would silently drop every merge,
    dismissal and decision: say so."""
    if merge is not None:
        return []
    found = viz.newest_attempt(output.resolve().parent / "merges.json", folder=False)
    out = []
    if found is not None:
        out.append(f"{found.name} is beside this inventory but --merge was not given, so its merges, dismissals and "
                   f"decisions are not in {output.name}. Collect the adjudicated inventory with --merge {found.name} "
                   "(and --reference, when there is one).")
    return out


@app.command()
def main(run: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
         output: Annotated[Path, typer.Option("--output", help="findings.draft.json for the draft; findings.json, "
                                                               "with --merge, for the adjudicated inventory")],
         merge: Annotated[Path | None, typer.Option(help="Adjudication: merges, updates, dismissals, decisions")] = None,
         reference: Annotated[Path | None, typer.Option(help="A review to compare with, with its matches; give it "
                                                             "together with --merge")] = None,
         manuscript_copy: Annotated[Path | None, typer.Option(
             "--manuscript", exists=True, dir_okay=False,
             help="A local reading copy of the manuscript, for a run whose manuscript is a connected document")] = None,
         todo: Annotated[Path | None, typer.Option(
             exists=True, dir_okay=False,
             help="The authors' to-do marks; default: STEM.todo.json beside the manuscript, when it is there")] = None,
         title: str = "What the manuscript review found",
         version: str = "",
         scope: str = "",
         limitation: Annotated[list[str] | None, typer.Option(help="A limitation to show; repeatable")] = None) -> None:
    run = run.resolve()
    if output.exists():
        typer.echo(f"{output.name} exists; write the next attempt as {viz.next_attempt(output, folder=False).name}.", err=True)
        raise typer.Exit(1)
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    if manuscript_copy is not None:
        snapshot = manuscript_copy.resolve()
        original, sha256 = str(snapshot), hashlib.sha256(snapshot.read_bytes()).hexdigest()
        current = snapshot.read_text(encoding="utf-8")
    elif data.get("inputs"):
        snapshot = run / data["inputs"][0]["snapshot"]
        original, sha256 = data["inputs"][0]["original"], data["inputs"][0]["sha256"]
        current = Path(original).read_text(encoding="utf-8") if Path(original).is_file() else snapshot.read_text(encoding="utf-8")
    else:
        typer.echo("This run holds no local copy of the manuscript: its source is a connected document, so there is no "
                   "text to quote. Export a reading copy to a local file (Markdown, LaTeX or plain text), register it "
                   "in the run (runs.py add RUN --skill manuscript-dashboard --file COPY --role other --name "
                   "reading-copy.md), and collect again with --manuscript COPY. A new run of a connected document "
                   "records its reading copy when it starts (runs.py start --reading-copy COPY).", err=True)
        raise typer.Exit(1)
    try:
        texts = clean_texts(run, data, snapshot, Path(original), current, from_copy=manuscript_copy is not None)
    except ValueError as exc:
        typer.echo(f"{exc}\nNothing was written.", err=True)
        raise typer.Exit(1) from exc
    if unreadable := contract_errors(run):
        typer.echo("These stages' findings files do not meet the stage-findings contract, so nothing was written. Write "
                   "each stage's next attempt (findings.2.json) with them fixed; uv run --script stage_check.py RUN "
                   "--skill SKILL checks one:\n" + "\n".join(unreadable), err=True)
        raise typer.Exit(1)
    marks = todo or marks_path(data, manuscript_copy)
    try:
        carried_marks = read_todo(marks, Path(original).name)
    except ValueError as exc:
        typer.echo(f"The authors' to-do marks in {marks.name} do not read, so nothing was written; the To-do tab writes "
                   f"them, so save them there again (or give --todo another file).\n{exc}", err=True)
        raise typer.Exit(1) from exc
    out_dir = output.resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    records = stage_records(run, out_dir, snapshot)
    # The coordinator is still running while it collects: it gets coverage only when it recorded findings itself.
    named = {skill for record in records["findings"] for skill in record["skills"]}
    skip = {COORDINATOR} if data["skills"].get(COORDINATOR, {}).get("status") not in TERMINAL and COORDINATOR not in named else set()
    statuses = {name: seat["status"] for name, seat in data["skills"].items() if name not in OWN and name not in skip}
    inventory: dict[str, Any] = {
        "schema_version": 2, "title": title, "run_id": data["run_id"],
        "scope": scope or f"Whole-manuscript run started {data['started_at'][:10]}; skills: "
                          + ", ".join(f"{k.removeprefix('manuscript-')} {STATUS_WORDS.get(v, v)}" for k, v in statuses.items()) + ".",
        "coverage": coverage(run, data, out_dir, skip), "findings": records["findings"],
        "changes": records["changes"] + recorded_changes(run, data, out_dir, *texts),
        "limitations": limitation or [], "manuscript": manuscript(snapshot, original, sha256, version, out_dir),
        "signals": signals(run), "dismissed": records["dismissed"],
        "not_checked": records["not_checked"] + ladder_gaps(run, data),
        "decisions": [], "panel": panel(run, data), "reference": None, "venues": venues(run, data),
        "story": story(run), "figures": figures(run, out_dir), "reference_list": reference_list(run, data.get("inputs")),
        "coauthors": coauthors(run),
        "todo": carried_marks,
    }
    mentions = concern_mentions(inventory["findings"])
    if merge:
        try:
            apply_merges(inventory, json.loads(merge.read_text(encoding="utf-8")), out_dir, merge.resolve().parent)
        except (KeyError, ValueError) as exc:
            typer.echo(f"The merge file could not be applied; nothing was written.\n{exc}", err=True)
            raise typer.Exit(1) from exc
    link_concerns(inventory, mentions)
    link_figures(inventory)
    link_coauthors(inventory)
    if reference:
        ref = json.loads(reference.read_text(encoding="utf-8"))
        source = ref["source"]
        path = Path(source["path"]) if Path(source["path"]).is_absolute() else reference.resolve().parent / source["path"]
        inventory["reference"] = {**ref, "source": {"path": relative(path, out_dir), "quote": source["quote"]}}
    try:
        checked = viz.Inventory.model_validate(inventory)
        viz.verify_evidence(checked, out_dir)
    except ValueError as exc:
        typer.echo(f"The draft inventory does not validate; nothing was written.\n{exc}", err=True)
        raise typer.Exit(1) from exc
    output.write_text(json.dumps(checked.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = viz.summarize(checked)
    warnings = warnings_for(output, merge)
    for warning in warnings:
        typer.echo(f"Warning: {warning}", err=True)
    carried = {"todo": {"file": checked.todo.file, "marks": len(checked.todo.marks), "restated": restated(checked)}} if checked.todo else {}
    typer.echo(json.dumps({"output": str(output.resolve()), "counts": summary["counts"], "signals": summary["signals"],
                           "benchmark": summary["benchmark"], **carried, **({"warnings": warnings} if warnings else {})}, indent=2))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
