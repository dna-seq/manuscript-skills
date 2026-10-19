# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "httpx>=0.27"]
# ///
"""Rank candidate venues by how much friction their AI policy puts on an AI-assisted manuscript, order a
shortlist into a journal ladder and a preprint ladder by the authors' priorities, print what every venue on a
ladder asks for, print one venue's requirements as a checklist, and list where named researchers publish.

The data is manuscript-integrity-check/references/venues.yaml (keep the two skills side by side); the read
date of each policy page comes from policy-snapshots/index.yaml, written by policy_watch.py. Facts researched
for one manuscript (review times, fees, preprint rules, author guidelines the catalogue lacks) and the authors'
priorities live in that manuscript's record and are passed with --record; the catalogue stays read-only.

    uv run --script venues.py rank                                    # all journals, least friction first
    uv run --script venues.py rank --ai-use drafting --field aging --refuse prompts --refuse ai-detector
    uv run --script venues.py rank --field bioinformatics --type software --min-jif 4
    uv run --script venues.py ladder --only KEY --only KEY --priority speed --priority reach --record REC.yaml
    uv run --script venues.py ladder --preprints --journal KEY --priority ai --record REC.yaml
    uv run --script venues.py common KEY KEY KEY --record REC.yaml    # what every venue on the ladder asks for
    uv run --script venues.py show <venue-key>                        # keys are listed by `rank`
    uv run --script venues.py peers "First Last" "Other Name" --since 2019
"""

from __future__ import annotations

import csv
import os
import re
import sys
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

WRITING_COST = {"free": 0, "disclose": 1, "disclose_all": 2, "red_line": 2, "banned_drafting": 5}
# Record-keeping is one cost however a policy words it: prompts on request, kept records, prompts in the paper.
RECORDS_COST = {"no": 0, "on_request": 1, "encouraged": 1, "recommended": 1, "required": 3}
# Paper-mill and plagiarism checks run at every large publisher and do not target AI-assisted writing.
SCREENING_COST = {"plagiarism": 0, "integrity_signals": 0, "may_detect_ai": 1, "ai_detector_deployed": 2}
MAX_BURDEN_POINTS = 2  # listed burdens differ in granularity between sources; more than two adds noise, not signal
# Friction points -> the word the ranking prints. The points are the sum explained in `friction`.
TIERS = [(1, "light"), (3, "moderate"), (5, "heavy")]
SEVERE = "severe"

# The catalogue's vocabulary in the words the authors read (README: no internal tokens in printed output).
WRITING_WORDS = {
    "free": "AI writing help needs no declaration",
    "disclose": "AI help is allowed if declared; only explicitly recorded exemptions apply",
    "disclose_all": "AI help is allowed, but every use must be declared, even language polish",
    "red_line": "AI help is allowed if declared, except that the results and discussion are reserved for the authors",
    "banned_drafting": "the journal asks authors not to have AI draft text; correction aids are allowed",
}
PROMPT_ASKS = {"on_request": "the prompts on request", "encouraged": "the prompts in the paper (encouraged)",
               "required": "the prompts in the paper (required)"}
PROMPT_WORDS = {"no": "not asked for", "on_request": "given on request", "encouraged": "encouraged in the paper",
                "required": "required in the paper"}
TRACKING_ASKS = {"recommended": "records of AI use kept in case the journal asks for them",
                 "required": "records of AI use beyond one acknowledgement, such as deposited outputs or kept versions"}
SCREENING_WORDS = {"plagiarism": "plagiarism checks only",
                   "integrity_signals": "plagiarism and paper-mill checks, with no AI-text detector named",
                   "may_detect_ai": "says it may use AI-text detection",
                   "ai_detector_deployed": "runs an AI-text detector on submissions"}
ACCESS_WORDS = {"full": "full open access", "hybrid": "hybrid (subscription, with an open-access option)",
                "subscription": "subscription only"}
STATUS_WORDS = {"VERIFIED": "checked against the journal's own pages",
                "PARTIAL": "partly checked; some fields were not researched",
                "SECONDARY": "taken from secondary reports, not from the journal's own pages",
                "NOT FOUND": "no AI policy could be found for this journal"}
REVIEWER_AI_WORDS = {"banned": "reviewers may not use AI tools",
                     "restricted": "reviewers may use only the publisher's approved AI tools",
                     "allowed": "reviewers may use AI tools"}
AI_USE_WORDS = {"polish": "AI corrected the spelling, grammar or clarity of text the authors wrote",
                "revision": "AI substantially reworded or restructured text the authors wrote",
                "drafting": "AI wrote new sentences or sections"}
VALIDATION_WORDS = {"none": "none of these", "independent-cohort": "an independent cohort",
                    "wet-lab": "wet-lab experiments", "multi-database": "results from more than one database",
                    "primary-analysis": "a primary analysis"}
DESIGN_WORDS = {"software": "software or resource", "public-data": "public-data reanalysis",
                "bioinformatics": "bioinformatics-finding", "mr": "Mendelian randomisation",
                "bibliometric": "bibliometric", "public-health-database": "public health-database", "other": "other"}
FIT_WORDS = {"go": "Fits", "conditional": "Depends", "unknown": "Not known", "no-go": "Does not fit"}
# When a quoted rule of the author guidelines applies (`submission_rules` in venues.yaml).
WHEN_WORDS = {"submission": "Rules of the author guidelines for the first submission:",
              "after_review": "Not needed until after the first review:"}
LIMIT_WORDS = {"abstract_words": "the abstract", "body_words": "the body", "over_limit_return": "overlength papers"}
ROUTE_WORDS = {"httpx": "a plain download", "chrome": "a headless browser", "browser": "a copy saved from a browser",
               "webfetch": "a web-fetch tool"}
LEGACY_ROUTE_PREFIX = re.compile(r"\b(httpx|chrome|wayback): ")
LEGACY_ROUTE_LABEL = {"httpx": "plain download: ", "chrome": "headless browser: ", "wayback": "Internet Archive: "}


# Abbreviations that reach the printed output through the catalogue's own text (publisher names, notes).
GLOSSARY = {"AAAS": "American Association for the Advancement of Science", "ACM": "Association for Computing Machinery",
            "APC": "article processing charge", "BMC": "BioMed Central",
            "CC-BY": "Creative Commons Attribution licence",
            "COPE": "Committee on Publication Ethics", "CSHL": "Cold Spring Harbor Laboratory",
            "DOI": "digital object identifier", "EMBO": "European Molecular Biology Organization",
            "ICMJE": "International Committee of Medical Journal Editors",
            "IEEE": "Institute of Electrical and Electronics Engineers", "IF": "impact factor",
            "ISCB": "International Society for Computational Biology", "JCR": "Journal Citation Reports",
            "JIF": "journal impact factor", "LLM": "large language model",
            "MDPI": "Multidisciplinary Digital Publishing Institute", "ML": "machine learning",
            "MR": "Mendelian randomisation", "OA": "open access", "OSI": "Open Source Initiative",
            "OUP": "Oxford University Press", "PLOS": "Public Library of Science", "RCT": "randomised controlled trial",
            "SN": "Springer Nature", "T&F": "Taylor & Francis", "URI": "uniform resource identifier"}


def abbreviations(text: str) -> str:
    """One closing line that spells out the abbreviations used in `text` (URLs ignored), or ''."""
    prose = re.sub(r"https?://\S+", " ", text)
    found = sorted(k for k in GLOSSARY if re.search(rf"(?<![\w&-]){re.escape(k)}s?(?![\w&])", prose))
    return "Abbreviations: " + "; ".join(f"{k}, {GLOSSARY[k]}" for k in found) + "." if found else ""


