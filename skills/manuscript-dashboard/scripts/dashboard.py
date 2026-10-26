# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "markdown-it-py>=3", "pyyaml>=6"]
# ///
"""Render evidence-linked review findings and edits as an offline dashboard.

    uv run --script dashboard.py RUN/manuscript-dashboard/findings.json --output-dir RUN/manuscript-dashboard/dashboard \
        [--revision RUN/manuscript-improve/revision]

`manuscript-dashboard.html` is one self-contained file: headline counts, review coverage, the funnel from raw signals
to distinct findings, cross-filtered breakdowns, the manuscript with every quoted problem highlighted and
explained in a margin comment, which skills found the same problem, every finding with its evidence, the
edits as word-level diffs, the corrected version with track changes (from manuscript-improve's revise.py),
counts of machine-writing patterns by type in each version, the simulated reviewers and readers and, when a
reference review is supplied, which of its problems the run caught. `summary.json` holds every derived count.

Counts are derived from distinct adjudicated records, never supplied headline totals. Evidence checks
establish local file/quotation identity, not scientific support or correctness of the adjudication.

Second attempts: no output is overwritten. The next attempt of a file takes a number before its extension
(findings.json, findings.2.json, findings.3.json), of a folder after its name (dashboard, dashboard.2); every
script of the end of a run refuses an existing output and names the next free one.
"""
from __future__ import annotations

import base64
import hashlib
import html
import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from urllib.parse import unquote
from typing import Any, Annotated, Literal

import typer
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Identity = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")]
SEVERITIES = ("blocker", "major", "minor", "info", "unknown")
STAGES = ("now", "writing", "journal", "final", "unknown")
ASSETS = Path(__file__).resolve().parents[1] / "assets"
TEMPLATE = ASSETS / "dashboard.html"
DESLOP = Path(__file__).resolve().parents[2] / "manuscript-deslop"
GUARD = Path(__file__).resolve().parents[2] / "manuscript-prose-edit" / "scripts" / "guard.py"
app = typer.Typer(add_completion=False)


