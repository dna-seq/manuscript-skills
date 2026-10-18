# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Find the people in a manuscript repository, for rev-marks.toml's `humans` list
(manuscript-revision-marks). It proposes; the authors confirm; only then does it write.

    uv run --script people.py [ROOT]                       # candidates with their evidence, and a proposal
    uv run --script people.py [ROOT] --write --confirm anna,tom

ROOT is any folder in the repository (default: the current one); the repository's root is where
rev-marks.toml lives. Where it looks:

- git history: every author and committer (name and email), and Co-authored-by trailers;
- the names already in revision marks' `by=` lists, in every tracked .md, .markdown and .tex file;
- author lists: LaTeX `\\author{...}`, Markdown front matter `author:` / `authors:`, CITATION.cff,
  AUTHORS and CODEOWNERS.

Each identity is classified:

- agent: its name, email local part or handle matches the agent list (references/agent-names.toml in
  manuscript-revision-marks, plus the project's own `agents`), or its email is a bot or AI vendor's
  no-reply address;
- person: a git author or committer, or a listed manuscript author, that is not an agent;
- unclear: a `by=` handle that no person's identity explains, and that is not an agent.

A `by=` handle is linked to a person when it equals their first name, their email's local part (or
its first dot-separated part), or their GitHub login, lowercased. The proposal lists the linked
handles, and for a person with no handle yet the one they would most likely sign with. Nothing here
decides who is a person: a name is written only with --write and listed in --confirm, and it is
merged into an existing rev-marks.toml without dropping anything already there.

Nothing leaves the machine. EXIT STATUS 0 done · 2 usage (a --confirm name the run did not find
needs --force-name) · 3 could not run (not a git repository, git absent, a malformed rev-marks.toml)
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib.util
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
AGENT_EMAILS = ("noreply@anthropic.com", "*@anthropic.com", "noreply@openai.com", "*@openai.com",
                "*[[]bot]@users.noreply.github.com", "*-bot@*", "*bot@*", "cursoragent@cursor.com",
                "*@cursor.com", "noreply@google.com", "*@x.ai", "devin-ai-integration*", "noreply@github.com")
GITHUB_NOREPLY = re.compile(r"^(?:\d+\+)?(?P<login>[^@]+)@users\.noreply\.github\.com$", re.IGNORECASE)
TRAILER = re.compile(r"^\s*(?P<name>.*?)\s*<(?P<email>[^>]*)>\s*$")
SEP, REC = "\x1f", "\x1e"
# Folders whose files are test data or examples, not the project's own manuscripts.
SKIPPED_DIRS = {"fixtures", "fixture", "tests", "test", "examples", "example", "vendor", "node_modules", "third_party"}
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
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def is_agent(people, name: str, email: str = "") -> bool:
    words = [w for w in re.split(r"[\s(),]+", name.lower()) if w]
    tokens = {name.lower(), "-".join(words), *words[:1]}
    login = GITHUB_NOREPLY.match(email)
    if email:
        tokens.add(email.split("@")[0].lower())
        if login:
            tokens.add(login.group("login").lower())
    if email and any(fnmatch.fnmatchcase(email.lower(), p) for p in AGENT_EMAILS):
        return True
    return any(people.known(t) == rm.Kind.AGENT for t in tokens if t)


def from_git(root: Path) -> list[Identity]:
    out = git(root, "log", "--all", f"--format=%an{SEP}%ae{SEP}%cn{SEP}%ce{SEP}"
              f"%(trailers:key=Co-authored-by,valueonly,separator=%x1d){REC}")
    found: list[Identity] = []
    for record in out.split(REC):
        parts = record.strip("\n").split(SEP)
        if len(parts) != 5:
            continue
        an, ae, cn, ce, trailers = parts
        found.append(Identity(an, ae, evidence=["git author"]))
        found.append(Identity(cn, ce, evidence=["git committer"]))
        for trailer in filter(None, trailers.split("\x1d")):
            m = TRAILER.match(trailer)
            if m:
                found.append(Identity(m.group("name"), m.group("email"), evidence=["Co-authored-by trailer"]))
    return found


