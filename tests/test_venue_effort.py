"""How much choosing a journal would change the manuscript (manuscript-journal-select's effort.py): what an editor
counts in a Markdown or LaTeX manuscript, each kind of change sized against a venue's recorded rules, a rule nobody
read kept as "not researched", and the estimate reaching the dashboard's Journals tab. Run with `uv run pytest`."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest
import typer
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


effort = _load("effort_under_test", ROOT / "skills" / "manuscript-journal-select" / "scripts" / "effort.py")
# collect.py imports its siblings (the renderer as `dashboard`, stage_check) by name, as when it runs as a script;
# a `dashboard` another test module loaded is the same file and is reused.
DASHBOARD = ROOT / "skills" / "manuscript-dashboard" / "scripts"
if str(DASHBOARD) not in sys.path:
    sys.path.insert(0, str(DASHBOARD))
dashboard = sys.modules.get("dashboard") or _load("dashboard", DASHBOARD / "dashboard.py")
collect = _load("collect_effort", DASHBOARD / "collect.py")

ABSTRACT = ["We built a tool that reads a genome locally and reports what published modules say about it.",
            "It is fast, open and runs on a laptop."]
BODY = {  # heading -> its paragraphs; the kinds follow the headings
    "1. Introduction": ["Genomes are cheap to sequence and hard to read without uploading them somewhere."],
    "1.1 Background": ["Earlier tools needed a server, a database and a week of setup."],
    "2. Methods": ["The engine joins the variant file with each module on position and allele.",
                   "Modules are tables written as CSV without code."],
    "3. Results": ["A whole genome is annotated in about a minute (Kulaga et al., 2024)."],
    "4. Discussion": ["Local processing keeps the genome on the user's computer."],
    "5. Conclusion": ["The tool makes reading one's own genome routine."],
}
CAPTIONS = ["**Figure 1.** The annotation report for one genome, with its sources.",
            "**Table 1.** Annotation time per genome.", "**Figure S1.** A supplementary view."]


def words(text: str) -> int:
    return sum(1 for token in text.split() if any(ch.isalnum() for ch in token))


def markdown_paper(structured: bool = False) -> str:
    abstract = ([f"**Background:** {ABSTRACT[0]}", f"**Results:** {ABSTRACT[1]}"] if structured else ABSTRACT)
    out = ["# **A Local Genome Reader**", "", "Anna Author, Ben Author", "", "## Abstract", "",
           "<!-- @rev C1 rounds=2 by=claude:2026-10-28 -->", "\n\n".join(abstract), "<!-- @/rev C1 -->", ""]
    for heading, paragraphs in BODY.items():
        level = "###" if heading[1:3] == ".1" else "##"
        out += [f"{level} {heading}", "", *("\n\n".join(paragraphs).split("\n")), ""]
        if heading.startswith("3."):
            out += ["![The report](figures/report.png)", "", CAPTIONS[0], "", CAPTIONS[1], "",
                    "| Genome | Minutes |", "|---|---|", "| A | 1.1 |", "", "**Box 1.** Who the tool is for.", "",
                    CAPTIONS[2], ""]
    out += ["## Data Availability", "", "The genomes are on Zenodo.", "", "## References", "",
            "Kulaga, A. (2024). A paper.", "", "Smith, B. (2020). Another paper.", "", "Lee, C. (2019). A third.", ""]
    return "\n".join(out)


def body_truth() -> int:
    box = "Box 1. Who the tool is for."  # a box's title line is text of the section it sits in
    return sum(words(p) for ps in BODY.values() for p in ps) + words(box)


def test_markdown_is_measured_as_an_editor_counts_it(tmp_path: Path) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text(markdown_paper(), encoding="utf-8")
    m = effort.measure(paper)
    assert m["body_words"] == body_truth()
    assert m["abstract_words"] == sum(words(p) for p in ABSTRACT) and m["abstract_paragraphs"] == len(ABSTRACT)
    assert m["abstract_headings"] == []
    # Figure S1 is the supplement's; the revision marks, the table cells and the back matter are not body text.
    assert (m["figures"], m["tables"], m["boxes"], m["references"]) == (1, 1, 1, 3)
    assert m["caption_words"] == sum(words(c.replace("**", "")) for c in CAPTIONS)
    assert [s["heading"] for s in m["sections"]] == ["Introduction", "Methods", "Results", "Discussion", "Conclusion"]
    assert [s["kind"] for s in m["sections"]] == ["introduction", "methods", "results", "discussion", "conclusion"]
    assert sum(p["words"] for p in m["parts"]) == m["body_words"]
    assert {p["kind"] for p in m["parts"] if p["heading"] == "Background"} == {"introduction"}


def test_a_structured_abstract_keeps_its_headings(tmp_path: Path) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text(markdown_paper(structured=True), encoding="utf-8")
    assert effort.measure(paper)["abstract_headings"] == ["Background", "Results"]


def test_latex_is_measured_too(tmp_path: Path) -> None:
    paper = tmp_path / "main.tex"
    paper.write_text("\n".join([
        r"\documentclass{article}", r"\begin{document}", r"\title{A Reader}", r"\maketitle",
        r"\begin{abstract}", ABSTRACT[0], r"\end{abstract}",
        r"\section{Introduction}", BODY["1. Introduction"][0] + r" \cite{a,b}",
        r"\section{Methods}", BODY["2. Methods"][0],
        r"\begin{figure}\includegraphics{x}\caption{A report.}\end{figure}",
        r"\begin{table}\caption{Times.}\begin{tabular}{ll}a & b\end{tabular}\end{table}",
        r"\section{Results}", BODY["3. Results"][0], r"\section{Discussion}", BODY["4. Discussion"][0],
        r"\begin{thebibliography}{9}\bibitem{a} A.\bibitem{b} B.\end{thebibliography}", r"\end{document}"]),
        encoding="utf-8")
    m = effort.measure(paper)
    assert (m["figures"], m["tables"], m["references"]) == (1, 1, 2)
    assert m["abstract_words"] == words(ABSTRACT[0])
    # Each key of a \cite counts as one word, as the printed reference number does.
    assert m["body_words"] == sum(words(BODY[h][0]) for h in ("1. Introduction", "2. Methods", "3. Results",
                                                              "4. Discussion")) + 2
    assert [s["kind"] for s in m["sections"]] == ["introduction", "methods", "results", "discussion"]


def measured(**over: object) -> dict:
    sections = [{"heading": h, "kind": k} for h, k in (("Introduction", "introduction"), ("Methods", "methods"),
                                                      ("Results", "results"), ("Discussion", "discussion"))]
    m = {"file": "paper.md", "body_words": 1000, "abstract_words": 200, "abstract_paragraphs": 1, "abstract_headings": [],
         "caption_words": 0, "table_words": 0, "figures": 3, "tables": 4, "boxes": 1, "references": 40,
         "sections": sections, "headings": ["Abstract", *(s["heading"] for s in sections), "Data Availability"],
         "parts": [{"heading": "Introduction", "kind": "introduction", "words": 200},
                   {"heading": "Methods", "kind": "methods", "words": 500},
                   {"heading": "Results", "kind": "results", "words": 200},
                   {"heading": "Discussion", "kind": "discussion", "words": 100}]}
    return {**m, **over}


def row(estimate: dict, aspect: str) -> dict:
    (found,) = [i for i in estimate["items"] if i["aspect"] == aspect]
    return found


def venue(**fields: object) -> dict:
    return {"key": "j", "name": "Journal", "url": "https://j.example/guidelines", **fields}


@pytest.mark.parametrize("limit, kind, size", [
    (1200, None, "none"), (950, None, "small"), (800, None, "medium"), (500, None, "large"),
    (800, "recommended", "small"), (500, "recommended", "medium"), (950, "recommended", "small")])
def test_the_body_cut_is_sized_by_the_share_of_the_body_it_removes(limit: int, kind: str | None, size: str) -> None:
    v = venue(limits={"body_words": limit, **({"body_words_kind": kind} if kind else {})})
    got = row(effort.estimate(measured(), v, {}, []), "body")
    assert got["size"] == size
    if size != "none":
        assert f"{round(100 * (1000 - limit) / 1000)}% of the body" in got["change"]


def test_a_paper_far_over_a_limit_that_returns_overlength_papers_is_a_major_change() -> None:
    v = venue(limits={"body_words": 960, "over_limit_return": 1.02})
    got = row(effort.estimate(measured(), v, {}, []), "body")
    assert got["size"] == "large" and "returned unread" in got["change"]


def test_a_limit_that_leaves_the_methods_out_counts_the_rest() -> None:
    v = venue(limits={"body_words": 700, "body_words_excludes": ["methods"]})
    est = effort.estimate(measured(), v, {}, [])
    got = row(est, "body")
    assert got["size"] == "none" and got["have"].startswith("500 words outside the methods (1,000 with them)")
    assert est["words_to_cut"] == 0


@pytest.mark.parametrize("limit, size", [(250, "none"), (150, "small"), (100, "medium")])
def test_the_abstract_cut_is_a_trim_up_to_a_third_and_a_rewrite_beyond(limit: int, size: str) -> None:
    assert row(effort.estimate(measured(), venue(limits={"abstract_words": limit}), {}, []), "abstract")["size"] == size


def test_an_unread_rule_is_not_researched_never_a_fit() -> None:
    est = effort.estimate(measured(), venue(), {}, [])
    sizes = {i["aspect"]: i["size"] for i in est["items"]}
    assert sizes == {"body": "unknown", "abstract": "unknown", "abstract_form": "unknown", "display": "unknown",
                     "structure": "unknown"}
    assert est["size"] == "no change" and "Not researched yet" in est["summary"]


def test_a_page_read_and_found_to_set_none_is_known() -> None:
    v = venue(limits={"none_stated": ["body_words", "abstract_words", "display_items"]}, abstract_headings=[],
              required_sections=[])
    est = effort.estimate(measured(), v, {}, [])
    assert all(i["size"] == "none" for i in est["items"]) and "Not researched" not in est["summary"]


@pytest.mark.parametrize("wanted, labels, size", [
    ([], [], "none"), ([], ["Background", "Results"], "small"), (["Background", "Results"], [], "small"),
    (["Background", "Results"], ["background", "results"], "none")])
def test_the_abstract_form(wanted: list[str], labels: list[str], size: str) -> None:
    got = row(effort.estimate(measured(abstract_headings=labels), venue(abstract_headings=wanted), {}, []),
              "abstract_form")
    assert got["size"] == size


@pytest.mark.parametrize("rule, article_type, size, over", [
    ({"article": 7, "report": 4}, "Research Article", "small", 1),  # 3 figures + 4 tables + 1 box = 8
    ({"article": 7, "report": 4}, "Report", "medium", 4),
    (9, "", "none", 0),
    ({"application note": {"figures": 3, "tables": 2}}, "Application Note", "medium", 3),  # the box counts as a table
    ({"research and applications": {"figures": 6, "tables": 4}}, "Application Note", "unknown", None),
])
def test_figures_and_tables_against_the_limit_for_the_article_type(rule: object, article_type: str, size: str,
                                                                   over: int | None) -> None:
    v = venue(figure_rules={"display_items": rule, "source": "https://j.example/figures", "checked": date(2026, 11, 2)})
    got = row(effort.estimate(measured(), v, {"article_type": article_type}, []), "display")
    assert got["size"] == size
    if over:
        assert f"merge {over} into" in got["change"]
    if size != "unknown":
        assert got["source"] == "https://j.example/figures" and got["checked"] == "2026-11-02"


def test_the_entry_can_give_the_limits_of_the_article_type_chosen() -> None:
    v = venue(limits={"body_words": 500}, figure_rules={"display_items": {"application note": {"figures": 3, "tables": 2}}})
    entry = {"article_type": "Research and Applications", "limits": {"body_words": 4000},
             "display_items": {"figures": 6, "tables": 4}}
    est = effort.estimate(measured(), v, entry, [])
    assert row(est, "body")["size"] == "none" and row(est, "display")["size"] == "small"


@pytest.mark.parametrize("required, size, words", [
    (["Introduction", "Method", "Results", "Discussion"], "none", None),  # "Methods" is "Method"
    (["Introduction", "Results", "Methods", "Discussion"], "medium", "reorder"),
    (["Introduction", "Methods", "Results", "Discussion", "Conclusions"], "medium", "Conclusions"),
    (["Background", "Implementation", "Results", "Discussion"], "small", "rename"),
    (["Introduction", "Methods", "Results and Discussion"], "small", "fold"),
    (["Introduction", "Discussion"], "none", None),  # Methods and Results are kinds it does not name: they stay
])
def test_the_body_sections_against_the_structure_a_venue_sets(required: list[str], size: str, words: str | None) -> None:
    got = row(effort.estimate(measured(), venue(required_sections=required), {}, []), "structure")
    assert got["size"] == size
    if words:
        assert words in got["change"]


def test_sections_to_add_are_matched_on_their_words() -> None:
    v = venue(required_sections=["Data Availability Statement", "Limitations of the study", "Introduction"])
    got = row(effort.estimate(measured(), v, {}, []), "sections")
    assert got["size"] == "small" and got["have"] == "1 of 2 present" and got["change"] == "add Limitations of the study"


def test_validation_the_paper_does_not_show_is_a_major_change_and_an_unchecked_rule_stays_open() -> None:
    rule = {"id": "comparison", "applies_to": ["software"], "strength": "required", "accepted_any": ["benchmark"],
            "description": "A method is compared with related methods"}
    v = venue(validation_requirements=[rule, {**rule, "id": "cohort", "description": "An independent cohort"}],
              manuscript_conditions={"comparison": {"met": "partly", "evidence": "Missing: ANNOVAR and VEP.",
                                                    "checked": date(2026, 10, 28)}})
    est = effort.estimate(measured(), v, {}, ["software"])
    rows = [i for i in est["items"] if i["aspect"] == "validation"]
    assert [(r["size"], r["limit"]) for r in rows] == [("large", "A method is compared with related methods"),
                                                       ("unknown", "An independent cohort")]
    assert rows[0]["change"] == "Missing: ANNOVAR and VEP." and est["size"] == "major"


def test_changes_judged_from_the_guidelines_join_the_estimate() -> None:
    entry = {"changes": [{"what": "STAR Methods", "change": "move Sections 2 and 3 into the STAR Methods",
                          "size": "medium", "rule": "the revision follows the Cell Press structure",
                          "url": "https://j.example/revise"}]}
    est = effort.estimate(measured(), venue(limits={"none_stated": ["body_words"]}), entry, [])
    assert est["size"] == "moderate" and row(est, "judged")["source"] == "https://j.example/revise"
    with pytest.raises(typer.BadParameter):
        effort.estimate(measured(), venue(), {"changes": [{"what": "x", "size": "huge"}]}, [])


MINUS = "\u2212"


@pytest.mark.parametrize("fields, aspect, numbers, note", [
    ({"limits": {"body_words": 8000, "body_words_kind": "recommended"}}, "body", f"1,000 / 8,000 · {MINUS}7,000", "advised"),
    ({"limits": {"body_words": 950}}, "body", "1,000 / 950 · +50", ""),
    ({"limits": {"body_words": 1000}}, "body", "1,000 / 1,000 · 0", ""),
    ({"limits": {"body_words": 700, "body_words_excludes": ["methods"]}}, "body", f"500 / 700 · {MINUS}200",
     "methods not counted"),
    ({"limits": {"none_stated": ["body_words"]}}, "body", "1,000 · no limit", ""),
    ({}, "body", "1,000 / ?", ""),
    ({"limits": {"abstract_words": 150}}, "abstract", "200 / 150 · +50", ""),
    ({"limits": {"abstract_words": 250}}, "abstract", f"200 / 250 · {MINUS}50", ""),
    ({"limits": {"abstract_characters": 1920}}, "abstract", "200 · no word limit", "at most 1,920 characters"),
    ({"figure_rules": {"display_items": 7}}, "display", "8 / 7 · +1", ""),
    ({"figure_rules": {"display_items": {"figures": 3, "tables": 2}}}, "display", "3 + 5 / 3 + 2 · +3", "boxes as tables"),
    ({"limits": {"none_stated": ["display_items"]}}, "display", "8 · no limit", ""),
])
def test_lengths_and_counts_read_as_numbers_against_the_limit(fields: dict, aspect: str, numbers: str, note: str) -> None:
    """The dashboard shows "the manuscript / the limit · how far over or under", never a sentence."""
    got = row(effort.estimate(measured(), venue(**fields), {}, []), aspect)
    assert (got["numbers"], got["note"]) == (numbers, note)
    assert dashboard.AdaptationItem.model_validate(got).numbers == numbers


def test_words_to_cut_add_the_body_and_the_abstract() -> None:
    est = effort.estimate(measured(), venue(limits={"body_words": 900, "abstract_words": 150}), {}, [])
    assert est["words_to_cut"] == 100 + 50 and est["size"] == "light"


CATALOGUE = {"checked": date(2026, 11, 2), "venues": {
    "short": {"name": "Short Journal", "url": "https://short.example/guide", "writing_help": "disclose",
              "limits": {"abstract_words": 150, "body_words": 2000}, "abstract_headings": [], "required_sections": []},
    "roomy": {"name": "Roomy Journal", "url": "https://roomy.example/guide", "writing_help": "disclose",
              "limits": {"body_words": 12000, "none_stated": ["abstract_words", "display_items"]},
              "abstract_headings": [], "required_sections": ["Introduction", "Method", "Results", "Discussion"]}}}


@pytest.fixture()
def catalogue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "venues.yaml"
    p.write_text(yaml.safe_dump(CATALOGUE), encoding="utf-8")
    monkeypatch.setattr(effort.venues, "VENUES_YAML", p)
    monkeypatch.setattr(effort.venues, "SNAPSHOT_INDEX", tmp_path / "index.yaml")
    return p


def test_the_cli_writes_what_the_dashboard_reads(tmp_path: Path, catalogue: Path) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text(markdown_paper(), encoding="utf-8")
    top3 = tmp_path / "top3.json"
    top3.write_text(json.dumps([{"key": "roomy", "name": "Roomy Journal", "article_type": "Technology and Code"},
                                {"key": "short", "name": "Short Journal", "article_type": "Application Note"}]),
                    encoding="utf-8")
    result = CliRunner().invoke(effort.app, [str(paper), "--top3", str(top3), "--format", "json"])
    assert result.exit_code == 0, result.output
    doc = json.loads(result.output)
    assert [v["key"] for v in doc["venues"]] == ["roomy", "short"]
    assert doc["measured"]["body_words"] == body_truth()
    short = doc["venues"][1]
    assert row(short, "body")["size"] == "none"  # a toy paper fits even the short limit
    text = CliRunner().invoke(effort.app, [str(paper), "--venue", "short", "--venue", "roomy"])
    assert text.exit_code == 0 and "## Short Journal: " in text.output and "## Roomy Journal: " in text.output
    missing = CliRunner().invoke(effort.app, [str(paper), "--venue", "nowhere"])
    assert missing.exit_code != 0

    # The run folder the dashboard reads: the estimate joins the journal's rung and validates as the dashboard's model.
    run = tmp_path / "run"
    folder = run / "manuscript-journal-select"
    folder.mkdir(parents=True)
    (folder / "p.journal-ladder.csv").write_text("ladder,rung,key,name\njournals,1,roomy,Roomy Journal\n"
                                                 "journals,2,short,Short Journal\njournals,3,other,Other\n",
                                                 encoding="utf-8")
    (folder / "top3.json").write_text(top3.read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "adaptation.json").write_text(result.output, encoding="utf-8")
    rows = {v["key"]: v for v in collect.venues(run)}
    assert rows["other"]["adaptation"] is None
    adapted = dashboard.Venue.model_validate(rows["roomy"]).adaptation
    assert adapted is not None and adapted.measured == doc["measured_text"]
    assert [i.what for i in adapted.items] == [i["what"] for i in doc["venues"][0]["items"]]
    assert adapted.size == doc["venues"][0]["size"]


def test_a_broken_estimate_file_shows_nothing_rather_than_a_guess(tmp_path: Path) -> None:
    path = tmp_path / "adaptation.json"
    path.write_text("{not json", encoding="utf-8")
    assert collect.adaptations(path) == {} and collect.adaptations(None) == {}
