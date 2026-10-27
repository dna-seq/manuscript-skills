"""Shared test setup: no test reads or writes the developer's own manuscript-skills folder (settings.yaml and the
user's venue catalogue beside it); a test that needs a configuration folder sets its own."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _own_config_folder(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CONFIG", str(tmp_path_factory.mktemp("manuscript-skills-config")))
