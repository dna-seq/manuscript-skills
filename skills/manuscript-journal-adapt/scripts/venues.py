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
    uv run --script venues.py ladder --only KEY --only KEY --record REC.yaml --study-design software \
        --validation-available none --ai-use polish --min-jif 3 --budget-eur 3000
    uv run --script venues.py ladder --preprints --journal KEY --journal KEY --priority ai --record REC.yaml
    uv run --script venues.py common KEY KEY KEY --record REC.yaml    # what every venue on the ladder asks for
    uv run --script venues.py show <venue-key>                        # keys are listed by `rank`
    uv run --script venues.py peers "First Last" "Other Name" --since 2019

`ladder` reads from the record what the options leave out: the priorities (a default order, labelled as such,
when none are recorded), the study design (`study.designs`; one the authors have not confirmed never makes a
journal "Does not fit"), `priorities.validation_available`, `priorities.jif_floor`, `priorities.budget_eur` and
`ai_use`. An option given on the command line wins over the record.
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
# A writing rule that forbids what AI already did to this text (drafting under a red line on results and
# discussion, any substantial AI writing under a drafting ban) is more than paperwork: the authors would rewrite
# those sections themselves or declare a use the rule forbids. Counted only once the AI use is established.
CONFLICT_POINTS = 4
# Record-keeping is one cost however a policy words it: prompts on request, kept records, prompts in the paper.
RECORDS_COST = {"no": 0, "on_request": 1, "encouraged": 1, "recommended": 1, "required": 3}
# Paper-mill and plagiarism checks run at every large publisher and do not target AI-assisted writing.
SCREENING_COST = {"plagiarism": 0, "integrity_signals": 0, "may_detect_ai": 1, "ai_detector_deployed": 2}
MAX_BURDEN_POINTS = 2  # listed burdens differ in granularity between sources; more than two adds noise, not signal
# An extra burden that restates the record-keeping (outputs deposited, versions or prompts kept) is the same work
# the record-keeping points already count, so it is listed but not counted again.
RECORD_KEEPING = re.compile(r"\b(deposit\w*|kept|keep\w*|prompts?|versions?)\b", re.IGNORECASE)
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
# Each part of an AI policy, judged by the work it puts on the authors: "good" none beyond one declaration,
# "warning" some, "red" a red flag (drafting banned, prompts or a record of AI changes required, a detector run
# on submissions, declared use held against the paper), "unknown" not researched. The ladder and the review
# dashboard show these as icons; the ladder CSV writes each as "level: words".
AI_ASPECTS = {"drafting": "AI drafting", "prompts": "Prompts", "records": "Record of AI changes",
              "detection": "AI-text detection", "declaration": "Where to declare",
              "counted": "Declared use held against the paper", "extra": "Extra AI work"}
DRAFTING_FLAGS = {"free": ("good", "allowed, with no declaration"), "disclose": ("good", "allowed if declared"),
                  "disclose_all": ("warning", "every use declared, even language polish"),
                  "red_line": ("warning", "not in the results and discussion; allowed elsewhere if declared"),
                  "banned_drafting": ("red", "banned for the whole paper; correction aids only")}
PROMPT_FLAGS = {"no": ("good", "not asked for"), "on_request": ("warning", "given on request"),
                "encouraged": ("warning", "encouraged in the paper"), "recommended": ("warning", "recommended"),
                "required": ("red", "required in the paper")}
TRACKING_FLAGS = {"no": ("good", "not asked for"), "on_request": ("warning", "given on request"),
                  "recommended": ("warning", "kept in case the journal asks"),
                  "required": ("red", "required: outputs deposited or versions kept")}
SCREENING_FLAGS = {"plagiarism": ("good", "none named; plagiarism checks only"),
                   "integrity_signals": ("good", "none named; plagiarism and paper-mill checks"),
                   "may_detect_ai": ("warning", "may be used"), "ai_detector_deployed": ("red", "run on submissions")}
FLAG_ICONS = {"good": "✓", "warning": "!", "red": "⚑", "unknown": "?"}
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
                "drafting": "AI wrote new sentences or sections",
                "unknown": "what AI did to the text has not been established"}
VALIDATION_WORDS = {"none": "none of these", "independent-cohort": "an independent cohort",
                    "wet-lab": "wet-lab experiments", "multi-database": "results from more than one database",
                    "primary-analysis": "a primary analysis"}
DESIGN_WORDS = {"software": "software or resource", "public-data": "public-data reanalysis",
                "bioinformatics": "bioinformatics-finding", "mr": "Mendelian randomisation",
                "bibliometric": "bibliometric", "public-health-database": "public health-database", "other": "other"}
# The verdict in the words the authors read; the codes (go, conditional, unknown, no-go) stay internal.
FIT_WORDS = {"go": "Fits", "conditional": "Depends", "unknown": "Could not be checked",
             "no-go": "Does not fit the stated constraints"}
# The red flags of an AI policy as sentences, for the ladder table (the CSV keeps "red: words" per aspect).
RED_FLAG_SENTENCES = {"drafting": "AI drafting is banned for the whole paper; only correction aids are allowed.",
                      "prompts": "The prompts must be given in the paper.",
                      "records": "AI outputs must be deposited or the versions kept.",
                      "detection": "An AI-text detector is run on submissions.",
                      "counted": "Declared AI use may be held against the paper."}
# A burden ruled out with --refuse, in words, for the venues of a shortlist that it left out.
BURDEN_WORDS = {"drafting-ban": "a ban on AI drafting", "red-line": "a ban on AI-written results or discussion",
                "prompts": "the prompts in the paper", "tracking": "records of AI use beyond one acknowledgement",
                "ai-detector": "AI-text detection", "supplement": "AI use documented in the supplement as well",
                "multi-place": "the AI-use statement in three or more places",
                "disclosure-penalty": "declared AI use that may count against the paper"}
# The shared record's study-design keys (manuscript-record.md) for the designs the validation rules name; any
# other record key is "other". The ladder's own keys are accepted as they are.
RECORD_DESIGNS = {"software-tool": "software", "database-resource": "software", "method-benchmark": "software",
                  "public-data-reanalysis": "public-data", "omics-profiling": "bioinformatics",
                  "genetic-association": "bioinformatics", "polygenic-score": "bioinformatics",
                  "mendelian-randomization": "mr"}
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
    unknown = "unknown"  # not established yet: each rule is described for every kind of use, no conflict assumed


