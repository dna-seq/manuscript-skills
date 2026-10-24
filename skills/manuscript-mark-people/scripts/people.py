# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Find the people in a manuscript repository, for rev-marks.toml's `humans` list
(manuscript-revision-marks). It proposes; the authors confirm; only then does it write.

    uv run --script people.py [PATH] [--config TOML]          # candidates, their evidence, the one question
    uv run --script people.py [PATH] --write --confirm anna,tom [--force-name]

PATH is the manuscript, or any folder in its repository (default: the current folder). The config is the
rev-marks.toml revision marks reads for it: the nearest one from PATH up to the repository root, as
rev_marks.py finds it, or the one --config names; a new one goes to the repository root (outside git,
into PATH's folder). Where it looks:

- git history: every author and committer (name and email), and Co-authored-by trailers. Outside a git
  repository, or without git, the history is not read, and the survey says so;
- the names already in revision marks' `by=` lists, in every tracked .md, .markdown and .tex file (outside
  git, every such file under the folder);
- author lists: LaTeX `\\author{...}`, Markdown front matter `author:` / `authors:`, CITATION.cff,
  AUTHORS and CODEOWNERS.

Each identity is classified:

- agent: its email is an AI vendor's or a bot's address (`*-bot@`, `*[bot]@`, `bot@`, the vendors'
  no-reply addresses), its name or login ends in [bot], its GitHub login is on the agent list
  (references/agent-names.toml in manuscript-revision-marks, plus the project's own `agents`), or, with
  no other evidence of a person, its full name or email local part is;
- person: a git author or committer, or a listed author, whose address is not an AI vendor's or a bot's,
  even when a word of the name (Devin, Yi, Luna) or the address is also an agent's name: those are listed
  apart, so the authors see them; and any other identity that is not an agent;
- unclear: a `by=` handle that no person's identity explains, and that is not an agent.

A `by=` handle is linked to a person when it equals their first name, their email's local part (or its
first dot-separated part), or their GitHub login, lowercased. Pre-selected are the handles of people
whose evidence converges: they sign `by=` entries, commit in git and are listed authors, and the handle
is not also an agent's name. Everyone else is to confirm, in the same one question. Nothing here decides
who is a person: a name is written only with --write and listed in --confirm, and it is merged into the
rev-marks.toml without dropping anything already there. Until then, a name not in `humans` counts as an
agent, so no passage reads as reviewed by mistake.

Nothing leaves the machine. EXIT STATUS 0 done · 2 usage (a --confirm name the run did not find needs
--force-name), a malformed rev-marks.toml · 3 could not run (PATH unreadable)
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REV_MARKS = Path(__file__).resolve().parents[2] / "manuscript-revision-marks" / "scripts" / "rev_marks.py"
MARKED_SUFFIXES = (".md", ".markdown", ".tex")
# No-reply and bot addresses: a commit or trailer from one of these is an agent's, whatever its name.
# `*bot@*` would take talbot@ and abbot@: a bot's address has the word on its own.
AGENT_EMAILS = ("noreply@anthropic.com", "*@anthropic.com", "noreply@openai.com", "*@openai.com",
                "*[[]bot]@*", "*-bot@*", "bot@*", "cursoragent@cursor.com",
                "*@cursor.com", "noreply@google.com", "*@x.ai", "devin-ai-integration*", "noreply@github.com")
GITHUB_NOREPLY = re.compile(r"^(?:\d+\+)?(?P<login>[^@]+)@users\.noreply\.github\.com$", re.IGNORECASE)
TRAILER = re.compile(r"^\s*(?P<name>.*?)\s*<(?P<email>[^>]*)>\s*$")
SEP, REC = "\x1f", "\x1e"
# Folders whose files are test data or examples, not the project's own manuscripts.
SKIPPED_DIRS = {"fixtures", "fixture", "tests", "test", "examples", "example", "vendor", "node_modules", "third_party"}
# Outside git: folders never walked, and how many files the walk reads at most.
UNWALKED_DIRS = SKIPPED_DIRS | {"__pycache__", "venv", "site-packages", "build", "dist"}
MAX_WALKED = 20000
AUTHOR_FILES = ("CITATION.cff", "AUTHORS", "AUTHORS.md", "AUTHORS.txt", "CONTRIBUTORS", "CONTRIBUTORS.md", "CODEOWNERS")
PLACEHOLDER_NAMES = {"anonymous", "anonymous author", "anonymous authors", "anonymised", "anonymized", "author",
                     "authors", "first author", "your name", "name surname", "jane doe", "john doe"}


