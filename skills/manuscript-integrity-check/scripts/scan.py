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
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import time
from collections import Counter
from difflib import SequenceMatcher
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import httpx
import typer
import yaml
from pydantic import BaseModel

app = typer.Typer(add_completion=False, no_args_is_help=True)

USER_AGENT = "manuscript-integrity-check/1.0 (pre-submission self-check; mailto:none@example.invalid)"


class Severity(str, Enum):
    blocker = "blocker"  # a desk-reject trigger by itself
    major = "major"  # an editor or reviewer will object
    minor = "minor"  # style or calibration
    info = "info"  # needs a human look, may be fine


class Finding(BaseModel):
    check: str
    severity: Severity
    line: Optional[int] = None
    excerpt: str = ""
    message: str
    suggestion: str = ""


class Reference(BaseModel):
    line: int
    text: str
    doi: Optional[str] = None
    pmid: Optional[str] = None
    arxiv: Optional[str] = None
    resolved_title: Optional[str] = None
    resolved_year: Optional[str] = None
    resolved_first_author: Optional[str] = None
    first_author_found: Optional[bool] = None
    title_similarity: Optional[float] = None
    # not_checked | resolved | mismatch | unresolved | retracted | concern | no_identifier
    status: str = "not_checked"


class Report(BaseModel):
    path: str
    words: int
    abstract_words: Optional[int] = None
    findings: list[Finding]
    references: list[Reference]
    vocabulary_per_1000_words: dict[str, float]
    top_vocabulary: list[tuple[str, int]]
    ing_tails: int = 0


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
    ("Data availability", [r"data availability", r"availability of data"], Severity.major),
    ("Code / software availability", [r"code availability", r"software availability", r"code and data availability",
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
# HTML-comment revision markers that name an AI as the reviser of a segment
# (`<!-- @rev ID rounds=N by=name:date,... -->`, the format of the manuscript ledger in dna-seq/just-dna-lite).
LEDGER_AI = re.compile(r"<!--\s*@rev\b[^>]*\bby=[^>]*\b(claude|gpt|chatgpt|gemini|copilot|ai|llm)\b", re.IGNORECASE)
MODEL_VERSION = re.compile(
    r"(?:claude[- ](?:opus|sonnet|haiku|fable)?[- ]?\d|gpt-?\d(?:\.\d)?(?:-\w+)?|gemini[- ]\d(?:\.\d)?|"
    r"llama[- ]?\d|qwen\d?|deepseek-\w+|claude-[a-z]+-\d)",
    re.IGNORECASE,
)

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>)\],;]+)", re.IGNORECASE)
PMID_RE = re.compile(r"\bPMID:?\s*(\d{5,9})\b", re.IGNORECASE)
ARXIV_RE = re.compile(r"\barXiv\W{0,3}(\d{4}\.\d{4,5})(?:v\d+)?\b|arxiv\.org/abs/(\d{4}\.\d{4,5})", re.IGNORECASE)
# Author-year citations in the text: "(Lambert et al., 2021)", "Lambert et al. (2021)", "(Illumina, 2023; ...)".
AUTHOR_YEAR_RE = re.compile(r"([A-Z][A-Za-z'\-]+(?: (?:et al\.|and|&) ?[A-Z]?[A-Za-z'\-]*)?),? \(?((?:19|20)\d{2})(?!\d)[a-z]?\)?")
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


def _scan_patterns(lines: list[str], patterns: list[str], check: str, severity: Severity, message: str,
                   suggestion: str, flags: int = re.IGNORECASE, stop_line: Optional[int] = None) -> list[Finding]:
    compiled = [re.compile(p, flags) for p in patterns]
    out: list[Finding] = []
    for i, line in enumerate(lines, start=1):
        if stop_line is not None and i >= stop_line:
            break
        for rx in compiled:
            for m in rx.finditer(line):
                out.append(Finding(check=check, severity=severity, line=i, excerpt=_excerpt(line, m.start(), m.end()),
                                   message=message.format(match=m.group(0)), suggestion=suggestion))
    return out


def _reference_start(lines: list[str]) -> Optional[int]:
    for i, line in enumerate(lines, start=1):
        if REF_HEADING.search(line.strip()) or LATEX_REF_HEADING.search(line):
            return i
    return None


