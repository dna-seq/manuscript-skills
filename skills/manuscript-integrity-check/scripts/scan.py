# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "httpx>=0.27", "pydantic>=2.6", "pyyaml>=6"]
# ///
"""Mechanical pre-submission scan of a manuscript (Markdown, LaTeX or plain text).

Finds what desk screeners find mechanically: chatbot leftovers, placeholders, missing declarations,
undisclosed AI use, unverifiable or mismatched references, overclaiming and LLM-overused vocabulary.
It reports; it never rewrites. The judgement calls (is this claim calibrated? is the denominator
reported?) are the skill's job, not this script's.

    uv run --script scan.py PAPER.md                      # offline checks only
    uv run --script scan.py PAPER.md --online             # also resolve DOIs / PMIDs / arXiv ids
    uv run --script scan.py PAPER.md --online --json out.json --md out.md
    uv run --script scan.py PAPER.md --references-only --online  # focused citation check
    uv run --script scan.py PAPER.md --final              # about to submit: end-stage items count too

The Markdown report groups findings by when the authors can act on them (fix now, then the writing, once the journal
is chosen, before submission) and quotes each one in its section. A draft's readiness and the exit code count only
the current work unless --final says the authors are about to submit. The JSON keeps every field, line numbers and
status codes included, for other tools.
"""

from __future__ import annotations

import csv
import fnmatch
import html
import ipaddress
import json
import re
import subprocess
import time
import tomllib
import unicodedata
import urllib.parse
from collections import Counter
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import httpx
import typer
import yaml
from pydantic import BaseModel, PrivateAttr

app = typer.Typer(add_completion=False, no_args_is_help=True)

USER_AGENT = "manuscript-integrity-check/1.0 (pre-submission self-check; mailto:none@example.invalid)"


class Severity(str, Enum):
    blocker = "blocker"  # a desk-reject trigger by itself
    major = "major"  # an editor or reviewer will object
    minor = "minor"  # style or calibration
    info = "info"  # needs a human look, may be fine


class Stage(str, Enum):
    """When the authors can act on a finding (references/author-priorities.md, "Order the work")."""
    now = "now"  # the science and the evidence
    writing = "writing"
    journal = "journal"  # once the journal is chosen
    final = "final"  # before submission, once the code, data and results are final


class Finding(BaseModel):
    check: str
    severity: Severity
    line: Optional[int] = None
    excerpt: str = ""
    message: str
    suggestion: str = ""
    section: Optional[str] = None  # the heading the line falls under, or the bibliography file and entry
    quote: str = ""  # the line or entry as written, shortened with [...] around the problem
    quote_span: Optional[tuple[int, int]] = None  # where the problem sits inside `quote`
    stage: str = ""  # a Stage value; filled from the check when not set where the finding is made
    why: str = ""  # why it matters for the paper, in a sentence for the authors
    # Set for a finding about a bibliography entry: `quote` is then the entry, not a line of the manuscript.
    _entry: bool = PrivateAttr(default=False)


class PublishedVersion(BaseModel):
    """Where a cited preprint was published, and how that record compares with the preprint's."""
    doi: Optional[str] = None
    title: Optional[str] = None
    venue: Optional[str] = None
    year: Optional[str] = None
    # crossref:is-preprint-of | biorxiv:published | medrxiv:published | arxiv:doi | arxiv:journal_ref, recorded by the
    # registries; arxiv:comment | crossref:title-search, candidates found by this script for the authors to confirm
    source: str = ""
    comment: Optional[str] = None  # the arXiv comment that names a venue ("Accepted by EMNLP 2023")
    title_similarity: Optional[float] = None
    shared_authors: Optional[bool] = None
    retraction: Optional[str] = None  # of the published version, when its record was read
    metadata_checked: bool = False


class Reference(BaseModel):
    line: int
    text: str
    doi: Optional[str] = None
    pmid: Optional[str] = None
    arxiv: Optional[str] = None
    url: Optional[str] = None  # a BibTeX url field that is not a DOI, arXiv or PubMed link
    other_ids: list[str] = []  # further identifiers the entry carries ("doi:10...", "pmid:123"), each checked too
    cited_title: Optional[str] = None  # the title as cited, when the entry has a title field (BibTeX)
    # Strictly normalised cited title against the record's: same | differs (a fuzzy match that is not exact) |
    # no_title (a BibTeX entry with no title field) | not_compared
    title_check: str = "not_compared"
    other_id_checks: list[dict[str, Optional[str]]] = []  # one per other_ids: id, state, title, why, same_work
    url_status: Optional[str] = None  # the url field's answer: "ok HTTP 200", "dead HTTP 404", "blocked ...", "unknown ..."
    resolved_title: Optional[str] = None
    resolved_year: Optional[str] = None
    resolved_first_author: Optional[str] = None
    first_author_found: Optional[bool] = None
    title_similarity: Optional[float] = None
    # not_checked | resolved | mismatch | unresolved | retracted | concern | no_identifier | lookup_failed
    status: str = "not_checked"
    # Retraction checking with its source, so that an unchecked reference never reads as clean:
    # retracted | concern | none_found (the registries asked hold no notice) | not_checked
    retraction: str = "not_checked"
    retraction_source: Optional[str] = None  # e.g. "crossref (retraction-watch)", "crossref+europepmc", "pubmed"
    retraction_notice: Optional[str] = None
    is_preprint: Optional[bool] = None
    published_version: Optional[PublishedVersion] = None
    withdrawn: Optional[bool] = None  # None: not checked (arXiv and bioRxiv/medRxiv expose withdrawals)
    withdrawn_source: Optional[str] = None
    resolved_authors: list[str] = []  # "Family, Given" as the record lists them
    author_check: str = "not_compared"  # consistent | differs | not_compared
    author_notes: list[str] = []
    author_severity: Optional[str] = None  # minor | info, when author_check is "differs"
    lookup_notes: list[str] = []
    # For an identifier that does not resolve: the record a Crossref title search found (also in lookup_notes).
    _title_match: Optional[dict] = PrivateAttr(default=None)
    # For an entry read from a BibTeX file: the file's name and the entry's key (`line` is then the file's line).
    _bib_file: Optional[str] = PrivateAttr(default=None)
    _bib_key: Optional[str] = PrivateAttr(default=None)
    # For an entry of a reference list in the manuscript: the section its list sits in ("References").
    _list: Optional[str] = PrivateAttr(default=None)


class InlineId(BaseModel):
    """An identifier written in the text (doi:, a doi.org or arXiv link, PMID, arXiv:, a bare URL), outside the
    reference list: resolved online, its title shown for a person to read; no match is attempted."""
    line: int
    kind: str  # doi | pmid | arxiv | url
    id: str
    section: str = ""  # the heading the line falls under
    state: str = "not_checked"  # ok | dead | blocked | unknown | not_checked
    title: Optional[str] = None
    detail: str = ""


class ReferenceReport(BaseModel):
    path: str
    online: bool
    findings: list[Finding]
    references: list[Reference]
    inline_ids: list[InlineId] = []


class Report(BaseModel):
    path: str
    words: int
    abstract_words: Optional[int] = None
    findings: list[Finding]
    references: list[Reference]
    vocabulary_per_1000_words: dict[str, float]
    top_vocabulary: list[tuple[str, int]]
    ing_tails: int = 0
    final: bool = False  # the authors are about to submit: final-stage findings count in the verdict
    inline_ids: list[InlineId] = []


# --------------------------------------------------------------------------------------------------
# Patterns. Each list names its source in references/screening-signals.md; keep them in sync.
# --------------------------------------------------------------------------------------------------

# Text an LLM chat interface emits that ended up in published papers (Retraction Watch and
# Problematic Paper Screener collections). One hit is a desk reject.
CHATBOT_LEFTOVERS = [
    r"as an ai language model",
    r"as a large language model",
    r"i am an ai",
    r"i (?:cannot|can't|am unable to) (?:browse|access|provide)",
    r"as of my (?:last )?knowledge (?:update|cutoff)",
    r"regenerate response",
    r"certainly[,!] here (?:is|are)",
    r"here is (?:a|the) (?:revised|rewritten|possible|draft|summary)",
    r"i hope this helps",
    r"let me know if you (?:need|would like|want)",
    r"feel free to (?:adjust|modify|ask)",
    r"\[insert [^\]]+\]",
    r"\[(?:your|author) name\]",
    r"in this (?:hypothetical|fictional) (?:scenario|example)",
    # The residue arXiv's CS moderators cite as grounds for a one-year ban (May 2026).
    r"would you like me to",
    r"here is a \d+[- ]word",
    r"(?:data|numbers|values) (?:in this table )?(?:is|are) illustrative",
    r"fill (?:it|this|them) in with the (?:real|actual)",
    r"replace (?:with|these with) (?:the )?(?:real|actual) (?:data|numbers|values)",
]

PLACEHOLDERS = [
    r"\bTODO\b",
    r"\bTBD\b",
    r"\bFIXME\b",
    r"\bXXX\b",
    r"<<\s*REPLACE\s*>>",
    r"\bAUTHOR TODO\b",
    r"\(\?\?\)|\?\?",
    r"\bto be (?:finalized|added|confirmed|completed)\b",
    r"\bFigure\s+X\b|\bTable\s+X\b",
    r"lorem ipsum",
]
# A placeholder for a missing citation marks a claim without its source: work for now, not for the final pass.
CITATION_PLACEHOLDERS = [r"\[citation needed\]", r"\[ref(?:erence)?s?\??\]"]

# An author-facing fill-in in square brackets: "[URL of the output VCF]", "[reference number]", "[date]",
# "[reason, and whether ...]", "[Calibration genome: whose genome it is ...]", "[   ]". The bracket is not one
# when a word, backslash command, brace, "]", "!" or "^" comes right before it (an index, a LaTeX optional
# argument, a link's second half, an image), or "(", "[", "{" or ":" right after it (a link or its definition).
BRACKET = re.compile(r"(?<![\w\\\]}!^])\[([^\[\]\n]{0,200})\](?![(\[{:])")
# The fill-in's first or last word says what is to be filled. A bracket with a digit in it is a citation, a grant
# number or a reference-format note ("[version 2; peer review: 2 approved]", "[cited 2024 Oct 10]"), and a tag
# such as "[dataset]", "[software]" or "[Internet]" names no such word, so neither is one.
FILL_IN_WORD = (r"(?:url|link|doi|pmid|accession|number|date|year|name|names|initials|reason|details|insert|add|"
                r"fill|placeholder|tbc|tba|todo|tbd|author|authors|affiliation|e-?mail|address|grant|value|values|"
                r"citation|page|pages|here)")
FILL_IN = re.compile(rf"^{FILL_IN_WORD}\b|\b{FILL_IN_WORD}$", re.IGNORECASE)
FILL_IN_ORDER = re.compile(r"^(?:insert|add|fill in|placeholder|todo|tbd|tbc|tba)\b", re.IGNORECASE)  # "[Insert Fig 2]"
COLON_INSTRUCTION = re.compile(r"^[A-Z][\w'’ -]{1,40}:\s+\S")  # "[Calibration genome: whose genome it is ...]"
TASK_BOX = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+\[[ xX]?\]")
TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$")
FENCE = re.compile(r"^\s{0,3}(?:`{3,}|~{3,})")


def _bracket_fill_ins(line: str) -> list[tuple[int, int]]:
    """Spans of the square-bracket fill-ins on one line (see BRACKET and FILL_IN)."""
    code = [m.span() for m in re.finditer(r"`[^`]*`", line)]
    out = []
    for m in BRACKET.finditer(line):
        body = m.group(1)
        if any(a <= m.start() < b for a, b in code) or re.search(r"\\[A-Za-z]+\*?\s*$", line[:m.start()]):
            continue
        if not body.strip():
            if not body or TASK_BOX.match(line) and line.index("[") == m.start() or TABLE_LINE.match(line):
                continue
            out.append(m.span())
            continue
        text = body.strip()
        if FILL_IN_ORDER.match(text) or any(re.search(p, text) for p in PLACEHOLDERS):
            out.append(m.span())
            continue
        if re.search(r"\d", text) or text[0] in "^@-" or re.fullmatch(r"(?:\.\s*){3}|…|sic", text, re.IGNORECASE):
            continue
        if FILL_IN.search(text) or COLON_INSTRUCTION.match(text):
            out.append(m.span())
    return out


def _placeholder_findings(lines: list[str], why: str) -> list[Finding]:
    """One finding per line naming every placeholder on it, in the order they stand: the PLACEHOLDERS words and the
    bracketed fill-ins. A match inside another ("TODO" in "AUTHOR TODO", "to be added" inside a bracket) is named
    once."""
    compiled = [re.compile(p) for p in PLACEHOLDERS]
    out: list[Finding] = []
    in_fence = False
    for i, line in enumerate(lines, start=1):
        spans = [m.span() for rx in compiled for m in rx.finditer(line)]
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            spans += _bracket_fill_ins(line)
        spans = sorted({s for s in spans if not any(o != s and o[0] <= s[0] and s[1] <= o[1] for o in spans)})
        if not spans:
            continue
        names = [line[a:b].strip() for a, b in spans]
        shown = [n if len(n) <= 90 else n[:85].rstrip() + "…]" for n in names]
        quoted = _names_listed([f"'{n}'" for n in shown], most=10)
        message = (f"The placeholder {quoted} is still in the text." if len(spans) == 1 else
                   f"The placeholders {quoted} are still in the text.")
        a, b = spans[0]
        out.append(_with_quote(Finding(check="placeholder", severity=Severity.major, line=i,
                                       excerpt=_excerpt(line, a, b), message=message,
                                       suggestion="Resolve or remove placeholders before the files are uploaded.",
                                       why=why), line, a, b))
    return out

# Overused vocabulary, by source. Corpus studies cannot identify an individual paper (Kobak; Liang), and
# word lists also catch non-native writers and permitted language polishing, so this is a density report,
# never a verdict. See references/screening-signals.md §2.
KOBAK_CSV = Path(__file__).resolve().parent.parent / "references" / "kobak_2024_style_words.csv"
KOBAK_MIN_RATIO = 2.0  # the 182 style words whose 2024 frequency was at least twice the counterfactual


def _kobak_words() -> set[str]:
    with KOBAK_CSV.open(encoding="utf-8") as fh:
        return {row["word"] for row in csv.DictReader(fh) if float(row["r"]) >= KOBAK_MIN_RATIO}


# Juzek & Ward, COLING 2025, Table 3 (the 21 focal words).
JUZEK_WARD = {
    "advancements", "aligns", "boasts", "comprehending", "delve", "delves", "delved", "delving", "emphasizing",
    "garnered", "groundbreaking", "intricate", "intricacies", "realm", "showcases", "showcasing", "surpasses",
    "surpassing", "underscore", "underscores", "underscoring",
}
# Wikipedia "Signs of AI writing", words-to-watch box (rev. 1380310647, 2026-10-15). Community-curated.
WIKIPEDIA_AIVOCAB = {
    "bolstered", "crucial", "delve", "emphasizing", "enduring", "enhance", "fostering", "garner", "highlight",
    "interplay", "intricate", "intricacies", "landscape", "meticulous", "meticulously", "pivotal", "robust",
    "showcase", "tapestry", "testament", "underscore", "valuable", "vibrant",
}
VOCAB_SOURCES: dict[str, set[str]] = {}  # filled in scan(); the CSV is read once

# Phrase families from Wikipedia's "Signs of AI writing" (rev. 1380310647).
STOCK_PHRASES = [
    r"it is (?:important|worth|crucial|critical) to (?:note|remember|consider)(?: that)?",
    r"\b(?:serves|stands|functions) as (?:a|an|the)\b",
    r"\bis a (?:testament|reminder) to\b",
    r"\bsetting the stage for\b", r"\bfocal point\b", r"\bindelible mark\b", r"\bdeeply rooted\b",
    r"\breflects broader\b", r"\bvaluable insights\b", r"\bdespite these challenges\b",
    r"\bit(?:'s| is) not just\b", r"^(?:additionally|furthermore|moreover),",
    r"plays? a (?:crucial|pivotal|vital|key|significant) role",
    r"in today's (?:rapidly )?(?:evolving|changing)",
    r"in the (?:ever-)?(?:evolving|changing) (?:landscape|field|world)",
    r"a (?:testament|stark reminder) to",
    r"pave[sd]? the way",
    r"shed(?:s|ding)? (?:new )?light on",
    r"not only [^.]{3,80} but also",
    r"in conclusion,",
    r"in summary,",
    r"overall, (?:this|our|these)",
    r"opens? (?:up )?new avenues",
    r"holds? (?:great|immense|significant) (?:promise|potential)",
]
# Sentence-final present-participle tails (", highlighting the importance of ..."): instruction-tuned models
# use present participial clauses 2.6-5.3x the human rate (Reinhart et al., PNAS 2025). Counted, not listed.
ING_TAIL_RE = re.compile(r",\s+(?:highlighting|underscoring|emphasizing|emphasising|showcasing|ensuring|"
                         r"contributing|fostering|reflecting|demonstrating|paving|offering|providing)\b[^.]{5,}\.")

# Tortured phrases: Cabanac, Labbé & Magazinov, arXiv:2107.06751, Table 1 (seed list). One hit is a red flag.
TORTURED_PHRASES = [
    r"profound neural organi[sz]ation", r"(?:fake|counterfeit) neural organi[sz]ation", r"versatile organi[sz]ation",
    r"organi[sz]ation (?:ambush|assault)", r"(?:enormous|huge|immense|colossal) information",
    r"information (?:stockroom|distribution center)", r"(?:counterfeit|human-made) consciousness",
    r"elite figuring", r"haze figuring", r"designs preparing unit", r"focal preparing unit", r"work process motor",
    r"facial acknowledgement", r"discourse acknowledgement", r"mean square (?:mistake|blunder)",
    r"mean (?:outright|supreme) (?:mistake|blunder)", r"(?:motion|flag|indicator|sign|signal) to (?:clamor|commotion)",
    r"(?:arbitrary|irregular) (?:backwoods|timberland|lush territory)", r"(?:arbitrary|irregular) esteem",
    r"(?:subterranean insect|underground creepy crawly) (?:state|province|area|region|settlement)",
    r"leftover vitality", r"(?:credulous|innocent|gullible) bayes", r"individual computeri[sz]ed collaborator",
]

# Markup that chat interfaces leave in copied text (Wikipedia "Signs of AI writing", §markup artifacts).
MARKUP_ARTIFACTS = [
    r"contentReference", r"oaicite", r"oai_citation", r"turn\d+search\d+", r"attributableIndex", r"\[cite: ?\d+\]",
    r"\[span_\d+\]", r"grok_card", r"grok_render", r"attached_file", r"ppl-ai-file-upload", r"utm_source=chatgpt",
    r"【", r":::writing",
]
# First person singular in the body of a paper (Academ-AI's search dictionary). Info only: a sole author may.
FIRST_PERSON_SINGULAR = [r"\bI (?:recommend|apologi[sz]e|hope|would suggest|cannot|can't|don't have)\b"]

# Claims an editor reads as hype unless the evidence is prospective and independent.
OVERCLAIM = [
    r"\bnovel\b", r"(?<![-\w])first(?:-ever)?\b(?= (?:to|tool|platform|system|method|study|time))",
    r"\bunprecedented\b", r"\bgroundbreaking\b", r"\brevolution(?:ary|ize|ise)s?\b",
    r"\bparadigm(?:[- ]shift)?\b", r"\bsuperhuman\b", r"\bfully autonomous\b", r"\bautonomous(?:ly)?\b",
    r"\bPhD-level\b", r"\bhuman-level\b", r"\bstate[- ]of[- ]the[- ]art\b", r"\bbreakthrough\b",
    # "discovery" alone is also a software term (service or module discovery); flag only claims of it.
    r"\b(?:new|novel|scientific|biological|ai[- ]driven|autonomous) discover(?:y|ies)\b",
    r"\b(?:we|agent|system|model|pipeline|it) (?:discovered|discovers)\b", r"\bproves?\b", r"\bguarantees?\b", r"\bclinical[- ]grade\b",
    r"\bdiagnos(?:e|is|tic)\b",
]

# Declarations publishers require. Each entry: label, heading/phrase patterns, severity if absent.
# A disclosure is a statement about the authors' own use, not any sentence that says "LLM".
AI_DISCLOSURE = [
    r"(?m)^#{1,6}.*\b(?:ai|artificial intelligence|llms?|language models?)\b.*\b(?:use|usage|disclosure|statement|declaration)\b",
    r"(?m)^#{1,6}.*\b(?:use|usage|disclosure|declaration) of (?:generative )?(?:ai|artificial intelligence|llms?)\b",
    r"declaration of generative ai",
    r"ai[- ]assisted technolog",
    r"ai[- ]use statement",
    r"(?:we|the authors) used [^.]{0,80}\b(?:claude|chatgpt|gpt-?\d|gemini|copilot|llama|deepseek|qwen|mistral)\b",
]
DECLARATIONS = [
    # "Data and code availability", "Data, code and materials availability" are data statements too.
    ("Data availability", [r"data availability", r"availability of data",
                           r"\bdata(?:,? (?:and |& )?(?:code|software|materials?|protocols?))+ availability"],
     Severity.major),
    ("Code or software availability", [r"code availability", r"software availability", r"code and data availability",
                                      r"availability and implementation", r"availability and requirements"],
     Severity.major),
    ("Competing interests", [r"competing interests?", r"conflicts? of interest", r"declaration of interests?"],
     Severity.major),
    ("Funding", [r"\bfunding\b"], Severity.major),
    ("Author contributions", [r"author contributions?", r"contribution statements?", r"credit authorship"],
     Severity.major),
]

