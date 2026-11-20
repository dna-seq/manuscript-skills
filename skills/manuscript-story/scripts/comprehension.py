# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12"]
# ///
"""Can a scientist from outside the field follow the paper, sentence by sentence?

Co-authors from outside a paper's sub-field stop where its own readers read past: a term used before the paper
defines it, a sentence they cannot parse, a number given without its reason (Paper 1 v0.7: 27 such comments from one
co-author, three on passages the run itself wrote, none caught). The story panel reads for the story, the prose
stage reads only what it edits and the re-check asks whether an edit is accurate, not whether it reads. This script
gives that reading its material and holds it to its contract:

    uv run --script comprehension.py scan PAPER.md [--json scan.json] [--md scan.md] [--known GWAS] \\
        [--before ORIGINAL.md] [--check]
    uv run --script comprehension.py passages ORIGINAL.md CORRECTED.md [--json passages.json]
    uv run --script comprehension.py prepare PAPER.md --into RUN/manuscript-story/comprehension \\
        [--section 2 --section 3 --section 4] [--original ORIGINAL.md] [--passages-only]
    uv run --script comprehension.py check RUN/manuscript-story/comprehension/answer.json \\
        --out RUN/manuscript-story/comprehension.json [--prefix ST] [--start 1]

`scan` is a list-only parse pass over the whole body: abbreviations used before they are spelled out or never
spelled out (the Abstract counted on its own, as journals count it), dense sentences (reader_metrics' `dense`) and
numbers that set a rule (a threshold, a window, "at least nine") with no reason, reference or citation in their
sentence or the next. Each is a place to read, never a finding by itself. A note before the Abstract (a draft note,
a statement of how two papers divide the work) is read as the body is, its abbreviations counted on their own: a
co-author reads it first, and on Paper 1 v0.7 one read it as the paper's only statement of that division. Title,
author lines and affiliations are not read. `--before ORIGINAL` marks each item the original also had
(`in_original`); `--check` exits 1 while any abbreviation is listed, which manuscript-improve uses to finish the
spelling-out a fix began (Paper 1 v0.7's fix spelled out VCF in the Abstract and stopped there).

`passages` lists what a revision wrote that is longer than a sentence: each paragraph of the corrected version with
two or more sentences the original lacks. Those are the passages a run writes for its own referees, which nobody
reads for whether they can be followed.

`prepare` writes a fresh reader's folder: `reading.md` (the sections chosen with `--section`, by their number or
a word of their heading; by default every Methods- and Results-like section), `passages.md` (with `--original`),
`brief.md` (the whole prompt) and `manifest.json`. Nothing else goes in: no record, no findings, no scan.

`check` reads the reader's `answer.json`, refuses one that skipped a section or passage, quotes words the paper does
not hold or names a problem outside the list, and writes the items as draft findings of category Comprehension
(`minor`, no decision, owned by manuscript-prose-edit), with a `major` finding for a section with five or more.

Exit codes: 0 done (`scan` without `--check` and `passages` always, as they only list), 1 an answer that breaks the
contract or, for `scan --check`, an abbreviation left, 2 a usage error.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import typer

app = typer.Typer(add_completion=False, help=__doc__.split("\n\n")[0])
HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


rm = _load("comprehension_reader_metrics", HERE / "reader_metrics.py")

# Abbreviations a scientist from any field reads without a definition. Anything else is spelled out once.
KNOWN = frozenset({"DNA", "RNA", "mRNA", "PDF", "URL", "ID", "IDS", "USA", "UK", "EU", "CPU", "GPU", "RAM", "OK",
                   "KB", "MB", "GB", "TB", "CODESPAN"})  # CODESPAN: reader_metrics's stand-in for code
NOT_A_DEFINITION = re.compile(r"\s*\((?:fig|figure|table|box|section|sec\.|see|e\.g\.|i\.e\.|eq|supplement|\d)", re.IGNORECASE)
NUMBER_WORDS = r"(?:two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|fifty|hundred)"
_NUM = rf"(?:\d+(?:[.,]\d+)?\s*%?|{NUMBER_WORDS})"
# A next sentence about the value just set ("This value keeps ...") gives its reason.
EXPLAINS = re.compile(r"(?:this|these|that|the (?:value|threshold|cut-?off|number|window|choice)s?)\b", re.IGNORECASE)
# A number that sets a rule: the rule's word, then the number within three words ("at least nine", "a threshold of
# 0.8", "top 10"), or the number before what it bounds ("a 5 kb window", "three-sample minimum").
RULE = re.compile(rf"\b(?:thresholds?|cut-?offs?|at least|at most|(?:a )?(?:minimum|maximum) of|windows?|top|set to|fixed at|"
                  rf"limited to|capped at|no more than|no fewer than|exceed\w*|(?:penalty|factor|weight) of)\W+(?:[\w-]+\W+){{0,3}}?"
                  rf"{_NUM}(?![\w])|(?<![\w.]){_NUM}[\s-]+(?:[\w-]+[\s-]+)?(?:thresholds?|cut-?offs?|windows?|minimum|"
                  rf"maximum|limit)\b|[≥≤]\s*{_NUM}(?![\w])", re.IGNORECASE)
REASON = re.compile(r"\b(?:because|since|so that|in order to|to (?:avoid|keep|ensure|match|balance|limit|reduce|"
                    r"exclude|include|reach)|following|as (?:in|recommended|suggested|used|proposed|described)|"
                    r"recommend\w*|chosen (?:so|to|because|as)|which (?:keeps|gives|avoids|ensures|matches)|reason|"
                    r"justif\w+|in line with|according to|consistent with|calibrated|tuned|optimi[sz]ed)\b",
                    re.IGNORECASE)
CITATION = re.compile(r"\[@[^\]]+\]|\[\d+(?:[,–-]\s*\d+)*\]|\((?=[^()]*\b(?:1[89]|20)\d{2}[a-z]?\b)[^()]*\)|"
                      r"\\cite[tp]?\{")
PROBLEMS = ("term-before-definition", "cannot-parse", "number-without-reason", "no-link", "could-not-restate")
ACTIONS = {
    "term-before-definition": "Define the term where the reader first meets it, from the paper's own definition, or "
                              "move the definition there.",
    "cannot-parse": "Split the sentence so each part says one thing, keeping every qualifier.",
    "number-without-reason": "Give the number's reason where it is set, from the paper, its code or its source; a "
                             "reason only the authors know is a question for them, never invented.",
    "no-link": "Say how this sentence follows from the one before, from what the paper already gives.",
    "could-not-restate": "Rewrite the sentence in the plainest words that keep its claim and its qualifiers.",
}
SUMMARIES = {
    "term-before-definition": "A term the reader meets before the paper defines it",
    "cannot-parse": "A sentence a reader outside the field could not parse",
    "number-without-reason": "A number given without its reason",
    "no-link": "A sentence with no link to the one before",
    "could-not-restate": "A sentence a co-author outside the field could not restate",
}
SECTION_MAJOR = 5


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        typer.echo(f"comprehension: {path} cannot be read: {e}", err=True)
        raise typer.Exit(2)


def _latex(text: str) -> bool:
    return bool(re.search(r"\\(?:section|documentclass)\b", text))


def _heading(section) -> str:
    return FRONT_NOTE if section.kind == "front" else re.sub(r"[*_#`]", "", section.heading).strip()


def _plain(paragraph: str, latex: bool) -> str:
    """The paragraph as a reader sees it, citations kept (scan looks for them)."""
    text = rm._strip_latex(paragraph) if latex else rm._strip_markdown(paragraph)
    return re.sub(r"\s+", " ", text).strip()


def fold(text: str) -> str:
    """Whitespace and Markdown emphasis set aside, for matching a reader's quote against the paper."""
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"[*_`]+", "", text).replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text).strip().lower()


