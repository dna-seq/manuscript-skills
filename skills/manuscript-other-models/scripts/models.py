#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12"]
# ///
"""Run one simulated referee, reader, critic or skeptic on another AI model, through a command-line agent the
authors already use (Claude Code, Codex CLI, Gemini CLI) and its own sign-in, not an API key: provider key
variables (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, GOOGLE_API_KEY and the like) are removed from the
environment each CLI is started with, and seat-run.json names the ones removed, never their values.

    uv run --script models.py detect [--json]              # the CLIs installed here, the host, their models
    uv run --script models.py check codex [--model M]      # one tiny call: is it signed in, is the model accepted?
    uv run --script models.py run codex --workspace WS --brief BRIEF.md [--model M] [--effort high] [--timeout 3600]

`run` copies WS to a new temporary folder outside every project and starts a new session of the CLI there
(never a resumed or forked one), with BRIEF as its whole prompt. The session may write only inside that copy:
Claude Code gets the file tools and no shell, Codex its workspace-write sandbox without network, Gemini its
auto_edit mode. Reads are limited by the CLI only for Claude Code, which refuses a file outside the copy; Codex
and Gemini limit writes, not reads, so for them the brief's instruction to read nothing else is the only read
boundary. seat-run.json records which (read_isolation: enforced or instruction-only). When it ends, the files it created are copied back into WS; a file it was given
and changed is reported and left as it was. Its last message is saved as WS/seat-answer.md, and
WS/seat-run.json records the CLI and its version, the model, the exact command, the exit status, the
duration, the files returned, and where the prompt as sent, the CLI's output and its errors were saved.
The copy is then deleted. Working in a copy keeps the project's own instructions (CLAUDE.md, AGENTS.md,
GEMINI.md), its git history and the agent's memory of the project away from the seat. The authors' own setup in
their home folder is left out where the CLI allows it: Claude Code reads no user settings (`--setting-sources
project,local`, so not the user's CLAUDE.md, hooks or plugins), and Codex no user config (`--ignore-user-config`:
not its plugins, skills or MCP servers; its configured model and effort are named on the command line instead).
Gemini CLI still loads the user's GEMINI.md. seat-run.json says which (`standing_instructions`).

The path of WS written in BRIEF (as the system writes it, or with forward slashes) is replaced by the copy's
path, so a brief that names its workspace works; otherwise the brief is sent as it is.

Exit codes: 0 the session finished and answered; 1 it ran but failed or gave no answer (seat-run.json says
why); 2 bad arguments, an unknown or missing CLI, or a workspace a seat already ran in; 3 it timed out.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)

RECORD, ANSWER = "seat-run.json", "seat-answer.md"
MODEL_NAME = re.compile(r"[\w.:@/\[\]-]+")
PING = "Reply with the single word READY and nothing else."
WINDOWS = os.name == "nt"

# Provider keys and tokens: with one of these set, a CLI can bill an API account instead of the authors' own
# sign-in. None is passed to any CLI. Only the names of those removed are recorded.
CREDENTIALS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "CODEX_API_KEY", "AZURE_OPENAI_API_KEY",
               "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS")
# Not secrets, but each sends a CLI's requests another way than its own sign-in (a gateway, a cloud account). They
# are kept, since the authors may rely on them, and named in the record.
ROUTE_SETTINGS = {"claude": ("ANTHROPIC_BASE_URL", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"),
                  "codex": ("OPENAI_BASE_URL",), "gemini": ("GOOGLE_GENAI_USE_VERTEXAI",)}


@dataclass(frozen=True)
class Cli:
    key: str
    name: str
    family: str  # the model family its subscription reaches
    host_env: tuple[str, ...]  # variables a session of this CLI sets for the commands it runs
    efforts: tuple[str, ...] = ()
    models_hint: str = ""
    # "enforced": the CLI itself refuses to read outside the copy; "instruction-only": it limits writes, and only the
    # brief's instruction keeps its reads inside the copy.
    read_isolation: str = "instruction-only"
    # What of the authors' own setup reaches a seat started by `run`: their instructions, memory and plugins.
    instructions: str = "loaded"


CLIS = {
    "claude": Cli("claude", "Claude Code", "Anthropic", ("CLAUDECODE",), ("low", "medium", "high", "xhigh", "max"),
                  "an alias (fable, opus, sonnet, haiku) or a full model id", "enforced",
                  "left out: no project folder above the copy (no CLAUDE.md, no memory of the project), and no user "
                  "settings (not the user's CLAUDE.md, hooks or plugins)"),
    "codex": Cli("codex", "Codex CLI", "OpenAI", ("CODEX_THREAD_ID", "CODEX_SESSION_ID"),
                 ("minimal", "low", "medium", "high", "xhigh"), instructions=(
                     "left out: no project folder above the copy (no AGENTS.md), and no user config (not its plugins, "
                     "skills or MCP servers); the user's own AGENTS.md in CODEX_HOME, if there is one, still loads")),
    "gemini": Cli("gemini", "Gemini CLI", "Google", ("GEMINI_CLI",), (), "a Gemini model id, e.g. gemini-2.5-pro",
                  instructions="partly: no project folder above the copy, but the user's own GEMINI.md still loads"),
}
READS = {"enforced": "reads limited to the copy by the CLI",
         "instruction-only": "writes limited to the copy by the CLI; reads only by the brief's instruction"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def host() -> str | None:
    """The CLI this command runs inside. Codex and Gemini are checked first: a session started from Claude Code
    inherits CLAUDECODE, so the innermost host is the one whose own variable is set."""
    for key in ("codex", "gemini", "claude"):
        if any(os.environ.get(var) for var in CLIS[key].host_env):
            return key
    return None


def version(binary: str) -> str:
    try:
        done = subprocess.run([binary, "--version"], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return (done.stdout or done.stderr).strip().splitlines()[0] if (done.stdout or done.stderr).strip() else "unknown"


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def codex_effort() -> str | None:
    """Codex's configured reasoning effort, which a seat run without the user config would otherwise lose."""
    try:
        return tomllib.loads((codex_home() / "config.toml").read_text(encoding="utf-8")).get("model_reasoning_effort")
    except (OSError, tomllib.TOMLDecodeError):
        return None


