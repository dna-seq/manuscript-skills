# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "httpx>=0.27"]
# ///
"""Rank candidate venues by how much friction their AI policy puts on an AI-assisted manuscript, print one
venue's requirements as a checklist, and list where named researchers publish.

The data is manuscript-integrity-check/references/venues.yaml (keep the two skills side by side); the read
date of each policy page comes from policy-snapshots/index.yaml, written by policy_watch.py.

    uv run --script venues.py rank                                    # all journals, least friction first
    uv run --script venues.py rank --ai-use drafting --field aging --refuse prompts --refuse ai-detector
    uv run --script venues.py rank --field bioinformatics --type software --min-jif 4
    uv run --script venues.py show <venue-key>                        # keys are listed by `rank`
    uv run --script venues.py peers "First Last" "Other Name" --since 2019
"""

from __future__ import annotations

import os
import re
import unicodedata
from collections import Counter
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Optional

import httpx
import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)

REFERENCES = Path(__file__).resolve().parents[2] / "manuscript-integrity-check" / "references"
VENUES_YAML = REFERENCES / "venues.yaml"
SNAPSHOT_INDEX = REFERENCES / "policy-snapshots" / "index.yaml"
STALE_AFTER_DAYS = 60
OPENALEX = "https://api.openalex.org"

WRITING_COST = {"free": 0, "disclose": 1, "disclose_all": 2, "red_line": 2, "banned_drafting": 4}
PROMPT_COST = {"no": 0, "on_request": 1, "encouraged": 1, "required": 3}
SCREENING_COST = {"plagiarism": 0, "integrity_signals": 1, "may_detect_ai": 1, "ai_detector_deployed": 2}
# Friction points -> the word the ranking prints. The points are the sum explained in `friction`.
TIERS = [(1, "light"), (3, "moderate"), (5, "heavy")]
SEVERE = "severe"


class AiUse(str, Enum):
    polish = "polish"  # spelling, grammar, clarity edits of author-written text
    revision = "revision"  # substantive rewording and restructuring of author-written text
    drafting = "drafting"  # new sentences or sections written by the model


class StudyDesign(str, Enum):
    public_data = "public-data"
    bioinformatics = "bioinformatics"
    mr = "mr"
    bibliometric = "bibliometric"
    public_health_database = "public-health-database"
    other = "other"


class Validation(str, Enum):
    none = "none"
    independent_cohort = "independent-cohort"
    wet_lab = "wet-lab"
    multi_database = "multi-database"
    primary_analysis = "primary-analysis"


class Burden(str, Enum):
    """Things an author can refuse in the interview; each excludes the venues that impose it."""
    drafting_ban = "drafting-ban"  # LLM drafting from a prompt forbidden (writing_help: banned_drafting)
    red_line = "red-line"  # AI-written results or discussion forbidden (writing_help: red_line)
    prompts = "prompts"  # prompts required or encouraged in the paper
    tracking = "tracking"  # AI use recorded beyond one acknowledgement (outputs deposited, versions kept)
    ai_detector = "ai-detector"  # AI-text detection named on the policy page
    supplement = "supplement"  # AI use documented in supplementary material as well
    multi_place = "multi-place"  # disclosure in three or more places
    disclosure_penalty = "disclosure-penalty"  # page says disclosed AI use may count against the paper


# ------------------------------------------------------------------------------------------------ data

def load_venues() -> tuple[date, dict[str, dict[str, Any]]]:
    raw = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))
    venues: dict[str, dict[str, Any]] = raw["venues"]
    resolved = {key: _resolve(key, venues, set()) for key in venues}
    return raw["checked"], resolved


