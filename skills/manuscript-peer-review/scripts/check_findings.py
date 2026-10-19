# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12"]
# ///
"""Check simulated-referee findings against the finding contract and the manuscript text.

A finding written by a reviewer seat is a proposal until it passes this check. Its quote must occur in
the manuscript, or in a supplementary file given with --supplement, after Unicode, whitespace and simple
Markdown/LaTeX markup normalisation; an absence finding must say where the seat looked; required fields
must be present with allowed values; a concern that asserts external prior work needs an identifier or
the status `unverified`. Findings that fail are listed as "not yet findings", never dropped. Findings
that point at the same text, carry the same group label or raise a near-identical concern are grouped,
with the number of distinct seats in each group. That count says how many seats raised a concern, not
whether it is right. The script gives no scores. Schema: ../references/finding-schema.md.

Each referee's report (its summary and one recommendation per journal) is checked too: the recommendation
is one of accept, minor revision, major revision or reject, gives a reason, and names the referee's own
findings it rests on. After adjudication the check says which recommendations rest on a finding the
defence refuted or narrowed, and sorts each referee's confirmed findings into the major concerns, minor
concerns and questions of its report. A file without reports (a quick pass) is not an error.

The Markdown report is written for people who did not write these skills: each group quotes the passage it
concerns with its section (the line number only in parentheses), statuses are plain words, prior-work
identifiers are full URLs, and after adjudication the groups are sorted by when the authors can act on
them. The JSON keeps every field, code and line number for other tools.

    uv run --script check_findings.py findings.json PAPER.md
    uv run --script check_findings.py findings.json PAPER.tex --supplement supp.md --md check.md --json check.json
    uv run --script check_findings.py findings.json PAPER.md --adjudicated      # also require verdict fields

Exit codes: 0 every finding (and strength) meets the contract; 1 at least one is not yet a finding
(failed, or its quote could not be checked); 2 unusable input (malformed JSON, unsupported file type).
"""

from __future__ import annotations

import bisect
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)


SEATS = ("claims-novelty", "evidence-statistics", "reproducibility", "champion", "skeptic",
         "desk-editor", "software-methods", "genomics", "human-data-clinical", "ai-systems")
SEVERITIES = ("blocker", "major", "optional", "uncertain")
CONSEQUENCES = ("validity", "support", "scope", "reproducibility", "interpretation")
ROUTES = ("fixable-in-text", "author-required", "venue", "policy", "dropped")
TRIAGE = ("substance", "misread-risk", "polish")
VERDICTS = ("confirmed", "refuted", "downgraded")
KINDS = ("present", "absence")
COSTS = ("text", "reanalysis", "new-data", "unknown")
STAGE_KEYS = ("now", "writing", "journal", "final")  # the optional `stage` an adjudicator may set
HAND_TO = ("manuscript-prose-edit", "manuscript-reference-check", "manuscript-reporting-check",
           "manuscript-integrity-check", "manuscript-policy-fit", "manuscript-journal-adapt",
           "manuscript-journal-select", "manuscript-story")
PRIOR_STATUS = ("verified", "unverified")
RECOMMENDATIONS = ("accept", "minor-revision", "major-revision", "reject")
RECOMMENDATION_WORDS = {"accept": "accept", "minor-revision": "minor revision", "major-revision": "major revision",
                        "reject": "reject"}
REQUIRED =("id", "seat", "location", "concern", "claim", "consequence", "severity", "change_my_mind", "route")

MIN_QUOTE_WORDS = 3  # shorter quotes must reach MIN_QUOTE_CHARS to anchor a finding
MIN_QUOTE_CHARS = 12
MAX_ELISION_GAP = 200  # tokens allowed between the fragments of an elided quote
EXCERPT_WIDTH = 160  # characters of manuscript text shown around a quoted passage in the Markdown report

# Plain words for the Markdown report; the JSON keeps the field names and tokens.
FIELD_WORDS = {
    "id": "an id", "seat": "the simulated referee who raised it", "location": "the section it concerns",
    "concern": "the concern itself", "claim": "the claim at stake",
    "consequence": "what resolving it could change about that claim", "severity": "a severity",
    "change_my_mind": "what would change a referee's mind", "route": "how it would be handled",
}
CONTRACT_WORDS = {"pass": "ready", "fail": "failed", "not_assessed": "could not be checked"}
# Where a confirmed concern sits in the order the authors work (author-priorities.md, "Order the work by
# when it can be done"). Groups after adjudication are listed in this order. Points for other checks are
# current work (a number that disagrees, a citation's identity), so they come before the end-stage group;
# an end-stage point for another check is listed in the end-stage group (finding_stage).
STAGES = (
    ("now", "Fix now: the science and the evidence"),
    ("writing", "Then the writing"),
    ("journal", "Once you have chosen the journal"),
    ("other-checks", "Also found, belongs to other checks"),
    ("final", "Before submission, once the code is final"),
    ("answered", "Answered by the paper (refuted by the defence pass)"),
    ("dropped", "Dropped"),
)
OTHER_CHECKS = ("manuscript-integrity-check", "manuscript-reference-check", "manuscript-reporting-check")

# --- normalisation ------------------------------------------------------------------------------------
# Every mask keeps the text's length, so a token's offsets point into the original file and give its line.

_TRANSLATE = {ord(c): '"' for c in "\u201c\u201d\u201e\u201f\u00ab\u00bb\u2033\u301d\u301e\uff02"}
_TRANSLATE |= {ord(c): "'" for c in "\u2018\u2019\u201a\u201b\u2032\u2039\u203a\u00b4"}
_TRANSLATE |= {ord(c): "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"}
_TRANSLATE |= {ord(c): " " for c in "\u00a0\u2007\u2009\u200a\u202f\u2060\u200b"}

_DASH_RUN = re.compile(r"-{2,}")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_LATEX_COMMENT = re.compile(r"(?<!\\)%[^\n]*")
_ELISION = re.compile(r"\s*(?:\[\s*(?:\.\.\.|\u2026)\s*\]|\.\.\.|\u2026)\s*")

# Removed entirely in the stripped view (their arguments are not prose a reader sees).
_DROP_WITH_ARG = re.compile(
    r"\\(?:cite[a-zA-Z]*|[cC]ref|autoref|eqref|ref|pageref|label|url|includegraphics|bibliography(?:style)?)"
    r"\*?(?:\[[^\]\n]*\])*\{[^{}]*\}")
_LATEX_ESCAPED = re.compile(r"\\([%&#$_{}~^])")
_LATEX_LINEBREAK = re.compile(r"\\\\")
_LATEX_COMMAND = re.compile(r"\\[a-zA-Z@]+\*?")
_MD_LINK = re.compile(r"(!?\[)([^\]\n]*)(\]\([^)\n]*\)|\]\[[^\]\n]*\])")
_MD_CITATION = re.compile(r"\[-?@[^\]\n]+\]|\[\^[^\]\n]+\]")
_NUMERIC_CITATION = re.compile(r"\[\d+(?:\s*[-,]\s*\d+)*\]")
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>\n]*>")
_LINE_MARKUP = re.compile(r"(?m)^[ \t]*(?:#{1,6}|>)")
_EMPHASIS = re.compile(r"\*+|(?<!\w)_+|_+(?!\w)|`+|[|{}$~]")

