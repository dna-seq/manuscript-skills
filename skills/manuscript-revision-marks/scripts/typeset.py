# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Typeset a document: Markdown or LaTeX to PDF through pandoc and tectonic, and LaTeX to a Markdown
reading twin through pandoc. Standard library only; pandoc and tectonic are its two binaries, which uv
does not install.

    uv run --script typeset.py pdf FILE.md|FILE.tex [--cap N] [--out PDF] [--strict] [--template TEMPLATE]
    uv run --script typeset.py pdf FILE.md|FILE.tex --draft [--config TOML] [--unknown agent|human]
    uv run --script typeset.py md FILE.tex [--out MD]

`pdf` from Markdown runs pandoc (--standalone --wrap=preserve --shift-heading-level-by=-1: the one `#`
heading is the title, `##` the sections) to `<stem>.tex` beside FILE, then tectonic; from LaTeX,
tectonic alone. The PDF is `<stem>.pdf` beside FILE unless --out says otherwise, tectonic's log
beside it as `<stem>.log`. Pandoc is given DejaVu fonts as template variables: its default, Latin
Modern, lacks ≥, ↔ and the superscript minus, and XeTeX drops a missing glyph with only a log line.
A venue template (--template) that sets its own fonts ignores them; it is a pandoc template, so it
is refused with a .tex source.

- A source carrying revision marks (rev_marks.py beside this file) is built from its clean twin,
  `<stem>.clean.md` or `<stem>.clean.tex`, and only when the twin is current (`rev_marks.py strip FILE
  --check`);
  otherwise it is refused and nothing is touched. Marks that do not lint are refused too. The files
  written are still named after FILE's stem.
- A failed render (pandoc or tectonic failing, or no PDF from tectonic) deletes the PDF an earlier
  build left at the target, and says so: a stale PDF never reads as the current one.
- Each glyph the fonts lack is a warning line with its code point; the exit stays 0 unless --strict.
- Pages come from the log's "Output written on … (N pages" line. Over --cap is exit 1 with the
  count; no such line under --cap is unknown, exit 3.
- `pdf --draft` builds a review copy, `<stem>.draft.pdf`, from the marked master itself: every segment
  whose latest round is not a person's (rev_marks.py's rule and rev-marks.toml) is shaded, a whole
  paragraph as a box, a run inside a paragraph highlighted (or coloured, where it carries commands).
  Markdown goes through unreviewed.lua and LaTeX gets unreviewed-preamble.tex before \begin{document}
  (the LaTeX intermediate is `<stem>.draft.tex`). It never writes the submission PDF, and it takes no
  --cap: the boxes change the length, so the submission build is the one measured.
- `md` writes the reading twin, pandoc's GitHub Markdown of FILE, to `<stem>.md` beside it, the
  abstract (which pandoc keeps only as metadata) put first under "## Abstract". LaTeX comments, the
  revision marks among them, do not reach it.
- A file this tool writes opens with a "typeset: generated from" comment, and a file of that name
  without one (a hand-written master) is never overwritten: exit 2.
- The binaries are `pandoc` and `tectonic` from PATH, or the paths in TYPESET_PANDOC and
  TYPESET_TECTONIC; a variable that names no executable is refused, never passed over for PATH. The
  environment reaches both unchanged, so tectonic caches its bundle where the caller's
  TECTONIC_CACHE_DIR says.

EXIT STATUS  0 done · 1 findings: the render failed, over the cap, a missing glyph under --strict, a
             marked source whose twin is missing or stale or whose marks do not lint · 2 usage ·
             3 could not run: a binary absent, FILE unreadable, pages unknown under --cap
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REV_MARKS = HERE / "rev_marks.py"
DRAFT_FILTER = HERE / "unreviewed.lua"
DRAFT_PREAMBLE = HERE / "unreviewed-preamble.tex"
BEGIN_DOCUMENT_RE = re.compile(r"^[ \t]*\\begin\{document\}", re.MULTILINE)
PANDOC_ARGS = ("--standalone", "--wrap=preserve", "--shift-heading-level-by=-1")
_DEJAVU_FACES = "Extension=.ttf, UprightFont=*, BoldFont=*-Bold, ItalicFont=*-Italic, BoldItalicFont=*-BoldItalic"
FONT_VARIABLES = (
    "mainfont=DejaVuSerif",
    f"mainfontoptions={_DEJAVU_FACES}",
    "monofont=DejaVuSansMono",
    f"monofontoptions={_DEJAVU_FACES.replace('*-Italic', '*-Oblique').replace('*-BoldItalic', '*-BoldOblique')}",
)
PAGES_RE = re.compile(r"Output written on .*? \((?P<pages>[0-9]+) pages?")
# XeTeX writes the code point in brackets; older ones leave it out, so it is taken from the character.
MISSING_RE = re.compile(r"Missing character: There is no (?P<char>.)(?: \(U\+(?P<code>[0-9A-Fa-f]+)\))?")
ABSTRACT_RE = re.compile(r"\\begin\{abstract\}(?P<body>.*?)\\end\{abstract\}", re.DOTALL)
GENERATED = "typeset: generated from"
LOG_TAIL_LINES = 40


