"""manuscript-journal-adapt's letters to the editor (letter.py): what a venue's facts put in its cover letter, a cover
letter whose every claim is traced to the fixture manuscript and no stronger there, declarations never invented, the
letter smells, a related paper named only once verified, and a presubmission inquiry. Every test runs the real
`needs` / `write` code on tests/fixtures/letters/paper.md and a catalogue of venue facts. Run with `uv run pytest`."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "manuscript-journal-adapt" / "scripts"
PAPER = ROOT / "tests" / "fixtures" / "letters" / "paper.md"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


letter = _load("letter_under_test", SCRIPTS / "letter.py")

RESOURCES = "Resources articles describe software tools and databases of broad use to the field."
CATALOGUE = {
    "checked": date(2026, 11, 1),
    "venues": {
        "pub": {"kind": "publisher", "name": "A Publisher", "url": "https://pub.example/policy",
                "disclosure_places": ["cover letter", "Acknowledgements"],
                "disclosure_fields": ["tool", "version", "how used"],
                "scope": {"quote": "The publisher's own scope, which no journal inherits."}},
        "shells": {"name": "Journal of Shells", "inherits": "pub", "url": "https://shells.example/guide",
                   "aliases": ["J Shells"],
                   "scope": {"quote": "Studies of molluscan biology and evolution.",
                             "article_types": {"Resources": RESOURCES},
                             "presubmission": "answered",
                             "source": "https://shells.example/guide#types", "checked": date(2026, 11, 10)},
                   "submission_rules": [
                       {"when": "submission", "rule": "a cover letter that declares any competing interests and "
                                                      "lists suggested reviewers",
                        "quote": ["The cover letter must declare competing interests and suggest three reviewers."],
                        "source": "https://shells.example/guide#letter", "checked": date(2026, 11, 10)},
                       {"when": "submission", "rule": "references in the journal's style",
                        "quote": ["Use the journal's reference style."]}]},
        "plain": {"name": "Plain Journal", "inherits": "pub", "url": "https://plain.example/guide"},
        "quiet": {"name": "Quiet Journal", "url": "https://quiet.example/guide", "disclosure_places": ["Methods"],
                  "fit_note": "pre-submission enquiries are not answered"},
    },
}


@pytest.fixture()
def catalogue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "venues.yaml"
    p.write_text(yaml.safe_dump(CATALOGUE), encoding="utf-8")
    monkeypatch.setattr(letter.venues, "VENUES_YAML", p)
    monkeypatch.setattr(letter.venues, "SNAPSHOT_INDEX", tmp_path / "index.yaml")
    return p


SHOWS = [
    {"text": "ShellAge re-reads every ring count from the original sources and holds 412 species, 160 of them new.",
     "from": ["ShellAge re-reads every ring count from the original sources", "It holds 412 species, 160 of them new"]},
    {"text": "Most correlations between shell thickness and lifespan that pass the false discovery rate fail on "
             "phylogenetically independent contrasts: 14 of 52 keep their sign and significance.",
     "from": ["Most correlations between shell thickness and lifespan that pass the false discovery rate fail on "
              "phylogenetically independent contrasts: 14 of 52 keep their sign and significance"]},
]
AI_USE = {"text": "Claude Code (Anthropic), running Claude Opus 5.5, wrote most of the code and drafted most of the "
                  "text; the authors checked the analyses and the text.",
          "from": ["Claude Code (Anthropic), running Claude Opus 5.5, wrote most of the code and drafted most of the text",
                   "The authors checked the analyses and the text"]}


def _cover(**changes: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "kind": "cover", "venue": "shells", "article_type": "Resources", "shows": [dict(s) for s in SHOWS],
        "fit": {"because": {"text": "ShellAge is a database that re-reads every ring count from the original sources.",
                            "from": ["ShellAge re-reads every ring count from the original sources"]}},
        "declarations": {
            "ai_use": AI_USE,
            "competing_interests": {"text": "The authors declare no competing interests.",
                                    "given_by": "the authors' message of 2026-11-15"},
            "reviewers": {"suggested": [{"name": "Cy Reviewer", "affiliation": "Shell Institute",
                                         "reason": "bivalve sclerochronology"}],
                          "given_by": "the authors' message of 2026-11-15"}},
        "signature": "Ada Example, Example University, ada@example.org",
    }
    spec.update(changes)
    return spec


def _write(tmp_path: Path, spec: dict[str, Any], **kwargs: Any) -> tuple[dict[str, Any], str, Path]:
    path = tmp_path / "LETTER.yaml"
    path.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    out = tmp_path / "RUN" / "manuscript-journal-adapt"
    record = letter.write_letter(letter.read_spec(path), PAPER, out, today=date(2026, 11, 15), **kwargs)
    return record, (out / record["letter"]).read_text(encoding="utf-8"), out


def _problems(record: dict[str, Any], part: str) -> list[str]:
    return [p for p in record["problems"] if p.startswith(part)]


# ------------------------------------------------------------------------------------------------ needs

def test_needs_reads_the_declarations_the_points_and_the_journals_own_words(catalogue: Path) -> None:
    n = letter.letter_needs(letter._venue("shells"))
    assert set(n["declarations"]) == {"ai_use", "competing_interests", "reviewers"}
    assert n["declarations"]["ai_use"]["fields"] == ["tool", "version", "how used"]
    assert n["declarations"]["competing_interests"]["source"] == "https://shells.example/guide#letter"
    assert [p["field"] for p in n["points"]] == ["submission_rules[0]"]  # the reference-style rule names no letter
    assert n["fit"]["article_types"] == {"Resources": RESOURCES}
    assert n["fit"]["scope"] == "Studies of molluscan biology and evolution."  # the journal's, not the publisher's
    assert (n["fit"]["source"], n["fit"]["checked"]) == ("https://shells.example/guide#types", "2026-11-10")
    assert n["presubmission"]["answered"] == "answered"
    # A journal's scope is its own: one that records none does not speak in its publisher's words.
    plain = letter.letter_needs(letter._venue("plain"))
    assert plain["fit"]["scope"] is None and "ai_use" in plain["declarations"]
    quiet = letter.letter_needs(letter._venue("quiet"))
    assert quiet["declarations"] == {} and quiet["presubmission"]["answered"] == "not_answered"
    assert not quiet["researched"]


def test_needs_command_prints_the_page_and_date_of_each_rule(catalogue: Path) -> None:
    result = CliRunner().invoke(letter.app, ["needs", "shells"])
    assert result.exit_code == 0, result.output
    assert f"- Resources articles: “{RESOURCES}”" in result.output
    assert "- Page: https://shells.example/guide#types, read 2026-11-10" in result.output
    assert "The page: “The cover letter must declare competing interests and suggest three reviewers.”" in result.output
    assert CliRunner().invoke(letter.app, ["needs", "nowhere"]).exit_code == 2


# ------------------------------------------------------------------------------------------------ the cover letter

def test_a_faithful_cover_letter_passes_and_traces_each_claim(catalogue: Path, tmp_path: Path) -> None:
    record, text, out = _write(tmp_path, _cover())
    assert record["passed"], record["problems"]
    assert record["letter"] == "cover-letter.shells.md"
    assert {p.name for p in out.iterdir()} == {"cover-letter.shells.md", "cover-letter.shells.claims.md",
                                              "cover-letter.shells.json"}
    # The request first, then what the paper shows, then the journal's own words and the declarations.
    assert text.startswith("Dear Editor,\n\nWe submit “ShellAge: a curated database of shell growth rings and "
                           "lifespan in bivalves” for consideration as a Resources article in Journal of Shells. "
                           "ShellAge re-reads")
    assert f"Journal of Shells's guidelines describe Resources articles as “{RESOURCES}”" in text
    assert "The authors declare no competing interests." in text
    assert "Suggested reviewers: Cy Reviewer, Shell Institute, bivalve sclerochronology." in text
    assert text.rstrip().endswith("Yours sincerely,\n\nAda Example, Example University, ada@example.org")
    claims = (out / "cover-letter.shells.claims.md").read_text(encoding="utf-8")
    assert "  - Abstract, line 9: It holds 412 species, 160 of them new" in claims
    assert "(https://shells.example/guide#types, read 2026-11-10)" in claims
    assert "Materials and methods > Use of AI tools, line" in claims
    data = json.loads((out / "cover-letter.shells.json").read_text(encoding="utf-8"))
    assert data["passed"] and data["quoted"]["what"] == "Resources articles"
    # Only the optional related-paper gap is left.
    assert record["gaps"] == ["a recent paper in Journal of Shells close to this one, if the authors know one"]


@pytest.mark.parametrize(("sentence", "expected"), [
    ({"text": "All correlations between shell thickness and lifespan that pass the false discovery rate fail on "
              "phylogenetically independent contrasts.",
      "from": ["Most correlations between shell thickness and lifespan that pass the false discovery rate fail"]},
     "the letter says “all” where the manuscript says “most”"),
    ({"text": "Thicker shells cause longer lifespans before the contrasts were applied.",
      "from": ["thicker shells were associated with longer lifespans before the contrasts were applied"]},
     "claim guard: The claim became stronger"),
    ({"text": "ShellAge holds 450 species from 61 families.", "from": ["ShellAge holds 412 species from 61 families"]},
     "“450” is not in the manuscript's sentences it rests on"),
    ({"text": "Thicker shells were associated with longer lifespans before the contrasts were applied.",
      "from": ["In the sampled families, thicker shells were associated with longer lifespans"]},
     "The scope qualifier “In the sampled families” was dropped"),
    ({"text": "Bivalves include the longest-lived animals known.",
      "from": ["Bivalves include the longest-lived animals known"]}, "G6: line"),
    ({"text": "ShellAge will change how ecologists study ageing in the oceans."}, "untraced"),
    ({"text": "ShellAge holds 412 species.", "from": ["ShellAge holds 412 species from 70 families"]},
     "is not in the manuscript word for word"),
    ({"text": "ShellAge trims the abstract.", "from": ["trim to 150 words once the journal is chosen"]},
     "a note to the authors, not manuscript text"),
])
def test_a_sentence_the_manuscript_does_not_support_fails(catalogue: Path, tmp_path: Path, sentence: dict[str, Any],
                                                           expected: str) -> None:
    record, _, _ = _write(tmp_path, _cover(shows=[SHOWS[0], sentence]))
    assert not record["passed"]
    assert any(expected in p for p in _problems(record, "shows[1]")), record["problems"]
    assert not _problems(record, "shows[0]")


def test_a_sentence_without_from_is_matched_to_its_closest_results_sentence(catalogue: Path, tmp_path: Path) -> None:
    record, _, _ = _write(tmp_path, _cover(shows=[SHOWS[0], {"text": "ShellAge holds 412 species from 61 families."}]))
    assert record["passed"], record["problems"]
    traced = record["traced"][1]
    assert traced["how"].startswith("closest sentence") and traced["sources"][0]["section"] == "Results > Database content"


def test_declarations_are_never_invented(catalogue: Path, tmp_path: Path) -> None:
    record, text, _ = _write(tmp_path, _cover(declarations={
        "funding": {"text": "This work was supported by the Wellcome Trust (grant EF-123).",
                    "from": ["This work was supported by the Example Foundation (grant EF-123)"]},
        "competing_interests": {"text": "The authors declare no competing interests."},
        "reviewers": {"suggested": [{"name": "Cy Reviewer"}]}}))
    assert any("names what its passages do not: Trust, Wellcome" in p for p in _problems(record, "declarations.funding"))
    assert any("no source" in p for p in _problems(record, "declarations.competing_interests"))
    assert any("reviewers come only from the authors" in p for p in _problems(record, "declarations.reviewers"))
    # None of them reaches the letter; each asked-for one is a gap instead.
    assert "Wellcome" not in text and "no competing interests" not in text and "Cy Reviewer" not in text
    assert "[TO FILL: funding, from the authors or the manuscript's own words" in text
    assert "[TO FILL: competing interests, from the authors or the manuscript's own words" in text
    assert "[TO FILL: suggested or excluded reviewers, from the authors]" in text
    # The AI-use statement the venue asks for and nobody gave is a gap too, pointing at the template.
    assert "[TO FILL: the use of AI tools, from what the authors say the tools did" in text


def test_a_declaration_copied_from_the_manuscript_passes(catalogue: Path, tmp_path: Path) -> None:
    record, text, _ = _write(tmp_path, _cover(declarations={**_cover()["declarations"], "funding": {
        "text": "This work was supported by the Example Foundation (grant EF-123).",
        "from": ["This work was supported by the Example Foundation (grant EF-123)"]}}))
    assert record["passed"], record["problems"]
    assert "This work was supported by the Example Foundation (grant EF-123)." in text


def test_an_unfinished_declaration_in_the_manuscript_is_no_source(catalogue: Path, tmp_path: Path) -> None:
    record, text, _ = _write(tmp_path, _cover(declarations={**_cover()["declarations"], "competing_interests": {
        "text": "To be completed.", "from": ["AUTHOR: to be completed"]}}))
    assert any("a note to the authors" in p for p in _problems(record, "declarations.competing_interests"))
    assert "To be completed." not in text


@pytest.mark.parametrize(("change", "expected"), [
    ({"closing": "We look forward to hearing from you."}, "G5 (templated letter opening or closing): “We look forward "
                                                          "to hearing from you”"),
    ({"closing": "Thank you. Please do not hesitate to contact us."}, "the closing is more than one line (G5)"),
    ({"points": [{"text": "ShellAge is a groundbreaking resource that sheds light on ageing.",
                  "given_by": "x"}]}, "A1 (significance inflation)"),
])
def test_the_letter_smells_fail(catalogue: Path, tmp_path: Path, change: dict[str, Any], expected: str) -> None:
    record, _, _ = _write(tmp_path, _cover(**change))
    assert any(expected in p for p in record["problems"]), record["problems"]


def test_the_journals_quoted_words_are_not_counted_as_smells(catalogue: Path, tmp_path: Path) -> None:
    hype = {**CATALOGUE["venues"]["shells"],
            "scope": {"article_types": {"Resources": "Groundbreaking resources of great interest to our readers."}}}
    p = catalogue
    p.write_text(yaml.safe_dump({**CATALOGUE, "venues": {**CATALOGUE["venues"], "shells": hype}}), encoding="utf-8")
    record, text, _ = _write(tmp_path, _cover())
    assert "Groundbreaking resources" in text
    assert record["passed"], record["problems"]


def test_g5_is_in_the_shared_smell_catalogue() -> None:
    style = letter.style
    doc = style.profile_text("We are pleased to submit our manuscript for your kind consideration.\n", False,
                             style.load_smells(), style.load_kobak())
    assert doc["smell_totals"].get("G5") == 2


def test_a_long_cover_letter_fails(catalogue: Path, tmp_path: Path) -> None:
    long_point = {"text": "ShellAge re-reads every ring count from the original sources. " * 40,
                  "from": ["ShellAge re-reads every ring count from the original sources"]}
    record, _, _ = _write(tmp_path, _cover(points=[long_point]))
    assert any("more than the 450 a one-page cover letter takes" in p for p in record["problems"])


# ------------------------------------------------------------------------------------------------ related paper

RELATED = {"citation": "Sample B (2025) Rings and years. J Shells 12:1-9", "doi": "10.1234/shells.2025.1",
           "verified": "manuscript-reference-check identity, 2026-11-15"}


def test_a_related_paper_is_named_only_once_verified(catalogue: Path, tmp_path: Path) -> None:
    unverified = {k: v for k, v in RELATED.items() if k != "verified"}
    record, text, _ = _write(tmp_path, _cover(related=unverified))
    assert "Rings and years" not in text and any("only once its identity is verified" in p for p in record["problems"])
    record, text, _ = _write(tmp_path, _cover(related=RELATED))
    assert record["passed"], record["problems"]
    assert "It follows on from Sample B (2025) Rings and years. J Shells 12:1-9 (https://doi.org/10.1234/shells.2025.1), " \
           "published in Journal of Shells." in text


@pytest.mark.parametrize(("found", "expected"), [
    ({"container-title": ["Journal of Other Things"], "issued": {"date-parts": [[2025]]}}, "not Journal of Shells"),
    ({"container-title": ["Journal of Shells"], "issued": {"date-parts": [[2019]]}}, "not within the last 3 years"),
    ({"container-title": ["J Shells"], "issued": {"date-parts": [[2025]]}}, None),
])
def test_crossref_must_place_the_related_paper_in_this_journal_recently(catalogue: Path, tmp_path: Path,
                                                                        found: dict[str, Any], expected: str | None) -> None:
    record, text, _ = _write(tmp_path, _cover(related=RELATED), lookup=lambda doi: found)
    if expected is None:
        assert record["passed"], record["problems"]
        assert "Rings and years" in text
    else:
        assert "Rings and years" not in text
        assert any(expected in p for p in record["problems"]), record["problems"]


# ------------------------------------------------------------------------------------------------ the inquiry

def _inquiry(**changes: Any) -> dict[str, Any]:
    spec: dict[str, Any] = {
        "kind": "inquiry", "venue": "shells", "article_type": "research article",
        "question": "Would the Journal of Shells consider ShellAge as a research article rather than as a Resource?",
        "shows": [dict(SHOWS[1])], "fit": {"use": "article_type"},
        "accept": "A yes or no is enough: with a yes we submit it as a research article, with a no as a Resource."}
    spec.update(changes)
    return spec


def test_an_inquiry_asks_first_and_carries_the_abstract(catalogue: Path, tmp_path: Path) -> None:
    record, text, out = _write(tmp_path, _inquiry())
    assert record["letter"] == "presubmission-inquiry.shells.md" and (out / "presubmission-inquiry.shells.md").exists()
    assert text.startswith("Subject: Presubmission inquiry: ShellAge: a curated database of shell growth rings and "
                           "lifespan in bivalves, as a research article\n\nDear Editor,\n\nWould the Journal of Shells")
    assert "A yes or no is enough" in text
    abstract = text.split("Abstract:\n\n")[1]
    assert abstract.startswith("Shell growth rings record the age of a bivalve")
    assert "AUTHOR" not in abstract and "14 of 52 keep their sign and significance." in abstract
    # No article-type words for "research article" are recorded: the rule the question turns on is a gap.
    assert any(g.startswith("the rule of Journal of Shells's author guide the question turns on") for g in record["gaps"])
    assert record["passed"], record["problems"]


def test_an_inquiry_must_ask_and_the_venue_must_answer(catalogue: Path, tmp_path: Path) -> None:
    record, _, _ = _write(tmp_path, _inquiry(question="We would like to know whether it fits."))
    assert any("does not end with a question mark" in p for p in record["problems"])
    record, _, _ = _write(tmp_path, _inquiry(venue="quiet"))
    assert any("does not answer presubmission inquiries: “pre-submission enquiries are not answered”" in p
               for p in record["problems"])


def test_an_inquiry_needs_a_question_and_what_the_authors_accept(tmp_path: Path) -> None:
    for missing in ("question", "accept"):
        spec = {k: v for k, v in _inquiry().items() if k != missing}
        path = tmp_path / "LETTER.yaml"
        path.write_text(yaml.safe_dump(spec), encoding="utf-8")
        with pytest.raises(letter.LetterError, match=missing):
            letter.read_spec(path)


# ------------------------------------------------------------------------------------------------ the command

def test_write_command_exit_codes(catalogue: Path, tmp_path: Path) -> None:
    good, bad = tmp_path / "good.yaml", tmp_path / "bad.yaml"
    good.write_text(yaml.safe_dump(_cover()), encoding="utf-8")
    bad.write_text(yaml.safe_dump(_cover(closing="We look forward to hearing from you.")), encoding="utf-8")
    run = tmp_path / "RUN"
    ok = CliRunner().invoke(letter.app, ["write", str(good), "--paper", str(PAPER), "--run", str(run)])
    assert ok.exit_code == 0, ok.output
    assert (run / "manuscript-journal-adapt" / "cover-letter.shells.claims.md").exists()
    assert CliRunner().invoke(letter.app, ["write", str(bad), "--paper", str(PAPER), "--run", str(run)]).exit_code == 1
    assert CliRunner().invoke(letter.app, ["write", str(good), "--paper", str(PAPER)]).exit_code == 2
    unknown = tmp_path / "unknown.yaml"
    unknown.write_text(yaml.safe_dump(_cover(venue="nowhere")), encoding="utf-8")
    assert CliRunner().invoke(letter.app, ["write", str(unknown), "--paper", str(PAPER), "--out",
                                           str(tmp_path / "o")]).exit_code == 2


def test_each_gap_is_drafted_as_a_finding_for_the_authors(catalogue: Path, tmp_path: Path) -> None:
    """RM2: a gap only the authors can fill reaches the dashboard's To-do list as a major finding of the stage; an
    optional one (a related paper) is info. The evidence is the gap's marker in the letter itself."""
    record, text, out = _write(tmp_path, _cover(declarations={
        "competing_interests": {"text": "The authors declare no competing interests."}}))
    findings = record["findings"]
    assert [f["id"] for f in findings] == [f"JA-L-shells-{n}" for n in range(1, len(record["gaps"]) + 1)]
    by_gap = {f["evidence"][0]["quote"]: f for f in findings}
    assert all(marker in text for marker in by_gap)  # each marker word for word in the letter
    optional = [f for f in findings if f["severity"] == "info"]
    assert [f["evidence"][0]["quote"] for f in optional] == [
        "[TO FILL, optional: a recent paper in Journal of Shells close to this one, if the authors know one]"]
    competing = next(f for f in findings if "competing interests" in f["detail"])
    assert (competing["severity"], competing["stage"], competing["decision"], competing["quote"]) == \
        ("major", "journal", False, None)
    assert competing["looked_in"] == [record["letter"]] and competing["evidence"][0]["path"] == record["letter"]
    assert json.loads((out / "cover-letter.shells.json").read_text(encoding="utf-8"))["findings"] == findings