AI_USE_RANK = {"polish": 0, "revision": 1, "drafting": 2}


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
# The transfer priority on the journal ladder: the preprint the authors post goes to the journal directly.
JOURNAL_TRANSFER_WORDS = "a direct transfer from your preprint server"
# The order a ladder uses until the authors state theirs; labelled as a default and never saved to the record.
# Journals: a fast first decision makes a rejection cost weeks rather than months and keeps the next journal on
# the ladder within reach; reach is what most authors weigh next; the AI-policy points count paperwork, not the
# chance of acceptance; cost comes last because the authors' budget decides it, and until they state it every
# fee they would pay stays visible as "Depends". Preprint servers: a direct transfer to a journal on the
# journal ladder saves a second submission, then speed, then AI-policy work (posting is usually free).
DEFAULT_PRIORITIES = {"journals": ["speed", "reach", "ai", "cost"], "preprints": ["transfer", "speed", "ai"]}
FIT_ORDER = {"go": 0, "conditional": 1, "unknown": 2, "no-go": 3}
# The ladder's first step: "Depends" and "could not be checked" tie, so that a journal whose rules were researched
# does not rise above one whose rules were not; only a fit the rules settle ("fits", "does not fit") moves a venue.
LADDER_FIT = {"go": 0, "conditional": 1, "unknown": 1, "no-go": 2}


class OutputFormat(str, Enum):
    md = "md"  # a table for the authors
    csv = "csv"  # one row per rung, in LADDER_COLUMNS; an empty cell means not known, never zero