class Stop(Exception):
    """End the run with *code*, after saying why."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


class RenderFailed(Exception):
    """pandoc or tectonic failed: the PDF at the target is stale."""


def say(message: str) -> None:
    print(f"typeset: {message}", file=sys.stderr)


def rev_marks():
    """rev_marks.py beside this file, loaded as a module: the one place that knows what a mark is."""
    if "rev_marks" in sys.modules:
        return sys.modules["rev_marks"]
    spec = importlib.util.spec_from_file_location("rev_marks", REV_MARKS)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rev_marks"] = module
    spec.loader.exec_module(module)
    return module


def binaries(*names: str) -> dict[str, str]:
    """Each binary's path; every one absent named in one refusal."""
    found, missing = {}, []
    for name in names:
        var = f"TYPESET_{name.upper()}"
        given = os.environ.get(var)
        path = shutil.which(given) if given else shutil.which(name)
        if path is None:
            missing.append(f"{var}={given} is not an executable" if given
                           else f"{name} is not on PATH (or set {var} to it)")
        else:
            found[name] = path
    if missing:
        raise Stop(3, "not run: " + "; ".join(missing))
    return found


def build_source(path: Path) -> Path:
    """FILE, or its clean twin when FILE carries marks; refused when that twin is not current."""
    rm = rev_marks()
    found = rm.parse(rm.read_source(path), rm.syntax_for(path))
    if found.errors:
        rm.print_issues(path, found.errors)
        raise Stop(1, f"{path} has revision marks that do not lint; fix them (rev_marks.py lint {path})")
    if not found.marks:
        return path
    twin = rm.clean_twin_path(path)
    if not twin.is_file() or twin.read_bytes() != found.clean_text().encode("utf-8"):
        state = "stale" if twin.is_file() else "missing"
        raise Stop(1, f"{path} carries revision marks and its clean twin {twin.name} is {state}; "
                      f"write it with rev_marks.py strip {path}, then build again")
    return twin


def writable(target: Path) -> None:
    """Refuse to overwrite a file this tool did not write."""
    if not target.exists():
        return
    with target.open("rb") as f:
        head = f.readline().decode("utf-8", "replace")
    if GENERATED not in head:
        raise Stop(2, f"{target} exists and was not written by typeset; it is never overwritten. "
                      "Move it aside, or write elsewhere")


def run(cmd: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, input=stdin, text=True, capture_output=True, check=False)


def drop_stale(pdf: Path) -> None:
    if pdf.exists():
        pdf.unlink()
        say(f"deleted {pdf}: an earlier build, it does not reflect this source")


def tail(text: str) -> str:
    return "\n".join(text.splitlines()[-LOG_TAIL_LINES:])


def missing_glyphs(log: str) -> dict[str, int]:
    """`U+2265 ≥` → how many times the fonts lacked it."""
    counts: dict[str, int] = {}
    for m in MISSING_RE.finditer(log):
        code = int(m.group("code"), 16) if m.group("code") else ord(m.group("char"))
        key = f"U+{code:04X} {m.group('char')}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def to_latex(pandoc: str, source: Path, master: Path, tex: Path, template: Path | None,
             extra: tuple[str, ...] = (), text: str | None = None) -> None:
    """Markdown to LaTeX; from *text* on stdin instead of *source* when given (run beside *source*)."""
    writable(tex)
    cmd = [pandoc, "--from=markdown", "--to=latex", *PANDOC_ARGS, *(f"--variable={v}" for v in FONT_VARIABLES),
           *extra]
    if template is not None:
        cmd.append(f"--template={template.resolve()}")
    proc = run([*cmd, *([] if text is not None else [str(source.resolve())])], source.parent, stdin=text)
    if proc.returncode != 0:
        raise RenderFailed(f"pandoc failed on {source.name} (exit {proc.returncode})\n{tail(proc.stderr)}")
    tex.write_text(f"% {GENERATED} {master.name}; edits here are overwritten\n{proc.stdout}", encoding="utf-8")
    print(f"wrote {tex} from {source.name}")


