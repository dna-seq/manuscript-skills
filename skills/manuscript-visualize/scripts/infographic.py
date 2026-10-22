# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "vl-convert-python>=1.9,<2", "markdown-it-py>=3"]
# ///
"""Render evidence-linked review findings and edits as an offline dashboard and a Vega-Lite infographic.

    uv run --script infographic.py findings.json --output-dir infographic

`dashboard.html` is one self-contained file: headline counts, review coverage, the funnel from raw signals
to distinct findings, cross-filtered breakdowns, where in the manuscript the findings sit, which skills
found the same problem, every finding with its evidence, the edits as word-level diffs, the reader and
referee panels and, when a reference review is supplied, which of its problems the run caught.
`annotated.html` is the manuscript itself with every quoted problem highlighted in red by severity and
explained in a margin comment. `infographic.svg` and `.png` are the static summary for slides.

Counts are derived from distinct adjudicated records, never supplied headline totals. Evidence checks
establish local file/quotation identity, not scientific support or correctness of the adjudication.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import textwrap
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identity = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]
SEVERITIES = ("blocker", "major", "minor", "info", "unknown")
STAGES = ("now", "writing", "journal", "final", "unknown")
ASSETS = Path(__file__).resolve().parents[1] / "assets"
TEMPLATE = ASSETS / "dashboard.html"
app = typer.Typer(add_completion=False)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Record):
    path: Text
    quote: Annotated[str, Field(min_length=1)]


class Coverage(Record):
    skill: Text
    status: Literal["completed", "partial", "blocked", "not_run", "reused", "unknown"]
    note: Text
    evidence: Annotated[list[Evidence], Field(min_length=1)]


class Source(Record):
    """One raw record a finding merges: a seat's finding, a scan hit, a reader's concern."""
    skill: Text
    id: Text


class Finding(Record):
    id: Identity
    category: Text
    section: Text
    summary: Text
    severity: Literal["blocker", "major", "minor", "info", "unknown"]
    assessment: Literal["confirmed", "candidate", "dismissed"]
    resolution: Literal["open", "addressed", "unknown"]
    skills: Annotated[list[Text], Field(min_length=1)]
    evidence: Annotated[list[Evidence], Field(min_length=1)]
    stage: Literal["now", "writing", "journal", "final", "unknown"] = "unknown"
    quote: str | None = None
    detail: str = ""
    action: str = ""
    decision: bool = False
    sources: list[Source] = Field(default_factory=list)


class Change(Record):
    id: Identity
    kind: Text
    section: Text
    summary: Text
    status: Literal["applied", "proposed"]
    finding_ids: list[Identity] = Field(default_factory=list)
    before: str | None = None
    after: str | None = None
    evidence: Annotated[list[Evidence], Field(min_length=1)]

    @model_validator(mode="after")
    def has_text(self) -> Change:
        if not any(text and text.strip() for text in (self.before, self.after)):
            raise ValueError(f"Change {self.id} needs before or after text.")
        return self


class Signal(Record):
    """Raw output screened before adjudication: scanner hits, seat findings proposed, reader concerns."""
    skill: Text
    check: Text
    count: Annotated[int, Field(ge=0)]
    note: str = ""


class Dismissed(Record):
    skill: Text
    summary: Text
    why: Text


class NotChecked(Record):
    skill: Text
    check: Text
    why: Text
    leaves_open: str = ""


class Decision(Record):
    id: Identity
    summary: Text
    finding_ids: list[Identity] = Field(default_factory=list)


class Recommendation(Record):
    seat: Text
    venue: Text
    recommendation: Literal["accept", "minor-revision", "major-revision", "reject"]
    reason: Text


class Step(Record):
    section: Text
    how: Literal["read", "skimmed", "skipped"] = "read"


class Reader(Record):
    seat: Text
    takeaway: Text
    stopped_at: Text
    next: str = ""
    left: str = ""  # the section where a real reader would close the paper, "finished", or "" when not recorded
    dips: list[Text] = Field(default_factory=list)  # sections where attention dropped and came back
    round: str = ""  # which panel, when a run has more than one
    path: list[Step] = Field(default_factory=list)  # the sections in the order the reader visited them


class Panel(Record):
    recommendations: list[Recommendation] = Field(default_factory=list)
    readers: list[Reader] = Field(default_factory=list)


class Manuscript(Record):
    title: Text
    version: str = ""
    sha256: str = ""
    sections: list[Text] = Field(default_factory=list)
    path: str = ""  # the reviewed text, relative to the inventory, for the annotated copy


MISS_REASONS = ("no-skill-covers", "skill-did-not-look", "judged-differently", "input-missing",
                "wording-preference", "later-decision")


class ReferenceItem(Record):
    id: Identity
    origin: Text
    summary: Text
    category: Text
    section: str = ""
    kind: str = ""
    substantive: bool = True
    # For an item the run did not catch in full: why, and the skill whose remit covers it.
    miss_reason: Literal["no-skill-covers", "skill-did-not-look", "judged-differently", "input-missing",
                         "wording-preference", "later-decision"] | None = None
    miss_note: str = ""
    owner: str = ""


class Match(Record):
    reference_id: Identity
    finding_ids: Annotated[list[Identity], Field(min_length=1)]
    match: Literal["full", "partial"]
    note: Text


class Reference(Record):
    """A review the run is compared with, such as a human referee's comments on the same version."""
    title: Text
    description: Text
    source: Evidence
    items: Annotated[list[ReferenceItem], Field(min_length=1)]
    matches: list[Match] = Field(default_factory=list)