# The ladder's CSV columns, in order. Units are in the names; numbers only in the numeric columns. `fits` is the
# whole verdict (validation rules, a conflict between the AI policy and the established AI use, the fee against
# the budget); `validation_fits` is the validation rules alone, which the ladder sorts by.
LADDER_COLUMNS = [
    "ladder", "rung", "chosen_rung", "key", "name", "fits", "fits_reason", "validation_fits", "validation_reason",
    "first_decision_days", "speed_measure", "speed_source", "speed_checked",
    "jif", "jif_year", "ai_points", "ai_tier", "ai_for_this_use",
    "ai_red_flags", "ai_drafting", "ai_prompts", "ai_records", "ai_detection", "ai_declaration", "ai_counted",
    "ai_extra", "ai_reasons", "ai_policy_url",
    "fee_amount", "fee_currency", "fee_year", "author_cost_eur", "fee_route", "fee_source", "fee_checked",
    "preprint_rule", "transfers", "guidelines_url", "facts_from_record", "priorities", "priorities_source",
    "ai_use", "study_designs",
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


def friction(v: dict[str, Any], ai_use: Optional[AiUse] = None) -> tuple[Optional[int], list[str]]:
    """Points, and the reasons behind them. None when the policy was not researched.

    Writing rule (0 free to 5 drafting ban) + record keeping (the highest of prompts and tracking, 0 to 3) +
    AI-text screening (0 to 2) + listed extra burdens (at most 2) + 1 if the policy says disclosed use may count
    against the paper, - 1 if it says it will not, + CONFLICT_POINTS when the writing rule conflicts with the AI
    use the authors established (`ai_conflict`; none while the use is unknown). Record keeping is counted once: a
    listed extra burden that restates it (outputs deposited, versions or prompts kept) is named but adds no points
    when the record-keeping points already count it. Disclosure places are a filter (`--refuse multi-place`), not
    points: repeating one statement costs little."""
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
    listed_burden = v.get("extra_burden") or []
    repeats = [b for b in listed_burden if records and RECORD_KEEPING.search(str(b))]
    burden = [b for b in listed_burden if b not in repeats]
    counted = min(len(burden), MAX_BURDEN_POINTS)
    score += counted
    if burden:
        listed = _and([f'"{b}"' for b in burden])
        cap = f", at most {MAX_BURDEN_POINTS} counted" if len(burden) > MAX_BURDEN_POINTS else ""
        reasons.append(f"It also lists extra work ({_points(counted)}{cap}): {listed}.")
    if repeats:
        same = _and([f'"{b}"' for b in repeats])
        reasons.append(f"It also lists {same}, the same record keeping, counted once above.")
    if v.get("disclosure_neutral") is False:
        score += 1
        reasons.append("It says declared AI use may count against the paper (1 point).")
    elif v.get("disclosure_neutral") is True:
        score = max(0, score - 1)
        reasons.append("It says declared AI use does not count against the paper (minus 1 point).")
    if ai_use is not None and ai_conflict(v, ai_use):
        score += CONFLICT_POINTS
        reasons.append(f"Its writing rule forbids what AI did to this text ({AI_USE_WORDS[ai_use.value]}), so those "
                       f"sections would be rewritten by you or the use declared against the rule "
                       f"({_points(CONFLICT_POINTS)}).")
    return score, reasons


def ai_flags(v: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Each aspect of the venue's AI policy as (level, words), from the same fields `friction` scores."""
    if v.get("writing_help") is None:
        return {aspect: ("unknown", "not researched") for aspect in AI_ASPECTS}
    places = v.get("disclosure_places") or []
    neutral = v.get("disclosure_neutral")
    extra = v.get("extra_burden") or []
    if not places:
        declaration = ("unknown", "not recorded")
    elif len(places) >= 3 or Burden.supplement in burdens(v):
        declaration = ("warning", f"{len(places)} places: " + "; ".join(places))
    else:
        declaration = ("good", "; ".join(places))
    return {
        "drafting": DRAFTING_FLAGS.get(v["writing_help"], ("unknown", "not recorded")),
        "prompts": PROMPT_FLAGS.get(v.get("prompts") or "no", ("unknown", "not recorded")),
        "records": TRACKING_FLAGS.get(v.get("tracking") or "no", ("unknown", "not recorded")),
        "detection": SCREENING_FLAGS.get(v.get("screening") or "plagiarism", ("unknown", "not recorded")),
        "declaration": declaration,
        "counted": ("good", "no, the policy says so") if neutral is True else
                   ("red", "yes, the policy says it may") if neutral is False else ("unknown", "not stated"),
        "extra": ("warning", "; ".join(extra)) if extra else ("good", "none listed"),
    }


def red_flags(v: dict[str, Any]) -> str:
    """The red flags of a venue's AI policy as sentences, for the ladder table the authors read (the icons and
    levels stay in the CSV and the dashboard)."""
    flags = ai_flags(v)
    if all(level == "unknown" for level, _ in flags.values()):
        return "Not known, because the AI policy has not been researched."
    red = [RED_FLAG_SENTENCES.get(a) or _sentence(f"{AI_ASPECTS[a]}: {words}")
           for a, (level, words) in flags.items() if level == "red"]
    return " ".join(red) if red else "None."


def tier(score: Optional[int]) -> str:
    if score is None:
        return "?"
    return next((word for limit, word in TIERS if score <= limit), SEVERE)


def verdict(v: dict[str, Any], ai_use: AiUse) -> str:
    """What the venue's writing rule means for this kind of AI use; with the use not established, what it would
    mean for each kind, and no conflict assumed."""
    rule = v.get("writing_help")
    if rule is None:
        return "Not known, because the AI policy has not been researched; read the live page."
    if ai_use == AiUse.unknown:
        pending = "Depends on what AI did to the text, which has not been established: "
        if rule == "banned_drafting":
            return pending + ("language correction is allowed under the recorded policy, but the journal asks "
                              "authors not to have AI draft text.")
        if rule == "red_line":
            return pending + ("AI help is allowed if declared, except AI-drafted results or discussion, which the "
                              "journal reserves for the authors.")
        if rule == "disclose" and v.get("exempt"):
            return ("Allowed; declare it. The recorded disclosure exemptions are: " + _and(v["exempt"])
                    + "; whether one covers this paper depends on what AI did to the text.")
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
    """A fit cell: the verdict in words, then why."""
    return f"{FIT_WORDS[status]}. {reason}"


def _worse(a: str, b: str) -> str:
    return max(a, b, key=FIT_ORDER.__getitem__)


def feasibility(v: dict[str, Any], designs: list[str], available: Optional[set[str]],
                confirmed: bool = True) -> tuple[str, str]:
    """The validation fit for the paper's study designs, which `ladder` sorts by.

    A mixed study is judged under each design: when one design would rule the venue out and another would not,
    the venue depends on how its editors read the paper. A design the authors have not confirmed (a skill's
    draft in the record) can lower a venue to "Depends", never to "Does not fit"."""
    if not designs:
        return validation_fit(v, None, available)
    outcomes = [(d, *validation_fit(v, d, available)) for d in designs]
    statuses = {status for _, status, _ in outcomes}
    worst = max(statuses, key=FIT_ORDER.__getitem__)
    if len(outcomes) == 1 or len(statuses) == 1:
        status, reason = worst, " ".join(dict.fromkeys(r for _, _, r in outcomes))
    else:
        status = "conditional" if worst == "no-go" else worst
        reason = ("It depends on which kind of paper the editors take this one for. "
                  + " ".join(f"As a {DESIGN_WORDS.get(d, d)} paper: {r}" for d, _, r in outcomes))
    if status == "no-go" and not confirmed:
        kinds = _or([f"a {DESIGN_WORDS.get(d, d)} paper" for d in designs])
        status = "conditional"
        reason += (f" This holds only if the paper is {kinds}, a study design the authors have not confirmed "
                   "yet.")
    return status, reason


def ai_conflict(v: dict[str, Any], ai_use: AiUse) -> Optional[str]:
    """The venue's writing rule against the AI use the authors established, when they conflict; None when they do
    not or the use is not established. A conflict is the authors' decision, never a reason to drop the venue."""
    rule = v.get("writing_help")
    if ai_use in (AiUse.unknown, AiUse.polish) or rule not in ("banned_drafting", "red_line"):
        return None
    if rule == "red_line" and ai_use != AiUse.drafting:
        return None
    return verdict(v, ai_use)


def overall_fit(v: dict[str, Any], feasible: tuple[str, str], ai_use: AiUse,
                budget_eur: Optional[float]) -> tuple[str, str]:
    """The verdict the authors read: the validation fit, lowered to "Depends" by a conflict between the AI policy
    and the established AI use, or by a fee the authors would pay that is above their budget or not yet weighed
    against one (an unknown budget is not read as "cost does not matter")."""
    status, reasons = feasible[0], [feasible[1]]
    conflict = ai_conflict(v, ai_use)
    if conflict:
        status = _worse(status, "conditional")
        reasons.append(f"{conflict} How to handle the journal's policy is your decision.")
    cost = fee_eur(v)[0]
    if cost is not None and cost > 0:
        if budget_eur is None:
            status = _worse(status, "conditional")
            reasons.append(f"It depends on whether you can pay the fee, about {cost:g} EUR for you: your budget "
                           "has not been stated yet.")
        elif cost > budget_eur:
            status = _worse(status, "conditional")
            reasons.append(f"The fee you would pay, about {cost:g} EUR, is above your budget of {budget_eur:g} EUR "
                           "unless a waiver or an agreement covers it.")
    return status, " ".join(reasons)


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


def _left_out_reason(v: dict[str, Any], *, field: Optional[list[str]], article_type: Optional[list[str]],
                     software: bool, oa: Optional[list[str]], min_jif: Optional[float],
                     refused: set[Burden]) -> Optional[str]:
    """Why a filter leaves this venue out, in words; None when every filter keeps it."""
    if field and not set(v.get("fields") or []) & set(field):
        return "not tagged with the fields asked for"
    if (article_type or software) and not _has_type(v, (article_type or []) + (["software"] if software else [])):
        return "no recorded article type of the kind asked for"
    if oa and v.get("oa") not in oa:
        return f"its access model is {_access(v)}"
    if min_jif is not None and v.get("jif") is None:
        return f"no impact factor is recorded, and the floor is {min_jif:g}"
    if min_jif is not None and v["jif"] < min_jif:
        return f"its impact factor, {v['jif']}, is below the floor of {min_jif:g}"
    ruled_out = sorted(b.value for b in burdens(v) & refused)
    if ruled_out:
        return "it asks for " + _and([BURDEN_WORDS[b] for b in ruled_out]) + ", which you ruled out"
    return None


def _selected(venues: dict[str, dict[str, Any]], *, preprints: bool, only: Optional[list[str]],
              field: Optional[list[str]], article_type: Optional[list[str]], software: bool,
              oa: Optional[list[str]], min_jif: Optional[float],
              refused: set[Burden]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """The venues the filters keep, and, from an explicit shortlist (`only`), each venue a filter left out, named
    with the reason so that nothing the authors listed disappears silently. No venue is left out by default:
    record-keeping rules are a burden to weigh, and leaving them out takes `--refuse tracking`."""
    kept: dict[str, dict[str, Any]] = {}
    left_out: list[str] = []
    pool = journals(venues, preprints)
    for key in dict.fromkeys(only or []):
        if key not in pool:
            kind = "preprint server" if preprints else "journal"
            other = "a preprint server" if venues.get(key, {}).get("kind") == "preprint" else (
                "a journal" if key in venues and not venues[key].get("kind") else None)
            left_out.append(f"{_name(venues[key]) if key in venues else key} (" + (
                f"{other}, not a {kind}" if other else f"not a {kind} in the catalogue or the record") + ")")
    for key, v in pool.items():
        if only and key not in only:
            continue
        reason = _left_out_reason(v, field=field, article_type=article_type, software=software, oa=oa,
                                  min_jif=min_jif, refused=refused)
        if reason:
            if only:
                left_out.append(f"{_name(v)} ({reason})")
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


def record_context(path: Optional[Path]) -> dict[str, Any]:
    """What else the record says that the ladder needs, each None when the record does not say it:

    - `designs`: `study.designs` as the ladder's design keys (RECORD_DESIGNS; unknown keys count as "other"),
      `confirmed`: whether `study.confirmed` is set (the authors confirmed the design);
    - `validation`: `priorities.validation_available`, the validation routes the authors have or can afford;
    - `ai_use`: what AI did to the text, `ai_use: polish | revision | drafting` (a mapping per section gives the
      most substantial use);
    - `jif_floor` and `budget_eur`: `priorities.jif_floor` and `priorities.budget_eur`."""
    out: dict[str, Any] = {"designs": None, "confirmed": False, "validation": None, "ai_use": None,
                           "jif_floor": None, "budget_eur": None}
    if path is None:
        return out
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    study = raw.get("study") if isinstance(raw.get("study"), dict) else {}
    designs = study.get("designs")
    if designs:
        keys = [designs] if isinstance(designs, str) else [str(d) for d in designs]
        own = {d.value for d in StudyDesign}
        out["designs"] = list(dict.fromkeys(k if k in own else RECORD_DESIGNS.get(k, "other") for k in keys))
        out["confirmed"] = bool(study.get("confirmed"))
    priorities = raw.get("priorities") if isinstance(raw.get("priorities"), dict) else {}
    routes = priorities.get("validation_available")
    if routes is not None:
        routes = [routes] if isinstance(routes, str) else [str(r) for r in routes]
        allowed = {v.value for v in Validation}
        if not set(routes) <= allowed:
            raise typer.BadParameter("the record's priorities.validation_available must be among "
                                     + ", ".join(sorted(allowed)))
        out["validation"] = set(routes)
    use = raw.get("ai_use")
    if isinstance(use, dict):
        use = list(use.values())
    if isinstance(use, list):
        known = [str(u) for u in use if str(u) in AI_USE_RANK]
        use = max(known, key=AI_USE_RANK.__getitem__) if known else None
    if use is not None:
        if str(use) not in {u.value for u in AiUse}:
            raise typer.BadParameter("the record's ai_use must be polish, revision, drafting or unknown")
        out["ai_use"] = AiUse(str(use))
    for name in ("jif_floor", "budget_eur"):
        if priorities.get(name) is not None:
            try:
                out[name] = float(priorities[name])
            except (TypeError, ValueError) as exc:
                raise typer.BadParameter(f"the record's priorities.{name} must be a number") from exc
    return out


def recorded_ladder(path: Optional[Path], preprints: bool) -> list[str]:
    """The order the authors chose for one ladder (`ladders: {journals: [...], preprints: [...]}` in the record),
    which may move a rung away from the sorted order for a reason the report states; [] when none is recorded."""
    if path is None:
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [str(k) for k in (raw.get("ladders") or {}).get("preprints" if preprints else "journals") or []]


def _merged(base: Any, given: Any) -> Any:
    """`given` laid over `base`: mappings merge key by key at every depth (a `limits` that gives only the abstract
    keeps the catalogue's body limit); anything else, lists included, is replaced."""
    if isinstance(base, dict) and isinstance(given, dict):
        return {**base, **{k: _merged(base.get(k), v) for k, v in given.items()}}
    return given


def with_facts(venues: dict[str, dict[str, Any]], facts: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The catalogue with the task's facts laid over it, field by field (mappings such as `limits` and
    `open_science` key by key). A venue the catalogue lacks can be added by the facts when they give it a name;
    `from_facts` lists the fields that came from the task."""
    out = dict(venues)
    for key, given in facts.items():
        if key not in venues and not given.get("name"):
            raise typer.BadParameter(f"the facts describe {key!r}, which the catalogue does not know; give it a "
                                     "name to add it for this task")
        out[key] = {**_merged(venues.get(key, {}), given), "key": key, "from_facts": sorted(given)}
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
                   journals_on_ladder: Optional[list[str]] = None, ai_use: Optional[AiUse] = None,
                   server: Optional[dict[str, Any]] = None) -> Optional[float]:
    """The venue's value on one priority, lower is better; None when not known. For `transfer` on the preprint
    ladder, the rung (counted from 0, in the order the journals are given) of the first journal the server
    transfers to directly; a server whose checked list reaches none of them comes after every one that reaches
    some. For `transfer` on the journal ladder (with the authors' preprint `server`), 0 when the server transfers
    to the journal directly, 1 when its checked list leaves the journal out. For `ai`, the AI-policy points for
    the established AI use, a conflicting writing rule included."""
    if priority == Priority.transfer and server is not None:
        return {"yes": 0.0, "no": 1.0}.get(from_server(v, server))
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
        return friction(v, ai_use)[0]
    return fee_eur(v)[0]


def from_server(v: dict[str, Any], server: dict[str, Any]) -> str:
    """Whether the authors' preprint server transfers manuscripts to this journal directly: "yes", "no" when the
    server's list was checked for it and leaves it out, "unknown" otherwise."""
    transfers = server.get("transfers")
    if transfers is None:
        return "unknown"
    if v["key"] in transfers:
        return "yes"
    return "no" if v["key"] in set(server.get("transfers_checked") or []) else "unknown"


def ladder_order(v: dict[str, Any], priorities: list[Priority], feasible: str,
                 journals_on_ladder: Optional[list[str]] = None, ai_use: Optional[AiUse] = None,
                 server: Optional[dict[str, Any]] = None) -> tuple[Any, ...]:
    """Feasibility (the validation fit, `feasibility`) first, then each priority in the authors' order. At the first
    step "Depends" and "could not be checked" tie (LADDER_FIT). An unknown value sorts below every known one at its
    step, and a tie passes to the next priority; the name breaks the last tie."""
    key: list[Any] = [LADDER_FIT[feasible]]
    for p in priorities:
        value = priority_value(v, p, journals_on_ladder, ai_use, server)
        key.append((1, 0.0) if value is None else (0, value))
    key.append(_name(v).lower())
    return tuple(key)


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().rstrip(".").lower()


# The headings of a paper's main parts. A required section named only by these fills a part every version has, so
# venues that name or order them differently disagree; any other section (keywords, declarations, abbreviations) is
# an addition the other versions can carry.
BODY_SECTIONS = {"introduction", "background", "methods", "materials and methods", "implementation",
                 "design and implementation", "results", "discussion", "results and discussion", "conclusion",
                 "conclusions", "availability and future directions", "future directions"}


def _body_section(text: Any) -> bool:
    """Whether a required section is one of the paper's main parts: "Methods (after Conclusions)" and
    "Introduction, Results and Discussion" are; "Availability and requirements" and "Keywords" are not."""
    name = re.sub(r"\(.*", "", str(text)).strip().rstrip(".").lower()
    name = re.sub(r"^complete\s+|\s+sections?$", "", name)
    parts = [part for part in re.split(r",\s*|\s+and\s+", name) if part]
    return name in BODY_SECTIONS or (bool(parts) and all(part in BODY_SECTIONS for part in parts))


def _who(names: list[str], total: int) -> str:
    return "every venue" if len(names) == total and total > 1 else _and(names)


# ------------------------------------------------------------------------------------------------ commands

@app.command()
def rank(
    ai_use: Annotated[AiUse, typer.Option(
        help="What AI did to the text: polish, revision or drafting; unknown (the default) until the "
             "conversation or the record establishes it")] = AiUse.unknown,
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
        hidden=True, help="No longer needed: record-keeping venues are listed unless --refuse tracking")] = False,
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
                               software=software, oa=oa, min_jif=min_jif, refused=refused)
    for key, v in kept.items():
        score, reasons = friction(v, ai_use)
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
               "you stated. \"Could not be checked\" means the rules have not been researched, which is not the "
               "same as having none.")
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
        typer.echo("\nLeft out of the venues you listed: " + "; ".join(left_out) + ".")
    glossary = abbreviations("\n".join(printed + left_out))
    if glossary:
        typer.echo("\n" + glossary)
    if stale:
        # An author's task never writes the plugin's snapshots: `check --venue KEY` without --update only reads.
        typer.echo(f"\nWARNING: {stale} of these policies were read more than {STALE_AFTER_DAYS} days ago. Re-read "
                   "the policy page of every venue you shortlist (policy_watch.py check --venue KEY, which changes "
                   "nothing in the plugin), and read the live page for any it cannot reach.", err=True)


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
                   preprints: bool, posted: Optional[dict[str, Any]] = None) -> str:
    """For a journal, its rule on manuscripts already posted as preprints, and with the authors' preprint server
    whether it transfers the manuscript there directly; for a preprint server, the journals it transfers
    manuscripts to directly, narrowed to the journal ladder when one is given. A journal missing from a server's
    list counts as "not to" only when the list was checked for it (`transfers_checked`)."""
    if not preprints:
        rule = (v.get("open_science") or {}).get("preprints")
        cell = _sentence(rule) if rule else "Not known."
        if posted is not None:
            cell += " " + {"yes": f"{_name(posted)} transfers the manuscript here directly.",
                           "no": f"{_name(posted)} does not transfer here directly.",
                           "unknown": f"Whether {_name(posted)} transfers here directly was not checked."}[from_server(v, posted)]
        return cell
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
             "transfer. Without it the record's `priorities` are used, and without those a default order that the "
             "output labels as a default (journals: speed, reach, ai, cost; preprint servers: transfer, speed, "
             "ai)")] = None,
    record: Annotated[Optional[Path], typer.Option(
        help="The manuscript record (or a facts file): its `priorities`, study design, validation, AI use, "
             "impact-factor floor and budget, and the `venue_facts` researched for this manuscript, laid over the "
             "catalogue")] = None,
    only: Annotated[Optional[list[str]], typer.Option(
        help="Only these venue keys (the shortlist); repeat --only for each. A listed venue a filter leaves out "
             "is named with the reason")] = None,
    field: Annotated[Optional[list[str]], typer.Option(help="Keep venues tagged with any of these fields")] = None,
    article_type: Annotated[Optional[list[str]], typer.Option("--type", help="Keep venues taking this type")] = None,
    software: Annotated[bool, typer.Option(help="Only venues with a software article type")] = False,
    oa: Annotated[Optional[list[str]], typer.Option(help="Keep these access models: full, hybrid, subscription")] = None,
    min_jif: Annotated[Optional[float], typer.Option(
        help="Drop venues below this JIF (and those without one); default: the record's priorities.jif_floor")] = None,
    refuse: Annotated[Optional[list[Burden]], typer.Option(
        help="Drop venues that impose this; repeatable (tracking leaves out venues that require AI records "
             "beyond one acknowledgement, which are kept unless refused)")] = None,
    include_tracking: Annotated[bool, typer.Option(
        hidden=True, help="No longer needed: record-keeping venues are listed unless --refuse tracking")] = False,
    preprints: Annotated[bool, typer.Option(help="Order preprint servers instead of journals")] = False,
    journal: Annotated[Optional[list[str]], typer.Option(
        help="With --preprints: the journals on the journal ladder, to show which ones each server transfers "
             "to directly; repeatable")] = None,
    server: Annotated[Optional[str], typer.Option(
        help="On the journal ladder: the preprint server the authors post to, for the transfer priority and the "
             "direct-transfer column (whether the server sends the preprint to each journal); default: the first "
             "rung of the record's preprint ladder")] = None,
    ai_use: Annotated[Optional[AiUse], typer.Option(
        help="What AI did to the text: polish, revision or drafting; default: the record's ai_use, else unknown "
             "(no conflict assumed)")] = None,
    study_design: Annotated[Optional[StudyDesign], typer.Option(
        help="What the paper contributes, for the validation rules (see `rank --help`); default: the record's "
             "study.designs")] = None,
    validation_available: Annotated[Optional[list[Validation]], typer.Option(
        help="Validation already available or affordable; repeatable; 'none' when unavailable; default: the "
             "record's priorities.validation_available")] = None,
    budget_eur: Annotated[Optional[float], typer.Option(
        help="The most the authors would pay to publish, in euros; default: the record's priorities.budget_eur. "
             "Without a budget, a fee the authors would pay makes a venue \"Depends\"")] = None,
    output: Annotated[OutputFormat, typer.Option(
        "--format", help="md: a table for the authors; csv: one row per venue in fixed columns (an empty cell "
                         "means not known; notes go to standard error)")] = OutputFormat.md,
) -> None:
    """A shortlist ordered into a ladder: feasibility first, then each of the authors' priorities in turn."""
    _, venues = load_venues()
    recorded, facts = load_record(record, preprints)
    venues = with_facts(venues, facts)
    context = record_context(record)
    try:
        priorities = list(priority or []) or [Priority(p) for p in recorded]
    except ValueError as exc:
        raise typer.BadParameter("the record's priorities must be among " +
                                 ", ".join(p.value for p in Priority)) from exc
    default_order = not priorities
    if default_order:
        # Until the authors state an order: a labelled default, never saved to the record. The transfer step
        # needs the journal ladder, so a preprint ladder without one starts at speed.
        priorities = [Priority(p) for p in DEFAULT_PRIORITIES["preprints" if preprints else "journals"]
                      if p != "transfer" or journal]
    if len(set(priorities)) != len(priorities):
        raise typer.BadParameter("name each priority once")
    if not preprints:
        server = server or next(iter(recorded_ladder(record, True)), None)
        if server is not None and server not in venues:
            raise typer.BadParameter(f"unknown preprint server {server!r}")
    posted = venues[server] if server and not preprints else None
    if Priority.transfer in priorities and not ((preprints and journal) or posted):
        raise typer.BadParameter("the transfer priority orders preprint servers (--preprints) by the journal ladder "
                                 "given with --journal, in ladder order, or journals by whether the preprint server "
                                 "(--server, or the first rung of the record's preprint ladder) transfers to them")
    unknown = sorted(set(journal or []) - set(venues))
    if unknown:
        raise typer.BadParameter(f"unknown journal keys: {', '.join(unknown)}")
    available = ({value.value for value in validation_available} if validation_available is not None
                 else context["validation"])
    if available and "none" in available and len(available) > 1:
        raise typer.BadParameter("'none' cannot be combined with an available validation route")
    designs = [study_design.value] if study_design else (context["designs"] or [])
    confirmed = study_design is not None or context["confirmed"]
    use = ai_use or context["ai_use"] or AiUse.unknown
    floor = min_jif if min_jif is not None else (None if preprints else context["jif_floor"])
    budget = budget_eur if budget_eur is not None else context["budget_eur"]
    kept, left_out = _selected(venues, preprints=preprints, only=only, field=field, article_type=article_type,
                               software=software, oa=oa, min_jif=floor, refused=set(refuse or []))
    feasible = {key: feasibility(v, designs, available, confirmed) for key, v in kept.items()}
    rows = sorted(kept.values(), key=lambda v: ladder_order(v, priorities, feasible[v["key"]][0], journal, use, posted))
    verdicts = {v["key"]: overall_fit(v, feasible[v["key"]], use, budget) for v in rows}
    notes = _ladder_notes(default_order, priorities, preprints, designs, confirmed, study_design is not None,
                          available, use, floor, budget, posted)
    if output == OutputFormat.csv:
        _ladder_csv(rows, venues, priorities, feasible, verdicts, journal, preprints, use,
                    recorded_ladder(record, preprints), "default" if default_order else "authors", designs, posted)
        if default_order:
            typer.echo("Note: no priorities are recorded for this ladder, so it uses the default order ("
                       + ", ".join(p.value for p in priorities) + "); the priorities_source column says "
                       "\"default\". Ask the authors for their order among the end-of-run decisions and rerun; "
                       "never save the default to the record.", err=True)
        if left_out:
            typer.echo("Left out of the venues listed with --only: " + "; ".join(left_out) + ".", err=True)
        return
    kind = "Preprint" if preprints else "Journal"
    typer.echo(f"# {kind} ladder\n")
    for note in notes:
        typer.echo(note + "\n")
    last = "Direct transfer" if preprints else "Manuscripts already posted as preprints"
    typer.echo(f"| Position | {'Server' if preprints else 'Journal'} | Fits | Speed | Reach "
               f"| AI-policy work | AI-policy red flags | What this means for your AI use | Cost | {last} |")
    typer.echo("|---:|---|---|---|---|---|---|---|---|---|")
    printed: list[str] = []
    for n, v in enumerate(rows, 1):
        fit, reason = verdicts[v["key"]]
        score, _ = friction(v, use)
        work = "not known" if score is None else tier(score)
        printed.append(f"| {n} | {_name(v)} (`{v['key']}`) | {fit_text(fit, reason)} | {_sentence(speed_days(v)[1])} "
                       f"| {_sentence(_jif(v))} | {_sentence(work)} | {red_flags(v)} | {verdict(v, use)} "
                       f"| {_sentence(fee_eur(v)[1])} | {_preprint_cell(v, venues, journal, preprints, posted)} |")
        typer.echo(printed[-1])
    if Priority.speed in priorities:
        # Publishers count first decisions over different papers: with desk rejections, after peer review only,
        # or over published papers only. Ranking such figures against each other orders the counting, not the speed.
        kinds = {}
        for v in rows:
            m = _first_decision(v)
            if m:
                kinds.setdefault(", ".join(str(m[k]) for k in ("statistic", "population") if m.get(k)) or "not described",
                                 []).append(_name(v))
        if len(kinds) > 1:
            typer.echo("\nThe first-decision figures are not like for like: " + "; ".join(
                f"{_and(names)}: {kind}" for kind, names in kinds.items()) + ". Before letting speed decide between "
                "these journals, compare a like-for-like measure, such as submission to publication for a sample of "
                "recent papers in each, and say in the report which order that gives.")
    for p in priorities:
        missing = [_name(v) for v in rows if priority_value(v, p, journal, use, posted) is None]
        if missing:
            words = JOURNAL_TRANSFER_WORDS if p == Priority.transfer and posted else PRIORITY_WORDS[p.value]
            typer.echo(f"\nNot known, so placed below the known values at the step for {words}: {_and(missing)}.")
    from_task = [f"{_name(v)} ({', '.join(f.replace('_', ' ') for f in v['from_facts'] if f not in TASK_ONLY)})"
                 for v in rows if set(v.get("from_facts") or []) - TASK_ONLY]
    if from_task:
        typer.echo("\nFacts read for this manuscript and taken from its record: " + "; ".join(from_task) + ".")
    if left_out:
        typer.echo("\nLeft out of the venues you listed: " + "; ".join(left_out) + ".")
    glossary = abbreviations("\n".join(printed + left_out))
    if glossary:
        typer.echo("\n" + glossary)