def utf8_console() -> None:
    """Print UTF-8 on every platform (a Windows console defaults to a legacy code page)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


# ---------- numbered attempts: a second attempt never overwrites the first ----------

ATTEMPT = re.compile(r"^(?P<base>.+?)\.(?P<n>[2-9]|[1-9]\d+)$")


def _split(path: Path, folder: bool | None = None) -> tuple[str, str]:
    """A name as (stem, extension) for numbering: `findings.json` is ("findings", ".json"), a folder `revision`
    is ("revision", ""). A folder has no extension, even when its name has a dot."""
    folder = path.is_dir() if folder is None else folder
    suffix = "" if folder or re.fullmatch(r"\.\d+", path.suffix or ".0") else path.suffix
    return (path.name[:-len(suffix)] if suffix else path.name), suffix


def attempt_base(path: Path, folder: bool | None = None) -> tuple[Path, int]:
    """The first attempt's path and this path's attempt number: findings.2.json is (findings.json, 2)."""
    stem, suffix = _split(path, folder)
    match = ATTEMPT.match(stem)
    if not match:
        return path, 1
    return path.with_name(match["base"] + suffix), int(match["n"])


def attempt_path(path: Path, number: int, folder: bool | None = None) -> Path:
    """Attempt `number` of the output whose first attempt is `path`."""
    base, _ = attempt_base(path, folder)
    stem, suffix = _split(base, folder)
    return base if number <= 1 else base.with_name(f"{stem}.{number}{suffix}")


def attempts(path: Path, folder: bool | None = None) -> list[Path]:
    """Every existing attempt of an output, oldest first: findings.json, findings.2.json, ..."""
    base, _ = attempt_base(path, folder)
    stem, suffix = _split(base, folder)
    pattern = re.compile(rf"^{re.escape(stem)}(?:\.(?P<n>[2-9]|[1-9]\d+))?{re.escape(suffix)}$")
    found = []
    if base.parent.is_dir():
        for candidate in base.parent.iterdir():
            if (match := pattern.match(candidate.name)) and (folder is None or candidate.is_dir() == folder):
                found.append((int(match["n"] or 1), candidate))
    return [p for _, p in sorted(found)]


def newest_attempt(path: Path, folder: bool | None = None) -> Path | None:
    """The newest existing attempt of an output, or None."""
    found = attempts(path, folder)
    return found[-1] if found else None


def next_attempt(path: Path, folder: bool | None = None) -> Path:
    """The first free attempt name after the newest existing one."""
    found = attempts(path, folder)
    last = attempt_base(found[-1], folder)[1] if found else 0
    return attempt_path(path, last + 1, folder)


def author_notes(text: str) -> list[tuple[int, int]]:
    """Where the notes to the authors are: each `[AUTHORS: ...]` the workflow left for a fact or a decision only
    the authors have, as (start, end), the outermost of nested notes, brackets balanced. An unclosed note runs to
    the end of its paragraph."""
    spans, at = [], 0
    while (start := text.find("[AUTHORS:", at)) >= 0:
        depth, end = 0, start
        stop = text.find("\n\n", start)
        stop = len(text) if stop < 0 else stop
        while end < stop:
            depth += {"[": 1, "]": -1}.get(text[end], 0)
            end += 1
            if not depth:
                break
        spans.append((start, end))
        at = end
    return spans


def strip_notes(text: str) -> str:
    """The text without its notes to the authors: a note alone on a line goes with its line, and the spaces a
    note leaves before punctuation or at a line end go with it."""
    out, at = [], 0
    for start, end in author_notes(text):
        out.append(text[at:start])
        at = end
    out.append(text[at:])
    joined = "\x00".join(out)
    # A line or list item that held only notes goes; so do the spaces a note leaves.
    joined = re.sub(r"(?m)^[ \t]*(?:[-*+][ \t]+|\d+[.)][ \t]+)?(?:\x00[ \t]*)+(?:\n|\Z)", "", joined)
    joined = re.sub(r"[ \t]*,[ \t]*\x00[ \t]*(?=[,.;:!?)\]]|\n|\Z)", "", joined)  # "Academy, [note], Romania"
    joined = re.sub(r"[ \t]*\x00[ \t]*(?=[,.;:!?)\]]|\n|\Z)", "", joined)  # before punctuation or a line end
    joined = re.sub(r"(?<=[(\[])[ \t]*\x00[ \t]*", "", joined)  # after an opening bracket
    joined = re.sub(r"[ \t]*\x00[ \t]*", " ", joined)
    joined = re.sub(r"\n{3,}", "\n\n", joined)
    return joined if text.startswith("\n") else joined.lstrip("\n")


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(Record):
    path: Text
    quote: Annotated[str, Field(min_length=1)]


class Coverage(Record):
    skill: Text
    # in_progress: the stage was still running when the inventory was collected
    status: Literal["completed", "partial", "blocked", "not_run", "reused", "in_progress", "unknown"]
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
    anchor: str | None = None
    why: str = ""  # the reasoning: what was wrong with the passage and why this wording fixes it
    comment: str = ""  # a question for the authors about this edit: a fact or decision only they have, never put in the text
    evidence: Annotated[list[Evidence], Field(min_length=1)]

    @model_validator(mode="after")
    def has_text(self) -> Change:
        if not any(text and text.strip() for text in (self.before, self.after)):
            raise ValueError(f"Change {self.id} needs before or after text.")
        if self.anchor is not None and self.before is not None:
            raise ValueError(f"Change {self.id} replaces a passage; only an addition names an anchor.")
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
    isolation: Literal["", "fresh-agent", "one-agent"] = ""  # how it ran; "" when the run did not record it
    model: str = ""  # the model that read it (codex/gpt-5.6-sol); "" when the run did not record it


class Concern(Record):
    """One concern of a simulated reviewer, with what would settle it and what the adjudication decided."""
    id: Text
    severity: str = ""  # the reviewer's own: major, optional or uncertain
    location: str = ""
    concern: Text
    suggestion: str = ""  # what would change the reviewer's mind
    route: str = ""  # fixable-in-text, author-required or policy
    placement: str = ""  # where the fix goes, to cost readers least
    cost: str = ""  # text, reanalysis or new work
    defence: str = ""  # how far the authors' defence answered it
    verdict: str = ""  # the adjudication: confirmed, downgraded or refuted
    verdict_evidence: str = ""
    finding_ids: list[Identity] = Field(default_factory=list)  # the inventory's problems that carry it
    criterion: list[str] = Field(default_factory=list)  # the criteria the reviewer wrote before reading it falls under
    off_criterion: str = ""  # why it matters although no criterion anticipated it
    norm_source: str = ""  # where an expectation it rests on is written: venue:, guideline:, module: or own:


class Criterion(Record):
    """A problem a reviewer wrote down before reading the paper, with the concerns raised under it, or the line saying
    what the reviewer checked and found nothing."""
    id: Text
    text: Text
    concerns: list[str] = Field(default_factory=list)
    checked: str = ""


class Reviewer(Record):
    seat: Text
    summary: str = ""
    isolation: Literal["", "fresh-agent", "one-agent"] = ""  # how it ran; "" when the run did not record it
    model: str = ""  # the model that read it (codex/gpt-5.6-sol); "" when the run did not record it
    strengths: list[str] = Field(default_factory=list)
    concerns: list[Concern] = Field(default_factory=list)
    criteria: list[Criterion] = Field(default_factory=list)


class Panel(Record):
    recommendations: list[Recommendation] = Field(default_factory=list)
    reviewers: list[Reviewer] = Field(default_factory=list)
    readers: list[Reader] = Field(default_factory=list)


class Manuscript(Record):
    title: Text
    version: str = ""
    sha256: str = ""
    sections: list[Text] = Field(default_factory=list)
    path: str = ""  # the reviewed text, relative to the inventory, for the manuscript view


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
    matched_by: str = ""  # who matched its items to the run's findings, after the inventory was frozen
    items: Annotated[list[ReferenceItem], Field(min_length=1)]
    matches: list[Match] = Field(default_factory=list)


class ListedReference(Record):
    """One entry of the manuscript's reference list as the reference check left it: its worst state and what was
    found, in the scanner's own words."""
    n: int
    line: int = 0
    text: Text
    state: Literal["fine", "corrected", "unverified", "not-checked", "wrong", "retracted"]
    link: str = ""  # doi.org, PubMed or arXiv
    notes: list[str] = Field(default_factory=list)


