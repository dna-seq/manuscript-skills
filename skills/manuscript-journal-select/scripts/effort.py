# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "httpx>=0.27"]
# ///
"""How much the manuscript would change for each recommended journal: the major work only, measured, so the
authors can weigh it before they choose. Not the full adaptation, which manuscript-journal-adapt does once a
journal is chosen.

    uv run --script effort.py PAPER.md --top3 RUN/manuscript-journal-select/top3.json --record REC.yaml
    uv run --script effort.py PAPER.md --top3 TOP3 --record REC --format json > RUN/manuscript-journal-select/adaptation.json
    uv run --script effort.py main.tex --venue iscience --venue frontiers-bioinformatics --record REC.yaml

The manuscript is measured as an editor counts it (venues.py's catalogue says what each journal allows):

- the body: Introduction to Conclusion, without the abstract, the captions, the tables, the references and the
  back matter (declarations, availability, funding), and without HTML comments such as revision marks;
- the abstract, its paragraphs and the headings it is written under;
- the main-text figures, tables and boxes (supplementary ones, numbered S1 and on, are left out);
- the main sections' headings, for the body structure a venue sets.

Each venue gets one row per kind of change: the length of the body and of the abstract, the abstract's form, the
figures and tables, the body's sections, the sections to add, and the validation a rule asks for that the record's
`conditions` say the paper does not show. A row is `none`, `small` (a trim, a heading, a short section), `medium`
(rewriting the abstract or a section, regrouping the paper, cutting up to a third of the body) or `large` (cutting
more than a third of the body, new analysis); `unknown` when nobody has read the rule, which never counts as fitting.
The venue's estimate is its largest row: no change, light, moderate or major. A recommended rather than required
length (`limits.body_words_kind: recommended`) counts one step lighter.

What only judgement finds (a fixed structure written as prose in the guidelines, such as Cell Press's STAR Methods)
comes from top3.json: each entry may carry `changes: [{what, size, why, url}]`, and `limits` or `display_items`
for the article type chosen when the catalogue records another one.

Exit codes: 0 for every report, 2 for a usage error.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Optional

import typer
import yaml

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parents[1]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The venue catalogue and its helpers (the one database the journal skills share), and the story skill's section
# parser, which already tells the body from the front and back matter in Markdown and LaTeX.
venues = _load("effort_venues", SKILLS / "manuscript-journal-adapt" / "scripts" / "venues.py")
metrics = _load("effort_reader_metrics", SKILLS / "manuscript-story" / "scripts" / "reader_metrics.py")

app = typer.Typer(add_completion=False, no_args_is_help=True)

SIZES = ("none", "small", "medium", "large")
OVERALL = {"none": "no change", "small": "light", "medium": "moderate", "large": "major"}
# The share of the body a cut removes: up to a tenth is a trim, up to a third rewrites sections, more is another paper.
BODY_CUT = ((0.10, "small"), (1 / 3, "medium"))
ABSTRACT_CUT = 0.35  # up to a third of the abstract is a trim; more is a rewrite
CAPTION = re.compile(r"^(?:\*\*|__)?\s*(Figure|Fig\.|Table)\s+(S?)(\d+)", re.IGNORECASE)
BOX = re.compile(r"^\s*(?:\*\*|__)?\s*Box\s+(\d+)\b", re.IGNORECASE | re.MULTILINE)
# A heading inside an abstract paragraph: "**Motivation:** ..." (reader_metrics has already dropped the opening
# asterisks of a paragraph, so only the closing ones are required) or LaTeX's \textbf{Motivation:}.
ABSTRACT_LABEL = re.compile(r"^(?:\*\*|__)?([A-Z][\w ,/&-]{0,40}?)\s*[:.]?\s*(?:\*\*|__)\s*[:.]?|"
                            r"^\\(?:textbf|paragraph)\{([^}:.]{1,40})[:.]?\}")
REFERENCES = re.compile(r"\b(references?|bibliography|literature cited)\b", re.IGNORECASE)
NUMBERING = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[A-Z]\.|[IVX]+\.)\s+")
# The headings of a body structure, by the kind of section reader_metrics gives them; a required heading such as
# "Results and Discussion" needs every kind it names.
STRUCTURE_KINDS = ("introduction", "methods", "results", "discussion", "conclusion")


class Format(str, Enum):
    md = "md"  # tables for the authors and the stage report
    json = "json"  # adaptation.json, which the dashboard's Journals tab reads


def heading_text(heading: str) -> str:
    """A heading as the reader sees it: no Markdown or LaTeX markup, no section number."""
    plain = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", re.sub(r"[*_`#]", "", heading)).strip()
    return NUMBERING.sub("", plain).strip()


def word_count(text: str, latex: bool) -> int:
    """Words as a word processor counts them: whitespace-separated tokens with a letter or digit, after markup that
    prints nothing (link targets, images, LaTeX commands) is removed. Citations count, as they do for editors."""
    if latex:
        text = re.sub(r"\\(?:cite[tp]?|citep|citet)\*?(?:\[[^\]]*\])*\{([^}]*)\}", lambda m: " [ref] " * len(m.group(1).split(",")), text)
        text = metrics._strip_latex(text)
    else:
        text = re.sub(r"!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?", " ", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    return sum(1 for token in text.split() if re.search(r"\w", token))


def _references(raw: str, latex: bool) -> Optional[int]:
    """How many entries the reference list has: LaTeX `\\bibitem`s (or the distinct keys cited, with a .bib), or the
    blank-line-separated entries or list items under a Markdown References heading; None when there is none."""
    if latex:
        items = re.findall(r"\\bibitem\b", raw)
        if items:
            return len(items)
        keys = {k.strip() for group in re.findall(r"\\cite[a-z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}", raw)
                for k in group.split(",") if k.strip()}
        return len(keys) or None
    text = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    found = None
    for match in re.finditer(r"^(#{1,6})\s+(.*\S)\s*$", text, flags=re.MULTILINE):
        if REFERENCES.search(heading_text(match.group(2))):
            found = match
    if found is None:
        return None
    level = len(found.group(1))
    rest = text[found.end():]
    stop = re.search(rf"^#{{1,{level}}}\s", rest, flags=re.MULTILINE)
    block = rest[:stop.start()] if stop else rest
    entries = 0
    for chunk in re.split(r"\n\s*\n", block):
        lines = [line for line in chunk.splitlines() if line.strip()]
        listed = [line for line in lines if re.match(r"^\s*(?:[-*+]|\d+[.)]|\[\d+\])\s+", line)]
        entries += len(listed) if len(listed) > 1 else int(bool(lines))
    return entries


def measure(path: Path) -> dict[str, Any]:
    """What an editor counts in the manuscript, with the main sections' headings and kinds."""
    raw = path.read_text(encoding="utf-8")
    latex = path.suffix.lower() == ".tex" or bool(re.search(r"\\(?:section|documentclass)\b", raw))
    text = raw
    if latex:  # the reference list is back matter, but a LaTeX one sits inside the last section
        text = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", "\n", text, flags=re.DOTALL)
        text = re.sub(r"\\(?:bibliography|bibliographystyle|addbibresource)\{[^}]*\}|\\printbibliography", " ", text)
    sections = metrics.parse(text)
    # A heading under the Abstract (### Background) is part of the abstract, not of the body.
    in_abstract: Optional[int] = None
    abstract, body, labels = [], [], []
    for s in sections:
        if in_abstract is not None and s.level > in_abstract:
            abstract.append(s)
            labels.append(heading_text(s.heading))
            continue
        in_abstract = s.level if s.kind == "abstract" else None
        if s.kind == "abstract":
            abstract.append(s)
        elif s.kind not in ("front", "back"):
            body.append(s)
    paragraphs = [p for s in abstract for p in s.text]
    for p in paragraphs:
        if m := ABSTRACT_LABEL.match(p.strip()):
            labels.append((m.group(1) or m.group(2)).strip())
    captions = [c for s in body + abstract for c in s.captions]
    if latex:
        figures = len(re.findall(r"\\begin\{figure\*?\}", raw))
        tables = len(re.findall(r"\\begin\{table\*?\}", raw))
    else:
        numbered = [(m.group(1).lower(), m.group(3)) for c in captions if (m := CAPTION.match(c)) and not m.group(2)]
        figures = len({n for kind, n in numbered if kind.startswith("fig")})
        tables = len({n for kind, n in numbered if kind == "table"})
    stripped = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    boxes = len(set(BOX.findall(stripped)))
    main_level = min((s.level for s in body), default=0)
    main = [s for s in body if s.level == main_level]
    table_words = 0
    if not latex:
        rows = [line for line in stripped.splitlines() if line.strip().startswith("|") and not re.fullmatch(r"[\s|:-]+", line)]
        table_words = word_count("\n".join(rows), latex)
    return {
        "file": path.name,
        "body_words": sum(word_count(p, latex) for s in body for p in s.text),
        # Each body section with the kind it inherits ("4.1 Annotation Speed" under "4. Benchmarking" is results),
        # for a venue whose limit leaves a kind out (Cell Reports Methods does not count the STAR Methods).
        "parts": [{"heading": heading_text(s.heading), "kind": s.kind, "words": sum(word_count(p, latex) for p in s.text)}
                  for s in body],
        "abstract_words": sum(word_count(p, latex) for p in paragraphs),
        "abstract_paragraphs": len(paragraphs),
        "abstract_headings": labels,
        "caption_words": sum(word_count(c, latex) for c in captions),
        "table_words": table_words,
        "figures": figures,
        "tables": tables,
        "boxes": boxes,
        "references": _references(raw, latex),
        "sections": [{"heading": heading_text(s.heading), "kind": metrics._kind(s.heading) or s.kind} for s in main],
        "headings": [heading_text(s.heading) for s in sections[1:]],  # sections[0] is the text before any heading
    }


