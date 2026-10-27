# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pillow>=10", "pymupdf>=1.24,<2"]  # figures.py's: this script imports it
# ///
"""Build the referees' and the defender's workspaces for a simulated review, and fill in each seat's brief.

    uv run --script workspaces.py seats WORK --paper PAPER.md --supplement SUPPLEMENT.md --files SUPPLEMENTARY_DIR \\
        --venue WORK/venue.md --journal "iScience=Research Article" --journal "JAMIA Open=Application Note" \\
        --design "software-tool (main), database-resource" \\
        --seat software-methods --seat skeptic --seat champion \\
        --remit software-methods=@REMIT.md --module software-methods=software-and-methods \\
        --module skeptic=genomics,human-data-and-clinical
    uv run --script workspaces.py defender WORK --paper PAPER.md --supplement SUPPLEMENT.md \\
        --files SUPPLEMENTARY_DIR --findings WORK/findings.merged.json [--drop "CH-8=why it went no further"]

WORK is this skill's folder in the run (RUN/manuscript-peer-review). Both commands put in a workspace only what
SKILL.md (step 3) and adjudication.md (the defence pass) allow:

- `manuscript.md` (`.tex`, `.txt`: the paper's own suffix), the reading copy: HTML comments, and in LaTeX `%`
  comments, removed, which removes the revision marks with them; a line that held only a comment goes too;
- `supplementary.md` for the first --supplement, `supplementary-2.md` and so on for the others, as reading copies;
- `supplementary/`: the files of --files that the paper or its supplement names (by file name or path), and
  the files those name in turn; --all-files takes every file, --file adds one. Markdown, LaTeX and HTML files
  become reading copies, any other file is copied as it is. The output lists each file left out and why;
- `figures/`: each figure as a PNG and `index.md`, from manuscript-figures' `figures.py workspace` run once on
  the paper, each supplement and each supplementary text file, merged into one index (a figure found twice
  keeps its first rendering with an image).

`seats` adds, for each seat, `finding-schema.md`, `venue.md` and, with --module, `domain-questions.md`: the
named domain modules without their when-to-load sections and the section on running the authors' code, with
links shown as text, since a seat opens nothing outside its workspace. It writes the seat's brief to
WORK/briefs/SEAT.md from the template in references/seats.md ("The seat brief"), with the journals, the
design, the remit, the modules, the workspace's absolute path and the seat's prefix filled in, and a last line
naming the files in the workspace. A seat's remit is its own section of seats.md; in the default panel the main
seat (the first that is neither the skeptic nor the champion) also takes the reproducibility remit and the
skeptic claims and novelty, unless that remit has a seat of its own. --also SEAT=SECTION adds another
section; --remit SEAT=TEXT (or SEAT=@FILE) replaces the remit, and a seat without a section of its own
(software-methods, genomics, a custom seat) needs one. A custom seat (custom:NAME) also needs --prefix.

`defender` adds `findings-to-answer.json`: every finding of the merged file except those dropped before the
defence (`route: dropped`, or --drop), in an order shuffled with a seed (--seed; by default one taken from the
file's contents), renumbered D1, D2 ..., with only what the defender may see: location, kind, quote,
looked_in, source (renamed to the workspace's file name), concern, claim, consequence, change_my_mind and each
prior work's citation and identifier. No seat, severity, group, criterion, route, cost or norm_source, and no
`venue.md`. WORK/defence-ids.json maps each D id to the original id and lists what was dropped. A text that
still names a seat or an original id is listed under warnings for the coordinator to look at.

A workspace that exists is never written over: the next attempt goes to SEAT.2 (with briefs/SEAT.2.md),
defender.2 and defence-ids.2.json. For the same seats on another model (manuscript-other-models), --suffix @codex
names the folders and briefs SEAT@codex; the brief still names the seat without its model. Each command prints a JSON summary; capture it with `runs.py exec`.

Exit codes: 0 built; 1 refused (an unknown seat or module, a seat without a remit or prefix, a journal without
its article type, a template placeholder this script cannot fill, an unknown --drop id); 2 usage error.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import importlib.util
import io
import json
import random
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Optional

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)

SKILL = Path(__file__).resolve().parents[1]
REFERENCES = SKILL / "references"
FIGURES_PY = SKILL.parent / "manuscript-figures" / "scripts" / "figures.py"

HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
LATEX_COMMENT = re.compile(r"(?<!\\)%[^\n]*")
HTML_COMMENT_SUFFIXES = {".md", ".markdown", ".qmd", ".rmd", ".txt", ".html", ".htm"}
READING_SUFFIXES = HTML_COMMENT_SUFFIXES | {".tex"}
FIGURE_SUFFIXES = {".md", ".markdown", ".qmd", ".rmd", ".tex"}  # documents figures.py reads for figures
MARK = "\x00"

DROPPED_MODULE_SECTIONS = {"Load it when", "Do not load it when", "Running the authors' code"}
DOMAIN_HEADER = ("# Your domain questions\n\nReviewer questions for your remit. They are prompts, not a checklist: "
                 "skip a question that does not apply to this paper, and raise a concern only when resolving it "
                 "could change a claim. Where a question suggests opening a link or looking up an identifier, work "
                 "from the files in your workspace instead and say what you could not check.\n")
DEFENDER_FIELDS = ("location", "kind", "quote", "looked_in", "source", "concern", "claim", "consequence",
                   "change_my_mind")
ORIGINAL_ID = re.compile(r"\b[A-Z]{2}[A-Z]?-\d+\b")
# Words that would tell the defender whose finding it is; ordinary words that name a seat ("figures",
# "reproducibility", "genomics") are left out, since concerns use them in their own sense.
WHOSE = re.compile(r"\b(?:skeptic|champion|reviewer 2|[a-z]+-(?:novelty|statistics|methods|editor|clinical|systems))\b",
                   re.I)


class Refused(Exception):
    """The inputs cannot make a workspace the skill's rules allow; the message says why."""