_TOKEN = re.compile(r"\w+|[^\w\s]")
# The end of a sentence: . ? or ! (with any closing quote or bracket) before whitespace. Decimals do not match.
# A line that is not prose: a Markdown heading, or a LaTeX command line such as \section{...} or \begin{...}.
_STRUCTURAL_LINE = re.compile(r"(?m)^[ \t]*(?:#{1,6}[ \t].*|\\[a-zA-Z]+\*?(?:\[[^\]\n]*\])?(?:\{[^}\n]*\})*[ \t]*)$\n?")
_SENTENCE_END = re.compile(r"[.?!][\"'\u201d\u2019)\]]*(?=\s)\s*")
_DROP_TOKENS = {'"', "'", "`"}


def _blank(match: re.Match[str]) -> str:
    """Spaces of the match's length, keeping its newlines so line numbers survive."""
    return re.sub(r"[^\n]", " ", match.group(0))


def _light(text: str, comments: Optional[str] = None) -> str:
    """Optionally blank out the file's comments, then unify quotes, dashes and odd spaces.

    Comments go first: collapsing dash runs would otherwise turn `<!--` into `<!-` and expose them.
    """
    if comments in ("markdown", "latex"):
        text = _HTML_COMMENT.sub(_blank, text)
    if comments == "latex":
        text = _LATEX_COMMENT.sub(_blank, text)
    text = text.translate(_TRANSLATE)
    return _DASH_RUN.sub(lambda m: "-" + " " * (len(m.group(0)) - 1), text)


def _stripped(text: str) -> str:
    """Blank out simple Markdown and LaTeX markup, citations and cross-references (same length)."""
    text = _DROP_WITH_ARG.sub(_blank, text)
    text = _LATEX_ESCAPED.sub(lambda m: " " + m.group(1), text)
    text = _LATEX_LINEBREAK.sub("  ", text)
    text = _LATEX_COMMAND.sub(_blank, text)
    text = _MD_CITATION.sub(_blank, text)
    text = _MD_LINK.sub(lambda m: " " * len(m.group(1)) + m.group(2) + " " * len(m.group(3)), text)
    text = _NUMERIC_CITATION.sub(_blank, text)
    text = _HTML_TAG.sub(_blank, text)
    text = _LINE_MARKUP.sub(_blank, text)
    return _EMPHASIS.sub(_blank, text)


def _tokens(text: str) -> list[tuple[str, int, int]]:
    out = []
    for m in _TOKEN.finditer(text):
        tok = m.group(0)
        if tok in _DROP_TOKENS:
            continue
        out.append((unicodedata.normalize("NFKC", tok).casefold(), m.start(), m.end()))
    return out


def _is_word(tok: str) -> bool:
    return tok[:1].isalnum() or tok[:1] == "_"


@dataclass
class Match:
    start: int  # character offsets in the original file
    end: int
    view: str
    occurrences: int


@dataclass
class Document:
    path: Path
    text: str
    mode: str  # "latex" or "markdown" (plain text is read as Markdown)
    views: dict[str, list[tuple[str, int, int]]] = field(default_factory=dict)
    words: dict[str, list[str]] = field(default_factory=dict)
    index: dict[str, dict[str, list[int]]] = field(default_factory=dict)
    line_starts: list[int] = field(default_factory=list)
    visible: str = ""  # the text with comments blanked out (same length), for excerpts

    @classmethod
    def load(cls, path: Path) -> "Document":
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        mode = "latex" if path.suffix.lower() == ".tex" else "markdown"
        doc = cls(path=path, text=text, mode=mode)
        doc.visible = _HTML_COMMENT.sub(_blank, text)
        if mode == "latex":
            doc.visible = _LATEX_COMMENT.sub(_blank, doc.visible)
        light = _light(text, comments=mode)
        doc.views = {"light": _tokens(light), "stripped": _tokens(_stripped(light))}
        for name, toks in doc.views.items():
            doc.words[name] = [t for t, _, _ in toks]
            idx: dict[str, list[int]] = {}
            for i, (tok, _, _) in enumerate(toks):
                idx.setdefault(tok, []).append(i)
            doc.index[name] = idx
        doc.line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
        return doc

    def line(self, offset: int) -> int:
        return bisect.bisect_right(self.line_starts, offset)

    def excerpt(self, start: int, end: int, width: int = EXCERPT_WIDTH) -> str:
        """The sentence (or table row) holding text[start:end] as a reader sees it, cut to about `width`
        characters around that span; the span is in bold when the excerpt shows more than the span.

        Comments are left out, as in the quote check. In prose the excerpt runs from the start of the
        sentence to its end within the paragraph; in a table it is the row.
        """
        text = self.visible
        first = text.rfind("\n", 0, start) + 1
        last = text.find("\n", end)
        last = len(text) if last < 0 else last
        row = text[first:last].lstrip()
        tidy = _readable_tex if self.mode == "latex" else (lambda part: part)
        if row.startswith("|") or (self.mode == "latex" and "&" in row):
            return cut_around(*(tidy(x) for x in (text[first:start], text[start:end], text[end:last])), width)
        breaks = [m.end() for m in re.finditer(r"\n[ \t]*\n", text[:start])]
        para_start = breaks[-1] if breaks else 0
        para_end = re.search(r"\n[ \t]*\n", text[end:])
        before = text[para_start:start]
        after = text[end:end + para_end.start()] if para_end else text[end:]
        headings = list(_STRUCTURAL_LINE.finditer(before))
        if headings:
            before = before[headings[-1].end():]
        stop_line = _STRUCTURAL_LINE.search(after)
        if stop_line:
            after = after[:stop_line.start()]
        sentence_ends = list(_SENTENCE_END.finditer(before))
        if sentence_ends:
            before = before[sentence_ends[-1].end():]
        stop = _SENTENCE_END.search(after)
        if re.search(r"[.?!][\"'\u201d\u2019)\]]*\s*$", text[start:end]):
            after = ""  # the quote ends its sentence
        elif stop:
            after = after[:stop.start() + len(stop.group(0).rstrip())]
        return cut_around(tidy(before), tidy(text[start:end]), tidy(after), width)

    def _occurrences(self, view: str, needle: list[str]) -> list[int]:
        hay = self.words[view]
        n = len(needle)
        return [i for i in self.index[view].get(needle[0], []) if hay[i:i + n] == needle]

    def find(self, fragments: list[list[str]], view: str) -> list[tuple[int, int]]:
        """Token spans where the fragments occur in order, each within MAX_ELISION_GAP of the last."""
        spans = []
        for s0 in self._occurrences(view, fragments[0]):
            end = s0 + len(fragments[0])
            for frag in fragments[1:]:
                nxt = [s for s in self._occurrences(view, frag) if end <= s <= end + MAX_ELISION_GAP]
                if not nxt:
                    break
                end = nxt[0] + len(frag)
            else:
                spans.append((s0, end))
        return spans

    def locate(self, quote: str) -> Optional[Match]:
        for view, prep in (("light", _light), ("stripped", lambda q: _stripped(_light(q)))):
            fragments = [[t for t, _, _ in _tokens(prep(f))] for f in _ELISION.split(quote) if f.strip()]
            fragments = [f for f in fragments if f]
            if not fragments:
                continue
            spans = self.find(fragments, view)
            if spans:
                toks = self.views[view]
                s, e = spans[0]
                return Match(start=toks[s][1], end=toks[e - 1][2], view=view, occurrences=len(spans))
        return None

    def longest_opening(self, quote: str) -> Optional[tuple[int, int, int, int]]:
        """(matched words, total words, start, end offsets) of the longest opening run of the quote found."""
        first = _ELISION.split(quote)[0]
        for view, prep in (("light", _light), ("stripped", lambda q: _stripped(_light(q)))):
            toks = [t for t, _, _ in _tokens(prep(first))]
            words = sum(_is_word(t) for t in toks)
            for k in range(len(toks) - 1, 0, -1):
                if sum(_is_word(t) for t in toks[:k]) < MIN_QUOTE_WORDS:
                    break
                occ = self._occurrences(view, toks[:k])
                if occ:
                    spans = self.views[view]
                    return (sum(_is_word(t) for t in toks[:k]), words, spans[occ[0]][1], spans[occ[0] + k - 1][2])
        return None