# Context to inspect: mentions alone do not establish author use or a disclosure obligation.
AI_TOOL_MENTIONS = [
    r"\bclaude\b", r"\bgpt-?\d", r"\bchatgpt\b", r"\bgemini\b", r"\bllama\b", r"\bmistral\b",
    r"\bcopilot\b", r"\bcursor\b", r"\bdeepseek\b", r"\bqwen\b", r"\bopus\b", r"\bsonnet\b",
    r"\blarge language models?\b", r"\bllms?\b", r"\bai agents?\b", r"\bagentic\b", r"\bai assistants?\b",
    r"\bchatbots?\b", r"\bgenerative ai\b", r"\bai[- ]generated\b", r"\bai[- ]assisted\b",
]
# Revision marks (`<!-- @rev ID rounds=N by=name:date,... -->`, or `% @rev ...` in LaTeX; the format of
# manuscript-revision-marks) and the agent names they may carry, shared with that skill.
LEDGER_BY = re.compile(r"(?:<!--|%)[ \t]*@rev\b[^\n>]*?\bby=([^\s>]+)")
AGENT_NAMES = Path(__file__).resolve().parents[2] / "manuscript-revision-marks" / "references" / "agent-names.toml"


# The names the scan recognised before the shared list existed, for an install without manuscript-revision-marks.
FALLBACK_AGENT_PATTERNS = ["claude", "claude-*", "gpt", "gpt-*", "chatgpt", "gemini", "gemini-*", "copilot", "ai", "llm"]


def _agent_patterns() -> list[str]:
    if not AGENT_NAMES.is_file():
        return FALLBACK_AGENT_PATTERNS
    data = tomllib.loads(AGENT_NAMES.read_text(encoding="utf-8"))
    return [n.lower() for n in data["names"] + data["patterns"]]


def ledger_ai(raw: str) -> list[str]:
    """For each revision mark that names a known AI model or agent in `by=`, the first such name."""
    patterns = _agent_patterns()
    out = []
    for m in LEDGER_BY.finditer(raw):
        names = [item.partition(":")[0].lower() for item in m.group(1).split(",")]
        ai = next((n for n in names if any(fnmatch.fnmatchcase(n, p) for p in patterns)), None)
        if ai is not None:
            out.append(ai)
    return out


MODEL_VERSION = re.compile(
    r"(?:claude[- ](?:opus|sonnet|haiku|fable)?[- ]?\d|gpt-?\d(?:\.\d)?(?:-\w+)?|gemini[- ]\d(?:\.\d)?|"
    r"llama[- ]?\d|qwen\d?|deepseek-\w+|claude-[a-z]+-\d)",
    re.IGNORECASE,
)

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>)\],;]+)", re.IGNORECASE)
PMID_RE = re.compile(r"\bPMID:?\s*(\d{1,9})\b", re.IGNORECASE)
# New-style ids (2101.00001), and old-style ones (hep-th/9901001, math.GT/0309136) after "arXiv:".
ARXIV_RE = re.compile(r"\barXiv\W{0,3}(\d{4}\.\d{4,5})(?:v\d+)?\b|arxiv\.org/abs/(\d{4}\.\d{4,5})|"
                      r"\barXiv:\s*([a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?\b", re.IGNORECASE)


def _arxiv_id(m: Optional[re.Match[str]]) -> Optional[str]:
    return next((g for g in m.groups() if g), None) if m else None
_CAP = r"[A-ZÀ-ÖØ-Þ][^\W\d_]*(?:['’\-][^\W\d_]+)*"  # a capitalised name word, any script with Latin capitals
_PARTICLES = r"(?:(?:van|von|de|der|den|del|della|di|da|du|la|le|ter|ten)\s+)*"
# Author-year citations in a parenthesis: "(Lambert et al., 2021)", "(Illumina, 2023; Ultima Genomics, 2025)".
AUTHOR_YEAR_RE = re.compile(rf"({_PARTICLES}{_CAP}(?:\s+{_CAP}){{0,5}}(?:\s+(?:et\s+al\.?|and|&)\s*(?:{_CAP})?)?),?\s+"
                            rf"((?:19|20)\d{{2}})(?!\d)[a-z]?")
CITE_LEAD = re.compile(r"^(?:e\.g\.|i\.e\.|see(?:\s+also)?|but\s+see|cf\.|for\s+example|for\s+a\s+review,?\s+see|"
                       r"reviewed\s+in|as\s+in|also|and)\s*,?\s*", re.IGNORECASE)
YEAR_TAIL = re.compile(r"(?:\s*,\s*(?:(?:19|20)\d{2}[a-z]?|[a-z])\b)*\s*,?\s*")
NOT_AUTHORS = {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
               "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov",
               "dec", "spring", "summer", "autumn", "fall", "winter"}
PAREN_GROUP_RE = re.compile(r"\(([^()]*?(?:19|20)\d{2}[a-z]?[^()]*)\)")
NUMERIC_CITE_RE = re.compile(r"\[(\d+(?:\s*[-–,]\s*\d+)*)\]")
REF_HEADING = re.compile(r"^#{1,6}\s*\**\s*(?:\d+\.?\s*)?(references|bibliography|literature cited|works cited)\b",
                         re.IGNORECASE)
LATEX_REF_HEADING = re.compile(r"\\(?:section|chapter)\*?\{(references|bibliography)\}|\\begin\{thebibliography\}",
                               re.IGNORECASE)
HEADING = re.compile(r"^#{1,6}\s|^\\(?:sub)*section\*?\{")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
ABSTRACT_HEADING = re.compile(r"^#{1,6}\s*\**\s*abstract|\\begin\{abstract\}", re.IGNORECASE)
NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*(%|-fold|×|x\b|fold\b|s\b|min\b|h\b|GB\b|MB\b)")


def _strip_comments(text: str) -> str:
    """Drop HTML comments (ledger markers, author notes) but keep line numbers stable."""
    return HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def _lines(text: str) -> list[str]:
    return text.splitlines()


def _excerpt(line: str, start: int, end: int, width: int = 60) -> str:
    lo, hi = max(0, start - width), min(len(line), end + width)
    return ("…" if lo else "") + line[lo:hi].strip() + ("…" if hi < len(line) else "")


QUOTE_WIDTH = 160


