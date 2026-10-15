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
        "label": "rasbt/ai-text-detector-modernbert (local)",
        "repo": "rasbt/ai-text-detector-modernbert", "kind": "local", "size_gb": 0.6, "ram_gb": 4,
        "needs": [], "licence": "Apache-2.0",
        "why": "trained on 2026 generators with arXiv, PLOS and PMC human text; runs on CPU; up to 8k tokens",
    },
    "tropa": {
        "label": "tropa-mini, wasitaigeneratedcom/ai-text-detector-small (local)",
        "repo": "wasitaigeneratedcom/ai-text-detector-small", "kind": "local", "size_gb": 1.7, "ram_gb": 6,
        "needs": [], "licence": "Apache-2.0",
        "why": "four classes including 'ai_edited'; documented threshold at 0.5% false positives; flags 15.6% of "
               "non-native TOEFL essays, so calibrate on the authors' own writing",
    },
    "editlens": {
        "label": "Pangram EditLens, pangram/editlens_roberta-large (local, gated)",
        "repo": "pangram/editlens_roberta-large", "kind": "local", "size_gb": 1.4, "ram_gb": 6,
        "needs": ["hf-token", "editlens-access"], "licence": "CC-BY-NC-SA (non-commercial)",
        "why": "estimates how much of a text was AI-edited, the real question for a polished manuscript; "
               "access needs manual approval by Pangram; detect.py does not run it yet",
    },
    "binoculars": {
        "label": "Binoculars (local, two Falcon-7B models)",
        "repo": "tiiuae/falcon-7b", "kind": "local", "size_gb": 28, "ram_gb": 64, "vram_gb": 30,
        "needs": [], "licence": "BSD-3 code; Falcon licence for the models",
        "why": "lowest false-positive rate on non-native academic text in Park et al. 2026 (0.1%); heavy; install "
               "from https://github.com/ahans30/Binoculars; detect.py does not run it",
    },
    "aiornot": {
        "label": "AI or Not API (hosted, free 1M words/month)",
        "repo": None, "kind": "remote", "size_gb": 0, "ram_gb": 0,
        "needs": ["aiornot-key"], "licence": "service terms",
        "why": "the only standing free hosted tier; the manuscript leaves the machine: get written confirmation "
               "that text is not stored or used for training before sending unpublished work",
    },
}

PAGES = {
    "hf-token": ("https://huggingface.co/settings/tokens",
                 "create a 'read' token, then run `hf auth login` (or set HF_TOKEN)"),
    "editlens-access": ("https://huggingface.co/pangram/editlens_roberta-large",
                        "log in and request access; approval is manual"),
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
            hardware.append(f"needs ~{d['ram_gb']} GB RAM")
        if d["kind"] == "local" and not env["cached"][key] and env["disk_free_gb"] < d["size_gb"] + 1:
            hardware.append(f"needs ~{d['size_gb']} GB free disk")
        vram = d.get("vram_gb")
        gpu = env["gpu"]
        if vram and not (gpu and gpu["vram_gb"] and gpu["vram_gb"] >= vram) and env["ram_gb"] < d["ram_gb"]:
            hardware.append(f"needs a {vram} GB GPU or {d['ram_gb']} GB RAM for CPU")
        out.append({"key": key, **{k: d[k] for k in ("label", "kind", "licence", "why")},
                    "cached": env["cached"][key], "missing": missing, "hardware": hardware,
                    "ready": not missing and not hardware})
    return out


def recommend(rows: list[dict[str, Any]], env: dict[str, Any]) -> str:
    local_ready = [r for r in rows if r["kind"] == "local" and r["ready"] and r["key"] in ("modernbert", "tropa")]
    first = local_ready[0]["key"] if local_ready else "modernbert"
    lines = [f"Recommended: `{first}` (local; the manuscript stays on this machine). Second opinion: "
             f"`{'tropa' if first == 'modernbert' else 'modernbert'}`."]
    if env["hf_token"]:
        lines.append("A Hugging Face token is configured: model downloads are authenticated, and the gated "
                     "EditLens model becomes possible once Pangram approves access.")
    else:
        lines.append("No Hugging Face token: the recommended models are public and download without one; a token "
                     "only raises rate limits and is needed for gated models (EditLens).")
    lines.append("Hosted `aiornot` only with the authors' explicit consent for this text (it leaves the machine).")
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
    typer.echo("# AI-text detector setup\n")
    typer.echo(f"- Hugging Face token: {'yes' if env['hf_token'] else 'no'}; AI or Not key: "
               f"{'yes' if env['aiornot_key'] else 'no'}")
    gpu_text = "none" if not gpu else gpu["name"] + (f" ({gpu['vram_gb']} GB)" if gpu["vram_gb"] else "")
    typer.echo(f"- GPU: {gpu_text}; RAM {env['ram_gb']} GB; free disk at the HF cache {env['disk_free_gb']} GB")
    typer.echo(f"- Can open a browser here: {'yes' if env['can_open_browser'] else 'no'}\n")
    typer.echo("| detector | kind | ready | downloaded | missing | note |\n|---|---|---|---|---|---|")
    for r in rows:
        typer.echo(f"| `{r['key']}` {r['label']} | {r['kind']} | {'yes' if r['ready'] else 'no'} | "
                   f"{'yes' if r['cached'] else 'no'} | {', '.join(r['missing'] + r['hardware']) or '-'} | {r['why']} |")
    typer.echo(f"\n{rec}")
    needed = sorted({m.split(" ")[0] for r in rows for m in r["missing"]})
    if needed:
        typer.echo("\nWhere to get what is missing (`detector_setup.py open NAME` opens the page, after the user agrees):")
        for name in needed:
            url, how = PAGES[name]
            typer.echo(f"- `{name}`: {url} ({how})")


@app.command("open")
def open_page(name: Annotated[str, typer.Argument(help=f"One of: {', '.join(PAGES)}")]) -> None:
    """Open the page where a token or access is obtained. Run only after the user has agreed."""
    if name not in PAGES:
        raise typer.BadParameter(f"unknown page {name!r}; known: {', '.join(PAGES)}")
    url, how = PAGES[name]
    opened = _can_open_browser() and webbrowser.open(url)
    typer.echo(f"{'Opened' if opened else 'Could not open a browser here; open it yourself'}: {url}\nThen: {how}")


if __name__ == "__main__":
    app()
