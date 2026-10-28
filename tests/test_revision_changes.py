"""manuscript-revision-marks/scripts/rev_marks.py changes: the rows of a round's changelog. Two kinds of
evidence: excerpts of a real round (tests/fixtures/revision-changes: Paper 1 of dna-seq/just-dna-lite, v0.5 to
v0.6) checked against the changelog its authors wrote by hand, and rounds built at test time from
docs/skill-landscape-2026-10.md, with segments, edits, removals and an unmarked edit placed by a seeded draw, so
the rows each round must produce are known before the command runs. Run with `uv run pytest`."""
from __future__ import annotations

import importlib.util
import json
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RM = ROOT / "skills" / "manuscript-revision-marks" / "scripts" / "rev_marks.py"
DOC = ROOT / "docs" / "skill-landscape-2026-10.md"
FIXTURES = ROOT / "tests" / "fixtures" / "revision-changes"
OLD, NEW, HAND = FIXTURES / "paper-v0.5.md", FIXTURES / "paper-v0.6.md", FIXTURES / "changes-from-v0.5.md"
BY1 = "anna:2026-09-25"
BY2 = "anna:2026-09-25,claude:2026-10-26"
SEEDS = (20261026, 7, 1234)

spec = importlib.util.spec_from_file_location("rev_marks", RM)
rm = importlib.util.module_from_spec(spec)
sys.modules["rev_marks"] = rm
spec.loader.exec_module(rm)
Change = rm.Change
MD = rm.Syntax.MARKDOWN


def run(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(RM), *map(str, args)], text=True, capture_output=True, check=False)


def rows_of(old: Path, new: Path) -> list[dict]:
    p = run("changes", "--json", old, new)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)["rows"]


def compare(old: str, new: str, syntax=MD) -> list:
    return rm.changes(rm.parse(old, syntax), rm.parse(new, syntax))


def expected_ids(old: str, new: str, syntax=MD) -> set[str]:
    """The segments a changelog must list, read from the marks alone: new, removed, or with another text,
    rounds or by=."""
    o = {s.id: s for s in rm.parse(old, syntax).segments}
    n = {s.id: s for s in rm.parse(new, syntax).segments}
    return (o.keys() ^ n.keys()) | {i for i in o.keys() & n.keys()
                                    if rm.norm(o[i].text) != rm.norm(n[i].text) or o[i].attributes != n[i].attributes}


def hand_written(text: str) -> tuple[set[str], int]:
    """The ids in the Id column of a changelog's tables, and how many of its rows name no id."""
    ids: set[str] = set()
    unnamed = 0
    in_table = False
    for line in text.splitlines():
        if line.startswith("| Id |"):
            in_table = True
        elif not line.startswith("|"):
            in_table = False
        elif in_table and not line.startswith("|---"):
            found = {m.group() for m in re.finditer(rm.ID_PATTERN, line.split("|")[1])}
            ids |= found
            unnamed += not found
    return ids, unnamed


def table_lines(markdown: str) -> list[list[str]]:
    """The body rows of the changelog table, split on unescaped pipes."""
    lines = [line for line in markdown.splitlines() if line.startswith("| ") and not line.startswith("| Id |")]
    return [[c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]] for line in lines]


# --- a real round, against the changelog its authors wrote ---------------------------------------------


def test_the_fixtures_are_marked_masters_that_lint():
    for path in (OLD, NEW):
        assert run("lint", path).returncode == 0


def test_every_id_of_the_hand_written_changelog_is_a_row():
    hand, unnamed = hand_written(HAND.read_text(encoding="utf-8"))
    rows = rows_of(OLD, NEW)
    listed = {r["id"] for r in rows if r["id"]}
    assert hand <= listed, f"the command misses {sorted(hand - listed)}"
    assert sum(1 for r in rows if r["id"] is None) == unnamed  # the draft note and the Competing Interests line
    # The one row the authors did not name: R2, the affiliation the round dropped, a segment of its own inside
    # the affiliation list that AU2 describes.
    assert listed - hand == {"R2"}


@pytest.mark.parametrize("old, new", [(OLD, NEW), (NEW, OLD), (NEW, NEW)])
def test_the_rows_are_exactly_the_segments_whose_marks_or_text_changed(old, new):
    rows = rows_of(old, new)
    assert {r["id"] for r in rows if r["id"]} == expected_ids(old.read_text(encoding="utf-8"),
                                                              new.read_text(encoding="utf-8"))
    assert len({r["id"] for r in rows if r["id"]}) == sum(1 for r in rows if r["id"])  # one row per segment


