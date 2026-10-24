"""Revision marks and mark-people, 0.19: who counts as a person, where the config is, what a survey can read
without git, the ids other skills produce, paragraphs as blocks, and a PDF build that only ever replaces or
deletes a PDF it wrote. No TeX is run: typeset.py runs against tests/fakes/fake-typeset."""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "manuscript-revision-marks" / "scripts"
RM, TS = SCRIPTS / "rev_marks.py", SCRIPTS / "typeset.py"
PEOPLE = ROOT / "skills" / "manuscript-mark-people" / "scripts" / "people.py"
FAKE = ROOT / "tests" / "fakes" / "fake-typeset"
PY = sys.executable


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rm = load("rev_marks", RM)
people = load("people", PEOPLE)


def run(script: Path, *args, env: dict | None = None) -> subprocess.CompletedProcess:
    e = dict(os.environ)
    for k, v in (env or {}).items():
        if v is None:
            e.pop(k, None)
        else:
            e[k] = str(v)
    return subprocess.run([PY, str(script), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                          env=e, check=False)


def git(repo: Path, *args: str, name: str = "Anna Smith", email: str = "anna.smith@example.org") -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email, "GIT_COMMITTER_NAME": name,
           "GIT_COMMITTER_EMAIL": email, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


# --- people.py: a co-author's first name is not an agent ---------------------------------------------------

AGENTS = people.rm.People(agents=people.rm.agent_list())


@pytest.mark.parametrize(("name", "email"), [
    ("Devin Patel", "devin.patel@uni.edu"), ("Yi Zhang", "yi@uni.cn"), ("Mark Talbot", "talbot@uni.edu"),
    ("Luna Garcia", "luna@lab.org"), ("Phi Nguyen", "phi.nguyen@uni.edu"), ("Gemma Smith", "gemma@uni.edu"),
])
def test_a_git_author_with_an_ordinary_address_is_a_person(name, email):
    assert not people.is_agent(AGENTS, name, email, person=True)


@pytest.mark.parametrize(("name", "email"), [
    ("Claude", "noreply@anthropic.com"), ("Claude Opus 5.5", "noreply@anthropic.com"), ("codex", "codex@openai.com"),
    ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"),
    ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com"),
    ("Copilot", "198982749+Copilot@users.noreply.github.com"), ("Lab Bot", "lab-bot@example.org"),
    ("Release", "bot@example.org"), ("Cursor Agent", "cursoragent@cursor.com"),
])
def test_real_agents_stay_agents_even_as_git_authors(name, email):
    assert people.is_agent(AGENTS, name, email, person=True)


def test_only_the_full_name_the_address_and_the_login_are_matched():
    assert not people.is_agent(AGENTS, "Devin Patel")  # one word of the name never decides
    assert not people.is_agent(AGENTS, "Mark Talbot", "talbot@uni.edu")  # *bot@* no longer takes talbot@
    assert people.is_agent(AGENTS, "Devin")  # a bare agent name with no evidence of a person
    assert people.is_agent(AGENTS, "Someone", "yi@uni.cn")  # an address that is an agent's, nothing else
    assert not people.is_agent(AGENTS, "Someone", "yi@uni.cn", person=True)


@pytest.fixture
def team(tmp_path: Path) -> Path:
    """Authors whose names are also agents' names, and real agents, in one repository."""
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "paper.md").write_text(
        "---\ntitle: T\nauthors:\n  - Anna Smith\n  - Devin Patel\n  - Yi Zhang\n---\n\n"
        "<!-- @rev C1 rounds=1 by=anna:2026-10-01 -->\nOne.\n<!-- @/rev C1 -->\n\n"
        "<!-- @rev C2 rounds=1 by=devin:2026-10-02 -->\nTwo.\n<!-- @/rev C2 -->\n\n"
        "<!-- @rev C3 rounds=1 by=claude:2026-10-03 -->\nThree.\n<!-- @/rev C3 -->\n", encoding="utf-8")
    git(tmp_path, "add", "paper.md")
    git(tmp_path, "commit", "-q", "-m", "Draft\n\nCo-authored-by: Claude <noreply@anthropic.com>")
    for name, email in (("Devin Patel", "devin@uni.edu"), ("Yi Zhang", "yi@uni.cn"), ("Mark Talbot", "talbot@uni.edu"),
                        ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"),
                        ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com"),
                        ("codex", "codex@openai.com")):
        git(tmp_path, "commit", "-q", "--allow-empty", "-m", "x", name=name, email=email)
    return tmp_path


