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
    "disclose": "AI help is allowed if declared, and language polish needs no declaration",
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
        return "Allowed; language polish needs no declaration." if ai_use == AiUse.polish else "Allowed; declare it."
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
    parts = [f"the abstract at most {limits['abstract_words']} words" if limits.get("abstract_words") else None,
             f"the body about {limits['body_words']} words" if limits.get("body_words") else None,
             f"papers more than {round(100 * (limits['over_limit_return'] - 1))}% over the limit are returned "
             "without review" if limits.get("over_limit_return") else None]
    parts = [x for x in parts if x]
    limit_text = f"{_and(parts)}." if parts else "not researched; read the live page."
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
        "- Abstract headings:",
        *items("abstract_headings"),
        "- Required sections (add the headings now; their final contents may wait for the last stage):",
        *items("required_sections"),
        "- Other rules the editors check on arrival:",
        *items("other_desk_rules"),
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
