"""A seeded random sample of the cited sentences the priority claims left out, and its estimate for the unchecked rest:
idea 10 of the 2026-10-24 comparison with academic-research-skills."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "manuscript-reference-check" / "scripts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sampler = _load("sample_claims", SCRIPTS / "sample_claims.py")
support = _load("support_for_sample", SCRIPTS / "support.py")

SENTENCES = [f"Study {n} measured an effect of {n} percent in its cohort [{n}]." for n in range(1, 31)]
PAPER = ("# A paper\n\n## Introduction\n\n" + " ".join(SENTENCES[:15]) + " This sentence cites nothing.\n\n"
         "## Discussion\n\nDuncan et al. (2019) reported lower accuracy in other ancestries. " + " ".join(SENTENCES[15:])
         + "\n\n## References\n\n1. Duncan L et al. Analysis. Nat Commun. 2019 [1].\n")


@pytest.fixture()
def paper(tmp_path: Path) -> Path:
    path = tmp_path / "paper.md"
    path.write_text(PAPER, encoding="utf-8")
    claims = tmp_path / "claims.yaml"
    claims.write_text(yaml.safe_dump({"claims": [
        {"id": "C1", "location": "paper.md:5 (Introduction)", "claim": SENTENCES[0], "reference": "1",
         "priority": "load-bearing"},
        {"id": "C2", "location": "paper.md:9 (Discussion)", "claim": "Duncan et al. (2019) reported lower accuracy in "
         "other ancestries.", "reference": "Duncan 2019", "priority": "borrowed-number"}]}), encoding="utf-8")
    return path


def test_cited_sentences_are_counted_without_the_reference_list(paper: Path) -> None:
    cited = sampler.cited_sentences(paper.read_text(encoding="utf-8"))
    assert len(cited) == 31  # 30 numbered and one narrative citation; the reference list's "[1]" is not one
    assert cited[0]["section"] == "Introduction" and cited[0]["markers"] == ["[1]"]
    assert not any("cites nothing" in c["sentence"] for c in cited)


def test_the_draw_leaves_out_the_priority_claims_and_repeats_with_its_seed(paper: Path) -> None:
    text = paper.read_text(encoding="utf-8")
    chosen = sampler.chosen_claims(paper.parent / "claims.yaml")
    drawn, counts = sampler.draw(text, chosen, 8, seed=7)
    assert counts == {"seed": 7, "cited_sentences": 31, "by_priority": 2, "population": 29, "drawn": 8}
    assert SENTENCES[0] not in [d["sentence"] for d in drawn]
    assert [d["line"] for d in drawn] == sorted(d["line"] for d in drawn)  # in reading order
    again, _ = sampler.draw(text, chosen, 8, seed=7)
    other, _ = sampler.draw(text, chosen, 8, seed=8)
    assert again == drawn and other != drawn


def test_the_cli_writes_a_claims_file_support_py_reads(paper: Path) -> None:
    out = paper.parent / "claims-sample.yaml"
    result = CliRunner().invoke(sampler.app, [str(paper), "--claims", str(paper.parent / "claims.yaml"), "--out",
                                              str(out), "--size", "5"])
    assert result.exit_code == 0, result.output
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["sample"]["population"] == 29 and data["sample"]["drawn"] == 5 and data["sample"]["seed"] > 0
    assert [c["id"] for c in data["claims"]] == ["S1", "S2", "S3", "S4", "S5"]
    assert all(c["priority"] == "sample" and c["location"].startswith("paper.md:") for c in data["claims"])
    claims, _ = support.load_claims(out)  # a valid claims file
    assert len(claims) == 5
    assert CliRunner().invoke(sampler.app, [str(paper), "--out", str(out)]).exit_code == 2  # never overwritten


def test_the_count_option_gives_the_coverage_numbers(paper: Path) -> None:
    result = CliRunner().invoke(sampler.app, [str(paper), "--claims", str(paper.parent / "claims.yaml"), "--count"])
    assert json.loads(result.output) == {"cited_sentences": 31, "by_priority": 2, "population": 29}


def _sample_run(tmp_path: Path, outcomes: list[str | None]) -> "support.SupportReport":
    (tmp_path / "source.txt").write_text("Study one measured an effect of 1 percent in its cohort.", encoding="utf-8")
    claims = [{"id": f"S{n}", "location": f"paper.md:{n}", "claim": "Study one measured an effect [1].", "reference": "1",
               "priority": "sample", "quote": "Study one measured an effect", "source": "source.txt",
               **({"outcome": o} if o else {})} for n, o in enumerate(outcomes, 1)]
    path = tmp_path / "claims-sample.yaml"
    path.write_text(yaml.safe_dump({"sample": {"seed": 7, "cited_sentences": 112, "by_priority": 12, "population": 100},
                                    "claims": claims}), encoding="utf-8")
    return support.run(path, online=False, cache_dir=tmp_path / "cache")


def test_the_estimate_for_the_unchecked_rest_has_its_interval(tmp_path: Path) -> None:
    report = _sample_run(tmp_path, ["confirmed"] * 7 + ["partial", "rejected", "blocked"])
    e = report.sample
    assert e["drawn"] == 10 and e["unchecked"] == 90 and e["outcomes"]["blocked"] == 1
    assert e["share_not_supported"] == round(2 / 9, 3)
    low, high = e["interval"]
    assert 0.05 < low < 0.07 and 0.54 < high < 0.56  # Wilson 95% for 2 of 9
    assert e["unchecked_not_supported"] == [round(low * 90), round(high * 90)] and e["check_the_rest"] is True
    md = support.to_markdown(report)
    assert "## A random sample of the other cited sentences" in md and "seed 7" in md
    assert "This is an estimate from a sample, not a check of each sentence." in md
    assert "the remaining cited sentences are checked too" in md


def test_a_clean_sample_gives_a_low_estimate_and_no_call_to_check_the_rest(tmp_path: Path) -> None:
    e = _sample_run(tmp_path, ["confirmed"] * 10).sample
    assert e["share_not_supported"] == 0 and e["interval"][0] == 0 and e["check_the_rest"] is False


def test_unrated_sample_claims_hold_back_the_estimate(tmp_path: Path) -> None:
    report = _sample_run(tmp_path, ["confirmed", None, "partial"])
    assert report.sample["unrated"] == ["S2"] and "share_not_supported" not in report.sample
    assert "record each reading's outcome" in support.to_markdown(report)


def test_an_unknown_outcome_is_refused(tmp_path: Path) -> None:
    with pytest.raises(support.ClaimsFileError, match="outcome"):
        _sample_run(tmp_path, ["supported"])


def test_a_claims_file_without_a_sample_reports_none(tmp_path: Path) -> None:
    path = tmp_path / "claims.yaml"
    (tmp_path / "s.txt").write_text("Study one measured an effect.", encoding="utf-8")
    path.write_text(yaml.safe_dump({"claims": [{"id": "C1", "location": "L1", "claim": "Study one measured an effect.",
                                               "reference": "1", "quote": "Study one measured an effect",
                                               "source": "s.txt", "outcome": "confirmed"}]}), encoding="utf-8")
    assert support.run(path, online=False, cache_dir=tmp_path / "c").sample is None