def _count(n: int, word: str, many: str = "") -> str:
    return f"{n:,} {word if n == 1 else many or word + 's'}"


def display_text(m: dict[str, Any]) -> str:
    return venues._and([_count(m["figures"], "figure"), _count(m["tables"], "table")]
                       + ([_count(m["boxes"], "box", "boxes")] if m["boxes"] else []))


def measured_text(m: dict[str, Any]) -> str:
    """One sentence of what was measured, for the report and the dashboard."""
    items = [display_text(m)] + ([_count(m["references"], "reference")] if m["references"] else [])
    return (f"Measured on {m['file']}: the body is {_count(m['body_words'], 'word')} (Introduction to Conclusion, "
            f"without captions, tables or back matter), the abstract {_count(m['abstract_words'], 'word')} in "
            f"{_count(m['abstract_paragraphs'], 'paragraph')}, with {venues._and(items)} in the main text.")


def _about(n: int) -> str:
    """A cut as authors plan it: to the nearest ten words, or hundred above a thousand."""
    step = 100 if n >= 1000 else 10
    return f"{max(step, round(n / step) * step):,}"


def _lighter(size: str) -> str:
    return SIZES[max(1, SIZES.index(size) - 1)]


def _source(v: dict[str, Any], field: str) -> dict[str, str]:
    """Where a fact was read: its provenance, else the field's own source and date (figure_rules keeps them
    inside), else the venue's guidelines page with no date."""
    p = (v.get("provenance") or {}).get(field) or (v.get(field) if isinstance(v.get(field), dict) else None) or {}
    return {"source": str(p.get("source") or v.get("url") or ""), "checked": str(p.get("checked") or "")}


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(text).lower())).strip()


