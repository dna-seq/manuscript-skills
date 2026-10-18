# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "httpx>=0.27", "pydantic>=2.6", "pyyaml>=6"]
# ///
"""Find the data, code and software a manuscript points to, classify every accession and link, flag
availability problems and, with --online, ask each public archive whether the record exists.

It reports; it never rewrites. Whether a statement is adequate for this study and venue is the skill's
judgement (manuscript-reporting-check/SKILL.md, references/availability.md).

    uv run --script check_availability.py PAPER.md                        # offline: extract and flag
    uv run --script check_availability.py PAPER.md --online               # also resolve every identifier
    uv run --script check_availability.py PAPER.md --venue bioinformatics-note --json out.json --md out.md
    uv run --script check_availability.py PAPER.md --record manuscript-record.yaml   # venue from the record

Identifier states: resolves | not_found | restricted (controlled access or embargo: legitimate, not a
defect) | not_assessed (with the reason). The reference list is left to manuscript-reference-check.
Licence, release and version checks run only on the authors' own code (named in a statement, or under an owner
a statement names); a tool in a comparison table or cited software is checked for existence only. Anonymised
review links (anonymous.4open.science) are never looked up.

Exit codes: 0 no major finding; 1 at least one major finding; 2 usage error.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from collections import Counter
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Callable, Optional
from urllib.parse import quote

import httpx
import typer
import yaml
from pydantic import BaseModel, Field

app = typer.Typer(add_completion=False, no_args_is_help=True)

USER_AGENT = ("manuscript-reporting-check/0.1 (pre-submission availability check; "
              "https://github.com/dna-seq/manuscript-skills)")
VENUES_PY = Path(__file__).resolve().parents[2] / "manuscript-journal-adapt" / "scripts" / "venues.py"
VENUES_YAML_OVERRIDE: Optional[Path] = None  # tests point the venue reader at a synthetic catalogue
# Seconds between requests to one host: NCBI allows 3 per second without a key, GitHub 60 per hour.
MIN_INTERVAL = {"eutils.ncbi.nlm.nih.gov": 0.34, "www.ncbi.nlm.nih.gov": 0.34, "api.github.com": 0.5}


class Severity(str, Enum):
    blocker = "blocker"  # never emitted by this script: a venue rule must be verified on the live page first
    major = "major"
    optional = "optional"
    uncertain = "uncertain"


class State(str, Enum):
    resolves = "resolves"
    not_found = "not_found"
    restricted = "restricted"
    not_assessed = "not_assessed"


class Stage(str, Enum):
    """When the authors can act on a finding (author-priorities.md, "Order the work by when it can be done")."""
    now = "now"
    writing = "writing"
    journal = "journal"
    final = "final"


STAGE_HEADING = {Stage.now: "Fix now", Stage.writing: "Then the writing",
                 Stage.journal: "Once you have chosen the journal",
                 Stage.final: "Before submission, once the code is final"}


class Mention(BaseModel):
    """A version of the authors' own software cited by name in the text ("Just-DNA-Lite 0.3.25"), not in a link."""
    version: str
    line: int
    section: str = ""
    quote: str = ""
    span: str = ""
    exists: Optional[bool] = None  # None: not looked up


class Identifier(BaseModel):
    kind: str
    family: str
    role: str  # data | code | archive | package | container | model | resource
    value: str
    url: str = ""
    line: int
    lines: list[int] = Field(default_factory=list)
    excerpt: str = ""
    section: str = ""
    quote: str = ""  # the sentence (or table row) of the first occurrence, trimmed around it
    span: str = ""  # the identifier as written there
    mentions: list[Mention] = Field(default_factory=list)
    in_statement: bool = False
    in_table: bool = False  # every occurrence sits in a table row (a comparison of other tools, a list)
    own: bool = False  # the authors' own: named in a statement, or code under an owner a statement names
    excluded: bool = False  # every occurrence follows "excluding", "except" or similar in its clause
    archives_code: bool = True  # archive role: some occurrence outside tables reads as code, not as data
    version: Optional[str] = None
    well_formed: bool = True
    problem: str = ""
    suggested: str = ""  # the well-formed spelling, when the malformed one has an obvious repair
    state: State = State.not_assessed
    detail: str = "offline: not resolved"
    title: str = ""
    licence: str = ""
    flags: list[str] = Field(default_factory=list)


class Statement(BaseModel):
    label: str
    covers: list[str]  # data, code
    start: int
    end: int
    names: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    in_article: bool = False
    request_route: bool = False
    not_applicable: bool = False


class Finding(BaseModel):
    check: str
    severity: Severity
    line: Optional[int] = None
    excerpt: str = ""
    message: str
    suggestion: str = ""
    rule: str = ""
    title: str = ""  # the finding in plain words, for the report heading
    stage: Optional[Stage] = None  # None: a note on what the run could not check
    section: str = ""
    quote: str = ""  # the manuscript's sentence or row, trimmed to about 160 characters around the problem
    span: str = ""  # the part of `quote` the finding is about


class VenueRules(BaseModel):
    key: str
    name: str
    publisher: str = ""
    url: str = ""
    checked: str = ""
    rules: list[str] = Field(default_factory=list)
    wants_archive: bool = False
    wants_licence: bool = False
    request_refused: bool = False
    availability_years: Optional[int] = None
    in_abstract: bool = False
    reporting_checklist: bool = False


class Report(BaseModel):
    path: str
    online: bool
    venue: Optional[VenueRules] = None
    statements: list[Statement]
    identifiers: list[Identifier]
    findings: list[Finding]


# ------------------------------------------------------------------------------------------- text layout

HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
MD_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LATEX_HEADING = re.compile(r"^\s*\\(part|chapter|section|subsection|subsubsection|paragraph)\*?\{(.*?)\}")
LATEX_LEVEL = {"part": 0, "chapter": 1, "section": 2, "subsection": 3, "subsubsection": 4, "paragraph": 5}
REF_TITLE = re.compile(r"^\W*(?:\d+\.?\s*)?(references|bibliography|literature cited|works cited|reference list)\W*$",
                       re.IGNORECASE)
ABSTRACT_TITLE = re.compile(r"^\W*(abstract|summary)\W*$", re.IGNORECASE)
_NOUN = r"(?:data|code|software|materials?|resources?)"
LABEL = re.compile(
    rf"{_NOUN}(?:\s*(?:,|and|&)\s*(?:and\s+)?{_NOUN})*\s+(?:availability|accessibility|access|sharing|deposition)"
    rf"(?:\s+statement)?"
    rf"|availability\s+of\s+{_NOUN}(?:\s*(?:,|and|&)\s*(?:and\s+)?{_NOUN})*"
    r"|availability\s+and\s+(?:implementation|requirements)"
    r"|accession\s+(?:numbers?|codes?)|key\s+resources\s+table",
    re.IGNORECASE)
LEAD_IN = re.compile(rf"^\s*(?:\*\*|__|\\textbf\{{|\\paragraph\*?\{{)?\s*({LABEL.pattern})\s*(?:\*\*|__|\}})?\s*([:.])?",
                     re.IGNORECASE)