def _resolve(key: str, venues: dict[str, dict[str, Any]], seen: set[str]) -> dict[str, Any]:
    """A venue's own fields over the fields of the venue it `inherits` (`kind` and URLs are never inherited
    from a publisher default, so a journal does not pose as the publisher or claim its sources)."""
    if key in seen:
        raise typer.BadParameter(f"inheritance cycle at {key}")
    if key not in venues:
        raise typer.BadParameter(f"{sorted(seen)[0] if seen else key} inherits unknown venue {key!r}")
    entry = venues[key]
    parent = entry.get("inherits")
    base = dict(_resolve(parent, venues, seen | {key})) if parent else {}
    # Timelines and editorial assessments describe a journal, not its parent or sibling.
    for journal_specific in ("review_speed", "editorial_profile"):
        base.pop(journal_specific, None)
    if base.get("kind") == "publisher":
        base.pop("kind")
        base.pop("name", None)
        base["publisher_policy_url"] = base.get("ai_policy_url") or base.get("url")
        for own in ("url", "sources", "jif", "jif_year", "fields", "article_types", "openalex", "aliases", "fit_note"):
            base.pop(own, None)
    return {**base, **{k: v for k, v in entry.items() if k != "inherits"}, "key": key}


def journals(venues: dict[str, dict[str, Any]], preprints: bool = False) -> dict[str, dict[str, Any]]:
    """Journals, or with `preprints` the preprint servers; never the publisher defaults."""
    kind = "preprint" if preprints else None
    return {k: v for k, v in venues.items() if v.get("kind") == kind}


def policy_urls(v: dict[str, Any]) -> list[str]:
    urls = [v.get("ai_policy_url"), v.get("publisher_policy_url"), v.get("url"), *(v.get("sources") or [])]
    return list(dict.fromkeys(u for u in urls if u))


def load_snapshot_index() -> dict[str, dict[str, Any]]:
    if not SNAPSHOT_INDEX.exists():
        return {}
    return yaml.safe_load(SNAPSHOT_INDEX.read_text(encoding="utf-8")) or {}


def policy_read(v: dict[str, Any], checked: date, index: dict[str, dict[str, Any]]) -> date:
    """When this venue's AI policy was last read: the oldest read date among its policy pages that the watcher has
    read, else the venue's own `checked`, else the file's."""
    dates = [date.fromisoformat(str(index[u]["read"])) for u in policy_urls(v) if index.get(u, {}).get("read")]
    if dates:
        return min(dates)
    return v.get("checked") or checked


def burdens(v: dict[str, Any]) -> set[Burden]:
    out: set[Burden] = set()
    if v.get("writing_help") == "banned_drafting":
        out.add(Burden.drafting_ban)
    if v.get("writing_help") == "red_line":
        out.add(Burden.red_line)
    if v.get("prompts") in ("required", "encouraged"):
        out.add(Burden.prompts)
    if v.get("tracking") == "required":
        out.add(Burden.tracking)
    if v.get("screening") in ("may_detect_ai", "ai_detector_deployed"):
        out.add(Burden.ai_detector)
    if any("supplement" in str(x).lower() for x in [*(v.get("disclosure_places") or []), *(v.get("extra_burden") or [])]):
        out.add(Burden.supplement)
    if len(v.get("disclosure_places") or []) >= 3:
        out.add(Burden.multi_place)
    if v.get("disclosure_neutral") is False:
        out.add(Burden.disclosure_penalty)
    return out


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
    if v.get("disclosure_neutral") is False:
        score += 1
        reasons.append("disclosed AI use may count against the paper")
    return score, reasons


def tier(score: Optional[int]) -> str:
    if score is None:
        return "?"
    return next((word for limit, word in TIERS if score <= limit), SEVERE)


def verdict(v: dict[str, Any], ai_use: AiUse) -> str:
    """What the venue's writing rule means for this kind of AI use."""
    rule = v.get("writing_help")
    if rule is None:
        return "unknown: read the live page"
    if rule == "banned_drafting":
        return {AiUse.polish: "correction allowed in cached policy; verify applicable disclosure requirements",
                AiUse.revision: "uncertain: verify whether the current rule permits this revision",
                AiUse.drafting: "incompatible with cached drafting ban; consider another venue or verify "
                                "compatibility (an author rewrite alone does not establish it)"}[ai_use]
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


def _has_type(v: dict[str, Any], wanted: list[str]) -> bool:
    types = set(v.get("article_types") or [])
    if v.get("software_article"):
        types.add("software")
    return bool(types & set(wanted))


