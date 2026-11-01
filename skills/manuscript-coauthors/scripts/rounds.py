# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Rounds of a manuscript shared with co-authors on Google Drive (manuscript-coauthors): open the next round's
folder, push a release to the Drive folder, record its Docs, and pull the comments back.

    uv run --script rounds.py show [--project DIR]
    uv run --script rounds.py open 0.7 [--from 0.6] [--project DIR]
    uv run --script rounds.py push 0.7 [--go] [--replace] [--project DIR]
    uv run --script rounds.py record 0.7 [--doc NAME=LINK ...] [--project DIR]
    uv run --script rounds.py circulated 0.7 [--commit SHA] [--project DIR]
    uv run --script rounds.py pull 0.6 --out RUN/manuscript-coauthors/exports [--go] [--project DIR]
    uv run --script rounds.py routes [--connector | --no-connector] [--host claude|codex] [--project DIR]
    uv run --script rounds.py sync 0.6 --into 0.7 [--export DIR] [--out DIR] [--check] [--project DIR]
    uv run --script rounds.py port 0.6 --run RUN [--gdoc READ_DOC.json ...] [--no-pull] [--go] [--project DIR]

`port` takes a round's comments from Google Docs all the way to the run's dashboard, for reviewers who only
use the Doc: pull (the connector's read_doc answers given with --gdoc, else `pull` through rclone), the
commenters recorded as people, the co-authors' findings (comments not triaged yet included), then the run's own
last collect, corrected version and dashboard commands replayed on the new inventory as their next attempts.
Every step goes through runs.py exec, so the run records it. Triage stays the agent's (the skill's step 2);
port again with --no-pull afterwards.

The settings are the project file's `coauthors` block (.manuscript-skills.yaml; saved with manuscript-integrity-
check's `project.py configure --drive ...`): how a release reaches Drive (`drive`: rclone into the shared folder
by its id, a copy into the folder Drive for desktop syncs, or by hand through a connector), each round's folder
name (`round_folder`, v{round}), the project's own .docx build (`build`), what a release uploads (`release.docs`
as Google Docs, `release.files` as they are; `PATH=Title` names the Doc, and {round} and {previous} are filled
in), and `rounds`, which this script keeps: each round's base commit, release date, Doc links and the dates it
went to the co-authors.

`push` and `pull` print the commands and run nothing unless `--go`. `push` never replaces a file already in the
round's Drive folder unless `--replace`: replacing a Doc keeps its link but can detach the co-authors' comments
from their text, so check the Doc's comments before asking for it. A Drive-for-desktop folder holds .gdoc links,
not the Docs' text, so `pull` needs rclone or a connector.

`sync` carries into the masters what was changed in a round's Docs after they went to the co-authors: accepted
suggestions and the authors' own edits, which an export shows no mark of and which the next release, built from the
masters, would undo. It compares each Doc's text (pending suggestions left out) with its master at the circulated
commit, Markdown set aside, and writes each paragraph that differs as an edit for runs.py apply on the masters of
--into; one the target master changed since is a conflict to settle by hand. `push --go` runs the same comparison for
the previous round first and refuses while its Docs hold changes the new masters lack (--unsynced-ok to release
anyway). A connector user gives the exports with --export; without rclone, push then asks for a recorded sync.

`routes` says which ways to the Docs this machine has: an rclone remote of type drive, the synced folder, and a
Google Drive connector among the agent's own tools, which the agent checks and passes as --connector (the script
cannot see them). When none can pull the comments it gives one setup note for the authors, for the host the run
is in: how to connect Google Drive there, or set up rclone. The run records it (runs.py issue --kind setup), the
progress pane shows it, and nothing waits for it.

EXIT STATUS 0 done · 1 refused (a file exists on Drive; a round folder exists) · 2 usage or settings · 3 could not
run (rclone, git or the build failed or is missing)
"""
from __future__ import annotations

import fnmatch
import importlib.util
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

SCRIPTS = Path(__file__).resolve().parents[2] / "manuscript-integrity-check" / "scripts"
COMMENTS = Path(__file__).resolve().parent / "comments.py"
LEFT_BEHIND = ("reviews", "build", "comments.yaml", "changes-from-*.md", "*.dashboard.html", "*.review.docx",
               "*.changes.xlsx", "*.proposed.*")  # a round's run outputs and its co-authors' comments stay with it
OFFICE = (".docx", ".xlsx", ".pptx")  # a release entry already in Drive's import format: uploaded as it is

app = typer.Typer(add_completion=False, no_args_is_help=True)


class Refused(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def projects() -> Any:
    """manuscript-integrity-check's project.py, which reads and writes the project file."""
    if "coauthors_project" not in sys.modules:
        sys.path.insert(0, str(SCRIPTS))  # project.py imports settings.py beside it
        spec = importlib.util.spec_from_file_location("coauthors_project", SCRIPTS / "project.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["coauthors_project"] = module
        spec.loader.exec_module(module)
    return sys.modules["coauthors_project"]


class Project:
    def __init__(self, where: Path | None):
        p = projects()
        start = (where or Path.cwd()).expanduser().resolve()
        self.path = p.config_path(str(start), start if start.name == p.CONFIG or start.is_dir() and
                                  (start / p.CONFIG).exists() else None)
        if not self.path.exists():
            raise Refused(f"No project file (.manuscript-skills.yaml) at or above {start}.")
        try:
            self.data = p.read(self.path)
        except p.ProjectError as exc:
            raise Refused(str(exc)) from exc
        if "coauthors" not in self.data:
            raise Refused(f"{self.path}: no co-author settings; save them with project.py configure --drive ...")
        self.block: dict[str, Any] = self.data["coauthors"]
        self.pattern = self.block.get("round_folder", p.ROUND_FOLDER)
        here = self.path.parent
        self.root = here.parent if self.round_of(here.name) else here  # the folder that holds the round folders

    def round_of(self, name: str) -> str | None:
        regex = re.escape(self.pattern).replace(re.escape("{round}"), r"(?P<round>\d[\w.-]*)")
        found = re.fullmatch(regex, name)
        return found.group("round") if found else None

    def folder(self, name: str) -> Path:
        return self.root / self.pattern.format(round=name)

    def rounds(self) -> dict[str, dict[str, Any]]:
        return self.block.setdefault("rounds", {})

    def previous(self, name: str) -> str | None:
        """The round before *name*: the latest round folder on disk that sorts before it."""
        def key(r: str) -> list[int | str]:
            return [int(x) if x.isdigit() else x for x in re.split(r"[.-]", r)]
        known = {r for d in self.root.iterdir() if d.is_dir() and (r := self.round_of(d.name))} | set(self.rounds())
        earlier = sorted((r for r in known if key(r) < key(name)), key=key)
        return earlier[-1] if earlier else None

    def save(self, path: Path | None = None) -> None:
        projects().write(path or self.path, self.data)


def git(folder: Path, *args: str) -> str | None:
    if shutil.which("git") is None:
        return None
    done = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True, encoding="utf-8")
    return done.stdout.strip() if done.returncode == 0 else None


