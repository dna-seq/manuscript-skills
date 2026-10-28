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

EXIT STATUS 0 done · 1 refused (a file exists on Drive; a round folder exists) · 2 usage or settings · 3 could not
run (rclone, git or the build failed or is missing)
"""
from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer

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
    say({"opened": new.as_posix(), "from": old.as_posix(), "base": base, "left_behind": left,
         "project_file": target.as_posix(), "mentions_of_the_old_round": labels[:20],
         "changelog": (new / f"changes-from-{project.pattern.format(round=source)}.md").as_posix()})


@app.command()
def push(name: str, go: Annotated[bool, typer.Option("--go", help="Build and upload; without it, only print")] = False,
         replace: Annotated[bool, typer.Option("--replace", help="Replace files already in the round's Drive folder")] = False,
         project_dir: ProjectOption = None) -> None:
    """Build the round's Docs and upload them, with its files, to the round's Drive folder."""
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
    if drive == "connector":
        plan["by_hand"] = ([f"{d.upload.as_posix()} as the Google {'Sheet' if d.kind == 'xlsx' else 'Doc'} “{d.title}”"
                            for d in docs] + [f"{f.source.as_posix()} as {f.dest}" for f in files])
        plan["note"] = "Upload these through the Drive connector or the Drive web page; then record the Doc links."
    if drive == "folder":
        plan["note"] = ("Drive for desktop uploads a .docx as a Word file unless its 'Convert uploads' setting is on; "
                        "open each in Google Docs (File > Save as Google Docs) before the co-authors comment.")
    if not go:
        say(plan | {"dry_run": True})
        return
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
        export = out / f"{title}.docx"
        ledger = folder / "comments.yaml"
        steps.append({"doc": title, "link": link, "export": export.as_posix(), "master": master and master.as_posix(),
                      "commands": [["rclone", "backend", "copyid", f"{project.block.get('remote', 'gdrive')}:", file_id,
                                    f"{out.as_posix()}/", "--drive-export-formats", "docx"],
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
        before = set(out.glob("*.docx"))
        execute([step["commands"][0]], folder)
        exported = sorted(set(out.glob("*.docx")) - before) or sorted(out.glob("*.docx"), key=os.path.getmtime)[-1:]
        if not exported:
            raise Refused(f"rclone exported nothing for {step['doc']}.", 3)
        command = [c if c != "EXPORTED.docx" else str(exported[0]) for c in step["commands"][1]]
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        if done.returncode != 0:
            raise Refused(f"Import of {step['doc']} failed: {done.stderr.strip()}", 3)
        results.append({"doc": step["doc"], "export": exported[0].as_posix(), **json.loads(done.stdout)})
    say({"round": name, "pulled": results})


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