def validation_fit(v: dict[str, Any], study: Optional[str] = None,
                   available: Optional[set[str]] = None) -> tuple[str, str]:
    """Resource fit under recorded rules only; unknown is not permission or an author veto."""
    if study and study in (v.get("excluded_study_designs") or []):
        return "no-go", f"recorded scope excludes {study}"
    rules = v.get("validation_requirements")
    if rules is None:
        return "unknown", "validation requirements not researched"
    applicable = [r for r in rules if study is None or study in r.get("applies_to", [])]
    if not applicable:
        return "unknown", "no applicable validation rule recorded for this design"
    outcomes: list[tuple[str, str]] = []
    for rule in applicable:
        options = set(rule.get("accepted_any") or [])
        description = rule.get("description") or "check the recorded validation requirement"
        if study is None or available is None or rule.get("strength") != "required" or not options:
            outcomes.append(("conditional", description))
        elif options & available:
            outcomes.append(("go", "recorded validation route available: " + ", ".join(sorted(options & available))))
        else:
            outcomes.append(("no-go", "none of the recorded alternatives available: " + ", ".join(sorted(options))))
    severity = {"go": 0, "conditional": 1, "unknown": 2, "no-go": 3}
    worst = max(outcomes, key=lambda item: severity[item[0]])[0]
    return worst, "; ".join(dict.fromkeys(reason for _, reason in outcomes))


def _jif(v: dict[str, Any]) -> str:
    if v.get("jif") is None:
        return "n/a"
    return f"{v['jif']}" + (f" ({v['jif_year']})" if v.get("jif_year") else "")


# ------------------------------------------------------------------------------------------------ commands

