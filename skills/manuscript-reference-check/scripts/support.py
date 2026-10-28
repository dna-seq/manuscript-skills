# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "httpx>=0.27", "pydantic>=2.6", "pyyaml>=6"]
# ///
"""Mechanical checks behind claim support: is the quoted passage in the cited source, does it carry the
claim's numbers, and does it point the same way as the claim?

It never decides that a source supports a claim, and it never reports `confirmed`. For each claim it reports
one status, the most serious that applies:

    source_unavailable  no text to check: no file, offline, paywalled, or an abstract that lacks the quote
    quote_not_found     the quote is not in the source text after normalisation (or no quote was given)
    polarity_mismatch   the quote was found, but one side says increase/association and the other
                        decrease/no difference, or a negation appears on one side only
    numbers_missing     the quote was found, but a number in the claim does not occur in it
    quote_located       the quote occurs verbatim in the source text, with no flag above

Normalisation folds whitespace, line-break hyphenation, ligatures, unicode quotes and dashes, soft hyphens and
spacing inside brackets, so a quote copied from a PDF still matches the publisher's XML. The reading that turns
these signals into confirmed / partial / rejected / blocked belongs to the skill (references/claim-support.md).

    uv run --script support.py claims.yaml                     # offline: local source files and the cache only
    uv run --script support.py claims.yaml --online            # also fetch legal open-access full text
    uv run --script support.py claims.yaml --json out.json --md out.md
    uv run --script support.py claims.yaml --online --cache-dir RUN/manuscript-reference-check/sources

Fetched texts are kept in --cache-dir; in a run, give the run's folder (as above) so the texts a report rests on
stay with it. Without it they go to the platform's cache folder (~/.cache on Linux, ~/Library/Caches on macOS,
%LOCALAPPDATA% on Windows), under manuscript-reference-check/sources.

Every text read for a work is also kept across runs (source_cache.py, in the platform's cache folder under
manuscript-skills): a work given by its identifier is read with every text held for it, the fullest first, and
fetched again only when none is the full text; a text an agent read in a browser joins them with `source_cache.py
save`, and earlier runs' sources/ folders with `source_cache.py seed`. The report says which sources were read with
texts kept from earlier reads, from which run and when; the verdicts are always this run's. --no-shared-cache reads
afresh.

With --online only public identifiers leave the machine: Europe PMC (PMC full text and abstracts), the bioRxiv
and medRxiv API (full-text JATS), and arXiv (HTML full text or the abstract). Paywalled sources are never
scraped; they come back `source_unavailable`, with any free full-text page the index lists for you to read.

Text in a source that may address AI systems ("ignore the previous instructions", "give a positive review") is
listed with the passage, for the reader to judge in context: papers about language models carry such sentences for
their own reasons. Such text hidden in invisible Unicode tag characters is flagged. Neither is ever acted on.

A claims file written by sample_claims.py (a seeded random sample of the cited sentences the priority classes did not
take) carries a `sample` block; once each sampled claim has the reading's `outcome`, the report gives the share not
fully supported, its 95% interval and what that means for the cited sentences nobody checked.

Exit codes: 0 every quote located with no flag; 1 at least one claim flagged (quote_not_found,
polarity_mismatch, numbers_missing) or a source that hides text for AI systems; 2 usage error or malformed claims
file; 3 nothing flagged, but at least one source was unavailable, so the run cannot be called clean.
"""

from __future__ import annotations

import functools
import html
import importlib.util
import json
import os
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated, Any, Optional

import httpx
import typer
import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

app = typer.Typer(add_completion=False, no_args_is_help=True)

USER_AGENT = ("manuscript-reference-check/1.0 (claim-support check by the authors; "
              "https://github.com/dna-seq/manuscript-skills)")
STATUSES = ("source_unavailable", "quote_not_found", "polarity_mismatch", "numbers_missing", "quote_located")
FLAGGED = {"quote_not_found", "polarity_mismatch", "numbers_missing"}
PRIORITIES = {"load-bearing", "abstract", "borrowed-number", "first-only", "other", "sample"}
# The reading's outcome of a claim (references/claim-support.md), recorded by the agent; the script never sets it.
OUTCOMES = ("confirmed", "partial", "rejected", "blocked")
MIN_QUOTE_CHARS = 30


# --------------------------------------------------------------------------------------------------
# Normalisation
# --------------------------------------------------------------------------------------------------