def test_name_matches_are_people_listed_apart_and_never_preselected(team: Path) -> None:
    s = people.survey(team)
    kinds = {i.name: i.kind for i in s.identities}
    assert {kinds[n] for n in ("Anna Smith", "Devin Patel", "Yi Zhang", "Mark Talbot")} == {"person"}
    assert {kinds[n] for n in ("Claude", "dependabot[bot]", "github-actions[bot]", "codex")} == {"agent"}
    devin = next(i for i in s.identities if i.name == "Devin Patel")
    assert devin.agent_words == ["devin"] and devin.ambiguous == {"devin"} and devin.handles == {"devin"}
    assert s.preselected() == ["anna"]  # signs, commits, listed; devin's handle is also an agent's name
    out = people.report(s)
    named = out[out.index("PEOPLE WHOSE NAME MATCHES AN AGENT NAME"):out.index("AGENTS (not proposed)")]
    assert "Devin Patel" in named and "Yi Zhang" in named and "Mark Talbot" not in named
    assert "Pre-selected (signs revision marks, commits in git and is a listed author): anna" in out
    assert "devin (Devin Patel signs marks as devin" in out and "devin is also an agent's name" in out
    assert "Nothing waits on it" in out and s.agent_handles == ["claude"]


# --- people.py: the config revision marks reads, and no git ------------------------------------------------


def test_the_nearest_config_is_read_and_written_as_rev_marks_finds_it(team: Path) -> None:
    (team / "rev-marks.toml").write_text('humans = ["zed"]\n', encoding="utf-8")
    sub = team / "paper"
    sub.mkdir()
    (sub / "draft.md").write_text("<!-- @rev C1 rounds=1 by=robi:2026-10-01 -->\nX.\n<!-- @/rev C1 -->\n",
                                  encoding="utf-8")
    (sub / "rev-marks.toml").write_text('# the paper\'s own\nhumans = ["robi"]\n', encoding="utf-8")
    s = people.survey(sub / "draft.md")
    assert s.config == (sub / "rev-marks.toml").resolve() and "robi" not in s.unclear
    r = run(PEOPLE, sub / "draft.md", "--write", "--confirm", "anna")
    assert r.returncode == 0, r.stderr
    assert tomllib.loads((sub / "rev-marks.toml").read_text(encoding="utf-8"))["humans"] == ["robi", "anna"]
    assert tomllib.loads((team / "rev-marks.toml").read_text(encoding="utf-8"))["humans"] == ["zed"]
    assert rm.find_config(sub / "draft.md") == (sub / "rev-marks.toml").resolve()
    other = team / "elsewhere" / "people.toml"
    assert run(PEOPLE, team, "--config", other, "--write", "--confirm", "tom", "--force-name").returncode == 0
    assert tomllib.loads(other.read_text(encoding="utf-8")) == {"humans": ["tom"]}


def test_a_malformed_config_is_exit_2_as_in_rev_marks(team: Path) -> None:
    (team / "rev-marks.toml").write_text("humans = [\n", encoding="utf-8")
    r = run(PEOPLE, team)
    assert r.returncode == 2 and "not TOML" in r.stderr, r.stderr
    assert run(RM, "lint", team / "paper.md").returncode == 2
    assert (team / "rev-marks.toml").read_text(encoding="utf-8") == "humans = [\n"


def test_without_git_the_marks_and_author_lists_are_read_and_a_confirmed_name_written(tmp_path: Path) -> None:
    (tmp_path / "paper.md").write_text("---\nauthors:\n  - Tom Okafor\n---\n\n"
                                       "<!-- @rev C1 rounds=1 by=grok:2026-10-01 -->\nX.\n<!-- @/rev C1 -->\n",
                                       encoding="utf-8")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "x.md").write_text("<!-- @rev C9 rounds=1 by=ghost:2026-10-01 -->\nY.\n"
                                               "<!-- @/rev C9 -->\n", encoding="utf-8")
    r = run(PEOPLE, tmp_path / "paper.md")
    assert r.returncode == 0, r.stderr
    assert "Git history: not read: not a git repository; the by= handles and author lists were" in r.stdout
    assert "Tom Okafor" in r.stdout and "grok" in r.stdout and "ghost" not in r.stdout
    r = run(PEOPLE, tmp_path / "paper.md", "--write", "--confirm", "tom")
    assert r.returncode == 0, r.stderr
    assert tomllib.loads((tmp_path / "rev-marks.toml").read_text(encoding="utf-8"))["humans"] == ["tom"]
    r = run(PEOPLE, tmp_path / "paper.md", env={"PATH": tmp_path / "nothing"})  # git absent too
    assert r.returncode == 0 and "git is not installed" in r.stdout, r.stdout + r.stderr