def load_rev_marks():
    spec = importlib.util.spec_from_file_location("rev_marks", REV_MARKS)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rev_marks"] = module
    spec.loader.exec_module(module)
    return module


rm = load_rev_marks()


@dataclass
class Identity:
    """One person or agent, as the repository shows them."""

    name: str
    email: str = ""
    kind: str = "unclear"  # person, agent, unclear
    evidence: list[str] = field(default_factory=list)
    handles: set[str] = field(default_factory=set)  # by= handles linked to this identity
    also: list[str] = field(default_factory=list)  # more emails of the same full name
    committed: bool = False  # a git author or committer
    listed: bool = False  # in a manuscript's author list (\author, front matter, CITATION.cff, AUTHORS)
    why: str = ""  # for an agent: what makes it one
    agent_words: list[str] = field(default_factory=list)  # for a person: words of the name that are agents' names
    ambiguous: set[str] = field(default_factory=set)  # linked handles that are also agents' names

    @property
    def key(self) -> str:
        return self.email.lower() or f"name:{self.name.lower()}"

    def likely_handles(self) -> list[str]:
        """Handles this identity might sign a by= entry with, most likely first."""
        out: list[str] = []
        first = self.name.split()[0] if self.name.split() else ""
        login = GITHUB_NOREPLY.match(self.email)
        local = self.email.split("@")[0].split("+")[-1] if "@" in self.email else ""
        for candidate in (first, login.group("login") if login else "", local, local.split(".")[0]):
            handle = re.sub(r"[^A-Za-z0-9_.-]", "", candidate).lower()
            if handle and re.match(r"[a-z]", handle) and handle not in out:
                out.append(handle)
        return out


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def agent_email(email: str) -> bool:
    return bool(email) and any(fnmatch.fnmatchcase(email.lower(), p) for p in AGENT_EMAILS)


def agent_reason(people, name: str, email: str = "", person: bool = False) -> str | None:
    """Why this identity is an agent, or None. *person*: it commits in git or is a listed author, so a full
    name or address that is also an agent's name (a co-author called Luna, yi@uni.edu) does not make it one.
    Only the full name, the email's local part and the GitHub login are matched, never one word of a name."""
    if agent_email(email):
        return "an AI vendor's or a bot's address"
    noreply = GITHUB_NOREPLY.match(email)
    login = noreply.group("login").lower() if noreply else ""
    if name.strip().lower().endswith("[bot]") or login.endswith("[bot]"):
        return "a bot account"
    if login and people.known(login) == rm.Kind.AGENT:
        return f"its GitHub login, {login}, is an agent's"
    if person:
        return None
    full = " ".join(name.lower().split())
    local = email.split("@")[0].lower() if "@" in email and not login else ""
    for token, what in ((full, "its name"), (local, "its address")):
        if token and people.known(token) == rm.Kind.AGENT:
            return f"{what}, {token}, is an agent's"
    return None


def is_agent(people, name: str, email: str = "", person: bool = False) -> bool:
    return agent_reason(people, name, email, person) is not None


def agent_words(people, ident: Identity) -> list[str]:
    """The words of a person's name, address or login that are also agents' names, for the authors to see."""
    noreply = GITHUB_NOREPLY.match(ident.email)
    local = ident.email.split("@")[0].lower() if "@" in ident.email else ""
    words = {" ".join(ident.name.lower().split()), *re.split(r"[\s(),]+", ident.name.lower()), local,
             *re.split(r"[._+-]", local), noreply.group("login").lower() if noreply else ""}
    return sorted(w for w in words if w and people.known(w) == rm.Kind.AGENT)


def from_git(root: Path) -> list[Identity]:
    out = git(root, "log", "--all", f"--format=%an{SEP}%ae{SEP}%cn{SEP}%ce{SEP}"
              f"%(trailers:key=Co-authored-by,valueonly,separator=%x1d){REC}")
    found: list[Identity] = []
    for record in out.split(REC):
        parts = record.strip("\n").split(SEP)
        if len(parts) != 5:
            continue
        an, ae, cn, ce, trailers = parts
        found.append(Identity(an, ae, evidence=["git author"], committed=True))
        found.append(Identity(cn, ce, evidence=["git committer"], committed=True))
        for trailer in filter(None, trailers.split("\x1d")):
            m = TRAILER.match(trailer)
            if m:
                found.append(Identity(m.group("name"), m.group("email"), evidence=["Co-authored-by trailer"]))
    return found


