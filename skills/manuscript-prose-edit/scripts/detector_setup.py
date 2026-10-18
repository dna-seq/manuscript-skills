# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "huggingface_hub>=0.34", "psutil>=5.9"]
# ///
"""Which AI-text detectors can run here, what is missing, and where to get it.

Free detectors only. Local ones (Hugging Face models) keep the manuscript on this machine; the one hosted
free tier is opt-in. Prints a recommendation and, for anything missing, the page where the token or access
is obtained. `open` launches that page in a browser: run it only after the user agreed.

    uv run --script detector_setup.py check            # environment, recommendation, what is missing
    uv run --script detector_setup.py check --json
    uv run --script detector_setup.py open hf-token     # after asking: opens the token page
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Annotated, Any, Optional

import psutil
import typer
from huggingface_hub import constants, get_token

app = typer.Typer(add_completion=False, no_args_is_help=True)

GB = 1024 ** 3

# Free detectors, best first for scientific prose. Sizes are download sizes, approximate.
DETECTORS: dict[str, dict[str, Any]] = {
    "modernbert": {
        "label": "the ModernBERT detector, rasbt/ai-text-detector-modernbert",
        "repo": "rasbt/ai-text-detector-modernbert", "kind": "local", "size_gb": 0.6, "ram_gb": 4,
        "needs": [], "licence": "Apache-2.0",
        "why": "Trained on text from 2026 language models and on human text from arXiv, PLOS and PubMed Central. It "
               "runs on an ordinary processor and reads up to about 8,000 tokens at a time.",
    },
    "tropa": {
        "label": "tropa-mini, wasitaigeneratedcom/ai-text-detector-small",
        "repo": "wasitaigeneratedcom/ai-text-detector-small", "kind": "local", "size_gb": 1.7, "ram_gb": 6,
        "needs": [], "licence": "Apache-2.0",
        "why": "Tells apart human, AI-written, AI-edited and humanized text. Its makers give a threshold with 0.5% "
               "false positives, but it flags 15.6% of essays by non-native English writers (TOEFL essays), so "
               "calibrate it on the authors' own writing.",
    },
    "editlens": {
        "label": "Pangram EditLens, pangram/editlens_roberta-large (access needs approval)",
        "repo": "pangram/editlens_roberta-large", "kind": "local", "size_gb": 1.4, "ram_gb": 6,
        "needs": ["hf-token", "editlens-access"], "licence": "CC-BY-NC-SA (non-commercial)",
        "why": "Estimates how much of a text was edited by AI, which is the real question for a polished "
               "manuscript. Pangram approves access by hand, and detect.py does not run it yet.",
    },
    "binoculars": {
        "label": "Binoculars, two Falcon-7B models",
        "repo": "tiiuae/falcon-7b", "kind": "local", "size_gb": 28, "ram_gb": 64, "vram_gb": 30,
        "needs": [], "licence": "BSD-3 code; Falcon licence for the models",
        "why": "Had the fewest false positives on non-native academic writing in Park et al. 2026 (0.1%). It needs "
               "large models, is installed from https://github.com/ahans30/Binoculars, and detect.py does not run "
               "it.",
    },
    "aiornot": {
        "label": "the AI or Not API (free up to 1 million words a month)",
        "repo": None, "kind": "remote", "size_gb": 0, "ram_gb": 0,
        "needs": ["aiornot-key"], "licence": "service terms",
        "why": "The only free hosted service. The manuscript is sent to the company, so before sending unpublished "
               "work, get written confirmation that the text is not stored or used for training.",
    },
}

# What a missing item is, in words, for the report (the JSON keeps the short keys).
NEEDS_WORDS = {"hf-token": "a Hugging Face token", "editlens-access": "access approval from Pangram",
               "aiornot-key": "an AI or Not API key"}
KIND_WORDS = {"local": "on this machine", "remote": "on the company's server (the text is sent there)"}

PAGES = {
    "hf-token": ("https://huggingface.co/settings/tokens",
                 "create a 'read' token, then run `hf auth login` (or set HF_TOKEN)"),
    "editlens-access": ("https://huggingface.co/pangram/editlens_roberta-large",
                        "log in and request access; Pangram approves it by hand, and whether it was granted cannot be "
                        "checked offline"),
    "aiornot-key": ("https://www.aiornot.com/dashboard/api",
                    "sign up, copy the API key, then `export AIORNOT_API_KEY=...`"),
}


def _gpu() -> Optional[dict[str, Any]]:
    if shutil.which("nvidia-smi"):
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True)
        if out.returncode == 0 and out.stdout.strip():
            name, mem = out.stdout.strip().splitlines()[0].rsplit(",", 1)
            return {"name": name.strip(), "vram_gb": round(int(mem) / 1024, 1), "backend": "cuda"}
    if sys.platform == "darwin" and platform.machine() == "arm64":
        return {"name": "Apple silicon GPU", "vram_gb": None, "backend": "mps"}
    return None


def _can_open_browser() -> bool:
    if sys.platform in ("darwin", "win32"):
        return True
    if os.environ.get("BROWSER"):
        return True
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return has_display and bool(shutil.which("xdg-open"))


def _cached(repo: Optional[str]) -> bool:
    if not repo:
        return False
    return (Path(constants.HF_HUB_CACHE) / f"models--{repo.replace('/', '--')}").exists()


def environment() -> dict[str, Any]:
    cache = Path(constants.HF_HUB_CACHE)
    probe = cache if cache.exists() else cache.parent if cache.parent.exists() else Path.home()
    return {
        "hf_token": get_token() is not None,
        "aiornot_key": bool(os.environ.get("AIORNOT_API_KEY")),
        "gpu": _gpu(),
        "ram_gb": round(psutil.virtual_memory().total / GB, 1),
        "hf_cache": str(cache),
        "disk_free_gb": round(shutil.disk_usage(probe).free / GB, 1),
        "can_open_browser": _can_open_browser(),
        "cached": {k: _cached(d["repo"]) for k, d in DETECTORS.items()},
    }


def assess(env: dict[str, Any]) -> list[dict[str, Any]]:
    """Each detector with what is ready and what is missing on this machine."""
    out = []
    for key, d in DETECTORS.items():
        missing: list[str] = []
        if "hf-token" in d["needs"] and not env["hf_token"]:
            missing.append("hf-token")
        if "editlens-access" in d["needs"]:
            missing.append("editlens-access (cannot be checked offline)")
        if "aiornot-key" in d["needs"] and not env["aiornot_key"]:
            missing.append("aiornot-key")
        hardware = []
        if d["ram_gb"] and env["ram_gb"] < d["ram_gb"]:
            hardware.append(f"about {d['ram_gb']} GB of memory")
        if d["kind"] == "local" and not env["cached"][key] and env["disk_free_gb"] < d["size_gb"] + 1:
            hardware.append(f"about {d['size_gb']} GB of free disk space")
        vram = d.get("vram_gb")
        gpu = env["gpu"]
        if vram and not (gpu and gpu["vram_gb"] and gpu["vram_gb"] >= vram) and env["ram_gb"] < d["ram_gb"]:
            hardware.append(f"a graphics card with {vram} GB of memory, or {d['ram_gb']} GB of memory to run on the "
                            "processor")
        out.append({"key": key, **{k: d[k] for k in ("label", "kind", "licence", "why")},
                    "cached": env["cached"][key], "missing": missing, "hardware": hardware,
                    "ready": not missing and not hardware})
    return out


def recommend(rows: list[dict[str, Any]], env: dict[str, Any]) -> str:
    local_ready = [r for r in rows if r["kind"] == "local" and r["ready"] and r["key"] in ("modernbert", "tropa")]
    first = local_ready[0]["key"] if local_ready else "modernbert"
    second = "tropa" if first == "modernbert" else "modernbert"
    lines = [f"Recommended: {DETECTORS[first]['label']} (`{first}`), which runs on this "
             f"machine, so the manuscript stays here. For a second opinion, use "
             f"{DETECTORS[second]['label']} (`{second}`)."]
    if env["hf_token"]:
        lines.append("A Hugging Face token is configured, so model downloads are authenticated, and the EditLens "
                     "model can be used once Pangram approves access.")
    else:
        lines.append("No Hugging Face token is configured. The recommended models are public and download without "
                     "one; a token only raises download limits and is needed for models that require approval "
                     "(EditLens).")
    lines.append("The hosted AI or Not service (`aiornot`) sends the text to the company; use it only when the "
                 "authors agree to that for this text.")
    return " ".join(lines)


@app.command()
def check(json_out: Annotated[bool, typer.Option("--json", help="Print JSON")] = False) -> None:
    """Report the environment, each free detector's readiness, and a recommendation."""
    env = environment()
    rows = assess(env)
    rec = recommend(rows, env)
    if json_out:
        typer.echo(json.dumps({"environment": env, "detectors": rows, "recommendation": rec,
                               "pages": {k: v[0] for k, v in PAGES.items()}}, indent=2))
        return
    gpu = env["gpu"]
    typer.echo("# Which AI-text detectors can run here\n")
    typer.echo(f"A Hugging Face token is {'configured' if env['hf_token'] else 'not configured'}, and an AI or Not "
               f"API key is {'set' if env['aiornot_key'] else 'not set'}.")
    gpu_text = ("no graphics card that the detectors can use" if not gpu else
                f"a graphics card ({gpu['name']}" + (f", {gpu['vram_gb']} GB" if gpu["vram_gb"] else "") + ")")
    typer.echo(f"This machine has {gpu_text}, {env['ram_gb']} GB of memory and {env['disk_free_gb']} GB of free disk "
               f"space where Hugging Face stores models. A browser {'can' if env['can_open_browser'] else 'cannot'} "
               "be opened from here.\n")
    typer.echo("| Detector | Where it runs | Ready here | Downloaded | What is missing | Notes |\n"
               "|---|---|---|---|---|---|")
    for r in rows:
        missing = [NEEDS_WORDS.get(m.split(" ")[0], m) for m in r["missing"]] + r["hardware"]
        typer.echo(f"| {_sentence_start(r['label'])} (`{r['key']}`) | {KIND_WORDS.get(r['kind'], r['kind'])} | "
                   f"{'yes' if r['ready'] else 'no'} | {'yes' if r['cached'] else 'no'} | "
                   f"{_listed(missing) if missing else 'nothing'} | {r['why']} |")
    typer.echo(f"\n{rec}")
    needed = sorted({m.split(" ")[0] for r in rows for m in r["missing"]})
    if needed:
        typer.echo("\nWhere to get what is missing (`detector_setup.py open NAME` opens the page, once the user "
                   "agrees):")
        for name in needed:
            url, how = PAGES[name]
            typer.echo(f"- {NEEDS_WORDS[name][:1].upper()}{NEEDS_WORDS[name][1:]} (`{name}`): {url}. {how[:1].upper()}"
                       f"{how[1:]}.")


def _sentence_start(label: str) -> str:
    """'The ModernBERT detector, ...' at the start of a cell; a product name such as 'tropa-mini' keeps its case."""
    return "The" + label[3:] if label.startswith("the ") else label


def _listed(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


@app.command("open")
def open_page(name: Annotated[str, typer.Argument(help=f"One of: {', '.join(PAGES)}")]) -> None:
    """Open the page where a token or access is obtained. Run only after the user has agreed."""
    if name not in PAGES:
        raise typer.BadParameter(f"There is no page called {name!r}; the pages are {', '.join(PAGES)}.")
    url, how = PAGES[name]
    opened = _can_open_browser() and webbrowser.open(url)
    typer.echo(f"Opened {url} in a browser." if opened else f"Could not open a browser here; open {url} yourself.")
    typer.echo(f"Then {how}.")


if __name__ == "__main__":
    app()