def _reference_entries(lines: list[str], start: Optional[int]) -> list[tuple[int, str]]:
    """Each non-empty line after the references heading, up to the next heading, is one entry."""
    if start is None:
        return []
    entries: list[tuple[int, str]] = []
    for i in range(start, len(lines)):
        line = lines[i].strip()
        if HEADING.match(line):
            break
        if len(line) < 25 or (line.startswith("*(") and line.endswith(")*")):
            continue
        entries.append((i + 1, line))
    return entries


def _split_entries(entries: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """A line holding several DOI-terminated references becomes one entry per DOI."""
    out: list[tuple[int, str]] = []
    for line_no, text in entries:
        dois = list(DOI_RE.finditer(text))
        if len(dois) < 2:
            out.append((line_no, text))
            continue
        start = 0
        for m in dois:
            out.append((line_no, text[start:m.end()].strip(" .;")))
            start = m.end()
        if len(text[start:].strip(" .;")) >= 25:
            out.append((line_no, text[start:].strip(" .;")))
    return out


LATEX_BIB = re.compile(r"\\(?:bibliography|addbibresource)\{([^}]+)\}")
LATEX_CITE_KEYS = re.compile(r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]+)\}")
BIB_ENTRY = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,(.*?)\n\}", re.DOTALL)
BIB_FIELD = re.compile(r"(\w+)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|\"[^\"]*\"|\d+)", re.DOTALL)


def _bib_files(tex: str, base: Path) -> list[Path]:
    out: list[Path] = []
    for m in LATEX_BIB.finditer(tex):
        for name in m.group(1).split(","):
            f = base / name.strip()
            f = f if f.suffix == ".bib" else f.with_suffix(".bib")
            if f.exists():
                out.append(f)
    return out


def _bib_references(bib: Path) -> list[tuple[str, "Reference"]]:
    """(cite key, Reference) for each BibTeX entry; text is "author (year). title. venue" for matching."""
    text = bib.read_text(encoding="utf-8")
    out: list[tuple[str, Reference]] = []
    for m in BIB_ENTRY.finditer(text):
        fields = {k.lower(): re.sub(r"[{}\s]+", " ", v.strip('{}"')).strip() for k, v in BIB_FIELD.findall(m.group(3))}
        line = text[: m.start()].count("\n") + 1
        venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or ""
        entry = f"{fields.get('author', '')} ({fields.get('year', '')}). {fields.get('title', '')}. {venue}"
        arxiv = ARXIV_RE.search(" ".join(fields.get(k, "") for k in ("eprint", "journal", "note", "url")))
        eprint = fields.get("eprint") if fields.get("archiveprefix", "").lower() == "arxiv" else None
        out.append((m.group(2), Reference(line=line, text=entry, doi=fields.get("doi") or None,
                                          pmid=fields.get("pmid") or None,
                                          arxiv=eprint or ((arxiv.group(1) or arxiv.group(2)) if arxiv else None))))
    return out


def _cite_key_findings(tex_lines: list[str], keys: set[str]) -> list[Finding]:
    out: list[Finding] = []
    for i, line in enumerate(tex_lines, start=1):
        for m in LATEX_CITE_KEYS.finditer(line):
            for key in (k.strip() for k in m.group(1).split(",")):
                if key and key not in keys:
                    out.append(Finding(check="citations", severity=Severity.major, line=i, excerpt=key,
                                       message=f"\\cite key '{key}' is not in the bibliography file.",
                                       suggestion="Add the entry (with DOI) or fix the key."))
    return out


def _declaration_findings(text_lower: str) -> list[Finding]:
    out: list[Finding] = []
    for label, patterns, severity in DECLARATIONS:
        if not any(re.search(p, text_lower) for p in patterns):
            out.append(Finding(check="declarations", severity=severity, message=f"No '{label}' statement found.",
                               suggestion=f"Add a '{label}' section in the venue's required form."))
    return out