def tracked(root: Path) -> list[Path]:
    """Tracked files, minus test data and examples."""
    return [root / line for line in git(root, "ls-files", "-z").split("\0")
            if line and not SKIPPED_DIRS & {part.lower() for part in Path(line).parts[:-1]}]


def walked(root: Path) -> tuple[list[Path], bool]:
    """Outside git: the manuscripts and author lists under *root*, minus test data, examples and hidden
    folders; and whether the walk stopped early."""
    out: list[Path] = []
    seen = 0
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d.lower() not in UNWALKED_DIRS)
        for name in sorted(names):
            seen += 1
            if seen > MAX_WALKED:
                return out, True
            if Path(name).suffix.lower() in MARKED_SUFFIXES or name in AUTHOR_FILES:
                out.append(Path(folder) / name)
    return out, False


def by_handles(files: list[Path]) -> dict[str, list[str]]:
    """Every by= name in the revision marks of *files*, with where it appears."""
    seen: dict[str, list[str]] = {}
    for path in files:
        if path.suffix.lower() not in MARKED_SUFFIXES or not path.is_file():
            continue
        try:
            found = rm.parse(rm.read_source(path), rm.syntax_for(path))
        except (OSError, UnicodeDecodeError):
            continue
        for m in found.marks:
            for entry in m.attributes.by if m.attributes else ():
                where = f"{path.name}:{m.line}"
                if where not in seen.setdefault(entry.name, []):
                    seen[entry.name].append(where)
    return seen


LATEX_AUTHOR = re.compile(r"\\author\s*(?:\[[^\]]*\])?\s*\{((?:[^{}]|\{[^{}]*\})*)\}", re.DOTALL)
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def author_lists(root: Path, files: list[Path]) -> list[Identity]:
    found: list[Identity] = []
    for path in files:
        suffix, name = path.suffix.lower(), path.name
        try:
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(root).as_posix()
        if suffix == ".tex":
            for block in LATEX_AUTHOR.findall(text):
                plain = re.sub(r"\\(?:thanks|footnote|textsuperscript|inst)\{[^{}]*\}|\$[^$]*\$", "", block)
                for person in re.split(r"\\and|\\\\|,|\band\b", plain):
                    person = " ".join(re.sub(r"[\\{}]", " ", person).split())
                    if person and re.search(r"[A-Za-z]", person):
                        found.append(Identity(person, evidence=[f"\\author in {rel}"], listed=True))
        elif suffix in (".md", ".markdown"):
            fm = FRONT_MATTER.match(text)
            if fm:
                found += [Identity(n, evidence=[f"front matter of {rel}"], listed=True)
                          for n in front_matter_authors(fm.group(1))]
        elif name == "CITATION.cff":
            for given, family in re.findall(r"given-names:\s*\"?([^\"\n]+)\"?\s*\n\s*family-names:\s*\"?([^\"\n]+)",
                                            text):
                found.append(Identity(f"{given.strip()} {family.strip()}", evidence=[f"{rel}"], listed=True))
            for family, given in re.findall(r"family-names:\s*\"?([^\"\n]+)\"?\s*\n\s*given-names:\s*\"?([^\"\n]+)",
                                            text):
                found.append(Identity(f"{given.strip()} {family.strip()}", evidence=[f"{rel}"], listed=True))
        elif name in ("AUTHORS", "AUTHORS.md", "AUTHORS.txt", "CONTRIBUTORS", "CONTRIBUTORS.md"):
            for line in text.splitlines():
                m = re.match(r"^\s*[-*]?\s*([^<#(\n]+?)\s*(?:<([^>]+)>)?\s*$", line)
                if m and re.search(r"[A-Za-z]", m.group(1)) and not line.lstrip().startswith("#"):
                    found.append(Identity(m.group(1), m.group(2) or "", evidence=[f"{rel}"], listed=True))
        elif name == "CODEOWNERS":
            for login in sorted(set(re.findall(r"(?<![\w/])@([A-Za-z0-9-]+)(?![/\w])", text))):
                found.append(Identity(login, f"{login}@users.noreply.github.com", evidence=[f"{rel}"]))
    return found


