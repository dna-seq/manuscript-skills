"""The behavioural cases reach the agent under neutral names: evals/stage.py and every case it stages."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest
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


stage = _load("evals_stage", ROOT / "evals" / "stage.py")
CASES = stage.load_cases()
GIVEAWAY = re.compile(r"seeded|clean|planted|control|fixture", re.IGNORECASE)


@pytest.mark.parametrize(("name", "is_dir", "expected"), [
    ("seeded.md", False, "manuscript.md"), ("clean.md", False, "manuscript.md"),
    ("edited-seeded.md", False, "edited.md"), ("paper-v2-seeded.md", False, "paper-v2.md"),
    ("review-ledger-seeded.yaml", False, "review-ledger.yaml"), ("clean-association.md", False, "association.md"),
    ("seeded", True, "paper"), ("clean", True, "paper"), ("original.md", False, "original.md"),
    ("sources", True, "sources"), ("unclean-notes.md", False, "unclean-notes.md"),
])
def test_names_lose_their_condition_word(name: str, is_dir: bool, expected: str) -> None:
    assert stage.neutral(name, is_dir) == expected


def test_prompts_keep_plain_words_and_lose_file_names() -> None:
    assert stage.staged_prompt("Check edited-seeded.md. Then seeded/paper.md, seeded/code and seeded/data.") == (
        "Check edited.md. Then paper/paper.md, paper/code and paper/data.")
    assert stage.staged_prompt("Just tell us, we'll clean it ourselves.") == "Just tell us, we'll clean it ourselves."


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_no_case_gives_its_condition_away(case_id: str, tmp_path: Path) -> None:
    case = CASES[case_id]
    staged = stage.stage(case, tmp_path / "run")
    names = list(staged["files"].values())
    assert len(names) == len(set(names)), names
    for path in staged["work"].rglob("*"):
        assert not GIVEAWAY.search(str(path.relative_to(staged["work"]))), (case_id, path)
        if path.is_file() and path.suffix in (".md", ".tex", ".yaml"):
            text = path.read_text(encoding="utf-8")
            comments = re.findall(r"<!--.*?-->", text, re.DOTALL) + re.findall(r"(?m)^\s*[#%].*$", text) \
                if path.suffix != ".md" else re.findall(r"<!--.*?-->", text, re.DOTALL)
            assert not [c for c in comments if re.search(r"fixture|seeded|planted", c, re.I)], (case_id, path)
    prompt = staged["prompt"]
    assert not re.search(r"seeded|planted|fixture", prompt, re.IGNORECASE), (case_id, prompt)
    assert not [t for t in re.findall(r"[\w./-]*clean[\w./-]*", prompt, re.IGNORECASE) if "." in t.rstrip(".,;:")
                or "/" in t], (case_id, prompt)
    settings = staged["config"] / "settings.yaml"
    assert settings.is_file() == bool(case.get("settings"))
    if case.get("settings"):
        assert yaml.safe_load(settings.read_text(encoding="utf-8")) == case["settings"]


def test_staged_files_lose_the_comments_that_name_them_and_keep_their_lines() -> None:
    ledger = (ROOT / "evals" / "fixtures" / "manuscript-reviewer-response" / "review-ledger-seeded.yaml").read_text(
        encoding="utf-8")
    scrubbed = stage.scrub(ledger, ".yaml")
    assert "SEEDED COPY" in ledger and "SEEDED" not in scrubbed
    assert scrubbed.count("\n") == ledger.count("\n") and yaml.safe_load(scrubbed) == yaml.safe_load(ledger)
    record = (ROOT / "evals" / "fixtures" / "manuscript-peer-review" / "manuscript-record.yaml").read_text(
        encoding="utf-8")
    assert "manuscript: manuscript.md" in stage.scrub(record, ".yaml")
    note = "<!-- Evaluation fixture for a skill: a fictional study.\nNothing here is real. -->\n# Title\n"
    assert stage.scrub(note, ".md") == "\n\n# Title\n"
    kept = "<!-- TODO: add the cohort size -->\nCells were seeded at 10,000 per well.\n"
    assert stage.scrub(kept, ".md") == kept  # a draft's own comment, and "seeded" as a word, stay


def test_staging_refuses_the_checkout_and_a_used_folder(tmp_path: Path) -> None:
    case = CASES["peer-review-seeded-01"]
    with pytest.raises(ValueError, match="inside the repository"):
        stage.stage(case, ROOT / "evals" / "run")
    assert not (ROOT / "evals" / "run").exists()
    used = tmp_path / "used"
    used.mkdir()
    (used / "notes.md").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        stage.stage(case, used)


def test_the_command_line_prints_the_folders_and_the_prompt(tmp_path: Path) -> None:
    runner = CliRunner()
    staged = runner.invoke(stage.app, ["peer-review-seeded-01", "--to", str(tmp_path / "run")])
    assert staged.exit_code == 0, staged.output
    assert f"Working folder: {tmp_path / 'run' / 'work'}" in staged.output
    assert "MANUSCRIPT_SKILLS_CONFIG=" in staged.output and "Prompt:" in staged.output
    assert (tmp_path / "run" / "work" / "manuscript.md").is_file()
    assert runner.invoke(stage.app, ["no-such-case"]).exit_code == 2


# --- planted items pinned to their files, and paired cases ------------------------------------------------------

EVALS = ROOT / "evals"


def _folded(text: str) -> str:
    return " ".join(text.split())


def _clean_twins(path: str) -> list[Path]:
    """The clean control of a seeded file, by the fixtures' naming: seeded.md and clean.md, a seeded/ folder and
    clean/, response-seeded.md and response-clean.md, paper-v2-seeded.md and paper-v2.md."""
    names = {path.replace("seeded", "clean"), path.replace("-seeded", "")} - {path}
    return [EVALS / n for n in sorted(names) if (EVALS / n).is_file()]


ANCHORED = {cid: case for cid, case in CASES.items() if case.get("anchors")}


@pytest.mark.parametrize("case_id", sorted(ANCHORED))
def test_each_planted_item_is_pinned_by_words_that_occur_exactly_once(case_id: str) -> None:
    """Idea 7 of the 2026-10-24 comparison: a planted item the fixture no longer holds, or holds twice, is caught
    before any grader reads a run."""
    case = ANCHORED[case_id]
    anchors = case["anchors"]
    assert sorted(a["item"] for a in anchors) == list(range(1, len(case["planted"]) + 1))
    assert len({a["id"] for a in anchors}) == len(anchors)
    for a in anchors:
        assert a.get("file"), (case_id, a["id"], "every anchor names its file")
        file = EVALS / a["file"]
        assert file.is_file(), (case_id, a["id"], file)
        if "anchor" not in a:
            continue  # a defect in an image, or an absence: the file names where it is
        text = _folded(file.read_text(encoding="utf-8"))
        assert text.count(_folded(a["anchor"])) == 1, (case_id, a["id"], text.count(_folded(a["anchor"])))
        if not a.get("in_clean"):
            for twin in _clean_twins(a["file"]):
                assert _folded(a["anchor"]) not in _folded(twin.read_text(encoding="utf-8")), (case_id, a["id"], twin)


def test_paired_cases_name_real_partners_with_one_file_apart() -> None:
    pairs = [(cid, p) for cid, case in CASES.items() for p in case.get("pairs") or []]
    assert pairs, "the reviewer-response cases name their pairs"
    for cid, pair in pairs:
        assert pair["with"] in CASES and pair["expect"] in ("same", "different"), (cid, pair)
        mine, theirs = set(CASES[cid]["files"]), set(CASES[pair["with"]]["files"])
        assert len(mine ^ theirs) == 2, (cid, pair["with"], mine ^ theirs)  # one file swapped, the rest shared
