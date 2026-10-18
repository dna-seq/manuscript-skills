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
"""

from __future__ import annotations

import csv
import fnmatch
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


class ReferenceReport(BaseModel):
    path: str
    online: bool
    findings: list[Finding]
    references: list[Reference]


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
    r"\[citation needed\]",
    r"\[ref(?:erence)?s?\??\]",
    r"\(\?\?\)|\?\?",
    r"\bto be (?:finalized|added|confirmed|completed)\b",
    r"\bFigure\s+X\b|\bTable\s+X\b",
    r"lorem ipsum",
]

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


def _agent_patterns() -> list[str]:
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
    """A finding about one bibliography entry: its section names the BibTeX file and key, or the reference
    list, and its quote is the entry as read."""
    if finding.section is None:
        finding.section = f"{ref._bib_file}, entry {ref._bib_key}" if ref._bib_file else "References"
    if not finding.quote:
        finding.quote, finding.quote_span = _quote(ref.text)
    return finding


def _scan_patterns(lines: list[str], patterns: list[str], check: str, severity: Severity, message: str,
                   suggestion: str, flags: int = re.IGNORECASE, stop_line: Optional[int] = None) -> list[Finding]:
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
                                               suggestion=suggestion), line, m.start(), m.end()))
    return out


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


def _parse_bib(text: str) -> tuple[list[tuple[str, int, dict[str, str]]], list[tuple[int, str]]]:
    """(key, line, raw fields) for each entry, and (line, why) for each that does not parse. @string macros are
    substituted, @comment and @preamble skipped, and an entry may close with } or )."""
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
            errors.append((line, str(exc)))
            break
        i = end
        if kind in ("comment", "preamble"):
            continue
        body = text[m.end():end - 1]
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
            fields: dict[str, str] = {}
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
            errors.append((line, str(exc)))
    return entries, errors


def _bib_plain(value: str) -> str:
    """An identifier field as written: braces gone, LaTeX escapes of URL characters undone."""
    return re.sub(r"\\([_%&#~$])", r"\1", value).replace("{", "").replace("}", "").strip()


def classify_url(url: str) -> tuple[str, str]:
    """("doi" | "arxiv" | "pmid" | "url", value): a URL on doi.org, arxiv.org or PubMed is that identifier."""
    u = urllib.parse.urlsplit(url)
    host, path = (u.hostname or "").lower(), urllib.parse.unquote(u.path)
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
    return list(dict.fromkeys(ids))


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


def _bib_references(bib: Path, errors: Optional[list[tuple[int, str]]] = None) -> list[tuple[str, "Reference"]]:
    """(cite key, Reference) for each BibTeX entry; text is "author (year). title. venue" for matching. Entries
    that do not parse are appended to *errors* as (line, why)."""
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
            out.append(Finding(check="declarations", severity=severity,
                               message=f"No '{label}' statement was found in the manuscript.",
                               suggestion=f"Add a '{label}' section in the form the chosen journal asks for, once "
                                          f"the code, data and results are final."))
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
        out.append(Finding(check="ai-use", severity=Severity.info,
                           message="AI tools are named, but no model version appears anywhere in the manuscript.",
                           suggestion="If these are tools the authors used, give a model identifier only where the "
                                      "journal or reproducibility needs it. Do not invent a version that is not "
                                      "known, and do not add dates or prompts unless they are asked for."))
    out.extend(mentions)
    return out


def _vocabulary(body_text: str) -> tuple[dict[str, float], list[tuple[str, int]], int]:
    """Hits per 1000 words for each source list, and the most frequent listed words."""
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", body_text)
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


def _citation_consistency(body: list[tuple[int, str]], refs: list[Reference]) -> list[Finding]:
    """In-text citations with no matching bibliography entry, and entries the text never cites."""
    if not refs:
        return []
    out: list[Finding] = []
    ref_tokens = [(_entry_tokens(r.text), r.text, _acronym(r.text), r) for r in refs]
    numeric_max = 0
    cited_surnames: set[str] = set()
    for i, line in body:
        for m in NUMERIC_CITE_RE.finditer(line):
            for part in re.split(r"[,\s]+", m.group(1)):
                bounds = [int(x) for x in re.split(r"[-–]", part) if x.strip().isdigit()]
                numeric_max = max([numeric_max, *bounds])
        groups = [(g.group(1), g.start(), g.end(), False) for g in PAREN_GROUP_RE.finditer(line)]
        if line.lstrip().startswith("|"):  # a table's reference column: "| McLaren et al., 2016 |"
            groups += [(c.group(1), c.start(), c.end(), True)
                       for c in re.finditer(r"\|([^|()]*(?:19|20)\d{2}[^|()]*)(?=\|)", line)]
        for group, start, end, whole in groups:
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
                    out.append(_with_quote(Finding(
                        check="citations", severity=Severity.major, line=i, excerpt=_excerpt(line, start, end),
                        message=f"The in-text citation '{name} {year}' has no bibliography entry with that surname "
                                f"and year.",
                        suggestion="Add the entry, with its DOI, or correct the citation."), line, start, end))
    if numeric_max > len(refs):
        out.append(Finding(check="citations", severity=Severity.major,
                           message=f"The text cites reference [{numeric_max}], but the bibliography has only "
                                   f"{len(refs)} entries.",
                           suggestion="Renumber the citations, or restore the missing entries."))
    if cited_surnames:
        for ref in refs:
            first_author = _name_words(ref.text[:120])[:1]
            if first_author and first_author[0] not in cited_surnames:
                out.append(_ref_finding(ref, Finding(
                    check="citations", severity=Severity.minor, line=ref.line, excerpt=ref.text[:100],
                    stage=Stage.writing.value, message="This bibliography entry is never cited in the text.",
                    suggestion="Cite it where it supports a claim, or remove it.")))
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


def _abstract_parts(lines: list[str]) -> list[tuple[str, int]]:
    """(label, words after the label) for each labelled part of a structured abstract ("Motivation:", "Results:");
    empty unless at least two parts are labelled."""
    parts: list[tuple[str, int]] = []
    for line in lines:
        m = ABSTRACT_PART.match(line)
        if m:
            parts.append((m.group("label").strip(), len(WORD_RE.findall(line[m.end():]))))
        elif parts:
            parts[-1] = (parts[-1][0], parts[-1][1] + len(WORD_RE.findall(line)))
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
                           message="No archived copy of the software or data is cited (for example on Zenodo, "
                                   "Software Heritage, figshare, Bioconductor or CRAN).",
                           suggestion="An archive and its DOI come once the code is final. Whether the journal or the "
                                      "paper's reproducibility needs one is checked separately "
                                      "(manuscript-reporting-check)."))
    if re.search(r"leave[- ]one[- ]out", text_lower):
        out.append(Finding(check="validation", severity=Severity.info,
                           message="The manuscript mentions leave-one-out validation.",
                           suggestion="Some journals reject machine-learning papers validated by leave-one-out alone, "
                                      "so report the performance on an independent test set as well."))
    limits = load_venue_limits().get(venue or "")
    name, url = venue_name_and_url(venue) if venue else ("", None)
    guidelines = f" ({url})" if url else ""
    if limits:
        abstract_max, body_max = limits.get("abstract_words"), limits.get("body_words")
        returned_at = limits.get("over_limit_return")
        body_rule = (" The count runs from the start of the file to the reference list and includes the title, "
                     "headings, tables and back matter, so it is approximate.")
        if body_max is None:
            out.append(Finding(check="venue", severity=Severity.info,
                               message=f"No body length limit is recorded for {name}, so the body length was not "
                                       f"checked.",
                               suggestion=f"Check the length or page limit in the journal's author "
                                          f"guidelines{guidelines}."))
        if abstract_max is not None and abstract_words is not None and abstract_words > abstract_max:
            out.append(Finding(check="venue", severity=Severity.major, section="Abstract",
                               message=f"The Abstract has {abstract_words} words, and {name} asks for at most "
                                       f"{abstract_max}. The count includes everything between the Abstract heading "
                                       f"and the next heading, labels included."
                                       + (_counted_parts(abstract_parts) if abstract_parts else ""),
                               suggestion=f"Cut it to the limit, after checking in the author guidelines{guidelines} "
                                          f"which parts of a structured abstract count."))
        if body_max is None:
            pass
        elif returned_at and body_words > returned_at * body_max:
            out.append(Finding(check="venue", severity=Severity.blocker,
                               message=f"The body has about {body_words} words, more than "
                                       f"{round(100 * (returned_at - 1))}% over the limit of about {body_max} for "
                                       f"{name}, and the journal returns such manuscripts without review." + body_rule,
                               suggestion="Move material to the supplement."))
        elif body_words > body_max:
            out.append(Finding(check="venue", severity=Severity.major,
                               message=f"The body has about {body_words} words, over the limit of about {body_max} "
                                       f"for {name}." + body_rule,
                               suggestion=f"Trim it, or check the page count in the journal's template{guidelines}."))
    elif venue:
        out.append(Finding(check="venue", severity=Severity.info,
                           message=f"No length limits are recorded for {name}, so the length was not checked.",
                           suggestion=f"Check the limits in the journal's author guidelines{guidelines}."))
    return out


def _dashes(lines: list[str], stop_line: Optional[int]) -> list[Finding]:
    count = sum(l.count("—") for l in lines[: (stop_line or len(lines) + 1) - 1])
    if count == 0:
        return []
    first = next(i for i, l in enumerate(lines, start=1) if "—" in l)
    return [Finding(check="style", severity=Severity.minor, line=first,
                    message=f"{count} em-dashes in the body.",
                    suggestion="Readers and screeners treat dense em-dash use as an LLM tell; use commas, colons, "
                               "parentheses or two sentences.")]


# --------------------------------------------------------------------------------------------------
# Online reference resolution
# --------------------------------------------------------------------------------------------------

def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower())


def _similarity(title: str, entry: str) -> float:
    """How much of the resolved title appears in the citation text (0..1)."""
    t, e = _norm(title).split(), set(_norm(entry).split())
    if not t:
        return 0.0
    token = sum(1 for w in t if w in e) / len(t)
    return max(token, SequenceMatcher(None, _norm(title), _norm(entry)).find_longest_match().size / max(len(_norm(title)), 1))


def _get(client: httpx.Client, url: str, **params: str) -> Optional[httpx.Response]:
    """GET with retries on 429 and 5xx. None means the service did not answer, never "not found"."""
    for attempt in range(3):
        try:
            r = client.get(url, params=params or None)
        except httpx.HTTPError:
            return None
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        return r
    return None


def _head(client: httpx.Client, url: str) -> Optional[httpx.Response]:
    try:
        return client.head(url, follow_redirects=False)
    except httpx.HTTPError:
        return None


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
        notes.append(f"On the {source} record but not in the citation's list: {', '.join(gaps[:8])}"
                     + (" …" if len(gaps) > 8 else "") + ".")
        level = "differs"
    if not ET_AL_RE.search(segment) and last < len(people) - 1:
        notes.append(f"The citation names {len(matched)} of the record's {len(people)} authors without 'et al.'")
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
        names = ", ".join(t for _, t in unknown[:8])
        if len(matched) == len(people) and all(i > max(used) for i, _ in unknown):
            notes.append(f"The {source} record lists {len(people)} author(s); the citation also names {names}. "
                         f"Registry lists can stop short; check the publisher's page if it matters.")
        else:
            notes.append(f"In the citation but not on the {source} record: {names}.")
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
            notes.append(f"Initials differ for {who}: citation {cited[:1].upper()}, record {shown}.")
            level = level if level != "consistent" else "initials"
        elif len(cited) > 1 and len(record_given[0]) > 1 and not (len(raw) <= 3 and raw.isupper()) \
                and not (cited.startswith(record_given[0]) or record_given[0].startswith(cited)):
            notes.append(f"Given name differs for {who}: citation {raw}, record {shown}.")
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
    title = (msg.get("title") or [""])[0]
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
            pv.title = (msg.get("title") or [""])[0]
            pv.venue = (msg.get("container-title") or [venue])[0]
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
        ref.resolved_title = (msg.get("title") or [""])[0]
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
    head = _head(client, f"https://doi.org/{ref.doi}")
    if head is not None and head.status_code in (301, 302, 303, 307, 308):
        ref.status = "resolved"
        ref.lookup_notes.append("The DOI exists (doi.org) but no Crossref or DataCite metadata was read.")
    elif head is not None and head.status_code == 404:
        ref.status = "unresolved"
    else:
        ref.status = "lookup_failed"
        ref.lookup_notes.append("Crossref and doi.org did not answer.")
    return None


def _resolve_datacite(client: httpx.Client, ref: Reference) -> bool:
    r = _get(client, f"https://api.datacite.org/dois/{ref.doi}")
    if r is None or r.status_code != 200:
        return False
    try:
        attrs = r.json()["data"]["attributes"]
    except (ValueError, KeyError, TypeError):
        return False
    ref.resolved_title = ((attrs.get("titles") or [{}])[0]).get("title")
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


def _resolve_pmid(client: httpx.Client, ref: Reference) -> Optional[tuple[str, str, Optional[str]]]:
    r = _get(client, "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", db="pubmed", id=ref.pmid or "",
             retmode="json")
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
    ref.resolved_title = doc.get("title", "")
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
        doi, title = str(item.get("DOI") or ""), (item.get("title") or [""])[0]
        if not doi or not title or item.get("type") == "posted-content" or doi.lower().startswith("10.48550/"):
            continue
        similarity = min(_similarity(title, ref.resolved_title or ""), _similarity(ref.resolved_title or "", title))
        theirs = {k for a in _crossref_authors(item) for k in _surname_keys(_split_author(a)[0])}
        if similarity >= 0.95 and theirs & ours:
            parts = (item.get("issued") or {}).get("date-parts") or [[None]]
            ref.published_version = PublishedVersion(
                doi=doi.lower(), title=title, venue=(item.get("container-title") or [hint])[0],
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
        title = (item.get("title") or [""])[0]
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
        ref.resolved_title = (items[0].get("title") or [""])[0]
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
                if ref.status in ("resolved", "retracted", "concern") and (
                        ref.title_similarity < 0.6 or ref.first_author_found is False):
                    ref.status = "mismatch"
                if ref.status in ("resolved", "retracted", "concern") and ref.resolved_authors and names_authors:
                    _compare_authors(ref, _record_source(ref))
            time.sleep(0.35)  # NCBI allows 3 req/s without a key; Crossref asks for politeness


def _record_source(ref: Reference) -> str:
    if ref.doi and not ARXIV_DOI_RE.match(ref.doi):
        return "DataCite" if any(n.startswith("DataCite") for n in ref.lookup_notes) else "Crossref"
    return "PubMed" if ref.pmid and not ref.arxiv else "arXiv"


def _reference_findings(refs: list[Reference], online: bool = False) -> list[Finding]:
    out: list[Finding] = []
    for ref in refs:
        short = ref.text[:140]
        if ref.status == "unresolved":
            ident, match = ref.doi or ref.pmid or ref.arxiv, ref._title_match
            if match and match["strong"]:
                out.append(Finding(check="references", severity=Severity.major, line=ref.line, excerpt=short,
                                   message=f"Identifier {ident} does not resolve. Crossref holds a record with this "
                                           f"title: doi:{match['doi']} '{match['title']}' (title similarity "
                                           f"{match['similarity']}, same first author).",
                                   suggestion="A mistyped identifier is the usual cause: compare that record with the "
                                              "entry (authors, year, journal), then correct the identifier."))
            else:
                found = (f"; Crossref's closest title match differs: doi:{match['doi']} '{match['title']}' (title "
                         f"similarity {match['similarity']}, first author shared: "
                         f"{'yes' if match['first_author_shared'] else 'no'})" if match else
                         "; the Crossref title search " + ("did not answer" if any(
                             "title search did not answer" in n for n in ref.lookup_notes) else "found no close record"))
                out.append(Finding(check="references", severity=Severity.blocker, line=ref.line, excerpt=short,
                                   message=f"Identifier {ident} does not resolve{found}.",
                                   suggestion="A typo in the identifier is the usual cause. Find the work by title, "
                                              "journal, volume and pages and correct the entry; a reference that no "
                                              "one can trace is a desk-reject trigger at several venues."))
        elif ref.status == "retracted":
            out.append(Finding(check="references", severity=Severity.blocker, line=ref.line, excerpt=short,
                               message="Cited work is marked as retracted"
                                       + (f" (source: {ref.retraction_source}"
                                          + (f"; notice {ref.retraction_notice}" if ref.retraction_notice else "")
                                          + ")." if ref.retraction_source else "."),
                               suggestion="Drop it, or cite it explicitly as retracted if the retraction is the point."))
        elif ref.status == "concern":
            out.append(Finding(check="references", severity=Severity.major, line=ref.line, excerpt=short,
                               message="Cited work carries an expression of concern"
                                       + (f" (source: {ref.retraction_source})." if ref.retraction_source else "."),
                               suggestion="Say so where it is cited, or support the claim with other work."))
        elif ref.status == "mismatch":
            notice = (f" The record it resolves to is marked {ref.retraction} ({ref.retraction_source})."
                      if ref.retraction in ("retracted", "concern") else "")
            out.append(Finding(check="references", severity=Severity.major, line=ref.line, excerpt=short,
                               message=f"Identifier resolves to '{ref.resolved_title}' by "
                                       f"{ref.resolved_first_author or '?'} (title similarity {ref.title_similarity}, "
                                       f"first author in citation: {ref.first_author_found}).{notice}",
                               suggestion="Correct the identifier or the citation text; check authors and year too."))
        elif ref.status == "lookup_failed":
            out.append(Finding(check="references", severity=Severity.info, line=ref.line, excerpt=short,
                               message="Lookup did not answer; identity and retraction not assessed ("
                                       + " ".join(ref.lookup_notes) + ")",
                               suggestion="Re-run later or check the record by hand. A failed lookup is not evidence "
                                          "that the reference is wrong."))
        elif ref.status == "no_identifier":
            weak = (ref.title_similarity or 0) < 0.6
            sev = Severity.major if weak and not ref.first_author_found else Severity.minor if weak else Severity.info
            if weak and ref.first_author_found:
                hint_author = " Same first author: the citation's title is probably shortened or altered; use the real one."
            else:
                hint_author = ""
            hint = (f" Best Crossref match: '{ref.resolved_title}' doi:{ref.doi} (similarity {ref.title_similarity})."
                    if ref.resolved_title else " Crossref found no match.")
            if (ref.title_similarity or 0) < 0.4 and not ref.first_author_found:
                hint += (" No close match: unverified, which is not evidence that the work does not exist (software, "
                         "web pages, reports and new works are often missing from Crossref). Search PubMed, the "
                         "publisher or the project page by title, journal, volume and pages.")
            out.append(Finding(check="references", severity=sev, line=ref.line, excerpt=short,
                               message="Reference carries no DOI, PMID or arXiv id." + hint + hint_author,
                               suggestion="Add the DOI (or PMID/arXiv id) after confirming title, authors, year."))
        elif ref.status == "not_checked" and not (ref.doi or ref.pmid or ref.arxiv):
            out.append(Finding(check="references", severity=Severity.minor, line=ref.line, excerpt=short,
                               message="Reference carries no DOI, PMID or arXiv id.",
                               suggestion="Run with --online to search Crossref, then add the identifier."))
        if ref.withdrawn:
            out.append(Finding(check="references", severity=Severity.major, line=ref.line, excerpt=short,
                               message=f"The cited preprint has been withdrawn by its authors ({ref.withdrawn_source}).",
                               suggestion="Cite the version or work that replaces it; its authors no longer stand by "
                                          "it. Keep it only to discuss the withdrawal."))
        pv = ref.published_version
        if pv is not None and pv.source in ("arxiv:comment", "crossref:title-search") \
                and ref.status not in ("unresolved", "mismatch"):
            said = f"The arXiv comment says '{pv.comment}'. " if pv.comment else ""
            found = (f"Crossref holds a record with the same title and a shared author: "
                     f"{', '.join(x for x in (pv.venue, pv.year) if x)}, doi:{pv.doi} (title similarity "
                     f"{pv.title_similarity})." if pv.doi else "No Crossref record with the same title was found.")
            out.append(Finding(check="references", severity=Severity.minor, line=ref.line, excerpt=short,
                               message=f"The cited preprint may have been published. {said}{found} A candidate to "
                                       f"confirm: neither arXiv nor Crossref links it to the preprint.",
                               suggestion="Open the published record, check that it is the same work and still reports "
                                          "what you cite, then cite it; keep the preprint if you need content the "
                                          "published version dropped."))
        elif pv is not None and ref.status not in ("unresolved", "mismatch"):
            where = ", ".join(x for x in (pv.venue, pv.year) if x) or "a journal"
            check = ""
            if pv.metadata_checked and (pv.title_similarity or 0) < 0.5 and not pv.shared_authors:
                check = " Its title and authors differ from the preprint's: confirm the link before switching."
            elif pv.metadata_checked:
                check = (f" Title similarity {pv.title_similarity}, shared authors: {pv.shared_authors}.")
            if pv.retraction in ("retracted", "concern"):
                check += f" The published version is marked {pv.retraction}."
            out.append(Finding(check="references", severity=Severity.minor, line=ref.line, excerpt=short,
                               message=f"Cites a preprint that has been published in {where}"
                                       + (f", doi:{pv.doi}" if pv.doi else "") + f" ({pv.source})." + check,
                               suggestion="Cite the published version after confirming it still reports what you "
                                          "cite: numbers, methods and author lists change between versions. Keep "
                                          "the preprint only if you need content the published version dropped."))
        if any(n.startswith("The entry names no author") for n in ref.lookup_notes):
            out.append(Finding(check="references", severity=Severity.info, line=ref.line, excerpt=short,
                               message=f"The entry names no author (no author field could be read); the record "
                                       f"lists {len(ref.resolved_authors)}. Authors were not compared.",
                               suggestion="Add the author list from the record, or check the entry's author field."))
        if ref.author_check == "differs" and ref.status not in ("unresolved", "mismatch"):
            out.append(Finding(check="references", severity=Severity(ref.author_severity or "minor"), line=ref.line,
                               excerpt=short, message="Author list differs from the record: " + " ".join(ref.author_notes),
                               suggestion="Check against the publisher's page. Registries truncate lists and spell "
                                          "names differently (initials, transliteration, particles); this is a "
                                          "metadata difference to check, not evidence of fabrication."))
    if online:
        unchecked = [r for r in refs if r.retraction == "not_checked" and r.status not in ("unresolved", "not_checked")]
        if unchecked:
            out.append(Finding(check="references", severity=Severity.info,
                               message=f"Retraction status not checked for {len(unchecked)} reference(s) (lines "
                                       f"{', '.join(str(r.line) for r in unchecked[:20])}): no registry that records "
                                       "retractions covers them (arXiv, DataCite, no identifier) or the lookup failed. "
                                       "They are not known to be clean.",
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
        return [Finding(check="ai-use", severity=Severity.info, message="--git: not a git repository, not checked.")]
    commits = [c for c in run.stdout.split("\x01") if c.strip()]
    ai = [c for c in commits if GIT_AI_TRAILER.search(c.split("\x00", 1)[-1])]
    if not ai:
        return []
    return [Finding(check="ai-use", severity=Severity.info,
                    message=f"{len(ai)} of {len(commits)} commits touching this file have an AI co-author trailer. "
                            "A trailer can mark automation (syncing comments, formatting), not writing.",
                    suggestion="Ask the authors what those commits changed; the disclosure follows their account.")]


def check_references(path: Path, online: bool, search_unidentified: bool) -> ReferenceReport:
    """Identity and citation consistency only, shared by focused checks and full audits."""
    raw = path.read_text(encoding="utf-8")
    text = _strip_comments(raw)
    lines = _lines(text)
    ref_start = _reference_start(lines)
    findings: list[Finding] = []
    refs: list[Reference] = []
    bibliography_only = path.suffix.lower() == ".bib"
    bibs = [path] if bibliography_only else _bib_files(text, path.parent) if path.suffix.lower() == ".tex" else []
    if bibs:
        keyed = []
        for bib in bibs:
            errors: list[tuple[int, str]] = []
            keyed += _bib_references(bib, errors)
            for line_no, why in errors:
                findings.append(Finding(check="references", severity=Severity.major, line=line_no,
                                        section=bib.name, stage=Stage.writing.value,
                                        message=f"A BibTeX entry in {bib.name} does not parse ({why}), so it was not "
                                                f"read or checked; the entries after it may be missing too.",
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
                    findings.append(Finding(check="references", severity=Severity.info, line=line_no,
                                            message=f"One paragraph holds {count} references; the scan split it at "
                                                    f"reference starts. Check the split in the table below.",
                                            suggestion="Put each reference on its own line, and move any lead-in "
                                                       "('Added in the revision:') out of the list."))
            if number:
                findings.append(Finding(check="references", severity=Severity.info, line=begin,
                                        excerpt=label.strip("*# "),
                                        message=f"A further reference list ({len(split)} entries) was checked with "
                                                f"the main one, and the text after the main list was read for "
                                                f"citations.", suggestion=""))
            for line_no, entry in split:
                doi = DOI_RE.search(entry)
                pmid = PMID_RE.search(entry)
                arxiv = ARXIV_RE.search(entry)
                refs.append(Reference(line=line_no, text=entry, doi=doi.group(1).rstrip(".") if doi else None,
                                      pmid=pmid.group(1) if pmid else None, arxiv=_arxiv_id(arxiv)))
        # Citations are read everywhere outside the lists: the body, and a supplement after the main list.
        cited_text = [(i, line) for i, line in enumerate(lines, start=1) if i not in in_lists]
        findings += _citation_consistency(cited_text, refs)
    if ref_start is None and not bibs:
        findings.append(Finding(check="references", severity=Severity.major,
                                message="No references/bibliography heading found; references were not checked.",
                                suggestion="Name the section 'References' or pass a .bib file separately."))
    elif not refs:
        findings.append(Finding(check="references", severity=Severity.major,
                                message="No bibliography entries could be parsed; references were not checked.",
                                suggestion="Check the bibliography format and inspect the entries manually."))
    if online and refs:
        resolve_references(refs, search_unidentified)
    findings += _reference_findings(refs, online)
    order = {s: i for i, s in enumerate(Severity)}
    findings.sort(key=lambda f: (order[f.severity], f.line or 0))
    return ReferenceReport(path=str(path), online=online, findings=findings, references=refs)


def scan(path: Path, online: bool, search_unidentified: bool, venue: Optional[str] = None,
         git: bool = False) -> Report:
    VOCAB_SOURCES.update({"kobak2025_r>=2": _kobak_words(), "juzek_ward2025": JUZEK_WARD,
                          "wikipedia_aivocab": WIKIPEDIA_AIVOCAB})
    raw = path.read_text(encoding="utf-8")
    text = _strip_comments(raw)
    lines = _lines(text)
    text_lower = text.lower()
    ref_start = _reference_start(lines)
    body_lines = lines[: (ref_start or len(lines) + 1) - 1]

    findings: list[Finding] = []
    findings += _scan_patterns(lines, CHATBOT_LEFTOVERS, "chatbot-leftover", Severity.blocker,
                               "Chat-interface text '{match}'.", "Delete it and re-read the surrounding passage.")
    # Placeholders are searched in the raw text too: an HTML-comment TODO still ships in the LaTeX.
    findings += _scan_patterns(_lines(raw), PLACEHOLDERS, "placeholder", Severity.major, "Placeholder '{match}'.",
                               "Resolve or remove before submission.", flags=0)
    findings += _declaration_findings(text_lower)
    findings += _ai_use_findings(lines, text_lower, ref_start, bool(ledger_ai(raw)))
    findings += _scan_patterns(body_lines, STOCK_PHRASES, "stock-phrase", Severity.minor, "Stock phrase '{match}'.",
                               "Say the specific thing instead, or cut the phrase.")
    findings += _scan_patterns(lines, MARKUP_ARTIFACTS, "chatbot-leftover", Severity.blocker,
                               "Chat-interface markup '{match}'.", "Delete it; check the citation it stood for.",
                               flags=0)
    findings += _scan_patterns(body_lines, TORTURED_PHRASES, "tortured-phrase", Severity.major,
                               "Tortured phrase '{match}' (paraphrase-tool fingerprint).",
                               "Use the standard term (see references/screening-signals.md §2.6).")
    findings += _scan_patterns(body_lines, FIRST_PERSON_SINGULAR, "first-person", Severity.info,
                               "First person singular '{match}'.",
                               "Chat text addresses a reader; a paper reports. Rephrase unless sole-authored.",
                               flags=0)
    findings += _scan_patterns(body_lines, OVERCLAIM, "overclaim", Severity.info, "Claim word '{match}'.",
                               "Keep only if the evidence in this paper supports it; prefer 'rediscovery' for "
                               "known answers and drop 'first/novel' unless a search shows it.")
    findings += _dashes(lines, ref_start)
    findings += _abstract_numbers(lines, ref_start)
    findings += _abstract_metric_dump(lines)
    findings += _percentages(body_lines)

    reference_report = check_references(path, online, search_unidentified)
    refs = reference_report.references
    findings += reference_report.findings
    if git:
        findings += _git_findings(path.resolve())
    ai_marks = ledger_ai(raw)
    if ai_marks:
        findings.append(Finding(check="ai-use", severity=Severity.info,
                                message=f"{len(ai_marks)} revision-ledger segments name an AI as reviser "
                                        f"({', '.join(sorted(set(ai_marks)))}).",
                                suggestion="Markers do not establish the kind of help. Use existing author "
                                           "context and the selected venue's rule and exemptions to determine "
                                           "whether a disclosure needs updating."))
    densities, top, n_words = _vocabulary("\n".join(body_lines))
    ing_tails = len(ING_TAIL_RE.findall("\n".join(body_lines)))
    if n_words and 1000 * ing_tails / n_words > 1.0:
        findings.append(Finding(check="style", severity=Severity.minor,
                                message=f"{ing_tails} sentences end in a participle tail (', highlighting ...').",
                                suggestion="State the consequence as its own claim with its evidence, or cut it."))
    span = _abstract_span(lines)
    abstract_words = (len(re.findall(r"[A-Za-z0-9][\w'-]*", "\n".join(lines[span[0]:span[1]]))) if span else None)
    findings += _venue_findings(lines, n_words, abstract_words, venue, text_lower)
    if densities["kobak2025_r>=2"] > 3.0:
        findings.append(Finding(check="vocabulary", severity=Severity.minor,
                                message=f"Kobak excess-style words at {densities['kobak2025_r>=2']} per 1000 words "
                                        f"(top: {', '.join(f'{w}×{c}' for w, c in top[:6])}).",
                                suggestion="Use the specific word or a number; a density, not proof of anything."))
    seen: set[tuple[str, Optional[int]]] = set()
    deduped: list[Finding] = []
    for f in findings:  # overlapping patterns ("TODO" inside "AUTHOR TODO") report a line once
        key = (f.check, f.line)
        if f.check in ("chatbot-leftover", "placeholder") and key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    findings = deduped
    order = {s: i for i, s in enumerate(Severity)}
    findings.sort(key=lambda f: (order[f.severity], f.line or 0))
    return Report(path=str(path), words=n_words, abstract_words=abstract_words, findings=findings, references=refs,
                  vocabulary_per_1000_words=densities, top_vocabulary=top, ing_tails=ing_tails)


def _verdict(counts: Counter[str]) -> str:
    if counts.get("blocker"):
        return f"not ready: {counts['blocker']} desk-reject trigger(s) to fix first"
    if counts.get("major"):
        return f"fix before submitting: {counts['major']} major finding(s), no desk-reject trigger"
    return "no blocker or major finding from the mechanical checks; the judgement checks in the skill still apply"


def references_to_markdown(report: ReferenceReport) -> str:
    out = [f"# Reference check: {report.path}", "",
           f"{len(report.references)} bibliography entries; {len(report.findings)} mechanical findings.", "",
           "Source support requires reading the cited work; identifier resolution alone does not establish it."]
    if not report.online:
        out += ["Online source identity and retraction checks: not assessed (offline mode)."]
    for finding in report.findings:
        location = f"L{finding.line}" if finding.line else "—"
        out += ["", f"- **{finding.severity.value} / {finding.check}** {location}: {finding.message}"
                + (f" `{finding.excerpt}`" if finding.excerpt else "")
                + (f"\n  → {finding.suggestion}" if finding.suggestion else "")]
    if report.online and report.references:
        states = Counter(ref.retraction for ref in report.references)
        out += ["", "Retraction check: " + ", ".join(f"{states[s]} {s}" for s in
                                                    ("retracted", "concern", "none_found", "not_checked") if states[s])
                + ". `not_checked` means no registry that records retractions answered for that entry; it is not "
                  "known to be clean."]
    if report.references:
        out += ["", "## References", "", "| line | status | id | resolved title | retraction | notes |",
                "|---|---|---|---|---|---|"]
        for ref in report.references:
            ident = ref.doi or (f"PMID {ref.pmid}" if ref.pmid else "") or (f"arXiv {ref.arxiv}" if ref.arxiv else "")
            title = (ref.resolved_title or "").replace("|", "\\|").replace("\n", " ")
            retraction = ref.retraction + (f" ({ref.retraction_source})" if ref.retraction_source else "")
            notes = []
            if ref.published_version:
                notes.append(f"published: {ref.published_version.doi or ref.published_version.venue}")
            if ref.withdrawn:
                notes.append("withdrawn")
            if ref.author_check == "differs":
                notes.append("authors differ")
            notes += [n for n in ref.author_notes if "stop short" in n]
            cell = "; ".join(notes).replace("|", "\\|")
            out.append(f"| {ref.line} | {ref.status} | {ident} | {title} | {retraction} | {cell} |")
    return "\n".join(out) + "\n"


def to_markdown(report: Report) -> str:
    counts = Counter(f.severity.value for f in report.findings)
    out = [f"# Mechanical scan: {report.path}", "",
           f"**Readiness:** {_verdict(counts)}", "",
           f"{report.words} words in the body, {report.abstract_words or '?'} in the abstract; findings: "
           + ", ".join(f"{counts.get(s.value, 0)} {s.value}" for s in Severity), "",
           "Listed vocabulary per 1000 words (density, not a verdict): "
           + ", ".join(f"{k} {v}" for k, v in report.vocabulary_per_1000_words.items())
           + f"; top: {', '.join(f'{w}×{c}' for w, c in report.top_vocabulary[:10]) or 'none'}; "
           f"participle tails: {report.ing_tails}", ""]
    for sev in Severity:
        group = [f for f in report.findings if f.severity == sev]
        if not group:
            continue
        out += [f"## {sev.value} ({len(group)})", ""]
        for f in group:
            loc = f"L{f.line}" if f.line else "—"
            out.append(f"- **{f.check}** {loc}: {f.message}" + (f" `{f.excerpt}`" if f.excerpt else "")
                       + (f"\n  → {f.suggestion}" if f.suggestion else ""))
        out.append("")
    checked = [r for r in report.references if r.status != "not_checked"]
    if checked:
        out += ["## References", "", "| line | status | id | resolved title | sim |", "|---|---|---|---|---|"]
        for r in report.references:
            ident = r.doi or (f"PMID {r.pmid}" if r.pmid else "") or (f"arXiv {r.arxiv}" if r.arxiv else "")
            out.append(f"| {r.line} | {r.status} | {ident} | {(r.resolved_title or '')[:90]} | {r.title_similarity or ''} |")
    return "\n".join(out) + "\n"


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
) -> None:
    if references_only:
        if venue or git:
            raise typer.BadParameter("--references-only cannot be combined with --venue or --git")
        report = check_references(path, online, search_unidentified)
        md = references_to_markdown(report)
    else:
        known = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))["venues"]
        if venue and venue not in known:
            raise typer.BadParameter(f"unknown venue {venue!r}; known: {', '.join(sorted(known))}")
        report = scan(path, online, search_unidentified, venue, git)
        md = to_markdown(report)
    if json_out:
        json_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {md_out}")
    else:
        typer.echo(md)
    raise typer.Exit(code=1 if any(f.severity == Severity.blocker for f in report.findings) else 0)


if __name__ == "__main__":
    app()