def _blank(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def prepare(text: str, latex: bool) -> list[str]:
    """The manuscript's lines with comments blanked, so line numbers stay those of the file."""
    text = HTML_COMMENT.sub(_blank, text)
    lines = text.splitlines()
    if latex:
        lines = [re.sub(r"(?<!\\)%.*$", "", line) for line in lines]
    return lines


TABULAR = r"\{(?:tabular\*?|tabularx|tabulary|longtable\*?|supertabular|xtabular)\}"


def table_mask(lines: list[str]) -> list[bool]:
    """Per line: a Markdown table row or a line inside a LaTeX tabular environment."""
    out: list[bool] = []
    inside = False
    for line in lines:
        if re.search(r"\\begin" + TABULAR, line):
            inside = True
        out.append(inside or line.lstrip().startswith("|"))
        if re.search(r"\\end" + TABULAR, line):
            inside = False
    return out


def _heading(line: str) -> Optional[tuple[int, str]]:
    m = MD_HEADING.match(line)
    if m:
        return len(m.group(1)), m.group(2).strip("*_ ").strip()
    m = LATEX_HEADING.match(line)
    if m:
        return LATEX_LEVEL[m.group(1)], m.group(2).strip()
    return None


def layout(lines: list[str]) -> tuple[list[str], list[bool], Optional[tuple[int, int]]]:
    """Per line: the heading it sits under and whether it is in the reference list; plus the abstract's
    0-based line span (from its heading or abstract environment to the next heading)."""
    sections: list[str] = []
    skip: list[bool] = []
    current, ref_level, in_bib = "", None, False
    abstract: Optional[tuple[int, int]] = None
    abstract_start: Optional[int] = None
    latex_abstract = False  # an abstract environment ends at \\end{abstract}, a heading's at the next heading
    for i, line in enumerate(lines):
        head = _heading(line)
        if "\\begin{thebibliography}" in line:
            in_bib = True
        if "\\begin{abstract}" in line and abstract_start is None:
            abstract_start, latex_abstract = i + 1, True
        if "\\end{abstract}" in line and latex_abstract and abstract is None:
            abstract = (abstract_start, i)
        if head:
            level, title = head
            if abstract_start is not None and abstract is None and not latex_abstract:
                abstract = (abstract_start, i)
            if ref_level is not None and level <= ref_level:
                ref_level = None
            if REF_TITLE.match(title):
                ref_level = level
            if ABSTRACT_TITLE.match(title) and abstract_start is None:
                abstract_start = i + 1
            current = title
        sections.append(current)
        skip.append(in_bib or ref_level is not None)
        if "\\end{thebibliography}" in line:
            in_bib = False
    if abstract is None and abstract_start is not None:
        abstract = (abstract_start, len(lines))
    return sections, skip, abstract


def _covers(label: str) -> list[str]:
    covers = []
    if re.search(r"data|accession|material|resource|key resources", label, re.IGNORECASE):
        covers.append("data")
    if re.search(r"code|software|implementation|requirements", label, re.IGNORECASE):
        covers.append("code")
    return covers or ["data"]


def find_statements(lines: list[str], skip: list[bool]) -> list[Statement]:
    """Availability statements: a heading that is the label, or a paragraph that opens with it."""
    out: list[Statement] = []
    i = 0
    while i < len(lines):
        if skip[i]:
            i += 1
            continue
        head = _heading(lines[i])
        title = re.sub(r"^\W*(?:\d+(?:\.\d+)*\.?\s*)?|\W*$", "", head[1]) if head else ""
        if head and LABEL.fullmatch(title):
            level = head[0]
            end = i + 1
            while end < len(lines):
                nxt = _heading(lines[end])
                if nxt and nxt[0] <= level:
                    break
                end += 1
            out.append(Statement(label=title, covers=_covers(title), start=i + 1, end=end))
            i += 1
            continue
        m = LEAD_IN.match(lines[i])
        if m and not head and (m.group(2) or re.match(r"\s*(\*\*|__|\\textbf|\\paragraph)", lines[i])):
            end = i + 1
            while end < len(lines) and lines[end].strip() and not _heading(lines[end]):
                end += 1
            out.append(Statement(label=m.group(1), covers=_covers(m.group(1)), start=i + 1, end=end))
            i = end
            continue
        i += 1
    return out


# ------------------------------------------------------------------------------------------- extraction

URL = re.compile(r"(?:https?://|www\.)[^\s<>\"'`)\]}|]+")
VERSION_NEAR = re.compile(r"\b(?:version|release|tag)\s+v?(\d+(?:\.\d+)+(?:[-.+]?[A-Za-z0-9]+)*)\b"
                          r"|\bv(\d+(?:\.\d+)+(?:[-.+]?[A-Za-z0-9]+)*)\b", re.IGNORECASE)
COMMIT_NEAR = re.compile(r"\bcommit\s+([0-9a-f]{7,40})\b", re.IGNORECASE)
BRANCHES = {"main", "master", "develop", "dev", "devel", "head", "trunk", "gh-pages", "latest"}
NOT_GITHUB_OWNERS = {"orgs", "features", "topics", "sponsors", "settings", "marketplace", "about", "pricing",
                     "collections", "login", "join", "apps", "search", "explore", "notifications", "site"}
NOT_HF_OWNERS = {"papers", "blog", "docs", "spaces", "collections", "learn", "organizations", "settings", "models",
                 "datasets", "tasks", "join", "login", "pricing", "chat", "posts", "api", "new"}
STOPWORDS = {"and", "or", "the", "a", "an", "under", "with", "as", "at", "from", "is", "package", "packages", "in",
             "repository", "index", "for", "of", "to", "via", "on"}

FAMILY = {
    "geo": ("GEO", "data"), "insdc": ("SRA/ENA/DDBJ", "data"), "arrayexpress": ("ArrayExpress", "data"),
    "biostudies": ("BioStudies", "data"), "dbgap": ("dbGaP", "data"), "ega": ("EGA", "data"),
    "pdb": ("PDB", "data"), "gwas-catalog": ("GWAS Catalog", "data"), "pgs-catalog": ("PGS Catalog", "data"),
    "zenodo": ("Zenodo", "archive"), "figshare": ("figshare", "archive"), "dryad": ("Dryad", "archive"),
    "osf": ("OSF", "archive"), "swh": ("Software Heritage", "archive"), "doi": ("DOI", "archive"),
    "github": ("GitHub", "code"), "gitlab": ("GitLab", "code"), "code-other": ("code host", "code"),
    "anon-review": ("anonymised review link", "code"),
    "pypi": ("PyPI", "package"), "cran": ("CRAN", "package"), "bioconductor": ("Bioconductor", "package"),
    "bioconda": ("Bioconda", "package"), "conda-forge": ("conda-forge", "package"), "conda": ("conda", "package"),
    "docker": ("Docker Hub", "container"), "quay": ("Quay", "container"), "ghcr": ("GHCR", "container"),
    "container-other": ("container registry", "container"),
    "hf-dataset": ("Hugging Face dataset", "data"), "hf-model": ("Hugging Face model", "model"),
    "hf-space": ("Hugging Face Space", "code"), "hf-repo": ("Hugging Face repository", "data"),
    "rrid": ("RRID", "resource"), "web": ("web address", "resource"),
}

Hit = tuple[str, str, str, Optional[str], bool, str, str, int]  # kind, value, url, version, ok, problem, suggested, col


def _hit(kind: str, value: str, col: int, url: str = "", version: Optional[str] = None, ok: bool = True,
         problem: str = "", suggested: str = "") -> Hit:
    return kind, value, url, version, ok, problem, suggested, col


def _geo(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"\bG(SE|SM|PL|DS)(?=[\s:_#-]{0,2}\d)[\s:_#-]{0,2}\d[0-9A-Za-z_-]*", line):
        token, prefix = m.group(0), "G" + m.group(1)
        if re.fullmatch(r"G(?:SE|SM|DS)\d{1,7}|GPL\d{3,7}", token):
            out.append(_hit("geo", token, m.start(), f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={token}"))
        elif prefix == "GPL":
            continue  # GPL-3.0, GPL 2, GPL3: licences, not GEO platforms
        elif re.fullmatch(r"G(?:SE|SM|DS)[\s:_#-]{1,2}\d{1,7}", token):
            fixed = prefix + re.sub(r"\D", "", token)
            out.append(_hit("geo", token, m.start(), ok=False, problem="it is written with a separator", suggested=fixed))
        else:
            out.append(_hit("geo", token, m.start(), ok=False,
                            problem=f"{prefix} must be followed by digits only"))
    return out


INSDC_PREFIX = r"(?:[SED]R[APRXS]|PRJ(?:NA|EB|DB)|SAM(?:N|EA|D))"


def _insdc(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"\b(?:[SED]R[APRXS]\d{6,10}|PRJ(?:NA|EB|DB)\d{1,9}|SAM(?:N|EA|D)\d{5,10})\b", line):
        out.append(_hit("insdc", m.group(0), m.start(), f"https://www.ebi.ac.uk/ena/browser/view/{m.group(0)}"))
    # A separator inside an otherwise complete accession. Short forms are never read: SRP54, ERP29 and DRP1
    # are gene symbols, not accessions.
    for m in re.finditer(rf"\b({INSDC_PREFIX})[\s:_-]+(\d{{6,10}})\b", line):
        out.append(_hit("insdc", m.group(0), m.start(), ok=False, problem="it is written with a separator",
                        suggested=m.group(1) + m.group(2)))
    return out


def _arrayexpress(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"\bE-[A-Z]{4}-\d+\b", line):
        out.append(_hit("arrayexpress", m.group(0), m.start(),
                        f"https://www.ebi.ac.uk/biostudies/arrayexpress/studies/{m.group(0)}"))
    for m in re.finditer(r"\bE(-?)(MTAB|GEOD|MEXP|TABM|ATMX|MARS)([\s_-]*)(\d+)\b", line):
        if not (m.group(1) == "-" and m.group(3) == "-"):
            out.append(_hit("arrayexpress", m.group(0), m.start(), ok=False, problem="its hyphens are missing or misplaced",
                            suggested=f"E-{m.group(2)}-{m.group(4)}"))
    for m in re.finditer(r"\bS-(?:BSST|BIAD|EPMC|SCDT|BSMS|JCB)\d+\b", line):
        out.append(_hit("biostudies", m.group(0), m.start(), f"https://www.ebi.ac.uk/biostudies/studies/{m.group(0)}"))
    return out


def _dbgap(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"\bphs\d{6}(?:\.v\d+(?:\.p\d+)?)?\b", line):
        out.append(_hit("dbgap", m.group(0), m.start(),
                        f"https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id={m.group(0)}"))
    for m in re.finditer(r"\bphs(?:[\s:_-]+(\d{6})\b|(\d{1,5}|\d{7,})\b)", line):
        if m.group(1):
            out.append(_hit("dbgap", m.group(0), m.start(), ok=False, problem="it is written with a separator",
                            suggested="phs" + m.group(1)))
        else:
            out.append(_hit("dbgap", m.group(0), m.start(), ok=False,
                            problem="a dbGaP study accession is \"phs\" followed by six digits"))
    return out


def _ega(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"\bEGA([SDCFNRXZBP])(?:([\s:_-]+)?(\d+))\b", line):
        sep, digits = m.group(2), m.group(3)
        if not sep and len(digits) == 11:
            out.append(_hit("ega", m.group(0), m.start(), f"https://ega-archive.org/search/{m.group(0)}"))
        elif sep and len(digits) == 11:
            out.append(_hit("ega", m.group(0), m.start(), ok=False, problem="it is written with a separator",
                            suggested=f"EGA{m.group(1)}{digits}"))
        else:
            out.append(_hit("ega", m.group(0), m.start(), ok=False,
                            problem=f"an EGA accession has 11 digits after its prefix and this one has {len(digits)}"))
    return out


PDB_ID = r"[1-9][A-Za-z0-9]{3}"


def _pdb(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"\b(?:PDB|Protein Data Bank)(?:\s+(?:ID|IDs|code|codes|entry|entries|accession|accessions))?"
                         rf"\s*[:#]?\s*\(?((?:{PDB_ID}\b(?:\s*(?:,|and|&|;)\s*)?)+)", line, re.IGNORECASE):
        for idm in re.finditer(PDB_ID, m.group(1)):
            pid = idm.group(0)
            if re.search(r"[A-Za-z]", pid):  # an all-digit token after "PDB" is a year or a count
                out.append(_hit("pdb", pid.upper(), m.start(1) + idm.start(),
                                f"https://www.rcsb.org/structure/{pid.upper()}"))
    for pat in (rf"rcsb\.org/structure/({PDB_ID})\b", rf"ebi\.ac\.uk/pdbe/entry/pdb/({PDB_ID})\b",
                rf"10\.2210/pdb({PDB_ID})/pdb"):
        for m in re.finditer(pat, line, re.IGNORECASE):
            out.append(_hit("pdb", m.group(1).upper(), m.start(), f"https://www.rcsb.org/structure/{m.group(1).upper()}"))
    return out


def _catalogs(line: str) -> list[Hit]:
    out = [_hit("gwas-catalog", m.group(0), m.start(), f"https://www.ebi.ac.uk/gwas/studies/{m.group(0)}")
           for m in re.finditer(r"\bGCST\d{6,8}\b", line)]
    out += [_hit("pgs-catalog", m.group(0), m.start(), f"https://www.pgscatalog.org/score/{m.group(0)}")
            for m in re.finditer(r"\bPGS\d{6}\b", line)]
    return out


def _archives(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"10\.5281/zenodo\.(\d+)", line, re.IGNORECASE):
        out.append(_hit("zenodo", f"10.5281/zenodo.{m.group(1)}", m.start(), f"https://doi.org/10.5281/zenodo.{m.group(1)}"))
    for m in re.finditer(r"zenodo\.org/(?:records?|deposit|uploads)/(\d+)", line, re.IGNORECASE):
        out.append(_hit("zenodo", f"10.5281/zenodo.{m.group(1)}", m.start(), f"https://zenodo.org/records/{m.group(1)}"))
    # Record numbers in prose: "Zenodo record 18370498", "public on Zenodo (records 18370498 and 19487816)".
    # A Zenodo record's DOI is 10.5281/zenodo.<record number>.
    for m in re.finditer(r"\bZenodo[\s(:,]{0,3}(?:(?:records?|deposits?|entry|entries)\s+)?(?:(?:no\.|number|ID)\s*)?#?"
                         r"(\d{5,9})\b((?:\s*(?:,|;|&|\band\b)\s*(?:and\s+)?#?\d{5,9}\b)*)", line, re.IGNORECASE):
        for number in [m.group(1)] + re.findall(r"\d{5,9}", m.group(2)):
            out.append(_hit("zenodo", f"10.5281/zenodo.{number}", m.start(), f"https://zenodo.org/records/{number}"))
    for m in re.finditer(r"10\.6084/m9\.figshare\.(\d+)(?:\.v\d+)?", line, re.IGNORECASE):
        out.append(_hit("figshare", m.group(0).rstrip("."), m.start(), f"https://doi.org/{m.group(0).rstrip('.')}"))
    for m in re.finditer(r"figshare\.com/articles/(?:[^\s/)\]]+/)*?(\d{5,})(?:/\d+)?", line, re.IGNORECASE):
        out.append(_hit("figshare", f"figshare:{m.group(1)}", m.start(), "https://" + m.group(0)))
    for m in re.finditer(r"10\.5061/dryad\.[0-9a-z]+", line, re.IGNORECASE):
        out.append(_hit("dryad", m.group(0).lower(), m.start(), f"https://doi.org/{m.group(0).lower()}"))
    for m in re.finditer(r"10\.17605/OSF\.IO/([A-Z0-9]{5})\b", line, re.IGNORECASE):
        out.append(_hit("osf", f"10.17605/OSF.IO/{m.group(1).upper()}", m.start(), f"https://osf.io/{m.group(1).lower()}"))
    for m in re.finditer(r"\bosf\.io/([a-z0-9]{5})\b(?!/?(?:preprints|registries|institutions))", line):
        out.append(_hit("osf", f"10.17605/OSF.IO/{m.group(1).upper()}", m.start(), f"https://osf.io/{m.group(1)}"))
    for m in re.finditer(r"\bswh:1:(?:cnt|dir|rev|rel|snp):[0-9a-f]{40}", line):
        out.append(_hit("swh", m.group(0), m.start(), f"https://archive.softwareheritage.org/{m.group(0)}"))
    return out


def _generic_dois(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"\b10\.\d{4,9}/[^\s\"<>)\]}]+", line):
        doi = m.group(0).rstrip(".,;:")
        out.append(_hit("doi", doi, m.start(), f"https://doi.org/{doi}"))
    return out


def _version_in_path(rest: str) -> Optional[str]:
    patterns = (r"^/releases/tag/([^/?#]+)", r"^/releases/download/([^/?#]+)", r"^/(?:tree|blob)/([^/?#]+)",
                r"^/commit/([0-9a-f]{7,40})", r"^/archive/refs/tags/([^/?#]+?)(?:\.zip|\.tar\.gz)",
                r"^/archive/([^/?#]+?)(?:\.zip|\.tar\.gz)", r"^/-/(?:tags|releases|tree|blob)/([^/?#]+)",
                r"^/-/commit/([0-9a-f]{7,40})")
    for pat in patterns:
        m = re.match(pat, rest)
        if m and m.group(1).lower() not in BRANCHES:
            return m.group(1)
    return None


def _near_version(line: str, col: int) -> Optional[str]:
    """A version or commit cited next to the link at `col`: in the text after it up to the next link, or, for the
    first link of its clause, in the text before it ("version 1.2 at https://..."). Another link's version never
    counts."""
    start = max(line.rfind(". ", 0, col), line.rfind("; ", 0, col)) + 1
    ends = [e for e in (line.find(". ", col), line.find("; ", col)) if e != -1]
    end = min(ends) if ends else len(line)
    urls = [m for m in re.finditer(r"(?:https?://|www\.|github\.com/|gitlab\.com/)[^\s<>\"'`)\]}|]+", line)
            if start <= m.start() < end]
    own = next((m for m in urls if m.start() <= col < m.end() or m.start() == col), None)
    after_from = own.end() if own else col
    nxt = next((m.start() for m in urls if m.start() > after_from), end)
    segments = [line[after_from:nxt]]
    if own is None or own is urls[0]:
        segments.append(line[start:col])
    for segment in segments:
        m = VERSION_NEAR.search(segment) or COMMIT_NEAR.search(segment)
        if m:
            return next(g for g in m.groups() if g)
    return None


def _code(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
                         r"([A-Za-z0-9._-]{1,100})((?:/[^\s<>\"'`)\]},;|]*)?)", line):
        owner, repo = m.group(1), re.sub(r"\.git$", "", m.group(2).rstrip("."))
        if owner.lower() in NOT_GITHUB_OWNERS or not repo:
            continue
        rest = m.group(3).rstrip(".")
        version = _version_in_path(rest) or _near_version(line, m.start())
        out.append(_hit("github", f"{owner}/{repo}", m.start(), f"https://github.com/{owner}/{repo}{rest}", version))
    for m in re.finditer(r"(?:https?://)?gitlab\.com/([^\s<>\"'`)\]},;|]+)", line):
        path = m.group(1).rstrip(".")
        project, _, rest = path.partition("/-/")
        project = re.sub(r"\.git$", "", project.strip("/"))
        if project.count("/") < 1:
            continue
        version = _version_in_path("/-/" + rest if rest else "") or _near_version(line, m.start())
        out.append(_hit("gitlab", project, m.start(), f"https://gitlab.com/{path}", version))
    for m in re.finditer(r"(?:https?://)?(?:bitbucket\.org|codeberg\.org|sourceforge\.net/projects)/"
                         r"[^\s<>\"'`)\]},;|]+", line):
        value = re.sub(r"^https?://", "", m.group(0)).rstrip("./")
        out.append(_hit("code-other", value, m.start(), "https://" + value, _near_version(line, m.start())))
    # Anonymised mirrors for double-blind review hide the real repository on purpose.
    for m in re.finditer(r"(?:https?://)?anonymous\.4open\.science/r/([A-Za-z0-9][\w.-]*)[^\s<>\"'`)\]},;|]*", line):
        url = "https://" + re.sub(r"^https?://", "", m.group(0)).rstrip("./")
        out.append(_hit("anon-review", m.group(1).rstrip("."), m.start(), url, _near_version(line, m.start())))
    return out


def _pip_names(args: str) -> list[tuple[str, Optional[str]]]:
    args = re.split(r"\s(?:&&|\|\||;|\||#)\s|`", args)[0]
    takes_value = {"-r", "-e", "-c", "-i", "-f", "--index-url", "--extra-index-url", "--find-links", "--requirement",
                   "--editable", "--constraint", "--target", "-t", "--python"}
    out, skip_next = [], False
    for token in args.split():
        token = token.strip("\"'")
        if skip_next:
            skip_next = False
            continue
        if token in takes_value:
            skip_next = True
            continue
        if token.startswith("-") or "/" in token or token.startswith(".") or "://" in token:
            continue
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?(?:(==|>=|~=|<=|>|<|!=)\s*([0-9][^,;\s]*))?$", token)
        if m and m.group(1).lower() not in STOPWORDS:
            out.append((m.group(1), m.group(3) if m.group(2) == "==" else None))
    return out


def _packages(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"pypi\.(?:org|python\.org)/(?:project|pypi)/([A-Za-z0-9][A-Za-z0-9._-]*?)(?:/([0-9][^/\s)\]]*))?/?"
                         r"(?=[\s)\]}>\"'`,;]|\.(?:\s|$)|$)", line):
        out.append(_hit("pypi", m.group(1), m.start(), f"https://pypi.org/project/{m.group(1)}/", m.group(2)))
    for m in re.finditer(r"\b(?:pip3?|python3?\s+-m\s+pip|uv\s+pip|pipx)\s+install\s+([^\n`]+)|\buv\s+add\s+([^\n`]+)",
                         line):
        for name, version in _pip_names(m.group(1) or m.group(2)):
            out.append(_hit("pypi", name, m.start(), f"https://pypi.org/project/{name}/", version))
    for m in re.finditer(r"\b(?:PyPI|Python Package Index)\s*(?:package|as|name|:)\s*[`'\"]?([A-Za-z0-9][A-Za-z0-9._-]*)",
                         line):
        if m.group(1).lower() not in STOPWORDS:
            out.append(_hit("pypi", m.group(1).rstrip("."), m.start(), f"https://pypi.org/project/{m.group(1).rstrip('.')}/"))
    rname = r"([A-Za-z][A-Za-z0-9.]*[A-Za-z0-9])"
    for m in re.finditer(rf"cran\.r-project\.org/(?:package=|web/packages/){rname}", line, re.IGNORECASE):
        out.append(_hit("cran", m.group(1), m.start(), f"https://CRAN.R-project.org/package={m.group(1)}"))
    for m in re.finditer(r"\binstall\.packages\(\s*(?:c\()?([^)]*)\)", line):
        for name in re.findall(r"[\"']([A-Za-z][A-Za-z0-9.]*[A-Za-z0-9])[\"']", m.group(1)):
            out.append(_hit("cran", name, m.start(), f"https://CRAN.R-project.org/package={name}"))
    for m in re.finditer(rf"\bCRAN\s+package\s+[`'\"]?{rname}", line):
        if m.group(1).lower() not in STOPWORDS:
            out.append(_hit("cran", m.group(1), m.start(), f"https://CRAN.R-project.org/package={m.group(1)}"))
    for m in re.finditer(r"bioconductor\.org/packages/(?:(?:release|devel|\d+\.\d+)/(?:bioc|data/annotation|"
                         rf"data/experiment|workflows)/html/)?{rname}(?:\.html)?", line, re.IGNORECASE):
        name = re.sub(r"\.html$", "", m.group(1))
        if name.lower() not in {"release", "devel", "html"}:
            out.append(_hit("bioconductor", name, m.start(), f"https://bioconductor.org/packages/{name}/"))
    for m in re.finditer(r"\b(?:BiocManager::install|biocLite)\(\s*(?:c\()?([^)]*)\)", line):
        for name in re.findall(r"[\"']([A-Za-z][A-Za-z0-9.]*[A-Za-z0-9])[\"']", m.group(1)):
            out.append(_hit("bioconductor", name, m.start(), f"https://bioconductor.org/packages/{name}/"))
    for m in re.finditer(rf"\bBioconductor\s+package\s+[`'\"]?{rname}", line):
        if m.group(1).lower() not in STOPWORDS:
            out.append(_hit("bioconductor", m.group(1), m.start(), f"https://bioconductor.org/packages/{m.group(1)}/"))
    for m in re.finditer(r"anaconda\.org/(bioconda|conda-forge)/([A-Za-z0-9][A-Za-z0-9._-]*)", line):
        out.append(_hit(m.group(1), m.group(2).rstrip("."), m.start(), "https://" + m.group(0).rstrip(".")))
    for m in re.finditer(r"bioconda\.github\.io/recipes/([A-Za-z0-9][A-Za-z0-9._-]*)", line):
        out.append(_hit("bioconda", m.group(1), m.start(), f"https://anaconda.org/bioconda/{m.group(1)}"))
    for m in re.finditer(r"\b(?:conda|mamba|micromamba)\s+(?:install|create)\b([^\n`]*)", line):
        args = re.split(r"\s(?:&&|\|\||;|\||#)\s", m.group(1))[0].split()
        channels = {args[i + 1] for i, a in enumerate(args[:-1]) if a in ("-c", "--channel")}
        skip_next = False
        for i, token in enumerate(args):
            if skip_next:
                skip_next = False
                continue
            if token in ("-c", "--channel", "-n", "--name", "-p", "--prefix", "--file"):
                skip_next = True
                continue
            if token.startswith("-"):
                continue
            channel, _, spec = token.rpartition("::")
            nm = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*?)(?:==?([0-9][^\s=]*))?$", spec.strip("\"'"))
            if not nm or nm.group(1).lower() in STOPWORDS:
                continue
            kind = (channel if channel in ("bioconda", "conda-forge") else "bioconda" if "bioconda" in channels
                    else "conda-forge" if "conda-forge" in channels else "conda")
            out.append(_hit(kind, nm.group(1), m.start(), f"https://anaconda.org/{kind}/{nm.group(1)}"
                            if kind != "conda" else "", nm.group(2)))
    return out


