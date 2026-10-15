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

TEXT_SUFFIXES = {".md", ".markdown", ".qmd", ".rmd", ".tex", ".txt", ".text", ".rst", ".csv", ".tsv"}

SEATS = ("claims-novelty", "evidence-statistics", "reproducibility", "champion", "skeptic",
         "desk-editor", "software-methods", "genomics", "human-data-clinical", "ai-systems")
SEVERITIES = ("blocker", "major", "optional", "uncertain")
CONSEQUENCES = ("validity", "support", "scope", "reproducibility", "interpretation")
ROUTES = ("fixable-in-text", "author-required", "venue", "policy", "dropped")
TRIAGE = ("substance", "misread-risk", "polish")
VERDICTS = ("confirmed", "refuted", "downgraded")
KINDS = ("present", "absence")
COSTS = ("text", "reanalysis", "new-data", "unknown")
HAND_TO = ("manuscript-prose-edit", "manuscript-reference-check", "manuscript-reporting-check",
           "manuscript-integrity-check", "manuscript-policy-fit", "manuscript-journal-adapt",
           "manuscript-journal-select")
PRIOR_STATUS = ("verified", "unverified")
REQUIRED = ("id", "seat", "location", "concern", "claim", "consequence", "severity", "change_my_mind", "route")

MIN_QUOTE_WORDS = 3  # shorter quotes must reach MIN_QUOTE_CHARS to anchor a finding
MIN_QUOTE_CHARS = 12
MAX_ELISION_GAP = 200  # tokens allowed between the fragments of an elided quote

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

    @classmethod
    def load(cls, path: Path) -> "Document":
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        mode = "latex" if path.suffix.lower() == ".tex" else "markdown"
        doc = cls(path=path, text=text, mode=mode)
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

    def longest_opening(self, quote: str) -> Optional[tuple[int, int, int]]:
        """(matched words, total words, line) for the longest opening run of the quote found anywhere."""
        first = _ELISION.split(quote)[0]
        for view, prep in (("light", _light), ("stripped", lambda q: _stripped(_light(q)))):
            toks = [t for t, _, _ in _tokens(prep(first))]
            words = sum(_is_word(t) for t in toks)
            for k in range(len(toks) - 1, 0, -1):
                if sum(_is_word(t) for t in toks[:k]) < MIN_QUOTE_WORDS:
                    break
                occ = self._occurrences(view, toks[:k])
                if occ:
                    return (sum(_is_word(t) for t in toks[:k]), words, self.line(self.views[view][occ[0]][1]))
        return None


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
                         "rests on state-of-the-art standing: keep it only if the paper claims superiority"),
    "new-work": (re.compile(r"\b(?:should|must|need(?:s)? to|ought to)\s+(?:also\s+)?"
                            r"(?:run|perform|add|include|conduct|test|repeat|collect|validate)\b", re.IGNORECASE),
                 "asks for new work: confirm the claim needs it, and offer narrowing the claim as the alternative"),
    "simplicity": (re.compile(r"\b(?:too simple|trivial|straightforward extension)\b", re.IGNORECASE),
                   "objects to simplicity: simplicity is not a defect unless a claim depends on it"),
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
                return [], f"source {wanted} could not be read ({reason})"
        return [], f"source {wanted} was not supplied (pass it with --supplement)"


def _check_quote(quote: str, source: Optional[str], sources: Sources, what: str) -> dict[str, Any]:
    """Locate one quote. status: verified | not_found | not_assessed."""
    words, chars = _quote_size(quote)
    if words < MIN_QUOTE_WORDS and chars < MIN_QUOTE_CHARS:
        return {"status": "not_found", "problem": f"{what} is too short to locate a finding "
                f"({words} words); quote at least {MIN_QUOTE_WORDS} words or {MIN_QUOTE_CHARS} characters"}
    docs, reason = sources.candidates(source)
    if reason:
        return {"status": "not_assessed", "problem": f"{what} not checked: {reason}"}
    for doc in docs:
        m = doc.locate(quote)
        if m:
            out = {"status": "verified", "file": doc.path.name, "line": doc.line(m.start),
                   "end_line": doc.line(max(m.start, m.end - 1)), "start": m.start, "end": m.end,
                   "view": m.view, "occurrences": m.occurrences}
            return out
    near = [(doc, doc.longest_opening(quote)) for doc in docs]
    near = [(doc, n) for doc, n in near if n]
    hint = ""
    if near:
        doc, (k, total, line) = max(near, key=lambda x: x[1][0])
        hint = f"; its first {k} of {total} words occur at {doc.path.name}:{line}, then the text differs"
    return {"status": "not_found", "problem": f"{what} not found verbatim in "
            f"{', '.join(d.path.name for d in docs)}{hint}"}