class RecheckConcern(Record):
    """A fresh agent's verdict on one confirmed problem, read against the corrected version (recheck.py)."""
    id: Identity
    verdict: Literal["fully", "partly", "not", "worse", "unchecked"]
    quote: str = ""
    why: Text
    section: str = ""
    summary: str = ""
    raised_by: list[str] = Field(default_factory=list)


class RecheckProblem(Record):
    origin: Literal["introduced", "missed"]
    section: str = ""
    quote: Text
    problem: Text


class Recheck(Record):
    """The independent re-check of the corrected version: one fresh agent's verdicts and new problems, and the number
    and reference checks run again on it."""
    schema_version: Literal[1]
    proposed_sha256: Text
    isolation: Literal["fresh-agent", "one-agent"] = "fresh-agent"
    model: str = ""
    concerns: list[RecheckConcern]
    new_problems: list[RecheckProblem] = Field(default_factory=list)
    numbers: dict[str, Any] = Field(default_factory=dict)


# A re-check verdict as the problem's resolution in the dashboard.
RESOLVED_AS = {"fully": "addressed", "partly": "partly", "not": "open", "worse": "worse", "unchecked": "unknown"}


class AiAspect(Record):
    level: Literal["good", "warning", "red", "unknown"]
    text: str = ""


class AiPolicy(Record):
    """A venue's AI policy, aspect by aspect (manuscript-journal-adapt's `ai_flags`), with where it was read."""
    aspects: dict[str, AiAspect]
    reasons: list[str] = Field(default_factory=list)
    url: str = ""
    source: str = ""


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
    ai_policy: AiPolicy | None = None
    fee: str = ""
    preprint_rule: str = ""
    why: str = ""
    url: str = ""


class StoryTest(Record):
    """One story test (manuscript-story's story-tests.md): does the paper do this for its readers?"""
    test: Text
    result: Literal["holds", "partly", "fails", "not-run"]
    note: str = ""  # what it found, with the passage quoted
    finding_ids: list[Identity] = Field(default_factory=list)
    change_ids: list[Identity] = Field(default_factory=list)


class StoryOption(Record):
    """A way to point the paper: a change of direction is only ever offered, never applied."""
    title: Text
    summary: str = ""  # the draft title and the Abstract's first sentences it would take
    readers: str = ""  # whom and which venues it suits
    cost: str = ""


class Story(Record):
    """How the paper tells its story, from manuscript-story: the direction, the tests and the options."""
    direction: str = ""
    confirmed: bool = False  # the authors confirmed the direction; otherwise it was drafted from the text
    drift: str = ""
    tests: list[StoryTest] = Field(default_factory=list)
    options: list[StoryOption] = Field(default_factory=list)


class FigureChange(Record):
    """One recommended change to a figure, in its content or in how it shows it, with the reason."""
    kind: Literal["content", "visual"]
    change: Text
    why: Text