@app.command()
def rank(
    ai_use: Annotated[AiUse, typer.Option(help="What AI did to the text")] = AiUse.revision,
    field: Annotated[Optional[list[str]], typer.Option(
        help="Keep venues tagged with any of these fields (aging, bioinformatics, genomics, genetics, "
             "systems-biology, clinical, general, data, software); repeatable")] = None,
    article_type: Annotated[Optional[list[str]], typer.Option(
        "--type", help="Keep venues that take this article type (research, methods, software, database, data, "
                       "review, perspective, letter); repeatable")] = None,
    oa: Annotated[Optional[list[str]], typer.Option(help="Keep these access models: full, hybrid, subscription")] = None,
    min_jif: Annotated[Optional[float], typer.Option(help="Drop venues below this JIF (and those without one)")] = None,
    max_friction: Annotated[Optional[int], typer.Option(help="Drop venues above this many friction points")] = None,
    refuse: Annotated[Optional[list[Burden]], typer.Option(
        help="Drop venues that impose this; repeatable")] = None,
    only: Annotated[Optional[list[str]], typer.Option(help="Only these venue keys (e.g. from `peers`)")] = None,
    preprints: Annotated[bool, typer.Option(help="Rank preprint servers (arXiv, bioRxiv, ...) instead of journals")] = False,
    software: Annotated[bool, typer.Option(help="Only venues with a software article type")] = False,
    strictest_first: Annotated[bool, typer.Option(help="Sort the most demanding venues first")] = False,
    include_tracking: Annotated[bool, typer.Option(
        help="Also list venues that require recording AI use beyond one acknowledgement")] = False,
    study_design: Annotated[Optional[StudyDesign], typer.Option(
        help="Study design for validation/scope feasibility")] = None,
    validation_available: Annotated[Optional[list[Validation]], typer.Option(
        help="Validation already available or affordable; repeatable; use 'none' explicitly when unavailable")] = None,
) -> None:
    """Journals (or preprint servers) by AI-policy friction, with what each means for the given AI use."""
    checked, venues = load_venues()
    index = load_snapshot_index()
    refused = set(refuse or [])
    available = {value.value for value in validation_available} if validation_available is not None else None
    if available and "none" in available and len(available) > 1:
        raise typer.BadParameter("'none' cannot be combined with an available validation route")
    rows = []
    left_out: list[str] = []
    for key, v in journals(venues, preprints).items():
        if only and key not in only:
            continue
        if field and not set(v.get("fields") or []) & set(field):
            continue
        if (article_type or software) and not _has_type(v, (article_type or []) + (["software"] if software else [])):
            continue
        if oa and v.get("oa") not in oa:
            continue
        if min_jif is not None and (v.get("jif") is None or v["jif"] < min_jif):
            continue
        hit = burdens(v) & refused
        if hit:
            continue
        if v.get("tracking") == "required" and not include_tracking and Burden.tracking not in refused:
            left_out.append(f"{v.get('name', key)} ({'; '.join(v.get('extra_burden') or [])})")
            continue
        score, reasons = friction(v)
        if max_friction is not None and (score is None or score > max_friction):
            continue
        rows.append((score, key, v, reasons))
    unknown_last = 99 if not strictest_first else -1
    rows.sort(key=lambda r: (r[0] if r[0] is not None else unknown_last, -(r[2].get("jif") or 0)),
              reverse=strictest_first)
    if study_design is not None or available is not None:
        # Stable sort: an impossible validation budget cannot be compensated by a light AI policy.
        order = {"go": 0, "conditional": 1, "unknown": 2, "no-go": 3}
        rows.sort(key=lambda r: order[validation_fit(
            r[2], study_design.value if study_design else None, available)[0]])
    typer.echo(f"Venue AI-policy friction for AI use '{ai_use.value}' ({len(rows)} "
               f"{'preprint servers' if preprints else 'journals'}; re-read the live page of any venue you shortlist "
               "before submitting)\n")
    typer.echo("Friction measures administrative burden, not enforcement probability or an assistant veto.\n")
    typer.echo("| friction | venue | validation/resource fit | JIF | OA | screening | for this AI use | why | policy read |")
    typer.echo("|---:|---|---|---:|---|---|---|---|---|")
    stale = 0
    for score, key, v, reasons in rows:
        read = policy_read(v, checked, index)
        stale += (date.today() - read).days > STALE_AFTER_DAYS
        fit, fit_reason = validation_fit(v, study_design.value if study_design else None, available)
        typer.echo(f"| {'?' if score is None else score} {tier(score)} | {v.get('name', key)} (`{key}`) "
                   f"| {fit}: {fit_reason} | {_jif(v)} "
                   f"| {v.get('oa') or '?'} | {v.get('screening') or '?'} | {verdict(v, ai_use)} "
                   f"| {'; '.join(reasons)} | {read} |")
    typer.echo("\nResource fit covers recorded validation/scope rules only; unknown is not approval. "
               "Open science, editorial openness, costs and comparable review times need a full selection review.")
    if left_out:
        typer.echo("\nLeft out because they require recording AI use beyond one acknowledgement "
                   "(--include-tracking lists them): " + "; ".join(left_out))
    if stale:
        typer.echo(f"\nWARNING: {stale} of these policies were read more than {STALE_AFTER_DAYS} days ago; run "
                   "policy_watch.py check --stale-days 60 --update and review what moved.", err=True)


