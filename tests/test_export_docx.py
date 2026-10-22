"""The annotated Word document: the corrected version as tracked changes signed by each stage, the review as
comments, and no note to the authors in the text."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import zipfile
from pathlib import Path

from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


viz = load("dashboard", ROOT / "skills/manuscript-dashboard/scripts/dashboard.py")
revise = load("revise", ROOT / "skills/manuscript-improve/scripts/revise.py")
export = load("export_docx", ROOT / "skills/manuscript-dashboard/scripts/export_docx.py")

ORIGINAL = """# A tool

## 1. Introduction

Genomes are cheap. This tool plays a crucial role in annotation. We use HuggingFace for data.

| Engine | Time |
|---|---|
| PLINK2 | 5.7 s |

## 2. Methods

The pipeline joins by rsID. It is fast. See [the code](https://example.org/code).
"""


def evidence() -> list[dict]:
    return [{"path": "review.md", "quote": "The review."}]


def make_run(tmp_path: Path) -> Path:
    (tmp_path / "review.md").write_text("The review.")
    (tmp_path / "original.md").write_text(ORIGINAL)
    working = ORIGINAL.replace("HuggingFace", "Hugging Face")
    (tmp_path / "working.md").write_text(working)
    inventory = {
        "schema_version": 2, "title": "Review", "run_id": "run", "scope": "Whole paper.",
        "coverage": [{"skill": skill, "status": "completed", "note": "All.", "evidence": evidence()}
                     for skill in ("manuscript-improve", "manuscript-integrity-check", "manuscript-journal-select")],
        "findings": [
            {"id": "IC-1", "category": "Text versus code", "section": "2. Methods", "summary": "The join key contradicts the code",
             "severity": "major", "assessment": "confirmed", "resolution": "open", "stage": "now", "detail": "The code joins by position.",
             "action": "Say position and genotype.", "skills": ["manuscript-integrity-check"], "evidence": evidence(),
             "quote": "The pipeline joins by rsID."},
            {"id": "JS-1", "category": "Journal fit", "section": "Cover letter", "summary": "No cover letter yet",
             "severity": "minor", "assessment": "confirmed", "resolution": "open", "skills": ["manuscript-journal-select"],
             "evidence": evidence()},
        ],
        "manuscript": {"title": "A tool", "path": "original.md", "sections": ["1. Introduction", "2. Methods"]},
        "changes": [
            {"id": "prose-edit.C1", "kind": "Applied edit", "section": "1. Introduction", "summary": "Spell the company's name",
             "status": "applied", "before": "We use HuggingFace for data.", "after": "We use Hugging Face for data.",
             "evidence": evidence()},
            {"id": "IC-C1", "kind": "Proposed edit", "section": "2. Methods", "summary": "Name the real join key", "status": "proposed",
             "finding_ids": ["IC-1"], "before": "The pipeline joins by rsID.",
             "after": "The pipeline joins by position and genotype [AUTHORS: which genome build?].", "evidence": evidence(),
             "why": "The code joins on position and genotype; rsIDs are not used."},
            {"id": "ST-C1", "kind": "Story edit", "section": "1. Introduction", "summary": "Say what the tool does",
             "status": "proposed", "before": "This tool plays a crucial role in annotation.", "after": "This tool annotates variants.",
             "evidence": evidence()},
            {"id": "JA-C8", "kind": "Proposed edit", "section": "2. Methods", "summary": "Declare the AI use", "status": "proposed",
             "before": "It is fast.", "after": "It is fast. We used [AUTHORS: tool and version] to draft it.", "evidence": evidence()},
        ],
    }
    (tmp_path / "findings.json").write_text(json.dumps(inventory))
    result = CliRunner().invoke(revise.app, [str(tmp_path / "original.md"), str(tmp_path / "working.md"), str(tmp_path / "findings.json"),
                                             "--output-dir", str(tmp_path / "revision")])
    assert result.exit_code == 0, result.output
    return tmp_path


def parts(path: Path) -> tuple[str, str]:
    with zipfile.ZipFile(path) as docx:
        return docx.read("word/document.xml").decode(), docx.read("word/comments.xml").decode()


def test_the_corrected_version_is_tracked_changes_with_the_review_as_comments(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    out = run / "review.docx"
    result = CliRunner().invoke(export.app, [str(run / "findings.json"), "--revision", str(run / "revision"), "--output", str(out)])
    assert result.exit_code == 0, result.output
    counts = json.loads(result.output)
    assert counts["questions"] == 3 and counts["problems"] == 2 and counts["problems_on_their_section"] == 1 and counts["reasons"] == 3
    document, comments = parts(out)
    text = re.sub(r"<[^>]+>", "", document)
    assert "AUTHORS" not in text and "position and genotype" in text
    authors = set(re.findall(r'<w:(?:ins|del) [^>]*w:author="([^"]+)"', document))
    assert authors == {"Prose edit", "Integrity check", "Story"}
    assert re.search(r'<w:del [^>]*><w:r>.*?<w:delText[^>]*>rsID', document)
    assert "Question for the authors (IC-C1): which genome build?" in comments
    assert "IC-1 · Major, fix now: The join key contradicts the code." in comments
    assert "2 questions for the authors about JA-C8, a proposal left out of this version until they answer:" in comments
    assert "Why: The code joins on position and genotype; rsIDs are not used." in comments
    assert "1 problem about this part whose passage is not quoted in this text:" in comments and "About Cover letter" in comments
    assert document.count("<w:commentRangeStart") == comments.count("<w:comment ")
    assert "<w:hyperlink" in document and "<w:tbl>" in document
    assert CliRunner().invoke(export.app, [str(run / "findings.json"), "--output", str(out)]).exit_code != 0


def test_without_a_corrected_version_the_reviewed_text_carries_the_problems_only(tmp_path: Path) -> None:
    run = make_run(tmp_path)
    out = run / "reviewed.docx"
    result = CliRunner().invoke(export.app, [str(run / "findings.json"), "--output", str(out), "--no-reasons"])
    assert result.exit_code == 0, result.output
    document, comments = parts(out)
    assert "<w:ins " not in document and "<w:del " not in document and "HuggingFace" in re.sub(r"<[^>]+>", "", document)
    assert "IC-1 · Major" in comments and "Question for the authors" not in comments