# ------------------------------------------------------------------------------------------- reading copies

def without_comments(text: str, suffix: str) -> str:
    """The text an editor sees: HTML comments (and, in LaTeX, `%` comments) removed. A line that held nothing
    but comments goes with them; revision marks are comments, so they go too."""
    pattern = LATEX_COMMENT if suffix == ".tex" else HTML_COMMENT
    marked = pattern.sub(MARK, text)
    lines = []
    for line in marked.split("\n"):
        if MARK in line and not line.replace(MARK, "").strip():
            continue
        lines.append(line.replace(MARK, ""))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines))


def read_text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="replace")


@dataclass
class Prepared:
    """What every workspace of one build gets: reading copies, supplementary files, figures."""
    documents: dict[str, str]  # workspace name -> reading copy
    files: dict[str, tuple[Path, Optional[str]]]  # supplementary/<rel> -> (source, reading copy or None)
    left_out: dict[str, str]  # rel -> why it is not in the workspace
    figures: Path  # a folder of PNGs and index.md
    names: dict[str, str]  # a file name a finding may give as `source` -> its name in the workspace
    warnings: list[str] = field(default_factory=list)

    def install(self, workspace: Path) -> None:
        workspace.mkdir(parents=True)
        for name, text in self.documents.items():
            (workspace / name).write_text(text, encoding="utf-8")
        for rel, (source, text) in self.files.items():
            target = workspace / "supplementary" / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if text is None:
                shutil.copyfile(source, target)
            else:
                target.write_text(text, encoding="utf-8")
        shutil.copytree(self.figures, workspace / "figures")

    def listing(self) -> list[str]:
        return [*self.documents, *(f"supplementary/{rel}" for rel in self.files), "figures/index.md"]


def document_name(path: Path, n: int) -> str:
    suffix = path.suffix.lower() if path.suffix.lower() in READING_SUFFIXES else ".md"
    return ("manuscript" if n == 0 else "supplementary" if n == 1 else f"supplementary-{n}") + suffix


def mentioned(path: Path, folder: Path, texts: list[str]) -> bool:
    rel = path.relative_to(folder).as_posix()
    return any(path.name in text or rel in text for text in texts)


