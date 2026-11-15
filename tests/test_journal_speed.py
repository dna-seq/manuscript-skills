"""How fast a journal answers (manuscript-journal-select's speed.py): the editor's first decision as the journal
publishes it or "not published", the first decision after peer review from dated review records (Life Science
Alliance Review Process Files, a PLOS peer review history, eLife docmaps) or "not measurable from public records",
and submission to acceptance from PubMed histories, each its own record and its own column. The real code runs on
pages saved in tests/fixtures/journal-speed, served in place of the network. Run with `uv run pytest`."""

from __future__ import annotations

import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlparse

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "journal-speed"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


speed = _load("speed_under_test", ROOT / "skills" / "manuscript-journal-select" / "scripts" / "speed.py")
venues = speed.venues

# PubMed ids of the saved efetch answer, by the journal query that finds them.
PMIDS = {'"Life Sci Alliance"[ta]': ["43020637", "43009280", "43015079"],
         '"PLoS Comput Biol"[ta]': ["43019353", "43024679"],
         '"Nucleic Acids Res"[ta]': ["43032927", "43031553", "41468912"]}
RPF = {"10.26508/lsa.202503590": "lsa-202503590-direct.pdf", "10.26508/lsa.202603770": "lsa-202603770-direct.pdf",
       "10.26508/lsa.202403190": "lsa-202403190-review-commons.pdf"}


def _efetch(ids: list[str]) -> bytes:
    root = ET.parse(FIXTURES / "pubmed-efetch.xml").getroot()
    out = ET.Element(root.tag)
    out.extend(a for a in root.findall("PubmedArticle") if a.findtext(".//PMID") in ids)
    return ET.tostring(out, encoding="utf-8")


def fake_fetch(url: str) -> bytes:
    """The saved page for a URL the harvest asks for; b"" (a page that does not exist) for anything else."""
    q = {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}
    if "esearch.fcgi" in url:
        ids = next((ids for journal, ids in PMIDS.items() if q["term"].startswith(journal)), [])
        return json.dumps({"esearchresult": {"count": str(len(ids)), "idlist": ids}}).encode()
    if "efetch.fcgi" in url:
        return _efetch(q["id"].split(","))
    if "reviewer-comments.pdf" in url:
        doi = url.split("/lookup/doi/")[1].removesuffix(".reviewer-comments.pdf")
        return (FIXTURES / RPF[doi]).read_bytes() if doi in RPF else b""
    if "peerReview" in url:
        return (FIXTURES / "plos-pcbi.1014910-review-history.html").read_bytes() if q["id"].endswith("1014910") else b""
    if "reviewed-preprints" in url:
        return (FIXTURES / "elife-reviewed-preprints-page1.json").read_bytes() if q["page"] == "1" else b'{"items": []}'
    if "docmaps" in url:
        path = FIXTURES / f"elife-{q['manuscript_id']}-docmap.json"
        return path.read_bytes() if path.is_file() else b""
    return b""


CATALOGUE = {"checked": date(2026, 10, 15), "venues": {
    "life-science-alliance": {"name": "Life Science Alliance", "review_speed": [
        {"metric": "submission-to-acceptance", "days": 142, "statistic": "median", "checked": date(2026, 10, 15)}]},
    "plos-comp-biol": {"name": "PLOS Computational Biology"},
    "elife": {"name": "eLife"},
    "nar": {"name": "Nucleic Acids Research", "review_speed": [
        {"metric": "submission-to-first-decision", "days": 18, "statistic": "median", "period": 2025,
         "checked": date(2026, 10, 27)}]},
    "mbe": {"name": "Molecular Biology and Evolution"},
}}


