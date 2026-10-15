# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Rank candidate venues by how much friction their AI policy puts on an AI-assisted manuscript, and print
one venue's requirements as a checklist for adapting a manuscript to it.

The data is manuscript-integrity-check/references/venues.yaml (keep the two skills side by side).

    uv run --script venues.py rank                        # all venues, least friction first
    uv run --script venues.py rank --ai-use revision --min-jif 5 --software
    uv run --script venues.py show bioinformatics
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)

VENUES_YAML = (Path(__file__).resolve().parents[2] / "manuscript-integrity-check" / "references" / "venues.yaml")
STALE_AFTER_DAYS = 60

WRITING_COST = {"free": 0, "disclose": 1, "disclose_all": 2, "red_line": 2, "banned_drafting": 4}
PROMPT_COST = {"no": 0, "on_request": 1, "encouraged": 1, "required": 3}
SCREENING_COST = {"plagiarism": 0, "integrity_signals": 1, "may_detect_ai": 1, "ai_detector_deployed": 2}


class AiUse(str, Enum):
    polish = "polish"  # spelling, grammar, clarity edits of author-written text
    revision = "revision"  # substantive rewording and restructuring of author-written text
    drafting = "drafting"  # new sentences or sections written by the model


def load_venues() -> tuple[date, dict[str, dict[str, Any]]]:
    raw = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))
    venues: dict[str, dict[str, Any]] = raw["venues"]
    resolved = {key: _resolve(key, venues, set()) for key in venues}
    return raw["checked"], resolved


def _resolve(key: str, venues: dict[str, dict[str, Any]], seen: set[str]) -> dict[str, Any]:
    """A venue's own fields over the fields of the venue it `inherits`."""
    if key in seen:
        raise typer.BadParameter(f"inheritance cycle at {key}")
    entry = venues[key]
    parent = entry.get("inherits")
    base = _resolve(parent, venues, seen | {key}) if parent else {}
    return {**base, **{k: v for k, v in entry.items() if k != "inherits"}}


def friction(v: dict[str, Any]) -> tuple[Optional[int], list[str]]:
    """Points, and the reasons behind them. None when the policy was not researched."""
    if v.get("writing_help") is None:
        return None, ["policy not researched"]
    reasons: list[str] = []
    score = WRITING_COST[v["writing_help"]]
    reasons.append(f"writing help: {v['writing_help']}")
    p = PROMPT_COST.get(v.get("prompts") or "no", 0)
    if p:
        score += p
        reasons.append(f"prompts {v['prompts']}")
    s = SCREENING_COST.get(v.get("screening") or "plagiarism", 0)
    if s:
        score += s
        reasons.append(f"screening: {v['screening']}")
    extra_places = max(0, len(v.get("disclosure_places") or []) - 2)
    if extra_places:
        score += extra_places
        reasons.append(f"{len(v['disclosure_places'])} disclosure places")
    burden = v.get("extra_burden") or []
    score += len(burden)
    reasons += burden
    if v.get("tracking") == "recommended":
        score += 1
        reasons.append("policy says to keep records of AI use")
    return score, reasons


def verdict(v: dict[str, Any], ai_use: AiUse) -> str:
    """What the venue's writing rule means for this kind of AI use."""
    rule = v.get("writing_help")
    if rule is None:
        return "unknown: read the live page"
    if rule == "banned_drafting":
        return {AiUse.polish: "fine: acknowledge in 3 places incl. a short supplementary note",
                AiUse.revision: "grey zone: an author pass over AI-revised text + a short supplementary note",
                AiUse.drafting: "incompatible unless authors rewrite the AI-drafted text"}[ai_use]
    if rule == "red_line":
        return {AiUse.polish: "fine, declare",
                AiUse.revision: "fine, declare (Amber)",
                AiUse.drafting: "Results and Discussion must be author-written (Red)"}[ai_use]
    if rule == "disclose_all":
        return "fine, but every use is declared" + (" and full prompts are required"
                                                    if v.get("prompts") == "required" else "")
    if rule == "disclose":
        return "fine, polish exempt" if ai_use == AiUse.polish else "fine, declare"
    return "fine"