def _acronyms(sentence: str):
    for m in rm.ACRONYM.finditer(sentence):
        word = m.group(0)
        base = word[:-1] if word.endswith("s") and len(word) > 2 and word[:-1].isupper() else word
        if rm.ROMAN.match(base) or sum(c.isalpha() for c in base) < 2 or base.upper() in KNOWN or base in KNOWN:
            continue
        before = sentence[:m.start()].rstrip()
        after = sentence[m.end():]
        defines = (before.endswith("(") and re.match(r"\s*[),;]", after) is not None) or \
                  (re.match(r"\s*\(\s*[A-Za-z]", after) is not None and NOT_A_DEFINITION.match(after) is None)
        yield base, defines


FRONT_NOTE = "the note before the Abstract"


def front_note(paragraph: str, latex: bool) -> bool:
    """A paragraph of the front matter that is prose (a note), not a title, author line or affiliation."""
    plain = rm._clean(paragraph, latex)
    words = rm.WORD.findall(plain)
    return len(words) >= 15 and re.search(r"[.!?][)\"'”’]?$", plain) is not None and plain.count(",") * 4 < len(words)


def _scope_of(section) -> str | None:
    if section.kind == "back":
        return None
    return {"front": "note", "abstract": "abstract"}.get(section.kind, "body")