def test_an_accept_all_confirms_the_handle_then_the_bump_reads_as_reviewed(tmp_path: Path) -> None:
    """The authors say Tom approved every passage: his handle is written in the same step as the rounds."""
    doc = tmp_path / "paper.md"
    doc.write_text("<!-- @rev R1.2 rounds=1 by=claude:2026-10-01 -->\nX.\n<!-- @/rev R1.2 -->\n", encoding="utf-8")
    (tmp_path / "rev-marks.toml").write_text('humans = ["anna"]\n', encoding="utf-8")
    assert run(PEOPLE, doc, "--write", "--confirm", "tom").returncode == 2  # not found: a typo is never written
    assert run(PEOPLE, doc, "--write", "--confirm", "tom", "--force-name").returncode == 0
    assert run(RM, "bump", doc, "R1.2", "--by", "tom").returncode == 0
    r = run(RM, "report", doc, "--unreviewed")
    assert "UNREVIEWED (0 of 1 segments" in r.stdout, r.stdout


# --- rev_marks.py: ids, paragraphs, labels, files it cannot read ---------------------------------------------


@pytest.mark.parametrize(("sid", "comment"), [("C3a", "C3"), ("R1.4b", "R1.4"), ("Ed.P1", "Ed.P1"), ("Ed1", "Ed1"),
                                              ("R2.P3b", "R2.P3"), ("IC-1", "IC-1"), ("R1.Minor3", "R1.Minor3"),
                                              ("IC-1.20261024", "IC-1.20261024")])
def test_ids_from_the_ledger_and_from_findings_are_marks(sid, comment):
    found = rm.parse(f"<!-- @rev {sid} rounds=1 by=anna:2026-10-01 -->\nText.\n<!-- @/rev {sid} -->\n")
    assert not found.issues, found.issues
    assert found.segments[0].attributes.comment_id == comment


def test_a_bad_id_is_explained_in_words():
    found = rm.parse("<!-- @rev Ed rounds=1 by=anna:2026-10-01 -->\nText.\n<!-- @/rev Ed -->\n")
    (issue, *_) = found.errors
    assert issue.code == rm.Code.BAD_ID and "with a digit somewhere" in issue.message and "(?=" not in issue.message


DOC = ("---\ntitle: A paper about things\nauthor: Anna Smith\n---\n\n"
       "# The title\n\n"
       "A first paragraph, on two\nlines of prose.\n\n"
       "![A figure caption that is alt text](fig1.png){#fig:one width=80%}\n\n"
       "- a list item\n- another item\n\n"
       "| a | b |\n|---|---|\n| 1 | 2 |\n\n"
       "## Methods\nText right under a heading.\n\n"
       "<!-- @rev C1 rounds=1 by=anna:2026-10-01 -->\nRewritten.\n<!-- @/rev C1 -->\n")


def test_blind_spots_count_paragraphs_not_lines_and_skip_front_matter_and_figures():
    found = rm.parse(DOC)
    ps = rm.paragraphs(found)
    assert [p.lines for p in ps] == [(8, 9), (13, 14), (16, 18), (21,), (24,)]  # a table's ruler is no prose
    assert [p.text for p in ps][0] == "A first paragraph, on two lines of prose."
    assert [p.covered for p in ps] == [False, False, False, False, True]
    assert rm.totals(found)["paragraphs"] == 5 and rm.totals(found)["blind spots"] == 4
    assert "title: A paper" not in " ".join(p.text for p in ps) and "fig1.png" not in " ".join(p.text for p in ps)


def test_a_mark_inside_a_paragraph_covers_the_whole_paragraph():
    found = rm.parse("Line one of a paragraph.\n<!-- @rev C1 rounds=1 by=grok:2026-10-01 -->\nLine two.\n"
                     "<!-- @/rev C1 -->\nLine three.\n\nAnother paragraph.\n")
    assert [(p.lines, p.covered) for p in rm.paragraphs(found)] == [((1, 3, 5), True), ((7,), False)]