def _ai_use_findings(lines: list[str], text_lower: str, ref_start: Optional[int],
                     revision_markers: bool = False) -> list[Finding]:
    body = lines[: (ref_start or len(lines) + 1) - 1]
    mentions = _scan_patterns(body, AI_TOOL_MENTIONS, "ai-use", Severity.info,
                              "AI tool or LLM mentioned ('{match}').",
                              "If this describes the authors' own use, check the selected venue's disclosure "
                              "rule and exemptions.")
    out: list[Finding] = []
    has_disclosure = any(re.search(p, text_lower) for p in AI_DISCLOSURE)
    if (mentions or revision_markers) and not has_disclosure:
        out.append(Finding(check="ai-use", severity=Severity.info,
                           line=mentions[0].line if mentions else None,
                           excerpt=mentions[0].excerpt if mentions else "",
                           message="AI-related text or revision markers found; no AI-use statement recognised.",
                           suggestion="Determine whether this concerns the authors' own use and whether the "
                                      "selected venue requires a statement for it. Apply exemptions; add only "
                                      "required fields and placements. This automated check cannot establish "
                                      "a disclosure violation."))
    named = [f for f in mentions if re.search(r"claude|gpt|gemini|llama|mistral|copilot|cursor|deepseek|qwen|opus|sonnet",
                                              f.message, re.IGNORECASE)]
    if named and not MODEL_VERSION.search("\n".join(body)):
        out.append(Finding(check="ai-use", severity=Severity.info,
                           message="AI tools are named but no model version appears anywhere.",
                           suggestion="If these are tools the authors used, supply a model identifier only "
                                      "where the venue or reproducibility requires it. Do not invent an "
                                      "unavailable version or require dates and prompts by default."))
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
                out.append(Finding(check="numbers", severity=Severity.major, line=i,
                                   excerpt=_excerpt(line, m.start(), m.end()),
                                   message=f"{num}/{den} is {actual:.{max(decimals, 1)}f}%, not {stated}%.",
                                   suggestion="Recompute from the counts (and check the counts against the data)."))
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
    return [Finding(check="abstract", severity=Severity.minor,
                    line=span[0], excerpt=", ".join(m.strip() for m in metrics[:8]),
                    message=f"The abstract reports {len(metrics)} metrics; check readability in context.",
                    suggestion="Keep the quantitative evidence needed for its claims and the venue's format. "
                               "A metric count alone is not a submission defect or a reason to remove results.")]


def _abstract_numbers(lines: list[str], ref_start: Optional[int]) -> list[Finding]:
    """Numbers stated in the abstract that never appear again in the body: check each by hand."""
    start = next((i for i, l in enumerate(lines) if ABSTRACT_HEADING.search(l.strip())), None)
    if start is None:
        return []
    end = next((i for i in range(start + 1, len(lines)) if HEADING.match(lines[i].strip())), len(lines))
    abstract = "\n".join(lines[start + 1:end])
    body = "\n".join(lines[end:(ref_start or len(lines) + 1) - 1])
    out: list[Finding] = []
    for m in NUMBER_RE.finditer(abstract):
        if m.group(1) not in body:
            out.append(Finding(check="numbers", severity=Severity.info, excerpt=m.group(0),
                               message=f"Abstract figure '{m.group(0)}' does not reappear in the body.",
                               suggestion="Confirm it is derived from a reported result (table, figure or text)."))
    return out


def _name_tokens(text: str) -> list[str]:
    """Words with apostrophes and hyphens folded away, so O'Daniel and Tandy-Connor match themselves."""
    return [re.sub(r"[^a-z]", "", w.lower()) for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*", text)]


def _citation_consistency(body_lines: list[str], refs: list[Reference]) -> list[Finding]:
    """In-text citations with no matching bibliography entry, and entries the text never cites."""
    if not refs:
        return []
    out: list[Finding] = []
    ref_tokens = [(set(_name_tokens(r.text)), r.text) for r in refs]
    numeric_max = 0
    cited_surnames: set[str] = set()
    for i, line in enumerate(body_lines, start=1):
        for m in NUMERIC_CITE_RE.finditer(line):
            for part in re.split(r"[,\s]+", m.group(1)):
                bounds = [int(x) for x in re.split(r"[-–]", part) if x.strip().isdigit()]
                numeric_max = max([numeric_max, *bounds])
        for group in PAREN_GROUP_RE.finditer(line):
            for m in AUTHOR_YEAR_RE.finditer(group.group(1)):
                surname, year = m.group(1).split()[0], m.group(2)
                key = _name_tokens(surname)[0]
                cited_surnames.add(key)
                if not any(key in tokens and year in text for tokens, text in ref_tokens):
                    out.append(Finding(check="citations", severity=Severity.major, line=i,
                                       excerpt=_excerpt(line, group.start(), group.end()),
                                       message=f"In-text citation '{surname} {year}' has no bibliography entry "
                                               f"with that surname and year.",
                                       suggestion="Add the entry (with DOI) or fix the citation."))
    if numeric_max > len(refs):
        out.append(Finding(check="citations", severity=Severity.major,
                           message=f"Text cites [{numeric_max}] but the bibliography has {len(refs)} entries.",
                           suggestion="Renumber, or restore the missing entries."))
    if cited_surnames:
        for ref in refs:
            first_author = _name_tokens(ref.text)[:1]
            if first_author and first_author[0] not in cited_surnames:
                out.append(Finding(check="citations", severity=Severity.minor, line=ref.line, excerpt=ref.text[:100],
                                   message="Bibliography entry is never cited in the text.",
                                   suggestion="Cite it where it supports a claim, or remove it."))
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


ARCHIVE_RE = re.compile(r"zenodo|10\.5281/|softwareheritage|swh:1:|figshare|10\.6084/|bioconductor|cran\.r-project",
                        re.IGNORECASE)


def _abstract_span(lines: list[str]) -> Optional[tuple[int, int]]:
    start = next((i for i, l in enumerate(lines) if ABSTRACT_HEADING.search(l.strip())), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if HEADING.match(lines[i].strip())), len(lines))
    return start + 1, end