def front_matter_authors(block: str) -> list[str]:
    names: list[str] = []
    lines = block.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(author|authors)\s*:\s*(.*)$", line)
        if not m:
            continue
        inline = m.group(2).strip()
        if inline.startswith("["):
            names += [n.strip(" \"'") for n in inline.strip("[]").split(",")]
        elif inline:
            names.append(inline.strip("\"'"))
        for item in lines[i + 1:]:
            sub = re.match(r"^\s*-\s*(?:name\s*:\s*)?(.+)$", item)
            if not sub:
                break
            names.append(sub.group(1).strip(" \"'"))
    return [n for n in names if n and re.search(r"[A-Za-z]", n)]


def merge(identities: list[Identity]) -> list[Identity]:
    """One identity per email, and one per full name across emails, evidence and emails pooled."""
    by_key: dict[str, Identity] = {}
    names: dict[str, str] = {}
    for ident in identities:
        if ident.name.strip().lower() in PLACEHOLDER_NAMES:
            continue
        name_key = " ".join(ident.name.lower().split())
        key = names.get(name_key) if " " in name_key else None  # a full name, not a bare login
        key = key or (ident.key if ident.email else names.get(name_key, ident.key))
        if ident.email and ident.key in by_key:
            key = ident.key
        if key in by_key:
            existing = by_key[key]
            existing.evidence += [e for e in ident.evidence if e not in existing.evidence]
            absorb(existing, ident)
        else:
            by_key[key] = ident
        names.setdefault(name_key, key)
    merged = list(by_key.values())
    # A GitHub no-reply address names a login; it is the person who commits under that login elsewhere.
    for ident in list(merged):
        login = GITHUB_NOREPLY.match(ident.email)
        owner = next((o for o in merged if o is not ident and login and login.group("login").lower() in
                      {o.name.lower(), o.email.split("@")[0].lower()}), None)
        if owner is not None:
            absorb(owner, ident)
            if ident.name.lower() != owner.name.lower():
                owner.evidence.append(f"also named {ident.name}")
            merged.remove(ident)
    return merged


def absorb(into: Identity, other: Identity) -> None:
    into.evidence += [e for e in other.evidence if e not in into.evidence]
    into.committed = into.committed or other.committed
    into.listed = into.listed or other.listed
    emails = {e.lower() for e in [into.email, *into.also] if e}
    if other.email and other.email.lower() not in emails:
        if into.email:
            into.also.append(other.email)
        else:
            into.email = other.email


@dataclass
class Survey:
    root: Path
    identities: list[Identity]
    handles: dict[str, list[str]]  # by= handle -> where
    unclear: list[str]  # by= handles linked to nobody and not agents
    agent_handles: list[str]
    config: Path | None  # the rev-marks.toml in use, if any
    target: Path = Path(rm.CONFIG_NAME)  # where --write merges the confirmed names
    history: str = ""  # why git history was not read; empty when it was
    note: str = ""  # anything else the survey could not do
    start: Path | None = None  # the PATH the survey was given

    def people(self) -> list[Identity]:
        return [i for i in self.identities if i.kind == "person"]

    def proposal(self) -> list[str]:
        """Every person's handle: the ones they sign with, else the one they most likely would."""
        out: list[str] = []
        for ident in self.people():
            picks = sorted(ident.handles) or ident.likely_handles()[:1]
            out += [h for h in picks if h not in out]
        return out

    def preselected(self) -> list[str]:
        """The handles whose evidence converges: signed by= entries, a git author or committer, a listed
        author, and not also an agent's name."""
        out: list[str] = []
        for ident in self.people():
            if ident.committed and ident.listed:
                out += [h for h in sorted(ident.handles - ident.ambiguous) if h not in out]
        return out