def _singular(text: str) -> str:
    """A heading compared as a name: case, punctuation and a plural s do not count ("Methods" is "Method")."""
    return " ".join(re.sub(r"s$", "", w) for w in _norm(text).split())


def _kinds(name: str) -> set[str]:
    """Every kind of body section a required heading names ("Results and Discussion": results and discussion)."""
    plain = re.sub(r"\(.*", "", str(name))
    return {kind for kind, rx in metrics.KINDS if kind in STRUCTURE_KINDS and rx.search(plain)}


def _present(required: str, headings: list[str]) -> bool:
    """Whether a section the venue asks for is already a heading: "Data Availability Statement" is "Data
    Availability"; parenthesised notes and the words statement and section do not count."""
    words = set(_norm(re.sub(r"\(.*?\)", "", required)).split()) - {"statement", "statements", "section", "sections"}
    return bool(words) and any(words <= set(_norm(h).split()) for h in headings)


def _display_rule(v: dict[str, Any], entry: dict[str, Any]) -> tuple[Any, str]:
    """The display-item limit for the article type chosen: an int (all items), `{figures, tables}`, or None, with
    the article type it was recorded for; a mapping by article type is matched on the type's words."""
    rule = entry.get("display_items")
    if rule is None:
        rule = (v.get("figure_rules") or {}).get("display_items")
    if not isinstance(rule, dict) or {"figures", "tables", "total"} & set(rule):
        return rule, ""
    wanted = _norm(entry.get("article_type") or "")
    for kind, value in rule.items():
        if wanted and (_norm(kind) in wanted or wanted in _norm(kind)):
            return value, str(kind)
    return "other types", ", ".join(str(k) for k in rule)