_STARS = re.compile(r"\*+")
_TEX_UNWRAP = re.compile(r"\\(?:emph|textbf|textit|texttt|textsc|textsf|underline|url|mbox|text)\{([^{}]*)\}")


def _readable_tex(text: str) -> str:
    """LaTeX source as a reader of the PDF would recognise it: formatting commands unwrapped, `~` as a
    space, list markers and escapes removed. References and citations stay, so the passage can be found."""
    for _ in range(2):
        text = _TEX_UNWRAP.sub(r"\1", text)
    text = re.sub(r"(?<!\\)~", " ", text)
    text = re.sub(r"\\item\b\s*", "", text)
    return re.sub(r"\\([%&#$_{}])", r"\1", text)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def cut_around(before: str, span: str, after: str, width: int = EXCERPT_WIDTH, mark: bool = True) -> str:
    """Show `span` with as much of its surroundings as fits in about `width` characters.

    Whitespace is collapsed, cuts fall between words and are marked [...], and the span is set in bold when
    some context is shown, so a reader sees which part of the line the finding is about.
    """
    before, span, after = (_squash(_STARS.sub("", x)) for x in (before, span, after))
    before, span, after = before.lstrip(), span.strip(), after.rstrip()
    if len(span) > width:
        half = width // 2
        return f"{span[:half].rsplit(' ', 1)[0]} [...] {span[-half:].split(' ', 1)[-1]}"
    room = max(0, width - len(span))
    left = min(len(before), room // 2)
    right = min(len(after), room - left)
    left = min(len(before), room - right)
    if len(before) > left:
        before = "[...] " + before[len(before) - left:].split(" ", 1)[-1] if left else ""
    if len(after) > right:
        after = after[:right].rsplit(" ", 1)[0] + " [...]" if right else ""
    shown = f"**{span}**" if mark and span and (before.strip() or after.strip()) else span
    return f"{before}{shown}{after}".strip()


def _quote_size(quote: str) -> tuple[int, int]:
    """Word tokens and characters of the quote after normalisation (elision marks removed)."""
    toks = [t for f in _ELISION.split(quote) for t, _, _ in _tokens(_light(f))]
    words = [t for t in toks if _is_word(t)]
    return len(words), sum(len(t) for t in toks)


# --- the contract -----------------------------------------------------------------------------------------

_PRIOR_WORK_CUE = re.compile(
    r"\b(?:not (?:novel|new)|lacks? novelty|novelty (?:is|seems) (?:limited|overstated|unclear)|incremental|"
    r"(?:already|previously) (?:been )?(?:shown|done|published|reported|described|proposed|developed|available)|"
    r"prior (?:work|art|tools?|methods?|studies|study)|existing (?:tools?|methods?|work|approaches|software|"
    r"predictors?|scores?|resources?|databases?)|has been (?:done|shown|published|reported)|"
    r"(?:is|are|was|were) not the first|first (?:tool|method|study|resource|database|score|to)\b|"
    r"missing (?:citations?|references?|comparisons?) (?:to|with))", re.IGNORECASE)
_IDENTIFIER = re.compile(
    r"^(?:(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/\S+|PMID:?\s*\d{1,9}|\d{6,9}|"
    r"(?:arXiv:\s*)?\d{4}\.\d{4,5}(?:v\d+)?|https?://\S+|(?:ISBN:?\s*)?[\d-]{10,17}[\dX])$", re.IGNORECASE)
_LINTS = {
    "state-of-the-art": (re.compile(r"\bstate[- ]of[- ]the[- ]art\b|\bSOTA\b", re.IGNORECASE),
                         "The concern rests on the paper not being state of the art, which matters only if the "
                         "paper claims to be better than other methods."),
    "new-work": (re.compile(r"\b(?:should|must|need(?:s)? to|ought to)\s+(?:also\s+)?"
                            r"(?:run|perform|add|include|conduct|test|repeat|collect|validate)\b", re.IGNORECASE),
                 "The concern asks for new work. Confirm that the claim needs it, and offer narrowing the claim "
                 "as the cheaper alternative."),
    # An objection to the work being simple: "too simple", "simplistic", "a trivial extension", "the method
    # is trivial". Not "near-trivial scores" or "non-trivial", which describe results, not the contribution
    # (smoke run on Paper 2, 2026-10-15).
    "simplicity": (re.compile(
        r"\btoo simple\b|\b(?:overly|rather|fairly|quite) simple\b|\bsimplistic\b"
        r"|(?<![-\w])trivial\s+(?:extension|contribution|method|approach|tool|idea|change|modification|"
        r"application|combination|adaptation|step|task|problem|engineering)\b"
        r"|\b(?:is|are|seems|seem|appears|appear|looks|look|remains|remain)\s+(?:rather\s+|fairly\s+|quite\s+|"
        r"somewhat\s+)?trivial\b"
        r"|\bstraightforward\s+(?:extension|application|combination|adaptation)\b", re.IGNORECASE),
        "The concern objects to the work being simple, which is not a defect unless a claim depends on more."),
}

_STOP = set("""about above after again against also among another because been before being between both
could does doing during each either every from further have having here into itself just more most much
must neither other otherwise over paper same should since some such than that their them then there these
they this those through under until upon very were what when where which while whom whose will with
within without would authors manuscript study claim claims section concern concerns issue issues problem
problems defect defects unclear seat seats reviewer referee second different wording seen raised point""".split())


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", text).casefold())
            if (len(w) >= 4 or (w.isdigit() and len(w) >= 3)) and w not in _STOP}


def _similar(a: str, b: str) -> bool:
    """Near-duplicate concerns: at least four shared content words and half the combined vocabulary.

    Errs towards keeping concerns apart: a missed merge leaves a duplicate for adjudication to fold,
    a false merge hides a distinct concern.
    """
    wa, wb = _content_words(a), _content_words(b)
    shared = wa & wb
    return len(shared) >= 4 and len(shared) / len(wa | wb) >= 0.5


def _norm_location(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


@dataclass
class Sources:
    manuscript: Document
    supplements: list[Document]
    unreadable: dict[str, str]  # supplied supplementary file name -> reason it could not be read

    def candidates(self, source: Optional[str]) -> tuple[list[Document], Optional[str]]:
        """Documents to search for a quote, or the reason the quote cannot be checked."""
        docs = [self.manuscript, *self.supplements]
        if not source:
            return docs, None
        wanted = source.replace("\\", "/").strip()
        for doc in docs:
            name = doc.path.as_posix()
            if wanted in ("manuscript", doc.path.name) or name.endswith("/" + wanted) or name == wanted:
                return [doc], None
        for name, reason in self.unreadable.items():
            if Path(name).name == Path(wanted).name:
                return [], f"the file {wanted} could not be read ({reason})"
        return [], f"the file {wanted} was not supplied (pass it with --supplement)"


def _words_list(items: list[str] | tuple[str, ...], last: str = "or") -> str:
    items = list(items)
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} {last} {items[-1]}"