def supplementary_files(folder: Optional[Path], texts: list[str], all_files: bool, extra: list[Path],
                        skip: set[Path]) -> tuple[dict[str, Path], dict[str, str]]:
    """The supplementary files a seat gets (rel -> source) and those it does not (rel -> why)."""
    chosen: dict[str, Path] = {}
    for path in extra:
        chosen[path.name] = path
    if folder is None:
        return chosen, {}
    candidates = sorted(p for p in folder.rglob("*")
                        if p.is_file() and not any(part.startswith(".") for part in p.relative_to(folder).parts)
                        and p.resolve() not in skip)
    if all_files:
        chosen.update({p.relative_to(folder).as_posix(): p for p in candidates})
        return chosen, {}
    searched = [*texts, *(without_comments(read_text(p), p.suffix.lower()) for p in extra
                          if p.suffix.lower() in READING_SUFFIXES)]
    while True:
        found = [p for p in candidates if p.relative_to(folder).as_posix() not in chosen
                 and mentioned(p, folder, searched)]
        if not found:
            break
        chosen.update({p.relative_to(folder).as_posix(): p for p in found})
        searched = [without_comments(read_text(p), p.suffix.lower()) for p in found
                    if p.suffix.lower() in READING_SUFFIXES]
    left = {p.relative_to(folder).as_posix(): "not named in the paper, its supplement or a file they name"
            for p in candidates if p.relative_to(folder).as_posix() not in chosen}
    return chosen, left