# Fields of `venue_facts` that describe the reading, not the venue: not listed as facts taken from the record.
TASK_ONLY = {"not_read"}


def _ladder_notes(default_order: bool, priorities: list[Priority], preprints: bool, designs: list[str],
                  confirmed: bool, design_given: bool, available: Optional[set[str]], use: AiUse,
                  floor: Optional[float], budget: Optional[float],
                  posted: Optional[dict[str, Any]] = None) -> list[str]:
    """The paragraphs above the ladder table: whose order it is, how it was sorted, and what it assumed."""
    def said(p: Priority) -> str:
        if p == Priority.transfer and posted is not None:
            return f"{JOURNAL_TRANSFER_WORDS}, {_name(posted)}"
        return PRIORITY_WORDS[p.value]

    steps = ", then by ".join(said(p) for p in priorities)
    notes = []
    if default_order:
        order = ", then ".join(said(p) for p in priorities)
        notes.append("**A default order, not yours yet.** You have not stated what matters most to you, so this "
                     f"ladder uses a default: {order}. It changes when you state your own order.")
    notes.append(f"Ordered by whether the paper fits each venue's recorded validation rules (\"Depends\" and \"could "
                 f"not be checked\" count the same), then by {steps}. A value "
                 "that is not known sorts below every known value at its step, and a tie passes to the next step. A "
                 "position is an order of preference under these priorities, not a chance of acceptance"
                 + ("; the speed compared is days to a first decision, which for most journals includes desk "
                    "rejections" if Priority.speed in priorities and not preprints else "") + ". AI-policy work is the paperwork a venue's AI policy "
                 "asks of the authors, from light to severe, and a writing rule that forbids what AI already did to "
                 "the text counts as severe; it is not the chance of rejection.")
    assumed = []
    if designs:
        kinds = _and([f"a {DESIGN_WORDS.get(d, d)} paper" for d in designs])
        if design_given:
            assumed.append(f"The validation rules are read for {kinds}.")
        elif confirmed:
            assumed.append(f"The validation rules are read for {kinds}, the study design the authors confirmed in "
                           "the manuscript record.")
        else:
            assumed.append(f"The validation rules are read for {kinds}, the study design in the manuscript record, "
                           "which the authors have not confirmed yet; until they do, a rule it falls under can make "
                           "a venue \"Depends\", never \"Does not fit\".")
    else:
        assumed.append("No study design is recorded, so each validation rule is shown as a condition to check.")
    if available is None:
        assumed.append("Which validation you have or can afford is not recorded.")
    else:
        assumed.append("Validation you have or can afford: "
                       + _and([VALIDATION_WORDS.get(a, a) for a in sorted(available)]) + ".")
    assumed.append("What AI did to the text has not been established, so the column on your AI use says what each "
                   "rule would mean, and no conflict is assumed." if use == AiUse.unknown
                   else f"The AI use compared with each policy: {AI_USE_WORDS[use.value]}.")
    if floor is not None:
        assumed.append(f"Venues below an impact factor of {floor:g}, or without one, are left out.")
    if not preprints:
        assumed.append(f"Your budget is {budget:g} EUR." if budget is not None else
                       "Your budget is not known yet, so every fee you would pay is shown and marks the venue "
                       "\"Depends\" until you state it.")
    notes.append(" ".join(assumed))
    return notes