def _quote(text: str, start: int = 0, end: int = 0, width: int = QUOTE_WIDTH) -> tuple[str, Optional[tuple[int, int]]]:
    """The text as written, cut to about `width` characters around [start, end) at word boundaries and marked
    [...] where shortened, with the span's place in the result (None when no span was given)."""
    text = re.sub(r"[\r\n\t]", " ", text)  # same length, so the offsets still apply
    lead = len(text) - len(text.lstrip())
    body = text.strip()
    start, end = min(max(0, start - lead), len(body)), min(max(0, end - lead), len(body))
    end = max(end, start)
    if end - start > width:
        end = start + width
    if len(body) <= width:
        return body, (start, end) if end > start else None
    lo = max(0, start - (width - (end - start)) // 2)
    hi = min(len(body), max(lo + width, end))
    if hi == len(body):
        lo = max(0, min(lo, hi - width))
    if lo > 0:
        space = body.find(" ", lo, start + 1)
        lo = space + 1 if space >= 0 else lo
    if hi < len(body):
        space = body.rfind(" ", end, hi)
        hi = space if space > end else hi
    prefix, suffix = ("[...] " if lo > 0 else ""), (" [...]" if hi < len(body) else "")
    shift = len(prefix) - lo
    return prefix + body[lo:hi].strip() + suffix, ((start + shift, end + shift) if end > start else None)


def _with_quote(finding: Finding, text: str, start: int = 0, end: int = 0) -> Finding:
    finding.quote, finding.quote_span = _quote(text, start, end)
    return finding


def _ref_finding(ref: "Reference", finding: Finding) -> Finding:
    """A finding about one bibliography entry: the entry quoted as written, placed in its BibTeX file and key when it
    came from one, else in the section that holds its reference list."""
    finding.section = finding.section or (f"{ref._bib_file}, entry {ref._bib_key}" if ref._bib_file
                                          else ref._list or "References")
    finding.line = finding.line or ref.line
    finding._entry = True
    return _with_quote(finding, ref.text)


def _scan_patterns(lines: list[str], patterns: list[str], check: str, severity: Severity, message: str,
                   suggestion: str, flags: int = re.IGNORECASE, stop_line: Optional[int] = None, why: str = "",
                   stage: str = "") -> list[Finding]:
    compiled = [re.compile(p, flags) for p in patterns]
    out: list[Finding] = []
    for i, line in enumerate(lines, start=1):
        if stop_line is not None and i >= stop_line:
            break
        for rx in compiled:
            for m in rx.finditer(line):
                out.append(_with_quote(Finding(check=check, severity=severity, line=i,
                                               excerpt=_excerpt(line, m.start(), m.end()),
                                               message=message.format(match=m.group(0).strip()),
                                               suggestion=suggestion, why=why, stage=stage), line, m.start(), m.end()))
    return out


# --- where a finding sits, and when the authors can act on it ---------------------------------------------------

MD_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
TEX_SECTION = re.compile(r"^\s*\\(chapter|section|subsection|subsubsection)\*?\s*(?:\[[^\]]*\])?\s*"
                         r"\{((?:[^{}]|\{[^{}]*\})*)\}")
TEX_LEVELS = {"chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3}
BOLD_LABEL = re.compile(r"^\*\*([^*]{2,80}?)\*\*\s*:?\s*$")  # "**References for Table S7.**" on a line of its own
FRONT_MATTER = "Front matter"
WHOLE_MANUSCRIPT = "Whole manuscript"


def _heading_text(text: str) -> str:
    text = re.sub(r"\\label\{[^}]*\}", "", text)
    text = re.sub(r"\\[A-Za-z]+\*?", "", text)  # \textit{x} -> {x}
    text = " ".join(re.sub(r"[{}*_`]", "", text).split()).strip(" .:")
    return text if len(text) <= 80 else text[:77].rsplit(" ", 1)[0] + " [...]"


def section_index(lines: list[str]) -> list[str]:
    """The section each line falls under (item i for line i + 1): its heading, with the top-level heading in front
    when nested ("Results, Runtime"); "Abstract" inside a LaTeX abstract environment; "Front matter" before the
    first heading. A lone top-level Markdown heading above all the others is the paper's title, not a section, and a
    line that is only bold text ("**References for Table S7.**") counts as a heading below the current one."""
    heads: dict[int, tuple[int, str]] = {}
    markdown: set[int] = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if m := MD_HEADING.match(stripped):
            heads[i] = (len(m.group(1)), _heading_text(m.group(2)))
            markdown.add(i)
        elif m := TEX_SECTION.match(line):
            heads[i] = (TEX_LEVELS[m.group(1)], _heading_text(m.group(2)))
        elif (m := BOLD_LABEL.match(stripped)) and len(m.group(1).split()) <= 8:
            heads[i] = (7, _heading_text(m.group(1)))
    levels = [level for level, _ in heads.values() if level < 7]
    first = min(heads) if heads else None
    title = first if (first in markdown and len(levels) > 1 and heads[first][0] == min(levels)
                      and levels.count(min(levels)) == 1) else None  # LaTeX keeps its title in \title
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    in_abstract = False
    for i, line in enumerate(lines):
        if i in heads and i != title:
            level, text = heads[i]
            while stack and stack[-1][0] >= level:
                stack.pop()
            if text:
                stack.append((level, text))
        if re.search(r"\\begin\{abstract\}", line):
            in_abstract = True
        if re.search(r"\\begin\{thebibliography\}", line):
            stack = [(1, "References")]
        names = [text for _, text in stack]
        if len(names) > 2:
            names = [names[0], names[-1]]
        out.append("Abstract" if in_abstract else ", ".join(names) or FRONT_MATTER)
        if re.search(r"\\end\{abstract\}", line):
            in_abstract = False
    return out


# When the authors can act on each check's findings (references/author-priorities.md, "Order the work by when it
# can be done"). A finding whose stage depends on more than its check sets it where it is made.
CHECK_STAGE: dict[str, Stage] = {
    "numbers": Stage.now, "citations": Stage.now, "references": Stage.now, "validation": Stage.now,
    "chatbot-leftover": Stage.writing, "stock-phrase": Stage.writing, "tortured-phrase": Stage.writing,
    "first-person": Stage.writing, "overclaim": Stage.writing, "style": Stage.writing, "vocabulary": Stage.writing,
    "abstract": Stage.writing,
    "venue": Stage.journal,
    "placeholder": Stage.final, "declarations": Stage.final, "ai-use": Stage.final, "availability": Stage.final,
}


def _place(findings: list[Finding], lines: list[str], sections: list[str]) -> None:
    """Give each finding the section its line falls under, a quote of that line when it has none, and its stage."""
    for f in findings:
        if f.section is None:
            f.section = sections[f.line - 1] if f.line and f.line <= len(sections) else WHOLE_MANUSCRIPT
        if not f.quote and f.line and f.line <= len(lines) and lines[f.line - 1].strip():
            _with_quote(f, lines[f.line - 1])
        f.stage = f.stage or CHECK_STAGE.get(f.check, Stage.now).value


def _reference_start(lines: list[str]) -> Optional[int]:
    for i, line in enumerate(lines, start=1):
        if REF_HEADING.search(line.strip()) or LATEX_REF_HEADING.search(line):
            return i
    return None


# A later list of references: "## Supplementary references", or a bold label such as "**References for Table S7.**".
FURTHER_REF_LABEL = re.compile(r"^(?:#{1,6}\s*\**|\*\*)\s*(?:\w+\s+){0,2}(?:references|bibliography)\b[^*\n]{0,60}"
                               r"(?:\*\*\s*:?|[^*\n]*)$", re.IGNORECASE)
# Where a new author-year reference starts: "Mordaunt, D. A., et al. (2024)" or "Ultima Genomics (2025). Title".
REF_START = (rf"{_PARTICLES}{_CAP},\s+(?:[A-ZÀ-ÖØ-Þ]\.\s?-?)+(?=[^()]{{0,300}}?\((?:19|20)\d{{2}}[a-z]?\))"
             rf"|(?:{_CAP}\s+){{0,6}}{_CAP}\s+\((?:19|20)\d{{2}}[a-z]?\)\.\s+(?=[A-Z*\"“‘'])")
REF_BOUNDARY = re.compile(rf"(?<=\.)\s+(?={REF_START})")
REF_LEAD_IN = re.compile(rf"(?P<lead>[^:]{{3,160}}?):\s+(?={REF_START})")


def _list_entries(lines: list[str], start: int, further: bool) -> list[tuple[int, str]]:
    """Each non-empty line after a list's label, up to the next heading, is one entry. A further list also ends at
    a bold label or a table; a lead-in ending in a colon ("Software without a paper:") is not an entry."""
    entries: list[tuple[int, str]] = []
    for i in range(start, len(lines)):
        line = lines[i].strip()
        if HEADING.match(line) or (further and (line.startswith("**") or line.startswith("|"))):
            break
        if len(line) < 25 or (line.startswith("*(") and line.endswith(")*")) or line.endswith(":"):
            continue
        entries.append((i + 1, line))
    return entries


def _reference_lists(lines: list[str], start: Optional[int]) -> list[tuple[int, int, str, list[tuple[int, str]]]]:
    """(label line, last line, label, entries) for the main reference list and any later list (a supplement's)."""
    if start is None:
        return []
    out = []
    begin, label, further = start, lines[start - 1].strip(), False
    while True:
        entries = _list_entries(lines, begin, further)
        end = entries[-1][0] if entries else begin
        out.append((begin, end, label, entries))
        nxt = next((i for i in range(end, len(lines)) if FURTHER_REF_LABEL.match(lines[i].strip())), None)
        if nxt is None:
            return out
        begin, label, further = nxt + 1, lines[nxt].strip(), True


def _numbered_parts(chunk: str) -> list[str]:
    """A paragraph that starts "[1]" or "1." split before "[2]", "[3]" ... or "2.", "3." ... in sequence."""
    numbered = re.match(r"\s*(\[(\d+)\]|(\d+)\.)\s", chunk)
    if not numbered:
        return [chunk]
    n, cut, parts = int(numbered.group(2) or numbered.group(3)), 0, []
    bracket = numbered.group(1).startswith("[")
    while True:
        n += 1
        marker = re.compile(rf"\s\[{n}\]\s" if bracket else rf"(?<=\.)\s+{n}\.\s+(?={_CAP},?\s+[A-Z])")
        nxt = marker.search(chunk, cut + 1)
        if not nxt:
            return parts + [chunk[cut:]]
        parts.append(chunk[cut:nxt.start()])
        cut = nxt.start()


def _split_after_dois(piece: str) -> list[str]:
    dois = list(DOI_RE.finditer(piece))
    if len(dois) < 2:
        return [piece]
    cuts = [0] + [m.end() for m in dois]
    return [piece[a:b] for a, b in zip(cuts, cuts[1:] + [len(piece)])]


def _split_entries(entries: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """One entry per reference: a line that holds several is split at line breaks (<br>), numbering ([2], 2.),
    author-year starts after a full stop and DOIs; a lead-in such as "Added in the revision:" is dropped."""
    out: list[tuple[int, str]] = []
    for line_no, text in entries:
        pieces: list[str] = []
        for chunk in re.split(r"<br\s*/?>", text, flags=re.IGNORECASE):
            for part in _numbered_parts(chunk):
                part = part.strip()
                lead = REF_LEAD_IN.match(part)
                if lead and not re.search(r"\((?:19|20)\d{2}", lead.group("lead")):
                    part = part[lead.end():]
                pieces += [p for piece in REF_BOUNDARY.split(part) for p in _split_after_dois(piece)]
        pieces = [p.strip(" .;") for p in pieces if len(p.strip(" .;")) >= 25]
        out += [(line_no, p) for p in pieces] or [(line_no, text)]
    return out


LATEX_BIB = re.compile(r"\\(?:bibliography|addbibresource)\{([^}]+)\}")
LATEX_CITE_KEYS = re.compile(r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]+)\}")
# LaTeX accents and letters as BibTeX writes them: {\"u}, \"{u}, {\c{s}}, \'{\i}, {\o}, \ss.
_ACCENTS = {'"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303", "=": "\u0304", ".": "\u0307",
            "u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "k": "\u0328", "r": "\u030a", "d": "\u0323",
            "b": "\u0331"}
_LATEX_LETTERS = {"ss": "ß", "aa": "å", "AA": "Å", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "o": "ø", "O": "Ø",
                  "l": "ł", "L": "Ł", "i": "i", "j": "j"}
LATEX_ACCENT = re.compile(r"\\([\"'`^~=.])\s*\{?\s*(\\[ij](?![A-Za-z])|[A-Za-z])\s*\}?"
                          r"|\\([uvHckrdb])(?:\s*\{\s*(\\[ij](?![A-Za-z])|[A-Za-z])\s*\}|\s+([A-Za-z]))")
LATEX_LETTER = re.compile(r"\\(ss|aa|AA|ae|AE|oe|OE|o|O|l|L|i|j)(?![A-Za-z])\s?")


class BibError(Exception):
    """A BibTeX entry that does not parse."""


BIB_HEAD = re.compile(r"@\s*([A-Za-z]+)\s*([{(])")
BIB_NAME = re.compile(r"[A-Za-z][\w\-:.+]*")
BIB_WORD = re.compile(r"[^\s,#{}()\"=]+")


def _bib_balanced(text: str, i: int, open_: str, close: str) -> int:
    """The index just past the `close` that matches the `open_` at text[i]."""
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == open_:
            depth += 1
        elif c == close:
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise BibError(f"no closing {close}")


def _bib_value(text: str, i: int, strings: dict[str, str]) -> tuple[str, int]:
    """One field value from position i: braces balanced at any depth, a quoted string, a number or an
    @string macro, joined by #."""
    pieces = []
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            raise BibError("a value runs off the end")
        c = text[i]
        if c == "{":
            j = _bib_balanced(text, i, "{", "}")
            pieces.append(text[i + 1:j - 1])
        elif c == '"':
            j, depth = i + 1, 0
            while j < len(text) and not (text[j] == '"' and depth == 0 and text[j - 1] != "\\"):
                depth += {"{": 1, "}": -1}.get(text[j], 0)
                j += 1
            if j >= len(text):
                raise BibError('no closing "')
            pieces.append(text[i + 1:j])
            j += 1
        else:
            m = BIB_WORD.match(text, i)
            if not m:
                raise BibError(f"no value at {c!r}")
            pieces.append(strings.get(m.group(0).lower(), m.group(0)))
            j = m.end()
        i = j
        while i < len(text) and text[i].isspace():
            i += 1
        if i < len(text) and text[i] == "#":
            i += 1
            continue
        return "".join(pieces), i


def _parse_bib(text: str) -> tuple[list[tuple[str, int, dict[str, str]]], list[tuple[int, str, bool]]]:
    """(key, line, raw fields) for each entry, and (line, why, kept) for each that does not parse. @string macros
    are substituted, @comment and @preamble skipped, and an entry may close with } or ). An entry whose key was
    read but whose fields stop parsing is kept with the fields before the problem (kept=True), as BibTeX keeps it."""
    entries, errors, strings = [], [], {}
    i = 0
    while True:
        at = text.find("@", i)
        if at == -1:
            break
        m = BIB_HEAD.match(text, at)
        if not m:
            i = at + 1
            continue
        line = text.count("\n", 0, at) + 1
        kind, opener = m.group(1).lower(), m.group(2)
        try:
            end = _bib_balanced(text, m.end() - 1, opener, "}" if opener == "{" else ")")
        except BibError as exc:
            errors.append((line, str(exc), False))
            break
        i = end
        if kind in ("comment", "preamble"):
            continue
        body = text[m.end():end - 1]
        key, fields = None, {}
        try:
            if kind == "string":
                name = BIB_NAME.match(body.lstrip())
                if not name:
                    raise BibError("@string without a name")
                rest = body.lstrip()[name.end():].lstrip()
                if not rest.startswith("="):
                    raise BibError("@string without =")
                strings[name.group(0).lower()] = _bib_value(rest, 1, strings)[0]
                continue
            key = re.match(r"\s*([^,\s]*)\s*(,|$)", body)
            if not key or not key.group(1):
                raise BibError("no key")
            j = key.end()
            while True:
                while j < len(body) and (body[j].isspace() or body[j] == ","):
                    j += 1
                if j >= len(body):
                    break
                name = BIB_NAME.match(body, j)
                if not name:
                    raise BibError(f"no field name at {body[j:j + 20]!r}")
                j = name.end()
                while j < len(body) and body[j].isspace():
                    j += 1
                if j >= len(body) or body[j] != "=":
                    raise BibError(f"field {name.group(0)} has no =")
                value, j = _bib_value(body, j + 1, strings)
                fields[name.group(0).lower()] = value
            entries.append((key.group(1), line, fields))
        except BibError as exc:
            kept = kind != "string" and bool(key and key.group(1))
            if kept:
                entries.append((key.group(1), line, fields))
            errors.append((line, str(exc), kept))
    return entries, errors


def _bib_plain(value: str) -> str:
    """An identifier field as written: braces gone, LaTeX escapes of URL characters undone."""
    return re.sub(r"\\([_%&#~$])", r"\1", value).replace("{", "").replace("}", "").strip()


LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa", ".test", ".invalid")


def _local_host(host: str) -> bool:
    """A host no reader of the paper can open: localhost, a private, loopback or link-local address, a name with no
    dot ("your-server"), or a reserved local suffix. Such a link is an example or a placeholder."""
    if not host or host == "localhost" or host.endswith(LOCAL_SUFFIXES):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return "." not in host
    return ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_reserved


def classify_url(url: str) -> tuple[str, str]:
    """("doi" | "arxiv" | "pmid" | "url" | "placeholder" | "local", value): a URL on doi.org, arxiv.org or PubMed is
    that identifier; a bracketed host ("https://[anonymized-for-review]") is a placeholder and a local or private
    host is an example, neither of which is ever looked up."""
    try:
        u = urllib.parse.urlsplit(url)
        host = (u.hostname or "").lower()
    except ValueError:  # urllib reads a bracketed host as an IPv6 address
        return "placeholder", url
    if _local_host(host):
        return "local", url
    path = urllib.parse.unquote(u.path)
    if host in ("doi.org", "dx.doi.org", "www.doi.org") and path.startswith("/10."):
        return "doi", path[1:]
    if host in ("arxiv.org", "www.arxiv.org"):
        m = re.fullmatch(r"/(?:abs|pdf)/(.+?)(?:v\d+)?(?:\.pdf)?/?", path)
        if m:
            return "arxiv", m.group(1)
    if host == "pubmed.ncbi.nlm.nih.gov" or (host in ("www.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov")
                                              and path.startswith("/pubmed/")):
        m = re.fullmatch(r"(?:/pubmed)?/(\d{1,9})/?", path)
        if m:
            return "pmid", m.group(1)
    return "url", url


def _bib_ids(fields: dict[str, str]) -> list[tuple[str, str]]:
    """Every identifier a BibTeX entry carries: doi, pmid, an arXiv eprint (archivePrefix or eprinttype arxiv),
    an arXiv id written into eprint, journal or note, and url (classified by its host)."""
    ids: list[tuple[str, str]] = []
    if fields.get("doi"):
        doi = _bib_plain(fields["doi"])
        ids.append(classify_url(doi) if doi.lower().startswith("http") else
                   ("doi", re.sub(r"(?i)^doi:\s*", "", doi)))
    if fields.get("pmid"):
        ids.append(("pmid", _bib_plain(fields["pmid"])))
    prefix = _bib_plain(fields.get("archiveprefix") or fields.get("eprinttype") or "").lower()
    if fields.get("eprint") and prefix == "arxiv":
        ids.append(("arxiv", re.sub(r"(?i)^arxiv:\s*", "", _bib_plain(fields["eprint"]))))
    written = _arxiv_id(ARXIV_RE.search(" ".join(fields.get(k, "") for k in ("eprint", "journal", "note"))))
    if written:
        ids.append(("arxiv", written))
    if fields.get("url"):
        ids.append(classify_url(_bib_plain(fields["url"])))
    return [i for i in dict.fromkeys(ids) if i[0] not in ("placeholder", "local")]


def _latex_text(value: str) -> str:
    """BibTeX field text as a reader sees it: accents composed, commands and braces dropped."""
    def accent(m: re.Match[str]) -> str:
        mark = _ACCENTS[m.group(1) or m.group(3)]
        letter = (m.group(2) or m.group(4) or m.group(5) or "").lstrip("\\")
        return letter + mark

    text = LATEX_ACCENT.sub(accent, value)
    text = LATEX_LETTER.sub(lambda m: _LATEX_LETTERS[m.group(1)], text)
    text = re.sub(r"\\([&%$#_{}])", r"\1", text.replace("\\-", ""))
    text = re.sub(r"\\[A-Za-z]+\*?", " ", text)  # \url, \texttt, \emph: keep the argument, drop the command
    text = re.sub(r"\\[ ,;:!]|~", " ", text)
    text = re.sub(r"---?", "–", text.replace("{", "").replace("}", ""))
    return unicodedata.normalize("NFC", " ".join(text.split()))


def _bib_files(tex: str, base: Path) -> list[Path]:
    out: list[Path] = []
    for m in LATEX_BIB.finditer(tex):
        for name in m.group(1).split(","):
            f = base / name.strip()
            f = f if f.suffix == ".bib" else f.with_suffix(".bib")
            if f.exists():
                out.append(f)
    return out


def _bib_references(bib: Path, errors: Optional[list[tuple[int, str, bool]]] = None) -> list[tuple[str, "Reference"]]:
    """(cite key, Reference) for each BibTeX entry; text is "author (year). title. venue" for matching. Entries
    that do not parse are appended to *errors* as (line, why, kept)."""
    text = bib.read_text(encoding="utf-8")
    entries, failed = _parse_bib(text)
    if errors is not None:
        errors += failed
    out: list[tuple[str, Reference]] = []
    for key, line, raw in entries:
        fields = {k: _latex_text(v) for k, v in raw.items()}
        venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or ""
        # An entry with no author starts with its year, so the online check knows there is no list to compare.
        entry = " ".join(f"{fields.get('author', '')} ({fields.get('year', '')}). {fields.get('title', '')}. "
                         f"{venue}".split())
        ids = _bib_ids(raw)
        first = {kind: value for kind, value in reversed(ids)}  # the first of each kind
        ref = Reference(line=line, text=entry, doi=first.get("doi"), pmid=first.get("pmid"), arxiv=first.get("arxiv"),
                        cited_title=fields.get("title") or None, url=first.get("url"),
                        other_ids=[f"{k}:{v}" for k, v in ids if first.get(k) != v])
        ref._bib_file, ref._bib_key = bib.name, key
        out.append((key, ref))
    return out


def _cite_key_findings(tex_lines: list[str], keys: set[str]) -> list[Finding]:
    out: list[Finding] = []
    for i, line in enumerate(tex_lines, start=1):
        for m in LATEX_CITE_KEYS.finditer(line):
            for key in (k.strip() for k in m.group(1).split(",")):
                if key and key not in keys:
                    at = line.find(key, m.start())
                    out.append(_with_quote(Finding(
                        check="citations", severity=Severity.major, line=i, excerpt=key,
                        message=f"The citation key '{key}' is cited here but has no entry in the bibliography file, "
                                f"so the reference will be missing from the PDF.",
                        suggestion="Add the entry, with its DOI, or correct the key."), line, at, at + len(key)))
    return out


def _declaration_findings(text_lower: str) -> list[Finding]:
    out: list[Finding] = []
    for label, patterns, severity in DECLARATIONS:
        if not any(re.search(p, text_lower) for p in patterns):
            out.append(Finding(check="declarations", severity=severity, section=WHOLE_MANUSCRIPT,
                               message=f"No '{label}' statement was found in the manuscript.",
                               why="Most journals require one.",
                               suggestion=f"Add the '{label}' statement in the form the chosen journal asks for, "
                                          f"once the code, data and results are final."))
    return out


def _ai_use_findings(lines: list[str], text_lower: str, ref_start: Optional[int],
                     revision_markers: bool = False) -> list[Finding]:
    body = lines[: (ref_start or len(lines) + 1) - 1]
    mentions = _scan_patterns(body, AI_TOOL_MENTIONS, "ai-use", Severity.info,
                              "The text names an AI tool or a large language model ('{match}').",
                              "If the sentence describes the authors' own use of the tool, check whether the "
                              "chosen journal asks for a statement about that use.")
    out: list[Finding] = []
    has_disclosure = any(re.search(p, text_lower) for p in AI_DISCLOSURE)
    if (mentions or revision_markers) and not has_disclosure:
        first = mentions[0] if mentions else None
        out.append(Finding(check="ai-use", severity=Severity.info,
                           line=first.line if first else None, excerpt=first.excerpt if first else "",
                           quote=first.quote if first else "", quote_span=first.quote_span if first else None,
                           message="The manuscript mentions AI tools or carries revision markers that name an AI, "
                                   "but no statement about the authors' own use of AI was recognised.",
                           suggestion="Whether a statement is needed depends on what the tools did and on the chosen "
                                      "journal's rule and its exemptions; if one is needed, give only the fields and "
                                      "places the journal asks for. This automated check cannot show that a "
                                      "statement is missing."))
    named = [f for f in mentions if re.search(r"claude|gpt|gemini|llama|mistral|copilot|cursor|deepseek|qwen|opus|sonnet",
                                              f.message, re.IGNORECASE)]
    if named and not MODEL_VERSION.search("\n".join(body)):
        out.append(Finding(check="ai-use", severity=Severity.info, section=WHOLE_MANUSCRIPT,
                           message="AI tools are named, but no model version appears anywhere in the manuscript.",
                           suggestion="If these are tools the authors used, give a model identifier only where the "
                                      "journal or reproducibility needs it. Do not invent a version that is not "
                                      "known, and do not add dates or prompts unless they are asked for."))
    out.extend(mentions)
    return out


def _vocabulary(body_text: str) -> tuple[dict[str, float], list[tuple[str, int]], int]:
    """Hits per 1000 words for each source list, and the most frequent listed words."""
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", _one_word_links(body_text))
    lower = Counter(w.lower() for w in words)
    n = max(len(words), 1)
    densities = {name: round(1000 * sum(lower[w] for w in vocab) / n, 2) for name, vocab in VOCAB_SOURCES.items()}
    union = set().union(*VOCAB_SOURCES.values())
    hits = Counter({w: lower[w] for w in union if lower[w]})
    return densities, hits.most_common(15), len(words)


# "12 of 40 (30%)", "12/40 (30.0%)", "12 out of 40 samples (30 %)": a percentage stated beside its counts.
PERCENT_OF_RE = re.compile(
    r"(?<![\w.])(\d[\d,]*)\s*(?:/|of|out of)\s*(\d[\d,]*)(?:\s+[A-Za-z][\w-]*){0,3}\s*[(\[,]\s*(\d+(?:\.\d+)?)\s?%")


def _percentages(lines: list[str]) -> list[Finding]:
    """Recompute every percentage stated beside its counts; a mismatch beyond rounding is flagged."""
    out: list[Finding] = []
    for i, line in enumerate(lines, start=1):
        for m in PERCENT_OF_RE.finditer(line):
            num, den = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
            stated = m.group(3)
            if den == 0 or num > den:
                continue
            decimals = len(stated.split(".")[1]) if "." in stated else 0
            actual = 100 * num / den
            if abs(actual - float(stated)) > 0.5 * 10 ** -decimals + 1e-9:
                out.append(_with_quote(Finding(
                    check="numbers", severity=Severity.major, line=i, excerpt=_excerpt(line, m.start(), m.end()),
                    message=f"{num} of {den} is {actual:.{max(decimals, 1)}f}%, not the {stated}% stated beside it.",
                    why="A percentage that disagrees with its own counts makes readers doubt the other numbers.",
                    suggestion="Recompute the percentage from the counts, and check the counts against the data."),
                    line, m.start(), m.end()))
    return out


# A reported metric: a decimal, a percentage, a fold change, a value with a unit, a sample size or an interval.
METRIC_RE = re.compile(
    r"(?<![\w.\[])(?:\d+(?:[.,]\d+)?\s?(?:%|×|-fold|fold\b|x\b|s\b|ms\b|min\b|h\b|GB\b|MB\b|TB\b|bp\b|kb\b|Mb\b)"
    r"|\d+\.\d+|\bn\s?=\s?\d[\d,]*|\b(?:CI|AUROC|AUC|F1|r|R2|R²|OR|HR|RR|β)\s?[=:]\s?-?\d)", re.IGNORECASE)
ABSTRACT_METRICS_MINOR = 6


def _abstract_metric_dump(lines: list[str]) -> list[Finding]:
    """An abstract that lists the benchmark table (llm-smells A12)."""
    span = _abstract_span(lines)
    if span is None:
        return []
    text = "\n".join(lines[span[0]:span[1]])
    metrics = METRIC_RE.findall(text)
    if len(metrics) <= ABSTRACT_METRICS_MINOR:
        return []
    shown = ", ".join(m.strip() for m in metrics[:5])
    return [Finding(check="abstract", severity=Severity.minor, section="Abstract",
                    line=span[0], excerpt=", ".join(m.strip() for m in metrics[:8]),
                    message=f"The Abstract reports {len(metrics)} numerical results (among them {shown}), which "
                            f"can make it hard to read.",
                    suggestion="Keep the numbers its claims need and the journal's format asks for. A count of "
                               "numbers is not a defect by itself, and not a reason to remove results.")]


def _abstract_numbers(lines: list[str], ref_start: Optional[int]) -> list[Finding]:
    """Numbers stated in the abstract that never appear again in the body: check each by hand."""
    start = next((i for i, l in enumerate(lines) if ABSTRACT_HEADING.search(l.strip())), None)
    if start is None:
        return []
    end = next((i for i in range(start + 1, len(lines)) if HEADING.match(lines[i].strip())), len(lines))
    body = "\n".join(lines[end:(ref_start or len(lines) + 1) - 1])
    out: list[Finding] = []
    for i in range(start + 1, end):
        for m in NUMBER_RE.finditer(lines[i]):
            if m.group(1) not in body:
                out.append(_with_quote(Finding(
                    check="numbers", severity=Severity.info, line=i + 1, excerpt=m.group(0), section="Abstract",
                    message=f"The Abstract states '{m.group(0)}', and this number does not appear again in the "
                            f"body.",
                    why="Every number in the Abstract should come from a result the paper reports.",
                    suggestion="Confirm that it comes from a result reported in a table, a figure or the text, or "
                               "report that result."), lines[i], m.start(), m.end()))
    return out


def _name_tokens(text: str) -> list[str]:
    """Words with apostrophes and hyphens folded away, so O'Daniel and Tandy-Connor match themselves."""
    return [re.sub(r"[^a-z]", "", w.lower()) for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*", text)]


def _author_year_citations(group: str, whole: bool = False) -> list[tuple[str, str]]:
    """(name, year) for each citation in a parenthesis. A citation starts the parenthesis or follows ';' (after an
    optional 'e.g.' or 'see'), so "(entered at EASRP 2026 and ...)" or "(accessed 10 October 2026)" is not one.
    With `whole`, the text must be citations and nothing else (a table cell "McLaren et al., 2016")."""
    out: list[tuple[str, str]] = []
    for segment in group.split(";"):
        text = CITE_LEAD.sub("", segment.strip())
        pos = 0
        while (m := AUTHOR_YEAR_RE.match(text, pos)) is not None:
            name = re.sub(r"\s+(?:et\s+al\.?|and|&).*$", "", m.group(1))
            if name.lower() not in NOT_AUTHORS:
                out.append((name, m.group(2)))
            pos = YEAR_TAIL.match(text, m.end()).end()  # "Smith, 2019, 2020b, Jones 2021"
        if whole and pos < len(text.rstrip(" .")):
            return []
    return out


def _name_words(name: str) -> list[str]:
    """A name's folded words without particles: 'van der Berg' -> ['berg'], 'Tandy-Connor' -> ['tandy', 'connor']."""
    return [w for w in _fold(name).split() if w not in NAME_PARTICLES]


def _acronym(entry: str) -> str:
    """Initials of a corporate author: 'National Human Genome Research Institute (2021). ...' -> 'NHGRI'."""
    author = re.split(r"\(|\.\s|,", entry, maxsplit=1)[0]
    return "".join(w[0] for w in re.findall(r"[A-Z][^\W\d_]*", author))


NARRATIVE_CITE_RE = re.compile(rf"({_PARTICLES}{_CAP})(?:\s+(?:et\s+al\.?|(?:and|&)\s+{_CAP}))?\s+"
                               rf"\((?:19|20)\d{{2}}[a-z]?\)")
# A table cell is read as a citation only with the marks of one: a comma before the year, "et al.", "and" or "&".
TABLE_CITE_CUE = re.compile(r",\s*(?:19|20)\d{2}|\bet\s+al\b|&|\band\b")


def _citation_consistency(body: list[tuple[int, str]], refs: list[Reference]) -> list[Finding]:
    """In-text citations with no matching bibliography entry, and entries the text never cites."""
    if not refs:
        return []
    out: list[Finding] = []
    ref_tokens = [(_entry_tokens(r.text), r.text, _acronym(r.text), r) for r in refs]
    numeric_max = 0
    cited_surnames: set[str] = set()
    narrative: set[str] = set()  # "Shenhar et al. (2025)": counts as citing once the text cites by author and year
    for i, line in body:
        for m in NARRATIVE_CITE_RE.finditer(line):
            narrative |= set(_name_words(m.group(1)))
        for m in NUMERIC_CITE_RE.finditer(line):
            for part in re.split(r"[,\s]+", m.group(1)):
                bounds = [int(x) for x in re.split(r"[-–]", part) if x.strip().isdigit()]
                numeric_max = max([numeric_max, *bounds])
        groups = [(g.group(1), g.start(), g.end(), False) for g in PAREN_GROUP_RE.finditer(line)]
        if line.lstrip().startswith("|"):  # a table's reference column: "| McLaren et al., 2016 |"
            groups += [(c.group(1), c.start(), c.end(), True)
                       for c in re.finditer(r"\|([^|()]*(?:19|20)\d{2}[^|()]*)(?=\|)", line)]
        for group, start, end, whole in groups:
            if whole and not TABLE_CITE_CUE.search(group):
                continue  # "| Longevity Variants 2026 |" names a module; "| Wang et al., 2010 |" cites
            for name, year in _author_year_citations(group, whole=whole):
                first = next((w for w in name.split() if w.lower() not in NAME_PARTICLES), name)
                key = "".join(_fold(first).split())
                cited_surnames |= {key, *_name_words(name)}  # every word: "Ultima Genomics" is cited as Ultima
                acronym = name if name.isupper() and len(name) > 1 else None
                found = [r for tokens, text, initials, r in ref_tokens
                         if year in text and (key in tokens or (acronym is not None and initials == acronym))]
                for r in found:
                    cited_surnames.update(_name_words(r.text[:120])[:1])
                if not found:
                    cited = re.search(rf"{re.escape(name)}.*?{year}", line[start:end])
                    if cited:  # the one citation, not the whole parenthesis
                        start, end = start + cited.start(), start + cited.end()
                    out.append(_with_quote(Finding(
                        check="citations", severity=Severity.major, line=i, excerpt=_excerpt(line, start, end),
                        message=f"The in-text citation '{name} {year}' has no bibliography entry with that surname "
                                f"and year.",
                        why="Readers cannot find the work it points to.",
                        suggestion="Add the entry, with its DOI, or correct the citation."), line, start, end))
    if numeric_max > len(refs):
        out.append(Finding(check="citations", severity=Severity.major,
                           message=f"The text cites reference [{numeric_max}], but the bibliography has only "
                                   f"{len(refs)} entries.",
                           why="At least one numbered citation points to no entry, so readers cannot find its source.",
                           suggestion="Renumber the citations, or restore the missing entries."))
    if cited_surnames:
        cited_surnames |= narrative
        for ref in refs:
            first_author = _name_words(ref.text[:120])[:1]
            if first_author and first_author[0] not in cited_surnames:
                out.append(_ref_finding(ref, Finding(
                    check="citations", severity=Severity.minor, line=ref.line, excerpt=ref.text[:100],
                    stage=Stage.writing.value, message="This bibliography entry is never cited in the text.",
                    why="Most journals list only works the text cites.",
                    suggestion="Cite each such entry where it supports a claim, or remove it.")))
    return out


# Venue rules, shared with manuscript-journal-adapt/scripts/venues.py.
VENUES_YAML = Path(__file__).resolve().parent.parent / "references" / "venues.yaml"


def load_venue_limits() -> dict[str, dict[str, float]]:
    """Length limits per venue key, following `inherits`; venues with no recorded limits are left out."""
    venues: dict[str, dict] = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))["venues"]

    def resolve(key: str) -> dict:
        entry = venues[key]
        parent = entry.get("inherits")
        return {**(resolve(parent) if parent else {}), **entry}

    return {key: resolve(key)["limits"] for key in venues if resolve(key).get("limits")}


def venue_name_and_url(venue: str) -> tuple[str, Optional[str]]:
    """The venue's name and its author-guidelines page as venues.yaml records them; the key itself if unknown."""
    try:
        venues: dict[str, dict] = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))["venues"]
    except (OSError, KeyError, TypeError, yaml.YAMLError):
        return venue, None
    entry, url = venues.get(venue) or {}, None
    seen: set[str] = set()
    while entry and url is None:
        url = entry.get("url")
        parent = entry.get("inherits")
        if not parent or parent in seen:
            break
        seen.add(parent)
        entry = venues.get(parent) or {}
    return (venues.get(venue) or {}).get("name") or venue, url