def estimate(m: dict[str, Any], v: dict[str, Any], entry: dict[str, Any], designs: list[str]) -> dict[str, Any]:
    """The major changes `v` asks of the manuscript measured as `m`, row by row, and the venue's estimate."""
    items: list[dict[str, Any]] = []
    limits = {**(v.get("limits") or {}), **(entry.get("limits") or {})}
    stated_none = set(limits.get("none_stated") or [])

    def add(aspect: str, what: str, have: str, limit: str, change: str, size: str, field: str = "limits") -> None:
        items.append({"aspect": aspect, "what": what, "have": have, "limit": limit, "change": change, "size": size,
                      **(_source(v, field) if field else {"source": "", "checked": ""})})

    # A limit that leaves some sections out (`limits.body_words_excludes: [methods]`) counts the rest only.
    excluded = [str(k) for k in limits.get("body_words_excludes") or []]
    body, cut_words = m["body_words"], 0
    counted = sum(p["words"] for p in m.get("parts") or [] if p["kind"] not in excluded) if excluded else body
    have = (f"{counted:,} words outside the {venues._and(excluded)} ({body:,} with them)" if excluded
            else f"{body:,} words")
    if n := limits.get("body_words"):
        advised = limits.get("body_words_kind") == "recommended"
        limit = f"{n:,} words" + (", advised" if advised else "") + (f", {venues._and(excluded)} not counted" if excluded else "")
        over = counted - n
        if over <= 0:
            add("body", "Length of the body", have, limit,
                f"fits, {-over:,} words to spare" + (" once the "
                f"{venues._and(excluded)} sections are the part the journal leaves out" if body > n else ""), "none")
        else:
            share = over / counted
            size = next((s for top, s in BODY_CUT if share <= top), "large")
            size = _lighter(size) if advised else size
            change = f"cut about {_about(over)} words, {round(100 * share)}% of the body"
            if (ratio := limits.get("over_limit_return")) and counted > n * ratio:
                size, change = "large", change + f"; papers more than {round(100 * (ratio - 1))}% over are returned unread"
            add("body", "Length of the body", have, limit, change, size)
            cut_words += over
    elif "body_words" in stated_none:
        add("body", "Length of the body", f"{body:,} words", "none stated", "none", "none")
    else:
        add("body", "Length of the body", f"{body:,} words", "not researched", "read the article-type page", "unknown")

    words = m["abstract_words"]
    if n := limits.get("abstract_words"):
        over = words - n
        if not words:
            add("abstract", "Length of the abstract", "no abstract found", f"{n} words", f"write an abstract of at most {n} words", "medium")
        elif over <= 0:
            add("abstract", "Length of the abstract", f"{words} words", f"{n} words", "fits", "none")
        else:
            add("abstract", "Length of the abstract", f"{words} words", f"{n} words",
                f"cut {over} words, {round(100 * over / words)}% of the abstract",
                "small" if over / words <= ABSTRACT_CUT else "medium")
            cut_words += over
    elif "abstract_words" in stated_none or limits.get("abstract_characters"):
        add("abstract", "Length of the abstract", f"{words} words",
            f"{limits['abstract_characters']} characters" if limits.get("abstract_characters") else "none stated",
            "check the characters when the abstract is final" if limits.get("abstract_characters") else "none", "none")
    else:
        add("abstract", "Length of the abstract", f"{words} words", "not researched", "read the author guidelines", "unknown")

    wanted, labels = v.get("abstract_headings"), m["abstract_headings"]
    shape = f"{_count(m['abstract_paragraphs'], 'paragraph')}, " + (f"headed {', '.join(labels)}" if labels else "no headings")
    if wanted is None:
        add("abstract_form", "Form of the abstract", shape, "not researched", "read the author guidelines", "unknown",
            "abstract_headings")
    elif not wanted:
        add("abstract_form", "Form of the abstract", shape, "no headings",
            f"write it without the headings {', '.join(labels)}" if labels else "none", "small" if labels else "none",
            "abstract_headings")
    elif [_norm(x) for x in labels] == [_norm(x) for x in wanted]:
        add("abstract_form", "Form of the abstract", shape, ", ".join(wanted), "none", "none", "abstract_headings")
    else:
        add("abstract_form", "Form of the abstract", shape, ", ".join(wanted),
            f"rewrite it under {', '.join(wanted)}", "small", "abstract_headings")

    rule, kind = _display_rule(v, entry)
    tables = m["tables"] + m["boxes"]
    count = display_text(m)
    if rule == "other types":
        add("display", "Figures and tables", count, f"recorded for {kind} only", "read the limit for this article type",
            "unknown", "figure_rules")
    elif isinstance(rule, (int, float)) or (isinstance(rule, dict) and "total" in rule):
        top = int(rule["total"] if isinstance(rule, dict) else rule)
        over = m["figures"] + tables - top
        add("display", "Figures and tables", count, f"{top} display items" + (f" ({kind})" if kind else ""),
            f"move or merge {over} into the supplement" if over > 0 else "fits",
            "none" if over <= 0 else "small" if over == 1 else "medium", "figure_rules")
    elif isinstance(rule, dict):
        over = max(0, m["figures"] - int(rule.get("figures", m["figures"]))) + max(0, tables - int(rule.get("tables", tables)))
        add("display", "Figures and tables", count,
            f"{rule.get('figures', 'any')} figures, {rule.get('tables', 'any')} tables" + (f" ({kind})" if kind else "")
            + (" (boxes count as tables)" if m["boxes"] else ""),
            f"move or merge {over} into the supplement" if over else "fits",
            "none" if not over else "small" if over == 1 else "medium", "figure_rules")
    elif "display_items" in stated_none:
        add("display", "Figures and tables", count, "none stated", "none", "none")
    else:
        add("display", "Figures and tables", count, "not researched", "read the figure guidelines", "unknown",
            "figure_rules")

    required = v.get("required_sections")
    main = m["sections"]
    if required is None:
        add("structure", "Body sections", ", ".join(s["heading"] for s in main), "not researched",
            "read the article-type page", "unknown", "required_sections")
        additions: list[str] = []
    else:
        structure = [str(x) for x in required if venues._body_section(x)]
        additions = [str(x) for x in required if not venues._body_section(x) and "in the abstract" not in str(x).lower()]
        paper = ", ".join(s["heading"] for s in main)
        if not structure:
            add("structure", "Body sections", paper, "no fixed structure recorded", "none", "none", "required_sections")
        else:
            def place(name: str) -> Optional[int]:
                """The first main section that reads as `name`: by its kind, or by its words for a heading of no
                kind ("Availability and future directions")."""
                kinds = _kinds(name)
                found = [i for i, s in enumerate(main)
                         if (s["kind"] in kinds if kinds else _present(name, [s["heading"]]))]
                return min(found) if found else None

            placed = [(x, place(x)) for x in structure]
            missing = [x for x, at in placed if at is None]
            places = [at for _, at in placed if at is not None]
            limit = ", ".join(structure)
            if missing:
                add("structure", "Body sections", paper, limit,
                    f"regroup the sections under {limit}; nothing reads as {venues._and(missing)} now", "medium",
                    "required_sections")
            elif places != sorted(places):
                add("structure", "Body sections", paper, limit, f"reorder the sections as {limit}", "medium",
                    "required_sections")
            else:
                # In order: name each section as the venue does, and fold a second section of a kind the venue
                # names once (two Methods sections) into the one before it. A kind it does not name stays.
                renames = [f"“{main[at]['heading']}” as {x}" for x, at in placed
                           if _singular(main[at]["heading"]) != _singular(x)]
                named = set().union(*(_kinds(x) for x in structure))
                folded = [f"“{s['heading']}”" for i, s in enumerate(main) if i not in places and s["kind"] in named]
                steps = ([f"rename {venues._and(renames)}"] if renames else []) + (
                    [f"fold {venues._and(folded)} into the section before {'it' if len(folded) == 1 else 'each'}"]
                    if folded else [])
                add("structure", "Body sections", paper, limit, "; ".join(steps) or "none",
                    "small" if steps else "none", "required_sections")
    if additions:
        absent = [x for x in additions if not _present(x, m["headings"])]
        add("sections", "Sections to add", f"{len(additions) - len(absent)} of {len(additions)} present",
            venues._and(additions), f"add {venues._and(absent)}" if absent else "none",
            "small" if absent else "none", "required_sections")

    checks = v.get(venues.MANUSCRIPT_CHECKS) or {}
    rules = {str(r.get("id")): r for r in v.get("validation_requirements") or [] if r.get("id")}
    for rule_id, verdict in checks.items():
        if verdict.get("met") is True:
            continue
        description = (rules.get(rule_id) or {}).get("description") or rule_id.replace("-", " ")
        items.append({"aspect": "validation", "what": "Validation the journal asks for", "have": "partly shown"
                      if verdict.get("met") == "partly" else "not shown", "limit": str(description),
                      "change": str(verdict.get("evidence") or "show what the rule asks for"), "size": "large",
                      "source": str(verdict.get("source") or v.get("url") or ""), "checked": str(verdict.get("checked") or "")})
    for r in venues.open_conditions(v, designs):
        items.append({"aspect": "validation", "what": "Validation the journal asks for", "have": "not checked",
                      "limit": str(r.get("description") or ""), "change": "check the manuscript against this rule",
                      "size": "unknown", "source": str(v.get("url") or ""), "checked": ""})

    for change in entry.get("changes") or []:
        size = str(change.get("size") or "unknown")
        if size not in (*SIZES, "unknown"):
            raise typer.BadParameter(f"top3.json: the size of {change.get('what')!r} must be none, small, medium, "
                                     "large or unknown")
        items.append({"aspect": "judged", "what": str(change.get("what") or "Other change"),
                      "have": str(change.get("have") or ""), "limit": str(change.get("rule") or ""),
                      "change": str(change.get("change") or change.get("why") or ""), "size": size,
                      "source": str(change.get("url") or ""), "checked": str(change.get("checked") or "")})

    known = [i["size"] for i in items if i["size"] in SIZES]
    top = max(known, key=SIZES.index) if known else "none"
    work = [i for i in items if i["size"] in SIZES[1:]]
    unknown = list(dict.fromkeys(i["what"] for i in items if i["size"] == "unknown"))
    # One sentence per change, each led by its own name ("Cell Press structure" keeps its capitals).
    summary = " ".join([f"{OVERALL[top].capitalize()} changes." if work else "No change measured.",
                        *(f"{i['what']}: {i['change'].rstrip('.')}." for i in work),
                        *([f"Not researched yet: {'; '.join(unknown)}."] if unknown else [])])
    return {"key": v["key"], "name": venues._name(v), "article_type": str(entry.get("article_type") or ""),
            "url": str(entry.get("url") or v.get("url") or ""), "size": OVERALL[top], "words_to_cut": cut_words,
            "summary": summary, "items": items}