def to_pdf(tectonic: str, tex: Path, pdf: Path) -> str:
    """Compile *tex* into *pdf*; tectonic's log text. Raises RenderFailed."""
    pdf.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".typeset-", dir=pdf.parent))
    try:
        proc = run([tectonic, "--keep-logs", "--outdir", str(work.resolve()), tex.name], tex.parent)
        built, log = work / f"{tex.stem}.pdf", work / f"{tex.stem}.log"
        text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
        if log.is_file():
            os.replace(log, pdf.with_suffix(".log"))
        if proc.returncode != 0 or not built.is_file():
            why = f"exit {proc.returncode}" if proc.returncode != 0 else "exit 0 but no PDF"
            raise RenderFailed(f"tectonic failed on {tex.name} ({why})\n{tail(text or proc.stderr or proc.stdout)}")
        os.replace(built, pdf)
        return text
    finally:
        shutil.rmtree(work, ignore_errors=True)


def glyph_warnings(pdf: Path, log: str) -> bool:
    """Warn of each glyph the fonts lacked; whether any was."""
    glyphs = missing_glyphs(log)
    for key, count in glyphs.items():
        say(f"warning: {pdf.name}: missing glyph {key} ({count} time{'s' if count > 1 else ''}): XeTeX left a"
            " gap there; use a font that has it")
    return bool(glyphs)


def cmd_draft(args, path: Path, kind: str) -> int:
    """The review copy: the marked master with its unreviewed segments shaded."""
    if args.cap is not None:
        raise Stop(2, "--draft takes no --cap: its boxes change the length; measure the build without --draft")
    tools = binaries(*(("pandoc", "tectonic") if kind == ".md" else ("tectonic",)))
    rm = rev_marks()
    found = rm.parse(rm.read_source(path), rm.syntax_for(path))
    if found.errors:
        rm.print_issues(path, found.errors)
        raise Stop(1, f"{path} has revision marks that do not lint; fix them (rev_marks.py lint {path})")
    try:
        people = rm.load_people(path, args.config, args.unknown)
    except rm.ConfigError as exc:
        raise Stop(2, str(exc)) from None
    spots = rm.unreviewed(found, people)
    text, skipped = rm.draft_text(found, {s.id for s in spots})
    for sid in skipped:
        say(f"warning: {sid} is not shaded: its inline marks enclose more than one paragraph; put them on lines"
            " of their own")
    stem = f"{path.stem}.draft"
    pdf = args.out if args.out is not None else path.with_name(f"{stem}.pdf")
    tex = path.with_name(f"{stem}.tex")
    try:
        if kind == ".md":
            to_latex(tools["pandoc"], path, path, tex, args.template,
                     (f"--lua-filter={DRAFT_FILTER}", f"--include-in-header={DRAFT_PREAMBLE}"), text)
        else:
            begin = BEGIN_DOCUMENT_RE.search(text)
            if begin is None:
                raise Stop(1, f"{path} has no \\begin{{document}} to put the draft's preamble before")
            writable(tex)
            preamble = DRAFT_PREAMBLE.read_text(encoding="utf-8")
            tex.write_text(f"% {GENERATED} {path.name}; edits here are overwritten\n{text[:begin.start()]}{preamble}"
                           f"{text[begin.start():]}", encoding="utf-8")
            print(f"wrote {tex} from {path.name}")
        log = to_pdf(tools["tectonic"], tex, pdf)
    except RenderFailed as exc:
        say(str(exc))
        drop_stale(pdf)
        return 1
    lacking = glyph_warnings(pdf, log)
    pages = PAGES_RE.search(log)
    n = f"{pages.group('pages')} page{'s' if pages.group('pages') != '1' else ''}" if pages else "pages unknown"
    shaded = [s.id for s in spots if s.id not in skipped]
    print(f"wrote {pdf}: {n}; {len(shaded)} of {len(found.segments)} segments shaded as unreviewed"
          + (f" ({', '.join(shaded)})" if shaded else ""))
    return 1 if lacking and args.strict else 0