@pytest.fixture(autouse=True)
def offline(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    catalogue = tmp_path / "venues.yaml"
    catalogue.write_text(yaml.safe_dump(CATALOGUE), encoding="utf-8")
    monkeypatch.setattr(venues, "VENUES_YAML", catalogue)
    monkeypatch.setattr(venues, "SNAPSHOT_INDEX", tmp_path / "index.yaml")
    monkeypatch.setattr(speed, "fetch", fake_fetch)
    monkeypatch.setattr(speed, "PAUSE", 0)
    return catalogue


def _run(*args: str) -> str:
    result = CliRunner().invoke(speed.app, [*args, "--checked", "2026-11-15"])
    assert result.exit_code == 0, result.output
    return result.output


def _records(facts: Path, key: str) -> dict[str, dict]:
    listed = yaml.safe_load(facts.read_text(encoding="utf-8"))["venues"][key]["review_speed"]
    return {venues.speed_kind(r["metric"]): r for r in listed if not r.get("sample")}


# ---------------------------------------------------------------------------------------- Review Process Files

def test_a_review_process_file_gives_its_timeline_and_how_the_paper_came() -> None:
    direct = speed.parse_rpf(speed.pdf_text((FIXTURES / "lsa-202503590-direct.pdf").read_bytes()))
    assert direct == {"submitted": date(2025, 12, 5), "first_decision": date(2026, 2, 24),
                      "accepted": date(2026, 10, 29), "route": "direct", "manuscript": "LSA-2025-03590-T",
                      "decisions": 2}
    commons = speed.parse_rpf(speed.pdf_text((FIXTURES / "lsa-202403190-review-commons.pdf").read_bytes()))
    assert commons["route"] == "review-commons" and commons["first_decision"] == date(2024, 12, 26)


@pytest.mark.parametrize(("name", "route", "first"), [
    ("lsa-202603750-columns.txt", "direct", date(2026, 6, 23)),  # labels first, then the dates
    ("lsa-202403105-opted-out.txt", "opted-out", date(2024, 12, 2)),  # dates kept, letters withheld
    ("lsa-202603709-bad-date.txt", "bad-timeline", date(2026, 8, 7)),  # dates first, one of them "2026-28-26"
    ("lsa-202603939-transfer.txt", "transfer", date(2026, 10, 21)),  # "previously reviewed at another journal"
])
def test_every_layout_of_the_timeline_is_read_and_only_direct_papers_count(name: str, route: str,
                                                                            first: date) -> None:
    parsed = speed.parse_rpf((FIXTURES / name).read_text(encoding="utf-8"))
    assert parsed["route"] == route and parsed["first_decision"] == first


def test_reviewed_counts_direct_submissions_and_names_the_rest(tmp_path: Path) -> None:
    facts = tmp_path / "facts.yaml"
    _run("reviewed", "life-science-alliance", "--records", "embo-rpf", "--journal", '"Life Sci Alliance"[ta]',
         "--out", str(tmp_path), "--facts", str(facts))
    rec = _records(facts, "life-science-alliance")
    after = rec["after-review"]
    # 81 days (2025-12-05 to 2026-02-24) and 35 (2026-05-13 to 2026-06-17); the Review Commons paper is apart.
    assert after["metric"] == "first-decision-after-review" and after["days"] == 58 and after["n"] == 2
    assert after["statistic"] == "median (interquartile range 46-70, n=2)"
    assert after["period"] == "first decisions 2026-02-24 to 2026-06-17"
    assert "submitted to the journal directly" in after["population"]
    assert after["note"] == "Left out: review-commons: 1 paper, median 2 days."
    assert after["counts"].startswith("days from submission (the Submission Date) to the first decision")
    # The catalogue's other measure stays beside it, untouched.
    assert rec["acceptance"]["days"] == 142
    rows = (tmp_path / "life-science-alliance.reviewed.tsv").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 4 and sorted(r.split("\t")[4] for r in rows[1:]) == ["direct", "direct", "review-commons"]


# ---------------------------------------------------------------------------------------- PLOS and eLife

def test_a_plos_history_gives_the_original_submission_and_the_first_letter(tmp_path: Path) -> None:
    page = (FIXTURES / "plos-pcbi.1014910-review-history.html").read_text(encoding="utf-8")
    assert speed.parse_plos(page) == {"submitted": date(2026, 3, 3), "first_decision": date(2026, 5, 14),
                                      "decisions": 3}
    facts = tmp_path / "facts.yaml"
    _run("reviewed", "plos-comp-biol", "--records", "plos", "--journal", '"PLoS Comput Biol"[ta]',
         "--out", str(tmp_path), "--facts", str(facts))
    after = _records(facts, "plos-comp-biol")["after-review"]
    assert after["days"] == 72 and after["n"] == 1
    # The other paper published no history: the sample is the authors who chose to publish one.
    assert after["population"].startswith("accepted papers whose authors chose to publish the peer review history "
                                          "(1 of the 2 recent papers read)")
    assert after["note"] == "Left out: no-history: 1 paper."


def test_elife_counts_from_sent_for_review_to_the_public_reviews(tmp_path: Path) -> None:
    docmap = json.loads((FIXTURES / "elife-112469-docmap.json").read_text(encoding="utf-8"))
    assert speed.parse_docmap(docmap) == {"sent": date(2026, 7, 13), "reviews": date(2026, 11, 12)}
    # The authors' reply is posted with the reviews here; dated earlier, it still never dates them.
    reviewed = next(s for s in docmap["steps"].values()
                    if any(a.get("status") == "peer-reviewed" for a in s.get("assertions") or []))
    reply = next(o for a in reviewed["actions"] for o in a["outputs"] if o["type"] == "reply")
    reply["published"] = "2026-10-01T09:00:00+00:00"
    assert speed.parse_docmap(docmap)["reviews"] == date(2026, 11, 12)
    facts = tmp_path / "facts.yaml"
    _run("reviewed", "elife", "--records", "elife", "--subject", "genetics-genomics", "--out", str(tmp_path),
         "--facts", str(facts))
    after = _records(facts, "elife")["after-review"]
    assert after["days"] == 50 and after["n"] == 1  # 113294 alone is in genetics and genomics
    assert "eLife publishes no submission date" in after["counts"]


# ---------------------------------------------------------------------------------------- PubMed histories

def test_nar_regular_articles_leave_out_issues_and_papers_not_yet_placed(tmp_path: Path) -> None:
    facts = tmp_path / "facts.yaml"
    _run("histories", "nar", "--journal", '"Nucleic Acids Res"[ta]', "--exclude-issue", "D1", "--placed-only",
         "--out", str(tmp_path), "--facts", str(facts))
    rec = _records(facts, "nar")
    assert rec["acceptance"]["days"] == 68 and rec["acceptance"]["n"] == 1  # 2026-07-31 to 2026-10-07, issue 21
    assert "only papers already placed in an issue" in rec["acceptance"]["population"]
    assert rec["editor"]["days"] == 18  # the catalogue's first decision is kept beside the new measures
    _run("histories", "nar", "--journal", '"Nucleic Acids Res"[ta]', "--exclude-issue", "D1",
         "--out", str(tmp_path), "--facts", str(facts))
    again = _records(facts, "nar")["acceptance"]
    assert again["n"] == 2 and again["days"] == 58.5  # the Database paper online before its issue is now in


# ---------------------------------------------------------------------------------------- the journal's own figure

def test_the_editors_first_decision_is_the_journals_figure_or_not_published(tmp_path: Path) -> None:
    facts = tmp_path / "facts.yaml"
    _run("editor", "life-science-alliance", "--not-published", "--source", "https://lsa.example/about",
         "--source", "https://lsa.example/editorial-process", "--facts", str(facts))
    rec = _records(facts, "life-science-alliance")["editor"]
    assert rec["days"] is None and rec["status"] == "not published"
    assert rec["source"] == "https://lsa.example/about; https://lsa.example/editorial-process"
    _run("editor", "mbe", "--days", "26", "--statistic", "mean", "--population", "all original submissions in 2021",
         "--period", "2021", "--source", "https://doi.org/10.1093/molbev/msac260", "--facts", str(facts))
    mbe = _records(facts, "mbe")["editor"]
    assert (mbe["days"], mbe["statistic"], mbe["population"]) == (26, "mean", "all original submissions in 2021")
    runner = CliRunner()
    neither = runner.invoke(speed.app, ["editor", "mbe", "--source", "u"])
    unsaid = runner.invoke(speed.app, ["editor", "mbe", "--days", "26", "--source", "u"])
    assert neither.exit_code == 2 and "give either --days" in neither.output
    assert unsaid.exit_code == 2 and "say whom the journal counts" in unsaid.output


def test_no_review_records_is_said_not_guessed(tmp_path: Path) -> None:
    facts = tmp_path / "facts.yaml"
    _run("reviewed", "mbe", "--records", "none", "--reason", "OUP publishes nothing of the review",
         "--source", "https://academic.oup.com/mbe/pages/author-guidelines", "--facts", str(facts))
    rec = _records(facts, "mbe")["after-review"]
    assert rec["days"] is None and rec["status"] == "not measurable from public records"
    refused = CliRunner().invoke(speed.app, ["reviewed", "mbe", "--records", "none"])
    assert refused.exit_code == 2 and "needs --reason and the pages read" in refused.output


# ---------------------------------------------------------------------------------------- kept apart

def test_the_ladder_compares_only_the_editors_first_decision() -> None:
    assert venues.speed_kind("first-decision-after-review") == "after-review"
    assert venues.speed_kind("first externally reviewed decision") == "after-review"
    assert venues.speed_kind("submission-to-first-decision (desk-inclusive)") == "editor"
    assert venues.speed_kind("submission-to-acceptance") == "acceptance"
    assert venues.speed_kind("acceptance-to-publication") == "publication"
    fast_review = {"review_speed": [{"metric": "first-decision-after-review", "days": 5}]}
    assert venues.speed_days(fast_review)[0] is None
    unpublished = {"review_speed": [{"metric": "submission-to-first-decision", "days": None,
                                     "status": "not published"}]}
    assert venues.speed_days(unpublished) == (None, "first decision not published by the journal")


def test_a_new_record_replaces_only_its_own_measure_and_sample(tmp_path: Path) -> None:
    facts = tmp_path / "facts.yaml"
    old = {"metric": "submission-to-acceptance", "days": 99, "checked": date(2026, 11, 15)}
    subset = {**old, "days": 120, "sample": "database papers"}
    for record in (old, subset, {**old, "days": 100}):
        speed.put_record(facts, "life-science-alliance", record)
    listed = yaml.safe_load(facts.read_text(encoding="utf-8"))["venues"]["life-science-alliance"]["review_speed"]
    assert sorted((r["days"], r.get("sample")) for r in listed) == [(100, None), (120, "database papers")]


def test_the_table_shows_each_measure_or_why_there_is_none(tmp_path: Path) -> None:
    facts = tmp_path / "facts.yaml"
    _run("editor", "life-science-alliance", "--not-published", "--source", "u", "--facts", str(facts))
    _run("reviewed", "life-science-alliance", "--records", "embo-rpf", "--journal", '"Life Sci Alliance"[ta]',
         "--out", str(tmp_path), "--facts", str(facts))
    _run("reviewed", "mbe", "--records", "none", "--reason", "nothing published", "--source", "u",
         "--facts", str(facts))
    out = CliRunner().invoke(speed.app, ["table", "life-science-alliance", "nar", "mbe", "--facts", str(facts)]).output
    rows = {line.split(" | ")[0].lstrip("| "): line.split(" | ")[1:] for line in out.splitlines()
            if line.startswith("| ") and "Journal" not in line}
    assert rows["Life Science Alliance"][:3] == [
        "not published", "58 days, median (interquartile range 46-70, n=2); first decisions 2026-02-24 to 2026-06-17",
        "142 days, median"]
    assert rows["Nucleic Acids Research"][:2] == ["18 days, median; population not stated; 2025", "not looked up"]
    assert rows["Molecular Biology and Evolution"][1] == "not measurable from public records"
    assert "What each column counts" in out and "- first decision after peer review: nothing published" in out
