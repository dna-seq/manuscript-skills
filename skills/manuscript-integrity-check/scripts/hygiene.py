# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "pillow>=10"]
# ///
"""Check the submission package: what the venue or preprint server will publish or read beyond the PDF.

Reports, never deletes or rewrites. Finds:

- LaTeX `%` comments with content, and `\\iffalse ... \\fi` or `comment` blocks with content, in .tex sources
  (arXiv offers every LaTeX source for download);
- hidden or injected text: white or near-white text, tiny fonts, `\\phantom` and zero-size boxes with text,
  invisible render modes, zero-width and Unicode tag characters, hidden HTML spans, Word hidden (`w:vanish`),
  white or tiny runs; prompts aimed at AI reviewers anywhere (hidden: blocker; visible: info, since a paper
  may quote one). PDFs need `pdftotext` (poppler) and are otherwise not assessed; colour is not readable
  from a PDF's text layer, so white text there is checked in the source instead;
- secrets (cloud, API and private keys, tokens, passwords in URLs), absolute local paths that carry a user
  name, Google Docs or Drive links (an editable link exposes the document);
- EXIF GPS positions and author or owner tags in figure files (needs Pillow, which `uv run --script`
  installs; without it figures are not assessed);
- revision marks (`<!-- @rev ... -->`, `% @rev ...`) left in a file to be uploaded: the venue receives the
  clean copy or a build from it, never the marked master;
- with --anonymous and the author names: self-identifying text for double-blind review (names outside the
  references, e-mail addresses, ORCID iDs, acknowledgements, first-person self-citation, repository URLs,
  document and figure metadata).

Secrets are masked in every output. A file type the script cannot read is listed as not assessed.

    uv run --script hygiene.py submission/                       # a directory, an archive or files
    uv run --script hygiene.py paper.tex figures/ --md hygiene.md --json hygiene.json
    uv run --script hygiene.py submission/ --final               # the authors are about to submit
    uv run --script hygiene.py arxiv-bundle.tar.gz --anonymous --author "Ada Lovelace" --author "C. Babbage"

Checking the upload files is the last step before submission, so most findings wait for it. Two cannot wait and
count at any stage: text hidden for AI reviewers, and a leaked secret.

Exit codes: 0 no blocker or major finding that counts now (hidden text for AI reviewers, a leaked secret; with
--final every blocker and major finding counts); 1 at least one; 2 usage error.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from enum import Enum
from pathlib import Path
from typing import Annotated, Iterator, Optional
from xml.etree import ElementTree

import typer
from pydantic import BaseModel

try:  # optional: figures are reported as not assessed without it
    from PIL import Image
except ImportError:  # pragma: no cover - depends on the environment
    Image = None  # type: ignore[assignment]

app = typer.Typer(add_completion=False, no_args_is_help=True)


class Severity(str, Enum):  # the same tiers as scan.py
    blocker = "blocker"
    major = "major"
    minor = "minor"
    info = "info"


class Finding(BaseModel):
    check: str  # comments | hidden-text | injection | invisible-characters | secrets | local-paths | links |
    #             metadata | word-review | anonymity | revision-marks
    severity: Severity
    location: str  # file, file:line, file paragraph N, file p. N
    line: Optional[int] = None
    excerpt: str = ""
    message: str
    suggestion: str = ""
    section: Optional[str] = None  # the heading the line falls under, in a LaTeX, Markdown or HTML source
    # Checking the upload files is the last step before submission (references/author-priorities.md).
    stage: str = "final"


class NotAssessed(BaseModel):
    location: str
    check: str
    reason: str


class HygieneReport(BaseModel):
    inputs: list[str]
    files: dict[str, int]  # kind -> count examined
    findings: list[Finding]
    not_assessed: list[NotAssessed]
    sha256: dict[str, str]  # top-level input files -> sha256, for reusing the check


# --------------------------------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------------------------------

# Text addressed to an automated reviewer rather than to a reader. The request for a good review counts only as an
# order (at the start of a sentence or line, after "please" or "you should/must"), or when its object is the paper
# itself: a paper about models says "models that produce high scores on the benchmark" for its own reasons. "As an
# AI assistant, I cannot ..." is a chat reply about the assistant itself, not a prompt to one; "as an AI reviewer"
# and "you are an AI assistant" address one.
_POSITIVE_REVIEW = r"""\b(?:positive|favou?rable|glowing|strong|high|excellent)\b[^.\n]{0,15}\b(?:review|score|rating|
        assessment|evaluation|recommendation)"""
INJECTION = re.compile(r"""(?imx)
    \b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+)?(?:of\s+)?(?:the\s+|your\s+)?(?:previous|prior|preceding|
        above|earlier|other|system)\s+(?:instructions?|prompts?|directions|guidelines|rules)
  | \byou\s+are\s+(?:now\s+)?an?\s+(?:ai|llm|language[- ]model|large\s+language\s+model|automated|machine)[- ]
        (?:based\s+)?(?:reviewer|referee|assistant)
  | \bas\s+an?\s+(?:ai|llm|language[- ]model|large\s+language\s+model|automated|machine)[- ](?:based\s+)?
        (?:reviewer|referee)\b
  | \bnote\s+(?:to|for)\s+(?:the\s+)?(?:ai|llm|language[- ]model|automated)\s+(?:reviewers?|referees?|assistants?)
  | (?:^|[.!?:;"“(\[]\s*|\bplease\s+|\b(?:must|should|shall)\s+(?:always\s+|only\s+)?)
        (?:give|write|produce|output|provide|generate|assign)\b[^.\n]{0,30}POSITIVE_REVIEW
  | \b(?:give|write|produce|output|provide|generate|assign)\s+(?:this|the)\s+(?:paper|manuscript|submission|work|
        article)\b[^.\n]{0,30}POSITIVE_REVIEW
  | \b(?:recommend|suggest|advise)\w*\b[^.\n]{0,25}\baccept(?:ance|ing|ed)?\b[^.\n]{0,20}\b(?:this|the)\s+
        (?:paper|manuscript|submission|work|article)
  | \b(?:rate|score)\s+(?:this|the)\s+(?:paper|manuscript|submission|work)\b[^.\n]{0,20}\b(?:highly|high|positively|
        \d+\s*/\s*10|strong)
  | \bdo\s+not\s+(?:mention|highlight|point\s+out|discuss|list|report|criticize|criticise)\b[^.\n]{0,25}\b(?:any\s+)?
        (?:weakness(?:es)?|limitations?|flaws?|negatives?|criticism|shortcomings|problems)
  | \bonly\s+(?:mention|highlight|list|discuss)\s+(?:the\s+)?(?:strengths|positives|positive\s+aspects)
""".replace("POSITIVE_REVIEW", _POSITIVE_REVIEW))

SECRETS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |DSA |EC |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY(?: BLOCK)?-----")),
    ("AWS access key ID", re.compile(r"\b((?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA|ANVA|AIPA)[0-9A-Z]{16})\b")),
    ("AWS secret access key", re.compile(r"(?i)aws_?secret_?access_?key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})")),
    ("Google API key", re.compile(r"\b(AIza[0-9A-Za-z_\-]{35})(?![\w-])")),
    ("GitHub token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("GitLab token", re.compile(r"\b(glpat-[A-Za-z0-9_\-]{20,})(?![\w-])")),
    ("Slack token", re.compile(r"\b(xox[abposr]-[A-Za-z0-9-]{10,})(?![\w-])")),
    ("Anthropic API key", re.compile(r"\b(sk-ant-[A-Za-z0-9_\-]{20,})(?![\w-])")),
    ("OpenAI API key", re.compile(r"\b(sk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{20,})(?![\w-])")),
    ("Hugging Face token", re.compile(r"\b(hf_[A-Za-z0-9]{30,})\b")),
    ("Stripe live key", re.compile(r"\b((?:sk|rk)_live_[A-Za-z0-9]{16,})\b")),
    ("JSON Web Token", re.compile(r"\b(eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})")),
    ("password in a URL", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:([^\s:/@]{3,})@")),
    ("credential assignment", re.compile(r"(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|"
                                         r"auth[_-]?token|client[_-]?secret)\b\s*[:=]\s*['\"]([^'\"\s]{6,})['\"]")),
]

LOCAL_PATH = re.compile(r"(?:/Users/|/home/|/mnt/[a-z]/Users/|\b[A-Za-z]:[\\/]+Users[\\/]+)([A-Za-z0-9._-]{2,})")
GENERIC_USERS = {"user", "username", "name", "you", "yourname", "me", "runner", "ubuntu", "example", "shared",
                 "public", "default", "jovyan", "vscode", "admin"}
GOOGLE_DOC = re.compile(r"https?://docs\.google\.com/(?:document|spreadsheets|presentation|drawings)/(?:u/\d/)?d/"
                        r"[\w-]{10,}[^\s)\]}>\"'\\]*")
GOOGLE_DRIVE = re.compile(r"https?://drive\.google\.com/(?:file/d/|drive/(?:u/\d/)?folders/|open\?id=)[\w-]{10,}"
                          r"[^\s)\]}>\"'\\]*")

# Characters a reader never sees. ZWJ/ZWNJ are legitimate in emoji and some scripts, so they are reported
# only as a count; Unicode tag characters carry hidden ASCII and are decoded.
INVISIBLE = re.compile("[\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064\u180e\ufeff\u202a-\u202e\u2066-\u2069]")
TAG_CHARS = re.compile("[\U000e0000-\U000e007f]+")

# Revision marks of manuscript-revision-marks: `<!-- @rev ID rounds=N by=name:date -->` and its closer in Markdown or
# HTML, `% @rev ...` in LaTeX. The master may carry them; the files a venue receives never do.
REVISION_MARK = re.compile(r"<!--\s*@/?rev\b.*?-->|(?<!\\)%[ \t]*@/?rev\b[^\n]*", re.DOTALL)
REVISION_BY = re.compile(r"\bby=([^\s>]+)")

PRIVATE_NOTE = re.compile(r"(?i)\b(?:todo|fixme|xxx|tbd|note to|reviewer|referee|rebuttal|editor|confidential|private|"
                          r"secret|don'?t|do not|remove|delete|hack|ugly|weak|fake|cheat|made up|not sure|unsure|hated?|"
                          r"stupid|damn|wtf|embarrass|hide|hidden|excluded?|dropped)\b")

TEX_EXT = {".tex", ".ltx"}
TEX_SUPPORT_EXT = {".sty", ".cls", ".bib", ".bbl", ".bst"}
MD_EXT = {".md", ".markdown", ".rmd", ".qmd"}
HTML_EXT = {".html", ".htm", ".xhtml"}
IMAGE_EXT = {".jpg", ".jpeg", ".tif", ".tiff", ".png", ".webp"}
ARCHIVE_SUFFIXES = (".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
SKIP_DIRS = {".git", ".svn", ".hg", "node_modules", "__pycache__", ".venv", "venv", ".ipynb_checkpoints"}
MAX_TEXT_BYTES = 10 * 1024 * 1024
MAX_MEMBERS = 3000
MIN_HIDDEN_WORDS = 4


def _mask(secret: str) -> str:
    secret = secret.strip().strip("'\"").splitlines()[0]
    return "****" if len(secret) <= 10 else f"{secret[:4]}…{secret[-2:]}"


def _snippet(text: str, limit: int = 110) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _words(text: str) -> int:
    return len(re.findall(r"[A-Za-z]{2,}", text))


_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_TEX_SECTION = re.compile(r"^\s*\\(chapter|section|subsection|subsubsection)\*?\s*(?:\[[^\]]*\])?\s*"
                          r"\{((?:[^{}]|\{[^{}]*\})*)\}")
_TEX_LEVELS = {"chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3}


def section_index(text: str) -> list[str]:
    """The heading each line falls under (item i for line i + 1), as scan.py names it: "Front matter" before the
    first heading, "Abstract" in a LaTeX abstract, a lone top-level heading above the others taken as the title."""
    lines = text.split("\n")
    heads: dict[int, tuple[int, str]] = {}
    markdown: set[int] = set()
    for i, line in enumerate(lines):
        m = _MD_HEADING.match(line.strip())
        if m:
            markdown.add(i)
        t = None if m else _TEX_SECTION.match(line)
        if m or t:
            raw = m.group(2) if m else t.group(2)
            title = " ".join(re.sub(r"[{}*_`]", "", re.sub(r"\\[A-Za-z]+\*?", "", raw)).split()).strip(" .:")
            heads[i] = (len(m.group(1)) if m else _TEX_LEVELS[t.group(1)], title[:80])
    levels = [level for level, _ in heads.values()]
    first = min(heads) if heads else None
    title_line = first if (first in markdown and len(levels) > 1 and heads[first][0] == min(levels)
                           and levels.count(min(levels)) == 1) else None
    out: list[str] = []
    stack: list[tuple[int, str]] = []
    in_abstract = False
    for i, line in enumerate(lines):
        if i in heads and i != title_line:
            level, title = heads[i]
            while stack and stack[-1][0] >= level:
                stack.pop()
            if title:
                stack.append((level, title))
        in_abstract = in_abstract or "\\begin{abstract}" in line
        names = [t for _, t in stack]
        out.append("Abstract" if in_abstract else ", ".join(names[:1] + names[-1:] if len(names) > 2 else names)
                   or "Front matter")
        in_abstract = in_abstract and "\\end{abstract}" not in line
    return out


def _with_sections(findings: list[Finding], text: str) -> list[Finding]:
    """Name the heading each finding's line falls under."""
    sections = section_index(text)
    for f in findings:
        if f.line and f.line <= len(sections):
            f.section = f.section or sections[f.line - 1]
    return findings


def _classify_hidden(location: str, line: Optional[int], how: str, text: str, check: str = "hidden-text"
                     ) -> Optional[Finding]:
    """A finding for text a reader cannot see; None when it is too slight to matter (a \\phantom{00} spacer)."""
    text = _snippet(text, 160)
    if INJECTION.search(text):
        return Finding(check="injection", severity=Severity.blocker, location=location, line=line, excerpt=text,
                       message=f"Hidden text ({how}) addresses an AI reviewer.",
                       suggestion="Remove it. Venues treat a hidden prompt to reviewers as misconduct (ICLR 2026 "
                                  "calls it an attempt at collusion under its Code of Ethics), whatever the venue's "
                                  "wording, because it misleads the review itself.")
    if _words(text) >= MIN_HIDDEN_WORDS:
        return Finding(check=check, severity=Severity.major, location=location, line=line, excerpt=text,
                       message=f"Text a reader cannot see ({how}).",
                       suggestion="Remove it, or make it visible if it belongs in the paper.")
    return None


# --------------------------------------------------------------------------------------------------
# Checks on any text
# --------------------------------------------------------------------------------------------------

def text_findings(location: str, text: str, with_lines: bool = True) -> list[Finding]:
    """Secrets, local paths, Google links, invisible characters and visible reviewer-directed prompts."""
    out: list[Finding] = []

    def where(offset: int) -> tuple[str, Optional[int]]:
        if not with_lines:
            return location, None
        line = _line_of(text, offset)
        return f"{location}:{line}", line

    taken: list[tuple[int, int]] = []
    for label, rx in SECRETS:
        for m in rx.finditer(text):
            group = 1 if rx.groups else 0
            span = m.span(group)
            if any(a < span[1] and span[0] < b for a, b in taken):
                continue
            taken.append(span)
            loc, line = where(m.start())
            out.append(Finding(check="secrets", severity=Severity.major, location=loc, line=line,
                               excerpt=_mask(m.group(group)),
                               message=f"Possible {label} ({_mask(m.group(group))}).",
                               suggestion="Remove it from every file in the package and revoke or rotate it: a key "
                                          "that has been in a shared file should be treated as exposed."))
    users: dict[str, int] = {}
    for m in LOCAL_PATH.finditer(text):
        if m.group(1).lower() not in GENERIC_USERS:
            users.setdefault(m.group(1), m.start())
    for user, offset in users.items():
        loc, line = where(offset)
        out.append(Finding(check="local-paths", severity=Severity.minor, location=loc, line=line,
                           excerpt=_snippet(text[offset:offset + 60]),
                           message=f"Absolute local path naming the account '{user}'.",
                           suggestion="Use a relative path; a home-directory path also identifies an author."))
    for rx, editable in ((GOOGLE_DOC, True), (GOOGLE_DRIVE, False)):
        for m in rx.finditer(text):
            url = m.group(0)
            if re.search(r"/(?:view|pub|preview|htmlview|export)\b|/viewform", url):
                continue
            loc, line = where(m.start())
            edit = editable and ("/edit" in url or not re.search(r"/d/[\w-]+/\w", url))
            out.append(Finding(check="links", severity=Severity.major if edit else Severity.minor, location=loc,
                               line=line, excerpt=_snippet(url, 90),
                               message="Editable Google document link." if edit else "Google Drive link.",
                               suggestion="Anyone with the link may be able to read, comment on or edit it. Use an "
                                          "archived, read-only copy (Zenodo, OSF, a supplementary file) or check its "
                                          "sharing setting."))
    counts: dict[int, int] = {}
    for m in INVISIBLE.finditer(text):
        if m.group(0) == "\ufeff" and m.start() == 0:
            continue  # a byte-order mark at the start of a file is harmless
        line = _line_of(text, m.start()) if with_lines else 0
        counts[line] = counts.get(line, 0) + 1
    if counts:
        lines = sorted(counts)
        out.append(Finding(check="invisible-characters", severity=Severity.minor, location=location,
                           line=lines[0] or None,
                           message=f"{sum(counts.values())} zero-width or text-direction control character(s)"
                                   + (f" on lines {', '.join(map(str, lines[:10]))}" if with_lines else "") + ".",
                           suggestion="Usually pasted from a web page or a chat interface. Remove them unless a script "
                                      "needs them; direction controls can make text read differently from how it "
                                      "displays."))
    for m in TAG_CHARS.finditer(text):
        hidden = "".join(chr(ord(c) - 0xE0000) for c in m.group(0) if 0x20 <= ord(c) - 0xE0000 < 0x7F)
        loc, line = where(m.start())
        finding = _classify_hidden(loc, line, "Unicode tag characters", hidden, "invisible-characters")
        out.append(finding or Finding(check="invisible-characters", severity=Severity.major, location=loc, line=line,
                                      excerpt=_snippet(hidden), message="Unicode tag characters carry hidden text.",
                                      suggestion="Remove them."))
    injection_lines: set[Optional[int]] = set()
    for m in INJECTION.finditer(text):
        loc, line = where(m.start())
        if line in injection_lines:
            continue
        injection_lines.add(line)
        out.append(Finding(check="injection", severity=Severity.info, location=loc, line=line,
                           excerpt=_snippet(text[max(0, m.start() - 30):m.end() + 30]),
                           message="Text addressed to an AI reviewer, not marked up as hidden.",
                           suggestion="Fine if the paper quotes it as an example; otherwise remove it."))
    return out


def _drop_shadowed(findings: list[Finding]) -> list[Finding]:
    """A hidden prompt is reported once, as hidden: drop the plain-text report of the same line."""
    hidden = {(f.location, f.line) for f in findings if f.check in ("injection", "hidden-text")
              and f.severity in (Severity.blocker, Severity.major)}
    return [f for f in findings if not (f.check == "injection" and f.severity == Severity.info
                                        and (f.location, f.line) in hidden)]


# --------------------------------------------------------------------------------------------------
# LaTeX
# --------------------------------------------------------------------------------------------------

_VERB = re.compile(r"\\verb\*?(.)(.*?)\1")
_URL_ARG = re.compile(r"\\(?:url|href|path)\s*\{[^}]*\}")
_VERBATIM_ENVS = ("verbatim", "Verbatim", "lstlisting", "minted", "alltt", "filecontents")


def tex_comment(line: str) -> Optional[tuple[int, str]]:
    """(column, text) of the comment on this line, ignoring \\%, \\verb and \\url arguments."""
    i = 0
    while i < len(line):
        if line[i] == "\\":
            for rx in (_VERB, _URL_ARG):
                m = rx.match(line, i)
                if m:
                    i = m.end()
                    break
            else:
                i += 2
            continue
        if line[i] == "%":
            return i, line[i + 1:]
        i += 1
    return None


def _has_content(comment: str) -> bool:
    body = comment.strip()
    if not body or re.match(r"^\s*!\s*(?:TeX|TEX|BIB)\b|^&|^!", comment):
        return False
    return bool(re.search(r"[A-Za-z0-9]", body))


def _plain(tex: str) -> str:
    tex = re.sub(r"\\(?:[a-zA-Z]+)\*?(?:\[[^\]]*\])?", " ", tex)
    return re.sub(r"[{}$]|\b\d+(?:\.\d+)?pt\b", " ", tex)


def _brace_group(text: str, start: int) -> tuple[str, int]:
    """Content of the {...} group whose opening brace is at text[start], and the index after it."""
    if start >= len(text) or text[start] != "{":
        return "", start
    depth, i = 0, start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
        i += 1
    return text[start + 1:], len(text)


def _declaration_scope(text: str, start: int) -> str:
    """Text a declaration (\\color{white}, \\fontsize{..}\\selectfont) applies to: up to the end of the
    enclosing group, a paragraph break or a reset."""
    end = min(len(text), start + 600)
    reset = re.compile(r"\n\s*\n|\\normalcolor\b|\\color\s*\{\s*(?:black|\.)\s*\}|\\normalsize\b|\\pdfliteral\s*\{\s*0\s+Tr")
    m = reset.search(text, start, end)
    if m:
        end = m.start()
    depth, i = 0, start
    while i < end:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            if depth == 0:
                break
            depth -= 1
        i += 1
    return text[start:i]


def _near_white(model: str, spec: str) -> bool:
    model, spec = model.strip().lower(), spec.strip()
    try:
        if model == "rgb":
            values = [float(x) for x in spec.split(",")]
        elif model == "rgb255" or (model == "rgb" and max(float(x) for x in spec.split(",")) > 1):
            values = [float(x) / 255 for x in spec.split(",")]
        elif model == "html":
            values = [int(spec[k:k + 2], 16) / 255 for k in (0, 2, 4)]
        elif model == "gray":
            values = [float(spec)]
        elif model == "cmyk":
            c, m_, y, k = (float(x) for x in spec.split(","))
            values = [(1 - c) * (1 - k), (1 - m_) * (1 - k), (1 - y) * (1 - k)]
        else:
            return False
    except ValueError:
        return False
    if model.lower() == "rgb" and len(values) == 3 and max(values) > 1:
        values = [v / 255 for v in values]
    return len(values) in (1, 3) and min(values) >= 0.94


_COLOUR_NAME = re.compile(r"\{\s*(white|white!\d+|[A-Za-z][\w!.-]*)\s*\}")
_ON_BACKGROUND = re.compile(r"\\(?:colorbox|fcolorbox|cellcolor|rowcolor|columncolor|pagecolor)\b|tcolorbox|colback\s*=|"
                            r"fill\s*=")


def _white_names(text: str) -> set[str]:
    names = {"white"}
    for m in re.finditer(r"\\definecolor\s*\{([^}]+)\}\s*\{([^}]+)\}\s*\{([^}]+)\}", text):
        if _near_white(m.group(2), m.group(3)):
            names.add(m.group(1).strip())
    for m in re.finditer(r"\\colorlet\s*\{([^}]+)\}\s*\{\s*white\s*\}", text):
        names.add(m.group(1).strip())
    return names


def _is_white(spec: str, names: set[str]) -> bool:
    spec = spec.strip()
    if spec in names:
        return True
    m = re.fullmatch(r"white!(\d+)(?:!\w+)?", spec)
    if m:
        return False  # white!90!black etc. mixes in colour; only plain white is invisible
    m = re.fullmatch(r"(\w+)!(\d+)", spec)  # black!3 = 3% black on white
    return bool(m and int(m.group(2)) <= 6)


def tex_findings(location: str, text: str) -> list[Finding]:
    """Comments, commented-out blocks and hidden text in one LaTeX source."""
    out: list[Finding] = []
    lines = text.split("\n")
    in_verbatim: Optional[str] = None
    plain_comments: list[tuple[int, str]] = []
    code_lines = []
    for number, line in enumerate(lines, start=1):
        if in_verbatim:
            if re.search(rf"\\end\{{{in_verbatim}\}}", line):
                in_verbatim = None
            code_lines.append("")
            continue
        env = re.search(r"\\begin\{(" + "|".join(_VERBATIM_ENVS) + r")\*?\}", line)
        if env and not re.search(rf"\\end\{{{env.group(1)}\}}", line):
            in_verbatim = env.group(1)
        found = tex_comment(line)
        if found is None:
            code_lines.append(line)
            continue
        column, comment = found
        code_lines.append(line[:column])
        if not _has_content(comment) or re.match(r"[ \t]*@/?rev\b", comment):
            continue  # a revision mark is reported as one (revision_mark_findings), not as a comment
        if PRIVATE_NOTE.search(comment):
            out.append(Finding(check="comments", severity=Severity.major, location=f"{location}:{number}", line=number,
                               excerpt=_snippet("%" + comment), message="A comment that reads as a private note will "
                               "be published with the source.",
                               suggestion="Delete it before uploading the source (arxiv_latex_cleaner removes all "
                                          "comments); keep notes in a file that is not uploaded."))
        else:
            plain_comments.append((number, comment))
    if plain_comments:
        first = plain_comments[0][0]
        shown = "; ".join(f"“%{_snippet(c, 50)}” (line {n})" for n, c in plain_comments[:4])
        out.append(Finding(check="comments", severity=Severity.minor, location=f"{location}:{first}", line=first,
                           excerpt=shown,
                           message=f"{len(plain_comments)} comment line(s) with content will be published with the "
                                   f"LaTeX source.",
                           suggestion="Read them as a stranger would; strip comments before uploading the source "
                                      "(for example with arxiv_latex_cleaner)."))
    code = "\n".join(code_lines)
    for rx, label in ((r"\\iffalse\b(.*?)\\fi\b", "\\iffalse block"),
                      (r"\\begin\{comment\}(.*?)\\end\{comment\}", "comment environment")):
        for m in re.finditer(rx, code, re.DOTALL):
            content = _plain(m.group(1))
            if _words(content) < 3:
                continue
            start, end = _line_of(code, m.start()), _line_of(code, m.end())
            severe = PRIVATE_NOTE.search(m.group(1)) or INJECTION.search(content)
            out.append(Finding(check="comments", severity=Severity.major if severe else Severity.minor,
                               location=f"{location}:{start}", line=start, excerpt=_snippet(content),
                               message=f"Commented-out text ({label}, lines {start}–{end}) will be published with "
                                       f"the LaTeX source.",
                               suggestion="Delete the block from the uploaded source if a reader should not see it."))
    out += _tex_hidden(location, code)
    return out


def _tex_hidden(location: str, code: str) -> list[Finding]:
    names = _white_names(code)
    hits: list[tuple[int, str, str]] = []  # (offset, how, hidden text)
    for m in re.finditer(r"\\textcolor\s*(?:\[([^\]]*)\])?\s*\{([^}]*)\}\s*(?=\{)", code):
        model, spec = m.group(1), m.group(2)
        if (model and _near_white(model, spec)) or (not model and _is_white(spec, names)):
            hits.append((m.start(), f"\\textcolor{{{spec}}}", _brace_group(code, m.end())[0]))
    for m in re.finditer(r"\\color\s*(?:\[([^\]]*)\])?\s*\{([^}]*)\}", code):
        model, spec = m.group(1), m.group(2)
        if (model and _near_white(model, spec)) or (not model and _is_white(spec, names)):
            hits.append((m.start(), f"\\color{{{spec}}}", _declaration_scope(code, m.end())))
    for m in re.finditer(r"\\fontsize\s*\{\s*(\d*\.?\d+)\s*(pt|bp|mm|px)?\s*\}", code):
        size = float(m.group(1)) * (2.845 if m.group(2) == "mm" else 1)
        if size < 2:
            hits.append((m.start(), f"\\fontsize{{{m.group(1)}{m.group(2) or ''}}}", _declaration_scope(code, m.end())))
    for m in re.finditer(r"\\[hv]?phantom\s*(?=\{)", code):
        hits.append((m.start(), "\\phantom", _brace_group(code, m.end())[0]))
    for m in re.finditer(r"\\scalebox\s*\{\s*(\d*\.?\d+)\s*\}\s*(?:\[[^\]]*\])?\s*(?=\{)", code):
        if float(m.group(1)) < 0.1:
            hits.append((m.start(), f"\\scalebox{{{m.group(1)}}}", _brace_group(code, m.end())[0]))
    for m in re.finditer(r"\\resizebox\s*\{\s*(\d*\.?\d+)\s*(pt|mm|cm|em|ex)?\s*\}\s*\{[^}]*\}\s*(?=\{)", code):
        if float(m.group(1)) == 0 or (m.group(2) in ("pt", None) and float(m.group(1)) < 2):
            hits.append((m.start(), f"\\resizebox{{{m.group(1)}{m.group(2) or ''}}}", _brace_group(code, m.end())[0]))
    for m in re.finditer(r"\\(?:makebox|framebox)\s*\[\s*0\s*(?:pt|mm|cm)?\s*\]\s*\[[^\]]*\]\s*(?=\{)|\\raisebox\s*\{\s*-?\d{3,}"
                         r"(?:pt|mm|cm)\s*\}\s*(?=\{)", code):
        hits.append((m.start(), "zero-width or displaced box", _brace_group(code, m.end())[0]))
    for m in re.finditer(r"\\pdfrender\s*\{[^}]*(?:Invisible|=\s*3)[^}]*\}|\\pdfliteral\s*\{\s*[37]\s+Tr\s*\}|"
                         r"\\transparent\s*\{\s*0(?:\.0*)?\s*\}|\\opacity\s*\{\s*0(?:\.0*)?\s*\}", code):
        hits.append((m.start(), "invisible rendering", _declaration_scope(code, m.end())))
    # \color{white}\fontsize{1pt}... is one piece of hidden text with two reasons: group by line.
    by_line: dict[int, tuple[list[str], str]] = {}
    for offset, how, hidden in sorted(hits):
        line = _line_of(code, offset)
        if _ON_BACKGROUND.search(code[max(0, offset - 150):offset]) and not INJECTION.search(_plain(hidden)):
            continue  # white text on a coloured box or table cell is visible
        reasons, text = by_line.setdefault(line, ([], _plain(hidden)))
        if how not in reasons:
            reasons.append(how)
        if len(_plain(hidden)) > len(text):
            by_line[line] = (reasons, _plain(hidden))
    out: list[Finding] = []
    for line, (reasons, text) in sorted(by_line.items()):
        finding = _classify_hidden(f"{location}:{line}", line, ", ".join(reasons), text)
        if finding:
            out.append(finding)
    return out


def revision_mark_findings(location: str, text: str) -> list[Finding]:
    """Revision marks left in a file to be uploaded: one finding per file, with how many and whether they name an
    AI model or agent as an editor (their `by=` names say who revised each passage)."""
    marks = list(REVISION_MARK.finditer(text))
    if not marks:
        return []
    names = sorted({item.partition(":")[0] for m in marks for by in REVISION_BY.findall(m.group(0))
                    for item in by.split(",") if item.partition(":")[0]})
    line = _line_of(text, marks[0].start())
    named = f", which name {', '.join(names[:6])}" + (" and others" if len(names) > 6 else "") + " as editors" \
        if names else ""
    return [Finding(check="revision-marks", severity=Severity.major, location=f"{location}:{line}", line=line,
                    excerpt=_snippet(marks[0].group(0), 90),
                    message=f"{len(marks)} revision mark{'' if len(marks) == 1 else 's'} (comments such as "
                            f"<!-- @rev ... --> or % @rev ...) {'is' if len(marks) == 1 else 'are'} still in this file"
                            f"{named}.",
                    suggestion="Upload the clean copy without marks, or a build from it (manuscript-revision-marks "
                               "writes it); the marked master stays as it is. Marks travel with a LaTeX or Markdown "
                               "source and say who revised each passage, an AI model included.")]


# --------------------------------------------------------------------------------------------------
# Markdown and HTML
# --------------------------------------------------------------------------------------------------

_HIDDEN_STYLE = re.compile(r"""(?ix)(?:color\s*:\s*(?:white|\#f{3}\b|\#f{6}\b|\#fef?efe|rgba?\(\s*25[0-5]\s*,\s*25[0-5]\s*,
    \s*25[0-5])|font-size\s*:\s*(?:0|0?\.\d+|1)(?:px|pt|em|rem)?\b|display\s*:\s*none|visibility\s*:\s*hidden|
    opacity\s*:\s*0(?:\.0+)?\b)""")
_HIDDEN_TAG = re.compile(r"<(?P<tag>span|div|p|font|section|small)\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)\s*>",
                         re.IGNORECASE | re.DOTALL)


def markup_findings(location: str, text: str) -> list[Finding]:
    out: list[Finding] = []
    for m in _HIDDEN_TAG.finditer(text):
        attrs = m.group("attrs")
        reason = None
        style = re.search(r"style\s*=\s*[\"']([^\"']*)[\"']", attrs, re.IGNORECASE)
        if style and _HIDDEN_STYLE.search(style.group(1)):
            reason = f"style '{_snippet(style.group(1), 40)}'"
        elif re.search(r"\bhidden\b(?!\s*=\s*[\"']?false)", attrs, re.IGNORECASE):
            reason = "hidden attribute"
        elif re.search(r"color\s*=\s*[\"']?(?:white|#f{3}\b|#f{6})", attrs, re.IGNORECASE):
            reason = "white font colour"
        if reason:
            line = _line_of(text, m.start())
            finding = _classify_hidden(f"{location}:{line}", line, reason, re.sub(r"<[^>]+>", " ", m.group("body")))
            if finding:
                out.append(finding)
    comments = []
    for m in re.finditer(r"<!--(.*?)-->", text, re.DOTALL):
        body = m.group(1).strip()
        if re.match(r"@/?rev\b", body) or _words(body) < 2:
            continue  # revision marks are reported as such (revision_mark_findings), not as comments
        line = _line_of(text, m.start())
        if INJECTION.search(body):
            out.append(_classify_hidden(f"{location}:{line}", line, "HTML comment", body))  # type: ignore[arg-type]
        else:
            comments.append((line, body))
    if comments:
        private = [c for c in comments if PRIVATE_NOTE.search(c[1])]
        out.append(Finding(check="comments", severity=Severity.minor if private else Severity.info,
                           location=f"{location}:{comments[0][0]}", line=comments[0][0],
                           excerpt="; ".join(f"“{_snippet(b, 50)}” (line {n})" for n, b in (private or comments)[:4]),
                           message=f"{len(comments)} HTML comment(s) with content"
                                   + (f", {len(private)} reading as private notes" if private else "")
                                   + ". They do not appear in PDF or Word output but are visible to anyone who gets "
                                     "this source file.",
                           suggestion="Remove them before sharing the source itself (a public repository, a "
                                      "supplementary file)."))
    return out


# --------------------------------------------------------------------------------------------------
# Word
# --------------------------------------------------------------------------------------------------

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DOCX_PARTS = re.compile(r"word/(?:document|footnotes|endnotes|header\d*|footer\d*)\.xml$")


def _w(element: Optional[ElementTree.Element], name: str) -> Optional[str]:
    return None if element is None else element.get(W + name)


def _hex_white(value: Optional[str]) -> bool:
    return bool(value) and re.fullmatch(r"[0-9A-Fa-f]{6}", value or "") is not None and \
        min(int(value[k:k + 2], 16) for k in (0, 2, 4)) >= 240  # type: ignore[index]


def _shaded(props: Optional[ElementTree.Element]) -> bool:
    if props is None:
        return False
    shd = props.find(W + "shd")
    fill = _w(shd, "fill")
    highlight = _w(props.find(W + "highlight"), "val")
    return bool((fill and fill.lower() not in ("auto", "ffffff")) or (highlight and highlight not in ("none", "white")))


def _run_hidden(run: ElementTree.Element, shaded: bool) -> Optional[str]:
    props = run.find(W + "rPr")
    if props is None:
        return None
    vanish = props.find(W + "vanish")
    if vanish is not None and _w(vanish, "val") not in ("0", "false", "off"):
        return "Word hidden text"
    if props.find(W + "specVanish") is not None:
        return "Word hidden text"
    size = _w(props.find(W + "sz"), "val")
    if size and size.isdigit() and int(size) < 4:
        return f"{int(size) / 2:g} pt font"
    if _hex_white(_w(props.find(W + "color"), "val")) and not shaded and not _shaded(props):
        return "white font colour"
    return None


def docx_findings(location: str, data: bytes, anonymous: bool) -> tuple[list[Finding], str, list[NotAssessed]]:
    """Findings for a .docx, its visible text (for the text checks), and anything not assessed."""
    out: list[Finding] = []
    visible: list[str] = []
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return [], "", [NotAssessed(location=location, check="all", reason="not a readable .docx (zip) file")]
    paragraph_no = 0
    for name in sorted(n for n in archive.namelist() if _DOCX_PARTS.search(n)):
        try:
            root = ElementTree.fromstring(archive.read(name))
        except ElementTree.ParseError:
            continue

        def walk(element: ElementTree.Element, shaded: bool, part: str = name.split("/")[-1]) -> None:
            nonlocal paragraph_no
            if element.tag in (W + "tc",):
                shaded = shaded or _shaded(element.find(W + "tcPr"))
            if element.tag == W + "p":
                paragraph_no += 1
                shaded_p = shaded or _shaded(element.find(W + "pPr"))
                runs: list[tuple[Optional[str], str]] = []
                for run in element.iter(W + "r"):
                    text = "".join(t.text or "" for t in run.iter(W + "t"))
                    if text:
                        runs.append((_run_hidden(run, shaded_p), text))
                where = f"{location} ({part}) paragraph {paragraph_no}"
                current, buffer = None, []
                for reason, text in runs + [(None, "")]:
                    if reason != current and buffer and current:
                        finding = _classify_hidden(where, None, current, " ".join(buffer))
                        if finding:
                            out.append(finding)
                        buffer = []
                    current = reason
                    if reason:
                        buffer.append(text)
                    else:
                        visible.append(text)
                visible.append("\n")
                return
            for child in element:
                walk(child, shaded, part)

        walk(root, False)
        xml = archive.read(name).decode("utf-8", "replace")
        inserted, deleted = len(re.findall(r"<w:ins\b", xml)), len(re.findall(r"<w:del\b", xml))
        if inserted or deleted:
            out.append(Finding(check="word-review", severity=Severity.info, location=location,
                               message=f"{inserted} tracked insertion(s) and {deleted} deletion(s) remain in "
                                       f"{name.split('/')[-1]}.",
                               suggestion="Accept or reject them unless the venue asks for a marked-up copy."))
    if "word/comments.xml" in archive.namelist():
        xml = archive.read("word/comments.xml").decode("utf-8", "replace")
        authors = sorted(set(re.findall(r"<w:comment\b[^>]*\bw:author=\"([^\"]*)\"", xml)))
        count = len(re.findall(r"<w:comment\b", xml))
        if count:
            out.append(Finding(check="word-review", severity=Severity.major, location=location,
                               message=f"{count} Word comment(s) remain" + (f" (by {', '.join(authors)})" if authors
                                                                             else "") + "; reviewers will see them.",
                               suggestion="Resolve and delete the comments in the file you upload."))
    if "docProps/core.xml" in archive.namelist():
        core = archive.read("docProps/core.xml").decode("utf-8", "replace")
        people = {m.group(2).strip() for m in re.finditer(r"<(dc:creator|cp:lastModifiedBy)>([^<]+)</\1>", core)}
        if people:
            out.append(Finding(check="metadata" if not anonymous else "anonymity",
                               severity=Severity.major if anonymous else Severity.info, location=location,
                               excerpt=", ".join(sorted(people)),
                               message=f"Document properties name {', '.join(sorted(people))}.",
                               suggestion="Clear the author fields (File > Info > Inspect Document) if the review is "
                                          "anonymous." if anonymous else "Expected for a named submission."))
    return out, "".join(visible), []


# --------------------------------------------------------------------------------------------------
# PDF (poppler's pdftotext and pdfinfo)
# --------------------------------------------------------------------------------------------------

def pdf_findings(location: str, data: bytes, anonymous: bool) -> tuple[list[Finding], str, list[NotAssessed]]:
    if shutil.which("pdftotext") is None:
        return [], "", [NotAssessed(location=location, check="all",
                                    reason="pdftotext (poppler-utils) is not installed; the PDF was not read")]
    out: list[Finding] = []
    skipped = [NotAssessed(location=location, check="hidden-text",
                           reason="text colour is not readable from a PDF's text layer; white text is checked in the "
                                  "LaTeX or Word source instead")]
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "in.pdf"
        pdf.write_bytes(data)
        text_run = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, timeout=120)
        if text_run.returncode != 0:
            return [], "", [NotAssessed(location=location, check="all", reason="pdftotext could not read the PDF")]
        text = text_run.stdout.decode("utf-8", "replace")
        bbox_run = subprocess.run(["pdftotext", "-bbox", "-enc", "UTF-8", str(pdf), "-"], capture_output=True,
                                  timeout=120)
        bbox = bbox_run.stdout.decode("utf-8", "replace") if bbox_run.returncode == 0 else ""
        info = ""
        if shutil.which("pdfinfo"):
            info_run = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, timeout=60)
            info = info_run.stdout.decode("utf-8", "replace") if info_run.returncode == 0 else ""
    for page_no, page in enumerate(re.findall(r"<page\b([^>]*)>(.*?)</page>", bbox, re.DOTALL), start=1):
        attrs, body = page
        width = float(re.search(r'width="([\d.]+)"', attrs).group(1)) if 'width="' in attrs else 1e9
        height = float(re.search(r'height="([\d.]+)"', attrs).group(1)) if 'height="' in attrs else 1e9
        runs: list[tuple[str, list[str]]] = []
        for m in re.finditer(r'<word xMin="([-\d.]+)" yMin="([-\d.]+)" xMax="([-\d.]+)" yMax="([-\d.]+)">(.*?)</word>',
                             body):
            x0, y0, x1, y1 = (float(v) for v in m.groups()[:4])
            word = re.sub(r"&amp;", "&", re.sub(r"&lt;", "<", re.sub(r"&gt;", ">", m.group(5))))
            how = ("tiny font (under 2 pt)" if (y1 - y0) < 2.0 else
                   "outside the page" if x1 < 0 or y1 < 0 or x0 > width or y0 > height else None)
            if how is None:
                continue
            if runs and runs[-1][0] == how:
                runs[-1][1].append(word)
            else:
                runs.append((how, [word]))
        for how, words in runs:
            finding = _classify_hidden(f"{location} p. {page_no}", None, how, " ".join(words))
            if finding:
                out.append(finding)
    for m in INJECTION.finditer(text):
        page_no = text.count("\f", 0, m.start()) + 1
        if any(f.check == "injection" and f.location == f"{location} p. {page_no}" for f in out):
            continue
        out.append(Finding(check="injection", severity=Severity.major, location=f"{location} p. {page_no}",
                           excerpt=_snippet(text[max(0, m.start() - 30):m.end() + 30]),
                           message="Text addressed to an AI reviewer is in the PDF text layer.",
                           suggestion="Check the page: if it is not visible there it is hidden (for example by colour) "
                                      "and must be removed; if the paper quotes it as an example, it is fine."))
    out += [f for f in text_findings(location, text, with_lines=False) if f.check != "injection"]
    for key, value in re.findall(r"^(Title|Author|Subject|Keywords|Creator):\s*(.+)$", info, re.MULTILINE):
        if key == "Author" or LOCAL_PATH.search(value):
            out.append(Finding(check="anonymity" if anonymous else "metadata",
                               severity=Severity.major if anonymous else Severity.info, location=location,
                               excerpt=_snippet(value, 80), message=f"PDF metadata {key}: '{_snippet(value, 80)}'.",
                               suggestion="Clear the metadata (for example \\hypersetup{pdfauthor={}}) if the review is "
                                          "anonymous." if anonymous else "Check it is what readers should see."))
    return out, text, skipped


