# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "httpx>=0.27", "pydantic>=2.6", "pyyaml>=6"]
# ///
"""Choose reporting guidelines by study design, print an item-audit table to fill, and validate the data file.

The data is references/guidelines.yaml; the design keys are those of
manuscript-integrity-check/references/manuscript-record.md; venue rules come from venues.yaml through the
same reader check_availability.py uses.

    uv run --script guidelines.py select --design genetic-association --design observational-human
    uv run --script guidelines.py select --record manuscript-record.yaml          # designs and venue from it
    uv run --script guidelines.py select --design software-tool --venue bioinformatics-note --json sel.json
    uv run --script guidelines.py items strega --manuscript paper.md --md audit.md
    uv run --script guidelines.py list
    uv run --script guidelines.py designs                                         # the design keys
    uv run --script guidelines.py validate --max-age-days 365

Exit codes: 0 success; 1 validate found a problem; 2 usage error (unknown design key, guideline or venue).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Optional

import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)

HERE = Path(__file__).resolve().parent
GUIDELINES_YAML = HERE.parent / "references" / "guidelines.yaml"
RECORD_MD = HERE.parents[1] / "manuscript-integrity-check" / "references" / "manuscript-record.md"
KINDS = {"reporting-guideline", "extension", "minimum-information", "venue-checklist"}
STATUSES = {"verified", "unverified", "withdrawn"}
STATES = "present, partial, missing, not applicable, or unclear (material not supplied)"
# Where a missing item goes in the report (author-priorities.md, "Order the work by when it can be done").
STAGE_RULE = ("A missing item belongs under \"Once you have chosen the journal\" in the report, unless its absence "
              "shows missing science (an analysis, comparison, correction or method the conclusions need), "
              "which belongs under \"Fix now\".")
KIND_WORDS = {"reporting-guideline": "a reporting guideline", "minimum-information": "a minimum-information "
              "standard", "venue-checklist": "the journal's own checklist"}


def _availability_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_reporting_check_availability", HERE / "check_availability.py")
    if spec is None or spec.loader is None:
        raise typer.BadParameter("cannot load check_availability.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_reporting_check_availability"] = module
    spec.loader.exec_module(module)
    return module


def design_table() -> list[tuple[str, str]]:
    """The shared study-design keys with what each covers, read from the table in manuscript-record.md."""
    text = RECORD_MD.read_text(encoding="utf-8")
    section = text.split("## Study-design keys", 1)[1].split("\n## ", 1)[0]
    return [(k, v.strip()) for k, v in re.findall(r"^\|\s*`([a-z0-9-]+)`\s*\|([^|\n]*)\|", section, re.MULTILINE)]


def design_keys() -> list[str]:
    """The shared study-design keys, read from the table in manuscript-record.md."""
    return [k for k, _ in design_table()]


DESIGN_HELP = ("Study-design key from manuscript-record.md; repeatable. One of: "
               + (", ".join(design_keys()) if RECORD_MD.exists() else "see `guidelines.py designs`"))


def load() -> dict[str, Any]:
    return yaml.safe_load(GUIDELINES_YAML.read_text(encoding="utf-8"))


def by_id(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {g["id"]: g for g in data["guidelines"]}


def _label(g: dict[str, Any]) -> str:
    name, version = str(g["name"]), str(g.get("version") or "").split()
    first = version[0].rstrip(",;") if version else ""
    return name if not re.match(r"\d", first) or first in name else f"{name} {first}"


def _source(g: dict[str, Any]) -> str:
    """The guideline's official pages as full URLs (a DOI as https://doi.org/...), for the authors to open."""
    s = g.get("sources") or {}
    parts = [s.get("equator"), f"https://doi.org/{s['paper_doi']}" if s.get("paper_doi") else None, s.get("checklist_url")]
    urls = [p for p in parts if p]
    return (urls[0] if len(urls) == 1 else ", ".join(urls[:-1]) + " and " + urls[-1]) if urls else "no source recorded"


