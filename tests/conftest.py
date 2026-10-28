"""Shared test setup: no test reads or writes the developer's own manuscript-skills folders (settings.yaml and the
user's venue catalogue beside it, and the texts kept across runs); a test that needs one sets its own."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _own_config_folder(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CONFIG", str(tmp_path_factory.mktemp("manuscript-skills-config")))
    # Nor the texts kept across runs (source_cache.py): a test that reads a source sees only what it put there.
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CACHE", str(tmp_path_factory.mktemp("manuscript-skills-cache")))