@functools.cache
def figures_module() -> ModuleType:
    """manuscript-figures' figures.py, whose `workspace` command renders each figure for a reader."""
    spec = importlib.util.spec_from_file_location("_peer_review_figures", FIGURES_PY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their annotations through sys.modules
    spec.loader.exec_module(module)
    return module


INDEX_LINE = re.compile(r"^- \*\*(?P<id>.+?)\*\*: (?P<images>\(no image\)|`[^`]+`(?:, `[^`]+`)*)(?P<rest>.*)$")


def render_figures(documents: list[Path], into: Path, width: int, warnings: list[str]) -> None:
    """figures.py workspace on each document, merged into one folder with one index.md."""
    into.mkdir(parents=True)
    header: list[str] = []
    entries: dict[str, tuple[list[str], str]] = {}  # figure id -> (images in `into`, rest of the line)
    with tempfile.TemporaryDirectory(prefix="seat-figures-") as scratch:
        for n, document in enumerate(documents):
            out = Path(scratch) / str(n)
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    figures_module().workspace(paper=document, into=out, width=width)
            except Exception as exc:  # an unreadable image must not stop the other documents' figures
                warnings.append(f"The figures of {document.name} could not be rendered: {exc}")
                continue
            lines = (out / "index.md").read_text(encoding="utf-8").splitlines()
            header = header or [line for line in lines[:next((i for i, x in enumerate(lines) if x.startswith("- **")),
                                                               len(lines))]]
            for line in lines:
                match = INDEX_LINE.match(line)
                if not match:
                    continue
                images = re.findall(r"`([^`]+)`", match["images"])
                if not images:
                    warnings.append(f"{match['id']} of {document.name} has no image: its file was not found beside "
                                    f"{document.name}; give the document at its own place, beside its figures.")
                known = entries.get(match["id"])
                if known and (known[0] or not images):
                    continue
                placed = []
                for image in images:
                    name = image if not (into / image).exists() else f"{Path(document).stem}-{image}"
                    shutil.copyfile(out / image, into / name)
                    placed.append(name)
                entries[match["id"]] = (placed, match["rest"])
    lines = header or ["# Figures", ""]
    if not entries:
        lines.append("The manuscript has no figures.")
    for figure, (images, rest) in entries.items():
        lines.append(f"- **{figure}**: " + (", ".join(f"`{i}`" for i in images) or "(no image)") + rest)
    (into / "index.md").write_text("\n".join(lines).rstrip("\n") + "\n", encoding="utf-8")


def prepare(paper: Path, supplements: list[Path], folder: Optional[Path], extra: list[Path], all_files: bool,
            width: int, scratch: Path) -> Prepared:
    warnings: list[str] = []
    documents: dict[str, str] = {}
    names: dict[str, str] = {}
    for n, path in enumerate([paper, *supplements]):
        name = document_name(path, n)
        documents[name] = without_comments(read_text(path), path.suffix.lower())
        names[path.name] = name
        names[name] = name
    skip = {p.resolve() for p in (paper, *supplements)}
    chosen, left = supplementary_files(folder, list(documents.values()), all_files, extra, skip)
    files: dict[str, tuple[Path, Optional[str]]] = {}
    for rel, source in chosen.items():
        suffix = source.suffix.lower()
        files[rel] = (source, without_comments(read_text(source), suffix) if suffix in READING_SUFFIXES else None)
        names.setdefault(source.name, f"supplementary/{rel}")
    figure_sources = [paper, *supplements, *(s for s, _ in files.values() if s.suffix.lower() in FIGURE_SUFFIXES)]
    render_figures(figure_sources, scratch / "figures", width, warnings)
    return Prepared(documents, files, left, scratch / "figures", names, warnings)


def next_free(path: Path) -> Path:
    """`path`, or path.2, path.3 ... when an earlier attempt is there: a workspace is never written over."""
    if not path.exists():
        return path
    n = 2
    while path.with_name(f"{path.name}.{n}").exists():
        n += 1
    return path.with_name(f"{path.name}.{n}")


# ------------------------------------------------------------------------------------------- the seats' briefs

def delink(text: str) -> str:
    """Markdown links as their text: a seat opens nothing outside its workspace."""
    return re.sub(r"\[([^\]\n]+)\]\([^)\n]+\)", r"\1", text)


@functools.cache
def seat_remits() -> dict[str, str]:
    """Each seat's remit as references/seats.md gives it: a section of its own, or a one-seat bullet."""
    text = (REFERENCES / "seats.md").read_text(encoding="utf-8")
    remits = {m["seat"]: delink(m["body"]).strip()
              for m in re.finditer(r"^### (?P<seat>[a-z-]+)[^\n]*\n(?P<body>.*?)(?=^#{2,3} |\Z)", text, re.S | re.M)}
    optional = re.search(r"^## Optional seats\n(?P<body>.*?)(?=^## |\Z)", text, re.S | re.M)
    for m in re.finditer(r"^- \*\*(?P<seat>[a-z-]+)\*\*: (?P<body>.*?)(?=^- |\Z)", optional["body"] if optional else "",
                         re.S | re.M):
        remits.setdefault(m["seat"], " ".join(delink(m["body"]).split()))
    return remits


@functools.cache
def seat_prefixes() -> dict[str, str]:
    text = (REFERENCES / "finding-schema.md").read_text(encoding="utf-8")
    table = re.search(r"^\| Seat \| Prefix \|.*?(?=\n\n)", text, re.S | re.M)
    return dict(re.findall(r"\| ([a-z-]+) \| ([A-Z]{2}) ", table.group(0) if table else ""))


def brief_template() -> list[str]:
    """The seat brief of references/seats.md as paragraphs and list items, without the quote markers."""
    text = (REFERENCES / "seats.md").read_text(encoding="utf-8")
    section = re.search(r"^## The seat brief\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    quoted = re.search(r"(?:^>.*\n?)+", section.group(1) if section else "", re.M)
    if not quoted:
        raise Refused("references/seats.md has no quoted seat brief under \"The seat brief\".")
    blocks: list[str] = []
    for line in quoted.group(0).splitlines():
        line = re.sub(r"^> ?", "", line)
        if not line.strip():
            blocks.append("")
        elif re.match(r"\d+\. ", line) or not blocks or not blocks[-1]:
            blocks.append(line)
        else:
            blocks[-1] += " " + line.strip()
    return blocks


def article(journals: list[tuple[str, Optional[str]]]) -> tuple[str, Optional[str], str]:
    """The two journal sentences of the template: one journal, or several."""
    one = journals[0]
    several = ", ".join(f"{name} ({kind})" if kind else name for name, kind in journals)
    several = re.sub(r", ([^,]+)$", r" and \1", several) if len(journals) > 1 else several
    return one[0], one[1] or "", several


def fill_brief(seat: str, prefix: str, remit: str, modules: bool, workspace: Path, journals: list[tuple[str, Optional[str]]],
               design: str, files: list[str]) -> str:
    blocks = brief_template()
    name, kind, several = article(journals)

    def journal(m: re.Match[str]) -> str:
        if len(journals) == 1:
            if not kind:
                raise Refused(f"Give the article type with the journal: --journal \"{name}=Research Article\".")
            return m["one"].replace("<journal>", name).replace("<article type>", kind)
        return re.sub(r"<journal 1>, <journal 2> and <journal 3>", several, m["several"])

    out = []
    for block in blocks:
        block = block.replace("<seat>", seat).replace("<prefix>", prefix).replace("<keys>", design)
        block = re.sub(r'<One journal: "(?P<one>.+?)" Several: "(?P<several>.+?)">', journal, block)
        block = block.replace("<absolute path of your workspace>", str(workspace.resolve()))
        block = re.sub(r'\s*<If a module is loaded: "(?P<sentence>.+?)">',
                       lambda m: " " + m["sentence"] if modules else "", block)
        if "<remit from seats.md>" in block:
            head, tail = block.split("<remit from seats.md>", 1)
            if "\n" in remit:
                block = head.rstrip() + "\n\n" + remit + ("\n\n" + tail.lstrip(". ").strip() if tail.strip(". ") else "")
            else:
                block = head + remit.rstrip(".") + tail
        out.append(block)
    text = "\n".join(out).strip() + "\n"
    if left := re.findall(r"<[A-Za-z][^<>\n]*>", text):
        raise Refused(f"The seat brief in references/seats.md has a placeholder this script does not fill: {left[0]}")
    listing = ", ".join(f"`{f}`" for f in files)
    return text + f"\nThe files in your workspace: {listing}.\n"


def remit_for(seat: str, seats: list[str], given: dict[str, str], also: dict[str, list[str]]) -> str:
    remits = seat_remits()
    if seat in given:
        return given[seat]
    if seat not in remits:
        raise Refused(f"The seat {seat} has no remit of its own in references/seats.md; give one with "
                      f"--remit {seat}=TEXT (or {seat}=@FILE).")
    extra = list(also.get(seat, []))
    main = next((s for s in seats if s not in {"skeptic", "champion"}), None)
    if seat == main and "reproducibility" not in seats and seat != "reproducibility":
        extra.append("reproducibility")
    if seat == "skeptic" and "claims-novelty" not in seats:
        extra.append("claims-novelty")
    parts = [remits[seat]]
    for other in dict.fromkeys(extra):
        if other not in remits:
            raise Refused(f"--also names {other}, which has no remit in references/seats.md.")
        parts.append(f"You also take the {other} remit:\n\n{remits[other]}")
    return "\n\n".join(parts)


def domain_questions(modules: list[str]) -> str:
    folder = REFERENCES / "domains"
    known = sorted(p.stem for p in folder.glob("*.md"))
    parts = [DOMAIN_HEADER]
    for module in modules:
        if module not in known:
            raise Refused(f"No domain module {module}; the modules are {', '.join(known)}.")
        kept, skipping = [], False
        for line in (folder / f"{module}.md").read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                skipping = line[3:].strip() in DROPPED_MODULE_SECTIONS
            if skipping or line.startswith("Record in the output why the module was loaded"):
                continue
            kept.append(line)
        parts.append(re.sub(r"\n{3,}", "\n\n", delink("\n".join(kept))).strip() + "\n")
    return "\n".join(parts)


# ------------------------------------------------------------------------------------------- the defender's findings

def defence_packet(merged: dict[str, Any], drops: dict[str, str], seed: int,
                   names: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str], list[str]]:
    findings = [f for f in merged.get("findings", []) if isinstance(f, dict)]
    ids = {str(f.get("id")) for f in findings}
    if unknown := sorted(set(drops) - ids):
        raise Refused(f"--drop names {', '.join(unknown)}, which the findings file does not have.")
    dropped = dict(drops)
    for f in findings:
        if f.get("route") == "dropped" and str(f.get("id")) not in dropped:
            dropped[str(f["id"])] = f.get("drop_reason") or "route: dropped"
    keep = [f for f in findings if str(f.get("id")) not in dropped]
    random.Random(seed).shuffle(keep)
    packet, mapping, warnings = [], {}, []
    for n, finding in enumerate(keep, 1):
        answer: dict[str, Any] = {"id": f"D{n}"}
        for key in DEFENDER_FIELDS:
            if finding.get(key) not in (None, "", []):
                answer[key] = finding[key]
        if "source" in answer:
            given = Path(str(answer["source"])).name  # the run's snapshot of a file is inputs/02-NAME
            answer["source"] = names.get(given) or names.get(re.sub(r"^\d+-", "", given)) or answer["source"]
            if answer["source"] not in names.values():
                warnings.append(f"D{n} quotes {answer['source']}, which is not in the defender's workspace.")
        if works := finding.get("prior_work"):
            answer["prior_work"] = [{k: w[k] for k in ("citation", "identifier") if isinstance(w, dict) and w.get(k)}
                                    for w in works]
        mapping[f"D{n}"] = str(finding.get("id"))
        text = json.dumps(answer, ensure_ascii=False)
        named = sorted({m for m in ORIGINAL_ID.findall(text) if m in ids} | set(WHOSE.findall(text)))
        if named:
            warnings.append(f"D{n} ({mapping[f'D{n}']}) names {', '.join(named)}: the defender should not learn "
                            "whose finding it is.")
        packet.append(answer)
    return packet, mapping, dropped, warnings


# ------------------------------------------------------------------------------------------- commands

def pairs(values: Optional[list[str]], option: str) -> dict[str, str]:
    out = {}
    for value in values or []:
        key, sep, rest = value.partition("=")
        if not sep or not key.strip():
            raise typer.BadParameter(f"{option} takes KEY=VALUE, not {value!r}.")
        out[key.strip()] = rest.strip()
    return out


def folder_name(seat: str) -> str:
    return seat.replace(":", "-")


def refuse(message: str) -> None:
    typer.echo(message, err=True)
    raise typer.Exit(1)


Paper = Annotated[Path, typer.Option("--paper", exists=True, dir_okay=False, help="The manuscript as Markdown, LaTeX or text")]
Supplement = Annotated[Optional[list[Path]], typer.Option("--supplement", exists=True, dir_okay=False,
                                                          help="A supplement document; repeat for several")]
Files = Annotated[Optional[Path], typer.Option("--files", exists=True, file_okay=False,
                                               help="The folder of supplementary files")]
File = Annotated[Optional[list[Path]], typer.Option("--file", exists=True, dir_okay=False,
                                                    help="A supplementary file to include whatever names it")]
AllFiles = Annotated[bool, typer.Option("--all-files", help="Every file of --files, named in the text or not")]
Width = Annotated[int, typer.Option(help="Width of each figure image, pixels")]


@app.command()
def seats(
    work: Annotated[Path, typer.Argument(file_okay=False, help="This skill's folder in the run")],
    paper: Paper,
    venue: Annotated[Path, typer.Option("--venue", exists=True, dir_okay=False, help="The referees' venue.md")],
    journal: Annotated[list[str], typer.Option("--journal", help="NAME=ARTICLE TYPE; repeat for each journal")],
    design: Annotated[str, typer.Option("--design", help="The study design keys, as the brief should give them")],
    seat: Annotated[list[str], typer.Option("--seat", help="A seat of the panel; repeat for each")],
    supplement: Supplement = None,
    files: Files = None,
    file: File = None,
    all_files: AllFiles = False,
    module: Annotated[Optional[list[str]], typer.Option("--module", help="SEAT=MODULE[,MODULE]")] = None,
    remit: Annotated[Optional[list[str]], typer.Option("--remit", help="SEAT=TEXT or SEAT=@FILE")] = None,
    also: Annotated[Optional[list[str]], typer.Option("--also", help="SEAT=SECTION of seats.md to add")] = None,
    prefix: Annotated[Optional[list[str]], typer.Option("--prefix", help="SEAT=XY for a custom seat")] = None,
    suffix: Annotated[str, typer.Option("--suffix", help="Added to folder and brief names: @codex")] = "",
    width: Width = 1600,
) -> None:
    """Each seat's workspace (WORK/seats/SEAT) and its filled-in brief (WORK/briefs/SEAT.md)."""
    try:
        panel = list(dict.fromkeys(seat))
        modules = {k: [m.strip() for m in v.split(",") if m.strip()] for k, v in pairs(module, "--module").items()}
        given = {k: (Path(v[1:]).read_text(encoding="utf-8").strip() if v.startswith("@") else v)
                 for k, v in pairs(remit, "--remit").items()}
        extra: dict[str, list[str]] = {}
        for k, v in pairs(also, "--also").items():
            extra.setdefault(k, []).extend(s.strip() for s in v.split(",") if s.strip())
        prefixes = {**seat_prefixes(), **pairs(prefix, "--prefix")}
        for option, named in (("--module", modules), ("--remit", given), ("--also", extra)):
            if stray := sorted(set(named) - set(panel)):
                raise Refused(f"{option} names {', '.join(stray)}, which is not a --seat.")
        for s in panel:
            if s not in prefixes:
                raise Refused(f"No prefix for the seat {s}: a custom seat is custom:NAME with --prefix {s}=XY, and the "
                              f"seats are {', '.join(sorted(seat_prefixes()))}.")
        journals = [(k.strip(), (v.strip() or None) if sep else None)
                    for k, sep, v in (j.partition("=") for j in journal)]
        remits = {s: remit_for(s, panel, given, extra) for s in panel}
        questions = {s: domain_questions(modules[s]) for s in panel if modules.get(s)}
        work.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="seat-workspaces-") as scratch:
            prepared = prepare(paper, supplement or [], files, file or [], all_files, width, Path(scratch))
            built = []
            for s in panel:
                workspace = next_free(work / "seats" / (folder_name(s) + folder_name(suffix)))
                prepared.install(workspace)
                shutil.copyfile(REFERENCES / "finding-schema.md", workspace / "finding-schema.md")
                shutil.copyfile(venue, workspace / "venue.md")
                listing = [*prepared.listing(), "venue.md", "finding-schema.md"]
                if s in questions:
                    (workspace / "domain-questions.md").write_text(questions[s], encoding="utf-8")
                    listing.append("domain-questions.md")
                brief = work / "briefs" / f"{workspace.name}.md"
                brief.parent.mkdir(parents=True, exist_ok=True)
                brief.write_text(fill_brief(s, prefixes[s], remits[s], s in questions, workspace, journals, design,
                                            listing), encoding="utf-8")
                built.append({"seat": s, "workspace": str(workspace.resolve()), "brief": str(brief.resolve()),
                              "modules": modules.get(s, []), "files": listing})
            figures = len(re.findall(r"^- \*\*", (prepared.figures / "index.md").read_text(encoding="utf-8"), re.M))
    except Refused as exc:
        refuse(str(exc))
        return
    typer.echo(json.dumps({"seats": built, "figures": figures, "left_out": prepared.left_out,
                           "warnings": prepared.warnings}, indent=2, ensure_ascii=False))