def tracked(root: Path) -> list[Path]:
    """Tracked files, minus test data and examples."""
    return [root / line for line in git(root, "ls-files", "-z").split("\0")
            if line and not SKIPPED_DIRS & {part.lower() for part in Path(line).parts[:-1]}]


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
        rel = str(path.relative_to(root))
        if suffix == ".tex":
            for block in LATEX_AUTHOR.findall(text):
                plain = re.sub(r"\\(?:thanks|footnote|textsuperscript|inst)\{[^{}]*\}|\$[^$]*\$", "", block)
                for person in re.split(r"\\and|\\\\|,|\band\b", plain):
                    person = " ".join(re.sub(r"[\\{}]", " ", person).split())
                    if person and re.search(r"[A-Za-z]", person):
                        found.append(Identity(person, evidence=[f"\\author in {rel}"]))
        elif suffix in (".md", ".markdown"):
            fm = FRONT_MATTER.match(text)
            if fm:
                found += [Identity(n, evidence=[f"front matter of {rel}"]) for n in front_matter_authors(fm.group(1))]
        elif name == "CITATION.cff":
            for given, family in re.findall(r"given-names:\s*\"?([^\"\n]+)\"?\s*\n\s*family-names:\s*\"?([^\"\n]+)",
                                            text):
                found.append(Identity(f"{given.strip()} {family.strip()}", evidence=[f"{rel}"]))
            for family, given in re.findall(r"family-names:\s*\"?([^\"\n]+)\"?\s*\n\s*given-names:\s*\"?([^\"\n]+)",
                                            text):
                found.append(Identity(f"{given.strip()} {family.strip()}", evidence=[f"{rel}"]))
        elif name in ("AUTHORS", "AUTHORS.md", "AUTHORS.txt", "CONTRIBUTORS", "CONTRIBUTORS.md"):
            for line in text.splitlines():
                m = re.match(r"^\s*[-*]?\s*([^<#(\n]+?)\s*(?:<([^>]+)>)?\s*$", line)
                if m and re.search(r"[A-Za-z]", m.group(1)) and not line.lstrip().startswith("#"):
                    found.append(Identity(m.group(1), m.group(2) or "", evidence=[f"{rel}"]))
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
    config: Path | None

    def proposal(self) -> list[str]:
        out: list[str] = []
        for ident in self.identities:
            if ident.kind != "person":
                continue
            picks = sorted(ident.handles) or ident.likely_handles()[:1]
            out += [h for h in picks if h not in out]
        return out


def survey(root: Path) -> Survey:
    people = rm.load_people(root / "x")
    files = tracked(root)
    identities = merge(from_git(root) + author_lists(root, files))
    for ident in identities:
        ident.kind = "agent" if is_agent(people, ident.name, ident.email) else "person"
    handles = by_handles(files)
    unclear, agent_handles = [], []
    for handle in handles:
        if people.known(handle) == rm.Kind.HUMAN:
            continue  # already listed
        if people.known(handle) == rm.Kind.AGENT:
            agent_handles.append(handle)
            continue
        owners = [i for i in identities if i.kind == "person" and handle.lower() in i.likely_handles()]
        for owner in owners:
            owner.handles.add(handle.lower())
        if not owners:
            unclear.append(handle)
    return Survey(root, identities, handles, unclear, agent_handles, people.config)


def report(s: Survey) -> str:
    lines = [f"People in {s.root} (rev-marks.toml: {s.config or 'none yet'})", ""]
    for kind, title in (("person", "PEOPLE (proposed for humans)"), ("agent", "AGENTS (not proposed)")):
        group = [i for i in s.identities if i.kind == kind]
        lines.append(f"{title}: {len(group)}")
        for i in sorted(group, key=lambda i: i.name.lower()):
            signs = f"  signs as {', '.join(sorted(i.handles))}" if i.handles else \
                f"  would sign as {i.likely_handles()[0]}?" if kind == "person" and i.likely_handles() else ""
            email = "".join(f" <{e}>" for e in [i.email, *i.also] if e)
            lines.append(f"  {i.name}{email}  [{'; '.join(i.evidence)}]{signs}")
        lines.append("")
    if s.agent_handles:
        lines += [f"by= HANDLES ON THE AGENT LIST: {', '.join(sorted(s.agent_handles))}", ""]
    lines.append(f"by= HANDLES NOBODY EXPLAINS (unclear; counted as agents until listed): {len(s.unclear)}")
    lines += [f"  {h}  ({', '.join(s.handles[h][:3])}{' …' if len(s.handles[h]) > 3 else ''})" for h in s.unclear]
    proposal = s.proposal()
    lines += ["", "PROPOSED rev-marks.toml humans (confirm each with the authors before writing):",
              f"  humans = {format_list(proposal)}",
              f"  then: people.py --write --confirm {','.join(proposal) or 'NAME,...'}"]
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
    config.write_text(text, encoding="utf-8")
    tomllib.loads(text)  # the merge left a file that still parses
    return merged


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="people.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("root", nargs="?", type=Path, default=Path.cwd())
    ap.add_argument("--write", action="store_true", help="merge the --confirm names into rev-marks.toml")
    ap.add_argument("--confirm", default="", help="the handles the authors confirmed as people, comma-separated")
    ap.add_argument("--force-name", action="store_true", help="accept a --confirm name this run did not find")
    args = ap.parse_args(argv)
    if shutil.which("git") is None:
        print("people.py: not run: git is not on PATH", file=sys.stderr)
        return 3
    try:
        root = Path(git(args.root, "rev-parse", "--show-toplevel").strip())
        s = survey(root)
    except (RuntimeError, OSError) as exc:
        print(f"people.py: not run: {exc}", file=sys.stderr)
        return 3
    except rm.ConfigError as exc:
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
    config = s.config or root / rm.CONFIG_NAME
    try:
        merged = write_humans(config, names)
    except ValueError as exc:
        print(f"people.py: not run: {exc}", file=sys.stderr)
        return 3
    print(f"wrote {config}: humans = {format_list(merged)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