def _venue_checklist_matches(g: dict[str, Any], venue: Any) -> bool:
    match = g.get("match") or {}
    return (any(re.search(p, venue.key) for p in match.get("keys") or [])
            or any(re.search(p, venue.publisher) for p in match.get("publishers") or []))


def select_guidelines(designs: list[str], venue_key: Optional[str] = None) -> dict[str, Any]:
    """Candidates for the designs: guidelines that apply, ones whose condition the authors confirm first, the
    base of every selected extension, venue checklists for the target venue only, and notes for designs that
    have no guideline."""
    known = design_keys()
    unknown = [d for d in designs if d not in known]
    if unknown:
        raise typer.BadParameter(f"unknown design key(s) {', '.join(unknown)}; known: {', '.join(known)} "
                                 "(`guidelines.py designs` lists what each covers)")
    data = load()
    index = by_id(data)
    apply: list[dict[str, Any]] = []
    conditional: list[dict[str, Any]] = []
    for g in data["guidelines"]:
        if g["kind"] == "venue-checklist" or g.get("status") == "withdrawn":
            continue
        matched = [d for d in designs if d in (g.get("designs") or [])]
        if not matched:
            continue
        entry = _summary(g) | {"matched": matched}
        (conditional if g.get("applies_if") else apply).append(entry)
    for group in (apply, conditional):
        for entry in list(group):
            base = index[entry["id"]].get("extends")
            mode = index[entry["id"]].get("base_items")
            if base and mode != "none" and not any(e["id"] == base for e in apply + conditional):
                group.append(_summary(index[base]) | {"matched": [], "base_of": entry["id"]})
    venue_info: Optional[dict[str, Any]] = None
    checklists: list[dict[str, Any]] = []
    if venue_key:
        venue = _availability_module().venue_rules(venue_key)
        named = [r for r in venue.rules if re.search(r"checklist|reporting summary|STROBE|STREGA|CONSORT|PRISMA|ARRIVE|"
                                                     r"STARD|TRIPOD|MDAR|EQUATOR", r, re.IGNORECASE)]
        venue_info = {"key": venue.key, "name": venue.name, "url": venue.url, "checked": venue.checked,
                      "reporting_checklist": venue.reporting_checklist, "rules": named}
        for g in data["guidelines"]:
            if g["kind"] == "venue-checklist" and _venue_checklist_matches(g, venue):
                checklists.append(_summary(g) | {"withdrawn": g.get("status") == "withdrawn"})
    notes = {d: data["design_notes"][d] for d in designs if d in (data.get("design_notes") or {})}
    return {"designs": designs, "venue": venue_info, "apply": apply, "confirm_first": conditional,
            "venue_checklists": checklists, "notes": notes}


def _summary(g: dict[str, Any]) -> dict[str, Any]:
    return {"id": g["id"], "name": _label(g), "kind": g["kind"], "extends": g.get("extends"),
            "applies_if": g.get("applies_if"), "note": g.get("note"), "source": _source(g), "licence": g.get("licence"),
            "checked": str(g.get("checked")), "status": g.get("status"), "items": len(g.get("items") or [])}


def _design_words(keys: list[str]) -> str:
    """The designs as the shared table describes them, each key in parentheses."""
    covers = dict(design_table()) if RECORD_MD.exists() else {}

    def phrase(k: str) -> str:
        text = covers.get(k, k).rstrip(".")
        return text[:1].lower() + text[1:] if text[1:2].islower() else text

    return "; ".join(f"{phrase(k)} ({k})" for k in keys)