def survey(path: Path, config: Path | None = None) -> Survey:
    """Who is a person, for the manuscript or folder at *path*; *config* overrides the rev-marks.toml lookup."""
    path = path.resolve()
    folder = path if path.is_dir() else path.parent
    root, history = folder, ""
    if shutil.which("git") is None:
        history = "git is not installed"
    else:
        try:
            root = Path(git(folder, "rev-parse", "--show-toplevel").strip()).resolve()
        except RuntimeError:
            history = "not a git repository"
    if config is not None and not config.is_file():
        people = rm.People(agents=rm.agent_list())  # a new file, written on --write
        found_config = None
    else:
        people = rm.load_people(path, config)
        found_config = people.config
    note = ""
    identities: list[Identity] = []
    if history:
        files, stopped = walked(root)
        if stopped:
            note = f"the walk stopped after {MAX_WALKED} files; name the manuscript's own folder to read all of it"
    else:
        files = tracked(root)
        try:
            identities = from_git(root)
        except RuntimeError as exc:  # a repository with no commits yet
            history = f"git log could not be read ({exc.args[0].splitlines()[0] if exc.args[0] else 'no commits'})"
    if path.is_file() and path.suffix.lower() in MARKED_SUFFIXES and path not in files:
        files.append(path)  # the manuscript itself, tracked or not
    identities = merge(identities + author_lists(root, files))
    for ident in identities:
        why = agent_reason(people, ident.name, ident.email, ident.committed or ident.listed)
        ident.kind, ident.why = ("agent", why) if why else ("person", "")
        if ident.kind == "person":
            ident.agent_words = agent_words(people, ident)
    handles = by_handles(files)
    unclear, agent_handles = [], []
    for handle in handles:
        known = people.known(handle)
        if known == rm.Kind.HUMAN:
            continue  # already listed
        owners = [i for i in identities if i.kind == "person" and handle.lower() in i.likely_handles()]
        for owner in owners:
            owner.handles.add(handle.lower())
            if known == rm.Kind.AGENT:
                owner.ambiguous.add(handle.lower())
        if known == rm.Kind.AGENT and not owners:
            agent_handles.append(handle)
        elif not owners:
            unclear.append(handle)
    target = config or found_config or root / rm.CONFIG_NAME
    return Survey(root, identities, handles, unclear, agent_handles, found_config, target, history, note, path)


def where(s: Survey, handle: str) -> str:
    places = s.handles.get(handle, [])
    return ", ".join(places[:3]) + (" …" if len(places) > 3 else "")


def describe(i: Identity, kind: str) -> str:
    email = "".join(f" <{e}>" for e in [i.email, *i.also] if e)
    line = f"  {i.name}{email}  [{'; '.join(i.evidence)}]"
    if kind == "agent":
        return f"{line}  {i.why}"
    if i.handles:
        line += f"  signs as {', '.join(sorted(i.handles))}"
    elif i.likely_handles():
        line += f"  would sign as {i.likely_handles()[0]}?"
    if i.agent_words:
        line += f"  ({', '.join(i.agent_words)}: also an agent's name)"
    if i.ambiguous:
        line += (f"; listing {', '.join(sorted(i.ambiguous))} as a person makes every by= round signed so a person's,"
                 " an AI's included")
    return line


def report(s: Survey) -> str:
    config = s.config or f"none yet; --write creates {s.target}"
    lines = [f"People in {s.root} (rev-marks.toml: {config})",
             "Git history: " + (f"not read: {s.history}; the by= handles and author lists were" if s.history
                                else "read") + (f". Note: {s.note}" if s.note else ""), ""]
    people = s.people()
    plain = [i for i in people if not i.agent_words and not i.ambiguous]
    named = [i for i in people if i.agent_words or i.ambiguous]
    agents = [i for i in s.identities if i.kind == "agent"]
    for title, group, kind in (("PEOPLE", plain, "person"),
                               ("PEOPLE WHOSE NAME MATCHES AN AGENT NAME (kept as people; show them to the authors)",
                                named, "person"),
                               ("AGENTS (not proposed)", agents, "agent")):
        lines.append(f"{title}: {len(group)}")
        lines += [describe(i, kind) for i in sorted(group, key=lambda i: i.name.lower())]
        lines.append("")
    if s.agent_handles:
        lines += [f"by= HANDLES ON THE AGENT LIST: {', '.join(sorted(s.agent_handles))}", ""]
    lines.append(f"by= HANDLES NOBODY EXPLAINS (counted as agents until listed): {len(s.unclear)}")
    lines += [f"  {h}  ({where(s, h)})" for h in s.unclear]
    pre = s.preselected()
    asked: list[str] = []
    for ident in people:
        evidence = "; ".join(ident.evidence)
        picks = sorted(ident.handles) or ident.likely_handles()[:1]
        for h in picks:
            if h in pre or any(h == a.split(" ")[0] for a in asked):
                continue
            how = f"signs marks as {h}" if h in ident.handles else "has signed no mark yet, so the handle is a guess"
            flag = f"; {h} is also an agent's name" if h in ident.ambiguous or h in ident.agent_words else ""
            asked.append(f"{h} ({ident.name} {how}; {evidence}{flag})")
    asked += [f"{h} (unexplained by= handle: {where(s, h)})" for h in s.unclear]
    lines += ["", "ONE QUESTION FOR THE AUTHORS, among the end-of-run decisions. Nothing waits on it: until it is",
              "answered, every name not in humans counts as an agent, so no passage reads as reviewed by mistake.",
              f"  Pre-selected (signs revision marks, commits in git and is a listed author): {', '.join(pre) or 'none'}",
              f"  Also people? {'; '.join(asked) or 'nobody else'}",
              f"  Write only what they confirm: people.py {s.start or s.root} --write --confirm "
              f"{','.join(pre) or 'NAME,...'}  (into {s.target})"]
    return "\n".join(lines) + "\n"