def codex_models() -> tuple[str | None, list[str]]:
    """Codex's configured default model and the models it lists for this account (its own cache)."""
    default = None
    try:
        default = tomllib.loads((codex_home() / "config.toml").read_text(encoding="utf-8")).get("model")
    except (OSError, tomllib.TOMLDecodeError):
        pass
    try:
        cache = json.loads((codex_home() / "models_cache.json").read_text(encoding="utf-8"))
        listed = [m["slug"] for m in cache.get("models", []) if m.get("visibility") == "list" and m.get("slug")]
    except (OSError, ValueError, AttributeError, TypeError):
        listed = []
    return default, listed


def codex_cache_version() -> str:
    """The Codex CLI version that wrote its model list: an older CLI is offered fewer, older models."""
    try:
        return str(json.loads((codex_home() / "models_cache.json").read_text(encoding="utf-8")).get("client_version") or "")
    except (OSError, ValueError, AttributeError):
        return ""


# ChatGPT plans of a work workspace. A personal plan (free, plus, pro, go) is offered fewer and older models in Codex.
WORK_PLANS = ("business", "team", "enterprise", "edu")


def codex_account() -> dict[str, str]:
    """How Codex CLI is signed in, from its auth.json and without any secret: `auth_mode` (chatgpt, or apikey for a
    key it stores), and for a ChatGPT sign-in the plan its token names and whether that is a work workspace or a
    personal plan. Only the token's claims are decoded; the token itself is never kept or shown."""
    try:
        auth = json.loads((codex_home() / "auth.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(auth, dict):
        return {}
    out = {"auth_mode": str(auth.get("auth_mode") or ("apikey" if auth.get("OPENAI_API_KEY") else ""))}
    token = str((auth.get("tokens") or {}).get("id_token") or "")
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        plan = str((claims.get("https://api.openai.com/auth") or {}).get("chatgpt_plan_type") or "")
    except (IndexError, ValueError, TypeError, AttributeError):
        plan = ""
    if plan:
        out |= {"plan": plan, "workspace": "work" if any(word in plan.lower() for word in WORK_PLANS) else "personal"}
    return out


def codex_account_line(account: dict[str, str]) -> str:
    if not account:
        return "Codex sign-in: not found (codex login)."
    if account.get("auth_mode") == "apikey":
        return "Codex sign-in: an API key it stores (codex login --with-api-key); the key's account is billed."
    if account.get("workspace") == "work":
        return f"Codex sign-in: ChatGPT, a work workspace (plan {account['plan']})."
    if account.get("workspace") == "personal":
        return (f"Codex sign-in: ChatGPT, a personal plan ({account['plan']}), which Codex offers fewer and older "
                "models than a work workspace. Where the authors have a work workspace, they sign in to it: "
                "codex logout, then codex login, choosing the work workspace.")
    return f"Codex sign-in: {account.get('auth_mode') or 'unknown'}."


# Codex's words when the server will not run a model for this CLI or this sign-in.
REFUSED_MODEL = re.compile(r"not supported when using Codex|model_not_found|model .* (?:does not exist|not supported)",
                           re.IGNORECASE)


def codex_refusal_advice(error: str, cli_version: str) -> str:
    """What to do when Codex refused a model. Both causes seen so far leave a weaker model looking like the only
    choice: a CLI older than the model (its error blames "a ChatGPT account"), and a personal plan."""
    if not REFUSED_MODEL.search(error):
        return ""
    return (f"Codex refused this model. Before choosing an older one, update Codex CLI (this one is "
            f"{cli_version or 'of unknown version'}; codex update, or the package manager it came from): a CLI too old "
            f"for a model is refused with the words \"not supported when using Codex with a ChatGPT account\" even on "
            f"a work workspace. Then check the sign-in below. A weaker model is the authors' choice, never a silent "
            f"fallback.")


# --- how each CLI is started, and how its answer is read ------------------------------------------------------

@dataclass
class Outcome:
    answer: str = ""
    error: str = ""
    models: list[str] = field(default_factory=list)
    session: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


def claude_argv(model: str | None, effort: str | None, last: Path) -> list[str]:
    # File tools only, no shell; acceptEdits lets it write inside the copy, and a read or write outside it is refused
    # in print mode. No MCP servers, skills or saved session.
    # No user settings: the authors' CLAUDE.md, hooks and plugins stay out of a seat (their sign-in does not live
    # there). Name the model: the user's default lives in those settings.
    argv = ["claude", "-p", "--output-format", "json", "--tools", "Read,Glob,Grep,Write,Edit",
            "--permission-mode", "acceptEdits", "--strict-mcp-config", "--disable-slash-commands",
            "--no-session-persistence", "--setting-sources", "project,local"]
    return argv + (["--model", model] if model else []) + (["--effort", effort] if effort else [])


def claude_read(stdout: str, stderr: str, last: Path) -> Outcome:
    data: Any = None
    for text in (stdout.strip(), (stdout.strip().splitlines() or [""])[-1]):
        try:
            data = json.loads(text)
            break
        except json.JSONDecodeError:
            continue
    if not isinstance(data, dict):
        return Outcome(error="Claude Code did not return JSON: " + stdout.strip()[:300])
    result = str(data.get("result") or "")
    out = Outcome(models=list(data.get("modelUsage") or {}), session=str(data.get("session_id") or ""),
                  usage={k: data[k] for k in ("total_cost_usd", "num_turns", "duration_ms") if k in data})
    if data.get("is_error") or data.get("subtype") not in (None, "success"):
        out.error = result or str(data.get("subtype") or "Claude Code reported an error.")
    else:
        out.answer = result
    return out


def codex_argv(model: str | None, effort: str | None, last: Path) -> list[str]:
    # workspace-write: it may write inside the copy (and its temporary folder), with no network for commands.
    # No user config: the authors' plugins, skills and MCP servers stay out of a seat; auth still comes from
    # CODEX_HOME, and the configured model and effort are passed by `session`.
    argv = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "--ignore-user-config", "-s", "workspace-write",
            "--json", "-o", str(last)]
    argv += ["-m", model] if model else []
    argv += ["-c", f"model_reasoning_effort={effort}"] if effort else []
    return argv + ["-"]


def codex_read(stdout: str, stderr: str, last: Path) -> Outcome:
    out = Outcome()
    errors = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = event.get("type")
        if kind == "thread.started":
            out.session = str(event.get("thread_id") or "")
        elif kind == "turn.completed":
            out.usage = event.get("usage") or {}
        elif kind in ("error", "turn.failed"):
            message = event.get("message") or (event.get("error") or {}).get("message") or ""
            try:  # Codex wraps the provider's JSON error in a string
                message = json.loads(message)["error"]["message"]
            except (ValueError, KeyError, TypeError):
                pass
            if message and message not in errors:
                errors.append(str(message))
    out.answer = last.read_text(encoding="utf-8").strip() if last.is_file() else ""
    if not out.answer:
        out.error = "; ".join(errors) or "Codex gave no final message."
    return out


def gemini_argv(model: str | None, effort: str | None, last: Path) -> list[str]:
    # auto_edit approves its file edits; a headless run has no one to approve a shell command, so it cannot run one.
    return ["gemini", "-o", "json", "--approval-mode", "auto_edit"] + (["-m", model] if model else [])


def gemini_read(stdout: str, stderr: str, last: Path) -> Outcome:
    data: Any = None
    for stream in (stdout, stderr):  # its answer comes on stdout, its error object on stderr after the startup log
        start = re.search(r"^\{", stream, re.MULTILINE)
        try:
            data = json.loads(stream[start.start():]) if start else None
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict):
            break
    if not isinstance(data, dict):
        return Outcome(error="Gemini CLI did not return JSON: " + stdout.strip()[:300])
    out = Outcome(session=str(data.get("session_id") or ""),
                  models=list((data.get("stats") or {}).get("models") or {}))
    if data.get("error"):
        out.error = str(data["error"].get("message") if isinstance(data["error"], dict) else data["error"])
    else:
        out.answer = str(data.get("response") or "")
    return out