class Venue(Record):
    """One rung of a journal or preprint ladder from manuscript-journal-select."""
    ladder: Literal["journals", "preprints"]
    rung: Annotated[int, Field(ge=1)]
    tool_rung: int | None = None  # the ladder tool's own order, when the selection reordered it
    name: Text
    key: str = ""
    article_type: str = ""
    chosen: bool = False
    fits: str = ""
    fits_reason: str = ""
    impact_factor: float | None = None
    impact_factor_year: str = ""
    first_decision_days: float | None = None
    speed_measure: str = ""
    ai_points: int | None = None
    ai_tier: str = ""
    ai_for_this_use: str = ""
    fee: str = ""
    preprint_rule: str = ""
    why: str = ""
    url: str = ""


class Inventory(Record):
    schema_version: Literal[1, 2] = 1
    title: Text
    run_id: Text
    scope: Text
    coverage: Annotated[list[Coverage], Field(min_length=1)]
    findings: list[Finding]
    changes: list[Change]
    limitations: list[Text] = Field(default_factory=list)
    illustrative: bool = False
    manuscript: Manuscript | None = None
    signals: list[Signal] = Field(default_factory=list)
    dismissed: list[Dismissed] = Field(default_factory=list)
    not_checked: list[NotChecked] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    panel: Panel | None = None
    reference: Reference | None = None
    venues: list[Venue] = Field(default_factory=list)

    @model_validator(mode="after")
    def reconcile(self) -> Inventory:
        for records, label, key in ((self.findings, "finding", "id"), (self.changes, "change", "id"),
                                    (self.coverage, "coverage", "skill"), (self.decisions, "decision", "id")):
            ids = [getattr(record, key) for record in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {label} IDs; merge repeated records before counting.")
        known = {finding.id for finding in self.findings}
        skills = {item.skill for item in self.coverage}
        applied = {fid for change in self.changes if change.status == "applied" for fid in change.finding_ids}
        for change in self.changes:
            if unknown := set(change.finding_ids) - known:
                raise ValueError(f"Change {change.id} links unknown findings: {sorted(unknown)}")
        for decision in self.decisions:
            if unknown := set(decision.finding_ids) - known:
                raise ValueError(f"Decision {decision.id} links unknown findings: {sorted(unknown)}")
        for finding in self.findings:
            if set(finding.skills) - skills:
                raise ValueError(f"Finding {finding.id} names a skill absent from coverage.")
            if finding.resolution == "addressed" and (finding.assessment != "confirmed" or finding.id not in applied):
                raise ValueError(f"Addressed finding {finding.id} needs confirmation and a linked applied edit.")
        rungs = [(venue.ladder, venue.rung) for venue in self.venues]
        if len(rungs) != len(set(rungs)):
            raise ValueError("Two venues share a rung of the same ladder.")
        if self.reference:
            items = [item.id for item in self.reference.items]
            if len(items) != len(set(items)):
                raise ValueError("Duplicate reference item IDs.")
            matched = [match.reference_id for match in self.reference.matches]
            if len(matched) != len(set(matched)):
                raise ValueError("A reference item has two match records; give it one, listing every finding.")
            if unknown := set(matched) - set(items):
                raise ValueError(f"Matches name unknown reference items: {sorted(unknown)}")
            for match in self.reference.matches:
                if unknown := set(match.finding_ids) - known:
                    raise ValueError(f"Reference match {match.reference_id} links unknown findings: {sorted(unknown)}")
                if any(f.assessment == "dismissed" for f in self.findings if f.id in match.finding_ids):
                    raise ValueError(f"Reference match {match.reference_id} rests on a dismissed flag.")
            full = {match.reference_id for match in self.reference.matches if match.match == "full"}
            for item in self.reference.items:
                if item.miss_reason and item.id in full:
                    raise ValueError(f"Reference item {item.id} was matched in full; it has no miss reason.")
        return self


def verify_evidence(data: Inventory, base: Path) -> dict[str, str]:
    """Check exact source identity before writing any outputs; return portable source hashes."""
    contents: dict[str, str] = {}
    hashes: dict[str, str] = {}

    def check(source: Evidence) -> None:
        if source.path not in contents:
            raw = (base / source.path).resolve().read_bytes()
            contents[source.path] = raw.decode("utf-8")
            hashes[source.path] = hashlib.sha256(raw).hexdigest()
        if not source.quote.strip() or source.quote not in contents[source.path]:
            raise ValueError(f"Evidence quote absent from {source.path}: {source.quote[:80]!r}")

    for item in [*data.coverage, *data.findings, *data.changes]:
        for source in item.evidence:
            check(source)
        if isinstance(item, Change) and item.status == "applied":
            for text in (item.before, item.after):
                if text and not any(text in contents[source.path] for source in item.evidence):
                    raise ValueError(f"Applied change {item.id} has before/after text absent from its evidence.")
    if data.reference:
        check(data.reference.source)
    return hashes


def ordered(counts: Counter, order: tuple[str, ...]) -> dict[str, int]:
    return {key: counts[key] for key in order if counts[key]}


def benchmark(data: Inventory) -> dict | None:
    """Which reference items the run matched, fully or in part; the rest are missed."""
    if not data.reference:
        return None
    state = {match.reference_id: match.match for match in data.reference.matches}
    rows: dict[str, Counter] = {}
    for item in data.reference.items:
        rows.setdefault(item.category, Counter())[state.get(item.id, "missed")] += 1
    linked = {fid for match in data.reference.matches for fid in match.finding_ids}
    substantive = [item for item in data.reference.items if item.substantive]
    short = [item for item in data.reference.items if state.get(item.id) != "full"]
    return {
        "items": len(data.reference.items),
        "full": sum(v == "full" for v in state.values()),
        "partial": sum(v == "partial" for v in state.values()),
        "missed": len(data.reference.items) - len(state),
        "substantive": len(substantive),
        "substantive_caught": sum(item.id in state for item in substantive),
        "by_category": {key: dict(value) for key, value in sorted(rows.items())},
        "by_origin": dict(Counter(item.origin for item in data.reference.items)),
        "confirmed_without_counterpart": sum(f.assessment == "confirmed" and f.id not in linked for f in data.findings),
        "miss_reasons": ordered(Counter(item.miss_reason or "unexplained" for item in short), (*MISS_REASONS, "unexplained")),
        "missed_by_owner": dict(Counter(item.owner or "unassigned" for item in short if item.substantive)),
    }


def competing(changes: list[Change]) -> list[list[str]]:
    """Proposals that rewrite the same passage: the authors choose one, never apply both."""
    def sentences(text: str) -> set[str]:
        return {" ".join(part.split()) for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) >= 40}
    proposed = [c for c in changes if c.status == "proposed" and c.before]
    parent = {c.id: c.id for c in proposed}

    def root(cid: str) -> str:
        while parent[cid] != cid:
            cid = parent[cid]
        return cid
    for i, a in enumerate(proposed):
        for b in proposed[i + 1:]:
            if a.before in b.before or b.before in a.before or sentences(a.before) & sentences(b.before):
                parent[root(b.id)] = root(a.id)
    groups: dict[str, list[str]] = {}
    for c in proposed:
        groups.setdefault(root(c.id), []).append(c.id)
    return [ids for ids in groups.values() if len(ids) > 1]