# --------------------------------------------------------------------------------------------------
# Figures (Pillow)
# --------------------------------------------------------------------------------------------------

EXIF_PEOPLE = {0x013B: "Artist", 0x8298: "Copyright", 0x9C9D: "XPAuthor", 0xA430: "CameraOwnerName",
               0xA431: "BodySerialNumber"}


def _degrees(value: object) -> Optional[float]:
    try:
        d, m, s = (float(x) for x in value)  # type: ignore[union-attr]
    except (TypeError, ValueError):
        return None
    return d + m / 60 + s / 3600


def image_findings(location: str, data: bytes, anonymous: bool) -> tuple[list[Finding], list[NotAssessed]]:
    if Image is None:
        return [], [NotAssessed(location=location, check="metadata",
                                reason="Pillow is not installed; EXIF GPS and author tags were not read "
                                       "(run with `uv run --script`, which installs it)")]
    try:
        with Image.open(io.BytesIO(data)) as img:
            exif = img.getexif()
            info = dict(img.info)
    except Exception as exc:  # noqa: BLE001 - any decoder error means the file was not read
        return [], [NotAssessed(location=location, check="metadata", reason=f"image could not be read ({type(exc).__name__})")]
    out: list[Finding] = []
    gps = exif.get_ifd(0x8825) if exif else {}
    if gps:
        lat, lon = _degrees(gps.get(2)), _degrees(gps.get(4))
        if lat is not None and lon is not None:
            lat = -lat if str(gps.get(1, "N")).upper().startswith("S") else lat
            lon = -lon if str(gps.get(3, "E")).upper().startswith("W") else lon
            out.append(Finding(check="metadata", severity=Severity.major, location=location,
                               excerpt=f"{lat:.3f}, {lon:.3f}",
                               message=f"The image records a GPS position ({lat:.3f}, {lon:.3f}).",
                               suggestion="Strip the metadata before submitting (for example `exiftool -all= FILE` or "
                                          "re-export without metadata); a position can identify a home, a clinic or "
                                          "a field site."))
        else:
            out.append(Finding(check="metadata", severity=Severity.minor, location=location,
                               message="The image carries a GPS block without a full position.",
                               suggestion="Strip the metadata before submitting."))
    people: list[str] = []
    for tag, label in EXIF_PEOPLE.items():
        value = exif.get(tag) if exif else None
        if isinstance(value, bytes):
            value = value.decode("utf-16-le" if tag == 0x9C9D else "utf-8", "replace").strip("\x00 ")
        if value and str(value).strip():
            people.append(f"{label} '{_snippet(str(value), 40)}'")
    for key in ("Author", "Copyright", "Artist"):
        if isinstance(info.get(key), str) and info[key].strip():
            people.append(f"{key} '{_snippet(info[key], 40)}'")
    xmp = info.get("xmp") or info.get("XML:com.adobe.xmp")
    if isinstance(xmp, (bytes, str)):
        xmp_text = xmp.decode("utf-8", "replace") if isinstance(xmp, bytes) else xmp
        for creator in re.findall(r"<dc:creator>.*?<rdf:li[^>]*>([^<]+)</rdf:li>", xmp_text, re.DOTALL):
            people.append(f"XMP creator '{_snippet(creator, 40)}'")
    if people:
        out.append(Finding(check="anonymity" if anonymous else "metadata",
                           severity=Severity.major if anonymous else Severity.minor, location=location,
                           excerpt="; ".join(people), message=f"Author or owner tags in the figure file: {'; '.join(people)}.",
                           suggestion="Strip the metadata if the review is anonymous or the tags are not meant to be "
                                      "published."))
    return out, []