def _venue_findings(lines: list[str], body_words: int, abstract_words: Optional[int], venue: Optional[str],
                    text_lower: str) -> list[Finding]:
    out: list[Finding] = []
    if not ARCHIVE_RE.search(text_lower):
        out.append(Finding(check="availability", severity=Severity.major,
                           message="No archived software or data record (Zenodo, Software Heritage, figshare, "
                                   "Bioconductor, CRAN) is cited.",
                           suggestion="Archive the submitted version (Zenodo, Software Heritage) and give its DOI; several "
                                      "journals want it in the abstract or the availability statement."))
    if re.search(r"leave[- ]one[- ]out", text_lower):
        out.append(Finding(check="validation", severity=Severity.info,
                           message="Leave-one-out validation is mentioned.",
                           suggestion="Some journals reject ML papers validated by leave-one-out alone; report an "
                                      "independent test set."))
    limits = load_venue_limits().get(venue or "")
    if limits:
        abstract_max, body_max = limits.get("abstract_words"), limits.get("body_words")
        returned_at = limits.get("over_limit_return")
        if body_max is None:
            out.append(Finding(check="venue", severity=Severity.info,
                               message=f"No body length limit recorded for {venue}; body length was not checked.",
                               suggestion="Check the journal template or page limit."))
        if abstract_max is not None and abstract_words is not None and abstract_words > abstract_max:
            out.append(Finding(check="venue", severity=Severity.major,
                               message=f"Abstract is {abstract_words} words; {venue} recommends at most "
                                       f"{abstract_max}.", suggestion="Cut to the limit."))
        if body_max is None:
            pass
        elif returned_at and body_words > returned_at * body_max:
            out.append(Finding(check="venue", severity=Severity.blocker,
                               message=f"Body is ~{body_words} words, over {venue}'s ~{body_max} by more than "
                                       f"{round(100 * (returned_at - 1))}% (returned without review).",
                               suggestion="Move material to the supplement."))
        elif body_words > body_max:
            out.append(Finding(check="venue", severity=Severity.major,
                               message=f"Body is ~{body_words} words, over {venue}'s ~{body_max}.",
                               suggestion="Trim, or check the page count in the journal template."))
    elif venue:
        out.append(Finding(check="venue", severity=Severity.info,
                           message=f"No length limits recorded for {venue}; length was not checked.",
                           suggestion="Read the venue's author guidelines and add the limits to venues.yaml."))
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
    for attempt in range(3):
        r = client.get(url, params=params or None)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(2 ** attempt)
            continue
        return r
    return None


def _resolve_doi(client: httpx.Client, ref: Reference) -> None:
    r = _get(client, f"https://api.crossref.org/works/{ref.doi}")
    if r is not None and r.status_code == 200:
        msg = r.json()["message"]
        ref.resolved_title = (msg.get("title") or [""])[0]
        parts = (msg.get("issued") or {}).get("date-parts") or [[None]]
        ref.resolved_year = str(parts[0][0]) if parts[0][0] else None
        authors = msg.get("author") or []
        ref.resolved_first_author = (authors[0].get("family") or authors[0].get("name")) if authors else None
        updates = [u.get("type", "") for u in msg.get("updated-by", []) or []]
        # Crossref carries Retraction Watch's records in `updated-by` (source "retraction-watch").
        ref.status = ("retracted" if any("retraction" in u for u in updates)
                      else "concern" if any("concern" in u for u in updates) else "resolved")
        return
    # Not every DOI is Crossref's (DataCite: Zenodo, figshare, arXiv). Ask doi.org whether it exists.
    head = client.head(f"https://doi.org/{ref.doi}", follow_redirects=False)
    ref.status = "resolved" if head.status_code in (301, 302, 303, 307, 308) else "unresolved"


