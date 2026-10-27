"""Offline tests for manuscript-peer-review's workspaces.py: the seats' and the defender's workspaces, built from
the paper, its supplement and its files, and each seat's brief filled in from the template in seats.md.

Run with `uv run --group dev pytest tests/test_peer_review_workspaces.py -q`.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
from PIL import Image
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "manuscript-peer-review" / "scripts" / "workspaces.py"
spec = importlib.util.spec_from_file_location("peer_review_workspaces", SCRIPT)
workspaces = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = workspaces
spec.loader.exec_module(workspaces)
runner = CliRunner()

PAPER = """# A tool for annotating genomes
<!-- A note for the co-authors: check the numbers. -->

## 1. Introduction

The tool annotates a VCF in minutes (Figure 1); the module sources are in S1_sources.csv.
<!-- @rev C3 rounds=1 by=agent:2026-10-27 -->
A rewritten sentence the editor sees without its mark.
<!-- @/rev C3 -->

![](fig/one.png)

**Figure 1.** The annotation run, step by step.
"""

SUPPLEMENT = """# Supplementary material

The coverage table is S2_coverage.md. <!-- inline note -->

![](fig/s1.png)

**Figure S1.** The controls.
"""


def png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 200), "white").save(path)
    return path


@pytest.fixture
def project(tmp_path: Path) -> Path:
    root = tmp_path / "paper"
    png(root / "fig" / "one.png")
    png(root / "fig" / "s1.png")
    (root / "paper.md").write_text(PAPER, encoding="utf-8")
    (root / "supplement.md").write_text(SUPPLEMENT, encoding="utf-8")
    files = root / "supplementary"
    files.mkdir()
    (files / "S1_sources.csv").write_text("id,source\n1,PMID:1\n", encoding="utf-8")
    (files / "S2_coverage.md").write_text("Coverage per score; the raw rows are in S2_rows.json.\n"
                                          "<!-- private: rerun before submission -->\n", encoding="utf-8")
    (files / "S2_rows.json").write_text("[]\n", encoding="utf-8")
    (files / "S3_unused.yaml").write_text("a: 1\n", encoding="utf-8")
    (files / ".hidden").write_text("x\n", encoding="utf-8")
    (root / "venue.md").write_text("# iScience\n\nWhat its referees are asked.\n", encoding="utf-8")
    return root


def seats(project: Path, work: Path, *extra: str) -> tuple[int, dict | str]:
    args = ["seats", str(work), "--paper", str(project / "paper.md"), "--supplement", str(project / "supplement.md"),
            "--files", str(project / "supplementary"), "--venue", str(project / "venue.md"),
            "--journal", "iScience=Research Article", "--design", "`software-tool`", *extra]
    result = runner.invoke(workspaces.app, args)
    return result.exit_code, (json.loads(result.stdout) if result.exit_code == 0 else result.output)


# ---------------------------------------------------------------- reading copies

def test_comments_and_revision_marks_leave_the_reading_copy() -> None:
    copy = workspaces.without_comments(PAPER, ".md")
    assert "<!--" not in copy and "@rev" not in copy and "co-authors" not in copy
    assert "A rewritten sentence the editor sees without its mark.\n\n![](fig/one.png)" in copy
    assert "The tool annotates" in copy


def test_latex_comments_go_and_an_escaped_percent_stays() -> None:
    tex = "Coverage is 95\\% here. % a note\n% @rev C1 rounds=1 by=agent:2026-10-27\nKept line.\n% @/rev C1\n"
    assert workspaces.without_comments(tex, ".tex") == "Coverage is 95\\% here. \nKept line.\n"


def test_html_comments_in_latex_are_text() -> None:
    assert "<!-- x -->" in workspaces.without_comments("a <!-- x --> b\n", ".tex")


# ---------------------------------------------------------------- the seats

def test_each_seat_gets_only_what_the_skill_allows(project: Path, tmp_path: Path) -> None:
    code, out = seats(project, tmp_path / "work", "--seat", "evidence-statistics", "--seat", "skeptic",
                      "--seat", "champion", "--module", "skeptic=genomics")
    assert code == 0, out
    skeptic = Path(out["seats"][1]["workspace"])
    files = sorted(p.relative_to(skeptic).as_posix() for p in skeptic.rglob("*") if p.is_file())
    assert files == ["domain-questions.md", "figures/figure-1.png", "figures/figure-s1.png", "figures/index.md",
                     "finding-schema.md", "manuscript.md", "supplementary.md", "supplementary/S1_sources.csv",
                     "supplementary/S2_coverage.md", "supplementary/S2_rows.json", "venue.md"]
    assert "<!--" not in (skeptic / "supplementary" / "S2_coverage.md").read_text(encoding="utf-8")
    assert out["left_out"] == {"S3_unused.yaml": "not named in the paper, its supplement or a file they name"}
    index = (skeptic / "figures" / "index.md").read_text(encoding="utf-8")
    assert "- **Figure 1**: `figure-1.png`. **Figure 1.** The annotation run" in index
    assert "- **Figure S1**: `figure-s1.png`" in index
    champion = Path(out["seats"][2]["workspace"])
    assert not (champion / "domain-questions.md").exists()


def test_all_files_takes_the_unnamed_ones(project: Path, tmp_path: Path) -> None:
    code, out = seats(project, tmp_path / "work", "--seat", "champion", "--all-files")
    assert code == 0 and out["left_out"] == {}
    assert (Path(out["seats"][0]["workspace"]) / "supplementary" / "S3_unused.yaml").is_file()
    assert not (Path(out["seats"][0]["workspace"]) / "supplementary" / ".hidden").exists()


def test_the_brief_is_the_template_filled_in(project: Path, tmp_path: Path) -> None:
    code, out = seats(project, tmp_path / "work", "--seat", "evidence-statistics", "--seat", "skeptic",
                      "--seat", "champion", "--module", "skeptic=genomics")
    assert code == 0, out
    entry = out["seats"][1]
    brief = Path(entry["brief"]).read_text(encoding="utf-8")
    assert brief.startswith("You are the **skeptic** on a simulated referee panel. The editor of iScience has asked "
                            "you to referee this manuscript, submitted as Research Article.")
    assert f"Work only from the files in {entry['workspace']};" in brief
    assert "numbered SK-1, SK-2" in brief and "Your domain questions are in `domain-questions.md`." in brief
    assert not re.search(r"<[A-Za-z][^<>\n]*>", brief) and not brief.startswith(">")
    # The default panel: the skeptic also covers claims and novelty, the main seat reproducibility.
    assert "You also take the claims-novelty remit:" in brief
    main = Path(out["seats"][0]["brief"]).read_text(encoding="utf-8")
    assert "You also take the reproducibility remit:" in main and "Your domain questions" not in main
    champion = Path(out["seats"][2]["brief"]).read_text(encoding="utf-8")
    assert "You also take" not in champion
    assert brief.rstrip().endswith("`venue.md`, `finding-schema.md`, `domain-questions.md`.")


def test_a_remit_with_its_own_seat_is_not_added_to_another(project: Path, tmp_path: Path) -> None:
    code, out = seats(project, tmp_path / "work", "--seat", "evidence-statistics", "--seat", "skeptic",
                      "--seat", "claims-novelty", "--seat", "reproducibility")
    assert code == 0, out
    assert all("You also take" not in Path(s["brief"]).read_text(encoding="utf-8") for s in out["seats"])


def test_several_journals_get_one_recommendation_each(project: Path, tmp_path: Path) -> None:
    code, out = seats(project, tmp_path / "work", "--seat", "champion", "--journal", "JAMIA Open=Application Note",
                      "--journal", "Frontiers in Bioinformatics")
    assert code == 0, out
    brief = Path(out["seats"][0]["brief"]).read_text(encoding="utf-8")
    assert ("The authors are considering iScience (Research Article), JAMIA Open (Application Note) and Frontiers in "
            "Bioinformatics for this manuscript. Referee it once, and give each journal your recommendation.") in brief


def test_a_given_remit_replaces_the_sections(project: Path, tmp_path: Path) -> None:
    remit = tmp_path / "remit.md"
    remit.write_text("you judge the software as an expert would, and you also take the reproducibility remit\n",
                     encoding="utf-8")
    code, out = seats(project, tmp_path / "work", "--seat", "software-methods", "--remit",
                      f"software-methods=@{remit}", "--module", "software-methods=software-and-methods")
    assert code == 0, out
    brief = Path(out["seats"][0]["brief"]).read_text(encoding="utf-8")
    assert ("Your remit: you judge the software as an expert would, and you also take the reproducibility remit. "
            "Your domain questions are in `domain-questions.md`.") in brief
    questions = (Path(out["seats"][0]["workspace"]) / "domain-questions.md").read_text(encoding="utf-8")
    assert "## Load it when" not in questions and "## Running the authors' code" not in questions
    assert "Record in the output why the module was loaded" not in questions
    assert not re.search(r"\]\([^)]+\)", questions)
    assert questions.startswith("# Your domain questions")


@pytest.mark.parametrize("extra, message", [
    (["--seat", "software-methods"], "--remit software-methods=TEXT"),
    (["--seat", "custom:clinician", "--remit", "custom:clinician=a clinician's view"], "--prefix custom:clinician=XY"),
    (["--seat", "skeptic", "--module", "skeptic=astronomy"], "No domain module astronomy"),
    (["--seat", "skeptic", "--module", "champion=genomics"], "--module names champion, which is not a --seat"),
    (["--seat", "skeptic", "--also", "skeptic=astrology"], "--also names astrology"),
])
def test_what_the_script_cannot_decide_is_refused(project: Path, tmp_path: Path, extra: list[str], message: str) -> None:
    code, out = seats(project, tmp_path / "work", *extra)
    assert code == 1 and message in out
    assert not (tmp_path / "work" / "seats").exists()


def test_one_journal_needs_its_article_type(project: Path, tmp_path: Path) -> None:
    args = ["seats", str(tmp_path / "w"), "--paper", str(project / "paper.md"), "--venue", str(project / "venue.md"),
            "--journal", "iScience", "--design", "x", "--seat", "champion"]
    result = runner.invoke(workspaces.app, args)
    assert result.exit_code == 1 and "article type" in result.output


def test_a_custom_seat_with_its_prefix_gets_a_folder_without_a_colon(project: Path, tmp_path: Path) -> None:
    code, out = seats(project, tmp_path / "work", "--seat", "custom:clinician", "--remit",
                      "custom:clinician=you read it as a clinician would", "--prefix", "custom:clinician=CL")
    assert code == 0, out
    assert Path(out["seats"][0]["workspace"]).name == "custom-clinician"
    assert "numbered CL-1, CL-2" in Path(out["seats"][0]["brief"]).read_text(encoding="utf-8")


def test_a_second_build_never_writes_over_the_first(project: Path, tmp_path: Path) -> None:
    work = tmp_path / "work"
    assert seats(project, work, "--seat", "champion")[0] == 0
    (work / "seats" / "champion" / "criteria.md").write_text("C1. kept\n", encoding="utf-8")
    code, out = seats(project, work, "--seat", "champion")
    assert code == 0
    assert Path(out["seats"][0]["workspace"]).name == "champion.2"
    assert Path(out["seats"][0]["brief"]).name == "champion.2.md"
    assert (work / "seats" / "champion" / "criteria.md").read_text(encoding="utf-8") == "C1. kept\n"


def test_the_template_in_seats_md_has_only_placeholders_the_script_fills() -> None:
    for journals in ([("J", "Article")], [("J1", "A"), ("J2", None), ("J3", "C")]):
        brief = workspaces.fill_brief("skeptic", "SK", "a remit", True, Path("/w"), journals, "`x`", ["manuscript.md"])
        assert not re.search(r"<[A-Za-z][^<>\n]*>", brief)


def test_every_seat_in_the_prefix_table_is_known() -> None:
    prefixes = workspaces.seat_prefixes()
    assert prefixes["skeptic"] == "SK" and prefixes["software-methods"] == "SW" and len(prefixes) == 11
    remits = workspaces.seat_remits()
    assert {"claims-novelty", "evidence-statistics", "reproducibility", "champion", "skeptic", "desk-editor",
            "figures"} <= set(remits)
    assert "software-methods" not in remits


# ---------------------------------------------------------------- figures

def test_a_figure_found_twice_keeps_its_first_image_and_names_do_not_collide(tmp_path: Path) -> None:
    for folder in ("a", "b"):
        png(tmp_path / folder / "fig.png")
    (tmp_path / "a" / "paper.md").write_text("![](fig.png)\n\n**Figure 1.** First.\n", encoding="utf-8")
    (tmp_path / "b" / "data.md").write_text("![](fig.png)\n\n**Figure 1.** Again.\n\n![](fig.png)\n\n"
                                            "**Figure S2.** Its own.\n", encoding="utf-8")
    warnings: list[str] = []
    workspaces.render_figures([tmp_path / "a" / "paper.md", tmp_path / "b" / "data.md"], tmp_path / "out", 400,
                              warnings)
    index = (tmp_path / "out" / "index.md").read_text(encoding="utf-8")
    assert "**Figure 1**: `figure-1.png`. **Figure 1.** First." in index and "Again" not in index
    assert "**Figure S2**: `figure-s2.png`" in index
    assert warnings == []


def test_a_figure_whose_file_is_missing_is_named(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text("![](gone.png)\n\n**Figure 1.** Lost.\n", encoding="utf-8")
    warnings: list[str] = []
    workspaces.render_figures([tmp_path / "paper.md"], tmp_path / "out", 400, warnings)
    assert "(no image)" in (tmp_path / "out" / "index.md").read_text(encoding="utf-8")
    assert warnings and "Figure 1 of paper.md has no image" in warnings[0]


# ---------------------------------------------------------------- the defender

MERGED = {
    "findings": [
        {"id": "SK-1", "seat": "skeptic", "location": "Section 1", "quote": "The tool annotates a VCF in minutes",
         "concern": "No timing is reported.", "claim": "Speed", "consequence": "support", "severity": "major",
         "change_my_mind": "A timing table.", "route": "fixable-in-text", "criterion": "C1", "group": "speed",
         "cost": "text", "norm_source": "venue: \"rigour\"",
         "prior_work": [{"citation": "Smith 2020", "identifier": "doi:10.1/x", "status": "verified", "checked_by": "x"}]},
        {"id": "CH-1", "seat": "champion", "location": "Supplement", "quote": "The coverage table is S2_coverage.md",
         "source": "02-supplement.md", "concern": "As the skeptic noted in SK-1, coverage is thin.", "claim": "Coverage",
         "consequence": "scope", "severity": "optional", "change_my_mind": "More scores.", "route": "author-required"},
        {"id": "SW-1", "seat": "software-methods", "location": "Methods", "kind": "absence",
         "looked_in": ["Methods"], "concern": "No version.", "claim": "Reproducibility",
         "consequence": "reproducibility", "severity": "major", "change_my_mind": "A version.", "route": "dropped",
         "drop_reason": "Fairness filter"},
        {"id": "SW-2", "seat": "software-methods", "location": "Methods", "quote": "The tool annotates a VCF",
         "concern": "Which VCF?", "claim": "Input", "consequence": "scope", "severity": "minor",
         "change_my_mind": "Name it.", "route": "fixable-in-text"},
    ],
    "reports": [{"seat": "skeptic", "summary": "x"}],
}


def defender(project: Path, work: Path, findings: Path, *extra: str) -> tuple[int, dict | str]:
    args = ["defender", str(work), "--paper", str(project / "paper.md"), "--supplement",
            str(project / "supplement.md"), "--files", str(project / "supplementary"), "--findings", str(findings),
            *extra]
    result = runner.invoke(workspaces.app, args)
    return result.exit_code, (json.loads(result.stdout) if result.exit_code == 0 else result.output)


def test_the_defender_sees_the_findings_but_not_who_raised_them(project: Path, tmp_path: Path) -> None:
    findings = tmp_path / "findings.merged.json"
    findings.write_text(json.dumps(MERGED), encoding="utf-8")
    work = tmp_path / "work"
    code, out = defender(project, work, findings, "--drop", "SW-2=Fairness filter: optional")
    assert code == 0, out
    packet = json.loads((work / "defender" / "findings-to-answer.json").read_text(encoding="utf-8"))["findings"]
    ids = json.loads((work / "defence-ids.json").read_text(encoding="utf-8"))
    assert sorted(ids["map"].values()) == ["CH-1", "SK-1"]
    assert ids["dropped_before_defence"] == {"SW-2": "Fairness filter: optional", "SW-1": "Fairness filter"}
    assert sorted(f["id"] for f in packet) == ["D1", "D2"]
    for finding in packet:
        assert set(finding) <= {"id", *workspaces.DEFENDER_FIELDS, "prior_work"}
    by_original = {ids["map"][f["id"]]: f for f in packet}
    assert by_original["SK-1"]["prior_work"] == [{"citation": "Smith 2020", "identifier": "doi:10.1/x"}]
    assert by_original["CH-1"]["source"] == "supplementary.md"  # the run's snapshot name, renamed
    assert not (work / "defender" / "venue.md").exists() and not (work / "defender" / "finding-schema.md").exists()
    leak = [w for w in out["warnings"] if "names" in w]
    assert len(leak) == 1 and "SK-1" in leak[0] and "skeptic" in leak[0]


def test_the_order_is_fixed_by_the_file_and_a_second_pass_is_numbered(project: Path, tmp_path: Path) -> None:
    findings = tmp_path / "findings.merged.json"
    findings.write_text(json.dumps(MERGED), encoding="utf-8")
    work = tmp_path / "work"
    assert defender(project, work, findings)[0] == 0
    code, out = defender(project, work, findings)
    assert code == 0 and Path(out["workspace"]).name == "defender.2"
    first = json.loads((work / "defence-ids.json").read_text(encoding="utf-8"))
    second = json.loads((work / "defence-ids.2.json").read_text(encoding="utf-8"))
    assert first["seed"] == second["seed"] and first["map"] == second["map"]


def test_an_unknown_drop_is_refused(project: Path, tmp_path: Path) -> None:
    findings = tmp_path / "findings.merged.json"
    findings.write_text(json.dumps(MERGED), encoding="utf-8")
    code, out = defender(project, tmp_path / "work", findings, "--drop", "XX-9=why")
    assert code == 1 and "XX-9" in out


# ---------------------------------------------------------------- the script itself

def dependencies(path: Path) -> set[str]:
    header = re.search(r"# dependencies = \[(.*?)\]", path.read_text(encoding="utf-8"))
    return {re.split(r"[<>=]", d.strip().strip('"'))[0] for d in header.group(1).split(",")} if header else set()


def test_it_declares_what_figures_py_needs() -> None:
    figures_py = ROOT / "skills" / "manuscript-figures" / "scripts" / "figures.py"
    assert dependencies(figures_py) <= dependencies(SCRIPT)


def test_a_seat_on_another_model_gets_its_own_folder_and_brief(project: Path, tmp_path: Path) -> None:
    work = tmp_path / "work"
    assert seats(project, work, "--seat", "skeptic")[0] == 0
    code, out = seats(project, work, "--seat", "skeptic", "--suffix", "@codex")
    assert code == 0, out
    assert Path(out["seats"][0]["workspace"]).name == "skeptic@codex"
    brief = Path(out["seats"][0]["brief"])
    assert brief.name == "skeptic@codex.md"
    assert brief.read_text(encoding="utf-8").startswith("You are the **skeptic** on")