def _check_quote(quote: str, source: Optional[str], sources: Sources, what: str) -> dict[str, Any]:
    """Locate one quote. status: verified | not_found | not_assessed."""
    words, chars = _quote_size(quote)
    if words < MIN_QUOTE_WORDS and chars < MIN_QUOTE_CHARS:
        return {"status": "not_found", "problem": f"The {what} has {words} word{'s' * (words != 1)}, too short to "
                f"show which passage is meant; quote at least {MIN_QUOTE_WORDS} words or {MIN_QUOTE_CHARS} "
                f"characters."}
    docs, reason = sources.candidates(source)
    if reason:
        return {"status": "not_assessed", "problem": f"The {what} could not be checked, because {reason}."}
    for doc in docs:
        m = doc.locate(quote)
        if m:
            out = {"status": "verified", "file": doc.path.name, "line": doc.line(m.start),
                   "end_line": doc.line(max(m.start, m.end - 1)), "start": m.start, "end": m.end,
                   "view": m.view, "occurrences": m.occurrences, "excerpt": doc.excerpt(m.start, m.end)}
            return out
    near = [(doc, doc.longest_opening(quote)) for doc in docs]
    near = [(doc, n) for doc, n in near if n]
    hint = ""
    if near:
        doc, (k, total, start, end) = max(near, key=lambda x: x[1][0])
        hint = (f" Its first {k} of {total} words occur in {doc.path.name}, where the text reads "
                f"\"{doc.excerpt(start, end)}\" (line {doc.line(start)}); after that the wording differs.")
    return {"status": "not_found", "problem": f"The {what} does not occur word for word in "
            f"{_words_list([d.path.name for d in docs])}.{hint}"}


def _enum(finding: dict[str, Any], key: str, allowed: tuple[str, ...], problems: list[str]) -> None:
    value = finding.get(key)
    if value is not None and value not in allowed:
        problems.append(f"The value '{value}' of {key} is not one of {_words_list(allowed)}.")


def _check_finding(raw: Any, position: int, sources: Sources, adjudicated: bool) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"id": f"#{position + 1}", "seat": None, "contract": "fail",
                "problems": ["This entry is not a JSON object, so it cannot be read as a finding."], "warnings": []}
    f = raw
    problems: list[str] = []
    warnings: list[str] = []
    fid = f.get("id") if _nonempty_str(f.get("id")) else f"#{position + 1}"

    for key in REQUIRED:
        if not _nonempty_str(f.get(key)):
            problems.append(f"It does not give {FIELD_WORDS[key]} ({key} is missing or empty).")
    seat = f.get("seat")
    if _nonempty_str(seat) and seat not in SEATS and not re.fullmatch(r"custom:[\w-]+", seat):
        problems.append(f"The referee '{seat}' (seat) is not one of {_words_list(SEATS)}, or custom:<name>.")
    for key, allowed in (("severity", SEVERITIES), ("consequence", CONSEQUENCES), ("route", ROUTES),
                         ("triage", TRIAGE), ("verdict", VERDICTS), ("kind", KINDS), ("cost", COSTS),
                         ("hand_to", HAND_TO), ("stage", STAGE_KEYS)):
        _enum(f, key, allowed, problems)

    kind = f.get("kind", "present")
    quote_result: Optional[dict[str, Any]] = None
    if kind == "absence":
        looked = f.get("looked_in")
        if not (isinstance(looked, list) and looked and all(_nonempty_str(x) for x in looked)):
            problems.append("It reports something missing but does not say where the referee looked for it "
                            "(looked_in).")
    elif not _nonempty_str(f.get("quote")):
        problems.append("It has no verbatim quote from the manuscript. Quote the passage, or, if the problem is "
                        "something missing, make it an absence finding that lists where the referee looked.")
    if _nonempty_str(f.get("quote")):
        quote_result = _check_quote(f["quote"], f.get("source"), sources, "quote")
        if quote_result["status"] == "not_found":
            problems.append(quote_result["problem"])
        elif quote_result["status"] == "verified" and quote_result["occurrences"] > 1:
            warnings.append(f"The quote occurs {quote_result['occurrences']} times in {quote_result['file']}, so "
                            f"the section named in the finding decides which passage is meant (the first is at "
                            f"line {quote_result['line']}).")

    defence_result: Optional[dict[str, Any]] = None
    if _nonempty_str(f.get("defence_quote")):
        defence_result = _check_quote(f["defence_quote"], f.get("defence_source"), sources,
                                      "defence quote (defence_quote)")
        if defence_result["status"] == "not_found":
            problems.append(defence_result["problem"])

    concern = f.get("concern") if isinstance(f.get("concern"), str) else ""
    prior = f.get("prior_work")
    needs_prior = bool(_PRIOR_WORK_CUE.search(concern)) or f.get("external_claim") is True
    if prior is not None:
        if not isinstance(prior, list):
            problems.append("The prior work (prior_work) must be a list.")
            prior = []
        for i, entry in enumerate(prior, 1):
            if not isinstance(entry, dict) or not _nonempty_str(entry.get("citation")):
                problems.append(f"Prior work {i} has no citation.")
                continue
            status, ident = entry.get("status"), entry.get("identifier")
            if status not in PRIOR_STATUS:
                problems.append(f"Prior work {i} needs the status verified or unverified.")
            if ident is not None and not (_nonempty_str(ident) and _IDENTIFIER.match(ident.strip())):
                problems.append(f"Prior work {i} has the identifier '{ident}', which is not a DOI, PubMed ID, "
                                f"arXiv id, ISBN or URL.")
            if status == "verified" and not _nonempty_str(ident):
                problems.append(f"Prior work {i} is marked verified but has no identifier.")
    if needs_prior:
        usable = [e for e in (prior or []) if isinstance(e, dict) and _nonempty_str(e.get("citation")) and
                  (e.get("status") == "unverified" or (e.get("status") == "verified" and _nonempty_str(e.get("identifier"))))]
        if f.get("external_claim") is False:
            warnings.append("The concern reads like a claim about prior work, but it is marked as not being one "
                            "(external_claim is false); check that it names no existing work.")
        elif not usable:
            problems.append("The concern says the work is not new or that other work exists, but it names no "
                            "prior work with an identifier or the status unverified (prior_work).")

    for name, (rx, message) in _LINTS.items():
        if rx.search(concern):
            warnings.append(f"{message} (fairness check: {name})")

    if f.get("route") == "dropped" and not _nonempty_str(f.get("drop_reason")):
        problems.append("It is dropped without a reason (drop_reason).")
    verdict = f.get("verdict")
    if adjudicated and verdict is None:
        problems.append("After the defence pass every finding needs a verdict: confirmed, refuted or "
                        "downgraded.")
    if verdict in ("confirmed", "downgraded") and f.get("triage") is None:
        problems.append(f"A {verdict} finding needs a triage class: substance, misread-risk or polish.")
    if verdict in VERDICTS and not _nonempty_str(f.get("verdict_evidence")):
        problems.append(f"A {verdict} finding needs the evidence that settled it (verdict_evidence): the text, "
                        f"the recomputation or the record.")
    if verdict == "refuted" and not _nonempty_str(f.get("defence_quote")):
        problems.append("A refuted finding needs the manuscript text that answers it (defence_quote).")

    if problems:
        contract = "fail"
    elif (quote_result and quote_result["status"] == "not_assessed") or \
            (defence_result and defence_result["status"] == "not_assessed"):
        contract = "not_assessed"
        problems.append(next(r["problem"] for r in (quote_result, defence_result)
                             if r and r["status"] == "not_assessed"))
    else:
        contract = "pass"
    return {"id": fid, "seat": seat, "location": f.get("location"), "kind": kind,
            "severity": f.get("severity"), "route": f.get("route"), "verdict": verdict,
            "triage": f.get("triage"), "concern": concern, "group_label": f.get("group"),
            "prior_work": prior or [], "contract": contract, "problems": problems,
            "warnings": warnings, "quote": quote_result, "defence": defence_result,
            "quote_text": f.get("quote"), "looked_in": f.get("looked_in"), "hand_to": f.get("hand_to"),
            "cost": f.get("cost"), "stage": f.get("stage")}


