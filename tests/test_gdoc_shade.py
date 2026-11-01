"""manuscript-revision-marks' gdoc_shade.py: the unreviewed passages shaded in a round's Google Doc, the shading
cleared after a review pass, and what changed since an older version coloured apart. The Doc is a made-up read_doc
answer built here; indices are UTF-16 code units, as Google counts them. Run with `uv run pytest`."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gdoc_shade", ROOT / "skills/manuscript-revision-marks/scripts/gdoc_shade.py")
shade = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = shade
spec.loader.exec_module(shade)

LONG = ("The platform keeps every genome on the computer that analyses it and never uploads a single variant "
        "to any server it does not control")
PAPER = ("# Draft\n\n"
         "<!-- @rev C1 rounds=1 by=claude:2026-10-01 -->\n"
         "An agent wrote this sentence about [local analysis](https://example.org) [@smith2020].\n"
         "<!-- @/rev C1 -->\n\n"
         "<!-- @rev C2 rounds=2 by=claude:2026-10-01,anna:2026-10-02 -->\nAnna reviewed this one.\n<!-- @/rev C2 -->\n\n"
         f"<!-- @rev C3 rounds=1 by=codex:2026-10-03 -->\n{LONG}.\n<!-- @/rev C3 -->\n\n"
         "<!-- @rev C4 rounds=1 by=codex:2026-10-03 -->\nA sentence the Doc lost.\n<!-- @/rev C4 -->\n\n"
         "Text nobody marked.\n")
YELLOW = {"red": 1, "green": 1}
AMBER = {"red": 1, "green": 0.9254902, "blue": 0.7019608}  # the shading colour, as Google rounds it
BLUE = {"red": 0.8, "green": 0.8980392, "blue": 1}  # the revision-difference colour, as Google rounds it


def read_doc(path: Path, paragraphs: list[list]) -> Path:
    """A read_doc answer: each paragraph a list of runs, a run "text" or (text, colour) or (text, "ins")."""
    content, index = [{"endIndex": 1, "sectionBreak": {}}], 1
    for para in paragraphs:
        elements = []
        for part in para:
            text, extra = (part, None) if isinstance(part, str) else part
            run = {"content": text, "textStyle": {}}
            if extra == "ins":
                run["suggestedInsertionIds"] = ["suggest.x"]
            elif extra:
                run["textStyle"]["backgroundColor"] = {"color": {"rgbColor": extra}}
            size = len(text.encode("utf-16-le")) // 2
            elements.append({"startIndex": index, "endIndex": index + size, "textRun": run})
            index += size
        content.append({"paragraph": {"elements": elements}})
    doc = {"title": "Draft", "tabs": [{"tabProperties": {"tabId": "t.0"}, "documentTab": {"body": {"content": content}}}]}
    path.write_text(json.dumps({"content": doc}), encoding="utf-8")
    return path


def doc_text(paragraphs: list[list]) -> str:
    return "".join(p if isinstance(p, str) else p[0] for para in paragraphs for p in para)


def at(paragraphs: list[list], phrase: str) -> tuple[int, int]:
    """The UTF-16 index range of *phrase* in the Doc (the body starts at index 1)."""
    text = doc_text(paragraphs)
    i = text.index(phrase)
    return 1 + len(text[:i].encode("utf-16-le")) // 2, 1 + len(text[:i + len(phrase)].encode("utf-16-le")) // 2


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "rev-marks.toml").write_text('humans = ["anna"]\n', encoding="utf-8")
    (tmp_path / "paper.md").write_text(PAPER, encoding="utf-8")
    return tmp_path


DOC = [["Draft\n"],
       ["\U0001F9EC An agent wrote this sentence about local analysis (Smith 2020).\n"],  # an emoji: two UTF-16 units
       [("Anna reviewed this one.", AMBER), "\n"],  # shaded before her review; to clear
       [LONG.replace("never uploads", "does not upload") + ".\n"],  # a co-author's direct edit in the middle
       [("Text", YELLOW), " nobody marked.\n"]]  # a co-author's own highlight: never touched


def run(*args) -> tuple[int, dict]:
    import contextlib
    import io
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = shade.main([str(a) for a in args])
    return code, json.loads(out.getvalue())


def test_plan_shades_the_unreviewed_clears_the_reviewed_and_reports_what_the_doc_lost(project: Path, tmp_path: Path):
    code, plan = run("plan", project / "paper.md", read_doc(tmp_path / "read.json", DOC))
    assert code == 0
    found = {s["id"]: s for s in plan["shade"]}
    assert set(found) == {"C1", "C3"}
    assert tuple(found["C1"]["range"]) == at(DOC, "An agent wrote this sentence about local analysis")
    assert found["C1"]["found"] == "exact"
    assert found["C3"]["found"] == "ends"  # the middle was edited in the Doc; its first and last words place it
    assert [m["id"] for m in plan["not_found"]] == ["C4"] and "not in the Doc" in plan["not_found"][0]["why"]
    assert plan["clear"] == [list(at(DOC, "Anna reviewed this one."))]
    requests = plan["requests"]
    assert requests[0]["updateTextStyle"]["textStyle"] == {} and requests[0]["updateTextStyle"]["fields"] == "backgroundColor"
    on = [r["updateTextStyle"] for r in requests[1:]]
    assert all(r["textStyle"]["backgroundColor"]["color"]["rgbColor"] == shade.SHADE and r["range"]["tabId"] == "t.0"
               for r in on)
    assert all(r["range"]["startIndex"] >= at(DOC, "Anna")[1] or r["range"]["endIndex"] <= at(DOC, "Anna")[0]
               for r in on)
    assert not any(r["updateTextStyle"]["range"]["startIndex"] <= at(DOC, "Text")[0] < r["updateTextStyle"]["range"]["endIndex"]
                   for r in requests)  # the co-author's yellow stays


def test_verify_passes_only_when_the_doc_carries_exactly_the_plan(project: Path, tmp_path: Path):
    c1 = "An agent wrote this sentence about local analysis"
    done = [["Draft\n"], ["\U0001F9EC ", (c1, AMBER), " (Smith 2020).\n"], ["Anna reviewed this one.\n"],
            [(LONG.replace("never uploads", "does not upload"), AMBER), ".\n"], [("Text", YELLOW), " nobody marked.\n"]]
    code, result = run("verify", project / "paper.md", read_doc(tmp_path / "after.json", done))
    assert code == 0 and result["ok"], result
    code, result = run("verify", project / "paper.md", read_doc(tmp_path / "before.json", DOC))
    assert code == 1 and result["stray_shade"] == [list(at(DOC, "Anna reviewed this one."))]
    assert result["missing_shade"]


def test_after_a_review_pass_the_same_plan_clears_it(project: Path, tmp_path: Path):
    (project / "paper.md").write_text(PAPER.replace("by=claude:2026-10-01 -->", "by=claude:2026-10-01,anna:2026-11-01 -->"))
    c1 = "An agent wrote this sentence about local analysis"
    shaded = [["Draft\n"], ["\U0001F9EC ", (c1, AMBER), " (Smith 2020).\n"], ["Anna reviewed this one.\n"],
              [LONG + ".\n"], ["Text nobody marked.\n"]]
    code, plan = run("plan", project / "paper.md", read_doc(tmp_path / "read.json", shaded))
    assert code == 0 and "C1" not in {s["id"] for s in plan["shade"]}
    assert plan["clear"] == [list(at(shaded, c1))]


def test_diff_colours_what_changed_since_an_older_version_and_lists_what_was_cut(tmp_path: Path):
    old = tmp_path / "revision-1.txt"
    old.write_text("Draft\n\nThe tool runs on one laptop. It was slow before. It reads VCF files quickly.\n")
    now = [["Draft\n"], ["The tool runs on any laptop. It reads VCF files ", ("quickly", BLUE), ".\n"],
           [("Text", AMBER), " added since.\n"]]
    code, result = run("diff", old, read_doc(tmp_path / "read.json", now))
    assert code == 0
    assert [c["now"] for c in result["changed"]] == ["any", "text added since"]
    assert [c["was"] for c in result["changed"]][0] == "one"
    assert [d["words"] for d in result["deleted"]] == ["it was slow before"]
    assert result["clear"] == [list(at(now, "quickly"))]  # no longer differs: its blue goes
    on = [r["updateTextStyle"] for r in result["requests"] if r["updateTextStyle"]["textStyle"]]
    assert all(r["textStyle"]["backgroundColor"]["color"]["rgbColor"] == shade.DIFF for r in on)
    assert [(r["range"]["startIndex"], r["range"]["endIndex"]) for r in on] == [at(now, "any"), at(now, "Text added since")]
    code, check = run("diff", old, read_doc(tmp_path / "read.json", now), "--verify")
    assert code == 1 and check["stray_colour"] == [list(at(now, "quickly"))]


def test_clear_removes_only_the_reserved_colours_it_is_asked_for(tmp_path: Path):
    doc = [[("one", AMBER), " ", ("two", BLUE), " ", ("three", YELLOW), "\n"]]
    path = read_doc(tmp_path / "read.json", doc)
    assert run("clear", path)[1]["clear"] == [list(at(doc, "one")), list(at(doc, "two"))]
    assert run("clear", path, "--colour", "diff")[1]["clear"] == [list(at(doc, "two"))]
    assert run("clear", path, "--colour", "shade")[1]["clear"] == [list(at(doc, "one"))]


def test_a_suggested_insertion_is_not_master_text_and_a_bad_answer_is_refused(project: Path, tmp_path: Path):
    doc = [["Draft\n"], ["An agent wrote this ", ("very ", "ins"), "sentence about local analysis.\n"]]
    code, plan = run("plan", project / "paper.md", read_doc(tmp_path / "read.json", doc))
    assert code == 0 and {s["id"]: s["found"] for s in plan["shade"]}["C1"] == "exact"
    (tmp_path / "bad.json").write_text('{"content": {"title": "x"}}')
    assert shade.main(["plan", str(project / "paper.md"), str(tmp_path / "bad.json")]) == 2