def summarize(data: Inventory) -> dict:
    confirmed = [finding for finding in data.findings if finding.assessment == "confirmed"]
    pairs = Counter(pair for f in confirmed for pair in combinations(sorted(set(f.skills)), 2))
    return {
        "run_id": data.run_id, "scope": data.scope, "illustrative": data.illustrative,
        "counts": {
            "confirmed_findings": len(confirmed),
            "addressed_findings": sum(f.resolution == "addressed" for f in confirmed),
            "open_findings": sum(f.resolution == "open" for f in confirmed),
            "resolution_unknown": sum(f.resolution == "unknown" for f in confirmed),
            "candidate_findings": sum(f.assessment == "candidate" for f in data.findings),
            "dismissed_flags": sum(f.assessment == "dismissed" for f in data.findings) + len(data.dismissed),
            "applied_edits": sum(c.status == "applied" for c in data.changes),
            "proposed_edits": sum(c.status == "proposed" for c in data.changes),
        },
        "by_category": dict(Counter(f.category for f in confirmed)),
        "by_severity": dict(Counter(f.severity for f in confirmed)),
        "by_resolution": dict(Counter(f.resolution for f in confirmed)),
        "by_stage": ordered(Counter(f.stage for f in confirmed), STAGES),
        "by_skill": dict(Counter(skill for f in confirmed for skill in set(f.skills))),
        "found_by_several_skills": sum(len(set(f.skills)) > 1 for f in confirmed),
        "skill_pairs": [{"skills": list(pair), "count": count} for pair, count in pairs.most_common()],
        "decisions": len(data.decisions) or sum(f.decision for f in data.findings if f.assessment != "dismissed"),
        "signals": sum(signal.count for signal in data.signals),
        "not_checked": len(data.not_checked),
        "benchmark": benchmark(data),
        "chosen_venues": [v.name for v in sorted(data.venues, key=lambda v: v.rung) if v.chosen],
        "competing_proposals": competing(data.changes),
        "coverage": [item.model_dump(exclude={"evidence"}) for item in data.coverage],
    }