def test_outputs_say_rounds_by_not_reviewers(tmp_path: Path):
    src, heat = tmp_path / "doc.md", tmp_path / "doc.heatmap.html"
    src.write_text(DOC, encoding="utf-8")
    r = run(RM, "report", src, "--blind", "--html", heat)
    assert r.returncode == 0, r.stderr
    assert "ROUNDS BY" in r.stdout and "REVIEWERS" not in r.stdout
    assert "A round is one pass over a passage, writing it or approving it" in r.stdout
    assert "BLIND SPOTS (4 of 5 paragraphs no round, writing or approval, has touched)" in r.stdout
    page = heat.read_text(encoding="utf-8")
    assert "<th>Written or approved by</th>" in page and "Reviewers" not in page
    assert "A round is one pass over a passage: writing it or approving it." in page
    bad = tmp_path / "bad.md"
    bad.write_text("<!-- @rev C1 rounds=2 by=anna -->\nX.\n<!-- @/rev C1 -->\n", encoding="utf-8")
    r = run(RM, "lint", bad)
    assert "by= entry 'anna' is not name:YYYY-MM-DD" in r.stderr and "reviewer" not in r.stderr, r.stderr


def test_a_pdf_upload_cannot_be_read_and_says_what_to_check(tmp_path: Path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7\n\xff\xfe binary")
    r = run(RM, "report", pdf)
    assert r.returncode == 3 and "is a PDF" in r.stderr and "clean twin" in r.stderr and "@rev" in r.stderr


def test_strip_out_writes_a_clean_copy_in_a_new_folder_and_never_over_the_master(tmp_path: Path):
    src = tmp_path / "paper.md"
    src.write_text(DOC, encoding="utf-8")
    out = tmp_path / "run" / "manuscript-improve" / "clean" / "working.md"
    r = run(RM, "strip", src, "--out", out)
    assert r.returncode == 0 and "@rev" not in out.read_text(encoding="utf-8"), r.stderr
    assert run(RM, "strip", src, "--out", src).returncode == 2 and src.read_text(encoding="utf-8") == DOC


# --- typeset.py: only its own PDFs ---------------------------------------------------------------------------

CLEAN = "# A title\n\nA sentence.\n"
FAKE_VARS = ("FAKE_PANDOC_RC", "FAKE_TECTONIC_PAGES", "FAKE_TECTONIC_MISSING", "FAKE_TECTONIC_OLD_LOG",
             "FAKE_TECTONIC_RC", "FAKE_TECTONIC_NOPDF", "TYPESET_PANDOC", "TYPESET_TECTONIC", "TECTONIC_CACHE_DIR")
BUNDLE_FAILURE = '''import sys
sys.stderr.write("note: connecting to https://relay.fullyjustified.net/default_bundle_v33.tar\\n"
                 "error: failed to retrieve the default bundle\\n"
                 "caused by: error sending request for url: dns error: failed to lookup address information\\n")
sys.exit(1)
'''


def wrapper(path: Path, target: Path = FAKE) -> None:
    path.write_text(f"#!/bin/sh\nexec '{PY}' '{target}' \"$0\" \"$@\"\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def T(tmp_path: Path):
    class T:
        pass
    t = T()
    t.dir, t.bin, t.fake = (tmp_path / n for n in ("doc", "bin", "fake"))
    for d in (t.dir, t.bin, t.fake):
        d.mkdir()
    for role in ("pandoc", "tectonic"):
        wrapper(t.bin / role)
    t.env = {"PATH": t.bin, "FAKE_TYPESET": t.fake, **{k: None for k in FAKE_VARS}}
    t.ts = lambda *args, **env: run(TS, *args, env={**t.env, **env})
    return t


pytestmark_posix = pytest.mark.skipif(os.name == "nt", reason="the fake binaries are POSIX shell wrappers")


@pytestmark_posix
def test_a_pdf_this_tool_wrote_has_a_record_and_is_replaced_and_one_it_did_not_is_never_touched(T):
    src, pdf = T.dir / "paper.md", T.dir / "paper.pdf"
    src.write_text(CLEAN, encoding="utf-8")
    assert T.ts("pdf", src).returncode == 0
    record = json.loads((T.dir / "paper.pdf.typeset.json").read_text(encoding="utf-8"))
    assert record["pdf"] == "paper.pdf" and record["for"] == "paper.md" and len(record["pdf_sha256"]) == 64
    assert T.ts("pdf", src).returncode == 0  # its own PDF, unchanged since: replaced
    pdf.write_bytes(b"%PDF the authors rebuilt it")  # changed since: no longer this tool's
    r = T.ts("pdf", src, FAKE_TECTONIC_RC=1)
    assert r.returncode == 2 and "did not write it" in r.stderr, r.stderr
    assert pdf.read_bytes() == b"%PDF the authors rebuilt it"
    r = T.ts("pdf", src, "--out", T.dir / "paper.typeset.pdf")
    assert r.returncode == 0 and (T.dir / "paper.typeset.pdf").is_file(), r.stderr


@pytestmark_posix
def test_a_foreign_log_is_kept_and_the_builds_log_goes_beside_it(T):
    src = T.dir / "main.tex"
    src.write_text("\\documentclass{article}\n\\begin{document}\nX.\n\\end{document}\n", encoding="utf-8")
    (T.dir / "main.log").write_text("This is pdfTeX, the authors' own log\n", encoding="utf-8")
    r = T.ts("pdf", src)
    assert r.returncode == 0, r.stderr
    assert (T.dir / "main.log").read_text(encoding="utf-8") == "This is pdfTeX, the authors' own log\n"
    assert (T.dir / "main.typeset.log").is_file() and "main.typeset.log" in r.stderr


@pytestmark_posix
def test_a_refused_build_and_an_absent_binary_leave_this_tools_pdf_and_say_so(T):
    src, pdf = T.dir / "paper.md", T.dir / "paper.pdf"
    src.write_text(CLEAN, encoding="utf-8")
    assert T.ts("pdf", src).returncode == 0
    built = pdf.read_bytes()
    src.write_text("<!-- @rev C1 rounds=1 by=grok:2026-10-01 -->\nNew.\n<!-- @/rev C1 -->\n", encoding="utf-8")
    r = T.ts("pdf", src)  # the twin is missing: refused before it starts
    assert r.returncode == 1 and "left as it is and may not match" in r.stderr and pdf.read_bytes() == built
    src.write_text(CLEAN, encoding="utf-8")
    (T.bin / "tectonic").unlink()
    r = T.ts("pdf", src, "--cap", "8")
    assert r.returncode == 3 and pdf.read_bytes() == built, r.stderr
    assert r.stderr.count("page count not measured: tectonic absent") == 1
    assert "conda install -c conda-forge tectonic" in r.stderr and "brew install tectonic" in r.stderr
    assert "github.com/tectonic-typesetting/tectonic/releases" in r.stderr and "pandoc:" not in r.stderr
    assert "left as it is and may not match" in r.stderr
    (T.bin / "pandoc").unlink()
    r = T.ts("pdf", src)
    assert "winget install --id JohnMacFarlane.Pandoc" in r.stderr and "choco install pandoc" in r.stderr


@pytestmark_posix
def test_a_bundle_download_failure_could_not_run_and_is_no_finding(T):
    src, pdf = T.dir / "paper.md", T.dir / "paper.pdf"
    src.write_text(CLEAN, encoding="utf-8")
    assert T.ts("pdf", src).returncode == 0
    built = pdf.read_bytes()
    offline = T.fake / "offline.py"
    offline.write_text(BUNDLE_FAILURE, encoding="utf-8")
    wrapper(T.bin / "tectonic", offline)
    r = T.ts("pdf", src, "--cap", "8")
    assert r.returncode == 3 and "could not download its TeX bundle" in r.stderr, r.stderr
    assert "page count not measured" in r.stderr and "deleted" not in r.stderr and pdf.read_bytes() == built


@pytestmark_posix
def test_the_draft_never_takes_the_submission_pdf_and_out_is_always_a_pdf(T):
    (T.dir / ".git").mkdir()
    src = T.dir / "paper.md"
    src.write_text("<!-- @rev C1 rounds=1 by=grok:2026-10-01 -->\nX.\n<!-- @/rev C1 -->\n", encoding="utf-8")
    r = T.ts("pdf", src, "--draft", "--out", T.dir / "paper.pdf")
    assert r.returncode == 2 and "submission PDF" in r.stderr and not (T.dir / "paper.pdf").exists(), r.stderr
    r = T.ts("pdf", src, "--out", T.dir / "paper.clean.md")
    assert r.returncode == 2 and "not a .pdf" in r.stderr, r.stderr
    r = T.ts("pdf", src, "--draft")
    assert r.returncode == 0 and (T.dir / "paper.draft.pdf.typeset.json").is_file(), r.stderr
    (T.dir / "paper.draft.pdf").write_bytes(b"%PDF a hand-made draft")
    assert T.ts("pdf", src, "--draft").returncode == 2
    assert (T.dir / "paper.draft.pdf").read_bytes() == b"%PDF a hand-made draft"