def markdown(document: dict[str, Any]) -> str:
    out = ["# What each journal would change in the manuscript", "", document["measured_text"], "",
           "Only the major changes are listed: lengths, the abstract's form, figures and tables, the body's sections, "
           "sections to add and validation a journal asks for. The rest of the adaptation (reference style, "
           "declarations, file formats) waits for manuscript-journal-adapt once a journal is chosen. Small is a trim, "
           "a heading or a short section; medium is rewriting the abstract or a section, regrouping the paper or "
           "cutting up to a third of the body; large is cutting more than that or new analysis.", ""]
    for v in document["venues"]:
        named = v["article_type"] and v["article_type"].lower() not in v["name"].lower()
        title = v["name"] + (f" ({v['article_type']})" if named else "")
        out += [f"## {title}: {v['size']}", "", v["summary"], "",
                "| What | This manuscript | The journal | Change | Size |", "|---|---|---|---|---|"]
        for i in v["items"]:
            cells = [i["what"], i["have"] or "—", i["limit"] or "—", i["change"] or "—", i["size"]]
            out.append("| " + " | ".join(str(c).replace("|", "/").replace("\n", " ") for c in cells) + " |")
        sources = sorted({f"{i['source']}" + (f" (read on {i['checked']})" if i["checked"] else "")
                          for i in v["items"] if i["source"]})
        if sources:
            out += ["", "Read on: " + "; ".join(sources) + "."]
        out.append("")
    return "\n".join(out)


