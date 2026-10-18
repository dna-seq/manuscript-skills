"""manuscript-revision-marks/scripts/rev_marks.py on a real document: docs/skill-landscape-2026-10.md, read at
test time, with marks put around its own lines and sentences, chosen by a seeded draw rather than pinned,
so editing that survey never breaks a test. The document itself is never written. Run with `uv run pytest`."""
from __future__ import annotations

import html
import importlib.util
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RM = ROOT / "skills" / "manuscript-revision-marks" / "scripts" / "rev_marks.py"
DOC = ROOT / "docs" / "skill-landscape-2026-10.md"
BY = "owner:2026-09-25,agent:2026-10-10"
SEED = 20261010

spec = importlib.util.spec_from_file_location("rev_marks", RM)
rm = importlib.util.module_from_spec(spec)
sys.modules["rev_marks"] = rm
spec.loader.exec_module(rm)
Code = rm.Code


@dataclass
class Result:
    rc: int
    out: str


def py(script: Path, *args) -> Result:
    """Run a script under this interpreter, stdout and stderr together."""
    p = subprocess.run([sys.executable, str(script), *map(str, args)], text=True, check=False,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return Result(p.returncode, p.stdout)


SENTENCE = re.compile(r"[A-Z][^.!?\r\n`*<>]{12,}[.!?]")


def open_mark(sid: str, rounds: int = 2, by: str = BY) -> str:
    return f"<!-- @rev {sid} rounds={rounds} by={by} -->"


def close_mark(sid: str) -> str:
    return f"<!-- @/rev {sid} -->"


def baseline() -> str:
    text = rm.read_source(DOC)
    assert "@rev" not in text, "the document carries marks of its own; pick another"
    return text


def wrap_inline(text: str, start: int, end: int, sid: str, rounds: int = 2, by: str = BY) -> str:
    """Glue a mark pair to text[start:end] without adding any whitespace."""
    return text[:start] + open_mark(sid, rounds, by) + text[start:end] + close_mark(sid) + text[end:]


def wrap_lines(text: str, start: int, end: int, sid: str, newline: str = "\n") -> str:
    """Marks on lines of their own around the whole lines text[start:end]. At the end of a file with
    no final terminator the closing mark becomes a new last line."""
    assert start == 0 or text[start - 1] == "\n"
    if end == len(text) and not text.endswith("\n"):
        closing = newline + close_mark(sid)
    else:
        assert text[end - 1] == "\n"
        closing = close_mark(sid) + newline
    return text[:start] + open_mark(sid) + newline + text[start:end] + closing + text[end:]


def line_span(text: str, needle: str) -> tuple[int, int]:
    at = text.index(needle)
    start = text.rfind("\n", 0, at) + 1
    nl = text.find("\n", at + len(needle))
    return start, len(text) if nl == -1 else nl + 1


def span(text: str, needle: str) -> tuple[int, int]:
    at = text.index(needle)
    return at, at + len(needle)


def prose_sentences(text: str) -> list[str]:
    """Sentences on prose lines outside code, each unique in the document, none opening its line: an
    inline mark put before one would open the line, which the tool warns of (INLINE_AT_LINE_START)."""
    code = rm.code_ranges(text)
    found = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        if raw.strip() and not raw.lstrip().startswith(("#", "|", "-", "```", ">")) and not rm.in_ranges(offset, code):
            m = next((m for m in SENTENCE.finditer(raw) if raw[: m.start()].strip()), None)
            if m and raw[: m.start()].count("`") % 2 == 0 and text.count(m.group()) == 1:
                found.append(m.group())
        offset += len(raw)
    return found


def picks() -> tuple[str, str, str]:
    """Two sentences on different lines, and a unique non-ASCII run, drawn from the document."""
    text = baseline()
    sentences = prose_sentences(text)
    rng = random.Random(SEED)
    a = rng.choice(sentences)
    b = rng.choice([s for s in sentences if line_span(text, s) != line_span(text, a)])
    uni = next(m.group() for m in re.finditer(r"\S*[^\x00-\x7f]\S*", text)
               if text.count(m.group()) == 1 and not rm.in_ranges(m.start(), rm.code_ranges(text))
               and "<!--" not in m.group())
    return a, b, uni


A, B, UNI = picks()


def snippet() -> str:
    text = baseline()
    return text[slice(*line_span(text, A))] + "\n" + text[slice(*line_span(text, B))]


def test_the_document_has_no_mark_and_strips_to_itself():
    text = baseline()
    found = rm.parse(text)
    assert found.errors == () and found.clean_text() == text


def test_hand_placed_marks_round_trip_byte_for_byte():
    original = baseline()
    marked = wrap_inline(original, *span(original, A), "C3")
    marked = wrap_inline(marked, *span(marked, UNI), "N1")
    marked = wrap_lines(marked, *line_span(marked, B), "C2")
    found = rm.parse(marked)
    assert found.errors == ()
    assert {s.id for s in found.segments} == {"C3", "N1", "C2"}
    assert found.segment("C3").text == A and found.segment("N1").text == UNI
    assert rm.strip_marks(marked).encode() == original.encode()


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("final_newline", [True, False], ids=["final-newline", "no-final-newline"])
def test_seeded_random_marks_round_trip(newline, final_newline):
    """Many segments on random lines and sentences, both placements, nested too."""
    original = baseline().replace("\n", newline)
    if not final_newline:
        original = original.rstrip("\r\n")
    code = rm.code_ranges(original)
    rng = random.Random(SEED)
    starts = [0] + [m.end() for m in re.finditer("\n", original)]
    lines = [(s, original.find("\n", s) + 1 if original.find("\n", s) != -1 else len(original))
             for s in starts if s < len(original)]
    # a line whose end sits inside code (an inline span carried on to the next line) would put a
    # closing mark inside that span, where it is an example and rightly refused: never chosen
    prose = [(s, e) for s, e in lines
             if original[s:e].strip() and not rm.in_ranges(s, code) and not rm.in_ranges(e - 1, code)]
    chosen = [prose[-1], *rng.sample(prose[:-1], 39)]  # the last line exercises the end-of-file rule
    marked, expected = original, set()
    for index, (start, end) in sorted(enumerate(chosen), key=lambda item: -item[1][0]):
        line = original[start:end]
        sentence = next((m for m in SENTENCE.finditer(line) if line[: m.start()].count("`") % 2 == 0), None)
        if index % 3 != 0 and sentence is not None:
            marked = wrap_inline(marked, start + sentence.start(), start + sentence.end(), f"C{index + 1}")
            expected.add(f"C{index + 1}")
            if index % 3 == 2:
                grow = len(open_mark(f"C{index + 1}")) + len(close_mark(f"C{index + 1}"))
                marked = wrap_lines(marked, start, end + grow, f"N{index + 1}", newline)
                expected.add(f"N{index + 1}")
        else:
            marked = wrap_lines(marked, start, end, f"C{index + 1}", newline)
            expected.add(f"C{index + 1}")
    found = rm.parse(marked)
    assert found.errors == ()
    assert {s.id for s in found.segments} == expected and len(expected) >= 40
    assert any(s.depth == 1 for s in found.segments)
    assert rm.strip_marks(marked).encode() == original.encode()


def case(kind: str) -> str:
    body, a, b = snippet(), A, B

    def one(om: str, cm: str = "<!-- @/rev C1 -->") -> str:
        return body.replace(a, om + a + cm, 1)

    return {
        "unbalanced-open": lambda: open_mark("C1") + "\n" + body,
        "unbalanced-close": lambda: body + close_mark("C1") + "\n",
        "crossed": lambda: open_mark("C1") + "\n" + body.replace(a, a + open_mark("C2"), 1)
        .replace(b, close_mark("C1") + b, 1) + close_mark("C2") + "\n",
        "self-nested": lambda: open_mark("C1") + "\n" + one(open_mark("C1")) + close_mark("C1") + "\n",
        "duplicate-id": lambda: one(open_mark("C1")).replace(b, open_mark("C1") + b + close_mark("C1"), 1),
        "rounds-zero": lambda: open_mark("C1", rounds=0) + "\n" + body + close_mark("C1") + "\n",
        "rounds-word": lambda: one(f"<!-- @rev C1 rounds=two by={BY} -->"),
        "rounds-negative": lambda: one(f"<!-- @rev C1 rounds=-1 by={BY} -->"),
        "date-month-13": lambda: one(open_mark("C1", 1, "owner:2026-13-01")),
        "date-feb-30": lambda: one(open_mark("C1", 1, "owner:2026-02-30")),
        "date-european": lambda: one(open_mark("C1", 1, "owner:25.09.2026")),
        "date-compact": lambda: one(open_mark("C1", 1, "owner:20260925")),
        "reviewer-without-date": lambda: one(open_mark("C1", 1, "owner")),
        "unknown-key": lambda: one("<!-- @rev C1 rounds=1 by=owner:2026-09-25 note=x -->"),
        "missing-key": lambda: one("<!-- @rev C1 rounds=1 -->"),
        "duplicate-key": lambda: one(f"<!-- @rev C1 rounds=1 rounds=1 by={BY} -->"),
        "bad-id": lambda: one(open_mark("c1"), "<!-- @/rev c1 -->"),
        "unterminated": lambda: body.replace(a, "<!-- @rev C1 rounds=1 by=owner:2026-09-25 " + a, 1),
        "multiline-mark": lambda: "<!-- @rev C1\nrounds=1 by=owner:2026-09-25 -->\n" + body + close_mark("C1") + "\n",
        "close-with-attributes": lambda: one(open_mark("C1"), "<!-- @/rev C1 rounds=1 -->"),
        "empty-inline": lambda: body.replace(a, open_mark("C1") + close_mark("C1") + a, 1),
        "empty-own-line": lambda: open_mark("C1") + "\n" + close_mark("C1") + "\n" + body,
        "whitespace-only": lambda: body.replace(a, open_mark("C1") + "   " + close_mark("C1") + a, 1),
        "unicode-inside": lambda: baseline().replace(UNI, open_mark("C1") + UNI + close_mark("C1"), 1),
        "mark-at-file-start": lambda: open_mark("C1") + "\n" + body + close_mark("C1") + "\n",
        "mark-at-file-end": lambda: open_mark("C1") + "\n" + body.rstrip("\n") + "\n" + close_mark("C1"),
        "nested-distinct-ids": lambda: open_mark("C1") + "\n" + body.replace(b, open_mark("N2") + b + close_mark("N2"), 1)
        + close_mark("C1") + "\n",
        "example-in-code-fence": lambda: body + "\n```markdown\n" + open_mark("C1") + "\n```\n",
        "example-in-inline-code": lambda: body + "\nWrite `" + close_mark("C1") + "` after the segment.\n",
    }[kind]()


ERRORS = {
    "unbalanced-open": Code.UNCLOSED, "unbalanced-close": Code.UNOPENED, "crossed": Code.CROSSED,
    "self-nested": Code.SELF_NESTED, "duplicate-id": Code.DUPLICATE_ID, "rounds-zero": Code.BAD_ROUNDS,
    "rounds-word": Code.BAD_ROUNDS, "rounds-negative": Code.BAD_ROUNDS, "date-month-13": Code.BAD_DATE,
    "date-feb-30": Code.BAD_DATE, "date-european": Code.BAD_DATE, "date-compact": Code.BAD_DATE,
    "reviewer-without-date": Code.BAD_REVIEWER, "unknown-key": Code.UNKNOWN_KEY,
    "missing-key": Code.MISSING_KEY, "duplicate-key": Code.DUPLICATE_KEY, "bad-id": Code.BAD_ID,
    "unterminated": Code.MALFORMED, "multiline-mark": Code.MALFORMED, "close-with-attributes": Code.MALFORMED,
    "empty-inline": Code.EMPTY_SEGMENT, "empty-own-line": Code.EMPTY_SEGMENT, "whitespace-only": Code.EMPTY_SEGMENT,
}
VALID = {"unicode-inside": 1, "mark-at-file-start": 1, "mark-at-file-end": 1, "nested-distinct-ids": 2,
         "example-in-code-fence": 0, "example-in-inline-code": 0}


@pytest.mark.parametrize(("kind", "code"), ERRORS.items(), ids=list(ERRORS))
def test_each_malformed_case_is_named_and_strip_refuses(kind, code, tmp_path):
    text = case(kind)
    assert code in {i.code for i in rm.parse(text).errors}
    with pytest.raises(rm.MarkErrors):
        rm.strip_marks(text)
    src = tmp_path / "doc.md"
    src.write_bytes(text.encode())
    r = py(RM, "lint", src)
    assert r.rc == 1 and str(code) in r.out, r.out
    assert py(RM, "strip", src).rc == 1  # never a half-recognised mark in the twin
    assert not rm.clean_twin_path(src).exists()


@pytest.mark.parametrize(("kind", "segments"), VALID.items(), ids=list(VALID))
def test_valid_placements_lint_clean_and_strip_only_the_marks(kind, segments):
    text = case(kind)
    found = rm.parse(text)
    assert found.errors == () and len(found.segments) == segments
    clean = found.clean_text()
    if segments == 0:
        assert clean == text
    if kind == "unicode-inside":
        assert found.segments[0].text == UNI and clean == baseline()
    if kind in ("mark-at-file-start", "mark-at-file-end"):
        assert clean == snippet().rstrip("\n") + ("\n" if kind == "mark-at-file-start" else "")


def test_rounds_unlike_the_reviewer_count_is_a_warning_and_strict_fails(tmp_path):
    text = snippet().replace(B, open_mark("C1", 3) + B + close_mark("C1"), 1)
    found = rm.parse(text)
    assert found.errors == () and [i.code for i in found.warnings] == [Code.ROUNDS_REVIEWERS_MISMATCH]
    src = tmp_path / "doc.md"
    src.write_bytes(text.encode())
    assert py(RM, "lint", src).rc == 0
    assert py(RM, "lint", "--strict", src).rc == 1


def test_an_inline_mark_between_two_spaces_is_flagged():
    text = snippet().replace(B, " " + open_mark("C1") + " " + B + close_mark("C1"), 1)
    assert Code.AMBIGUOUS_SPACE in {i.code for i in rm.parse(text).warnings}


def marked() -> tuple[str, str]:
    original = baseline()
    m = wrap_inline(original, *span(original, A), "C3")
    m = wrap_inline(m, *span(m, UNI), "N1", rounds=1, by="agent:2026-10-10")
    m = wrap_lines(m, *line_span(m, B), "C2")
    return original, m


def test_report_counts_equal_the_marked_segments_and_the_heatmap_is_self_contained(tmp_path):
    original, m = marked()
    t = rm.totals(rm.parse(m))
    assert {k: t[k] for k in ("segments", "rounds", "comments", "max rounds")} == \
        {"segments": 3, "rounds": 5, "comments": 3, "max rounds": 2}
    src, heat = tmp_path / "doc.md", tmp_path / "heat.html"
    src.write_bytes(m.encode())
    r = py(RM, "report", src, "--html", heat)
    assert r.rc == 0, r.out
    rows = {line.split()[0]: line.split()[1] for line in r.out.splitlines() if re.match(r"^[CN][0-9]+ ", line)}
    assert rows == {"C2": "2", "C3": "2", "N1": "1"}
    page = heat.read_text(encoding="utf-8")
    assert len(re.findall(r"<mark ", page)) == page.count("</mark>") == 3
    assert re.search(r"<(script|link|img|iframe)\b|url\(|(src|href)=\"https?:", page) is None
    assert "@rev" not in page
    body = page[page.index('<div class="doc">') + len('<div class="doc">'): page.rindex("</div>\n</main>")]
    assert html.unescape(re.sub(r"</?mark[^>]*>", "", body)) == original


def test_bump_changes_exactly_one_mark(tmp_path):
    original, m = marked()
    src = tmp_path / "doc.md"
    src.write_bytes(m.encode())
    before = rm.parse(m)
    r = py(RM, "bump", src, "C3", "--by", "second:2026-10-11")
    assert r.rc == 0 and "C3: rounds=3" in r.out, r.out
    after_text = rm.read_source(src)
    after = rm.parse(after_text)
    assert {b.id for b, a in zip(before.segments, after.segments, strict=True) if b.attributes != a.attributes} == {"C3"}
    c3b, c3a = before.segment("C3"), after.segment("C3")
    assert c3a.attributes.by == (*c3b.attributes.by, rm.Entry("second", date(2026, 10, 11)))
    assert after_text[: c3a.open.start] == m[: c3b.open.start]
    assert after_text[c3a.open.end:] == m[c3b.open.end:]
    assert rm.strip_marks(after_text) == original


def test_bump_defaults_to_today_and_refuses_unknown_ids_and_bad_dates(tmp_path):
    _, m = marked()
    assert rm.parse_entry("second", date(2026, 10, 12)) == rm.Entry("second", date(2026, 10, 12))
    with pytest.raises(KeyError):
        rm.bump_segment(m, "C99", rm.Entry("second", date(2026, 10, 12)))
    src = tmp_path / "doc.md"
    src.write_bytes(m.encode())
    assert py(RM, "bump", src, "C99", "--by", "second").rc == 1
    assert py(RM, "bump", src, "C3", "--by", "second:10/11/2026").rc == 2
    assert rm.read_source(src) == m


def test_strip_writes_the_twin_and_check_sees_it_go_stale(tmp_path):
    original, m = marked()
    src = tmp_path / "doc.md"
    twin = tmp_path / "doc.clean.md"
    src.write_bytes(m.encode())
    assert py(RM, "strip", src, "--check").rc == 1
    assert py(RM, "strip", src).rc == 0
    assert twin.read_bytes() == original.encode()
    assert py(RM, "strip", src, "--check").rc == 0
    src.write_bytes(m.replace(A, A[:-1] + "!", 1).encode())
    assert py(RM, "strip", src, "--check").rc == 1
    assert py(RM, "strip", twin).rc == 1
    out = tmp_path / "out" / "x.md"
    out.parent.mkdir()
    assert py(RM, "strip", src, "--out", out).rc == 0
    assert A[:-1] + "!" in out.read_text(encoding="utf-8")


def test_a_missing_file_could_not_run(tmp_path):
    r = py(RM, "lint", tmp_path / "nothing.md")
    assert r.rc == 3 and "cannot read" in r.out


def test_blind_spots_are_exactly_the_uncovered_paragraphs(tmp_path):
    unmarked = rm.parse(baseline())
    every = rm.paragraphs(unmarked)
    assert every and [p.line for p in rm.blind_spots(unmarked)] == [p.line for p in every]
    _, m = marked()
    found = rm.parse(m)
    ps, spots, t = rm.paragraphs(found), rm.blind_spots(found), rm.totals(found)
    covered = [p for p in ps if p.covered]
    assert covered and len(covered) + len(spots) == len(ps) == t["paragraphs"] and t["blind spots"] == len(spots)
    for p in covered:
        assert any(s.open.start < p.end and p.start < s.close.end for s in found.segments)
    src = tmp_path / "doc.md"
    src.write_bytes(m.encode())
    r = py(RM, "report", src, "--blind")
    header = next(line for line in r.out.splitlines() if line.startswith("BLIND SPOTS"))
    assert f"({len(spots)} of" in header
    assert [int(line.split()[0]) for line in r.out.split(header, 1)[1].strip().splitlines()] == [p.line for p in spots]


def test_marking_a_blind_paragraph_removes_exactly_that_one():
    text = baseline()
    before = rm.blind_spots(rm.parse(text))
    target = before[len(before) // 2]
    lines = text.splitlines(keepends=True)
    lines.insert(target.line, close_mark("N9") + "\n")
    lines.insert(target.line - 1, open_mark("N9", rounds=1, by="agent:2026-10-10") + "\n")
    after = rm.blind_spots(rm.parse("".join(lines)))
    assert len(after) == len(before) - 1
    assert {p.text for p in after} == {p.text for p in before} - {target.text}


def test_a_crossed_pair_is_one_error_and_the_inner_segment_still_pairs():
    """The crossed opening leaves the stack, so it is not also reported as never closed."""
    found = rm.parse(case("crossed"))
    assert [i.code for i in found.errors] == [Code.CROSSED]
    assert [s.id for s in found.segments] == ["C2"]


# --- LaTeX: marks as comment lines (D92) -------------------------------------------------------------
# A small document written for the test, each line tagged with whether it is prose: the classification
# is what these tests pin, so the document is pinned too.

TEX_LINES = [
    (r"\documentclass{article}", False),
    (r"\usepackage{fontspec}", False),
    (r"\title{A title the preamble holds}", False),
    (r"\newcommand{\kit}{the kit}", False),
    (r"\begin{document}", False),
    (r"\maketitle", False),
    (r"\begin{abstract}", False),
    (r"We measure what a review round reads, and what it leaves alone.", True),
    (r"\end{abstract}", False),
    (r"", False),
    (r"\section{Introduction}", False),
    (r"\label{sec:intro}", False),
    (r"A paragraph opens here, at 50\% of the time, with \emph{some} emphasis", True),
    (r"and carries on to a second line.  % a note to self, not prose", True),
    (r"% a comment line on its own", False),
    (r"\textbf{Bold opening} and the rest of the sentence.", True),
    (r"\begin{itemize}", False),
    (r"  \item The first item of the list.", True),
    (r"  \item", False),
    (r"\end{itemize}", False),
    (r"\begin{figure}[h]", False),
    (r"  \centering", False),
    (r"  \includegraphics[width=\linewidth]{figure-one}", False),
    (r"  \caption{What the figure shows, in \emph{words}.}", True),
    (r"\end{figure}", False),
    (r"\begin{verbatim}", False),
    (r"% @rev C9 rounds=1 by=owner:2026-09-25", False),
    (r"code, not prose", False),
    (r"\end{verbatim}", False),
    (r"Write \verb|% @/rev C9| to close a segment.", True),
    (r"\begin{tabular}{ll}", False),
    (r"one & two \\", True),
    (r"\hline", False),
    (r"\end{tabular}", False),
    (r"\[", False),
    (r"  E = m c^2", True),
    (r"\]", False),
    (r"\subsection*{A starred heading}", False),
    (r"The last paragraph \cite{someone2026}.", True),
    (r"\end{document}", False),
    (r"Text after the end is not the document.", False),
]
TEX = "".join(line + "\n" for line, _ in TEX_LINES)
TEX_PROSE = [n for n, (_, prose) in enumerate(TEX_LINES, start=1) if prose]
TEX_VERBATIM = range(25, 29)  # 0-based lines of the verbatim block
TEX_SYN = rm.Syntax.TEX


def tex_open(sid: str, rounds: int = 2, by: str = BY) -> str:
    return f"% @rev {sid} rounds={rounds} by={by}"


def tex_close(sid: str) -> str:
    return f"% @/rev {sid}"


def tex_wrap(lines: list[str], first: int, last: int, sid: str, rounds: int = 2, by: str = BY) -> list[str]:
    """Marks on lines of their own around lines[first:last] (0-based, last exclusive)."""
    return [*lines[:first], tex_open(sid, rounds, by), *lines[first:last], tex_close(sid), *lines[last:]]


def tex_marked() -> str:
    lines = [line for line, _ in TEX_LINES]
    lines = tex_wrap(lines, 38, 39, "C4", rounds=1, by="agent:2026-10-10")
    lines = tex_wrap(lines, 15, 18, "C3")
    lines = tex_wrap(lines, 12, 14, "C2")
    return "".join(line + "\n" for line in lines)


def test_tex_syntax_follows_the_suffix():
    assert rm.syntax_for(rm.Path("paper.tex")) == TEX_SYN
    assert rm.syntax_for(rm.Path("paper.md")) == rm.syntax_for(rm.Path("notes.txt")) == rm.Syntax.MARKDOWN
    assert rm.clean_twin_path(rm.Path("d/paper.tex")) == rm.Path("d/paper.clean.tex")
    assert rm.clean_twin_path(rm.Path("d/paper.md")) == rm.Path("d/paper.clean.md")


def test_tex_examples_and_escaped_percents_are_no_marks():
    found = rm.parse(TEX, TEX_SYN)
    assert found.errors == () and found.marks == () and found.clean_text() == TEX
    escaped = "Half is 50\\% @rev C1 rounds=1 by=owner:2026-09-25 of it.\n"
    assert rm.parse(escaped, TEX_SYN).marks == ()


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("final_newline", [True, False], ids=["final-newline", "no-final-newline"])
def test_tex_seeded_marks_round_trip_byte_for_byte(newline, final_newline):
    """Single lines drawn by a seed, the last line always among them (the end-of-file rule), and one
    segment around several of them, so segments nest."""
    lines = [line for line, _ in TEX_LINES]
    eligible = [i for i in range(len(lines) - 1) if i not in TEX_VERBATIM]
    chosen = sorted({*random.Random(SEED).sample(eligible, 12), len(lines) - 1})
    outer = (chosen[2], chosen[6])  # around chosen[2] .. chosen[6], inclusive
    marked: list[str] = []
    for i, line in enumerate(lines):
        if i == outer[0]:
            marked.append(tex_open("N1"))
        if i in chosen:
            marked.append(tex_open(f"C{i}"))
        marked.append(line)
        if i in chosen:
            marked.append(tex_close(f"C{i}"))
        if i == outer[1]:
            marked.append(tex_close("N1"))
    end = newline if final_newline else ""
    original, text = newline.join(lines) + end, newline.join(marked) + end
    found = rm.parse(text, TEX_SYN)
    assert found.errors == (), found.errors
    assert {s.id for s in found.segments} == {"N1", *(f"C{i}" for i in chosen)}
    assert any(s.depth == 1 for s in found.segments)
    assert rm.strip_marks(text, TEX_SYN).encode() == original.encode()


TEX_ERRORS = {
    "inline-after-text": ("A sentence. " + tex_open("C1") + "\nMore.\n" + tex_close("C1") + "\n", Code.INLINE_MARK),
    "inline-after-break": (tex_open("C1") + "\nA line\\\\% @/rev C1\n", Code.INLINE_MARK),
    "pair-on-one-line": (tex_open("C1") + " % @/rev C1\nText.\n", Code.MALFORMED),
    "unclosed": (tex_open("C1") + "\nText.\n", Code.UNCLOSED),
    "bad-id": ("% @rev c1 rounds=1 by=owner:2026-09-25\nText.\n% @/rev c1\n", Code.BAD_ID),
    "missing-key": ("% @rev C1 rounds=1\nText.\n" + tex_close("C1") + "\n", Code.MISSING_KEY),
    "empty": (tex_open("C1") + "\n" + tex_close("C1") + "\nText.\n", Code.EMPTY_SEGMENT),
}


@pytest.mark.parametrize("kind", list(TEX_ERRORS))
def test_tex_malformed_marks_are_named_and_strip_refuses(kind, tmp_path):
    text, code = TEX_ERRORS[kind]
    assert code in {i.code for i in rm.parse(text, TEX_SYN).errors}
    src = tmp_path / "doc.tex"
    src.write_bytes(text.encode())
    r = py(RM, "lint", src)
    assert r.rc == 1 and str(code) in r.out, r.out
    assert py(RM, "strip", src).rc == 1
    assert not (tmp_path / "doc.clean.tex").exists()


def test_the_same_inline_mark_in_markdown_is_no_error():
    """Inline marks stay Markdown's; only a .tex refuses them."""
    found = rm.parse("A sentence. <!-- @rev C1 rounds=1 by=owner:2026-09-25 -->More.<!-- @/rev C1 -->\n")
    assert found.errors == () and len(found.segments) == 1


def test_tex_strip_check_report_and_bump_on_the_command_line(tmp_path):
    src, twin = tmp_path / "paper.tex", tmp_path / "paper.clean.tex"
    src.write_bytes(tex_marked().encode())
    assert py(RM, "strip", src, "--check").rc == 1
    r = py(RM, "strip", src)
    assert r.rc == 0 and "paper.clean.tex" in r.out, r.out
    assert twin.read_bytes() == TEX.encode()
    assert py(RM, "strip", src, "--check").rc == 0
    assert py(RM, "strip", twin).rc == 1  # a twin is never stripped again
    r = py(RM, "report", src, "--blind")
    assert r.rc == 0, r.out
    rows = {line.split()[0]: line.split()[1] for line in r.out.splitlines() if re.match(r"^C[0-9]+ ", line)}
    assert rows == {"C2": "2", "C3": "2", "C4": "1"}
    before = rm.read_source(src)
    r = py(RM, "bump", src, "C3", "--by", "second:2026-10-11")
    assert r.rc == 0 and "C3: rounds=3" in r.out, r.out
    after = rm.read_source(src)
    changed = [(a, b) for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b]
    assert changed == [(tex_open("C3"), tex_open("C3", 3, BY + ",second:2026-10-11"))]
    assert rm.strip_marks(after, TEX_SYN) == TEX
    assert py(RM, "strip", src, "--check").rc == 0  # a bump touches only a mark: the twin stays current


def test_tex_blind_spots_are_the_prose_lines_of_the_body():
    found = rm.parse(TEX, TEX_SYN)
    assert [p.line for p in rm.paragraphs(found)] == TEX_PROSE
    assert [p.line for p in rm.blind_spots(found)] == TEX_PROSE


def test_tex_marking_a_blind_line_removes_exactly_that_one():
    marked = rm.parse(tex_marked(), TEX_SYN)
    assert {p.text for p in rm.paragraphs(marked) if p.covered} == \
        {TEX_LINES[i][0].strip() for i in (12, 13, 15, 17, 38)}
    lines = [line for line, _ in TEX_LINES]
    before = rm.blind_spots(rm.parse(TEX, TEX_SYN))
    after = rm.blind_spots(rm.parse("".join(x + "\n" for x in tex_wrap(lines, 31, 32, "N1")), TEX_SYN))
    assert {p.text for p in before} - {p.text for p in after} == {"one & two \\\\"}
    assert len(after) == len(before) - 1


def test_a_tex_file_without_a_document_environment_is_all_body():
    text = "\\section{Heading}\nA paragraph of a chapter file.\n\\input{other}\n"
    assert [p.line for p in rm.paragraphs(rm.parse(text, TEX_SYN))] == [2]


# --- ledger ids: a mark can name the review-ledger item it answers (manuscript-reviewer-response) -------


@pytest.mark.parametrize("sid", ["C3", "N1", "C3a", "R1.2", "R2.W1", "R2.P1", "R1.4a", "R10.S12b"])
def test_ledger_and_comment_ids_are_marks(sid):
    text = f"Intro line.\n{open_mark(sid)}\nA rewritten sentence.\n{close_mark(sid)}\n"
    found = rm.parse(text)
    assert not found.issues, found.issues
    assert [s.id for s in found.segments] == [sid]
    assert found.clean_text() == "Intro line.\nA rewritten sentence.\n"


@pytest.mark.parametrize("sid", ["r1.2", "R1.", "R1..2", "R.2", "1.2", "R1.2A", "R1.w1"])
def test_malformed_ledger_ids_are_refused(sid):
    found = rm.parse(f"{open_mark(sid)}\nText.\n{close_mark(sid)}\n")
    assert Code.BAD_ID in {i.code for i in found.errors}


def test_ledger_items_split_by_letter_group_under_one_comment():
    text = (f"{open_mark('R1.4a')}\nOne place.\n{close_mark('R1.4a')}\n\n"
            f"{open_mark('R1.4b')}\nAnother place.\n{close_mark('R1.4b')}\n\n"
            f"{open_mark('R2.W1')}\nA third.\n{close_mark('R2.W1')}\n")
    found = rm.parse(text)
    assert {s.attributes.comment_id for s in found.segments} == {"R1.4", "R2.W1"}
    assert rm.totals(found)["comments"] == 2