def _check_strength(raw: Any, position: int, sources: Sources) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"index": position + 1, "contract": "fail",
                "problems": ["This entry is not a JSON object, so it cannot be read as a strength."]}
    problems = [f"It does not give {word} ({k} is missing or empty)." for k, word in (
        ("seat", "the simulated referee who noted it"), ("location", "the section"), ("quote", "a quote"),
        ("note", "what is strong about it")) if not _nonempty_str(raw.get(k))]
    result = None
    if _nonempty_str(raw.get("quote")):
        result = _check_quote(raw["quote"], raw.get("source"), sources, "quote")
        if result["status"] != "verified":
            problems.append(result["problem"])
    contract = "pass" if not problems else ("not_assessed" if result and result["status"] == "not_assessed"
                                            and len(problems) == 1 else "fail")
    return {"index": position + 1, "seat": raw.get("seat"), "location": raw.get("location"),
            "note": raw.get("note"), "contract": contract, "problems": problems, "quote": result,
            "quote_text": raw.get("quote")}


def _challenge(f: dict[str, Any]) -> Optional[str]:
    """Why a finding a recommendation rests on no longer stands as the referee raised it, or None."""
    if f["contract"] != "pass":
        return "not-yet-a-finding"
    if f.get("verdict") == "refuted":
        return "refuted"
    if f.get("route") == "dropped":
        return "dropped"
    if f.get("verdict") == "downgraded":
        return "downgraded"
    return None


def _check_report(raw: Any, position: int, findings: list[dict[str, Any]]) -> dict[str, Any]:
    """One referee's report: a summary and, for each journal, a recommendation resting on its own findings."""
    if not isinstance(raw, dict):
        return {"index": position + 1, "seat": None, "summary": None, "recommendations": [], "contract": "fail",
                "problems": ["This entry is not a JSON object, so it cannot be read as a referee's report."]}
    problems: list[str] = []
    seat = raw.get("seat")
    if not _nonempty_str(seat):  # a seat's own file: the report belongs to the one referee who wrote the findings
        seats = {f["seat"] for f in findings if _nonempty_str(f.get("seat"))}
        seat = seats.pop() if len(seats) == 1 else None
        if seat is None:
            problems.append("It does not say which simulated referee wrote it (seat is missing or empty).")
    if not _nonempty_str(raw.get("summary")):
        problems.append("It has no summary of the paper and the referee's overall view (summary is missing or "
                        "empty).")
    by_id = {f["id"]: f for f in findings}
    raw_recs = raw.get("recommendations")
    if not (isinstance(raw_recs, list) and raw_recs):
        problems.append("It gives no recommendation (recommendations must be a list with one entry per journal).")
        raw_recs = []
    recs, venues = [], set()
    for i, r in enumerate(raw_recs, 1):
        if not isinstance(r, dict):
            problems.append(f"Recommendation {i} is not a JSON object.")
            continue
        venue, rec = r.get("venue"), r.get("recommendation")
        what = f"The recommendation for {venue}" if _nonempty_str(venue) else f"Recommendation {i}"
        if not _nonempty_str(venue):
            problems.append(f"Recommendation {i} does not name the journal it is for (venue).")
        elif venue in venues:
            problems.append(f"It gives two recommendations for {venue}.")
        else:
            venues.add(venue)
        if rec not in RECOMMENDATIONS:
            problems.append(f"{what} is '{rec}', not one of {_words_list(RECOMMENDATIONS)}.")
        if not _nonempty_str(r.get("reason")):
            problems.append(f"{what} gives no reason.")
        rests_on = r.get("rests_on", [])
        if not (isinstance(rests_on, list) and all(_nonempty_str(x) for x in rests_on)):
            problems.append(f"{what} must list the ids of the findings it rests on (rests_on).")
            rests_on = []
        if not rests_on and rec in RECOMMENDATIONS and rec != "accept":
            problems.append(f"{what} ({RECOMMENDATION_WORDS[rec]}) names none of the referee's findings it rests on "
                            f"(rests_on).")
        challenged = {}
        for fid in rests_on:
            f = by_id.get(fid)
            if f is None:
                problems.append(f"{what} rests on {fid}, which is not a finding in this file.")
            elif seat and f.get("seat") != seat:
                problems.append(f"{what} rests on {fid}, which another referee ({f.get('seat')}) raised.")
            elif _challenge(f):
                challenged[fid] = _challenge(f)
        recs.append({"venue": venue, "recommendation": rec, "form_wording": r.get("form_wording"),
                     "reason": r.get("reason"), "fit": r.get("fit"), "rests_on": rests_on, "challenged": challenged})
    return {"index": position + 1, "seat": seat, "summary": raw.get("summary"), "recommendations": recs,
            "contract": "fail" if problems else "pass", "problems": problems}