def _enum(finding: dict[str, Any], key: str, allowed: tuple[str, ...], problems: list[str]) -> None:
    value = finding.get(key)
    if value is not None and value not in allowed:
        problems.append(f"{key} '{value}' is not one of: {', '.join(allowed)}")


def _check_finding(raw: Any, position: int, sources: Sources, adjudicated: bool) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"id": f"#{position + 1}", "seat": None, "contract": "fail",
                "problems": ["not a JSON object"], "warnings": []}
    f = raw
    problems: list[str] = []
    warnings: list[str] = []
    fid = f.get("id") if _nonempty_str(f.get("id")) else f"#{position + 1}"

    for key in REQUIRED:
        if not _nonempty_str(f.get(key)):
            problems.append(f"missing or empty field: {key}")
    seat = f.get("seat")
    if _nonempty_str(seat) and seat not in SEATS and not re.fullmatch(r"custom:[\w-]+", seat):
        problems.append(f"seat '{seat}' is not one of: {', '.join(SEATS)}, or custom:<name>")
    for key, allowed in (("severity", SEVERITIES), ("consequence", CONSEQUENCES), ("route", ROUTES),
                         ("triage", TRIAGE), ("verdict", VERDICTS), ("kind", KINDS), ("cost", COSTS),
                         ("hand_to", HAND_TO)):
        _enum(f, key, allowed, problems)

    kind = f.get("kind", "present")
    quote_result: Optional[dict[str, Any]] = None
    if kind == "absence":
        looked = f.get("looked_in")
        if not (isinstance(looked, list) and looked and all(_nonempty_str(x) for x in looked)):
            problems.append("absence finding without looked_in: list where the seat looked for the missing item")
    elif not _nonempty_str(f.get("quote")):
        problems.append("no verbatim quote: quote the manuscript, or make it an absence finding with looked_in")
    if _nonempty_str(f.get("quote")):
        quote_result = _check_quote(f["quote"], f.get("source"), sources, "quote")
        if quote_result["status"] == "not_found":
            problems.append(quote_result["problem"])
        elif quote_result["status"] == "verified" and quote_result["occurrences"] > 1:
            warnings.append(f"quote occurs {quote_result['occurrences']} times; the location field decides which "
                            f"(first at line {quote_result['line']})")

    defence_result: Optional[dict[str, Any]] = None
    if _nonempty_str(f.get("defence_quote")):
        defence_result = _check_quote(f["defence_quote"], f.get("defence_source"), sources, "defence_quote")
        if defence_result["status"] == "not_found":
            problems.append(defence_result["problem"])

    concern = f.get("concern") if isinstance(f.get("concern"), str) else ""
    prior = f.get("prior_work")
    needs_prior = bool(_PRIOR_WORK_CUE.search(concern)) or f.get("external_claim") is True
    if prior is not None:
        if not isinstance(prior, list):
            problems.append("prior_work must be a list")
            prior = []
        for i, entry in enumerate(prior, 1):
            if not isinstance(entry, dict) or not _nonempty_str(entry.get("citation")):
                problems.append(f"prior_work[{i}] needs a citation")
                continue
            status, ident = entry.get("status"), entry.get("identifier")
            if status not in PRIOR_STATUS:
                problems.append(f"prior_work[{i}] status must be verified or unverified")
            if ident is not None and not (_nonempty_str(ident) and _IDENTIFIER.match(ident.strip())):
                problems.append(f"prior_work[{i}] identifier '{ident}' is not a DOI, PMID, arXiv id, ISBN or URL")
            if status == "verified" and not _nonempty_str(ident):
                problems.append(f"prior_work[{i}] is marked verified without an identifier")
    if needs_prior:
        usable = [e for e in (prior or []) if isinstance(e, dict) and _nonempty_str(e.get("citation")) and
                  (e.get("status") == "unverified" or (e.get("status") == "verified" and _nonempty_str(e.get("identifier"))))]
        if f.get("external_claim") is False:
            warnings.append("the concern reads like a prior-work claim but is marked external_claim: false")
        elif not usable:
            problems.append("asserts external prior work without a named work carrying an identifier "
                            "or the status unverified (prior_work)")

    for name, (rx, message) in _LINTS.items():
        if rx.search(concern):
            warnings.append(f"fairness filter ({name}): {message}")

    if f.get("route") == "dropped" and not _nonempty_str(f.get("drop_reason")):
        problems.append("route dropped without drop_reason")
    verdict = f.get("verdict")
    if adjudicated and verdict is None:
        problems.append("adjudicated findings need a verdict: confirmed, refuted or downgraded")
    if verdict in ("confirmed", "downgraded") and f.get("triage") is None:
        problems.append(f"a {verdict} finding needs triage: substance, misread-risk or polish")
    if verdict in VERDICTS and not _nonempty_str(f.get("verdict_evidence")):
        problems.append(f"a {verdict} finding needs verdict_evidence: the text, recomputation or record that "
                        f"settles it")
    if verdict == "refuted" and not _nonempty_str(f.get("defence_quote")):
        problems.append("a refuted finding needs defence_quote: the text that answers it")

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
            "warnings": warnings, "quote": quote_result, "defence": defence_result}