# --------------------------------------------------------------------------------------------------
# Anonymity
# --------------------------------------------------------------------------------------------------

def _name_pattern(name: str) -> re.Pattern[str]:
    parts = [re.escape(p.strip(".")) for p in name.split() if p.strip(".")]
    body = r"\.?\s+".join(parts)
    return re.compile(rf"(?<![\w@]){body}(?![\w@])", re.IGNORECASE)


def _reference_start(text: str) -> int:
    m = re.search(r"(?im)^#{1,6}\s*\**\s*(?:references|bibliography|literature cited)\b|\\begin\{thebibliography\}|"
                  r"\\bibliography\{|\\printbibliography|^\s*references\s*$", text)
    return m.start() if m else len(text)


def anonymity_findings(location: str, text: str, authors: list[str], affiliations: list[str],
                       with_lines: bool = True) -> list[Finding]:
    out: list[Finding] = []
    body = text[:_reference_start(text)]

    def add(offset: int, severity: Severity, message: str, suggestion: str, excerpt: str = "") -> None:
        line = _line_of(text, offset) if with_lines else None
        out.append(Finding(check="anonymity", severity=severity, location=f"{location}:{line}" if line else location,
                           line=line, excerpt=excerpt or _snippet(text[max(0, offset - 30):offset + 60]),
                           message=message, suggestion=suggestion))

    for term in authors + affiliations:
        for m in _name_pattern(term).finditer(body):
            add(m.start(), Severity.major, f"'{term}' appears outside the reference list.",
                "Remove or anonymise it for review (a name in your own reference list, cited in the third person, is "
                "usually allowed).")
    for m in re.finditer(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", body):
        add(m.start(), Severity.major, f"E-mail address '{m.group(0)}'.", "Remove it from the review version.")
    for m in re.finditer(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b", body):
        add(m.start(), Severity.major, "ORCID iD.", "Remove it from the review version.")
    ack = re.search(r"(?im)^#{1,6}\s*\**\s*acknowledge?ments?\b|\\(?:section|subsection|paragraph)\*?\s*\{\s*acknowledge?"
                    r"ments?\s*\}|\\begin\s*\{\s*ack\s*\}|\\acks\b", body)
    if ack:
        add(ack.start(), Severity.minor, "Acknowledgements section present.",
            "Check the venue's rule: double-blind venues usually ask for it to be removed or anonymised for review.")
    for m in re.finditer(r"(?i)\b(?:our|we)\s+(?:(?:previous|prior|earlier|recent)\s+)?(?:work|study|paper|tool|method|"
                         r"pipeline|analysis)s?\b[^.\n]{0,40}?(?:\[\d+|\\cite\w*\{|\([A-Z][\w-]+[^()]{0,30}(?:19|20)\d{2})",
                         body):
        add(m.start(), Severity.minor, "First-person reference to the authors' own published work.",
            "Cite your earlier work in the third person ('Smith et al. showed') for review.")
    for m in re.finditer(r"https?://(?:www\.)?(?:github|gitlab|bitbucket)\.(?:com|org)/([\w.-]+)", body):
        add(m.start(), Severity.minor, f"Repository URL naming the account '{m.group(1)}'.",
            "Use an anonymised mirror (for example anonymous.4open.science) for review.")
    # LaTeX comments are blanked (offsets kept), so a commented-out "% \usepackage[accepted]{...}" sets nothing.
    uncommented = "\n".join(line[:c[0]] + " " * (len(line) - c[0]) if (c := tex_comment(line)) else line
                            for line in text.split("\n"))
    for m in re.finditer(r"\\usepackage\s*\[[^\]]*\b(?:final|accepted|camera-?ready)\b[^\]]*\]|\\(?:iclr|acl|naacl|emnlp|"
                         r"icml)finalcopy\b", uncommented):
        add(m.start(), Severity.minor, "Camera-ready option set: the template will print the author block.",
            "Use the review option of the template.")
    return out


# --------------------------------------------------------------------------------------------------
# The package
# --------------------------------------------------------------------------------------------------

def _is_archive(name: str) -> bool:
    return name.lower().endswith(ARCHIVE_SUFFIXES)


def iter_package(paths: list[Path]) -> Iterator[tuple[str, str, bytes]]:
    """(location, lower-case name, bytes) for every file in the inputs, archives expanded in memory."""
    for path in paths:
        if path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.is_file() and not any(part in SKIP_DIRS for part in f.relative_to(path).parts):
                    yield from _file_entries(str(f), f)
        else:
            yield from _file_entries(str(path), path)


def _file_entries(location: str, path: Path) -> Iterator[tuple[str, str, bytes]]:
    name = path.name.lower()
    data = path.read_bytes()
    if not _is_archive(name):
        yield location, name, data
        return
    yield from _archive_entries(location, name, data)


def _archive_entries(location: str, name: str, data: bytes) -> Iterator[tuple[str, str, bytes]]:
    count = 0
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                count += 1
                if count > MAX_MEMBERS:
                    yield f"{location}:…", "__truncated__", b""
                    return
                yield f"{location}:{info.filename}", Path(info.filename).name.lower(), archive.read(info)
        return
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as archive:
        for member in archive:
            if not member.isfile():
                continue
            count += 1
            if count > MAX_MEMBERS:
                yield f"{location}:…", "__truncated__", b""
                return
            handle = archive.extractfile(member)
            if handle is not None:
                yield f"{location}:{member.name}", Path(member.name).name.lower(), handle.read()


def _decode(data: bytes) -> Optional[str]:
    if len(data) > MAX_TEXT_BYTES or b"\x00" in data[:2048]:
        return None
    return data.decode("utf-8", "replace")


def _suffix(name: str) -> str:
    return Path(name).suffix.lower()


def check_package(paths: list[Path], anonymous: bool = False, authors: Optional[list[str]] = None,
                  affiliations: Optional[list[str]] = None) -> HygieneReport:
    authors, affiliations = authors or [], affiliations or []
    findings: list[Finding] = []
    skipped: list[NotAssessed] = []
    files: dict[str, int] = {}

    def count(kind: str) -> None:
        files[kind] = files.get(kind, 0) + 1

    for location, name, data in iter_package(paths):
        if name == "__truncated__":
            skipped.append(NotAssessed(location=location, check="all",
                                       reason=f"archive has more than {MAX_MEMBERS} files; the rest were not read"))
            continue
        suffix = _suffix(name)
        visible = ""
        if suffix == ".docx":
            count("word")
            found, visible, na = docx_findings(location, data, anonymous)
            findings += found
            skipped += na
            findings += [f for f in text_findings(location, visible, with_lines=False)]
        elif suffix == ".doc":
            count("word")
            skipped.append(NotAssessed(location=location, check="all", reason="legacy .doc is not read; save as .docx"))
        elif suffix == ".pdf":
            count("pdf")
            found, visible, na = pdf_findings(location, data, anonymous)
            findings += found
            skipped += na
        elif suffix in IMAGE_EXT:
            count("image")
            found, na = image_findings(location, data, anonymous)
            findings += found
            skipped += na
        else:
            text = _decode(data)
            if text is None:
                count("other (not read)")
                continue
            kind = ("latex" if suffix in TEX_EXT else "latex support" if suffix in TEX_SUPPORT_EXT
                    else "markdown" if suffix in MD_EXT else "html" if suffix in HTML_EXT else "text")
            count(kind)
            found = text_findings(location, text)
            if suffix in TEX_EXT:
                found += tex_findings(location, text)
            elif suffix in MD_EXT or suffix in HTML_EXT:
                found += markup_findings(location, text)
            if kind in ("latex", "markdown", "html", "text"):
                found += revision_mark_findings(location, text)
            if anonymous and suffix not in (".bib", ".bbl", ".bst"):
                found += anonymity_findings(location, text, authors, affiliations)
            findings += _with_sections(found, text) if suffix in TEX_EXT | MD_EXT | HTML_EXT else found
            continue
        if anonymous and visible:
            findings += anonymity_findings(location, visible, authors, affiliations, with_lines=False)
    if not files:
        skipped.append(NotAssessed(location=", ".join(map(str, paths)), check="all", reason="no files found"))
    findings = _staged(_drop_shadowed(findings))
    order = {s: i for i, s in enumerate(Severity)}
    findings.sort(key=lambda f: (order[f.severity], f.location, f.line or 0))
    digests = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
    return HygieneReport(inputs=[str(p) for p in paths], files=files, findings=findings, not_assessed=skipped,
                         sha256=digests)


def _staged(findings: list[Finding]) -> list[Finding]:
    """Checking the upload files is the last step, except for what cannot wait (author-priorities.md): text hidden for
    AI reviewers misleads the review whenever it is found, and a key that has been in a shared file is exposed now."""
    for f in findings:
        if f.check == "secrets" or (f.check == "injection" and f.severity in (Severity.blocker, Severity.major)):
            f.stage = "now"
    return findings


def offline_text_checks(path: Path) -> list[Finding]:
    """The checks the pre-commit hook runs on a manuscript source: comments, hidden text, secrets."""
    text = path.read_text(encoding="utf-8", errors="replace")
    found = text_findings(str(path), text)
    if path.suffix.lower() in TEX_EXT:
        found += tex_findings(str(path), text)
    elif path.suffix.lower() in MD_EXT | HTML_EXT:
        found += markup_findings(str(path), text)
    order = {s: i for i, s in enumerate(Severity)}
    return sorted(_staged(_drop_shadowed(_with_sections(found, text))), key=lambda f: (order[f.severity], f.line or 0))


SEVERITY_LEAD = {Severity.blocker: "Serious", Severity.major: "Important", Severity.minor: "Minor",
                 Severity.info: "To look at"}
NUMBERED = re.compile(r"^(?P<number>(?:\d+(?:\.\d+)*|[IVX]+))[.)]?\s+(?P<title>\S.*)$")
# Headings read naturally after "the" ("in the Methods"); any other heading is quoted ("in the section “Speed”").
PLAIN_HEADINGS = re.compile(r"^(?:abstract|introduction|background|methods?|materials|results|discussion|conclusions?|"
                            r"references|bibliography|acknowledge?ments|funding|supplementary|appendix|limitations|"
                            r"data|code|availability|declarations?|author|competing|ethics)\b", re.IGNORECASE)
WHAT_IS_QUOTED = {"comments": "the comment reads", "hidden-text": "the hidden text reads",
                  "injection": "the text reads", "invisible-characters": "the hidden characters spell",
                  "secrets": "the masked value is", "local-paths": "the path reads", "links": "the link is",
                  "anonymity": "the text reads", "metadata": "the recorded value is", "word-review": "it reads",
                  "revision-marks": "the first reads"}


def where(f: Finding) -> str:
    """'In main.tex, under the Methods (line 31)': the file, the heading and the line, never a bare line number."""
    file = f.location[: -len(f":{f.line}")] if f.line and f.location.endswith(f":{f.line}") else f.location
    under = ""
    if f.section == "Front matter":
        under = ", before the first heading"
    elif f.section:
        numbered = NUMBERED.match(f.section.split(", ")[-1])
        under = (f", under section {numbered.group('number')}, {numbered.group('title')}" if numbered
                 else f", under the {f.section}" if PLAIN_HEADINGS.match(f.section)
                 else f", under the heading “{f.section}”")
    return f"In {file}{under}" + (f" (line {f.line})" if f.line else "")


def _sentence(text: str) -> str:
    text = " ".join(text.split())
    return text if not text or text[-1] in ".!?”" else text + "."


def finding_text(f: Finding) -> str:
    """One finding as sentences: what is wrong, where it is with its text quoted, and what to do."""
    place = where(f)
    if f.excerpt and f.excerpt.startswith("“"):  # several comments, each quoted with its line
        place += f", the first of them read {f.excerpt}."
    elif f.excerpt:
        place += f", {WHAT_IS_QUOTED.get(f.check, 'the text reads')} “{f.excerpt}”" + (
            "" if f.excerpt.rstrip("…")[-1:] in ".!?" and not f.excerpt.endswith("…") else ".")
    else:
        place += "."
    return " ".join(p for p in (_sentence(f.message), place, _sentence(f.suggestion)) if p)


def to_markdown(report: HygieneReport) -> str:
    counts = {s: sum(f.severity == s for f in report.findings) for s in Severity}
    examined = ", ".join(f"{n} {k}" for k, n in sorted(report.files.items())) or "no files"
    found = ", ".join(f"{counts[s]} {SEVERITY_LEAD[s].lower()}" for s in Severity if counts[s]) or "nothing"
    out = [f"# Submission files: {', '.join(Path(i).name for i in report.inputs)}", "",
           f"Files examined: {examined}. This check lists what a journal or preprint server would publish or read "
           "beyond the PDF: comments, hidden text, secrets, local paths, shared-document links and file metadata. It "
           "changes nothing, and secrets are masked.", "",
           f"Found: {found}. Within each group the most serious findings come first: “Serious” marks what misleads "
           "the review or could get the paper returned, “Important” what should not be published with the files, "
           "“Minor” what is worth cleaning, and “To look at” what may be fine.", ""]
    urgent = [f for f in report.findings if f.stage == "now"]
    later = [f for f in report.findings if f.stage != "now"]
    if urgent:
        out += ["## Fix now, whatever the stage", "",
                "These cannot wait for the last step before submission: text hidden for AI reviewers misleads the "
                "review whoever reads the files, and a key that has been in a shared file should be treated as "
                "exposed already, so it needs revoking now even after it is deleted.", ""]
        out += [f"- **{SEVERITY_LEAD[f.severity]}.** {finding_text(f)}" for f in urgent]
        out.append("")
    if later:
        out += ["## Before submission, once the code is final", "",
                "All of these concern the files as they will be uploaded, so they are done in the last step before "
                "submission. They are not problems with the draft while it is being written.", ""]
        out += [f"- **{SEVERITY_LEAD[f.severity]}.** {finding_text(f)}" for f in later]
        out.append("")
    if report.not_assessed:
        out += ["## What could not be checked", ""]
        out += [f"- {n.location}: {_sentence(n.reason[:1].upper() + n.reason[1:])}" for n in report.not_assessed]
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def exit_code(report: HygieneReport, final: bool = False) -> int:
    """1 when a blocker or major finding counts now: text hidden for AI reviewers or a leaked secret at any stage,
    and every other one too when the authors are about to submit (--final); else 0."""
    return 1 if any(f.severity in (Severity.blocker, Severity.major) and (final or f.stage == "now")
                    for f in report.findings) else 0


def _utf8_console() -> None:
    """UTF-8 on the console whatever the platform's default (a Windows console is often cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):  # a stream that cannot change its encoding keeps it
                pass


@app.command()
def main(
    paths: Annotated[list[Path], typer.Argument(exists=True, readable=True, help="Files, directories or archives")],
    anonymous: Annotated[bool, typer.Option(help="Check for self-identifying text (double-blind review)")] = False,
    author: Annotated[Optional[list[str]], typer.Option(help="An author's name, for --anonymous (repeatable)")] = None,
    affiliation: Annotated[Optional[list[str]], typer.Option(help="An affiliation, for --anonymous (repeatable)")] = None,
    final: Annotated[bool, typer.Option(help="The authors are about to submit: every blocker and major finding "
                                             "counts in the exit code, not only hidden text and leaked secrets")] = False,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the full report as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the Markdown report here (default: stdout)")] = None,
) -> None:
    _utf8_console()
    if (author or affiliation) and not anonymous:
        raise typer.BadParameter("--author and --affiliation are used only with --anonymous")
    report = check_package(paths, anonymous, author or [], affiliation or [])
    md = to_markdown(report)
    if json_out:
        json_out.write_text(json.dumps(report.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {md_out}")
    else:
        typer.echo(md)
    raise typer.Exit(code=exit_code(report, final))


if __name__ == "__main__":
    app()