DASHBOARD_SCRIPTS = ROOT / "skills" / "manuscript-dashboard" / "scripts"


def test_the_dashboard_collects_each_letter_with_its_text_and_gaps(catalogue: Path, tmp_path: Path) -> None:
    """RM2: collect.py reads every letter letter.py wrote beside the stage report into the inventory's `letters`,
    which the Journals tab shows."""
    if str(DASHBOARD_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(DASHBOARD_SCRIPTS))
    dashboard = sys.modules.get("dashboard") or _load("dashboard", DASHBOARD_SCRIPTS / "dashboard.py")
    collect = _load("collect_letters", DASHBOARD_SCRIPTS / "collect.py")
    record, text, out = _write(tmp_path, _cover())
    (out / "notes.json").write_text("{}", encoding="utf-8")  # not a letter
    (out / "presubmission-inquiry.broken.json").write_text("{", encoding="utf-8")  # does not parse: left out
    found = collect.letters(tmp_path / "RUN")
    assert len(found) == 1
    letter_view = dashboard.Letter.model_validate(found[0])
    assert (letter_view.kind, letter_view.venue, letter_view.journal) == ("cover", "shells", record["journal"])
    assert letter_view.text == text and letter_view.gaps == record["gaps"]
    assert letter_view.file == "cover-letter.shells.md" and letter_view.claims == "cover-letter.shells.claims.md"
    assert letter_view.passed == record["passed"] and letter_view.words == record["words"]
    assert collect.letters(tmp_path / "nowhere") == []


def test_the_drafted_findings_pass_the_stage_check(catalogue: Path, tmp_path: Path) -> None:
    """Copied as they are into the stage's findings.json, the drafts pass what `runs.py finish` holds a stage to."""
    stage_check = _load("stage_check_letters", DASHBOARD_SCRIPTS / "stage_check.py")
    record, _, out = _write(tmp_path, _cover())
    doc = {"skill": "manuscript-journal-adapt", "findings": record["findings"], "changes": []}
    assert record["findings"]
    assert stage_check.fatal(doc) == []
    assert stage_check.placement(doc, "manuscript-journal-adapt", out, []) == []