def _entry_markdown(e: dict[str, Any], index: dict[str, dict[str, Any]], applies: bool = False) -> str:
    kind = (f"an extension of {_label(index[e['extends']])}" if e["kind"] == "extension" and e.get("extends") in index
            else KIND_WORDS.get(e["kind"], e["kind"]))
    why = (f" It comes in as the base of {_label(index[e['base_of']])}." if e.get("base_of") else
           f" It {'applies' if applies else 'is a candidate'} because of the design: {_design_words(e['matched'])}."
           if e.get("matched") else "")
    cond = (f" It applies only if {e['applies_if'].rstrip('.')}." if e.get("applies_if") else "") + (
        f" {e['note'].strip()}" if e.get("note") else "")
    withdrawn = " It has been withdrawn, so the authors are not asked for it." if e.get("withdrawn") else ""
    unverified = " Part of this entry could not be confirmed online." if e["status"] == "unverified" else ""
    return (f"- **{e['name']}** ({e['id']}) is {kind}.{why}{cond}{withdrawn} The official text is at {e['source']}; "
            f"its licence is recorded as “{e['licence']}”, checked on {e['checked']}.{unverified}")


def selection_markdown(sel: dict[str, Any]) -> str:
    index = by_id(load())
    out = ["# Reporting guidelines for this study", "", f"Study designs considered: {_design_words(sel['designs'])}.", ""]
    v = sel["venue"]
    if v:
        page = f" ({v['url']})" if v.get("url") else ""
        if v["reporting_checklist"]:
            out += [f"The rules recorded for {v['name']} on {v['checked']} ask for a reporting checklist: "
                    + "; ".join(f"“{r}”" for r in v["rules"]) + f". Check this on the journal's page{page}; a missing "
                    "item can then cost an editorial query or a return.", ""]
        else:
            out += [f"The rules recorded for {v['name']} on {v['checked']} name no reporting checklist. Read the "
                    f"journal's page{page} before treating any guideline as required; until then, missing items are "
                    "optional advice.", ""]
    else:
        out += ["No journal is chosen yet, so missing items are optional advice until a journal's rule makes a "
                "guideline required.", ""]
    out += [STAGE_RULE, ""]

    def block(title: str, entries: list[dict[str, Any]], applies: bool = False) -> None:
        if entries:
            out.extend([f"## {title}", "", *[_entry_markdown(e, index, applies) for e in entries], ""])

    block("Apply", sel["apply"], applies=True)
    block("Confirm the condition first", sel["confirm_first"])
    block("The journal's own checklists", sel["venue_checklists"])
    if sel["notes"]:
        out += ["## Designs without a guideline of their own", ""]
        out += [f"- {_design_words([k])}. {v.strip()}" for k, v in sel["notes"].items()]
        out.append("")
    if not (sel["apply"] or sel["confirm_first"]):
        out += ["No bundled reporting guideline matches these designs, and none is invented here: the availability "
                "and reproducibility checks carry the weight instead.", ""]
    return "\n".join(out)


def _natural(n: str) -> tuple[Any, ...]:
    return tuple(int(p) if p.isdigit() else p for p in re.findall(r"\d+|\D+", str(n)))


def audit_rows(gid: str) -> list[dict[str, str]]:
    """The items to audit for one guideline, with its base's items when an extension keeps them."""
    index = by_id(load())
    if gid not in index:
        raise typer.BadParameter(f"unknown guideline {gid!r}; known: {', '.join(sorted(index))}")
    g = index[gid]
    own = [{"guideline": _label(g), **{k: str(v) for k, v in item.items()}} for item in g.get("items") or []]
    base_id, mode = g.get("extends"), g.get("base_items")
    if not base_id or mode == "none":
        return own
    base = [{"guideline": _label(index[base_id]), **{k: str(v) for k, v in item.items()}}
            for item in index[base_id].get("items") or []]
    if mode == "interleave":
        return sorted(base + own, key=lambda r: (_natural(r["n"]), r["guideline"] != _label(index[base_id])))
    return base + own


