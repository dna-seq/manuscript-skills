"""Journal selection and adaptation, 0.19: the ladder never stops for the authors' priorities, reads the paper's facts
from the record, keeps the authors' own shortlist whole and speaks plain words; `common` adapts nothing before the
choice that only one venue asks for. Run with `uv run pytest`."""

from __future__ import annotations

import csv
import importlib.util
import io
import re
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


venues = _load("venues_0_19", SCRIPTS / "venues.py")
watch = _load("policy_watch_0_19", SCRIPTS / "policy_watch.py")

# Calm: light policy, a EUR fee and a validation rule for public-data findings. Strict: a drafting ban and a USD
# fee. Keeper: requires AI records and lists the same deposit again as extra work. Low: a low impact factor.
CATALOGUE = {
    "checked": date(2026, 10, 15),
    "venues": {
        "calm": {"name": "Calm Journal", "url": "https://calm.example/guidelines", "fields": ["bioinformatics"],
                 "writing_help": "disclose", "prompts": "no", "screening": "plagiarism", "jif": 6.0,
                 "disclosure_places": ["Methods"],
                 "limits": {"body_words": 4000, "abstract_words": 250},
                 "publication_costs": [{"amount": 2000, "currency": "EUR"}],
                 "validation_requirements": [{"applies_to": ["public-data"], "strength": "required",
                                              "accepted_any": ["independent-cohort"],
                                              "description": "Independent validation required"}]},
        "strict": {"name": "Strict Journal", "url": "https://strict.example/guidelines", "fields": ["bioinformatics"],
                   "writing_help": "banned_drafting", "prompts": "no", "screening": "plagiarism", "jif": 8.0,
                   "publication_costs": [{"amount": 3000, "currency": "USD"}]},
        "keeper": {"name": "Keeper Journal", "url": "https://keeper.example/guidelines", "fields": ["bioinformatics"],
                   "writing_help": "disclose", "prompts": "no", "tracking": "required", "screening": "plagiarism",
                   "jif": 5.0, "extra_burden": ["AI outputs deposited in an open repository",
                                               "AI tool cited as a reference"]},
        "low": {"name": "Low Journal", "url": "https://low.example/guidelines", "fields": ["bioinformatics"],
                "writing_help": "disclose", "prompts": "no", "screening": "plagiarism", "jif": 1.5},
        "server": {"kind": "preprint", "name": "A Server", "writing_help": "disclose", "transfers": ["strict"]},
        "quiet": {"kind": "preprint", "name": "Quiet Server", "writing_help": "disclose", "transfers": [],
                  "transfers_checked": ["strict", "calm"]},
    },
}


@pytest.fixture()
def catalogue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "venues.yaml"
    p.write_text(yaml.safe_dump(CATALOGUE), encoding="utf-8")
    monkeypatch.setattr(venues, "VENUES_YAML", p)
    monkeypatch.setattr(venues, "SNAPSHOT_INDEX", tmp_path / "index.yaml")
    return p


