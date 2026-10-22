# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "vl-convert-python>=1.9,<2"]
# ///
"""Render evidence-linked review findings and edits as a Vega-Lite infographic and offline report.

    uv run --script infographic.py findings.json --output-dir infographic

Counts are derived from distinct adjudicated records, never supplied headline totals. Evidence checks
establish local file/quotation identity, not scientific support or correctness of the adjudication.
"""
from __future__ import annotations

import hashlib
import html
import json
import textwrap
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal

import typer
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identity = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]
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


class Inventory(Record):
    schema_version: Literal[1] = 1
    title: Text
    run_id: Text
    scope: Text
    coverage: Annotated[list[Coverage], Field(min_length=1)]
    findings: list[Finding]
    changes: list[Change]
    limitations: list[Text] = Field(default_factory=list)
    illustrative: bool = False

    @model_validator(mode="after")
    def reconcile(self) -> Inventory:
        for records, label, key in ((self.findings, "finding", "id"), (self.changes, "change", "id"),
                                    (self.coverage, "coverage", "skill")):
            ids = [getattr(record, key) for record in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate {label} IDs; merge repeated records before counting.")
        known = {finding.id for finding in self.findings}
        skills = {item.skill for item in self.coverage}
        applied = {fid for change in self.changes if change.status == "applied" for fid in change.finding_ids}
        for change in self.changes:
            if unknown := set(change.finding_ids) - known:
                raise ValueError(f"Change {change.id} links unknown findings: {sorted(unknown)}")
        for finding in self.findings:
            if set(finding.skills) - skills:
                raise ValueError(f"Finding {finding.id} names a skill absent from coverage.")
            if finding.resolution == "addressed" and (finding.assessment != "confirmed" or finding.id not in applied):
                raise ValueError(f"Addressed finding {finding.id} needs confirmation and a linked applied edit.")
        return self


def verify_evidence(data: Inventory, base: Path) -> dict[str, str]:
    """Check exact source identity before writing any outputs; return portable source hashes."""
    contents: dict[str, str] = {}
    hashes: dict[str, str] = {}
    for item in [*data.coverage, *data.findings, *data.changes]:
        for source in item.evidence:
            if source.path not in contents:
                path = (base / source.path).resolve()
                raw = path.read_bytes()
                contents[source.path] = raw.decode("utf-8")
                hashes[source.path] = hashlib.sha256(raw).hexdigest()
            if not source.quote.strip() or source.quote not in contents[source.path]:
                raise ValueError(f"Evidence quote absent from {source.path}: {source.quote[:80]!r}")
        if isinstance(item, Change) and item.status == "applied":
            for text in (item.before, item.after):
                if text and not any(text in contents[source.path] for source in item.evidence):
                    raise ValueError(f"Applied change {item.id} has before/after text absent from its evidence.")
    return hashes


def summarize(data: Inventory) -> dict:
    confirmed = [finding for finding in data.findings if finding.assessment == "confirmed"]
    return {
        "run_id": data.run_id, "scope": data.scope, "illustrative": data.illustrative,
        "counts": {
            "confirmed_findings": len(confirmed),
            "addressed_findings": sum(f.resolution == "addressed" for f in confirmed),
            "open_findings": sum(f.resolution == "open" for f in confirmed),
            "resolution_unknown": sum(f.resolution == "unknown" for f in confirmed),
            "candidate_findings": sum(f.assessment == "candidate" for f in data.findings),
            "dismissed_flags": sum(f.assessment == "dismissed" for f in data.findings),
            "applied_edits": sum(c.status == "applied" for c in data.changes),
            "proposed_edits": sum(c.status == "proposed" for c in data.changes),
        },
        "by_category": dict(Counter(f.category for f in confirmed)),
        "by_severity": dict(Counter(f.severity for f in confirmed)),
        "by_resolution": dict(Counter(f.resolution for f in confirmed)),
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
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "background": "#ffffff", "padding": 28,
        "title": {"text": titles, "subtitle": textwrap.wrap(data.scope, width=105), "anchor": "start",
                  "fontSize": 25, "subtitleFontSize": 14, "subtitlePadding": 14, "offset": 24},
        "spacing": 28,
        "vconcat": [
            {"hconcat": [metric("Confirmed findings", counts["confirmed_findings"], "#305b96"),
                         metric("Findings addressed", counts["addressed_findings"], "#17735e"),
                         metric("Applied edits", counts["applied_edits"], "#6653a3"),
                         metric("Candidate findings", counts["candidate_findings"], "#a46415")], "spacing": 20},
            {"hconcat": [bars("Confirmed findings by type", summary["by_category"], "#305b96"),
                         bars("Confirmed findings by severity", summary["by_severity"], "#6386ae")], "spacing": 60},
            {"hconcat": [bars("Confirmed findings: current status", summary["by_resolution"], "#6386ae"),
                         bars("Edits recorded", {"Applied": counts["applied_edits"],
                                                  "Proposed": counts["proposed_edits"]}, "#6653a3")], "spacing": 60},
            note([f"Run: {data.run_id}", *coverage,
                  f"Dismissed flags: {counts['dismissed_flags']}. Unknown resolution: {counts['resolution_unknown']}.",
                  *data.limitations,
                  "Counts describe this review scope, not detection accuracy or publication readiness.",
                  "One finding is counted once across skills; edits and findings are separate units."]),
        ],
        "config": {"font": "DejaVu Sans", "view": {"stroke": None},
                   "title": {"anchor": "start", "fontSize": 15, "color": "#172b43"},
                   "axis": {"labelFontSize": 12, "titleFontSize": 12, "gridColor": "#e5e7eb"}},
    }


def evidence_html(sources: list[Evidence]) -> str:
    return "".join(f"<details><summary>{html.escape(Path(source.path).name)}</summary>"
                   f"<blockquote>{html.escape(source.quote)}</blockquote></details>" for source in sources)


def report_html(data: Inventory, summary: dict, svg: str) -> str:
    esc = html.escape
    rows = []
    for finding in data.findings:
        rows.append(f'<article data-record><h3>{esc(finding.id)} · {esc(finding.summary)}</h3>'
                    f'<p>{esc(finding.category)} · {esc(finding.section)} · {finding.severity} · '
                    f'{finding.assessment} · {finding.resolution}</p><p>{esc(", ".join(finding.skills))}</p>'
                    f'{evidence_html(finding.evidence)}</article>')
    changes = []
    for change in data.changes:
        before = esc(change.before) if change.before is not None else "(Addition)"
        after = esc(change.after) if change.after is not None else "(Deletion)"
        changes.append(f'<article data-record><h3>{esc(change.id)} · {esc(change.summary)}</h3>'
                       f'<p>{change.status} · {esc(change.kind)} · {esc(change.section)} · '
                       f'Findings: {esc(", ".join(change.finding_ids)) or "independent edit"}</p>'
                       f'<div class="comparison"><section><h4>Before</h4><pre>{before}</pre></section>'
                       f'<section><h4>After</h4><pre>{after}</pre></section></div>'
                       f'{evidence_html(change.evidence)}</article>')
    coverage = "".join(f'<li><strong>{esc(item.skill)}: {item.status}</strong>. {esc(item.note)}'
                       f'{evidence_html(item.evidence)}</li>' for item in data.coverage)
    limits = "".join(f"<li>{esc(line)}</li>" for line in data.limitations)
    disclaimer = "Illustrative example. " if data.illustrative else ""
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(data.title)}</title><style>
body{{font:16px/1.55 system-ui,sans-serif;color:#172b43;background:#fff;margin:0 auto;max-width:1150px;padding:24px}}
h1,h2,h3,h4{{line-height:1.25}} .chart svg{{width:100%;height:auto}}article{{border-top:1px solid #d5dce5;padding:16px 0}}
blockquote{{border-left:3px solid #6386ae;margin:12px 0;padding-left:16px;white-space:pre-wrap}}
details{{margin:8px 0}}summary{{cursor:pointer}}pre{{white-space:pre-wrap;font:inherit;margin:0;overflow-wrap:anywhere}}
.comparison{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}input{{font:inherit;padding:10px;width:min(90%,600px)}}
.note{{color:#48586b}}[hidden]{{display:none!important}}@media(max-width:650px){{.comparison{{grid-template-columns:1fr}}}}
@media print{{input,label,.search-status{{display:none}}article, .comparison{{break-inside:avoid}}}}
</style></head><body><h1>{esc(data.title)}</h1><p>{esc(data.scope)}</p>
<p class="note">{disclaimer}Run: {esc(data.run_id)}. Counts describe this scope, not detection accuracy or publication readiness.</p>
<div class="chart" role="img" aria-label="Review findings, edits and coverage">{svg}</div>
<h2>Review coverage</h2><ul>{coverage}</ul><ul>{limits}</ul>
<p>Each finding is counted once across skills. Applied edits, proposed edits, candidates and dismissed flags remain separate.
Evidence excerpts are embedded below; the original files need not accompany this report.</p>
<label for="search">Search findings, edits and evidence</label><br><input id="search" type="search" placeholder="Category, section, phrase or finding ID">
<p class="search-status" role="status" id="search-status"></p>
<h2>Findings ({len(data.findings)})</h2>{''.join(rows) or '<p>No findings recorded within this scope.</p>'}
<h2>Edits ({len(data.changes)})</h2>{''.join(changes) or '<p>No edits recorded.</p>'}
<script>
const search=document.getElementById('search'), status=document.getElementById('search-status');
const records=Array.from(document.querySelectorAll('[data-record]'));
function filterRecords(){{const q=search.value.toLocaleLowerCase();let visible=0;
for(const record of records){{record.hidden=!record.textContent.toLocaleLowerCase().includes(q);if(!record.hidden)visible++;}}
status.textContent=`${{visible}} of ${{records.length}} evidence records shown. Chart totals retain the full stated scope.`;}}
search.addEventListener('input',filterRecords);filterRecords();
</script></body></html>'''


def render(source: Path, output_dir: Path) -> dict:
    import vl_convert as vlc

    data = Inventory.model_validate_json(source.read_text(encoding="utf-8"))
    hashes = verify_evidence(data, source.resolve().parent)
    summary = summarize(data)
    summary["evidence_sha256"] = hashes
    summary["inventory_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    spec = chart(data, summary)
    # Compile before creating outputs. All chart data is inline and static rendering permits no remote URLs.
    svg = vlc.vegalite_to_svg(spec, allowed_base_urls=[])
    png = vlc.vegalite_to_png(spec, scale=2, allowed_base_urls=[])
    document = report_html(data, summary, svg)
    outputs = {"infographic.svg": svg, "infographic.png": png, "infographic.html": document,
               "infographic.vl.json": json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
               "summary.json": json.dumps(summary, ensure_ascii=False, indent=2) + "\n"}
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
         output_dir: Annotated[Path, typer.Option("--output-dir")]) -> None:
    try:
        summary = render(source, output_dir)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps({"output_dir": str(output_dir.resolve()), "counts": summary["counts"]}, indent=2))


if __name__ == "__main__":
    app()