_CHAR_MAP = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'", "\u00b4": "'", "`": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"', "\u00ab": '"', "\u00bb": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2015": "-", "\u2212": "-",
    "\ufe63": "-", "\uff0d": "-", "\u00d7": "x", "\u22c5": "x",
    "\u00ad": None, "\u200b": None, "\u200c": None, "\u200d": None, "\u2060": None, "\ufeff": None,
})


def normalise(text: str) -> str:
    """Fold the differences that copying from a PDF, HTML or XML introduces, never the wording.

    Ligatures, full-width forms and superscript digits (NFKC); typographic quotes, dashes and the minus sign;
    soft hyphens and zero-width characters; hyphenation across a line break and hyphens between letters (on both
    sides alike, so "long- term", "long-term" and "longterm" meet); the Lancet decimal point; spaces inside
    brackets and before punctuation; case and runs of whitespace.
    """
    text = unicodedata.normalize("NFKC", text).casefold().translate(_CHAR_MAP)
    text = re.sub(r"(\d)\u00b7(\d)", r"\1.\2", text)
    text = re.sub(r"([^\W\d_])-\s+([^\W\d_])", r"\1\2", text)  # hyphenation at a line break
    text = re.sub(r"([^\W\d_])-([^\W\d_])", r"\1\2", text)
    text = re.sub(r"(\d)\s*-\s*(\d)", r"\1-\2", text)
    text = re.sub(r"(\d)\s*x\s*(\d)", r"\1x\2", text)
    text = re.sub(r"10\s*\^\s*\{?\s*(-?)\s*(\d+)\s*\}?", r"10\1\2", text)  # LaTeX 10^{-6}
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    text = re.sub(r"\s+([)\],.;:!?%])", r"\1", text)
    return text.strip()


# --------------------------------------------------------------------------------------------------
# Text from XML and HTML sources
# --------------------------------------------------------------------------------------------------

_JATS_SKIP = {"ref-list", "permissions", "license", "funding-group", "object-id", "contrib-group", "aff",
              "author-notes", "history", "pub-date", "article-id", "journal-meta", "custom-meta-group", "kwd-group"}
_JATS_BLOCK = {"p", "title", "article-title", "caption", "tr", "list-item", "abstract", "sec", "table-wrap", "fig",
               "label", "disp-quote", "def-item", "boxed-text"}
_JATS_META_TEXT = {"title-group", "abstract", "trans-abstract"}


def _local(tag: Any) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def jats_to_text(xml_text: str) -> str:
    """Article title, abstracts, body, tables and figure captions of a JATS article; references left out."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        stripped = re.sub(r"<ref-list\b.*?</ref-list>", " ", xml_text, flags=re.DOTALL)
        return html.unescape(re.sub(r"<[^>]+>", " ", stripped))
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        tag = _local(node.tag)
        if tag in _JATS_SKIP:
            if node.tail:
                parts.append(node.tail)
            return
        if node.text and tag != "article-meta":
            parts.append(node.text)
        for child in node:
            # Of the front matter only the title and the abstracts are text; volume, dates and ids are not.
            if tag == "article-meta" and _local(child.tag) not in _JATS_META_TEXT:
                continue
            walk(child)
        if tag in _JATS_BLOCK:
            parts.append("\n")
        if node.tail:
            parts.append(node.tail)

    walk(root)
    return re.sub(r"[ \t]+", " ", "".join(parts))


class _HTMLText(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg", "button", "form"}
    BLOCK = {"p", "div", "section", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "figcaption", "caption",
             "blockquote", "br", "table"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.parts.append(data)


def html_to_text(page: str) -> str:
    parser = _HTMLText()
    parser.feed(page)
    return re.sub(r"[ \t]+", " ", "".join(parser.parts))


def read_text_file(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    suffix = path.suffix.lower()
    if suffix in (".xml", ".nxml", ".jats"):
        return jats_to_text(raw)
    if suffix in (".html", ".htm", ".xhtml"):
        return html_to_text(raw)
    return raw


# --------------------------------------------------------------------------------------------------
# Locating the quote
# --------------------------------------------------------------------------------------------------

ELLIPSIS_RE = re.compile(r"\[\s*(?:\.\s*){3}\]|\[\s*…\s*\]|(?:\.\s*){3}|…")
MAX_ELLIPSIS_GAP = 1500


def locate(quote: str, source: str) -> Optional[tuple[int, int, str]]:
    """(start, end, "exact" | "ellipsis") of the normalised quote in the normalised source, or None."""
    segments = [normalise(s) for s in ELLIPSIS_RE.split(quote)]
    segments = [s.strip(" ,;:") for s in segments if s.strip(" ,;:.")]
    if not segments:
        return None
    if len(segments) == 1:
        at = source.find(segments[0])
        return (at, at + len(segments[0]), "exact") if at >= 0 else None
    for first in re.finditer(re.escape(segments[0]), source):
        start, cursor = first.start(), first.end()
        for seg in segments[1:]:
            at = source.find(seg, cursor)
            if at < 0 or at - cursor > MAX_ELLIPSIS_GAP:
                break
            cursor = at + len(seg)
        else:
            return start, cursor, "ellipsis"
    return None


def closest_passage(quote: str, source: str) -> tuple[Optional[str], Optional[float]]:
    """The source window most like the quote, to show what the source says instead."""
    q_words = quote.split()
    s_words = source.split()
    if not q_words or not s_words:
        return None, None
    width, step = len(q_words), max(1, len(q_words) // 4)
    wanted = set(q_words)
    scored: list[tuple[int, int]] = []
    for i in range(0, max(1, len(s_words) - width + 1), step):
        scored.append((len(wanted & set(s_words[i:i + width])), i))
    best_text, best_ratio = None, 0.0
    for _, i in sorted(scored, reverse=True)[:5]:
        window = " ".join(s_words[max(0, i - 3):i + width + 3])
        ratio = SequenceMatcher(None, quote, window, autojunk=False).ratio()
        if ratio > best_ratio:
            best_text, best_ratio = window, ratio
    return best_text, round(best_ratio, 2)


def sentence_context(source: str, start: int, end: int, reach: int = 300) -> str:
    """The located passage widened to the sentences around it (citations often sit at the sentence end)."""
    lo, hi = max(0, start - reach), min(len(source), end + reach)
    before = source[lo:start]
    cut = max(before.rfind(". "), before.rfind("\n"))
    left = lo + cut + 2 if cut >= 0 else lo
    after = source[end:hi]
    stop = after.find(". ")
    right = end if source[end - 1:end] in ".!?" else end + stop + 1 if stop >= 0 else hi
    return source[left:right].strip()


# A passage that reports someone else's result: the number may belong to a primary study, not this source.
SECONDARY_RE = re.compile(
    r"\bet al\b\.?|\[\d+(?:\s*[-,]\s*\d+)*\]|\([^()]*[a-z][^()]*\b(?:19|20)\d{2}[a-z]?\)|\breported by\b|"
    r"\baccording to\b|"
    r"\bas (?:shown|reported|described|found) (?:by|in)\b|\bprevious(?:ly)? (?:studies|work|reports?)\b|"
    r"\bha(?:s|ve) been (?:shown|reported|demonstrated|documented)\b|\bstudies have\b|\bwas reported\b")
# A date in parentheses ("Build 3 (24 June 2017) of LongevityMap", "(June 2017)", "(accessed 10 October 2026)")
# dates a release or a visit; it cites nothing, so it is no sign of a borrowed number.
MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
         r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?")
DATE_IN_PARENTHESES = re.compile(
    rf"\(\s*(?:(?:accessed|retrieved|updated|released|published|as of|on|in)\s+)?(?:"
    rf"(?:\d{{1,2}}(?:st|nd|rd|th)?\s+)?{MONTH},?\s+(?:\d{{1,2}}(?:st|nd|rd|th)?,?\s+)?(?:19|20)\d{{2}}|"
    rf"(?:19|20)\d{{2}}-\d{{1,2}}(?:-\d{{1,2}})?)\s*\)", re.IGNORECASE)


def secondary_markers(context: str) -> list[str]:
    """The words around a quote that cite or report other work, without dates in parentheses."""
    return list(dict.fromkeys(m.group(0) for m in SECONDARY_RE.finditer(context)
                              if not DATE_IN_PARENTHESES.fullmatch(m.group(0))))


# --------------------------------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------------------------------

SCI_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)x10(-?)(\d+)\b|(?<![\w.])(\d+(?:\.\d+)?)e(-?)(\d+)\b")
NUM_RE = re.compile(r"(?<![\w.])(?<![a-z]-)(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)(?!\d)")
CITATION_MARKERS = [
    re.compile(r"\[\s*\d+(?:\s*[-\u2013,]\s*\d+)*\s*\]"),                               # [3], [3-5], [3, 7]
    re.compile(r"\\(?:no)?cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{[^}]*\}"),                   # \citep{key}
    re.compile(r"\[@[^\]]+\]"),                                                         # [@key]
    re.compile(r"\([^()]*\b[A-Z][a-z][\w'\-]*[^()]*?\b(?:19|20)\d{2}[a-z]?[^()]*\)"),   # (Duncan et al., 2019)
    re.compile(r"\b[A-Z][\w'\-]+(?: et al\.?| and [A-Z][\w'\-]+)? \((?:19|20)\d{2}[a-z]?\)"),  # Duncan et al. (2019)
    re.compile(r"\b(?:fig(?:ure)?s?|tables?|supplementary (?:fig(?:ure)?s?|tables?|data|notes?)|eqs?|equations?|"
               r"sections?|refs?|references?)\.?\s*s?\d+[a-z]?(?:\s*(?:[-\u2013,]|and|&)\s*s?\d+[a-z]?)*",
               re.IGNORECASE),                                                          # Figure 2, Table S1
]


def strip_citations(claim: str) -> str:
    """The claim without citation markers and figure or table references, whose numbers are not claims."""
    for rx in CITATION_MARKERS:
        claim = rx.sub(" ", claim)
    return claim


def numbers_in(text: str) -> list[tuple[str, Decimal]]:
    """(as written, value) for every number in normalised text; 3.7x10-6, 3.7e-6 and 0.0000037 are one value."""
    out: list[tuple[str, Decimal]] = []
    masked = list(text)
    for m in SCI_RE.finditer(text):
        mantissa, sign, exponent = (m.group(1), m.group(2), m.group(3)) if m.group(1) else (m.group(4), m.group(5),
                                                                                              m.group(6))
        try:
            out.append((m.group(0), Decimal(f"{mantissa}e{sign}{exponent}")))
        except InvalidOperation:
            continue
        masked[m.start():m.end()] = " " * (m.end() - m.start())
    for m in NUM_RE.finditer("".join(masked)):
        try:
            out.append((m.group(1), Decimal(m.group(1).replace(",", ""))))
        except InvalidOperation:
            continue
    return out


def _year_like(raw: str, value: Decimal) -> bool:
    return raw.isdigit() and len(raw) == 4 and 1800 <= value <= 2100


class NumberCheck(BaseModel):
    in_claim: list[str] = []
    found: list[str] = []
    missing: list[str] = []
    year_like_missing: list[str] = []  # reported, never flagged: "in 2019" rarely needs to be in the quote


def check_numbers(claim: str, quote: str) -> NumberCheck:
    quote_values = {value for _, value in numbers_in(normalise(quote))}
    result = NumberCheck()
    for raw, value in numbers_in(normalise(strip_citations(claim))):
        result.in_claim.append(raw)
        if value in quote_values:
            result.found.append(raw)
        elif _year_like(raw, value):
            result.year_like_missing.append(raw)
        else:
            result.missing.append(raw)
    return result


# --------------------------------------------------------------------------------------------------
# Polarity
# --------------------------------------------------------------------------------------------------

UP_RE = re.compile(r"\b(?:increas\w*|higher|greater|more|elevat\w*|rais(?:e|ed|es|ing)|ris(?:e|es|ing)|rose|"
                   r"enhanc\w*|improv\w*|upregulat\w*|gain(?:s|ed)?|exceed\w*|larger|stronger|better|"
                   r"outperform\w*)\b")
DOWN_RE = re.compile(r"\b(?:decreas\w*|lower(?:ed|s|ing)?|reduc\w*|less|fewer|smaller|declin\w*|diminish\w*|"
                     r"downregulat\w*|impair\w*|loss|lose|lost|drop(?:s|ped)?|fell|fall(?:s|ing)?|weaker|worse|"
                     r"worst|poorer|attenuat\w*|underperform\w*)\b")
NULL_RE = re.compile(r"\b(?:similar(?:ly)?|comparabl[ey]|unchanged|equivalent|indistinguishable|"
                     r"no (?:significant |statistically significant |clear )?(?:difference|change|effect|association|"
                     r"correlation|relationship|link|evidence)|did not (?:differ|change|affect)|not (?:differ\w*|"
                     r"associated|correlated|significant\w*|related|linked)|independent of|unrelated|"
                     r"nonsignificant\w*|insignificant)\b")
ASSOC_RE = re.compile(r"\b(?:associat\w*|correlat\w*|linked|predict(?:s|ed|or|ors)?|risk factor)\b")
NEGATION_RE = re.compile(r"\b(?:not|no|never|none|neither|nor|without|cannot|fail(?:s|ed)? to|lack(?:s|ed|ing)?)\b|"
                         r"n't\b")


def _negated(text: str, start: int) -> bool:
    window = " ".join(text[:start].split()[-3:])
    return bool(NEGATION_RE.search(window))


def polarity_terms(text: str) -> set[str]:
    """Labels for the direction a normalised text states: up, down, null, assoc, and not_up/not_down/not_assoc."""
    labels: set[str] = set()
    null_spans = [m.span() for m in NULL_RE.finditer(text)]
    if null_spans:
        labels.add("null")

    def inside_null(pos: int) -> bool:
        return any(lo <= pos < hi for lo, hi in null_spans)

    for label, rx in (("up", UP_RE), ("down", DOWN_RE), ("assoc", ASSOC_RE)):
        for m in rx.finditer(text):
            if inside_null(m.start()):
                continue
            labels.add(f"not_{label}" if _negated(text, m.start()) else label)
    return labels


def polarity_mismatch(claim: str, quote: str) -> list[str]:
    """Reasons the claim and the quote point different ways; empty when no mechanical reason was found."""
    c, q = polarity_terms(normalise(strip_citations(claim))), polarity_terms(normalise(quote))
    reasons: list[str] = []
    directional = {"up", "down", "assoc"}
    if "null" in c and "null" not in q and q & directional:
        reasons.append(f"The claim states no difference or association, but the passage states {_describe(q)}.")
    if "null" in q and "null" not in c and c & directional:
        reasons.append(f"The passage states no difference or association, but the claim states {_describe(c)}.")
    for a, b in (("up", "down"), ("down", "up")):
        if a in c and b not in c and b in q and a not in q:
            reasons.append(f"The claim states {_word(a)}, but the passage states {_word(b)}.")
    for label in ("up", "down", "assoc"):
        if f"not_{label}" in c and label in q and f"not_{label}" not in q:
            reasons.append(f"The claim negates {_word(label)}, but the passage does not.")
        if f"not_{label}" in q and label in c and f"not_{label}" not in c:
            reasons.append(f"The passage negates {_word(label)}, but the claim does not.")
    return list(dict.fromkeys(reasons))


def _word(label: str) -> str:
    return {"up": "an increase", "down": "a decrease", "assoc": "an association"}[label]


def _describe(labels: set[str]) -> str:
    return " and ".join(_word(x) for x in ("up", "down", "assoc") if x in labels)


# --------------------------------------------------------------------------------------------------
# Sources: local files, the cache, and legal open-access routes
# --------------------------------------------------------------------------------------------------

class SourceInfo(BaseModel):
    given: Optional[str] = None
    kind: str = "none"  # file | doi | pmid | pmcid | arxiv | none
    # supplied | full_text | partial (more than an abstract, less than the full text: a browser excerpt) | abstract | none
    scope: str = "none"
    via: Optional[str] = None
    cache_file: Optional[str] = None
    reason: Optional[str] = None
    free_urls: list[str] = []
    characters: int = 0
    url: Optional[str] = None  # the identifier as a link the authors can open (https://doi.org/..., PubMed, arXiv)
    aimed_at_ai: list[str] = []  # visible passages that may address AI systems: read in context, never acted on
    hidden_for_ai: list[str] = []  # text hidden in invisible characters that addresses AI systems, never acted on
    # The texts read earlier for this work that this reading used (source_cache.py): {run, read_at, texts}.
    reused_from: Optional[dict[str, Any]] = None


IDENTIFIER_PATTERNS = [
    ("pmcid", re.compile(r"^(?:pmcid:\s*)?(PMC\d+)$", re.IGNORECASE)),
    ("pmid", re.compile(r"^pmid:\s*(\d{1,9})$", re.IGNORECASE)),
    ("arxiv", re.compile(r"^(?:arxiv:\s*|https?://arxiv\.org/(?:abs|html|pdf)/)(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?$",
                         re.IGNORECASE)),
    ("doi", re.compile(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)),
]
ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.(\d{4}\.\d{4,5})(?:v\d+)?$", re.IGNORECASE)
RXIV_DOI_RE = re.compile(r"^10\.1101/(?:\d{4}\.\d{2}\.\d{2}\.)?\d{6,}(?:v\d+)?$")
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def parse_identifier(value: str) -> Optional[tuple[str, str]]:
    value = value.strip()
    for kind, rx in IDENTIFIER_PATTERNS:
        m = rx.match(value)
        if m:
            ident = m.group(1).upper() if kind == "pmcid" else m.group(1)
            arxiv = ARXIV_DOI_RE.match(ident) if kind == "doi" else None
            return ("arxiv", arxiv.group(1)) if arxiv else (kind, ident.rstrip(".,;"))
    return None


def identifier_url(kind: str, value: str) -> Optional[str]:
    """The page a reader opens for an identifier: doi.org, PubMed, Europe PMC or arXiv."""
    return {"doi": f"https://doi.org/{value}", "pmid": f"https://pubmed.ncbi.nlm.nih.gov/{value}/",
            "pmcid": f"https://europepmc.org/article/PMC/{value}", "arxiv": f"https://arxiv.org/abs/{value}"}.get(kind)


def platform_cache_root() -> Path:
    """The user's cache folder on this platform: %LOCALAPPDATA% on Windows, ~/Library/Caches on macOS, else
    $XDG_CACHE_HOME or ~/.cache."""
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        return Path(local) if local else Path.home() / "AppData" / "Local"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches"
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def default_cache_dir() -> Path:
    """Where fetched texts go without --cache-dir. A run passes its own folder, so the texts stay with its report."""
    return platform_cache_root() / "manuscript-reference-check" / "sources"


def _cache_paths(cache_dir: Path, kind: str, value: str) -> tuple[Path, Path]:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{kind}_{value}").strip("_")
    return cache_dir / f"{stem}.txt", cache_dir / f"{stem}.json"


class Fetcher:
    """Polite GETs: one client, a pause per host (3 s for arXiv, as its terms ask), retries on 429 and 5xx."""

    PAUSE = {"arxiv.org": 3.1, "export.arxiv.org": 3.1}

    def __init__(self) -> None:
        self.client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        self.last: dict[str, float] = {}

    def get(self, url: str, **params: str) -> Optional[httpx.Response]:
        host = httpx.URL(url).host
        for attempt in range(3):
            wait = self.PAUSE.get(host, 1.0) - (time.monotonic() - self.last.get(host, -1e9))
            if wait > 0:
                time.sleep(wait)
            self.last[host] = time.monotonic()
            try:
                r = self.client.get(url, params=params or None)
            except httpx.HTTPError:
                return None
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            return r
        return None

    def close(self) -> None:
        self.client.close()


def _json(r: Optional[httpx.Response]) -> Optional[dict]:
    if r is None or r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _europepmc_fulltext(fetch: Fetcher, pmcid: str) -> Optional[str]:
    r = fetch.get(f"{EUROPEPMC}/{pmcid}/fullTextXML")
    if r is None or r.status_code != 200 or "<" not in r.text[:200]:
        return None
    text = jats_to_text(r.text)
    return text if len(text.split()) > 200 else None


def _europepmc(fetch: Fetcher, kind: str, value: str) -> tuple[Optional[str], SourceInfo]:
    info = SourceInfo(given=f"{kind}:{value}", kind=kind)
    if kind == "pmcid":
        text = _europepmc_fulltext(fetch, value)
        if text:
            info.scope, info.via = "full_text", "europepmc:fullTextXML"
            return text, info
        info.reason = "Europe PMC serves no full text for this article through its API."
        info.free_urls = [f"https://europepmc.org/article/PMC/{value}"]
        return None, info
    query = f'DOI:"{value}"' if kind == "doi" else f"EXT_ID:{value} AND SRC:MED"
    data = _json(fetch.get(f"{EUROPEPMC}/search", query=query, format="json", resultType="core", pageSize="1"))
    if data is None:
        info.reason = "Europe PMC did not answer, so no open-access text was found."
        return None, info
    hits = [h for h in data.get("resultList", {}).get("result", [])
            if (kind == "doi" and (h.get("doi") or "").lower() == value.lower())
            or (kind == "pmid" and str(h.get("pmid") or "") == value)]
    if not hits:
        info.reason = "Europe PMC does not index this work, so no legal open-access copy was found."
        return None, info
    hit = hits[0]
    info.free_urls = [u.get("url") for u in (hit.get("fullTextUrlList") or {}).get("fullTextUrl", [])
                      if u.get("availabilityCode") in ("F", "OA") and u.get("url")]
    if hit.get("pmcid"):
        text = _europepmc_fulltext(fetch, hit["pmcid"])
        if text:
            info.scope, info.via, info.free_urls = "full_text", "europepmc:fullTextXML", []
            return text, info
    abstract = html.unescape(re.sub(r"<[^>]+>", " ", hit.get("abstractText") or "")).strip()
    title = hit.get("title") or ""
    if abstract:
        info.scope, info.via = "abstract", "europepmc:abstract"
        info.reason = "Only the abstract is openly available; the full text is paywalled or not deposited."
        return f"{title}\n{abstract}", info
    info.reason = ("Europe PMC lists a free full text (often an author manuscript) that its API does not serve; "
                   "read it at the link below." if info.free_urls else
                   "There is no open-access full text and no abstract; the work is paywalled or not deposited.")
    return None, info


def _rxiv(fetch: Fetcher, doi: str) -> tuple[Optional[str], SourceInfo]:
    info = SourceInfo(given=f"doi:{doi}", kind="doi")
    for server in ("biorxiv", "medrxiv"):
        data = _json(fetch.get(f"https://api.biorxiv.org/details/{server}/{doi}"))
        versions = (data or {}).get("collection") or []
        if not versions:
            continue
        latest = versions[-1]
        if latest.get("jatsxml"):
            r = fetch.get(latest["jatsxml"])
            if r is not None and r.status_code == 200 and "<" in r.text[:200]:
                text = jats_to_text(r.text)
                if len(text.split()) > 200:
                    info.scope, info.via = "full_text", f"{server}:jatsxml (version {latest.get('version')})"
                    return text, info
        if latest.get("abstract"):
            info.scope, info.via = "abstract", f"{server}:abstract"
            info.reason = "The full-text XML could not be fetched, so only the abstract was read."
            return f"{latest.get('title', '')}\n{latest['abstract']}", info
    return None, info


def _arxiv(fetch: Fetcher, arxiv_id: str) -> tuple[Optional[str], SourceInfo]:
    info = SourceInfo(given=f"arxiv:{arxiv_id}", kind="arxiv")
    r = fetch.get(f"https://arxiv.org/html/{arxiv_id}")
    if r is not None and r.status_code == 200 and "html" in r.headers.get("content-type", ""):
        text = html_to_text(r.text)
        if len(text.split()) > 300:
            info.scope, info.via = "full_text", "arxiv:html"
            return text, info
    r = fetch.get("https://export.arxiv.org/api/query", id_list=arxiv_id)
    if r is not None and r.status_code == 200:
        m = re.search(r"<entry>.*?<title>(.*?)</title>.*?<summary>(.*?)</summary>", r.text, re.DOTALL)
        if m:
            info.scope, info.via = "abstract", "arxiv:abstract"
            info.reason = "arXiv has no HTML full text for this paper, so only the abstract was read."
            info.free_urls = [f"https://arxiv.org/pdf/{arxiv_id}"]
            return html.unescape(f"{m.group(1)}\n{m.group(2)}"), info
    info.reason = "arXiv did not answer, so no text was read."
    return None, info


SOURCE_CACHE = Path(__file__).resolve().parent / "source_cache.py"


@functools.cache
def _source_cache() -> Any:
    """source_cache.py beside this script: every text read for a work, kept across runs."""
    spec = importlib.util.spec_from_file_location("support_source_cache", SOURCE_CACHE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["support_source_cache"] = module
    spec.loader.exec_module(module)
    return module


def _scope_of(held: list[dict[str, Any]]) -> str:
    """What the texts read earlier for a work amount to: the full text, more than an abstract, or the abstract."""
    scopes = {item.get("scope") for item in held}
    return "full_text" if scopes & {"full_text"} else "partial" if scopes - {"abstract"} else "abstract"


def _reuse(held: list[dict[str, Any]]) -> dict[str, Any]:
    oldest = min(held, key=lambda item: item.get("read_at") or "")
    return {"texts": len(held), "runs": sorted({item["run"] for item in held if item.get("run")}),
            "oldest": (oldest.get("read_at") or "")[:10], "scopes": sorted({item.get("scope", "") for item in held})}


def fetch_identifier(kind: str, value: str, fetch: Optional[Fetcher], cache_dir: Path,
                     shared: bool = True) -> tuple[Optional[str], SourceInfo]:
    """The text of a work given by its identifier: this run's copy; else every text read for it earlier
    (source_cache.py), used as it is when one is the full text or nothing may be fetched; else fetched, kept for later
    runs, and joined with any partial texts read earlier. The run keeps its own copy of whatever it read."""
    text_path, meta_path = _cache_paths(cache_dir, kind, value)
    if text_path.exists() and meta_path.exists():
        info = SourceInfo.model_validate_json(meta_path.read_text(encoding="utf-8"))
        info.cache_file = str(text_path)
        return text_path.read_text(encoding="utf-8"), info
    store = _source_cache() if shared else None
    keys = [store.work_key(kind, value)] if store else []
    held = store.lookup(keys) if store else []
    if held and (fetch is None or _scope_of(held) == "full_text"):
        info = SourceInfo(given=f"{kind}:{value}", kind=kind, scope=_scope_of(held), via=f"earlier read: {held[0]['via']}",
                          url=held[0].get("url"), reused_from=_reuse(held))
        return _keep(store.combined(held), info, text_path, meta_path)
    if fetch is None:
        return None, SourceInfo(given=f"{kind}:{value}", kind=kind,
                                reason="The source is given as an identifier, and reading it needs the online "
                                       "lookups (or save the source's text and give its path).")
    text, info = _fetched(kind, value, fetch)
    if text is not None and store:
        store.store(keys, text, info.scope, info.via or "fetched", info.url or identifier_url(kind, value),
                    store.run_id(cache_dir))
    if held:  # a partial text read earlier (a browser excerpt) joins what was fetched, or stands in for it
        earlier = [item for item in held if text is None or store.read(item) != text]
        if earlier:
            info.reused_from = _reuse(earlier)
            if text is None:
                info = SourceInfo(given=f"{kind}:{value}", kind=kind, scope=_scope_of(earlier),
                                  via=f"earlier read: {earlier[0]['via']}", url=earlier[0].get("url"),
                                  reused_from=_reuse(earlier), free_urls=info.free_urls)
                text = store.combined(earlier)
            else:
                text = text + "\n\n----- Texts read earlier for this work -----\n\n" + store.combined(earlier)
                info.scope = "full_text" if info.scope == "full_text" else _scope_of(earlier + [{"scope": info.scope}])
    if text is not None:
        return _keep(text, info, text_path, meta_path)
    return text, info


def _keep(text: str, info: SourceInfo, text_path: Path, meta_path: Path) -> tuple[str, SourceInfo]:
    """This run's copy of a text it read, with its record."""
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")
    meta_path.write_text(info.model_dump_json(indent=2), encoding="utf-8")
    info.cache_file = str(text_path)
    return text, info


def _fetched(kind: str, value: str, fetch: Fetcher) -> tuple[Optional[str], SourceInfo]:
    if kind == "arxiv":
        text, info = _arxiv(fetch, value)
    elif kind == "doi" and RXIV_DOI_RE.match(value):
        text, info = _rxiv(fetch, value)
        if text is None:
            text, info = _europepmc(fetch, kind, value)
    else:
        text, info = _europepmc(fetch, kind, value)
    return text, info


def load_source(given: Optional[str], base: Path, fetch: Optional[Fetcher],
                cache_dir: Path, shared: bool = True) -> tuple[Optional[str], SourceInfo]:
    if not given:
        return None, SourceInfo(reason="No source was given for this claim.")
    path = Path(given).expanduser()
    path = path if path.is_absolute() else base / path
    if path.is_file():
        if path.suffix.lower() == ".pdf":
            return None, SourceInfo(given=given, kind="file",
                                    reason="The source is a PDF; convert it to text first (pdftotext -layout "
                                           "FILE.pdf) and give the .txt file.")
        text = read_text_file(path)
        return text, SourceInfo(given=given, kind="file", scope="supplied", via="file")
    ident = parse_identifier(given)
    if ident is None:
        return None, SourceInfo(given=given, kind="file", reason=f"The source file {path} was not found.")
    text, info = fetch_identifier(ident[0], ident[1], fetch, cache_dir, shared)
    info.url = info.url or identifier_url(*ident)
    return text, info


HYGIENE = Path(__file__).resolve().parents[2] / "manuscript-integrity-check" / "scripts" / "hygiene.py"


@functools.cache
def _hygiene() -> Any:
    """manuscript-integrity-check's hygiene.py: its pattern for text addressed to an AI reviewer is reused here."""
    spec = importlib.util.spec_from_file_location("_refcheck_hygiene", HYGIENE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["_refcheck_hygiene"] = module  # pydantic resolves deferred annotations through sys.modules
    spec.loader.exec_module(module)
    return module


def aimed_at_ai(text: str) -> tuple[list[str], list[str]]:
    """Passages of a source that may address AI systems, each with its surroundings (at most three), and text hidden
    in Unicode tag characters that does. A visible match is a passage to read: a paper about chatbots or benchmarks
    can say "as an AI assistant" or "produce high scores" for its own reasons."""
    hygiene = _hygiene()
    hidden = "".join(chr(ord(c) - 0xE0000) for m in hygiene.TAG_CHARS.finditer(text) for c in m.group(0)
                     if 0x20 <= ord(c) - 0xE0000 < 0x7F)
    found: list[list[str]] = []
    for body in (text, hidden):
        passages: list[str] = []
        shown = -1  # where the last passage shown ends: two cues in one sentence are one passage
        for m in hygiene.INJECTION.finditer(body):
            if m.start() < shown or len(passages) == 3:
                continue
            shown = m.end() + 40
            passages.append(hygiene._snippet(body[max(0, m.start() - 40):shown], 160))
        found.append(passages)
    return found[0], found[1]


# --------------------------------------------------------------------------------------------------
# The claims file
# --------------------------------------------------------------------------------------------------

class ClaimIn(BaseModel):
    id: str = Field(min_length=1)
    location: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    quote: Optional[str] = None
    source: Optional[str] = None
    priority: Optional[str] = None
    outcome: Optional[str] = None  # confirmed | partial | rejected | blocked, after the reading

    @field_validator("id", "location", "reference", "source", mode="before")
    @classmethod
    def _scalar_to_text(cls, value: Any) -> Any:
        return str(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value

    @field_validator("claim", "quote", mode="after")
    @classmethod
    def _not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("priority")
    @classmethod
    def _known_priority(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in PRIORITIES:
            raise ValueError(f"must be one of {', '.join(sorted(PRIORITIES))}")
        return value

    @field_validator("outcome")
    @classmethod
    def _known_outcome(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in OUTCOMES:
            raise ValueError(f"must be one of {', '.join(OUTCOMES)}")
        return value


class ClaimsFileError(ValueError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


def load_claims(path: Path) -> tuple[list[ClaimIn], Path]:
    """The claims and the directory relative source paths resolve against. Raises ClaimsFileError."""
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ClaimsFileError([f"cannot read {path}: {exc}"]) from exc
    try:
        data = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ClaimsFileError([f"{path.name} is not valid {'JSON' if path.suffix.lower() == '.json' else 'YAML'}: "
                               f"{str(exc).splitlines()[0]}"]) from exc
    base = path.parent
    if isinstance(data, dict):
        if data.get("sources_dir") is not None:
            base = base / str(data["sources_dir"])
        items = data.get("claims")
    else:
        items = data
    if not isinstance(items, list) or not items:
        raise ClaimsFileError(["expected a non-empty list of claims (top level, or under 'claims:')"])
    claims: list[ClaimIn] = []
    problems: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(items):
        label = f"claims[{i}]" + (f" (id {item.get('id')})" if isinstance(item, dict) and item.get("id") else "")
        if not isinstance(item, dict):
            problems.append(f"{label}: expected a mapping of fields, got {type(item).__name__}")
            continue
        try:
            claim = ClaimIn.model_validate(item)
        except ValidationError as exc:
            for err in exc.errors():
                field = ".".join(str(p) for p in err["loc"]) or "entry"
                problems.append(f"{label}: '{field}' {err['msg'].lower()}")
            continue
        if claim.id in seen:
            problems.append(f"{label}: duplicate id '{claim.id}'")
            continue
        seen.add(claim.id)
        claims.append(claim)
    if problems:
        raise ClaimsFileError(problems)
    return claims, base


# --------------------------------------------------------------------------------------------------
# Checking a claim
# --------------------------------------------------------------------------------------------------

class ClaimResult(BaseModel):
    id: str
    location: str
    reference: str
    claim: str
    priority: Optional[str] = None
    outcome: Optional[str] = None
    status: str
    flags: list[str] = []
    quote: Optional[str] = None
    match: Optional[str] = None  # exact | ellipsis
    source: SourceInfo
    numbers: Optional[NumberCheck] = None
    polarity: list[str] = []
    secondary_markers: list[str] = []
    context: Optional[str] = None
    closest_passage: Optional[str] = None
    closest_ratio: Optional[float] = None
    notes: list[str] = []


def check_claim(claim: ClaimIn, text: Optional[str], source: SourceInfo) -> ClaimResult:
    result = ClaimResult(id=claim.id, location=claim.location, reference=claim.reference, claim=claim.claim,
                         priority=claim.priority, outcome=claim.outcome, status="quote_located", quote=claim.quote,
                         source=source)
    if text is not None:
        source.characters = len(text)
    if text is None or not text.strip():
        result.status, result.flags = "source_unavailable", ["source_unavailable"]
        return result
    norm_source = normalise(text)
    if not claim.quote:
        if source.scope in ("abstract", "partial"):
            result.status, result.flags = "source_unavailable", ["source_unavailable"]
            result.notes.append("Only the abstract was available and no quote was given; read the full text.")
        else:
            result.status, result.flags = "quote_not_found", ["quote_not_found"]
            result.notes.append("No quote was given. Locate the passage that carries the claim and add it.")
        return result
    found = locate(claim.quote, norm_source)
    if found is None:
        passage, ratio = closest_passage(normalise(claim.quote), norm_source)
        result.closest_passage, result.closest_ratio = passage, ratio
        if source.scope in ("abstract", "partial"):
            result.status, result.flags = "source_unavailable", ["source_unavailable"]
            result.notes.append("The quote is not in the abstract, the only text available; the full text may hold it."
                                if source.scope == "abstract" else
                                "The quote is not in the texts read for this work (not the full text); the full text "
                                "may hold it.")
        else:
            result.status, result.flags = "quote_not_found", ["quote_not_found"]
        return result
    start, end, kind = found
    result.match = kind
    result.context = sentence_context(norm_source, start, end)
    result.secondary_markers = secondary_markers(result.context)
    if len(normalise(claim.quote)) < MIN_QUOTE_CHARS:
        result.notes.append("The quote is short; a short string can occur by chance. Read the passage around it.")
    if source.scope == "abstract":
        result.notes.append("Located in the abstract; the full text was not available.")
    elif source.scope == "partial":
        result.notes.append("Located in a text read earlier for this work (an excerpt); the full text was not "
                            "available.")
    result.numbers = check_numbers(claim.claim, claim.quote)
    result.polarity = polarity_mismatch(claim.claim, claim.quote)
    if result.polarity:
        result.flags.append("polarity_mismatch")
    if result.numbers.missing:
        result.flags.append("numbers_missing")
    result.status = next((s for s in STATUSES if s in result.flags), "quote_located")
    return result


class SupportReport(BaseModel):
    claims_file: str
    online: bool
    cache_dir: str
    summary: dict[str, int]
    results: list[ClaimResult]
    sample: Optional[dict[str, Any]] = None  # the random sample's estimate for the unchecked cited sentences
    note: str = ("Mechanical checks only. A located quote does not show that the source supports the claim, and no "
                 "status here means 'confirmed': a reader decides that from the passage (references/claim-support.md).")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """The 95% Wilson interval of a proportion k/n, which stays within 0 and 1 for a small sample."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    centre, half = p + z * z / (2 * n), z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return max(0.0, (centre - half) / (1 + z * z / n)), min(1.0, (centre + half) / (1 + z * z / n))


def sample_meta(path: Path) -> Optional[dict[str, Any]]:
    """The `sample` block sample_claims.py writes into a claims file, when the file has one."""
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError):
        return None
    meta = data.get("sample") if isinstance(data, dict) else None
    return meta if isinstance(meta, dict) and isinstance(meta.get("population"), int) else None


def estimate(meta: dict[str, Any], results: list["ClaimResult"]) -> dict[str, Any]:
    """What the sampled sentences say about the cited sentences nobody checked: the share not fully supported among
    those the reading could judge, its 95% interval, and that range applied to the unchecked rest. Blocked claims
    are left out of the share; unrated ones keep the estimate from being given."""
    drawn = [r for r in results if r.priority == "sample"]
    counts = {o: sum(r.outcome == o for r in drawn) for o in OUTCOMES}
    unrated = [r.id for r in drawn if r.outcome is None]
    judged = counts["confirmed"] + counts["partial"] + counts["rejected"]
    off = counts["partial"] + counts["rejected"]
    rest = max(0, int(meta["population"]) - len(drawn))
    out: dict[str, Any] = {**{k: meta.get(k) for k in ("seed", "cited_sentences", "by_priority", "population")},
                           "drawn": len(drawn), "outcomes": counts, "unrated": unrated, "unchecked": rest}
    if judged and not unrated:
        low, high = wilson(off, judged)
        out |= {"share_not_supported": round(off / judged, 3), "interval": [round(low, 3), round(high, 3)],
                "unchecked_not_supported": [round(low * rest), round(high * rest)],
                "check_the_rest": off / judged > 0.2}
    return out


def run(claims_path: Path, online: bool, cache_dir: Path, shared: bool = True) -> SupportReport:
    claims, base = load_claims(claims_path)
    fetch = Fetcher() if online else None
    results: list[ClaimResult] = []
    texts: dict[str, tuple[Optional[str], SourceInfo]] = {}
    try:
        for claim in claims:
            key = claim.source or ""
            if key not in texts:
                texts[key] = load_source(claim.source, base, fetch, cache_dir, shared)
                if texts[key][0]:
                    texts[key][1].aimed_at_ai, texts[key][1].hidden_for_ai = aimed_at_ai(texts[key][0])
            text, info = texts[key]
            results.append(check_claim(claim, text, info.model_copy(deep=True)))
    finally:
        if fetch is not None:
            fetch.close()
    summary = {status: sum(r.status == status for r in results) for status in STATUSES}
    summary["claims"] = len(results)
    summary["with_secondary_markers"] = sum(bool(r.secondary_markers) for r in results)
    summary["sources_aimed_at_ai"] = len({r.source.given for r in results if r.source.aimed_at_ai})
    summary["sources_hiding_text_for_ai"] = len({r.source.given for r in results if r.source.hidden_for_ai})
    reused = {r.source.given: r.source.reused_from for r in results if r.source.reused_from}
    summary["sources_reused"] = len(reused)
    summary["sources_read"] = len({r.source.given for r in results if r.source.characters})
    meta = sample_meta(claims_path)
    return SupportReport(claims_file=str(claims_path), online=online, cache_dir=str(cache_dir), summary=summary,
                         results=results, sample=estimate(meta, results) if meta else None)


def exit_code(report: SupportReport) -> int:
    if any(r.status in FLAGGED or r.source.hidden_for_ai for r in report.results):
        return 1
    if any(r.status == "source_unavailable" for r in report.results):
        return 3
    return 0


# Each status in words, as a heading and as the summary's phrase for "For N claims, ...".
STATUS_HEADING = {
    "quote_not_found": "The quoted passage was not found in the source",
    "polarity_mismatch": "The passage points in a different direction from the claim",
    "numbers_missing": "A number in the claim is not in the passage",
    "source_unavailable": "This claim could not be checked: no source text was available",
    "quote_located": "The quoted passage was found in the source",
}
STATUS_SUMMARY = {
    "quote_located": "the quoted passage was found in the source and nothing was flagged",
    "numbers_missing": "the passage was found, but a number in the claim is not in it",
    "polarity_mismatch": "the passage was found, but it points in a different direction from the claim",
    "quote_not_found": "the quoted passage was not found in the source text",
    "source_unavailable": "no source text was available, so the check could not run",
}
REPORT_ORDER = ("quote_not_found", "polarity_mismatch", "numbers_missing", "source_unavailable", "quote_located")
SERVICE_NAMES = {"europepmc": "Europe PMC", "biorxiv": "bioRxiv", "medrxiv": "medRxiv", "arxiv": "arXiv"}
FILE_LINE = re.compile(r"^(?P<file>[^:()]+?):(?P<line>\d+)(?:\s*\((?P<section>[^)]*)\))?$")
LINE_ONLY = re.compile(r"^(?:L|line\s*)?(?P<line>\d+)$", re.IGNORECASE)


def where_in_manuscript(location: str) -> str:
    """'seeded.md:14 (Introduction)' as 'under Introduction (seeded.md, line 14)'; never a bare 'L14'."""
    location = " ".join(location.split())
    m = FILE_LINE.match(location)
    if m and m.group("section"):
        return f"under {m.group('section')} ({m.group('file')}, line {m.group('line')})"
    if m:
        return f"({m.group('file')}, line {m.group('line')})"
    m = LINE_ONLY.match(location)
    if m:
        return f"(line {m.group('line')})"
    return f"under {location}"


def _quoted(text: str) -> str:
    return "“" + " ".join(text.split()) + "”"


def _quoted_end(text: str) -> str:
    """A quotation that ends a sentence: the full stop is added only when the quote does not end one itself."""
    return _quoted(text) + ("" if text.rstrip()[-1:] in ".!?" else ".")


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _listed(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _source_sentence(r: ClaimResult) -> str:
    cited = f"It cites reference {r.reference}" + (f" ({r.source.url})" if r.source.url else "") + "."
    if r.source.scope == "supplied":
        return f"{cited} The source text was read from the supplied file {r.source.given}."
    earlier = ""
    if r.source.reused_from:
        reused = r.source.reused_from
        earlier = (f" It reused {_plural(reused['texts'], 'text', 'texts')} read for this work earlier"
                   + (f" (in run {', '.join(reused['runs'])}" if reused.get("runs") else " (")
                   + (f", the oldest on {reused['oldest']})" if reused.get("oldest") else ")") + ".")
    if r.source.scope == "partial":
        return f"{cited} More than the abstract but not the full text was read: {r.source.via}.{earlier}"
    if r.source.scope in ("full_text", "abstract"):
        via = r.source.via or ""
        service = SERVICE_NAMES.get(via.split(":", 1)[0], "")
        version = re.search(r"\(version [^)]+\)", via)
        what = "The full text" if r.source.scope == "full_text" else "Only the abstract"
        return (f"{cited} {what} was read" + (f" from {service}" if service else "")
                + (f" {version.group(0)}" if version else "") + "." + earlier)
    return cited


def _claim_block(r: ClaimResult) -> list[str]:
    lines = [f"## {STATUS_HEADING[r.status]} (claim {r.id})", "",
             f"The manuscript says, {where_in_manuscript(r.location)}: {_quoted_end(r.claim)}", "",
             _source_sentence(r), ""]
    found = r.status in ("quote_located", "numbers_missing", "polarity_mismatch")
    if r.status == "source_unavailable":
        lines.append(f"This claim could not be checked. {r.source.reason or 'No source text was available.'}")
        if r.source.free_urls:
            lines.append("A free full text is listed at " + _listed(r.source.free_urls) + "; read it there.")
        if r.quote:
            lines.append(f"The passage to look for is {_quoted_end(r.quote)}")
    elif r.status == "quote_not_found" and r.quote:
        lines.append(f"The quoted passage, {_quoted(r.quote)}, was not found in the source text.")
        if r.closest_passage:
            alike = f", about {round(100 * r.closest_ratio)}% alike," if r.closest_ratio is not None else ""
            lines.append(f"The closest passage in the source{alike} reads "
                         f"{_quoted(r.closest_passage)}. The quote may be misquoted, or it may sit in a figure, a "
                         "table or a supplement that the text lacks.")
    elif found:
        how = " Its parts were found in order, with the omissions marked." if r.match == "ellipsis" else ""
        lines.append(f"The quoted passage was found in the source: {_quoted_end(r.quote or '')}{how}")
    extra: list[str] = []
    if r.source.hidden_for_ai:
        extra.append("The source hides text addressed to AI systems in invisible characters: "
                     + _listed([_quoted(a) for a in r.source.hidden_for_ai]) + ". The check did not act on it. Hidden "
                     "instructions to AI tools are a sign of a manipulated document, so read this source yourself "
                     "before relying on it.")
    if r.source.aimed_at_ai:
        extra.append("The source contains " + ("a passage" if len(r.source.aimed_at_ai) == 1 else "passages")
                     + " that may address AI systems: " + _listed([_quoted(a) for a in r.source.aimed_at_ai]) + ". The "
                     "check did not act on it. Read it in context: a paper about language models or benchmarks can "
                     "use such words for its own reasons.")
    if r.numbers and r.numbers.missing:
        extra.append(f"The claim gives {_listed(r.numbers.missing)}, which the passage does not contain. The number "
                     "may be wrong, or it may sit in a nearby sentence, a table or a conversion, so read the source "
                     "around the passage before deciding.")
    if r.numbers and r.numbers.year_like_missing:
        extra.append(f"The claim also gives the year {_listed(r.numbers.year_like_missing)}, which is not in the "
                     "passage; a year rarely needs to be, so it is not flagged.")
    for reason in r.polarity:
        extra.append(f"{reason} A word list cannot read every sentence, so read both and decide.")
    if r.secondary_markers:
        extra.append("The passage around the quote cites or reports other work ("
                     + _listed([_quoted(m) for m in r.secondary_markers]) + "), so the number may come from a primary "
                     "study. Cite that study after checking its own text, or write “as summarised by”.")
    extra += r.notes
    if found and not extra:
        extra.append("Nothing was flagged. Read the passage to decide whether it carries the claim as written.")
    if extra:
        lines += [""] + extra
    return lines + [""]


def _sample_lines(e: dict[str, Any]) -> list[str]:
    """The random sample's estimate, in sentences for the authors."""
    o = e["outcomes"]
    lines = ["## A random sample of the other cited sentences", "",
             f"The priority claims took {_plural(int(e['by_priority'] or 0), 'cited sentence', 'cited sentences')}. Of "
             f"the other {e['population']}, {e['drawn']} were drawn at random (seed {e['seed']}, so the draw can be "
             f"repeated) and checked like the rest."]
    if e["unrated"]:
        lines.append(f"{_plural(len(e['unrated']), 'sampled sentence has', 'sampled sentences have')} no outcome yet "
                     f"({_listed(e['unrated'])}): record each reading's outcome before the estimate is given.")
        return lines + [""]
    if "share_not_supported" not in e:
        lines.append(f"None of them could be judged ({o['blocked']} blocked), so the sample gives no estimate.")
        return lines + [""]
    judged = o["confirmed"] + o["partial"] + o["rejected"]
    off = o["partial"] + o["rejected"]
    low, high = (round(100 * x) for x in e["interval"])
    few, many = e["unchecked_not_supported"]
    lines.append(f"Of the {judged} the reading could judge, {off} {'was' if off == 1 else 'were'} not fully supported "
                 f"by {'its' if judged == 1 else 'their'} source ({round(100 * e['share_not_supported'])}%; with 95% "
                 f"confidence between {low}% and {high}%)"
                 + (f"; {o['blocked']} could not be checked" if o["blocked"] else "") + ".")
    lines.append(f"If the cited sentences nobody checked are like the sample, about {few} to {many} of those "
                 f"{e['unchecked']} may not be fully supported. This is an estimate from a sample, not a check of each "
                 "sentence.")
    if e["check_the_rest"]:
        lines.append("More than one in five of the sample was not fully supported, which points to a habit of the "
                     "draft: the remaining cited sentences are checked too, in the order they appear.")
    return lines + [""]


def to_markdown(report: SupportReport) -> str:
    s = report.summary
    out = ["# Do the cited sources contain the quoted passages?", "",
           f"This report covers the {_plural(s['claims'], 'claim', 'claims')} in {Path(report.claims_file).name}. "
           "For each claim it looks for the quoted passage in the source's text, then compares the claim's numbers "
           "and direction of effect with the passage. It is a mechanical check: a passage that was found still has "
           "to be read to decide whether it supports the claim.", ""]
    counts = [f"For {_plural(s[k], 'claim', 'claims')}, {STATUS_SUMMARY[k]}." for k in
              ("quote_located", "numbers_missing", "polarity_mismatch", "quote_not_found", "source_unavailable") if s[k]]
    out += [" ".join(counts), ""]
    if s.get("sources_hiding_text_for_ai"):
        out += [f"{_plural(s['sources_hiding_text_for_ai'], 'source hides', 'sources hide')} text addressed to AI "
                "systems in invisible characters; the claims citing them say where. The check did not act on it.", ""]
    if s.get("sources_aimed_at_ai"):
        out += [f"{_plural(s['sources_aimed_at_ai'], 'source contains', 'sources contain')} passages that may address "
                "AI systems, listed with the claims citing them, to read in context.", ""]
    if s.get("sources_reused"):
        oldest = min((r.source.reused_from.get("oldest") or "" for r in report.results if r.source.reused_from),
                     default="")
        out += [f"{_plural(s['sources_reused'], 'source was', 'sources were')} read with texts kept from earlier reads "
                f"of the same work (source_cache.py{', the oldest from ' + oldest if oldest else ''}); "
                f"{max(s['sources_read'] - s['sources_reused'], 0)} only from what this run fetched or was given. The "
                "verdicts are this run's own.", ""]
    if not report.online:
        out += ["The check ran offline, so sources given only as an identifier were read from the local cache. A run "
                "with the online lookups fetches their open-access text.", ""]
    if report.sample:
        out += _sample_lines(report.sample)
    for status in REPORT_ORDER:
        for r in report.results:
            if r.status == status:
                out += _claim_block(r)
    return "\n".join(out).rstrip("\n") + "\n"


@app.command()
def main(
    claims_file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True,
                                                help="YAML or JSON claims file")],
    online: Annotated[bool, typer.Option(help="Fetch legal open-access text for identifiers (Europe PMC, "
                                              "bioRxiv/medRxiv, arXiv)")] = False,
    cache_dir: Annotated[Optional[Path], typer.Option(help="Where fetched texts are kept; in a run, "
                                                           "RUN/manuscript-reference-check/sources (default: the "
                                                           "platform's cache folder, under "
                                                           "manuscript-reference-check/sources)")] = None,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the full report as JSON")] = None,
    shared_cache: Annotated[bool, typer.Option(help="Use and add to the texts read for each work in earlier runs "
                                                    "(source_cache.py); --no-shared-cache reads afresh")] = True,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the Markdown report here (default: stdout)")] = None,
) -> None:
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on the console whatever the platform's default
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    try:
        report = run(claims_file, online, (cache_dir or default_cache_dir()).expanduser(), shared_cache)
    except ClaimsFileError as exc:
        typer.echo(f"malformed claims file {claims_file}:", err=True)
        for problem in exc.problems:
            typer.echo(f"  - {problem}", err=True)
        raise typer.Exit(code=2) from exc
    if json_out:
        json_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md = to_markdown(report)
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {md_out}")
    else:
        typer.echo(md)
    raise typer.Exit(code=exit_code(report))


if __name__ == "__main__":
    app()
