# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Flag content changes after a manuscript edit, or list them between two versions of a manuscript.

A copy-editing pass may change wording, never content. The guard compares the text before and after in two ways:

- whole-text counts of selected number, citation, identifier, term, URL and code-span patterns, plus selected
  hedges, negations and causal verbs (the `protected` and `watched` fields);
- sentence by sentence (`sentence_changes`): it aligns the sentences of BEFORE and AFTER, allowing for split,
  merged and moved sentences, and reports for each aligned pair a claim that moved on the causal or evidential
  ladder, novelty or generality wording that appeared or went, a scope qualifier ("in this cohort", "in mice"),
  limiting or concessive word ("only", "albeit", "despite"), null-result marker ("did not differ") or
  evidence-status word ("self-reported", "predicted") that disappeared or appeared, a changed negation, a deleted
  sentence, and every number, citation or identifier that one sentence has and its counterpart lacks, with
  section and line. A sentence counts as merged into another only when it lends it some of its words; one that
  shares nothing with its neighbours was deleted. The ladders are in references/claim-ladders.md.

It cannot prove semantic equivalence: swapped values and changed relationships can pass every check. Read the
diff in context.

    uv run --script guard.py BEFORE.md AFTER.md
    uv run --script guard.py PAPER.md --against HEAD                      # compare with the committed version
    uv run --script guard.py BEFORE.md AFTER.md --json report.json --md report.md
    uv run --script guard.py BEFORE.md AFTER.md --authorised requested.yaml  # the claim changes a request asked for
    uv run --script guard.py BEFORE.md AFTER.md --allow-strengthening     # every claim change authorised at once
    uv run --script guard.py ORIGINAL.tex REVISED.tex --revision --json inventory.json
    uv run --script guard.py ORIGINAL.md PROPOSED.md --revision --authorised requested.yaml  # fail on unrequested widening
    uv run --script guard.py BEFORE.md AFTER.md --moved-to SUPPLEMENT.md  # text moved to another file (repeatable)
    uv run --script guard.py BEFORE.md AFTER.md --relocated               # a story edit: caveats moved on purpose
        uv run --script guard.py BEFORE.md AFTER.md --only Discussion           # the edit was asked for there only
    uv run --script guard.py PAPER.md --summary                            # title, Abstract, Conclusions vs body
    uv run --script guard.py ORIGINAL.md FINAL.md --revision --relocated-in RUN/manuscript-story \
        --authorised requested.yaml                                       # only the story stage's changes move caveats

Edit mode (default). Exit code 1 when a protected item changed: a count of numbers, citations, identifiers,
terms, URLs or code; a claim that rose on a ladder or gained novelty or generality wording; a scope,
null-result or evidence-status marker that disappeared, or a limiting or concessive word that left a surviving
sentence; or a number, citation or identifier that is new to its sentence and its paragraph, or left them.
`--allow-strengthening` exempts every claim change (never the counts or the tokens) when the authors authorised a
claim correction. Warnings, which the authors must still see: a lowered claim (protected instead when the
sentence is negated, since a weaker verb can then strengthen it), an added qualifier, a changed negation, a deleted
sentence, a number, citation or identifier moved to another sentence of the same paragraph or into a `--moved-to`
file. One moved to another paragraph stays protected (see story moves for the exception). A deleted sentence that
is only a stock phrase the contract lets an edit cut (an empty implication, a mini-conclusion, a filler phrase,
signposting; ../manuscript-deslop/references/smell-patterns.yaml) is not listed: fewer than four content words
remain once the phrase is taken out. One that said more is listed as a warning, "cut as a stock phrase". A
technical term added to a paragraph that already has it (a pronoun given its noun) is not counted as a change.

