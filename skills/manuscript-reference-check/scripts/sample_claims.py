# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Draw a seeded random sample of the cited sentences the claim-support check did not choose by priority.

The priority classes (claims the conclusions rest on, the Abstract, borrowed numbers, priority and absence claims,
claims another skill flagged) are always checked in full. The other cited sentences are many and look alike; a
random sample of them, checked like the rest, gives an estimate for the ones left unchecked, which support.py
reports with its interval. The draw is seeded (by default from the manuscript's own sha256), so anyone can repeat it.

    uv run --script sample_claims.py PAPER.md --claims claims.yaml --out claims-sample.yaml [--size 10] [--seed 7]
    uv run --script sample_claims.py PAPER.md --claims claims.yaml --count       # the coverage counts only

The output is a claims file of its own: each drawn sentence as a claim (`priority: sample`, ids S1, S2, ...) with
its location and citation markers, and a `sample` block (seed, how many cited sentences the manuscript has, how
many the priority claims took, how many were left, how many were drawn). Locate each sentence's passage in its
source and fill `quote` and `source` as for any claim, run support.py on it, then record the reading's outcome in
`outcome` (confirmed, partial, rejected or blocked).

Cited sentences are found with the claim guard's sentence splitter and citation patterns (manuscript-prose-edit's
guard.py): numbered "[12]", author-year "(Duncan et al., 2019)", narrative "Duncan et al. (2019)", LaTeX `\\cite{}`
and Pandoc `[@key]`. The reference list itself is not counted. A sentence already in the claims file (its `claim`
holds the sentence, or the sentence holds it) is a priority claim, not a candidate.

Exit codes: 0 written; 2 usage error (no cited sentence left to draw from, an output that exists).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import re
import sys
import unicodedata
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
import yaml

app = typer.Typer(add_completion=False, no_args_is_help=True)

GUARD = Path(__file__).resolve().parents[2] / "manuscript-prose-edit" / "scripts" / "guard.py"
REFERENCE_LIST = re.compile(r"^(?:references|bibliography|literature cited|works cited|reference list)$", re.IGNORECASE)
DEFAULT_SIZE = 10


def _guard() -> Any:
    if "sample_guard" not in sys.modules:
        spec = importlib.util.spec_from_file_location("sample_guard", GUARD)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules["sample_guard"] = module  # dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
    return sys.modules["sample_guard"]


def folded(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[^\w%.]+", " ", text).split())


def cited_sentences(text: str) -> list[dict]:
    """Every sentence of the manuscript that carries a citation, in reading order, with its line, section and
    citation markers; the reference list is left out."""
    guard = _guard()
    title = guard.document_title(text)
    out = []
    for s in guard.segment(text):
        top = guard._top_section(s, title) or ""
        numbered = guard.NUMBERED_HEADING.match(top)
        if REFERENCE_LIST.match((numbered.group(2) if numbered else top).strip()):
            continue
        markers = sorted(guard.sentence_tokens(s.text)["citation"])
        if markers:
            section = s.section[len(title) + 3:] if title and s.section.startswith(title + " > ") else s.section
            out.append({"line": s.line, "section": section.replace(" > ", ", "), "sentence": s.text,
                        "markers": markers})
    return out


def chosen_claims(path: Optional[Path]) -> list[str]:
    """The sentences of a claims file, folded, so that the priority claims are not drawn again."""
    if path is None:
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.suffix.lower() != ".json" else \
        json.loads(path.read_text(encoding="utf-8"))
    items = data.get("claims") if isinstance(data, dict) else data
    return [folded(str(c.get("claim") or "")) for c in items or [] if isinstance(c, dict) and c.get("claim")]


def is_chosen(sentence: str, chosen: list[str]) -> bool:
    s = folded(sentence)
    return any(c and (c in s or s in c) and min(len(c), len(s)) >= 20 for c in chosen)


def draw(text: str, chosen: list[str], size: int, seed: int) -> tuple[list[dict], dict]:
    """The drawn sentences, in reading order, and the counts behind them."""
    cited = cited_sentences(text)
    rest = [c for c in cited if not is_chosen(c["sentence"], chosen)]
    picked = sorted(random.Random(seed).sample(range(len(rest)), min(size, len(rest))))
    counts = {"seed": seed, "cited_sentences": len(cited), "by_priority": len(cited) - len(rest),
              "population": len(rest), "drawn": len(picked)}
    return [rest[i] for i in picked], counts


@app.command()
def main(
    manuscript: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="The manuscript (Markdown, LaTeX or text)")],
    claims: Annotated[Optional[Path], typer.Option(exists=True, dir_okay=False,
                                                   help="The claims file with the priority claims")] = None,
    out: Annotated[Optional[Path], typer.Option(help="Where to write the sample's claims file")] = None,
    size: Annotated[int, typer.Option(min=1, help="How many sentences to draw")] = DEFAULT_SIZE,
    seed: Annotated[Optional[int], typer.Option(help="The seed; default: from the manuscript's sha256")] = None,
    count: Annotated[bool, typer.Option("--count", help="Print the coverage counts and write nothing")] = False,
) -> None:
    text = manuscript.read_text(encoding="utf-8")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    seed = int(sha[:8], 16) if seed is None else seed
    drawn, counts = draw(text, chosen_claims(claims), size, seed)
    if count:
        typer.echo(json.dumps({k: v for k, v in counts.items() if k not in ("seed", "drawn")}, indent=2))
        return
    if out is None:
        raise typer.BadParameter("give --out for the sample's claims file, or --count for the counts only")
    if out.exists():
        raise typer.BadParameter(f"{out} exists; write the next attempt under a new name.")
    if not drawn:
        raise typer.BadParameter("every cited sentence is already a priority claim: there is nothing to sample")
    sample = {"manuscript": manuscript.name, "manuscript_sha256": sha, **counts}
    entries = [{"id": f"S{n}", "location": f"{manuscript.name}:{d['line']}" + (f" ({d['section']})" if d["section"] else ""),
                "claim": d["sentence"], "reference": "; ".join(d["markers"]), "priority": "sample"}
               for n, d in enumerate(drawn, 1)]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("# A seeded random sample of the cited sentences the priority classes did not take. For each one,\n"
                   "# locate the passage, fill quote and source, run support.py, then record outcome.\n"
                   + yaml.safe_dump({"sample": sample, "claims": entries}, sort_keys=False, allow_unicode=True),
                   encoding="utf-8")
    typer.echo(json.dumps({"out": str(out.resolve()), **counts}, indent=2))


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app()