def items_markdown(gid: str, manuscript: Optional[Path]) -> str:
    index = by_id(load())
    g = index.get(gid)
    rows = audit_rows(gid)
    if g is None:
        raise typer.BadParameter(f"unknown guideline {gid!r}")
    ident = ""
    if manuscript:
        ident = (f"Manuscript: {manuscript.name} (sha256 {hashlib.sha256(manuscript.read_bytes()).hexdigest()[:16]}), "
                 f"table generated {date.today().isoformat()}. ")
    out = [f"# Item audit: {_label(g)}" + (f" with {_label(index[g['extends']])}" if g.get("extends")
                                            and g.get("base_items") != "none" else ""), "",
           ident + f"The items are paraphrased in our own words; the official checklist is at {_source(g)} "
           f"(its licence is recorded as “{g.get('licence')}”). When the journal asks for its form, give the authors "
           "the answers keyed by the official item numbers (where in the manuscript, a short quote) to transfer; "
           "never reproduce the form's text.", "",
           f"Fill one row per item. Reported: {STATES}. Where: the section and a short quote of the sentence that "
           "reports it, with the line only in parentheses; for a missing item, where you looked. When to fix: "
           + STAGE_RULE[:1].lower() + STAGE_RULE[1:], "",
           "| What to report | Guideline (item) | Topic | Reported | Where, with a short quote | When to fix | Note |",
           "|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['text']} | {r['guideline']} (item {r['n']}) | {r.get('topic', '')} |  |  |  |  |")
    if not rows:
        out.append(f"| No items are bundled: key the answers to the item numbers of the official form at {_source(g)} "
                   f"| {_label(g)} |  |  |  |  |  |")
    return "\n".join(out) + "\n"


def validate_data(max_age_days: Optional[int] = None, today: Optional[date] = None) -> tuple[list[str], list[str]]:
    """Schema problems (errors) and stale entries (warnings)."""
    data = load()
    keys = set(design_keys())
    errors: list[str] = []
    warnings: list[str] = []
    today = today or date.today()
    ids = [g.get("id") for g in data.get("guidelines") or []]
    index = {g.get("id"): g for g in data.get("guidelines") or []}
    if len(ids) != len(set(ids)):
        errors.append("duplicate guideline ids")
    for k in data.get("design_notes") or {}:
        if k not in keys:
            errors.append(f"design_notes: unknown design key {k!r}")
    for g in data.get("guidelines") or []:
        gid = g.get("id", "?")
        for field in ("id", "name", "version", "kind", "scope", "sources", "licence", "licence_basis", "checked",
                      "status", "verification"):
            if not g.get(field):
                errors.append(f"{gid}: missing {field}")
        if g.get("kind") not in KINDS:
            errors.append(f"{gid}: kind {g.get('kind')!r} not in {sorted(KINDS)}")
        if g.get("status") not in STATUSES:
            errors.append(f"{gid}: status {g.get('status')!r} not in {sorted(STATUSES)}")
        sources = g.get("sources") or {}
        if not any(sources.get(k) for k in ("equator", "paper_doi", "checklist_url")):
            errors.append(f"{gid}: no primary source (equator, paper_doi or checklist_url)")
        for k, url in sources.items():
            if k != "paper_doi" and url and not str(url).startswith("https://"):
                errors.append(f"{gid}: sources.{k} is not an https URL")
        if sources.get("paper_doi") and not re.fullmatch(r"10\.\d{4,9}/\S+", str(sources["paper_doi"])):
            errors.append(f"{gid}: paper_doi {sources['paper_doi']!r} is not a DOI")
        checked = g.get("checked")
        if not isinstance(checked, date):
            errors.append(f"{gid}: checked is not a date")
        elif max_age_days is not None and (today - checked).days > max_age_days:
            warnings.append(f"{gid}: checked {checked}, more than {max_age_days} days ago")
        designs = g.get("designs")
        if not isinstance(designs, list):
            errors.append(f"{gid}: designs must be a list")
            designs = []
        for d in designs:
            if d not in keys:
                errors.append(f"{gid}: unknown design key {d!r}")
        if g.get("kind") == "venue-checklist":
            if designs:
                errors.append(f"{gid}: a venue checklist is chosen by venue, not by design")
            if not (g.get("match") or {}).get("keys") and not (g.get("match") or {}).get("publishers"):
                errors.append(f"{gid}: venue checklist without a match rule")
        else:
            if not designs:
                errors.append(f"{gid}: no design keys")
            if not g.get("items"):
                errors.append(f"{gid}: no items")
        if g.get("extends"):
            if g["extends"] not in index:
                errors.append(f"{gid}: extends unknown guideline {g['extends']!r}")
            if g.get("base_items") not in ("interleave", "append", "none"):
                errors.append(f"{gid}: an extension needs base_items: interleave | append | none")
        seen: set[str] = set()
        for item in g.get("items") or []:
            n = str(item.get("n", ""))
            if not n or not item.get("text"):
                errors.append(f"{gid}: an item lacks n or text")
            if n in seen:
                errors.append(f"{gid}: item {n} repeats")
            seen.add(n)
            if len(str(item.get("text", "")).split()) > 30:
                errors.append(f"{gid}: item {n} is long for a paraphrase (over 30 words)")
    return errors, warnings


