"""Offline tests for manuscript-story's comprehension pass (comprehension.py).

Run with `uv run pytest tests/test_comprehension.py -vvv`.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals" / "fixtures" / "manuscript-story"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cp = _load("story_comprehension", ROOT / "skills" / "manuscript-story" / "scripts" / "comprehension.py")
runner = CliRunner()

PAPER = """# A Tool

## Abstract

We score genomes with PGS on a laptop. A polygenic score (PGS) adds up effects.

## 1. Introduction

The T2T reference is new. Telomere-to-telomere (T2T) assemblies close gaps. A VCF (Figure 1) lists variants.
Results are kept as PGS values, and the DNA is never uploaded.

## 2. Methods

A site is kept when at least nine samples carry it and the quality is above three. We use a window of 5 kb because
linkage decays within it. The score has a threshold of 0.8 (Smith et al., 2020). A cut-off of 0.1 is used.
This value keeps the false discovery rate below one in ten.

## 3. Results

Annotation took 31 s with the default sets.

## References

1. Smith J, et al. A GWAS of everything. 2020.
"""


def test_scan_abbreviations_in_the_abstract_and_the_body_apart() -> None:
    items = {(i["term"], i["note"]) for i in cp.scan_text(PAPER) if i["kind"] == "abbreviation"}
    assert ("PGS", "used before it is spelled out (spelled out in Abstract)") in items
    assert ("T2T", "used before it is spelled out (spelled out in 1. Introduction)") in items
    # a parenthesis naming a figure is no definition; the Abstract's definition does not count for the body
    assert ("VCF", "never spelled out") in items
    assert ("PGS", "never spelled out") in items
    # known to every reader, and back matter is not read
    assert not {t for t, _ in items} & {"DNA", "GWAS"}


def test_scan_numbers_need_a_reason_beside_them() -> None:
    numbers = [i["quote"] for i in cp.scan_text(PAPER) if i["kind"] == "number"]
    assert numbers == ["A site is kept when at least nine samples carry it and the quality is above three."]
    # "because" in the sentence, a citation, and a following sentence that explains: all pass; the Results'
    # "default sets" sets no rule


def test_scan_known_list_and_dense_sentences() -> None:
    text = PAPER.replace("Annotation took 31 s with the default sets.",
                         "Annotation, which ran on the author's laptop (a machine with 16 GB of memory and a solid-state "
                         "disk bought last year), took 31 s with the default sets, although runs that used every set took "
                         "longer, since each set is read from disk when the run starts.")
    items = cp.scan_text(text, known=frozenset({"T2T"}))
    assert "T2T" not in {i.get("term") for i in items}
    assert [i["section"] for i in items if i["kind"] == "dense"] == ["3. Results"]


def test_passages_are_paragraphs_with_two_new_sentences() -> None:
    after = PAPER.replace("Annotation took 31 s with the default sets.",
                          "Annotation took 31 s with the default sets. The run keeps a cache on disk. It also writes "
                          "a log for each sample.").replace("We score genomes", "We now score genomes")
    found = cp.passages_of(PAPER, after)
    assert [(p["id"], p["section"], len(p["new"])) for p in found] == [("P1", "3. Results", 2)]


def _prepared(tmp_path: Path, **kw) -> tuple[Path, Path]:
    original = tmp_path / "original.md"
    original.write_text(PAPER, encoding="utf-8")
    paper = tmp_path / "paper.md"
    paper.write_text(PAPER.replace("Annotation took 31 s with the default sets.",
                                   "Annotation took 31 s with the default sets. The run keeps a cache on disk. It "
                                   "also writes a log for each sample."), encoding="utf-8")
    folder = tmp_path / "comprehension"
    args = ["prepare", str(paper), "--into", str(folder), "--original", str(original)]
    for s in kw.get("sections", []):
        args += ["--section", s]
    result = runner.invoke(cp.app, args)
    assert result.exit_code == 0, result.output
    return paper, folder


def test_prepare_writes_only_the_reading(tmp_path: Path) -> None:
    _, folder = _prepared(tmp_path, sections=["2"])
    assert sorted(p.name for p in folder.iterdir()) == ["brief.md", "manifest.json", "passages.md", "reading.md"]
    reading = (folder / "reading.md").read_text(encoding="utf-8")
    assert reading.startswith("## 2. Methods") and "Results" not in reading
    assert "The run keeps a cache on disk." in (folder / "passages.md").read_text(encoding="utf-8")
    brief = (folder / "brief.md").read_text(encoding="utf-8")
    assert "answer.json" in brief and "number-without-reason" in brief and "P1" in brief
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sections"] == ["2. Methods"] and manifest["passages"] == ["P1"]


def _answer(folder: Path, items: list[dict], read: list[str]) -> Path:
    path = folder / "answer.json"
    path.write_text(json.dumps({"seat": "outside-expert", "read": read, "items": items}), encoding="utf-8")
    return path


def test_check_writes_comprehension_findings(tmp_path: Path) -> None:
    _, folder = _prepared(tmp_path)
    stops = [{"quote": "A site is kept when at least nine samples carry it", "section": "2. Methods",
              "problem": "term-before-definition", "term": "site", "why": "What exactly is a site?"}]
    stops += [{"quote": "The run keeps a cache on disk.", "section": "P1", "problem": "could-not-restate",
               "why": f"Which run? ({n})"} for n in range(5)]
    answer = _answer(folder, stops, ["2. Methods", "3. Results", "P1"])
    out = tmp_path / "comprehension.json"
    result = runner.invoke(cp.app, ["check", str(answer), "--out", str(out), "--start", "4"])
    assert result.exit_code == 0, result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    findings = data["findings"]
    assert [f["id"] for f in findings] == [f"ST-{n}" for n in range(4, 11)]
    first = findings[0]
    assert (first["category"], first["severity"], first["decision"], first["owner"]) == \
        ("Comprehension", "minor", False, "manuscript-prose-edit")
    assert first["summary"].endswith("(site)")
    assert first["evidence"] == [{"path": "comprehension/answer.json", "quote": "What exactly is a site?"}]
    # five stops in one section make a major finding on the section; a passage counts under its section
    assert findings[-1]["severity"] == "major" and findings[-1]["section"] == "3. Results"
    assert data["on_passages_the_run_wrote"] == [f"ST-{n}" for n in range(5, 10)]


def test_check_refuses_a_skipped_section_a_bad_quote_or_kind(tmp_path: Path) -> None:
    _, folder = _prepared(tmp_path)
    answer = _answer(folder, [
        {"quote": "a sentence the paper lacks entirely", "section": "2. Methods", "problem": "cannot-parse", "why": "x"},
        {"quote": "The run keeps a cache on disk.", "section": "P1", "problem": "boring", "why": "x"},
        {"quote": "The T2T reference is new.", "section": "1. Introduction", "problem": "term-before-definition",
         "why": "x"},
    ], ["2. Methods"])
    result = runner.invoke(cp.app, ["check", str(answer), "--out", str(tmp_path / "c.json")])
    assert result.exit_code == 1
    assert "not read: 3. Results" in result.output and "not read: P1" in result.output
    assert "item 1: the quote is not in the paper" in result.output
    assert "item 2: problem 'boring'" in result.output
    assert "item 3: a term-before-definition names its `term`" in result.output


def test_check_refuses_a_paper_changed_since_prepare(tmp_path: Path) -> None:
    paper, folder = _prepared(tmp_path)
    paper.write_text(paper.read_text(encoding="utf-8") + "\nA new line.\n", encoding="utf-8")
    answer = _answer(folder, [], ["2. Methods", "3. Results", "P1"])
    result = runner.invoke(cp.app, ["check", str(answer), "--out", str(tmp_path / "c.json")])
    assert result.exit_code == 1


def test_scan_runs_on_the_seeded_outsider_fixture() -> None:
    items = cp.scan_text((FIXTURES / "outsider-seeded.md").read_text(encoding="utf-8"))
    assert {"ASV", "CLR"} <= {i.get("term") for i in items}
    assert any(i["kind"] == "number" and "at least 4 of 7" in i["quote"] for i in items)


NOTED = """# A Tool for Reading Genomes

