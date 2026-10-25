"""guard.py false alarms found in the blind v0.3 run: a storage device read as a cause, a negated proof word read as
proof, and the title of a cited work read as the authors' claim."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


guard = _load("guard_false_alarms", ROOT / "skills" / "manuscript-prose-edit" / "scripts" / "guard.py")

PAPER = """# A local annotator

## Abstract

The tool annotates one genome in 39 seconds. These timings do not establish accuracy across individuals.

## Results

The tool annotated one genome in 39 seconds on a workstation with a solid-state drive.

## Discussion

Timing one genome does not show accuracy across individuals.

## References

Smith, J. (2020). A fast annotator. *Bioinformatics*, 36, 1–2.
"""


def _widened(after: str) -> list[dict[str, object]]:
    return guard.unrequested(guard.compare(PAPER, after, revision=True, authorised=[]))


def test_a_storage_drive_is_not_a_cause() -> None:
    assert not [f for f in guard._ladder("HDD, hard disk drive; SSD, solid-state drive.", guard.CAUSAL)]
    assert guard._ladder("Loss of Foo drives tumour growth.", guard.CAUSAL)[0][1] == "causation"
    after = PAPER.replace("## References", "## Abbreviations\n\nHDD, hard disk drive; SSD, solid-state drive.\n\n"
                                           "## References")
    assert not _widened(after)


def test_a_negated_proof_word_states_a_limit() -> None:
    for sentence in ("They do not establish accuracy.", "It does not provide diagnoses or establish clinical validity.",
                     "This cannot be confirmed from one genome."):
        assert not [r for r in guard._ladder(sentence, guard.EVIDENTIAL) if r[1] == "proof"], sentence
    assert [r for r in guard._ladder("These timings establish accuracy.", guard.EVIDENTIAL) if r[1] == "proof"]
    assert not [f for f in guard.summary_check(PAPER)["findings"] if f["kind"] == "evidential"]


def test_the_title_of_a_cited_work_is_not_the_authors_claim() -> None:
    after = PAPER.replace("*Bioinformatics*, 36, 1–2.", "*Bioinformatics*, 36, 1–2.\n\nPoplin, R. (2018). A universal "
                                                        "SNP and small-indel variant caller. *Nat Biotechnol*, 36, 983.")
    assert not _widened(after)
    claimed = PAPER.replace("on a workstation", "on a workstation, and it works universally")
    assert _widened(claimed)  # the same word in the body still counts