ARCHIVE_RE = re.compile(r"zenodo|10\.5281/|softwareheritage|swh:1:|figshare|10\.6084/|bioconductor|cran\.r-project",
                        re.IGNORECASE)


def _abstract_span(lines: list[str]) -> Optional[tuple[int, int]]:
    start = next((i for i, l in enumerate(lines) if ABSTRACT_HEADING.search(l.strip())), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if HEADING.match(lines[i].strip())), len(lines))
    return start + 1, end


ABSTRACT_PART = re.compile(r"^\s*(?:\*\*|__|\\textbf\s*\{)?\s*(?P<label>[A-Z][A-Za-z ,&/-]{2,40}?)\s*"
                           r"(?::\s*(?:\*\*|__|\})|(?:\*\*|__|\})\s*:|:)\s*")
WORD_RE = re.compile(r"[A-Za-z0-9][\w'-]*")
# A URL, an e-mail address or a DOI is one word, as a reader (and a count by spaces) sees it; split at its dots,
# slashes and @ it counted as five.
LINK_WORD_RE = re.compile(r"(?:\bhttps?://|\bwww\.)\S+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\b(?:doi:\s*)?10\.\d{4,9}/\S+",
                          re.IGNORECASE)


def _one_word_links(text: str) -> str:
    return LINK_WORD_RE.sub(" URL ", text)


def _count_words(text: str) -> int:
    return len(WORD_RE.findall(_one_word_links(text)))


def _abstract_parts(lines: list[str]) -> list[tuple[str, int]]:
    """(label, words after the label) for each labelled part of a structured abstract ("Motivation:", "Results:");
    empty unless at least two parts are labelled."""
    parts: list[tuple[str, int]] = []
    for line in lines:
        m = ABSTRACT_PART.match(line)
        if m:
            parts.append((m.group("label").strip(), _count_words(line[m.end():])))
        elif parts:
            parts[-1] = (parts[-1][0], parts[-1][1] + _count_words(line))
    return parts if len(parts) >= 2 else []


def _counted_parts(parts: list[tuple[str, int]]) -> str:
    named = [f"{label} {count}" for label, count in parts]
    listing = ", ".join(named[:-1]) + f" and {named[-1]}" if len(named) > 1 else named[0]
    return f" By part, the words after each label are: {listing}."


def _venue_findings(lines: list[str], body_words: int, abstract_words: Optional[int], venue: Optional[str],
                    text_lower: str, abstract_parts: Optional[list[tuple[str, int]]] = None) -> list[Finding]:
    out: list[Finding] = []
    if not ARCHIVE_RE.search(text_lower):
        # A cheap offline hint only: manuscript-reporting-check owns availability (what the venue requires,
        # whether accessions, DOIs and releases resolve), so the defect is graded there, once.
        out.append(Finding(check="availability", severity=Severity.info, stage=Stage.final.value,
                           section=WHOLE_MANUSCRIPT,
                           message="No archived copy of the software or data is cited (for example on Zenodo, "
                                   "Software Heritage, figshare, Bioconductor or CRAN).",
                           why="An archive and its DOI come once the code is final.",
                           suggestion="Whether the journal or the paper's reproducibility needs an archive is checked "
                                      "with the availability statement (manuscript-reporting-check)."))
    if re.search(r"leave[- ]one[- ]out", text_lower):
        first = next((i for i, l in enumerate(lines, start=1) if re.search(r"leave[- ]one[- ]out", l, re.IGNORECASE)),
                     None)
        out.append(Finding(check="validation", severity=Severity.info, line=first,
                           section=None if first else WHOLE_MANUSCRIPT,
                           message="The manuscript mentions leave-one-out validation.",
                           why="Some journals reject machine-learning papers validated by leave-one-out alone.",
                           suggestion="If that is the only validation, report the performance on an independent test "
                                      "set as well."))
    limits = load_venue_limits().get(venue or "")
    name, url = venue_name_and_url(venue) if venue else ("", None)
    guidelines = f" ({url})" if url else ""
    if limits:
        abstract_max, body_max = limits.get("abstract_words"), limits.get("body_words")
        returned_at = limits.get("over_limit_return")
        body_rule = (" The count runs from the start of the file to the reference list and includes the title, "
                     "headings, tables and back matter, so it is approximate.")
        if body_max is None:
            out.append(Finding(check="venue", severity=Severity.info, section=WHOLE_MANUSCRIPT,
                               message=f"No body length limit is recorded for {name}, so the body length was not "
                                       f"checked.",
                               suggestion=f"Check the length or page limit in the journal's author "
                                          f"guidelines{guidelines}."))
        if abstract_max is not None and abstract_words is not None and abstract_words > abstract_max:
            # A page that recommends a length and allows flexibility (`abstract_words_kind: recommended`) is quoted
            # as a recommendation, never turned into a requirement.
            recommended = limits.get("abstract_words_kind") == "recommended"
            out.append(Finding(check="venue", severity=Severity.major, section="Abstract",
                               message=f"The Abstract has {abstract_words} words, and {name} "
                                       f"{'recommends' if recommended else 'asks for'} at most {abstract_max}. The "
                                       f"count includes everything between the Abstract heading and the next heading, "
                                       f"labels included." + (_counted_parts(abstract_parts) if abstract_parts else ""),
                               suggestion=f"Cut it to the {'recommended length' if recommended else 'limit'}, after "
                                          f"checking in the author guidelines{guidelines} which parts of a structured "
                                          f"abstract count."))
        if body_max is None:
            pass
        elif returned_at and body_words > returned_at * body_max:
            out.append(Finding(check="venue", severity=Severity.blocker, section=WHOLE_MANUSCRIPT,
                               message=f"The body has about {body_words} words, more than "
                                       f"{round(100 * (returned_at - 1))}% over the limit of about {body_max} for "
                                       f"{name}, and the journal returns such manuscripts without review." + body_rule,
                               suggestion="Move material to the supplement."))
        elif body_words > body_max:
            out.append(Finding(check="venue", severity=Severity.major, section=WHOLE_MANUSCRIPT,
                               message=f"The body has about {body_words} words, over the limit of about {body_max} "
                                       f"for {name}." + body_rule,
                               suggestion=f"Trim it, or check the page count in the journal's template{guidelines}."))
    elif venue:
        out.append(Finding(check="venue", severity=Severity.info, section=WHOLE_MANUSCRIPT,
                           message=f"No length limits are recorded for {name}, so the length was not checked.",
                           suggestion=f"Check the limits in the journal's author guidelines{guidelines}."))
    return out


def _dashes(lines: list[str], stop_line: Optional[int]) -> list[Finding]:
    count = sum(l.count("—") for l in lines[: (stop_line or len(lines) + 1) - 1])
    if count == 0:
        return []
    first = next(i for i, l in enumerate(lines, start=1) if "—" in l)
    at = lines[first - 1].index("—")
    return [_with_quote(Finding(
        check="style", severity=Severity.minor, line=first,
        message=f"The body uses {count} em dash{'es' if count > 1 else ''}; the first is quoted here.",
        why="Readers and screeners treat dense em-dash use as a sign of text written by a language model.",
        suggestion="Use commas, colons, parentheses or two sentences instead."), lines[first - 1], at, at + 1)]


# --------------------------------------------------------------------------------------------------
# Online reference resolution
# --------------------------------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


GREEK = ("alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi pi rho sigma tau upsilon phi "
         "chi psi omega").split()
TEX_SPECIAL = {"ss": "ß", "o": "ø", "O": "Ø", "ae": "æ", "AE": "Æ", "oe": "œ", "OE": "Œ", "aa": "å", "AA": "Å",
               "l": "ł", "L": "Ł", "i": "i", "j": "j", **dict(zip(GREEK, "αβγδεζηθικλμνξπρστυφχψω")),
               **dict(zip((g.capitalize() for g in GREEK), "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ"))}


def _delatex(s: str) -> str:
    """LaTeX accents, commands, braces and math dollars out of a title (cite-check's reading)."""
    s = s.replace("\\\\", " ")
    s = re.sub(r"\\([`'^\"~=.])\s*", "", s)
    s = re.sub(r"\\[uvHtcdbkr](?![A-Za-z])\s*", "", s)
    s = re.sub(r"\\([&%$#_{}])", r"\1", s)
    s = re.sub(r"\\([A-Za-z]+)\s*", lambda m: TEX_SPECIAL.get(m.group(1), " "), s)
    return s.replace("~", " ").replace("{", "").replace("}", "").replace("$", "")


def _strict_title(s: str) -> str:
    """A title compared strictly: LaTeX and HTML out, NFKD with accents dropped, casefolded, every character that
    is not a letter or digit a space."""
    s = unicodedata.normalize("NFKD", _fetched(_delatex(s)))
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def _similarity(title: str, entry: str) -> float:
    """How much of the resolved title appears in the citation text (0..1)."""
    t, e = _norm(title).split(), set(_norm(entry).split())
    if not t:
        return 0.0
    found = [w in e for w in t]
    for i in range(len(t) - 1):  # a word that markup split in two ("Pharm<scp>CAT</scp>" read "Pharm CAT")
        if not (found[i] and found[i + 1]) and t[i] + t[i + 1] in e:
            found[i] = found[i + 1] = True
    token = sum(found) / len(t)
    return max(token, SequenceMatcher(None, _norm(title), _norm(entry)).find_longest_match().size / max(len(_norm(title)), 1))


# One run asks each URL once, and spaces its requests to one host: doi.org 1 s, NCBI 0.4 s (under its three a
# second without a key), a web page's host 0.5 s. The registries' own pacing (arXiv 3 s, the per-reference pause)
# stays where it is.
HOST_GAP = {"doi.org": 1.0, "eutils.ncbi.nlm.nih.gov": 0.4}
API_HOSTS = {"api.crossref.org", "api.datacite.org", "export.arxiv.org", "www.ebi.ac.uk", "api.biorxiv.org",
             "www.medrxiv.org", "www.biorxiv.org", "arxiv.org"}
_ASKED: dict[tuple, Optional[httpx.Response]] = {}
_LAST_ASK: dict[str, float] = {}


def _space(url: str) -> None:
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    gap = HOST_GAP.get(host, 0.0 if host in API_HOSTS else 0.5)
    last = _LAST_ASK.get(host)
    if gap and last is not None and time.monotonic() - last < gap:
        time.sleep(gap - (time.monotonic() - last))
    _LAST_ASK[host] = time.monotonic()


def _get(client: httpx.Client, url: str, accept: Optional[str] = None, follow: bool = False,
         **params: str) -> Optional[httpx.Response]:
    """GET with retries on 429 and 5xx, asked once per run. None means the service did not answer, never "not
    found"."""
    key = ("GET", url, accept, follow, tuple(sorted(params.items())))
    if key in _ASKED:
        return _ASKED[key]
    r = None
    for attempt in range(3):
        _space(url)
        try:
            r = client.get(url, params=params or None, headers={"Accept": accept} if accept else None,
                           follow_redirects=follow)
        except httpx.HTTPError:
            r = None
            break
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            r = None
            continue
        break
    _ASKED[key] = r
    return r


def _head(client: httpx.Client, url: str, follow: bool = False) -> Optional[httpx.Response]:
    key = ("HEAD", url, None, follow, ())
    if key not in _ASKED:
        _space(url)
        try:
            _ASKED[key] = client.head(url, follow_redirects=follow)
        except httpx.HTTPError:
            _ASKED[key] = None
    return _ASKED[key]


def _json_message(r: Optional[httpx.Response]) -> Optional[dict]:
    if r is None or r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    return data.get("message") if isinstance(data, dict) and isinstance(data.get("message"), dict) else None


# --- names ------------------------------------------------------------------------------------------------
# Registries and citation styles spell the same person differently: initials or given names, diacritics or
# transliterations (Müller, Mueller, Muller), particles (van der, de la), hyphens and apostrophes. Surnames of two
# letters (Ng, Li, Xu) are names like any other.

NAME_PARTICLES = {"van", "von", "der", "den", "de", "del", "della", "di", "da", "dos", "das", "du", "la", "le", "ter",
                  "ten", "zu", "y", "e", "bin", "ibn"}
NAME_STOPWORDS = {"et", "al", "and", "others", "eds", "ed", "editor", "editors", "in", "the", "of", "with", "jr", "sr",
                  "ii", "iii", "iv"}
GROUP_AUTHOR_RE = re.compile(r"\b(?:consortium|collaborat\w*|group|project|network|initiative|team|committee|"
                             r"investigators?|society|association|alliance|council)\b", re.IGNORECASE)
ET_AL_RE = re.compile(r"\bet\.?\s*al\b|\band\s+(?:\d+\s+)?others\b|\.\.\.|…", re.IGNORECASE)
_TRANSLIT = str.maketrans({"ß": "ss", "ẞ": "ss", "ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
                           "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "þ": "th", "Þ": "Th", "ı": "i"})
_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})
NAME_TOKEN_RE = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")


