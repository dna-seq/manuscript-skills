"""Text moved in from another file, and every text read for a cited work kept across runs, 0.49
(docs/run-audit-2026-10.md, item 13 and the source cache): the v0.6 story stage's supplement guard reported the
numbers of a paragraph moved in from the main text as new, and v0.6's reference check proposed deleting "equipment"
because it had only the abstract of a paper whose full text v0.5 had read in a browser."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = load("guard_049", ROOT / "skills/manuscript-prose-edit/scripts/guard.py")
cache = load("source_cache_049", ROOT / "skills/manuscript-reference-check/scripts/source_cache.py")
support = load("support_049", ROOT / "skills/manuscript-reference-check/scripts/support.py")
runner = CliRunner()

MOVED = "The 0.10.1 run gave Pearson r 0.999997 against PLINK2 on chrX and took 21.4 s."
MAIN = f"# Paper\n\n## Results\n\nThe tool is fast.\n\n{MOVED}\n"
SUP_BEFORE = "# Supplement\n\n**S3. Benchmarks.** The runs used 16 threads.\n"
SUP_AFTER = f"# Supplement\n\n**S3. Benchmarks.** The runs used 16 threads. {MOVED}\n"


def test_numbers_moved_in_from_the_main_text_are_not_new_to_the_supplement() -> None:
    plain = guard.compare(SUP_BEFORE, SUP_AFTER)
    assert guard.exit_code(plain) == 1 and plain["protected"]["numbers"]["added"]
    moved = guard.compare(SUP_BEFORE, SUP_AFTER, moved_from=[("paper.md", MAIN)])
    assert guard.exit_code(moved) == 0 and "numbers" not in moved["protected"]
    tokens = [c for c in moved["sentence_changes"] if c.get("token_status")]
    assert tokens and {c["token_status"] for c in tokens} == {"from_other_file"}
    assert {c["severity"] for c in tokens} == {"warning"} and {c["token_file"] for c in tokens} == {"paper.md"}
    assert moved["moved_from"]["files"] == ["paper.md"]
    assert "came with text moved here from paper.md" in guard.to_markdown(moved)


def test_a_number_the_source_file_does_not_hold_stays_new() -> None:
    after = SUP_AFTER.replace("took 21.4 s.", "took 21.4 s on 64 cores.")
    report = guard.compare(SUP_BEFORE, after, moved_from=[("paper.md", MAIN)])
    assert guard.exit_code(report) == 1
    assert [c["token"] for c in report["sentence_changes"] if c.get("token_status") == "new"] == ["64"]


def test_guard_moved_from_on_the_command_line(tmp_path: Path) -> None:
    for name, text in (("before.md", SUP_BEFORE), ("after.md", SUP_AFTER), ("paper.md", MAIN)):
        (tmp_path / name).write_text(text, encoding="utf-8")
    args = [str(tmp_path / "before.md"), str(tmp_path / "after.md")]
    assert runner.invoke(guard.app, args).exit_code == 1
    assert runner.invoke(guard.app, [*args, "--moved-from", str(tmp_path / "paper.md")]).exit_code == 0


# --- the source cache -----------------------------------------------------------------------------------------

def test_every_text_read_for_a_work_is_kept_once_and_found_by_any_identifier(tmp_path: Path) -> None:
    keys = ["doi:10.1016/j.gim.2023.101058", "pmid:37000001"]
    assert cache.store(keys, "The abstract.", "abstract", "europepmc:abstract", base=tmp_path)
    assert cache.store(["doi:10.1016/j.gim.2023.101058"], "An excerpt naming equipment.", "excerpt", "browser",
                       run="20261025T235613Z-1931e926", base=tmp_path)
    assert cache.store(keys, "The abstract.", "abstract", "again", base=tmp_path) is None  # the same text, once
    held = cache.lookup(["pmid:37000001"], base=tmp_path)
    assert [h["scope"] for h in held] == ["abstract"]  # the excerpt was saved under the DOI alone
    held = cache.lookup(["doi:10.1016/j.gim.2023.101058"], base=tmp_path)
    assert [h["scope"] for h in held] == ["excerpt", "abstract"]  # the fullest first
    text = cache.combined(held, base=tmp_path)
    assert text.startswith("An excerpt naming equipment.") and "Another text read for this work: abstract" in text
    assert cache.parse_key("https://doi.org/10.1016/J.GIM.2023.101058") == "doi:10.1016/j.gim.2023.101058"
    assert cache.parse_key("PMC5292722") == "pmcid:PMC5292722" and cache.parse_key("not an id") is None


def test_seed_indexes_an_earlier_run_s_sources_and_never_guesses(tmp_path: Path) -> None:
    run = tmp_path / "reviews" / "20261025T235613Z-1931e926"
    sources = run / "manuscript-reference-check" / "sources"
    sources.mkdir(parents=True)
    (run / "manuscript-reference-check" / "references.json").write_text(
        json.dumps({"references": [{"doi": "10.1093/nar/gkac931"}]}), encoding="utf-8")
    (sources / "doi_10.1002_cpt.2350.txt").write_text("Fetched full text.", encoding="utf-8")
    (sources / "doi_10.1002_cpt.2350.json").write_text(json.dumps({"given": "doi:10.1002/cpt.2350",
                                                                   "scope": "full_text"}), encoding="utf-8")
    (sources / "pmc_Manrai2016_PMC5292722.plain.txt").write_text("A PMC text.", encoding="utf-8")
    (sources / "doi_10.1093_nar_gkac931.txt").write_text("A copy named after a recorded DOI.", encoding="utf-8")
    (sources / "web_cost_fact_sheet.txt").write_text("A web page.", encoding="utf-8")
    indexed, skipped = cache.seed(run, base=tmp_path / "cache")
    assert indexed == 3 and [Path(s).name for s in skipped] == ["web_cost_fact_sheet.txt"]
    held = cache.lookup(["doi:10.1093/nar/gkac931"], base=tmp_path / "cache")
    assert held[0]["scope"] == "saved" and held[0]["run"] == "20261025T235613Z-1931e926"
    assert cache.lookup(["doi:10.1002/cpt.2350"], base=tmp_path / "cache")[0]["scope"] == "full_text"
    assert cache.lookup(["pmcid:PMC5292722"], base=tmp_path / "cache")


def test_save_on_the_command_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CACHE", str(tmp_path / "cache"))
    excerpt = tmp_path / "excerpt.txt"
    excerpt.write_text("costs of labour, equipment and analysis", encoding="utf-8")
    assert cache.main(["save", "doi:10.1016/j.gim.2023.101058", str(excerpt), "--via", "browser",
                       "--url", "https://example.org/fulltext"]) == 0
    assert cache.main(["show", "doi:10.1016/j.gim.2023.101058"]) == 0
    assert cache.main(["show", "doi:10.1000/nothing"]) == 1
    assert cache.main(["save", "not-an-id", str(excerpt)]) == 2


# --- support.py reads with what is kept -------------------------------------------------------------------------

CLAIM = "Costs include labour, equipment and analysis."


def claims_file(tmp_path: Path, quote: str = "labour, equipment and analysis") -> Path:
    path = tmp_path / "claims.yaml"
    path.write_text(json.dumps({"claims": [{"id": "C1", "location": "Introduction, paragraph 2", "claim": CLAIM, "reference": "Mordaunt 2024",
                                            "source": "doi:10.1016/j.gim.2023.101058", "quote": quote}]}),
                    encoding="utf-8")
    return path


def test_offline_a_work_is_read_from_every_text_kept_for_it_and_the_report_says_so(tmp_path: Path) -> None:
    keys = ["doi:10.1016/j.gim.2023.101058"]
    cache.store(keys, "An abstract about genome costs.", "abstract", "europepmc:abstract")
    cache.store(keys, "The costs of labour, equipment and analysis rose.", "excerpt", "browser",
                run="20261025T235613Z-1931e926", read_at="2026-10-26T00:24:22+00:00")
    report = support.run(claims_file(tmp_path), online=False, cache_dir=tmp_path / "run-sources")
    result = report.results[0]
    assert result.status == "quote_located" and result.source.scope == "partial"
    assert result.source.reused_from["runs"] == ["20261025T235613Z-1931e926"]
    assert (tmp_path / "run-sources" / "doi_10.1016_j.gim.2023.101058.txt").is_file()  # the run keeps its copy
    assert "read with texts kept from earlier reads" in support.to_markdown(report)
    alone = support.run(claims_file(tmp_path), online=False, cache_dir=tmp_path / "fresh", shared=False)
    assert alone.results[0].status == "source_unavailable"


def test_a_quote_missing_from_a_partial_text_is_unavailable_not_absent(tmp_path: Path) -> None:
    cache.store(["doi:10.1016/j.gim.2023.101058"], "An excerpt about something else.", "excerpt", "browser")
    report = support.run(claims_file(tmp_path), online=False, cache_dir=tmp_path / "run-sources")
    assert report.results[0].status == "source_unavailable"


def test_a_fetched_text_is_kept_and_joins_a_partial_one_read_earlier(tmp_path: Path, monkeypatch) -> None:
    keys = ["doi:10.1016/j.gim.2023.101058"]
    cache.store(keys, "The costs of labour, equipment and analysis rose.", "excerpt", "browser")
    fetched = support.SourceInfo(given="doi:10.1016/j.gim.2023.101058", kind="doi", scope="abstract",
                                 via="europepmc:abstract")
    monkeypatch.setattr(support, "_fetched", lambda kind, value, fetch: ("An abstract.", fetched.model_copy()))
    text, info = support.fetch_identifier("doi", "10.1016/j.gim.2023.101058", object(), tmp_path / "run")
    assert text.startswith("An abstract.") and "equipment" in text and info.scope == "partial"
    assert {h["scope"] for h in cache.lookup(keys)} == {"excerpt", "abstract"}  # the fetched one kept too
