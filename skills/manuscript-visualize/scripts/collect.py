# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "pyyaml>=6"]
# ///
"""Draft the dashboard inventory from a manuscript-skills run, so nothing the run recorded is dropped.

    uv run --script collect.py RUN --output RUN/manuscript-visualize/findings.json
    uv run --script collect.py RUN --output OUT.json --merge merges.json --reference reference.json

It reads run.json for coverage, the manuscript snapshot for its title and sections, every skill's
findings.json (../references/stage-findings.md), the check outputs as raw signal counts, the reader
reports, the referees' recommendations and the recorded before/after changes. A recorded change counts
as applied only when its after-text is in the current manuscript and its before-text is not; otherwise it
is a proposal.

The merge file is the adjudication: which records describe one problem, which a reviewer verified,
corrected or dismissed, and the decisions for the authors. Collect never makes those calls; it applies
them, keeps every source ID and refuses an inventory that does not validate.
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

import infographic as viz

SEVERITY = {"blocker": "blocker", "serious": "blocker", "major": "major", "important": "major", "minor": "minor",
            "optional": "minor", "info": "info", "uncertain": "unknown", "unknown": "unknown"}
TERMINAL = {"completed", "partial", "blocked", "not_run", "reused"}
PREFIX = {"manuscript-integrity-check": "IC", "manuscript-reference-check": "RF", "manuscript-reporting-check": "RP",
          "manuscript-peer-review": "PR", "manuscript-policy-fit": "PF", "manuscript-journal-select": "JS",
          "manuscript-journal-adapt": "JA", "manuscript-prose-edit": "PE", "manuscript-deslop": "DS",
          "manuscript-story": "ST", "manuscript-improve": "IM", "manuscript-reviewer-response": "RR",
          "manuscript-revision-marks": "RM", "manuscript-mark-people": "MP"}
SKIP = {"findings.json", "merges.json"}
CHANGE_FIELDS = ("id", "kind", "section", "summary", "status", "finding_ids", "before", "after", "evidence")
app = typer.Typer(add_completion=False)


def relative(path: Path, out_dir: Path) -> str:
    return os.path.relpath(path.resolve(), out_dir.resolve())


def heading(line: str) -> str | None:
    if match := re.match(r"^#{1,4}\s+(.+?)\s*#*\s*$", line):
        return re.sub(r"[*_`]", "", match.group(1)).strip()
    if match := re.match(r"^\\(?:sub)*section\*?\{(.+)\}", line):
        return match.group(1).strip()
    return None


def manuscript(run: Path, data: dict, version: str, out_dir: Path) -> dict | None:
    if not data["inputs"]:
        return None
    source = data["inputs"][0]
    names = [name for line in (run / source["snapshot"]).read_text(encoding="utf-8").splitlines() if (name := heading(line))]
    return {"title": names[0] if names else Path(source["original"]).name, "version": version,
            "sha256": source["sha256"], "sections": names[1:], "path": relative(run / source["snapshot"], out_dir)}


def coverage(run: Path, data: dict, out_dir: Path) -> list[dict]:
    rows = []
    for name, seat in data["skills"].items():
        if name == "manuscript-visualize":
            continue
        status = seat["status"]
        rows.append({"skill": name, "status": status if status in TERMINAL else "unknown",
                     "note": seat.get("reason") or f"Recorded status: {status}.",
                     "evidence": [{"path": relative(run / name / "README.md", out_dir), "quote": f"Status: **{status}**."}]})
    return rows


def stage_records(run: Path, out_dir: Path, snapshot: Path) -> dict[str, list]:
    """Every skill's findings.json, with evidence paths rebased onto the inventory's folder."""
    found: dict[str, list] = {"findings": [], "dismissed": [], "not_checked": [], "changes": []}
    seen: set[str] = set()
    for path in sorted(run.glob("manuscript-*/findings.json")):
        skill, folder = path.parent.name, path.parent
        if skill == "manuscript-visualize":
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
            found["findings"].append({
                "id": fid, "category": record.get("category") or "Uncategorised",
                "section": record.get("section") or "Whole manuscript", "summary": record["summary"],
                "severity": SEVERITY.get(str(record.get("severity", "unknown")).lower(), "unknown"),
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
            known = {k: record[k] for k in CHANGE_FIELDS if k in record}
            extra = [f"{k.replace('_', ' ')}: {v}" for k, v in record.items() if k not in CHANGE_FIELDS and v not in (None, "", False, [])]
            if extra:
                known["summary"] = f"{known.get('summary', '')} ({'; '.join(map(str, extra))})".strip()
            found["changes"].append({**known, "evidence": rebase(record.get("evidence") or [])})
    return found


def signals(run: Path) -> list[dict]:
    """Raw output counts: scanner and checker hits by check, referee proposals, reader concerns."""
    rows = []
    for path in sorted(run.glob("manuscript-*/**/*.json")):
        if path.name in SKIP or "commands" in path.parts or path.relative_to(run).parts[0] == "manuscript-visualize":
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


def panel(run: Path) -> dict:
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
                        "round": path.parent.name if path.parent.name != "readers" else ""})
    recommendations = []
    for path in sorted(run.glob("manuscript-peer-review/**/*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("reports"), list):
            continue
        for report in doc["reports"]:
            for rec in report.get("recommendations", []):
                if rec.get("recommendation") in {"accept", "minor-revision", "major-revision", "reject"}:
                    recommendations.append({"seat": report.get("seat", "referee"), "venue": rec["venue"],
                                            "recommendation": rec["recommendation"], "reason": rec.get("reason") or "No reason given."})
        if recommendations:
            break
    return {"readers": readers, "recommendations": recommendations}


def number(text: str | None) -> float | None:
    try:
        return float(text) if text not in (None, "") else None
    except ValueError:
        return None


def venues(run: Path) -> list[dict]:
    """The journal and preprint ladders manuscript-journal-select wrote, in the order it chose."""
    folder = run / "manuscript-journal-select"
    top = json.loads((folder / "top3.json").read_text(encoding="utf-8")) if (folder / "top3.json").is_file() else []
    chosen = {entry.get("key") or entry.get("name"): entry for entry in top}
    rows = []
    for ladder in ("journals", "preprints"):
        files = [f for f in sorted(folder.glob(f"*.{ladder.rstrip('s')}-ladder.csv")) if not re.search(r"-ladder-\w+\.csv$", f.name)]
        if not files:
            continue
        with files[0].open(encoding="utf-8") as handle:
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
                             "ai_tier": row.get("ai_tier") or "", "ai_for_this_use": row.get("ai_for_this_use") or "", "fee": fee,
                             "preprint_rule": row.get("preprint_rule") or "", "why": (pick or {}).get("why", ""),
                             "url": row.get("guidelines_url") or (pick or {}).get("url", "")})
    return rows


def recorded_changes(run: Path, data: dict, out_dir: Path, current: str) -> list[dict]:
    """runs.py change records; applied only when the revised manuscript holds the after-text and not the before-text."""
    out = []
    for skill, seat in data["skills"].items():
        for number, change in enumerate(seat["changes"], 1):
            path = run / change["path"]
            text = path.read_text(encoding="utf-8")
            parts = re.match(r"# (.*?)\n\nReason: (.*?)\n\n## Before\n\n(.*)\n\n## After\n\n(.*)\Z", text, re.S)
            if not parts:
                continue
            section, reason, before, after = parts.groups()
            before = None if before.strip() == "(No previous block.)" else before.strip()
            after = None if after.strip() == "(Block removed.)" else after.strip()
            applied = (after is None or after in current) and (before is None or before not in current)
            out.append({"id": f"{skill.removeprefix('manuscript-')}.C{number}", "kind": "Applied edit" if applied else "Recorded change, not in the revision", "section": section,
                        "summary": reason, "status": "applied" if applied else "proposed", "finding_ids": [],
                        "before": before, "after": after, "evidence": [{"path": relative(path, out_dir), "quote": (after or before)[:200]}]})
    return out


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


@app.command()
def main(run: Annotated[Path, typer.Argument(exists=True, file_okay=False)],
         output: Annotated[Path, typer.Option("--output")],
         merge: Annotated[Path | None, typer.Option(help="Adjudication: merges, updates, dismissals, decisions")] = None,
         reference: Annotated[Path | None, typer.Option(help="A review to compare with, with its matches")] = None,
         title: str = "What the manuscript review found",
         version: str = "",
         scope: str = "",
         limitation: Annotated[list[str] | None, typer.Option(help="A limitation to show; repeatable")] = None) -> None:
    run = run.resolve()
    if output.exists():
        typer.echo(f"{output} exists; write the next attempt under a new name.", err=True)
        raise typer.Exit(1)
    out_dir = output.resolve().parent
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    snapshot = run / data["inputs"][0]["snapshot"]
    original = Path(data["inputs"][0]["original"])
    current = original.read_text(encoding="utf-8") if original.is_file() else snapshot.read_text(encoding="utf-8")
    records = stage_records(run, out_dir, snapshot)
    statuses = {name: seat["status"] for name, seat in data["skills"].items() if name != "manuscript-visualize"}
    inventory: dict[str, Any] = {
        "schema_version": 2, "title": title, "run_id": data["run_id"],
        "scope": scope or f"Whole-manuscript run started {data['started_at'][:10]}; skills: "
                          + ", ".join(f"{k.removeprefix('manuscript-')} {v}" for k, v in statuses.items()) + ".",
        "coverage": coverage(run, data, out_dir), "findings": records["findings"],
        "changes": records["changes"] + recorded_changes(run, data, out_dir, current),
        "limitations": limitation or [], "manuscript": manuscript(run, data, version, out_dir),
        "signals": signals(run), "dismissed": records["dismissed"], "not_checked": records["not_checked"],
        "decisions": [], "panel": panel(run), "reference": None, "venues": venues(run),
    }
    if merge:
        try:
            apply_merges(inventory, json.loads(merge.read_text(encoding="utf-8")), out_dir, merge.resolve().parent)
        except (KeyError, ValueError) as exc:
            typer.echo(f"The merge file could not be applied; nothing was written.\n{exc}", err=True)
            raise typer.Exit(1) from exc
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
    typer.echo(json.dumps({"output": str(output.resolve()), "counts": summary["counts"], "signals": summary["signals"],
                           "benchmark": summary["benchmark"]}, indent=2))


if __name__ == "__main__":
    app()