def test_each_row_says_what_changed_in_the_real_round():
    rows = rows_of(OLD, NEW)
    by_id = {r["id"]: r for r in rows if r["id"]}
    o, n = rm.parse(rm.read_source(OLD)), rm.parse(rm.read_source(NEW))
    assert {i for i, r in by_id.items() if r["status"] == "new"} == {s.id for s in n.segments} - {s.id for s in o.segments}
    assert {i for i, r in by_id.items() if r["status"] == "removed"} == {s.id for s in o.segments} - {s.id for s in n.segments}
    for i, r in by_id.items():
        if r["status"] in ("revised", "rounds"):
            before, after = o.segment(i).attributes, n.segment(i).attributes
            assert after.by[: len(before.by)] == before.by
            assert r["new_by"] == [e.render() for e in after.by[len(before.by) :]]
            assert (r["old_rounds"], r["new_rounds"]) == (before.rounds, after.rounds)
    # T6 changed only where the new sentence F5 sits inside it.
    assert by_id["T6"]["inside"] == ["F5"] and by_id["F5"]["status"] == "new"
    assert by_id["C2a"]["where"] == "Abstract" and by_id["R24"]["where"] == "5.6 Conclusion"
    draft, competing = [r for r in rows if r["id"] is None]
    assert "v0.5" in draft["old_text"] and "v0.6" in draft["new_text"] and draft["old_line"] == draft["new_line"] == 3
    assert competing["where"] == "Competing Interests" and "Ryangguk Kim" in competing["old_text"]
    # The deleted list item's place in v0.6 is the item that now opens the list.
    assert "Ryangguk Kim" not in competing["new_text"]
    assert competing["new_line"] == line_of(rm.read_source(NEW), "- Anton Kulaga, Olga")


def test_the_markdown_table_has_one_row_per_change_and_an_empty_why():
    p = run("changes", OLD, NEW)
    assert p.returncode == 0, p.stderr
    rows = rows_of(OLD, NEW)
    table = table_lines(p.stdout.split("## The record behind each row")[0])
    assert [t[0] for t in table] == [r["id"] or "(none)" for r in rows]
    assert all(len(t) == 5 and t[4] == "" for t in table)
    record = p.stdout.split("## The record behind each row")[1]
    assert sum(1 for line in record.splitlines() if line.startswith("- ")) == len(rows)


# --- rounds built at test time ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """What a round does to one paragraph."""

    sid: str | None = None  # mark it as this segment
    by: str = BY1
    token: str | None = None  # change one word in its middle to this
    gone: bool = False  # delete it


def mark(text: str, sid: str, by: str) -> str:
    return f"<!-- @rev {sid} rounds={by.count(',') + 1} by={by} -->\n{text}<!-- @/rev {sid} -->\n"


