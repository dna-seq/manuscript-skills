"""Offline tests for manuscript-mark-people/scripts/people.py on a throwaway git repository. Run with
`uv run pytest`."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PEOPLE = ROOT / "skills" / "manuscript-mark-people" / "scripts" / "people.py"

spec = importlib.util.spec_from_file_location("people", PEOPLE)
people = importlib.util.module_from_spec(spec)
sys.modules["people"] = people
spec.loader.exec_module(people)

PAPER = ("---\ntitle: A paper\nauthors:\n  - Tom Example\n---\n\n"
         "<!-- @rev C1 rounds=2 by=claude:2026-10-01,anna:2026-10-02 -->\nText.\n<!-- @/rev C1 -->\n\n"
         "<!-- @rev C2 rounds=1 by=robi:2026-10-03 -->\nMore.\n<!-- @/rev C2 -->\n")
TEX = "\\documentclass{article}\n\\author{Maria Lopez\\thanks{Lab} \\and Anonymous}\n\\begin{document}\nX.\n\\end{document}\n"


def git(repo: Path, *args: str, name: str = "Anna Smith", email: str = "anna.smith@example.org") -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_NAME": name,
           "GIT_COMMITTER_EMAIL": email, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "paper.md").write_text(PAPER, encoding="utf-8")
    (tmp_path / "main.tex").write_text(TEX, encoding="utf-8")
    (tmp_path / "evals" / "fixtures").mkdir(parents=True)
    (tmp_path / "evals" / "fixtures" / "fake.tex").write_text("\\author{Jana Fixture}\n", encoding="utf-8")
    git(tmp_path, "add", "paper.md", "main.tex", "evals/fixtures/fake.tex")
    git(tmp_path, "commit", "-q", "-m", "Draft\n\nCo-authored-by: Claude Opus 5.5 <noreply@anthropic.com>")
    (tmp_path / "notes.md").write_text("notes\n", encoding="utf-8")
    git(tmp_path, "add", "notes.md")
    git(tmp_path, "commit", "-q", "-m", "Bump deps", name="renovate[bot]",
        email="29139614+renovate[bot]@users.noreply.github.com")
    git(tmp_path, "commit", "-q", "--allow-empty", "-m", "Notes", name="Newton Winter",
        email="76408211+anna.smith@users.noreply.github.com")
    return tmp_path


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(PEOPLE), *args], capture_output=True, text=True, check=False)


def test_people_agents_and_unclear_handles_are_told_apart(repo: Path) -> None:
    s = people.survey(repo)
    kinds = {i.name: i.kind for i in s.identities}
    assert kinds["Anna Smith"] == "person" and kinds["Tom Example"] == "person" and kinds["Maria Lopez"] == "person"
    assert kinds["Claude Opus 5.5"] == "agent" and kinds["renovate[bot]"] == "agent"
    assert "Jana Fixture" not in kinds and "Anonymous" not in kinds  # test data and placeholders
    assert "Newton Winter" not in kinds  # the no-reply login anna.smith is Anna Smith
    anna = next(i for i in s.identities if i.name == "Anna Smith")
    assert anna.handles == {"anna"} and "also named Newton Winter" in anna.evidence
    assert s.agent_handles == ["claude"] and s.unclear == ["robi"]
    assert s.proposal() == ["anna", "maria", "tom"]
    assert s.preselected() == []  # anna signs and commits, but no author list names her


def test_the_report_proposes_and_writes_nothing(repo: Path) -> None:
    r = run(str(repo))
    assert r.returncode == 0, r.stderr
    question = r.stdout[r.stdout.index("ONE QUESTION FOR THE AUTHORS"):]
    assert "Nothing waits on it" in question and "Pre-selected (signs revision marks, commits in git and is a" \
        " listed author): none" in question
    for handle in ("anna (Anna Smith signs marks as anna", "maria (Maria Lopez has signed no mark yet",
                   "tom (Tom Example has signed no mark yet", "robi (unexplained by= handle: paper.md:"):
        assert handle in question, question
    assert not (repo / "rev-marks.toml").exists()


def test_write_needs_confirmed_names_and_merges_without_dropping(repo: Path) -> None:
    assert run(str(repo), "--write").returncode == 2
    assert run(str(repo), "--write", "--confirm", "anah").returncode == 2  # a typo is not written
    (repo / "rev-marks.toml").write_text('# ours\nunknown = "agent"\nhumans = [\n  "zed",\n]\nagents = ["lab-bot"]\n')
    r = run(str(repo / "evals"), "--write", "--confirm", "anna,Tom")
    assert r.returncode == 0, r.stderr
    text = (repo / "rev-marks.toml").read_text()
    data = tomllib.loads(text)
    assert data == {"unknown": "agent", "humans": ["zed", "anna", "tom"], "agents": ["lab-bot"]}
    assert text.startswith("# ours\n")
    assert run(str(repo), "--write", "--confirm", "robi", "--force-name").returncode == 0
    assert tomllib.loads((repo / "rev-marks.toml").read_text())["humans"][-1] == "robi"


def test_a_listed_handle_is_no_longer_unclear_and_outside_git_it_reads_what_it_can(repo: Path, tmp_path_factory) -> None:
    (repo / "rev-marks.toml").write_text('humans = ["robi"]\n')
    assert people.survey(repo).unclear == []
    nogit = tmp_path_factory.mktemp("nogit")
    (nogit / "paper.md").write_text(PAPER, encoding="utf-8")
    r = run(str(nogit))
    assert r.returncode == 0 and "Git history: not read: not a git repository" in r.stdout, r.stdout
    assert "Tom Example" in r.stdout and "robi" in r.stdout
    assert run(str(nogit / "missing")).returncode == 3


def test_github_bot_pattern_does_not_swallow_logins_ending_in_b_o_or_t() -> None:
    p = people.rm.People(agents=people.rm.agent_list())
    assert not people.is_agent(p, "winternewt", "76408211+winternewt@users.noreply.github.com")
    assert people.is_agent(p, "dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com")


# --- a Doc's commenters: mapped to the paper's people, aliases kept ------------------------------------------


def test_a_commenter_maps_to_an_author_by_full_name_or_initials_else_gets_a_new_handle(repo: Path) -> None:
    s = people.survey(repo / "paper.md")
    pp = people.rm.load_people(repo / "paper.md")
    m = people.resolve("Tom Example", pp, s.identities)
    assert (m.handle, m.rule) == ("tomexample", "author")
    m = people.resolve("M. Lop", pp, s.identities)  # Google shows a shortened name: initial and surname start
    assert (m.handle, m.rule, m.via) == ("marialopez", "initials", "Maria Lopez")
    m = people.resolve("A Smith", pp, s.identities)  # Anna Smith signs by=anna: her existing handle wins
    assert m.rule == "initials" and m.handle in ("anna", "annasmith")
    m = people.resolve("Petra Outside", pp, s.identities)  # a reviewer who is not on the paper
    assert (m.handle, m.rule) == ("petraoutside", "new")
    assert people.resolve("Sol", pp, s.identities).handle == "sol2"  # never an agent's name


def test_recorded_commenters_become_people_and_their_names_aliases(repo: Path) -> None:
    config = repo / "rev-marks.toml"
    config.write_text('# kept\nhumans = ["anna"]\nagents = ["lab-bot"]\n', encoding="utf-8")
    s = people.survey(repo / "paper.md")
    pp = people.rm.load_people(repo / "paper.md")
    matches = [people.resolve(n, pp, s.identities) for n in ("M. Lop", "Maria Lopez", "Petra Outside")]
    humans, aliases = people.record_people(config, matches)
    data = tomllib.loads(config.read_text(encoding="utf-8"))
    assert data["humans"] == ["anna", "marialopez", "petraoutside"] and data["agents"] == ["lab-bot"]
    assert data["aliases"] == {"marialopez": ["M. Lop", "Maria Lopez"], "petraoutside": ["Petra Outside"]}
    assert "# kept" in config.read_text(encoding="utf-8")
    pp = people.rm.load_people(repo / "paper.md")  # the next pull finds them by alias
    assert people.resolve("M Lop", pp, s.identities).rule == "alias"
    assert pp.known("marialopez") == people.rm.Kind.HUMAN
    people.write_aliases(config, {"marialopez": ["m. lop", "Dr Maria Lopez"]})  # nothing twice, nothing lost
    assert tomllib.loads(config.read_text())["aliases"]["marialopez"] == ["M. Lop", "Maria Lopez", "Dr Maria Lopez"]


def test_an_authors_line_lists_people_and_a_shortened_name_fits_a_surname_first_author(tmp_path: Path) -> None:
    """A Markdown manuscript's own author line, surname first with affiliation marks, as many drafts write it."""
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "paper.md").write_text(
        "# A paper\n\n**Authors:** Lopez Maria^1,2,†^, Example Tom^3^, Outside Petra^1,\\*^\n\n## Abstract\n\nText.\n",
        encoding="utf-8")
    git(tmp_path, "add", "paper.md")
    git(tmp_path, "commit", "-q", "-m", "Draft", name="Maria Lopez", email="maria@example.org")  # git: given name first
    s = people.survey(tmp_path / "paper.md")
    listed = {i.name for i in s.identities if i.listed}
    assert {"Lopez Maria", "Example Tom", "Outside Petra"} <= listed
    pp = people.rm.load_people(tmp_path / "paper.md")
    m = people.resolve("M Lop", pp, s.identities)  # one person in two orders, not two candidates
    assert m.rule == "initials" and m.via in ("Lopez Maria", "Maria Lopez")
    assert m.handle == "marialopez"  # git's order: the handle she would sign with
    assert people.resolve("P Out", pp, s.identities).via == "Outside Petra"