def _by_referee(findings: list[dict[str, Any]], groups: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    """Each referee's confirmed and downgraded findings, as the sections of its report: major concerns, minor
    concerns and questions for the authors. Refuted and dropped findings are not in a report. A finding that
    waits until the code is final is at most a minor concern, whatever its severity."""
    order = {fid: n for n, g in enumerate(groups) for fid in g["findings"]}
    out: dict[str, dict[str, list[str]]] = {}
    for f in sorted(findings, key=lambda f: order.get(f["id"], 10**6)):
        if f["contract"] != "pass" or f.get("verdict") not in ("confirmed", "downgraded") or f.get("route") == "dropped":
            continue
        if f.get("severity") == "uncertain":
            section = "questions"
        elif f.get("severity") in ("blocker", "major") and f.get("stage") != "final":
            section = "major"
        else:
            section = "minor"
        out.setdefault(f["seat"], {"major": [], "minor": [], "questions": []})[section].append(f["id"])
    return out


def finding_stage(f: dict[str, Any]) -> str:
    """When the authors can act on an adjudicated finding (a key of STAGES)."""
    if f.get("verdict") == "refuted":
        return "answered"
    if f.get("route") == "dropped":
        return "dropped"
    if f.get("stage") == "final":  # archive records, declarations, version numbers: never a current concern
        return "final"
    if f.get("hand_to") in OTHER_CHECKS:
        return "other-checks"
    if f.get("stage") in STAGE_KEYS:
        return f["stage"]
    if f.get("route") == "venue":
        return "journal"
    if f.get("triage") in ("misread-risk", "polish"):
        return "writing"
    return "now"


def _group(findings: list[dict[str, Any]], adjudicated: bool = False) -> list[dict[str, Any]]:
    """Union findings that share text, a group label, a near-identical concern, or (absence) a location.

    After adjudication each group carries the stage at which the authors can act on it, and groups are
    ordered by stage, then severity, then position in the manuscript.
    """
    members = [f for f in findings if f["contract"] == "pass"]
    parent = list(range(len(members)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(i: int, j: int) -> None:
        parent[root(i)] = root(j)

    for i, a in enumerate(members):
        for j in range(i + 1, len(members)):
            b = members[j]
            qa, qb = a["quote"], b["quote"]
            overlap = (qa and qb and qa["status"] == qb["status"] == "verified" and qa["file"] == qb["file"]
                       and qa["start"] < qb["end"] and qb["start"] < qa["end"])
            label = _nonempty_str(a["group_label"]) and a["group_label"] == b["group_label"]
            absent = (a["kind"] == b["kind"] == "absence" and _nonempty_str(a["location"])
                      and _norm_location(a["location"]) == _norm_location(b["location"] or ""))
            if overlap or label or absent or _similar(a["concern"], b["concern"]):
                join(i, j)

    clusters: dict[int, list[dict[str, Any]]] = {}
    for i, f in enumerate(members):
        clusters.setdefault(root(i), []).append(f)
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    stage_rank = {key: i for i, (key, _) in enumerate(STAGES)}

    def first_offset(fs: list[dict[str, Any]]) -> int:
        offsets = [f["quote"]["start"] for f in fs if f["quote"] and f["quote"]["status"] == "verified"]
        return min(offsets) if offsets else 10**12

    groups = []
    for fs in clusters.values():
        fs.sort(key=lambda f: rank.get(f["severity"], 99))
        stage = min((finding_stage(f) for f in fs), key=stage_rank.__getitem__) if adjudicated else None
        lead = [f for f in fs if not adjudicated or finding_stage(f) == stage] or fs
        seats = sorted({f["seat"] for f in fs})
        where = sorted({f"{f['quote']['file']}:{f['quote']['line']}" for f in fs
                        if f["quote"] and f["quote"]["status"] == "verified"})
        passages, seen = [], set()
        for f in sorted(fs, key=lambda f: first_offset([f])):
            q = f["quote"]
            if q and q["status"] == "verified" and (q["file"], q["line"]) not in seen:
                seen.add((q["file"], q["line"]))
                passages.append({"finding": f["id"], "location": f["location"], "file": q["file"],
                                 "line": q["line"], "excerpt": q["excerpt"]})
        absences = [{"finding": f["id"], "location": f["location"], "looked_in": f["looked_in"]}
                    for f in fs if f["kind"] == "absence"]
        groups.append({
            "findings": [f["id"] for f in fs], "seats": seats, "n_seats": len(seats),
            "severity": lead[0]["severity"], "where": where,
            "locations": sorted({f["location"] for f in fs if f["location"]}),
            "verdicts": sorted({f["verdict"] for f in fs if f["verdict"]}),
            "routes": sorted({f["route"] for f in fs if f["route"]}),
            "concern": lead[0]["concern"], "concern_from": lead[0]["id"], "stage": stage,
            "passages": passages, "absences": absences,
            "verdict_by_finding": {f["id"]: f["verdict"] for f in fs if f["verdict"]},
            "costs": sorted({f["cost"] for f in lead if f.get("cost")}),
            "hand_to": sorted({f["hand_to"] for f in lead if f.get("hand_to")}),
            "_order": (stage_rank[stage] if stage else 0, rank.get(lead[0]["severity"], 99), first_offset(fs)),
        })
    groups.sort(key=lambda g: g["_order"])
    for n, g in enumerate(groups, 1):
        g["group"] = f"G{n}"
        del g["_order"]
    return groups


def _not_text(path: Path) -> str | None:
    """Why *path* cannot be read as text, or None when it can. Any file is tried, whatever its name: YAML,
    JSON, TOML, BibTeX, HTML and the like are text a manuscript legitimately ships with. Only content that is
    not UTF-8 text (a spreadsheet, a Word file, a PDF, an image) is refused."""
    data = path.read_bytes()
    if b"\0" in data:
        return "it is a binary file, not text"
    try:
        data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return "it is not UTF-8 text"
    return None


def _load_sources(manuscript: Path, supplements: list[Path]) -> Sources:
    why = _not_text(manuscript)
    if why:
        raise ValueError(f"{manuscript.name}: {why}. Convert it to Markdown or text first (for example "
                         f"`pandoc -t gfm`).")
    docs, unreadable = [], {}
    for path in supplements:
        why = "file not found" if not path.is_file() else _not_text(path)
        if why:
            unreadable[path.name] = f"{why}; convert it to text to check quotes from it" \
                if why != "file not found" else why
        else:
            docs.append(Document.load(path))
    return Sources(manuscript=Document.load(manuscript), supplements=docs, unreadable=unreadable)


def check(data: Any, manuscript: Path, supplements: Optional[list[Path]] = None,
          adjudicated: bool = False) -> dict[str, Any]:
    """Check parsed findings JSON: a list of findings, or an object with findings, strengths and the referees'
    reports (`reports`, a list, in a merged file; `report`, one object, in a seat's own file)."""
    raw_reports: list[Any] = []
    if isinstance(data, list):
        raw_findings, raw_strengths = data, []
    elif isinstance(data, dict) and isinstance(data.get("findings", []), list) and \
            isinstance(data.get("strengths", []), list):
        raw_findings, raw_strengths = data.get("findings", []), data.get("strengths", [])
        if "reports" in data and "report" in data:
            raise ValueError("give either 'report' (a seat's own file) or 'reports' (a merged file), not both")
        if "reports" in data:
            if not isinstance(data["reports"], list):
                raise ValueError("'reports' must be a list of referee reports")
            raw_reports = data["reports"]
        elif "report" in data:
            raw_reports = [data["report"]]
    else:
        raise ValueError("expected a JSON list of findings, or an object with a 'findings' list")
    sources = _load_sources(manuscript, list(supplements or []))
    findings = [_check_finding(f, i, sources, adjudicated) for i, f in enumerate(raw_findings)]
    seen: dict[str, int] = {}
    for f in findings:
        seen[f["id"]] = seen.get(f["id"], 0) + 1
    for f in findings:
        if seen[f["id"]] > 1:
            f["problems"].append(f"Another finding has the same id, {f['id']}.")
            f["contract"] = "fail"
    strengths = [_check_strength(s, i, sources) for i, s in enumerate(raw_strengths)]
    groups = _group(findings, adjudicated)
    counts = {k: sum(f["contract"] == k for f in findings) for k in ("pass", "fail", "not_assessed")}
    panel = sorted({f["seat"] for f in findings if _nonempty_str(f.get("seat"))})
    reports = [_check_report(r, i, findings) for i, r in enumerate(raw_reports)]
    written: set[str] = set()
    for r in reports:
        if r["seat"] in written:
            r["problems"].append(f"Another report in this file is also by {r['seat']}.")
            r["contract"] = "fail"
        if r["seat"]:
            written.add(r["seat"])
    # Seats that wrote findings or strengths but no report. Only meaningful once any referee wrote one: a quick
    # pass, or a file from before referees gave recommendations, has none at all.
    writers = sorted(set(panel) | {s["seat"] for s in strengths if _nonempty_str(s.get("seat"))})
    missing = [s for s in writers if s not in written] if reports else []
    venues = sorted({rec["venue"] for r in reports for rec in r["recommendations"] if _nonempty_str(rec["venue"])})
    partial = {r["seat"]: [v for v in venues if v not in {rec["venue"] for rec in r["recommendations"]}]
               for r in reports if r["seat"]}
    return {
        "manuscript": manuscript.name,
        "supplements": [d.path.name for d in sources.supplements],
        "unreadable": dict(sorted(sources.unreadable.items())),
        "stage": "adjudicated" if adjudicated else "seat findings",
        "summary": {"findings": len(findings), **counts, "groups": len(groups), "seats": len(panel),
                    "strengths": len(strengths),
                    "strengths_not_anchored": sum(s["contract"] != "pass" for s in strengths),
                    "reports": len(reports), "reports_failed": sum(r["contract"] != "pass" for r in reports)},
        "panel": panel, "findings": findings, "groups": groups, "strengths": strengths,
        "reports": reports, "venues": venues, "reports_missing": missing,
        "venues_missing": {seat: vs for seat, vs in partial.items() if vs},
        "by_referee": _by_referee(findings, groups) if adjudicated else None,
    }


def identifier_url(identifier: Any) -> Optional[str]:
    """A link a reader can open for a DOI, PubMed ID, arXiv id or URL; None for an ISBN or anything else."""
    if not _nonempty_str(identifier):
        return None
    ident = identifier.strip()
    m = re.fullmatch(r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)", ident, re.IGNORECASE)
    if m:
        return f"https://doi.org/{m.group(1)}"
    m = re.fullmatch(r"(?:arXiv:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?)", ident, re.IGNORECASE)
    if m:
        return f"https://arxiv.org/abs/{m.group(1)}"
    m = re.fullmatch(r"PMID:?\s*(\d{1,9})|(\d{6,9})", ident, re.IGNORECASE)
    if m:
        return f"https://pubmed.ncbi.nlm.nih.gov/{m.group(1) or m.group(2)}/"
    if re.match(r"https?://\S+$", ident):
        return ident
    return None


def _plural(n: int, word: str, many: Optional[str] = None) -> str:
    return f"{n} {word if n == 1 else (many or word + 's')}"


NUMBER_WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _referees(seats: list[str], tail: str = "") -> str:
    """'one simulated referee (skeptic)': the description first, the seat names only in parentheses."""
    n = len(seats)
    count = NUMBER_WORDS[n] if n < len(NUMBER_WORDS) else str(n)
    names = _words_list(seats, "and") if seats else "not named"
    return f"{count} simulated referee{'' if n == 1 else 's'} ({names}{tail})"


def _raised_by(seat: Any) -> str:
    return f"a simulated referee ({seat})" if _nonempty_str(seat) else "no named referee"


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def _trim(text: Any, width: int = EXCERPT_WIDTH) -> str:
    text = _squash(str(text or "")).strip()
    return text if len(text) <= width else text[:width].rsplit(" ", 1)[0] + " [...]"


def _sentence(text: Any) -> str:
    text = _squash(str(text or "")).strip()
    return text if not text or text[-1] in ".?!\"'" else text + "."


SEVERITY_WORDS = {"blocker": "A blocking concern", "major": "A major concern", "optional": "An optional concern",
                  "uncertain": "An uncertain concern"}
ROUTE_WORDS = {"fixable-in-text": "can be fixed in the text", "author-required": "needs new work from the authors",
               "venue": "is a question for the chosen journal",
               "policy": "is an ethics, consent or privacy question for manuscript-policy-fit",
               "dropped": "was dropped"}
COST_WORDS = {"text": "a change of wording", "reanalysis": "a reanalysis of existing data",
              "new-data": "new data or experiments"}


def _passage_sentences(group: dict[str, Any], manuscript: str) -> list[str]:
    out = []
    for p in group["passages"]:
        where = f"line {p['line']}" if p["file"] == manuscript else f"{p['file']}, line {p['line']}"
        place = f"In {p['location']}, the" if _nonempty_str(p["location"]) else "The"
        text = "manuscript" if p["file"] == manuscript else f"file {p['file']}"
        out.append(f"{place} {text} reads \"{p['excerpt']}\" ({where}).")
    for a in group["absences"]:
        looked = a["looked_in"] if isinstance(a["looked_in"], list) else []
        out.append(f"Finding {a['finding']} reports something missing from {a['location'] or 'the paper'}; the "
                   f"referee looked in {_words_list(looked, 'and') if looked else 'places it did not list'}.")
    return out


def _verdict_sentence(group: dict[str, Any]) -> str:
    by_verdict: dict[str, list[str]] = {}
    for fid, verdict in group["verdict_by_finding"].items():
        by_verdict.setdefault(verdict, []).append(fid)
    if not by_verdict:
        return ""
    parts = [f"{v} for {_words_list(ids, 'and')}" for v, ids in by_verdict.items()]
    return f"The defence pass verdict is {_words_list(parts, 'and')}."


def _group_markdown(n: int, g: dict[str, Any], report: dict[str, Any]) -> list[str]:
    total = report["summary"]["seats"]
    head = (f"### {n}. {SEVERITY_WORDS.get(g['severity'], 'A concern')} raised by {g['n_seats']} of "
            f"{_plural(total, 'simulated referee')}")
    ids = "finding" if len(g["findings"]) == 1 else "findings"
    group_tail = f"; group {g['group']}"
    body = [f"It comes from {ids} {_words_list(g['findings'], 'and')}, written by "
            f"{_referees(g['seats'], group_tail)}."]
    body += _passage_sentences(g, report["manuscript"])
    body.append(f"Finding {g['concern_from']} states the concern as follows. {_sentence(g['concern'])}")
    verdict = _verdict_sentence(g)
    if verdict:
        body.append(verdict)
    if report["stage"] == "adjudicated" and g["stage"] not in ("answered", "dropped"):
        routes = [ROUTE_WORDS[r] for r in g["routes"] if r in ROUTE_WORDS and r != "dropped"]
        costs = [COST_WORDS[c] for c in g["costs"] if c in COST_WORDS]
        if routes:
            body.append(f"As proposed, it {_words_list(routes)}" + (f", at the cost of {_words_list(costs)}"
                                                                     if costs else "") + ".")
        if g["stage"] == "other-checks":
            body.append(f"It belongs to {_words_list(g['hand_to'])}; mention it there rather than as a referee "
                        f"concern.")
    return [head, "", *[f"{line}" for line in body], ""]


CHALLENGE_WORDS = {"refuted": "the defence refuted", "dropped": "adjudication dropped",
                   "downgraded": "adjudication narrowed or downgraded",
                   "not-yet-a-finding": "has not yet met the contract"}


def _recommendation_lines(report: dict[str, Any]) -> list[str]:
    """The referees' recommendations, and what adjudication did to the findings each one rests on."""
    if not report["reports"]:
        return ["This file holds no referee reports, so it has no recommendations (a quick pass writes none). Never "
                "write a recommendation for a referee who did not give one.", ""]
    lines = ["## The referees' recommendations", ""]
    for r in report["reports"]:
        if r["contract"] != "pass":
            continue
        for rec in r["recommendations"]:
            form = f" (on the journal's form: \"{rec['form_wording']}\")" if _nonempty_str(rec["form_wording"]) else ""
            rests = (f" It rests on {_words_list(rec['rests_on'], 'and')}." if rec["rests_on"] else "")
            line = (f"- {_cap(_raised_by(r['seat']))}, for {rec['venue']}: "
                    f"{RECOMMENDATION_WORDS[rec['recommendation']]}{form}. {_sentence(rec['reason'])}{rests}")
            by_kind: dict[str, list[str]] = {}
            for fid, why in rec["challenged"].items():
                by_kind.setdefault(why, []).append(fid)
            if by_kind:
                parts = [f"{CHALLENGE_WORDS[k]} {_words_list(ids, 'and')}" for k, ids in by_kind.items()]
                line += (f" Of those, {_words_list(parts, 'and')}: say so in one sentence after this recommendation in "
                         f"the referee's report, and leave the recommendation as the referee gave it.")
            lines.append(line)
    lines.append("")
    if report["reports_missing"]:
        lines += [f"These simulated referees wrote findings but no report, so they have no recommendation: "
                  f"{_words_list(report['reports_missing'], 'and')}. Ask them for it, or say in the result that "
                  f"they gave none; never write one for them.", ""]
    for seat, vs in report["venues_missing"].items():
        lines += [f"The simulated referee ({seat}) gave no recommendation for {_words_list(vs, 'and')}, which "
                  f"another referee was asked about.", ""]
    bad = [r for r in report["reports"] if r["contract"] != "pass"]
    if bad:
        lines += ["### Reports that do not meet the contract", ""]
        for r in bad:
            who = f"by {_raised_by(r['seat'])}" if r["seat"] else f"number {r['index']}"
            lines.append(f"- The report {who}. " + " ".join(_sentence(p) for p in r["problems"]))
        lines.append("")
    return lines


SECTION_WORDS = (("major", "major concerns"), ("minor", "minor concerns"), ("questions", "questions for the authors"))


def _by_referee_lines(report: dict[str, Any]) -> list[str]:
    if not report["by_referee"]:
        return []
    number = {fid: n for n, g in enumerate(report["groups"], 1) for fid in g["findings"]}
    lines = ["## What each referee's report contains", "",
             "Each referee's confirmed and narrowed findings, sorted into the sections of its report. The number "
             "after each finding is its concern above, where the passage and the verdict are.", ""]
    for seat, sections in sorted(report["by_referee"].items()):
        parts = []
        for key, words in SECTION_WORDS:
            ids = sections[key]
            listed = _words_list([f"{fid} (concern {number[fid]})" for fid in ids], "and") if ids else "none"
            parts.append(f"{words}: {listed}")
        lines.append(f"- {_cap(_raised_by(seat))}: " + "; ".join(parts) + ".")
    return lines + [""]


def to_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    adjudicated = report["stage"] == "adjudicated"
    lines = [f"# Finding check: {report['manuscript']}", ""]
    intro = (f"This check read {_plural(s['findings'], 'finding')} from {_plural(s['seats'], 'simulated referee')}, "
             f"{'after' if adjudicated else 'before'} the defence pass, in which a separate reader checks each "
             f"concern against the paper. ")
    if s["findings"]:
        go_on = "the report" if adjudicated else "the defence pass"
        intro += (f"{s['pass']} of them quote the manuscript word for word and give every required field, so "
                  f"they go on to {go_on}. ")
    not_yet = s["fail"] + s["not_assessed"]
    if not_yet:
        intro += (f"{not_yet} {'is' if not_yet == 1 else 'are'} not yet {'a finding' if not_yet == 1 else 'findings'}, "
                  f"because {s['fail']} failed the check and {s['not_assessed']} could not be checked. ")
    if s["pass"]:
        intro += (f"The {_plural(s['pass'], 'finding')} that passed fall into {_plural(s['groups'], 'group')} that "
                  f"share text, a group label or a near-identical concern. ")
    if s["strengths"]:
        intro += (f"Of {_plural(s['strengths'], 'strength')}, {s['strengths_not_anchored']} "
                  f"{'lacks' if s['strengths_not_anchored'] == 1 else 'lack'} a verified quote. ")
    if report["supplements"]:
        intro += f"Besides the manuscript, the check searched {_words_list(report['supplements'], 'and')}. "
    for name, why in report.get("unreadable", {}).items():
        intro += f"It could not read {name} ({why}), so quotes from it were not checked. "
    lines += [intro.strip(), "",
              "A group's count says how many simulated referees raised the concern. Agreement between referees "
              "is not evidence that the concern is right.", ""]
    lines += _recommendation_lines(report)
    if adjudicated and report["groups"]:
        lines += ["The groups are sorted by when the authors can act on them, then by severity. When writing the "
                  "report, put work that another fix depends on first, and merge groups that share a root cause "
                  "by giving their findings the same group label and running the check again.", ""]
        n = 0
        for key, title in STAGES:
            members = [g for g in report["groups"] if g["stage"] == key]
            if not members:
                continue
            lines += [f"## {title}", ""]
            for g in members:
                n += 1
                lines += _group_markdown(n, g, report)
    elif report["groups"]:
        lines += ["## Groups", ""]
        for n, g in enumerate(report["groups"], 1):
            lines += _group_markdown(n, g, report)
    lines += _by_referee_lines(report)
    bad = [f for f in report["findings"] if f["contract"] != "pass"]
    if bad:
        lines += ["## Not yet findings", "",
                  "Each of these needs a verbatim quote, the missing fields or a checked identifier before it can "
                  "go further. None has been dropped.", ""]
        for f in bad:
            quoted = (f" It quotes \"{_trim(f.get('quote_text'))}\""
                      + (f" from {f['location']}." if _nonempty_str(f.get("location")) else ".")
                      if _nonempty_str(f.get("quote_text")) else "")
            who = f"raised by {_raised_by(f.get('seat'))}"
            lines.append(f"- **{f['id']}**, {who}, {CONTRACT_WORDS[f['contract']]}.{quoted} "
                         + " ".join(_sentence(p) for p in f["problems"]))
        lines.append("")
    loose = [st for st in report["strengths"] if st["contract"] != "pass"]
    if loose:
        lines += ["## Strengths without a verified quote", ""]
        for st in loose:
            where = f" in {st['location']}" if _nonempty_str(st.get("location")) else ""
            who = f", noted by {_raised_by(st['seat'])}{where}," if _nonempty_str(st.get("seat")) else where
            quoted = f" quotes \"{_trim(st.get('quote_text'))}\"." if _nonempty_str(st.get("quote_text")) else \
                " has no quote."
            lines.append(f"- Strength {st['index']}{who}{quoted} " + " ".join(_sentence(p) for p in st["problems"]))
        lines.append("")
    warned = [f for f in report["findings"] if f["warnings"]]
    if warned:
        lines += ["## Warnings for the adjudicator", "",
                  "These do not stop a finding; the adjudicator decides whether the concern is fair as written.", ""]
        for f in warned:
            lines.append(f"- The concern of **{f['id']}**, raised by {_raised_by(f['seat'])}, reads "
                         f"\"{_trim(f['concern'])}\" " + " ".join(_sentence(w) for w in f["warnings"]))
        lines.append("")
    cited = [(f["id"], e) for f in report["findings"] for e in f["prior_work"] if isinstance(e, dict)]
    if cited:
        lines += ["## Prior work named in findings", ""]
        for fid, e in cited:
            ident = e.get("identifier")
            url = identifier_url(ident)
            named = f"{e.get('citation') or 'a work with no citation'}"
            named += f", {url}" if url else (f" ({ident})" if _nonempty_str(ident) else ", with no identifier")
            if e.get("status") == "verified":
                state = "Its identifier resolved to this work" + (
                    f" (checked by {e['checked_by']})." if _nonempty_str(e.get("checked_by")) else ".")
            elif e.get("status") == "unverified":
                state = ("Its identity is not confirmed, because the identifier could not be resolved."
                         if _nonempty_str(ident) else "Its identity is not confirmed, because it has no identifier.")
            else:
                state = "It has no status yet; resolve the identifier and mark it verified or unverified."
            lines.append(f"- **{fid}** names {named}. {state}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


@app.command()
def main(
    findings: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Findings JSON (schema: references/finding-schema.md)")],
    manuscript: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Manuscript source: Markdown, LaTeX or text")],
    supplement: Annotated[Optional[list[Path]], typer.Option("--supplement", "-s", help="Another file findings may quote (supplementary text, an \\input file); repeatable")] = None,
    adjudicated: Annotated[bool, typer.Option(help="Require verdict fields (after the adjudication pass)")] = False,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the check as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the Markdown report here (default: stdout)")] = None,
) -> None:
    """Check findings against the contract and the manuscript; list failures as not yet findings."""
    try:
        data = json.loads(findings.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        typer.echo(f"{findings.name}: malformed JSON: {exc}", err=True)
        raise typer.Exit(code=2)
    try:
        report = check(data, manuscript, supplement, adjudicated)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=2)
    md = to_markdown(report)
    if md_out:
        md_out.write_text(md, encoding="utf-8")
    else:
        typer.echo(md)
    if json_out:
        json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    s = report["summary"]
    ok = s["pass"] == s["findings"] and s["strengths_not_anchored"] == 0 and s["reports_failed"] == 0
    raise typer.Exit(code=0 if ok else 1)


if __name__ == "__main__":
    app()