@app.command()
def defender(
    work: Annotated[Path, typer.Argument(file_okay=False, help="This skill's folder in the run")],
    paper: Paper,
    findings: Annotated[Path, typer.Option("--findings", exists=True, dir_okay=False,
                                           help="The merged findings (findings.merged.json)")],
    supplement: Supplement = None,
    files: Files = None,
    file: File = None,
    all_files: AllFiles = False,
    drop: Annotated[Optional[list[str]], typer.Option("--drop", help="ID=REASON for a finding dropped before the defence")] = None,
    seed: Annotated[Optional[int], typer.Option(help="Seed of the order; by default one from the file's contents")] = None,
    width: Width = 1600,
) -> None:
    """The defender's workspace (WORK/defender) with the findings stripped of who raised them, and the id map."""
    try:
        raw = findings.read_bytes()
        try:
            merged = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise Refused(f"{findings.name} is not JSON: {exc}") from exc
        seed = seed if seed is not None else int.from_bytes(hashlib.sha256(raw).digest()[:4], "big")
        work.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="defender-workspace-") as scratch:
            prepared = prepare(paper, supplement or [], files, file or [], all_files, width, Path(scratch))
            packet, mapping, dropped, warnings = defence_packet(merged, pairs(drop, "--drop"), seed, prepared.names)
            workspace = next_free(work / "defender")
            prepared.install(workspace)
            (workspace / "findings-to-answer.json").write_text(
                json.dumps({"findings": packet}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            attempt = workspace.name.removeprefix("defender")
            ids = work / f"defence-ids{attempt}.json"
            ids.write_text(json.dumps({"seed": seed, "findings": findings.name, "map": mapping,
                                       "dropped_before_defence": dropped}, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    except Refused as exc:
        refuse(str(exc))
        return
    typer.echo(json.dumps({"workspace": str(workspace.resolve()), "findings_to_answer": len(packet),
                           "ids": str(ids.resolve()), "dropped_before_defence": dropped,
                           "files": [*prepared.listing(), "findings-to-answer.json"], "left_out": prepared.left_out,
                           "warnings": prepared.warnings + warnings}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