class FigureItem(Record):
    """One figure or table as manuscript-figures reviewed it. Which display items exist is the authors' decision."""
    id: Text  # "Figure 2", "Table 3", "Figure S1"
    kind: Literal["figure", "table"] = "figure"
    part: Literal["main", "supplement"] = "main"  # the main text gets the full review, the supplement a lighter one
    caption: str = ""
    image: str = ""  # the figure as rendered, relative to the inventory; embedded in the dashboard (a table has none)
    verdict: Literal["keep", "change", "move-to-supplement", "move-to-main-text"]
    message: str = ""  # the one thing a reader should take from it
    why: str = ""  # the reason for the verdict
    recommendations: list[FigureChange] = Field(default_factory=list)
    proposed_image: str = ""  # a redrawn draft from the authors' code: a proposal beside their figure, never in its place
    code: str = ""  # the code that draws it, when the project has it
    finding_ids: list[Identity] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def part_from_number(cls, values: Any) -> Any:
        """A record written before items said their part: Figure S1 and Table S2 are supplementary."""
        if isinstance(values, dict) and "part" not in values and \
                re.match(r"(?i)^(?:supplementary\s+)?(?:figure|table)\s+S\d", str(values.get("id", ""))):
            return {**values, "part": "supplement"}
        return values


class NewFigure(Record):
    """A figure the paper does not have and its readers need: a decision for the authors."""
    title: Text
    kind: str = ""  # a schematic overview, the real output a user sees, a key result now only in a table
    shows: str = ""
    why: Text
    placement: str = ""
    source: str = ""  # what it is built from: a table, the authors' output files; never invented data
    replaces: str = ""  # what goes to the supplement to keep within the limit
    finding_ids: list[Identity] = Field(default_factory=list)


class FigureLimit(Record):
    count: Annotated[int, Field(ge=0)]
    counts: str = "figures"  # or "figures and tables", as the venue counts display items
    source: str = ""  # the venue's page or the record that gives it


class Figures(Record):
    """The figures stage: each figure's verdict and recommendations, and the figures to add."""
    limit: FigureLimit | None = None
    items: list[FigureItem] = Field(default_factory=list)
    new: list[NewFigure] = Field(default_factory=list)


class Inventory(Record):
    schema_version: Literal[2]
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
    story: Story | None = None
    figures: Figures | None = None
    reference_list: list[ListedReference] = Field(default_factory=list)

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
        for reviewer in self.panel.reviewers if self.panel else []:
            for concern in reviewer.concerns:
                if unknown := set(concern.finding_ids) - known:
                    raise ValueError(f"Reviewer concern {concern.id} links unknown findings: {sorted(unknown)}")
        for finding in self.findings:
            if set(finding.skills) - skills:
                raise ValueError(f"Finding {finding.id} names a skill absent from coverage.")
            if finding.resolution == "addressed" and (finding.assessment != "confirmed" or finding.id not in applied):
                raise ValueError(f"Addressed finding {finding.id} needs confirmation and a linked applied edit.")
        if self.figures:
            ids = [item.id for item in self.figures.items]
            if len(ids) != len(set(ids)):
                raise ValueError("Two figure records share an ID.")
            for record in [*self.figures.items, *self.figures.new]:
                if unknown := set(record.finding_ids) - known:
                    raise ValueError(f"Figure {getattr(record, 'id', None) or record.title} links unknown findings: {sorted(unknown)}")
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


def figure_counts(figures: Figures | None) -> dict | None:
    """How many figures and tables got each verdict, the new figures proposed, and the main-text display items
    the venue counts (figures, or figures and tables together) before and after the proposed moves."""
    if not figures:
        return None
    verdicts = Counter(item.verdict for item in figures.items)
    tables_count = bool(figures.limit and "table" in figures.limit.counts.lower())
    counted = [item for item in figures.items if item.kind == "figure" or tables_count]
    main = [item for item in counted if item.part == "main"]
    promoted = [item for item in counted if item.part == "supplement" and item.verdict == "move-to-main-text"]
    kinds = Counter((item.kind, item.part) for item in figures.items)
    return {"items": len(figures.items), "figures": kinds[("figure", "main")] + kinds[("figure", "supplement")],
            "tables": kinds[("table", "main")] + kinds[("table", "supplement")],
            "supplementary": kinds[("figure", "supplement")] + kinds[("table", "supplement")],
            "by_verdict": ordered(verdicts, ("keep", "change", "move-to-supplement", "move-to-main-text")),
            "new": len(figures.new), "main_now": len(main),
            "main_if_accepted": len(main) - sum(item.verdict == "move-to-supplement" for item in main) + len(promoted) + len(figures.new),
            "limit": figures.limit.count if figures.limit else None}