def _transfers_cell(transfers: Optional[list[str]], checked: Optional[list[str]],
                    journals_on_ladder: Optional[list[str]]) -> str:
    """The direct transfers for the CSV: the journal keys, "none" when the list was read and names none of the
    ladder's journals, empty when not known (no list, or a ladder journal it was not read for)."""
    if transfers is None:
        return ""
    yes = [k for k in transfers if not journals_on_ladder or k in journals_on_ladder]
    if yes:
        return ";".join(yes)
    read_for = set(checked or transfers)
    if journals_on_ladder and any(k not in read_for for k in journals_on_ladder):
        return ""
    return "none"


def _ladder_csv(rows: list[dict[str, Any]], venues: dict[str, dict[str, Any]], priorities: list[Priority],
                feasible: dict[str, tuple[str, str]], verdicts: dict[str, tuple[str, str]],
                journals_on_ladder: Optional[list[str]], preprints: bool, ai_use: AiUse, chosen: list[str],
                source: str, designs: list[str], posted: Optional[dict[str, Any]] = None) -> None:
    """The ladder as CSV on stdout, in LADDER_COLUMNS: `rung` is the sorted order under the priorities,
    `chosen_rung` the order recorded in the record (empty for a venue it does not list)."""
    def cell(value: Any) -> str:
        return "" if value is None else str(value)

    writer = csv.DictWriter(sys.stdout, fieldnames=LADDER_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for n, v in enumerate(rows, 1):
        fit, reason = verdicts[v["key"]]
        valid, valid_reason = feasible[v["key"]]
        score, why = friction(v, ai_use)
        flags = ai_flags(v)
        speed = _first_decision(v) or {}
        fee = (v.get("publication_costs") or [{}])[0]
        rule = (v.get("open_science") or {}).get("preprints")
        writer.writerow({
            "ladder": "preprints" if preprints else "journals", "rung": n,
            "chosen_rung": chosen.index(v["key"]) + 1 if v["key"] in chosen else "", "key": v["key"], "name": _name(v),
            "fits": FIT_WORDS[fit], "fits_reason": reason,
            "validation_fits": FIT_WORDS[valid], "validation_reason": valid_reason,
            "first_decision_days": cell(speed.get("days")),
            "speed_measure": ", ".join(str(speed[k]) for k in ("metric", "statistic", "population", "period")
                                       if speed.get(k)) if speed else speed_days(v)[1],
            "speed_source": cell(speed.get("source")), "speed_checked": cell(speed.get("checked")),
            "jif": cell(v.get("jif")), "jif_year": cell(v.get("jif_year")),
            "ai_points": cell(score), "ai_tier": "" if score is None else tier(score),
            "ai_for_this_use": verdict(v, ai_use),
            "ai_red_flags": "" if score is None else sum(level == "red" for level, _ in flags.values()),
            **{f"ai_{aspect}": f"{level}: {words}" for aspect, (level, words) in flags.items()},
            "ai_reasons": " ".join(why), "ai_policy_url": cell(policy_page(v)),
            "fee_amount": cell(fee.get("amount")), "fee_currency": cell(fee.get("currency")),
            "fee_year": cell(fee.get("fee_year")), "author_cost_eur": cell(fee.get("author_cost_eur")),
            "fee_route": cell(fee.get("route")), "fee_source": cell(fee.get("source")),
            "fee_checked": cell(fee.get("checked")),
            "preprint_rule": cell(rule),
            # A server: the journals it transfers to. A journal: the authors' preprint server when it transfers here
            # directly, "none" when its checked list leaves the journal out, empty when not known.
            "transfers": (_transfers_cell(v.get("transfers"), v.get("transfers_checked"), journals_on_ladder)
                          if preprints or posted is None else
                          {"yes": posted["key"], "no": "none"}.get(from_server(v, posted), "")),
            "guidelines_url": cell(v.get("url")),
            "facts_from_record": ";".join(v.get("from_facts") or []),
            "priorities": ";".join(p.value for p in priorities),
            "priorities_source": source, "ai_use": ai_use.value, "study_designs": ";".join(designs),
        })


def _unread_reason(v: dict[str, Any], index: dict[str, dict[str, Any]]) -> Optional[str]:
    """Why the venue's author guidelines could not be read: what the record says (`not_read` in its venue_facts),
    else the policy watcher's last failed attempt on the guidelines page; None when nothing says it failed."""
    if v.get("not_read"):
        return str(v["not_read"]).rstrip(".")
    attempt = index.get(v.get("url") or "", {}).get("last_attempt")
    return plain_reason(str(attempt.get("reason") or "")).rstrip(".") or None if attempt else None


@app.command()
def common(
    keys: Annotated[list[str], typer.Argument(
        help="The venues on the ladder (keys from `rank`), journals and preprint servers alike")],
    record: Annotated[Optional[Path], typer.Option(
        help="The manuscript record (or a facts file) whose `venue_facts` fill what the catalogue lacks")] = None,
    ai_use: Annotated[Optional[AiUse], typer.Option(
        help="What AI did to the text, for what the strictest AI rule means; default: the record's ai_use, else "
             "unknown")] = None,
) -> None:
    """What every venue on a ladder asks for: what one version of the manuscript can satisfy now, where the venues
    disagree, what waits for the final code and data, and what has not been researched."""
    _, venues = load_venues()
    _, facts = load_record(record)
    venues = with_facts(venues, facts)
    use = ai_use or record_context(record)["ai_use"] or AiUse.unknown
    index = load_snapshot_index()
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
        forms = {tuple(_norm(x) for x in h) for _, h in known_h}
        # Like the lengths: one shared form only when every venue's headings are known and the same, since
        # "Adapt now" items are applied to the manuscript before the choice.
        if len(known_h) == total and len(forms) == 1:
            now.append(f"- [ ] Abstract: {form(known_h[0][1])} ({_who([_name(v) for v, _ in known_h], total)}).")
        elif len(forms) == 1:
            differ.append(f"- Abstract headings: recorded only for {_and([_name(v) for v, _ in known_h])} "
                          f"({form(known_h[0][1])}); the other venues' headings are unknown. Keep this as a "
                          "venue-specific choice until those rules are checked.")
        else:
            differ.append("- Abstract headings differ: " + "; ".join(f"{_name(v)}: {form(h)}" for v, h in known_h)
                          + "." + (" The other venues' headings are unknown." if len(known_h) < total else ""))

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

    # Sections outside the body are additions; the body's headings are one structure per venue, compared whole, and
    # adapted now only when every venue sets the same one, like the abstract headings. A part of the abstract changes
    # the abstract's form, so it is adapted now only when every venue asks for it.
    structures: dict[str, list[str]] = {}
    additions: dict[str, tuple[str, list[str]]] = {}
    abstract_parts: dict[str, tuple[str, list[str]]] = {}
    for v in vs:
        values = v.get("required_sections")
        if values is None:
            gap(v, "the required sections")
            continue
        if body := [str(x) for x in values if _body_section(x)]:
            structures[_name(v)] = body
        for x in values:
            if not _body_section(x):
                kept = abstract_parts if "in the abstract" in str(x).lower() else additions
                kept.setdefault(_norm(x), (str(x), []))[1].append(_name(v))
    if additions:
        now.append("- Sections to add (one a single venue requires costs the others little):")
        now.extend(f"  - [ ] {_sentence(text)[:-1]} ({_who(names, total)})" for text, names in additions.values())
    for text, names in abstract_parts.values():
        if len(names) == total:
            now.append(f"- [ ] {_sentence(text)[:-1]} (every venue)")
        else:
            differ.append(f"- {_sentence(text)[:-1]}, asked by {_and(names)} only: it changes the abstract's form, so "
                          "it waits for the choice.")
    forms = {tuple(_norm(x) for x in body) for body in structures.values()}
    others = [_name(v) for v in vs if _name(v) not in structures]
    if len(forms) == 1 and not others:
        now.append(f"- [ ] Body sections: {', '.join(next(iter(structures.values())))} (every venue).")
    elif len(forms) == 1:
        differ.append(f"- Body sections: {', '.join(next(iter(structures.values())))}, set by "
                      f"{_and(list(structures))}; {_and(others)} set none or are not researched for it. Keep this "
                      "as a venue-specific choice until those rules are checked.")
    elif forms:
        differ.append("- Body sections differ, and a heading names one part of the paper, so one version follows one "
                      "venue's structure: " + "; ".join(f"{n}: {', '.join(b)}" for n, b in structures.items()) + "."
                      + (f" {_and(others)} set none or are not researched for it." if others else ""))
    union("other_desk_rules", "Rules the editors check on arrival, to check against the draft", now,
          "the rules checked on arrival")

    # (when, rule) -> the rule's text, the venues stating it, whether each marks it free for the others.
    shared: dict[tuple[str, str], tuple[str, list[str], list[bool]]] = {}
    for v in vs:
        rules = v.get("submission_rules")
        if rules is None:
            gap(v, "the other rules of its author guidelines")
            continue
        for r in rules:
            entry = shared.setdefault((str(r.get("when")), _norm(r["rule"])), (r["rule"], [], []))
            entry[1].append(_name(v))
            entry[2].append(bool(r.get("free_for_others")))
    first = [(t, n, all(f)) for (w, _), (t, n, f) in shared.items() if w == "submission"]
    after = [(t, n) for (w, _), (t, n, _) in shared.items() if w == "after_review"]
    same = [f"  - [ ] {_sentence(t)[:-1]} (every venue)" for t, n, _ in first if len(n) == total]
    # A rule only some venues state goes under "Adapt now" when the catalogue marks it free for the others (an
    # addition such as alt text or a dataset citation, `free_for_others`); an order, a format or a style waits.
    free = [f"  - [ ] {_sentence(t)[:-1]} ({_and(n)})" for t, n, f in first if len(n) < total and f]
    own = [f"  - {_sentence(t)[:-1]} ({_and(n)})" for t, n, f in first if len(n) < total and not f]
    if same:
        now += ["- Rules of the author guidelines that every venue shares:", *same]
    if free:
        now += ["- Rules only some venues state that cost the others nothing (additions every version can carry):",
                *free]
    if own:
        differ += ["- Rules that only some venues state; a section order, a format or a reference style waits for the "
                   "choice:", *own]
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
        # The strictest rule and what it means for the use that happened. A statement describes that use; writing
        # passages again afterwards does not undo it, so no rewrite is suggested. Rules of equal cost are all named.
        top = max(WRITING_COST[r] for _, r in rules_known)
        strictest: dict[str, list[dict[str, Any]]] = {}
        for v, r in rules_known:
            if WRITING_COST[r] == top:
                strictest.setdefault(r, []).append(v)
        def owner(at: list[dict[str, Any]]) -> str:
            return f"{_name(at[0])}'s" if len(at) == 1 else f"the one {_and([_name(v) for v in at])} share"

        if len(strictest) == 1:
            head = "The strictest rule on the list is " + "".join(
                f"{owner(at)}: {WRITING_WORDS[r]}." for r, at in strictest.items())
        else:
            count = {2: "Two", 3: "Three", 4: "Four"}.get(len(strictest), str(len(strictest)))
            head = (f"{count} rules are equally strict on the list: "
                    + "; ".join(f"{owner(at)}, {WRITING_WORDS[r]}" for r, at in strictest.items()) + ".")
        meanings = []
        for r, at in strictest.items():
            if use != AiUse.unknown:
                meaning = verdict(at[0], use)
                whose = "it" if len(strictest) == 1 else f"{owner(at)} rule"
                meanings.append(f"For the AI use you described, {whose} means: {meaning[:1].lower() + meaning[1:]}")
        ai_lines.append(f"\n{head} " + " ".join(meanings) if meanings else f"\n{head} What it means for this paper "
                        "depends on what AI did to the text, which has not been established.")
    for v in vs:
        if not v.get("writing_help"):
            gap(v, "its AI policy")

    names = _and([_name(v) for v in vs])
    out = [f"# What the venues on this ladder ask for: {names}", "",
           "Each requirement is listed with the venues that ask for it; \"every venue\" means all of them. A venue "
           "missing from an item may simply not have been researched for it (see the last section), which is not "
           "the same as having no rule.", "",
           "## Adapt now: one version serves every venue", ""]
    out += now or ["Nothing recorded is shared by every venue."]
    out += ["", "## Choose per venue: the venues disagree", "",
            "These wait until the venue is chosen, or follow the ladder's first choice.", ""]
    out += differ or ["Nothing recorded disagrees."]
    out += ["", "## At the end, once the code, data and results are final", "",
            "Done earlier, these have to be done twice.", ""]
    out += end or ["Nothing recorded."]
    out += ["", "## AI writing rules on the list", "", *(ai_lines or ["None recorded."])]
    if gaps:
        out += ["", "## Not researched yet", "",
                "Neither the catalogue nor what was read for this manuscript covers these, so a venue listed here "
                "may still have a rule:", ""]
        for v in vs:
            if _name(v) in gaps:
                why = _unread_reason(v, index)
                out.append(f"- {_name(v)} ({v.get('url') or 'no guidelines page recorded'}): "
                           f"{_and(gaps[_name(v)])}." + (f" The page could not be read: {why}." if why else ""))
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
    for stream in (sys.stdout, sys.stderr):  # tables, quotes and names print in UTF-8 on every platform
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