def metric(label: str, count: int, color: str) -> dict:
    return {"width": 205, "height": 90, "data": {"values": [{"count": count, "label": label}]},
            "layer": [
                {"mark": {"type": "text", "align": "left", "fontSize": 46, "fontWeight": "bold", "color": color},
                 "encoding": {"x": {"value": 0}, "y": {"value": 30}, "text": {"field": "count"}}},
                {"mark": {"type": "text", "align": "left", "fontSize": 14, "color": "#374151"},
                 "encoding": {"x": {"value": 0}, "y": {"value": 76}, "text": {"field": "label"}}},
            ]}


def bars(title: str, counts: dict[str, int], color: str) -> dict:
    rows = [{"label": label, "count": count} for label, count in counts.items()]
    if not rows:
        return {"width": 300, "height": 80, "title": title, "data": {"values": [{}]},
                "mark": {"type": "text", "text": "No records in this scope", "color": "#4b5563", "fontSize": 14}}
    maximum = max(counts.values()) + 1
    step = max(1, (maximum + 4) // 5)
    encoding = {
        "y": {"field": "label", "type": "nominal", "sort": "-x", "title": None,
              "axis": {"labelLimit": 200}},
        "x": {"field": "count", "type": "quantitative", "title": "Number of records",
              "scale": {"zero": True, "domainMax": maximum},
              "axis": {"values": list(range(0, maximum + 1, step)), "format": "d"}},
        "tooltip": [{"field": "label", "title": "Type"}, {"field": "count", "title": "Records"}],
    }
    return {"width": 300, "height": max(90, len(rows) * 32), "title": title, "data": {"values": rows},
            "encoding": encoding,
            "layer": [{"mark": {"type": "bar", "color": color, "cornerRadiusEnd": 3}},
                      {"mark": {"type": "text", "align": "left", "dx": 5, "fontSize": 13},
                       "encoding": {"text": {"field": "count"}}}]}


def note(lines: list[str]) -> dict:
    wrapped = [part for line in lines for part in textwrap.wrap(line, width=112)]
    return {"width": 880, "height": max(25, len(wrapped) * 19),
            "data": {"values": [{"text": line, "line": i} for i, line in enumerate(wrapped)]},
            "mark": {"type": "text", "align": "left", "baseline": "top", "fontSize": 13, "color": "#374151"},
            "encoding": {"x": {"value": 0}, "y": {"field": "line", "type": "ordinal", "axis": None,
                         "scale": {"padding": 0}}, "text": {"field": "text"}}}


def chart(data: Inventory, summary: dict) -> dict:
    counts = summary["counts"]
    coverage = [f"{item.skill.removeprefix('manuscript-')}: {item.status}. {item.note}" for item in data.coverage]
    titles = textwrap.wrap(("ILLUSTRATIVE EXAMPLE — " if data.illustrative else "") + data.title, width=65)
    rows = [
        {"hconcat": [metric("Confirmed findings", counts["confirmed_findings"], "#305b96"),
                     metric("Findings addressed", counts["addressed_findings"], "#17735e"),
                     metric("Applied edits", counts["applied_edits"], "#6653a3"),
                     metric("Candidate findings", counts["candidate_findings"], "#a46415")], "spacing": 20},
        {"hconcat": [bars("Confirmed findings by type", summary["by_category"], "#305b96"),
                     bars("Confirmed findings by severity", summary["by_severity"], "#6386ae")], "spacing": 60},
        {"hconcat": [bars("Confirmed findings: current status", summary["by_resolution"], "#6386ae"),
                     bars("Edits recorded", {"Applied": counts["applied_edits"],
                                              "Proposed": counts["proposed_edits"]}, "#6653a3")], "spacing": 60},
    ]
    caught = []
    if bench := summary["benchmark"]:
        rows.append({"hconcat": [bars(f"{data.reference.title}: {bench['items']} problems",
                                      {"Matched": bench["full"], "Partly matched": bench["partial"],
                                       "Not caught": bench["missed"]}, "#305b96"),
                                 bars("Confirmed findings by stage", summary["by_stage"], "#6386ae")],
                     "spacing": 60})
        caught = [f"Compared with {data.reference.title}: {bench['full']} matched, {bench['partial']} partly "
                  f"matched and {bench['missed']} not caught of {bench['items']} problems it raised. "
                  f"{bench['confirmed_without_counterpart']} confirmed findings have no counterpart there."]
    rows.append(note([f"Run: {data.run_id}", *coverage,
                      f"Dismissed flags: {counts['dismissed_flags']}. Unknown resolution: {counts['resolution_unknown']}.",
                      *caught, *data.limitations,
                      "Counts describe this review scope, not detection accuracy or publication readiness.",
                      "One finding is counted once across skills; edits and findings are separate units."]))
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "background": "#ffffff", "padding": 28,
        "title": {"text": titles, "subtitle": textwrap.wrap(data.scope, width=105), "anchor": "start",
                  "fontSize": 25, "subtitleFontSize": 14, "subtitlePadding": 14, "offset": 24},
        "spacing": 28,
        "vconcat": rows,
        "config": {"font": "DejaVu Sans", "view": {"stroke": None},
                   "title": {"anchor": "start", "fontSize": 15, "color": "#172b43"},
                   "axis": {"labelFontSize": 12, "titleFontSize": 12, "gridColor": "#e5e7eb"}},
    }