def edit(text: str, token: str) -> str:
    """One word of the paragraph's middle half becomes *token*, so no change can merge with a neighbour's."""
    words = [m for m in re.finditer(r"\b[A-Za-z]{5,}\b", text) if len(text) // 4 < m.start() < 3 * len(text) // 4]
    m = random.Random(token).choice(words)
    return text[: m.start()] + token + text[m.end() :]


def build(base: str, paras, plan: dict[int, Step]) -> str:
    text = base
    for k in sorted(plan, key=lambda k: paras[k].start, reverse=True):
        p, step = paras[k], plan[k]
        body = "" if step.gone else text[p.start : p.end]
        if step.token and not step.gone:
            body = edit(body, step.token)
        if step.sid and not step.gone:
            body = mark(body, step.sid, step.by)
        text = text[: p.start] + body + text[p.end :]
    return text


@dataclass(frozen=True)
class Round:
    old: str
    new: str
    ids: dict[str, str]  # role -> segment id
    tokens: dict[str, str]  # role -> the word the round wrote


ROLES = ("revised", "revised2", "unbumped", "rounds", "removed", "added", "marked", "unmarked", "kept")


def make_round(seed: int, unbumped: bool = True, loose: bool = True) -> Round:
    base = rm.read_source(DOC)
    assert "@rev" not in base
    paras = rm.paragraphs(rm.parse(base))
    candidates = [k for k, p in enumerate(paras[:-1]) if len(p.text.split()) > 20 and "`" not in p.text]
    chosen = dict(zip(ROLES, random.Random(seed).sample(candidates, len(ROLES))))
    ids = {role: f"C{k}" for role, k in chosen.items()}
    ids["added"], ids["marked"] = "N1", "N2"
    tokens = {role: f"Zqx{role}{seed}" for role in ("revised", "revised2", "unbumped", "added", "unmarked")}
    old = build(base, paras, {chosen[r]: Step(ids[r]) for r in ("revised", "revised2", "unbumped", "rounds", "removed",
                                                                "kept")})
    new = build(base, paras, {
        chosen["revised"]: Step(ids["revised"], BY2, tokens["revised"]),
        chosen["revised2"]: Step(ids["revised2"], BY2, tokens["revised2"]),
        chosen["unbumped"]: Step(ids["unbumped"], BY1 if unbumped else BY2, tokens["unbumped"]),
        chosen["rounds"]: Step(ids["rounds"], BY2),
        chosen["removed"]: Step(gone=True),
        chosen["added"]: Step(ids["added"], "claude:2026-10-26", tokens["added"]),
        chosen["marked"]: Step(ids["marked"], "claude:2026-10-26"),
        chosen["unmarked"]: Step(token=tokens["unmarked"] if loose else None),
        chosen["kept"]: Step(ids["kept"]),
    })
    return Round(old, new, ids, tokens)


def line_of(text: str, needle: str) -> int:
    return text[: text.index(needle)].count("\n") + 1


@pytest.mark.parametrize("seed", SEEDS)
def test_a_built_round_lists_every_change_and_nothing_else(seed):
    r = make_round(seed)
    rows = compare(r.old, r.new)
    status = {row.id: row.status for row in rows if row.id}
    assert status == {r.ids["revised"]: Change.REVISED, r.ids["revised2"]: Change.REVISED,
                      r.ids["unbumped"]: Change.REVISED, r.ids["rounds"]: Change.ROUNDS,
                      r.ids["removed"]: Change.REMOVED, r.ids["added"]: Change.NEW, r.ids["marked"]: Change.NEW}
    assert set(status) == expected_ids(r.old, r.new)
    assert {row.id for row in rows if row.unbumped} == {r.ids["unbumped"]}
    by_id = {row.id: row for row in rows if row.id}
    assert by_id[r.ids["marked"]].text_unchanged and not by_id[r.ids["added"]].text_unchanged
    assert by_id[r.ids["revised"]].new_by == ("claude:2026-10-26",) and by_id[r.ids["unbumped"]].new_by == ()
    loose = [row for row in rows if row.status == Change.UNMARKED]
    assert len(loose) == 1 and r.tokens["unmarked"] in loose[0].new_text
    assert loose[0].new_line == line_of(r.new, r.tokens["unmarked"])
    for role in ("revised", "revised2", "unbumped", "added"):
        assert r.tokens[role] in by_id[r.ids[role]].new_text
    new_lines = [row.new_line for row in rows if row.new_line is not None]
    assert new_lines == sorted(new_lines)  # in the order of the new text


@pytest.mark.parametrize("seed", SEEDS)
def test_strict_fails_only_on_a_change_no_new_round_records(seed, tmp_path):
    for unbumped, loose, code in ((True, True, 1), (True, False, 1), (False, True, 1), (False, False, 0)):
        r = make_round(seed, unbumped=unbumped, loose=loose)
        (tmp_path / "old.md").write_text(r.old, encoding="utf-8")
        (tmp_path / "new.md").write_text(r.new, encoding="utf-8")
        p = run("changes", "--strict", tmp_path / "old.md", tmp_path / "new.md")
        assert p.returncode == code, p.stderr
        assert (r.ids["unbumped"] in p.stderr) == unbumped
        assert run("changes", tmp_path / "old.md", tmp_path / "new.md").returncode == 0


@pytest.mark.parametrize("seed", SEEDS)
def test_without_marks_every_changed_paragraph_is_a_row(seed):
    r = make_round(seed)
    rows = compare(rm.strip_marks(r.old), rm.strip_marks(r.new))
    assert all(row.status == Change.UNMARKED and row.id is None for row in rows)
    # Five edited paragraphs and one deleted one; the marked-only and bumped-only paragraphs read the same.
    assert len(rows) == 6
    assert {t for t in r.tokens.values() if any(t in row.new_text for row in rows)} == set(r.tokens.values())
    assert sum(1 for row in rows if row.new_text == "" and row.new_line is None) == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_a_round_against_itself_and_marks_added_to_unchanged_text(seed):
    r = make_round(seed)
    assert compare(r.old, r.old) == [] and compare(r.new, r.new) == []
    plain = rm.strip_marks(r.old)
    rows = compare(plain, r.old)
    assert {row.id for row in rows} == {s.id for s in rm.parse(r.old).segments}
    assert all(row.status == Change.NEW and row.text_unchanged for row in rows)


@pytest.mark.parametrize("seed", SEEDS)
def test_cells_show_the_changed_words_and_full_shows_the_whole_text(seed, tmp_path):
    r = make_round(seed)
    (tmp_path / "old.md").write_text(r.old, encoding="utf-8")
    (tmp_path / "new.md").write_text(r.new, encoding="utf-8")
    sid, token = r.ids["revised"], r.tokens["revised"]
    short = {t[0]: t for t in table_lines(run("changes", tmp_path / "old.md", tmp_path / "new.md").stdout)}[sid]
    full = {t[0]: t for t in table_lines(run("changes", "--full", tmp_path / "old.md", tmp_path / "new.md").stdout)}[sid]
    segment = rm.parse(r.new).segment(sid)
    assert token in short[3] and "…" in short[3] and len(short[3].split()) <= 2 * rm.EXCERPT_CONTEXT + 3
    assert full[3] == rm.cell(segment.text)


# --- small cases ------------------------------------------------------------------------------------------


def test_a_change_inside_a_nested_segment_and_one_outside_it():
    def doc(second: str, third: str, inner: str = BY1, outer: str = BY1) -> str:
        return (f"## Results\n\n<!-- @rev P1 rounds={outer.count(',') + 1} by={outer} -->\nThe first sentence stays."
                f" <!-- @rev C1 rounds={inner.count(',') + 1} by={inner} -->{second}<!-- @/rev C1 --> {third}\n"
                "<!-- @/rev P1 -->\n")

    old = doc("The second sentence changes.", "The third stays.")
    rows = {r.id: r for r in compare(old, doc("The second sentence was rewritten.", "The third stays.", inner=BY2))}
    assert rows["C1"].status == Change.REVISED and not rows["C1"].unbumped
    assert rows["P1"].inside == ("C1",) and not rows["P1"].unbumped and rows["P1"].where == "Results"
    rows = {r.id: r for r in compare(old, doc("The second sentence changes.", "The third moved."))}
    assert set(rows) == {"P1"} and rows["P1"].unbumped and rows["P1"].inside == ()


def test_a_deletion_at_the_edge_of_a_new_segment_is_its_own_and_elsewhere_is_unmarked():
    plain = "Plain words before the passage stay as they were. The passage reads well.\n\nAnother paragraph with an extra word in it.\n"
    new = ("Plain words before the passage stay as they <!-- @rev N1 rounds=1 by=claude:2026-10-26 -->The passage"
           " reads better.<!-- @/rev N1 -->\n\nAnother paragraph with a word in it.\n")
    rows = compare(plain, new)
    assert [(r.id, r.status) for r in rows] == [("N1", Change.NEW), (None, Change.UNMARKED)]
    assert rows[0].old_text == "were. The passage reads well." and not rows[0].text_unchanged  # its Was shows the cut
    assert rows[1].old_text == "Another paragraph with an extra word in it." and rows[1].new_line == 3
    # Beside a segment the round only revised, the cut word is outside its text in both rounds: unmarked.
    old = plain.replace("The passage reads well.", "<!-- @rev N1 rounds=1 by=anna:2026-09-25 -->The passage reads"
                        " well.<!-- @/rev N1 -->")
    rows = compare(old, new.replace("rounds=1 by=claude", "rounds=2 by=anna:2026-09-25,claude"))
    assert [(r.id, r.status) for r in rows] == [("N1", Change.REVISED), (None, Change.UNMARKED), (None, Change.UNMARKED)]
    assert "were." in rows[1].old_text and "were." not in rows[1].new_text


def test_tex_rounds_compare_preamble_body_and_comments():
    old = ("\\documentclass{article}\n\\title{A study}\n\\begin{document}\n\\section{Introduction}\n"
           "% @rev C1 rounds=1 by=anna:2026-09-25\nWe measured twelve samples.\n% @/rev C1\nNothing else changed.\n\n"
           "\\section{Methods}\nThe method is old.\n% AUTHOR TODO: check the method\n\\end{document}\n")
    new = old.replace("A study", "A better study").replace("twelve", "fourteen").replace(
        "rounds=1 by=anna:2026-09-25", "rounds=2 by=anna:2026-09-25,claude:2026-10-26").replace(
        "% AUTHOR TODO: check the method\n", "")
    rows = compare(old, new, rm.Syntax.TEX)
    assert [(r.id, r.status) for r in rows] == [(None, Change.UNMARKED), ("C1", Change.REVISED), (None, Change.UNMARKED)]
    title, c1, todo = rows
    assert title.where == "" and title.old_text == "\\title{A study}" and title.new_text == "\\title{A better study}"
    assert c1.where == "Introduction" and c1.new_by == ("claude:2026-10-26",)
    assert todo.where == "Methods" and "AUTHOR TODO" in todo.old_text and "AUTHOR TODO" not in todo.new_text


def test_pipes_in_a_changed_table_are_escaped(tmp_path):
    old = "<!-- @rev T1 rounds=1 by=anna:2026-09-25 -->\n| a | b |\n|---|---|\n| 1 | 2 |\n<!-- @/rev T1 -->\n"
    (tmp_path / "old.md").write_text(old, encoding="utf-8")
    (tmp_path / "new.md").write_text(old.replace("| 1 | 2 |", "| 1 | 3 |"), encoding="utf-8")
    p = run("changes", tmp_path / "old.md", tmp_path / "new.md")
    [row] = table_lines(p.stdout)
    assert row[0] == "T1" and "\\|" in row[2] and "3" in row[3] and row[4] == ""


def test_exit_codes(tmp_path):
    good = tmp_path / "good.md"
    good.write_text("<!-- @rev C1 rounds=1 by=anna:2026-09-25 -->\nText.\n<!-- @/rev C1 -->\n", encoding="utf-8")
    broken = tmp_path / "broken.md"
    broken.write_text("<!-- @rev C1 rounds=1 by=anna:2026-09-25 -->\nText.\n", encoding="utf-8")
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    assert run("changes", good, good).returncode == 0
    p = run("changes", good, broken)
    assert p.returncode == 1 and "unclosed" in p.stderr
    assert run("changes", good, tmp_path / "missing.md").returncode == 3
    assert run("changes", good, pdf).returncode == 3
    assert run("changes", good).returncode == 2


def test_seen_marks_what_the_co_authors_have_not_seen(tmp_path):
    """--seen SEEN: against the base itself every row is new to the co-authors; against the finished round, every
    row is as they saw it; and a segment rewritten again after they saw it is "changed again"."""
    base_rows = rows_of(OLD, NEW)
    unseen = json.loads(run("changes", OLD, NEW, "--json", "--seen", OLD).stdout)
    assert [r["since_seen"] for r in unseen["rows"]] == ["new"] * len(base_rows)
    seen_all = json.loads(run("changes", OLD, NEW, "--json", "--seen", NEW).stdout)
    assert {r["since_seen"] for r in seen_all["rows"]} == {"same"} and seen_all["seen"] == str(NEW)
    text = NEW.read_text(encoding="utf-8")
    revised = next(r["id"] for r in base_rows if r["status"] == "revised" and not r["inside"])
    first = rm.parse(text, MD).segment(revised)
    later = tmp_path / "later.md"  # the round goes on after the co-authors saw NEW: a revised segment is rewritten again
    body = text[first.open.end:first.close.start]
    later.write_text(text[:first.open.end] + body.replace(" ", "  ", 1).rstrip() + " Rewritten once more.\n"
                     + text[first.close.start:], encoding="utf-8")
    table = run("changes", OLD, later, "--seen", NEW)
    assert table.returncode == 0, table.stderr
    assert "| Since they saw it |" in table.stdout and "1 changed again" in table.stdout
    row = next(line for line in table.stdout.splitlines() if line.startswith(f"| {first.id} |"))
    assert row.rstrip().endswith("| Changed again |")
    assert run("changes", OLD, NEW, "--seen", tmp_path / "missing.md").returncode == 3