def fill(text: str, **values: str) -> str:
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


@dataclass(frozen=True)
class Doc:
    """One Google Doc (or Sheet) of a release: a master built to .docx, or an office file imported as it is."""

    source: Path
    title: str

    @property
    def office(self) -> bool:
        return self.source.suffix.lower() in OFFICE

    @property
    def upload(self) -> Path:
        return self.source if self.office else built(self.source)

    @property
    def kind(self) -> str:  # the format Drive imports it from, and the extension rclone lists it with
        return self.upload.suffix.lower()[1:]

    @property
    def on_drive(self) -> str:
        return f"{self.title}.{self.kind}"


@dataclass(frozen=True)
class File:
    """One file of a release, uploaded as it is, to its path below the round's Drive folder."""

    source: Path
    dest: str


def releases(project: Project, name: str) -> tuple[list[Doc], list[File], list[str]]:
    """What the round uploads: its Docs with their titles, its files with where each goes, and the file
    patterns that match nothing (a PDF not built yet)."""
    folder = project.folder(name)
    values = {"round": name, "previous": project.previous(name) or ""}
    release = project.block.get("release", {})
    docs = []
    for entry in release.get("docs", []):
        path, _, title = (fill(part, **values).strip() for part in entry.partition("="))
        docs.append(Doc(folder / path, title or Path(path).stem))
    files: list[File] = []
    unmatched: list[str] = []
    for entry in release.get("files", []):
        pattern, _, dest = (fill(part, **values).strip() for part in entry.partition("="))
        found = [f for f in sorted(folder.glob(pattern)) if f.is_file()]
        if dest and not dest.endswith("/") and len(found) > 1:
            raise Refused(f"{entry}: {len(found)} files cannot all take the name {dest}; end it with / for a folder.")
        files += [File(f, f"{dest}{f.name}" if not dest or dest.endswith("/") else dest) for f in found]
        unmatched += [] if found else [pattern]
    return docs, files, unmatched


def built(master: Path) -> Path:
    return master.parent / "build" / f"{master.stem}.docx"


def build_commands(project: Project, folder: Path, docs: list[Doc]) -> list[list[str]]:
    """How each master becomes a .docx: the project's own build ({file} is the master below the round folder),
    or pandoc from the clean copy. An office file needs none."""
    out = []
    for doc in docs:
        if doc.office:
            continue
        if project.block.get("build"):
            relative = doc.source.relative_to(folder).as_posix()
            out.append(shlex.split(fill(project.block["build"], file=relative, stem=doc.source.stem)))
        else:
            clean = doc.source.with_name(f"{doc.source.stem}.clean{doc.source.suffix}")
            out.append(["pandoc", str(clean if clean.exists() else doc.source), "-o", str(built(doc.source))])
    return out


def remote(project: Project, name: str, file: str = "") -> list[str]:
    target = f"{project.block['remote']}:{project.pattern.format(round=name)}" + (f"/{file}" if file else "")
    return [target, "--drive-root-folder-id", project.block["folder_id"]]


def lsjson(project: Project, name: str, *flags: str) -> list[dict[str, Any]]:
    done = subprocess.run(["rclone", "lsjson", "-R", *flags, *remote(project, name)], capture_output=True, text=True,
                          encoding="utf-8")
    if done.returncode != 0:
        if "directory not found" in done.stderr.lower():
            return []
        raise Refused(f"rclone lsjson failed: {done.stderr.strip()}", 3)
    return json.loads(done.stdout or "[]")


def listing(project: Project, name: str) -> list[dict[str, Any]]:
    """The round's Drive folder as rclone lists it, each entry's Path below it. rclone shows a Google Doc as
    "Title.docx" (a Sheet as "Title.xlsx"), like a Word file; the Docs are what --drive-skip-gdocs leaves out,
    so each entry says whether it is one (`gdoc`)."""
    every = lsjson(project, name)
    plain = {e["ID"] for e in lsjson(project, name, "--drive-skip-gdocs")} if every else set()
    return [e | {"gdoc": e["ID"] not in plain and not e.get("IsDir")} for e in every]


def doc_link(entry: dict[str, Any]) -> str:
    kind = {"xlsx": "spreadsheets", "pptx": "presentation"}.get(Path(entry["Name"]).suffix[1:].lower(), "document")
    return f"https://docs.google.com/{kind}/d/{entry['ID']}/edit"


def gdocs(entries: list[dict[str, Any]]) -> dict[str, str]:
    """The Google Docs and Sheets at the top of the round's folder: title -> link."""
    return {Path(e["Name"]).stem: doc_link(e) for e in entries if e["gdoc"] and "/" not in e.get("Path", e["Name"])}


LOST_IMAGE = re.compile(r"Could not (?:convert|fetch|find) (?:image|resource)\s+['\"]?([^\s:'\"]+)", re.IGNORECASE)