@app.command()
def main(
    manuscript: Annotated[Path, typer.Argument(exists=True, dir_okay=False,
                                               help="The manuscript, Markdown or LaTeX")],
    top3: Annotated[Optional[Path], typer.Option(
        exists=True, dir_okay=False,
        help="manuscript-journal-select's top3.json: the venues, their article types and the changes judged from "
             "the rules a script cannot read")] = None,
    venue: Annotated[Optional[list[str]], typer.Option(
        help="A venue key instead of top3.json; repeatable")] = None,
    record: Annotated[Optional[Path], typer.Option(
        exists=True, dir_okay=False,
        help="The manuscript record: its venue facts, the study design and the conditions checked against the "
             "manuscript; without --top3 or --venue, the first three rungs of its journal ladder")] = None,
    format: Annotated[Format, typer.Option(help="md for the authors, json for the dashboard")] = Format.md,
) -> None:
    """The major changes each recommended journal would ask of the manuscript, measured."""
    entries: list[dict[str, Any]] = []
    if top3 is not None:
        doc = json.loads(top3.read_text(encoding="utf-8"))
        if isinstance(doc, dict):
            doc = doc.get("journals") or doc.get("top3") or []
        entries = [e for e in doc if isinstance(e, dict) and e.get("key")]
    entries += [{"key": k} for k in venue or [] if k not in {e["key"] for e in entries}]
    if not entries and record is not None:
        entries = [{"key": k} for k in venues.recorded_ladder(record, False)[:3]]
    if not entries:
        raise typer.BadParameter("name the venues: --top3 FILE, --venue KEY, or a --record with a journal ladder")
    _, catalogue = venues.load_venues()
    _, facts = venues.load_record(record)
    context = venues.record_context(record)
    catalogue = venues.with_conditions(venues.with_facts(catalogue, facts), context["conditions"])
    unknown = [e["key"] for e in entries if e["key"] not in catalogue]
    if unknown:
        raise typer.BadParameter(f"unknown venue keys: {', '.join(unknown)}")
    m = measure(manuscript)
    document = {"manuscript": m["file"], "measured": m, "measured_text": measured_text(m),
                "venues": [estimate(m, {**catalogue[e["key"]], "key": e["key"]}, e, context["designs"] or [])
                           for e in entries]}
    typer.echo(json.dumps(document, ensure_ascii=False, indent=2) if format == Format.json else markdown(document))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # names and quotes print in UTF-8 on every platform
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