Anna Smith^1^, Ben Jones^2^

^1^ Institute of Biostatistics, University of Rostock, Germany

> Draft note: this paper presents the GUI and the MCP server, while the companion paper presents the modules and
> their evaluation, so that each can be reviewed on its own.

## Abstract

We score genomes on a laptop.

## 1. Introduction

The MCP server answers questions. A Model Context Protocol (MCP) server is a tool an assistant calls.
"""


def test_scan_reads_the_note_before_the_abstract_and_not_the_author_lines() -> None:
    items = cp.scan_text(NOTED)
    notes = [i for i in items if i["section"] == cp.FRONT_NOTE]
    assert [(i["term"], i["note"]) for i in notes] == [("GUI", "never spelled out in the note"),
                                                        ("MCP", "never spelled out in the note")]
    # the body counts its own first use, not the note's
    assert ("MCP", "used before it is spelled out (spelled out in 1. Introduction)") in {
        (i["term"], i["note"]) for i in items if i["kind"] == "abbreviation" and i["section"] != cp.FRONT_NOTE}
    assert not any("Rostock" in i["quote"] or "Smith" in i["quote"] for i in items)


def test_scan_check_finishes_a_spelling_out_and_marks_what_the_original_had(tmp_path: Path) -> None:
    original = tmp_path / "original.md"
    original.write_text(PAPER, encoding="utf-8")
    fixed = tmp_path / "fixed.md"
    fixed.write_text(PAPER.replace("We score genomes with PGS", "We score genomes with polygenic scores (PGS)"),
                     encoding="utf-8")
    out = tmp_path / "scan.json"
    result = runner.invoke(cp.app, ["scan", str(fixed), "--before", str(original), "--check", "--json", str(out)])
    assert result.exit_code == 1, result.output
    items = json.loads(out.read_text(encoding="utf-8"))["items"]
    abbreviations = {i["term"]: i for i in items if i["kind"] == "abbreviation"}
    assert "PGS" not in {t for t, i in abbreviations.items() if i["section"] == "Abstract"}
    assert abbreviations["T2T"]["in_original"] is True
    assert "T2T" in result.output
    done = tmp_path / "done.md"
    done.write_text("# T\n\n## Abstract\n\nA polygenic score (PGS) adds effects.\n\n## 1. Methods\n\n"
                    "Each polygenic score (PGS) is summed.\n", encoding="utf-8")
    assert runner.invoke(cp.app, ["scan", str(done), "--check"]).exit_code == 0