def _points(n: int) -> str:
    return f"{n} point" + ("" if n == 1 else "s")


def _sentence(text: str) -> str:
    text = str(text).strip()
    return text[:1].upper() + text[1:] + ("" if text.endswith((".", "!", "?")) else ".")


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _quoted(quote: Any) -> str:
    """The page's sentences, each in quotation marks: one string or a list of them."""
    return " ".join(f"“{q}”" for q in ([quote] if isinstance(quote, str) else quote or []))


def _or(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " or " + items[-1]


def route_words(route: Optional[str]) -> str:
    """How policy_watch.py read a page, in words: an archived copy is named with its capture date."""
    if not route:
        return "an unrecorded method"
    m = re.match(r"wayback:(\d{4})(\d{2})(\d{2})", route)
    if m:
        return f"the Internet Archive's copy of {m.group(1)}-{m.group(2)}-{m.group(3)}"
    return ROUTE_WORDS.get(route, route)


def plain_reason(reason: str) -> str:
    """A stored failure reason; older index entries name the fetch routes by their code names."""
    return LEGACY_ROUTE_PREFIX.sub(lambda m: LEGACY_ROUTE_LABEL[m.group(1)], reason)


class AiUse(str, Enum):
    polish = "polish"  # spelling, grammar, clarity edits of author-written text
    revision = "revision"  # substantive rewording and restructuring of author-written text
    drafting = "drafting"  # new sentences or sections written by the model


class StudyDesign(str, Enum):
    software = "software"  # the contribution is a tool, method or resource, not a biological finding
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


class Priority(str, Enum):
    """What the authors want most from a venue, in their order; `ladder` sorts by them after feasibility."""
    speed = "speed"  # days to a first decision, as the venue publishes it
    reach = "reach"  # journal impact factor
    ai = "ai"  # AI-policy work, in the points `rank` explains
    cost = "cost"  # what the authors would pay, in euros
    transfer = "transfer"  # preprint servers: how high on the journal ladder the first direct-transfer journal is


PRIORITY_WORDS = {"speed": "speed to a first decision", "reach": "reach (journal impact factor)",
                  "ai": "a light AI-policy burden", "cost": "a low cost to the authors",
                  "transfer": "a direct transfer to a journal high on the journal ladder"}
FIT_ORDER = {"go": 0, "conditional": 1, "unknown": 2, "no-go": 3}


class OutputFormat(str, Enum):
    md = "md"  # a table for the authors
    csv = "csv"  # one row per rung, in LADDER_COLUMNS; an empty cell means not known, never zero


# The ladder's CSV columns, in order. Units are in the names; numbers only in the numeric columns.
LADDER_COLUMNS = [
    "ladder", "rung", "chosen_rung", "key", "name", "fits", "fits_reason",
    "first_decision_days", "speed_measure", "speed_source", "speed_checked",
    "jif", "jif_year", "ai_points", "ai_tier", "ai_for_this_use",
    "fee_amount", "fee_currency", "fee_year", "author_cost_eur", "fee_route", "fee_source", "fee_checked",
    "preprint_rule", "transfers", "guidelines_url", "facts_from_record", "priorities",
]
FIRST_DECISION = re.compile(r"first[- ]decision", re.I)


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
    # Timelines, fees, editorial assessments, direct-transfer lists and the quoted rules of one journal's page
    # describe that journal (or server), not its parent or sibling.
    for journal_specific in ("review_speed", "publication_costs", "editorial_profile", "submission_rules",
                             "limit_quotes", "quoted_from", "transfers", "transfers_checked"):
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
    """When this venue's AI policy was last read: the later of the research date (the venue's own `checked`, else
    the file's) and the oldest watcher read among its policy pages. An archived copy counts at its capture date."""
    researched = v.get("checked") or checked
    dates = [date.fromisoformat(str(index[u]["read"])) for u in policy_urls(v) if index.get(u, {}).get("read")]
    return max(researched, min(dates)) if dates else researched


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
    """Points, and the reasons behind them. None when the policy was not researched.

    Writing rule (0 free to 5 drafting ban) + record keeping (the highest of prompts and tracking, 0 to 3) +
    AI-text screening (0 to 2) + listed extra burdens (at most 2) + 1 if the policy says disclosed use may count
    against the paper, - 1 if it says it will not. Disclosure places are a filter (`--refuse multi-place`),
    not points: repeating one statement costs little."""
    if v.get("writing_help") is None:
        return None, ["The AI policy has not been researched, so read the live page."]
    rule = v["writing_help"]
    score = WRITING_COST[rule]
    reasons: list[str] = [_sentence(f"{WRITING_WORDS[rule]} ({_points(score)})")]
    prompts, tracking = v.get("prompts") or "no", v.get("tracking") or "no"
    records = max(RECORDS_COST.get(prompts, 0), RECORDS_COST.get(tracking, 0))
    if records:
        score += records
        asks = [x for x in (PROMPT_ASKS.get(prompts), TRACKING_ASKS.get(tracking)) if x]
        reasons.append(f"It asks for {_and(asks)} ({_points(records)}).")
    s = SCREENING_COST.get(v.get("screening") or "plagiarism", 0)
    if s:
        score += s
        reasons.append(f"It {SCREENING_WORDS[v['screening']]} ({_points(s)}).")
    burden = v.get("extra_burden") or []
    counted = min(len(burden), MAX_BURDEN_POINTS)
    score += counted
    if burden:
        listed = _and([f'"{b}"' for b in burden])
        cap = f", at most {MAX_BURDEN_POINTS} counted" if len(burden) > MAX_BURDEN_POINTS else ""
        reasons.append(f"It also lists extra work ({_points(counted)}{cap}): {listed}.")
    if v.get("disclosure_neutral") is False:
        score += 1
        reasons.append("It says declared AI use may count against the paper (1 point).")
    elif v.get("disclosure_neutral") is True:
        score = max(0, score - 1)
        reasons.append("It says declared AI use does not count against the paper (minus 1 point).")
    return score, reasons


def tier(score: Optional[int]) -> str:
    if score is None:
        return "?"
    return next((word for limit, word in TIERS if score <= limit), SEVERE)


def verdict(v: dict[str, Any], ai_use: AiUse) -> str:
    """What the venue's writing rule means for this kind of AI use."""
    rule = v.get("writing_help")
    if rule is None:
        return "Not known, because the AI policy has not been researched; read the live page."
    if rule == "banned_drafting":
        return {AiUse.polish: "Language correction is allowed under the recorded policy; check whether it must be "
                              "declared.",
                AiUse.revision: "Possibly a conflict for you to weigh: the journal bans AI drafting and does not "
                                "say whether substantial rewording counts as drafting.",
                AiUse.drafting: "A conflict for you to weigh: the journal asks authors not to have AI draft text, "
                                "and the AI-use statement has to say that it did."}[ai_use]
    if rule == "red_line":
        return {AiUse.polish: "Allowed; declare it.",
                AiUse.revision: "Allowed; declare it.",
                AiUse.drafting: "A conflict for you to weigh if AI drafted the results or discussion, which "
                                "the journal reserves for the authors; other AI-drafted text is allowed if "
                                "declared."}[ai_use]
    if rule == "disclose_all":
        return "Allowed, but every use must be declared" + (", with the full prompts."
                                                             if v.get("prompts") == "required" else ".")
    if rule == "disclose":
        if ai_use == AiUse.polish and v.get('exempt'):
            return "Allowed; the recorded disclosure exemptions are: " + _and(v['exempt']) + ". Apply only an exemption that covers this use."
        return "Allowed; declare it. No applicable language-polish exemption has been recorded." if ai_use == AiUse.polish else "Allowed; declare it."
    return "Allowed; no declaration needed."


def _has_type(v: dict[str, Any], wanted: list[str]) -> bool:
    types = set(v.get("article_types") or [])
    if v.get("software_article"):
        types.add("software")
    return bool(types & set(wanted))


def validation_fit(v: dict[str, Any], study: Optional[str] = None,
                   available: Optional[set[str]] = None) -> tuple[str, str]:
    """Resource fit under recorded rules only; unknown is not permission or an author veto.

    Returns a status code (go, conditional, unknown, no-go) and the reason in sentences for the authors."""
    if study and study in (v.get("excluded_study_designs") or []):
        return "no-go", f"Its recorded scope excludes {DESIGN_WORDS.get(study, study)} studies."
    rules = v.get("validation_requirements")
    if rules is None:
        return "unknown", "Its validation requirements have not been researched."
    applicable = [r for r in rules if study is None or study in r.get("applies_to", [])]
    if not applicable:
        return "unknown", "No validation rule is recorded for this study design."
    outcomes: list[tuple[str, str]] = []
    for rule in applicable:
        options = set(rule.get("accepted_any") or [])
        description = _sentence(rule.get("description") or "check the recorded validation requirement")
        if study is None or available is None or rule.get("strength") != "required" or not options:
            outcomes.append(("conditional", description))
        elif options & available:
            have = _and([VALIDATION_WORDS.get(o, o) for o in sorted(options & available)])
            outcomes.append(("go", f"It accepts {have}, which you have."))
        else:
            needs = _or([VALIDATION_WORDS.get(o, o) for o in sorted(options)])
            outcomes.append(("no-go", f"It requires {needs}, and you have none of these."))
    severity = {"go": 0, "conditional": 1, "unknown": 2, "no-go": 3}
    worst = max(outcomes, key=lambda item: severity[item[0]])[0]
    return worst, " ".join(dict.fromkeys(reason for _, reason in outcomes))


def fit_text(status: str, reason: str) -> str:
    """A validation-fit cell: the status in a word, then why."""
    return f"{FIT_WORDS[status]}. {reason}"


def policy_page(v: dict[str, Any]) -> Optional[str]:
    """The page that states this venue's AI policy: its own, else its publisher's, else its guidelines."""
    return v.get("ai_policy_url") or v.get("publisher_policy_url") or v.get("url")


def _access(v: dict[str, Any]) -> str:
    return ACCESS_WORDS.get(v.get("oa") or "", "not recorded")


def _jif(v: dict[str, Any]) -> str:
    if v.get("jif") is None:
        return "not recorded"
    return f"{v['jif']}" + (f" ({v['jif_year']})" if v.get("jif_year") else "")


def _name(v: dict[str, Any]) -> str:
    return v.get("name") or v["key"]


def _selected(venues: dict[str, dict[str, Any]], *, preprints: bool, only: Optional[list[str]],
              field: Optional[list[str]], article_type: Optional[list[str]], software: bool,
              oa: Optional[list[str]], min_jif: Optional[float], refused: set[Burden],
              include_tracking: bool) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """The venues the filters keep, and the ones left out only because they require AI records beyond one
    acknowledgement (named, so the authors can ask for them)."""
    kept: dict[str, dict[str, Any]] = {}
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
        if burdens(v) & refused:
            continue
        if v.get("tracking") == "required" and not include_tracking and Burden.tracking not in refused:
            left_out.append(f"{_name(v)} ({'; '.join(v.get('extra_burden') or [])})")
            continue
        kept[key] = v
    return kept, left_out


# ------------------------------------------------------------------------------------------------ task facts

def load_record(path: Optional[Path], preprints: bool = False) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """The authors' priorities for one ladder and the venue facts researched for one manuscript.

    Reads the shared manuscript record (`priorities: {journals: [speed, reach], preprints: [transfer, ai]}`, or one
    list for both ladders; `venue_facts: {key: {...}}`) or a plain facts file with a `venues` mapping. These facts
    were read from the venues' own pages for this task; the catalogue is not changed by an author's task."""
    if path is None:
        return [], {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    priorities = raw.get("priorities") or []
    if isinstance(priorities, dict):
        priorities = priorities.get("preprints" if preprints else "journals") or []
    facts = raw.get("venue_facts") or raw.get("venues") or {}
    return [str(p) for p in priorities], facts


def recorded_ladder(path: Optional[Path], preprints: bool) -> list[str]:
    """The order the authors chose for one ladder (`ladders: {journals: [...], preprints: [...]}` in the record),
    which may move a rung away from the sorted order for a reason the report states; [] when none is recorded."""
    if path is None:
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [str(k) for k in (raw.get("ladders") or {}).get("preprints" if preprints else "journals") or []]


def with_facts(venues: dict[str, dict[str, Any]], facts: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The catalogue with the task's facts laid over it, field by field. A venue the catalogue lacks can be added
    by the facts when they give it a name; `from_facts` lists the fields that came from the task."""
    out = dict(venues)
    for key, given in facts.items():
        if key not in venues and not given.get("name"):
            raise typer.BadParameter(f"the facts describe {key!r}, which the catalogue does not know; give it a "
                                     "name to add it for this task")
        out[key] = {**venues.get(key, {}), **given, "key": key, "from_facts": sorted(given)}
    return out


def _first_decision(v: dict[str, Any]) -> Optional[dict[str, Any]]:
    return next((m for m in v.get("review_speed") or [] if m.get("days") is not None
                 and FIRST_DECISION.search(str(m.get("metric") or ""))), None)


def speed_days(v: dict[str, Any]) -> tuple[Optional[float], str]:
    """Days to a first decision, the one speed measure `ladder` compares, and the venue's figures in words.

    Only first-decision figures are compared: a time to acceptance or to publication measures something else,
    and is shown but never ranked against a first decision."""
    figures = [m for m in v.get("review_speed") or [] if m.get("days") is not None]
    for m in figures:
        if FIRST_DECISION.search(str(m.get("metric") or "")):
            detail = ", ".join(str(m[k]) for k in ("statistic", "population", "period") if m.get(k))
            return float(m["days"]), f"{m['days']} days to first decision" + (f" ({detail})" if detail else "")
    if figures:
        return None, "; ".join(f"{m['days']} days, {m.get('metric') or 'measure not named'}" for m in figures) + \
            " (no first-decision figure, so not compared)"
    return None, "not known"


def fee_eur(v: dict[str, Any]) -> tuple[Optional[float], str]:
    """What the authors would pay in euros, and the fee in words. `author_cost_eur` is the amount left to the
    authors after an agreement, discount, fund or waiver they can use; without it a fee in euros is compared as
    listed, and a fee in another currency is shown but not compared."""
    costs = v.get("publication_costs") or []
    if not costs:
        return None, "not known"
    c = costs[0]
    amount, currency = c.get("amount"), str(c.get("currency") or "")
    shown = (f"{amount} {currency}".strip() + (f" ({c['fee_year']})" if c.get("fee_year") else "")
             if amount is not None else "fee not recorded")
    if c.get("route"):
        shown += f"; {c['route']}"
    if c.get("author_cost_eur") is not None:
        return float(c["author_cost_eur"]), f"{shown}; the authors would pay about {c['author_cost_eur']} EUR"
    if amount is not None and currency.upper() == "EUR":
        return float(amount), shown
    return None, f"{shown} (no euro figure, so not compared)"


def priority_value(v: dict[str, Any], priority: Priority,
                   journals_on_ladder: Optional[list[str]] = None) -> Optional[float]:
    """The venue's value on one priority, lower is better; None when not known. For `transfer`, the rung (counted
    from 0, in the order the journals are given) of the first journal the server transfers to directly; a server
    whose checked list reaches none of them comes after every one that reaches some."""
    if priority == Priority.transfer:
        transfers = v.get("transfers")
        if transfers is None or not journals_on_ladder:
            return None
        rungs = [n for n, k in enumerate(journals_on_ladder) if k in transfers]
        return float(rungs[0]) if rungs else float(len(journals_on_ladder))
    if priority == Priority.speed:
        return speed_days(v)[0]
    if priority == Priority.reach:
        return -float(v["jif"]) if v.get("jif") is not None else None
    if priority == Priority.ai:
        return friction(v)[0]
    return fee_eur(v)[0]


def ladder_order(v: dict[str, Any], priorities: list[Priority], study: Optional[str],
                 available: Optional[set[str]], journals_on_ladder: Optional[list[str]] = None) -> tuple[Any, ...]:
    """Feasibility first, then each priority in the authors' order. An unknown value sorts below every known one
    at its step, and a tie passes to the next priority; the name breaks the last tie."""
    key: list[Any] = [FIT_ORDER[validation_fit(v, study, available)[0]]]
    for p in priorities:
        value = priority_value(v, p, journals_on_ladder)
        key.append((1, 0.0) if value is None else (0, value))
    key.append(_name(v).lower())
    return tuple(key)


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().rstrip(".").lower()


def _who(names: list[str], total: int) -> str:
    return "every venue" if len(names) == total and total > 1 else _and(names)


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
        help="What the paper contributes, for the validation rules: software (a tool, method or resource paper, "
             "even one with benchmarks on human data), public-data (reanalysis of public data for a finding), "
             "bioinformatics (a biological finding from computation), mr (Mendelian randomisation), bibliometric, "
             "public-health-database, other")] = None,
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
    kept, left_out = _selected(venues, preprints=preprints, only=only, field=field, article_type=article_type,
                               software=software, oa=oa, min_jif=min_jif, refused=refused,
                               include_tracking=include_tracking)
    for key, v in kept.items():
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
    kind = "preprint servers" if preprints else "journals"
    typer.echo(f"These {len(rows)} {kind} are ranked by how much work their AI policy asks of the authors, least "
               f"first, for a manuscript where {AI_USE_WORDS[ai_use.value]} (AI use \"{ai_use.value}\"). Policies "
               "change, so read the live policy page (last column) of any you shortlist before submitting.\n")
    typer.echo("How to read the table:")
    typer.echo("- AI-policy work counts the paperwork the policy asks for, in points: 0 to 1 is light, 2 to 3 "
               "moderate, 4 to 5 heavy and 6 or more severe. It is not the chance of rejection, and a high count "
               "does not stop you submitting.")
    typer.echo("- The validation column compares the validation rules recorded for the journal with the resources "
               "you stated. \"Not known\" means the rules have not been researched, which is not the same as "
               "having none.")
    typer.echo("- Impact factor is the journal impact factor from Clarivate's Journal Citation Reports, with its "
               "year where the journal states one.")
    typer.echo("- Access is full open access (free to read, usually paid for by an article processing charge), "
               "hybrid (a subscription journal with an optional open-access fee) or subscription only.")
    typer.echo("- The short name in backticks after each title is its key: `venues.py show KEY` prints that "
               "journal's checklist.\n")
    typer.echo("| AI-policy work | Journal | Validation rules and your resources | Impact factor | Access "
               "| Screening for AI text | What this means for your AI use | Why it scores this "
               "| AI policy page (date read) |")
    typer.echo("|---|---|---|---:|---|---|---|---|---|")
    stale = 0
    printed: list[str] = []
    for score, key, v, reasons in rows:
        read = policy_read(v, checked, index)
        stale += (date.today() - read).days > STALE_AFTER_DAYS
        fit, fit_reason = validation_fit(v, study_design.value if study_design else None, available)
        screening = SCREENING_WORDS.get(v.get("screening") or "", "not recorded")
        page = policy_page(v)
        printed.append(f"| {'not known' if score is None else _points(score)} ({tier(score)}) "
                       f"| {v.get('name', key)} (`{key}`) | {fit_text(fit, fit_reason)} | {_jif(v)} | {_access(v)} "
                       f"| {_sentence(screening)} | {verdict(v, ai_use)} | {' '.join(reasons)} "
                       f"| {page + f' (read {read})' if page else f'No page recorded (read {read}).'} |")
        typer.echo(printed[-1])
    typer.echo("\nThe validation column covers only the rules recorded in the catalogue. Open science, how "
               "receptive the editors are, costs and comparable review times need the full comparison.")
    if left_out:
        typer.echo("\nThese were left out because they require records of AI use beyond one acknowledgement "
                   "(add --include-tracking to list them): " + "; ".join(left_out) + ".")
    glossary = abbreviations("\n".join(printed + left_out))
    if glossary:
        typer.echo("\n" + glossary)
    if stale:
        typer.echo(f"\nWARNING: {stale} of these policies were read more than {STALE_AFTER_DAYS} days ago; run "
                   "policy_watch.py check --stale-days 60 --update and review what moved.", err=True)


PROFILE_LABELS = {"validation_requirements": "Validation requirements",
                  "excluded_study_designs": "Study designs it excludes",
                  "open_science": "Open science and open source", "editorial_profile": "Editorial profile",
                  "review_speed": "Review times", "publication_costs": "Publication costs"}
PROFILE_ITEM = {"validation_requirements": "Rule", "review_speed": "Measure", "publication_costs": "Fee"}
KEY_WORDS = {"applies_to": "applies to", "accepted_any": "accepted alternatives (any one is enough)",
             "description": "condition", "checked": "read on", "evidence_kind": "kind of evidence",
             "fee_year": "fee year", "source_code": "source code", "software_licence": "software licence",
             "data_and_artifacts": "data and artifacts", "open_peer_review": "open peer review"}


def _token(value: Any, key: str) -> str:
    text = str(value)
    if key in ("applies_to", "excluded_study_designs"):
        return DESIGN_WORDS.get(text, text)
    if key == "accepted_any":
        return VALIDATION_WORDS.get(text, text)
    return text


def _flat(value: Any) -> bool:
    return isinstance(value, list) and all(not isinstance(x, (dict, list)) for x in value)


def _scalar(value: Any, key: str) -> str:
    if value is None:
        return "not researched"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(_token(x, key) for x in value) or "none"
    return _token(value, key)


def _profile_lines(value: Any, key: str, depth: int) -> list[str]:
    """A selection-profile value as nested bullets with the catalogue's field names in words."""
    pad = "  " * depth
    if isinstance(value, dict):
        lines: list[str] = []
        for k, sub in value.items():
            label = KEY_WORDS.get(k, k.replace("_", " "))
            if isinstance(sub, dict) or (isinstance(sub, list) and not _flat(sub)):
                lines += [f"{pad}- {label}:", *_profile_lines(sub, k, depth + 1)]
            else:
                lines.append(f"{pad}- {label}: {_scalar(sub, k)}")
        return lines
    if isinstance(value, list) and not _flat(value):
        lines = []
        for n, item in enumerate(value, 1):
            lines += [f"{pad}- {PROFILE_ITEM.get(key, 'Entry')} {n}:", *_profile_lines(item, key, depth + 1)]
        return lines
    return [f"{pad}- {_scalar(value, key)}"]


@app.command()
def show(
    venue: Annotated[str, typer.Argument(help="Venue key, as listed by `rank`")],
    ai_use: Annotated[Optional[AiUse], typer.Option(
        help="What AI did to the text; without it, the checklist covers each kind of use")] = None,
) -> None:
    """One venue's requirements as a checklist for adapting a manuscript, ordered by when each item can be done."""
    checked, venues = load_venues()
    if venue not in venues:
        raise typer.BadParameter(f"unknown venue {venue!r}; known: {', '.join(sorted(venues))}")
    v = venues[venue]
    index = load_snapshot_index()
    score, reasons = friction(v)
    read = policy_read(v, checked, index)

    def items(field: str) -> list[str]:
        values = v.get(field)
        if values is None:
            return ["  - Not researched; read the live page."]
        if not values:
            return ["  - None listed."]
        return [f"  - [ ] {x}" for x in values]

    def listed(field: str) -> str:
        return ", ".join(v.get(field) or []) or "not recorded"

    limits = v.get("limits") or {}
    recommended = " (recommended, not required)" if limits.get("abstract_words_kind") == "recommended" else ""
    parts = [f"the abstract at most {limits['abstract_words']} words{recommended}" if limits.get("abstract_words")
             else None,
             f"the body about {limits['body_words']} words" if limits.get("body_words") else None,
             f"papers more than {round(100 * (limits['over_limit_return'] - 1))}% over the limit are returned "
             "without review" if limits.get("over_limit_return") else None]
    parts = [x for x in parts if x]
    limit_text = f"{_and(parts)}." if parts else "not researched; read the live page."
    limit_quotes = [f"  - On {LIMIT_WORDS.get(k, k.replace('_', ' '))}, the page says: {_quoted(q)}"
                    for k, q in (v.get("limit_quotes") or {}).items() if q]
    origin = v.get("quoted_from")
    origin_line = ([f"The page's words above are quoted from the Internet Archive's copy of {origin['copy_date']}, "
                    f"{origin['source']}, read on {origin['checked']}"
                    + (f": {origin['note']}." if origin.get("note") else ".")]
                   if origin else [])

    def rules(when: str) -> list[str]:
        found = [r for r in v.get("submission_rules") or [] if r.get("when") == when]
        box = "[ ] " if when == "submission" else ""
        return [f"  - {box}{_sentence(r['rule'])} The page: {_quoted(r['quote'])}" for r in found]

    first_submission = rules("submission")
    after_review = rules("after_review")
    rule_lines = ([f"- {WHEN_WORDS['submission']}", *first_submission] if first_submission else
                  [f"- {WHEN_WORDS['submission'][:-1]}: not researched; read the live page."]
                  if v.get("submission_rules") is None else [])
    if after_review:
        rule_lines += [f"- {WHEN_WORDS['after_review']}", *after_review]
    exemptions = ("not researched, so read the live page" if v.get("exempt") is None
                  else ", ".join(v["exempt"]) or "none listed in the recorded policy")
    neutral = v.get("disclosure_neutral")
    counts = ("the page does not say" if neutral is None
              else "the page says it does not" if neutral else "the page says it may")
    screening = SCREENING_WORDS.get(v.get("screening") or "", "not recorded")
    if v.get("screening_note"):
        screening += f" ({v['screening_note']})"
    if score is None:
        work = f"**AI-policy work:** not known. {reasons[0]}"
    else:
        work = f"**AI-policy work:** {_points(score)} ({tier(score)}). " + " ".join(reasons)
    uses = [ai_use] if ai_use else list(AiUse)
    sources = []
    for u in policy_urls(v):
        e = index.get(u, {})
        att = e.get("last_attempt")
        line = (f"- {u} was read on {e['read']} with {route_words(e.get('route'))}; "
                f"{e.get('passages', 0)} of its passages mention AI." if e.get("read")
                else f"- {u} has not yet been read by the policy watcher.")
        if att:
            line += f" The last attempt, on {att['date']}, could not read it: {plain_reason(att['reason'])}."
        sources.append(line)
    out = [
        f"# {v.get('name', venue)}: checklist for adapting a manuscript",
        "",
        f"- **Publisher:** {v.get('publisher') or 'not recorded'}",
        f"- **Journal impact factor:** {_jif(v)}",
        f"- **Access:** {_access(v)}",
        f"- **Fields:** {listed('fields')}",
        f"- **Article types:** {listed('article_types')}",
        f"- **How this entry was checked:** {STATUS_WORDS.get(v.get('status') or '', 'not recorded')}. "
        f"The AI policy was last read on {read}.",
        f"- **Author guidelines:** {v.get('url') or 'not recorded'}",
        f"- **AI policy page:** {policy_page(v) or 'not recorded'}",
        "",
        "## AI policy",
        "",
        work,
        "",
        *[f"- **If {AI_USE_WORDS[u.value]}** (AI use \"{u.value}\"): {verdict(v, u)}" for u in uses],
        "- **What AI may do in the writing:** " + (_sentence(WRITING_WORDS[v["writing_help"]]) if v.get("writing_help")
                                                    else "Not researched; read the live page."),
        f"- **Uses that need no declaration:** {exemptions}.",
        f"- **Prompts:** {PROMPT_WORDS.get(v.get('prompts') or '', 'not recorded')}.",
        f"- **Screening for AI text:** {screening}.",
        f"- **Whether declared AI use counts against the paper:** {counts}.",
        f"- **Reviewers and AI tools:** {REVIEWER_AI_WORDS.get(v.get('reviewer_ai') or '', 'not researched')}.",
        "- **AI in images and figures** (not counted in the points):",
        *items("image_rules"),
        "",
        "## Now that the journal is chosen",
        "",
        "These can be done on the current draft.",
        "",
        f"- [ ] Length: {limit_text}",
        *limit_quotes,
        "- Abstract headings:",
        *items("abstract_headings"),
        "- Required sections (add the headings now; their final contents may wait for the last stage):",
        *items("required_sections"),
        "- Other rules the editors check on arrival:",
        *items("other_desk_rules"),
        *rule_lines,
        *([""] + origin_line if origin_line else []),
        "",
        "## At the end, once the code, data and results are final",
        "",
        "These wait until the software version, data and results will not change again; done earlier, they "
        "have to be done twice.",
        "",
        "- Software and availability (archived release, its DOI and the versions quoted in the paper):",
        *items("software"),
        "- The AI-use statement goes in:",
        *items("disclosure_places"),
        "- and states:",
        *items("disclosure_fields"),
        "- Extra work this journal asks for about AI:",
        *items("extra_burden"),
        "- Penalties the journal states: " + (", ".join(v.get("penalties") or []) or "none found") + ".",
        "",
        "## What can and cannot be verified",
        "",
        "Apply the current rules for the article type, including its exemptions.",
        "",
        "- Visible in the files you supply: counts, headings, the required statements and where they sit, links.",
        "- Testable with the materials: whether references support the claims, and whether deposited code and "
        "data exist and run.",
        "- Known only to the authors: which tools were actually used, the drafting history, complete logs and "
        "human oversight.",
        "- Up to the editors: how the policy is interpreted, whether text is attributed to AI, and what "
        "screening finds.",
        "",
        "A conflict with the policy is the authors' decision; these checks are advice.",
        "",
        f"## Policy pages (to re-read them: `policy_watch.py check --venue {venue}`)",
        "",
        *sources,
    ]
    if v.get("fit_note") or v.get("permitted_uses"):
        out += ["", "## Notes from the catalogue", ""]
        if v.get("fit_note"):
            out.append(_sentence(v["fit_note"]))
        if v.get("permitted_uses"):
            out.append("Uses the policy permits (permitted is not the same as exempt from declaration): "
                       + "; ".join(v["permitted_uses"]) + ".")
    out += ["", "## Selection profile", "",
            "A missing field has not been researched; it does not mean the journal has no rule.", ""]
    for field, label in PROFILE_LABELS.items():
        value = v.get(field)
        if value is None or _flat(value):
            out.append(f"- **{label}:** {_scalar(value, field)}.")
        else:
            out += [f"- **{label}:**", *_profile_lines(value, field, 1)]
    glossary = abbreviations("\n".join(out))
    typer.echo("\n".join(out + (["", glossary] if glossary else [])))


def _preprint_cell(v: dict[str, Any], venues: dict[str, dict[str, Any]], journals_on_ladder: Optional[list[str]],
                   preprints: bool) -> str:
    """For a journal, its rule on manuscripts already posted as preprints; for a preprint server, the journals it
    transfers manuscripts to directly, narrowed to the journal ladder when one is given. A journal missing from a
    server's list counts as "not to" only when the list was checked for it (`transfers_checked`)."""
    if not preprints:
        rule = (v.get("open_science") or {}).get("preprints")
        return _sentence(rule) if rule else "Not known."
    transfers = v.get("transfers")
    if transfers is None:
        return "Not recorded."

    def named(keys: list[str], join: Any = _and) -> str:
        return join([_name(venues[k]) if k in venues else k for k in keys])

    if not journals_on_ladder:
        return f"Transfers directly to {named(transfers)}." if transfers else "No direct transfers recorded."
    checked = set(v.get("transfers_checked") or transfers)
    yes = [k for k in journals_on_ladder if k in transfers]
    no = [k for k in journals_on_ladder if k not in transfers and k in checked]
    unchecked = [k for k in journals_on_ladder if k not in checked]
    parts = ([f"transfers directly to {named(yes)}"] if yes else []) \
        + ([f"not to {named(no, _or)}"] if no else []) + ([f"not checked for {named(unchecked, _or)}"] if unchecked else [])
    return _sentence("; ".join(parts))


@app.command()
def ladder(
    priority: Annotated[Optional[list[Priority]], typer.Option(
        help="What the authors want most, first; repeatable: speed, reach, ai, cost, and for preprint servers "
             "transfer. Without it the record's `priorities` are used")] = None,
    record: Annotated[Optional[Path], typer.Option(
        help="The manuscript record (or a facts file): its `priorities` and the `venue_facts` researched for "
             "this manuscript, laid over the catalogue")] = None,
    only: Annotated[Optional[list[str]], typer.Option(help="Only these venue keys (the shortlist)")] = None,
    field: Annotated[Optional[list[str]], typer.Option(help="Keep venues tagged with any of these fields")] = None,
    article_type: Annotated[Optional[list[str]], typer.Option("--type", help="Keep venues taking this type")] = None,
    software: Annotated[bool, typer.Option(help="Only venues with a software article type")] = False,
    oa: Annotated[Optional[list[str]], typer.Option(help="Keep these access models: full, hybrid, subscription")] = None,
    min_jif: Annotated[Optional[float], typer.Option(help="Drop venues below this JIF (and those without one)")] = None,
    refuse: Annotated[Optional[list[Burden]], typer.Option(help="Drop venues that impose this; repeatable")] = None,
    include_tracking: Annotated[bool, typer.Option(
        help="Also list venues that require recording AI use beyond one acknowledgement")] = False,
    preprints: Annotated[bool, typer.Option(help="Order preprint servers instead of journals")] = False,
    journal: Annotated[Optional[list[str]], typer.Option(
        help="With --preprints: the journals on the journal ladder, to show which ones each server transfers "
             "to directly; repeatable")] = None,
    ai_use: Annotated[AiUse, typer.Option(help="What AI did to the text")] = AiUse.revision,
    study_design: Annotated[Optional[StudyDesign], typer.Option(
        help="What the paper contributes, for the validation rules (see `rank --help`)")] = None,
    validation_available: Annotated[Optional[list[Validation]], typer.Option(
        help="Validation already available or affordable; repeatable; 'none' when unavailable")] = None,
    output: Annotated[OutputFormat, typer.Option(
        "--format", help="md: a table for the authors; csv: one row per rung in fixed columns (an empty cell "
                         "means not known)")] = OutputFormat.md,
) -> None:
    """A shortlist ordered into a ladder: feasibility first, then each of the authors' priorities in turn."""
    _, venues = load_venues()
    recorded, facts = load_record(record, preprints)
    venues = with_facts(venues, facts)
    try:
        priorities = list(priority or []) or [Priority(p) for p in recorded]
    except ValueError as exc:
        raise typer.BadParameter("the record's priorities must be among " +
                                 ", ".join(p.value for p in Priority)) from exc
    if not priorities:
        raise typer.BadParameter("give the authors' priorities with --priority (speed, reach, ai, cost; transfer "
                                 "for preprint servers), most important first, or record them as `priorities` in "
                                 "the manuscript record")
    if len(set(priorities)) != len(priorities):
        raise typer.BadParameter("name each priority once")
    if Priority.transfer in priorities and not (preprints and journal):
        raise typer.BadParameter("the transfer priority orders preprint servers (--preprints) by the journal ladder "
                                 "given with --journal, first rung first")
    unknown = sorted(set(journal or []) - set(venues))
    if unknown:
        raise typer.BadParameter(f"unknown journal keys: {', '.join(unknown)}")
    available = {value.value for value in validation_available} if validation_available is not None else None
    if available and "none" in available and len(available) > 1:
        raise typer.BadParameter("'none' cannot be combined with an available validation route")
    study = study_design.value if study_design else None
    kept, left_out = _selected(venues, preprints=preprints, only=only, field=field, article_type=article_type,
                               software=software, oa=oa, min_jif=min_jif, refused=set(refuse or []),
                               include_tracking=include_tracking)
    rows = sorted(kept.values(), key=lambda v: ladder_order(v, priorities, study, available, journal))
    if output == OutputFormat.csv:
        _ladder_csv(rows, venues, priorities, study, available, journal, preprints, ai_use,
                    recorded_ladder(record, preprints))
        return
    kind = "Preprint" if preprints else "Journal"
    typer.echo(f"# {kind} ladder\n")
    typer.echo("Ordered by whether the paper fits each venue's recorded rules, then by "
               + ", then by ".join(PRIORITY_WORDS[p.value] for p in priorities)
               + ". A value that is not known sorts below every known value at its step, and a tie passes to the "
                 "next step. A rung is an order of preference under these priorities, not a chance of acceptance; "
                 "the speed compared is days to a first decision, which for most journals includes desk "
                 "rejections.\n")
    last = "Direct transfer" if preprints else "Manuscripts already posted as preprints"
    typer.echo(f"| Rung | {'Server' if preprints else 'Journal'} | Fits its recorded rules | Speed | Reach "
               f"| AI-policy work | What this means for your AI use | Cost | {last} |")
    typer.echo("|---:|---|---|---|---|---|---|---|---|")
    printed: list[str] = []
    for n, v in enumerate(rows, 1):
        fit, reason = validation_fit(v, study, available)
        score, _ = friction(v)
        work = "not known" if score is None else f"{_points(score)} ({tier(score)})"
        printed.append(f"| {n} | {_name(v)} (`{v['key']}`) | {fit_text(fit, reason)} | {_sentence(speed_days(v)[1])} "
                       f"| {_sentence(_jif(v))} | {_sentence(work)} | {verdict(v, ai_use)} "
                       f"| {_sentence(fee_eur(v)[1])} | {_preprint_cell(v, venues, journal, preprints)} |")
        typer.echo(printed[-1])
    for p in priorities:
        missing = [_name(v) for v in rows if priority_value(v, p, journal) is None]
        if missing:
            typer.echo(f"\nNot known, so placed below the known values at the step for {PRIORITY_WORDS[p.value]}: "
                       f"{_and(missing)}.")
    from_task = [f"{_name(v)} ({', '.join(f.replace('_', ' ') for f in v['from_facts'])})"
                 for v in rows if v.get("from_facts")]
    if from_task:
        typer.echo("\nFacts read for this manuscript and taken from its record: " + "; ".join(from_task) + ".")
    if left_out:
        typer.echo("\nThese were left out because they require records of AI use beyond one acknowledgement "
                   "(add --include-tracking to list them): " + "; ".join(left_out) + ".")
    glossary = abbreviations("\n".join(printed + left_out))
    if glossary:
        typer.echo("\n" + glossary)


def _ladder_csv(rows: list[dict[str, Any]], venues: dict[str, dict[str, Any]], priorities: list[Priority],
                study: Optional[str], available: Optional[set[str]], journals_on_ladder: Optional[list[str]],
                preprints: bool, ai_use: AiUse, chosen: list[str]) -> None:
    """The ladder as CSV on stdout, in LADDER_COLUMNS: `rung` is the sorted order under the priorities,
    `chosen_rung` the order recorded in the record (empty for a venue it does not list)."""
    def cell(value: Any) -> str:
        return "" if value is None else str(value)

    writer = csv.DictWriter(sys.stdout, fieldnames=LADDER_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for n, v in enumerate(rows, 1):
        fit, reason = validation_fit(v, study, available)
        score, _ = friction(v)
        speed = _first_decision(v) or {}
        fee = (v.get("publication_costs") or [{}])[0]
        rule = (v.get("open_science") or {}).get("preprints")
        transfers = v.get("transfers")
        writer.writerow({
            "ladder": "preprints" if preprints else "journals", "rung": n,
            "chosen_rung": chosen.index(v["key"]) + 1 if v["key"] in chosen else "", "key": v["key"], "name": _name(v),
            "fits": FIT_WORDS[fit], "fits_reason": reason,
            "first_decision_days": cell(speed.get("days")),
            "speed_measure": ", ".join(str(speed[k]) for k in ("metric", "statistic", "population", "period")
                                       if speed.get(k)) if speed else speed_days(v)[1],
            "speed_source": cell(speed.get("source")), "speed_checked": cell(speed.get("checked")),
            "jif": cell(v.get("jif")), "jif_year": cell(v.get("jif_year")),
            "ai_points": cell(score), "ai_tier": "" if score is None else tier(score),
            "ai_for_this_use": verdict(v, ai_use),
            "fee_amount": cell(fee.get("amount")), "fee_currency": cell(fee.get("currency")),
            "fee_year": cell(fee.get("fee_year")), "author_cost_eur": cell(fee.get("author_cost_eur")),
            "fee_route": cell(fee.get("route")), "fee_source": cell(fee.get("source")),
            "fee_checked": cell(fee.get("checked")),
            "preprint_rule": cell(rule),
            "transfers": "" if transfers is None else ";".join(
                k for k in transfers if not journals_on_ladder or k in journals_on_ladder),
            "guidelines_url": cell(v.get("url")),
            "facts_from_record": ";".join(v.get("from_facts") or []),
            "priorities": ";".join(p.value for p in priorities),
        })


@app.command()
def common(
    keys: Annotated[list[str], typer.Argument(
        help="The venues on the ladder (keys from `rank`), journals and preprint servers alike")],
    record: Annotated[Optional[Path], typer.Option(
        help="The manuscript record (or a facts file) whose `venue_facts` fill what the catalogue lacks")] = None,
) -> None:
    """What every venue on a ladder asks for: what one version of the manuscript can satisfy now, where the venues
    disagree, what waits for the final code and data, and what has not been researched."""
    _, venues = load_venues()
    _, facts = load_record(record)
    venues = with_facts(venues, facts)
    unknown = [k for k in keys if k not in venues]
    if unknown:
        raise typer.BadParameter(f"unknown venue keys: {', '.join(unknown)}")
    vs = [venues[k] for k in dict.fromkeys(keys)]
    if len(vs) < 2:
        raise typer.BadParameter("name at least two venues")
    total = len(vs)
    now: list[str] = []
    differ: list[str] = []
    end: list[str] = []
    gaps: dict[str, list[str]] = {}

    def gap(v: dict[str, Any], what: str) -> None:
        gaps.setdefault(_name(v), []).append(what)

    for key, label in (("body_words", "the body"), ("abstract_words", "the abstract")):
        have = [(v, (v.get("limits") or {}).get(key)) for v in vs]
        for v, n in have:
            if not n:
                gap(v, f"the length of {label}")
        known = [(v, n) for v, n in have if n]
        if not known:
            continue
        listing = "; ".join(f"{_name(v)}, {n}" for v, n in known)
        shortest = min(n for _, n in known)
        if len(known) == total and len({n for _, n in known}) == 1:
            now.append(f"- [ ] Length of {label}: at most {shortest} words, the limit of every venue that states one "
                       f"({listing}).")
        elif len(known) < total:
            differ.append(f"- Length of {label}: recorded limits are {listing} words; other venues' limits are unknown. "
                          "Keep this as a venue-specific choice until those rules are checked; no shared cap is established.")
        else:
            differ.append(f"- Length of {label}: the limits differ ({listing} words). Writing to the shortest, "
                          f"{shortest} words, fits all of them; whether that cut is worth making before the choice "
                          "is your decision.")

    headings = [(v, v.get("abstract_headings")) for v in vs]
    for v, h in headings:
        if h is None:
            gap(v, "the abstract headings")
    known_h = [(v, h) for v, h in headings if h is not None]
    if known_h:
        def form(h: list[str]) -> str:
            return ", ".join(h) if h else "no headings (unstructured)"
        if len({tuple(_norm(x) for x in h) for _, h in known_h}) == 1:
            now.append(f"- [ ] Abstract: {form(known_h[0][1])} ({_who([_name(v) for v, _ in known_h], total)}).")
        else:
            differ.append("- Abstract headings differ: " + "; ".join(f"{_name(v)}: {form(h)}" for v, h in known_h)
                          + ".")

    def union(field: str, label: str, target: list[str], what: str) -> None:
        items: dict[str, tuple[str, list[str]]] = {}
        for v in vs:
            values = v.get(field)
            if values is None:
                gap(v, what)
                continue
            for x in values:
                items.setdefault(_norm(x), (str(x), []))[1].append(_name(v))
        if items:
            target.append(f"- {label}:")
            target.extend(f"  - [ ] {_sentence(text)[:-1]} ({_who(names, total)})" for text, names in items.values())

    union("required_sections", "Sections to add (one a single venue requires costs the others little)", now,
          "the required sections")
    union("other_desk_rules", "Rules the editors check on arrival, to check against the draft", now,
          "the rules checked on arrival")

    shared: dict[tuple[str, str], tuple[str, list[str]]] = {}
    for v in vs:
        rules = v.get("submission_rules")
        if rules is None:
            gap(v, "the other rules of its author guidelines")
            continue
        for r in rules:
            shared.setdefault((str(r.get("when")), _norm(r["rule"])), (r["rule"], []))[1].append(_name(v))
    first = [(t, n) for (w, _), (t, n) in shared.items() if w == "submission"]
    after = [(t, n) for (w, _), (t, n) in shared.items() if w == "after_review"]
    same = [f"  - [ ] {_sentence(t)[:-1]} (every venue)" for t, n in first if len(n) == total]
    own = [f"  - {_sentence(t)[:-1]} ({_and(n)})" for t, n in first if len(n) < total]
    if same:
        now += ["- Rules of the author guidelines that every venue shares:", *same]
    if own:
        differ += ["- Rules that only some venues state. Those that cost the others nothing (alt text, dataset "
                   "citations) can be adopted now; a section order or a reference style waits for the choice:", *own]
    if after:
        differ += ["- Not needed until after the first review:",
                   *[f"  - {_sentence(t)[:-1]} ({_who(n, total)})" for t, n in after]]

    union("software", "Software and availability", end, "its software and availability rules")
    union("disclosure_places", "Where the AI-use statement goes (one statement, placed everywhere a venue asks)",
          end, "where the AI-use statement goes")
    union("disclosure_fields", "What the AI-use statement states", end, "what the AI-use statement states")
    union("extra_burden", "Extra work about AI", end, "its extra AI requirements")

    rules_known = [(v, v["writing_help"]) for v in vs if v.get("writing_help")]
    ai_lines = [f"- {_name(v)}: {WRITING_WORDS[r]}." for v, r in rules_known]
    if len({r for _, r in rules_known}) > 1:
        strict_v, strict_r = max(rules_known, key=lambda item: WRITING_COST[item[1]])
        ai_lines.append(f"\nThe strictest is {_name(strict_v)}'s: {WRITING_WORDS[strict_r]}. A manuscript written "
                        "and declared to that rule keeps every venue on the list open; whether to write to it is "
                        "your decision.")
    for v in vs:
        if not v.get("writing_help"):
            gap(v, "its AI policy")

    names = _and([_name(v) for v in vs])
    out = [f"# What the venues on this ladder ask for: {names}", "",
           "Each requirement is listed with the venues that ask for it; \"every venue\" means all of them. A venue "
           "missing from an item may simply not have been researched for it (see the last section), which is not "
           "the same as having no rule.", "",
           "## Adapt now: one version serves every venue", ""]
    out += now or ["Nothing is recorded that every venue shares; read the author guidelines in the last section."]
    out += ["", "## Choose per venue: the venues disagree", "",
            "These wait until the venue is chosen, or follow the first rung of the ladder.", ""]
    out += differ or ["Nothing recorded disagrees."]
    out += ["", "## At the end, once the code, data and results are final", "",
            "Done earlier, these have to be done twice.", ""]
    out += end or ["Nothing recorded."]
    out += ["", "## AI writing rules on the list", "", *(ai_lines or ["None recorded."])]
    if gaps:
        out += ["", "## Not researched yet", "",
                "Read these on the venue's own author guidelines, and add what you find to the manuscript "
                "record's `venue_facts` so the next run includes it:", ""]
        for v in vs:
            if _name(v) in gaps:
                out.append(f"- {_name(v)} ({v.get('url') or 'no guidelines page recorded'}): "
                           f"{_and(gaps[_name(v)])}.")
    glossary = abbreviations("\n".join(out))
    typer.echo("\n".join(out + (["", glossary] if glossary else [])))


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


def _same_name(found: str, wanted: str) -> bool:
    """The same name in any word order, also when one side adds middle initials: OpenAlex lists "Anton Y. Kulaga"
    for a search on "Anton Kulaga". Without initials at least two full words must agree ("J. Smith" is not
    "K. Smith")."""
    a, b = _fold(found).split(), _fold(wanted).split()
    full_a, full_b = sorted(t for t in a if len(t) > 1), sorted(t for t in b if len(t) > 1)
    return sorted(a) == sorted(b) or (len(full_a) >= 2 and full_a == full_b)


def _author_line(a: dict[str, Any]) -> str:
    places = ", ".join(i["display_name"] for i in (a.get("last_known_institutions") or [])[:2])
    return f"{a['id'].rsplit('/', 1)[-1]} {a['display_name']} ({a['works_count']} works; {places or 'no institution'})"


def _author_ids(name: str) -> tuple[list[str], list[str], list[str]]:
    """The OpenAlex author record with this (folded) name and the most works, every record with that name, and,
    when none has it, the nearest records the search found, so that one can be passed with --author-id."""
    results = _openalex("authors", search=name, **{"per-page": 25})["results"]
    found = sorted((a for a in results if _same_name(a["display_name"], name)), key=lambda a: -a["works_count"])
    nearest = [] if found else [_author_line(a) for a in results[:5]]
    return [a["id"].rsplit("/", 1)[-1] for a in found[:1]], [_author_line(a) for a in found], nearest


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
        chosen, candidates, nearest = _author_ids(name)
        if candidates:
            typer.echo(f"{name}: " + "; ".join(candidates))
        else:
            typer.echo(f"{name}: OpenAlex has no author with this name." + (
                f" The nearest names it found: {'; '.join(nearest)}. If one of them is this person, run the command "
                "again with --author-id and the id before that name." if nearest else ""))
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
    typer.echo(f"\nJournals these researchers published in since {since} ({sum(counts.values())} papers, from "
               "OpenAlex). AI-policy work is explained in `venues.py rank`; a journal not in the catalogue has an "
               "AI policy nobody has read for it yet.\n")
    typer.echo("| Papers | Journal | Published by | Catalogue key | AI-policy work | What AI may do in the writing |")
    typer.echo("|---:|---|---|---|---|---|")
    missing: list[str] = []
    matched: list[str] = []
    for (sid, name), n in counts.most_common():
        key = by_source.get(sid) or by_name.get(_fold(name))
        if key:
            score, _ = friction(venues[key])
            matched.append(key)
            typer.echo(f"| {n} | {name} | {', '.join(sorted(who[(sid, name)]))} | `{key}` "
                       f"| {'not known' if score is None else f'{_points(score)} ({tier(score)})'} "
                       f"| {_sentence(WRITING_WORDS.get(venues[key].get('writing_help') or '', 'not researched'))} |")
        else:
            missing.append(name)
            typer.echo(f"| {n} | {name} | {', '.join(sorted(who[(sid, name)]))} | not in the catalogue "
                       "| not known | Not researched. |")
    if matched:
        typer.echo("\nRank just these: venues.py rank " + " ".join(f"--only {k}" for k in dict.fromkeys(matched)))
    if missing:
        typer.echo(f"\n{len(missing)} journals are not in the catalogue; read their AI policy before recommending "
                   "one.")


if __name__ == "__main__":
    app()