def _paragraphs(section, latex: bool) -> list[str]:
    return [p for p in section.text if section.kind != "front" or front_note(p, latex)]


def abbreviations(sections, latex: bool) -> list[dict]:
    """Abbreviations first used before their definition, or never defined: in the note before the Abstract, in the
    Abstract and in the rest, each apart."""
    out = []
    for scope in ("note", "abstract", "body"):
        first: dict[str, tuple[str, str]] = {}
        defined: dict[str, str] = {}
        for s in sections:
            if _scope_of(s) != scope:
                continue
            for paragraph in _paragraphs(s, latex):
                for sentence in rm._sentences(rm._clean(paragraph, latex)):
                    for acr, defines in _acronyms(sentence):
                        if defines:
                            defined.setdefault(acr, _heading(s))
                        elif acr not in first and acr not in defined:
                            first[acr] = (_heading(s), sentence)
        for acr, (section, sentence) in first.items():
            where = defined.get(acr)
            out.append({"kind": "abbreviation", "term": acr, "section": section, "quote": sentence,
                        "note": (f"used before it is spelled out (spelled out in {where})" if where
                                 else "never spelled out" + {"abstract": " in the Abstract",
                                                             "note": " in the note"}.get(scope, ""))})
    return out


def scan_text(text: str, known: frozenset[str] = frozenset()) -> list[dict]:
    latex = _latex(text)
    sections = rm.parse(text)
    items = [i for i in abbreviations(sections, latex) if i["term"] not in known]
    for s in sections:
        if s.kind == "back":
            continue
        for paragraph in _paragraphs(s, latex):
            plain = rm._sentences(_plain(paragraph, latex))
            for n, sentence in enumerate(plain):
                bare = re.sub(r"\s+", " ", rm._drop_citations(sentence)).strip()
                if rm.dense(bare):
                    items.append({"kind": "dense", "section": _heading(s), "quote": bare,
                                  "note": f"{len(rm.WORD.findall(bare))} words with nested clauses"})
                if s.kind not in ("methods", "results"):
                    continue
                if RULE.search(bare):
                    following = plain[n + 1] if n + 1 < len(plain) else ""
                    # the next sentence gives the reason only when it sets no rule of its own
                    explained = (REASON.search(following) or EXPLAINS.match(following)) and not RULE.search(following)
                    if not (REASON.search(sentence) or CITATION.search(sentence) or explained):
                        items.append({"kind": "number", "section": _heading(s), "quote": bare,
                                      "note": "a number that sets a rule, with no reason or source beside it"})
    return items


