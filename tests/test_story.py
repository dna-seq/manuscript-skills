"""Offline tests for manuscript-story's reading measures (reader_metrics.py).

Run with `uv run pytest tests/test_story.py -vvv`.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
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


rm = _load("story_reader_metrics", ROOT / "skills" / "manuscript-story" / "scripts" / "reader_metrics.py")

PAPER = """# A Tool for Reading Genomes

> Draft note for the authors: not part of the paper.

**Authors:** A. Author, B. Author

## Abstract

We built a tool that reads a genome on the reader's own computer. It annotates a whole genome in a minute.

## 1. Introduction

People receive files of variants they cannot read. We wanted a tool that reads them locally.

## 2. Methods

The pipeline joins variants with module tables.

### 2.1 Module format

Modules are tables, not code.

## 3. Benchmarking

### 3.1 Speed

A whole genome took 33 seconds against 6,005 seconds before.

## 4. Discussion

The tool makes local reading practical.

### 4.1 Limitations

Only four call sets were measured, and none came from an array.

### 4.2 Data privacy

Nothing leaves the computer during annotation.

## Conclusion

Readers can install it today.

## References

Zzyzx, Q. (2020). Backmatterword reference. *Journal*, 1, 1-2.

## Funding

Backmatterword grant 12345.
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_sections_get_their_kind_and_subsections_inherit_it():
    kinds = [(s.heading.strip("# "), s.kind) for s in rm.parse(PAPER)]
    assert kinds == [
        ("(front matter)", "front"), ("A Tool for Reading Genomes", "front"), ("Abstract", "abstract"),
        ("1. Introduction", "introduction"), ("2. Methods", "methods"), ("2.1 Module format", "methods"),
        ("3. Benchmarking", "results"), ("3.1 Speed", "results"), ("4. Discussion", "discussion"),
        ("4.1 Limitations", "limitations"), ("4.2 Data privacy", "discussion"), ("Conclusion", "conclusion"),
        ("References", "back"), ("Funding", "back"),
    ]


def test_front_and_back_matter_are_not_measured(tmp_path: Path):
    prof = rm.profile(_write(tmp_path, "paper.md", PAPER))
    body_sections = rm.parse(PAPER)
    body_paras = [p for s in body_sections if s.kind not in ("front", "back") for p in s.text]
    assert prof["body"] == rm.measure(body_paras)
    assert not any("Backmatterword" in p or "Draft note" in p for p in body_paras)
    assert sum(k["words"] for k in prof["kinds"].values()) == prof["body"]["words"]
    assert sum(k["share_of_body"] for k in prof["kinds"].values()) == pytest.approx(1.0, abs=0.01)


def test_revision_marks_and_comments_change_nothing(tmp_path: Path):
    marked = PAPER.replace("We wanted a tool", "<!-- @rev C3 rounds=2 by=robi:2026-09-25,claude:2026-10-10 -->We "
                                               "wanted a tool<!-- @/rev C3 -->")
    marked = marked.replace("## 2. Methods", "<!-- AUTHOR TODO: add a figure\nacross two lines -->\n\n## 2. Methods")
    assert rm.profile(_write(tmp_path, "a.md", marked))["body"] == rm.profile(_write(tmp_path, "b.md", PAPER))["body"]


def test_tables_images_code_blocks_and_citations_are_not_prose(tmp_path: Path):
    extra = ("\n| Genome | Seconds |\n|---|---|\n| one | 33 |\n| two | 65 |\n\n"
             "![](figures/f1.jpg){width=95%}\n\n```bash\nuv run tool 1 2 3\n```\n")
    noisy = PAPER.replace("A whole genome took 33 seconds against 6,005 seconds before.",
                          "A whole genome took 33 seconds against 6,005 seconds before (Smith et al., 2021; Lee, "
                          "2019) [4]." + extra)
    a = rm.profile(_write(tmp_path, "noisy.md", noisy))["body"]
    b = rm.profile(_write(tmp_path, "plain.md", PAPER))["body"]
    assert a == b


@pytest.mark.parametrize("sentence, ends_on_caveat", [
    ("The tool is fast on every genome we tried, albeit on four genomes.", True),
    ("Albeit on four genomes, the tool is fast on every genome we tried.", False),
    ("The tool is fast on every genome we tried, which may not hold for arrays.", True),
    ("The tool is fast on every genome we tried, and it runs on a laptop.", False),
    ("The tool is fast on every genome we tried and runs on a laptop.", False),
])
def test_a_caveat_in_the_stress_position_is_counted(sentence: str, ends_on_caveat: bool):
    m = rm.measure([sentence])
    assert m["sentences"] == 1
    assert m["caveat_ending_share"] == (1.0 if ends_on_caveat else 0.0)


def test_moving_a_caveat_to_the_front_of_a_sentence_keeps_its_count():
    end = rm.measure(["The tool is fast on every genome we tried, albeit on four genomes."])
    front = rm.measure(["Albeit on four genomes, the tool is fast on every genome we tried."])
    assert end["limiting_per_100"] == front["limiting_per_100"] > 0
    assert end["words"] == front["words"]


def test_abbreviations_do_not_split_sentences():
    m = rm.measure(["Tools such as VEP, e.g. version 110, and others (cf. Table 2) et al. agree on this point."])
    assert m["sentences"] == 1