def _fold(text: str) -> str:
    """Lower-case ASCII letters and spaces: diacritics dropped, apostrophes removed, other marks to spaces."""
    text = unicodedata.normalize("NFKD", text.translate(_TRANSLIT))
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z]+", " ", re.sub(r"['’`ʼ]", "", text)).strip()


def _surname_keys(family: str) -> set[str]:
    """Spellings under which a family name can appear in a citation."""
    keys: set[str] = set()
    for variant in {family, family.translate(_UMLAUTS)}:
        words = _fold(variant).split()
        core = [w for w in words if w not in NAME_PARTICLES] or words
        if core:
            keys.add("".join(core))
            keys.update(w for w in core if len(w) > 1)
    return keys


def _entry_tokens(text: str) -> set[str]:
    tokens = set(_name_tokens(text))  # the earlier matching, kept
    for variant in {text, text.translate(_UMLAUTS)}:
        words = _fold(variant).split()
        tokens.update(words)
        tokens.update(a + b for a, b in zip(words, words[1:]))
    return tokens


def _split_author(name: str) -> tuple[str, str]:
    family, _, given = name.partition(", ")
    return family, given


def _crossref_authors(msg: dict) -> list[str]:
    out = []
    for a in msg.get("author") or []:
        if a.get("family"):
            out.append(f"{a['family']}, {a['given']}" if a.get("given") else a["family"])
        elif a.get("name"):
            out.append(a["name"])
    return out[:200]


def _pubmed_author(name: str) -> str:
    """'Lambert SA' -> 'Lambert, SA'; collective names stay whole."""
    parts = name.split()
    if len(parts) > 1 and parts[-1].isupper() and len(parts[-1]) <= 4:
        return f"{' '.join(parts[:-1])}, {parts[-1]}"
    return name


def _given_first_author(name: str) -> str:
    """'Samuel A. Lambert' -> 'Lambert, Samuel A.'; particles stay with the family name."""
    parts = name.split()
    if len(parts) < 2:
        return name
    i = len(parts) - 1
    while i > 1 and parts[i - 1].lower() in NAME_PARTICLES:
        i -= 1
    return f"{' '.join(parts[i:])}, {' '.join(parts[:i])}"


def _author_segment(entry: str, title: Optional[str]) -> Optional[str]:
    """The citation's text before its title, where every common style puts the authors; None if not found."""
    if not title:
        return None
    title_words = _fold(title).split()
    words: list[tuple[str, int]] = []
    for m in NAME_TOKEN_RE.finditer(entry):
        words.extend((w, m.start()) for w in _fold(m.group(0)).split())
    plain = [w for w, _ in words]
    for size in (4, 3, 2):
        probe = title_words[:size]
        if len(probe) < min(size, len(title_words)) or not probe:
            continue
        for i in range(len(plain) - len(probe) + 1):
            if plain[i:i + len(probe)] == probe:
                return entry[:words[i][1]]
    return None


def _names_listed(names: list[str], most: int = 8) -> str:
    """'A, B and C', or 'A, B, ... and 4 others' past `most` names."""
    if len(names) > most:
        return ", ".join(names[:most]) + f" and {len(names) - most} others"
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def _compare_authors(ref: Reference, source: str) -> None:
    """Compare the record's author list with the citation's, beyond the first author.

    Records an outcome in `author_check` and the details in `author_notes`. A difference is a metadata question
    for the authors to check against the publisher's page, never evidence that a reference was invented:
    registries cut long lists short, list editors or groups, and spell names their own way.
    """
    record = [_split_author(a) for a in ref.resolved_authors]
    people = [(f, g) for f, g in record if f and not GROUP_AUTHOR_RE.search(f)]
    segment = _author_segment(ref.text, ref.resolved_title)
    if not people or segment is None or GROUP_AUTHOR_RE.search(segment):
        ref.author_check = "not_compared"
        return
    # arXiv keeps names as the submitter typed them ("Kulaga Anton" beside "Ryangguk Kim"), so either part can be
    # the family name there.
    any_order = source == "arXiv"
    spans = [(m.group(0), _fold(m.group(0)), m.start(), m.end()) for m in NAME_TOKEN_RE.finditer(segment)]
    spans = [s for s in spans if s[1] and s[1] not in NAME_STOPWORDS]
    tokens = [(raw, folded) for raw, folded, _, _ in spans]

    def keys_of(family: str, given: str) -> set[str]:
        keys = _surname_keys(family)
        return keys | {w for w in _fold(given).split() if len(w) > 1} if any_order else keys

    def matches(i: int, keys: set[str]) -> bool:
        raw, folded = tokens[i]
        parts = folded.split()
        return "".join(parts) in keys or any(p in keys for p in parts) or \
            "".join(_fold(raw.translate(_UMLAUTS)).split()) in keys

    # Each record author is searched after the previous one's place, so two authors who share a surname (Wang P and
    # Wang K; Griffith M first and Griffith OL last) take different tokens; out-of-order lists fall back to any token
    # not yet taken.
    places: list[Optional[int]] = []
    taken: set[int] = set()
    cursor = 0
    for family, given in people:
        keys = keys_of(family, given)
        place = next((i for i in range(cursor, len(tokens)) if i not in taken and matches(i, keys)), None)
        if place is None:
            place = next((i for i in range(len(tokens)) if i not in taken and matches(i, keys)), None)
        places.append(place)
        if place is not None:
            taken.add(place)
            cursor = place + 1
    matched = [i for i, p in enumerate(places) if p is not None]
    notes: list[str] = []
    level = "consistent"
    if not matched:
        ref.author_check, ref.author_notes = "differs", [f"No author on the {source} record appears before the title."]
        return
    last = max(matched)
    gaps = [people[i][0] for i in range(last + 1) if places[i] is None]
    if gaps:
        notes.append(f"{_names_listed(gaps)} {'is' if len(gaps) == 1 else 'are'} on the {source} record but not in "
                     f"the entry's author list.")
        level = "differs"
    if not ET_AL_RE.search(segment) and last < len(people) - 1:
        notes.append(f"The entry names {len(matched)} of the record's {len(people)} authors and does not say "
                     f"'et al.'")
        level = "differs" if level == "differs" else "omits"
    known: set[str] = set()
    for f, g in record:
        given_words = _fold(g).split()
        known |= _surname_keys(f) | set(given_words) | set(_fold(f).split()) | {"".join(given_words)}
    used = set(taken)
    surname_first = min(used) == 0
    record_surnames = set().union(*(_surname_keys(f) for f, _ in people))

    def separated(i: int, j: int, comma: bool = True) -> bool:
        """A person boundary between tokens i < j: a semicolon, '&', 'and' or (unless allowed) a comma."""
        between = segment[spans[i][3]:spans[j][2]]
        return bool(re.search(r"[,;&]|\band\b" if comma else r"[;&]|\band\b", between, re.IGNORECASE))

    def given_run(place: int) -> list[int]:
        """The tokens that spell the given names of the author cited at `place`, in citation order."""
        run: list[int] = []
        if surname_first:
            k = place + 1
            if k < len(tokens) and k not in used and not separated(place, k, comma=False) \
                    and not matches(k, record_surnames):
                run.append(k)
                k += 1
                while k < len(tokens) and k not in used and not separated(k - 1, k):
                    run.append(k)
                    k += 1
        else:
            k = place - 1
            while k >= 0 and k not in used and not separated(k, k + 1):
                run.insert(0, k)
                k -= 1
        return [k for k in run if not (tokens[k][1] in NAME_PARTICLES and tokens[k][0].islower())]  # "E." is an initial

    runs = {place: given_run(place) for place in used}
    given_slots = {k for run in runs.values() for k in run}
    if surname_first and len(re.findall(r"\band\b", segment)) >= 2 and "&" not in segment:
        # BibTeX style ("Family, Given and Family, Given"): the given name of an author missing from the record
        # follows that author's surname after a bare comma, so it is not a further author.
        given_slots |= {k for k in range(1, len(tokens)) if k not in used and k - 1 not in used | given_slots
                        and not separated(k - 1, k, comma=False) and re.fullmatch(r"\s*,\s*", segment[
                            spans[k - 1][3]:spans[k][2]])}
    unknown = [(i, t) for i, (t, f) in enumerate(tokens)
               if i not in used and i not in given_slots and not (len(t) <= 3 and t.isupper())
               and len(f.replace(" ", "")) > 1 and f not in NAME_PARTICLES and "".join(f.split()) not in known
               and not set(f.split()) & known and _fold(t.translate(_UMLAUTS)) not in known]
    if unknown:
        names = _names_listed([t for _, t in unknown])
        if len(matched) == len(people) and all(i > max(used) for i, _ in unknown):
            notes.append(f"The {source} record lists {len(people)} author{'s' if len(people) > 1 else ''}, and the "
                         f"entry also names {names}. Registry lists can stop short, so check the publisher's page if "
                         f"it matters.")
        else:
            notes.append(f"The entry's author list names {names}, {'who is' if len(unknown) == 1 else 'who are'} "
                         f"not on the {source} record.")
            level = "differs"
    for (family, given), place in zip(people, places):
        if place is None or not runs.get(place):
            continue
        shown, who = given, family
        if any_order:  # the record's given name is whichever part the citation did not use as the surname
            used_parts = set(tokens[place][1].split()) | {"".join(tokens[place][1].split())}
            given = " ".join(w for w in _fold(f"{family} {given}").split() if w not in used_parts)
            shown, who = f"{shown} {family}", tokens[place][0]
        record_given = _fold(given).split()
        if not record_given:
            continue
        raw, cited = tokens[runs[place][0]]
        if cited[:1] != record_given[0][:1]:
            notes.append(f"For {who}, the entry gives the initial {cited[:1].upper()} and the record gives "
                         f"{shown.rstrip('.')}.")
            level = level if level != "consistent" else "initials"
        elif len(cited) > 1 and len(record_given[0]) > 1 and not (len(raw) <= 3 and raw.isupper()) \
                and not (cited.startswith(record_given[0]) or record_given[0].startswith(cited)):
            notes.append(f"For {who}, the entry gives the given name {raw} and the record gives {shown.rstrip('.')}.")
            level = level if level != "consistent" else "initials"
    ref.author_check = {"consistent": "consistent", "omits": "differs", "initials": "differs"}.get(level, "differs")
    ref.author_notes = notes
    ref.author_severity = {"differs": "minor"}.get(level, "info") if ref.author_check == "differs" else None


# --- retractions, expressions of concern, withdrawals --------------------------------------------------------

RETRACTION_UPDATES = ("retraction", "withdrawal", "removal")  # Crossref `updated-by` types (incl. partial_retraction)
WITHDRAWN_RE = re.compile(r"\b(?:has|have) been withdrawn\b|\b(?:is|was|being) withdrawn\b|\bwithdrawn by\b|"
                          r"\bwithdrawn (?:due to|because|for|pending|as|at)\b|^\W*withdrawn\b|\bwithdrawal of this\b",
                          re.IGNORECASE)
RESTORED_RE = re.compile(r"\b(?:erroneously|mistakenly|accidentally|inadvertently)\b[^.]{0,40}\bwithdr|"
                         r"\bwithdr\w*\b[^.]{0,40}\b(?:in error|by mistake|erroneously|mistakenly)\b", re.IGNORECASE)
EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.(\d{4}\.\d{4,5})(?:v\d+)?$", re.IGNORECASE)
RXIV_DOI_RE = re.compile(r"^10\.1101/(?:\d{4}\.\d{2}\.\d{2}\.)?\d{6,}(?:v\d+)?$")
_ARXIV_LAST = [0.0]


def _withdrawn(text: str) -> bool:
    return bool(WITHDRAWN_RE.search(text)) and not RESTORED_RE.search(text)


def _crossref_notice(msg: dict) -> tuple[str, str, Optional[str]]:
    """('retracted' | 'concern' | 'none', source, notice DOI) from a Crossref work record.

    Crossref carries Retraction Watch's records in `updated-by` (source "retraction-watch") beside publishers'
    own notices. A retraction outranks an expression of concern on the same work.
    """
    updates = msg.get("updated-by") or []
    for state, test in (("retracted", lambda k: any(r in k for r in RETRACTION_UPDATES)),
                        ("concern", lambda k: "concern" in k)):
        for u in updates:
            if test(str(u.get("type", "")).lower()):
                origin = u.get("source")
                return state, "crossref" + (f" ({origin})" if origin else ""), u.get("DOI")
    title = _fetched((msg.get("title") or [""])[0])
    if re.match(r"\s*(?:retracted|withdrawn)\b", title, re.IGNORECASE):
        return "retracted", "crossref (title)", None
    return "none", "crossref", None


def _europepmc_record(client: httpx.Client, doi: Optional[str], pmid: Optional[str]) -> Optional[dict]:
    """Europe PMC's record for a DOI or PMID: {} when it holds none, None when it did not answer."""
    query = f'DOI:"{doi}"' if doi else f"EXT_ID:{pmid} AND SRC:MED"
    r = _get(client, EUROPEPMC_SEARCH, query=query, format="json", resultType="core", pageSize="1")
    if r is None or r.status_code != 200:
        return None
    try:
        hits = r.json().get("resultList", {}).get("result", [])
    except (ValueError, AttributeError):
        return None
    for hit in hits:
        if (doi and (hit.get("doi") or "").lower() == doi.lower()) or (not doi and str(hit.get("pmid")) == str(pmid)):
            return hit
    return {}


def _europepmc_notice(hit: dict) -> tuple[str, Optional[str]]:
    """Europe PMC marks a retracted paper by publication type and links notices as comment-corrections."""
    types = [t.lower() for t in (hit.get("pubTypeList") or {}).get("pubType") or []]
    links = (hit.get("commentCorrectionList") or {}).get("commentCorrection") or []
    for state, prefixes in (("retracted", ("retraction in", "partial retraction in")),
                            ("concern", ("expression of concern in",))):
        for link in links:
            if (link.get("type") or "").lower().startswith(prefixes):
                return state, link.get("reference") or link.get("id")
        if state == "retracted" and "retracted publication" in types:
            return state, None
    return "none", None


def _check_retraction(client: httpx.Client, ref: Reference, first: Optional[tuple[str, str, Optional[str]]]) -> None:
    """Ask a second registry unless the first already found a retraction; any notice found wins.

    Crossref (with Retraction Watch) and PubMed each miss retractions the other records, so a clean answer from
    one source does not end the search. A reference no registry answered for stays `not_checked`, never clean.
    """
    answered: list[str] = []
    state, notice, found_by = "none", None, None
    if first is not None:
        answered.append(first[0])
        if first[1] != "none":
            state, found_by, notice = first[1], first[0], first[2]
    if state != "retracted":
        hit = _europepmc_record(client, ref.doi, ref.pmid)
        if hit is None:
            ref.lookup_notes.append("Europe PMC did not answer; retraction checked with fewer sources.")
        elif hit:
            answered.append("europepmc")
            second, second_notice = _europepmc_notice(hit)
            if second == "retracted" or (second == "concern" and state == "none"):
                state, found_by, notice = second, "europepmc", second_notice
    if not answered:
        ref.retraction = "not_checked"
        return
    ref.retraction = {"none": "none_found"}.get(state, state)
    ref.retraction_source = found_by if state != "none" else "+".join(dict.fromkeys(answered))
    ref.retraction_notice = notice
    if state in ("retracted", "concern") and ref.status == "resolved":
        ref.status = state


# --- registries ----------------------------------------------------------------------------------------------

def _published_version(client: httpx.Client, ref: Reference, doi: Optional[str], source: str,
                       venue: Optional[str] = None) -> None:
    """Record where a cited preprint was published, with the published record's metadata compared."""
    pv = PublishedVersion(doi=doi.lower() if doi else None, source=source, venue=venue)
    if doi:
        msg = _json_message(_get(client, f"https://api.crossref.org/works/{doi}"))
        if msg is None:
            ref.lookup_notes.append(f"Crossref did not return the published version {doi}; compare it by hand.")
        else:
            pv.title = _fetched((msg.get("title") or [""])[0])
            pv.venue = (msg.get("container-title") or [venue])[0]
            pv.venue = _fetched(pv.venue) if pv.venue else pv.venue
            parts = (msg.get("issued") or {}).get("date-parts") or [[None]]
            pv.year = str(parts[0][0]) if parts[0][0] else None
            pv.title_similarity = round(_similarity(pv.title, ref.resolved_title or ref.text), 2) if pv.title else None
            theirs = {k for a in _crossref_authors(msg) for k in _surname_keys(_split_author(a)[0])}
            ours = {k for a in ref.resolved_authors for k in _surname_keys(_split_author(a)[0])} or _entry_tokens(ref.text)
            pv.shared_authors = bool(theirs & ours) if theirs else None
            state, _, _ = _crossref_notice(msg)
            pv.retraction = {"none": "none_found"}.get(state, state)
            pv.metadata_checked = True
    ref.published_version = pv


def _rxiv_details(client: httpx.Client, ref: Reference, msg: dict) -> None:
    """bioRxiv/medRxiv: the server's own record of a later publication and of a withdrawal."""
    servers = ["medrxiv", "biorxiv"] if "medrxiv" in json.dumps(msg.get("institution") or "").lower() else \
        ["biorxiv", "medrxiv"]
    for server in servers:
        r = _get(client, f"https://api.biorxiv.org/details/{server}/{ref.doi}")
        if r is None or r.status_code != 200:
            ref.lookup_notes.append(f"The {server} API did not answer.")
            continue
        try:
            versions = r.json().get("collection") or []
        except (ValueError, AttributeError):
            versions = []
        if not versions:
            continue
        latest = versions[-1]
        ref.withdrawn = _withdrawn(f"{latest.get('title', '')}. {latest.get('abstract', '')}")
        ref.withdrawn_source = f"{server}:details"
        published = str(latest.get("published") or "")
        if ref.published_version is None and published.startswith("10."):
            _published_version(client, ref, published, f"{server}:published")
        return


def _resolve_doi(client: httpx.Client, ref: Reference) -> Optional[tuple[str, str, Optional[str]]]:
    """Crossref first; DataCite for dataset, software and preprint DOIs; doi.org for any other agency."""
    r = _get(client, f"https://api.crossref.org/works/{ref.doi}")
    msg = _json_message(r)
    if msg is not None:
        ref.resolved_title = _fetched((msg.get("title") or [""])[0])
        parts = (msg.get("issued") or {}).get("date-parts") or [[None]]
        ref.resolved_year = str(parts[0][0]) if parts[0][0] else None
        authors = msg.get("author") or []
        ref.resolved_first_author = (authors[0].get("family") or authors[0].get("name")) if authors else None
        ref.resolved_authors = _crossref_authors(msg)
        state, source, notice = _crossref_notice(msg)
        ref.status = state if state != "none" else "resolved"
        ref.is_preprint = msg.get("type") == "posted-content" or msg.get("subtype") == "preprint"
        if ref.is_preprint:
            later = [t.get("id") for t in (msg.get("relation") or {}).get("is-preprint-of", []) if t.get("id")]
            if later:
                _published_version(client, ref, later[0], "crossref:is-preprint-of")
            if RXIV_DOI_RE.match(ref.doi or ""):
                _rxiv_details(client, ref, msg)
        return source, state, notice
    if r is not None and r.status_code == 404 and _resolve_datacite(client, ref):
        return None
    _resolve_csl(client, ref)
    return None


CSL = "application/vnd.citationstyles.csl+json"


def _csl_record(client: httpx.Client, doi: str) -> tuple[str, Optional[dict], str]:
    """("ok" | "dead" | "unknown", the CSL record, why): doi.org hands the request to whichever agency
    registered the DOI (Crossref, DataCite, mEDRA, JaLC, ...)."""
    r = _get(client, f"https://doi.org/{urllib.parse.quote(doi, safe='/()._;:-')}", accept=CSL, follow=True)
    if r is None:
        return "unknown", None, "doi.org did not answer"
    if r.status_code == 406:
        return "unknown", None, "the DOI's registration agency gives no record to compare"
    if r.status_code in (404, 410) or 400 <= r.status_code < 500 and r.status_code != 429:
        return "dead", None, f"doi.org answered HTTP {r.status_code}"
    if r.status_code != 200:
        return "unknown", None, f"doi.org answered HTTP {r.status_code}"
    try:
        rec = r.json()
    except ValueError:
        return "unknown", None, "doi.org's answer is not a CSL record"
    return ("ok", rec, "") if isinstance(rec, dict) else ("unknown", None, "doi.org's answer is not a CSL record")


def _csl_title(rec: dict) -> Optional[str]:
    title = rec.get("title")
    title = title[0] if isinstance(title, list) and title else title
    return _fetched(title) if isinstance(title, str) and title.strip() else None


def _resolve_csl(client: httpx.Client, ref: Reference) -> None:
    """Neither Crossref nor DataCite has the DOI: ask doi.org for its agency's CSL record, so its title is still
    compared. A DOI doi.org does not know is unresolved; an agency that gives no record is not assessed."""
    state, rec, why = _csl_record(client, ref.doi or "")
    if state == "dead":
        ref.status = "unresolved"
        return
    if state == "unknown" or rec is None or not _csl_title(rec):
        ref.status = "lookup_failed"
        ref.lookup_notes.append(f"Crossref and DataCite hold no record and {why or 'the record has no title'}; "
                                "the title was not compared.")
        return
    ref.resolved_title = _csl_title(rec)
    parts = ((rec.get("issued") or {}).get("date-parts") or [[None]])
    ref.resolved_year = str(parts[0][0]) if parts and parts[0] and parts[0][0] else None
    names = [f"{a['family']}, {a['given']}" if a.get("family") and a.get("given") else a.get("family") or
             a.get("literal") or "" for a in rec.get("author") or [] if isinstance(a, dict)]
    ref.resolved_authors = [n for n in names if n][:200]
    ref.resolved_first_author = _split_author(ref.resolved_authors[0])[0] if ref.resolved_authors else None
    ref.status = "resolved"
    ref.lookup_notes.append("doi.org gave the record (the DOI is registered with neither Crossref nor DataCite); "
                            "no retraction registry covers it.")


def _resolve_datacite(client: httpx.Client, ref: Reference) -> bool:
    r = _get(client, f"https://api.datacite.org/dois/{ref.doi}")
    if r is None or r.status_code != 200:
        return False
    try:
        attrs = r.json()["data"]["attributes"]
    except (ValueError, KeyError, TypeError):
        return False
    title = ((attrs.get("titles") or [{}])[0]).get("title")
    ref.resolved_title = _fetched(title) if isinstance(title, str) else title
    ref.resolved_year = str(attrs["publicationYear"]) if attrs.get("publicationYear") else None
    names = []
    for c in attrs.get("creators") or []:
        family, given = c.get("familyName"), c.get("givenName")
        names.append(f"{family}, {given}" if family and given else family or c.get("name") or "")
    ref.resolved_authors = [n for n in names if n][:200]
    ref.resolved_first_author = _split_author(ref.resolved_authors[0])[0] if ref.resolved_authors else None
    kind = ((attrs.get("types") or {}).get("resourceTypeGeneral") or "").lower()
    ref.is_preprint = kind == "preprint"
    ref.status = "resolved"
    ref.lookup_notes.append(f"DataCite record ({kind or 'unknown type'}); DataCite carries no retraction notices.")
    return True


EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
NCBI_TOOL = "manuscript-skills"  # NCBI's `tool=`: names the software, never a person


def _resolve_pmid(client: httpx.Client, ref: Reference) -> Optional[tuple[str, str, Optional[str]]]:
    r = _get(client, EUTILS, db="pubmed", id=ref.pmid or "", retmode="json", tool=NCBI_TOOL)
    if r is not None and 400 <= r.status_code < 500:
        ref.status = "unresolved"
        return None
    if r is None or r.status_code != 200:
        ref.status = "lookup_failed"
        ref.lookup_notes.append("PubMed did not answer.")
        return None
    try:
        doc = r.json().get("result", {}).get(ref.pmid or "", {})
    except (ValueError, AttributeError):
        doc = {}
    if not doc or "error" in doc:
        ref.status = "unresolved"
        return None
    ref.resolved_title = _fetched(doc.get("title", ""))
    ref.resolved_year = (doc.get("pubdate") or "")[:4] or None
    authors = doc.get("authors") or []
    ref.resolved_first_author = authors[0]["name"] if authors else None  # "Lambert SA"
    ref.resolved_authors = [_pubmed_author(a.get("name", "")) for a in authors if a.get("name")][:200]
    retracted = "Retracted Publication" in (doc.get("pubtype") or [])
    ref.status = "retracted" if retracted else "resolved"
    return "pubmed", "retracted" if retracted else "none", None


def _arxiv_error(entry: str, title: str) -> bool:
    """arXiv answers a malformed id with an entry whose id is under /api/errors, titled Error, and a
    well-formed id that does not exist with no entry. A paper whose title merely contains "Error" is a paper."""
    entry_id = re.search(r"<id>(.*?)</id>", entry, re.DOTALL)
    if entry_id and "/api/errors" in entry_id.group(1):
        return True
    return " ".join(title.split()) == "Error" and not (entry_id and "/abs/" in entry_id.group(1))


def _resolve_arxiv(client: httpx.Client, ref: Reference) -> None:
    wait = 3.1 - (time.monotonic() - _ARXIV_LAST[0])  # arXiv asks for 3 s between calls
    if wait > 0:
        time.sleep(wait)
    _ARXIV_LAST[0] = time.monotonic()
    r = _get(client, "https://export.arxiv.org/api/query", id_list=ref.arxiv or "")
    if r is None or r.status_code != 200:
        ref.status = "lookup_failed"
        ref.lookup_notes.append("arXiv did not answer.")
        return
    entry = re.search(r"<entry>(.*?)</entry>", r.text, re.DOTALL)
    m = re.search(r"<title>(.*?)</title>", entry.group(1), re.DOTALL) if entry else None
    if not m or _arxiv_error(entry.group(1), m.group(1)):
        ref.status = "unresolved"
        return
    body = entry.group(1)

    def field(name: str) -> Optional[str]:
        found = re.search(rf"<arxiv:{name}[^>]*>(.*?)</arxiv:{name}>", body, re.DOTALL)
        return " ".join(found.group(1).split()) if found else None

    ref.resolved_title = " ".join(m.group(1).split())
    year = re.search(r"<published>(\d{4})", body)
    ref.resolved_year = year.group(1) if year else None
    names = [" ".join(n.split()) for n in re.findall(r"<author>\s*<name>(.*?)</name>", body, re.DOTALL)]
    ref.resolved_first_author = names[0] if names else None  # name order varies
    ref.resolved_authors = [_given_first_author(n) for n in names][:200]
    ref.is_preprint = True
    ref.withdrawn = _withdrawn(field("comment") or "")
    ref.withdrawn_source = "arxiv:comment"
    ref.lookup_notes.append("arXiv records withdrawals, not retractions; retraction was not checked.")
    ref.status = "resolved"
    if field("doi"):
        _published_version(client, ref, field("doi"), "arxiv:doi", field("journal_ref"))
    elif field("journal_ref"):
        _published_version(client, ref, None, "arxiv:journal_ref", field("journal_ref"))
    elif not ref.withdrawn:
        _published_by_title(client, ref, field("comment"))


# "Accepted by EMNLP 2023", "accepted for publication in Bioinformatics", "To appear in Proc. ACL".
ARXIV_ACCEPTED_RE = re.compile(r"\b(?:accepted|to appear|published|appears?|appeared)\b[^.;]{0,25}?\b(?:by|at|in|to|for)"
                               r"\s+(?:the\s+)?(?P<venue>[A-Z][^;()]{1,80}?)\s*(?:[.;(]|$)", re.IGNORECASE)


def _crossref_title_search(client: httpx.Client, query: str, rows: int = 3) -> Optional[list[dict]]:
    """Crossref's best bibliographic matches for a query; None when Crossref did not answer."""
    msg = _json_message(_get(client, "https://api.crossref.org/works",
                             **{"query.bibliographic": query[:300], "rows": str(rows)}))
    return None if msg is None else [i for i in msg.get("items") or [] if isinstance(i, dict)]


def _published_by_title(client: httpx.Client, ref: Reference, comment: Optional[str]) -> None:
    """An arXiv preprint whose record names no DOI or journal: a venue in its comment, and a Crossref record with the
    same title and a shared author. Both are candidates to confirm; neither is a link the registries recorded."""
    accepted = ARXIV_ACCEPTED_RE.search(comment or "")
    hint = accepted.group("venue").strip() if accepted else None
    first = _split_author(ref.resolved_authors[0]) if ref.resolved_authors else ("", "")
    items = _crossref_title_search(client, f"{ref.resolved_title} {first[1]} {first[0]}")
    if items is None:
        ref.lookup_notes.append("Crossref did not answer the search for a published version.")
    ours = {k for a in ref.resolved_authors for part in _split_author(a) for k in _surname_keys(part)}
    for item in items or []:
        doi, title = str(item.get("DOI") or ""), _fetched((item.get("title") or [""])[0])
        if not doi or not title or item.get("type") == "posted-content" or doi.lower().startswith("10.48550/"):
            continue
        similarity = min(_similarity(title, ref.resolved_title or ""), _similarity(ref.resolved_title or "", title))
        theirs = {k for a in _crossref_authors(item) for k in _surname_keys(_split_author(a)[0])}
        if similarity >= 0.95 and theirs & ours:
            parts = (item.get("issued") or {}).get("date-parts") or [[None]]
            venue = (item.get("container-title") or [hint])[0]
            ref.published_version = PublishedVersion(
                doi=doi.lower(), title=title, venue=_fetched(venue) if venue else venue,
                year=str(parts[0][0]) if parts[0][0] else None, source="crossref:title-search",
                title_similarity=round(similarity, 2), shared_authors=True, comment=comment if hint else None,
                retraction={"none": "none_found"}.get(_crossref_notice(item)[0], _crossref_notice(item)[0]),
                metadata_checked=True)
            return
    if hint:
        ref.published_version = PublishedVersion(venue=hint, source="arxiv:comment", comment=comment)


def _title_candidate(client: httpx.Client, ref: Reference) -> None:
    """An identifier that does not resolve: the record Crossref finds for the entry's own text, as a candidate."""
    query = re.sub(rf"{DOI_RE.pattern}|{PMID_RE.pattern}|{ARXIV_RE.pattern}|https?://\S+", " ", ref.text,
                   flags=re.IGNORECASE)
    items = _crossref_title_search(client, query)
    if items is None:
        ref.lookup_notes.append("The Crossref title search did not answer.")
        return
    names_authors = not re.match(r"\(?(?:19|20)\d{2}", ref.text.strip())
    best: Optional[dict] = None
    for item in items:
        title = _fetched((item.get("title") or [""])[0])
        if not item.get("DOI") or not title:
            continue
        authors = _crossref_authors(item)
        first_shared = bool(authors) and bool(_surname_keys(_split_author(authors[0])[0]) & _entry_tokens(ref.text))
        candidate = {"doi": str(item["DOI"]).lower(), "title": title, "similarity": round(_similarity(title, ref.text), 2),
                     "first_author_shared": first_shared}
        if candidate["similarity"] < 0.5:  # a search always returns something; a distant title is no candidate
            continue
        candidate["strong"] = candidate["similarity"] >= 0.9 and (first_shared or not names_authors)
        if best is None or candidate["strong"]:
            best = candidate
        if candidate["strong"]:
            break
    ref._title_match = best
    ref.lookup_notes.append(
        f"Crossref title search: doi:{best['doi']} '{best['title']}' (title similarity {best['similarity']}, first "
        f"author shared: {'yes' if best['first_author_shared'] else 'no'})." if best else
        "A Crossref title search found no close record.")


def _search_crossref(client: httpx.Client, ref: Reference) -> None:
    """No identifier: ask Crossref for the best bibliographic match and report how well it fits."""
    items = _crossref_title_search(client, ref.text, rows=1)
    if items:
        ref.resolved_title = _fetched((items[0].get("title") or [""])[0])
        ref.doi = items[0].get("DOI")
        authors = items[0].get("author") or []
        ref.resolved_first_author = (authors[0].get("family") or authors[0].get("name")) if authors else None
    elif items is None:
        ref.lookup_notes.append("Crossref search did not answer.")
    ref.status = "no_identifier"


def _first_author_keys(ref: Reference) -> set[str]:
    if ref.resolved_authors:
        family, given = _split_author(ref.resolved_authors[0])
        if _record_source(ref) == "arXiv":  # name order as typed: either part can be the family name
            return _surname_keys(family) | {w for w in _fold(given).split() if len(w) > 1}
        return _surname_keys(family)
    # A bare name of unknown order (Crossref search, arXiv): any part longer than an initial.
    return {t for t in _fold(ref.resolved_first_author or "").split() if len(t) > 1}


def resolve_references(refs: list[Reference], search_unidentified: bool) -> None:
    _ASKED.clear()
    with httpx.Client(timeout=20, headers={"User-Agent": USER_AGENT}) as client:
        for ref in refs:
            arxiv_doi = ARXIV_DOI_RE.match(ref.doi or "")
            if arxiv_doi and not ref.arxiv:
                ref.arxiv = arxiv_doi.group(1)
            first, route = None, None
            if ref.doi and not arxiv_doi:
                first, route = _resolve_doi(client, ref), "doi"
            elif ref.pmid:
                first, route = _resolve_pmid(client, ref), "pmid"
            elif ref.arxiv:
                _resolve_arxiv(client, ref)
            elif search_unidentified:
                _search_crossref(client, ref)
            if route and ref.status in ("resolved", "retracted", "concern"):
                _check_retraction(client, ref, first)
            if ref.status == "unresolved" and search_unidentified:  # the entry's text leaves the machine
                _title_candidate(client, ref)
            # A BibTeX entry without an author field starts with its year: there is no list to compare.
            names_authors = not re.match(r"\(?(?:19|20)\d{2}", ref.text.strip())
            if ref.resolved_title:
                ref.title_similarity = round(_similarity(ref.resolved_title, ref.text), 2)
                if not names_authors and ref.resolved_authors:
                    ref.lookup_notes.append("The entry names no author, so authors were not compared with the record.")
                elif ref.resolved_first_author or ref.resolved_authors:
                    keys = _first_author_keys(ref)
                    ref.first_author_found = bool(keys) and bool(keys & _entry_tokens(ref.text))
                # A title that does not match is a different work; a first author that does not match, with
                # the title right, is usually a wrong author list (RefChecker flags both). A mismatch outranks a
                # retraction notice, which then belongs to the work the identifier points to, not the one cited.
                untitled = ref._bib_file is not None and not ref.cited_title  # nothing to compare the title with
                if ref.status in ("resolved", "retracted", "concern") and (
                        (ref.title_similarity < 0.6 and not untitled) or ref.first_author_found is False):
                    ref.status = "mismatch"
                if untitled:
                    ref.title_check = "no_title"
                elif ref.cited_title and ref.status in ("resolved", "retracted", "concern"):
                    same = _strict_title(ref.cited_title) == _strict_title(ref.resolved_title)
                    ref.title_check = "same" if same else "differs"
                if ref.status in ("resolved", "retracted", "concern") and ref.resolved_authors and names_authors:
                    _compare_authors(ref, _record_source(ref))
            ref.other_id_checks = [_check_other_id(client, ref, other) for other in ref.other_ids]
            if ref.url:
                ref.url_status = _url_status(client, ref.url)
            time.sleep(0.35)  # NCBI allows 3 req/s without a key; Crossref asks for politeness


def _fetched(title: str) -> str:
    """A title as a source returned it: HTML entities (`&amp;`) and HTML or JATS tags (Crossref's <i>, Wiley's
    <scp> small caps, MathML) removed. A publisher's pretty-printed XML puts line breaks around a tag, so
    "(Pharm\\n <scp>CAT</scp>\\n )" reads "(Pharm CAT)": the space inside brackets goes, and a word the markup split
    is matched by `_similarity`."""
    text = " ".join(re.sub(r"<[^>]+>", "", html.unescape(html.unescape(title))).split())
    return re.sub(r"\s+([)\]},.;:!?])", r"\1", re.sub(r"([(\[{])\s+", r"\1", text))


def _title_of(client: httpx.Client, kind: str, value: str) -> tuple[str, Optional[str], str]:
    """("ok" | "dead" | "unknown", the title, why) for one identifier, by its own registry."""
    if kind == "doi":
        msg = _json_message(_get(client, f"https://api.crossref.org/works/{value}"))
        if msg is not None and (msg.get("title") or [""])[0]:
            return "ok", _fetched(msg["title"][0]), ""
        state, rec, why = _csl_record(client, value)
        return (state, _csl_title(rec) if rec else None, why) if state != "ok" or (rec and _csl_title(rec)) else \
            ("unknown", None, "the record has no title")
    if kind == "pmid":
        r = _get(client, EUTILS, db="pubmed", id=value, retmode="json", tool=NCBI_TOOL)
        if r is None or r.status_code != 200:
            return ("dead", None, f"PubMed answered HTTP {r.status_code}") if r is not None and \
                400 <= r.status_code < 500 else ("unknown", None, "PubMed did not answer")
        try:
            doc = r.json()["result"].get(value) or {}
        except (ValueError, KeyError, TypeError, AttributeError):
            return "unknown", None, "PubMed's answer does not parse"
        return ("ok", _fetched(doc["title"]), "") if doc.get("title") and "error" not in doc else \
            ("dead", None, "no such PMID")
    if kind == "arxiv":
        r = _get(client, "https://export.arxiv.org/api/query", id_list=value)
        if r is None or r.status_code != 200:
            return "unknown", None, "arXiv did not answer"
        entry = re.search(r"<entry>(.*?)</entry>", r.text, re.DOTALL)
        m = re.search(r"<title>(.*?)</title>", entry.group(1), re.DOTALL) if entry else None
        if not m or _arxiv_error(entry.group(1), m.group(1)):
            return "dead", None, "no such arXiv id"
        return "ok", " ".join(m.group(1).split()), ""
    return "unknown", None, f"no registry for {kind}"


def _check_other_id(client: httpx.Client, ref: Reference, other: str) -> dict[str, Optional[str]]:
    """A further identifier of the same entry: does it resolve, and to the same work as the first?"""
    kind, _, value = other.partition(":")
    state, title, why = _title_of(client, kind, value)
    same = None
    if state == "ok" and title:
        against = ref.resolved_title or ref.cited_title
        same = None if not against else str(_strict_title(title) == _strict_title(against)
                                            or _similarity(title, against) >= 0.6).lower()
    return {"id": other, "state": state, "title": title, "why": why, "same_work": same}


def _url_status(client: httpx.Client, url: str) -> str:
    """"ok HTTP n", "dead HTTP n", "blocked HTTP 403" or "unknown ...": HEAD, then GET when HEAD does not answer
    2xx or 3xx; the status only, redirects followed."""
    r = _head(client, url, follow=True)
    if r is None or not 200 <= r.status_code < 400:
        r = _get(client, url, follow=True)
    if r is None:
        return "unknown: no answer"
    if 200 <= r.status_code < 400:
        return f"ok HTTP {r.status_code}"
    if r.status_code in (401, 403):
        return f"blocked HTTP {r.status_code}"
    if r.status_code == 429 or r.status_code >= 500:
        return f"unknown: HTTP {r.status_code}"
    return f"dead HTTP {r.status_code}"


def _record_source(ref: Reference) -> str:
    if ref.doi and not ARXIV_DOI_RE.match(ref.doi):
        return "DataCite" if any(n.startswith("DataCite") for n in ref.lookup_notes) else "Crossref"
    return "PubMed" if ref.pmid and not ref.arxiv else "arXiv"


def doi_url(doi: str) -> str:
    return f"https://doi.org/{doi}"


def identifier_url(ref: Reference) -> Optional[str]:
    """A link the authors can open for the entry's identifier: doi.org, PubMed or arXiv."""
    if ref.doi and not ARXIV_DOI_RE.match(ref.doi):
        return doi_url(ref.doi)
    if ref.pmid:
        return f"https://pubmed.ncbi.nlm.nih.gov/{ref.pmid}/"
    if ref.arxiv:
        return f"https://arxiv.org/abs/{ref.arxiv}"
    return doi_url(ref.doi) if ref.doi else None


def _identifier_phrase(ref: Reference) -> str:
    kind = ("DOI" if ref.doi and not ARXIV_DOI_RE.match(ref.doi) else "PubMed ID" if ref.pmid
            else "arXiv id" if ref.arxiv else "identifier")
    url = identifier_url(ref)
    return f"the {kind} {url}" if url else f"the {kind}"


def _share(similarity: Optional[float]) -> str:
    """How much of a record's title appears in the entry, in words."""
    return f"{round(100 * (similarity or 0))}% of its title appears in the entry"


SOURCE_WORDS = {"crossref": "Crossref", "crossref (retraction-watch)": "Crossref, from Retraction Watch's records",
                "crossref (title)": "Crossref, from the title of the record", "europepmc": "Europe PMC",
                "pubmed": "PubMed", "arxiv:comment": "arXiv's comment field", "biorxiv:details": "bioRxiv",
                "medrxiv:details": "medRxiv", "crossref:is-preprint-of": "Crossref",
                "biorxiv:published": "bioRxiv", "medrxiv:published": "medRxiv", "arxiv:doi": "arXiv",
                "arxiv:journal_ref": "arXiv's journal reference", "crossref:title-search": "a Crossref title search"}


def source_words(source: Optional[str]) -> str:
    """'crossref+europepmc' as 'Crossref and Europe PMC'."""
    names = [SOURCE_WORDS.get(part, part) for part in (source or "").split("+") if part]
    return " and ".join(names) if names else "the registry"


NO_IDENTIFIER = "The entry carries no DOI, PubMed ID or arXiv id."
ID_KIND_WORDS = {"doi": "the DOI", "pmid": "the PubMed ID", "arxiv": "the arXiv id"}


def id_url(kind: str, value: str) -> str:
    """A link the authors can open for one identifier ("doi", "pmid", "arxiv"; anything else is its own URL)."""
    return {"doi": doi_url(value), "pmid": f"https://pubmed.ncbi.nlm.nih.gov/{value}/",
            "arxiv": f"https://arxiv.org/abs/{value}"}.get(kind, value)


def _reference_findings(refs: list[Reference], online: bool = False, unidentified: str = "strict") -> list[Finding]:
    """Findings per reference. `unidentified="strict"` (the default) never lets an entry with no identifier pass:
    a Crossref match is a candidate to confirm, at least minor; "lax" lets a close match fall to info."""
    out: list[Finding] = []

    def add(ref: Reference, severity: Severity, message: str, suggestion: str, why: str = "",
            stage: Stage = Stage.now) -> None:
        out.append(_ref_finding(ref, Finding(check="references", severity=severity, line=ref.line,
                                             excerpt=ref.text[:140], message=message, why=why,
                                             suggestion=suggestion, stage=stage.value)))

    for ref in refs:
        ident = _identifier_phrase(ref)
        if ref.status == "unresolved":
            match = ref._title_match
            if match and match["strong"]:
                add(ref, Severity.major,
                    f"{ident[0].upper()}{ident[1:]} does not resolve. Crossref holds a record with this title: "
                    f"{doi_url(match['doi'])}, “{match['title']}”, with the same first author "
                    f"({_share(match['similarity'])}).",
                    why="Readers and editors who follow the identifier reach nothing.",
                    suggestion="A mistyped identifier is the usual cause: compare that record with the entry (authors, "
                               "year, journal), then correct the identifier.")
            else:
                if match:
                    found = (f"; Crossref's closest title match is a different work: {doi_url(match['doi'])}, "
                             f"“{match['title']}” ({_share(match['similarity'])}; its first author "
                             f"{'is' if match['first_author_shared'] else 'is not'} in the entry)")
                elif any("title search did not answer" in n for n in ref.lookup_notes):
                    found = ", and the Crossref title search did not answer"
                else:
                    found = ", and the Crossref title search found no close record"
                add(ref, Severity.blocker, f"{ident[0].upper()}{ident[1:]} does not resolve{found}.",
                    why="A reference that no one can trace is grounds for a desk rejection at several journals.",
                    suggestion="A typo in the identifier is the usual cause. Find the work by title, journal, volume "
                               "and pages and correct the entry.")
        elif ref.status == "retracted":
            notice = f", notice {doi_url(ref.retraction_notice)}" if ref.retraction_notice else ""
            add(ref, Severity.blocker,
                f"The cited work is marked as retracted (found by {source_words(ref.retraction_source)}{notice}).",
                why="A retracted work cannot carry a claim as evidence.",
                suggestion="Drop it, or cite it explicitly as retracted if the retraction is the point.")
        elif ref.status == "concern":
            add(ref, Severity.major, f"The cited work carries an expression of concern (found by "
                                     f"{source_words(ref.retraction_source)}).",
                why="The publisher has flagged doubts about its results.",
                suggestion="Say so where it is cited, or support the claim with other work.")
        elif ref.status == "mismatch":
            details = []
            if (ref.title_similarity or 0) < 0.6:
                details.append(f"only {_share(ref.title_similarity)}")
            if ref.first_author_found is False:
                details.append("the record's first author is not in the entry")
            notice = (f" That record is marked {'as retracted' if ref.retraction == 'retracted' else 'with an expression of concern'}"
                      f" ({source_words(ref.retraction_source)})." if ref.retraction in ("retracted", "concern") else "")
            add(ref, Severity.major,
                f"{ident[0].upper()}{ident[1:]} leads to a different work: “{ref.resolved_title}” by "
                f"{ref.resolved_first_author or 'an unnamed author'}"
                + (f" ({' and '.join(details)})" if details else "") + "." + notice,
                why="Readers who follow the identifier reach the wrong paper.",
                suggestion="Correct the identifier or the citation text, and check the authors and year too.")
        elif ref.status == "lookup_failed":
            add(ref, Severity.info,
                "This entry could not be checked: the registry did not answer, so neither its identity nor its "
                "retraction status is known. " + " ".join(ref.lookup_notes),
                suggestion="Run the check again later, or open the record by hand. A failed lookup is not evidence "
                           "that the reference is wrong.")
        elif ref.status == "no_identifier":
            weak = (ref.title_similarity or 0) < 0.6
            best = (f"Crossref's best match is {doi_url(ref.doi)}, “{ref.resolved_title}” ({_share(ref.title_similarity)})"
                    if ref.resolved_title and ref.doi else "")
            if weak and not ref.first_author_found:
                add(ref, Severity.major,
                    "The entry carries no DOI, PubMed ID or arXiv id, and Crossref holds no close match for it"
                    + (f" (the best, {doi_url(ref.doi)}, “{ref.resolved_title}”, is a different work)"
                       if best else "") + ". It is unverified, which is not evidence that the work does not exist.",
                    why="Software, web pages, reports and new works are often missing from Crossref, but a reference "
                        "nobody can find cannot support a claim.",
                    suggestion="Search PubMed, the publisher or the project page by title, journal, volume and pages, "
                               "and add the identifier if the work has one.")
            elif weak:
                add(ref, Severity.minor,
                    f"The entry carries no DOI, PubMed ID or arXiv id. {best}, with the same first author, so the "
                    f"entry's title is probably shortened or altered.",
                    why="A title that differs from the published one makes the work hard to find.",
                    suggestion="Use the title as published, and add the identifier.")
            else:
                strict = unidentified == "strict"
                candidate = (" It stays a candidate until someone confirms it is the work cited: a search match is "
                             "not a verification." if strict and best else "")
                add(ref, Severity.minor if strict else Severity.info,
                    "The entry carries no DOI, PubMed ID or arXiv id. " + (f"{best}." if best else "") + candidate,
                    why="An identifier lets readers find the work, and many journals' reference styles ask for one.",
                    suggestion="Add the identifier after confirming the title, authors and year.", stage=Stage.journal)
        elif ref.status == "not_checked" and not (ref.doi or ref.pmid or ref.arxiv):
            add(ref, Severity.minor, NO_IDENTIFIER,
                why="An identifier lets readers find the work, and many journals' reference styles ask for one.",
                suggestion="Run the scan with --online to search Crossref, then add the identifier the work has.",
                stage=Stage.journal)
        if ref.withdrawn:
            add(ref, Severity.major, f"The cited preprint has been withdrawn by its authors (recorded by "
                                     f"{source_words(ref.withdrawn_source)}).",
                why="Its authors no longer stand by it.",
                suggestion="Cite the version or work that replaces it, and keep it only to discuss the withdrawal.")
        pv = ref.published_version
        if pv is not None and pv.source in ("arxiv:comment", "crossref:title-search") \
                and ref.status not in ("unresolved", "mismatch"):
            said = f" The arXiv comment says “{pv.comment}”." if pv.comment else ""
            found = (f" Crossref holds a record with the same title and a shared author: "
                     f"{', '.join(x for x in (pv.venue, pv.year) if x)}, {doi_url(pv.doi)} "
                     f"({round(100 * (pv.title_similarity or 0))}% of the titles match)." if pv.doi else
                     " No Crossref record with the same title was found.")
            add(ref, Severity.minor,
                f"The cited preprint may have been published.{said}{found} A candidate to confirm: neither arXiv nor "
                f"Crossref links it to the preprint.",
                why="Numbers, methods and author lists can change between a preprint and its published version.",
                suggestion="Open the published record, check that it is the same work and still reports what you "
                           "cite, then cite it; keep the preprint if you need content the published version dropped.")
        elif pv is not None and ref.status not in ("unresolved", "mismatch"):
            where = ", ".join(x for x in (pv.venue, pv.year) if x) or "a journal"
            check = ""
            if pv.metadata_checked and (pv.title_similarity or 0) < 0.5 and not pv.shared_authors:
                check = " Its title and authors differ from the preprint's, so confirm the link before switching."
            elif pv.metadata_checked:
                check = (f" {round(100 * (pv.title_similarity or 0))}% of the published title matches the "
                         f"preprint's, and the two {'share' if pv.shared_authors else 'do not share'} authors.")
            if pv.retraction in ("retracted", "concern"):
                check += (" The published version is marked as retracted." if pv.retraction == "retracted" else
                          " The published version carries an expression of concern.")
            add(ref, Severity.minor,
                f"The cited preprint has been published in {where}" + (f", {doi_url(pv.doi)}" if pv.doi else "")
                + f" (recorded by {source_words(pv.source)})." + check,
                why="Numbers, methods and author lists can change between a preprint and its published version.",
                suggestion="Cite the published version after confirming it still reports what you cite. Keep the "
                           "preprint only if you need content the published version dropped.")
        if ref.title_check == "differs" and ref.status not in ("unresolved", "mismatch"):
            a, b = _strict_title(ref.cited_title or ""), _strict_title(ref.resolved_title or "")
            tail = (" One is the other with a subtitle added or dropped." if a.startswith(b + " ")
                    or b.startswith(a + " ") else "")
            add(ref, Severity.minor,
                f"The cited title, “{_fetched(_delatex(ref.cited_title or ''))}”, is close to the record's but not "
                f"the same: “{ref.resolved_title}”.{tail}",
                why="A title that differs from the published one makes the work harder to find.",
                suggestion="Copy the title from the record, keeping the journal's capitalisation style.",
                stage=Stage.journal)
        elif ref.title_check == "no_title" and ref.resolved_title:
            add(ref, Severity.minor,
                f"The entry has no title, so it could not be compared with the work its identifier names, "
                f"“{ref.resolved_title}”.",
                why="Without a title, nobody can tell from the entry whether the identifier names the work meant.",
                suggestion="Add the title from the record after checking it is the work you cite.")
        for other in ref.other_id_checks:
            kind, _, value = (other["id"] or "").partition(":")
            named = f"{ID_KIND_WORDS.get(kind, kind)} {id_url(kind, value)}"
            if other["state"] == "dead":
                add(ref, Severity.major, f"The entry also gives {named}, which does not resolve ({other['why']}).",
                    why="Readers who follow it reach nothing.",
                    suggestion="Correct it or remove it: every identifier an entry carries is followed.")
            elif other["state"] == "unknown":
                add(ref, Severity.info, f"The entry also gives {named}, which could not be checked ({other['why']}).",
                    suggestion="Run the check again later, or open it by hand.")
            elif other["same_work"] == "false":
                # A preprint and its published version often carry different titles.
                preprint = kind == "arxiv" or bool(ref.arxiv) or value.startswith("10.1101/") \
                    or (ref.doi or "").startswith("10.1101/")
                add(ref, Severity.minor if preprint else Severity.major,
                    f"The entry's identifiers name works with different titles: {named} is “{other['title']}”, and "
                    f"its first identifier is “{ref.resolved_title or ref.cited_title}”."
                    + (" They may be a preprint and its published version." if preprint else ""),
                    why="Readers who follow one of them may reach a different paper from the one cited.",
                    suggestion="Keep the identifier of the work you cite and remove the other, unless the two are "
                               "versions of one work and the entry means both.")
        if ref.url_status and not ref.url_status.startswith("ok"):
            state, _, detail = ref.url_status.partition(" ")
            state = state.rstrip(":")
            if state == "dead":
                add(ref, Severity.major, f"The entry's link {ref.url} does not answer ({detail}).",
                    why="Readers who follow it reach nothing.",
                    suggestion="Replace it with an archived or current link: a DOI, or a Software Heritage or Wayback "
                               "Machine snapshot.")
            elif state == "blocked":
                add(ref, Severity.info, f"The entry's link {ref.url} refuses automated access ({detail}), so it was "
                                        f"not checked.",
                    suggestion="Open it by hand to confirm that it still works.")
            else:
                add(ref, Severity.info, f"The entry's link {ref.url} could not be checked ({detail}).",
                    suggestion="Run the check again later, or open it by hand.")
        if any(n.startswith("The entry names no author") for n in ref.lookup_notes):
            add(ref, Severity.info,
                f"The entry names no author (no author field could be read), so its authors were not compared with "
                f"the record, which lists {len(ref.resolved_authors)}.",
                suggestion="Add the author list from the record, or check the entry's author field.")
        if ref.author_check == "differs" and ref.status not in ("unresolved", "mismatch"):
            add(ref, Severity(ref.author_severity or "minor"),
                f"The author list differs from the {_record_source(ref)} record. " + " ".join(ref.author_notes),
                suggestion="Check it against the publisher's page. Registries cut lists short and spell names "
                           "differently (initials, transliteration, particles), so this is a metadata difference to "
                           "check, not evidence of fabrication.")
    if online:
        unchecked = [r for r in refs if r.retraction == "not_checked" and r.status not in ("unresolved", "not_checked")]
        if unchecked:
            named = [f"“{_quote(r.text, width=60)[0]}” (line {r.line})" for r in unchecked[:12]]
            more = f" and {len(unchecked) - 12} more" if len(unchecked) > 12 else ""
            out.append(Finding(check="references", severity=Severity.info, section="References",
                               message=f"The retraction status of {len(unchecked)} "
                                       f"{'entry' if len(unchecked) == 1 else 'entries'} could not be checked, so "
                                       f"{'it is' if len(unchecked) == 1 else 'they are'} not known to be clean: "
                                       + ", ".join(named) + more + ".",
                               why="No registry that records retractions covers them (arXiv, DataCite and entries "
                                   "without an identifier are not covered), or the lookup failed.",
                               suggestion="For any that carry the argument, check the publisher's page or the "
                                          "Retraction Watch database by hand."))
    return out


# --------------------------------------------------------------------------------------------------

GIT_AI_TRAILER = re.compile(r"^co-authored-by:.*\b(claude|gpt|chatgpt|openai|gemini|copilot|cursor|codex|"
                            r"anthropic|deepseek|qwen|mistral)\b", re.IGNORECASE | re.MULTILINE)


def _git_findings(path: Path) -> list[Finding]:
    """Commits touching the file whose message carries an AI co-author trailer."""
    run = subprocess.run(["git", "-C", str(path.parent), "log", "--format=%H%x00%B%x01", "--", path.name],
                         capture_output=True, text=True)
    if run.returncode != 0:
        return [Finding(check="ai-use", severity=Severity.info, section=WHOLE_MANUSCRIPT,
                        message="The file is not in a git repository, so its commit messages were not checked.")]
    commits = [c for c in run.stdout.split("\x01") if c.strip()]
    ai = [c for c in commits if GIT_AI_TRAILER.search(c.split("\x00", 1)[-1])]
    if not ai:
        return []
    return [Finding(check="ai-use", severity=Severity.info, section=WHOLE_MANUSCRIPT,
                    message=f"{len(ai)} of {len(commits)} commits touching this file have an AI co-author trailer. "
                            "A trailer can mark automation (syncing comments, formatting), not writing.",
                    suggestion="Ask the authors what those commits changed; the disclosure follows their account.")]


# --- identifiers in the text and live figures (from cite-check) ----------------------------------------------

# A URL ends at whitespace, quotes (straight or curly), dashes and characters a URL never carries unencoded.
INLINE_URL_RE = re.compile(r"https?://[^\s<>\"'`{}\\|^“”‘’«»—–]+")
INLINE_DOI_RE = re.compile(r"\bdoi:\s*(10\.\d{4,9}/[^\s\"<>{}`]+)", re.IGNORECASE)
INLINE_ARXIV_RE = re.compile(r"\barXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)",
                             re.IGNORECASE)
CLOSERS = {")": "(", "]": "[", "}": "{", ">": "<"}
FENCE_RE = re.compile(r"^\s*(```|~~~)")
VERBATIM_RE = re.compile(r"\\(begin|end)\{(verbatim|Verbatim|lstlisting|minted|comment)\*?\}")
NEW_BLOCK_RE = re.compile(r"^\s*(#|[-*+]\s|\d+[.)]\s|\||>|\\item|\\(sub)*section|\\paragraph)")
LIVE_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?:%|[kM])?(?!\w)")
LIVE_CUE_RE = re.compile(r"\b(currently|as of|to date|so far|now|at present|at the time of writing)\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


def _trim_id(s: str) -> str:
    """Strip trailing punctuation, and closers the identifier does not open itself."""
    while s:
        c = s[-1]
        if c in ".,;:!?'\"*_":
            s = s[:-1]
        elif c in CLOSERS and s.count(c) > s.count(CLOSERS[c]):
            s = s[:-1]
        else:
            break
    return s


def _inline_ids(line: str) -> list[tuple[str, str]]:
    # "[https://a](https://a)": a Markdown link whose text is its own URL ends where the text does.
    found = [classify_url(_trim_id(m.group(0).split("](", 1)[0])) for m in INLINE_URL_RE.finditer(line)]
    found += [("doi", _trim_id(m.group(1))) for m in INLINE_DOI_RE.finditer(line)]
    found += [("pmid", m.group(1)) for m in PMID_RE.finditer(line)]
    found += [("arxiv", m.group(1)) for m in INLINE_ARXIV_RE.finditer(line)]
    return [i for i in dict.fromkeys(found) if i[0] not in ("placeholder", "local")]


def _prose_lines(path: Path, text: str) -> list[tuple[int, str]]:
    """(line number, text) with code and comments blanked: what a reader reads as prose."""
    out, in_code, tex = [], False, path.suffix.lower() == ".tex"
    for n, line in enumerate((text if tex else _strip_comments(text)).splitlines(), 1):
        if tex:
            v = list(VERBATIM_RE.finditer(line))
            if v:
                in_code = v[-1].group(1) == "begin"  # a one-line \begin{verbatim}...\end{verbatim} closes itself
                out.append((n, ""))
                continue
            if in_code:
                out.append((n, ""))
                continue
            line = re.sub(r"\\verb\*?(\S)(.*?)\1", " ", line)
            line = re.sub(r"(?<!\\)%.*", "", line)
            line = re.sub(r"\\([_%&#~$])", r"\1", line)  # \url{a\_b}: the URL as the reader sees it
        else:
            if FENCE_RE.match(line):
                in_code = not in_code
                out.append((n, ""))
                continue
            if in_code:
                out.append((n, ""))
                continue
            line = re.sub(r"(`+)(.+?)\1", " ", re.sub(r"<!--.*?-->", " ", line))
        out.append((n, line))
    return out


def _undated(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """(line, sentence head) for each sentence with a number and a live cue ("currently", "as of", "to date",
    "so far", "now", "at present", "at the time of writing") but no year: a live figure must say when."""
    blocks: list[list[tuple[int, str]]] = []
    cur: list[tuple[int, str]] = []
    for n, line in lines:
        if not line.strip() or NEW_BLOCK_RE.match(line):
            if cur:
                blocks.append(cur)
            cur = [(n, line)] if line.strip() else []
        else:
            cur.append((n, line))
    if cur:
        blocks.append(cur)
    hits = []
    for block in blocks:
        text, starts = "", []
        for n, line in block:
            starts.append((len(text), n))
            text += line.strip() + " "
        pos = 0
        for m in [*SENTENCE_END_RE.finditer(text), None]:
            end = m.end() if m else len(text)
            s = text[pos:end].strip()
            if s:
                body = INLINE_URL_RE.sub(" ", s)
                if LIVE_NUMBER_RE.search(body) and LIVE_CUE_RE.search(body) and not YEAR_RE.search(body):
                    lead = len(text[pos:end]) - len(text[pos:end].lstrip())
                    at = max(ln for off, ln in starts if off <= pos + lead)
                    head = " ".join(s.split())
                    hits.append((at, head if len(head) <= 80 else head[:79] + "…"))
            pos = end
    return hits


def resolve_inline(items: list[InlineId]) -> None:
    """Resolve each identifier in the text once; a URL by its status only."""
    with httpx.Client(timeout=20, headers={"User-Agent": USER_AGENT}) as client:
        for item in items:
            if item.kind == "url":
                status = _url_status(client, item.id)
                item.state = status.split(" ")[0].rstrip(":")
                item.detail = status.split(" ", 1)[1] if " " in status else ""
            else:
                item.state, item.title, item.detail = _title_of(client, item.kind, item.id)


def _inline_findings(items: list[InlineId]) -> list[Finding]:
    out = []
    for item in items:
        link = id_url(item.kind, item.id)
        named = f"the link {link}" if item.kind == "url" else f"{ID_KIND_WORDS[item.kind]} {link}"
        if item.state == "dead":
            out.append(Finding(check="references", severity=Severity.major, line=item.line, excerpt=item.id,
                               message=f"The text gives {named}, which does not resolve ({item.detail}).",
                               why="Readers who follow it reach nothing.",
                               suggestion="Correct it, or replace a dead link with an archived or current one."))
        elif item.state in ("unknown", "blocked"):
            out.append(Finding(check="references", severity=Severity.info, line=item.line, excerpt=item.id,
                               message=f"The text gives {named}, which could not be checked ({item.detail}).",
                               suggestion="Open it by hand to confirm that it works."))
    return out


def _undated_findings(prose: list[tuple[int, str]]) -> list[Finding]:
    return [Finding(check="undated", severity=Severity.minor, line=n, excerpt=head, stage=Stage.writing.value,
                    message=f"A figure said to be current carries no date: “{head}”.",
                    why="Counts like this change, and without a date a reader cannot tell when it was true.",
                    suggestion="Say when it was true (“as of October 2026”), or drop the “currently”.")
            for n, head in _undated(prose)]


def check_references(path: Path, online: bool, search_unidentified: bool,
                     sections: Optional[list[str]] = None, unidentified: str = "strict") -> ReferenceReport:
    """Identity and citation consistency only, shared by focused checks and full audits."""
    _ASKED.clear()  # one run, one cache: never an answer from an earlier run in the same process
    raw = path.read_text(encoding="utf-8")
    text = _strip_comments(raw)
    lines = _lines(text)
    sections = sections if sections is not None else section_index(lines)
    ref_start = _reference_start(lines)
    findings: list[Finding] = []
    refs: list[Reference] = []
    inline: list[InlineId] = []
    bibliography_only = path.suffix.lower() == ".bib"
    bibs = [path] if bibliography_only else _bib_files(text, path.parent) if path.suffix.lower() == ".tex" else []
    if bibs:
        keyed = []
        for bib in bibs:
            errors: list[tuple[int, str, bool]] = []
            keyed += _bib_references(bib, errors)
            for line_no, why, kept in errors:
                if kept:
                    findings.append(Finding(check="references", severity=Severity.minor, line=line_no,
                                            section=bib.name, stage=Stage.writing.value,
                                            message=f"A BibTeX entry in {bib.name} stops parsing partway ({why}). The "
                                                    f"fields before that point were read and checked; the rest of the "
                                                    f"entry was not.",
                                            why="BibTeX skips the same fields, so they may be missing from the PDF "
                                                "too. A line starting with % inside an entry is not a comment there.",
                                            suggestion="Fix or remove the field it names, then run the check again."))
                    continue
                findings.append(Finding(check="references", severity=Severity.major, line=line_no,
                                        section=bib.name, stage=Stage.writing.value,
                                        message=f"A BibTeX entry in {bib.name} does not parse ({why}), so it was not "
                                                f"read or checked; the entries after it may be missing too.",
                                        why="An entry that cannot be read cannot be checked, and BibTeX may drop it "
                                            "from the PDF.",
                                        suggestion="Fix the entry's braces, quotes or commas, then run the check again."))
        refs = [r for _, r in keyed]
        if not bibliography_only:
            findings += _cite_key_findings(lines, {k for k, _ in keyed})
    if not bibliography_only:
        lists = _reference_lists(lines, ref_start)
        in_lists: set[int] = set()
        for number, (begin, end, label, entries) in enumerate(lists):
            in_lists.update(range(begin, end + 1))  # 1-based: the label line and the list's lines
            split = _split_entries(entries)
            for line_no, count in Counter(n for n, _ in split).items():
                if count > 1:
                    starts = [f"“{' '.join(e.split()[:4])}”" for n, e in split if n == line_no]
                    findings.append(Finding(check="references", severity=Severity.info, line=line_no,
                                            message=f"One paragraph holds {count} references. The scan split it where "
                                                    f"each reference starts, into entries beginning "
                                                    f"{_names_listed(starts, 10)}.",
                                            why="If the split is wrong, an entry can be reported as uncited, missing "
                                                "or garbled.",
                                            suggestion="Check that these are the references the paragraph holds, put "
                                                       "each on its own line, and move any lead-in ('Added in the "
                                                       "revision:') out of the list.", stage=Stage.writing.value))
            if number:
                findings.append(Finding(check="references", severity=Severity.info, line=begin,
                                        excerpt=label.strip("*# "),
                                        message=f"A further reference list, “{label.strip('*# ')}” ({len(split)} "
                                                f"entries), was checked with the main one, and the text after the main "
                                                f"list was read for citations.",
                                        suggestion="Nothing to change, unless this list should not be read as "
                                                   "references.", stage=Stage.writing.value))
            for line_no, entry in split:
                doi = DOI_RE.search(entry)
                pmid = PMID_RE.search(entry)
                arxiv = ARXIV_RE.search(entry)
                ref = Reference(line=line_no, text=entry, doi=doi.group(1).rstrip(".") if doi else None,
                                pmid=pmid.group(1) if pmid else None, arxiv=_arxiv_id(arxiv))
                ref._list = sections[begin - 1] if begin <= len(sections) else None
                refs.append(ref)
        # Citations are read everywhere outside the lists: the body, and a supplement after the main list.
        cited_text = [(i, line) for i, line in enumerate(lines, start=1) if i not in in_lists]
        findings += _citation_consistency(cited_text, refs)
        prose = [(n, line) for n, line in _prose_lines(path, raw) if n not in in_lists]
        inline = [InlineId(line=n, kind=kind, id=ident, section=sections[n - 1] if n <= len(sections) else "")
                  for n, line in prose for kind, ident in _inline_ids(line)]
        findings += _undated_findings(prose)
    if ref_start is None and not bibs:
        findings.append(Finding(check="references", severity=Severity.major, section=WHOLE_MANUSCRIPT,
                                message="No references heading (References or Bibliography) was found, so the "
                                        "references were not checked.",
                                suggestion="Name the section 'References', or pass the .bib file separately."))
    elif not refs:
        findings.append(Finding(check="references", severity=Severity.major, section="References",
                                message="No bibliography entries could be read, so the references were not checked.",
                                suggestion="Check how the bibliography is written, and read the entries by hand."))
    if online and refs:
        resolve_references(refs, search_unidentified)
    findings += _reference_findings(refs, online, unidentified)
    if online and inline:
        resolve_inline(inline)
        findings += _inline_findings(inline)
    _place(findings, lines, sections)
    order = {s: i for i, s in enumerate(Severity)}
    findings.sort(key=lambda f: (order[f.severity], f.line or 0))
    return ReferenceReport(path=str(path), online=online, findings=findings, references=refs, inline_ids=inline)


def scan(path: Path, online: bool, search_unidentified: bool, venue: Optional[str] = None,
         git: bool = False, final: bool = False, unidentified: str = "strict") -> Report:
    VOCAB_SOURCES.update({"kobak2025_r>=2": _kobak_words(), "juzek_ward2025": JUZEK_WARD,
                          "wikipedia_aivocab": WIKIPEDIA_AIVOCAB})
    raw = path.read_text(encoding="utf-8")
    text = _strip_comments(raw)
    lines = _lines(text)
    sections = section_index(lines)
    text_lower = text.lower()
    ref_start = _reference_start(lines)
    body_lines = lines[: (ref_start or len(lines) + 1) - 1]

    leftover_why = "Editors and screening tools search for such leftovers, and one can be enough for a desk rejection."
    findings: list[Finding] = []
    findings += _scan_patterns(lines, CHATBOT_LEFTOVERS, "chatbot-leftover", Severity.blocker,
                               "The phrase '{match}' is text a chat interface produces, not part of a paper.",
                               "Delete the leftover text and re-read the passage around it.", why=leftover_why)
    # Placeholders are searched in the raw text too: an HTML-comment TODO still ships in the LaTeX.
    findings += _placeholder_findings(_lines(raw), why="Placeholders belong in a draft, but an editor reads one in a "
                                                       "submission as an unfinished manuscript.")
    findings += _scan_patterns(_lines(raw), CITATION_PLACEHOLDERS, "placeholder", Severity.major,
                               "The placeholder '{match}' marks a claim that has no source yet.",
                               "Find the source and cite it, or reword the claim so that it needs none.",
                               why="A claim without its source cannot be checked by readers or referees.",
                               stage=Stage.now.value)
    findings += _declaration_findings(text_lower)
    findings += _ai_use_findings(lines, text_lower, ref_start, bool(ledger_ai(raw)))
    findings += _scan_patterns(body_lines, STOCK_PHRASES, "stock-phrase", Severity.minor,
                               "'{match}' is a stock phrase.", "Say the specific thing instead, or cut the phrase.",
                               why="Such phrases say little, and readers and screeners associate them with text "
                                   "written by a language model.")
    findings += _scan_patterns(lines, MARKUP_ARTIFACTS, "chatbot-leftover", Severity.blocker,
                               "'{match}' is markup a chat interface leaves in copied text; it usually stands where "
                               "a citation was.", "Delete it, and find the source the citation should name.",
                               flags=0, why=leftover_why, stage=Stage.now.value)
    findings += _scan_patterns(body_lines, TORTURED_PHRASES, "tortured-phrase", Severity.major,
                               "'{match}' is a garbled synonym of a standard term (a tortured phrase).",
                               "Use the standard term.",
                               why="Paraphrasing tools produce such phrases, and screeners search for them as a sign "
                                   "of paper mills.")
    findings += _scan_patterns(body_lines, FIRST_PERSON_SINGULAR, "first-person", Severity.info,
                               "'{match}' addresses the reader in the first person singular, as a chat reply would.",
                               "Rephrase, unless the paper has a single author.", flags=0,
                               why="A paper reports its results; chat text speaks to one reader.")
    findings += _scan_patterns(body_lines, OVERCLAIM, "overclaim", Severity.info,
                               "The word '{match}' claims more than many results can show.",
                               "Keep such a word only where the evidence in this paper supports it. Prefer "
                               "'rediscovery' for known answers, and drop 'first' or 'novel' unless a literature "
                               "search shows it.",
                               why="Editors and referees read such words as hype unless the paper's own evidence "
                                   "supports them.")
    findings += _dashes(lines, ref_start)
    findings += _abstract_numbers(lines, ref_start)
    findings += _abstract_metric_dump(lines)
    findings += _percentages(body_lines)

    reference_report = check_references(path, online, search_unidentified, sections, unidentified)
    refs = reference_report.references
    findings += reference_report.findings
    if git:
        findings += _git_findings(path.resolve())
    ai_marks = ledger_ai(raw)
    if ai_marks:
        findings.append(Finding(check="ai-use", severity=Severity.info, section=WHOLE_MANUSCRIPT,
                                message=f"{len(ai_marks)} revision markers (comments such as <!-- @rev ... -->) "
                                        f"name an AI as the reviser of a passage ({', '.join(sorted(set(ai_marks)))}).",
                                suggestion="Markers do not establish the kind of help. Use what the authors say they "
                                           "used and the chosen journal's rule and exemptions to decide whether a "
                                           "statement about AI use needs updating."))
    densities, top, n_words = _vocabulary("\n".join(body_lines))
    ing_tails = len(ING_TAIL_RE.findall("\n".join(body_lines)))
    if n_words and 1000 * ing_tails / n_words > 1.0:
        first_tail = next(((i, m) for i, l in enumerate(body_lines, start=1) if (m := ING_TAIL_RE.search(l))), None)
        tail = Finding(check="style", severity=Severity.minor, line=first_tail[0] if first_tail else None,
                       message=f"{ing_tails} sentences end in a clause that starts with a present participle "
                               f"(“, highlighting ...”); the first is quoted here.",
                       why="Language models write such tails several times as often as people do, and a tail "
                           "usually adds a claim without its evidence.",
                       suggestion="State the consequence as its own claim with its evidence, or cut it.")
        findings.append(_with_quote(tail, body_lines[first_tail[0] - 1], first_tail[1].start(), first_tail[1].end())
                        if first_tail else tail)
    span = _abstract_span(lines)
    abstract_words = _count_words("\n".join(lines[span[0]:span[1]])) if span else None
    findings += _venue_findings(lines, n_words, abstract_words, venue, text_lower,
                                _abstract_parts(lines[span[0]:span[1]]) if span else None)
    if densities["kobak2025_r>=2"] > 3.0:
        findings.append(Finding(check="vocabulary", severity=Severity.minor, section=WHOLE_MANUSCRIPT,
                                message=f"Words whose use in papers rose sharply after chat assistants appeared "
                                        f"(Kobak et al. 2025) occur {densities['kobak2025_r>=2']} times per 1,000 "
                                        f"words; the most frequent are "
                                        f"{_names_listed([f'{w} ({c})' for w, c in top[:6]])}.",
                                why="It is a density, not proof of anything: writing in a second language and "
                                    "permitted language polishing raise it too.",
                                suggestion="Where one of these words stands in for a specific statement, use the "
                                           "specific word or a number."))
    seen: set[tuple[str, Optional[int], str]] = set()
    deduped: list[Finding] = []
    _place(findings, lines, sections)
    for f in findings:  # overlapping patterns ("TODO" inside "AUTHOR TODO") report a line once
        key = (f.check, f.line, f.stage)
        if f.check in ("chatbot-leftover", "placeholder") and key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    findings = deduped
    order = {s: i for i, s in enumerate(Severity)}
    findings.sort(key=lambda f: (order[f.severity], f.line or 0))
    return Report(path=str(path), words=n_words, abstract_words=abstract_words, findings=findings, references=refs,
                  vocabulary_per_1000_words=densities, top_vocabulary=top, ing_tails=ing_tails, final=final,
                  inline_ids=reference_report.inline_ids)


def unchecked_lookups(references: list[Reference], inline: list[InlineId]) -> int:
    """Online lookups that did not answer: references, their further identifiers and url fields, and identifiers
    in the text. Any of them makes a run with no blocker exit 3, never 0."""
    return (sum(r.status == "lookup_failed" for r in references)
            + sum(c["state"] == "unknown" for r in references for c in r.other_id_checks)
            + sum(bool(r.url_status) and r.url_status.startswith("unknown") for r in references)
            + sum(i.state == "unknown" for i in inline))


# --------------------------------------------------------------------------------------------------
# Reports for the authors (references/author-priorities.md, "Writing for the authors"): grouped by when the work
# can be done, each finding in sentences that name its section and quote its text. The JSON keeps the fields.
# --------------------------------------------------------------------------------------------------

STAGE_TITLES = {Stage.now: "Fix now: the science and the evidence", Stage.writing: "Then the writing",
                Stage.journal: "Once you have chosen the journal",
                Stage.final: "Before submission, once the code is final"}
STAGE_INTROS = {Stage.final: "These are done once the code, data and results are final. They are not problems with "
                             "the current draft."}
SEVERITY_LEAD = {Severity.blocker: "Serious", Severity.major: "Important", Severity.minor: "Minor",
                 Severity.info: "To look at"}
SEVERITY_KEY = ("Within each group the most serious findings come first: “Serious” marks what could get the paper "
                "returned without review, “Important” what an editor or referee would object to, “Minor” style and "
                "calibration, and “To look at” what needs a human eye and may be fine.")
GROUP_SHOWN = 12  # occurrences listed under a repeated finding; the rest are counted by section
STATUS_WORDS = {
    "resolved": "found, with the title and first author of the entry",
    "mismatch": "the identifier leads to a different work",
    "unresolved": "the identifier does not resolve", "retracted": "found, and marked as retracted",
    "concern": "found, and it carries an expression of concern",
    "lookup_failed": "could not be checked, because the registry did not answer",
    "not_checked": "not looked up",
}
RETRACTION_WORDS = {"retracted": "marked as retracted", "concern": "an expression of concern",
                    "none_found": "none found", "not_checked": "not checked, so not known to be clean"}


def counted_findings(findings: list[Finding], final: bool) -> list[Finding]:
    """The findings a readiness verdict counts: end-stage items only when the authors are about to submit."""
    return [f for f in findings if final or f.stage != Stage.final.value]


def _sentence(text: str) -> str:
    text = " ".join(text.split())
    return text if not text or text[-1] in ".!?”" else text + "."


def _plural(n: int, one: str, many: Optional[str] = None) -> str:
    return f"{n} {one if n == 1 else many or one + 's'}"


# Emphasis and code marks of the manuscript's own Markdown: a quote cut short can leave one open, which would set the
# rest of the report in bold or code.
QUOTE_MARKUP = re.compile(r"\*\*|__|`|(?<![\w*])\*(?=[^\s*])|(?<=[^\s*])\*(?![\w*])")


def _marked_quote(f: Finding) -> str:
    """The quote in curly quotes without the manuscript's emphasis marks, with the part the finding is about in bold."""
    quote = f.quote
    a, b = f.quote_span or (0, 0)
    part = quote[a:b]
    a, b = a + len(part) - len(part.lstrip()), b - (len(part) - len(part.rstrip()))
    clean = [QUOTE_MARKUP.sub("", piece) for piece in (quote[:a], quote[a:b], quote[b:])] if b > a else \
        [QUOTE_MARKUP.sub("", quote), "", ""]
    middle = f"**{clean[1].strip()}**" if clean[1].strip() else ""
    return f"“{clean[0]}{middle}{clean[2]}”"


NUMBERED = re.compile(r"^(?P<number>(?:\d+(?:\.\d+)*|[IVX]+))[.)]?\s+(?P<title>\S.*)$")


# Headings read naturally after "the" ("in the Methods"); any other heading is quoted ("in the section “Speed”").
PLAIN_HEADINGS = re.compile(r"^(?:abstract|introduction|background|methods?|materials|results|discussion|conclusions?|"
                            r"references|bibliography|acknowledge?ments|funding|supplementary|appendix|limitations|"
                            r"data|code|availability|declarations?|author|competing|ethics)\b", re.IGNORECASE)


def _section_name(section: str) -> str:
    """'the Methods'; a numbered heading as 'section 2.1, Annotation Pipeline' (its parent is in the number); any
    other heading quoted, 'the section “Reproducing the analysis”'."""
    numbered = NUMBERED.match(section.split(", ")[-1]) if section != WHOLE_MANUSCRIPT else None
    if numbered:
        return f"section {numbered.group('number')}, {numbered.group('title')}"
    return f"the {section}" if PLAIN_HEADINGS.match(section) else f"the section “{section}”"


def _where(f: Finding) -> str:
    """'In the Methods (line 10)': the section, with the line in parentheses."""
    at = f" (line {f.line})" if f.line else ""
    section = f.section or WHOLE_MANUSCRIPT
    if section == FRONT_MATTER:
        return f"In the front matter, before the first heading{at}"
    if ".bib, entry " in section:
        bib, key = section.split(", entry ", 1)
        return f"In {bib}, entry {key}{at}"
    if section == WHOLE_MANUSCRIPT:
        return f"In the manuscript{at}"
    return f"In {_section_name(section)}{at}"


def _place_sentence(f: Finding) -> str:
    if not f.quote:
        return f"{_where(f)}." if f.line and f.section != WHOLE_MANUSCRIPT else ""
    quoted = _marked_quote(f)
    end = "" if f.quote.rstrip("*")[-1:] in ".!?" else "."
    if f.section and ".bib, entry " in f.section:
        bib, key = f.section.split(", entry ", 1)
        return f"The entry {key} in {bib}" + (f" (line {f.line})" if f.line else "") + f" gives {quoted}{end}"
    what = "the entry reads" if f._entry else "the manuscript reads"
    return f"{_where(f)}, {what} {quoted}{end}"


def _finding_lines(f: Finding) -> list[str]:
    parts = [_sentence(f.message), _place_sentence(f), _sentence(f.why), _sentence(f.suggestion)]
    return [f"- **{SEVERITY_LEAD[f.severity]}.** " + " ".join(p for p in parts if p)]


GROUP_MESSAGES = {
    ("chatbot-leftover", Stage.writing.value): "Text left over from a chat interface appears in {n} places.",
    ("chatbot-leftover", Stage.now.value): "Markup that chat interfaces leave in copied text appears in {n} places; "
                                           "it usually stands where a citation was.",
    ("placeholder", Stage.final.value): "Placeholders are still in the text in {n} places.",
    ("placeholder", Stage.now.value): "Placeholders mark {n} claims that have no source yet.",
    ("stock-phrase", Stage.writing.value): "Stock phrases appear in {n} places.",
    ("tortured-phrase", Stage.writing.value): "Garbled synonyms of standard terms (tortured phrases) appear in {n} "
                                              "places.",
    ("first-person", Stage.writing.value): "The first person singular addresses the reader, as a chat reply would, "
                                           "in {n} places.",
    ("overclaim", Stage.writing.value): "Words that claim more than many results can show appear in {n} places.",
    ("ai-use", Stage.final.value): "The text names AI tools or large language models in {n} places.",
}


def _group_message(f: Finding, n: int) -> Optional[str]:
    """The headline for several findings of one kind, or None when they are reported one by one."""
    if f.check == "citations" and "never cited" in f.message:
        return f"{n} entries of the reference list are never cited in the text."
    if f.check == "citations" and "has no bibliography entry" in f.message:
        return f"{n} in-text citations have no entry in the reference list with that surname and year."
    if f.check == "references" and f.message == NO_IDENTIFIER:
        return f"{n} entries carry no DOI, PubMed ID or arXiv id."
    if f.check == "citations" and "has no entry in the bibliography file" in f.message:
        return f"{n} citation keys have no entry in the bibliography file, so those references will be missing."
    template = GROUP_MESSAGES.get((f.check, f.stage))
    return template.format(n=n) if template else None


def _group_lines(group: list[Finding]) -> list[str]:
    first = group[0]
    parts = [_group_message(first, len(group)) or "", _sentence(first.why), _sentence(first.suggestion)]
    out = [f"- **{SEVERITY_LEAD[first.severity]}.** " + " ".join(p for p in parts if p)]
    for f in group[:GROUP_SHOWN]:
        out.append(f"  - {_where(f)}: {_marked_quote(f)}" if f.quote else f"  - {_where(f)}: {_sentence(f.message)}")
    rest = group[GROUP_SHOWN:]
    if rest:
        places = list(dict.fromkeys(_section_name((f.section or WHOLE_MANUSCRIPT).split(", ")[-1]) for f in rest))
        out.append(f"  - {len(rest)} more, in {_names_listed(places)}.")
    return out


def _clusters(findings: list[Finding]) -> list[list[Finding]]:
    """Findings in report order: by severity, then by place; repeats of one kind with one explanation together."""
    order = {s: i for i, s in enumerate(Severity)}
    clusters: dict[tuple, list[Finding]] = {}
    for f in findings:
        groupable = _group_message(f, 2) is not None
        key = (f.severity, f.check, f.why, f.suggestion, _group_message(f, 0)) if groupable else (id(f),)
        clusters.setdefault(key, []).append(f)
    out = [sorted(members, key=lambda f: f.line or 0) for members in clusters.values()]
    return sorted(out, key=lambda c: (order[c[0].severity], c[0].line or -1))  # whole-manuscript findings first


def _stage_lines(findings: list[Finding]) -> list[str]:
    out: list[str] = []
    for stage in Stage:
        members = [f for f in findings if (f.stage or Stage.now.value) == stage.value]
        if not members:
            continue
        out += [f"## {STAGE_TITLES[stage]}", ""]
        if stage in STAGE_INTROS:
            out += [STAGE_INTROS[stage], ""]
        for cluster in _clusters(members):
            out += _group_lines(cluster) if len(cluster) > 1 else _finding_lines(cluster[0])
        out.append("")
    return out


def _entry_place(ref: Reference) -> str:
    return f"{ref._bib_file}, entry {ref._bib_key}" if ref._bib_file else f"line {ref.line}"


def _reference_rows(refs: list[Reference]) -> list[str]:
    out = ["| Entry | Where | Link | What the check found | Retraction notices |", "|---|---|---|---|---|"]
    for ref in refs:
        entry = _quote(ref.text, width=90)[0]
        found = STATUS_WORDS.get(ref.status, ref.status)
        if ref.status == "no_identifier":
            found = ("no identifier, and Crossref's best match fits" if (ref.title_similarity or 0) >= 0.6 else
                     "no identifier, and no close match in Crossref")
        notes = []
        if ref.published_version:
            pv = ref.published_version
            notes.append(f"published since, {doi_url(pv.doi)}" if pv.doi else f"published since, in {pv.venue}")
        if ref.withdrawn:
            notes.append("withdrawn by its authors")
        if ref.author_check == "differs":
            notes.append("the author list differs from the record")
        found = "; ".join([found] + notes)
        retraction = RETRACTION_WORDS.get(ref.retraction, ref.retraction)
        if ref.retraction_source and ref.retraction != "not_checked":
            retraction += f" ({source_words(ref.retraction_source)})"
        cells = [entry, _entry_place(ref), identifier_url(ref) or "no identifier", found, retraction]
        out.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    return out


def _retraction_coverage(refs: list[Reference]) -> str:
    states = Counter(ref.retraction for ref in refs)
    parts = [f"{_plural(states['retracted'], 'entry is', 'entries are')} marked as retracted" if states["retracted"]
             else "", f"{_plural(states['concern'], 'entry carries', 'entries carry')} an expression of concern"
             if states["concern"] else "",
             f"{_plural(states['none_found'], 'entry has', 'entries have')} no notice in the registries asked"
             if states["none_found"] else "",
             f"{_plural(states['not_checked'], 'entry', 'entries')} could not be checked, so "
             f"{'it is' if states['not_checked'] == 1 else 'they are'} not known to be clean"
             if states["not_checked"] else ""]
    parts = [p for p in parts if p]
    return ("The retraction search asked Crossref, which carries Retraction Watch's records, and Europe PMC, or PubMed "
            f"for an entry known only by its PubMed ID. Of the {_plural(len(refs), 'entry', 'entries')}, "
            + _names_listed(parts, len(parts)) + ".")


INLINE_STATE_WORDS = {"ok": "resolves", "dead": "does not resolve", "blocked": "refuses automated access",
                      "unknown": "did not answer"}


def _inline_section(items: list[InlineId]) -> list[str]:
    """The identifiers in the text, each with the title it resolved to, for a person to read against the
    sentence; nothing is matched automatically."""
    checked = [i for i in items if i.state != "not_checked"]
    if not checked:
        return []
    out = ["", "## Identifiers and links in the text", "",
           "Each identifier or link written in the text was looked up. Read each title against the sentence that "
           "gives it: nothing here was matched automatically.", "",
           "| Identifier or link | Where | What it answered | Title |", "|---|---|---|---|"]
    for i in checked:
        answer = INLINE_STATE_WORDS.get(i.state, i.state) + (f" ({i.detail})" if i.detail else "")
        cells = [id_url(i.kind, i.id), f"{i.section} (line {i.line})" if i.section else f"(line {i.line})", answer,
                 f"“{i.title}”" if i.title else ""]
        out.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    return out


def references_to_markdown(report: ReferenceReport) -> str:
    """The focused reference check: what manuscript-reference-check's Step 1 reports to the authors."""
    out = [f"# Reference check of {Path(report.path).name}", "",
           f"The reference list has {_plural(len(report.references), 'entry', 'entries')}. This check compares each "
           "entry with its registry record (Crossref, DataCite, PubMed or arXiv) by title and authors, looks for "
           "retractions, expressions of concern, withdrawals and published versions of preprints, and matches the "
           "in-text citations against the list. Whether a source supports the sentence that cites it needs the "
           "source to be read; this check does not establish it."]
    if not report.online:
        out += ["", "It ran offline, so whether each entry is the work it names, and whether it was retracted, was "
                    "not assessed (offline mode). Run it again with --online to look the identifiers up."]
    out += ["", SEVERITY_KEY if report.findings else "The check found no problem in the entries and citations.", ""]
    out += _stage_lines(report.findings)
    if report.online and report.references:
        out += ["## What the retraction search covered", "", _retraction_coverage(report.references), ""]
    if report.references:
        out += ["## Each entry as checked", ""] + _reference_rows(report.references)
    out += _inline_section(report.inline_ids)
    return "\n".join(out).rstrip("\n") + "\n"


def _verdict(findings: list[Finding]) -> str:
    counts = Counter(f.severity for f in findings)
    serious, important = counts[Severity.blocker], counts[Severity.major]
    if serious:
        return (f"not ready. {_plural(serious, 'finding')} could get the paper returned without review (a desk "
                f"rejection); {'it is' if serious == 1 else 'they are'} marked “Serious” below, so fix "
                f"{'it' if serious == 1 else 'them'} first.")
    if important:
        return (f"not ready yet. {_plural(important, 'finding')} would draw an objection from an editor or referee, "
                f"but none would by itself get the paper returned without review.")
    return ("the mechanical checks found nothing serious or important. The judgement checks of the full review still "
            "apply.")


VOCAB_NAMES = {"kobak2025_r>=2": "the words whose use in papers rose most after chat assistants appeared (Kobak et al. "
                                 "2025)",
               "juzek_ward2025": "the focal words of Juzek and Ward (2025)",
               "wikipedia_aivocab": "the words to watch in Wikipedia's “Signs of AI writing”"}


def _vocabulary_sentence(report: Report) -> str:
    rates = [f"{v} of {VOCAB_NAMES.get(k, k)}" for k, v in report.vocabulary_per_1000_words.items() if v]
    if not rates:
        text = "None of the words that screeners associate with AI writing appear in the body."
    else:
        text = "Per 1,000 words, the body uses " + _names_listed(rates, len(rates)) + "."
    if report.top_vocabulary:
        text += " The most frequent are " + _names_listed([f"{w} ({c})" for w, c in report.top_vocabulary[:8]]) + "."
    if report.ing_tails:
        text += (f" {_plural(report.ing_tails, 'sentence ends', 'sentences end')} in a participle tail such as “, "
                 f"highlighting the importance of ...”.")
    return text + (" These rates describe the text; they are not evidence of how it was written." if rates or
                   report.ing_tails else "")


def to_markdown(report: Report) -> str:
    counted = counted_findings(report.findings, report.final)
    later = _clusters([f for f in report.findings if f.stage == Stage.final.value])  # as listed: repeats are one item
    if report.final:
        mode = ("You are about to submit (the scan ran with --final), so the items under “Before submission, once the "
                "code is final” count in the readiness too.")
    else:
        mode = ("The manuscript is treated as work in progress: items for the last step before submission are listed "
                f"at the end and not counted in the readiness ({_plural(len(later), 'item')} this time). Run the scan "
                "with --final when you are about to submit, and they count too.")
    size = f"The body has about {report.words:,} words" + (f" and the Abstract {report.abstract_words:,}."
                                                         if report.abstract_words is not None else
                                                         "; no Abstract heading was found.")
    out = [f"# Mechanical scan of {Path(report.path).name}", "",
           "This scan checks what editors and screening tools can check mechanically: text left over from chat "
           "interfaces, placeholders, required statements, numbers that disagree with their counts, citations and "
           "references, length limits, and wording that screeners count. It reports and never rewrites. Whether a "
           "claim is calibrated, or a denominator reported, is left to the full review.", "",
           f"**Readiness:** {_verdict(counted)}", "", mode, "", size + " " + _vocabulary_sentence(report), ""]
    if report.findings:
        out += [SEVERITY_KEY, ""]
    out += _stage_lines(report.findings)
    if any(r.status != "not_checked" for r in report.references):
        out += ["## Each reference as checked", ""] + _reference_rows(report.references)
    out += _inline_section(report.inline_ids)
    return "\n".join(out).rstrip("\n") + "\n"


@app.command()
def main(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    online: Annotated[bool, typer.Option(help="Resolve DOIs, PMIDs and arXiv ids over the network")] = False,
    references_only: Annotated[bool, typer.Option(help="Check references and citation consistency without other audit checks")] = False,
    search_unidentified: Annotated[bool, typer.Option(help="With --online, search Crossref by the entry text for "
                                                           "references with no identifier or one that does not "
                                                           "resolve; --no-search-unidentified keeps reference "
                                                           "text on this machine")] = True,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the full report as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the Markdown report here (default: stdout)")] = None,
    venue: Annotated[Optional[str], typer.Option(help="Venue key from references/venues.yaml")] = None,
    git: Annotated[bool, typer.Option(help="Only when the authors ask: count commits touching the file that carry an AI "
                                            "co-author trailer (informational; trailers often mark automation)")] = False,
    final: Annotated[bool, typer.Option(help="The authors are about to submit: count the end-stage items (statements, "
                                              "archives, placeholders) in the readiness and the exit code")] = False,
    unidentified: Annotated[str, typer.Option(help="strict: an entry with no identifier never passes, a Crossref "
                                                   "match is a candidate to confirm (at least minor); lax: a close "
                                                   "match falls to info")] = "strict",
) -> None:
    """Exit 0 clean, 1 a blocker, 3 (with --online) no blocker but a lookup that did not answer, so the run
    cannot be called clean; 2 usage."""
    if unidentified not in ("strict", "lax"):
        raise typer.BadParameter("--unidentified takes strict or lax")
    if references_only:
        if venue or git:
            raise typer.BadParameter("--references-only cannot be combined with --venue or --git")
        report = check_references(path, online, search_unidentified, unidentified=unidentified)
        md = references_to_markdown(report)
        counted = report.findings
    else:
        known = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))["venues"]
        if venue and venue not in known:
            raise typer.BadParameter(f"unknown venue {venue!r}; known: {', '.join(sorted(known))}")
        report = scan(path, online, search_unidentified, venue, git, final, unidentified)
        md = to_markdown(report)
        counted = counted_findings(report.findings, final)
    if json_out:
        json_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {md_out}")
    else:
        typer.echo(md)
    if any(f.severity == Severity.blocker for f in counted):
        raise typer.Exit(code=1)
    unchecked = unchecked_lookups(report.references, report.inline_ids) if online else 0
    if unchecked:
        typer.echo(f"{_plural(unchecked, 'online lookup')} did not answer, so the run cannot be called clean "
                   f"(exit code 3).", err=True)
    raise typer.Exit(code=3 if unchecked else 0)


if __name__ == "__main__":
    app()
