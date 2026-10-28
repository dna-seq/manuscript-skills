"""The rules that decide whether a venue takes the paper at all: a journal's validation requirements and a preprint
server's screening rules. A list that was read is the venue's complete rules, so `[]` and a design none of them
covers fit; a list nobody read is "Could not be checked" and the ladder, `stale` and `common` all say it must be
read. A server may send the paper to another that sends it back. Run with `uv run pytest`."""

from __future__ import annotations

import csv
import importlib.util
import io
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "manuscript-journal-adapt" / "scripts"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


venues = _load("venues_rules", SCRIPTS / "venues.py")

# Open: its pages state no validation requirement. Cohort: a rule for public-data findings only. Unread: nobody
# read its rules. Bio sends health-related papers to Med; Med sends software papers back to Bio; Wide states none.
CATALOGUE = {
    "checked": date(2026, 10, 28),
    "venues": {
        "open": {"name": "Open Journal", "url": "https://open.example/guidelines", "writing_help": "disclose",
                 "validation_requirements": [],
                 "provenance": {"validation_requirements": {"source": "https://open.example/types",
                                                            "checked": date(2026, 10, 28)}}},
        "cohort": {"name": "Cohort Journal", "url": "https://cohort.example/guidelines", "writing_help": "disclose",
                   "validation_requirements": [{"applies_to": ["public-data"], "strength": "required",
                                                "accepted_any": ["independent-cohort"],
                                                "description": "Findings from public data need an independent "
                                                               "cohort"}]},
        "methods": {"name": "Methods Journal", "url": "https://methods.example/guidelines",
                    "writing_help": "disclose",
                    "validation_requirements": [{"id": "comparison", "applies_to": ["software"], "strength": "required",
                                                 "accepted_any": ["benchmark"],
                                                 "description": "A method is compared with related methods"}]},
        "unread": {"name": "Unread Journal", "url": "https://unread.example/guidelines", "writing_help": "disclose"},
        "bio": {"kind": "preprint", "name": "Bio Server", "url": "https://bio.example/faq", "writing_help": "disclose",
                "screening_rules": [{"applies_to": ["health", "clinical"], "outcome": "redirected",
                                     "redirect_to": "med", "strength": "conditional",
                                     "description": "Papers with health-related information go to Med Server"}]},
        "med": {"kind": "preprint", "name": "Med Server", "url": "https://med.example/faq", "writing_help": "disclose",
                "screening_rules": [{"applies_to": ["software", "bioinformatics"], "outcome": "redirected",
                                     "redirect_to": "bio", "strength": "conditional",
                                     "description": "Tools without clinical data belong on Bio Server"}]},
        "wide": {"kind": "preprint", "name": "Wide Server", "url": "https://wide.example/help",
                 "writing_help": "disclose", "screening_rules": []},
        "blank": {"kind": "preprint", "name": "Blank Server", "url": "https://blank.example/help",
                  "writing_help": "disclose"},
    },
}


@pytest.fixture()
def catalogue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "venues.yaml"
    p.write_text(yaml.safe_dump(CATALOGUE), encoding="utf-8")
    monkeypatch.setattr(venues, "VENUES_YAML", p)
    monkeypatch.setattr(venues, "SNAPSHOT_INDEX", tmp_path / "index.yaml")
    return p