def _image(ref: str, col: int) -> Optional[Hit]:
    ref = ref.strip("\"'`.,;")
    ref = ref.split("@", 1)[0]
    parts = ref.split("/")
    host = parts[0] if len(parts) > 1 and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost") else ""
    path = "/".join(parts[1:]) if host else ref
    name, _, tag = path.rpartition(":") if ":" in path.split("/")[-1] else (path, "", "")
    if not name or not re.fullmatch(r"[a-z0-9][a-z0-9._/-]*", name):
        return None
    if host in ("", "docker.io", "registry-1.docker.io", "index.docker.io"):
        name = name if "/" in name else f"library/{name}"
        return _hit("docker", name, col, f"https://hub.docker.com/r/{name}", tag or None)
    if host == "quay.io":
        return _hit("quay", name, col, f"https://quay.io/repository/{name}", tag or None)
    if host == "ghcr.io":
        return _hit("ghcr", name, col, f"https://ghcr.io/{name}", tag or None)
    return _hit("container-other", f"{host}/{name}", col, "", tag or None)


def _containers(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"\bdocker\s+pull\s+(?:--?[\w-]+\s+)*([^\s`]+)", line):
        hit = _image(m.group(1), m.start())
        if hit:
            out.append(hit)
    for m in re.finditer(r"\b(?:singularity|apptainer)\s+(?:pull|build|exec|run)\s+(?:[^\s`]+\s+)?docker://([^\s`]+)", line):
        hit = _image(m.group(1), m.start())
        if hit:
            out.append(hit)
    for m in re.finditer(r"hub\.docker\.com/(?:r/([\w.-]+/[\w.-]+)|_/([\w.-]+))", line):
        name = m.group(1) or f"library/{m.group(2)}"
        out.append(_hit("docker", name.lower().rstrip("."), m.start(), "https://" + m.group(0)))
    for m in re.finditer(r"(?<![\w/])((?:quay|ghcr)\.io/[\w.-]+/[\w./-]+(?::[\w.-]+)?)", line):
        hit = _image(m.group(1), m.start())
        if hit:
            out.append(hit)
    return out


HF_NAME = r"[A-Za-z0-9][\w.-]{0,95}"
HF_WORD = r"(?:Hugging\s?Face(?:\s+Hub)?|\bHF\s+Hub)"


def _huggingface(line: str) -> list[Hit]:
    out = []
    for m in re.finditer(r"(?:https?://)?(?:huggingface\.co|hf\.co)/(datasets/|spaces/)?([A-Za-z0-9][\w.-]{0,95})/"
                         r"([A-Za-z0-9][\w.-]{0,95})(?:/(?:tree|blob|resolve)/([^/\s)\]]+))?|hf://(datasets|spaces)/"
                         r"([A-Za-z0-9][\w.-]{0,95})/([A-Za-z0-9][\w.-]{0,95})", line):
        prefix = m.group(1) or (m.group(5) + "/" if m.group(5) else "")
        owner, name = (m.group(2), m.group(3)) if m.group(2) else (m.group(6), m.group(7))
        name = name.rstrip(".")
        if not prefix and owner.lower() in NOT_HF_OWNERS:
            continue
        kind = "hf-dataset" if prefix == "datasets/" else "hf-space" if prefix == "spaces/" else "hf-model"
        rev = m.group(4) if m.group(4) and m.group(4).lower() not in BRANCHES else None
        out.append(_hit(kind, f"{owner}/{name}", m.start(), f"https://huggingface.co/{prefix}{owner}/{name}", rev))
    # Repositories named in prose, without a link. "the ORG organization on Hugging Face (a, b, c)" names
    # repositories of unstated type (hf-repo: the lookup tries datasets, models and Spaces).
    for m in re.finditer(rf"\b({HF_NAME})\s+organi[sz]ation\s+on\s+(?:the\s+)?{HF_WORD}\s*\(([^)]*)\)"
                         rf"|{HF_WORD}\s+organi[sz]ation\s+[`'\"]?({HF_NAME})[`'\"]?\s*\(([^)]*)\)", line, re.IGNORECASE):
        owner, names = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        for name in re.split(r"\s*(?:,|;|&|\band\b)\s*", names):
            name = name.strip(" `'\"….")
            if re.fullmatch(HF_NAME, name):
                out.append(_hit("hf-repo", f"{owner}/{name}", m.start(), f"https://huggingface.co/{owner}/{name}"))
    # "Hugging Face dataset org/name", "Hugging Face models org/a and org/b"
    for m in re.finditer(rf"{HF_WORD}\s+(datasets?|models?|spaces?|repositor(?:y|ies)|repos?)\s*[:(]?\s*"
                         rf"((?:[`'\"]?{HF_NAME}/{HF_NAME}[`'\"]?(?:\s*(?:,|;|&|\band\b)\s*)?)+)", line, re.IGNORECASE):
        word = m.group(1).lower()
        kind = ("hf-dataset" if word.startswith("dataset") else "hf-model" if word.startswith("model")
                else "hf-space" if word.startswith("space") else "hf-repo")
        prefix = {"hf-dataset": "datasets/", "hf-space": "spaces/"}.get(kind, "")
        for rm in re.finditer(rf"({HF_NAME})/({HF_NAME})", m.group(2)):
            owner, name = rm.group(1), rm.group(2).rstrip(".")
            out.append(_hit(kind, f"{owner}/{name}", m.start(), f"https://huggingface.co/{prefix}{owner}/{name}"))
    return out


def _rrid(line: str) -> list[Hit]:
    out = [_hit("rrid", f"RRID:{m.group(1)}", m.start(), f"https://scicrunch.org/resolver/RRID:{m.group(1)}")
           for m in re.finditer(r"\bRRID:\s?([A-Za-z]+_[A-Za-z0-9][A-Za-z0-9_:-]*[A-Za-z0-9])", line)]
    for m in re.finditer(r"\bRRID\s+([A-Z][A-Za-z]*_[A-Za-z0-9][A-Za-z0-9_:-]*[A-Za-z0-9])", line):
        out.append(_hit("rrid", m.group(0), m.start(), ok=False, problem="the colon after RRID is missing",
                        suggested=f"RRID:{m.group(1)}"))
    return out


EXTRACTORS: list[Callable[[str], list[Hit]]] = [_geo, _insdc, _arrayexpress, _dbgap, _ega, _pdb, _catalogs, _archives,
                                                _code, _packages, _containers, _huggingface, _rrid]