def format_list(names: list[str]) -> str:
    return "[" + ", ".join(f'"{n}"' for n in names) + "]"


HUMANS_RE = re.compile(r"^humans\s*=\s*\[.*?\]", re.DOTALL | re.MULTILINE)


def write_humans(config: Path, names: list[str]) -> list[str]:
    """Merge *names* into the config's humans, keeping every other line; the humans now listed."""
    text = config.read_text(encoding="utf-8") if config.is_file() else ""
    try:
        current = tomllib.loads(text).get("humans", []) if text else []
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{config}: not TOML: {exc}") from None
    merged = list(dict.fromkeys([*current, *names]))
    line = f"humans = {format_list(merged)}"
    if HUMANS_RE.search(text):
        text = HUMANS_RE.sub(lambda _: line, text, count=1)
    else:
        header = "" if text else "# Who is a person in this project's revision marks (manuscript-revision-marks).\n"
        text = header + line + "\n" + text
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(text, encoding="utf-8")
    tomllib.loads(text)  # the merge left a file that still parses
    return merged


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="people.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("root", nargs="?", type=Path, default=Path.cwd(), metavar="PATH",
                    help="the manuscript, or a folder in its repository (default: the current folder)")
    ap.add_argument("--config", type=Path, help=f"the {rm.CONFIG_NAME} to read and write (default: the nearest one"
                                                " from PATH up to the repository root, as rev_marks.py finds it)")
    ap.add_argument("--write", action="store_true", help="merge the --confirm names into rev-marks.toml")
    ap.add_argument("--confirm", default="", help="the handles the authors confirmed as people, comma-separated")
    ap.add_argument("--force-name", action="store_true", help="accept a --confirm name this run did not find")
    args = ap.parse_args(argv)
    if not args.root.exists():
        print(f"people.py: not run: {args.root} does not exist", file=sys.stderr)
        return 3
    try:
        s = survey(args.root, args.config)
    except rm.ConfigError as exc:
        print(f"people.py: {exc}", file=sys.stderr)
        return 2
    except (RuntimeError, OSError) as exc:
        print(f"people.py: not run: {exc}", file=sys.stderr)
        return 3
    if not args.write:
        sys.stdout.write(report(s))
        return 0
    names = [n.strip().lower() for n in args.confirm.split(",") if n.strip()]
    if not names:
        print("people.py: --write needs --confirm with the names the authors confirmed", file=sys.stderr)
        return 2
    known = {h.lower() for h in s.handles} | {h for i in s.identities for h in i.likely_handles()}
    strange = [n for n in names if n not in known]
    if strange and not args.force_name:
        print(f"people.py: not found in this repository: {', '.join(strange)}; check the spelling, or pass"
              " --force-name to list them anyway", file=sys.stderr)
        return 2
    bad = [n for n in names if not re.fullmatch(rm.NAME_PATTERN, n)]
    if bad:
        print(f"people.py: not a by= name ({rm.NAME_PATTERN}): {', '.join(bad)}", file=sys.stderr)
        return 2
    try:
        merged = write_humans(s.target, names)
    except ValueError as exc:
        print(f"people.py: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"people.py: not run: {exc}", file=sys.stderr)
        return 3
    print(f"wrote {s.target}: humans = {format_list(merged)}")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
