# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "httpx>=0.27"]
# ///
"""Rank candidate venues by how much friction their AI policy puts on an AI-assisted manuscript, order a
shortlist into a journal ladder and a preprint ladder by the authors' priorities, print what every venue on a
ladder asks for, print one venue's requirements as a checklist, and list where named researchers publish.

The data is manuscript-integrity-check/references/venues.yaml (keep the two skills side by side), with the
user's own catalogue laid over it: `venues.yaml` beside settings.yaml (`~/.config/manuscript-skills/` on Linux,
or $MANUSCRIPT_SKILLS_CONFIG), which keeps the venue facts read in an installed plugin across updates. Every
fact carries the date it was read (its own `checked`, else `provenance.FIELD.checked`, else its entry's or its
file's `checked`), and the two catalogues and a manuscript record's `venue_facts` merge field by field, the newest
date winning. `stale` lists the facts of a ladder that are old enough to re-read; `where` names the catalogue a
run writes what it reads into, and `save` merges a facts file into the user's catalogue. The read date of each
policy page also comes from policy-snapshots/index.yaml, written by policy_watch.py. The authors' priorities,
ladders, AI use, study design and the routes that pay a fee for them (`cost_routes`) live in the manuscript's
record and are passed with --record.

    uv run --script venues.py rank                                    # all journals, least friction first
    uv run --script venues.py rank --ai-use drafting --field aging --refuse prompts --refuse ai-detector
    uv run --script venues.py rank --field bioinformatics --type software --min-jif 4
    uv run --script venues.py ladder --only KEY --only KEY --priority speed --priority reach --record REC.yaml
    uv run --script venues.py ladder --only KEY --only KEY --record REC.yaml --study-design software \
        --validation-available none --ai-use polish --min-jif 3 --budget-eur 3000
    uv run --script venues.py ladder --preprints --journal KEY --journal KEY --priority ai --record REC.yaml
    uv run --script venues.py common KEY KEY KEY --record REC.yaml    # what every venue on the ladder asks for
    uv run --script venues.py show <venue-key>                        # keys are listed by `rank`
    uv run --script venues.py stale --record REC.yaml                 # facts of the record's ladders to re-read
    uv run --script venues.py stale KEY KEY --format csv
    uv run --script venues.py where                                   # the catalogue new facts go into
    uv run --script venues.py save FACTS.yaml                         # merge read facts into the user's catalogue
    uv run --script venues.py peers "First Last" "Other Name" --since 2019

`ladder` reads from the record what the options leave out: the priorities (a default order, labelled as such,
when none are recorded), the study design (`study.designs`; one the authors have not confirmed never makes a
journal "Does not fit"), `priorities.validation_available`, `priorities.jif_floor`, `priorities.budget_eur` and
`ai_use`. An option given on the command line wins over the record.
"""

from __future__ import annotations

import csv
import importlib.util
import os
import re
import sys
import tempfile
import unicodedata
from collections import Counter
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Optional

import httpx
import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
REFERENCES = PLUGIN_ROOT / "skills" / "manuscript-integrity-check" / "references"
VENUES_YAML = REFERENCES / "venues.yaml"
SNAPSHOT_INDEX = REFERENCES / "policy-snapshots" / "index.yaml"
SETTINGS_PY = REFERENCES.parent / "scripts" / "settings.py"
STALE_AFTER_DAYS = 60  # an AI policy changes often: re-read it after two months
FACT_STALE_AFTER_DAYS = 365  # fees, review times, article types, limits, preprint rules, transfers: after a year
# Clarivate releases Journal Citation Reports each June; the end of the month is taken, so that a value read in the
# days after a release is re-read once more rather than trusted before the new figures reach the journal's pages.
JCR_RELEASE = (6, 30)
OPENALEX = "https://api.openalex.org"

# The fields of an AI policy, which go stale after STALE_AFTER_DAYS.
AI_FIELDS = {"writing_help", "exempt", "permitted_uses", "prompts", "tracking", "screening", "screening_note",
             "disclosure_places", "disclosure_fields", "disclosure_neutral", "extra_burden", "penalties",
             "image_rules", "reviewer_ai", "ai_policy_url"}
# Names, addresses and the catalogue's own notes: dated like any fact, but nothing a run re-reads for its age.
NEVER_STALE = {"name", "publisher", "url", "sources", "aliases", "openalex", "fields", "status", "fit_note",
               "not_read", "quoted_from", "jif_year"}
# Keys of a venue entry that describe the entry rather than the venue: never merged as facts and never dated.
ENTRY_KEYS = {"key", "kind", "inherits", "checked", "provenance", "from_facts"}
# Keys inside a fact's mapping that say where and when it was read, not what it says.
READ_KEYS = {"source", "checked"}
# An older way to date one field, `<field>_source` and `<field>_checked` (or `_read`) beside the field it dates; read
# into `provenance`. `transfers_checked` (a list of journals) and `not_read` (a reason) are facts of their own.
SIDECAR = re.compile(r"^(?P<field>.+)_(?P<what>source|checked|read)$")

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
                    "primary-analysis": "a primary analysis",
                    "benchmark": "a comparison with existing methods on shared data"}
DESIGN_WORDS = {"software": "software or resource", "public-data": "public-data reanalysis",
                "bioinformatics": "bioinformatics-finding", "mr": "Mendelian randomisation",
                "bibliometric": "bibliometric", "public-health-database": "public health-database",
                "health": "health-related", "clinical": "clinical-research", "human-data": "personal-data",
                "other": "other"}
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
                  "mendelian-randomization": "mr", "observational-human": "clinical", "randomized-trial": "clinical",
                  "case-report": "clinical", "prediction-model": "clinical"}
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
    first = text.split(" ", 1)[0]
    # A name spelled with an inner capital (bioRxiv, medRxiv, iScience, mRNA) keeps its case at a sentence's start.
    start = text[:1] if any(c.isupper() for c in first[1:]) else text[:1].upper()
    return start + text[1:] + ("" if text.endswith((".", "!", "?")) else ".")


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
    # What the paper reports rather than contributes, which preprint servers screen on: health-related information
    # about people (disease risk, clinical variant interpretation, risk scores for diseases), clinical research on
    # people, and data that identify a person (the authors' own released genomes included). The record gives them
    # as `study.health_information`, the study-design keys RECORD_DESIGNS maps to "clinical" and `study.human_data`.
    health = "health"
    clinical = "clinical"
    human_data = "human-data"
    other = "other"


