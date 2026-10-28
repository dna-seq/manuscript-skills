"""The citation metadata name the version that ships: CITATION.cff, which GitHub's "Cite this repository" and
Zenodo read, and the README's BibTeX agree with both plugin manifests. Run with `uv run pytest`."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def manifest_versions() -> set[str]:
    return {json.loads((ROOT / d / "plugin.json").read_text(encoding="utf-8"))["version"]
            for d in (".claude-plugin", ".codex-plugin")}


def test_citation_file_names_the_shipped_version():
    cff = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert manifest_versions() == {str(cff["version"])}
    assert date.fromisoformat(str(cff["date-released"])) <= date.today()
    assert cff["cff-version"] == "1.2.0" and cff["license"] == "MIT"
    assert any(a.get("family-names") == "Kulaga" for a in cff["authors"])


def test_readme_bibtex_names_the_shipped_version():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    entry = re.search(r"```bibtex\n(@software\{.*?\n\})\n```", readme, re.S)
    assert entry, "the README's Citing section has no @software entry"
    assert {m for m in re.findall(r"version\s*=\s*\{([^}]+)\}", entry.group(1))} == manifest_versions()