def _resolve_pmid(client: httpx.Client, ref: Reference) -> None:
    r = _get(client, "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", db="pubmed", id=ref.pmid or "",
             retmode="json")
    doc = (r.json().get("result", {}).get(ref.pmid or "", {}) if r is not None and r.status_code == 200 else {})
    if not doc or "error" in doc:
        ref.status = "unresolved"
        return
    ref.resolved_title = doc.get("title", "")
    ref.resolved_year = (doc.get("pubdate") or "")[:4] or None
    authors = doc.get("authors") or []
    ref.resolved_first_author = authors[0]["name"] if authors else None  # "Lambert SA"
    ref.status = "retracted" if "Retracted Publication" in (doc.get("pubtype") or []) else "resolved"


def _resolve_arxiv(client: httpx.Client, ref: Reference) -> None:
    r = _get(client, "https://export.arxiv.org/api/query", id_list=ref.arxiv or "")
    m = re.search(r"<entry>.*?<title>(.*?)</title>", r.text, re.DOTALL) if r is not None else None
    if not m or "Error" in m.group(1):
        ref.status = "unresolved"
        return
    ref.resolved_title = " ".join(m.group(1).split())
    year = re.search(r"<entry>.*?<published>(\d{4})", r.text, re.DOTALL)
    ref.resolved_year = year.group(1) if year else None
    author = re.search(r"<entry>.*?<author>\s*<name>(.*?)</name>", r.text, re.DOTALL)
    ref.resolved_first_author = author.group(1).strip() if author else None  # name order varies
    ref.status = "resolved"


def _search_crossref(client: httpx.Client, ref: Reference) -> None:
    """No identifier: ask Crossref for the best bibliographic match and report how well it fits."""
    r = _get(client, "https://api.crossref.org/works", **{"query.bibliographic": ref.text[:300], "rows": "1"})
    items = r.json()["message"]["items"] if r is not None and r.status_code == 200 else []
    if items:
        ref.resolved_title = (items[0].get("title") or [""])[0]
        ref.doi = items[0].get("DOI")
        authors = items[0].get("author") or []
        ref.resolved_first_author = (authors[0].get("family") or authors[0].get("name")) if authors else None
    ref.status = "no_identifier"


def resolve_references(refs: list[Reference], search_unidentified: bool) -> None:
    with httpx.Client(timeout=20, headers={"User-Agent": USER_AGENT}) as client:
        for ref in refs:
            if ref.doi:
                _resolve_doi(client, ref)
            elif ref.pmid:
                _resolve_pmid(client, ref)
            elif ref.arxiv:
                _resolve_arxiv(client, ref)
            elif search_unidentified:
                _search_crossref(client, ref)
            if ref.resolved_title:
                ref.title_similarity = round(_similarity(ref.resolved_title, ref.text), 2)
                if ref.resolved_first_author:
                    # Any part of the name longer than an initial: sources disagree on name order.
                    want = [t for t in _name_tokens(ref.resolved_first_author) if len(t) > 2]
                    ref.first_author_found = bool(want) and any(t in set(_name_tokens(ref.text)) for t in want)
                # A title that does not match is a different work; a first author that does not match, with
                # the title right, is usually a wrong author list (RefChecker flags both).
                if ref.status == "resolved" and (ref.title_similarity < 0.6 or ref.first_author_found is False):
                    ref.status = "mismatch"
            time.sleep(0.35)  # NCBI allows 3 req/s without a key; Crossref asks for politeness