def _record(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "manuscript-record.yaml"
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def _run(*args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(venues.app, list(args))
    stderr = result.stderr if result.stderr_bytes is not None else ""
    return result.exit_code, result.stdout, stderr


def _rows(stdout: str) -> dict[str, dict[str, str]]:
    return {r["key"]: r for r in csv.DictReader(io.StringIO(stdout))}


def _order(stdout: str) -> list[str]:
    return re.findall(r"^\| \d+ \| .*?\(`([a-z-]+)`\)", stdout, flags=re.M)


ONLY = ["--only", "calm", "--only", "strict", "--only", "keeper"]


# ---------------------------------------------------------------------------------------- default priorities

def test_without_priorities_the_ladder_uses_a_labelled_default_and_never_saves_it(catalogue: Path,
                                                                                  tmp_path: Path) -> None:
    record = _record(tmp_path, {"venue_facts": {}})
    before = record.read_text(encoding="utf-8")
    code, out, _ = _run("ladder", *ONLY, "--record", str(record))
    assert code == 0, out
    first_paragraph = out.split("\n\n")[1]
    assert first_paragraph.startswith("**A default order, not yours yet.**")
    assert "speed to a first decision, then reach" in first_paragraph and "a low cost to the authors" in out
    assert "Your budget is not known yet" in out
    assert record.read_text(encoding="utf-8") == before  # the default is never written to the record
    code, out, err = _run("ladder", *ONLY, "--record", str(record), "--format", "csv")
    assert code == 0
    rows = _rows(out)
    assert {r["priorities_source"] for r in rows.values()} == {"default"}
    assert {r["priorities"] for r in rows.values()} == {"speed;reach;ai;cost"}
    assert "default order" in err


def test_stated_priorities_are_not_labelled_as_a_default(catalogue: Path, tmp_path: Path) -> None:
    record = _record(tmp_path, {"priorities": {"journals": ["reach"]}})
    code, out, _ = _run("ladder", *ONLY, "--record", str(record))
    assert code == 0 and "default order" not in out.lower()
    # Calm's validation rule is a condition to check, Strict's and Keeper's rules were never read: feasibility
    # first, then reach.
    assert _order(out) == ["calm", "strict", "keeper"]
    code, out, _ = _run("ladder", *ONLY, "--record", str(record), "--format", "csv")
    assert {r["priorities_source"] for r in _rows(out).values()} == {"authors"}


def test_the_preprint_default_starts_with_transfer_only_when_a_journal_ladder_is_given(catalogue: Path) -> None:
    code, out, _ = _run("ladder", "--preprints", "--format", "csv")
    assert code == 0 and {r["priorities"] for r in _rows(out).values()} == {"speed;ai"}
    code, out, _ = _run("ladder", "--preprints", "--journal", "strict", "--format", "csv")
    assert code == 0 and {r["priorities"] for r in _rows(out).values()} == {"transfer;speed;ai"}
    assert list(_rows(out)) == ["server", "quiet"]  # the server that transfers to the first journal leads


# ---------------------------------------------------------------------------------------- facts from the record

def test_an_unconfirmed_design_never_makes_a_journal_not_fit(catalogue: Path, tmp_path: Path) -> None:
    record = _record(tmp_path, {"priorities": {"journals": ["reach"], "validation_available": ["none"]},
                                "study": {"designs": ["public-data-reanalysis"]}})
    code, out, _ = _run("ladder", *ONLY, "--record", str(record), "--format", "csv")
    calm = _rows(out)["calm"]
    assert calm["validation_fits"] == "Depends" and "not confirmed" in calm["validation_reason"]
    assert calm["study_designs"] == "public-data"
    code, out, _ = _run("ladder", *ONLY, "--record", str(record))
    table = [line for line in out.splitlines() if line.startswith("| ") and "(`" in line]
    assert not [line for line in table if "Does not fit" in line] and "which the authors have not confirmed yet" in out
    # Confirmed by the authors, or stated on the command line: the rule rules the journal out, and it goes last.
    data = yaml.safe_load(record.read_text(encoding="utf-8"))
    data["study"]["confirmed"] = "2026-10-24"
    record.write_text(yaml.safe_dump(data), encoding="utf-8")
    code, out, _ = _run("ladder", *ONLY, "--record", str(record), "--format", "csv")
    rows = _rows(out)
    assert rows["calm"]["validation_fits"] == "Does not fit the stated constraints" and list(rows)[-1] == "calm"
    record.write_text(yaml.safe_dump({"priorities": {"journals": ["reach"]}}), encoding="utf-8")
    code, out, _ = _run("ladder", *ONLY, "--record", str(record), "--study-design", "public-data",
                        "--validation-available", "none", "--format", "csv")
    assert _rows(out)["calm"]["validation_fits"] == "Does not fit the stated constraints"


def test_a_mixed_study_that_one_design_rules_out_depends_on_how_the_editors_read_it() -> None:
    calm = CATALOGUE["venues"]["calm"]
    status, reason = venues.feasibility(calm, ["software", "public-data"], {"none"}, confirmed=True)
    assert status == "conditional" and "As a public-data reanalysis paper" in reason
    assert venues.feasibility(calm, ["public-data"], {"none"}, confirmed=True)[0] == "no-go"
    assert venues.feasibility(calm, ["public-data"], {"none"}, confirmed=False)[0] == "conditional"


def test_the_record_supplies_the_floor_the_ai_use_and_the_budget(catalogue: Path, tmp_path: Path) -> None:
    record = _record(tmp_path, {"priorities": {"journals": ["reach"], "jif_floor": 3, "budget_eur": 2500},
                                "ai_use": "drafting"})
    code, out, err = _run("ladder", *ONLY, "--only", "low", "--record", str(record), "--format", "csv")
    rows = _rows(out)
    assert "low" not in rows and "Low Journal (its impact factor, 1.5, is below the floor of 3)" in err
    # Drafting at a journal that bans it: the authors' decision, never "Does not fit".
    assert "your decision" in rows["strict"]["fits_reason"] and rows["strict"]["ai_use"] == "drafting"
    assert rows["strict"]["fits"] != "Does not fit the stated constraints"
    status, reason = venues.overall_fit(CATALOGUE["venues"]["strict"], ("go", "It accepts what you have."),
                                        venues.AiUse.drafting, None)
    assert status == "conditional" and "asks authors not to have AI draft text" in reason
    assert "budget" not in rows["calm"]["fits_reason"]  # 2000 EUR is within the budget of 2500 EUR
    code, out, _ = _run("ladder", *ONLY, "--record", str(record), "--budget-eur", "1000", "--format", "csv")
    assert _rows(out)["calm"]["fits"] == "Depends" and "above your budget" in _rows(out)["calm"]["fits_reason"]


def test_an_unknown_budget_leaves_a_fee_the_authors_would_pay_as_depends(catalogue: Path) -> None:
    code, out, _ = _run("ladder", *ONLY, "--priority", "cost", "--format", "csv")
    calm = _rows(out)["calm"]
    assert calm["fits"] == "Depends" and "your budget has not been stated yet" in calm["fits_reason"]


def test_the_ai_use_is_unknown_until_established_and_assumes_no_conflict(catalogue: Path) -> None:
    code, out, _ = _run("ladder", *ONLY, "--priority", "reach", "--format", "csv")
    strict = _rows(out)["strict"]
    assert strict["ai_use"] == "unknown" and strict["ai_for_this_use"].startswith("Depends on what AI did")
    assert "conflict" not in strict["fits_reason"]
    code, out, _ = _run("rank")
    assert code == 0 and "has not been established" in out and '(AI use "unknown")' in out
    assert venues.ai_conflict(CATALOGUE["venues"]["strict"], venues.AiUse.unknown) is None
    assert venues.ai_conflict(CATALOGUE["venues"]["strict"], venues.AiUse.drafting)


# ---------------------------------------------------------------------------------------- the authors' shortlist

def test_a_record_keeping_venue_on_the_shortlist_is_never_left_out_by_default(catalogue: Path) -> None:
    code, out, err = _run("ladder", *ONLY, "--priority", "ai", "--format", "csv")
    assert "keeper" in _rows(out) and not err.strip().startswith("Left out")
    code, out, _ = _run("ladder", *ONLY, "--priority", "ai")
    assert "(`keeper`)" in out and "Left out" not in out
    code, out, _ = _run("rank")
    assert "(`keeper`)" in out


def test_a_refused_burden_names_what_it_left_out_in_both_formats(catalogue: Path) -> None:
    code, out, _ = _run("ladder", *ONLY, "--priority", "ai", "--refuse", "tracking")
    assert "(`keeper`)" not in out
    assert "Left out of the venues you listed: Keeper Journal (it asks for records of AI use beyond one " \
           "acknowledgement, which you ruled out)." in out
    code, out, err = _run("ladder", *ONLY, "--priority", "ai", "--refuse", "tracking", "--format", "csv")
    assert "keeper" not in _rows(out) and "Keeper Journal" in err


# ---------------------------------------------------------------------------------------- data

def test_record_keeping_is_counted_once() -> None:
    keeper = CATALOGUE["venues"]["keeper"]
    score, reasons = venues.friction(keeper)
    # disclose 1 + records required 3 + one extra burden (the citation) 1; the deposit is the same record keeping.
    assert score == 5
    assert any("counted once" in r and "deposited" in r for r in reasons)
    alone = {**keeper, "tracking": None}
    assert venues.friction(alone)[0] == 1 + 2  # without the record-keeping points, both burdens count


def test_partial_facts_merge_into_the_catalogue_key_by_key(catalogue: Path) -> None:
    _, resolved = venues.load_venues()
    merged = venues.with_facts(resolved, {"calm": {"limits": {"abstract_words": 200},
                                                   "open_science": {"preprints": "allowed"}}})
    assert merged["calm"]["limits"] == {"body_words": 4000, "abstract_words": 200}
    assert merged["calm"]["open_science"] == {"preprints": "allowed"}
    assert merged["calm"]["from_facts"] == ["limits", "open_science"]
    replaced = venues.with_facts(resolved, {"calm": {"disclosure_places": ["Cover letter"]}})
    assert replaced["calm"]["disclosure_places"] == ["Cover letter"]  # a list replaces the catalogue's list


@pytest.mark.parametrize("transfers, checked, ladder, cell", [
    (None, None, ["strict"], ""),  # no list: not known
    ([], ["strict", "calm"], ["strict", "calm"], "none"),  # read for both, names neither
    (["calm"], None, ["strict"], ""),  # read only for Calm: Strict is not known
    (["strict", "calm"], None, ["strict"], "strict"),
    ([], None, None, "none"),
])
def test_the_transfers_cell_tells_none_from_not_known(transfers, checked, ladder, cell) -> None:
    assert venues._transfers_cell(transfers, checked, ladder) == cell


def test_the_preprint_csv_writes_none_for_a_read_list_that_reaches_no_ladder_journal(catalogue: Path) -> None:
    code, out, _ = _run("ladder", "--preprints", "--journal", "strict", "--journal", "calm", "--priority", "ai",
                        "--format", "csv")
    rows = _rows(out)
    assert rows["quiet"]["transfers"] == "none" and rows["server"]["transfers"] == "strict"


# ---------------------------------------------------------------------------------------- common

def _common(tmp_path: Path, facts: dict, *args: str) -> str:
    record = _record(tmp_path, {"venue_facts": facts})
    code, out, _ = _run("common", *args, "--record", str(record))
    assert code == 0, out
    return out


def _section(text: str, heading: str) -> str:
    return text.split(f"## {heading}")[1].split("\n## ")[0]


def test_one_venues_abstract_headings_wait_when_the_others_are_unknown(catalogue: Path, tmp_path: Path) -> None:
    one = _common(tmp_path, {"calm": {"abstract_headings": ["Motivation", "Results"]}}, "calm", "strict")
    assert "Motivation" not in _section(one, "Adapt now")
    assert "recorded only for Calm Journal" in _section(one, "Choose per venue")
    both = _common(tmp_path, {"calm": {"abstract_headings": ["Motivation", "Results"]},
                              "strict": {"abstract_headings": ["motivation", "Results."]}}, "calm", "strict")
    assert "Abstract: Motivation, Results (every venue)" in _section(both, "Adapt now")


def test_a_rule_free_for_the_others_is_adapted_now_and_a_format_waits(catalogue: Path, tmp_path: Path) -> None:
    rules = [{"when": "submission", "rule": "alt text under every figure", "quote": "q", "free_for_others": True},
             {"when": "submission", "rule": "sections in this order: Introduction, Methods", "quote": "q"}]
    out = _common(tmp_path, {"calm": {"submission_rules": rules}}, "calm", "strict")
    assert "Alt text under every figure (Calm Journal)" in _section(out, "Adapt now")
    assert "Sections in this order" in _section(out, "Choose per venue")
    assert "Sections in this order" not in _section(out, "Adapt now")


def test_the_strictest_ai_rule_is_stated_with_its_meaning_and_no_rewrite(catalogue: Path, tmp_path: Path) -> None:
    out = _common(tmp_path, {}, "calm", "strict", "--ai-use", "drafting")
    rules = _section(out, "AI writing rules on the list")
    assert "The strictest rule on the list is Strict Journal's" in rules and "a conflict for you to weigh" in rules
    assert "keeps every venue on the list open" not in out and "rewrit" not in rules.lower()
    # Two rules of the same cost are both named.
    tie = {"calm": {"writing_help": "red_line"}, "strict": {"writing_help": "disclose_all"}}
    rules = _section(_common(tmp_path, tie, "calm", "strict"), "AI writing rules on the list")
    assert "Two rules are equally strict" in rules and "Calm Journal's" in rules and "Strict Journal's" in rules
    assert "has not been established" in rules


def test_the_gaps_give_the_reason_a_page_could_not_be_read_and_no_homework(catalogue: Path, tmp_path: Path) -> None:
    out = _common(tmp_path, {"strict": {"not_read": "the guidelines page answered HTTP 403, 2026-10-24"}},
                  "calm", "strict")
    gaps = _section(out, "Not researched yet")
    assert "Strict Journal (https://strict.example/guidelines):" in gaps
    assert "The page could not be read: the guidelines page answered HTTP 403, 2026-10-24." in gaps
    assert "venue_facts" not in out and "Read these" not in out


# ---------------------------------------------------------------------------------------- plain words

BANNED = ("GO", "NO-GO", "CONDITIONAL", "UNKNOWN", "no-go", "Rung", "rung", "⚑", "points", "venue_facts")


def test_what_the_authors_read_has_no_codes_rungs_icons_or_points(catalogue: Path, tmp_path: Path) -> None:
    record = _record(tmp_path, {"study": {"designs": ["public-data-reanalysis"]},
                                "priorities": {"validation_available": ["none"]}})
    code, ladder, _ = _run("ladder", *ONLY, "--record", str(record))
    assert code == 0 and "| Position |" in ladder
    common = _common(tmp_path, {}, "calm", "strict", "keeper")
    for text in (ladder, common):
        found = [t for t in BANNED if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", text)]
        assert not found, found
    assert "follow the ladder's first choice" in common


def test_the_stale_policy_warning_never_tells_an_author_task_to_write_the_plugin(catalogue: Path) -> None:
    code, _, err = _run("rank")
    assert code == 0 and "--update" not in err


# ---------------------------------------------------------------------------------------- policy_watch

def test_record_compares_without_writing_the_plugins_snapshots_unless_asked(tmp_path: Path,
                                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watch, "SNAPSHOTS", tmp_path / "snapshots")
    monkeypatch.setattr(watch, "INDEX", tmp_path / "snapshots" / "index.yaml")
    url = "https://example.org/policy"
    monkeypatch.setattr(watch, "watched_urls", lambda only=None: {url: ["x"]})
    monkeypatch.setattr(watch, "venue_names", lambda: {"x": "X"})
    page = tmp_path / "saved.html"
    page.write_text("<html><body><h2>Use of generative AI</h2><p>Authors must disclose the use of large language "
                    "models in the Methods.</p><p>" + "Reviewers assess novelty and rigour. " * 20 + "</p></body></html>",
                    encoding="utf-8")
    result = CliRunner().invoke(watch.app, ["record", url, str(page)])
    assert result.exit_code == 0, result.output
    assert not watch.INDEX.exists()
    result = CliRunner().invoke(watch.app, ["record", url, str(page), "--update"])
    assert result.exit_code == 0 and watch.INDEX.exists()


def test_an_archived_read_is_reported_as_not_the_current_rule() -> None:
    o = watch.Outcome("https://example.org/policy", watch.Result.unchanged, "wayback:20240617115300", blocks=2)
    assert any("not the current rule" in line for line in watch.render(o, {}))
    live = watch.Outcome("https://example.org/policy", watch.Result.unchanged, "httpx", blocks=2)
    assert not any("archived" in line for line in watch.render(live, {}))


def test_chrome_is_found_outside_the_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(watch.sys, "platform", "darwin")
    assert Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") in watch._chrome_paths()
    installed = tmp_path / "chrome.exe"
    installed.write_bytes(b"")
    monkeypatch.setattr(watch.shutil, "which", lambda name: None)
    monkeypatch.setattr(watch, "_chrome_paths", lambda: [tmp_path / "missing", installed])
    assert watch._chrome() == str(installed)


def test_body_sections_are_one_structure_per_venue_and_wait_when_they_differ(catalogue: Path, tmp_path: Path) -> None:
    """Background or Introduction names the same part of the paper, so venues that name or order the body's sections
    differently disagree; keywords or declarations are additions one version carries for every venue."""
    out = _common(tmp_path, {
        "calm": {"required_sections": ["Keywords (3 to 10)", "Background", "Implementation", "Results", "Conclusions",
                                       "Availability and Implementation (in the abstract)"]},
        "strict": {"required_sections": ["Introduction", "Design and Implementation", "Results",
                                         "Availability and requirements"]}}, "calm", "strict")
    now, differ = _section(out, "Adapt now"), _section(out, "Choose per venue")
    assert "Keywords (3 to 10) (Calm Journal)" in now and "Availability and requirements (Strict Journal)" in now
    for heading in ("Background", "Introduction", "Design and Implementation", "Results", "in the abstract"):
        assert heading not in now
    assert ("Body sections differ, and a heading names one part of the paper, so one version follows one venue's "
            "structure: Calm Journal: Background, Implementation, Results, Conclusions; Strict Journal: Introduction, "
            "Design and Implementation, Results.") in differ
    assert "Availability and Implementation (in the abstract), asked by Calm Journal only" in differ


def test_the_same_body_structure_at_every_venue_is_adapted_now(catalogue: Path, tmp_path: Path) -> None:
    same = ["Introduction", "Methods", "Results", "Discussion"]
    out = _common(tmp_path, {"calm": {"required_sections": same},
                             "strict": {"required_sections": [s.lower() for s in same]}}, "calm", "strict")
    assert "Body sections: Introduction, Methods, Results, Discussion (every venue)." in _section(out, "Adapt now")
    one = _common(tmp_path, {"calm": {"required_sections": same}}, "calm", "strict")
    assert "Body sections" not in _section(one, "Adapt now")
    assert "set by Calm Journal; Strict Journal set none or are not researched for it" in _section(one, "Choose per venue")


def test_which_required_sections_are_the_body() -> None:
    body = ["Methods (after Conclusions)", "Introduction, Results and Discussion (a complete research article)",
            "Complete methods and results sections (only research articles)", "Discussion (if appropriate)",
            "Availability and Future Directions", "Background"]
    extra = ["Keywords (3 to 10)", "Availability and requirements", "Data availability", "List of abbreviations",
             "Author summary (150 to 200 words)", "Declarations (Competing interests, Funding)"]
    assert all(venues._body_section(s) for s in body) and not any(venues._body_section(s) for s in extra)


# ---------------------------------------------------------------------------------------- AI use and the preprint server

def test_a_writing_rule_that_forbids_what_ai_did_counts_as_severe_and_sorts_below() -> None:
    redline = {"name": "Red Line Journal", "writing_help": "red_line", "prompts": "no", "screening": "plagiarism"}
    assert venues.friction(redline)[0] == venues.friction(redline, venues.AiUse.revision)[0] == 2
    score, reasons = venues.friction(redline, venues.AiUse.drafting)
    assert score == 2 + venues.CONFLICT_POINTS and venues.tier(score) == "severe"
    assert any("forbids what AI did to this text (AI wrote new sentences or sections)" in r for r in reasons)
    strict = CATALOGUE["venues"]["strict"]
    assert venues.friction(strict, venues.AiUse.polish)[0] == 5  # language correction is allowed under a drafting ban
    assert venues.friction(strict, venues.AiUse.revision)[0] == 5 + venues.CONFLICT_POINTS


@pytest.mark.parametrize("use, order", [("unknown", ["calm", "strict", "keeper"]),
                                        ("drafting", ["calm", "keeper", "strict"])])
def test_the_ai_step_weighs_the_established_ai_use(catalogue: Path, use: str, order: list[str]) -> None:
    code, out, _ = _run("ladder", *ONLY, "--priority", "ai", "--priority", "reach", "--ai-use", use, "--format", "csv")
    assert code == 0 and list(_rows(out)) == order
    assert (_rows(out)["strict"]["ai_tier"] == "severe") == (use == "drafting")


def test_the_journal_ladder_can_put_journals_the_preprint_server_transfers_to_first(catalogue: Path,
                                                                                    tmp_path: Path) -> None:
    software = ("--study-design", "software")  # no validation rule for a software paper: the fit ties
    code, out, _ = _run("ladder", *ONLY, *software, "--priority", "transfer", "--priority", "reach", "--server", "server",
                        "--format", "csv")
    rows = _rows(out)
    # Strict is on the server's list; the list was not checked for the other two, so they are not known and follow.
    assert code == 0 and list(rows) == ["strict", "calm", "keeper"]
    assert [rows[k]["transfers"] for k in rows] == ["server", "", ""]
    code, out, _ = _run("ladder", *ONLY, *software, "--priority", "reach", "--server", "quiet", "--format", "csv")
    assert {k: r["transfers"] for k, r in _rows(out).items()} == {"strict": "none", "calm": "none", "keeper": ""}
    # The record's preprint ladder names the server; the table says it in words.
    record = _record(tmp_path, {"priorities": {"journals": ["transfer", "reach"]}, "ladders": {"preprints": ["server"]},
                                "study": {"designs": ["software"], "confirmed": True}})
    code, out, _ = _run("ladder", *ONLY, "--record", str(record))
    assert code == 0 and _order(out) == ["strict", "calm", "keeper"]
    assert "a direct transfer from your preprint server, A Server" in out
    assert "A Server transfers the manuscript here directly." in out
    assert "Whether A Server transfers here directly was not checked." in out
    code, _, err = _run("ladder", *ONLY, "--priority", "transfer", "--format", "csv")
    assert code != 0


def test_the_journal_transfer_priority_needs_a_known_server(catalogue: Path) -> None:
    code, out, _ = _run("ladder", *ONLY, "--server", "nowhere")
    assert code != 0