@app.command()
def show(venue: Annotated[str, typer.Argument(help="Venue key, as listed by `rank`")]) -> None:
    """One venue's requirements, as the checklist for adapting a manuscript to it."""
    checked, venues = load_venues()
    if venue not in venues:
        raise typer.BadParameter(f"unknown venue {venue!r}; known: {', '.join(sorted(venues))}")
    v = venues[venue]
    index = load_snapshot_index()
    score, reasons = friction(v)

    def items(field: str) -> str:
        values = v.get(field)
        if values is None:
            return "  - not researched: read the live page\n"
        if not values:
            return "  - none\n"
        return "".join(f"  - [ ] {x}\n" for x in values)

    def tri(value: Optional[bool], yes: str, no: str) -> str:
        return "not stated" if value is None else (yes if value else no)

    limits = v.get("limits") or {}
    parts = [f"abstract ≤ {limits['abstract_words']} words" if limits.get("abstract_words") else None,
             f"body ≈ {limits['body_words']} words" if limits.get("body_words") else None,
             f"returned without review at {round(100 * (limits['over_limit_return'] - 1))}% over"
             if limits.get("over_limit_return") else None]
    limit_text = "; ".join(x for x in parts if x) or "not researched: read the live page"
    exemptions = ("not researched" if v.get("exempt") is None
                  else ", ".join(v["exempt"]) or "none listed in the cached policy")
    sources = []
    for u in policy_urls(v):
        e = index.get(u, {})
        att = e.get("last_attempt")
        sources.append(f"  - {u}: " + (f"read {e['read']} via {e['route']}, {e.get('passages', 0)} AI passages"
                                       if e.get("read") else "not yet read by policy_watch.py")
                       + (f"; last attempt {att['date']} failed: {att['reason']}" if att else ""))
    out = [
        f"# {v.get('name', venue)}: adaptation checklist",
        "",
        f"Publisher: {v.get('publisher', '?')}. JIF: {_jif(v)}. Access: {v.get('oa') or '?'}. Fields: "
        f"{', '.join(v.get('fields') or []) or '?'}. Article types: {', '.join(v.get('article_types') or []) or '?'}.",
        f"Status of this entry: {v.get('status', '?')}; policy read {policy_read(v, checked, index)}. "
        f"Author guidelines: {v.get('url', '?')}",
        f"AI policy: {v.get('ai_policy_url') or v.get('publisher_policy_url') or v.get('url', '?')}",
        "",
        f"AI-policy friction: {'?' if score is None else score}, {tier(score)} ({'; '.join(reasons)}).",
        f"Writing help: **{v.get('writing_help') or 'not researched'}**. Exempt from disclosure: "
        f"{exemptions}. Prompts: {v.get('prompts') or '?'}.",
        f"Screening: {v.get('screening') or '?'}" + (f" ({v['screening_note']})" if v.get("screening_note") else "") + ".",
        "Declared AI use counting against the paper: "
        + tri(None if v.get("disclosure_neutral") is None else not v["disclosure_neutral"],
              "the page says it may", "the page says it does not") + ".",
        f"Reviewers and AI tools: {v.get('reviewer_ai') or 'not stated'}.",
        "",
        "- AI disclosure goes in:",
        items("disclosure_places").rstrip("\n"),
        "- and states:",
        items("disclosure_fields").rstrip("\n"),
        "- Extra work this venue asks for:",
        items("extra_burden").rstrip("\n"),
        "- AI in images and figures (not scored as friction):",
        items("image_rules").rstrip("\n"),
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
        "",
        "Verification limits (apply the current article-type rules and exemptions):",
        "- Observable in supplied materials: counts, headings, required statement fields and locations, links.",
        "- Testable with materials: reference support, deposited artifacts and code/data reproducibility.",
        "- Author-reported process: actual tool use, drafting history, complete logs and human oversight.",
        "- Editorial judgement / unknown enforcement: policy interpretation, AI attribution and screening outcomes.",
        "A policy conflict is the author's decision; these checks are advice, not an assistant veto.",
        "",
        "Policy pages (re-check: policy_watch.py check --venue " + venue + "):",
        *sources,
    ]
    if v.get("fit_note"):
        out += ["", f"Fit note: {v['fit_note']}"]
    if v.get("permitted_uses"):
        out += ["", "Permitted uses (not necessarily exempt from disclosure): "
                + "; ".join(v["permitted_uses"])]
    out += ["", "Selection profile (missing data means not researched):"]
    for profile_field in ("validation_requirements", "excluded_study_designs", "open_science",
                          "editorial_profile", "review_speed", "publication_costs"):
        value = v.get(profile_field)
        rendered = ("not researched" if value is None else
                    yaml.safe_dump(value, sort_keys=False, allow_unicode=True).rstrip())
        out += [f"- {profile_field}:", "\n".join("  " + line for line in rendered.splitlines())]
    typer.echo("\n".join(out))