def passages_of(original: str, corrected: str) -> list[dict]:
    """Paragraphs of *corrected* holding two or more sentences *original* lacks: what the revision wrote."""
    latex = _latex(original) or _latex(corrected)
    old = {fold(sentence) for s in rm.parse(original) for p in s.text
           for sentence in rm._sentences(rm._clean(p, latex))}
    out = []
    for s in rm.parse(corrected):
        if s.kind in ("front", "back"):
            continue
        for paragraph in s.text:
            new = [x for x in rm._sentences(rm._clean(paragraph, latex)) if fold(x) not in old]
            if len(new) >= 2:
                out.append({"id": f"P{len(out) + 1}", "section": _heading(s), "paragraph": paragraph, "new": new})
    return out


def _key(item: dict) -> tuple[str, str]:
    return item["kind"], item.get("term") or fold(item["quote"])


def mark_original(items: list[dict], original: list[dict]) -> list[dict]:
    """Mark each item the original's scan also lists (the same abbreviation, or the same sentence)."""
    before = {_key(i) for i in original}
    return [{**i, "in_original": _key(i) in before} for i in items]


def _markdown_scan(items: list[dict]) -> str:
    lines = ["# Comprehension scan (places to read, not findings)", ""]
    if not items:
        return "\n".join(lines + ["Nothing listed.", ""])
    for kind, title in (("abbreviation", "Abbreviations"), ("dense", "Dense sentences"),
                        ("number", "Numbers that set a rule without a reason")):
        group = [i for i in items if i["kind"] == kind]
        if group:
            lines += [f"## {title} ({len(group)})", ""]
            lines += [f"- {i['section']}: " + (f"**{i['term']}**, " if kind == "abbreviation" else "")
                      + f"{i['note']}"
                      + {True: " (the original too)", False: " (new)"}.get(i.get("in_original"), "")
                      + f": \"{i['quote']}\"" for i in group]
            lines.append("")
    return "\n".join(lines)