ADAPTERS: dict[str, tuple[Callable[[str | None, str | None, Path], list[str]], Callable[[str, str, Path], Outcome]]] = {
    "claude": (claude_argv, claude_read),
    "codex": (codex_argv, codex_read),
    "gemini": (gemini_argv, gemini_read),
}


def environment(key: str) -> dict[str, str]:
    """The environment a CLI is started with: the session's own, without provider keys, so that the CLI uses its
    own sign-in."""
    env = {name: value for name, value in os.environ.items() if name.upper() not in CREDENTIALS}
    if key == "claude":
        env.pop("CLAUDECODE", None)  # Claude Code refuses to start inside a variable it set for its own session
    return env


def sign_in(key: str) -> dict[str, Any]:
    """How the CLI was signed in, without any secret: the key variables removed and the route settings left that
    this CLI reads (a gateway for Claude Code says nothing about how Codex reached its model)."""
    names = {name.upper() for name in os.environ}
    return {"route": "the CLI's own sign-in", "credential_variables_removed": [n for n in CREDENTIALS if n in names],
            "route_settings_kept": [n for n in ROUTE_SETTINGS.get(key, ()) if os.environ.get(n)]}


# --- one session in a throwaway copy -----------------------------------------------------------------------------

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): digest(p) for p in sorted(folder.rglob("*")) if p.is_file()}