# What the paper reports, which holds whichever kind of paper the editors take it for: these are added to each
# reading of the paper rather than judged as another reading.
TRAITS = {StudyDesign.health.value, StudyDesign.clinical.value, StudyDesign.human_data.value}


class Validation(str, Enum):
    none = "none"
    independent_cohort = "independent-cohort"
    wet_lab = "wet-lab"
    multi_database = "multi-database"
    primary_analysis = "primary-analysis"
    benchmark = "benchmark"  # a software or method paper compared with existing tools on shared data


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

def _as_date(value: Any) -> Optional[date]:
    """A date as YAML gives it, or as text that starts with one ("2026-10-27 (archived copy ...)"); else None."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    m = re.match(r"\s*(\d{4}-\d{2}-\d{2})", str(value)) if value is not None else None
    return date.fromisoformat(m.group(1)) if m else None


def _items(value: Any) -> list[dict[str, Any]]:
    """The records of a list of records (`review_speed`, `publication_costs`); [] for anything else."""
    return value if isinstance(value, list) and value and all(isinstance(i, dict) for i in value) else []


def _own_date(value: Any, entry_date: Optional[date]) -> Optional[date]:
    """The date a fact carries itself: a mapping's `checked`, or the oldest of a list's records (a record without
    one counts at the entry's date), so a list is as fresh as its oldest part."""
    if isinstance(value, dict):
        return _as_date(value.get("checked"))
    if not any("checked" in i for i in _items(value)):
        return None
    dates = [d for d in (_as_date(i.get("checked")) or entry_date for i in _items(value)) if d]
    return min(dates) if dates else None


def _own_source(value: Any) -> Optional[str]:
    if isinstance(value, dict):
        return value.get("source")
    return next((i["source"] for i in _items(value) if i.get("source")), None)


def _stamp(entry: dict[str, Any], fallback: Optional[date], layer: str) -> dict[str, Any]:
    """The entry with `provenance` giving, for every fact in it, when it was read, the page and the layer it comes
    from (`catalogue`, `user` or `record`).

    A fact's date is its own `checked` (a mapping's, or the oldest of a list's records) or `provenance.FIELD`,
    the later of the two when both are given (a re-read that found the fact unchanged moves only its date); without
    either, the entry's `checked`, else the file's (`fallback`), else none. A `provenance` date for a field the
    entry does not set is kept: it confirms the value another layer holds."""
    entry_date = _as_date(entry.get("checked")) or fallback
    given = {f: (p if isinstance(p, dict) else {"checked": p}) for f, p in (entry.get("provenance") or {}).items()}
    facts: dict[str, Any] = {}
    for field, value in entry.items():
        m = SIDECAR.match(field)
        if m and m["field"] in entry and field not in ENTRY_KEYS and not isinstance(value, (list, dict)):
            given.setdefault(m["field"], {}).setdefault("source" if m["what"] == "source" else "checked", value)
        else:
            facts[field] = value
    provenance: dict[str, dict[str, Any]] = {}
    for field, value in facts.items():
        if field in ENTRY_KEYS:
            continue
        p = given.get(field, {})
        dates = [d for d in (_own_date(value, entry_date), _as_date(p.get("checked"))) if d]
        provenance[field] = {"checked": max(dates) if dates else entry_date,
                             "source": p.get("source") or _own_source(value), "layer": layer}
    for field, p in given.items():
        if field not in provenance and _as_date(p.get("checked")):
            provenance[field] = {"checked": _as_date(p.get("checked")), "source": p.get("source"), "layer": layer}
    return {**facts, "provenance": provenance}


def _redated(value: Any, when: date) -> Any:
    """A fact confirmed unchanged on `when`: the dates it carries itself move, nothing else."""
    if isinstance(value, dict) and "checked" in value:
        return {**value, "checked": when}
    if _items(value):
        return [{**i, "checked": when} if "checked" in i else i for i in value]
    return value


def _content(value: Any) -> Any:
    """What a fact says, without where and when it was read: to tell a repeated fact from a changed one."""
    if isinstance(value, dict):
        return {k: _content(v) for k, v in value.items() if k not in READ_KEYS}
    if isinstance(value, list):
        return [_content(v) for v in value]
    return value


def _lay(old: dict[str, Any], new: dict[str, Any]) -> tuple[dict[str, Any], set[str]]:
    """The stamped entry `new` laid over the stamped entry `old`, field by field, the newer read winning; and the
    fields `new` supplied. A fact without a date loses to a dated one only when it is older: an undated fact is
    laid over the earlier layer, as before facts carried dates. On the same date the later layer wins.

    A mapping merges key by key (the winner's keys over the loser's), and its date is the winner's when the winner
    covers every key of the loser, else the older of the two, so that a key nobody re-read is not dated by a read
    that skipped it. Anything else, lists included, is replaced. A mapping with only `source` and `checked`, a
    `provenance` date without the fact, or the same fact read again confirms the value `old` holds: its date moves
    when the new read is later, the value and its layer stay, and the field is not counted as supplied."""
    out = {k: v for k, v in old.items() if k != "provenance"}
    provenance = dict(old.get("provenance") or {})
    won: set[str] = set()
    for k in ("kind", "inherits"):
        if k in new:
            out[k] = new[k]
    dates = [d for d in (_as_date(old.get("checked")), _as_date(new.get("checked"))) if d]
    if dates:
        out["checked"] = max(dates)
    for field, p in (new.get("provenance") or {}).items():
        before = provenance.get(field) or {}
        then, now = before.get("checked"), p.get("checked")
        value = new.get(field)
        confirms = field not in new or (isinstance(value, dict) and not set(value) - READ_KEYS)
        if field not in out:
            if field in new:
                out[field], provenance[field] = value, p
                won.add(field)
            continue
        newer = now is None or then is None or now >= then
        confirms = confirms or _content(_merged(out[field], value)) == _content(out[field])
        if confirms:
            if now is not None and newer:
                out[field] = _redated(out[field], now)
                provenance[field] = {**before, "checked": now, "source": p.get("source") or before.get("source")}
            continue
        winner, loser = (value, out[field]) if newer else (out[field], value)
        merged = _merged(loser, winner)
        when, src = (now, p.get("source")) if newer else (then, before.get("source"))
        if isinstance(winner, dict) and isinstance(loser, dict) and not set(loser) - READ_KEYS <= set(winner):
            when = min(d for d in (now, then) if d) if now or then else None
        if isinstance(merged, dict) and "checked" in merged and when is not None:
            merged["checked"] = when
        out[field] = merged
        provenance[field] = {**(p if newer else before), "checked": when, "source": src}
        if newer:
            won.add(field)
    return {**out, "provenance": provenance}, won


def user_catalogue() -> Path:
    """The user's own venue catalogue, beside settings.yaml (settings.py `config_dir`), where an installed plugin
    keeps the venue facts its runs read: a plugin update replaces the shipped catalogue, never this file."""
    settings = sys.modules.get("_venues_settings")
    if settings is None:
        spec = importlib.util.spec_from_file_location("_venues_settings", SETTINGS_PY)
        if spec is None or spec.loader is None:
            raise typer.BadParameter(f"cannot load {SETTINGS_PY}")
        settings = importlib.util.module_from_spec(spec)
        sys.modules["_venues_settings"] = settings
        spec.loader.exec_module(settings)
    return settings.config_dir() / "venues.yaml"


def repository_checkout(root: Optional[Path] = None) -> bool:
    """Whether this copy of the plugin is its own git checkout, whose shipped catalogue a run edits and the
    maintainers commit, rather than an installed copy in a plugin cache, which an update replaces."""
    root = PLUGIN_ROOT if root is None else root
    parts = [p.lower() for p in root.parts]
    cached = any(a == "plugins" and b == "cache" for a, b in zip(parts, parts[1:]))
    return (root / ".git").exists() and not cached


def fact_target() -> Path:
    """The catalogue a run writes the venue facts it reads into: the shipped one in the plugin's own checkout,
    else the user's."""
    return VENUES_YAML if repository_checkout() else user_catalogue()


def _read_layer(path: Path) -> Optional[dict[str, Any]]:
    """The user's catalogue, or None (with a warning) when it cannot be read: it never stops a run."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        typer.echo(f"WARNING: your venue catalogue {path} could not be read and is left out: {exc}", err=True)
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get("venues") or {}, dict):
        typer.echo(f"WARNING: your venue catalogue {path} has no `venues` mapping and is left out.", err=True)
        return None
    return raw


def merged_catalogue() -> tuple[date, dict[str, dict[str, Any]]]:
    """The shipped catalogue's date, and its entries (before inheritance) with the user's catalogue laid over them,
    entry by entry and field by field, the newest read winning. A venue only the user's catalogue knows is added
    when it has a name."""
    raw = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))
    checked = raw["checked"]
    venues = {key: _stamp(entry or {}, _as_date(checked), "catalogue") for key, entry in raw["venues"].items()}
    user = user_catalogue()
    own = _read_layer(user) if user.is_file() and user.resolve() != VENUES_YAML.resolve() else None
    for key, entry in ((own or {}).get("venues") or {}).items():
        entry = entry or {}
        if key not in venues and not entry.get("name"):
            typer.echo(f"WARNING: your venue catalogue describes {key!r}, which the plugin's catalogue does not "
                       "know; give it a name to add it. Left out.", err=True)
            continue
        stamped = _stamp(entry, _as_date(own.get("checked")), "user")
        venues[key] = _lay(venues[key], stamped)[0] if key in venues else stamped
    return checked, venues


def load_venues() -> tuple[date, dict[str, dict[str, Any]]]:
    checked, venues = merged_catalogue()
    resolved = {key: _resolve(key, venues, set()) for key in venues}
    return checked, resolved


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
    # Each field keeps the date and page of the entry it comes from: the parent's for what the journal inherits.
    provenance = {**{f: p for f, p in (base.get("provenance") or {}).items() if f in base},
                  **(entry.get("provenance") or {})}
    return {**base, **{k: v for k, v in entry.items() if k != "inherits"}, "provenance": provenance, "key": key}


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
    """When this venue's AI policy was last read: the later of the research date (the date of its writing rule,
    else the venue's own `checked`, else the file's) and the oldest watcher read among its policy pages. An
    archived copy counts at its capture date."""
    researched = ((v.get("provenance") or {}).get("writing_help") or {}).get("checked") or v.get("checked") or checked
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


def venue_rules(v: dict[str, Any]) -> tuple[str, Optional[list[dict[str, Any]]], str]:
    """The rules that decide whether a venue takes the paper at all: a preprint server's `screening_rules` (what it
    declines or sends to another server), a journal's `validation_requirements`. Returns the field, its list (None
    when nobody has read it; [] when it was read and the venue states none) and its name in words."""
    if v.get("kind") == "preprint":
        return "screening_rules", v.get("screening_rules"), "screening rules"
    return "validation_requirements", v.get("validation_requirements"), "validation requirements"


def _paper(design: str) -> str:
    return f"a {DESIGN_WORDS.get(design, design)} paper"


def _read_on(v: dict[str, Any], field: str) -> str:
    """" (read on DATE, PAGE)" for a fact, from its provenance; empty when neither is known."""
    p = (v.get("provenance") or {}).get(field) or {}
    parts = [f"read on {p['checked']}" if p.get("checked") else "", p.get("source") or ""]
    return f" ({', '.join(x for x in parts if x)})" if any(parts) else ""


def _redirect_name(rule: dict[str, Any], venues: Optional[dict[str, dict[str, Any]]]) -> str:
    key = rule.get("redirect_to")
    return str((venues or {}).get(key, {}).get("name") or "another server") if key else "another server"


def validation_fit(v: dict[str, Any], study: Optional[str] = None, available: Optional[set[str]] = None,
                   venues: Optional[dict[str, dict[str, Any]]] = None,
                   traits: Optional[list[str]] = None) -> tuple[str, str]:
    """Whether the venue takes the paper under its recorded rules only: a journal's validation requirements, a
    preprint server's screening rules. Unknown is not permission or an author veto.

    A rule list is read as the venue's complete rules for every kind of paper: `[]` (read, none stated) and a list
    none of whose rules covers this design both fit, with the page they were read on. A screening rule that
    declines the paper or sends it to another server (`outcome`, `redirect_to`) is "Depends" unless it is
    `required` and the design is stated, which makes it "Does not fit". Returns a status code (go, conditional,
    unknown, no-go) and the reason in sentences for the authors. `traits` (TRAITS: what the paper reports) count
    with the design: a rule for either applies."""
    kinds = [k for k in dict.fromkeys([study, *(traits or [])]) if k]
    excluded = [k for k in kinds if k in (v.get("excluded_study_designs") or [])]
    if excluded:
        return "no-go", f"Its recorded scope excludes {DESIGN_WORDS.get(excluded[0], excluded[0])} studies."
    field, rules, words = venue_rules(v)
    if rules is None:
        return "unknown", f"Its {words} have not been researched."
    if not rules:
        return "go", f"Its pages{_read_on(v, field)} state no {words[:-1]} for any kind of paper."
    applicable = [r for r in rules if study is None or set(kinds) & set(r.get("applies_to", []))]
    if not applicable:
        covered = _or([_paper(d) for d in dict.fromkeys(d for r in rules for d in r.get("applies_to", []))])
        return "go", (f"None of its {words}{_read_on(v, field)} applies to {_or([_paper(k) for k in kinds])}; they "
                      f"cover {covered}.")
    outcomes: list[tuple[str, str]] = []
    for rule in applicable:
        options = set(rule.get("accepted_any") or [])
        description = _sentence(rule.get("description") or "check the recorded rule")
        outcome = rule.get("outcome")
        if outcome in ("declined", "redirected") and not options:
            to = _redirect_name(rule, venues)
            certain = rule.get("strength") == "required" and study is not None
            hit = next((k for k in kinds if k in rule.get("applies_to", [])), None)
            paper = _paper(hit) if hit else "such a paper"
            action = (("It sends" if certain else "It may send") + f" {paper} to {to}" if outcome == "redirected"
                      else ("It declines" if certain else "It may decline") + f" {paper}")
            outcomes.append(("no-go" if certain else "conditional", f"{action}: {description}"))
        elif study is None or available is None or rule.get("strength") != "required" or not options:
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


def unread_rules(v: dict[str, Any]) -> list[dict[str, Any]]:
    """The rule a ladder cannot judge the venue without, when nobody has read it: a journal's validation
    requirements, a server's screening rules. In the form of `stale_facts`, so `stale` lists it with the page to
    read; a venue whose guidelines could not be read (`not_read`) is not listed again."""
    field, rules, words = venue_rules(v)
    if rules is not None or v.get("not_read"):
        return []
    return [{"field": field, "checked": None, "source": v.get("url"), "layer": None,
             "reason": f"its {words} were never read, so the ladder says \"Could not be checked\" until they are"}]


def redirects(v: dict[str, Any], designs: list[str]) -> set[str]:
    """The servers an applicable screening rule of `v` may send this paper to."""
    return {str(r["redirect_to"]) for r in v.get("screening_rules") or [] if r.get("outcome") == "redirected"
            and r.get("redirect_to") and set(designs) & set(r.get("applies_to") or [])}


def turns_away(v: dict[str, Any], designs: list[str]) -> bool:
    """Whether an applicable screening rule of `v` may decline this paper or send it elsewhere."""
    return any(r.get("outcome") in ("declined", "redirected") and set(designs) & set(r.get("applies_to") or [])
               for r in v.get("screening_rules") or [])


def bounces(rows: list[dict[str, Any]], venues: dict[str, dict[str, Any]], designs: list[str]) -> dict[str, str]:
    """For each server on a preprint ladder that may send this paper to a server which may in turn send it back or
    decline it, the sentence that says so: the paper can pass between them without being posted anywhere."""
    out: dict[str, str] = {}
    if not designs:
        return out
    for v in rows:
        for key in sorted(redirects(v, designs)):
            other = venues.get(key)
            if other is None or not turns_away(other, designs):
                continue
            back = "send it back" if v["key"] in redirects(other, designs) else "decline it"
            out[v["key"]] = (f"{_name(other)} may in turn {back}, so the paper can pass between "
                             f"{_name(v)} and {_name(other)} without being posted on either.")
    return out


def fit_text(status: str, reason: str) -> str:
    """A fit cell: the verdict in words, then why."""
    return f"{FIT_WORDS[status]}. {reason}"


def _worse(a: str, b: str) -> str:
    return max(a, b, key=FIT_ORDER.__getitem__)


def feasibility(v: dict[str, Any], designs: list[str], available: Optional[set[str]],
                confirmed: bool = True, venues: Optional[dict[str, dict[str, Any]]] = None) -> tuple[str, str]:
    """The validation fit for the paper's study designs, which `ladder` sorts by.

    A mixed study is judged under each design: when one design would rule the venue out and another would not,
    the venue depends on how its editors read the paper. What the paper reports (TRAITS: health information,
    clinical research, data on a person) holds under every reading, so its rules count with each design. A design
    the authors have not confirmed (a skill's draft in the record) can lower a venue to "Depends", never to "Does
    not fit"."""
    if not designs:
        return validation_fit(v, None, available, venues)
    traits = [d for d in designs if d in TRAITS]
    readings = [d for d in designs if d not in TRAITS] or traits[:1]
    traits = [t for t in traits if t not in readings]
    outcomes = [(d, *validation_fit(v, d, available, venues, traits)) for d in readings]
    statuses = {status for _, status, _ in outcomes}
    worst = max(statuses, key=FIT_ORDER.__getitem__)
    if len(outcomes) == 1 or len(statuses) == 1:
        status, reason = worst, " ".join(dict.fromkeys(r for _, _, r in outcomes))
    else:
        status = "conditional" if worst == "no-go" else worst
        who = "its screeners" if v.get("kind") == "preprint" else "the editors"
        reason = (f"It depends on which kind of paper {who} take this one for. "
                  + " ".join(f"As {_paper(d)}: {r}" for d, _, r in outcomes))
    if status == "no-go" and not confirmed:
        kinds = _or([_paper(d) for d in designs])
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


def jif_verified(v: dict[str, Any]) -> bool:
    """Whether the impact factor was read with its Journal Citation Reports year on the journal's or publisher's
    own page or in JCR. One recorded without a year comes from a third party (an aggregator site, a circulating
    value): it counts against an impact-factor floor, but ranks below every verified one."""
    return v.get("jif") is not None and bool(v.get("jif_year"))


def _jif(v: dict[str, Any]) -> str:
    if v.get("jif") is None:
        return "not recorded"
    if not jif_verified(v):
        return f"{v['jif']} (not verified: a third-party figure without its year)"
    return f"{v['jif']} ({v['jif_year']})"


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
    """The authors' priorities for one ladder, and what the record says about venues: the routes that pay a
    journal's fee for these authors, and the venue facts older records kept for one manuscript.

    Reads the shared manuscript record (`priorities: {journals: [speed, reach], preprints: [transfer, ai]}`, or one
    list for both ladders; `cost_routes: {key: {author_cost_eur, route, source, checked}}`, each given to its venue
    as `cost_route`; `venue_facts: {key: {...}}`, which new runs write to the catalogue instead) or a plain facts
    file with a `venues` mapping. A venue entry without a date of its own takes the record's `updated`, so a newer
    read in a catalogue wins over it."""
    if path is None:
        return [], {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    priorities = raw.get("priorities") or []
    if isinstance(priorities, dict):
        priorities = priorities.get("preprints" if preprints else "journals") or []
    updated = _as_date(raw.get("updated"))
    facts = {key: dict(entry or {}) for key, entry in (raw.get("venue_facts") or raw.get("venues") or {}).items()}
    for key, route in (raw.get("cost_routes") or {}).items():
        facts.setdefault(key, {})["cost_route"] = route
    if updated:
        for entry in facts.values():
            entry.setdefault("checked", updated)
    return [str(p) for p in priorities], facts


def record_context(path: Optional[Path]) -> dict[str, Any]:
    """What else the record says that the ladder needs, each None when the record does not say it:

    - `designs`: `study.designs` as the ladder's design keys (RECORD_DESIGNS; unknown keys count as "other"),
      with "health" added for `study.health_information: true` and "human-data" for a `study.human_data`
      classification other than `none` (what preprint servers screen on); `confirmed`: whether `study.confirmed`
      is set (the authors confirmed the design);
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
    keys = ([designs] if isinstance(designs, str) else [str(d) for d in designs]) if designs else []
    own = {d.value for d in StudyDesign}
    keys = [k if k in own else RECORD_DESIGNS.get(k, "other") for k in keys]
    if study.get("health_information") is True:
        keys.append(StudyDesign.health.value)
    if study.get("human_data") and str(study["human_data"]) != "none":
        keys.append(StudyDesign.human_data.value)
    if keys:
        out["designs"] = list(dict.fromkeys(keys))
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
    """The catalogue with the record's facts laid over it, field by field, the newest read winning (mappings such
    as `limits` and `open_science` key by key; `_lay`). A venue the catalogue lacks can be added by the facts when
    they give it a name; `from_facts` lists the fields the record supplied."""
    out = dict(venues)
    for key, given in facts.items():
        if key not in venues and not given.get("name"):
            raise typer.BadParameter(f"the facts describe {key!r}, which the catalogue does not know; give it a "
                                     "name to add it for this task")
        merged, won = _lay(venues.get(key, {}), _stamp(given, None, "record"))
        out[key] = {**merged, "key": key, "from_facts": sorted(won)}
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


def fee_routes(v: dict[str, Any]) -> tuple[Any, list[str]]:
    """What these authors would pay in euros after the agreements, funds and waivers that cover them, when the
    record's cost route (`cost_route`) or an older record's fee says so, and the routes in words: the venue's own
    (`publication_costs[0].route`) first, then the authors'."""
    c = (v.get("publication_costs") or [{}])[0]
    own = v.get("cost_route") or {}
    cost = own.get("author_cost_eur", c.get("author_cost_eur"))
    routes = [str(r) for r in (c.get("route"), own.get("route")) if r]
    return cost, list(dict.fromkeys(routes))


def fee_eur(v: dict[str, Any]) -> tuple[Optional[float], str]:
    """What the authors would pay in euros, and the fee in words. `author_cost_eur` (in the record's cost route) is
    the amount left to the authors after an agreement, discount, fund or waiver they can use; without it a fee in
    euros is compared as listed, and a fee in another currency is shown but not compared."""
    costs = v.get("publication_costs") or []
    if not costs and not v.get("cost_route"):
        return None, "not known"
    c = costs[0] if costs else {}
    amount, currency = c.get("amount"), str(c.get("currency") or "")
    shown = (f"{amount} {currency}".strip() + (f" ({c['fee_year']})" if c.get("fee_year") else "")
             if amount is not None else "fee not recorded")
    cost, routes = fee_routes(v)
    if routes:
        shown += "; " + "; ".join(routes)
    if cost is not None:
        return float(cost), f"{shown}; the authors would pay about {cost} EUR"
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
    step a venue whose rules nobody read ("Could not be checked") sorts below every venue whose rules were read and
    only "Does not fit" below it (FIT_ORDER): not knowing whether the paper fits is a reason to try a venue later,
    never earlier. An unknown value sorts below every known one at its
    step, and at the reach step an unverified impact factor (`jif_verified`) sorts below every verified one and
    above an unknown one; a tie passes to the next priority; the name breaks the last tie."""
    key: list[Any] = [FIT_ORDER[feasible]]
    for p in priorities:
        value = priority_value(v, p, journals_on_ladder, ai_use, server)
        low = p == Priority.reach and not jif_verified(v)
        key.append((2, 0.0) if value is None else (1 if low else 0, value))
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


# ------------------------------------------------------------------------------------------------ staleness

def jcr_release(on: date) -> date:
    """The latest release of Journal Citation Reports on `on` (each June, taken at JCR_RELEASE)."""
    this_year = date(on.year, *JCR_RELEASE)
    return this_year if on >= this_year else date(on.year - 1, *JCR_RELEASE)


def stale_facts(v: dict[str, Any], on: date) -> list[dict[str, Any]]:
    """The facts recorded for a venue that are old enough to re-read on `on`, each with its field, the date it was
    read, its page, the layer it comes from and why it is due: an AI-policy field after STALE_AFTER_DAYS, an impact
    factor (verified or not) read before the latest Journal Citation Reports release, anything else after
    FACT_STALE_AFTER_DAYS. A field nobody recorded is not stale: it is
    unresearched (`common` lists those)."""
    provenance = v.get("provenance") or {}
    due = []
    for field in v:
        p = provenance.get(field)
        if field in ENTRY_KEYS or field in NEVER_STALE or p is None:
            continue
        when = p.get("checked")
        if field == "jif":
            release = jcr_release(on)
            if when is not None and when >= release:
                continue
            reason = f"Journal Citation Reports released new impact factors in June {release.year}" + (
                "" if jif_verified(v) else "; this one is a third-party figure, so look for it on the journal's page")
        else:
            limit = STALE_AFTER_DAYS if field in AI_FIELDS else FACT_STALE_AFTER_DAYS
            if when is not None and (on - when).days <= limit:
                continue
            kind = "an AI-policy fact" if field in AI_FIELDS else "this kind of fact"
            reason = (f"read {(on - when).days} days ago, and {kind} is re-read after {limit}" if when
                      else "no date is recorded")
        page = p.get("source") or (policy_page(v) if field in AI_FIELDS else v.get("url"))
        due.append({"field": field, "checked": when, "source": page, "layer": p.get("layer"), "reason": reason})
    return due


STALE_COLUMNS = ["key", "name", "field", "checked", "source", "layer", "reason"]


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
             "public-health-database, other; and what the paper reports, which preprint servers screen on: "
             "health (health-related information about people), clinical (clinical research on people), human-data "
             "(data that identify a person, the authors' own released genomes included)")] = None,
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
        fit, fit_reason = validation_fit(v, study_design.value if study_design else None, available, venues)
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
                  "screening_rules": "What it declines or sends to another server",
                  "excluded_study_designs": "Study designs it excludes",
                  "open_science": "Open science and open source", "editorial_profile": "Editorial profile",
                  "review_speed": "Review times", "publication_costs": "Publication costs",
                  "reviewer_form": "What the journal asks its referees", "figure_rules": "Figure rules"}
PROFILE_ITEM = {"validation_requirements": "Rule", "screening_rules": "Rule", "review_speed": "Measure",
                "publication_costs": "Fee"}
KEY_WORDS = {"applies_to": "applies to", "accepted_any": "accepted alternatives (any one is enough)",
             "redirect_to": "sends it to",
             "description": "condition", "checked": "read on", "evidence_kind": "kind of evidence",
             "fee_year": "fee year", "source_code": "source code", "software_licence": "software licence",
             "data_and_artifacts": "data and artifacts", "open_peer_review": "open peer review",
             "recommendations": "recommendation options", "widths_mm": "widths (mm)",
             "max_height_mm": "greatest height (mm)", "min_text_pt": "smallest text at print size (pt)",
             "max_text_pt": "largest text at print size (pt)", "dpi": "resolution (dpi)",
             "display_items": "display items at most", "alt_text": "alt text required"}
# The page's own words, each printed as a quoted bullet.
QUOTED_KEYS = {"questions", "recommendations", "guidance"}


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
            if k in QUOTED_KEYS and isinstance(sub, list):
                lines += [f"{pad}- {label}:", *[f"{pad}  - “{q}”" for q in sub]]
            elif isinstance(sub, dict) or (isinstance(sub, list) and not _flat(sub)):
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
        if field == "review_speed" and value == []:
            read = ((v.get("provenance") or {}).get(field) or {}).get("checked")
            out.append(f"- **{label}:** the venue publishes none" + (f" (looked for on {read})." if read else "."))
        elif value is None or _flat(value):
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
    study_design: Annotated[Optional[list[StudyDesign]], typer.Option(
        help="What the paper contributes, for the validation rules (see `rank --help`), and what it reports, for "
             "the preprint servers' screening rules (health, clinical, human-data); repeatable; default: the "
             "record's study.designs, health_information and human_data")] = None,
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
    designs = [d.value for d in study_design] if study_design else (context["designs"] or [])
    confirmed = bool(study_design) or context["confirmed"]
    use = ai_use or context["ai_use"] or AiUse.unknown
    floor = min_jif if min_jif is not None else (None if preprints else context["jif_floor"])
    budget = budget_eur if budget_eur is not None else context["budget_eur"]
    kept, left_out = _selected(venues, preprints=preprints, only=only, field=field, article_type=article_type,
                               software=software, oa=oa, min_jif=floor, refused=set(refuse or []))
    feasible = {key: feasibility(v, designs, available, confirmed, venues) for key, v in kept.items()}
    if preprints:
        # A server that may send the paper to one that may send it back: say so on its rung, as a condition, with
        # the servers on the ladder that would take the paper as it is.
        as_is = [_name(v) for v in kept.values() if feasible[v["key"]][0] == "go"]
        for key, sentence in bounces(list(kept.values()), venues, designs).items():
            status, reason = feasible[key]
            if as_is:
                sentence += f" {_and(as_is)} {'has' if len(as_is) == 1 else 'have'} no screening rule against it."
            feasible[key] = (_worse(status, "conditional") if status != "unknown" else status, f"{reason} {sentence}")
    rows = sorted(kept.values(), key=lambda v: ladder_order(v, priorities, feasible[v["key"]][0], journal, use, posted))
    unread = [v for v in rows if unread_rules(v)]
    verdicts = {v["key"]: overall_fit(v, feasible[v["key"]], use, budget) for v in rows}
    notes = _ladder_notes(default_order, priorities, preprints, designs, confirmed, bool(study_design),
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
        if unread:
            typer.echo(_unread_note(unread), err=True)
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
    if Priority.reach in priorities:
        unverified = [_name(v) for v in rows if v.get("jif") is not None and not jif_verified(v)]
        if unverified:
            typer.echo(f"\nImpact factors not verified on the journal's own pages (third-party figures without their "
                       f"year), so placed below the verified ones at the step for {PRIORITY_WORDS['reach']}: "
                       f"{_and(unverified)}.")
    for p in priorities:
        missing = [_name(v) for v in rows if priority_value(v, p, journal, use, posted) is None]
        if missing:
            words = JOURNAL_TRANSFER_WORDS if p == Priority.transfer and posted else PRIORITY_WORDS[p.value]
            typer.echo(f"\nNot known, so placed below the known values at the step for {words}: {_and(missing)}.")
    from_task = [f"{_name(v)} ({', '.join(f.replace('_', ' ') for f in v['from_facts'] if f not in TASK_ONLY)})"
                 for v in rows if set(v.get("from_facts") or []) - TASK_ONLY]
    if from_task:
        typer.echo("\nFacts read for this manuscript and taken from its record: " + "; ".join(from_task) + ".")
    if unread:
        typer.echo("\n" + _unread_note(unread))
    due = [v for v in rows if stale_facts(v, date.today())]
    if due:
        keys = " ".join(v["key"] for v in due)
        typer.echo(f"\nSome recorded facts about {_and([_name(v) for v in due])} are old enough to re-read before "
                   f"they decide anything: `venues.py stale {keys}` lists each one with its page.")
    if left_out:
        typer.echo("\nLeft out of the venues you listed: " + "; ".join(left_out) + ".")
    glossary = abbreviations("\n".join(printed + left_out))
    if glossary:
        typer.echo("\n" + glossary)


def _unread_note(unread: list[dict[str, Any]]) -> str:
    """The ladder's last word on venues whose deciding rules nobody has read: the lookup is not finished."""
    keys = " ".join(v["key"] for v in unread)
    kinds = _and(sorted({venue_rules(v)[2] for v in unread}))
    return (f"Not finished: the {kinds} of {_and([_name(v) for v in unread])} have never been read, so they show "
            f"\"Could not be checked\". Read them before handing the ladder over (`venues.py stale {keys}` names "
            "each page), write them into the catalogue, `[]` when the pages state none, or `not_read` with the "
            "reason when a page cannot be read, and run the ladder again.")


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
    rules = "screening rules (what each server declines or sends to another server)" if preprints else \
        "validation rules"
    notes.append(f"Ordered by whether the paper fits each venue's recorded {rules} (\"Fits\", then \"Depends\", "
                 f"then \"Could not be checked\", then \"Does not fit\"), then by {steps}. A value "
                 "that is not known sorts below every known value at its step, and a tie passes to the next step. A "
                 "position is an order of preference under these priorities, not a chance of acceptance"
                 + ("; the speed compared is days to a first decision, which for most journals includes desk "
                    "rejections" if Priority.speed in priorities and not preprints else "") + ". AI-policy work is the paperwork a venue's AI policy "
                 "asks of the authors, from light to severe, and a writing rule that forbids what AI already did to "
                 "the text counts as severe; it is not the chance of rejection.")
    assumed = []
    if designs:
        kinds = _and([_paper(d) for d in designs])
        if design_given:
            assumed.append(f"The {rules} are read for {kinds}.")
        elif confirmed:
            assumed.append(f"The {rules} are read for {kinds}, the study design the authors confirmed in "
                           "the manuscript record.")
        else:
            assumed.append(f"The {rules} are read for {kinds}, the study design in the manuscript record, "
                           "which the authors have not confirmed yet; until they do, a rule it falls under can make "
                           "a venue \"Depends\", never \"Does not fit\".")
    else:
        assumed.append(f"No study design is recorded, so each of the {rules} is shown as a condition to check.")
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
            "fee_year": cell(fee.get("fee_year")), "author_cost_eur": cell(fee_routes(v)[0]),
            "fee_route": "; ".join(fee_routes(v)[1]), "fee_source": cell(fee.get("source")),
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
        if unread_rules(v):
            gap(v, f"its {venue_rules(v)[2]}")

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


@app.command()
def stale(
    keys: Annotated[Optional[list[str]], typer.Argument(
        help="The venues to check (keys from `rank`); default: both ladders of the record")] = None,
    record: Annotated[Optional[Path], typer.Option(
        help="The manuscript record: its `ladders` when no keys are given, and its venue facts and cost routes, "
             "which count with their own dates")] = None,
    every: Annotated[bool, typer.Option("--all", help="Every journal and preprint server in the catalogue")] = False,
    on: Annotated[Optional[str], typer.Option(help="Judge the age of each fact on this date (YYYY-MM-DD); "
                                                   "default: today")] = None,
    output: Annotated[OutputFormat, typer.Option(
        "--format", help="md: grouped by the page to re-read; csv: one row per fact, in STALE_COLUMNS")] = OutputFormat.md,
) -> None:
    """What to read for a ladder's venues, with the page each is on: the validation requirements or screening rules
    nobody has read, and the recorded facts old enough to re-read. Only these need reading."""
    day = _as_date(on) if on else date.today()
    if day is None:
        raise typer.BadParameter("--on takes a date, YYYY-MM-DD")
    _, venues = load_venues()
    venues = with_facts(venues, load_record(record)[1])
    if every:
        chosen = [k for k, v in venues.items() if v.get("kind") != "publisher"]
    else:
        chosen = list(keys or []) or [*recorded_ladder(record, False), *recorded_ladder(record, True)]
    if not chosen:
        raise typer.BadParameter("name the venues, give a record with `ladders`, or pass --all")
    unknown = [k for k in chosen if k not in venues]
    if unknown:
        raise typer.BadParameter(f"unknown venue keys: {', '.join(unknown)}")
    found = {k: unread_rules(venues[k]) + stale_facts(venues[k], day) for k in dict.fromkeys(chosen)}
    if output == OutputFormat.csv:
        writer = csv.DictWriter(sys.stdout, fieldnames=STALE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for k, due in found.items():
            for d in due:
                writer.writerow({"key": k, "name": _name(venues[k]),
                                 **{c: "" if d.get(c) is None else d[c] for c in STALE_COLUMNS[2:]}})
        return
    target = fact_target()
    out = ["# Venue facts to read", "",
           f"Judged on {day}. A journal's validation requirements and a preprint server's screening rules are read "
           "when nobody has read them yet: a ladder cannot say whether the paper fits without them. An AI-policy fact "
           f"is re-read after {STALE_AFTER_DAYS} days, an impact factor once "
           "Journal Citation Reports has released newer figures (each June), and every other fact after "
           f"{FACT_STALE_AFTER_DAYS} days. Only these need reading: a fact found unchanged keeps its value and takes "
           "the new date; a changed one is replaced by the new value with the new date, each with the page it was "
           f"read on. Write them into {target}.", ""]
    for k, due in found.items():
        if not due:
            continue
        out += [f"## {_name(venues[k])} (`{k}`)", ""]
        pages: dict[tuple[Any, Any, str], list[str]] = {}
        for d in due:
            pages.setdefault((d["source"], d["checked"], d["reason"]), []).append(d["field"])
        for (page, when, reason), fields in pages.items():
            read = f"read on {when}" if when else ("never read" if reason.startswith("its ") else "no date")
            out.append(f"- {_and([f'`{f}`' for f in fields])}: {read}, from "
                       f"{page or 'no page recorded'}; {reason}.")
        out.append("")
    fresh = [_name(venues[k]) for k, due in found.items() if not due]
    if fresh and len(fresh) < len(found):
        out.append(f"Nothing to re-read for {_and(fresh)}.")
    elif fresh:
        out.append("Every recorded fact about these venues is within its re-check period.")
    typer.echo("\n".join(out).rstrip())


@app.command()
def where() -> None:
    """The catalogue a run writes the venue facts it reads into, and why that one."""
    target = fact_target()
    typer.echo(str(target))
    if target == VENUES_YAML:
        typer.echo("This is the plugin's own repository checkout: write venue facts into its shipped catalogue, "
                   "above, in place (keep its comments), each with `source` and `checked`.")
    else:
        typer.echo("This is an installed copy of the plugin, which an update replaces: save venue facts to your own "
                   "catalogue, above, with `venues.py save FACTS.yaml` (or edit it), each with `source` and "
                   "`checked`. venues.py lays it over the shipped catalogue, the newest date winning.")


def _plain(entry: dict[str, Any]) -> dict[str, Any]:
    """A stamped entry as the user's catalogue keeps it: `provenance` with each fact's date and page."""
    provenance = {f: {k: p[k] for k in ("checked", "source") if p.get(k) is not None}
                  for f, p in (entry.get("provenance") or {}).items()}
    return {**{k: v for k, v in entry.items() if k != "provenance"}, "provenance": provenance}


USER_HEADER = ("# Venue facts read by manuscript-skills runs in an installed plugin, which venues.py lays over the\n"
               "# plugin's catalogue field by field, the newest date winning. Written by `venues.py save`; plugin\n"
               "# updates never replace it. Each fact's date and page are under the venue's `provenance`.\n")


@app.command()
def save(
    facts_file: Annotated[Path, typer.Argument(
        help="A facts file in the catalogue's form: `venues: {KEY: {FIELD: VALUE, ..., provenance: {FIELD: "
             "{source, checked}}}}`, or a record's `venue_facts`")],
    user: Annotated[bool, typer.Option(
        help="Save to your own catalogue even in the plugin's repository checkout")] = False,
) -> None:
    """Merge the venue facts a run read into the user's catalogue, field by field, the newest date winning: a fact
    found unchanged moves only its date, a changed one replaces the old value."""
    target = user_catalogue()
    if repository_checkout() and not user:
        typer.echo(f"This is the plugin's repository checkout: venue facts go into {VENUES_YAML}, edited in place so "
                   f"its comments stay. Pass --user to save them to {target} instead.", err=True)
        raise typer.Exit(2)
    raw = yaml.safe_load(facts_file.read_text(encoding="utf-8")) or {}
    given = raw.get("venues") or raw.get("venue_facts") or {}
    file_date = _as_date(raw.get("checked"))
    stamped = {key: _stamp(entry or {}, file_date, "user") for key, entry in given.items()}
    undated = [f"{key}.{f}" for key, e in stamped.items() for f, p in e["provenance"].items() if p["checked"] is None]
    if undated:
        raise typer.BadParameter("every fact needs the date it was read (`checked`, in the fact, its "
                                 f"`provenance` or its venue); these have none: {', '.join(undated)}")
    current = (_read_layer(target) if target.is_file() else {}) or {}
    if target.is_file() and not current:
        raise typer.BadParameter(f"{target} cannot be read; fix or move it first, it is never overwritten")
    mine = current.get("venues") or {}
    _, known = merged_catalogue()
    for key, entry in stamped.items():
        if key not in known and key not in mine and not entry.get("name"):
            raise typer.BadParameter(f"the facts describe {key!r}, which no catalogue knows; give it a name")
        old = _stamp(mine[key] or {}, _as_date(current.get("checked")), "user") if key in mine else {}
        mine[key] = _plain(_lay(old, entry)[0])
    target.parent.mkdir(parents=True, exist_ok=True)
    body = USER_HEADER + yaml.safe_dump({**current, "venues": mine}, sort_keys=False, allow_unicode=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, suffix=".tmp", delete=False) as tmp:
        tmp.write(body)
    os.replace(tmp.name, target)
    count = sum(len(e["provenance"]) for e in stamped.values())
    typer.echo(f"Saved {count} facts about {len(stamped)} venues to {target}.")


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