def execute(commands: list[list[str]], cwd: Path) -> None:
    for command in commands:
        if command[0] == "copy":  # into the folder Drive for desktop syncs, the same on every platform
            Path(command[2]).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(command[1], command[2])
            continue
        if shutil.which(command[0]) is None:
            raise Refused(f"{command[0]} is not installed; nothing was uploaded after this point.", 3)
        done = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8")
        if done.returncode != 0:
            raise Refused(f"{shlex.join(command)} failed: {(done.stderr or done.stdout).strip()}", 3)
        if lost := LOST_IMAGE.findall(f"{done.stderr}\n{done.stdout}"):  # pandoc warns and builds the Doc without it
            svg = any(name.lower().endswith(".svg") for name in lost)
            raise Refused(f"{shlex.join(command)} left out {', '.join(sorted(set(lost)))}: it could not convert "
                          + ("the SVG; install rsvg-convert (librsvg) and push again." if svg else
                             "the image; check the file and the tool pandoc names, and push again.")
                          + " Nothing was uploaded.", 3)


UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def file_name(title: str) -> str:
    """A Doc title as a local file name every file system takes (NTFS and Windows refuse : and its kin)."""
    return UNSAFE_NAME.sub("-", title).strip().rstrip(".") or "document"


REV_MARKS = Path(__file__).resolve().parents[2] / "manuscript-revision-marks" / "scripts" / "rev_marks.py"


def sign_offs(masters: list[Path]) -> dict[str, str]:
    """For each marked master of the release, how many of its passages an AI or agent wrote last with no person's
    name recorded since (revision marks' unreviewed count), in words a co-author reads."""
    if "rounds_rev_marks" not in sys.modules:
        spec = importlib.util.spec_from_file_location("rounds_rev_marks", REV_MARKS)
        module = importlib.util.module_from_spec(spec)
        sys.modules["rounds_rev_marks"] = module
        spec.loader.exec_module(module)
    rm = sys.modules["rounds_rev_marks"]
    out = {}
    for path in masters:
        if path.suffix.lower() not in (".md", ".markdown", ".tex") or not path.is_file():
            continue
        found = rm.parse(rm.read_source(path), rm.Syntax.TEX if path.suffix.lower() == ".tex" else rm.Syntax.MARKDOWN)
        if not found.segments or found.errors:
            continue
        try:
            open_ = rm.unreviewed(found, rm.load_people(path))
        except rm.ConfigError:
            continue
        out[path.name] = (f"{len(open_)} of {len(found.segments)} marked passages were last written by an AI or agent "
                          f"with no person's sign-off since")
    return out


# How to reach a round's Google Docs from each host, said once in a setup note when no route can pull the comments.
SETUP = {
    "claude": ("connect Google Drive in Claude (Settings, Connectors on claude.ai; on a Team or Enterprise plan an "
               "owner may have to allow it first) and check it with /mcp in a terminal session"),
    "codex": ("turn on the Google Drive connector of your ChatGPT workspace for Codex (Settings, Connectors); many "
              "workspaces have it on already"),
}
RCLONE_SETUP = ("or, on any host, add a Google Drive remote with `rclone config` and save it with `project.py "
                "configure --drive rclone --drive-remote NAME` (rclone also uploads each release)")


def drive_remotes() -> list[str] | None:
    """The rclone remotes of type drive; None when rclone is not installed."""
    if shutil.which("rclone") is None:
        return None
    try:
        done = subprocess.run(["rclone", "listremotes", "--long"], capture_output=True, text=True, encoding="utf-8",
                              timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line.split(":", 1)[0].strip() for line in done.stdout.splitlines()
            if ":" in line and line.split(":", 1)[1].split() == ["drive"]] if done.returncode == 0 else []