def _run(*args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(venues.app, list(args))
    return result.exit_code, result.stdout, result.stderr if result.stderr_bytes is not None else ""


def _rows(stdout: str) -> dict[str, dict[str, str]]:
    return {r["key"]: r for r in csv.DictReader(io.StringIO(stdout))}


def _resolved(catalogue: Path) -> dict[str, dict]:
    return venues.load_venues()[1]


# ---------------------------------------------------------------------------------------- journals

@pytest.mark.parametrize("key,design,available,status", [
    ("open", "software", None, "go"),  # read, none stated
    ("open", None, None, "go"),
    ("cohort", "software", None, "go"),  # read; its one rule covers another design
    ("cohort", "public-data", {"none"}, "no-go"),
    ("methods", "software", None, "conditional"),  # a comparison is asked for; not known whether there is one
    ("methods", "software", {"benchmark"}, "go"),
    ("methods", "software", {"none"}, "no-go"),
    ("unread", "software", None, "unknown"),
])
def test_a_read_rule_list_is_the_journals_whole_rules(catalogue: Path, key: str, design: str | None,
                                                      available: set[str] | None, status: str) -> None:
    assert venues.validation_fit(_resolved(catalogue)[key], design, available)[0] == status


def test_a_fit_names_the_page_it_was_read_on_and_what_the_rules_cover(catalogue: Path) -> None:
    v = _resolved(catalogue)
    _, reason = venues.validation_fit(v["open"], "software")
    assert "https://open.example/types" in reason and "2026-10-28" in reason
    _, reason = venues.validation_fit(v["cohort"], "software")
    assert "public-data reanalysis paper" in reason
    assert venues.validation_fit(v["unread"], "software")[1] == "Its validation requirements have not been researched."


def test_the_ladder_says_it_is_not_finished_while_a_rule_was_never_read(catalogue: Path) -> None:
    only = ["--only", "open", "--only", "unread", "--priority", "reach", "--study-design", "software"]
    code, out, _ = _run("ladder", *only)
    assert code == 0
    assert "Not finished: the validation requirements of Unread Journal have never been read" in out
    assert "`venues.py stale unread`" in out
    code, out, err = _run("ladder", *only, "--format", "csv")
    rows = _rows(out)
    assert rows["open"]["fits"] == "Fits" and rows["unread"]["fits"] == "Could not be checked"
    assert list(rows) == ["open", "unread"]  # a read fit sorts above one nobody read
    assert "Not finished" in err and "Not finished" not in out  # the CSV stays clean


def test_stale_and_common_list_the_rules_nobody_read(catalogue: Path) -> None:
    code, out, _ = _run("stale", "unread", "open", "blank", "--format", "csv")
    rows = list(csv.DictReader(io.StringIO(out)))
    assert code == 0
    assert {(r["key"], r["field"]) for r in rows} == {("unread", "validation_requirements"),
                                                     ("blank", "screening_rules")}
    assert {r["source"] for r in rows} == {"https://unread.example/guidelines", "https://blank.example/help"}
    code, out, _ = _run("stale", "unread")
    assert "never read" in out and "https://unread.example/guidelines" in out
    code, out, _ = _run("common", "open", "unread", "blank")
    gaps = out.split("## Not researched yet", 1)[1]
    assert "its validation requirements" in gaps and "its screening rules" in gaps
    assert "Open Journal" not in gaps.split("its validation requirements")[0].rsplit("\n", 1)[-1]


# ---------------------------------------------------------------------------------------- preprint servers

def test_a_server_that_sends_the_paper_to_one_that_sends_it_back_is_named_on_both_rungs(catalogue: Path) -> None:
    # A software paper that reports health information: Bio may send it to Med, which may send it back.
    args = ["ladder", "--preprints", "--only", "bio", "--only", "med", "--only", "wide", "--priority", "ai",
            "--study-design", "software", "--study-design", "health", "--format", "csv"]
    code, out, _ = _run(*args)
    rows = _rows(out)
    assert code == 0
    assert rows["wide"]["fits"] == "Fits" and list(rows)[0] == "wide"
    for key, other in (("bio", "Med Server"), ("med", "Bio Server")):
        assert rows[key]["fits"] == "Depends"
        assert f"{other} may in turn send it back" in rows[key]["fits_reason"]
        assert rows[key]["fits_reason"].endswith("Wide Server has no screening rule against it.")  # the way out
    assert "It may send a health-related paper to Med Server" in rows["bio"]["fits_reason"]
    # Health information is a fact about the paper, not another reading of it: no "depends on which kind of paper".
    assert all("which kind of paper" not in rows[k]["fits_reason"] for k in rows)
    assert "It may send a software or resource paper to Bio Server" in rows["med"]["fits_reason"]
    # A plain software paper: Bio has nothing against it, so nothing bounces.
    code, out, _ = _run(*args[:-4], "--format", "csv")
    rows = _rows(out)
    assert rows["bio"]["fits"] == "Fits" and "in turn" not in rows["med"]["fits_reason"]


def test_the_record_adds_what_the_paper_reports_to_its_designs(catalogue: Path, tmp_path: Path) -> None:
    record = tmp_path / "manuscript-record.yaml"
    record.write_text(yaml.safe_dump({"study": {"designs": ["software-tool"], "health_information": True,
                                                "human_data": "author-self-released"}}), encoding="utf-8")
    context = venues.record_context(record)
    assert context["designs"] == ["software", "health", "human-data"] and context["confirmed"] is False
    code, out, _ = _run("ladder", "--preprints", "--only", "bio", "--only", "med", "--priority", "ai",
                        "--record", str(record), "--format", "csv")
    rows = _rows(out)
    assert code == 0 and rows["bio"]["fits"] == "Depends" and "in turn" in rows["bio"]["fits_reason"]
    record.write_text(yaml.safe_dump({"study": {"designs": ["software-tool"], "human_data": "none"}}),
                      encoding="utf-8")
    assert venues.record_context(record)["designs"] == ["software"]


def test_a_required_refusal_does_not_fit_only_once_the_design_is_confirmed(catalogue: Path, tmp_path: Path) -> None:
    v = {**_resolved(catalogue)["med"]}
    v["screening_rules"] = [{**v["screening_rules"][0], "strength": "required"}]
    assert venues.validation_fit(v, "software")[0] == "no-go"
    assert venues.feasibility(v, ["software"], None, confirmed=False)[0] == "conditional"
    assert venues.validation_fit(v, "health")[0] == "go"


# ---------------------------------------------------------------------------------------- the manuscript's own verdict

@pytest.mark.parametrize("met,confirmed,status,words", [
    (True, False, "Fits", "The manuscript meets it: Section 4 compares it with PLINK2."),
    ("partly", False, "Depends", "The manuscript meets part of it: Section 4 compares it with PLINK2."),
    (False, False, "Depends", "The manuscript does not meet it: Section 4 compares it with PLINK2."),
    (False, True, "Does not fit the stated constraints", "The manuscript does not meet it"),
])
def test_a_condition_checked_against_the_manuscript_settles_the_verdict(catalogue: Path, tmp_path: Path, met: object,
                                                                         confirmed: bool, status: str, words: str) -> None:
    study = {"designs": ["software-tool"], **({"confirmed": True} if confirmed else {})}
    record = tmp_path / "manuscript-record.yaml"
    record.write_text(yaml.safe_dump({"study": study, "conditions": {"methods": {"comparison": {
        "met": met, "evidence": "Section 4 compares it with PLINK2", "checked": "2026-10-28"}}}}), encoding="utf-8")
    code, out, err = _run("ladder", "--only", "methods", "--only", "open", "--priority", "reach", "--record", str(record),
                          "--format", "csv")
    row = _rows(out)["methods"]
    assert code == 0 and row["fits"] == status and words in row["fits_reason"]
    assert "Not checked against the manuscript" not in err  # it was checked


def test_the_ladder_names_the_conditions_nobody_checked_against_the_manuscript(catalogue: Path) -> None:
    code, out, _ = _run("ladder", "--only", "methods", "--only", "open", "--priority", "reach",
                        "--study-design", "software")
    assert code == 0 and "Not checked against the manuscript: Methods Journal (`comparison`)" in out
    # A server's redirect is its screeners' call, which no reading of the manuscript settles: never listed.
    code, out, _ = _run("ladder", "--preprints", "--only", "bio", "--only", "med", "--priority", "ai",
                        "--study-design", "software", "--study-design", "health")
    assert "Not checked against the manuscript" not in out


def test_a_condition_must_say_met_true_false_or_partly(catalogue: Path, tmp_path: Path) -> None:
    record = tmp_path / "manuscript-record.yaml"
    record.write_text(yaml.safe_dump({"conditions": {"methods": {"comparison": {"met": "yes"}}}}), encoding="utf-8")
    assert _run("ladder", "--only", "methods", "--only", "open", "--record", str(record))[0] != 0


def test_a_length_the_guidelines_do_not_set_is_known_not_a_gap(catalogue: Path, tmp_path: Path) -> None:
    read = yaml.safe_load(catalogue.read_text(encoding="utf-8"))
    read["venues"]["open"]["limits"] = {"abstract_words": 200, "none_stated": ["body_words"]}
    read["venues"]["methods"]["limits"] = {"abstract_words": 150, "body_words": 7000}
    catalogue.write_text(yaml.safe_dump(read), encoding="utf-8")
    code, out, _ = _run("common", "open", "methods")
    assert code == 0
    gaps = out.split("## Not researched yet", 1)[1] if "## Not researched yet" in out else ""
    assert "the length of the body" not in gaps.split("Open Journal", 1)[-1].split("\n", 1)[0]
    assert "Methods Journal, 7000; Open Journal sets none)" in out  # the one limit fits both