def test_caveats_moving_into_results_read_harder_but_into_limitations_do_not(tmp_path: Path):
    before = rm.profile(_write(tmp_path, "before.md", PAPER))
    accreted = PAPER.replace(
        "A whole genome took 33 seconds against 6,005 seconds before.",
        "A whole genome took 33 seconds against 6,005 seconds before, although this may not hold on other "
        "machines. It does not establish performance on laptops, nor on rotational disks, and may not "
        "generalise.").replace(
        "Only four call sets were measured, and none came from an array.",
        "Only four call sets were measured, and none came from an array. It does not cover arrays, may not "
        "generalise, and cannot establish clinical validity, although it might.")
    after = rm.profile(_write(tmp_path, "after.md", accreted))
    moved = rm.changes(before, after)
    harder = {(c["scope"], c["measure"]) for c in moved if c["reads"] == "harder"}
    assert ("results", "negations_per_100") in harder
    assert ("results", "hedges_per_100") in harder
    assert ("results", "caveat_ending_share") in harder
    assert not {m for scope, m in harder if scope == "limitations"} & {
        "negations_per_100", "limiting_per_100", "hedges_per_100"}


def test_losing_the_authors_voice_reads_harder(tmp_path: Path):
    before = rm.profile(_write(tmp_path, "before.md", PAPER))
    impersonal = PAPER.replace("We built a tool", "A tool was built").replace(
        "We wanted a tool that reads them locally.", "A tool that reads them locally was needed.")
    after = rm.profile(_write(tmp_path, "after.md", impersonal))
    found = {(c["scope"], c["measure"], c["reads"]) for c in rm.changes(before, after)}
    assert ("body", "first_person_per_100", "harder") in found


def test_identical_versions_move_nothing(tmp_path: Path):
    p = rm.profile(_write(tmp_path, "paper.md", PAPER))
    assert rm.changes(p, p) == []


def test_latex_sections_abstract_citations_and_captions(tmp_path: Path):
    tex = r"""\documentclass{article}
\begin{document}
\title{A Tool}
\begin{abstract}
We built a tool that reads a genome locally \cite{smith2021}.
\end{abstract}
\section{Introduction}
People cannot read their variant files. We wanted a local tool~\cite{lee2019}.
\section{Results}
\subsection{Speed}
A whole genome took 33 seconds, as \emph{expected}.
\begin{figure}
\includegraphics{f1.png}
\caption{The report a user sees. It does not show every variant.}
\end{figure}
\section{Limitations}
Only four call sets were measured.
\section*{Acknowledgements}
Backmatterword thanks.
\end{document}
"""
    prof = rm.profile(_write(tmp_path, "paper.tex", tex))
    assert set(prof["kinds"]) == {"abstract", "introduction", "results", "limitations"}
    assert prof["captions"]["count"] == 1
    assert prof["captions"]["negations_per_100"] > 0
    assert [s["kind"] for s in prof["sections"]] == ["abstract", "introduction", "results", "limitations"]


def test_unicode_words_and_a_paper_without_known_headings(tmp_path: Path):
    text = "# Über die Genomlektüre\n\nDie Ergebnisse überraschen alle Leser. Naïve readers do not stop at any step.\n"
    prof = rm.profile(_write(tmp_path, "de.md", text))
    assert prof["body"]["words"] == len(rm.WORD.findall("Die Ergebnisse überraschen alle Leser. Naïve readers do "
                                                         "not stop at any step."))
    assert prof["body"]["negations_per_100"] > 0


def test_an_empty_section_measures_zero_without_failing():
    m = rm.measure([])
    assert m["words"] == 0 and m["sentences"] == 0


def test_cli_writes_json_and_reports_usage_errors(tmp_path: Path):
    runner = CliRunner()
    a, b = _write(tmp_path, "a.md", PAPER), _write(tmp_path, "b.md", PAPER.replace("We built", "A tool was built"))
    out = tmp_path / "m.json"
    res = runner.invoke(rm.app, [str(b), "--before", str(a), "--json", str(out), "--label", "v1", "--label", "v2"])
    assert res.exit_code == 0, res.output
    data = json.loads(out.read_text())
    assert [v["label"] for v in data["versions"]] == ["v1", "v2"]
    assert isinstance(data["moved"], list)
    assert "| Measure | v1 | v2 |" in res.output
    assert runner.invoke(rm.app, [str(tmp_path / "missing.md")]).exit_code == 2
    assert runner.invoke(rm.app, [str(a), str(b), "--label", "only-one"]).exit_code == 2


@pytest.mark.skipif(not (FIXTURES / "lively.md").exists(), reason="eval fixtures not present")
def test_the_accreted_fixture_reads_harder_than_the_lively_one():
    before = rm.profile(FIXTURES / "lively.md")
    after = rm.profile(FIXTURES / "accreted.md")
    harder = {(c["scope"], c["measure"]) for c in rm.changes(before, after) if c["reads"] == "harder"}
    assert ("results", "negations_per_100") in harder or ("results", "hedges_per_100") in harder
    assert after["kinds"]["results"]["share_of_body"] > before["kinds"]["results"]["share_of_body"]
