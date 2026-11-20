# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "httpx>=0.27"]
# ///
"""Draft a cover letter for one venue, or a presubmission inquiry to its editor, and trace every claim it makes to
the manuscript.

    uv run --script letter.py needs VENUE [--format md|json]                 # what the venue's facts ask of the letter
    uv run --script letter.py write LETTER.yaml --paper PAPER.md --run RUN    # or --out DIR
    uv run --script letter.py write LETTER.yaml --paper PAPER.md --run RUN --verify-related   # check the DOI too

`needs` reads the venue catalogue (venues.py: the shipped venues.yaml with the user's own laid over it) and lists
what belongs in that venue's cover letter: every declaration its facts place there (the AI-use statement when
`disclosure_places` names the cover letter; competing interests, a preprint, data availability, funding or suggested
and excluded reviewers when a rule of its pages says so), the other points its pages ask the letter to make, the
journal's own words on its scope and on each article type (`scope` in the catalogue) with the page and the date it
was read, and whether it answers presubmission inquiries.

`write` takes the letter's content from LETTER.yaml (references/letters.md gives the fields) and writes, beside the
stage's report (RUN/manuscript-journal-adapt/, or --out DIR):

- `cover-letter.VENUE.md` or `presubmission-inquiry.VENUE.md`: the letter, ready to edit and send once its gaps are
  filled. The request comes first (G6): what is submitted, as which article type, or the question asked.
- `....claims.md`: not for sending. Each claim the letter makes about the paper beside the manuscript's sentences it
  rests on, with section and line; the venue's words it quotes, with their page and the date they were read; each
  declaration with its source; the points the venue asks the letter to make; the gaps; and the checks.
- `....json`: the same, for the dashboard or a later check.

Nothing is invented. A sentence about the paper must name the manuscript passages it rests on (`from`: at least three
words in a row, copied) or is matched to its closest sentence of the Abstract or Results; one that matches none is
untraced. The claim guard (manuscript-prose-edit/scripts/guard.py) then compares it with those sentences: a claim
raised on the causal or evidential ladder, a generality or novelty word added, a scope, limitation, null-result or
evidence-status marker dropped, or a number, citation or identifier the sentences lack is a problem. A sentence that
rests on the Introduction tells the editor background they know (G6). A declaration rests on the manuscript's own
passages or on what the authors said (`given_by`); a name or number it adds to its passages is a problem, so no
funder, grant or person is made up. Suggested reviewers come only from the authors. A related paper is named only
when `verified` says how its identity was checked (and, with --verify-related, Crossref confirms the journal and a
year within the last three). What is missing stays in the letter as a marked gap, `[TO FILL: ...]`, for the authors.

The letter then passes the smell check for letters: the templated openings and closings of G5, chat leftovers (G1)
and the inflation, implication, promotional and priority patterns (A1, A3, A4, A5) of
manuscript-deslop/references/smell-patterns.yaml, each a problem at its first use, quoted words aside; a closing of
more than one sentence; a cover letter longer than a page (450 words before the signature) or an inquiry longer than
300 words besides the abstract. An inquiry to a venue whose facts say it does not answer them is a problem too.

Exit codes: 0 written and every check passed (gaps may remain: the claims file lists them); 1 written with problems;
2 a bad letter file, an unknown venue or a manuscript that cannot be read.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter
from datetime import date
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Callable, Optional

import typer
import yaml

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The venue catalogue, the claim guard and the smell patterns: the letter is checked by the same code as an edit.
venues = _load("letter_venues", HERE / "venues.py")
guard = _load("letter_guard", SKILLS / "manuscript-prose-edit" / "scripts" / "guard.py")
style = _load("letter_style", SKILLS / "manuscript-deslop" / "scripts" / "style_profile.py")

app = typer.Typer(add_completion=False, no_args_is_help=True)

STAGE = "manuscript-journal-adapt"
GAP = "[TO FILL: {}]"
GAP_RX = re.compile(r"\[TO FILL(?:, optional)?: [^\]]*\]")
COVER_WORDS = 450   # one page, before the signature
INQUIRY_WORDS = 300  # besides the abstract
SHOWS = {"cover": (2, 3), "inquiry": (1, 3)}
LETTER_SMELLS = ("G5", "G1", "A1", "A3", "A4", "A5")
SHOWN_FROM = re.compile(r"^(?:abstract|summary|results?\b.*|findings)$", re.IGNORECASE)
BACKGROUND = re.compile(r"^(?:introduction|background)\b", re.IGNORECASE)
AUTO_TRACE = 0.3  # word overlap (Dice) a sentence without `from` needs with its closest Abstract or Results sentence
RELATED_YEARS = 3
COVER_LETTER = re.compile(r"cover[- ]letters?", re.IGNORECASE)
NOT_ANSWERED = re.compile(r"(?:pre-?submission|presubmission) (?:enquiries|inquiries) (?:are|will) not (?:be )?answered|"
                          r"(?:does|do) not (?:answer|accept|consider|respond to) (?:any )?(?:pre-?submission |"
                          r"presubmission )?(?:enquiries|inquiries)", re.IGNORECASE)

# Declarations in the order the letter gives them, and the words that put a venue's cover-letter rule under each.
DECLARATIONS: dict[str, tuple[str, re.Pattern[str]]] = {
    "ai_use": ("the use of AI tools", re.compile(r"\bAI\b|artificial intelligence|large language|\bLLMs?\b|generative",
                                                 re.IGNORECASE)),
    "competing_interests": ("competing interests", re.compile(
        r"competing|conflicts? of interest|declaration of interests", re.IGNORECASE)),
    "preprint": ("the preprint", re.compile(r"preprint", re.IGNORECASE)),
    "data_availability": ("data availability", re.compile(
        r"data availability|availability of (?:the )?data|data (?:are|is) available", re.IGNORECASE)),
    "funding": ("funding", re.compile(r"\bfunding\b|\bfunders?\b", re.IGNORECASE)),
    "reviewers": ("suggested or excluded reviewers", re.compile(r"\b(?:reviewers?|referees?)\b", re.IGNORECASE)),
}
OPENING_WORDS = {"we", "the", "this", "our", "it", "in", "a", "an", "all", "no", "none", "both", "each", "they",
                 "these", "there", "its"}


class Format(str, Enum):
    md = "md"
    json = "json"


class LetterError(ValueError):
    """A letter file that cannot be used as it is."""


# ------------------------------------------------------------------------------------------------ the venue

def _fact_read(v: dict[str, Any], field: str) -> tuple[Optional[str], Optional[str]]:
    """The page a fact is on and the date it was read (provenance, else the entry's guidelines page)."""
    p = (v.get("provenance") or {}).get(field) or {}
    page = p.get("source")
    if not page and field in venues.AI_FIELDS | {"disclosure_places", "disclosure_fields"}:
        page = venues.policy_page(v)
    when = p.get("checked")
    return page or v.get("url"), str(when) if when else None


def _quote_text(quote: Any) -> str:
    if isinstance(quote, list):
        return " … ".join(str(q).strip() for q in quote if str(q).strip())
    return str(quote or "").strip()


def _strings(value: Any, path: str) -> list[tuple[str, str]]:
    """Every string of a fact, with where it sits ("fit_note", "other_desk_rules[1]")."""
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        return [x for n, item in enumerate(value) for x in _strings(item, f"{path}[{n}]")]
    if isinstance(value, dict):
        return [x for k, item in value.items() if k not in ("source", "checked") for x in _strings(item, f"{path}.{k}")]
    return []


def letter_needs(v: dict[str, Any]) -> dict[str, Any]:
    """What a venue's recorded facts ask of a cover letter and of a presubmission inquiry."""
    declarations: dict[str, dict[str, Any]] = {}
    points: list[dict[str, Any]] = []
    places = v.get("disclosure_places") or []
    if any(COVER_LETTER.search(str(p)) for p in places):
        page, when = _fact_read(v, "disclosure_places")
        declarations["ai_use"] = {"label": DECLARATIONS["ai_use"][0],
                                  "rule": "AI use is disclosed in " + ", ".join(map(str, places)),
                                  "fields": list(v.get("disclosure_fields") or []), "source": page, "checked": when}
    for n, rule in enumerate(v.get("submission_rules") or []):
        text = " ".join([str(rule.get("rule") or ""), _quote_text(rule.get("quote"))])
        if not COVER_LETTER.search(text):
            continue
        page, when = rule.get("source"), rule.get("checked")
        if not page or not when:
            p2, w2 = _fact_read(v, "submission_rules")
            page, when = page or p2, when or w2
        point = {"field": f"submission_rules[{n}]", "rule": str(rule.get("rule") or ""),
                 "quote": _quote_text(rule.get("quote")), "source": page, "checked": str(when) if when else None}
        points.append(point)
        for key, (label, rx) in DECLARATIONS.items():
            if rx.search(text) and key not in declarations:
                declarations[key] = {"label": label, "rule": point["rule"], "quote": point["quote"],
                                     "source": page, "checked": point["checked"]}
    for field in ("other_desk_rules", "fit_note", "extra_burden", "required_sections", "editorial_profile"):
        for where, text in _strings(v.get(field), field):
            if not COVER_LETTER.search(text):
                continue
            page, when = _fact_read(v, field)
            points.append({"field": where, "rule": text, "quote": "", "source": page, "checked": when})
            for key, (label, rx) in DECLARATIONS.items():
                if rx.search(text) and key not in declarations:
                    declarations[key] = {"label": label, "rule": text, "quote": "", "source": page, "checked": when}
    scope = v.get("scope") if isinstance(v.get("scope"), dict) else {}
    page, when = _fact_read(v, "scope")
    page = scope.get("source") or page
    fit = {"scope": _quote_text(scope.get("quote")) or None,
           "article_types": {str(k): _quote_text(q) for k, q in (scope.get("article_types") or {}).items()},
           "source": page, "checked": str(scope.get("checked") or when) if (scope.get("checked") or when) else None}
    answered = scope.get("presubmission")
    said = _quote_text(scope.get("presubmission_quote"))
    if answered is None:
        for where, text in _strings({k: v.get(k) for k in ("fit_note", "editorial_profile", "submission_rules",
                                                            "other_desk_rules")}, ""):
            if NOT_ANSWERED.search(text):
                answered, said = "not_answered", text
                break
    return {"venue": v.get("key"), "name": v.get("name") or v.get("key"), "url": v.get("url"),
            "declarations": declarations, "points": points, "fit": fit,
            "presubmission": {"answered": answered, "quote": said or None},
            "researched": v.get("submission_rules") is not None or bool(declarations) or bool(scope)}


def _venue(key: str) -> dict[str, Any]:
    _, catalogue = venues.load_venues()
    if key not in catalogue:
        raise LetterError(f"unknown venue {key!r}; `venues.py rank` lists the keys")
    v = catalogue[key]
    if v.get("kind") in ("publisher", "preprint"):
        raise LetterError(f"{key!r} is a {v['kind']} entry, not a journal")
    return v


def needs_markdown(n: dict[str, Any]) -> str:
    lines = [f"# What {n['name']} asks of a cover letter", ""]
    if not n["researched"]:
        lines += [f"The catalogue records no cover-letter rule for {n['name']}: read {n['url'] or 'its author guide'} "
                  "for what the letter must say, and record each rule (`submission_rules`) and the journal's words on "
                  "its scope and article types (`scope`) with venues.py save.", ""]
    lines += ["## Declarations the letter must hold", ""]
    if n["declarations"]:
        for key, d in n["declarations"].items():
            fields = f" It names: {', '.join(d['fields'])}." if d.get("fields") else ""
            quote = f" The page: “{d['quote']}”" if d.get("quote") else ""
            lines.append(f"- `{key}` ({d['label']}): {_sentence(d['rule'])}{quote}{fields} ({d['source']}, read {d['checked']})")
    else:
        lines.append("- None recorded.")
    lines += ["", "## Other points the venue asks the letter to make", ""]
    lines += [f"- [ ] {_sentence(p['rule'])}" + (f" The page: “{p['quote']}”" if p["quote"] else "")
              + f" ({p['source']}, read {p['checked']})" for p in n["points"]] or ["- None recorded."]
    fit = n["fit"]
    lines += ["", "## The journal's own words on what it publishes", ""]
    if fit["scope"]:
        lines.append(f"- Scope: “{fit['scope']}”")
    for name, quote in fit["article_types"].items():
        lines.append(f"- {name} articles: “{quote}”")
    if fit["scope"] or fit["article_types"]:
        lines.append(f"- Page: {fit['source']}, read {fit['checked']}")
    else:
        lines.append(f"- Not recorded: read {n['url'] or 'the author guide'} and record them as `scope` "
                     "(quote, article_types, source, checked) with venues.py save.")
    p = n["presubmission"]
    lines += ["", "## Presubmission inquiries", "",
              {"answered": "- The journal answers them.", "not_answered": "- The journal does not answer them."}.get(
                  p["answered"] or "", "- Not recorded: the author guide or the editorial office says.")]
    if p["quote"]:
        lines.append(f"  The page: “{p['quote']}”")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------ the manuscript

def _norm(text: str) -> str:
    return guard._folded(re.sub(r"[*_`^\\]", "", text))


class Manuscript:
    """The manuscript's sentences as the claim guard reads them, with their sections (the title left out)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.title = guard.document_title(text)
        self.sentences = []
        for s in guard.segment(text):
            parts = [p for p in s.section.split(" > ") if p]
            if parts and self.title and parts[0] == self.title:
                parts = parts[1:]
            self.sentences.append({"text": s.text, "line": s.line, "block": s.block, "words": s.words,
                                   "section": " > ".join(parts), "top": parts[0] if parts else "",
                                   "note": s.text.lstrip().startswith(">")})
        self._joined = ""
        self._spans: list[tuple[int, int]] = []
        for s in self.sentences:
            start = len(self._joined)
            self._joined += _norm(s["text"]) + " "
            self._spans.append((start, len(self._joined) - 1))

    def locate(self, passage: str) -> list[dict[str, Any]]:
        """The sentences a passage copied from the manuscript lies in; [] when it is not there word for word."""
        folded = _norm(passage)
        if not folded:
            return []
        at = self._joined.find(folded)
        if at < 0:
            return []
        end = at + len(folded)
        return [s for s, (a, b) in zip(self.sentences, self._spans) if a < end and at < b]

    def closest(self, sentence: str) -> tuple[Optional[dict[str, Any]], float]:
        """The Abstract or Results sentence that shares most words with `sentence`."""
        words = guard._content_words(sentence)
        best, score = None, 0.0
        for s in self.sentences:
            if s["note"] or not SHOWN_FROM.match(s["top"]):
                continue
            d = guard._dice(words, s["words"])
            if d > score:
                best, score = s, d
        return best, score

    def abstract(self) -> Optional[str]:
        """The Abstract's paragraphs as written, without notes to the authors (block quotes) or comments."""
        m = re.search(r"^#{1,6}\s*\**\s*(?:abstract|summary)\b.*$", self.text, re.IGNORECASE | re.MULTILINE)
        if m:
            rest = self.text[m.end():]
            nxt = re.search(r"^#{1,6}\s", rest, re.MULTILINE)
            body = rest[:nxt.start()] if nxt else rest
        else:
            tex = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", self.text, re.DOTALL)
            if not tex:
                return None
            body = tex.group(1)
        body = re.sub(r"<!--.*?-->", "", body, flags=re.DOTALL)
        kept = [line for line in body.splitlines() if not line.lstrip().startswith(">")]
        paragraphs = [" ".join(p.split()) for p in "\n".join(kept).split("\n\n")]
        text = "\n\n".join(p for p in paragraphs if p)
        return text or None


# ------------------------------------------------------------------------------------------------ the letter file

def _passages(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return list(value)
    raise LetterError("`from` is a passage of the manuscript or a list of them")


def _item(value: Any, where: str) -> Optional[dict[str, Any]]:
    """A sentence or declaration: {text, from, given_by}; a bare string is its text."""
    if value is None:
        return None
    if isinstance(value, str):
        value = {"text": value}
    if not isinstance(value, dict) or not isinstance(value.get("text"), str) or not value["text"].strip():
        raise LetterError(f"{where} needs `text`")
    return {"text": " ".join(value["text"].split()), "from": _passages(value.get("from")),
            "given_by": value.get("given_by")}


def read_spec(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise LetterError(f"cannot read {path}: {e}") from e
    if not isinstance(raw, dict):
        raise LetterError(f"{path} is not a mapping of the letter's fields")
    kind = raw.get("kind", "cover")
    if kind not in ("cover", "inquiry"):
        raise LetterError("`kind` is cover or inquiry")
    for field in ("venue", "article_type"):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise LetterError(f"`{field}` is required")
    shows = raw.get("shows") or []
    if not isinstance(shows, list):
        raise LetterError("`shows` is a list of sentences")
    points = raw.get("points") or []
    if not isinstance(points, list):
        raise LetterError("`points` is a list of sentences")
    fit = raw.get("fit") or {}
    if not isinstance(fit, dict) or fit.get("use", "auto") not in ("auto", "scope", "article_type"):
        raise LetterError("`fit.use` is scope or article_type")
    declarations = raw.get("declarations") or {}
    if not isinstance(declarations, dict):
        raise LetterError("`declarations` is a mapping")
    unknown = set(declarations) - set(DECLARATIONS) - {"other"}
    if unknown:
        raise LetterError(f"unknown declarations: {', '.join(sorted(unknown))}; known: "
                          f"{', '.join(DECLARATIONS)}, other")
    spec: dict[str, Any] = {
        "kind": kind, "venue": raw["venue"].strip(), "article_type": raw["article_type"].strip(),
        "title": raw.get("title"), "editor": raw.get("editor"),
        "shows": [_item(s, f"shows[{n}]") for n, s in enumerate(shows)],
        "points": [_item(s, f"points[{n}]") for n, s in enumerate(points)],
        "fit": {"use": fit.get("use", "auto"), "because": _item(fit.get("because"), "fit.because")},
        "related": raw.get("related"), "declarations": {}, "question": raw.get("question"),
        "accept": raw.get("accept"), "closing": raw.get("closing"), "signature": raw.get("signature"),
    }
    for key, value in declarations.items():
        if key == "reviewers":
            if not isinstance(value, dict):
                raise LetterError("`declarations.reviewers` is {suggested, excluded, given_by}")
            spec["declarations"][key] = value
        elif key == "other":
            spec["declarations"][key] = [dict(_item(x, f"declarations.other[{n}]") or {},
                                              label=(x or {}).get("label") if isinstance(x, dict) else None)
                                         for n, x in enumerate(value or [])]
        else:
            spec["declarations"][key] = _item(value, f"declarations.{key}")
    if kind == "inquiry":
        if not isinstance(spec["question"], str) or not spec["question"].strip():
            raise LetterError("an inquiry needs `question`: what the authors ask the editor")
        if not spec["accept"]:
            raise LetterError("an inquiry needs `accept`: what the authors will take as an answer")
    if isinstance(spec["accept"], list):
        spec["accept"] = " ".join(str(x).strip() for x in spec["accept"])
    return spec


# ------------------------------------------------------------------------------------------------ checks

def _tokens_added(letter: str, sources: str) -> list[str]:
    a, b = guard.sentence_tokens(letter), guard.sentence_tokens(sources)
    return [t for kind in guard.TOKEN_KINDS for t in (a[kind] - b[kind])]


# How much of a set a sentence speaks of; a summary that says "all" where the paper says "most" claims more. The guard
# reads "in all species" and "always"; a bare quantifier is a letter's usual way of rounding up.
QUANTIFIERS = (("almost all", 3), ("nearly all", 3), ("the majority", 3), ("most", 3), ("all", 4), ("every", 4),
               ("none", 4), ("many", 2), ("some", 1), ("several", 1), ("a few", 1))
QUANTIFIER_RX = re.compile(r"\b(" + "|".join(re.escape(q) for q, _ in QUANTIFIERS) + r")\b", re.IGNORECASE)


def _quantifier(text: str) -> tuple[int, str]:
    rank = dict(QUANTIFIERS)
    found = [(rank[m.group(1).lower()], m.group(1).lower()) for m in QUANTIFIER_RX.finditer(text)]
    return max(found) if found else (0, "")


def claim_problems(sentence: str, sources: list[dict[str, Any]], title: Optional[str] = None) -> list[str]:
    """What the claim guard says of a letter sentence against the manuscript sentences it rests on: stronger claims,
    dropped qualifiers and numbers, citations or identifiers the sentences do not have (the paper's title aside, so
    the 2 of "MitoAge 2" is no new number)."""
    source_text = " ".join(s["text"] for s in sources)
    report = guard.compare(source_text, sentence)
    out = []
    for c in report["sentence_changes"]:
        if c["severity"] == "protected" and c["kind"] in guard.CLAIM_KINDS:
            out.append(f"claim guard: {guard.describe(c)}")
    out += [f"“{t}” is not in the manuscript's sentences it rests on"
            for t in _tokens_added(sentence, f"{title or ''} {source_text}")]
    (said, word), (had, before) = _quantifier(sentence), _quantifier(source_text)
    if said >= 3 and said > had:
        out.append(f"claim guard: the letter says “{word}” where the manuscript says "
                   + (f"“{before}”" if before else "no such quantifier") + "; that claims more of the set")
    return out


def _capitalised(text: str) -> set[str]:
    """Names a declaration states: capitalised words not opening a sentence, and every number."""
    found = set()
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        words = re.findall(r"[A-Za-z][\w'’.-]*[\w]|[A-Za-z]", sentence)
        for n, w in enumerate(words):
            if n == 0 and w.lower() in OPENING_WORDS:
                continue
            if w[0].isupper() and w.lower() not in OPENING_WORDS:
                found.add(w)
    return found


def trace(item: dict[str, Any], ms: Manuscript, part: str, *, shown: bool) -> dict[str, Any]:
    """Where a letter sentence about the paper comes from, and what the claim guard says of it. `shown`: it says
    what the paper shows, so it must rest on the Abstract or Results."""
    out = {"part": part, "text": item["text"], "from": item["from"], "sources": [], "problems": [], "how": None}
    sources: list[dict[str, Any]] = []
    for passage in item["from"]:
        if len(passage.split()) < 3:
            out["problems"].append(f"the passage “{passage}” is shorter than three words")
            continue
        found = ms.locate(passage)
        if not found:
            out["problems"].append(f"the passage “{passage}” is not in the manuscript word for word")
        sources += [s for s in found if s not in sources]
    if item["from"]:
        out["how"] = "named"
    else:
        best, score = ms.closest(item["text"])
        if best is not None and score >= AUTO_TRACE:
            sources, out["how"] = [best], f"closest sentence ({score:.2f} of words shared)"
        else:
            out["problems"].append("untraced: no passage named, and no sentence of the Abstract or Results is close")
    for s in sources:
        if s["note"]:
            out["problems"].append(f"line {s['line']} is a note to the authors, not manuscript text")
        elif shown and BACKGROUND.match(s["top"]):
            out["problems"].append(f"G6: line {s['line']} is in the {s['top']}, background the editor knows; say what "
                                   "the paper shows, from the Abstract or Results")
    out["sources"] = [{"text": s["text"], "section": s["section"], "line": s["line"]} for s in sources]
    if sources:
        out["problems"] += claim_problems(item["text"], sources, ms.title)
    return out


def declaration_check(key: str, item: dict[str, Any], ms: Manuscript) -> dict[str, Any]:
    """A declaration rests on the manuscript's own passages or on the authors' words; it adds no name or number."""
    out = {"key": key, "text": item["text"], "from": item["from"], "given_by": item.get("given_by"), "sources": [],
           "problems": []}
    if not item["from"] and not item.get("given_by"):
        out["problems"].append("no source: name the manuscript's passages (`from`) or who gave it (`given_by`)")
        return out
    if item["from"]:
        sources: list[dict[str, Any]] = []
        for passage in item["from"]:
            found = ms.locate(passage) if len(passage.split()) >= 3 else []
            if not found:
                out["problems"].append(f"the passage “{passage}” is not in the manuscript word for word")
            sources += [s for s in found if s not in sources]
        for s in sources:
            if s["note"]:
                out["problems"].append(f"line {s['line']} is a note to the authors, not manuscript text")
        out["sources"] = [{"text": s["text"], "section": s["section"], "line": s["line"]} for s in sources]
        if sources and not item.get("given_by"):
            source_text = " ".join(s["text"] for s in sources)
            known = {w.lower() for w in re.findall(r"[\w'’.-]+", source_text)}
            added = sorted(w for w in _capitalised(item["text"]) if w.lower() not in known)
            if added:
                out["problems"].append("names what its passages do not: " + ", ".join(added))
            out["problems"] += [f"“{t}” is not in its passages" for t in _tokens_added(item["text"], source_text)]
    return out


def smell_problems(letter: str) -> list[dict[str, Any]]:
    """The letter's uses of the letter smells, each at its first use, in every paragraph however short (a closing line
    is one); quoted words (the journal's own) aside, as style_profile.py reads a report."""
    smells = {k: v for k, v in style.load_smells().items() if k in LETTER_SMELLS}
    cleaned = style.clean(letter, False, report=True)
    out = []
    line = 1
    for block in re.split(r"\n\s*\n", cleaned):
        start = line
        line += block.count("\n") + 2
        sents = style.sentences(" ".join(block.split()))
        for k, sent in enumerate(sents):
            for sid, smell in smells.items():
                if smell["scope"] == "end" and k != len(sents) - 1:
                    continue
                target = sent.lstrip("\"“(") if smell["scope"] in ("start", "end") else sent
                for rx in smell["patterns"]:
                    m = rx.search(target)
                    if m and not (smell["scope"] == "start" and m.start() != 0):
                        out.append({"id": sid, "name": smell["name"], "words": m.group(0).strip(), "line": start})
                        break
    return out


def crossref(doi: str) -> dict[str, Any]:
    import httpx
    r = httpx.get(f"https://api.crossref.org/works/{doi}", timeout=20,
                  headers={"User-Agent": "manuscript-skills letter.py (cover-letter check)"})
    r.raise_for_status()
    return r.json()["message"]


def _journal_names(v: dict[str, Any]) -> set[str]:
    def norm(x: str) -> str:
        return re.sub(r"^the\s+", "", " ".join(re.sub(r"[^\w\s]", " ", x.lower()).split()))
    return {norm(n) for n in [v.get("name") or "", *(v.get("aliases") or [])] if n}


def related_check(related: Any, v: dict[str, Any], today: date,
                  lookup: Optional[Callable[[str], dict[str, Any]]]) -> dict[str, Any]:
    """Whether the related paper may be named: its identity verified, and (with a lookup) Crossref placing it in this
    journal within the last RELATED_YEARS years."""
    if not related:
        return {"named": False, "problems": [], "citation": None}
    if not isinstance(related, dict) or not related.get("citation"):
        raise LetterError("`related` is {citation, doi, verified, why}")
    out: dict[str, Any] = {"named": False, "problems": [], "citation": related["citation"],
                           "doi": related.get("doi"), "verified": related.get("verified")}
    if not related.get("verified"):
        out["problems"].append("a related paper is named only once its identity is verified (`verified`: how, by "
                               "manuscript-reference-check's identity check); it is left out")
        return out
    if lookup is not None:
        if not related.get("doi"):
            out["problems"].append("no DOI to check; the related paper is left out")
            return out
        try:
            record = lookup(str(related["doi"]))
        except Exception as e:  # noqa: BLE001 - any failure to read the record leaves the paper out
            out["problems"].append(f"Crossref could not be read for {related['doi']} ({e}); the paper is left out")
            return out
        titles = {re.sub(r"^the\s+", "", " ".join(re.sub(r"[^\w\s]", " ", t.lower()).split()))
                  for t in record.get("container-title") or []}
        year = ((record.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        if not titles & _journal_names(v):
            out["problems"].append(f"Crossref places {related['doi']} in {', '.join(record.get('container-title') or ['no journal'])}, "
                                   f"not {v.get('name')}; the paper is left out")
            return out
        if not year or year < today.year - RELATED_YEARS:
            out["problems"].append(f"{related['doi']} is from {year or 'an unknown year'}, not within the last "
                                   f"{RELATED_YEARS} years; the paper is left out")
            return out
        out["crossref_year"] = year
    out["named"] = True
    return out


# ------------------------------------------------------------------------------------------------ the letter

def _sentence(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in ".?!:]" else text + "."


def _type_phrase(article: str) -> str:
    """'Resources' → 'Resources articles'; 'research article' stays 'research articles'."""
    return article + ("s" if re.search(r"\barticle$", article, re.IGNORECASE) else
                      "" if re.search(r"\barticles$", article, re.IGNORECASE) else " articles")


ARTICLE_NOUNS = re.compile(r"\b(?:article|paper|report|note|review|letter|communication|survey|summary|"
                           r"perspective|commentary|brief|protocol|resource)$", re.IGNORECASE)


def _as_type(article: str) -> str:
    """'Resources' → 'a Resources article'; 'research article' → 'a research article'."""
    phrase = article if ARTICLE_NOUNS.search(article) else f"{article} article"
    return ("an " if phrase[:1].lower() in "aeiou" else "a ") + phrase


def compose(spec: dict[str, Any], v: dict[str, Any], needs: dict[str, Any], ms: Manuscript,
            related: dict[str, Any], withheld: frozenset[str] = frozenset()) -> tuple[str, list[str], dict[str, Any]]:
    """The letter's text, the gaps it leaves and the venue words it quotes. `withheld`: declarations that failed their
    check, which the letter leaves as gaps rather than state."""
    journal = needs["name"]
    title = spec["title"] or ms.title or None
    gaps: list[str] = []

    def gap(what: str, optional: bool = False) -> str:
        gaps.append(what)
        return f"[TO FILL{', optional' if optional else ''}: {what}]"

    title_text = f"“{title}”" if title else gap("the manuscript's title")
    article = spec["article_type"]
    editor = spec["editor"] or "Editor"
    shows = " ".join(_sentence(s["text"]) for s in spec["shows"]) or gap("two or three sentences on what the paper "
                                                                          "shows, from its Abstract and Results")
    points = " ".join(_sentence(p["text"]) for p in spec["points"])
    fit = needs["fit"]
    use = spec["fit"]["use"]
    by_type = {k.lower(): (k, q) for k, q in fit["article_types"].items()}
    quoted: dict[str, Any] = {}
    if use in ("auto", "article_type") and article.lower() in by_type:
        name, quote = by_type[article.lower()]
        quoted = {"what": _type_phrase(name), "quote": quote}
        fit_text = f"{journal}'s guidelines describe {_type_phrase(name)} as “{quote}”"
    elif use in ("auto", "scope") and fit["scope"]:
        quoted = {"what": "its scope", "quote": fit["scope"]}
        fit_text = f"{journal} describes its scope as “{fit['scope']}”"
    elif spec["kind"] == "inquiry":
        fit_text = gap(f"the rule of {journal}'s author guide the question turns on (its scope, or what it says of "
                       f"{_type_phrase(article)}), quoted from it")
    else:
        fit_text = gap(f"why the paper fits {journal}, in the journal's own words on its scope or on "
                       f"{_type_phrase(article)}, quoted from its author guide")
    if quoted:
        quoted.update(source=fit["source"], checked=fit["checked"])
    because = spec["fit"]["because"]
    fit_paragraph = _sentence(fit_text) + (f" {_sentence(because['text'])}" if because else "")
    related_text = ""
    if related["named"]:
        doi = f" (https://doi.org/{related['doi']})" if related.get("doi") else ""
        why = (spec["related"] or {}).get("why")
        why_text = f" {_sentence(why['text'] if isinstance(why, dict) else str(why))}" if why else ""
        related_text = f"It follows on from {related['citation']}{doi}, published in {journal}.{why_text}"
    elif spec["kind"] == "cover":
        related_text = gap(f"a recent paper in {journal} close to this one, if the authors know one", optional=True)
    closing = _sentence(spec["closing"]) if spec["closing"] else "Yours sincerely,"
    signature = spec["signature"].strip() if isinstance(spec["signature"], str) and spec["signature"].strip() \
        else gap("the corresponding author's name, affiliation and email")

    lines: list[str] = []
    if spec["kind"] == "inquiry":
        lines += [f"Subject: Presubmission inquiry: {title or 'the manuscript'}, as {_as_type(article)}", "",
                  f"Dear {editor},", "", _sentence(spec["question"].strip()) + " " + shows, "", fit_paragraph]
        if related["named"]:
            lines += ["", related_text]
        lines += ["", _sentence(str(spec["accept"]).strip())]
        decl = _declaration_lines(spec, needs, gap, withheld, required=False)
        for paragraph in decl:
            lines += ["", paragraph]
        abstract = ms.abstract()
        lines += ["", "Abstract:", "", abstract or gap("the abstract")]
    else:
        lines += [f"Dear {editor},", "",
                  f"We submit {title_text} for consideration as {_as_type(article)} in {journal}. {shows}"]
        if points:
            lines += ["", points]
        lines += ["", fit_paragraph, "", related_text]
        decl = _declaration_lines(spec, needs, gap, withheld, required=True)
        for paragraph in decl:
            lines += ["", paragraph]
    lines += ["", closing, "", signature]
    return "\n".join(lines).rstrip() + "\n", gaps, quoted


def _declaration_lines(spec: dict[str, Any], needs: dict[str, Any], gap: Callable[..., str],
                       withheld: frozenset[str], *, required: bool) -> list[str]:
    """One paragraph per declaration, in DECLARATIONS order: the authors' or the manuscript's words, or a gap for
    each the venue asks for and nobody supplied."""
    given = spec["declarations"]
    out = []
    for key, (label, _) in DECLARATIONS.items():
        asked = key in needs["declarations"] and required
        if key == "reviewers":
            r = given.get(key)
            if r and r.get("given_by"):
                for which in ("suggested", "excluded"):
                    people = r.get(which) or []
                    if people:
                        names = "; ".join(", ".join(str(p[f]) for f in ("name", "affiliation", "email", "reason")
                                                    if isinstance(p, dict) and p.get(f)) for p in people)
                        out.append(f"{'Suggested' if which == 'suggested' else 'Excluded'} reviewers: {names}.")
            elif asked or r:
                out.append(gap("suggested or excluded reviewers, from the authors"))
            continue
        item = given.get(key)
        if item and key in withheld:
            out.append(gap(f"{label}, from the authors or the manuscript's own words (the draft's has no source for "
                           "all it says)"))
        elif item:
            out.append(_sentence(item["text"]))
        elif asked:
            source = ("what the authors say the tools did, in the short template of disclosure-templates.md"
                      if key == "ai_use" else "the authors' words")
            out.append(gap(f"{label}, from {source}: {needs['name']} asks for it in the cover letter"))
    for n, item in enumerate(given.get("other") or []):
        out.append(gap(f"{item.get('label') or 'a declaration'}, from the authors or the manuscript's own words")
                   if f"other[{n}]" in withheld else _sentence(item["text"]))
    return out


def _words(text: str) -> int:
    return len(re.findall(r"[\w'’-]+", text))


def write_letter(spec: dict[str, Any], paper: Path, out_dir: Path, *, today: Optional[date] = None,
                 lookup: Optional[Callable[[str], dict[str, Any]]] = None) -> dict[str, Any]:
    """Compose, check and write the letter and its claims file; return the record (also written as JSON)."""
    today = today or date.today()
    try:
        ms = Manuscript(paper.read_text(encoding="utf-8"))
    except OSError as e:
        raise LetterError(f"cannot read {paper}: {e}") from e
    v = _venue(spec["venue"])
    needs = letter_needs(v)
    related = related_check(spec["related"], v, today, lookup)
    problems: list[str] = list(related["problems"])
    declared = []
    for key, item in spec["declarations"].items():
        if key == "reviewers":
            if not item.get("given_by"):
                problems.append("declarations.reviewers: reviewers come only from the authors (`given_by`); left out")
            declared.append({"key": key, "given_by": item.get("given_by"), "suggested": item.get("suggested") or [],
                             "excluded": item.get("excluded") or [], "problems": []})
            continue
        for n, one in enumerate(item if key == "other" else [item]):
            d = declaration_check(key if key != "other" else f"other[{n}]", one, ms)
            problems += [f"declarations.{d['key']}: {p} (left as a gap)" for p in d["problems"]]
            declared.append(d)
    withheld = frozenset(d["key"] for d in declared if d["problems"])
    letter, gaps, quoted = compose(spec, v, needs, ms, related, withheld)

    lo, hi = SHOWS[spec["kind"]]
    if not lo <= len(spec["shows"]) <= hi:
        problems.append(f"what the paper shows takes {lo} to {hi} sentences; the letter has {len(spec['shows'])}")
    traced = [trace(s, ms, f"shows[{n}]", shown=True) for n, s in enumerate(spec["shows"])]
    traced += [trace(p, ms, f"points[{n}]", shown=False) for n, p in enumerate(spec["points"])]
    if spec["fit"]["because"]:
        traced.append(trace(spec["fit"]["because"], ms, "fit.because", shown=False))
    why = (spec["related"] or {}).get("why") if related["named"] else None
    if why:
        traced.append(trace(_item(why, "related.why") or {}, ms, "related.why", shown=False))
    for t in traced:
        problems += [f"{t['part']}: {p}" for p in t["problems"]]
    if spec["kind"] == "inquiry":
        if not spec["question"].strip().endswith("?"):
            problems.append("the inquiry's question does not end with a question mark: ask it, first")
        if needs["presubmission"]["answered"] == "not_answered":
            problems.append(f"{needs['name']}'s facts say it does not answer presubmission inquiries"
                            + (f": “{needs['presubmission']['quote']}”" if needs["presubmission"]["quote"] else ""))
    if spec["closing"] and len(re.findall(r"[.!?](?:\s|$)", spec["closing"].strip())) > 1:
        problems.append("the closing is more than one line (G5)")
    smells = smell_problems(letter)
    problems += [f"{s['id']} ({s['name']}): “{s['words']}”" for s in smells]
    # The inquiry is counted up to its abstract, the cover letter up to its closing line.
    body = (letter.split("\nAbstract:\n")[0] if spec["kind"] == "inquiry"
            else letter.rsplit("\n\n", 2)[0])
    words = _words(GAP_RX.sub("", body))
    limit = INQUIRY_WORDS if spec["kind"] == "inquiry" else COVER_WORDS
    if words > limit:
        problems.append(f"{words} words, more than the {limit} a "
                        f"{'presubmission inquiry' if spec['kind'] == 'inquiry' else 'one-page cover letter'} takes")

    stem = f"{'presubmission-inquiry' if spec['kind'] == 'inquiry' else 'cover-letter'}.{spec['venue']}"
    out_dir.mkdir(parents=True, exist_ok=True)
    record = {"kind": spec["kind"], "venue": spec["venue"], "journal": needs["name"], "paper": str(paper),
              "letter": f"{stem}.md", "words": words, "passed": not problems, "problems": problems, "gaps": gaps,
              "quoted": quoted, "needs": needs, "traced": traced, "declarations": declared, "related": related,
              "smells": smells, "written": today.isoformat(),
              "findings": gap_findings(spec, needs["name"], f"{stem}.md", letter, gaps)}
    (out_dir / f"{stem}.md").write_text(letter, encoding="utf-8")
    (out_dir / f"{stem}.claims.md").write_text(claims_markdown(record), encoding="utf-8")
    (out_dir / f"{stem}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False, default=str) + "\n",
                                          encoding="utf-8")
    return record


def gap_findings(spec: dict[str, Any], journal: str, file: str, letter: str, gaps: list[str]) -> list[dict[str, Any]]:
    """Each gap the letter leaves, as a draft finding for the stage's findings.json: what only the authors can give
    (a name, a declaration's facts, the title) is `major`, so the dashboard's To-do list, the Word review and the
    workbook carry it; an optional one (a related paper) is `info`. Their evidence is the gap's marker in the letter."""
    what = "presubmission inquiry" if spec["kind"] == "inquiry" else "cover letter"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", spec["venue"]).strip("-") or "venue"
    out = []
    for n, gap in enumerate(dict.fromkeys(gaps), 1):
        optional = f"[TO FILL, optional: {gap}]" in letter
        marker = f"[TO FILL{', optional' if optional else ''}: {gap}]"
        out.append({"id": f"JA-L-{slug}-{n}", "category": "Submission package", "section": f"The {what} to {journal}",
                    "quote": None, "looked_in": [file], "summary": f"The {what} to {journal} waits for something only "
                    "you can give", "detail": f"The letter leaves a gap for {gap.rstrip('.')}.",
                    "action": f"Give it, and the letter is written again with it (letter.py write); until then the "
                              f"letter says {marker}.",
                    "severity": "info" if optional else "major", "stage": "journal", "confidence": "confirmed",
                    "decision": False, "evidence": [{"path": file, "quote": marker}]})
    return out


def claims_markdown(r: dict[str, Any]) -> str:
    what = "presubmission inquiry" if r["kind"] == "inquiry" else "cover letter"
    lines = [f"# Where the {what} to {r['journal']} gets what it says", "",
             f"The letter is `{r['letter']}`, {r['words']} words. This file is not for sending.", "",
             "## Checks", ""]
    if r["problems"]:
        lines.append(f"{len(r['problems'])} problem{'s' if len(r['problems']) != 1 else ''} to fix before sending:")
        lines += ["", *[f"- {p}" for p in r["problems"]]]
    else:
        lines.append("Every claim about the paper is traced to the manuscript and keeps its strength; no letter smell "
                     "(G5, G1, A1, A3, A4, A5) and no background for the editor (G6) was found.")
    lines += ["", "## Gaps for the authors", ""]
    lines += [f"- {g}" for g in r["gaps"]] or ["- None."]
    lines += ["", "## What the paper shows, and where the manuscript says it", ""]
    for t in r["traced"]:
        lines.append(f"- **{t['part']}**: {t['text']}")
        for s in t["sources"]:
            lines.append(f"  - {s['section'] or 'before the first section'}, line {s['line']}: {s['text']}")
        if t["how"] and t["how"] != "named":
            lines.append(f"  - matched as the {t['how']}; name the passages with `from` to make it exact")
        lines += [f"  - Problem: {p}" for p in t["problems"]]
    if not r["traced"]:
        lines.append("- Nothing.")
    q = r["quoted"]
    lines += ["", "## The journal's words the letter quotes", ""]
    lines.append(f"- On {q['what']}: “{q['quote']}” ({q['source']}, read {q['checked']})" if q else
                 "- None: the catalogue records no scope or article-type words for this journal. Read its author guide "
                 "and record them as `scope` with venues.py save.")
    rel = r["related"]
    if rel.get("citation"):
        lines += ["", "## Related paper in the journal", "",
                  f"- {rel['citation']}: " + (f"named; identity verified ({rel['verified']})" if rel["named"]
                                               else "left out")]
    lines += ["", "## Declarations", ""]
    asked = r["needs"]["declarations"]
    for key, d in asked.items():
        lines.append(f"- `{key}` is asked for in the cover letter: {_sentence(d['rule'])}"
                     + (f" The page: “{d['quote']}”" if d.get("quote") else "")
                     + (f" It names: {', '.join(d['fields'])}." if d.get("fields") else "")
                     + f" ({d['source']}, read {d['checked']})")
    for d in r["declarations"]:
        src = (f"given by {d['given_by']}" if d.get("given_by") else
               "; ".join(f"{s['section']}, line {s['line']}" for s in d.get("sources") or []) or "no source")
        lines.append(f"- `{d['key']}` in the letter, from {src}")
        lines += [f"  - Problem: {p}" for p in d.get("problems") or []]
    if not asked and not r["declarations"]:
        lines.append("- None asked for and none given.")
    lines += ["", "## Other points the journal asks the letter to make", ""]
    lines += [f"- [ ] {_sentence(p['rule'])}" + (f" The page: “{p['quote']}”" if p["quote"] else "")
              + f" ({p['source']}, read {p['checked']})" for p in r["needs"]["points"]] or ["- None recorded."]
    if not r["needs"]["researched"]:
        lines += ["", f"The catalogue records no cover-letter rule for {r['journal']}: read {r['needs']['url']} for "
                      "what the letter must say before sending."]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------------ commands

@app.command()
def needs(
    venue: Annotated[str, typer.Argument(help="Venue key, as `venues.py rank` lists it")],
    format: Annotated[Format, typer.Option("--format", help="md or json")] = Format.md,
) -> None:
    """What the venue's recorded facts ask of a cover letter and of a presubmission inquiry."""
    try:
        n = letter_needs(_venue(venue))
    except LetterError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2)
    typer.echo(json.dumps(n, indent=2, ensure_ascii=False, default=str) if format == Format.json
               else needs_markdown(n))


@app.command()
def write(
    spec_path: Annotated[Path, typer.Argument(help="The letter's content (references/letters.md gives the fields)")],
    paper: Annotated[Path, typer.Option("--paper", help="The manuscript the letter's claims come from")],
    run: Annotated[Optional[Path], typer.Option("--run", help="The run folder: writes beside the stage report")] = None,
    out: Annotated[Optional[Path], typer.Option("--out", help="Write here instead")] = None,
    verify_related: Annotated[bool, typer.Option(
        "--verify-related", help="Check the related paper's journal and year with Crossref")] = False,
) -> None:
    """Write the letter, its claims file and its JSON, checking every claim against the manuscript."""
    if (run is None) == (out is None):
        typer.echo("give --run RUN or --out DIR", err=True)
        raise typer.Exit(2)
    out_dir = out if out is not None else run / STAGE  # type: ignore[operator]
    try:
        record = write_letter(read_spec(spec_path), paper, out_dir, lookup=crossref if verify_related else None)
    except LetterError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2)
    stem = out_dir / record["letter"]
    typer.echo(f"Wrote {stem} and {stem.with_suffix('.claims.md').name} ({record['words']} words).")
    if record["gaps"]:
        typer.echo(f"Gaps for the authors: {len(record['gaps'])}: " + "; ".join(record["gaps"]))
    if record["problems"]:
        typer.echo("Problems:\n" + "\n".join(f"- {p}" for p in record["problems"]))
        raise typer.Exit(1)
    typer.echo("Every check passed.")


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    _utf8_console()
    app()