@app.command()
def scan(paper: Path, json_out: Path | None = typer.Option(None, "--json"), md: Path | None = typer.Option(None),
         known: list[str] = typer.Option([], help="An abbreviation this paper's readers know without a definition."),
         before: Path | None = typer.Option(None, "--before", help="The original, to mark what it also had."),
         check: bool = typer.Option(False, "--check", help="Exit 1 while any abbreviation is listed.")) -> None:
    """List-only parse pass over the whole body and the note before the Abstract."""
    items = scan_text(_read(paper), frozenset(known))
    if before:
        items = mark_original(items, scan_text(_read(before), frozenset(known)))
    if json_out:
        json_out.write_text(json.dumps({"paper": paper.name, "items": items}, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
    report = _markdown_scan(items)
    if md:
        md.write_text(report, encoding="utf-8")
    if not (json_out or md):
        typer.echo(report)
    left = [i["term"] for i in items if i["kind"] == "abbreviation"]
    if check and left:
        typer.echo(f"comprehension: {len(left)} abbreviation(s) not spelled out at first use: {', '.join(left)}",
                   err=True)
        raise typer.Exit(1)


@app.command()
def passages(original: Path, corrected: Path, json_out: Path | None = typer.Option(None, "--json")) -> None:
    """The corrected version's paragraphs with two or more new sentences."""
    found = passages_of(_read(original), _read(corrected))
    if json_out:
        json_out.write_text(json.dumps(found, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for p in found:
        typer.echo(f"{p['id']} {p['section']}: {len(p['new'])} new sentences")


def _picked(section, wanted: list[str]) -> bool:
    heading = _heading(section)
    if not wanted:
        return section.kind in ("methods", "results")
    for w in wanted:
        if re.fullmatch(r"[SA]?\d+(?:\.\d+)*", w):
            if re.match(rf"{re.escape(w)}(?:[.\s]|$)", heading):
                return True
        elif w.lower() in heading.lower():
            return True
    return False


BRIEF = """You are a senior scientist in the paper's broader field, outside its sub-field, and you are named on it as a
co-author: you must be able to defend every sentence to a referee. You have never seen this paper before.

Read {what}, every sentence, in order, slowly. Stop at each sentence you could not restate in your own words, and
note it, quoting it exactly, with the problem, one of:

- term-before-definition: a term, abbreviation or name you meet before the paper says what it is (give it as `term`);
- cannot-parse: a sentence you had to read twice and still could not take apart;
- number-without-reason: a number that sets a rule or a choice (a threshold, a count, a weight) with no reason or
  source given where it is set;
- no-link: a sentence whose relation to the one before you cannot tell;
- could-not-restate: anything else that stopped you, with why.

Say what stopped you, in one sentence of your own (`why`). Do not review the science, judge the results or suggest
edits; do not read anything outside this folder. Skipping nothing is the job: list in `read` every section heading
of `reading.md`{and_passages} once you have read it.

Write your answer as `answer.json` in this folder:

```json
{{"seat": "outside-expert",
 "read": ["the section headings as reading.md gives them"{passage_ids}],
 "items": [{{"quote": "the sentence, verbatim", "section": "its heading, or the passage id",
            "problem": "term-before-definition", "term": "site", "why": "one sentence"}}]}}
```
"""


@app.command()
def prepare(paper: Path, into: Path = typer.Option(...),
            section: list[str] = typer.Option([], help="A section by its number (2, 3.1) or a word of its heading."),
            original: Path | None = typer.Option(None, help="The text before the run: its new passages are read too."),
            passages_only: bool = typer.Option(False, help="Read only the passages the run wrote.")) -> None:
    """Write a fresh outside-expert reader's folder."""
    text = _read(paper)
    if passages_only and original is None:
        typer.echo("comprehension: --passages-only needs --original", err=True)
        raise typer.Exit(2)
    picked = [] if passages_only else [s for s in rm.parse(text) if s.kind not in ("front", "back") and _picked(s, section)]
    found = passages_of(_read(original), text) if original else []
    if not picked and not found:
        typer.echo("comprehension: nothing to read: no section matched and no passage is new", err=True)
        raise typer.Exit(2)
    into.mkdir(parents=True, exist_ok=True)
    if picked:
        body = [f"{'#' * max(s.level, 1)} {_heading(s)}\n\n" + "\n\n".join(s.text) for s in picked]
        (into / "reading.md").write_text("\n\n".join(body) + "\n", encoding="utf-8")
    if found:
        parts = [f"## {p['id']} ({p['section']})\n\n{p['paragraph']}" for p in found]
        (into / "passages.md").write_text("# Passages\n\n" + "\n\n".join(parts) + "\n", encoding="utf-8")
    what = " and ".join(x for x in ("`reading.md`" if picked else "", "each passage of `passages.md`" if found else "") if x)
    ids = "".join(f', "{p["id"]}"' for p in found[:2]) + (", ..." if len(found) > 2 else "")
    (into / "brief.md").write_text(BRIEF.format(what=what, and_passages=", and every passage id of `passages.md`"
                                                if found else "", passage_ids=ids), encoding="utf-8")
    manifest = {"paper": str(paper), "digest": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                "sections": [_heading(s) for s in picked], "passages": [p["id"] for p in found],
                "passage_sections": {p["id"]: p["section"] for p in found}}
    (into / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    typer.echo(f"{into}: {len(picked)} sections, {len(found)} passages")


def contract(answer: dict, manifest: dict, paper: str) -> list[str]:
    problems = []
    if not isinstance(answer.get("items"), list) or not isinstance(answer.get("read"), list):
        return ["answer.json needs `read` and `items` lists"]
    read = {fold(str(r)) for r in answer["read"]}
    for name in manifest["sections"] + manifest["passages"]:
        if fold(name) not in read:
            problems.append(f"not read: {name}")
    folded = fold(paper)
    for n, item in enumerate(answer["items"], 1):
        quote = str(item.get("quote") or "")
        if item.get("problem") not in PROBLEMS:
            problems.append(f"item {n}: problem {item.get('problem')!r} is not one of {', '.join(PROBLEMS)}")
        if len(quote.split()) < 3 or fold(quote) not in folded:
            problems.append(f"item {n}: the quote is not in the paper word for word: {quote[:80]!r}")
        if not str(item.get("why") or "").strip():
            problems.append(f"item {n}: no `why`")
        if item.get("problem") == "term-before-definition" and not str(item.get("term") or "").strip():
            problems.append(f"item {n}: a term-before-definition names its `term`")
    return problems


def findings(items: list[dict], manifest: dict, prefix: str, start: int, evidence: str) -> list[dict]:
    """Draft records for the stage's findings.json; `evidence` is the answer's path from the stage folder."""
    out = []
    by_section: dict[str, list[str]] = {}
    by_quote: dict[str, str] = {}
    for item in items:
        section = manifest["passage_sections"].get(item.get("section"), item.get("section") or "")
        fid = f"{prefix}-{start + len(out)}"
        term = f" ({item['term']})" if item.get("term") else ""
        out.append({"id": fid, "category": "Comprehension", "section": section, "quote": item["quote"],
                    "summary": SUMMARIES[item["problem"]] + term, "detail": item["why"],
                    "action": ACTIONS[item["problem"]], "severity": "minor", "stage": "now",
                    "confidence": "confirmed", "decision": False, "owner": "manuscript-prose-edit",
                    "evidence": [{"path": evidence, "quote": item["why"]}]})
        by_section.setdefault(section, []).append(fid)
        by_quote[fid] = item["why"]
    for section, ids in by_section.items():
        if len(ids) >= SECTION_MAJOR:
            out.append({"id": f"{prefix}-{start + len(out)}", "category": "Comprehension", "section": section,
                        "quote": None, "looked_in": [section],
                        "summary": "Written for a narrower reader than the recorded audience",
                        "detail": f"A reader outside the field stopped {len(ids)} times in this section ({', '.join(ids)}).",
                        "action": "Fix each stop listed; the section reads for its audience once they are gone.",
                        "severity": "major", "stage": "now", "confidence": "confirmed", "decision": False,
                        "owner": "manuscript-prose-edit",
                        "evidence": [{"path": evidence, "quote": by_quote[ids[0]]}]})
    return out


@app.command()
def check(answer_path: Path, out: Path = typer.Option(...), prefix: str = typer.Option("ST"),
          start: int = typer.Option(1, help="The number of the first finding id.")) -> None:
    """Hold the reader's answer to its contract and write it as draft Comprehension findings."""
    folder = answer_path.parent
    try:
        answer = json.loads(_read(answer_path))
        manifest = json.loads(_read(folder / "manifest.json"))
    except json.JSONDecodeError as e:
        typer.echo(f"comprehension: {e}", err=True)
        raise typer.Exit(1)
    paper = _read(Path(manifest["paper"]))
    if hashlib.sha256(paper.encode("utf-8")).hexdigest()[:16] != manifest["digest"]:
        typer.echo(f"comprehension: {manifest['paper']} changed since the folder was prepared; prepare it again", err=True)
        raise typer.Exit(1)
    problems = contract(answer, manifest, paper)
    for p in problems:
        typer.echo(p)
    if problems:
        raise typer.Exit(1)
    try:
        evidence = answer_path.resolve().relative_to(out.resolve().parent).as_posix()
    except ValueError:
        evidence = str(answer_path)
    drafted = findings(answer["items"], manifest, prefix, start, evidence)
    run_wrote = [f["id"] for f, item in zip(drafted, answer["items"]) if item.get("section") in manifest["passages"]]
    result = {"seat": answer.get("seat", "outside-expert"), "paper": manifest["paper"], "digest": manifest["digest"],
              "read": answer["read"], "stops": len(answer["items"]), "on_passages_the_run_wrote": run_wrote,
              "findings": drafted}
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    typer.echo(f"{out}: {result['stops']} stops, {len(drafted)} findings")


if __name__ == "__main__":
    _utf8_console()
    app()