def _excerpt(line: str, col: int, width: int = 90) -> str:
    start = max(0, col - width // 3)
    text = line[start: start + width].strip()
    return ("…" if start else "") + text + ("…" if start + width < len(line) else "")


CODE_WORDS = re.compile(r"\b(?:code|software|source|releases?|versions?|implementation|packages?|tools?|scripts?|"
                        r"pipelines?|repositor(?:y|ies)|notebooks?)\b", re.IGNORECASE)
DATA_WORDS = re.compile(r"\b(?:data(?:sets?)?|genomes?|exomes?|genotypes?|phenotypes?|samples?|reads|sequences|"
                        r"VCFs?|BAMs?|FASTQs?|alignments?|assembl(?:y|ies)|spectra|matrices|images|recordings|"
                        r"measurements|outputs|cohorts?|participants)\b", re.IGNORECASE)


def _near_text(lines: list[str], i: int, col: int, before: int = 100, after: int = 60) -> str:
    """The words around column `col` of line `i`, within its sentence (continued from the previous line)."""
    prev = lines[i - 1].strip() if i > 0 else ""
    text = (prev + " " if prev else "") + lines[i]
    pos = col + (len(prev) + 1 if prev else 0)
    start = max(text.rfind(". ", 0, pos) + 2, pos - before, 0)
    ends = [e for e in (text.find(". ", pos), pos + after) if e != -1]
    return text[start:min(ends)]


# ------------------------------------------------------------------------------------------- quoting
# Findings quote the manuscript's own sentence (or table row) so the authors need not open the file and count
# lines; the line number is only a parenthetical aid (author-priorities.md, "Writing for the authors").

QUOTE_WIDTH = 160
BLOCK_START = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s|\\item\b|\\(?:begin|end)\{)")
LATEX_ARG = re.compile(r"\\(?:textbf|textit|emph|texttt|textsc|underline)\{([^{}]*)\}")


def _breaks(line: str, table: bool) -> bool:
    """A line that cannot continue the paragraph above it."""
    return not line.strip() or table or bool(_heading(line)) or bool(re.match(r"^\s*\\(?:begin|end)\{", line))


def _sentence_at(lines: list[str], i: int, col: int, tables: list[bool]) -> tuple[str, int]:
    """The sentence containing column `col` of line `i` (read across the line breaks of its paragraph or list
    item; a table row on its own), and the column's offset in it."""
    if tables[i] or _heading(lines[i]):
        line = lines[i]
        return line.strip(), max(0, col - (len(line) - len(line.lstrip())))
    start = i
    while start > 0 and not BLOCK_START.match(lines[start]) and not _breaks(lines[start - 1], tables[start - 1]):
        start -= 1
    end = i
    while end + 1 < len(lines) and not _breaks(lines[end + 1], tables[end + 1]) and not BLOCK_START.match(lines[end + 1]):
        end += 1
    text, pos = "", 0
    for k in range(start, end + 1):
        stripped = lines[k].strip()
        if k == i:
            pos = len(text) + max(0, col - (len(lines[k]) - len(lines[k].lstrip())))
        text += stripped + " "
    text = text.rstrip()
    bounds = [0] + [m.end() for m in SENTENCE.finditer(text)]
    s = max(b for b in bounds if b <= pos)
    e = next((b for b in bounds if b > pos), len(text))
    return text[s:e].strip(), pos - s


def _trim(sentence: str, pos: int, length: int, width: int = QUOTE_WIDTH) -> str:
    """The sentence, shortened with [...] to about `width` characters around [pos, pos + length)."""
    if len(sentence) <= width + 20:
        return sentence
    left = max(0, pos - max(30, (width - length) // 2))
    right = min(len(sentence), max(left + width, pos + length + 10))
    if left > 0:
        space = sentence.find(" ", left)
        left = space + 1 if 0 <= space < pos else left
    if right < len(sentence):
        space = sentence.rfind(" ", pos + length, right)
        right = space if space != -1 else right
    return ("[...] " if left else "") + sentence[left:right].strip() + (" [...]" if right < len(sentence) else "")


def _plain(text: str) -> str:
    """Markup that only gets in the way of reading a quote: Markdown bold, LaTeX \\url, \\href and font commands."""
    text = re.sub(r"\\href\{([^{}]*)\}\{([^{}]*)\}", r"\2 (\1)", text)
    text = re.sub(r"\\url\{([^{}]*)\}", r"\1", text)
    for _ in range(3):
        text = LATEX_ARG.sub(r"\1", text)
    text = re.sub(r"\\item\s*", "", text).replace("\\%", "%").replace("\\_", "_").replace("\\&", "&")
    text = re.sub(r"(?<!\\)~", " ", text).replace("\\\\", " ")
    return re.sub(r"\s{2,}", " ", text.replace("**", "")).strip()


def _quote(lines: list[str], i: int, col: int, span: str, tables: list[bool]) -> tuple[str, str]:
    """(quote, span): the sentence around `span` at column `col` of line `i`, trimmed, with markup removed."""
    sentence, pos = _sentence_at(lines, i, col, tables)
    return _plain(_trim(sentence, pos, len(span))), _plain(span)


def _span_at(line: str, col: int, value: str) -> tuple[int, str]:
    """Where the identifier is written on the line, and how: the value itself, the link or token it sits in,
    or (for a number named after its archive, "Zenodo records 18370498 and 19487816") its last part."""
    if line.startswith(value, col):
        return col, value
    token = re.match(r"[^\s]+", line[col:])
    word = re.sub(r"[.,;:)\]}>\"'`*]+$", "", token.group(0)) if token else value
    tail = re.split(r"[/.:]", value)[-1]
    if len(tail) >= 4 and tail.lower() not in word.lower():
        at = line.find(tail, col)
        if 0 <= at - col < 160:
            return at, tail
    return col, word or value


ANONYMISED = "anonymised for review: never looked up, because the link hides the real repository on purpose"
OFFLINE = "not looked up in this offline run"
MALFORMED = "not looked up, because the identifier is malformed"
EXCLUDED_BEFORE = re.compile(r"\b(?:exclud(?:e|es|ed|ing)|except(?:ing)?|other than|apart from|omitt(?:ed|ing)|"
                             r"but not)\b[^.;:()]{0,30}$", re.IGNORECASE)


def extract(lines: list[str], skip: list[bool], sections: list[str], statements: list[Statement],
            tables: Optional[list[bool]] = None) -> list[Identifier]:
    """Every identifier outside the reference list, merged by (kind, value, version)."""
    tables = tables if tables is not None else table_mask(lines)
    in_statement = {n for s in statements for n in range(s.start, s.end + 1)}
    found: dict[tuple[str, str, Optional[str]], Identifier] = {}
    for i, line in enumerate(lines):
        if skip[i]:
            continue
        hits = [h for ex in EXTRACTORS for h in ex(line)]
        if i + 1 in in_statement:
            claimed = {h[1].lower() for h in hits} | {h[1].lower().removeprefix("10.5281/") for h in hits}
            hits += [h for h in _generic_dois(line) if h[1].lower() not in claimed
                     and not re.match(r"10\.(5281|6084|5061|17605)/", h[1], re.IGNORECASE)]
            # Any other link in a statement (a web service, a registry, an FTP folder) is checked for existence.
            for m in URL.finditer(line):
                if not any(m.start() <= h[7] < m.end() for h in hits):
                    address = re.sub(r"^https?://", "", m.group(0)).rstrip(".,;:/*")
                    hits.append(_hit("web", address, m.start(), "https://" + address))
        for kind, value, url, version, ok, problem, suggested, col in hits:
            key = (kind, value, version)
            excluded = bool(EXCLUDED_BEFORE.search(line[max(0, col - 60):col]))
            near = _near_text(lines, i, col) if FAMILY[kind][1] == "archive" else ""
            archives_code = not tables[i] and (bool(CODE_WORDS.search(near)) or not DATA_WORDS.search(near))
            if key in found:
                found[key].archives_code |= archives_code
                if i + 1 not in found[key].lines:
                    found[key].lines.append(i + 1)
                found[key].in_statement |= i + 1 in in_statement
                found[key].in_table &= tables[i]
                found[key].excluded &= excluded
                continue
            family, role = FAMILY[kind]
            at, written = _span_at(line, col, value)
            quote, span = _quote(lines, i, at, written, tables)
            found[key] = Identifier(kind=kind, family=family, role=role, value=value, url=url, line=i + 1,
                                    lines=[i + 1], excerpt=_excerpt(line, col), section=sections[i],
                                    quote=quote, span=span,
                                    in_statement=i + 1 in in_statement, in_table=tables[i], excluded=excluded,
                                    archives_code=archives_code,
                                    version=version, well_formed=ok, problem=problem, suggested=suggested,
                                    detail=MALFORMED if not ok else ANONYMISED if kind == "anon-review" else OFFLINE)
    return sorted(found.values(), key=lambda x: (x.line, x.kind, x.value))


CODE_HOST = re.compile(r"(?:https?://)?(?:www\.)?(github\.com|gitlab\.com)/([A-Za-z0-9][\w.-]*)", re.IGNORECASE)


def mark_own(identifiers: list[Identifier], statements: list[Statement]) -> None:
    """The authors' own identifiers get the licence, release and version checks; the rest (a tool in a
    comparison table, software the paper only cites) are checked for existence only. Own: named in an
    availability statement, an anonymised review link, or code under an owner a statement names (an
    organisation link counts), and a package or image named like an own repository. When no statement
    names any code, code outside tables counts as own."""
    owners = {(m.group(1).lower(), m.group(2).lower()) for s in statements for u in s.links
              for m in [CODE_HOST.match(u)] if m}
    owners |= {(("github.com" if x.kind == "github" else "gitlab.com"), x.value.split("/")[0].lower())
               for x in identifiers if x.in_statement and x.kind in ("github", "gitlab")}
    statement_code = bool(owners) or any(x.in_statement and x.role == "code" for x in identifiers)
    for x in identifiers:
        host = "github.com" if x.kind == "github" else "gitlab.com" if x.kind == "gitlab" else ""
        x.own = (x.in_statement or x.kind == "anon-review"
                 or (bool(host) and (host, x.value.split("/")[0].lower()) in owners)
                 or (not statement_code and x.role in ("code", "package", "container") and not x.in_table))
    repo_names = {x.value.split("/")[-1].lower() for x in identifiers if x.own and x.role == "code"}
    for x in identifiers:
        if x.role in ("package", "container") and x.value.split("/")[-1].lower() in repo_names:
            x.own = True


GENERIC_REPO_NAMES = {"tool", "tools", "code", "data", "scripts", "analysis", "analyses", "pipeline", "paper",
                      "manuscript", "software", "package", "app", "web", "docs", "src", "main", "model", "models"}


def find_version_mentions(lines: list[str], skip: list[bool], sections: list[str], identifiers: list[Identifier],
                          tables: Optional[list[bool]] = None) -> None:
    """Versions of the authors' own repositories cited by name rather than in a link ("Just-DNA-Lite 0.3.25" in
    a benchmark table), attached to the repository so that --online can ask whether the tag exists."""
    tables = tables if tables is not None else table_mask(lines)
    repos: dict[str, Identifier] = {}
    for x in identifiers:
        if x.own and x.kind in ("github", "gitlab") and x.well_formed:
            key = x.value.lower()
            if key not in repos or (repos[key].version and not x.version):
                repos[key] = x
    for key, x in repos.items():
        name = x.value.split("/")[-1]
        if len(name) < 4 or name.lower() in GENERIC_REPO_NAMES:
            continue
        words = [w for w in re.split(r"[-_. ]+", name) if w]
        pattern = re.compile(rf"(?<![\w/.-]){'[-_ ]?'.join(re.escape(w) for w in words)}(?![\w-])\s*[,(]?\s*"
                             r"(?:version\s+|release\s+)?v?(\d+(?:\.\d+)+(?:[-+][0-9A-Za-z.]+)?)\b", re.IGNORECASE)
        known = {y.version for y in identifiers if y.value.lower() == key and y.version}
        for i, line in enumerate(lines):
            if skip[i]:
                continue
            for m in pattern.finditer(line):
                version = m.group(1)
                if version in known or version.lstrip("v") in {k.lstrip("v") for k in known}:
                    continue
                known.add(version)
                quote, span = _quote(lines, i, m.start(), m.group(0).rstrip(" ,("), tables)
                x.mentions.append(Mention(version=version, line=i + 1, section=sections[i], quote=quote, span=span))


# ------------------------------------------------------------------------------------------- statements

REQUEST = re.compile(
    r"\b(?:up)?on\s+(?:a\s+)?(?:reasonable|justified|written|formal|motivated|academic)?\s*request\b"
    r"|\bby\s+request\b|\b(?:available|provided|shared|obtainable|supplied)\s+on\s+demand\b"
    r"|\b(?:available|obtainable|obtained|provided|shared|requested)\s+(?:directly\s+)?from\s+the\s+"
    r"(?:corresponding\s+|first\s+|senior\s+|lead\s+|last\s+)?authors?\b"
    r"|\bcontact(?:ing)?\s+the\s+(?:corresponding\s+)?authors?\b", re.IGNORECASE)
RESTRICTION = re.compile(
    r"consent|privacy|confidential|ethic|third[- ]part|data access committee|\bDACs?\b|GDPR|HIPAA|"
    r"data (?:use|transfer|sharing|access) agreement|\bDUA\b|licen[cs]|proprietary|controlled[- ]access|re-?identif|"
    r"legal|commercial|institutional review board|\bIRB\b|governance|restrict", re.IGNORECASE)
IN_ARTICLE = re.compile(r"\b(?:within|in)\s+the\s+(?:article|paper|manuscript|main text)\b|supplementary|"
                        r"supporting information|additional file|\btable s\d|source data", re.IGNORECASE)
NOT_APPLICABLE = re.compile(r"\bnot applicable\b|\bno (?:new )?(?:data|code|datasets?|software) (?:were|was) "
                            r"(?:generated|created|produced|collected|used)|^\W*n/?a\W*$", re.IGNORECASE)
ACCESS_ROUTE = re.compile(r"apply|application|authori[sz]ed access|data access committee|\bDACs?\b|request access|"
                          r"access (?:is|was) (?:granted|managed|controlled)|controlled[- ]access|\bdbGaP\b|\bEGA\b|"
                          r"reviewer|token", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\\])")
# Where an offer of material on request is an availability claim: inside an availability statement, or in a
# Methods-like section in a sentence that names what is shared. Appendices, tables and other prose are not.
METHODS_TITLE = re.compile(r"\b(?:methods?|materials?|implementation|experimental|procedures?|data|datasets?|software|"
                           r"code|resources?|samples?|participants|patients|study (?:design|population)|"
                           r"statistical analys[ie]s|availability)\b", re.IGNORECASE)
SHARES_MATERIAL = re.compile(r"\b(?:data(?:sets?)?|code|scripts?|software|materials?|samples?|reagents?|plasmids?|"
                             r"strains?|cell lines?|protocols?|genotypes?|sequences?|images?|models?|files?|records?|"
                             r"resources?|results)\b", re.IGNORECASE)


def analyse_statements(statements: list[Statement], lines: list[str], identifiers: list[Identifier]) -> None:
    for s in statements:
        text = "\n".join(lines[s.start - 1: s.end])
        body = "\n".join(lines[s.start: s.end]) if _heading(lines[s.start - 1]) else text
        s.names = sorted({x.value for x in identifiers if any(s.start <= n <= s.end for n in x.lines)})
        s.links = list(dict.fromkeys(u.rstrip(".,;:") for u in URL.findall(text)))
        s.in_article = bool(IN_ARTICLE.search(body))
        s.request_route = bool(REQUEST.search(body))
        s.not_applicable = bool(NOT_APPLICABLE.search(body.strip()))


def request_sentences(lines: list[str], skip: list[bool], sections: Optional[list[str]] = None,
                      statements: Optional[list[Statement]] = None,
                      tables: Optional[list[bool]] = None) -> list[tuple[int, str, str]]:
    """Sentences offering material on request, read across line breaks within a paragraph, each with the line
    of the request phrase and the phrase itself. Only availability claims count: a sentence inside an
    availability statement, or one in a Methods-like section that names what is shared. Table rows are never
    read."""
    sections = sections if sections is not None else [""] * len(lines)
    tables = tables if tables is not None else table_mask(lines)
    in_statement = {n for s in statements or [] for n in range(s.start, s.end + 1)}
    out: list[tuple[int, str, str]] = []
    paragraph: list[int] = []
    for i in range(len(lines) + 1):
        if i < len(lines) and not skip[i] and not tables[i] and lines[i].strip() and not _heading(lines[i]):
            paragraph.append(i)
            continue
        if paragraph:
            text, starts = "", []
            for j in paragraph:
                starts.append((len(text), j))
                text += lines[j].strip() + " "
            pos = 0
            for sentence in SENTENCE.split(text):
                at = text.index(sentence, pos)
                pos = at + len(sentence)
                m = REQUEST.search(sentence)
                if not m:
                    continue
                j = max(j for offset, j in starts if offset <= at + m.start())
                if j + 1 in in_statement or (SHARES_MATERIAL.search(sentence)
                                              and (not sections[j] or METHODS_TITLE.search(sections[j]))):
                    out.append((j + 1, _plain(_trim(sentence.strip(), m.start(), len(m.group(0)))),
                                _plain(m.group(0))))
            paragraph = []
    return out


# ------------------------------------------------------------------------------------------- venue

def _load_venues_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_reporting_check_venues", VENUES_PY)
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"cannot load {VENUES_PY}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_reporting_check_venues"] = module
    spec.loader.exec_module(module)
    if VENUES_YAML_OVERRIDE is not None:
        module.VENUES_YAML = VENUES_YAML_OVERRIDE
    return module


AVAIL_RULE = re.compile(r"availab|archiv|\bDOI\b|repositor|licen[cs]|\bOSI\b|open[- ]source|source code|\bcode\b|"
                        r"\bdata\b|software|deposit|request|test data|reproduc|checklist|STROBE|STREGA|CONSORT|"
                        r"PRISMA|ARRIVE|STARD|TRIPOD|MDAR|reporting summary|EQUATOR", re.IGNORECASE)
SOFT_RULE = re.compile(r"recommended|encouraged|not required|optional|where applicable|if required", re.IGNORECASE)


def venue_rules(key: str) -> VenueRules:
    """The availability rules venues.yaml records for one venue, read through venues.py's own loader."""
    venues_module = _load_venues_module()
    checked, venues = venues_module.load_venues()
    if key not in venues:
        raise typer.BadParameter(f"unknown venue {key!r}; list them with venues.py rank")
    v: dict[str, Any] = venues[key]
    rules: list[str] = []
    for field in ("software", "required_sections", "other_desk_rules"):
        for item in v.get(field) or []:
            if field == "software" or AVAIL_RULE.search(str(item)):
                rules.append(str(item))
    open_science = v.get("open_science")
    if isinstance(open_science, dict):
        for field, value in open_science.items():
            if field not in ("source", "checked") and isinstance(value, str) and AVAIL_RULE.search(value):
                rules.append(f"{field}: {value}")
    hard = [r for r in rules if not SOFT_RULE.search(r)]
    years = next((int(m.group(1)) for r in rules if re.search(r"availab", r, re.IGNORECASE)
                  for m in [re.search(r"(\d+)\s*years?", r)] if m), None)
    return VenueRules(
        key=key, name=str(v.get("name", key)), publisher=str(v.get("publisher") or ""), url=str(v.get("url", "")),
        checked=str(v.get("checked") or checked),
        rules=rules,
        wants_archive=any(re.search(r"archiv|\bDOI\b|Zenodo|Software Heritage|figshare", r, re.IGNORECASE) for r in hard),
        wants_licence=any(re.search(r"licen[cs]|\bOSI\b|Open Source Definition|open[- ]source", r, re.IGNORECASE)
                          for r in hard),
        request_refused=any(re.search(r"(?:upon|on) request[^.]{0,40}not accept|not accept\w*[^.]{0,40}(?:upon|on) request",
                                      r, re.IGNORECASE) for r in rules),
        availability_years=years,
        in_abstract=any(re.search(r"in the abstract", r, re.IGNORECASE) for r in rules),
        reporting_checklist=any(re.search(r"reporting checklist|reporting summary|STROBE|STREGA|CONSORT|PRISMA|"
                                          r"ARRIVE|STARD|TRIPOD|MDAR|EQUATOR", r, re.IGNORECASE) for r in rules),
    )


def venue_from_record(record: Path) -> Optional[str]:
    data = yaml.safe_load(record.read_text(encoding="utf-8")) or {}
    venue = data.get("venue") or {}
    return venue.get("key") if isinstance(venue, dict) else None


# ------------------------------------------------------------------------------------------- online

class Http:
    """One polite client: per-host spacing, backoff on 429 and 5xx, never a verdict from a refused request."""

    def __init__(self, github_token: Optional[str] = None) -> None:
        self.client = httpx.Client(timeout=20, headers={"User-Agent": USER_AGENT}, follow_redirects=False)
        self.last: dict[str, float] = {}
        self.github_token = github_token
        self.github_blocked = ""

    def close(self) -> None:
        self.client.close()

    def get(self, url: str, params: Optional[dict[str, str]] = None,
            headers: Optional[dict[str, str]] = None) -> httpx.Response | str:
        """The response, or the reason no usable answer came."""
        host = httpx.URL(url).host
        reason = "the server gave no answer"
        for attempt in range(3):
            wait = MIN_INTERVAL.get(host, 0.2) - (time.monotonic() - self.last.get(host, 0.0))
            if wait > 0:
                time.sleep(wait)
            self.last[host] = time.monotonic()
            try:
                r = self.client.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:  # timeouts and refused connections are expected on the open web
                reason = f"the server could not be reached ({type(exc).__name__})"
                time.sleep(2 ** attempt)
                continue
            if r.headers.get("x-ratelimit-remaining") == "0":
                return r
            if r.status_code == 429 or r.status_code >= 500:
                retry = r.headers.get("retry-after", "")
                time.sleep(min(float(retry), 30.0) if retry.isdigit() else 2 ** attempt)
                reason = f"the server answered with an error (HTTP {r.status_code}) on {attempt + 1} attempts"
                continue
            return r
        return reason


def _na(ident: Identifier, reason: str) -> None:
    ident.state, ident.detail = State.not_assessed, reason


def _json(r: httpx.Response) -> Any:
    """The parsed body, or None for an empty body or an HTML error page where JSON was expected."""
    if not r.content.strip():
        return None
    try:
        return r.json()
    except ValueError:
        return None


def _resolve_geo(http: Http, ident: Identifier) -> None:
    if ident.value.startswith("GDS"):
        r = http.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                     {"db": "gds", "term": f"{ident.value}[ACCN]", "retmode": "json", "tool": "manuscript-reporting-check"})
        if isinstance(r, str) or r.status_code != 200:
            return _na(ident, r if isinstance(r, str) else f"HTTP {r.status_code}")
        count = int(((_json(r) or {}).get("esearchresult") or {}).get("count", "0"))
        ident.state, ident.detail = (State.resolves, "in GEO DataSets") if count else (State.not_found, "no GEO record")
        return
    r = http.get("https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi",
                 {"acc": ident.value, "targ": "self", "form": "text", "view": "brief"})
    if isinstance(r, str):
        return _na(ident, r)
    text = r.text
    if r.status_code == 200 and re.search(r"^\^(?:SERIES|SAMPLE|PLATFORM)\s*=", text, re.MULTILINE):
        title = re.search(r"^!\w+_title\s*=\s*(.*)$", text, re.MULTILINE)
        status = re.search(r"^!\w+_status\s*=\s*(.*)$", text, re.MULTILINE)
        ident.state, ident.title = State.resolves, title.group(1).strip() if title else ""
        ident.detail = status.group(1).strip() if status else "public"
    elif "is currently private" in text:
        date = re.search(r"released on ([A-Za-z]{3,9} \d{1,2}, \d{4})", text)
        ident.state = State.restricted
        ident.detail = (f"private until {date.group(1) if date else 'an unstated date'}: reviewers need the secure "
                        "token, and the record must be released at publication")
    elif "Could not find a public or private accession" in text:
        ident.state, ident.detail = State.not_found, "GEO has no public or private record with this accession"
    else:
        _na(ident, f"unexpected GEO answer (HTTP {r.status_code})")


