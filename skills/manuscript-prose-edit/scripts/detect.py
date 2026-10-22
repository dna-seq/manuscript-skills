# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pyyaml>=6", "httpx>=0.27", "huggingface_hub>=0.34", "torch>=2.4",
#                 "transformers>=4.48"]
# ///
"""Score a manuscript with a free AI-text detector, window by window, as a hint for a human reread.

A detector score is not evidence of authorship and not a target to push down (references/detector-evidence.md).
Each window gets one of three states: flagged, not flagged, or not assessed (too short, or the call failed).
With --sample (the authors' own earlier writing, ideally from before 2023), the flag threshold is the
highest score any sample window received; without it, the detector's documented threshold is used and
the report says the result is uncalibrated.

    uv run --script detect.py PAPER.md                                   # local ModernBERT
    uv run --script detect.py PAPER.md --detector tropa --sample my_2021_paper.md
    uv run --script detect.py PAPER.md --detector aiornot --allow-remote # hosted; the text leaves the machine

Run `detector_setup.py check` first to see what is available here.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Annotated, Any, Callable, Optional

import httpx
import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)
HERE = Path(__file__).resolve().parent

MIN_WORDS, MAX_WORDS = 120, 400
DEFAULT_THRESHOLDS = {"modernbert": 0.5, "tropa": 0.976}  # tropa: its card's 0.5% false-positive operating point
REMOTE = {"aiornot"}


def _load_profile() -> ModuleType:
    spec = importlib.util.spec_from_file_location("style_profile", HERE.parents[1] / "manuscript-deslop" / "scripts" / "style_profile.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["style_profile"] = module
    spec.loader.exec_module(module)
    return module


def windows(text: str, latex: bool, profile: ModuleType) -> list[dict[str, Any]]:
    """Consecutive prose paragraphs merged into windows of MIN_WORDS to MAX_WORDS words (references excluded)."""
    out: list[dict[str, Any]] = []
    current: list[tuple[int, str]] = []
    count = 0

    cleaned = profile.clean(text, latex)
    heads = profile.headings(cleaned)

    def flush() -> None:
        nonlocal current, count
        if current:
            out.append({"line": current[0][0], "end_line": current[-1][0], "words": count,
                        "section": profile.section_at(heads, current[0][0]),
                        "text": "\n\n".join(p for _, p in current)})
        current, count = [], 0

    for line, para in profile.paragraphs(cleaned):
        n = len(profile.WORD.findall(para))
        if count and count + n > MAX_WORDS:
            flush()
        current.append((line, para))
        count += n
        if count >= MIN_WORDS:
            flush()
    flush()
    return out


def score_windows(wins: list[dict[str, Any]], scorer: Callable[[str], float],
                  threshold: float, calibrated: bool) -> list[dict[str, Any]]:
    rows = []
    for w in wins:
        row = {k: w[k] for k in ("line", "end_line", "words")} | {"section": w.get("section", "")}
        if w["words"] < 50:
            row.update(state="not assessed", score=None, reason="under 50 words")
        else:
            try:
                score = float(scorer(w["text"]))
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:  # a failed call is not a pass
                row.update(state="not assessed", score=None, reason=f"{type(exc).__name__}: {exc}"[:120])
            else:
                row.update(state="flagged" if score > threshold else "not flagged", score=round(score, 4))
        row["calibrated"] = calibrated
        row["excerpt"] = w["text"][:140]
        rows.append(row)
    return rows


# --- detectors ------------------------------------------------------------------------------------------------
# torch and transformers are imported inside the loaders: they take seconds to import and are not needed for the
# hosted detector or for --help.

def _device() -> str:
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_modernbert() -> Callable[[str], float]:
    """rasbt/ai-text-detector-modernbert, following its model card (temperature-scaled softmax, label 'ai')."""
    import torch
    from huggingface_hub import hf_hub_download
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    repo = "rasbt/ai-text-detector-modernbert"
    meta = json.loads(Path(hf_hub_download(repo, "detector-config.json")).read_text(encoding="utf-8"))
    device = _device()
    tokenizer = AutoTokenizer.from_pretrained(repo)
    model = AutoModelForSequenceClassification.from_pretrained(repo).to(device).eval()

    def score(text: str) -> float:
        inputs = tokenizer(text, truncation=True, max_length=meta["max_length"], return_tensors="pt").to(device)
        with torch.inference_mode():
            probs = (model(**inputs).logits / meta["temperature"]).float().softmax(dim=-1)
        return probs[0, meta["label_mapping"]["ai"]].item()

    return score


def load_tropa() -> Callable[[str], float]:
    """tropa-mini, following its model card: mean-pooled encoder plus a 4-way head; ai_score = 1 - P(human)."""
    import torch
    import torch.nn as nn
    from transformers import AutoConfig, AutoModel, AutoTokenizer, PreTrainedModel

    class AIDetectionModel(PreTrainedModel):
        config_class = AutoConfig
        _tied_weights_keys: list[str] = []

        @property
        def all_tied_weights_keys(self) -> dict:
            return {}

        def __init__(self, config: Any) -> None:
            super().__init__(config)
            self.model = AutoModel.from_config(config)
            self.classifier = nn.Linear(config.hidden_size, getattr(config, "detector_num_labels", 1))

        def forward(self, input_ids: Any, attention_mask: Any = None, **kwargs: Any) -> Any:
            h = self.model(input_ids, attention_mask=attention_mask)[0]
            mask = attention_mask.unsqueeze(-1).float()
            return self.classifier((h * mask).sum(1) / mask.sum(1))

    repo = "wasitaigeneratedcom/ai-text-detector-small"
    device = _device()
    tokenizer = AutoTokenizer.from_pretrained(repo)
    model = AIDetectionModel.from_pretrained(repo).to(device).eval()

    def score(text: str) -> float:
        enc = tokenizer(text, truncation=True, max_length=768, return_tensors="pt").to(device)
        with torch.inference_mode():
            probs = torch.softmax(model(**enc), dim=-1)[0]
        return 1.0 - probs[0].item()

    return score


def load_aiornot() -> Callable[[str], float]:
    """AI or Not v2 text endpoint (free tier); needs AIORNOT_API_KEY."""
    key = os.environ.get("AIORNOT_API_KEY")
    if not key:
        raise typer.BadParameter("AIORNOT_API_KEY is not set. `detector_setup.py check` says where to get a key.")
    client = httpx.Client(timeout=60, headers={"Authorization": f"Bearer {key}"})

    def score(text: str) -> float:
        if len(text) < 250:
            raise ValueError("AI or Not needs at least 250 characters")
        r = client.post("https://api.aiornot.com/v2/text/sync", data={"text": text})
        r.raise_for_status()
        return float(r.json()["report"]["ai_text"]["confidence"])

    return score


LOADERS = {"modernbert": load_modernbert, "tropa": load_tropa, "aiornot": load_aiornot}


DETECTOR_NAMES = {"modernbert": "the ModernBERT detector, rasbt/ai-text-detector-modernbert",
                  "tropa": "tropa-mini, wasitaigeneratedcom/ai-text-detector-small",
                  "aiornot": "AI or Not, a hosted service"}
SMALL_NUMBERS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _count(n: int, one: str, many: str) -> str:
    return f"{SMALL_NUMBERS[n] if n < len(SMALL_NUMBERS) else n} {one if n == 1 else many}"


def _lines(r: dict[str, Any]) -> str:
    return f"line {r['line']}" if r["line"] == r["end_line"] else f"lines {r['line']} to {r['end_line']}"


def _why_not_scored(reason: str) -> str:
    if reason.startswith("under "):
        return f"the passage has fewer than {reason.split()[1]} words, too few to score"
    return f"the detector failed on it ({reason})"


def to_markdown(path: str, detector: str, rows: list[dict[str, Any]], threshold: float, calibrated: bool) -> str:
    profile = _load_profile()
    name = DETECTOR_NAMES.get(detector, detector)
    flagged = [r for r in rows if r["state"] == "flagged"]
    unscored = [r for r in rows if r["state"] == "not assessed"]
    below = [r for r in rows if r["state"] == "not flagged"]

    def where(r: dict[str, Any]) -> str:
        return profile.place(r.get("section", ""), _lines(r))

    def opening(r: dict[str, Any]) -> str:
        return "“" + " ".join(r["excerpt"].split())[:100] + "…”"

    basis = (f"{threshold:.3f}, the highest score the detector gave to the authors' own earlier writing" if calibrated
             else f"{threshold:.3f}, the threshold the detector's makers give. It was not calibrated on the authors' "
                  "own writing, which makes a flag even weaker evidence")
    out = [f"# Passages an AI-text detector flagged for rereading: {path}", "",
           f"Each passage got a score from 0 to 1: the detector's estimate that a language model wrote it ({name}). "
           f"A passage is flagged when its score is above {basis}.", "",
           f"Of {_count(len(rows), 'passage', 'passages')}, {len(flagged)} {'was' if len(flagged) == 1 else 'were'} "
           f"flagged, {len(below)} {'was' if len(below) == 1 else 'were'} below the threshold, and {len(unscored)} "
           f"could not be scored.", "",
           "A flag marks a passage to reread for stock phrasing and for claims the evidence does not carry. If the "
           "passage has neither, leave it as it is. A detector score is not evidence of who wrote the text, and "
           "editing only to lower it does not improve the paper.", "", "## Flagged passages", ""]
    out += [f"- In {where(r)}, the score was {r['score']:.3f}. The passage begins {opening(r)}" for r in flagged] or [
        "No passage was flagged."]
    if unscored:
        out += ["", "## Passages that could not be scored", ""]
        out += [f"- In {where(r)}, {_why_not_scored(str(r.get('reason', '')))}. The passage begins {opening(r)}"
                for r in unscored]
    if below:
        out += ["", "## Passages below the threshold", "", "| Where | Score | Begins |", "|---|---|---|"]
        out += [f"| {where(r)[:1].upper()}{where(r)[1:]} | {r['score']:.3f} | {opening(r)} |" for r in below]
    return "\n".join(out) + "\n"


@app.command()
def main(
    path: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    detector: Annotated[str, typer.Option(help=f"One of: {', '.join(LOADERS)}")] = "modernbert",
    sample: Annotated[Optional[list[Path]], typer.Option(exists=True, dir_okay=False,
                                                         help="The authors' own earlier writing, for calibration")] = None,
    allow_remote: Annotated[bool, typer.Option(help="Allow a hosted detector (the text leaves this machine)")] = False,
    json_out: Annotated[Optional[Path], typer.Option("--json", help="Write rows as JSON (input for the critic)")] = None,
    md_out: Annotated[Optional[Path], typer.Option("--md", help="Write the Markdown report here")] = None,
) -> None:
    if detector not in LOADERS:
        raise typer.BadParameter(f"There is no detector called {detector!r}; the detectors are "
                                 f"{', '.join(LOADERS)}.")
    if detector in REMOTE and not allow_remote:
        raise typer.BadParameter(f"{DETECTOR_NAMES.get(detector, detector)} sends the manuscript to a third party. "
                                 "Pass --allow-remote only when the authors agree to that for this text.")
    profile = _load_profile()
    scorer = LOADERS[detector]()
    wins = windows(path.read_text(encoding="utf-8"), path.suffix == ".tex", profile)
    threshold, calibrated = DEFAULT_THRESHOLDS.get(detector, 0.5), False
    if sample:
        sample_wins = [w for s in sample for w in windows(s.read_text(encoding="utf-8"), s.suffix == ".tex", profile)]
        sample_scores = [r["score"] for r in score_windows(sample_wins, scorer, 1.0, True) if r["score"] is not None]
        if sample_scores:
            threshold, calibrated = max(sample_scores), True
    rows = score_windows(wins, scorer, threshold, calibrated)
    if json_out:
        json_out.write_text(json.dumps({"detector": detector, "threshold": threshold, "calibrated": calibrated,
                                        "windows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    md = to_markdown(str(path), detector, rows, threshold, calibrated)
    if md_out:
        md_out.write_text(md, encoding="utf-8")
        typer.echo(f"Wrote the report to {md_out}.")
    else:
        typer.echo(md)


if __name__ == "__main__":
    app()