def cmd_pdf(args) -> int:
    path: Path = args.file
    kind = path.suffix.lower()
    if kind not in (".md", ".tex"):
        raise Stop(2, f"{path}: pdf takes a .md or a .tex file")
    if args.draft:
        if args.template is not None and kind == ".tex":
            raise Stop(2, "--template is a pandoc template, for a .md source; a .tex source carries its own preamble")
        return cmd_draft(args, path, kind)
    if args.template is not None and kind == ".tex":
        raise Stop(2, "--template is a pandoc template, for a .md source; a .tex source carries its own preamble")
    if args.template is not None and not args.template.is_file():
        raise Stop(2, f"template {args.template} is not a file")
    if args.cap is not None and args.cap < 1:
        raise Stop(2, "--cap takes a whole number of pages, at least 1")
    tools = binaries(*(("pandoc", "tectonic") if kind == ".md" else ("tectonic",)))
    pdf = args.out if args.out is not None else path.with_suffix(".pdf")
    try:
        source = build_source(path)
    except Stop:
        if pdf.exists():
            say(f"{pdf} was left as it is and may not match {path.name}")
        raise
    try:
        if kind == ".md":
            tex = path.with_suffix(".tex")
            to_latex(tools["pandoc"], source, path, tex, args.template)
        else:
            tex = source
        log = to_pdf(tools["tectonic"], tex, pdf)
    except RenderFailed as exc:
        say(str(exc))
        drop_stale(pdf)
        return 1
    findings = unknown = False
    if glyph_warnings(pdf, log) and args.strict:
        findings = True
    pages = PAGES_RE.search(log)
    if pages is None:
        print(f"wrote {pdf}: pages unknown (no \"Output written\" line in the log)")
        if args.cap is not None:
            say(f"{pdf.name}: pages unknown, so the cap of {args.cap} could not be checked")
            unknown = True
    else:
        n = int(pages.group("pages"))
        print(f"wrote {pdf}: {n} page{'s' if n != 1 else ''}")
        if args.cap is not None and n > args.cap:
            say(f"{pdf.name} has {n} pages, over the cap of {args.cap}")
            findings = True
    return 1 if findings else 3 if unknown else 0


def cmd_md(args) -> int:
    path: Path = args.file
    if path.suffix.lower() != ".tex":
        raise Stop(2, f"{path}: md takes a .tex file")
    out = args.out if args.out is not None else path.with_suffix(".md")
    pandoc = binaries("pandoc")["pandoc"]
    writable(out)
    cmd = [pandoc, "--from=latex", "--to=gfm", "--wrap=none"]
    proc = run([*cmd, str(path.resolve())], path.parent)
    if proc.returncode != 0:
        say(f"pandoc failed on {path.name} (exit {proc.returncode})\n{tail(proc.stderr)}")
        return 1
    body = proc.stdout
    abstract = ABSTRACT_RE.search(path.read_text(encoding="utf-8"))
    if abstract is not None:
        first = run(cmd, path.parent, stdin=abstract.group("body").strip())
        if first.returncode != 0:
            say(f"pandoc failed on the abstract of {path.name} (exit {first.returncode})\n{tail(first.stderr)}")
            return 1
        body = f"## Abstract\n\n{first.stdout.strip()}\n\n{body}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"<!-- {GENERATED} {path.name}; edits here are overwritten -->\n\n{body}", encoding="utf-8")
    print(f"wrote {out}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="typeset.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pdf", help="Markdown or LaTeX to PDF")
    p.add_argument("file", type=Path)
    p.add_argument("--cap", type=int, help="the page limit; more is exit 1")
    p.add_argument("--out", type=Path, help="the PDF; default <stem>.pdf beside FILE")
    p.add_argument("--strict", action="store_true", help="a missing glyph is exit 1")
    p.add_argument("--template", type=Path, help="a pandoc LaTeX template, for a Markdown source")
    p.add_argument("--draft", action="store_true", help="a review copy with unreviewed segments shaded")
    p.add_argument("--config", type=Path, help="rev-marks.toml for --draft (default: found from FILE up)")
    p.add_argument("--unknown", choices=["agent", "human"], help="for --draft: what an unlisted name counts as")
    p.set_defaults(run=cmd_pdf)
    p = sub.add_parser("md", help="LaTeX to its Markdown reading twin")
    p.add_argument("file", type=Path)
    p.add_argument("--out", type=Path, help="default <stem>.md beside FILE")
    p.set_defaults(run=cmd_md)
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)  # what was written, then what was found, in that order
    if not args.file.is_file():
        say(f"cannot read {args.file}")
        return 3
    try:
        return args.run(args)
    except Stop as exc:
        say(str(exc))
        return exc.code
    except (OSError, UnicodeDecodeError) as exc:
        say(str(exc))
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