def _ncbi_count(http: Http, db: str, term: str) -> int | str:
    r = http.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                 {"db": db, "term": term, "retmode": "json", "tool": "manuscript-reporting-check"})
    if isinstance(r, str):
        return r
    if r.status_code != 200:
        return f"HTTP {r.status_code}"
    return int(((_json(r) or {}).get("esearchresult") or {}).get("count", "0"))


def _resolve_insdc(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://www.ebi.ac.uk/ena/browser/api/summary/{ident.value}")
    if isinstance(r, str):
        return _na(ident, r)
    summaries = (_json(r) or {}).get("summaries") or [] if r.status_code == 200 else []
    if summaries:
        s = summaries[0]
        status = str(s.get("statusDescription") or "public").lower()
        ident.title = str(s.get("title") or "")
        if status == "public":
            ident.state, ident.detail = State.resolves, "public at ENA"
        elif status == "private":
            ident.state, ident.detail = State.restricted, "registered but not yet public (held until publication)"
        else:
            ident.state, ident.detail = State.not_found, f"withdrawn at the archive (status: {status})"
            ident.flags.append("withdrawn")
        return
    if r.status_code not in (200, 404):
        return _na(ident, f"ENA answered HTTP {r.status_code}")
    db = "bioproject" if ident.value.startswith("PRJ") else "biosample" if ident.value.startswith("SAM") else "sra"
    count = _ncbi_count(http, db, ident.value)
    if isinstance(count, str):
        return _na(ident, f"not at ENA; NCBI lookup failed ({count})")
    ident.state, ident.detail = ((State.resolves, f"found in NCBI {db} (not yet mirrored at ENA)") if count
                                 else (State.not_found, "neither ENA nor NCBI has this accession"))


def _resolve_biostudies(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://www.ebi.ac.uk/biostudies/api/v1/studies/{ident.value}")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 200:
        attrs = {a.get("name"): a.get("value") for a in (_json(r) or {}).get("attributes", []) if isinstance(a, dict)}
        ident.state, ident.title, ident.detail = State.resolves, str(attrs.get("Title") or ""), "public at BioStudies"
    elif r.status_code == 404:
        ident.state, ident.detail = State.not_found, "BioStudies has no study with this accession"
    elif r.status_code in (401, 403):
        _na(ident, "BioStudies refused the request: the study may be private until publication")
    else:
        _na(ident, f"BioStudies answered HTTP {r.status_code}")


def _resolve_dbgap(http: Http, ident: Identifier) -> None:
    base = ident.value.split(".")[0]
    count = _ncbi_count(http, "gap", base)
    if isinstance(count, str):
        return _na(ident, count)
    if not count:
        ident.state, ident.detail = State.not_found, "dbGaP has no study with this accession"
        return
    ident.state = State.restricted
    ident.detail = "dbGaP study exists; individual-level data are controlled access (dbGaP authorized access)"
    r = http.get("https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi", {"study_id": base})
    current = re.search(r"study_id=(phs\d{6}\.v\d+\.p\d+)", r.headers.get("location", "")) if not isinstance(r, str) else None
    if current and "." in ident.value and current.group(1) != ident.value:
        ident.detail += f"; the current version is {current.group(1)} (cite the version analysed)"


def _resolve_ega(http: Http, ident: Identifier) -> None:
    endpoint = {"S": "studies", "D": "datasets", "C": "dacs"}.get(ident.value[3])
    if not endpoint:
        return _na(ident, "only EGA studies (EGAS), datasets (EGAD) and committees (EGAC) are looked up")
    r = http.get(f"https://metadata.ega-archive.org/{endpoint}/{ident.value}")
    if isinstance(r, str):
        return _na(ident, r)
    data = _json(r) if r.status_code == 200 else None
    if isinstance(data, dict) and data.get("accession_id"):
        ident.title = str(data.get("title") or "")
        ident.state = State.restricted
        ident.detail = ("controlled access through the EGA and its data access committee"
                        + ("" if data.get("is_released", True) else "; not yet released"))
    elif r.status_code in (200, 404):
        ident.state, ident.detail = State.not_found, "the EGA has no record with this accession"
    else:
        _na(ident, f"EGA answered HTTP {r.status_code}")


def _resolve_pdb(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://data.rcsb.org/rest/v1/holdings/status/{ident.value}")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 404:
        ident.state, ident.detail = State.not_found, "the PDB has no entry with this ID"
        return
    if r.status_code != 200:
        return _na(ident, f"RCSB answered HTTP {r.status_code}")
    status = str(((_json(r) or {}).get("rcsb_repository_holdings_combined") or {}).get("status", "")).upper()
    if status == "CURRENT":
        ident.state, ident.detail = State.resolves, "released"
    elif status == "UNRELEASED":
        ident.state, ident.detail = State.restricted, "deposited but on hold until publication"
    elif status == "OBSOLETE":
        ident.state, ident.detail = State.not_found, "obsolete (withdrawn or superseded)"
        ident.flags.append("withdrawn")
    else:
        _na(ident, f"unexpected holdings status {status or 'none'}")


def _resolve_gwas(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://www.ebi.ac.uk/gwas/rest/api/v2/studies/{ident.value}")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 404:
        ident.state, ident.detail = State.not_found, "the GWAS Catalog has no study with this accession"
    elif r.status_code == 200:
        data = _json(r) or {}
        ident.state, ident.title, ident.detail = State.resolves, str(data.get("disease_trait") or ""), "in the GWAS Catalog"
        if data.get("full_summary_stats_available") is False:
            ident.flags.append("no-summary-statistics")
    else:
        _na(ident, f"GWAS Catalog answered HTTP {r.status_code}")


def _resolve_pgs(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://www.pgscatalog.org/rest/score/{ident.value}")
    if isinstance(r, str):
        return _na(ident, r)
    data = _json(r) if r.status_code == 200 else None
    if isinstance(data, dict) and data.get("id"):
        ident.state, ident.title, ident.detail = State.resolves, str(data.get("name") or ""), "in the PGS Catalog"
    elif r.status_code in (200, 404):
        ident.state, ident.detail = State.not_found, "the PGS Catalog has no score with this ID"
    else:
        _na(ident, f"PGS Catalog answered HTTP {r.status_code}")


def _resolve_doi(http: Http, ident: Identifier) -> None:
    if ident.value.startswith("figshare:"):
        r = http.get(f"https://api.figshare.com/v2/articles/{ident.value.split(':', 1)[1]}")
        if isinstance(r, str):
            return _na(ident, r)
        if r.status_code == 200:
            data = _json(r) or {}
            ident.state, ident.title = State.resolves, str(data.get("title") or "")
            ident.licence, ident.detail = str((data.get("license") or {}).get("name") or ""), "public on figshare"
        elif r.status_code == 404:
            ident.state, ident.detail = State.not_found, "figshare has no public item with this ID"
        else:
            _na(ident, f"figshare answered HTTP {r.status_code}")
        return
    doi = ident.value
    r = http.get(f"https://api.datacite.org/dois/{quote(doi, safe='/')}")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 200:
        attrs = ((_json(r) or {}).get("data") or {}).get("attributes") or {}
        ident.state, ident.detail = State.resolves, "registered with DataCite"
        ident.title = str(((attrs.get("titles") or [{}])[0]).get("title") or "")
        rights = [x.get("rights", "") for x in attrs.get("rightsList") or []
                  if x.get("rights") and "access" not in x.get("rights", "").lower()]
        ident.licence = rights[0] if rights else ""
        relations = {x.get("relationType") for x in attrs.get("relatedIdentifiers") or []}
        if ident.kind == "zenodo" and "HasVersion" in relations and "IsVersionOf" not in relations:
            ident.flags.append("concept-doi")
        return
    if r.status_code != 404:
        return _na(ident, f"DataCite answered HTTP {r.status_code}")
    h = http.get(f"https://doi.org/api/handles/{quote(doi, safe='/')}")
    if isinstance(h, str):
        return _na(ident, f"not in DataCite; doi.org lookup failed ({h})")
    code = (_json(h) or {}).get("responseCode") if h.status_code in (200, 404) else None
    if code == 1:
        ident.state, ident.detail = State.resolves, "registered at doi.org (not a DataCite DOI)"
    elif code == 100:
        ident.state, ident.detail = State.not_found, "doi.org has no such DOI"
    else:
        _na(ident, f"doi.org answered HTTP {h.status_code}")


def _resolve_swh(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://archive.softwareheritage.org/api/1/resolve/{ident.value}/")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 200:
        ident.state, ident.detail = State.resolves, "archived at Software Heritage"
    elif r.status_code == 404:
        ident.state, ident.detail = State.not_found, "Software Heritage has no object with this identifier"
    else:
        _na(ident, f"Software Heritage answered HTTP {r.status_code}")


def _github_limited(http: Http, r: httpx.Response) -> bool:
    if r.status_code in (403, 429) and (r.headers.get("x-ratelimit-remaining") == "0" or r.status_code == 429):
        reset = r.headers.get("x-ratelimit-reset", "")
        when = time.strftime("%H:%M UTC", time.gmtime(int(reset))) if reset.isdigit() else "later"
        http.github_blocked = f"GitHub rate limit reached (resets at {when}); rerun later or with --github-auth"
        return True
    return False


def _resolve_github(http: Http, ident: Identifier) -> None:
    if http.github_blocked:
        return _na(ident, http.github_blocked)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if http.github_token:
        headers["Authorization"] = f"Bearer {http.github_token}"
    api = f"https://api.github.com/repos/{ident.value}"

    def get(url: str) -> httpx.Response | str:
        r = http.get(url, headers=headers)
        if isinstance(r, httpx.Response) and _github_limited(http, r):
            return http.github_blocked
        return r

    r = get(api)
    if isinstance(r, httpx.Response) and r.status_code in (301, 307) and r.headers.get("location"):
        r = get(r.headers["location"])
        if isinstance(r, httpx.Response) and r.status_code == 200:
            ident.flags.append("renamed")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 404:
        ident.state, ident.detail = State.not_found, "GitHub has no public repository here (missing, renamed or private)"
        return
    if r.status_code != 200:
        return _na(ident, f"GitHub answered HTTP {r.status_code}")
    data = _json(r)
    if not isinstance(data, dict) or not data.get("full_name"):
        return _na(ident, "GitHub answered without repository data")
    full = data["full_name"]
    api = f"https://api.github.com/repos/{full}"
    ident.state, ident.title = State.resolves, str(data.get("description") or "")
    ident.detail = "public repository" + (f" (now {full})" if full.lower() != ident.value.lower() else "")
    if data.get("archived"):
        ident.detail += "; archived (read-only)"
    lic = data.get("license")
    if not lic:
        ident.flags.append("no-licence")
    elif lic.get("spdx_id") in (None, "NOASSERTION"):
        ident.licence = "unrecognised licence file"
        ident.flags.append("licence-unrecognised")
    else:
        ident.licence = str(lic.get("spdx_id"))
    if ident.own:  # a third-party repository is checked for existence only
        _check_code_version(ident, get, f"{api}/commits/{{}}", f"{api}/git/ref/tags/{{}}",
                            f"{api}/releases?per_page=1", f"{api}/tags?per_page=1")


def _ref_exists(get: Callable[[str], httpx.Response | str], commit_url: str, tag_url: str,
                version: str) -> Optional[bool]:
    """Whether the repository has this commit or tag (also tried with and without a leading v); None when the
    host gave no usable answer."""
    if re.fullmatch(r"[0-9a-f]{7,40}", version):
        r = get(commit_url.format(version))
        return None if isinstance(r, str) else r.status_code == 200
    candidates = [version] + ([f"v{version}"] if not version.startswith("v") else [version[1:]])
    for tag in candidates:
        r = get(tag_url.format(quote(tag, safe="")))
        if isinstance(r, str):
            return None
        if r.status_code == 200:
            return True
    return False


def _check_code_version(ident: Identifier, get: Callable[[str], httpx.Response | str], commit_url: str,
                        tag_url: str, releases_url: str, tags_url: str) -> None:
    for mention in ident.mentions:
        mention.exists = _ref_exists(get, commit_url, tag_url, mention.version)
        if mention.exists is None and "version-not-assessed" not in ident.flags:
            ident.flags.append("version-not-assessed")
    if ident.version:
        found = _ref_exists(get, commit_url, tag_url, ident.version)
        if found is None:
            ident.flags.append("version-not-assessed")
        elif not found:
            ident.flags.append("version-missing")
        return
    r = get(releases_url)
    if isinstance(r, httpx.Response) and r.status_code == 200 and _json(r):
        ident.flags.append("has-release")
        return
    t = get(tags_url)
    if isinstance(t, httpx.Response) and t.status_code == 200:
        ident.flags.append("has-tag" if _json(t) else "no-release")
    else:
        ident.flags.append("version-not-assessed")


def _resolve_gitlab(http: Http, ident: Identifier) -> None:
    api = f"https://gitlab.com/api/v4/projects/{quote(ident.value, safe='')}"

    def get(url: str) -> httpx.Response | str:
        return http.get(url)

    r = get(f"{api}?license=true")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 404:
        ident.state, ident.detail = State.not_found, "GitLab has no public project here (missing, renamed or private)"
        return
    if r.status_code != 200:
        return _na(ident, f"GitLab answered HTTP {r.status_code}")
    data = _json(r) or {}
    ident.state, ident.title, ident.detail = State.resolves, str(data.get("description") or ""), "public project"
    lic = data.get("license")
    if not lic:
        ident.flags.append("no-licence")
    elif str(lic.get("key")) == "other":
        ident.licence = "unrecognised licence file"
        ident.flags.append("licence-unrecognised")
    else:
        ident.licence = str(lic.get("name") or lic.get("key"))
    if ident.own:
        _check_code_version(ident, get, f"{api}/repository/commits/{{}}", f"{api}/repository/tags/{{}}",
                            f"{api}/releases?per_page=1", f"{api}/repository/tags?per_page=1")


def _resolve_pypi(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://pypi.org/pypi/{ident.value}/json")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 404:
        ident.state, ident.detail = State.not_found, "PyPI has no package with this name"
        return
    if r.status_code != 200:
        return _na(ident, f"PyPI answered HTTP {r.status_code}")
    info = (_json(r) or {}).get("info") if isinstance(_json(r), dict) else None
    if not info:
        return _na(ident, "PyPI answered without package data")
    ident.state, ident.title = State.resolves, str(info.get("summary") or "")
    ident.detail = f"latest {info.get('version')}"
    classifiers = [c.split("::")[-1].strip() for c in info.get("classifiers") or [] if c.startswith("License ::")]
    lic = info.get("license_expression") or (info.get("license") if len(str(info.get("license") or "")) < 60 else "")
    ident.licence = str(lic or (classifiers[0] if classifiers else ""))
    if ident.version:
        v = http.get(f"https://pypi.org/pypi/{ident.value}/{ident.version}/json")
        if isinstance(v, httpx.Response) and v.status_code == 404:
            ident.flags.append("version-missing")


def _resolve_cran(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://crandb.r-pkg.org/{ident.value}/all")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 404:
        ident.state, ident.detail = State.not_found, "CRAN has never had a package with this name"
        return
    if r.status_code != 200:
        return _na(ident, f"crandb answered HTTP {r.status_code}")
    data = _json(r)
    if not isinstance(data, dict) or "versions" not in data:
        return _na(ident, "crandb answered without package data")
    versions = data.get("versions") or {}
    latest = str(data.get("latest") or "")
    ident.state, ident.title = State.resolves, str(data.get("title") or "")
    ident.licence = str((versions.get(latest) or {}).get("License") or "")
    ident.detail = f"latest {latest}"
    if data.get("archived"):
        ident.detail += "; archived (removed from CRAN, so install.packages() no longer finds it)"
        ident.flags.append("withdrawn")
    if ident.version and ident.version not in versions:
        ident.flags.append("version-missing")


def _resolve_bioconductor(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://bioconductor.org/packages/{ident.value}/")
    if isinstance(r, str):
        return _na(ident, r)
    where = r.headers.get("location", "")
    if r.status_code in (301, 302, 303, 307, 308) and "removed-packages" in where:
        ident.state = State.not_found
        ident.detail = "not in the current Bioconductor release (removed, renamed or never accepted)"
    elif (r.status_code in (301, 302, 303, 307, 308) and f"/{ident.value}.html" in where) or r.status_code == 200:
        ident.state, ident.detail = State.resolves, "in the current Bioconductor release"
    else:
        _na(ident, f"Bioconductor answered HTTP {r.status_code}")


def _resolve_anaconda(http: Http, ident: Identifier) -> None:
    if ident.kind == "conda":
        return _na(ident, "the conda channel is not stated, so the package cannot be looked up")
    r = http.get(f"https://api.anaconda.org/package/{ident.kind}/{ident.value}")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 404:
        ident.state, ident.detail = State.not_found, f"{ident.family} has no package with this name"
        return
    if r.status_code != 200:
        return _na(ident, f"anaconda.org answered HTTP {r.status_code}")
    data = _json(r)
    if not isinstance(data, dict) or "name" not in data and "versions" not in data:
        return _na(ident, "anaconda.org answered without package data")
    ident.state, ident.title = State.resolves, str(data.get("summary") or "")
    ident.licence, ident.detail = str(data.get("license") or ""), f"latest {data.get('latest_version')}"
    if ident.version and ident.version not in (data.get("versions") or []):
        ident.flags.append("version-missing")


def _resolve_container(http: Http, ident: Identifier) -> None:
    if ident.kind == "docker":
        r = http.get(f"https://hub.docker.com/v2/repositories/{ident.value}/")
        if isinstance(r, str):
            return _na(ident, r)
        if r.status_code == 404:
            ident.state, ident.detail = State.not_found, "Docker Hub has no public repository with this name"
            return
        if r.status_code != 200:
            return _na(ident, f"Docker Hub answered HTTP {r.status_code}")
        ident.state, ident.detail = State.resolves, "public on Docker Hub"
        if ident.version:
            t = http.get(f"https://hub.docker.com/v2/repositories/{ident.value}/tags/{ident.version}")
            if isinstance(t, httpx.Response) and t.status_code == 404:
                ident.flags.append("version-missing")
        return
    if ident.kind == "quay":
        r = http.get(f"https://quay.io/api/v1/repository/{ident.value}")
        if isinstance(r, str):
            return _na(ident, r)
        if r.status_code in (401, 403):
            return _na(ident, "Quay gives the same answer for a private and a missing repository")
        if r.status_code == 404:
            ident.state, ident.detail = State.not_found, "Quay has no repository with this name"
            return
        if r.status_code != 200:
            return _na(ident, f"Quay answered HTTP {r.status_code}")
        ident.state, ident.detail = State.resolves, "public on Quay"
        if ident.version:
            t = http.get(f"https://quay.io/api/v1/repository/{ident.value}/tag/",
                         {"specificTag": ident.version, "onlyActiveTags": "true"})
            if isinstance(t, httpx.Response) and t.status_code == 200 and not (_json(t) or {}).get("tags"):
                ident.flags.append("version-missing")
        return
    _na(ident, "this registry needs a token exchange that is not implemented; open the image page to check")


def _resolve_huggingface(http: Http, ident: Identifier) -> None:
    kind = {"hf-dataset": "datasets", "hf-model": "models", "hf-space": "spaces"}[ident.kind]
    r = http.get(f"https://huggingface.co/api/{kind}/{ident.value}")
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code == 401:
        return _na(ident, "Hugging Face gives the same answer for a private and a missing repository")
    if r.status_code == 404:
        ident.state, ident.detail = State.not_found, "Hugging Face has no repository here"
        return
    if r.status_code != 200:
        return _na(ident, f"Hugging Face answered HTTP {r.status_code}")
    data = _json(r) or {}
    ident.licence = str((data.get("cardData") or {}).get("license") or "")
    if data.get("gated"):
        ident.state, ident.detail = State.restricted, f"gated ({data['gated']}): users must accept terms or be approved"
    else:
        ident.state, ident.detail = State.resolves, "public"
    if ident.version:
        v = http.get(f"https://huggingface.co/api/{kind}/{ident.value}/revision/{quote(ident.version, safe='')}")
        if isinstance(v, httpx.Response) and v.status_code == 404:
            ident.flags.append("version-missing")


def _resolve_hf_repo(http: Http, ident: Identifier) -> None:
    """A repository named without its type: try datasets, then models, then Spaces."""
    refused = ""
    for kind in ("hf-dataset", "hf-model", "hf-space"):
        probe = ident.model_copy(update={"kind": kind, "flags": []})
        _resolve_huggingface(http, probe)
        if probe.state in (State.resolves, State.restricted):
            label = FAMILY[kind][0]
            ident.state, ident.detail, ident.licence = probe.state, f"{probe.detail} ({label})", probe.licence
            ident.flags += probe.flags
            return
        if probe.state == State.not_assessed:
            refused = refused or probe.detail
    if refused:
        _na(ident, f"no public dataset, model or Space found; {refused}")
    else:
        ident.state, ident.detail = State.not_found, "Hugging Face has no dataset, model or Space here"


def _resolve_web(http: Http, ident: Identifier) -> None:
    """Any other link in an availability statement: does the address answer?"""
    r = http.get(ident.url)
    if isinstance(r, str):
        return _na(ident, r)
    if r.status_code in (404, 410):
        ident.state, ident.detail = State.not_found, f"the server says the page does not exist (HTTP {r.status_code})"
    elif 200 <= r.status_code < 300:
        ident.state, ident.detail = State.resolves, "the page answers"
    elif 300 <= r.status_code < 400:
        where = r.headers.get("location", "")
        ident.state, ident.detail = State.resolves, "the address redirects" + (f" to {where}" if where else "")
    elif r.status_code in (401, 403, 405, 429):
        _na(ident, f"the server refused an automated request (HTTP {r.status_code}); open the link in a browser")
    else:
        _na(ident, f"the server answered HTTP {r.status_code}")


def _resolve_anonymised(http: Http, ident: Identifier) -> None:
    _na(ident, ANONYMISED)


def _resolve_rrid(http: Http, ident: Identifier) -> None:
    r = http.get(f"https://scicrunch.org/resolver/{ident.value}.json")
    if isinstance(r, str):
        return _na(ident, r)
    data = _json(r) if r.status_code in (200, 404) else None
    hits = ((data or {}).get("hits") or {}) if isinstance(data, dict) else {}
    if hits.get("total"):
        item = ((hits.get("hits") or [{}])[0].get("_source") or {}).get("item") or {}
        ident.state, ident.title, ident.detail = State.resolves, str(item.get("name") or ""), "registered RRID"
    elif r.status_code in (200, 404) and isinstance(data, dict):
        ident.state, ident.detail = State.not_found, "the RRID resolver has no such identifier"
    else:
        _na(ident, f"SciCrunch answered HTTP {r.status_code}")


RESOLVERS: dict[str, Callable[[Http, Identifier], None]] = {
    "geo": _resolve_geo, "insdc": _resolve_insdc, "arrayexpress": _resolve_biostudies,
    "biostudies": _resolve_biostudies, "dbgap": _resolve_dbgap, "ega": _resolve_ega, "pdb": _resolve_pdb,
    "gwas-catalog": _resolve_gwas, "pgs-catalog": _resolve_pgs, "zenodo": _resolve_doi, "figshare": _resolve_doi,
    "dryad": _resolve_doi, "osf": _resolve_doi, "doi": _resolve_doi, "swh": _resolve_swh,
    "github": _resolve_github, "gitlab": _resolve_gitlab, "pypi": _resolve_pypi, "cran": _resolve_cran,
    "bioconductor": _resolve_bioconductor, "bioconda": _resolve_anaconda, "conda-forge": _resolve_anaconda,
    "conda": _resolve_anaconda, "docker": _resolve_container, "quay": _resolve_container, "ghcr": _resolve_container,
    "container-other": _resolve_container, "hf-dataset": _resolve_huggingface, "hf-model": _resolve_huggingface,
    "hf-space": _resolve_huggingface, "hf-repo": _resolve_hf_repo, "anon-review": _resolve_anonymised,
    "rrid": _resolve_rrid, "web": _resolve_web,
}


def resolve_all(identifiers: list[Identifier], github_token: Optional[str] = None) -> None:
    http = Http(github_token)
    try:
        for ident in identifiers:
            if not ident.well_formed:
                continue
            if ident.kind == "code-other":
                _na(ident, "no lookup is implemented for this code host; open the link to check")
                continue
            RESOLVERS[ident.kind](http, ident)
    finally:
        http.close()


# ------------------------------------------------------------------------------------------- findings

def _rule_ref(venue: Optional[VenueRules], pattern: str) -> str:
    if not venue:
        return ""
    rule = next((r for r in venue.rules if re.search(pattern, r, re.IGNORECASE)), "")
    return f"{venue.name}: \"{rule}\" (venues.yaml, checked {venue.checked}; verify at {venue.url})" if rule else ""


NAMED_ARCHIVES: list[tuple[str, str, set[str], tuple[str, ...]]] = [  # pattern, label, kinds, link hosts
    (r"\bZenodo\b", "Zenodo", {"zenodo"}, ("zenodo.org",)),
    (r"\bfigshare\b", "figshare", {"figshare"}, ("figshare.com",)),
    (r"\bDryad\b", "Dryad", {"dryad"}, ("datadryad.org",)),
    (r"\bOSF\b|Open Science Framework", "OSF", {"osf"}, ("osf.io",)),
    (r"Software Heritage", "Software Heritage", {"swh"}, ("softwareheritage.org",)),
    (r"Hugging\s?Face", "Hugging Face", {"hf-dataset", "hf-model", "hf-space", "hf-repo"}, ("huggingface.co", "hf.co")),
    (r"\bGitHub\b", "GitHub", {"github"}, ("github.com",)),
    (r"\bGitLab\b", "GitLab", {"gitlab"}, ("gitlab.com",)),
    (r"\bGEO\b|Gene Expression Omnibus", "GEO", {"geo"}, ("ncbi.nlm.nih.gov/geo",)),
    (r"\b(?:SRA|ENA)\b|Sequence Read Archive|European Nucleotide Archive", "SRA/ENA", {"insdc"},
     ("ncbi.nlm.nih.gov/sra", "ebi.ac.uk/ena")),
    (r"ArrayExpress", "ArrayExpress", {"arrayexpress"}, ("ebi.ac.uk/biostudies",)),
    (r"\bPyPI\b", "PyPI", {"pypi"}, ("pypi.org",)),
    (r"\bCRAN\b", "CRAN", {"cran"}, ("r-project.org",)),
    (r"Bioconductor", "Bioconductor", {"bioconductor"}, ("bioconductor.org",)),
    (r"Bioconda", "Bioconda", {"bioconda"}, ("anaconda.org/bioconda", "bioconda.github.io")),
]


def _unidentified_archives(statements: list[Statement], lines: list[str],
                           identifiers: list[Identifier]) -> list[Finding]:
    """A statement that names an archive or code host in prose but gives nothing the script can look up there."""
    out: list[Finding] = []
    for s in statements:
        kinds = {x.kind for x in identifiers if any(s.start <= n <= s.end for n in x.lines)}
        for pattern, label, archive_kinds, hosts in NAMED_ARCHIVES:
            where = next((n for n in range(s.start, s.end + 1) if re.search(pattern, lines[n - 1])), None)
            if where is None or kinds & archive_kinds or any(h in u.lower() for u in s.links for h in hosts):
                continue
            out.append(Finding(check="archive-unidentified", severity=Severity.uncertain, line=where,
                               excerpt=_excerpt(lines[where - 1], re.search(pattern, lines[where - 1]).start()),
                               message=f"The '{s.label}' statement names {label} but gives no accession, DOI or link "
                                       "there that the script could read, so nothing was checked (not assessed).",
                               suggestion="Find the record and check it by hand, or ask the authors for its identifier: "
                                          "readers find a deposit by its accession or DOI, not by the archive's name."))
    return out


def _anonymised_finding(links: list[Identifier], venue: Optional[VenueRules]) -> Finding:
    rule = _rule_ref(venue, r"archiv|DOI|Zenodo|Software Heritage") if venue and venue.wants_archive else ""
    return Finding(
        check="anonymised-code", severity=Severity.major if rule else Severity.optional,
        line=links[0].line, excerpt=links[0].excerpt,
        message=f"The code is reachable only through anonymised review links ({', '.join(x.value for x in links)}), "
                "with no version and no archived copy. That suits double-blind review, but the mirror is temporary "
                "and hides the real repository, so it was not looked up (not assessed).",
        suggestion="By acceptance, replace each link with the public repository, the release tag the results came "
                   "from and an archived DOI (Zenodo or Software Heritage)."
                   + (" The venue's recorded rule asks for an archived copy: check on its live page whether that "
                      "applies at submission or at acceptance." if rule else ""),
        rule=rule)


def _context_only(x: Identifier) -> bool:
    """Cited as context rather than as the study's own material: a third-party tool, package or image the
    authors do not own, anything that appears only in a table, or an identifier the text excludes."""
    return not x.own and (x.in_table or x.excluded or x.role in ("code", "package", "container", "model"))


def findings_for(lines: list[str], skip: list[bool], statements: list[Statement], identifiers: list[Identifier],
                 abstract: Optional[tuple[int, int]], venue: Optional[VenueRules], online: bool,
                 sections: Optional[list[str]] = None, tables: Optional[list[bool]] = None) -> list[Finding]:
    out: list[Finding] = []
    if not statements:
        out.append(Finding(check="no-statement", severity=Severity.major,
                           message="No data or code availability statement was found.",
                           suggestion="Add one that names each dataset and the code with its location (accession, "
                                      "DOI or URL), or says why a dataset cannot be shared and how to apply for it."))
    for s in statements:
        excerpt = lines[s.start - 1].strip()[:90]
        if s.not_applicable or s.names or s.links or s.request_route:
            if s.in_article and not s.names and not s.links:
                out.append(Finding(check="in-article-only", severity=Severity.optional, line=s.start, excerpt=excerpt,
                                   message="The statement points only to the article or its supplement.",
                                   suggestion="Check that the underlying data, not only summaries, are in the "
                                              "supplement; otherwise deposit them and give the accession."))
            continue
        if s.in_article:
            out.append(Finding(check="in-article-only", severity=Severity.optional, line=s.start, excerpt=excerpt,
                               message="The statement points only to the article or its supplement.",
                               suggestion="Check that the underlying data, not only summaries, are in the supplement; "
                                          "otherwise deposit them and give the accession."))
            continue
        out.append(Finding(check="empty-statement", severity=Severity.major, line=s.start, excerpt=excerpt,
                           message=f"The '{s.label}' statement names no accession, DOI, link or location.",
                           suggestion="Name where each dataset or the code is (accession, DOI or URL), or state "
                                      "why it cannot be shared and how to apply for access."))
    out += _unidentified_archives(statements, lines, identifiers)
    for line_no, sentence, phrase in request_sentences(lines, skip, sections, statements, tables):
        rule = _rule_ref(venue, r"request") if venue and venue.request_refused else ""
        where = {"line": line_no, "excerpt": sentence[:120], "quote": sentence, "span": phrase,
                 "section": sections[line_no - 1] if sections else ""}
        if RESTRICTION.search(sentence) and not rule:
            out.append(Finding(check="request-route", severity=Severity.optional, **where,
                               message="Access is by request, with a stated restriction.",
                               suggestion="Check that it names who decides on access (a data access committee or "
                                          "named office, not one author), the criteria, and what remains public."))
        else:
            out.append(Finding(check="request-only", severity=Severity.major, **where,
                               message="Material is offered only on request from the authors, with no stated reason.",
                               suggestion="Deposit it and give the accession or DOI; if it cannot be public, say why "
                                          "and route requests through a controlled-access archive or committee.",
                               rule=rule))
    for x in identifiers:
        if not x.well_formed:
            fixable = bool(x.suggested)
            out.append(Finding(check="malformed-identifier", severity=Severity.optional if fixable else Severity.major,
                               line=x.line, excerpt=x.excerpt,
                               message=f"{x.family} identifier '{x.value}' is malformed: {x.problem}.",
                               suggestion=(f"Write it as {x.suggested}." if fixable else
                                           "Copy the accession from the archive's confirmation; readers cannot "
                                           "find a malformed one.")))
    own_code = [x for x in identifiers if x.role == "code" and x.kind != "hf-space" and x.own]
    anonymised = [x for x in own_code if x.kind == "anon-review"]
    code = [x for x in own_code if x.kind != "anon-review"]
    archived = any(x.role == "archive" and x.archives_code and x.well_formed and x.state != State.not_found
                   for x in identifiers)
    if anonymised and not archived:
        out.append(_anonymised_finding(anonymised, venue))
    versioned_packages = any(x.role in ("package", "container") and x.version for x in identifiers if x.in_statement)
    if code and not archived and venue and venue.wants_archive:
        first = code[0]
        out.append(Finding(check="no-archive", severity=Severity.major, line=first.line, excerpt=first.excerpt,
                           message="The code is linked but no archived copy (Zenodo, Software Heritage, figshare or "
                                   "another DOI-minting archive) is cited.",
                           suggestion="Archive the version the results came from and cite its DOI where the venue "
                                      "asks for it.", rule=_rule_ref(venue, r"archiv|DOI|Zenodo|Software Heritage")))
    elif code and not archived and not versioned_packages:
        for x in code:
            if x.version:
                continue
            extra = (" The repository has no release or tag at all." if "no-release" in x.flags else
                     f" The repository has releases or tags, but the paper does not say which one was used."
                     if {"has-release", "has-tag"} & set(x.flags) else "")
            out.append(Finding(check="code-unversioned", severity=Severity.optional, line=x.line, excerpt=x.excerpt,
                               message=f"{x.family} link {x.value} cites no release, tag or commit and no archived "
                                       f"copy, so the code behind the results can change after publication.{extra}",
                               suggestion="Tag a release for the version used, archive it (Zenodo or Software "
                                          "Heritage) and cite the tag and the DOI."))
    if venue and venue.in_abstract and own_code:
        if abstract is None:
            out.append(Finding(check="abstract-availability", severity=Severity.uncertain,
                               message="The venue wants the software location in the abstract, but no abstract was "
                                       "found to check.", rule=_rule_ref(venue, r"in the abstract")))
        else:
            inside = [x for x in identifiers if x.role in ("code", "archive", "package")
                      and any(abstract[0] < n <= abstract[1] for n in x.lines)]
            if not inside:
                out.append(Finding(check="abstract-availability", severity=Severity.major, line=abstract[0],
                                   message="The venue wants the software (or its archived version) in the abstract; "
                                           "the abstract names neither.", rule=_rule_ref(venue, r"in the abstract")))
    if online:
        for x in identifiers:
            out += _online_findings(x, venue, statements, lines)
        unassessed = [x for x in identifiers if x.well_formed and x.state == State.not_assessed]
        if unassessed:
            out.append(Finding(check="not-assessed", severity=Severity.uncertain,
                               message=f"{len(unassessed)} identifier(s) could not be checked online: "
                                       + "; ".join(f"{x.value} ({x.detail})" for x in unassessed[:8])
                                       + ("; …" if len(unassessed) > 8 else ""),
                               suggestion="Open these by hand or rerun later; they are not counted as resolving."))
    elif any(x.well_formed for x in identifiers):
        out.append(Finding(check="not-assessed", severity=Severity.uncertain,
                           message="Identifiers were not looked up (offline run); existence, licences and releases "
                                   "are not assessed.", suggestion="Rerun with --online."))
    seen: set[tuple[str, Optional[int], str]] = set()
    deduped = []
    for f in out:  # one finding per root cause and place: a sentence matched twice is reported once
        key = (f.check, f.line, f.message)
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    order = {s: i for i, s in enumerate(Severity)}
    return sorted(deduped, key=lambda f: (order[f.severity], f.line or 0))


def _online_findings(x: Identifier, venue: Optional[VenueRules], statements: list[Statement],
                     lines: list[str]) -> list[Finding]:
    out: list[Finding] = []
    context = _context_only(x)
    severity = Severity.optional if context else Severity.major
    note = (" The text excludes it, which this may explain." if x.excluded else
            " It is cited as context (a table, or software the authors do not own), so only its existence was "
            "checked." if context else "")
    if x.state == State.not_found:
        withdrawn = "withdrawn" in x.flags
        out.append(Finding(check="withdrawn" if withdrawn else "not-found", severity=severity, line=x.line,
                           excerpt=x.excerpt, message=f"{x.family}: {x.value}: {x.detail}.{note}",
                           suggestion="Check the identifier against the archive's record. If it is private until "
                                      "publication, say so and give editors and reviewers access."))
    if "withdrawn" in x.flags and x.state != State.not_found:
        out.append(Finding(check="withdrawn", severity=severity, line=x.line, excerpt=x.excerpt,
                           message=f"{x.family}: {x.value}: {x.detail}.{note}",
                           suggestion="Point to where the software or data can be obtained now, with its version."))
    if not x.own and x.role in ("code", "package", "container", "model"):
        return out  # licence, release and version checks are for the authors' own software
    if "version-missing" in x.flags:
        out.append(Finding(check="version-not-found", severity=Severity.major, line=x.line, excerpt=x.excerpt,
                           message=f"{x.family} {x.value} exists but has no version, tag or revision '{x.version}'.",
                           suggestion="Cite a version that exists (or publish the tag before submission)."))
    if "no-licence" in x.flags:
        sev = Severity.major if venue and venue.wants_licence else Severity.optional
        out.append(Finding(check="no-licence", severity=sev, line=x.line, excerpt=x.excerpt,
                           message=f"{x.family} reports no licence file for {x.value}; without one, nobody else may "
                                   "legally reuse or redistribute the code.",
                           suggestion="Add a LICENSE file with an open-source licence (for example MIT, BSD-3-Clause, "
                                      "Apache-2.0 or GPL-3.0) before submission.",
                           rule=_rule_ref(venue, r"licen|OSI|open source") if sev == Severity.major else ""))
    if "licence-unrecognised" in x.flags:
        out.append(Finding(check="licence-unrecognised", severity=Severity.uncertain, line=x.line, excerpt=x.excerpt,
                           message=f"{x.family} cannot classify the licence file of {x.value}.",
                           suggestion="Read the LICENSE file: confirm it is an open-source licence that allows reuse."))
    if "concept-doi" in x.flags:
        out.append(Finding(check="concept-doi", severity=Severity.optional, line=x.line, excerpt=x.excerpt,
                           message=f"{x.value} is a Zenodo concept DOI: it always points at the newest version, not "
                                   "necessarily the one the results came from.",
                           suggestion="Cite the version DOI of the release used (the concept DOI can stay as well)."))
    if "no-summary-statistics" in x.flags:
        out.append(Finding(check="summary-statistics", severity=Severity.optional, line=x.line, excerpt=x.excerpt,
                           message=f"The GWAS Catalog lists no full summary statistics for {x.value}.",
                           suggestion="If the paper says summary statistics are available there, deposit them or "
                                      "correct the statement."))
    if x.state == State.restricted:
        statement = next((s for s in statements if s.start <= x.line <= s.end), None)
        text = "\n".join(lines[s.start - 1: s.end]) if statement else lines[x.line - 1]
        if not ACCESS_ROUTE.search(text):
            out.append(Finding(check="access-route", severity=Severity.optional, line=x.line, excerpt=x.excerpt,
                               message=f"{x.family} {x.value}: {x.detail}. The text does not say how to obtain access.",
                               suggestion="Add one sentence on the access route (who approves requests and where to "
                                          "apply). Controlled access itself is legitimate."))
    return out


# ------------------------------------------------------------------------------------------- driver

def check(path: Path, online: bool = False, venue: Optional[str] = None,
          github_token: Optional[str] = None) -> Report:
    raw = path.read_text(encoding="utf-8")
    lines = prepare(raw, latex=path.suffix.lower() in (".tex", ".ltx"))
    sections, skip, abstract = layout(lines)
    tables = table_mask(lines)
    statements = find_statements(lines, skip)
    identifiers = extract(lines, skip, sections, statements, tables)
    analyse_statements(statements, lines, identifiers)
    mark_own(identifiers, statements)
    find_version_mentions(lines, skip, sections, identifiers, tables)
    rules = venue_rules(venue) if venue else None
    if online:
        resolve_all(identifiers, github_token)
    findings = findings_for(lines, skip, statements, identifiers, abstract, rules, online, sections, tables)
    return Report(path=str(path), online=online, venue=rules, statements=statements, identifiers=identifiers,
                  findings=findings)


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def to_markdown(report: Report) -> str:
    counts = Counter(f.severity.value for f in report.findings)
    out = [f"# Availability check: {report.path}", "",
           f"Online lookups: {'yes' if report.online else 'no (offline run)'}. Findings: "
           + ", ".join(f"{counts.get(s.value, 0)} {s.value}" for s in Severity if s != Severity.blocker) + ".", ""]
    if report.venue:
        v = report.venue
        out += [f"## Venue rules: {v.name} ({v.key})", "",
                f"From venues.yaml, checked {v.checked}. Verify against the live page before treating any as binding: "
                f"{v.url}", ""]
        out += [f"- {r}" for r in v.rules] or ["- none recorded: read the live page"]
        flags = [("archived copy asked for", v.wants_archive), ("licence asked for", v.wants_licence),
                 ("'on request' refused", v.request_refused), ("location wanted in the abstract", v.in_abstract),
                 ("reporting checklist asked for", v.reporting_checklist)]
        out += ["", "Read from those rules: " + "; ".join(f"{k}: {'yes' if b else 'no'}" for k, b in flags)
                + (f"; availability period: {v.availability_years} years" if v.availability_years else "") + ".", ""]
    for sev in Severity:
        group = [f for f in report.findings if f.severity == sev]
        if not group:
            continue
        out += [f"## {sev.value} ({len(group)})", ""]
        for f in group:
            loc = f"L{f.line}" if f.line else "-"
            out.append(f"- **{f.check}** {loc}: {f.message}" + (f" `{f.excerpt}`" if f.excerpt else "")
                       + (f"\n  → {f.suggestion}" if f.suggestion else "") + (f"\n  Rule: {f.rule}" if f.rule else ""))
        out.append("")
    if report.statements:
        out += ["## Availability statements", "", "| lines | label | covers | names | links | in article | request |",
                "|---|---|---|---|---|---|---|"]
        for s in report.statements:
            out.append(f"| {s.start}-{s.end} | {_cell(s.label)} | {', '.join(s.covers)} | {_cell(', '.join(s.names)) or '-'} "
                       f"| {len(s.links)} | {'yes' if s.in_article else 'no'} | {'yes' if s.request_route else 'no'} |")
        out.append("")
    if report.identifiers:
        out += ["## Identifiers", "", "Where: `statement` (in an availability statement), `own` (the authors' code "
                "elsewhere), `context` (a table, a third-party tool or an excluded ID: existence only), `text`.", "",
                "| line | kind | identifier | where | version | state | detail |", "|---|---|---|---|---|---|---|"]
        for x in report.identifiers:
            detail = x.detail + (f"; {x.title[:60]}" if x.title else "") + (f"; licence {x.licence}" if x.licence else "")
            where = ("statement" if x.in_statement else "own" if x.own else "context" if _context_only(x) else "text")
            out.append(f"| {x.line} | {x.family} | {_cell(x.value)} | {where} | "
                       f"{_cell(x.version or '-')} | {x.state.value if x.well_formed else 'malformed'} | {_cell(detail)} |")
    return "\n".join(out) + "\n"


@app.command()
def main(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True, help="Manuscript (.md, .tex, .txt)")],
    online: Annotated[bool, typer.Option(help="Look every identifier up in its public archive")] = False,
    venue: Annotated[Optional[str], typer.Option(help="Venue key from venues.yaml (see venues.py rank)")] = None,
    record: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False,
                                                   help="manuscript-record.yaml: read the venue from it")] = None,
    github_auth: Annotated[bool, typer.Option(help="Send $GITHUB_TOKEN or $GH_TOKEN to api.github.com (raises the "
                                                   "unauthenticated limit of 60 requests an hour)")] = False,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write the full report as JSON")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the Markdown report here (default: stdout)")] = None,
) -> None:
    if record and not venue:
        venue = venue_from_record(record)
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")) if github_auth else None
    report = check(path, online=online, venue=venue, github_token=token)
    md = to_markdown(report)
    if json_out:
        json_out.write_text(json.dumps(json.loads(report.model_dump_json()), indent=2), encoding="utf-8")
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"wrote {md_out}")
    else:
        typer.echo(md)
    raise typer.Exit(code=1 if any(f.severity in (Severity.blocker, Severity.major) for f in report.findings) else 0)


if __name__ == "__main__":
    app()