def decision_list(data: Inventory) -> list[dict]:
    """The decisions for the authors: those the adjudication wrote, then every stage's `decision: true` finding that
    none of them links, so writing one decision never hides the stages' own."""
    linked = {fid for decision in data.decisions for fid in decision.finding_ids}
    return [*(d.model_dump() for d in data.decisions),
            *({"id": f.id, "summary": f.summary, "finding_ids": [f.id]} for f in data.findings
              if f.decision and f.assessment != "dismissed" and f.id not in linked)]


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
        "decisions": len(decision_list(data)),
        "signals": sum(signal.count for signal in data.signals),
        "not_checked": len(data.not_checked),
        "benchmark": benchmark(data),
        "chosen_venues": [v.name for v in sorted(data.venues, key=lambda v: v.rung) if v.chosen],
        "competing_proposals": competing(data.changes),
        "figures": figure_counts(data.figures),
        "coverage": [item.model_dump(exclude={"evidence"}) for item in data.coverage],
    }


def inline(document: dict) -> str:
    """JSON for a script element: escaping "<" means neither "</script>" nor "<!--" can end or confuse it."""
    text = json.dumps(document, ensure_ascii=False)
    for character, escape in (("<", "\\u003c"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        text = text.replace(character, escape)
    return text


IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".svg": "image/svg+xml", ".webp": "image/webp"}
IMAGE_LIMIT = 8 * 1024 * 1024


def embed_images(rendered: str, folders: list[Path]) -> str:
    """Put each local image into the page as a data URI, so the dashboard stays one file that works on another
    computer. An image that cannot be found, or is too large, keeps its path and says so."""
    def embed(match: re.Match) -> str:
        source = html.unescape(match.group(2))
        if re.match(r"(?i)^(?:[a-z][a-z0-9+.-]*:|//)", source):
            return match.group(0)
        name = unquote(source.split("#")[0].split("?")[0])
        for folder in folders:
            path = (folder / name).resolve()
            if path.is_file() and path.suffix.lower() in IMAGE_TYPES and path.stat().st_size <= IMAGE_LIMIT:
                data = base64.b64encode(path.read_bytes()).decode("ascii")
                return f'{match.group(1)}src="data:{IMAGE_TYPES[path.suffix.lower()]};base64,{data}"'
        return f'{match.group(1)}title="Not embedded: {html.escape(name)} was not found or is over 8 MB" src="{match.group(2)}"'
    return re.sub(r'(<img\b[^>]*?)src="([^"]*)"', embed, rendered)


def pandoc_script(marker: str, tag: str) -> Any:
    """A markdown-it inline rule for pandoc's superscript (`^1,2^`) or subscript (`H~2~O`): the text between two
    markers, with no unescaped space or line break in it, becomes `<sup>`/`<sub>` (tokens `sup_open`, `sub_open`).
    Manuscripts written for pandoc mark affiliations this way, and plain CommonMark shows the markers as text.
    `~~` (strikeout) is left alone."""
    def rule(state: Any, silent: bool) -> bool:
        start = state.pos
        if state.src[start] != marker or state.src[start + 1:start + 2] in (marker, "") or state.src[start - 1:start] == marker:
            return False
        end = start + 1
        while end < state.posMax and state.src[end] != marker:
            if state.src[end] == "\\" and end + 1 < state.posMax:
                end += 2
                continue
            if state.src[end].isspace():
                return False
            end += 1
        if end >= state.posMax:
            return False
        if not silent:
            state.push(f"{tag}_open", tag, 1)
            state.push("text", "", 0).content = re.sub(r"\\(.)", r"\1", state.src[start + 1:end])
            state.push(f"{tag}_close", tag, -1)
        state.pos = end + 1
        return True
    return rule


def markdown_parser() -> Any:
    """The Markdown reader for manuscripts: CommonMark with tables and pandoc's superscript and subscript. Raw HTML
    is shown as text, so an author's comment stays visible."""
    from markdown_it import MarkdownIt

    parser = MarkdownIt("commonmark", {"html": False}).enable("table")
    parser.inline.ruler.before("emphasis", "pandoc_superscript", pandoc_script("^", "sup"))
    parser.inline.ruler.before("emphasis", "pandoc_subscript", pandoc_script("~", "sub"))
    return parser


def manuscript_html(text: str, suffix: str, folders: list[Path] | None = None) -> str:
    """The reviewed text as HTML. Raw HTML in Markdown is shown as text, so an author's comment stays visible.
    Local images are embedded from the first of `folders` that holds them."""
    if suffix in {".md", ".markdown", ".txt"}:
        rendered = markdown_parser().render(text)
        return embed_images(rendered, folders or [])
    parts = []
    for block in re.split(r"\n\s*\n", text):
        if heading := re.match(r"\\(?:sub)*section\*?\{(.+?)\}", block.strip()):
            parts.append(f"<h2>{html.escape(heading.group(1))}</h2>")
        elif block.strip():
            parts.append(f"<p>{html.escape(block.strip())}</p>")
    return "\n".join(parts)


def skill_of(path: str) -> str:
    return next((part for part in Path(path).parts if part.startswith("manuscript-")), "")


def writing_patterns(versions: list[tuple[str, str, str, str]]) -> dict:
    """How often each machine-writing pattern of the deslop catalogue occurs in each version of the text.

    A hit is a place to look, never a verdict: human writers use these too."""
    sys.path.insert(0, str(DESLOP / "scripts"))
    import style_profile

    smells, kobak = style_profile.load_smells(), style_profile.load_kobak()
    groups = dict(re.findall(r"^## ([A-Z])\. (.+)$", (DESLOP / "references" / "llm-smells.md").read_text(encoding="utf-8"), re.M))
    out = []
    for key, label, text, suffix in versions:
        # Notes to the authors ("[AUTHORS: ...]") are removed before submission and are not the paper's prose.
        profile = style_profile.profile_text(strip_notes(text), suffix == ".tex", smells, kobak)
        out.append({"key": key, "label": label, "words": profile["metrics"]["words"], "totals": profile["smell_totals"]})
    used = sorted({sid for version in out for sid in version["totals"]}, key=lambda sid: (sid[0], int(sid[1:] or 0)))
    return {"versions": out, "patterns": [{"id": sid, "name": smells[sid]["name"], "group": groups.get(sid[0], "")} for sid in used]}


def image_data(base: Path, name: str) -> tuple[str, str]:
    """A figure image as a data URI, so the dashboard stays one file; or why it could not be embedded."""
    path = (base / name).resolve()
    if not (path.is_file() and path.suffix.lower() in IMAGE_TYPES):
        return "", f"Not embedded: {Path(name).name} was not found."
    if path.stat().st_size > IMAGE_LIMIT:
        return "", f"Not embedded: {Path(name).name} is over 8 MB."
    return f"data:{IMAGE_TYPES[path.suffix.lower()]};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}", ""


def image_folders(base: Path, path: Path) -> list[Path]:
    """Where the manuscript's relative image paths point: beside the reviewed copy, then beside the original the
    run snapshotted (run.json sits above the inventory's folder)."""
    folders = [path.parent]
    for manifest in (base / "run.json", base.parent / "run.json"):
        if manifest.is_file():
            try:
                folders += [Path(source["original"]).parent for source in json.loads(manifest.read_text(encoding="utf-8")).get("inputs", [])]
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
    return folders


def _guard() -> Any:
    """manuscript-prose-edit's claim guard: its ladders and checks draw the claim ladder."""
    if "dashboard_guard" not in sys.modules:
        spec = importlib.util.spec_from_file_location("dashboard_guard", GUARD)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["dashboard_guard"] = module  # dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
    return sys.modules["dashboard_guard"]


# The changes a claim can undergo besides a move on a ladder, in the guard's kinds.
CLAIM_MARKERS = ("generality", "scope", "limitation", "null_result", "evidence_status")


def claim_movements(original: str, proposed: str, requested: Path | None) -> dict | None:
    """How the corrected version moved each claim of the reviewed text: a move on the causal or the evidential ladder
    (from its rung before to its rung after, with what asked for it when the run recorded its requested claim
    changes), the scope, limits, null results and generality it gained or lost, and each sentence of the title,
    Abstract or Conclusions that claims more than the body. None when nothing moved."""
    import yaml

    guard = _guard()
    entries = None
    if requested is not None and requested.is_file():
        try:
            entries = guard.parse_authorisations(yaml.safe_load(requested.read_text(encoding="utf-8")))
        except (yaml.YAMLError, ValueError):
            entries = None
    original, proposed = strip_notes(original), strip_notes(proposed)
    report = guard.compare(original, proposed, revision=True, authorised=entries)
    title = report.get("title")
    ladders = {"causal": (guard.CAUSAL, guard.CAUSAL_PLAIN, guard.CAUSAL_WORDS),
               "evidential": (guard.EVIDENTIAL, guard.EVIDENTIAL_PLAIN, guard.EVIDENTIAL_WORDS)}

    def level(text: str, ladder: str) -> int:
        rungs, plain, _ = ladders[ladder]
        return max((lv for lv, _, _ in guard._ladder(text, rungs)), default=plain)

    axes = {}
    for ladder, (rungs, plain, words) in ladders.items():
        names = dict(sorted({(r.level, r.name) for r in rungs}))
        axes[ladder] = [{"level": lv, "label": words.get(name, name) + (" or a plain statement" if lv == plain else "")}
                        for lv, name in names.items()]
    moves, others = [], []
    for c in report["sentence_changes"]:
        where = guard._section(c, title)
        line = c["after_line"] or c["before_line"]
        asked = list(c.get("authorised_by") or [])
        if c["kind"] in ladders and c["change"] in ("raised", "lowered", "mixed"):
            moves.append({"ladder": c["kind"], "from": level(c["before"], c["kind"]), "to": level(c["after"], c["kind"]),
                          "where": where, "line": line, "before": c["before"], "after": c["after"],
                          "asked_by": asked, "words": guard.describe(c)})
        elif c["kind"] in CLAIM_MARKERS:
            others.append({"kind": c["kind"], "change": c["change"], "where": where, "line": line,
                           "before": c["before"], "after": c["after"], "asked_by": asked, "words": guard.describe(c)})
    try:
        checked = guard.summary_check(proposed)
    except ValueError:  # a text without headings has no Abstract or body to compare
        checked = {"findings": []}
    summary = []
    for f in checked["findings"]:
        item = {"kind": f["kind"], "where": guard._summary_place(f, title), "sentence": f["sentence"],
                "body": guard._section({"section": f["body_section"]}, title) + f" (line {f['body_line']})",
                "body_sentence": f["body_sentence"], "words": guard._summary_problem(f)}
        if f["kind"] in ladders:
            item |= {"ladder": f["kind"], "from": level(f["body_sentence"], f["kind"]), "to": level(f["sentence"], f["kind"])}
        summary.append(item)
    if not (moves or others or summary):
        return None
    return {"axes": axes, "moves": moves, "others": others, "summary": summary, "requested": entries is not None}


def dashboard_html(data: Inventory, summary: dict, base: Path | None = None, revision: dict | None = None,
                   writing: dict | None = None, claims: dict | None = None, recheck: dict | None = None) -> str:
    """The template with the inventory inlined as JSON and the reviewed and corrected texts rendered as HTML.

    Evidence keeps its file name and the skill folder it came from, never a local path."""
    payload = data.model_dump(mode="json")
    for item in [*payload["coverage"], *payload["findings"], *payload["changes"]]:
        for source in item["evidence"]:
            source["skill"] = skill_of(source["path"])
            source["path"] = Path(source["path"]).name
    if payload["reference"]:
        payload["reference"]["source"]["path"] = Path(payload["reference"]["source"]["path"]).name
    # The re-check's verdict becomes each problem's resolution on the page; the inventory file keeps its own.
    for verdict in (recheck or {}).get("concerns", []):
        for finding in payload["findings"]:
            if finding["id"] == verdict["id"]:
                finding["resolution"] = RESOLVED_AS[verdict["verdict"]]
                finding["recheck"] = {k: verdict[k] for k in ("verdict", "quote", "why")}
    for item in (payload["figures"] or {}).get("items", []):
        for key in ("image", "proposed_image"):
            if item[key]:
                item[f"{key}_data"], item[f"{key}_note"] = image_data(base, item[key]) if base is not None else ("", "")
                item[key] = Path(item[key]).name
    paper = ""
    if base is not None and data.manuscript and data.manuscript.path:
        path = (base / data.manuscript.path).resolve()
        paper = manuscript_html(path.read_text(encoding="utf-8"), path.suffix.lower(), image_folders(base, path))
    if payload["manuscript"]:
        payload["manuscript"].pop("path", None)
    hashes = [{"file": Path(path).name, "sha256": value} for path, value in summary.get("evidence_sha256", {}).items()]
    corrected = {key: value for key, value in revision.items() if key not in {"body_html", "pieces"}} if revision else None
    document = {"inventory": payload, "summary": {**summary, "evidence_sha256": hashes}, "has_paper": bool(paper),
                "revision": corrected, "writing": writing, "claims": claims, "recheck": recheck,
                "decisions": decision_list(data),
                "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    template = TEMPLATE.read_text(encoding="utf-8")
    return (template.replace("__TITLE__", html.escape(data.title)).replace("__MANUSCRIPT_HTML__", paper)
            .replace("__REVISION_HTML__", revision["body_html"] if revision else "")
            .replace("__INVENTORY_JSON__", inline(document)))


def render(source: Path, output_dir: Path, revision: Path | None = None) -> dict:
    data = Inventory.model_validate_json(source.read_text(encoding="utf-8"))
    base = source.resolve().parent
    hashes = verify_evidence(data, base)
    summary = summarize(data)
    summary["evidence_sha256"] = hashes
    summary["inventory_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    versions = []
    if data.manuscript and data.manuscript.path:
        path = (base / data.manuscript.path).resolve()
        versions.append(("original", f"Reviewed version{f' ({data.manuscript.version})' if data.manuscript.version else ''}",
                         path.read_text(encoding="utf-8"), path.suffix.lower()))
    corrected = claims = recheck = None
    if revision is not None:
        corrected = json.loads((revision / "revision.json").read_text(encoding="utf-8"))
        if corrected.get("inventory_sha256") != summary["inventory_sha256"]:
            raise ValueError("The corrected version was built from another inventory; rebuild it with revise.py from this one.")
        suffix = versions[0][3] if versions else ".md"
        # revise.py names the texts after the manuscript's own extension (proposed.tex); older runs wrote .md.
        files = corrected.get("files") or {"revised": "revised.md", "proposed": "proposed.md"}
        proposed = (revision / files["proposed"]).read_text(encoding="utf-8")
        versions += [("revised", "After the applied edits", (revision / files["revised"]).read_text(encoding="utf-8"), suffix),
                     ("proposed", "Corrected version", proposed, suffix)]
        # The text for the dashboard's save button. A corrected version built before questions became comments
        # may still carry notes in its text: they are listed, to be removed.
        corrected.setdefault("comments", [])
        corrected.setdefault("notes_in_text", [{"note": proposed[a:b], "line": proposed.count("\n", 0, a) + 1}
                                               for a, b in author_notes(proposed)])
        corrected["text"] = proposed
        # The proposals the corrected version holds back are out of play, so they join no competing group.
        held = {h["id"] for h in corrected.get("held", [])}
        summary["competing_proposals"] = competing([c for c in data.changes if c.id not in held])
        summary["revision"] = {key: len(corrected.get(key) or []) for key in ("applied", "proposed_in_this_version", "held",
                                                                                 "alternatives", "not_placed", "restored")}
        summary["revision"]["proposed_sha256"] = corrected["proposed_sha256"]
        summary["revision"] |= {"questions": len(corrected["comments"]), "notes_in_text": len(corrected["notes_in_text"]),
                                "notes_in_working_copy": len(corrected.get("notes_in_working_copy") or [])}
        if versions[0][0] == "original":  # the claim ladder compares the reviewed text with the corrected one
            claims = claim_movements(versions[0][2], proposed, revision.parent / "requested-claims.yaml")
        found = newest_attempt(revision.parent / "recheck.json", folder=False)
        if found is not None:
            checked = Recheck.model_validate_json(found.read_text(encoding="utf-8"))
            if unknown := {c.id for c in checked.concerns} - {f.id for f in data.findings}:
                raise ValueError(f"The re-check names problems this inventory does not have: {sorted(unknown)}")
            # A re-check reads one build; edits held or reversed after it make a later build, which it predates.
            recheck = checked.model_dump(mode="json") | {"current": checked.proposed_sha256 == corrected["proposed_sha256"]}
            summary["recheck"] = {"verdicts": {v: sum(c.verdict == v for c in checked.concerns)
                                               for v in ("fully", "partly", "not", "worse", "unchecked")},
                                  "introduced": sum(p.origin == "introduced" for p in checked.new_problems),
                                  "missed": sum(p.origin == "missed" for p in checked.new_problems),
                                  "current": recheck["current"]}
        if claims:
            moves = claims["moves"]
            summary["claims"] = {"lowered": sum(m["to"] < m["from"] for m in moves),
                                 "raised": sum(m["to"] > m["from"] for m in moves),
                                 "raised_not_asked": sum(m["to"] > m["from"] and not m["asked_by"] for m in moves)
                                 if claims["requested"] else None,
                                 "other": len(claims["others"]), "summary_over_body": len(claims["summary"])}
    writing = writing_patterns(versions) if versions else None
    if writing:
        summary["writing_patterns"] = {v["key"]: {"words": v["words"], "hits": sum(v["totals"].values()), "by_pattern": v["totals"]}
                                       for v in writing["versions"]}
    outputs = {"manuscript-dashboard.html": dashboard_html(data, summary, base, corrected, writing, claims, recheck),
               "summary.json": json.dumps(summary, ensure_ascii=False, indent=2) + "\n"}
    if any((output_dir / name).exists() for name in outputs):
        raise ValueError(f"Output files already exist in {output_dir.name}; render this attempt into "
                         f"{next_attempt(output_dir, folder=True).name} to keep the previous one.")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in outputs.items():
        (output_dir / name).write_text(value, encoding="utf-8")
    return summary


@app.command()
def main(source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
         output_dir: Annotated[Path, typer.Option("--output-dir")],
         revision: Annotated[Path | None, typer.Option(help="The corrected version: revise.py's output folder",
                                                       exists=True, file_okay=False)] = None) -> None:
    try:
        summary = render(source, output_dir, revision)
    except (ValueError, OSError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps({"output_dir": str(output_dir.resolve()), "counts": summary["counts"],
                           "benchmark": summary["benchmark"]}, indent=2))


if __name__ == "__main__":
    utf8_console()
    app()