def _check_strength(raw: Any, position: int, sources: Sources) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"index": position + 1, "contract": "fail", "problems": ["not a JSON object"]}
    problems = [f"missing or empty field: {k}" for k in ("seat", "location", "quote", "note")
                if not _nonempty_str(raw.get(k))]
    result = None
    if _nonempty_str(raw.get("quote")):
        result = _check_quote(raw["quote"], raw.get("source"), sources, "quote")
        if result["status"] != "verified":
            problems.append(result["problem"])
    contract = "pass" if not problems else ("not_assessed" if result and result["status"] == "not_assessed"
                                            and len(problems) == 1 else "fail")
    return {"index": position + 1, "seat": raw.get("seat"), "location": raw.get("location"),
            "note": raw.get("note"), "contract": contract, "problems": problems, "quote": result}


def _group(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Union findings that share text, a group label, a near-identical concern, or (absence) a location."""
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

    def first_offset(fs: list[dict[str, Any]]) -> int:
        offsets = [f["quote"]["start"] for f in fs if f["quote"] and f["quote"]["status"] == "verified"]
        return min(offsets) if offsets else 10**12

    groups = []
    for fs in clusters.values():
        fs.sort(key=lambda f: rank.get(f["severity"], 99))
        seats = sorted({f["seat"] for f in fs})
        where = sorted({f"{f['quote']['file']}:{f['quote']['line']}" for f in fs
                        if f["quote"] and f["quote"]["status"] == "verified"})
        groups.append({
            "findings": [f["id"] for f in fs], "seats": seats, "n_seats": len(seats),
            "severity": fs[0]["severity"], "where": where,
            "locations": sorted({f["location"] for f in fs if f["location"]}),
            "verdicts": sorted({f["verdict"] for f in fs if f["verdict"]}),
            "routes": sorted({f["route"] for f in fs if f["route"]}),
            "concern": fs[0]["concern"], "_order": (rank.get(fs[0]["severity"], 99), first_offset(fs)),
        })
    groups.sort(key=lambda g: g["_order"])
    for n, g in enumerate(groups, 1):
        g["group"] = f"G{n}"
        del g["_order"]
    return groups


def _load_sources(manuscript: Path, supplements: list[Path]) -> Sources:
    if manuscript.suffix.lower() not in TEXT_SUFFIXES:
        raise ValueError(f"{manuscript.name}: unsupported manuscript type '{manuscript.suffix}'. Convert it to "
                         f"Markdown or text first (for example `pandoc -t gfm`).")
    docs, unreadable = [], {}
    for path in supplements:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            unreadable[path.name] = f"unsupported type '{path.suffix}'; convert it to text to check its quotes"
        elif not path.is_file():
            unreadable[path.name] = "file not found"
        else:
            docs.append(Document.load(path))
    return Sources(manuscript=Document.load(manuscript), supplements=docs, unreadable=unreadable)


def check(data: Any, manuscript: Path, supplements: Optional[list[Path]] = None,
          adjudicated: bool = False) -> dict[str, Any]:
    """Check parsed findings JSON (a list of findings, or an object with findings and strengths)."""
    if isinstance(data, list):
        raw_findings, raw_strengths = data, []
    elif isinstance(data, dict) and isinstance(data.get("findings", []), list) and \
            isinstance(data.get("strengths", []), list):
        raw_findings, raw_strengths = data.get("findings", []), data.get("strengths", [])
    else:
        raise ValueError("expected a JSON list of findings, or an object with a 'findings' list")
    sources = _load_sources(manuscript, list(supplements or []))
    findings = [_check_finding(f, i, sources, adjudicated) for i, f in enumerate(raw_findings)]
    seen: dict[str, int] = {}
    for f in findings:
        seen[f["id"]] = seen.get(f["id"], 0) + 1
    for f in findings:
        if seen[f["id"]] > 1:
            f["problems"].append(f"duplicate id {f['id']}")
            f["contract"] = "fail"
    strengths = [_check_strength(s, i, sources) for i, s in enumerate(raw_strengths)]
    groups = _group(findings)
    counts = {k: sum(f["contract"] == k for f in findings) for k in ("pass", "fail", "not_assessed")}
    return {
        "manuscript": manuscript.name,
        "supplements": [d.path.name for d in sources.supplements] + sorted(sources.unreadable),
        "stage": "adjudicated" if adjudicated else "seat findings",
        "summary": {"findings": len(findings), **counts, "groups": len(groups),
                    "strengths": len(strengths),
                    "strengths_not_anchored": sum(s["contract"] != "pass" for s in strengths)},
        "findings": findings, "groups": groups, "strengths": strengths,
    }


def to_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [f"# Finding check: {report['manuscript']}", ""]
    if report["supplements"]:
        lines.append(f"Supplementary sources: {', '.join(report['supplements'])}.")
    lines += [f"Stage: {report['stage']}. Findings: {s['findings']}. Meeting the contract: {s['pass']}. "
              f"Not yet findings: {s['fail'] + s['not_assessed']} ({s['fail']} failed, {s['not_assessed']} not "
              f"assessed). Groups: {s['groups']}.",
              "Seat counts say how many seats raised a concern; agreement between seats is not confirmation.", ""]
    if report["groups"]:
        lines += ["## Groups", "", "| Group | Seats | Findings | Where | Severity | Verdicts | Concern |",
                  "|---|---|---|---|---|---|---|"]
        for g in report["groups"]:
            where = ", ".join(g["where"]) or "; ".join(g["locations"]) or "-"
            concern = " ".join(g["concern"].split()).replace("|", "\\|")
            lines.append(f"| {g['group']} | {g['n_seats']}: {', '.join(g['seats'])} | {', '.join(g['findings'])} "
                         f"| {where} | {g['severity']} | {', '.join(g['verdicts']) or '-'} | {concern} |")
        lines.append("")
    bad = [f for f in report["findings"] if f["contract"] != "pass"]
    if bad:
        lines += ["## Not yet findings", "",
                  "Each needs a verbatim quote, the missing fields or a checked identifier before adjudication; "
                  "none has been dropped.", ""]
        for f in bad:
            lines.append(f"- **{f['id']}** ({f['seat'] or 'no seat'}, {f['contract']}): " + "; ".join(f["problems"]))
        lines.append("")
    loose = [s for s in report["strengths"] if s["contract"] != "pass"]
    if loose:
        lines += ["## Strengths without a verified quote", ""]
        lines += [f"- strength {s['index']} ({s.get('seat') or 'no seat'}): " + "; ".join(s["problems"]) for s in loose]
        lines.append("")
    warned = [f for f in report["findings"] if f["warnings"]]
    if warned:
        lines += ["## Warnings", ""]
        lines += [f"- {f['id']}: " + "; ".join(f["warnings"]) for f in warned]
        lines.append("")
    cited = [(f["id"], e) for f in report["findings"] for e in f["prior_work"] if isinstance(e, dict)]
    if cited:
        lines += ["## Prior work named in findings", ""]
        for fid, e in cited:
            ident = e.get("identifier") or "no identifier"
            lines.append(f"- {fid}: {e.get('citation')} ({ident}): {e.get('status')}")
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
    raise typer.Exit(code=0 if s["pass"] == s["findings"] and s["strengths_not_anchored"] == 0 else 1)


if __name__ == "__main__":
    app()