def inline(document: dict) -> str:
    """JSON for a script element: escaping "<" means neither "</script>" nor "<!--" can end or confuse it."""
    text = json.dumps(document, ensure_ascii=False)
    for character, escape in (("<", "\\u003c"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        text = text.replace(character, escape)
    return text


def manuscript_html(text: str, suffix: str) -> str:
    """The reviewed text as HTML. Raw HTML in Markdown is shown as text, so an author's comment stays visible."""
    if suffix in {".md", ".markdown", ".txt"}:
        from markdown_it import MarkdownIt

        return MarkdownIt("commonmark", {"html": False}).enable("table").render(text)
    parts = []
    for block in re.split(r"\n\s*\n", text):
        if heading := re.match(r"\\(?:sub)*section\*?\{(.+?)\}", block.strip()):
            parts.append(f"<h2>{html.escape(heading.group(1))}</h2>")
        elif block.strip():
            parts.append(f"<p>{html.escape(block.strip())}</p>")
    return "\n".join(parts)


def skill_of(path: str) -> str:
    return next((part for part in Path(path).parts if part.startswith("manuscript-")), "")


def dashboard_html(data: Inventory, summary: dict, base: Path | None = None, mode: str = "full") -> str:
    """The template with the inventory inlined as JSON and the reviewed text rendered for the manuscript view.

    Evidence keeps its file name and the skill folder it came from, never a local path. `mode="paper"` is the
    annotated manuscript alone."""
    payload = data.model_dump(mode="json")
    for item in [*payload["coverage"], *payload["findings"], *payload["changes"]]:
        for source in item["evidence"]:
            source["skill"] = skill_of(source["path"])
            source["path"] = Path(source["path"]).name
    if payload["reference"]:
        payload["reference"]["source"]["path"] = Path(payload["reference"]["source"]["path"]).name
    paper = ""
    if base is not None and data.manuscript and data.manuscript.path:
        path = (base / data.manuscript.path).resolve()
        paper = manuscript_html(path.read_text(encoding="utf-8"), path.suffix.lower())
    if payload["manuscript"]:
        payload["manuscript"].pop("path", None)
    hashes = [{"file": Path(path).name, "sha256": value} for path, value in summary.get("evidence_sha256", {}).items()]
    document = {"inventory": payload, "summary": {**summary, "evidence_sha256": hashes}, "mode": mode,
                "has_paper": bool(paper), "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    title = f"Annotated: {data.manuscript.title}" if mode == "paper" and data.manuscript else data.title
    template = TEMPLATE.read_text(encoding="utf-8")
    return (template.replace("__TITLE__", html.escape(title)).replace("__MANUSCRIPT_HTML__", paper)
            .replace("__INVENTORY_JSON__", inline(document)))


def render(source: Path, output_dir: Path, static: bool = True) -> dict:
    data = Inventory.model_validate_json(source.read_text(encoding="utf-8"))
    hashes = verify_evidence(data, source.resolve().parent)
    summary = summarize(data)
    summary["evidence_sha256"] = hashes
    summary["inventory_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    spec = chart(data, summary)
    base = source.resolve().parent
    outputs: dict[str, str | bytes] = {"dashboard.html": dashboard_html(data, summary, base),
                                       "infographic.vl.json": json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                                       "summary.json": json.dumps(summary, ensure_ascii=False, indent=2) + "\n"}
    if data.manuscript and data.manuscript.path:
        outputs["annotated.html"] = dashboard_html(data, summary, base, mode="paper")
    if static:
        import vl_convert as vlc

        # Compile before creating outputs. All chart data is inline and static rendering permits no remote URLs.
        outputs["infographic.svg"] = vlc.vegalite_to_svg(spec, allowed_base_urls=[])
        outputs["infographic.png"] = vlc.vegalite_to_png(spec, scale=2, allowed_base_urls=[])
    if any((output_dir / name).exists() for name in outputs):
        raise ValueError("Output files already exist; choose a new output directory to retain the previous attempt.")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        if isinstance(value, bytes):
            (output_dir / name).write_bytes(value)
        else:
            (output_dir / name).write_text(value, encoding="utf-8")
    return summary


@app.command()
def main(source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
         output_dir: Annotated[Path, typer.Option("--output-dir")],
         static: Annotated[bool, typer.Option(help="Also write the SVG and PNG infographic")] = True) -> None:
    try:
        summary = render(source, output_dir, static)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps({"output_dir": str(output_dir.resolve()), "counts": summary["counts"],
                           "benchmark": summary["benchmark"]}, indent=2))


if __name__ == "__main__":
    app()