@app.command()
def rank(
    ai_use: Annotated[AiUse, typer.Option(help="What AI did to the text")] = AiUse.revision,
    min_jif: Annotated[Optional[float], typer.Option(help="Drop venues below this JIF (and those without one)")] = None,
    software: Annotated[bool, typer.Option(help="Only venues with a software article type")] = False,
    strictest_first: Annotated[bool, typer.Option(help="Sort the most demanding venues first")] = False,
    include_tracking: Annotated[bool, typer.Option(
        help="Also list venues that require recording AI use beyond one acknowledgement")] = False,
) -> None:
    """Venues by AI-policy friction, with what each means for the given AI use."""
    checked, venues = load_venues()
    rows = []
    left_out: list[str] = []
    for key, v in venues.items():
        if v.get("tracking") == "required" and not include_tracking:
            left_out.append(f"{v.get('name', key)} ({'; '.join(v.get('extra_burden') or [])})")
            continue
        if min_jif is not None and (v.get("jif") is None or v["jif"] < min_jif):
            continue
        if software and not v.get("software_article"):
            continue
        score, reasons = friction(v)
        rows.append((score, key, v, reasons))
    unknown_last = 99 if not strictest_first else -1
    rows.sort(key=lambda r: (r[0] if r[0] is not None else unknown_last), reverse=strictest_first)
    typer.echo(f"Venue AI-policy friction (policies read {checked}; re-check the live page before submitting)\n")
    typer.echo("| friction | venue | JIF | screening | for AI use: " + ai_use.value + " | why |")
    typer.echo("|---:|---|---:|---|---|---|")
    for score, key, v, reasons in rows:
        typer.echo(f"| {'?' if score is None else score} | {v.get('name', key)} (`{key}`) | {v.get('jif') or 'n/a'} "
                   f"| {v.get('screening') or '?'} | {verdict(v, ai_use)} | {'; '.join(reasons)} |")
    if left_out:
        typer.echo("\nLeft out because they require recording AI use beyond one acknowledgement "
                   "(--include-tracking lists them): " + "; ".join(left_out))
    _warn_if_stale(checked)


@app.command()
def show(venue: Annotated[str, typer.Argument(help="Venue key, e.g. bioinformatics")]) -> None:
    """One venue's requirements, as the checklist for adapting a manuscript to it."""
    checked, venues = load_venues()
    if venue not in venues:
        raise typer.BadParameter(f"unknown venue {venue!r}; known: {', '.join(sorted(venues))}")
    v = venues[venue]
    score, reasons = friction(v)

    def items(field: str) -> str:
        values = v.get(field)
        if values is None:
            return "  - not researched: read the live page\n"
        if not values:
            return "  - none\n"
        return "".join(f"  - [ ] {x}\n" for x in values)

    limits = v.get("limits")
    limit_text = ("not researched: read the live page" if not limits else
                  f"abstract ≤ {limits['abstract_words']} words; body ≈ {limits['body_words']} words; "
                  f"returned without review at {round(100 * (limits['over_limit_return'] - 1))}% over")
    out = [
        f"# {v.get('name', venue)}: adaptation checklist",
        "",
        f"Publisher: {v.get('publisher', '?')}. JIF: {v.get('jif') or 'n/a'}. Status of this entry: "
        f"{v.get('status', '?')}, read {checked}. Author guidelines: {v.get('url', '?')}",
        f"AI policy: {v.get('ai_policy_url') or v.get('url', '?')}",
        "",
        f"AI-policy friction: {'?' if score is None else score} ({'; '.join(reasons)}).",
        f"Writing help: **{v.get('writing_help') or 'not researched'}**. Exempt from disclosure: "
        f"{', '.join(v.get('exempt') or []) or 'nothing'}. Prompts: {v.get('prompts') or '?'}.",
        f"Screening: {v.get('screening') or '?'}" + (f" ({v['screening_note']})" if v.get("screening_note") else "") + ".",
        "",
        "- AI disclosure goes in:",
        items("disclosure_places").rstrip("\n"),
        "- and states:",
        items("disclosure_fields").rstrip("\n"),
        "- Extra work this venue asks for:",
        items("extra_burden").rstrip("\n"),
        f"- Length: {limit_text}",
        "- Abstract headings:",
        items("abstract_headings").rstrip("\n"),
        "- Required sections:",
        items("required_sections").rstrip("\n"),
        "- Software and availability:",
        items("software").rstrip("\n"),
        "- Other desk rules:",
        items("other_desk_rules").rstrip("\n"),
        "- Penalties stated: " + (", ".join(v.get("penalties") or []) or "none found"),
    ]
    if v.get("fit_note"):
        out += ["", f"Fit note: {v['fit_note']}"]
    typer.echo("\n".join(out))
    _warn_if_stale(checked)


def _warn_if_stale(checked: date) -> None:
    age = (date.today() - checked).days
    if age > STALE_AFTER_DAYS:
        typer.echo(f"\nWARNING: venue data is {age} days old; policies changed several times in 2026. "
                   f"Re-read the pages and update venues.yaml.", err=True)


if __name__ == "__main__":
    app()