def _reference_findings(refs: list[Reference]) -> list[Finding]:
    out: list[Finding] = []
    for ref in refs:
        short = ref.text[:140]
        if ref.status == "unresolved":
            out.append(Finding(check="references", severity=Severity.blocker, line=ref.line, excerpt=short,
                               message=f"Identifier does not resolve ({ref.doi or ref.pmid or ref.arxiv}).",
                               suggestion="Find the real record or remove the citation. One fabricated reference "
                                          "is a desk reject at several venues."))
        elif ref.status == "retracted":
            out.append(Finding(check="references", severity=Severity.blocker, line=ref.line, excerpt=short,
                               message="Cited work is marked as retracted.",
                               suggestion="Drop it, or cite it explicitly as retracted if the retraction is the point."))
        elif ref.status == "concern":
            out.append(Finding(check="references", severity=Severity.major, line=ref.line, excerpt=short,
                               message="Cited work carries an expression of concern.",
                               suggestion="Say so where it is cited, or support the claim with other work."))
        elif ref.status == "mismatch":
            out.append(Finding(check="references", severity=Severity.major, line=ref.line, excerpt=short,
                               message=f"Identifier resolves to '{ref.resolved_title}' by "
                                       f"{ref.resolved_first_author or '?'} (title similarity {ref.title_similarity}, "
                                       f"first author in citation: {ref.first_author_found}).",
                               suggestion="Correct the identifier or the citation text; check authors and year too."))
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
                hint += (" No matching record: possibly fabricated. Search PubMed by title and by journal, volume "
                         "and pages before keeping it.")
            out.append(Finding(check="references", severity=sev, line=ref.line, excerpt=short,
                               message="Reference carries no DOI, PMID or arXiv id." + hint + hint_author,
                               suggestion="Add the DOI (or PMID/arXiv id) after confirming title, authors, year."))
        elif ref.status == "not_checked" and not (ref.doi or ref.pmid or ref.arxiv):
            out.append(Finding(check="references", severity=Severity.minor, line=ref.line, excerpt=short,
                               message="Reference carries no DOI, PMID or arXiv id.",
                               suggestion="Run with --online to search Crossref, then add the identifier."))
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
    findings += _ai_use_findings(lines, text_lower, ref_start, bool(LEDGER_AI.search(raw)))
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

    refs: list[Reference] = []
    bibs = _bib_files(raw, path.parent) if path.suffix == ".tex" else []
    if bibs:
        keyed = [kr for bib in bibs for kr in _bib_references(bib)]
        refs = [r for _, r in keyed]
        findings += _cite_key_findings(_lines(raw), {k for k, _ in keyed})
        ref_start = ref_start or len(lines)  # the bibliography is a separate file, not a missing section
    for line_no, entry in _split_entries(_reference_entries(lines, ref_start)):
        doi = DOI_RE.search(entry)
        pmid = PMID_RE.search(entry)
        arxiv = ARXIV_RE.search(entry)
        refs.append(Reference(line=line_no, text=entry, doi=doi.group(1).rstrip(".") if doi else None,
                              pmid=pmid.group(1) if pmid else None,
                              arxiv=(arxiv.group(1) or arxiv.group(2)) if arxiv else None))
    findings += _citation_consistency(body_lines, refs)
    if git:
        findings += _git_findings(path.resolve())
    ledger_ai = LEDGER_AI.findall(raw)
    if ledger_ai:
        findings.append(Finding(check="ai-use", severity=Severity.info,
                                message=f"{len(ledger_ai)} revision-ledger segments name an AI as reviser "
                                        f"({', '.join(sorted(set(n.lower() for n in ledger_ai)))}).",
                                suggestion="Markers do not establish the kind of help. Use existing author "
                                           "context and the selected venue's rule and exemptions to determine "
                                           "whether a disclosure needs updating."))
    if ref_start is None:
        findings.append(Finding(check="references", severity=Severity.major,
                                message="No references/bibliography heading found; references were not checked.",
                                suggestion="Name the section 'References' or pass the bibliography separately."))
    if online:
        resolve_references(refs, search_unidentified)
    findings += _reference_findings(refs)

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
    search_unidentified: Annotated[bool, typer.Option(help="With --online, search Crossref for references that "
                                                           "carry no identifier")] = True,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the full report as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the Markdown report here (default: stdout)")] = None,
    venue: Annotated[Optional[str], typer.Option(help="Venue key from references/venues.yaml")] = None,
    git: Annotated[bool, typer.Option(help="Only when the authors ask: count commits touching the file that carry an AI "
                                            "co-author trailer (informational; trailers often mark automation)")] = False,
) -> None:
    known = yaml.safe_load(VENUES_YAML.read_text(encoding="utf-8"))["venues"]
    if venue and venue not in known:
        raise typer.BadParameter(f"unknown venue {venue!r}; known: {', '.join(sorted(known))}")
    report = scan(path, online, search_unidentified, venue, git)
    if json_out:
        json_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md = to_markdown(report)
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {md_out}")
    else:
        typer.echo(md)
    raise typer.Exit(code=1 if any(f.severity == Severity.blocker for f in report.findings) else 0)


if __name__ == "__main__":
    app()