Story moves (`--relocated`), for an edit that moves caveats on purpose (manuscript-story's):
- A scope, limiting or concessive, null-result or evidence-status marker that a sentence lost, or that a deleted
  sentence carried, is a warning instead of protected when another sentence of the same top-level section (the
  Results with its subsections) states the same marker (same scope key, word, null result or status key) about
  the same thing: it shares at least two content words with the sentence the marker left, and it either gained
  the marker in this edit or already had it. Each gained occurrence accounts for one lost marker, and a sentence
  that lost markers of a kind offers only what it gained beyond them.
- A scope qualifier or evidence status (model system, cohort, ancestry, self-report, reference build, "in this
  study") lost from a sentence of the Abstract or the Introduction stays protected, wherever else the paper
  states it. A `--moved-to` file is never the same section, so a marker that reappears only there stays
  protected too.
- A number that left its sentence for another paragraph of the same section is a warning when the sentence it
  went to shares at least two content words with the one it left (`token_status` "moved_within_section"); every
  other number, citation or identifier stays protected as in edit mode. A number repeated in a paragraph that
  already had it is not counted as a change of the whole-text counts.
- A new sentence whose claim wording would be protected is a warning when it is a headline for a result: it stands
  in the paragraph of a result, before it, names no number, citation, identifier or technical term that paragraph
  lacked, and claims no more than the paragraph does (no higher rung on either ladder, and no comparative, causal
  connective, novelty or generality wording the paragraph does not have).
A relocated caveat gets `relocated_to` (a list of {marker, section, line, file, sentence}) and a note naming
where the paper states it; every finding has `relocated_to` in this mode.

`--relocated-in PATH` (repeatable; implies --relocated) limits story moves to the changes in PATH: the sentence a
caveat or number left, a new or changed sentence that took it and a headline must each lie inside one of them; a
sentence that already stated the caveat may lie anywhere in the section. PATH is a stage's run folder (its change
records in `changes/` and the proposals in its `findings.json`), one change record, or a YAML or JSON list of
passages (`passage`, `before`, `after`). A path that does not exist adds no passage, so nothing can move.

Requested claim changes (`--authorised FILE`): a YAML or JSON list of the claim changes something asked for,
one entry per change: `passage` (a verbatim, contiguous run of at least three words copied from the sentence as
it was before or after the edit), `finding` (what asked for it: a finding, proposal or referee comment id, or
"authors' request"; a list is allowed; `comment` with a referee comment id such as R2.4 is read the same way)
and optional `kinds` (the claim kinds it covers, such as causal or scope). A change record with `before`, `after`
and `finding_ids` (manuscript-dashboard's format) is read as it is; its `comment`, a question for the authors,
is not an id. A claim change whose sentence contains an entry's passage, or lies inside it, is matched: it gets
`authorised_by` (the ids), and a widened claim is authorised. Numbers, citations and identifiers are never
authorised this way. Entries that matched no change are listed (`authorisations.unused`): their edit may not
have landed. Every claim change gets `authorised_by` when the file is given, empty when nothing matched.

Revision mode (`--revision`): for an original and a revised manuscript where content changes are expected.
Lists every change of the kinds above with section and line, in the same fields, and exits 0, except with
`--authorised`: then a claim that widened (a higher rung, new generality, a lost scope, limiting, null-result or
evidence-status marker) or a declaration (below) with no matching entry exits 1, so the run restores its wording
without asking anyone. It also lists every deleted and new sentence and, for each rewritten sentence with no other
change, the words it lost and gained (kind "wording"), so each change can be shown before and after.

Declarations (kind "declaration", protected in both modes): a new, deleted or reworded sentence that declares what
only the authors can (consent, ethics approval or exemption, competing interests, funding, an author's
contribution or credit), found by its heading (Competing interests, Consent, Ethics, Funding, Author
contributions, Acknowledgements and the like) or a cue phrase ("consent was obtained", "declare no competing
interests", "funded by", "conceived the study"). A respelled word is not a change; a word an author's credit lost
is. An `--authorised` entry can cover one (the authors supplied the wording); `--allow-strengthening` never does.

The requested sections (`--only SECTION`, repeatable): the request covered these sections only, named by a heading
("Discussion" covers its subsections too) or a path of headings ("Results > Speed"), numbering and case set aside. A
sentence changed, moved, added or deleted anywhere else is listed under `only.outside` and fails, in either mode. A
name no heading carries is a usage error that lists the sections.

The summary against the body (`--summary`, one manuscript): each sentence of the title, the Abstract (or the text
before the first heading) and the Conclusions is compared with the body sentences about the same thing (sharing
three content words and a Dice similarity of 0.25; the Introduction and the back matter are neither summary nor
body). It fails when the summary claims more than every one of them (a higher rung on either ladder, or generality
wording) or leaves out a scope, limiting word, null result or evidence status that the closest one states (when that
one is 0.4 similar or more, and the summary part does not state it in another sentence). A title that names a topic
claims nothing and is skipped. Summary sentences no body sentence is close to are listed, never failed.

Moved text (`--moved-to FILE`, once per file): a sentence of BEFORE found in FILE is moved, not deleted (alignment
`moved_to_other_file`); one changed on the way is compared with its copy there (`after_file`, with `after_line` in
that file), and the whole-text counts do not report as removed what FILE holds (`moved_to`).

Exit codes: 0 no protected change (with --revision: no unrequested widening or declaration when --authorised is
given, else always), 1 a protected change or a change outside the `--only` sections (with --summary: a summary
sentence that claims more than the body or leaves out its limit), 2 usage error.
"""

from __future__ import annotations

import bisect
import functools
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Annotated, Callable, Optional

import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)

SMELL_PATTERNS = Path(__file__).resolve().parents[2] / "manuscript-deslop" / "references" / "smell-patterns.yaml"

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
LATEX_COMMENT = re.compile(r"(?<!\\)%.*$", re.MULTILINE)
# A `%` starts a comment only in LaTeX; in Markdown it is a percent sign and must not hide the rest of the line.
LATEX_SIGNS = re.compile(r"\\(?:documentclass|usepackage|begin\{|(?:sub)*section\*?\{|[a-zA-Z]*cite[a-z]*\*?[\[{]|"
                         r"emph\{|textbf\{|textit\{|label\{|ref\{)")

# Protected patterns: a count change warrants review; it does not by itself prove semantic drift.
PROTECTED: dict[str, re.Pattern[str]] = {
    "numbers": re.compile(
        r"(?<![\w.])[-+−]?\d[\d,]*(?:\.\d+)?(?:\s?(?:%|×|-fold|fold|bp|kb|Mb|Gb|GB|MB|TB|ms|s|min|h|°C))?(?![\w])"),
    "citations": re.compile(
        r"\((?:[^()]*?\b(?:19|20)\d{2}[a-z]?\b[^()]*?)\)|\[\d+(?:\s*[-–,]\s*\d+)*\]|\\cite[pt]?\*?\{[^}]+\}|@[A-Za-z][\w:-]+"),
    "identifiers": re.compile(
        r"\b10\.\d{4,9}/[^\s\"<>)\],;]+|\bPMID:?\s*\d{5,9}\b|\barXiv\W{0,3}\d{4}\.\d{4,5}\b|\brs\d{3,}\b|"
        r"\bPGS\d{6}\b|\bGCST\d+\b|\bENS[GTP]\d{11}\b|\bchr(?:\d{1,2}|[XYM]|MT)\b", re.IGNORECASE),
    "urls": re.compile(r"https?://[^\s)>\]]+"),
    "code": re.compile(r"`[^`\n]+`"),
    # Technical terms: tokens with a digit or several capitals (GRCh38, APOE, CYP2D6, VCF, PRS, MCP).
    "terms": re.compile(r"\b(?:[A-Za-z]+\d(?:[\w-]|\.\d)*|[A-Z]{2,}[\w-]*|[a-z]+[A-Z][\w-]*)\b"),
}

# Watched: a change may be fine, but each one can flip or strengthen a claim.
WATCHED: dict[str, re.Pattern[str]] = {
    "hedges": re.compile(
        r"\b(?:may|might|could|can|suggests?|suggested|likely|unlikely|possibly|potentially|appears?|appeared|"
        r"approximately|roughly|about|around|probably|perhaps|preliminary|tentative(?:ly)?|estimated?|"
        r"partly|partially|some|often|usually|typically)\b", re.IGNORECASE),
    "negations": re.compile(r"\b(?:not|no|never|none|nor|neither|without|cannot|n't|fails?|failed|lacks?|absent)\b",
                            re.IGNORECASE),
    "causal": re.compile(
        r"\b(?:causes?|caused|causal(?:ly)?|leads? to|led to|drives?|drove|determines?|determined|proves?|proved|"
        r"demonstrates?|demonstrated|shows?|showed|shown|establish(?:es|ed)?|confirms?|confirmed|guarantees?|"
        r"ensures?|ensured|results? in|resulted in|due to|because)\b", re.IGNORECASE),
    "comparatives": re.compile(
        r"\b(?:more|less|fewer|faster|slower|higher|lower|better|worse|greater|smaller|larger|first|only|all|"
        r"every|always|best|most|least)\b", re.IGNORECASE),
}


def _is_latex(text: str) -> bool:
    return bool(LATEX_SIGNS.search(text))


def _prose(text: str, latex: bool | None = None) -> str:
    """The text a reader sees: drop HTML comments (revision markers, notes) and, in LaTeX, `%` comments."""
    text = HTML_COMMENT.sub("", text)
    return LATEX_COMMENT.sub("", text) if (_is_latex(text) if latex is None else latex) else text


def _items(text: str, rx: re.Pattern[str]) -> Counter[str]:
    return Counter(" ".join(m.group(0).split()) for m in rx.finditer(text))


def _paragraphs(text: str) -> list[str]:
    return [" ".join(p.split()) for p in re.split(r"\n\s*\n", text) if p.strip()]


def _diff(before: Counter[str], after: Counter[str], moved: Counter[str] | None = None) -> dict[str, dict[str, int]]:
    """Items lost and gained. With `moved` (the counts in the files text was moved to), an item lost here but
    present there is not counted as removed."""
    gone = before - after
    removed = dict(gone - moved) if moved is not None else dict(gone)
    added = {k: after[k] - before[k] for k in after if after[k] > before[k]}
    return {"removed": removed, "added": added}


def _moved_items(before: Counter[str], after: Counter[str], moved: Counter[str]) -> dict[str, int]:
    """Items lost from the text that a file it was moved to accounts for."""
    return dict((before - after) & moved)


PAIR_LIMIT = 250_000  # paragraph pairs above which a changed run is paired by position, as a fallback


def _pair_paragraphs(a: list[str], b: list[str]) -> list[tuple[Optional[int], Optional[int]]]:
    """Pair the paragraphs of a changed run by their words, in order; an unpaired one was removed or added.
    Pairing by position matched a deleted table caption with the unchanged paragraph after it, and reported that
    paragraph as removed."""
    n, m = len(a), len(b)
    if n * m > PAIR_LIMIT:
        return [(k if k < n else None, k if k < m else None) for k in range(max(n, m))]
    wa, wb = [_content_words(p) for p in a], [_content_words(p) for p in b]
    neg = float("-inf")
    best = [[neg] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if best[i][j] == neg:
                continue
            steps = [(i + 1, j, 0.0), (i, j + 1, 0.0)]
            if i < n and j < m:
                sim = _dice(wa[i], wb[j])
                if sim >= MIN_SIMILARITY:
                    steps.append((i + 1, j + 1, sim * (len(wa[i]) + len(wb[j]) + 1)))
            for ni, nj, score in steps:
                if ni <= n and nj <= m and best[i][j] + score > best[ni][nj]:
                    best[ni][nj] = best[i][j] + score
                    back[ni][nj] = (i, j)
    pairs: list[tuple[Optional[int], Optional[int]]] = []
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj = back[i][j]  # type: ignore[misc]
        pairs.append((pi if pi < i else None, pj if pj < j else None))
        i, j = pi, pj
    return pairs[::-1]


def _rewritten_paragraphs(before: str, after: str, threshold: float,
                          moved: list[tuple[str, str]] | tuple[()] = ()) -> list[dict[str, object]]:
    """Paragraphs whose counterpart shares less than `threshold` of its characters. A removed paragraph whose
    copy is in a file the text was moved to is listed only when the copy kept less than `threshold`."""
    a, b = _paragraphs(before), _paragraphs(after)
    elsewhere = [(name, p, _content_words(p)) for name, text in moved for p in _paragraphs(text)]
    out: list[dict[str, object]] = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        for i, j in _pair_paragraphs(a[i1:i2], b[j1:j2]):
            old = a[i1 + i] if i is not None else ""
            new = b[j1 + j] if j is not None else ""
            target = None
            if old and not new and elsewhere:
                words = _content_words(old)
                sim, name, copy = max(((_dice(words, w), name, p) for name, p, w in elsewhere), key=lambda x: x[0])
                if sim >= MOVE_SIMILARITY:
                    target, new = name, copy
            ratio = SequenceMatcher(None, old, new, autojunk=False).ratio()
            if ratio < threshold:
                out.append({"similarity": round(ratio, 2), "before": old[:160], "after": new[:160],
                            "moved_to": target})
    return out


def change_rate(before: str, after: str) -> float:
    """Share of the original's words that did not survive in place (a word-level diff)."""
    a, b = before.split(), after.split()
    if not a:
        return 0.0
    kept = sum(block.size for block in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return round(1 - kept / len(a), 3)


CHANGE_WARN, CHANGE_STOP = 0.25, 0.50


# ---------------------------------------------------------------------------------------------------------------
# Sentences: segmentation with section and line, so every finding has a location
# ---------------------------------------------------------------------------------------------------------------

FRONT_MATTER = re.compile(r"\A---[ \t]*\n.*?\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.DOTALL)
FENCED_CODE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[^\n]*\n.*?^[ \t]{0,3}\1[ \t]*$", re.DOTALL | re.MULTILINE)
DISPLAY_MATH = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]|\\begin\{(equation|align|gather|multline|eqnarray|displaymath)"
                          r"(\*?)\}.*?\\end\{\1\2\}", re.DOTALL)
MD_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t#]*$")
TEX_HEADING = re.compile(r"^\s*\\(part|chapter|section|subsection|subsubsection)\*?(?:\[[^\]]*\])?\{(.*)\}\s*$")
TEX_LEVEL = {"part": 0, "chapter": 1, "section": 2, "subsection": 3, "subsubsection": 4}
TEX_ABSTRACT = re.compile(r"^\s*\\(begin|end)\{abstract\}\s*$")
# Structural LaTeX lines that hold no prose (a caption or footnote does, so it is not listed).
TEX_STRUCTURE = re.compile(
    r"^\s*\\(?:begin|end|label|includegraphics|maketitle|centering|bibliography|bibliographystyle|usepackage|"
    r"documentclass|newcommand|renewcommand|input|include|title|author|date|affil\w*|keywords|tableofcontents|"
    r"clearpage|newpage|vspace|hspace|hline|toprule|midrule|bottomrule|noindent|appendix|small|footnotesize)\b"
    r"\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})*\s*$")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$|^[^\n]*&[^\n]*\\\\\s*$")
LIST_ITEM = re.compile(r"^(\s*(?:[-*+]|\d{1,3}[.)]|\\item(?:\[[^\]]*\])?)\s+)")
BOUNDARY = re.compile(r"[.!?][\"'”’)\]]*(?:\[[\d,\s–-]+\])?(?=[\s\x00]*\s[\s\x00]*[\"'“‘(\[*_\\$~]*[A-Z0-9])")
ABBREVIATIONS = {
    "al", "e.g", "i.e", "fig", "figs", "eq", "eqs", "ref", "refs", "tab", "no", "nos", "vs", "cf", "approx", "ca",
    "dr", "prof", "mr", "ms", "mrs", "st", "suppl", "sect", "sec", "ch", "vol", "pp", "resp", "incl", "est", "inc",
    "ltd", "co", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "sp", "spp",
    "var", "ed", "eds", "viz", "chr",
}
WORD = re.compile(r"[^\W\d_][\w'’-]*|\d+(?:[.,]\d+)*")
STOPWORDS = frozenset(
    "the a an of in on for to and or with by at from as is are was were be been being this that these those it its "
    "we our us which who whom whose than then there their they them has have had into onto over under also such "
    "both each other more most less very can will would should".split())


@dataclass
class Sentence:
    text: str          # the sentence as a reader sees it (comments removed), whitespace collapsed
    line: int          # 1-based line of its first character in the file
    block: int         # paragraph index (blank lines and headings separate paragraphs)
    section: str       # heading path, e.g. "Results > Performance"
    words: frozenset[str]
    file: Optional[str] = None  # set for a sentence of a file the text was moved to (--moved-to)


HIDDEN = "\x00"  # an inline comment: removed from the sentence text, but keeps every offset


def _spaces(m: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", m.group(0))


def _hidden(m: re.Match[str]) -> str:
    return re.sub(r"[^\n]", HIDDEN, m.group(0))


def _mask(text: str, latex: bool) -> str:
    """Blank out what is not prose while keeping every offset, so lines stay correct."""
    out = FRONT_MATTER.sub(_spaces, text)
    out = HTML_COMMENT.sub(_hidden, out)
    if latex:
        out = LATEX_COMMENT.sub(_hidden, out)
    out = FENCED_CODE.sub(_spaces, out)
    return DISPLAY_MATH.sub(_spaces, out)


def _clean_title(title: str) -> str:
    return " ".join(re.sub(r"\\[A-Za-z]+\*?|[{}*_`]", "", title).split())


def _content_words(text: str) -> frozenset[str]:
    return frozenset(w for w in (t.lower() for t in WORD.findall(text)) if w not in STOPWORDS and len(w) > 1)


def _is_abbreviation(chunk: str, dot: int) -> bool:
    prev = re.search(r"([A-Za-z][A-Za-z.]*)$", chunk[:dot])
    if not prev:
        return False
    word = prev.group(1)
    return (word.lower().rstrip(".") in ABBREVIATIONS or bool(re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]?", word))
            or bool(re.fullmatch(r"[A-Z]", word)))


def segment(text: str, file: Optional[str] = None, block_base: int = 0) -> list[Sentence]:
    """Split a Markdown or LaTeX manuscript into sentences with line, paragraph and section. A file the text was
    moved to is segmented with its name and a paragraph numbering of its own (`block_base`)."""
    latex = _is_latex(text)
    masked = _mask(text, latex)
    line_starts = [0] + [m.end() for m in re.finditer(r"\n", text)]
    out: list[Sentence] = []
    headings: list[tuple[int, str]] = []
    block = 0
    chunk: list[int] = []  # [start, end) of the running prose chunk

    def section() -> str:
        return " > ".join(t for _, t in headings)

    def emit(start: int, end: int, split: bool) -> None:
        piece = masked[start:end]
        cuts = [0]
        if split:
            cuts += [m.end() for m in BOUNDARY.finditer(piece) if not _is_abbreviation(piece, m.start())]
        cuts.append(len(piece))
        for a, b in zip(cuts, cuts[1:]):
            raw = piece[a:b].replace(HIDDEN, "")
            body = " ".join(raw.split())
            if not re.search(r"[A-Za-z]", body):
                continue
            offset = start + a + (len(piece[a:b]) - len(piece[a:b].lstrip(" \t\n\r" + HIDDEN)))
            out.append(Sentence(body, bisect.bisect_right(line_starts, offset), block_base + block, section(),
                                _content_words(body), file))

    def flush() -> None:
        if chunk:
            emit(chunk[0], chunk[1], True)
            chunk.clear()

    pos = 0
    previous_blank = True
    for raw_line in masked.split("\n"):
        start, end = pos, pos + len(raw_line)
        pos = end + 1
        line = raw_line.rstrip("\r")
        if not line.replace(HIDDEN, "").strip():
            flush()
            if not previous_blank:
                block += 1
            previous_blank = True
            continue
        previous_blank = False
        md, tex = MD_HEADING.match(line), TEX_HEADING.match(line)
        if md or tex:
            flush()
            level = len(md.group(1)) if md else TEX_LEVEL[tex.group(1)]
            title = _clean_title(md.group(2) if md else tex.group(2))
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, title))
            block += 1
            continue
        abstract = TEX_ABSTRACT.match(line) if latex else None
        if abstract:  # \begin{abstract} ... \end{abstract} is the Abstract, as a heading would be
            flush()
            if abstract.group(1) == "begin":
                headings.append((TEX_LEVEL["section"], "Abstract"))
            elif headings and headings[-1] == (TEX_LEVEL["section"], "Abstract"):
                headings.pop()
            block += 1
            continue
        if latex and TEX_STRUCTURE.match(line):
            flush()
            continue
        if TABLE_ROW.match(line):
            flush()
            if not re.fullmatch(r"[\s|:\-+]+", line):
                emit(start, end, False)
            continue
        item = LIST_ITEM.match(line)
        if item:
            flush()
            chunk.extend([start + len(item.group(1)), end])
            continue
        if chunk:
            chunk[1] = end
        else:
            chunk.extend([start, end])
    flush()
    return out


# ---------------------------------------------------------------------------------------------------------------
# Alignment: identical sentences anchor; changed runs are aligned 1:1, split (1:2, 1:3) or merged (2:1, 3:1)
# ---------------------------------------------------------------------------------------------------------------

MIN_SIMILARITY, MOVE_SIMILARITY = 0.3, 0.5
# Each sentence of a split or merge must lend the other side at least this share of its content words. Without
# it, a dropped sentence next to a rewritten one rode along in a 2:1 "merge" on its neighbour's similarity and was
# never reported.
MIN_CONTRIBUTION = 0.3
# A deleted sentence most of whose words (this share) sit in one sentence of the edited text was probably merged
# into it across a paragraph boundary; the report says where.
MERGED_ELSEWHERE = 0.6


@dataclass
class Group:
    before: list[int]
    after: list[int]
    kind: str  # equal | changed | split | merged | moved | moved_out | deleted | inserted


def _dice(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


def _contributes(members: list[frozenset[str]], other: frozenset[str]) -> bool:
    """Every sentence of the larger side of a split or merge shares some of its words with the other side."""
    return all(not w or len(w & other) / len(w) >= MIN_CONTRIBUTION for w in members)


def _align_run(bs: list[Sentence], as_: list[Sentence], ib: list[int], ia: list[int]) -> list[Group]:
    """Best monotone alignment of a run of changed sentences (dynamic programming over group shapes)."""
    n, m = len(ib), len(ia)
    shapes = ((1, 0), (0, 1), (1, 1), (2, 1), (1, 2), (3, 1), (1, 3))
    band = (15 + abs(n - m)) if n * m > 2500 else None
    neg = float("-inf")
    best = [[neg] * (m + 1) for _ in range(n + 1)]
    back: list[list[tuple[int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    union_b: dict[tuple[int, int], frozenset[str]] = {}
    union_a: dict[tuple[int, int], frozenset[str]] = {}

    def words(cache: dict[tuple[int, int], frozenset[str]], seq: list[Sentence], idx: list[int], a: int, b: int):
        if (a, b) not in cache:
            cache[(a, b)] = frozenset().union(*(seq[idx[k]].words for k in range(a, b)))
        return cache[(a, b)]

    for i in range(n + 1):
        for j in range(m + 1):
            current = best[i][j]
            if current == neg:
                continue
            for di, dj in shapes:
                ni, nj = i + di, j + dj
                if ni > n or nj > m or (band is not None and abs(ni * m / max(n, 1) - nj) > band):
                    continue
                score = 0.0
                if di and dj:
                    wb, wa = words(union_b, bs, ib, i, ni), words(union_a, as_, ia, j, nj)
                    sim = _dice(wb, wa)
                    if sim < MIN_SIMILARITY:
                        continue
                    if di > 1 and not _contributes([bs[ib[k]].words for k in range(i, ni)], wa):
                        continue
                    if dj > 1 and not _contributes([as_[ia[k]].words for k in range(j, nj)], wb):
                        continue
                    score = sim * (len(wb) + len(wa) + 1)
                if current + score > best[ni][nj]:
                    best[ni][nj] = current + score
                    back[ni][nj] = (i, j)
    groups: list[Group] = []
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj = back[i][j]  # type: ignore[misc]
        before, after = ib[pi:i], ia[pj:j]
        kind = ("deleted" if not after else "inserted" if not before else "changed" if len(before) == len(after)
                else "split" if len(after) > len(before) else "merged")
        groups.append(Group(before, after, kind))
        i, j = pi, pj
    return groups[::-1]


def _pair_best_first(pairs: list[tuple[float, int, int]], floor: float) -> list[tuple[int, int]]:
    """Greedy one-to-one pairing, most similar first, of (similarity, left, right) candidates at or above floor."""
    used_l: set[int] = set()
    used_r: set[int] = set()
    out = []
    for sim, left, right in sorted(pairs, reverse=True):
        if sim < floor:
            break
        if left in used_l or right in used_r:
            continue
        used_l.add(left)
        used_r.add(right)
        out.append((left, right))
    return out


def align(bs: list[Sentence], as_: list[Sentence], external: list[Sentence] | tuple[Sentence, ...] = ()) -> list[Group]:
    """Align the sentences of two versions. `external` holds the sentences of files the text was moved to; a
    group of kind "moved_out" points into them, at index len(as_) + k."""
    groups: list[Group] = []
    keys_b, keys_a = [s.text for s in bs], [s.text for s in as_]
    # A sentence copied word for word into a file the text was moved to has left; it does not enter the alignment
    # of what stayed, where it could be paired with an unrelated new sentence.
    verbatim: dict[str, list[int]] = {}
    for k, s in enumerate(external):
        verbatim.setdefault(s.text, []).append(len(as_) + k)
    taken: set[int] = set()
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, keys_b, keys_a, autojunk=False).get_opcodes():
        if tag == "equal":
            groups += [Group([i1 + k], [j1 + k], "equal") for k in range(i2 - i1)]
            continue
        staying = []
        run_after = set(keys_a[j1:j2])
        for i in range(i1, i2):
            free = [k for k in verbatim.get(bs[i].text, []) if k not in taken]
            if free and bs[i].text not in run_after:
                taken.add(free[0])
                groups.append(Group([i], [free[0]], "moved_out"))
            else:
                staying.append(i)
        groups += _align_run(bs, as_, staying, list(range(j1, j2)))
    # A sentence moved out of its run: pair leftover deletions and insertions by similarity, best first.
    deleted = [g for g in groups if g.kind == "deleted"]
    inserted = [g for g in groups if g.kind == "inserted"]
    for di, ai in _pair_best_first([(_dice(bs[d.before[0]].words, as_[a.after[0]].words), di, ai)
                                    for di, d in enumerate(deleted) for ai, a in enumerate(inserted)], MOVE_SIMILARITY):
        inserted[ai].before, inserted[ai].kind = deleted[di].before, "moved"
        deleted[di].kind = "absorbed"
    # A sentence moved to another file with changes: pair what is still deleted with that file's sentences.
    deleted = [g for g in groups if g.kind == "deleted"]
    free = [k for k in range(len(external)) if len(as_) + k not in taken]
    for di, k in _pair_best_first([(_dice(bs[d.before[0]].words, external[k].words), di, k)
                                   for di, d in enumerate(deleted) for k in free], MOVE_SIMILARITY):
        deleted[di].after, deleted[di].kind = [len(as_) + k], "moved_out"
    return [g for g in groups if g.kind != "absorbed"]


# ---------------------------------------------------------------------------------------------------------------
# Claim markers (references/claim-ladders.md explains each list)
# ---------------------------------------------------------------------------------------------------------------

Filter = Callable[[str, int, int], bool]

FIGURE_WORDS = re.compile(r"\b(?:fig(?:ure)?s?|tables?|panels?|insets?|diagrams?|schematics?|supplementary|"
                          r"appendix|box|screenshots?|below|above|example)\b", re.IGNORECASE)
PROCEDURAL_OBJECT = re.compile(
    r"^\s+(?:(?:a|an|the|our|new|its|their)\s+)?(?:[\w-]+\s+){0,2}?(?:baselines?|protocols?|pipelines?|frameworks?|"
    r"cohorts?|databases?|resources?|collaborations?|workflows?|colon(?:y|ies)|lines?|cultures?|criteria|standards?|"
    r"benchmarks?|registr(?:y|ies)|consortium|repositor(?:y|ies)|partnerships?|receipt|identity|configuration|"
    r"setup|installation|methods?|tools?|practices?|guidelines?|techniques?|software)\b", re.IGNORECASE)


def _not_descriptive(text: str, start: int, end: int) -> bool:
    """'Figure 2 shows the layout' describes a figure; 'Figure 2 shows that X' still makes a claim."""
    following = text[end:end + 30]
    if re.match(r"\s+that\b", following, re.IGNORECASE):
        return True
    if re.match(r"\s+(?:as|together|below|above|alongside|side by side|on (?:the|a) (?:left|right|map|screen|page))\b",
                following, re.IGNORECASE):
        return False
    return not FIGURE_WORDS.search(text[max(0, start - 30):end + 30])


def _not_procedural(text: str, start: int, end: int) -> bool:
    """'established a pipeline', 'confirmed the configuration', 'well-established methods' are not proof."""
    if re.search(r"well[- ]$", text[max(0, start - 5):start], re.IGNORECASE):
        return False
    return not PROCEDURAL_OBJECT.match(text[end:end + 60])


def _not_clearly_modifier(text: str, start: int, end: int) -> bool:
    return not re.match(r"\s+(?:defined|separated|visible|label+ed|distinct|stated|marked|shown in)\b", text[end:],
                        re.IGNORECASE)


@dataclass(frozen=True)
class Rung:
    level: int
    name: str
    rx: re.Pattern[str]
    keep: Optional[Filter] = None


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


# Causal force. A sentence with no marker states a plain relation and sits at rung 4 ("affects").
CAUSAL: tuple[Rung, ...] = (
    Rung(0, "compatibility", _rx(r"\b(?:consistent|compatible|in line|in keeping) with\b")),
    Rung(1, "association", _rx(
        r"\bassociat(?:es|ed|ion|ions) (?:with|between)\b|\bassociations? of\b|\bcorrelat(?:es|ed|ion|ions) "
        r"(?:with|between)\b|\b(?:is|are|was|were) (?:\w+ )?(?:linked|related) (?:to|with)\b|"
        r"\blinked (?:[\w-]+ ){1,4}?(?:to|with)\b|\blinks? between\b|\bco-?occur(?:s|red|ring)? with\b|"
        r"\benriched (?:in|for|among)\b")),
    Rung(2, "prediction", _rx(r"\bpredict(?:s|ed|ing)?\b|\bpredictive (?:of|for)\b|\bpredictors? of\b|"
                              r"\bprognostic (?:for|of)\b|\bforecasts?\b")),
    Rung(3, "contribution", _rx(
        r"\bcontribut(?:es|ed|ing|e|ion|ions) (?:\w+ ){0,3}?to\b|\bplay(?:s|ed|ing)? an? (?:[\w-]+ ){0,2}?role in\b|"
        r"\b(?:is|are|was|were|be|been) involved in\b|\bparticipat(?:es|ed|e) in\b|\bmodulat(?:es|ed|e)\b|"
        r"\binfluenc(?:es|ed|e)\b")),
    Rung(4, "effect", _rx(
        r"\baffect(?:s|ed|ing)?\b(?! (?:individuals|patients|carriers|relatives|members|samples|subjects|tissues?|"
        r"cases|families|siblings|people|participants|genes?)\b)|\b(?:leads?|leading|led) to\b|"
        r"\bresult(?:s|ed|ing)? in\b|\b(?:gives?|gave|giving) rise to\b|\binduc(?:es|ed|e|ing)\b|"
        r"\bpromot(?:es|ed|e|ing)\b|\binhibit(?:s|ed|ing)?\b|\bprevent(?:s|ed|ing)?\b|\bprotect(?:s|ed|ing)? against\b|"
        r"\b(?:increas|decreas|reduc|lower|rais|elevat)(?:es|ed|e|ing|s)? the (?:risk|odds|likelihood|incidence|"
        r"probability) of\b")),
    Rung(5, "causation", _rx(
        r"\bcaus(?:es|ed|ing|e|al|ally|ative|ation)\b|\bdriv(?:es|en|ing|e)\b|\bdrove\b|\bdrivers? of\b|"
        r"\bdetermined by\b|\bdetermines\b|\b(?:is|are|was|were) (?:\w+ )?responsible for\b|\bunderl(?:ies|ie|ay)\b|"
        r"\bmediat(?:es|ed|e|ing)\b")),
)
CAUSAL_PLAIN = 4

# Evidential force. A sentence with no marker is a plain assertion and sits at rung 3 ("shows").
EVIDENTIAL: tuple[Rung, ...] = (
    Rung(0, "possibility", _rx(
        r"\b(?:may)\b(?!\s+\d)|\b(?:might|could|possibly|potentially|perhaps|conceivably|plausibly|likely|unlikely|"
        r"probably)\b|\b(?:appears?|appeared|seems?|seemed) to\b|\bit is possible that\b|"
        r"\bwe (?:speculate|hypothesi[sz]e)\b")),
    Rung(1, "suggestion", _rx(r"\bsuggest(?:s|ed|ing|ive of)?\b|\bhint(?:s|ed)? (?:at|that)\b|"
                              r"\bpoint(?:s|ed)? (?:to|towards)\b")),
    Rung(2, "indication", _rx(
        r"(?<!as )\bindicat(?:es|ed|e|ing)\b|\bsupport(?:s|ed|ing)? (?:the|our|this|a|an|these) (?:[\w-]+ ){0,2}?"
        r"(?:hypothes[ie]s|conclusions?|notion|idea|view|interpretation|claim|model|role|link)\b|"
        r"\b(?:provides?|provided|is|are|was|were|offers?) (?:\w+ )?evidence (?:for|that|of)\b")),
    Rung(3, "demonstration", _rx(r"\bshow(?:s|ed|n|ing)?\b|\bdemonstrat(?:es|ed|e|ing)\b|\breveal(?:s|ed|ing)?\b|"
                                 r"\b(?:find|finds|found) that\b"), _not_descriptive),
    Rung(4, "proof", _rx(r"\bprov(?:es|ed|en|e|ing)\b|\bproof (?:of|that)\b|\bestablish(?:es|ed|ing)?\b|"
                         r"\bconfirm(?:s|ed|ing)?\b|\bguarantee(?:s|d)?\b"), _not_procedural),
    Rung(4, "proof", _rx(r"\bconclusive(?:ly)?\b|\bdefinitive(?:ly)?\b|\bunequivocal(?:ly)?\b|\bunambiguous(?:ly)?\b|"
                         r"\bbeyond (?:any |reasonable )?doubt\b|\birrefutabl[ey]\b|\bundoubtedly\b|\bcertainly\b|"
                         r"\bunquestionabl[ey]\b|\bclearly\b"), _not_clearly_modifier),
)
EVIDENTIAL_PLAIN = 3

GENERALITY: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("novelty", _rx(
        r"\bfor the first time\b|\b(?:the|a) first (?:[\w-]+ ){0,2}?(?:study|studies|report|tool|method|approach|"
        r"framework|demonstration|analysis|evidence|description|map|atlas|resource|implementation|account|alternative|"
        r"platform|pipeline|system|model|software|assay|test|solution|database|benchmark|application)\b|\bfirst-ever\b|"
        r"\bnovel\b|\bunprecedented\b|\bpioneering\b|\bgroundbreaking\b|\bstate-of-the-art\b")),
    ("generality", _rx(
        r"\balways\b|\binvariably\b|\buniversal(?:ly)?\b|\bin (?:all|every) (?:[\w-]+ ){0,1}?(?:cases?|settings?|"
        r"populations?|patients|individuals|samples|species|tissues|conditions|contexts?|cohorts?)\b|"
        r"\bacross all\b|\bregardless of\b|\birrespective of\b|\bgenerali[sz]able\b|"
        r"\bbroadly applicable\b|\bin any (?:[\w-]+ )?(?:setting|population|"
        r"species|tissue|genome|context)\b")),
)

ANCESTRY = (r"european|east asian|south asian|african(?:[- ]american)?|hispanic|latin[oax]|latinx|asian|japanese|"
            r"chinese|han chinese|korean|finnish|british|white|black|caucasian|admixed|indigenous|native american|"
            r"ashkenazi(?: jewish)?")
MODEL_CANON = {"mice": "mouse", "murine": "mouse", "rats": "rat", "rodents": "rodent", "flies": "fly",
               "fruit flies": "fly", "drosophila": "fly", "worms": "worm", "nematodes": "worm", "c. elegans": "worm",
               "cell lines": "cells", "cell line": "cells", "cultured cells": "cells", "cell cultures": "cells",
               "cell culture": "cells", "animals": "animal", "animal models": "animal", "animal model": "animal",
               "organoids": "organoid", "xenografts": "xenograft", "macaques": "primate", "monkeys": "primate",
               "primates": "primate", "pigs": "pig", "dogs": "dog", "plants": "plant", "e. coli": "bacteria"}
BUILD_CANON = {"hg38": "grch38", "hg19": "grch37", "chm13": "t2t-chm13", "t2t": "t2t-chm13"}

# Scope rules in priority order: an earlier rule claims its span, so one phrase is counted once.
SCOPE: tuple[tuple[re.Pattern[str], Callable[[re.Match[str]], str]], ...] = (
    (_rx(r"\b(?:in|within) (?:this|the present|the current|our) (?:study|paper|work|article|manuscript|report)\b"),
     lambda m: "this-study"),
    (_rx(r"\b(?:in|within|across|among|from|on|for) (?:this|these|our|the present|the current|the studied|the tested|"
         r"the analy[sz]ed|the evaluated|the investigated|the sampled|the included) (?:[\w-]+ ){0,2}?(?:cohorts?|"
         r"samples?|datasets?|data|populations?|settings?|trials?|benchmarks?|participants|patients|individuals|"
         r"subjects|genomes|exomes|families|animals|cells|experiments?|analys[ie]s|systems?)\b|\bin our hands\b"),
     lambda m: "this-data"),
    (_rx(r"\bunder (?:these|the (?:tested|studied|experimental|present|current|same|given)|our|such|standard|"
         r"laboratory|controlled|experimental) conditions\b|\b(?:at|for|within|over) the (?:tested|studied|examined|"
         r"evaluated|investigated) (?:[\w-]+ ){0,2}?(?:ranges?|doses?|concentrations?|temperatures?|conditions|values|"
         r"parameters|settings)\b"),
     lambda m: "conditions"),
    (re.compile(rf"\b({ANCESTRY})[- ](?:ancestry|ancestries|descent|origin|populations?|individuals|participants|"
                rf"samples|cohorts?)\b|\bof ({ANCESTRY}) (?:ancestry|descent|origin)\b", re.IGNORECASE),
     lambda m: "ancestry:" + (m.group(1) or m.group(2)).lower()),
    (_rx(r"\bin (?:some|several|certain|selected|a few|most|many|a (?:subset|subgroup|minority|fraction|proportion) of)"
         r" (?:[\w-]+ ){0,2}?(?:cohorts?|patients|participants|individuals|samples|cases|studies|tissues|cell types|"
         r"conditions|settings|populations|genomes|datasets|species|strains|families|subjects)\b|"
         r"\bin (?:a |one )?subgroups?\b"),
     lambda m: "subset"),
    (_rx(r"\b(?:in vitro|in vivo|in silico|ex vivo|in situ|in utero)\b"), lambda m: " ".join(m.group(0).lower().split())),
    (_rx(r"\bin (?:a |an |the )?(?:[\w-]+ ){0,2}?(mice|mouse|murine|rats?|rodents?|zebrafish|fruit flies|flies|"
         r"drosophila|yeast|worms|nematodes|c\. elegans|primates|macaques|monkeys|pigs|dogs|animal models?|animals|"
         r"xenografts?|organoids|cell lines?|cultured cells|cell cultures?|cells|plants|arabidopsis|bacteria|"
         r"e\. coli)\b"),
     lambda m: "model:" + MODEL_CANON.get(m.group(1).lower(), m.group(1).lower())),
    (_rx(r"\bin (?:[\w-]+ ){0,2}?(humans|people|persons|patients|adults|children|adolescents|infants|neonates|men|"
         r"women|males|females|older adults|elderly|volunteers|twins|carriers|non-carriers)\b"),
     lambda m: "people:" + m.group(1).lower()),
    (_rx(r"\b(?:in|on|from|with|using) (?:the )?(simulated|synthetic|real|public|benchmark|training|validation|test|"
         r"held-out|independent|external|discovery|replication) (?:data|datasets?|sets?|cohorts?|samples|genomes|"
         r"reads|splits?)\b|\bin simulations?\b|\b(internally|externally) validated\b"),
     lambda m: "data:" + (m.group(1) or m.group(2) or "simulation").lower()),
    # A reference build bounds a genomic result: "on GRCh38" and "hg38" are the same build.
    (_rx(r"\b(GRCh3[78]|hg1[89]|hg38|T2T-CHM13|CHM13|T2T)\b"),
     lambda m: "build:" + BUILD_CANON.get(m.group(1).lower(), m.group(1).lower())),
)

NULL_RESULT = _rx(
    r"\bno (?:statistically )?significant\b|\bnot (?:statistically )?significant(?:ly)?\b|\bnon-?significant(?:ly)?\b|"
    r"\binsignificant(?:ly)?\b|\b(?:did|does|do) not (?:\w+ )?(?:differ|change|improve|reduce|increase|decrease|affect|"
    r"alter|predict|replicate|reach|associate|correlate|vary|survive|show|detect|find|support)\b|"
    r"\b(?:was|were|is|are|been) not (?:\w+ )?(?:associated|correlated|different|changed|altered|enriched|affected|"
    r"predictive|related|detected|replicated|observed|improved|reduced|increased)\b|"
    r"\bno (?:[\w-]+ ){0,2}?(?:association|associations|difference|differences|effect|effects|correlation|enrichment|"
    r"evidence|improvement|change|signal|relationship|benefit|link|increase|decrease|reduction)\b|"
    r"\bfail(?:s|ed)? to (?:\w+ )?(?:replicate|reach|detect|show|improve|reduce|predict|find|support|differ)\b|"
    r"\b(?:remained|was|were|is|are) unchanged\b|\bnull (?:results?|findings?|associations?|effects?)\b|"
    r"\bn\.s\.|\b[pP]\s*[>≥]\s*0?\.0[15]\b|\bno longer significant\b|\blost significance\b|\bnot replicated\b")

EVIDENCE_STATUS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("self-reported", _rx(r"\b(?:self|patient|participant|parent|caregiver|proxy|user)[- ]?report(?:ed|s)?\b")),
    ("reported", _rx(r"\breport(?:ed|edly)\b")),
    ("perceived", _rx(r"\bperceived\b|\bsubjective(?:ly)?\b")),
    ("predicted", _rx(r"\b(?:in silico |computationally )?predicted\b")),
    ("putative", _rx(r"\bputative(?:ly)?\b|\bpresum(?:ed|ptive)\b|\bsuspected\b|\bcandidate\b")),
    ("estimated", _rx(r"\bestimated\b|\bestimates?\b|\bimputed\b|\binferred\b|\bmodell?ed\b|\bsimulated\b|"
                      r"\bprojected\b|\bextrapolated\b|\bapproximated\b")),
    ("observed", _rx(r"\bobserved\b|\bmeasured\b|\bdetected\b|\brecorded\b|\bvalidated\b")),
)

# Limiting and concessive words ("tested on only four genomes", "Albeit tested on four genomes, ..."): losing one
# presents the evidence as broader than the authors wrote. A contrastive connector can carry the concession after a
# restructure ("Although X, Y" → "X. However, Y"), so it offsets a lost word; its own loss is a glue cut.
LIMITING = _rx(r"\bonly\b|\bmere(?:ly)?\b|\bsolely\b|\bas few as\b|\b(?:limited|restricted) to\b|"
               r"\bjust (?=(?:\d|one|two|three|four|five|six|seven|eight|nine|ten|a few|a handful|a single)\b)")
CONCESSIVE = _rx(r"\balbeit\b|\b(?:even )?(?:al)?though\b|\beven if\b|\bdespite\b|\bin spite of\b|"
                 r"\bnotwithstanding\b|\bwhil(?:e|st)\b")
CONTRASTIVE = _rx(r"\bhowever\b|\bbut\b|\byet\b|\bnevertheless\b|\bnonetheless\b|\bwhereas\b")
NOT_LIMITING = _rx(r"\b(?:not|the|an|its|their|our|if)\s+$")  # not only, the only tool, if only, not limited to


def _limitation_marks(text: str) -> tuple[list[str], int]:
    """Limiting and concessive words in a sentence, and the number of contrastive connectors that can stand in."""
    strong: list[str] = []
    offsets = len(CONTRASTIVE.findall(text))
    for rx in (LIMITING, CONCESSIVE):
        for m in rx.finditer(text):
            word = " ".join(m.group(0).lower().split())
            prefix = text[max(0, m.start() - 8):m.start()]
            if rx is LIMITING and NOT_LIMITING.search(prefix) or word == "though" and re.search(r"\bas\s+$", prefix):
                continue
            preceding = text[:m.start()].rstrip()
            if word.startswith("whil") and preceding and preceding[-1] not in ".;:(\"“*_":
                offsets += 1  # "X rose, while Y fell" contrasts; only a clause-initial "While X, Y" concedes
                continue
            strong.append(word)
    return strong, offsets


NEGATION = _rx(r"\b(?:not|no|never|none|nor|neither|without|cannot|absent|lacks?|lacked|lacking)\b|n['’]t\b")
FIRST_PERSON = _rx(r"\b(?:we|our|us)\b")


def _reported_is_status(text: str, start: int, end: int) -> bool:
    """'participants reported' is a status; 'we report', 'the reported benchmarks' and 'reported in Table 2' are not."""
    if re.search(r"\b(?:we|here|this (?:study|paper|article|work))\s+$", text[max(0, start - 20):start], re.IGNORECASE):
        return False
    if re.search(r"\b(?:the|our|these|those)\s+$", text[max(0, start - 8):start], re.IGNORECASE):
        return False  # "the reported benchmarks" names the paper's own results, not a self-report
    return not re.match(r"\s+(?:in|at)\s+(?:table|fig|figure|supplementary|section|appendix|box)", text[end:end + 30],
                        re.IGNORECASE)


def _ladder(text: str, rungs: tuple[Rung, ...]) -> list[tuple[int, str, str]]:
    found = []
    for rung in rungs:
        for m in rung.rx.finditer(text):
            if rung.keep is None or rung.keep(text, m.start(), m.end()):
                found.append((rung.level, rung.name, " ".join(m.group(0).lower().split())))
    return found


def _scope_keys(text: str) -> list[tuple[str, str]]:
    taken: list[tuple[int, int]] = []
    keys = []
    for rx, key in SCOPE:
        for m in rx.finditer(text):
            if any(m.start() < b and a < m.end() for a, b in taken):
                continue
            taken.append(m.span())
            keys.append((key(m), " ".join(m.group(0).split())))
    return keys


def _status_keys(text: str) -> list[tuple[str, str]]:
    taken: list[tuple[int, int]] = []
    keys = []
    for key, rx in EVIDENCE_STATUS:
        for m in rx.finditer(text):
            if any(m.start() < b and a < m.end() for a, b in taken):
                continue
            if key == "reported" and not _reported_is_status(text, m.start(), m.end()):
                continue
            taken.append(m.span())
            keys.append((key, m.group(0).lower()))
    return keys


def _scope_sides(tb: str, ta: str, survives: bool) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Scope keys of a sentence before and after. "In this study" is framing, not scope, when the sentence was
    deleted or keeps a first person ("In this study, we show" → "We show")."""
    sb, sa = _scope_keys(tb), _scope_keys(ta)
    if not survives or FIRST_PERSON.search(ta):
        sb = [(k, s) for k, s in sb if k != "this-study"]
    return sb, sa


def _null_marks(text: str) -> list[str]:
    return [m.group(0).lower() for m in NULL_RESULT.finditer(text)]


def _keyed_diff(before: list[tuple[str, str]], after: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    """Surface forms of keys that lost or gained occurrences; synonyms within one key are not a change."""
    kb, ka = Counter(k for k, _ in before), Counter(k for k, _ in after)
    removed = [s for k in kb - ka for s in _surfaces(before, k)]
    added = [s for k in ka - kb for s in _surfaces(after, k)]
    return removed, added


def _surfaces(pairs: list[tuple[str, str]], key: str) -> list[str]:
    return sorted({s for k, s in pairs if k == key})


def _strength(markers: list[tuple[int, str, str]], plain: int) -> tuple[int, int]:
    levels = [level for level, _, _ in markers] + [plain]
    return min(levels), max(levels)


def _direction(before: list[tuple[int, str, str]], after: list[tuple[int, str, str]], plain: int) -> str | None:
    bmin, bmax = _strength(before, plain)
    amin, amax = _strength(after, plain)
    up, down = amin > bmin or amax > bmax, amin < bmin or amax < bmax
    return "mixed" if up and down else "raised" if up else "lowered" if down else None


def _rung_names(markers: list[tuple[int, str, str]]) -> str:
    names = [name for _, name, _ in sorted(set(markers))]
    return "+".join(dict.fromkeys(names)) or "plain statement"


# ---------------------------------------------------------------------------------------------------------------
# Numbers, citations and identifiers per sentence
# ---------------------------------------------------------------------------------------------------------------

CITE_TEX = re.compile(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\]){0,2}\{([^}]+)\}")
CITE_PANDOC = re.compile(r"(?<![\w.])@([A-Za-z][\w:.#$%&+?<>~/-]*[\w])")
CITE_NUMERIC = re.compile(r"\[(\d+(?:\s*[-–—,]\s*\d+)*)\]")
CITE_PAREN = re.compile(r"\((?:[^()]*?\b(?:19|20)\d{2}[a-z]?\b[^()]*?)\)")
SURNAME = r"(?:(?:van|von|de|del|der|den|la|le|du) )*[A-ZÀ-ÖØ-ÞĀ-Ž][^\W\d_]*(?:['’\-][^\W\d_]+)*"
AUTHOR_YEAR = re.compile(rf"({SURNAME})(?:\s+(?:et al\.?|(?:and|&) {SURNAME}))?,?\s+((?:19|20)\d{{2}}[a-z]?)")
NARRATIVE = re.compile(rf"({SURNAME})(?:\s+(?:et al\.?|(?:and|&) {SURNAME}))?\s+\(((?:19|20)\d{{2}}[a-z]?)\)")
TEX_POINTERS = re.compile(r"\\(?:[a-zA-Z]*ref|label|url|href|includegraphics|input|include)\*?(?:\[[^\]]*\])?\{[^}]*\}")
TOKEN_KINDS = ("number", "citation", "identifier")


def _blank_spans(text: str, spans: list[tuple[int, int]]) -> str:
    chars = list(text)
    for a, b in spans:
        chars[a:b] = " " * (b - a)
    return "".join(chars)


def _norm_number(s: str) -> str:
    s = s.replace("−", "-").replace("\u2009", "").replace("\u00a0", "").replace(" ", "")
    return re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s).lower()


def _expand_numeric(group: str) -> list[int]:
    """'1-3, 5' → [1, 2, 3, 5], so adding reference 4 to [3] reports [4] alone."""
    out: list[int] = []
    for part in re.split(r"\s*,\s*", group.strip()):
        bounds = [int(x) for x in re.split(r"\s*[-–—]\s*", part) if x.strip().isdigit()]
        if len(bounds) == 2 and 0 <= bounds[1] - bounds[0] <= 50:
            out += range(bounds[0], bounds[1] + 1)
        else:
            out += bounds
    return out


def sentence_tokens(text: str) -> dict[str, Counter[str]]:
    """Numbers, citations and identifiers in one sentence, normalised so formatting alone is not a change."""
    cites: Counter[str] = Counter()
    spans: list[tuple[int, int]] = []
    for m in CITE_TEX.finditer(text):
        cites.update("\\cite{" + k.strip() + "}" for k in m.group(1).split(",") if k.strip())
        spans.append(m.span())
    for m in CITE_PANDOC.finditer(text):
        cites["@" + m.group(1)] += 1
        spans.append(m.span())
    for m in CITE_NUMERIC.finditer(text):
        cites.update(f"[{n}]" for n in _expand_numeric(m.group(1)))
        spans.append(m.span())
    for m in NARRATIVE.finditer(text):
        cites[f"{m.group(1)} {m.group(2)}"] += 1
        spans.append(m.span())
    masked = _blank_spans(text, spans)
    for m in CITE_PAREN.finditer(masked):
        for unit in AUTHOR_YEAR.finditer(m.group(0)):
            cites[f"{unit.group(1)} {unit.group(2)}"] += 1
            spans.append((m.start() + unit.start(), m.start() + unit.end()))
    masked = _blank_spans(text, spans)
    ids: Counter[str] = Counter()
    id_spans = []
    for m in PROTECTED["identifiers"].finditer(masked):
        ids[" ".join(m.group(0).split()).lower().rstrip(".,;:")] += 1
        id_spans.append(m.span())
    id_spans += [m.span() for m in PROTECTED["urls"].finditer(masked)]
    id_spans += [m.span() for m in TEX_POINTERS.finditer(masked)]
    masked = _blank_spans(masked, id_spans)
    numbers = Counter(_norm_number(m.group(0)) for m in PROTECTED["numbers"].finditer(masked))
    return {"number": numbers, "citation": cites, "identifier": ids}


# ---------------------------------------------------------------------------------------------------------------
# Sentence-level comparison
# ---------------------------------------------------------------------------------------------------------------

CLAIM_KINDS = ("causal", "evidential", "generality", "scope", "limitation", "null_result", "evidence_status")
# What an --authorised entry can cover: the claim kinds and a declaration only the authors can make. Never numbers,
# citations or identifiers, and --allow-strengthening covers the claim kinds only.
REQUESTABLE = CLAIM_KINDS + ("declaration",)


def _finding(kind: str, change: str, severity: str, g: Group, bs: list[Sentence], as_: list[Sentence],
             **extra: object) -> dict[str, object]:
    before = " ".join(bs[i].text for i in g.before)
    after = " ".join(as_[j].text for j in g.after)
    elsewhere = as_[g.after[0]].file if g.after else None  # moved to another file: placed by where it was
    out: dict[str, object] = {
        "id": 0, "kind": kind, "change": change, "severity": severity, "authorised": False,
        "section": as_[g.after[0]].section if g.after and not elsewhere else bs[g.before[0]].section,
        "before_line": bs[g.before[0]].line if g.before else None,
        "after_line": as_[g.after[0]].line if g.after else None,
        "after_file": elsewhere,
        "alignment": g.kind, "before": before, "after": after,
        "removed": [], "added": [], "strength_before": None, "strength_after": None,
        "token": None, "token_status": None, "token_file": None, "note": "",
    }
    out.update(extra)
    return out


def _letter_words(words: frozenset[str]) -> set[str]:
    """Content words with a letter in them: numbers are compared as numbers, not as wording."""
    return {w for w in words if re.search(r"[^\W\d_]", w)}


def _surface(words: set[str], text: str) -> list[str]:
    """The words as the sentence spells them ('PRS', not 'prs'), sorted."""
    out = []
    for w in words:
        m = re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text, re.IGNORECASE)
        out.append(m.group(0) if m else w)
    return sorted(out, key=str.lower)


# The smells the prose-edit contract names as whole sentences that carry nothing, which an edit may cut: empty
# implication (A3), mini-conclusion (A8), filler phrase (B5), signposting (C4), slogan (H1), landing phrase (H10).
STOCK_SENTENCE_SMELLS = ("A3", "A8", "B5", "C4", "H1", "H10")


@functools.cache
def _stock_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    smells = yaml.safe_load(SMELL_PATTERNS.read_text(encoding="utf-8"))["smells"] if SMELL_PATTERNS.is_file() else {}
    return tuple((str(smells[sid].get("scope", "any")), re.compile(p, re.IGNORECASE))
                 for sid in STOCK_SENTENCE_SMELLS if sid in smells for p in smells[sid]["patterns"])


# A deleted sentence is a stock phrase only when fewer content words than this remain once the phrase is taken
# out: "For the purpose of reproducibility, all code is archived" still says where the code is.
STOCK_REMAINDER = 4


def _stock_phrases(text: str, last_in_paragraph: bool) -> tuple[list[str], int]:
    """The stock phrases from the smell catalogue (../manuscript-deslop/references/smell-patterns.yaml) in a
    sentence, and how many content words with letters remain once they are taken out."""
    target = text.lstrip("\"“(*_")
    spans: list[tuple[int, int]] = []
    for scope, rx in _stock_patterns():
        if scope == "end" and not last_in_paragraph:
            continue
        for m in rx.finditer(target):
            if m.end() > m.start() and (scope != "start" or m.start() == 0):
                spans.append(m.span())
    phrases = sorted({" ".join(target[a:b].split()) for a, b in spans}, key=str.lower)
    rest = _letter_words(_content_words(_blank_spans(target, spans)))
    return phrases, len(rest)


def _stock_sentence(text: str, last_in_paragraph: bool) -> bool:
    """A sentence that is a stock phrase and little else, so an edit may cut it unreported."""
    phrases, rest = _stock_phrases(text, last_in_paragraph)
    return bool(phrases) and rest < STOCK_REMAINDER


def _sentence_findings(g: Group, bs: list[Sentence], as_: list[Sentence], ctx: dict[str, object],
                       revision: bool) -> list[dict[str, object]]:
    """A deleted sentence with no other claim finding (both modes; an edit may cut a sentence that is only a stock
    phrase unreported). In a revision inventory also a new sentence and the words a rewritten sentence lost or
    gained, so every change is shown before and after."""
    if not g.after:
        i = g.before[0]
        own = bs[i].words
        last = i + 1 == len(bs) or bs[i + 1].block != bs[i].block
        phrases, rest = _stock_phrases(bs[i].text, last)
        if not revision and phrases and rest < STOCK_REMAINDER:
            return []
        unit = _unit(bs[i].text)
        note = f"Deleting a {unit} removes what it said, so the authors must see it."
        if phrases:
            note = (f"It was cut as a stock phrase ({_quoted_list(phrases)}), but it said more than that phrase, so "
                    "check that nothing it said was lost.")
        main = ctx["main_after"]  # type: ignore[assignment]
        if own and unit == "sentence":
            share, line = max(((len(own & s.words) / len(own), s.line) for s in main), default=(0.0, 0))  # type: ignore[union-attr]
            if share >= MERGED_ELSEWHERE:
                note = (f"Most of its words are in the sentence at line {line} of the edited text, so it may have "
                        "been merged there; check that nothing it said was lost.")
        return [_finding("sentence", "removed", "warning", g, bs, as_, note=note)]
    if not revision:
        return []
    if not g.before:
        return [_finding("sentence", "added", "warning", g, bs, as_, note="A new sentence adds content, so check "
                         "it against the authors' instructions.")]
    words_b, words_a = ctx["words_b"], ctx["words_a"]  # type: ignore[assignment]
    b_blocks = {bs[i].block for i in g.before}
    a_blocks = {as_[j].block for j in g.after}
    near_b = set().union(*(words_b.get(b, set()) for b in b_blocks))  # type: ignore[union-attr]
    near_a = set().union(*(words_a.get(a, set()) for a in a_blocks))  # type: ignore[union-attr]
    own_b = _letter_words(frozenset().union(*(bs[i].words for i in g.before)))
    own_a = _letter_words(frozenset().union(*(as_[j].words for j in g.after)))
    text_b, text_a = " ".join(bs[i].text for i in g.before), " ".join(as_[j].text for j in g.after)
    dropped, gained = _surface(own_b - near_a, text_b), _surface(own_a - near_b, text_a)
    if not dropped and not gained:
        return []
    return [_finding("wording", "changed", "warning", g, bs, as_, removed=dropped, added=gained,
                     note="Check that the rewording kept what the sentence said.")]


def _claim_findings(g: Group, bs: list[Sentence], as_: list[Sentence]) -> list[dict[str, object]]:
    tb = " ".join(bs[i].text for i in g.before)
    ta = " ".join(as_[j].text for j in g.after)
    found: list[dict[str, object]] = []
    negated = bool(NEGATION.search(tb) or NEGATION.search(ta))
    whole = "inserted" if not g.before else "deleted" if not g.after else None

    for kind, rungs, plain in (("causal", CAUSAL, CAUSAL_PLAIN), ("evidential", EVIDENTIAL, EVIDENTIAL_PLAIN)):
        mb, ma = _ladder(tb, rungs), _ladder(ta, rungs)
        removed = sorted((Counter(s for _, _, s in mb) - Counter(s for _, _, s in ma)).elements())
        added = sorted((Counter(s for _, _, s in ma) - Counter(s for _, _, s in mb)).elements())
        if not g.after or not g.before:
            markers = mb or ma
            if not markers:
                continue
            strong = max(level for level, _, _ in markers) >= 1
            change = "removed" if not g.after else "added"
            severity = "protected" if change == "added" and strong else "warning"
            note = ("Deleting a claim changes the science, so the authors must see it." if change == "removed"
                    else "A new claim needs the authors' approval and its evidence.")
            found.append(_finding(kind, change, severity, g, bs, as_, removed=removed, added=added,
                                  strength_before=_rung_names(mb) if mb else None,
                                  strength_after=_rung_names(ma) if ma else None, note=note))
            continue
        direction = _direction(mb, ma, plain)
        if direction is None:
            continue
        severity = "warning" if direction == "lowered" and not negated else "protected"
        note = ("The sentence is negated, so a weaker verb can make the claim stronger; read both versions." if negated
                else "Narrowing a claim is a correction the authors must approve." if direction == "lowered" else "")
        found.append(_finding(kind, direction, severity, g, bs, as_, removed=removed, added=added,
                              strength_before=_rung_names(mb), strength_after=_rung_names(ma), note=note))

    gen_removed, gen_added = _keyed_diff(
        [(k, " ".join(m.group(0).lower().split())) for k, rx in GENERALITY for m in rx.finditer(tb)],
        [(k, " ".join(m.group(0).lower().split())) for k, rx in GENERALITY for m in rx.finditer(ta)])
    if gen_added:
        found.append(_finding("generality", "raised", "protected", g, bs, as_, removed=gen_removed, added=gen_added,
                              note="The claim now reaches further than the authors wrote."))
    elif gen_removed:
        found.append(_finding("generality", "lowered", "warning", g, bs, as_, removed=gen_removed,
                              note="The claim now reaches less far, which the authors must approve."))

    sb, sa = _scope_sides(tb, ta, bool(g.after))
    s_removed, s_added = _keyed_diff(sb, sa)
    if s_removed:
        found.append(_finding("scope", "replaced" if s_added else "removed", "protected", g, bs, as_,
                              removed=s_removed, added=s_added, note="The claim may now read as more general than the "
                              "data."))
    elif s_added and whole is None:
        found.append(_finding("scope", "added", "warning", g, bs, as_, added=s_added,
                              note="This narrows the claim, so the authors must see it."))

    (lb, ob), (la, oa) = _limitation_marks(tb), _limitation_marks(ta)
    l_removed = sorted((Counter(lb) - Counter(la)).elements())
    l_added = sorted((Counter(la) - Counter(lb)).elements())
    if len(lb) > len(la) and len(lb) + ob > len(la) + oa and whole != "inserted":
        # The claim widens when its sentence survives without the limit; a deleted sentence and a claim narrowed in
        # the same edit (a lowered rung, an added qualifier) are warnings the authors must still see.
        narrowed = any(c["change"] == "lowered" and c["kind"] in ("causal", "evidential")
                       or (c["kind"] == "scope" and c["change"] == "added") for c in found)
        note = ("The sentence that held it was deleted, so list it for the authors." if whole else
                "The claim was also narrowed in the same edit, so check that the limit survives."
                if narrowed else "The claim may now read as resting on more evidence, or holding more widely, than "
                "the authors wrote.")
        severity = "warning" if whole or narrowed else "protected"
        found.append(_finding("limitation", "removed", severity, g, bs, as_, removed=l_removed, added=l_added,
                              note=note))
    elif len(la) > len(lb) and len(la) + oa > len(lb) + ob and whole is None:
        found.append(_finding("limitation", "added", "warning", g, bs, as_, removed=l_removed, added=l_added,
                              note="This narrows the claim, so the authors must see it."))

    nb, na = _null_marks(tb), _null_marks(ta)
    null_change = None
    if len(nb) > len(na) and whole != "inserted":
        null_change = "removed"
        found.append(_finding("null_result", "removed", "protected", g, bs, as_,
                              removed=sorted((Counter(nb) - Counter(na)).elements()) or sorted(set(nb)),
                              added=sorted((Counter(na) - Counter(nb)).elements()),
                              note="A null or negative result must stay stated as one: a rewording can turn "
                                   "absence of evidence into evidence of absence."))
    elif len(na) > len(nb):
        null_change = "added"
        found.append(_finding("null_result", "added", "warning", g, bs, as_,
                              added=sorted((Counter(na) - Counter(nb)).elements()) or sorted(set(na)),
                              note="A new null result changes what the sentence reports, so the authors must see "
                                   "it."))

    e_removed, e_added = _keyed_diff(_status_keys(tb), _status_keys(ta))
    if e_removed and whole != "inserted":
        found.append(_finding("evidence_status", "replaced" if e_added else "removed", "protected", g, bs, as_,
                              removed=e_removed, added=e_added,
                              note="The sentence now says the finding was obtained another way." if e_added else
                              "Readers can no longer tell how the finding was obtained."))
    elif e_added and whole is None:
        found.append(_finding("evidence_status", "added", "warning", g, bs, as_, added=e_added,
                              note="This changes how the finding is said to have been obtained, so the authors "
                                   "must see it."))

    gb, ga = [m.group(0).lower() for m in NEGATION.finditer(tb)], [m.group(0).lower() for m in NEGATION.finditer(ta)]
    if len(gb) != len(ga) and whole is None:  # a whole new or deleted sentence is reported by its claims and tokens
        change = "removed" if len(gb) > len(ga) else "added"
        if change != null_change:
            found.append(_finding("negation", change, "warning", g, bs, as_,
                                  removed=sorted((Counter(gb) - Counter(ga)).elements()),
                                  added=sorted((Counter(ga) - Counter(gb)).elements()),
                                  note="Check that the claim did not flip."))
    return found


# ---------------------------------------------------------------------------------------------------------------
# Declarations only the authors can make: consent, ethics approval, competing interests, funding, contributions
# ---------------------------------------------------------------------------------------------------------------

# A heading that names a declaration, as the whole heading (a Results subsection "Contribution of rare variants"
# is not one); BMC's "Ethics approval and consent to participate" and an umbrella "Declarations" are.
DECLARATION_HEADING = _rx(
    r"^\s*(?:[A-Z]?[\d.]+\s+)?(?:competing (?:interests?|financial interests?)|conflicts? of interests?|"
    r"declarations?(?: of (?:competing )?interests?)?|disclosures?|consent(?: for publication| to participate)?|"
    r"ethic(?:s|al)\b|funding|financial (?:support|disclosure)|author(?:s'|s|'s)? contributions?|contributions|"
    r"contributorship|credit(?: author(?:ship)? statement)?|acknowledg(?:e)?ments?)")
DECLARATION_CUES = _rx(
    r"\b(?:informed |written |verbal )?consent\b[^.]{0,80}?\b(?:obtained|given|provided|waived|signed|received|"
    r"granted)\b|\b(?:obtained|gave|given|provided|signed|waived)\b[^.]{0,40}?\bconsent\b|\bconsented\b|"
    r"\b(?:ethics|ethical|institutional review) (?:committee|board|approval|review)\b|\bIRB\b|"
    r"\bexempt(?:ed|ion)? from (?:ethic(?:s|al) )?(?:review|approval|oversight)\b|"
    r"\b(?:competing|conflicts? of) interests?\b|\bdeclares? (?:that )?(?:they have )?no\b|"
    r"\bfunded by\b|\bfunding (?:from|by|was)\b|\bsupported by (?:a |an |the )?(?:[\w-]+ ){0,3}?(?:grant|award|"
    r"fellowship|funding)\b|\bgrant (?:no\.?|number|agreement)\b|"
    r"\b[A-Z]\.(?:\s?[A-Z]\.)+,?\s+(?:and [A-Z]\.(?:\s?[A-Z]\.)+\s+)?(?:conceived|designed|supervised|wrote|"
    r"performed|analy[sz]ed|contributed|acquired|curated|reviewed|edited|developed|implemented)\b|"
    r"\bcontributed equally\b|\bauthors? (?:read|approved|have read)\b")


def _declares(s: Sentence) -> bool:
    """A sentence under a declarations heading (Competing interests, Consent, Ethics, Funding, Author contributions,
    Acknowledgements), or one with a cue phrase of consent, ethics approval, competing interests, funding or
    authorship."""
    return bool(any(DECLARATION_HEADING.match(h) for h in s.section.split(" > ")) or DECLARATION_CUES.search(s.text))


INITIALS = re.compile(r"\b[A-Z]\.(?:\s?[A-Z]\.)*(?:\s?[A-Z][a-z]+)?")


def _declaration_words(text: str) -> set[str]:
    """The content words of a declaration, and the people it names by their initials ("A.K.", "C.M.")."""
    return set(_letter_words(_content_words(text))) | {"".join(m.group(0).split()) for m in INITIALS.finditer(text)}


def _respelled(lost: set[str], gained: set[str]) -> tuple[set[str], set[str]]:
    """Leave out words that were only respelled ("recieved" → "received"): a spelling fix changes no declaration."""
    lost, gained = set(lost), set(gained)
    for word in sorted(lost):
        match = next((w for w in sorted(gained) if SequenceMatcher(None, word, w).ratio() >= 0.85), None)
        if match:
            lost.discard(word)
            gained.discard(match)
    return lost, gained


def _declaration_findings(g: Group, bs: list[Sentence], as_: list[Sentence]) -> list[dict[str, object]]:
    """A new, deleted or reworded sentence that declares what only the authors can: consent, ethics approval or
    exemption, competing interests, funding, an author's contribution or credit. Protected: the run never writes,
    drops or narrows one on its own."""
    if not any(_declares(bs[i]) for i in g.before) and not any(_declares(as_[j]) for j in g.after):
        return []
    note = "Only the authors can make it, so the run never writes, rewords or drops one on its own."
    if not g.before:
        return [_finding("declaration", "added", "protected", g, bs, as_, note=note)]
    if not g.after:
        return [_finding("declaration", "removed", "protected", g, bs, as_, note=note)]
    text_b, text_a = " ".join(bs[i].text for i in g.before), " ".join(as_[j].text for j in g.after)
    words_b, words_a = _declaration_words(text_b), _declaration_words(text_a)
    lost, gained = _respelled(words_b - words_a, words_a - words_b)
    if not lost and not gained:
        return []
    return [_finding("declaration", "changed", "protected", g, bs, as_, removed=_surface(lost, text_b),
                     added=_surface(gained, text_a), note=note)]


def _token_findings(g: Group, bs: list[Sentence], as_: list[Sentence], tok_b: list[dict[str, Counter[str]]],
                    tok_a: list[dict[str, Counter[str]]], ctx: dict[str, object]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    b_blocks = {bs[i].block for i in g.before}
    a_blocks = {as_[j].block for j in g.after}
    near_b = b_blocks | {b for a in a_blocks for b in ctx["a2b"].get(a, ())}  # type: ignore[union-attr]
    near_a = a_blocks | {a for b in b_blocks for a in ctx["b2a"].get(b, ())}  # type: ignore[union-attr]
    for kind in TOKEN_KINDS:
        cb: Counter[str] = sum((tok_b[i][kind] for i in g.before), Counter())
        ca: Counter[str] = sum((tok_a[j][kind] for j in g.after), Counter())
        for token in sorted(ca - cb):
            in_paragraph = any(token in ctx["block_b"][b][kind] for b in near_b)  # type: ignore[index]
            status = ("moved_within_paragraph" if in_paragraph else
                      "from_elsewhere" if token in ctx["doc_b"][kind] else "new")  # type: ignore[index]
            found.append(_finding(kind, "added", "warning" if in_paragraph else "protected", g, bs, as_,
                                  added=[token], token=token, token_status=status,
                                  note={"new": "It is not in the original.", "from_elsewhere": "It appears "
                                        "elsewhere in the original, but not in this sentence or its paragraph.",
                                        "moved_within_paragraph": "It moved here from another sentence of the same "
                                        "paragraph."}[status]))
        for token in sorted(cb - ca):
            in_paragraph = any(token in ctx["block_a"].get(a, {}).get(kind, ()) for a in near_a)  # type: ignore[union-attr]
            other_file = None if in_paragraph or token in ctx["doc_a"][kind] else (  # type: ignore[index]
                ctx["doc_ext"][kind].get(token))  # type: ignore[index]
            status = ("moved_within_paragraph" if in_paragraph else "moved_elsewhere" if token in ctx["doc_a"][kind]
                      else "in_other_file" if other_file else "removed")  # type: ignore[index]
            found.append(_finding(kind, "removed", "protected" if status == "removed" or status == "moved_elsewhere"
                                  else "warning", g, bs, as_, removed=[token], token=token, token_status=status,
                                  token_file=other_file,
                                  note={"removed": "It is not in the edited text.", "moved_elsewhere": "It is now "
                                        "only in another paragraph.", "moved_within_paragraph": "It moved to another "
                                        "sentence of the same paragraph.", "in_other_file": f"It is now only in "
                                        f"{other_file}, a file the text was moved to."}[status]))
    return found


# ---------------------------------------------------------------------------------------------------------------
# Story moves (--relocated): a caveat or number that left its sentence for another one of the same section is still
# in the paper, and a headline that only restates its paragraph adds no claim
# ---------------------------------------------------------------------------------------------------------------

RELOCATABLE = {"scope": ("removed", "replaced"), "limitation": ("removed",), "null_result": ("removed",),
               "evidence_status": ("removed", "replaced")}
# A scope qualifier or evidence status never leaves a sentence of the Abstract or the Introduction: readers take the
# claim from there, and a caveat stated elsewhere does not reach them.
STAYS_IN_OPENING = ("scope", "evidence_status")
OPENING_SECTION = re.compile(r"^(?:abstract|summary|introduction|background)\b", re.IGNORECASE)
# Content words a sentence must share with the one a caveat or number left, to state it about the same thing.
CONTEXT_WORDS = 2
# Causal and inferential connectives a headline may use only when its paragraph does.
HEADLINE_CONNECTIVES = _rx(r"\b(?:because|due to|owing to|thanks to|therefore|thus|hence|as a result|so that)\b")


def _caveat_marks(text: str) -> list[tuple[str, str, str]]:
    """(kind, key, surface) of each marker a caveat can carry, keyed as the claim checks key them."""
    marks = [("scope", k, s) for k, s in _scope_keys(text)]
    marks += [("limitation", w, w) for w in _limitation_marks(text)[0]]
    marks += [("null_result", s, s) for s in _null_marks(text)]
    return marks + [("evidence_status", k, s) for k, s in _status_keys(text)]


def _lost_caveat(kind: str, tb: str, ta: str, survives: bool = True
                 ) -> tuple[list[tuple[str, str]], Callable[[Counter[str]], bool]]:
    """The (key, surface) markers of one kind a sentence lost (all of them when it was deleted), and the test
    `_claim_findings` applies with `found` of them counted as still in the paper: True while the loss is still
    protected."""
    if kind == "limitation":
        (lb, ob), (la, oa) = _limitation_marks(tb), _limitation_marks(ta)
        return ([(w, w) for w in sorted((Counter(lb) - Counter(la)).elements())],
                lambda found: len(lb) > len(la) + found.total() and len(lb) + ob > len(la) + oa + found.total())
    if kind == "null_result":
        nb, na = _null_marks(tb), _null_marks(ta)
        return ([(s, s) for s in sorted((Counter(nb) - Counter(na)).elements())],
                lambda found: len(nb) > len(na) + found.total())
    sb, sa = _scope_sides(tb, ta, survives) if kind == "scope" else (_status_keys(tb), _status_keys(ta))
    deficit = Counter(k for k, _ in sb) - Counter(k for k, _ in sa)
    lost, left = [], Counter(deficit)
    for k, s in sb:
        if left[k] > 0:
            lost.append((k, s))
            left[k] -= 1
    return lost, lambda found: bool(deficit - found)


def _caveat_destinations(groups: list[Group], bs: list[Sentence], as_: list[Sentence], n_main: int
                         ) -> tuple[dict[tuple[str, str], list[tuple[int, int, str]]], Counter[tuple[int, str]],
                                    dict[tuple[str, str], list[tuple[int, int, str]]]]:
    """Where the main text states each marker, by (kind, key), as (group, sentence, surface): the occurrences new or
    changed sentences gained, with how many markers of each kind a group may give away (what it gained beyond what
    it lost of that kind, so a sentence that swapped one qualifier for another is no destination for either), and
    the occurrences sentences already had. A file the text was moved to is never a destination: it is not the
    section the caveat left."""
    gained: dict[tuple[str, str], list[tuple[int, int, str]]] = {}
    standing: dict[tuple[str, str], list[tuple[int, int, str]]] = {}
    capacity: Counter[tuple[int, str]] = Counter()
    for unit, g in enumerate(groups):
        after = [j for j in g.after if j < n_main]
        if not after:
            continue
        had = Counter((kind, key) for i in g.before for kind, key, _ in _caveat_marks(bs[i].text))
        marks = [(j, mark) for j in after for mark in _caveat_marks(as_[j].text)]
        for kind in RELOCATABLE:
            capacity[(unit, kind)] = (sum(1 for _, mark in marks if mark[0] == kind)
                                      - sum(v for (k, _), v in had.items() if k == kind))
        left = Counter(had)
        for j, (kind, key, surface) in marks:
            if left[(kind, key)] > 0:
                left[(kind, key)] -= 1
                standing.setdefault((kind, key), []).append((unit, j, surface))
            else:
                gained.setdefault((kind, key), []).append((unit, j, surface))
    return gained, capacity, standing


def _caveat_place(s: Sentence, title: Optional[str]) -> str:
    """'the Discussion, Limitations (line 12)', or 'supplementary.md, in the S3 Cohort (line 5)'."""
    where = f"{_section({'section': s.section}, title)} (line {s.line})"
    return f"{s.file}, in {where}" if s.file else where


def _top_section(s: Sentence, title: Optional[str]) -> Optional[str]:
    """The top-level heading a sentence of the main text sits under, without the paper's title ('Results' for
    'Paper > Results > Speed', '' before the first heading); None for a file the text was moved to."""
    if s.file:
        return None
    section = s.section
    if title and section == title:
        return ""
    if title and section.startswith(title + " > "):
        section = section[len(title) + 3:]
    return section.split(" > ")[0]


def _opening(top: Optional[str], headed: bool) -> bool:
    """The Abstract or the Introduction; in a paper with headings, the text before the first one is its abstract."""
    if top is None:
        return False
    if not top:
        return headed
    numbered = NUMBERED_HEADING.match(top)
    return bool(OPENING_SECTION.match(numbered.group(2) if numbered else top))


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def _context(text: str, drop: set[str]) -> set[str]:
    return {_stem(w) for w in _letter_words(_content_words(text))} - drop


def _shares_context(a: str, b: str, drop: set[str]) -> bool:
    """Two sentences about the same thing: at least CONTEXT_WORDS content words in common, markers left out."""
    return len(_context(a, drop) & _context(b, drop)) >= CONTEXT_WORDS


def _marker_words(text: str) -> set[str]:
    return {_stem(w) for _, _, surface in _caveat_marks(text) for w in _content_words(surface)}


# A sentence another stage reworded before the story stage recorded its change still lies inside that change when
# this share of its content words is in it.
INSIDE_SHARE = 0.8


@functools.lru_cache(maxsize=64)
def _passage_words(passage: str) -> frozenset[str]:
    return frozenset(_stem(w) for w in _letter_words(_content_words(passage)))


def _inside(text: str, passages: Optional[list[str]]) -> bool:
    """A sentence inside one of the changes story moves are limited to (always, when they are not limited): copied
    there word for word, or, when an earlier stage reworded it, with most of its content words in one change."""
    if passages is None:
        return True
    folded = _folded(text)
    if not folded:
        return False
    if any(folded in p for p in passages):
        return True
    words = {_stem(w) for w in _letter_words(_content_words(text))}
    return len(words) >= 3 and any(len(words & _passage_words(p)) >= INSIDE_SHARE * len(words) for p in passages)


def _relocate(changes: list[dict[str, object]], owner: dict[int, int], groups: list[Group], bs: list[Sentence],
              as_: list[Sentence], n_main: int, titles: dict[Optional[str], Optional[str]],
              passages: Optional[list[str]] = None) -> None:
    """Story moves: downgrade a lost caveat, a number moved within its section and a headline sentence to warnings
    where the rules in the module docstring allow it. `passages` limits the moves to those changes."""
    title = titles.get(None)
    top_b = [_top_section(s, title) for s in bs]
    top_a = [_top_section(s, title) for s in as_]
    headed = any(top_b) or any(t for t in top_a[:n_main])
    group_of = {j: n for n, g in enumerate(groups) for j in g.after}
    gained, capacity, standing = _caveat_destinations(groups, bs, as_, n_main)
    for c in changes:
        c["relocated_to"] = None
        n = owner.get(id(c))
        kind = str(c["kind"])
        if n is None or c["severity"] != "protected" or c["change"] not in RELOCATABLE.get(kind, ()):
            continue
        g = groups[n]
        if not g.before:
            continue
        tb, ta = " ".join(bs[i].text for i in g.before), " ".join(as_[j].text for j in g.after)
        top = top_b[g.before[0]]
        if kind in STAYS_IN_OPENING and _opening(top, headed):
            c["note"] = (f"{c['note']} A scope qualifier or evidence status in the Abstract or the Introduction stays "
                         "in its sentence, wherever else the paper states it.")
            continue
        if not any(_inside(bs[i].text, passages) for i in g.before) and not any(
                _inside(as_[j].text, passages) for j in g.after if j < n_main):
            continue
        drop = _marker_words(tb)  # markers say nothing about the subject: "only" is no shared context
        lost, still = _lost_caveat(kind, tb, ta, survives=bool(g.after))
        found: Counter[str] = Counter()
        spots: list[tuple[int, str, bool]] = []  # (sentence, surface, already stated there)

        def fits(unit: int, j: int) -> bool:
            return unit != n and top_a[j] == top and _shares_context(tb, as_[j].text, drop)

        for key, _ in lost:
            if not still(found):
                break
            slots = gained.get((kind, key), [])
            k = next((k for k, (unit, j, _) in enumerate(slots) if capacity[(unit, kind)] > 0 and fits(unit, j)
                      and _inside(as_[j].text, passages)), None)
            if k is not None:
                unit, j, surface = slots.pop(k)
                capacity[(unit, kind)] -= 1
                spots.append((j, surface, False))
            else:  # a sentence that already states it accounts for one lost occurrence of this sentence
                spot = next(((j, surface) for unit, j, surface in standing.get((kind, key), [])
                             if fits(unit, j) and (j, surface) not in [(x, y) for x, y, _ in spots]), None)
                if spot is None:
                    continue
                spots.append((spot[0], spot[1], True))
            found[key] += 1
        if not spots:
            continue
        c["relocated_to"] = [{"marker": surface, "section": as_[j].section, "line": as_[j].line,
                              "file": as_[j].file, "sentence": as_[j].text} for j, surface, _ in spots]
        places = [(surface, _caveat_place(as_[j], title), there) for j, surface, there in spots]
        if still(found):
            left, rest = Counter(found), []
            for key, s in lost:
                if left[key] > 0:
                    left[key] -= 1
                else:
                    rest.append(s)
            c["note"] = (f"{c['note']} " + _listed([f"{_q(s)} {'is still stated in' if there else 'moved to'} {p}"
                                                     for s, p, there in places])
                         + f", but no other sentence of the same section holds the remaining {_quoted_list(rest)}.")
            continue
        one = len(places) == 1
        if all(there for _, _, there in places):
            went = (f"The same section still states it, in {places[0][1]}" if one else
                    "The same section still states them: " + _listed([f"{_q(s)} in {p}" for s, p, _ in places]))
        elif one:
            went = f"It moved to {places[0][1]}"
        else:
            went = "They moved: " + _listed([f"{_q(s)} {'is still in' if there else 'to'} {p}"
                                             for s, p, there in places])
        c["severity"] = "warning"
        c["note"] = (f"{went}, so the paper still states {'it' if one else 'them'}; check that readers still see "
                     f"which claim {'it qualifies' if one else 'they qualify'}.")
    _relocate_numbers(changes, owner, groups, bs, as_, n_main, top_b, top_a, passages)
    _headlines(changes, owner, groups, bs, as_, n_main, group_of, passages)


def _relocate_numbers(changes: list[dict[str, object]], owner: dict[int, int], groups: list[Group],
                      bs: list[Sentence], as_: list[Sentence], n_main: int, top_b: list[Optional[str]],
                      top_a: list[Optional[str]], passages: Optional[list[str]]) -> None:
    """A number that left its sentence for another paragraph of the same section, into a sentence about the same
    thing: both findings become warnings ("moved_within_section"). Citations and identifiers stay protected."""
    left = [c for c in changes if c["kind"] == "number" and c["change"] == "removed" and c["severity"] == "protected"
            and c["token_status"] == "moved_elsewhere" and id(c) in owner]
    came = [c for c in changes if c["kind"] == "number" and c["change"] == "added" and c["severity"] == "protected"
            and c["token_status"] == "from_elsewhere" and id(c) in owner]
    candidates = []
    for r, removed in enumerate(left):
        gr = groups[owner[id(removed)]]
        if not gr.before or not (any(_inside(bs[i].text, passages) for i in gr.before)
                                 or any(_inside(as_[j].text, passages) for j in gr.after if j < n_main)):
            continue
        tb = " ".join(bs[i].text for i in gr.before)
        for a, added in enumerate(came):
            ga = groups[owner[id(added)]]
            if ga is gr or added["token"] != removed["token"] or not ga.after or ga.after[0] >= n_main:
                continue
            j = ga.after[0]
            if top_a[j] != top_b[gr.before[0]] or not _inside(as_[j].text, passages):
                continue
            drop = _marker_words(tb) | _marker_words(as_[j].text)  # a shared "albeit" says nothing about the subject
            shared = len(_context(tb, drop) & _context(as_[j].text, drop))
            if shared >= CONTEXT_WORDS:
                candidates.append((shared, r, a))
    for r, a in _pair_best_first([(float(s), r, a) for s, r, a in candidates], CONTEXT_WORDS):
        removed, added = left[r], came[a]
        for c in (removed, added):
            c["severity"], c["token_status"] = "warning", "moved_within_section"
        removed["note"] = (f"It moved to another sentence of the same section, at line {added['after_line']}, which "
                           "is about the same thing.")
        added["note"] = (f"It moved here from another sentence of the same section, at line "
                         f"{removed['before_line']} before the edit.")


def _headlines(changes: list[dict[str, object]], owner: dict[int, int], groups: list[Group], bs: list[Sentence],
               as_: list[Sentence], n_main: int, group_of: dict[int, int], passages: Optional[list[str]]) -> None:
    """A new sentence before a result in its paragraph that names nothing the paragraph lacked and claims no more
    than it does is a headline: its claim findings become warnings."""
    for n, g in enumerate(groups):
        if g.before or not g.after or any(j >= n_main for j in g.after):
            continue
        claims = [c for c in changes if owner.get(id(c)) == n and c["severity"] == "protected"
                  and c["kind"] in ("causal", "evidential", "generality")]
        block = as_[g.after[0]].block
        if not claims or any(as_[j].block != block for j in g.after):
            continue
        headline = " ".join(as_[j].text for j in g.after)
        results = [k for k in range(n_main) if as_[k].block == block and k not in g.after
                   and groups[group_of[k]].before]
        if not results or min(g.after) > max(results) or not all(_inside(as_[j].text, passages) for j in g.after):
            continue
        blocks = {bs[i].block for k in results for i in groups[group_of[k]].before}
        paragraph = [s.text for s in bs if s.block in blocks]
        if not _restates(headline, paragraph):
            continue
        for c in claims:
            c["severity"] = "warning"
            c["note"] = ("A headline for the result in its paragraph: it names no number, citation or term the "
                         "paragraph lacks and claims no more than the paragraph does. Show it to the authors.")


def _restates(headline: str, paragraph: list[str]) -> bool:
    """The headline names nothing the paragraph did not have and claims no more than the paragraph does."""
    whole = " ".join(paragraph)
    mine, theirs = sentence_tokens(headline), sentence_tokens(whole)
    if any(set(mine[kind]) - set(theirs[kind]) for kind in TOKEN_KINDS):
        return False
    if set(_items(headline, PROTECTED["terms"])) - set(_items(whole, PROTECTED["terms"])):
        return False
    for rungs, plain in ((CAUSAL, CAUSAL_PLAIN), (EVIDENTIAL, EVIDENTIAL_PLAIN)):
        markers = _ladder(headline, rungs)
        ceiling = max((_strength(_ladder(p, rungs), plain)[1] for p in paragraph), default=plain)
        if markers and max(level for level, _, _ in markers) > ceiling:
            return False

    def words(rx: re.Pattern[str], text: str) -> set[str]:
        return {" ".join(m.group(0).lower().split()) for m in rx.finditer(text)}

    for rx in (WATCHED["comparatives"], HEADLINE_CONNECTIVES):
        if words(rx, headline) - words(rx, whole):
            return False
    return not ({k for k, rx in GENERALITY if rx.search(headline)} - {k for k, rx in GENERALITY if rx.search(whole)})


# ---------------------------------------------------------------------------------------------------------------
# The changes story moves may be limited to (--relocated-in)
# ---------------------------------------------------------------------------------------------------------------

CHANGE_PARTS = re.compile(r"^## (?:Before|After)[ \t]*$", re.MULTILINE)
NO_BLOCK = {"(No previous block.)", "(Block removed.)"}


def _record_passages(text: str) -> list[str]:
    """The before and after text of a runs.py change record; a file without those headings is one passage."""
    parts = CHANGE_PARTS.split(text)
    if len(parts) == 1:
        return [text]
    return [p for p in parts[1:] if p.strip() and p.strip() not in NO_BLOCK]


def _data_passages(data: object) -> list[str]:
    """Passages of a list of change records or requests (`passage`, `before`, `after`), or of a mapping holding
    one under `changes`, `passages` or `authorised` (a stage's findings.json, say)."""
    if isinstance(data, dict):
        data = next((data[k] for k in ("changes", "passages", "authorised") if isinstance(data.get(k), list)), [])
    out: list[str] = []
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, str):
            out.append(entry)
        elif isinstance(entry, dict):
            out += [str(entry[k]) for k in ("passage", "before", "after") if isinstance(entry.get(k), str)]
    return out


def relocation_passages(paths: list[Path]) -> list[str]:
    """The folded passages of the changes story moves are limited to. A folder is a stage's run folder: the change
    records in it and in its `changes/` subfolder, and the changes in its `findings.json`. A path that does not
    exist adds nothing."""
    texts: list[str] = []
    for path in paths:
        files: list[Path] = []
        if path.is_dir():
            files = [p for folder in (path, path / "changes") if folder.is_dir() for p in sorted(folder.glob("*.md"))
                     if CHANGE_PARTS.search(p.read_text(encoding="utf-8"))]
            files += [path / "findings.json"] if (path / "findings.json").is_file() else []
        elif path.is_file():
            files = [path]
        for f in files:
            raw = f.read_text(encoding="utf-8")
            if f.suffix.lower() in (".json", ".yaml", ".yml"):
                texts += _data_passages(yaml.safe_load(raw))
            else:
                texts += _record_passages(raw)
    return [p for p in (_folded(_prose(t)) for t in texts) if p]


EXTERNAL_BLOCKS = 1_000_000  # paragraph numbers of a moved-to file start at (its position + 1) times this


def sentence_changes(before_text: str, after_text: str, moved: list[tuple[str, str]] | tuple[()] = (), *,
                     revision: bool = False, relocated: bool = False, passages: Optional[list[str]] = None
                     ) -> tuple[list[dict[str, object]], dict[str, int]]:
    """Align the sentences of two versions and list claim, scope and token changes with their locations.

    `moved` lists (name, text) of the files part of the text was moved to: a sentence found there is moved, not
    deleted, and a changed one is compared with its copy there. `revision` adds the inventory's new sentences and
    rewordings. `relocated` applies the story moves of the module docstring (every finding then has
    `relocated_to`); `passages` (relocation_passages) limits them to those changes."""
    changes, alignment, _ = _analyse(before_text, after_text, moved, revision=revision, relocated=relocated,
                                     passages=passages)
    return changes, alignment


def _analyse(before_text: str, after_text: str, moved: list[tuple[str, str]] | tuple[()] = (), *,
             revision: bool = False, relocated: bool = False, passages: Optional[list[str]] = None
             ) -> tuple[list[dict[str, object]], dict[str, int], dict[str, object]]:
    """sentence_changes, plus what the whole-text counts need: the sentences and how paragraphs correspond."""
    bs, main = segment(before_text), segment(after_text)
    external = [s for n, (name, text) in enumerate(moved)
                for s in segment(text, file=name, block_base=(n + 1) * EXTERNAL_BLOCKS)]
    groups = align(bs, main, external)
    as_ = main + external
    tok_b = [sentence_tokens(s.text) for s in bs]
    tok_a = [sentence_tokens(s.text) for s in as_]

    def by_block(sents: list[Sentence], toks: list[dict[str, Counter[str]]]) -> dict[int, dict[str, Counter[str]]]:
        out: dict[int, dict[str, Counter[str]]] = {}
        for s, t in zip(sents, toks):
            slot = out.setdefault(s.block, {k: Counter() for k in TOKEN_KINDS})
            for k in TOKEN_KINDS:
                slot[k].update(t[k])
        return out

    def words_by_block(sents: list[Sentence]) -> dict[int, set[str]]:
        out: dict[int, set[str]] = {}
        for s in sents:
            out.setdefault(s.block, set()).update(s.words)
        return out

    b2a: dict[int, set[int]] = {}
    a2b: dict[int, set[int]] = {}
    for g in groups:
        for i in g.before:
            for j in g.after:
                b2a.setdefault(bs[i].block, set()).add(as_[j].block)
                a2b.setdefault(as_[j].block, set()).add(bs[i].block)
    doc_ext: dict[str, dict[str, str]] = {k: {} for k in TOKEN_KINDS}
    for s, t in zip(external, tok_a[len(main):]):
        for k in TOKEN_KINDS:
            for token in t[k]:
                doc_ext[k].setdefault(token, str(s.file))
    ctx: dict[str, object] = {
        "b2a": b2a, "a2b": a2b, "block_b": by_block(bs, tok_b), "block_a": by_block(as_, tok_a),
        "doc_b": {k: set().union(*(t[k] for t in tok_b)) for k in TOKEN_KINDS},
        "doc_a": {k: set().union(*(t[k] for t in tok_a[:len(main)])) for k in TOKEN_KINDS},
        "doc_ext": doc_ext, "main_after": main, "words_b": words_by_block(bs), "words_a": words_by_block(as_),
    }
    changes: list[dict[str, object]] = []
    owner: dict[int, int] = {}  # id of a claim or token finding → index of its group
    for n, g in enumerate(groups):
        if g.kind == "equal":
            continue
        claims = _claim_findings(g, bs, as_) + _declaration_findings(g, bs, as_)
        owner.update((id(c), n) for c in claims)
        if not claims:
            claims = _sentence_findings(g, bs, as_, ctx, revision)
        tokens = _token_findings(g, bs, as_, tok_b, tok_a, ctx)
        owner.update((id(c), n) for c in tokens)
        changes += claims + tokens
    changes.sort(key=lambda c: (c["after_line"] if c["after_line"] is not None and not c["after_file"]
                                else c["before_line"] or 0, c["before_line"] or 0))
    if relocated:
        titles = {None: document_title(after_text) or document_title(before_text)}
        titles.update((name, document_title(text)) for name, text in moved)
        _relocate(changes, owner, groups, bs, as_, len(main), titles, passages)
    for n, c in enumerate(changes, 1):
        c["id"] = n
    counts = Counter(g.kind for g in groups)
    alignment = {"sentences_before": len(bs), "sentences_after": len(main), "unchanged": counts["equal"],
                 "changed": counts["changed"], "split": counts["split"], "merged": counts["merged"],
                 "moved": counts["moved"], "moved_to_other_file": counts["moved_out"],
                 "moved_to_other_file_changed": sum(1 for g in groups if g.kind == "moved_out"
                                                    and bs[g.before[0]].text != as_[g.after[0]].text),
                 "deleted": counts["deleted"], "inserted": counts["inserted"]}
    return changes, alignment, {"before": bs, "after": main, "a2b": a2b, "groups": groups, "all_after": as_}


def _added_in_own_paragraph(rx: re.Pattern[str], parts: dict[str, object]) -> Counter[str]:
    """Occurrences an edit added to a paragraph that already had the item ("it" given its noun): per item, how many.
    A paragraph's earlier version is the paragraphs its sentences were aligned with."""
    def by_block(sents: list[Sentence]) -> dict[int, Counter[str]]:
        out: dict[int, Counter[str]] = {}
        for s in sents:
            out.setdefault(s.block, Counter()).update(_items(s.text, rx))
        return out

    before, after = by_block(parts["before"]), by_block(parts["after"])  # type: ignore[arg-type]
    a2b: dict[int, set[int]] = parts["a2b"]  # type: ignore[assignment]
    again: Counter[str] = Counter()
    for block, items in after.items():
        earlier = sum((before.get(b, Counter()) for b in a2b.get(block, ())), Counter())
        for item, n in items.items():
            if earlier[item] and n > earlier[item]:
                again[item] += n - earlier[item]
    return again


def document_title(text: str) -> Optional[str]:
    """The paper's title when it is the one level-1 Markdown heading above the sections, else None."""
    masked = _mask(text, _is_latex(text))
    headings = [(len(m.group(1)), _clean_title(m.group(2))) for m in map(MD_HEADING.match, masked.split("\n")) if m]
    if len(headings) > 1 and headings[0][0] == 1 and sum(level == 1 for level, _ in headings) == 1:
        return headings[0][1]
    return None


def _folded(text: str) -> str:
    """Lower case, straight quotes and single spaces, so a passage copied from either version matches."""
    text = text.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"'}))
    return " ".join(text.lower().split())


def parse_authorisations(data: object) -> list[dict[str, object]]:
    """The requested claim changes from a loaded YAML or JSON document: a list of entries, or a mapping with the
    list under `authorised` (or `changes`, for change records). Each entry gives `passages` (folded), `findings`
    and `kinds`. Raises ValueError with a message for the user."""
    if isinstance(data, dict):
        data = data.get("authorised", data.get("changes"))
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError("the file must hold a list of requested claim changes")
    entries: list[dict[str, object]] = []
    for n, raw in enumerate(data, 1):
        if not isinstance(raw, dict):
            raise ValueError(f"entry {n} is not a mapping with a passage and what asked for it")
        given = [str(raw[k]) for k in ("passage", "after", "before") if raw.get(k) and len(str(raw[k]).split()) >= 3]
        passages = [_folded(p) for p in given]
        if not passages:
            raise ValueError(f"entry {n} needs a passage: at least three words in a row, copied exactly from the "
                             "sentence")
        by = next((raw[k] for k in ("finding", "findings", "finding_ids", "id") if raw.get(k)), None)
        if by is None and raw.get("comment"):
            # A referee comment id ("R2.4") asked for it; a change record's `comment` is a question, never an id.
            ids = raw["comment"] if isinstance(raw["comment"], list) else [raw["comment"]]
            by = ids if all(re.fullmatch(r"\S{1,32}", str(x).strip()) for x in ids) else None
        findings = [str(x) for x in (by if isinstance(by, list) else [by]) if x]
        if not findings:
            raise ValueError(f"entry {n} does not say what asked for the change (a finding, a referee comment id or "
                             "the authors' request)")
        kinds = [str(k) for k in raw.get("kinds") or []]
        unknown = [k for k in kinds if k not in REQUESTABLE]
        if unknown:
            raise ValueError(f"entry {n} names unknown claim kinds {unknown}; use {list(REQUESTABLE)}")
        entries.append({"passages": passages, "shown": given[0], "findings": findings, "kinds": kinds})
    return entries


def authorise(changes: list[dict[str, object]], entries: list[dict[str, object]]) -> list[dict[str, object]]:
    """Match each claim change to the requests whose passage its sentence contains, or lies inside; a matched
    widening is authorised. Every claim change gets `authorised_by`. Returns the entries that matched nothing."""
    used = [False] * len(entries)
    for c in changes:
        if c["token"] is not None or c["kind"] not in REQUESTABLE:
            continue
        c["authorised_by"] = []
        texts = [_folded(str(c[k])) for k in ("before", "after") if c[k]]
        for n, e in enumerate(entries):
            if e["kinds"] and c["kind"] not in e["kinds"]:  # type: ignore[operator]
                continue
            if any(p in t or (len(t.split()) >= 3 and t in p) for p in e["passages"] for t in texts):  # type: ignore[union-attr]
                used[n] = True
                c["authorised_by"] += [f for f in e["findings"] if f not in c["authorised_by"]]  # type: ignore[operator, union-attr]
                if c["severity"] == "protected":
                    c["authorised"] = True
    return [e for e, u in zip(entries, used) if not u]


def unrequested(report: dict[str, object]) -> list[dict[str, object]]:
    """Claims that widened with no matching request, when the requests were given; empty otherwise."""
    if report.get("authorisations") is None:
        return []
    return [c for c in report["sentence_changes"]  # type: ignore[union-attr]
            if c["token"] is None and c["kind"] in REQUESTABLE and c["severity"] == "protected" and not c["authorised"]]


# ---------------------------------------------------------------------------------------------------------------
# The requested sections (--only): a sentence changed anywhere else was not asked for
# ---------------------------------------------------------------------------------------------------------------

def _heading_key(title: str) -> str:
    """A heading as a requested section is compared with it: numbering, case and spacing set aside."""
    title = " ".join(title.split())
    numbered = NUMBERED_HEADING.match(title)
    return (numbered.group(2) if numbered else title).casefold()


def in_sections(s: Sentence, wanted: list[str]) -> bool:
    """Whether a sentence lies under a requested section: a heading anywhere in its path ("Discussion" takes
    "Discussion > Limitations" too), or a run of headings written as a path ("Results > Speed")."""
    path = [_heading_key(p) for p in s.section.split(" > ")] if s.section else []
    for name in wanted:
        parts = [_heading_key(p) for p in name.split(">")]
        if any(path[i:i + len(parts)] == parts for i in range(len(path) - len(parts) + 1)):
            return True
    return False


def outside_sections(parts: dict[str, object], wanted: list[str]) -> list[dict[str, object]]:
    """Each changed, moved, deleted or new sentence (or run of them) that lies, before or after the edit, outside the
    requested sections. A sentence moved to another file is placed by where it was."""
    bs: list[Sentence] = parts["before"]  # type: ignore[assignment]
    as_: list[Sentence] = parts["all_after"]  # type: ignore[assignment]
    out: list[dict[str, object]] = []
    for g in parts["groups"]:  # type: ignore[union-attr]
        if g.kind == "equal":
            continue
        here = [as_[j] for j in g.after if as_[j].file is None]
        stray = [x for x in [bs[i] for i in g.before] + here if not in_sections(x, wanted)]
        if stray:
            out.append({"alignment": g.kind, "section": stray[0].section, "after_file": None,
                        "before_line": bs[g.before[0]].line if g.before else None,
                        "after_line": here[0].line if here else None,
                        "before": " ".join(bs[i].text for i in g.before), "after": " ".join(x.text for x in here)})
    return out


def _sections_named(sents: list[Sentence], title: Optional[str]) -> list[str]:
    """The top-level headings of a text, in order, for a usage message."""
    return list(dict.fromkeys(t for t in (_top_section(x, title) for x in sents) if t))


# ---------------------------------------------------------------------------------------------------------------
# The summary against the body (--summary): the title, Abstract and Conclusions claim no more than the body states
# ---------------------------------------------------------------------------------------------------------------

SUMMARY_PART = re.compile(r"^(?:abstract|summary|author summary|lay summary|plain[- ]language summary|"
                          r"significance(?: statement)?|highlights|key (?:points|findings))\b", re.IGNORECASE)
CONCLUSION_PART = re.compile(r"^(?:conclusions?|concluding remarks|summary and conclusions?)\b", re.IGNORECASE)
# Parts that are neither summary nor body: the Introduction states prior work and aims, the back matter declares.
NOT_BODY = re.compile(r"^(?:introduction|background|references|bibliography|literature cited|acknowledge?ments?|"
                      r"funding|(?:author )?contributions|competing interests|conflicts? of interest|declarations?|"
                      r"(?:data|code|data and code|software) availability|availability|ethics|consent|"
                      r"supplementary|appendix|keywords|abbreviations)\b", re.IGNORECASE)
# A body sentence is about the same thing as a summary sentence when they share this many content words with a
# letter in them and reach this Dice similarity of their content words; the closest few are compared. A limit the
# summary leaves out counts only against a body sentence this close: "VarRank scores only missense variants" is not
# the sentence an Abstract's benchmark result restates (seeded peer-review fixture, 0.29).
SUMMARY_SHARED, SUMMARY_SIMILARITY, SUMMARY_MATCHES, SUMMARY_CLOSE = 3, 0.25, 5, 0.4
RAISING = ("causal", "evidential", "generality")
# A title states a claim when it has a word of the ladders or a verb of effect or finding; otherwise it names a topic
# ("Loss of Foo and tumour growth", "A role for Foo in tumour growth") and claims nothing to compare.
TITLE_VERB = _rx(r"\b(?:is|are|was|were|has|have|does|do|can|could|may|might|will|would|shows?|reveals?|explains?|"
                 r"predicts?|improves?|increases?|decreases?|reduces?|raises?|lowers?|slows?|speeds?|accelerates?|"
                 r"enhances?|impairs?|protects?|prevents?|promotes?|inhibits?|blocks?|regulates?|controls?|drives?|"
                 r"determines?|underlies|confers?|leads?|affects?|alters?|outperforms?|enables?|identifies|links?|"
                 r"doubles?|halves?|extends?|shortens?|restores?|rescues?|requires?)\b")
TEX_TITLE = re.compile(r"\\title(?:\[[^\]]*\])?\{((?:[^{}]|\{[^{}]*\})*)\}")
YAML_TITLE = re.compile(r"^title:[ \t]*(.+?)[ \t]*$", re.MULTILINE)


def _title_sentence(text: str) -> Optional[Sentence]:
    """The paper's title as a sentence: a front-matter `title`, the one level-1 Markdown heading, or LaTeX's title."""
    found: Optional[tuple[str, int]] = None
    front = FRONT_MATTER.match(text)
    heading = document_title(text)
    yaml_title = YAML_TITLE.search(front.group(0)) if front else None
    tex_title = TEX_TITLE.search(text) if _is_latex(text) else None
    if yaml_title:
        found = (yaml_title.group(1).strip("'\""), yaml_title.start(1))
    elif heading:
        m = re.search(rf"^ {{0,3}}#[ \t]+{re.escape(heading)}", text, re.MULTILINE)
        found = (heading, m.start() if m else 0)
    elif tex_title:
        found = (_clean_title(tex_title.group(1)), tex_title.start())
    if not found or not re.search(r"[A-Za-z]", found[0]):
        return None
    body = " ".join(found[0].split())
    return Sentence(body, text.count("\n", 0, found[1]) + 1, -1, "Title", _content_words(body), None)


def _summary_part(s: Sentence, title: Optional[str], headed: bool) -> Optional[str]:
    """'title', 'abstract' or 'conclusions' for a sentence of a summary part, else None. In a paper with headings, the
    text before the first one (under the title) is its abstract."""
    if s.section == "Title" and s.block == -1:
        return "title"
    top = _top_section(s, title)
    path = [_heading_key(p) for p in (s.section.split(" > ") if s.section else [])]
    if title and path and path[0] == _heading_key(title):
        path = path[1:]
    if any(CONCLUSION_PART.match(p) for p in path):
        return "conclusions"
    if (top == "" and headed) or (top and SUMMARY_PART.match(_heading_key(top))):
        return "abstract"
    return None


def _in_body(s: Sentence, title: Optional[str], headed: bool) -> bool:
    top = _top_section(s, title)
    return bool(top) and not NOT_BODY.match(_heading_key(top)) and _summary_part(s, title, headed) is None


def summary_check(text: str) -> dict[str, object]:
    """Each sentence of the title, the Abstract and the Conclusions against the body sentences closest to it: a claim
    stronger or more general than every one of them, or a scope, limit, null result or evidence status that the
    closest one states and the summary sentence leaves out. The Introduction and the back matter are neither."""
    title = document_title(text)
    sents = segment(text)
    headed = any(x.section for x in sents)
    named = _title_sentence(text)
    summary = ([named] if named else []) + [x for x in sents if _summary_part(x, title, headed)]
    body = [x for x in sents if _in_body(x, title, headed)]
    if not summary or not body:
        raise ValueError("--summary needs a title, an Abstract or Conclusions, and body sections (Results, "
                         "Discussion) under their own headings")
    stated: dict[tuple[str, str], str] = {}  # the whole text of each summary part, by (part, section)
    for x in summary:
        key = (_summary_part(x, title, headed) or "", x.section)
        stated[key] = (stated.get(key, "") + " " + x.text).strip()
    findings: list[dict[str, object]] = []
    unmatched: list[dict[str, object]] = []
    pair = Group([0], [0], "changed")
    stems = {id(x): frozenset(_stem(w) for w in x.words) for x in summary + body}  # "tumours" meets "tumour"
    for x in summary:
        part = _summary_part(x, title, headed) or ""
        sx = stems[id(x)]
        scored = sorted(((_dice(sx, stems[id(b)]), n, b) for n, b in enumerate(body)
                         if len(_letter_words(sx & stems[id(b)])) >= SUMMARY_SHARED), key=lambda t: (-t[0], t[1]))
        matches = [b for d, _, b in scored if d >= SUMMARY_SIMILARITY][:SUMMARY_MATCHES]
        close = bool(scored) and scored[0][0] >= SUMMARY_CLOSE
        if not matches:
            unmatched.append({"part": part, "section": x.section, "line": x.line, "sentence": x.text})
            continue
        # The body sentence is "before" and the summary sentence "after": what the summary adds or leaves out.
        against = [[f for f in _claim_findings(pair, [b], [x]) if f["severity"] == "protected"
                    and f["kind"] in CLAIM_KINDS] for b in matches]
        # One body sentence about the same thing that states the claim as strongly, on both ladders and as widely,
        # supports it; the limits are compared with the closest one.
        supported = any(not any(f["kind"] in RAISING for f in fs) for fs in against)
        if part == "title" and not (TITLE_VERB.search(x.text) or _ladder(x.text, CAUSAL)
                                    or _ladder(x.text, EVIDENTIAL)):
            continue
        for f in against[0]:
            kind = str(f["kind"])
            if kind in RAISING and supported or kind not in RAISING and not close:
                continue
            if kind in ("scope", "evidence_status"):
                keys = _scope_keys if kind == "scope" else _status_keys
                lost = {k for k, _ in keys(matches[0].text)} - {k for k, _ in keys(x.text)}
                if kind == "evidence_status" and lost <= {"observed"}:
                    continue  # "measured" or "observed" describes the method; leaving it out widens nothing
                if lost and lost <= {k for k, _ in keys(stated[(part, x.section)])}:
                    continue  # the part states it once, in another of its sentences
            findings.append({"kind": kind, "change": f["change"], "part": part, "section": x.section,
                             "line": x.line, "sentence": x.text, "body_section": matches[0].section,
                             "body_line": matches[0].line, "body_sentence": matches[0].text,
                             "removed": f["removed"], "added": f["added"], "strength_summary": f["strength_after"],
                             "strength_body": f["strength_before"]})
    return {"mode": "summary", "title": title, "summary_sentences": len(summary), "body_sentences": len(body),
            "findings": findings, "unmatched": unmatched,
            "summary": {"findings": len(findings), "unmatched": len(unmatched),
                        "by_kind": dict(Counter(str(f["kind"]) for f in findings))}}


def compare(before_text: str, after_text: str, threshold: float = 0.5, *, revision: bool = False,
            allow_strengthening: bool = False, moved: list[tuple[str, str]] | tuple[()] = (),
            relocated: bool = False, authorised: list[dict[str, object]] | None = None,
            relocated_in: list[str] | None = None, only: list[str] | None = None) -> dict[str, object]:
    """Compare two versions. `moved` lists (name, text) of the files part of the text was moved to (a
    supplement, say): what is found there counts as moved, not removed. `relocated`: a story edit moved caveats
    on purpose, so the story moves of the module docstring are warnings. `relocated_in`: the folded passages
    (relocation_passages) those moves are limited to; it implies `relocated`. `authorised`: the requested claim
    changes (parse_authorisations); a widened claim no entry matches is unrequested. `only`: the sections the request
    covered; a sentence changed anywhere else is listed in `only.outside` and fails."""
    relocated = relocated or relocated_in is not None
    latex = _is_latex(before_text) or _is_latex(after_text)
    before, after = _prose(before_text, latex), _prose(after_text, latex)
    elsewhere = "\n\n".join(_prose(text, _is_latex(text)) for _, text in moved)
    moved_counts: dict[str, dict[str, int]] = {}
    protected, watched = {}, {}
    for patterns, out in ((PROTECTED, protected), (WATCHED, watched)):
        for name, rx in patterns.items():
            ib, ia = _items(before, rx), _items(after, rx)
            im = _items(elsewhere, rx) if moved else None
            out[name] = _diff(ib, ia, im)
            if im is not None and patterns is PROTECTED and _moved_items(ib, ia, im):
                moved_counts[name] = _moved_items(ib, ia, im)
    changes, alignment, parts = _analyse(before_text, after_text, moved, revision=revision, relocated=relocated,
                                         passages=relocated_in)
    if only is not None:
        sents = parts["before"] + parts["after"]  # type: ignore[operator]
        missing = [name for name in only if not any(in_sections(x, [name]) for x in sents)]
        if missing:
            known = _sections_named(sents, document_title(after_text) or document_title(before_text))
            raise ValueError(f"no section is named {_listed([repr(m) for m in missing])}; the sections are "
                             f"{_listed(known) if known else 'none (the text has no headings)'}")
    # An item added to a paragraph that already has it (a pronoun given its noun; in a story edit, a headline that
    # repeats its paragraph's number) is not a change of content; the sentence findings still list a moved token.
    repeated: dict[str, dict[str, int]] = {}
    for name in ("terms",) + (("numbers", "citations", "identifiers") if relocated else ()):
        added = protected[name]["added"]
        again = _added_in_own_paragraph(PROTECTED[name], parts) if added else Counter()
        for item in [i for i in added if again[i]]:
            n = min(added[item], again[item])
            repeated.setdefault(name, {})[item] = n
            added[item] -= n
            if not added[item]:
                del added[item]
    if allow_strengthening:
        for c in changes:
            if c["kind"] in CLAIM_KINDS and c["severity"] == "protected":
                c["authorised"] = True
    unused = authorise(changes, authorised) if authorised is not None else []
    summary = Counter(f"{c['severity']}" for c in changes)
    report: dict[str, object] = {
        "mode": "revision" if revision else "edit",
        "title": document_title(after_text) or document_title(before_text),
        "allow_strengthening": allow_strengthening,
        "protected": {k: v for k, v in protected.items() if v["removed"] or v["added"]},
        "watched": {k: v for k, v in watched.items() if v["removed"] or v["added"]},
        "moved_to": {"files": [name for name, _ in moved], "sentences": alignment["moved_to_other_file"],
                     "sentences_changed": alignment["moved_to_other_file_changed"],
                     "counts": moved_counts} if moved else None,
        "rewritten_paragraphs": _rewritten_paragraphs(before, after, threshold, [(n, _prose(t, _is_latex(t)))
                                                                                  for n, t in moved]),
        "words_before": len(before.split()),
        "words_after": len(after.split()),
        "change_rate": change_rate(before, after),
        "sentence_changes": changes,
        "alignment": alignment,
        "summary": {"protected": summary["protected"], "warning": summary["warning"],
                    "authorised": sum(1 for c in changes if c["authorised"]),
                    "by_kind": dict(Counter(str(c["kind"]) for c in changes))},
    }
    if repeated:
        report["repeated_in_paragraph"] = repeated
    if only is not None:  # only with the flag, so a report without it is unchanged
        report["only"] = {"sections": list(only), "outside": outside_sections(parts, only)}
        report["summary"]["outside_scope"] = len(report["only"]["outside"])  # type: ignore[index]
    if relocated:  # only with the flag, so a report without it is unchanged
        report["relocated"] = True
        report["summary"]["relocated"] = sum(1 for c in changes  # type: ignore[index]
                                             if c["relocated_to"] and c["severity"] == "warning")
        if relocated_in is not None:
            report["relocated_in"] = {"passages": len(relocated_in)}
    if authorised is not None:  # likewise only with the requests
        report["authorisations"] = {"entries": len(authorised), "unused": [
            {"findings": e["findings"], "passage": e["shown"]} for e in unused]}
        report["summary"]["unrequested"] = len(unrequested(report))  # type: ignore[index]
    return report


def exit_code(report: dict[str, object]) -> int:
    """1 when an edit made a protected change; a revision inventory returns 1 only for a claim that widened with
    no matching request, when the requests were given. Either fails on a change outside the requested sections."""
    if (report.get("only") or {}).get("outside"):  # type: ignore[union-attr]
        return 1
    if report["mode"] == "revision":
        return int(bool(unrequested(report)))
    if report["protected"]:
        return 1
    return int(any(c["severity"] == "protected" and not c["authorised"]
                   for c in report["sentence_changes"]))  # type: ignore[union-attr]


def _git_show(path: Path, ref: str) -> str:
    listed = subprocess.run(["git", "-C", str(path.parent), "ls-files", "--full-name", path.name],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    rel = listed.stdout.strip()
    if listed.returncode != 0 or not rel:
        raise typer.BadParameter(f"{path} is not tracked by git, so there is no earlier version to compare with.")
    shown = subprocess.run(["git", "-C", str(path.parent), "show", f"{ref}:{rel}"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if shown.returncode != 0:
        raise typer.BadParameter(f"git has no version of {rel} at {ref!r}: {shown.stderr.strip()}")
    return shown.stdout


# ---------------------------------------------------------------------------------------------------------------
# The Markdown report: every change in plain words, with its section and the sentence quoted
# ---------------------------------------------------------------------------------------------------------------

CAUSAL_WORDS = {"compatibility": "compatibility with a finding", "association": "an association",
                "prediction": "a prediction", "contribution": "a contribution", "effect": "an effect",
                "causation": "a cause", "plain statement": "a plain statement of effect"}
EVIDENTIAL_WORDS = {"possibility": "a possibility", "suggestion": "a suggestion", "indication": "an indication",
                    "demonstration": "a demonstration", "proof": "proof", "plain statement": "a plain assertion"}
TOKEN_NOUNS = {"number": ("number", "numbers"), "citation": ("citation", "citations"),
               "identifier": ("identifier", "identifiers")}
COUNT_NOUNS = {"numbers": ("number", "numbers"), "citations": ("citation", "citations"),
               "identifiers": ("identifier", "identifiers"), "urls": ("link", "links"),
               "code": ("code span", "code spans"), "terms": ("technical term", "technical terms"),
               "hedges": ("hedge", "hedges"), "negations": ("negation", "negations"),
               "causal": ("causal or proof word", "causal or proof words"),
               "comparatives": ("comparative or quantifier", "comparatives and quantifiers")}
EXCERPT = 160


def _q(text: object) -> str:
    return "“" + str(text) + "”"


def _listed(items: list[str]) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


SMALL_NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _count_word(n: int, one: str, many: str) -> str:
    """'one place', 'three places', '12 places': small counts in words, as in running prose."""
    return f"{SMALL_NUMBERS[n] if n < len(SMALL_NUMBERS) else n} {one if n == 1 else many}"


def _quoted_list(words: object) -> str:
    return _listed([_q(w) for w in words])  # type: ignore[union-attr]


def _upper_first(sentence: str) -> str:
    return sentence[:1].upper() + sentence[1:]


def _lower_first(sentence: str) -> str:
    """'A negation changed' → 'a negation changed' after 'In the Results, '; 'APOE ...' and 'GRCh38 ...' stay."""
    first = sentence.split(" ", 1)[0]
    if len(first) > 1 and any(ch.isupper() or ch.isdigit() for ch in first[1:]):
        return sentence
    return sentence[:1].lower() + sentence[1:]


def excerpt(text: object, marks: object = (), width: int = EXCERPT) -> str:
    """The sentence quoted, cut to about `width` characters around the first changed word, which is in bold."""
    body = " ".join(str(text).split())
    spans: list[tuple[int, int]] = []
    for mark in marks or ():  # type: ignore[union-attr]
        if mark:
            spans += [m.span() for m in re.finditer(rf"(?<!\w){re.escape(str(mark))}(?!\w)", body, re.IGNORECASE)]
    lo, hi = 0, len(body)
    if len(body) > width + 40:
        first = min(spans)[0] if spans else 0
        lo = max(0, first - width // 3)
        hi = min(len(body), lo + width)
        lo = max(0, hi - width)
        if lo > 0:
            lo = body.find(" ", lo) + 1 or lo
        if hi < len(body):
            cut = body.rfind(" ", lo, hi)
            hi = cut if cut > lo else hi
    merged: list[list[int]] = []
    for a, b in sorted(spans):
        if a < lo or b > hi:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    piece = body[lo:hi]
    for a, b in reversed(merged):
        piece = piece[:a - lo] + "**" + piece[a - lo:b - lo] + "**" + piece[b - lo:]
    return _q(("…" if lo else "") + piece + ("…" if hi < len(body) else ""))


# "6. Conclusion", "5.1 Limitations", "A.2 Extra runs"; a bare capital ("A Study of ...") is a word, not a number.
NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*|[A-Z](?:\.\d+)+|[A-Z](?=\.))\.?\s+(\S.*)$")


def _section(c: dict[str, object], title: Optional[str]) -> str:
    """'the Results, Performance' or 'section 5.1, Limitations': the heading path without the paper's title,
    ready to follow 'In'. A numbered heading names its parents already, so only the deepest one is given."""
    section = str(c["section"] or "")
    if title and section.startswith(title + " > "):
        section = section[len(title) + 3:]
    elif title and section == title:
        return "the text under the title"
    if not section:
        return "the text before the first heading"
    numbered = NUMBERED_HEADING.match(section.split(" > ")[-1])
    if numbered:
        return f"section {numbered.group(1)}, {numbered.group(2)}"
    return "the " + section.replace(" > ", ", ")


def _unit(text: object) -> str:
    """What the guard aligned: a sentence, or a table row (Markdown or LaTeX), which is compared as one unit."""
    return "table row" if TABLE_ROW.match(str(text or "")) else "sentence"


def _where(c: dict[str, object], title: Optional[str]) -> str:
    b, a = c["before_line"], c["after_line"]
    unit = _unit(c["after"] or c["before"])
    if c.get("after_file"):
        return f"{_section(c, title)} (line {b} before the edit, now in {c['after_file']}, line {a})"
    lines = (f"line {a}" if b == a else f"line {b} before the edit, line {a} after") if a and b else (
        f"a new {unit}, line {a}" if a else f"a deleted {unit}, line {b} before the edit")
    return f"{_section(c, title)} ({lines})"


def _became(removed: object, added: object) -> str:
    r, a = list(removed or []), list(added or [])  # type: ignore[call-overload]
    if r and a:
        return f"{_quoted_list(r)} became {_quoted_list(a)}"
    if r:
        return f"{_quoted_list(r)} {'was' if len(r) == 1 else 'were'} removed"
    return f"{_quoted_list(a)} {'was' if len(a) == 1 else 'were'} added"


def _strength_words(value: object, words: dict[str, str]) -> str:
    return _listed([words.get(n, n) for n in str(value or "plain statement").split("+")])


def describe(c: dict[str, object]) -> str:
    """What changed in one sentence, in plain words."""
    kind, change, removed, added = c["kind"], c["change"], c["removed"], c["added"]
    if kind in ("causal", "evidential"):
        words = CAUSAL_WORDS if kind == "causal" else EVIDENTIAL_WORDS
        measure = "the relation it states" if kind == "causal" else "its certainty"
        if change == "removed":
            return f"A {_unit(c['before'])} that claimed {_strength_words(c['strength_before'], words)} was deleted."
        if change == "added":
            return f"A new {_unit(c['after'])} claims {_strength_words(c['strength_after'], words)}."
        verdict = {"raised": "The claim became stronger", "lowered": "The claim became weaker",
                   "mixed": "The claim's strength changed in both directions"}[str(change)]
        moved = (f"{measure} went from {_strength_words(c['strength_before'], words)} to "
                 f"{_strength_words(c['strength_after'], words)}")
        return (f"{verdict}: {_became(removed, added)}, so {moved}." if removed or added else f"{verdict}: {moved}.")
    if kind == "generality":
        return (f"Wording that claims novelty or generality was added: {_quoted_list(added)}." if change == "raised"
                else f"Wording that claimed novelty or generality was removed: {_quoted_list(removed)}.")
    if kind == "scope":
        if change == "added":
            return f"The scope qualifier {_quoted_list(added)} was added."
        if change == "replaced":
            return f"The scope qualifier {_quoted_list(removed)} was replaced by {_quoted_list(added)}."
        return f"The scope qualifier {_quoted_list(removed)} was dropped."
    if kind == "limitation":
        if change == "added":
            return f"The limiting word {_quoted_list(added)} was added."
        return f"The limiting word {_quoted_list(removed)} was dropped."
    if kind == "null_result":
        return (f"The null result {_quoted_list(removed)} is no longer stated." if change == "removed"
                else f"A null result was added: {_quoted_list(added)}.")
    if kind == "evidence_status":
        if change == "added":
            return f"The word {_quoted_list(added)}, which says how the finding was obtained, was added."
        if change == "replaced":
            return f"{_upper_first(_became(removed, added))}, which says how the finding was obtained."
        return f"The word {_quoted_list(removed)}, which said how the finding was obtained, was dropped."
    if kind == "negation":
        return f"A negation changed: {_became(removed, added)}."
    if kind == "declaration":
        what = ("a declaration only the authors can make (consent, ethics approval, competing interests, funding or "
                "an author's contribution)")
        if change == "added":
            return f"A new {_unit(c['after'])} makes {what}."
        if change == "removed":
            return f"A {_unit(c['before'])} that made {what} was deleted."
        return f"The wording of {what} changed: {_became(removed, added)}."
    if kind == "sentence":
        unit = _unit(c["before"] if change == "removed" else c["after"])
        return f"The {unit} is gone from the edited text." if change == "removed" else f"The {unit} is new."
    if kind == "wording":
        r, a = list(removed or []), list(added or [])  # type: ignore[call-overload]
        parts = ([f"{_quoted_list(r)} {'was' if len(r) == 1 else 'were'} dropped"] if r else []) + (
            [f"{_quoted_list(a)} {'was' if len(a) == 1 else 'were'} added"] if a else [])
        return f"The wording changed: {', and '.join(parts)}."
    return f"The {kind} changed: {_became(removed, added)}."


def _action(c: dict[str, object], revision: bool) -> str:
    by = c.get("authorised_by")
    if by:
        return f"Asked for by {_listed([str(x) for x in by])}; it is listed so that the authors see it."  # type: ignore[union-attr]
    if by is not None and c["severity"] == "protected" and not c["authorised"]:
        return "Nothing in the list of requested changes asked for this, so restore the original wording."
    if revision:
        return ""
    if c["authorised"]:
        return "The authors authorised this claim change; it is listed so they see it."
    if c["severity"] == "protected":
        return "Revert this unless the authors asked for it."
    return "Show this to the authors if it stays."


def _claim_lines(c: dict[str, object], title: Optional[str], revision: bool) -> list[str]:
    head = " ".join(x for x in (f"In {_where(c, title)}, {_lower_first(describe(c))}", str(c["note"] or ""),
                                _action(c, revision)) if x)
    out = [f"- {head}"]
    if c["before"]:
        out.append(f"  - Before the edit: {excerpt(c['before'], c['removed'])}")
    if c["after"]:
        out.append(f"  - After the edit: {excerpt(c['after'], c['added'])}")
    for spot in c.get("relocated_to") or ():  # type: ignore[union-attr]
        out.append(f"  - Where it is now: {excerpt(spot['sentence'], [spot['marker']])}")
    return out


TOKEN_SENTENCES = {
    "new": ("{items} {is} new: {they} {is} not in the original.", "Remove {them} unless the authors supplied {them}."),
    "from_elsewhere": ("{items} {is} new to this sentence and its paragraph; {they} {appear} elsewhere in the "
                       "original.", "Check that {they} {belong} here."),
    "moved_within_paragraph": ("{items} moved between sentences of the same paragraph.",
                               "Check that {they} still {belong} to the right claim."),
    "moved_within_section": ("{items} moved between two sentences of the same section that are about the same "
                             "thing.", "Check that {they} still {belong} to the right claim."),
    "removed": ("{items} {was} removed and {is} not in the edited text.",
                "Restore {them} unless the authors asked for the change."),
    "moved_elsewhere": ("{items} {was} removed from this sentence and {is} now only in another paragraph.",
                        "Check that {they} still {belong} to the right claim."),
    "in_other_file": ("{items} {was} removed here and {is} now only in {file}, a file the text was moved to.",
                      "Check that {they} still {belong} to the right claim there."),
}


def _token_sentence(kind: str, status: str, tokens: list[str], revision: bool, file: Optional[str] = None) -> str:
    one = len(tokens) == 1
    noun = TOKEN_NOUNS.get(kind, (kind, kind + "s"))[0 if one else 1]
    fill = {"items": f"The {noun} {_quoted_list(tokens)}", "is": "is" if one else "are", "was": "was" if one else "were",
            "they": "it" if one else "they", "them": "it" if one else "them", "appear": "appears" if one else "appear",
            "belong": "belongs" if one else "belong", "file": file or ""}
    what, action = TOKEN_SENTENCES[status]
    return what.format(**fill) + ("" if revision else " " + action.format(**fill))


def _token_lines(tokens: list[dict[str, object]], title: Optional[str], revision: bool) -> list[str]:
    """One bullet per sentence pair; within it, one sentence per kind of token and what happened to it."""
    pairs: dict[tuple[object, ...], list[dict[str, object]]] = {}
    for c in tokens:
        pairs.setdefault((c["before_line"], c["after_line"], c["before"], c["after"]), []).append(c)
    out = []
    for (_, _, before, after), items in pairs.items():
        groups: dict[tuple[str, str, Optional[str]], list[str]] = {}
        for c in items:
            groups.setdefault((str(c["kind"]), str(c["token_status"]), c.get("token_file")),  # type: ignore[arg-type]
                              []).append(str(c["token"]))
        sentences = [_token_sentence(kind, status, toks, revision, file)
                     for (kind, status, file), toks in groups.items()]
        sentences[0] = f"In {_where(items[0], title)}, {_lower_first(sentences[0])}"
        out.append("- " + " ".join(sentences))
        marks = [str(c["token"]) for c in items]
        if before:
            out.append(f"  - Before the edit: {excerpt(before, marks)}")
        if after:
            out.append(f"  - After the edit: {excerpt(after, marks)}")
    return out


def _count_items(counts: dict[str, int]) -> str:
    return _listed([_q(k) + (f" ({n} times)" if n > 1 else "") for k, n in counts.items()])


def _count_lines(groups: dict[str, dict[str, dict[str, int]]]) -> list[str]:
    out = []
    for name, d in groups.items():
        for direction in ("removed", "added"):
            items = d.get(direction) or {}
            if not items:
                continue
            noun = COUNT_NOUNS.get(name, (name, name))[0 if len(items) == 1 else 1]
            out.append(f"- The {noun} {_count_items(items)} {'was' if len(items) == 1 else 'were'} "
                       f"{'removed' if direction == 'removed' else 'added'}.")
    return out


def to_markdown(report: dict[str, object]) -> str:
    revision = report.get("mode") == "revision"
    title = report.get("title")  # type: ignore[assignment]
    changes = report.get("sentence_changes", [])
    claims = [c for c in changes if c["token"] is None and c["kind"] != "wording"]  # type: ignore[union-attr]
    wording = [c for c in changes if c["kind"] == "wording"]  # type: ignore[union-attr]
    tokens = [c for c in changes if c["token"] is not None]  # type: ignore[union-attr]
    open_changes = [c for c in changes if c["severity"] == "protected" and not c["authorised"]]  # type: ignore[union-attr]
    shown = [c for c in changes if c["severity"] != "protected" or c["authorised"]]  # type: ignore[union-attr]
    rate = float(report["change_rate"])  # type: ignore[arg-type]
    lines = ["# Revision inventory: what changed between the two versions" if revision else "# What the edit changed",
             ""]
    requests = report.get("authorisations")
    widened = unrequested(report)
    if revision:
        claims_open = [c for c in widened if c["kind"] != "declaration"]
        declared = [c for c in widened if c["kind"] == "declaration"]
        verdict = ""
        if claims_open:
            one = len(claims_open) == 1
            verdict += (f" {_upper_first(_count_word(len(claims_open), 'claim', 'claims'))} now "
                        f"{'reaches' if one else 'reach'} further than the original and nothing in the list of "
                        f"requested changes asked for {'it' if one else 'them'}: restore the original wording, marked "
                        "below.")
        if declared:
            one = len(declared) == 1
            verdict += (f" {_upper_first(_count_word(len(declared), 'declaration', 'declarations'))} only the authors "
                        f"can make (consent, ethics, competing interests, funding, contributions) {'was' if one else 'were'} "
                        f"written, changed or removed, and nothing in the list of requested changes asked for "
                        f"{'it' if one else 'them'}: restore the original wording, marked below.")
        if not verdict:
            verdict = (" Every claim that now reaches further matches a requested change."
                       if report["summary"]["authorised"] else  # type: ignore[index]
                       " No claim reaches further than in the original.")
        lines.append(f"This is a revision, so content changes are expected. The comparison lists "
                     f"{_count_word(len(changes), 'change', 'changes')}, sentence by sentence; check "
                     f"{'it' if len(changes) == 1 else 'each'} against the response letter or the authors' "
                     "instructions."
                     + ("" if requests is None else verdict)
                     + (" Nothing here fails the run." if requests is None else ""))
    elif open_changes:
        one = len(open_changes) == 1
        lines.append(f"The edit changed content in {_count_word(len(open_changes), 'place', 'places')}, listed below; "
                     f"revert {'it' if one else 'each'} unless the authors asked for {'it' if one else 'them'}."
                     + (f" {_upper_first(_count_word(len(shown), 'other change needs', 'other changes need'))} "
                        "only to be shown to the authors." if shown else ""))
    elif report["protected"]:
        lines.append("The edit added or removed a number, citation, identifier, link, code span or technical term "
                     "that no single sentence accounts for; the counts over the whole text below name it. Revert the "
                     "change unless the authors asked for it."
                     + (f" {_upper_first(_count_word(len(shown), 'other change needs', 'other changes need'))} "
                        "only to be shown to the authors." if shown else ""))
    elif (report.get("only") or {}).get("outside"):  # type: ignore[union-attr]
        n = len(report["only"]["outside"])  # type: ignore[index]
        lines.append(f"The edit changed {_count_word(n, 'sentence', 'sentences')} outside the requested sections, "
                     f"listed below; restore {'it' if n == 1 else 'them'}. Within them it changed no content that "
                     "must be reverted.")
    elif shown:
        lines.append(f"The edit changed no content that must be reverted. "
                     f"{_upper_first(_count_word(len(shown), 'change', 'changes'))} should be shown to the authors.")
    else:
        lines.append("This comparison found no change of content. It cannot prove that the meaning is unchanged, so "
                     "read the edited passages in context.")
    only = report.get("only")
    if only:
        names = _listed([str(n) for n in only["sections"]])  # type: ignore[index]
        outside = only["outside"]  # type: ignore[index]
        lines += ["", "## Changes outside the requested sections", ""]
        if outside:
            one = len(outside) == 1
            lines.append(f"The request covered {names} only, so {'this change' if one else f'these {len(outside)} changes'}"
                         f" elsewhere {'was' if one else 'were'} not asked for: restore the original wording.")
            for o in outside:
                lines.append(f"- In {_where(o, title)}:")
                if o["before"]:
                    lines.append(f"  - Before the edit: {excerpt(o['before'])}")
                if o["after"]:
                    lines.append(f"  - After the edit: {excerpt(o['after'])}")
        else:
            lines.append(f"Every changed sentence lies in {names}, as the request asked.")
    level = (" More than half the words changed, so check the meaning and that the edit stayed within the request."
             if rate > CHANGE_STOP else " More than a quarter of the words changed, so reread the text for meaning."
             if rate > CHANGE_WARN else "")
    share = "Less than 1%" if 0 < rate < 0.005 else "None" if rate == 0 else f"About {round(100 * rate)}%"
    lines += ["", f"{share} of the original words changed ({report['words_before']} words before, "
                  f"{report['words_after']} after).{level}", ""]
    moved = report.get("moved_to")
    if moved:
        files = _listed([str(f) for f in moved["files"]])  # type: ignore[index]
        n, changed = int(moved["sentences"]), int(moved["sentences_changed"])  # type: ignore[index]
        lines += [f"{_upper_first(_count_word(n, 'sentence', 'sentences'))} moved from this text to {files}"
                  + (f"; {_count_word(changed, 'of them was', 'of them were')} changed on the way, and the changes "
                     "below compare each with its copy there." if changed else
                     (", word for word." if n else ".")), ""]
    relocations = int(report.get("summary", {}).get("relocated", 0))  # type: ignore[union-attr]
    if relocations:
        one = relocations == 1
        lines += [f"{_upper_first(_count_word(relocations, 'caveat', 'caveats'))} moved from "
                  f"{'its' if one else 'their'} sentence to another one; {'it is' if one else 'each is'} listed below "
                  "with where it went.", ""]
    lines.append("## Changes to what the claims say, sentence by sentence")
    lines += [""] + ([x for c in claims for x in _claim_lines(c, title, revision)] or  # type: ignore[arg-type]
                     ["No sentence changed how strong, how general or how qualified its claim is."])
    lines += ["", "## Numbers, citations and identifiers, sentence by sentence", ""]
    lines += _token_lines(tokens, title, revision) or [  # type: ignore[arg-type]
        "No sentence gained or lost a number, citation or identifier."]
    if revision:
        lines += ["", "## Other sentences that were reworded", ""]
        lines += [x for c in wording for x in _claim_lines(c, title, revision)] or [  # type: ignore[arg-type]
            "No other sentence lost or gained a word."]
    summary = report.get("summary", {})
    if summary.get("authorised") and requests is not None:  # type: ignore[union-attr]
        n = summary["authorised"]  # type: ignore[index]
        lines += ["", f"{_upper_first(_count_word(n, 'claim change matches', 'claim changes match'))} a requested "
                      f"change, named beside {'it' if n == 1 else 'each'}. {'It is' if n == 1 else 'They are'} still "
                      f"listed above so that the authors see {'it' if n == 1 else 'each one'} in place."]
    elif summary.get("authorised"):  # type: ignore[union-attr]
        n = summary["authorised"]  # type: ignore[index]
        marked = _count_word(n, "claim change is", "claim changes are")
        lines += ["", f"The authors asked for a claim correction, so {marked} marked as authorised. "
                      f"{'It is' if n == 1 else 'They are'} still listed above so that the authors see "
                      f"{'it' if n == 1 else 'each one'} in place."]
    for e in (requests or {}).get("unused", []):  # type: ignore[union-attr]
        lines += ["", f"A requested change from {_listed([str(x) for x in e['findings']])} matches no changed "
                      f"sentence; check that its edit landed: {excerpt(e['passage'])}."]
    lines += ["", "## Counts over the whole text", ""]
    lines += _count_lines(report["protected"]) or [  # type: ignore[arg-type]
        "No number, citation, identifier, link, code span or technical term was added or removed."]
    for name, items in (report.get("repeated_in_paragraph") or {}).items():  # type: ignore[union-attr]
        noun = COUNT_NOUNS.get(name, (name, name))[0 if len(items) == 1 else 1]
        lines.append(f"- The {noun} {_count_items(items)} {'was' if len(items) == 1 else 'were'} added again in a "
                     f"paragraph that already had {'it' if len(items) == 1 else 'them'}, which is not counted as a "
                     "change of content.")
    watched = _count_lines(report["watched"])  # type: ignore[arg-type]
    lines += ["", "Hedges, negations and claim words also change with ordinary editing, and these counts have no "
                  "location. The sections above list each sentence in which the checks saw a claim change; for a "
                  "word below that they do not explain, find it in the text and check its sentence." if watched else
              "No hedge, negation or claim word was added or removed."]
    if watched:
        lines += [""] + watched
    rewritten = report["rewritten_paragraphs"]
    lines += ["", "## Paragraphs that were largely rewritten", ""]
    for p in rewritten:  # type: ignore[union-attr]
        kept = round(100 * float(p["similarity"]))
        if p.get("moved_to"):
            lines.append(f"- A paragraph that began {_q(str(p['before']) + '…')} moved to {p['moved_to']} and kept "
                         f"about {kept}% of its wording there.")
        elif p["before"] and p["after"]:
            lines.append(f"- A paragraph kept about {kept}% of its wording. It began {_q(str(p['before']) + '…')} "
                         f"and now begins {_q(str(p['after']) + '…')}.")
        elif p["after"]:
            lines.append(f"- A new paragraph begins {_q(str(p['after']) + '…')}.")
        else:
            lines.append(f"- A paragraph that began {_q(str(p['before']) + '…')} was removed.")
    if not rewritten:
        lines.append("No paragraph was largely rewritten.")
    return "\n".join(lines) + "\n"


SUMMARY_PARTS = {"title": "the title", "abstract": "the Abstract", "conclusions": "the Conclusions"}


def _summary_place(f: dict[str, object], title: Optional[str]) -> str:
    if f["part"] == "title":
        return f"the title (line {f['line']})"
    return f"{_section(f, title)} (line {f['line']})"


def _summary_problem(f: dict[str, object]) -> str:
    """What the summary sentence says beyond its body sentence, in plain words."""
    kind, removed, added = f["kind"], f["removed"], f["added"]
    if kind in ("causal", "evidential"):
        words = CAUSAL_WORDS if kind == "causal" else EVIDENTIAL_WORDS
        measure = "The relation it states is" if kind == "causal" else "Its certainty is"
        if f["change"] == "raised":
            return (f"{measure} {_strength_words(f['strength_summary'], words)}, where the body's is "
                    f"{_strength_words(f['strength_body'], words)}.")
        return "Its claim differs in strength from the body's and one of them is negated: read both."
    if kind == "generality":
        return f"It reaches further than the body: {_quoted_list(added)}."
    return {"scope": f"It leaves out the scope the body states: {_quoted_list(removed)}.",
            "limitation": f"It leaves out the limit the body states: {_quoted_list(removed)}.",
            "null_result": f"It leaves out the null result the body reports: {_quoted_list(removed)}.",
            "evidence_status": f"It no longer says how the finding was obtained, which the body does: "
                               f"{_quoted_list(removed)}."}.get(str(kind), "Read it against the body.")


def summary_markdown(report: dict[str, object]) -> str:
    title = report.get("title")  # type: ignore[assignment]
    findings: list[dict[str, object]] = report["findings"]  # type: ignore[assignment]
    unmatched: list[dict[str, object]] = report["unmatched"]  # type: ignore[assignment]
    stronger = [f for f in findings if f["kind"] in RAISING]
    left_out = [f for f in findings if f["kind"] not in RAISING]
    lines = ["# Do the title, Abstract and Conclusions claim more than the body?", ""]
    n = len({(f["section"], f["line"]) for f in findings})
    if findings:
        lines.append(f"{_upper_first(_count_word(n, 'sentence', 'sentences'))} of the summary "
                     f"{'claims' if n == 1 else 'claim'} more than the body or {'leaves' if n == 1 else 'leave'} out "
                     "a limit the body states. Each is quoted below with the body sentence it was compared with: "
                     "bring the summary down to what the body shows, or give it the qualifier the body has.")
    else:
        lines.append("No sentence of the title, the Abstract or the Conclusions claims more than the body sentences "
                     "closest to it, or leaves out a limit the closest one states. The check compares wording, so "
                     "still read the summary against the Results.")
    lines += ["", f"It compared {_count_word(int(report['summary_sentences']), 'summary sentence', 'summary sentences')}"
                  f" with {_count_word(int(report['body_sentences']), 'body sentence', 'body sentences')} (the "
                  "Introduction and the back matter are neither)."
                  + (f" {_upper_first(_count_word(len(unmatched), 'summary sentence has', 'summary sentences have'))}"
                     f" no close body sentence and {'is' if len(unmatched) == 1 else 'are'} listed at the end."
                     if unmatched else ""), ""]
    for heading, group in (("Claims stronger than the body", stronger),
                           ("Limits the body states that the summary leaves out", left_out)):
        if not group:
            continue
        lines += [f"## {heading}", ""]
        for f in group:
            body = {"section": f["body_section"]}
            lines += [f"- In {_summary_place(f, title)}: {_summary_problem(f)}",
                      f"  - The summary: {excerpt(f['sentence'], f['added'])}",
                      f"  - The body, in {_section(body, title)} (line {f['body_line']}): "
                      f"{excerpt(f['body_sentence'], f['removed'])}"]
        lines.append("")
    if unmatched:
        lines += ["## Summary sentences with no close body sentence", "",
                  "No sentence of the body shares enough words with these to be compared. Check that the body "
                  "states each, or that it is background.", ""]
        lines += [f"- In {_summary_place(u, title)}: {excerpt(u['sentence'])}" for u in unmatched]
    return "\n".join(lines).rstrip("\n") + "\n"


@app.command()
def main(
    before: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Original, or the edited file with --against")],
    after: Annotated[Optional[Path], typer.Argument(exists=True, dir_okay=False, help="Edited version")] = None,
    against: Annotated[Optional[str], typer.Option(help="Compare BEFORE (edited, on disk) with this git ref")] = None,
    threshold: Annotated[float, typer.Option(help="Flag paragraphs below this similarity")] = 0.5,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the report as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Also write the Markdown report to this file")] = None,
    revision: Annotated[bool, typer.Option("--revision", help="Inventory mode for a revised manuscript: list every "
                                           "content change with section and line; exit 0, or 1 with --authorised when "
                                           "a claim widened or a declaration changed with no matching "
                                           "entry")] = False,
    allow_strengthening: Annotated[bool, typer.Option("--allow-strengthening", help="The authors authorised a claim "
                                                      "correction: report claim changes without failing on them")] = False,
    moved_to: Annotated[Optional[list[Path]], typer.Option(
        "--moved-to", exists=True, dir_okay=False, help="A file part of the text was moved to (a supplement, say); "
        "repeat for several. Text found there counts as moved, not removed")] = None,
    relocated: Annotated[bool, typer.Option("--relocated", help="A story edit moved caveats on purpose: a lost scope, "
                                            "limiting, null-result or evidence-status marker is a warning when another "
                                            "sentence of the same top-level section, about the same thing, states it "
                                            "(never for a scope or evidence status lost from the Abstract or "
                                            "Introduction); so is a number moved within its section and a headline "
                                            "that restates its paragraph. Citations and identifiers stay "
                                            "protected")] = False,
    relocated_in: Annotated[Optional[list[Path]], typer.Option(
        "--relocated-in", help="Limit --relocated (implied) to these changes: a stage's run folder (its change "
        "records and findings.json, e.g. RUN/manuscript-story), one change record, or a YAML/JSON list of passages; "
        "repeatable. A missing path adds nothing")] = None,
    authorised: Annotated[Optional[Path], typer.Option(
        "--authorised", exists=True, dir_okay=False, help="YAML or JSON list of the claim changes a request asked "
        "for (per entry: passage, at least three words in a row copied from the sentence; finding, or comment with "
        "a referee comment id): a widened claim or a changed declaration no entry matches fails, also with "
        "--revision")] = None,
    only: Annotated[Optional[list[str]], typer.Option(
        "--only", help="A section the request covered, by its heading ('Discussion', or a path such as "
        "'Results > Speed'); repeatable. A sentence changed, moved, added or deleted anywhere else fails")] = None,
    summary: Annotated[bool, typer.Option(
        "--summary", help="Check one manuscript: a sentence of the title, the Abstract or the Conclusions that claims "
        "more than the body sentences closest to it, or leaves out a scope, limit or null result the closest one "
        "states, fails")] = False,
) -> None:
    if summary:
        if after is not None or against or revision or only or moved_to or relocated or relocated_in or authorised:
            raise typer.BadParameter("--summary checks one manuscript on its own: give only the file, and --json or "
                                     "--md if wanted.")
        try:
            result = summary_check(before.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        markdown = summary_markdown(result)
        if json_out:
            json_out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        if md_out:
            md_out.write_text(markdown, encoding="utf-8")
        typer.echo(markdown)
        raise typer.Exit(code=1 if result["findings"] else 0)
    if against:
        before_text, after_text = _git_show(before.resolve(), against), before.read_text(encoding="utf-8")
    elif after is not None:
        before_text, after_text = before.read_text(encoding="utf-8"), after.read_text(encoding="utf-8")
    else:
        raise typer.BadParameter("Give the edited file as the second argument, or name the git version to "
                                 "compare with in --against.")
    moved = [(path.name, path.read_text(encoding="utf-8")) for path in moved_to or []]
    requests = None
    if authorised is not None:
        try:
            requests = parse_authorisations(yaml.safe_load(authorised.read_text(encoding="utf-8")))
        except (yaml.YAMLError, ValueError) as exc:
            raise typer.BadParameter(f"{authorised}: {exc}") from exc
    scope = relocation_passages(relocated_in) if relocated_in else None
    try:
        report = compare(before_text, after_text, threshold, revision=revision,
                         allow_strengthening=allow_strengthening, moved=moved, relocated=relocated,
                         authorised=requests, relocated_in=scope, only=only)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    markdown = to_markdown(report)
    if json_out:
        json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    if md_out:
        md_out.write_text(markdown, encoding="utf-8")
    typer.echo(markdown)
    raise typer.Exit(code=exit_code(report))


def _utf8_console() -> None:
    """Print UTF-8 whatever the console's code page (a Windows console is often cp1252), so quotes never crash."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # a stream that cannot change its encoding keeps it
                pass


if __name__ == "__main__":
    _utf8_console()
    app()
