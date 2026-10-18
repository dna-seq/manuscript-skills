"""manuscript-revision-marks/scripts/typeset.py against tests/fakes/fake-typeset: no TeX is run.

A Markdown source goes through pandoc with the ported arguments and DejaVu fonts to `<stem>.tex`, then
tectonic; a LaTeX source goes to tectonic alone. A marked source is built from its clean twin only when
the twin is current; marks that do not lint are refused. A failed render deletes the stale PDF and says
so. Missing glyphs are one warning each with the code point, exit 1 only under --strict. Pages over the
cap are exit 1; pages unknown under a cap are exit 3. An absent binary, or a variable naming none, is
exit 3 naming it. The caller's TECTONIC_CACHE_DIR reaches tectonic. A hand-written file is never
overwritten. `md` writes the reading twin with the abstract first."""
from __future__ import annotations

import json
import os
import stat

import pytest
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "manuscript-revision-marks" / "scripts"
TS = SCRIPTS / "typeset.py"
RM = SCRIPTS / "rev_marks.py"
FAKE = ROOT / "tests" / "fakes" / "fake-typeset"
PY = sys.executable


@dataclass
class Result:
    rc: int
    out: str


def py(script, *args, env: dict | None = None) -> Result:
    """Run a script under this interpreter, stdout and stderr together; env is laid over the current
    environment, a None value unsets the key."""
    e = dict(os.environ)
    for k, v in (env or {}).items():
        if v is None:
            e.pop(k, None)
        else:
            e[k] = str(v)
    p = subprocess.run([PY, str(script), *map(str, args)], env=e, text=True, check=False,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return Result(p.returncode, p.stdout)
FAKE_VARS = ("FAKE_PANDOC_RC", "FAKE_TECTONIC_PAGES", "FAKE_TECTONIC_MISSING", "FAKE_TECTONIC_OLD_LOG",
             "FAKE_TECTONIC_RC", "FAKE_TECTONIC_NOPDF", "TYPESET_PANDOC", "TYPESET_TECTONIC", "TECTONIC_CACHE_DIR")
MARKED = ("# A title\n\n<!-- @rev C1 rounds=1 by=owner:2026-10-10 -->\nA sentence at or above, ≥ one.\n"
          "<!-- @/rev C1 -->\n\nAnother paragraph.\n")
CLEAN = "# A title\n\nA sentence at or above, ≥ one.\n\nAnother paragraph.\n"


def wrapper(path):
    path.write_text(f"#!/bin/sh\nexec '{PY}' '{FAKE}' \"$0\" \"$@\"\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def T(tmp_path):
    class T:
        pass
    t = T()
    t.dir, t.bin, t.fake, t.empty = (tmp_path / n for n in ("doc", "bin", "fake", "empty"))
    for d in (t.dir, t.bin, t.fake, t.empty):
        d.mkdir()
    for role in ("pandoc", "tectonic"):
        wrapper(t.bin / role)
    t.env = {"PATH": t.bin, "FAKE_TYPESET": t.fake, **{k: None for k in FAKE_VARS}}

    def ts(*args, **env):
        return py(TS, *args, env={**t.env, **env})

    def calls(role=None):
        log = t.fake / "calls.log"
        lines = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
        return [c for c in lines if role is None or c["role"] == role]

    t.ts, t.calls = ts, calls
    return t


def test_markdown_goes_through_pandoc_then_tectonic(T):
    src = T.dir / "paper.md"
    src.write_text(CLEAN)
    r = T.ts("pdf", src)
    assert r.rc == 0, r.out
    tex, pdf = T.dir / "paper.tex", T.dir / "paper.pdf"
    assert tex.read_text().startswith("% typeset: generated from paper.md;")
    assert "% fake markdown to latex\n" + CLEAN in tex.read_text()
    assert pdf.read_text().startswith("%PDF fake\n% typeset: generated from paper.md;")
    assert (T.dir / "paper.log").is_file() and "1 page" in r.out
    (pandoc,), (tectonic,) = T.calls("pandoc"), T.calls("tectonic")
    for arg in ("--standalone", "--wrap=preserve", "--shift-heading-level-by=-1", "--from=markdown",
                "--to=latex", "--variable=mainfont=DejaVuSerif", "--variable=monofont=DejaVuSansMono"):
        assert arg in pandoc["args"], arg
    assert pandoc["args"][-1] == str(src.resolve())
    assert tectonic["args"][:1] == ["--keep-logs"] and tectonic["args"][-1] == "paper.tex"
    assert tectonic["cwd"] == str(T.dir)
    assert [p.name for p in T.dir.iterdir() if p.name.startswith(".typeset-")] == []
    assert T.ts("pdf", src).rc == 0  # its own .tex is rewritten


def test_a_venue_template_reaches_pandoc_and_only_for_markdown(T):
    """--template goes to pandoc by its absolute path, after the font variables; a missing one, or one
    given with a .tex source, is refused before anything runs"""
    src, tpl = T.dir / "paper.md", T.dir / "venue.latex"
    src.write_text(CLEAN)
    tpl.write_text("$body$\n")
    r = T.ts("pdf", src, "--template", tpl)
    assert r.rc == 0, r.out
    (pandoc,) = T.calls("pandoc")
    assert f"--template={tpl.resolve()}" in pandoc["args"], pandoc["args"]
    assert pandoc["args"][-1] == str(src.resolve())
    r = T.ts("pdf", src, "--template", T.dir / "none.latex")
    assert r.rc == 2 and "is not a file" in r.out, r.out
    tex = T.dir / "other.tex"
    tex.write_text("\\documentclass{article}\n")
    r = T.ts("pdf", tex, "--template", tpl)
    assert r.rc == 2 and "for a .md source" in r.out, r.out
    assert len(T.calls()) == 2  # only the first build's pandoc and tectonic


def test_a_marked_markdown_source_builds_only_from_a_current_twin(T):
    src, twin, pdf = T.dir / "paper.md", T.dir / "paper.clean.md", T.dir / "paper.pdf"
    src.write_text(MARKED)
    pdf.write_text("an old build")
    r = T.ts("pdf", src)
    assert r.rc == 1 and "paper.clean.md is missing" in r.out and "rev_marks.py strip" in r.out, r.out
    assert "left as it is" in r.out and pdf.read_text() == "an old build"
    assert T.calls() == [] and not (T.dir / "paper.tex").exists()
    twin.write_text(CLEAN.replace("one", "two"))
    r = T.ts("pdf", src)
    assert r.rc == 1 and "is stale" in r.out and T.calls() == [], r.out
    assert py(RM, "strip", src).rc == 0 and twin.read_text() == CLEAN
    r = T.ts("pdf", src)
    assert r.rc == 0, r.out
    assert T.calls("pandoc")[0]["args"][-1] == str(twin.resolve())
    tex = (T.dir / "paper.tex").read_text()
    assert "@rev" not in tex and CLEAN in tex and tex.startswith("% typeset: generated from paper.md;")
    assert "@rev" not in pdf.read_text() and not (T.dir / "paper.clean.tex").exists()


def test_marks_that_do_not_lint_are_refused_and_examples_are_no_marks(T):
    src = T.dir / "paper.md"
    src.write_text("Text.\n<!-- @rev C1 rounds=1 by=owner:2026-10-10 -->\nMore.\n")
    r = T.ts("pdf", src)
    assert r.rc == 1 and "unclosed" in r.out and "do not lint" in r.out and T.calls() == [], r.out
    src.write_text("Text.\n\n```\n<!-- @rev C1 rounds=1 by=owner:2026-10-10 -->\n```\n")
    assert T.ts("pdf", src).rc == 0
    assert T.calls("pandoc")[0]["args"][-1] == str(src.resolve())


def test_a_latex_source_needs_no_pandoc_and_a_marked_one_builds_from_its_twin(T):
    src, pdf = T.dir / "paper.tex", T.dir / "paper.pdf"
    body = "\\documentclass{article}\n\\begin{document}\nText.\n\\end{document}\n"
    src.write_text(body)
    (T.bin / "pandoc").unlink()
    r = T.ts("pdf", src)
    assert r.rc == 0 and T.calls("pandoc") == [] and pdf.read_text() == "%PDF fake\n" + body, r.out
    src.write_text(body.replace("Text.\n", "% @rev C1 rounds=1 by=owner:2026-10-10\nText.\n% @/rev C1\n"))
    r = T.ts("pdf", src)
    assert r.rc == 1 and "paper.clean.tex is missing" in r.out, r.out
    assert py(RM, "strip", src).rc == 0
    r = T.ts("pdf", src)
    assert r.rc == 0, r.out
    assert T.calls("tectonic")[-1]["args"][-1] == "paper.clean.tex"
    assert pdf.read_text() == "%PDF fake\n" + body and (T.dir / "paper.log").is_file()
    assert not (T.dir / "paper.clean.pdf").exists()


@pytest.mark.parametrize("failure", [{"FAKE_TECTONIC_RC": 1}, {"FAKE_TECTONIC_NOPDF": 1}, {"FAKE_PANDOC_RC": 64}],
                         ids=["tectonic-fails", "tectonic-no-pdf", "pandoc-fails"])
def test_a_failed_render_deletes_the_stale_pdf_and_says_so(T, failure):
    src, pdf = T.dir / "paper.md", T.dir / "paper.pdf"
    src.write_text(CLEAN)
    pdf.write_text("an old build")
    r = T.ts("pdf", src, **failure)
    assert r.rc == 1, r.out
    assert not pdf.exists() and f"deleted {pdf}" in r.out
    if "FAKE_TECTONIC_RC" in failure:
        assert "Undefined control sequence" in r.out  # the log's tail is shown
    r = T.ts("pdf", src, **failure)  # nothing to delete: nothing said of it
    assert r.rc == 1 and "deleted" not in r.out


def test_missing_glyphs_are_warned_with_their_code_points(T):
    src = T.dir / "paper.md"
    src.write_text(CLEAN)
    r = T.ts("pdf", src, FAKE_TECTONIC_MISSING="≥漢≥")
    assert r.rc == 0, r.out
    warned = [x for x in r.out.splitlines() if "missing glyph" in x]
    assert len(warned) == 2
    assert "U+2265 ≥ (2 times)" in warned[0] and "U+6F22 漢 (1 time)" in warned[1]
    assert T.ts("pdf", src, FAKE_TECTONIC_MISSING="≥", FAKE_TECTONIC_OLD_LOG=1).out.count("U+2265 ≥") == 1
    r = T.ts("pdf", "--strict", src, FAKE_TECTONIC_MISSING="漢")
    assert r.rc == 1 and (T.dir / "paper.pdf").is_file(), r.out
    assert T.ts("pdf", "--strict", src).rc == 0


def test_pages_are_measured_against_the_cap(T):
    src, pdf = T.dir / "paper.md", T.dir / "paper.pdf"
    src.write_text(CLEAN)
    r = T.ts("pdf", src, "--cap", "3", FAKE_TECTONIC_PAGES=3)
    assert r.rc == 0 and "3 pages" in r.out, r.out
    r = T.ts("pdf", src, "--cap", "2", FAKE_TECTONIC_PAGES=3)
    assert r.rc == 1 and "has 3 pages, over the cap of 2" in r.out and pdf.is_file(), r.out
    r = T.ts("pdf", src, "--cap", "2", FAKE_TECTONIC_PAGES="none")
    assert r.rc == 3 and "pages unknown" in r.out and "could not be checked" in r.out, r.out
    r = T.ts("pdf", src, FAKE_TECTONIC_PAGES="none")
    assert r.rc == 0 and "pages unknown" in r.out, r.out
    assert T.ts("pdf", src, "--cap", "0").rc == 2


def test_an_absent_binary_could_not_run_and_is_named(T):
    src = T.dir / "paper.md"
    src.write_text(CLEAN)
    r = T.ts("pdf", src, PATH=T.empty)
    assert r.rc == 3 and "pandoc is not on PATH" in r.out and "tectonic is not on PATH" in r.out, r.out
    tex = T.dir / "other.tex"
    tex.write_text("\\documentclass{article}\n")
    r = T.ts("pdf", tex, PATH=T.empty)
    assert r.rc == 3 and "tectonic" in r.out and "pandoc" not in r.out, r.out
    r = T.ts("pdf", src, TYPESET_TECTONIC=T.empty / "tectonic")
    assert r.rc == 3 and "TYPESET_TECTONIC=" in r.out, r.out  # never passed over for the one on PATH
    assert T.calls() == []
    wrapper(T.empty / "pandoc")
    (T.bin / "pandoc").unlink()
    r = T.ts("pdf", src, TYPESET_PANDOC=T.empty / "pandoc")
    assert r.rc == 0 and len(T.calls("pandoc")) == 1, r.out


def test_the_callers_tectonic_cache_dir_reaches_tectonic(T):
    src = T.dir / "paper.md"
    src.write_text(CLEAN)
    assert T.ts("pdf", src, TECTONIC_CACHE_DIR=T.fake / "cache").rc == 0
    assert T.calls("tectonic")[0]["cache"] == str(T.fake / "cache")


def test_out_puts_the_pdf_and_its_log_elsewhere(T):
    src, out = T.dir / "paper.md", T.dir / "build" / "final.pdf"
    src.write_text(CLEAN)
    r = T.ts("pdf", src, "--out", out)
    assert r.rc == 0 and out.is_file() and (T.dir / "build" / "final.log").is_file(), r.out
    assert not (T.dir / "paper.pdf").exists()


def test_a_hand_written_file_is_never_overwritten(T):
    src, tex = T.dir / "paper.md", T.dir / "paper.tex"
    src.write_text(CLEAN)
    tex.write_text("\\documentclass{article}\n% my master\n")
    r = T.ts("pdf", src)
    assert r.rc == 2 and "never overwritten" in r.out and T.calls() == [], r.out
    assert tex.read_text() == "\\documentclass{article}\n% my master\n"
    r = T.ts("md", tex)
    assert r.rc == 2 and src.read_text() == CLEAN, r.out


def test_md_writes_the_reading_twin_with_the_abstract_first(T):
    src = T.dir / "paper.tex"
    src.write_text("\\documentclass{article}\n\\begin{document}\n\\begin{abstract}\n  A short abstract.\n"
                   "\\end{abstract}\n% @rev C1 rounds=1 by=owner:2026-10-10\nBody.\n% @/rev C1\n\\end{document}\n")
    r = T.ts("md", src)
    assert r.rc == 0, r.out
    md = (T.dir / "paper.md").read_text()
    assert md.startswith("<!-- typeset: generated from paper.tex;")
    assert md.index("## Abstract") < md.index("A short abstract.") < md.index("\\documentclass")
    whole, abstract = T.calls("pandoc")
    assert "--to=gfm" in whole["args"] and "--wrap=none" in whole["args"] and whole["args"][-1] == str(src.resolve())
    assert abstract["stdin"] == "A short abstract." and "--to=gfm" in abstract["args"]
    assert T.ts("md", src).rc == 0  # its own twin is rewritten
    assert T.ts("md", src, "--out", T.dir / "twin" / "read.md").rc == 0
    assert (T.dir / "twin" / "read.md").is_file()


def test_usage_and_an_unreadable_file(T):
    (T.dir / "notes.txt").write_text("x\n")
    assert T.ts("pdf", T.dir / "notes.txt").rc == 2
    (T.dir / "a.md").write_text("x\n")
    assert T.ts("md", T.dir / "a.md").rc == 2
    r = T.ts("pdf", T.dir / "nothing.md")
    assert r.rc == 3 and "cannot read" in r.out
    assert T.ts("pdf", T.dir / "a.md", "--template", T.dir / "none.latex").rc == 2
    assert T.ts().rc == 2