def say(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


ProjectOption = Annotated[Path | None, typer.Option("--project", help="The project folder or file (default: from here up)")]


@app.command()
def show(project_dir: ProjectOption = None) -> None:
    """The co-author settings and the rounds released so far."""
    project = Project(project_dir)
    say({"project_file": project.path.as_posix(), "rounds_folder": project.root.as_posix(), **project.block})


@app.command("open")
def open_round(name: str, source: Annotated[str | None, typer.Option("--from", help="The round to copy (default: the latest before it)")] = None,
               project_dir: ProjectOption = None) -> None:
    """Make the next round's folder: a copy of the released round without its run outputs and comments."""
    project = Project(project_dir)
    source = source or project.previous(name)
    if source is None:
        raise Refused(f"No round before {name} to copy; give --from.")
    old, new = project.folder(source), project.folder(name)
    if not old.is_dir():
        raise Refused(f"{old} does not exist.")
    if new.exists():
        raise Refused(f"{new} exists already; nothing was copied.", 1)
    left: list[str] = []

    def ignore(folder: str, names: list[str]) -> list[str]:
        skip = [n for n in names if any(fnmatch.fnmatch(n, p) for p in LEFT_BEHIND)]
        left.extend(Path(folder, n).relative_to(old).as_posix() for n in skip)
        return skip

    shutil.copytree(old, new, ignore=ignore)
    p = projects()
    base = git(old, "rev-parse", "--short", "HEAD")
    project.rounds()[name] = {"base": base} if base else {}
    target = new / p.CONFIG if (new / p.CONFIG).exists() else project.path
    if target == project.path:  # one project file above the rounds: its manuscripts move to the new round
        prefix = project.pattern.format(round=source) + "/"
        project.data["manuscripts"] = [m.replace(prefix, project.pattern.format(round=name) + "/", 1)
                                       if m.startswith(prefix) else m for m in project.data.get("manuscripts", [])]
    project.save(target)
    labels = []
    for master in project.data.get("manuscripts", []):
        path = new / Path(master).name
        if path.is_file():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if re.search(rf"(?<![\w.]){re.escape(project.pattern.format(round=source))}(?![\w])", line):
                    labels.append(f"{path.name}:{number}: {line.strip()[:120]}")
    carry = ({"carry_from_the_docs": f"What was changed in the v{source} Docs after they went out is not in these masters "
                                     f"yet: rounds.py sync {source} --into {name} --out DIR, then runs.py apply."}
             if project.rounds().get(source, {}).get("docs") else {})
    # The To-do marks travel with the round; marks saved in the old round's dashboard after this stay there, and
    # the new round's first run merges them (todo.py merge).
    marks = []
    for master in project.data.get("manuscripts", []):
        stem = Path(master).stem
        copied = new / f"{stem}.todo.json"
        if copied.is_file() or (old / f"{stem}.dashboard.html").is_file():
            count = len(json.loads(copied.read_text(encoding="utf-8")).get("marks", [])) if copied.is_file() else 0
            marks.append({"file": copied.as_posix(), "copied_marks": count, "previous": (old / copied.name).as_posix()})
    say({"opened": new.as_posix(), "from": old.as_posix(), "base": base, "left_behind": left,
         "project_file": target.as_posix(), "mentions_of_the_old_round": labels[:20], "todo_marks": marks,
         "changelog": (new / f"changes-from-{project.pattern.format(round=source)}.md").as_posix(), **carry})


@app.command()
def push(name: str, go: Annotated[bool, typer.Option("--go", help="Build and upload; without it, only print")] = False,
         replace: Annotated[bool, typer.Option("--replace", help="Replace files already in the round's Drive folder")] = False,
         unsynced_ok: Annotated[bool, typer.Option(
             "--unsynced-ok", help="Release although the previous round's Docs hold changes these masters lack")] = False,
         project_dir: ProjectOption = None) -> None:
    """Build the round's Docs and upload them, with its files, to the round's Drive folder. The previous round's Docs
    are checked first: what was changed there after they went out must be in these masters (rounds.py sync)."""
    project = Project(project_dir)
    folder = project.folder(name)
    if not folder.is_dir():
        raise Refused(f"{folder} does not exist; open the round first.")
    docs, files, unmatched = releases(project, name)
    if not docs and not files:
        raise Refused("Nothing to release: save release docs and files with project.py configure --release-doc/--release-file.")
    if missing := [d.source.as_posix() for d in docs if not d.source.is_file()]:
        raise Refused(f"Missing: {', '.join(missing)}.")
    drive = project.block["drive"]
    builds = build_commands(project, folder, docs)
    uploads: list[list[str]] = []
    existing: list[str] = []
    destination = project.pattern.format(round=name)
    again = ["--ignore-times"] if replace else []
    if drive == "rclone":
        entries = listing(project, name) if go else []
        on_drive = {(e["gdoc"], e.get("Path", e["Name"])) for e in entries}
        for doc in docs:
            existing += [doc.title] if (True, doc.on_drive) in on_drive else []
            uploads.append(["rclone", "copyto", str(doc.upload), *remote(project, name, doc.on_drive),
                            "--drive-import-formats", doc.kind, *again])
        for file in files:
            existing += [file.dest] if (False, file.dest) in on_drive else []
            uploads.append(["rclone", "copyto", str(file.source), *remote(project, name, file.dest), *again])
    elif drive == "folder":
        target = Path(project.block["folder"]).expanduser() / destination
        for doc in docs:
            existing += [doc.title] if (target / doc.on_drive).exists() else []
            uploads.append(["copy", str(doc.upload), str(target / doc.on_drive)])
        for file in files:
            existing += [file.dest] if (target / file.dest).exists() else []
            uploads.append(["copy", str(file.source), str(target / file.dest)])
    plan = {"round": name, "drive": drive, "destination": destination, "build": [shlex.join(c) for c in builds],
            "upload": [shlex.join(c) for c in uploads], **({"not_found": unmatched} if unmatched else {})}
    if unsigned := sign_offs([d.source for d in docs if not d.office]):
        plan["no_sign_off"] = unsigned  # tell the co-authors which wording nobody has put their name to yet
    if drive == "connector":
        plan["by_hand"] = ([f"{d.upload.as_posix()} as the Google {'Sheet' if d.kind == 'xlsx' else 'Doc'} “{d.title}”"
                            for d in docs] + [f"{f.source.as_posix()} as {f.dest}" for f in files])
        plan["note"] = "Upload these through the Drive connector or the Drive web page; then record the Doc links."
    if drive == "folder":
        plan["note"] = ("Drive for desktop uploads a .docx as a Word file unless its 'Convert uploads' setting is on; "
                        "open each in Google Docs (File > Save as Google Docs) before the co-authors comment.")
    previous = project.previous(name)
    prior = project.rounds().get(previous or "", {})
    checks_previous = bool(previous and prior.get("docs") and prior.get("circulated")) and not unsynced_ok
    if checks_previous:
        plan["sync_check"] = (f"--go first compares the v{previous} Docs with v{previous} as the co-authors got it and "
                              f"refuses while the v{name} masters lack what was changed there (rounds.py sync {previous} "
                              f"--into {name}).")
    if not go:
        say(plan | {"dry_run": True})
        return
    if checks_previous:
        unsynced(project, previous, name, drive)
    if existing and not replace:
        raise Refused(f"Already in {destination} on Drive: {', '.join(existing)}. Replacing a Doc keeps its link but "
                      "can detach the co-authors' comments; check its comments, then use --replace.", 1)
    execute(builds, folder)
    if not_built := [d.upload.as_posix() for d in docs if not d.upload.is_file()]:
        raise Refused(f"The build did not write {', '.join(not_built)}.", 3)
    if drive != "connector":
        execute(uploads, folder)
    entry = project.rounds().setdefault(name, {})
    entry["released"] = date.today().isoformat()
    commit = git(folder, "rev-parse", "--short", "HEAD")
    if commit:
        entry.setdefault("circulated", []).append({"date": date.today().isoformat(), "commit": commit})
    if drive == "rclone":
        titles = {d.title for d in docs}
        entry["docs"] = entry.get("docs", {}) | {t: link for t, link in gdocs(listing(project, name)).items() if t in titles}
    project.save()
    say(plan | {"uploaded": drive != "connector", "recorded": entry})


def unsynced(project: Project, previous: str, name: str, drive: str) -> None:
    """Refuse a release while the previous round's Docs hold changes the new round's masters lack."""
    if drive != "rclone":
        if not any(s.get("into") == name for s in project.rounds()[previous].get("synced", [])):
            raise Refused(f"Check the v{previous} Docs first: download each as .docx (named by its title) and run "
                          f"rounds.py sync {previous} --into {name} --export DIR, then apply what it finds; or release "
                          "without it with --unsynced-ok.", 1)
        return
    with tempfile.TemporaryDirectory() as scratch:
        result = compare(project, previous, name, None, Path(scratch))
    left = [f"{d['doc']}, {e['section'] or 'the start'}: “{e['doc'][:90]}”" for d in result["docs"]
            for e in [*d.get("edits", []), *d.get("conflicts", [])]]
    if left:
        raise Refused(f"The v{previous} Docs hold {len(left)} change(s) the v{name} masters lack. Carry them first "
                      f"(rounds.py sync {previous} --into {name} --out DIR, then runs.py apply), or release without "
                      "them with --unsynced-ok:\n  " + "\n  ".join(left[:20]), 1)


def a_day(value: str | None) -> str:
    try:
        return date.fromisoformat(value).isoformat() if value else date.today().isoformat()
    except ValueError as exc:
        raise Refused(f"Not a date (YYYY-MM-DD): {value}.") from exc


@app.command()
def record(name: str, doc: Annotated[list[str] | None, typer.Option("--doc", help="NAME=LINK of a Doc of this round; repeat")] = None,
           base: Annotated[str | None, typer.Option(help="The commit the round opened from (for a round opened by hand)")] = None,
           released: Annotated[str | None, typer.Option(help="The day the round went to Drive, YYYY-MM-DD")] = None,
           project_dir: ProjectOption = None) -> None:
    """Record the round's Doc links (given, or read from its Drive folder with rclone), and for a round released
    before these settings existed, its base commit and release day."""
    project = Project(project_dir)
    entry = project.rounds().setdefault(name, {})
    found: dict[str, str] = {}
    for item in doc or []:
        title, _, link = item.partition("=")
        if not title.strip() or not link.strip():
            raise Refused(f"--doc takes NAME=LINK, not {item!r}.")
        found[title.strip()] = link.strip()
    if not doc and not base and not released:
        if project.block["drive"] != "rclone":
            raise Refused("Give the links with --doc NAME=LINK; only rclone can read them from Drive.")
        found = gdocs(listing(project, name))
    if base:
        entry["base"] = base
    if released:
        entry["released"] = a_day(released)
    if found:
        entry["docs"] = entry.get("docs", {}) | found
    project.save()
    say({"round": name, **entry})


@app.command()
def circulated(name: str, commit: Annotated[str | None, typer.Option(help="The commit the co-authors got (default: HEAD)")] = None,
               day: Annotated[str | None, typer.Option("--date", help="When, YYYY-MM-DD (default: today)")] = None,
               project_dir: ProjectOption = None) -> None:
    """Note that the round went to the co-authors again, as of a commit: the changelog marks what changed since."""
    project = Project(project_dir)
    commit = commit or git(project.folder(name), "rev-parse", "--short", "HEAD")
    if not commit:
        raise Refused("No commit: give --commit, or run inside the git repository.", 3)
    entry = project.rounds().setdefault(name, {})
    entry.setdefault("circulated", []).append({"date": a_day(day), "commit": commit})
    project.save()
    say({"round": name, "circulated": entry["circulated"]})


@app.command()
def pull(name: str, out: Annotated[Path, typer.Option("--out", help="Where the exports go: the run's manuscript-coauthors/exports")],
         go: Annotated[bool, typer.Option("--go", help="Export and import; without it, only print")] = False,
         project_dir: ProjectOption = None) -> None:
    """Export the round's Docs as .docx and merge their comments into the round's comments.yaml."""
    project = Project(project_dir)
    folder = project.folder(name)
    docs = project.rounds().get(name, {}).get("docs", {})
    if not docs:
        raise Refused(f"No Docs recorded for round {name}: rounds.py record {name} --doc NAME=LINK.")
    masters = {d.title: d.source for d in releases(project, name)[0] if not d.office}
    steps = []
    for title, link in docs.items():
        if "/spreadsheets/" in link or "/presentation/" in link:
            continue  # a Sheet or Slides: no manuscript text for its comments to sit in
        found = re.search(r"/d/([\w-]{20,})", link)
        file_id = found.group(1) if found else link
        master = masters.get(title)
        export = out / f"{file_name(title)}.docx"  # the Drive title stays as it is; only the local name changes
        ledger = folder / "comments.yaml"
        steps.append({"doc": title, "link": link, "export": export.as_posix(), "master": master and master.as_posix(),
                      "commands": [["rclone", "backend", "copyid", f"{project.block.get('remote', 'gdrive')}:", file_id,
                                    export.as_posix(), "--drive-export-formats", "docx"],
                                   [sys.executable, str(COMMENTS), "import", "EXPORTED.docx", "--ledger", str(ledger),
                                    "--doc", link, *(["--master", str(master)] if master else [])]]})
    if project.block["drive"] != "rclone" or not go:
        say({"round": name, "dry_run": not go, "steps": [s | {"commands": [shlex.join(c) for c in s["commands"]]}
                                                         for s in steps],
             **({"by_hand": "Without rclone: download each Doc with the Drive connector (download_file_content, "
                            "exportMimeType application/vnd.openxmlformats-officedocument.wordprocessingml.document) "
                            "into --out, then run the import command on it."} if project.block["drive"] != "rclone" else {})})
        return
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for step in steps:
        execute([step["commands"][0]], folder)
        exported = [Path(step["export"])] if Path(step["export"]).is_file() else []
        if not exported:
            raise Refused(f"rclone exported nothing for {step['doc']}.", 3)
        command = [c if c != "EXPORTED.docx" else str(exported[0]) for c in step["commands"][1]]
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        if done.returncode != 0:
            raise Refused(f"Import of {step['doc']} failed: {done.stderr.strip()}", 3)
        results.append({"doc": step["doc"], "export": exported[0].as_posix(), **json.loads(done.stdout)})
    say({"round": name, "pulled": results})


def comments_module() -> Any:
    """comments.py beside this script: the Doc's text, the master's clean text and the edits between them."""
    if "coauthors_comments" not in sys.modules:
        spec = importlib.util.spec_from_file_location("coauthors_comments", COMMENTS)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["coauthors_comments"] = module  # its dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
    return sys.modules["coauthors_comments"]


def released_text(master: Path, commit: str) -> str:
    """The master as the co-authors got it: its text at the commit recorded when the round was circulated."""
    top = git(master.parent, "rev-parse", "--show-toplevel")
    if top is None:
        raise Refused(f"{master}: not in a git repository, so the version the co-authors got cannot be read.", 3)
    relative = master.resolve().relative_to(Path(top).resolve()).as_posix()
    done = subprocess.run(["git", "-C", top, "show", f"{commit}:{relative}"], capture_output=True, text=True,
                          encoding="utf-8")
    if done.returncode != 0:
        raise Refused(f"{relative} at {commit}: {done.stderr.strip()}", 3)
    return done.stdout


def exports_of(project: Project, name: str, titles: list[str], given: Path | None, into: Path) -> dict[str, Path]:
    """Each Doc of the round as .docx: from a folder of exports named by the Doc's title (a pull's, or downloads
    through a Drive connector), else exported now with rclone."""
    if given is not None:
        return {title: given / f"{title}.docx" for title in titles if (given / f"{title}.docx").is_file()}
    if project.block.get("drive") != "rclone":
        raise Refused("Give the round's Docs exported as .docx with --export DIR (a pull's exports, or each Doc "
                      "downloaded through the Drive connector as .docx and named by its title); only rclone exports "
                      "them here.")
    links = project.rounds().get(name, {}).get("docs", {})
    into.mkdir(parents=True, exist_ok=True)
    found = {}
    for title in titles:
        file_id = re.search(r"/d/([\w-]{20,})", links[title])
        before = set(into.glob("*.docx"))
        execute([["rclone", "backend", "copyid", f"{project.block.get('remote', 'gdrive')}:",
                  file_id.group(1) if file_id else links[title], f"{into.as_posix()}/", "--drive-export-formats", "docx"]],
                project.folder(name))
        new = sorted(set(into.glob("*.docx")) - before) or [into / f"{title}.docx"]
        if not new[0].is_file():
            raise Refused(f"rclone exported nothing for {title}.", 3)
        found[title] = new[0]
    return found


def compare(project: Project, name: str, into: str, given: Path | None, scratch: Path) -> dict[str, Any]:
    """For each Doc of round *name* built from a master: the paragraphs the Doc now reads differently from the master
    the co-authors got, as edits on the same master in round *into*. An edit whose released paragraph that master no
    longer has is a conflict to settle by hand; one whose new text it already has is carried."""
    cm = comments_module()
    entry = project.rounds().get(name, {})
    if not entry.get("docs"):
        raise Refused(f"No Docs recorded for round {name}: rounds.py record {name}.")
    if not entry.get("circulated"):
        raise Refused(f"Round {name} records no commit the co-authors got: rounds.py circulated {name} --commit SHA.")
    commit = entry["circulated"][-1]["commit"]
    masters = {d.title: d.source for d in releases(project, name)[0] if not d.office and d.title in entry["docs"]}
    exports = exports_of(project, name, list(masters), given, scratch)
    ledger_path = project.folder(name) / "comments.yaml"
    items = cm.read_ledger(ledger_path)["items"] if ledger_path.is_file() else []
    results, today = [], date.today().isoformat()
    for title, master in masters.items():
        relative = master.relative_to(project.folder(name)).as_posix()
        target = project.folder(into) / relative
        if title not in exports:
            results.append({"doc": title, "master": relative, "missing_export": True})
            continue
        found = cm.read_docx(exports[title])
        pending = {f.key for f in found} | {f"{relative}|{f.key}" for f in found}
        released = cm.clean_of(released_text(master, commit), master)
        now = cm.clean_of(cm.rev_marks().read_source(target), target) if target.is_file() else ""
        shown_now = cm.shown_as(now)
        edits, conflicts, carried = [], [], 0
        for edit in cm.doc_edits(released, cm.doc_paragraphs(exports[title])):
            ids = cm.suggestions_in(edit, items, pending)
            what = (f"accepted suggestion{'s' if len(ids) > 1 else ''} {', '.join(ids)}" if ids
                    else "an accepted suggestion or an author's own edit")
            if cm.shown_as(edit.after) in shown_now:
                carried += 1
            elif now.count(edit.before) == 1:
                edits.append({"before": edit.before, "after": edit.after, "section": edit.section,
                              "reason": f"Edited in the Doc of v{name} after it went to the co-authors ({what}); "
                                        f"carried into the master on {today}.",
                              "released": " … ".join(edit.released), "doc": " … ".join(edit.doc)})
            else:
                conflicts.append({"section": edit.section, "released": " … ".join(edit.released),
                                  "doc": " … ".join(edit.doc), "suggestions": ids,
                                  "why": ("the master has this paragraph more than once" if now.count(edit.before) > 1
                                          else f"{relative} in v{into} no longer has the paragraph as released")})
        results.append({"doc": title, "master": relative, "into": target.as_posix(), "edits": edits,
                        "conflicts": conflicts, "carried": carried})
    return {"round": name, "into": into, "commit": commit, "docs": results}


@app.command()
def sync(name: str,
         into: Annotated[str | None, typer.Option("--into", help="The round whose masters take the edits (default: this one)")] = None,
         export: Annotated[Path | None, typer.Option(
             "--export", help="A folder of the round's Docs as .docx named by title (a pull's exports); else rclone exports them")] = None,
         out: Annotated[Path | None, typer.Option("--out", help="Write each master's edits here as STEM.edits.json, for runs.py apply")] = None,
         check: Annotated[bool, typer.Option("--check", help="Exit 1 while a Doc has text the masters of --into lack")] = False,
         project_dir: ProjectOption = None) -> None:
    """What was changed in the round's Docs after they went to the co-authors (accepted suggestions, the authors' own
    edits), as edits on the masters the next release is built from. An export does not say a suggestion was accepted,
    so the Doc's text is compared with the master as the co-authors got it (the circulated commit)."""
    project = Project(project_dir)
    into = into or name
    if not project.folder(into).is_dir():
        raise Refused(f"{project.folder(into)} does not exist; open round {into} first (rounds.py open {into}).")
    with tempfile.TemporaryDirectory() as scratch:
        result = compare(project, name, into, export, Path(scratch))
    open_items = sum(len(d.get("edits", [])) + len(d.get("conflicts", [])) for d in result["docs"])
    if out is not None:
        out.mkdir(parents=True, exist_ok=True)
        for doc in result["docs"]:
            if doc.get("edits"):
                path = out / f"{Path(doc['master']).stem}.edits.json"
                path.write_text(json.dumps([{k: e[k] for k in ("before", "after", "reason", "section")} for e in doc["edits"]],
                                           ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                doc["edits_file"] = path.as_posix()
        project.rounds().setdefault(name, {}).setdefault("synced", []).append(
            {"date": date.today().isoformat(), "into": into, "edits": sum(len(d.get("edits", [])) for d in result["docs"]),
             "conflicts": sum(len(d.get("conflicts", [])) for d in result["docs"])})
        project.save()
    say(result | {"to_carry": open_items})
    if check and open_items:
        raise SystemExit(1)


@app.command()
def routes(project_dir: ProjectOption = None,
           connector: Annotated[bool | None, typer.Option(
               "--connector/--no-connector",
               help="Whether a Google Drive connector is among your tools (the agent checks; the script cannot see them)")] = None,
           host: Annotated[str, typer.Option(help="The host the run is in, for the setup note: claude or codex")] = "claude") -> None:
    """Which ways to a round's Google Docs this machine has, what each can do, and, when none can pull the comments,
    one setup note for the authors. Record the note with runs.py issue --kind setup and go on: nothing waits for it."""
    if host not in SETUP:
        raise Refused(f"--host is one of {', '.join(SETUP)}.")
    try:
        block = Project(project_dir).block
    except Refused:
        block = {}  # no settings yet: say what the machine has, for the first-use questions
    remotes = drive_remotes()
    wanted = block.get("remote") if block.get("drive") == "rclone" else None
    rclone_ready = bool(remotes) and (wanted is None or wanted in remotes)
    folder = block.get("folder") if block.get("drive") == "folder" else None
    folder_ready = bool(folder) and Path(str(folder)).expanduser().is_dir()
    can_pull = [*(["rclone"] if rclone_ready else []), *(["connector"] if connector else [])]
    can_push = [*(["rclone"] if rclone_ready else []), *(["folder"] if folder_ready else []),
                *(["connector, by hand"] if connector else [])]
    note = None
    if not can_pull:
        missing = ("rclone is not installed" if remotes is None else
                   f"rclone has no remote {wanted!r}" if wanted and remotes else "rclone has no Google Drive remote")
        unknown = " and no connector was checked" if connector is None else " and no Google Drive connector is connected"
        note = (f"The co-authors' Google Doc comments could not be pulled ({missing}{unknown}); the run went on without "
                f"them. To have them next time, {SETUP[host]}, {RCLONE_SETUP}.")
    say({"rclone": {"installed": remotes is not None, "drive_remotes": remotes or [], "configured": wanted,
                    "ready": rclone_ready},
         "folder": {"configured": folder, "ready": folder_ready},
         "connector": connector, "can_pull": can_pull, "can_push": can_push, "setup_note": note})


# --- port: a round's comments from Google Docs to the run's dashboard ----------------------------------------------

SKILLS = Path(__file__).resolve().parents[2]
RUNS = SCRIPTS / "runs.py"
ATTEMPT = re.compile(r"^(?P<stem>.+?)(?:\.(?P<n>\d+))?(?P<ext>\.[A-Za-z]+)?$")


def next_attempt(path: Path) -> Path:
    """The run's next free attempt of a file or folder: findings.json, findings.2.json, ...; dashboard, dashboard.2."""
    stem, ext = (path.stem, path.suffix) if path.suffix else (path.name, "")
    taken = [1 if child.name == path.name else int(m.group(1)) for child in path.parent.glob(f"{stem}*")
             if child.name == path.name or (m := re.fullmatch(re.escape(stem) + r"\.(\d+)" + re.escape(ext), child.name))]
    return path if not taken else path.with_name(f"{stem}.{max(taken) + 1}{ext}")


def recorded(run: Path, skill: str, script: str) -> list[str] | None:
    """The argv of the run's last finished command of *skill* that ran a script named like *script*."""
    try:
        data = json.loads((run / "run.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Refused(f"{run}: not a run ({exc}).", 2) from exc
    for command in reversed((data.get("skills", {}).get(skill) or {}).get("commands") or []):
        argv = command.get("argv") or []
        if command.get("exit_code", 0) == 0 and any(fnmatch.fnmatch(Path(a).name, script) for a in argv):
            return [str(a) for a in argv]
    return None


def replace_option(argv: list[str], flag: str, value: str | None) -> list[str]:
    """argv with *flag*'s value set (added when missing), or the flag removed when *value* is None."""
    out, skip = [], False
    for n, a in enumerate(argv):
        if skip:
            skip = False
            continue
        if a == flag:
            skip = True
            continue
        out.append(a)
    return out + ([flag, value] if value is not None else [])


def script_args(argv: list[str], script: str) -> list[str]:
    """What follows the script in a recorded `uv run --script SCRIPT ...`."""
    at = next(n for n, a in enumerate(argv) if fnmatch.fnmatch(Path(a).name, script))
    return argv[at + 1:]


def under(run: Path, path: str) -> Path:
    found = Path(path)
    return found if found.is_absolute() else run / found


def port_plan(project: Project, name: str, run: Path, gdocs_: list[Path], pull_: bool) -> list[dict[str, Any]]:
    """The steps of `port`, each a runs.py exec of one command under the skill that owns it."""
    run = run.resolve()
    folder = project.folder(name)
    ledger = folder / "comments.yaml"
    masters = {d.title: d.source for d in releases(project, name)[0] if not d.office}
    data = yaml.safe_load(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {}
    master = (folder / data["master"]) if (data or {}).get("master") else next(iter(masters.values()), None)
    steps: list[dict[str, Any]] = []
    uv = ["uv", "run", "--script"]
    if pull_ and gdocs_:
        for source in gdocs_:
            try:
                title = json.loads(source.read_text(encoding="utf-8")).get("content", {}).get("title", "")
            except (OSError, json.JSONDecodeError, AttributeError) as exc:
                raise Refused(f"{source}: not a saved read_doc answer ({exc}).", 2) from exc
            own = masters.get(title) or master
            steps.append({"step": "pull", "skill": "manuscript-coauthors", "argv": [
                *uv, str(COMMENTS), "import-gdoc", str(source), "--ledger", str(ledger),
                *(["--master", str(own)] if own else []),
                *(["--doc", project.rounds().get(name, {}).get("docs", {}).get(title, "")]
                  if project.rounds().get(name, {}).get("docs", {}).get(title) else [])]})
    elif pull_:
        steps.append({"step": "pull", "skill": "manuscript-coauthors", "argv": [
            *uv, str(Path(__file__).resolve()), "pull", name, "--out",
            str(next_attempt(run / "manuscript-coauthors" / "exports")), "--go", "--project", str(project.path)]})
    def order(r: str) -> list[Any]:
        return [(0, int(x), "") if x.isdigit() else (1, 0, x) for x in r.split(".")]
    later = sorted((r for r in project.rounds() if order(r) > order(name) and project.folder(r).is_dir()), key=order)
    new_master = None
    if later:
        nxt = project.folder(later[0])
        candidate = nxt / master.name if master else None
        new_master = candidate if candidate and candidate.is_file() else None
    findings = next_attempt(run / "manuscript-coauthors" / "findings.json")
    steps.append({"step": "findings", "skill": "manuscript-coauthors", "argv": [
        *uv, str(COMMENTS), "findings", str(ledger), "--new", str(new_master or master), "--out", str(findings),
        "--untriaged", *(["--next-round", later[0]] if new_master else [])]})
    collect = recorded(run, "manuscript-dashboard", "collect*.py")
    if collect is None:
        return steps  # a run without a dashboard yet: the coauthors stage's findings wait for one
    inventory = next_attempt(run / "manuscript-dashboard" / "findings.json")
    args = replace_option(script_args(collect, "collect*.py"), "--output", str(inventory))
    steps.append({"step": "collect", "skill": "manuscript-dashboard",
                  "argv": [*uv, str(SKILLS / "manuscript-dashboard" / "scripts" / "collect.py"), *args]})
    revision = None
    revise = recorded(run, "manuscript-improve", "revise.py")
    if revise:
        args = script_args(revise, "revise.py")
        positional = [n for n, a in enumerate(args) if not a.startswith("-") and (n == 0 or not args[n - 1].startswith("--"))]
        if len(positional) >= 3:
            args[positional[2]] = str(inventory)
        revision = next_attempt(run / "manuscript-improve" / "revision")
        args = replace_option(args, "--output-dir", str(revision))
        steps.append({"step": "corrected version", "skill": "manuscript-improve",
                      "argv": [*uv, str(SKILLS / "manuscript-improve" / "scripts" / "revise.py"), *args]})
    dashboard = next_attempt(run / "manuscript-dashboard" / "dashboard")
    steps.append({"step": "dashboard", "skill": "manuscript-dashboard", "argv": [
        *uv, str(SKILLS / "manuscript-dashboard" / "scripts" / "dashboard.py"), str(inventory), "--output-dir",
        str(dashboard), *(["--revision", str(revision)] if revision else [])]})
    for script, default in (("export_docx.py", "manuscript-review.docx"), ("export_changes.py", "manuscript-changes.xlsx")):
        before = recorded(run, "manuscript-dashboard", script)
        if not before:
            continue
        args = script_args(before, script)
        args = [str(inventory) if n == 0 else a for n, a in enumerate(args)]
        args = replace_option(args, "--revision", str(revision) if revision else None)
        out = next_attempt(run / "manuscript-dashboard" / default)
        args = replace_option(args, "--output", str(out))
        steps.append({"step": script.removesuffix(".py").replace("_", " "), "skill": "manuscript-dashboard",
                      "argv": [*uv, str(SKILLS / "manuscript-dashboard" / "scripts" / script), *args]})
    return steps


@app.command()
def port(name: str, run: Annotated[Path, typer.Option("--run", help="The run whose dashboard shows the round's comments")],
         gdoc: Annotated[list[Path] | None, typer.Option("--gdoc", help="A Doc's read_doc answer (commentsIncluded), saved as JSON; repeat per Doc")] = None,
         no_pull: Annotated[bool, typer.Option("--no-pull", help="Rebuild from the ledger as it is (after triage)")] = False,
         go: Annotated[bool, typer.Option("--go", help="Run the steps; without it, only print them")] = False,
         project_dir: ProjectOption = None) -> None:
    """Take the round's comments from Google Docs to the run's dashboard: pull, people, findings, collect, corrected
    version, dashboard (and the Word and workbook files when the run made them), each a runs.py exec."""
    project = Project(project_dir)
    if not (run / "run.json").is_file():
        raise Refused(f"{run}: no run.json; give the run the round's dashboard belongs to.", 2)
    steps = port_plan(project, name, run, list(gdoc or []), not no_pull)
    commands = [{"step": s["step"], "command": shlex.join([sys.executable, str(RUNS), "exec", str(run), "--skill",
                                                           s["skill"], "--", *s["argv"]])} for s in steps]
    if not go:
        say({"round": name, "dry_run": True, "steps": commands})
        return
    done: list[dict[str, Any]] = []
    for step, command in zip(steps, commands):
        result = subprocess.run(shlex.split(command["command"]), capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            say({"round": name, "done": done, "failed": step["step"], "exit_code": result.returncode,
                 "error": (result.stderr or result.stdout).strip()[-2000:]})
            raise SystemExit(result.returncode if result.returncode in (1, 2) else 3)
        done.append({"step": step["step"], "output": result.stdout.strip()[-1500:]})
    say({"round": name, "done": done,
         "next": "Triage the comments (manuscript-coauthors step 2), then port again with --no-pull."})


def main() -> None:
    try:
        app()  # typer itself exits 2 on a usage error
    except Refused as exc:
        typer.echo(str(exc), err=True)
        raise SystemExit(exc.code) from exc


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 whatever the console's code page (Windows)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    main()
