"""Offline tests for manuscript-figures' figures.py: finding figures and their citations, rendering them at
their printed size and measuring what looking cannot.

Run with `uv run --group dev pytest tests/test_figures.py -q`.
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "evals" / "fixtures" / "manuscript-figures"
spec = importlib.util.spec_from_file_location("figures", ROOT / "skills" / "manuscript-figures" / "scripts" / "figures.py")
figures = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = figures
spec.loader.exec_module(figures)
runner = CliRunner()


def png(path: Path, width: int = 600, height: int = 300, colour: str = "white") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (width, height), colour).save(path)
    return path


def notes_of(output_dir: Path) -> list[str]:
    return [n["note"] for n in json.loads((output_dir / "figures.json").read_text())["findings"]]


MARKDOWN = """# A paper

## 1. Introduction

The overview is in Figure 1, the result in Figs. 2b and 3, and the controls in Supplementary Figure 1.

![](fig/one.png)

**Figure 1.** The overview, as in Figure 3.

![](fig/two.png)

Figure 2: The result.

![The third figure, with its caption in the alt text](fig/three.png)

![](fig/four.png)

*Figure S1.* The controls.

Figure 2 shows the result again, and Figure 7 does not exist.
"""


def test_markdown_figures_take_their_caption_number_and_files(tmp_path: Path) -> None:
    for name in ("one", "two", "three", "four"):
        png(tmp_path / "fig" / f"{name}.png")
    (tmp_path / "paper.md").write_text(MARKDOWN)
    source, found = figures.find_figures(tmp_path / "paper.md")
    assert [(f.id, f.files) for f in found] == [("Figure 1", ["fig/one.png"]), ("Figure 2", ["fig/two.png"]),
                                                ("Unnumbered figure 3", ["fig/three.png"]), ("Figure S1", ["fig/four.png"])]
    assert found[0].caption.startswith("**Figure 1.**") and found[2].caption.startswith("The third figure")
    # "Figure 2 shows ..." is a sentence, not a caption: it does not number anything.
    assert figures.caption_number("Figure 2 shows the result again.") is None
    assert figures.caption_number("Supplementary Figure 3. Controls.") == "S3"


def test_figures_without_numbered_captions_are_numbered_in_order(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text("# P\n\n![A first](a.png)\n\nText.\n\n![A second](b.png)\n")
    _, found = figures.find_figures(tmp_path / "paper.md")
    assert [f.id for f in found] == ["Figure 1", "Figure 2"]


def test_citations_skip_the_own_caption_and_report_order_absence_and_missing_figures(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text(MARKDOWN)
    source, found = figures.find_figures(tmp_path / "paper.md")
    cites = figures.citations(source, found)
    body = [c["id"] for c in cites if not c["in_caption_of"]]
    assert body[:4] == ["Figure 1", "Figure 2", "Figure 3", "Figure S1"]  # "Figs. 2b and 3" is two citations
    assert any(c["in_caption_of"] == "Figure 1" and c["id"] == "Figure 3" for c in cites)
    notes = [n["note"] for n in figures.citation_problems(found, cites)]
    assert "Unnumbered figure 3 is never cited in the text." in notes
    assert "The text cites Figure 7, which does not exist (1. Introduction, paper.md line 21)." in notes
    # A caption without its number leaves the citations of that number pointing nowhere: both are reported.
    assert "The text cites Figure 3, which does not exist (1. Introduction, paper.md line 5)." in notes
    assert figures.cited_numbers(False, "2–4") == ["2", "3", "4"] and figures.cited_numbers(True, "1 and 3") == ["S1", "S3"]


def test_a_figure_first_cited_after_a_later_one_is_out_of_order(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text("# P\n\nSee Figure 2, then Figure 1.\n\n![](a.png)\n\n**Figure 1.** A.\n\n![](b.png)\n\n**Figure 2.** B.\n")
    source, found = figures.find_figures(tmp_path / "paper.md")
    notes = [n["note"] for n in figures.citation_problems(found, figures.citations(source, found))]
    assert notes == ["Figure 2 is first cited before Figure 1 (P, paper.md line 3)."]


def test_latex_follows_inputs_graphicspath_figure_star_refs_and_ignores_comments(tmp_path: Path) -> None:
    (tmp_path / "figs").mkdir()
    (tmp_path / "main.tex").write_text(
        "\\graphicspath{{figs/}}\n\\section{Intro}\nSee Figures~\\ref{fig:a} and \\cref{fig:b,fig:gone}.\n"
        "% \\ref{fig:old} is commented out\n\\input{part}\n")
    (tmp_path / "part.tex").write_text(
        "\\begin{figure}\\includegraphics[width=\\columnwidth]{a}\\caption{The \\textbf{first} result.}\\label{fig:a}\\end{figure}\n"
        "\\begin{figure*}\\includegraphics{b.pdf}\\caption[short]{The second.}\\label{fig:b}\\end{figure*}\n"
        "\\renewcommand{\\thefigure}{S\\arabic{figure}}\n"
        "\\begin{figure}\\includegraphics{c}\\caption{Controls.}\\label{fig:c}\\end{figure}\n")
    png(tmp_path / "figs" / "a.png")
    source, found = figures.find_figures(tmp_path / "main.tex")
    assert [(f.id, f.wide, f.caption) for f in found] == [("Figure 1", False, "The first result."), ("Figure 2", True, "The second."),
                                                          ("Figure S1", False, "Controls.")]
    assert figures.resolve("a", source) == (tmp_path / "figs" / "a.png").resolve()
    assert source.where(found[0].start) == "part.tex line 1"
    notes = [n["note"] for n in figures.citation_problems(found, figures.citations(source, found))]
    assert "The text cites a figure labelled fig:gone, which does not exist (Intro, main.tex line 3)." in notes
    assert "Figure S1 is never cited in the text." in notes and not any("fig:old" in n for n in notes)


def vector_pdf(path: Path, width_pt: float = 1152, size: float = 9, line: float = 0.5) -> Path:
    import pymupdf

    with pymupdf.open() as doc:
        page = doc.new_page(width=width_pt, height=width_pt / 2)
        page.insert_text((72, 72), "Time (s)", fontsize=size)
        page.draw_line((72, 100), (500, 100), width=line)
        doc.save(str(path))
    return path


def test_vector_text_and_lines_are_measured_as_printed(tmp_path: Path) -> None:
    page = figures.Page(vector_pdf(tmp_path / "fig.pdf"), 1, True, width_pt=1152)
    record, notes = figures.measure(page, tmp_path / "out", 85.0, {"min_pt": 6, "min_line_pt": 0.25, "min_dpi": 300})
    scale = 85 / 25.4 * 72 / 1152  # a 16-inch figure printed in an 85 mm column
    assert record["min_text_pt"] == pytest.approx(9 * scale, abs=0.1)
    assert record["min_line_pt"] == pytest.approx(0.5 * scale, abs=0.01)
    assert record["smallest_text"][0]["text"] == "Time (s)"
    assert any("text as small as 1.9 pt" in n for n in notes) and any("lines as thin as" in n for n in notes)
    with Image.open(tmp_path / "out" / "sheet.png") as sheet, Image.open(tmp_path / "out" / "view.png") as view:
        assert view.width == round(85 / 25.4 * 300)
        assert sheet.width == 2 * round(85 / 25.4 * 150) + 36  # colour, greyscale and two simulations, two by two


def test_a_raster_is_measured_by_its_resolution_as_printed(tmp_path: Path) -> None:
    page = figures.pages_of(png(tmp_path / "small.png", width=600), tmp_path)[0][0]
    record, notes = figures.measure(page, tmp_path / "out", 85.0, {"min_pt": 6, "min_line_pt": 0.25, "min_dpi": 300})
    assert record["dpi"] == 179 and "text" not in json.dumps(record).lower().replace("text_source", "")
    assert notes == ["is 600 pixels wide, 179 dpi printed 85 mm wide; the minimum used is 300 dpi"]


def test_red_and_green_merge_under_simulated_deuteranopia() -> None:
    image = Image.new("RGB", (2, 1))
    image.putpixel((0, 0), (214, 39, 40))
    image.putpixel((1, 0), (44, 160, 44))
    seen = figures.simulated(image, figures.CVD["Deuteranopia"])
    assert math.dist(image.getpixel((0, 0)), image.getpixel((1, 0))) > 150
    assert math.dist(seen.getpixel((0, 0)), seen.getpixel((1, 0))) < 60


def test_unreadable_files_are_reported_not_fatal(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("not an image")
    assert figures.pages_of(tmp_path / "notes.txt", tmp_path) == ([], ".txt is not an image format this script renders")
    (tmp_path / "paper.md").write_text("# P\n\nFigure 1 shows it.\n\n![](missing.png)\n\n**Figure 1.** Gone.\n")
    result = runner.invoke(figures.app, ["inventory", str(tmp_path / "paper.md"), "--output-dir", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert notes_of(tmp_path / "out") == ["Figure 1: missing.png was not found."]


def test_the_seeded_fixture_shows_an_uncited_figure_and_the_clean_control_shows_nothing(tmp_path: Path) -> None:
    for name in ("seeded", "clean"):
        result = runner.invoke(figures.app, ["inventory", str(FIXTURES / name / "paper.md"), "--output-dir", str(tmp_path / name)])
        assert result.exit_code == 0, result.output
    assert notes_of(tmp_path / "seeded") == ["Figure 4 is never cited in the text."]
    assert notes_of(tmp_path / "clean") == []
    document = json.loads((tmp_path / "seeded" / "figures.json").read_text())
    assert [f["id"] for f in document["figures"]] == ["Figure 1", "Figure 2", "Figure 3", "Figure 4"]
    assert (tmp_path / "seeded" / document["figures"][1]["files"][0]["sheet"]).is_file()
    # The script cannot see that Figure 2's labels are unreadable: it is a sharp raster. Looking at the sheet can.
    assert document["figures"][1]["files"][0]["dpi"] > 300
    again = runner.invoke(figures.app, ["inventory", str(FIXTURES / "seeded" / "paper.md"), "--output-dir", str(tmp_path / "seeded")])
    assert again.exit_code == 1 and "exists" in again.output


def test_the_latex_fixture_measures_vector_text_and_finds_a_missing_label(tmp_path: Path) -> None:
    result = runner.invoke(figures.app, ["inventory", str(FIXTURES / "latex" / "main.tex"), "--output-dir", str(tmp_path / "out"),
                                         "--column-mm", "89", "--min-pt", "7"])
    assert result.exit_code == 0, result.output
    notes = notes_of(tmp_path / "out")
    assert any(n.startswith("Figure 1: runtime has text as small as") and "the minimum used is 7 pt" in n for n in notes)
    assert "The text cites a figure labelled fig:peak, which does not exist (Discussion, main.tex line 15)." in notes
    document = json.loads((tmp_path / "out" / "figures.json").read_text())
    assert document["figures"][1]["printed_mm"] == 178.0 and document["figures"][1]["printed_width"] == "page (figure*)"


def test_a_seat_workspace_gets_the_figures_and_their_captions_and_nothing_else(tmp_path: Path) -> None:
    into = tmp_path / "seat" / "figures"
    result = runner.invoke(figures.app, ["workspace", str(FIXTURES / "seeded" / "paper.md"), "--into", str(into)])
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in into.iterdir()) == ["figure-1.png", "figure-2.png", "figure-3.png", "figure-4.png", "index.md"]
    index = (into / "index.md").read_text()
    assert "**Figure 4**: `figure-4.png`. **Figure 4.** Resident memory of Varlens during one annotation run." in index
    assert not re.search(r"\d\s?pt\b|dpi|never cited|greyscale", index)  # no measurement or note: the seat looks for itself
    assert runner.invoke(figures.app, ["workspace", str(FIXTURES / "seeded" / "paper.md"), "--into", str(into)]).exit_code == 1


def test_eval_cases_are_well_formed_and_use_files_that_exist() -> None:
    import yaml

    cases = yaml.safe_load((ROOT / "evals" / "manuscript-figures.yaml").read_text(encoding="utf-8"))
    assert 3 <= len(cases) <= 7 and len({c["id"] for c in cases}) == len(cases)
    for case in cases:
        assert {"id", "skill", "prompt", "files", "planted", "rubric", "fail_if"} <= set(case), case["id"]
        assert all((ROOT / "evals" / f).is_file() for f in case["files"]), case["id"]
    assert {c["skill"] for c in cases} == {"manuscript-figures", "manuscript-peer-review"}
    assert any(all("/clean/" in f for f in c["files"]) for c in cases)  # the clean control