@app.command()
def select(
    design: Annotated[Optional[list[str]], typer.Option(help=DESIGN_HELP)] = None,
    venue: Annotated[Optional[str], typer.Option(help="Venue key from venues.yaml")] = None,
    record: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False,
                                                   help="manuscript-record.yaml: designs and venue from it")] = None,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the selection as JSON")] = None,
) -> None:
    """Guidelines for the study's designs, with the venue's checklist rule when a venue is known."""
    designs = list(design or [])
    if record:
        data = yaml.safe_load(record.read_text(encoding="utf-8")) or {}
        designs = designs or list(((data.get("study") or {}).get("designs")) or [])
        venue = venue or ((data.get("venue") or {}).get("key") if isinstance(data.get("venue"), dict) else None)
    if not designs:
        raise typer.BadParameter("give at least one --design (or a record with study.designs)")
    sel = select_guidelines(designs, venue)
    if json_out:
        json_out.write_text(json.dumps(sel, indent=2), encoding="utf-8")
    typer.echo(selection_markdown(sel))


@app.command()
def items(
    guideline: Annotated[str, typer.Argument(help="Guideline id (see `list`)")],
    manuscript: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False,
                                                       help="Record the manuscript's sha256 in the table header")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the table here (default: stdout)")] = None,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the rows as JSON")] = None,
) -> None:
    """An item-audit table to fill: one row per item, with empty state and location columns."""
    md = items_markdown(guideline, manuscript)
    if json_out:
        json_out.write_text(json.dumps(audit_rows(guideline), indent=2), encoding="utf-8")
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {md_out}")
    else:
        typer.echo(md)


@app.command()
def designs() -> None:
    """The study-design keys select accepts (manuscript-record.md's list), with what each covers."""
    for key, covers in design_table():
        typer.echo(f"{key:<26} {covers}")


@app.command("list")
def list_guidelines() -> None:
    """Every bundled guideline with its version, kind and designs."""
    for g in load()["guidelines"]:
        typer.echo(f"{g['id']:<36} {_label(g):<40} {g['kind']:<20} {', '.join(g.get('designs') or []) or '(by venue)'}"
                   + ("  [withdrawn]" if g.get("status") == "withdrawn" else ""))


@app.command()
def validate(
    max_age_days: Annotated[Optional[int], typer.Option(help="Warn about entries checked longer ago than this")] = None,
) -> None:
    """Check guidelines.yaml against its schema and the shared design keys."""
    errors, warnings = validate_data(max_age_days)
    for w in warnings:
        typer.echo(f"stale: {w}")
    for e in errors:
        typer.echo(f"error: {e}")
    typer.echo(f"{len(load()['guidelines'])} entries; {len(errors)} errors; {len(warnings)} stale")
    raise typer.Exit(code=1 if errors else 0)


if __name__ == "__main__":
    app()