def _fold(name: str) -> str:
    """Journal or person name folded for matching: accents, case, punctuation, a leading 'the', a parenthetical."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = re.sub(r"\([^)]*\)", " ", name).replace("&", " and ")
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    return re.sub(r"^the ", "", name)


def _openalex(path: str, **params: Any) -> dict[str, Any]:
    if os.environ.get("OPENALEX_MAILTO"):
        params["mailto"] = os.environ["OPENALEX_MAILTO"]
    r = httpx.get(f"{OPENALEX}/{path}", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _author_ids(name: str) -> tuple[list[str], list[str]]:
    """The OpenAlex author record with this exact (folded) name and the most works, plus the other candidates."""
    found = [a for a in _openalex("authors", search=name, **{"per-page": 25})["results"]
             if _fold(a["display_name"]) == _fold(name)
             or sorted(_fold(a["display_name"]).split()) == sorted(_fold(name).split())]
    found.sort(key=lambda a: -a["works_count"])
    lines = [f"{a['id'].rsplit('/', 1)[-1]} {a['display_name']} ({a['works_count']} works; "
             f"{', '.join(i['display_name'] for i in (a.get('last_known_institutions') or [])[:2]) or 'no institution'})"
             for a in found]
    return [a["id"].rsplit("/", 1)[-1] for a in found[:1]], lines


@app.command()
def peers(
    names: Annotated[list[str], typer.Argument(help="Researchers whose publishing venues to list")],
    since: Annotated[int, typer.Option(help="First publication year counted")] = date.today().year - 6,
    author_id: Annotated[Optional[list[str]], typer.Option(
        help="OpenAlex author ids to use instead of name search (OpenAlex sometimes splits one person)")] = None,
) -> None:
    """Journals the named researchers published in (OpenAlex), matched against venues.yaml with their friction."""
    checked, venues = load_venues()
    by_source = {v["openalex"]: k for k, v in journals(venues).items() if v.get("openalex")}
    by_name: dict[str, str] = {}
    for k, v in journals(venues).items():
        for n in [v.get("name", ""), *(v.get("aliases") or [])]:
            by_name.setdefault(_fold(n), k)
    ids: list[tuple[str, str]] = [(a, a) for a in (author_id or [])]
    for name in names if not author_id else []:
        chosen, candidates = _author_ids(name)
        typer.echo(f"{name}: " + ("; ".join(candidates) if candidates else "no OpenAlex author with this name"))
        if len(candidates) > 1:
            typer.echo(f"  using {chosen[0]}; pass --author-id for others that are the same person")
        ids += [(name, c) for c in chosen]
    counts: Counter[tuple[str, str]] = Counter()
    who: dict[tuple[str, str], set[str]] = {}
    for label, aid in ids:
        cursor = "*"
        while cursor:
            page = _openalex("works", filter=f"author.id:{aid},from_publication_date:{since}-01-01",
                             select="primary_location", cursor=cursor, **{"per-page": 200})
            for w in page["results"]:
                src = (w.get("primary_location") or {}).get("source") or {}
                if src.get("type") != "journal":
                    continue
                key = (src["id"].rsplit("/", 1)[-1], src["display_name"])
                counts[key] += 1
                who.setdefault(key, set()).add(label)
            cursor = page["meta"].get("next_cursor") if page["results"] else None
    typer.echo(f"\nJournals since {since} ({sum(counts.values())} papers):\n")
    typer.echo("| papers | journal | who | venue key | friction | writing help |")
    typer.echo("|---:|---|---|---|---|---|")
    missing: list[str] = []
    matched: list[str] = []
    for (sid, name), n in counts.most_common():
        key = by_source.get(sid) or by_name.get(_fold(name))
        if key:
            score, _ = friction(venues[key])
            matched.append(key)
            typer.echo(f"| {n} | {name} | {', '.join(sorted(who[(sid, name)]))} | `{key}` "
                       f"| {'?' if score is None else score} {tier(score)} | {venues[key].get('writing_help') or '?'} |")
        else:
            missing.append(name)
            typer.echo(f"| {n} | {name} | {', '.join(sorted(who[(sid, name)]))} | not in venues.yaml | | |")
    if matched:
        typer.echo("\nRank just these: venues.py rank " + " ".join(f"--only {k}" for k in dict.fromkeys(matched)))
    if missing:
        typer.echo(f"\n{len(missing)} journals are not in venues.yaml; read their AI policy before recommending one.")


if __name__ == "__main__":
    app()