def validate(key: str, model: str | None, effort: str | None) -> Cli:
    if key not in CLIS:
        raise typer.BadParameter(f"Unknown CLI {key!r}; use one of {', '.join(CLIS)}.")
    cli = CLIS[key]
    if model is not None and not MODEL_NAME.fullmatch(model):
        raise typer.BadParameter("--model may contain letters, digits and . _ : @ / [ ] - only.")
    if effort is not None and effort not in cli.efforts:
        raise typer.BadParameter(f"{cli.name} takes no --effort." if not cli.efforts
                                 else f"--effort for {cli.name} is one of {', '.join(cli.efforts)}.")
    if shutil.which(key) is None:
        raise typer.BadParameter(f"{cli.name} ({key}) is not installed or not on PATH.")
    return cli


def group_options() -> dict[str, Any]:
    """Start the CLI in a process group of its own, so that stopping it also stops what it started."""
    if WINDOWS:
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)}
    return {"start_new_session": True}


def stop(process: subprocess.Popen) -> None:
    """Stop the CLI and everything it started: on Windows the whole tree with taskkill, elsewhere its process group,
    politely first."""
    if WINDOWS:
        try:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            process.kill()
            process.wait(timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return
    for sig, wait in ((signal.SIGTERM, 10), (getattr(signal, "SIGKILL", signal.SIGTERM), 5)):
        try:
            os.killpg(process.pid, sig)
        except (ProcessLookupError, PermissionError):
            return
        try:
            process.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue


def session(key: str, copy: Path, prompt: str, model: str | None, effort: str | None, timeout: float,
            stdout_path: Path, stderr_path: Path) -> dict[str, Any]:
    """Start one fresh session of the CLI in COPY with PROMPT on stdin and wait for it, at most TIMEOUT seconds."""
    build, read = ADAPTERS[key]
    last = Path(tempfile.mkdtemp(prefix="manuscript-seat-last-")) / "last-message.txt"
    # Codex without a model runs the default the authors configured: name it on the command line, so the command the
    # record keeps says which model was asked for, as `codex exec --model gpt-6.1-sol` would.
    configured = codex_models()[0] if key == "codex" and not model else None
    effort = effort or (codex_effort() if key == "codex" else None)
    argv = build(model or configured, effort, last)
    argv[0] = shutil.which(argv[0]) or argv[0]
    started = time.monotonic()
    record: dict[str, Any] = {"command": argv, "started_at": now()}
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        process = subprocess.Popen(argv, cwd=copy, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                   env=environment(key), **group_options())
        try:
            process.stdin.write(prompt.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            process.wait(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            stop(process)
            timed_out = True
    record |= {"finished_at": now(), "seconds": round(time.monotonic() - started, 1),
               "exit_code": process.returncode}
    outcome = read(stdout_path.read_text(encoding="utf-8", errors="replace"),
                   stderr_path.read_text(encoding="utf-8", errors="replace"), last)
    shutil.rmtree(last.parent, ignore_errors=True)
    if timed_out:
        status, error = "timeout", f"No answer within {timeout:g} seconds; the session was stopped."
    elif outcome.answer and process.returncode == 0:
        status, error = "answered", ""
    else:
        status = "failed"
        error = outcome.error or f"{CLIS[key].name} exited with status {process.returncode} and no answer."
        if not outcome.error and stderr_path.stat().st_size:
            tail = stderr_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()[-3:]
            error += " Last error output: " + " | ".join(tail)
    reported = outcome.models[0] if outcome.models else None
    return record | {"status": status, "error": error, "answer": outcome.answer, "session_id": outcome.session,
                     "model_requested": model, "models_reported": outcome.models, "usage": outcome.usage,
                     "model": f"{key}/{reported or model or configured or 'default'}", "sign_in": sign_in(key)}


def emit(result: dict[str, Any], as_json: bool, lines: list[str]) -> None:
    typer.echo(json.dumps(result, indent=2) if as_json else "\n".join(lines))


# --- commands -----------------------------------------------------------------------------------------------------

@app.command()
def detect(as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """List the supported CLIs installed here, which one this command runs inside, and the models each offers."""
    current = host()
    clis = []
    for key, cli in CLIS.items():
        path = shutil.which(key)
        entry: dict[str, Any] = {"cli": key, "name": cli.name, "family": cli.family, "installed": bool(path),
                                 "path": path, "version": version(path) if path else None, "host": key == current,
                                 "other_family": current is not None and cli.family != CLIS[current].family,
                                 "efforts": list(cli.efforts), "models": cli.models_hint, "notes": []}
        if key == "codex" and path:
            default, listed = codex_models()
            account, written_by = codex_account(), codex_cache_version()
            entry["default_model"], entry["models"], entry["sign_in"] = default, listed or entry["models"], account
            entry["notes"].append(codex_account_line(account))
            if written_by and entry["version"] and written_by not in entry["version"]:
                entry["notes"].append(f"Its list of models was written by Codex CLI {written_by}, not by this one "
                                      f"({entry['version']}); `check` asks the server itself.")
            if default and listed and default not in listed:
                entry["notes"].append(f"Its configured default model, {default}, is not among the models it lists for "
                                      f"this sign-in ({', '.join(listed)}). Run `check codex` first: an older Codex CLI "
                                      "and a personal ChatGPT plan are each offered fewer models, and updating the CLI "
                                      "or signing in to a work workspace keeps the default. Pass an older model with "
                                      "--model only when the authors choose it.")
        clis.append(entry)
    notes = []
    if os.environ.get("CODEX_SANDBOX_NETWORK_DISABLED") == "1":
        notes.append("This command runs in Codex's sandbox without network: run `models.py check` and `run` with "
                     "escalated permissions (Codex asks you to approve), or the other CLI cannot reach its model.")
    result = {"host": current, "host_family": CLIS[current].family if current else None, "clis": clis, "notes": notes}
    lines = [f"Host: {CLIS[current].name} ({CLIS[current].family})" if current else
             "Host: not recognised (no Claude Code, Codex or Gemini CLI session variable set)"]
    for e in clis:
        if not e["installed"]:
            lines.append(f"- {e['cli']}: not installed")
            continue
        relation = "the host" if e["host"] else "another model family" if e["other_family"] else (
            "same family as the host: another model, not another family" if current else e["family"])
        models = ", ".join(e["models"]) if isinstance(e["models"], list) else e["models"]
        lines.append(f"- {e['cli']}: {e['name']} {e['version']}, {e['family']}; {relation}"
                     + (f"; models: {models}" if models else ""))
        lines.extend(f"  note: {n}" for n in e["notes"])
    lines.extend(f"Note: {n}" for n in notes)
    emit(result, as_json, lines)


@app.command()
def check(cli: str, model: Annotated[str | None, typer.Option()] = None,
          effort: Annotated[str | None, typer.Option()] = None,
          timeout: Annotated[float, typer.Option(help="Seconds")] = 180,
          as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """One tiny call in an empty folder: is the CLI signed in, and does it accept the model? Sends no manuscript."""
    info = validate(cli, model, effort)
    with tempfile.TemporaryDirectory(prefix="manuscript-seat-check-") as folder:
        base = Path(folder)
        (base / "copy").mkdir()
        result = session(cli, base / "copy", PING, model, effort, timeout, base / "stdout", base / "stderr")
    result = {"cli": cli, "name": info.name, "version": version(cli)} | result
    ok = result["status"] == "answered"
    advice = codex_refusal_advice(result["error"], result["version"]) if cli == "codex" and not ok else ""
    if cli == "codex":
        result["account"] = codex_account()
    emit(result | ({"advice": advice} if advice else {}), as_json,
         [f"{info.name}: {'ready' if ok else result['status']}, model {result['model']}"
          + ("" if ok else f". {result['error']}"), *([advice] if advice else []),
          *([codex_account_line(result["account"])] if cli == "codex" else []), *sign_in_lines(result["sign_in"])])
    raise typer.Exit(0 if ok else 3 if result["status"] == "timeout" else 1)


@app.command()
def run(cli: str,
        workspace: Annotated[Path, typer.Option(help="The seat's workspace: everything it may read")],
        brief: Annotated[Path, typer.Option(help="The seat's brief, sent as its whole prompt; the workspace's "
                                                 "path in it is replaced by the copy's")],
        model: Annotated[str | None, typer.Option()] = None,
        effort: Annotated[str | None, typer.Option()] = None,
        timeout: Annotated[float, typer.Option(help="Seconds before the session is stopped")] = 3600,
        as_json: Annotated[bool, typer.Option("--json")] = False) -> None:
    """Run one seat as a fresh session of CLI in a copy of WORKSPACE; copy back the files it wrote."""
    info = validate(cli, model, effort)
    workspace = workspace.expanduser().resolve()
    if not workspace.is_dir():
        raise typer.BadParameter(f"{workspace} is not a folder.")
    if (workspace / RECORD).exists():
        raise typer.BadParameter(f"A seat already ran in {workspace} ({RECORD}); prepare a fresh workspace for each "
                                 "seat and model.")
    if not brief.is_file() or not brief.read_text(encoding="utf-8").strip():
        raise typer.BadParameter(f"{brief} is not a non-empty brief.")
    given = snapshot(workspace)
    parent = Path(tempfile.mkdtemp(prefix="manuscript-seat-"))
    copy = parent / "workspace"
    try:
        shutil.copytree(workspace, copy)
        text = brief.read_text(encoding="utf-8")
        named = {str(workspace): str(copy), workspace.as_posix(): copy.as_posix()}  # the same on POSIX
        prompt = text
        for given_path, copy_path in named.items():
            prompt = prompt.replace(given_path, copy_path)
        (workspace / "seat-run.prompt.md").write_text(prompt, encoding="utf-8")
        result = session(cli, copy, prompt, model, effort, timeout,
                         workspace / "seat-run.stdout.txt", workspace / "seat-run.stderr.txt")
        after = snapshot(copy)
        returned, changed = [], []
        for name, sha in after.items():
            if name not in given:
                target = workspace / name
                if target.exists():  # never overwrite: report it instead
                    changed.append(name)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(copy / name, target)
                returned.append(name)
            elif sha != given[name]:
                changed.append(name)
        deleted = [name for name in given if name not in after]
    finally:
        shutil.rmtree(parent, ignore_errors=True)
    answer = result.pop("answer")
    if answer:
        (workspace / ANSWER).write_text(answer + "\n", encoding="utf-8")
    record = {"cli": cli, "name": info.name, "family": info.family, "version": version(cli), "host": host()} | result | {
        "read_isolation": info.read_isolation, "write_isolation": "enforced", "standing_instructions": info.instructions,
        "workspace": str(workspace), "brief": str(brief.resolve()),
        "workspace_path_in_brief_replaced": sum(text.count(given_path) for given_path in named),
        "prompt": "seat-run.prompt.md", "answer": ANSWER if answer else None,
        "stdout": "seat-run.stdout.txt", "stderr": "seat-run.stderr.txt",
        "returned": returned, "changed_not_returned": changed, "deleted_in_copy": deleted}
    (workspace / RECORD).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    lines = [f"{info.name} ({record['model']}): {record['status']} in {record['seconds']} s"
             + (f". {record['error']}" if record["error"] else ""),
             f"Isolation: {READS[info.read_isolation]}; the authors' own instructions, memory and plugins "
             f"{info.instructions}."]
    if cli == "codex" and record["status"] != "answered" and (advice := codex_refusal_advice(record["error"],
                                                                                          record["version"])):
        lines[1:1] = [advice, codex_account_line(codex_account())]
    lines += sign_in_lines(record["sign_in"])
    if returned:
        lines.append("Returned: " + ", ".join(returned))
    if changed:
        lines.append("Changed in the copy and not returned (the workspace keeps its own): " + ", ".join(changed))
    if answer:
        lines.append(f"Answer: {workspace / ANSWER}")
    lines.append(f"Record: {workspace / RECORD}")
    emit(record, as_json, lines)
    raise typer.Exit({"answered": 0, "timeout": 3}.get(record["status"], 1))


def sign_in_lines(route: dict[str, Any]) -> list[str]:
    lines = []
    if route["credential_variables_removed"]:
        lines.append("Not passed to the CLI, so that it used its own sign-in: "
                     + ", ".join(route["credential_variables_removed"]) + ".")
    if route["route_settings_kept"]:
        lines.append("Note: " + ", ".join(route["route_settings_kept"]) + " is set, so the CLI may have sent its "
                     "requests that way rather than through its own sign-in.")
    return lines


def utf8_streams() -> None:
    """A CLI's answer can hold any character; a Windows console's code page would otherwise fail on it."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    utf8_streams()
    app()
