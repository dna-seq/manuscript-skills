"""Tests for the 0.19 changes to the referee panel (manuscript-peer-review/scripts/check_findings.py) and to seats on
other models (manuscript-other-models/scripts/models.py), from the 2026-10-24 reviews of 0.18.0: the figures seat,
policy points kept out of "the science and the evidence", what the defence returned for each finding, narrowed
findings, refuted misread risks, finding ids the dashboard links, demands for what the field expects, provider keys
kept from the CLIs, honest read isolation, Windows process handling and UTF-8 output. Run with `uv run pytest`."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
PEER = ROOT / "skills" / "manuscript-peer-review"
OTHER = ROOT / "skills" / "manuscript-other-models"
SEEDED = ROOT / "evals" / "fixtures" / "manuscript-peer-review" / "seeded.md"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


cf = _load("check_findings_0_19", PEER / "scripts" / "check_findings.py")
models = _load("models_0_19", OTHER / "scripts" / "models.py")
runner = CliRunner()

LEAK = "We assigned ClinVar variants at random to training (80%) and test (20%) sets."
CAUSAL = "This shows that the variants VarRank prioritises cause elevated LDL cholesterol."
DEFENCE = "Features were standardised on the training set."


def _finding(**overrides: Any) -> dict[str, Any]:
    base = {"id": "EV-1", "seat": "evidence-statistics", "location": "Methods, Benchmark", "quote": LEAK,
            "concern": "A variant-level random split puts variants from the same gene on both sides.",
            "claim": "Abstract: held-out performance of VarRank.", "consequence": "validity", "severity": "major",
            "change_my_mind": "Results on a gene-disjoint split.", "route": "author-required"}
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


def _adjudicated(**overrides: Any) -> dict[str, Any]:
    return _finding(**{"verdict": "confirmed", "triage": "substance", "verdict_evidence": "The quoted text shows it.",
                       "defence_outcome": "not answered", **overrides})


def _only(report: dict[str, Any]) -> dict[str, Any]:
    assert len(report["findings"]) == 1
    return report["findings"][0]


def _report(seat: str = "evidence-statistics", rests_on: tuple[str, ...] = ("EV-1",)) -> dict[str, Any]:
    return {"seat": seat, "summary": "The authors present VarRank; the benchmark cannot yet support the claim.",
            "recommendations": [{"venue": "bioinformatics", "recommendation": "major-revision",
                                 "reason": "The split can leak gene identity.", "rests_on": list(rests_on)}]}


# --- finding 17: the figures seat, and points that belong to other checks ---------------------------------------

@pytest.mark.parametrize("fields", [{"seat": "figures"}, {"seat": "figures@codex"},
                                    {"hand_to": "manuscript-figures", "route": "fixable-in-text"}])
def test_the_figures_seat_and_the_figures_hand_off_meet_the_contract(fields: dict[str, Any]) -> None:
    f = _only(cf.check([_finding(**fields)], SEEDED))
    assert f["contract"] == "pass", f["problems"]


@pytest.mark.parametrize("fields, owner", [
    ({"route": "policy"}, "manuscript-policy-fit"),
    ({"route": "policy", "stage": "now"}, "manuscript-policy-fit"),
    ({"route": "fixable-in-text", "hand_to": "manuscript-policy-fit"}, "manuscript-policy-fit"),
    ({"route": "fixable-in-text", "hand_to": "manuscript-figures"}, "manuscript-figures"),
])
def test_policy_points_and_other_checks_are_never_the_science_and_the_evidence(fields: dict[str, Any],
                                                                               owner: str) -> None:
    report = cf.check([_adjudicated(**fields)], SEEDED, adjudicated=True)
    assert [g["stage"] for g in report["groups"]] == ["other-checks"]
    md = cf.to_markdown(report)
    assert "## Fix now" not in md and "## Also found, belongs to other checks" in md
    assert f"It belongs to {owner}; mention it there rather than as a referee concern." in md


def test_a_figures_seat_concern_about_what_a_figure_shows_is_ranked_as_science() -> None:
    report = cf.check([_adjudicated(seat="figures", id="FI-1")], SEEDED, adjudicated=True)
    assert [g["stage"] for g in report["groups"]] == ["now"]


def test_the_seat_lists_agree_with_the_code() -> None:
    schema = (PEER / "references" / "finding-schema.md").read_text(encoding="utf-8")
    seat_row = next(line for line in schema.splitlines() if line.startswith("| `seat` |"))
    assert set(re.findall(r"`([a-z-]+)`", seat_row)) - {"seat", "custom"} >= set(cf.SEATS)
    hand_row = next(line for line in schema.splitlines() if line.startswith("| `hand_to` |"))
    assert set(re.findall(r"`(manuscript-[a-z-]+)`", hand_row)) == set(cf.HAND_TO)
    table = (PEER / "SKILL.md").read_text(encoding="utf-8").split("## What this skill judges")[1].split("## Choose")[0]
    assert set(re.findall(r"\| (manuscript-[a-z-]+)", table)) == set(cf.OTHER_CHECKS)


# --- what the defence returned, and narrowed findings ---------------------------------------------------------

def test_the_defence_outcome_is_required_after_adjudication_in_the_dashboards_words() -> None:
    missing = _only(cf.check([_adjudicated(defence_outcome=None)], SEEDED, adjudicated=True))
    assert missing["contract"] == "fail" and any("defence_outcome" in p for p in missing["problems"])
    for outcome in ("premise not supported", "answered", "not answered"):
        f = _only(cf.check([_adjudicated(defence_outcome=outcome)], SEEDED, adjudicated=True))
        assert f["contract"] == "pass" and f["defence_outcome"] == outcome, f["problems"]
    hyphenated = _only(cf.check([_adjudicated(defence_outcome="not-answered")], SEEDED, adjudicated=True))
    assert hyphenated["contract"] == "fail"
    dropped = _only(cf.check([_adjudicated(defence_outcome=None, route="dropped", drop_reason="No claim consequence.")],
                             SEEDED, adjudicated=True))
    assert dropped["contract"] == "pass", dropped["problems"]
    assert _only(cf.check([_finding()], SEEDED))["contract"] == "pass"  # before the defence pass, nothing to record
    assert cf.DEFENCE_OUTCOMES == ("premise not supported", "answered", "partly answered", "not answered")


def test_a_partly_answered_finding_is_confirmed_only_as_narrowed() -> None:
    partly = {"defence_outcome": "partly answered"}
    raised = _only(cf.check([_adjudicated(**partly)], SEEDED, adjudicated=True))
    assert raised["contract"] == "fail" and any("never confirmed as raised" in p for p in raised["problems"])
    no_original = _only(cf.check([_adjudicated(**partly, narrowed=True)], SEEDED, adjudicated=True))
    assert no_original["contract"] == "fail" and any("original_concern" in p for p in no_original["problems"])
    narrowed = _only(cf.check([_adjudicated(**partly, narrowed=True, original_concern="The split leaks and the "
                                            "features are standardised on all data.")], SEEDED, adjudicated=True))
    assert narrowed["contract"] == "pass" and narrowed["narrowed"] is True
    downgraded = _only(cf.check([_adjudicated(**partly, verdict="downgraded", severity="optional")], SEEDED,
                                adjudicated=True))
    assert downgraded["contract"] == "pass"
    not_bool = _only(cf.check([_adjudicated(narrowed="yes", original_concern="x y z")], SEEDED, adjudicated=True))
    assert not_bool["contract"] == "fail"


def test_a_recommendation_resting_on_a_narrowed_finding_is_flagged() -> None:
    finding = _adjudicated(defence_outcome="partly answered", narrowed=True,
                           original_concern="The split leaks gene identity and the scaling uses all data.")
    report = cf.check({"findings": [finding], "reports": [_report()]}, SEEDED, adjudicated=True)
    rec = report["reports"][0]["recommendations"][0]
    assert rec["challenged"] == {"EV-1": "narrowed"}
    assert "adjudication narrowed EV-1" in cf.to_markdown(report)


# --- a refuted finding kept as a misread risk -----------------------------------------------------------------

def test_a_refuted_misread_risk_is_a_writing_item_and_never_in_the_referees_report() -> None:
    findings = [_adjudicated(),
                _adjudicated(id="SK-1", seat="skeptic", quote=CAUSAL, concern="Causal wording for an association.",
                             verdict="refuted", triage="misread-risk", defence_quote=DEFENCE, route="fixable-in-text",
                             defence_outcome="answered"),
                _adjudicated(id="SK-2", seat="skeptic", quote=DEFENCE, concern="Scaling leaks the test set.",
                             verdict="refuted", triage=None, defence_quote=DEFENCE, defence_outcome="answered")]
    report = cf.check(findings, SEEDED, adjudicated=True)
    assert report["summary"]["fail"] == 0
    stages = {fid: g["stage"] for g in report["groups"] for fid in g["findings"]}
    assert stages == {"EV-1": "now", "SK-1": "writing", "SK-2": "answered"}
    assert report["by_referee"] == {"evidence-statistics": {"major": ["EV-1"], "minor": [], "questions": []}}
    md = cf.to_markdown(report)
    assert "bring the answer next to the claim it qualifies" in md
    assert md.index("## Then the writing") < md.index("## Answered by the paper")


# --- finding ids the dashboard links ---------------------------------------------------------------------------

def test_ids_the_dashboard_cannot_link_or_that_take_a_stage_prefix_are_named() -> None:
    findings = [_finding(id="EV-1"), _finding(id="SKX-3", seat="skeptic@codex", quote=CAUSAL, concern="Causal."),
                _finding(id="F1", quote=DEFENCE, concern="Scaling."),
                _finding(id="RP-1", seat="reproducibility", quote="VarRank is a logistic regression on 12 features",
                         concern="No library.")]
    report = cf.check(findings, SEEDED)
    assert report["ids"] == {"unlinked": ["F1"], "stage_prefix": ["RP-1"]}
    md = cf.to_markdown(report)
    assert "The ids F1 do not have the form the dashboard links" in md
    assert "The ids RP-1 take the prefix of another skill's own records" in md
    clean = cf.check([_finding(id="EV-1")], SEEDED)
    assert clean["ids"] == {"unlinked": [], "stage_prefix": []} and "dashboard links" not in cf.to_markdown(clean)


def test_the_documented_seat_prefixes_are_linkable_and_free() -> None:
    schema = (PEER / "references" / "finding-schema.md").read_text(encoding="utf-8")
    section = schema.split("### Finding ids")[1].split("## ")[0]
    cells = [[c.strip() for c in line.strip().strip("|").split("|")] for line in section.splitlines()
             if line.startswith("| ")]
    prefixes = [row[i + 1] for row in cells for i in range(0, len(row) - 1, 2) if re.fullmatch(r"[A-Z]{2}", row[i + 1])]
    assert len(prefixes) >= 11 and len(set(prefixes)) == len(prefixes)
    assert not set(prefixes) & set(cf.STAGE_PREFIXES)
    for prefix in prefixes:
        for letter in ("", "C", "X", "G"):
            assert cf.CONCERN_ID.fullmatch(f"{prefix}{letter}-12")
    stage_rule = (ROOT / "skills" / "manuscript-dashboard" / "references" / "stage-findings.md").read_text(
        encoding="utf-8")
    assert set(cf.STAGE_PREFIXES) <= set(re.findall(r"\b([A-Z]{2})\s+[a-z]+", stage_rule))
    assert '"id": "RP-1"' not in schema


# --- finding 22: the 0.18.0 warnings on descriptive text --------------------------------------------------------

@pytest.mark.parametrize("concern, change, warned", [
    ("The recruitment dates of the external validation cohort are not given.", "The dates in Methods.", False),
    ("There is no description of how the external validation cohort was recruited.", "A sentence in Methods.", False),
    ("The second cohort was recruited at another hospital, which Methods does not name.", "The hospital.", False),
    ("The risk score should be validated in an external cohort before the clinical claim.", "Validation.", True),
    ("The association lacks replication in an independent sample.", "A sentence of caution.", True),
    ("The model was tuned without an external validation set.", "The test results.", True),
    ("Performance is reported on one cohort only.", "Replication in an independent cohort.", True),
])
def test_a_demand_for_what_the_field_expects_is_read_where_it_is_asked(concern: str, change: str,
                                                                        warned: bool) -> None:
    f = _only(cf.check([_finding(concern=concern, change_my_mind=change)], SEEDED))
    assert any("source of the expectation" in w for w in f["warnings"]) is warned, f["warnings"]


@pytest.mark.parametrize("concern, warned", [
    ("Second-generation sequencing reads were aligned with BWA, but its version is not stated.", False),
    ("The split leaks gene identity. Secondly, the baselines are not named.", True),
    ("The split leaks gene identity; third: the n differs.", True),
    ("A second-stage filter removes variants, but its threshold is not stated.", False),
])
def test_an_ordinal_opens_a_new_point_only_with_a_comma_or_a_colon(concern: str, warned: bool) -> None:
    f = _only(cf.check([_finding(concern=concern)], SEEDED))
    assert any("one concern per finding" in w for w in f["warnings"]) is warned, f["warnings"]


# --- UTF-8 output on any console --------------------------------------------------------------------------------

def test_the_checker_prints_any_quote_on_a_console_that_is_not_utf8(tmp_path: Path) -> None:
    paper = tmp_path / "paper.md"
    paper.write_text("# Methods\n\nThe naïve Bayes baseline uses a 5 µm grid around each variant.\n", encoding="utf-8")
    findings = tmp_path / "findings.json"
    findings.write_text(json.dumps([_finding(quote="The naïve Bayes baseline uses a 5 µm grid", concern="Unstated.",
                                             change_my_mind="State it.")]), encoding="utf-8")
    env = {**os.environ, "PYTHONIOENCODING": "ascii"}
    done = subprocess.run([sys.executable, str(PEER / "scripts" / "check_findings.py"), str(findings), str(paper)],
                          capture_output=True, env=env, timeout=120)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert "naïve Bayes" in done.stdout.decode("utf-8")


# --- seats on other models: provider keys, read isolation, Windows ---------------------------------------------

FAKE = '''#!{python}
import json, os, sys
from pathlib import Path
name, args = Path(sys.argv[0]).name, sys.argv[1:]
if args == ["--version"]:
    print(name + " 9.9.9")
    sys.exit(0)
sys.stdin.read()
keys = {keys!r}
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({{"cli": name, "env": {{k: os.environ.get(k) for k in keys}}}}) + "\\n")
Path("findings.json").write_text("[]")
if name == "claude":
    print(json.dumps({{"type": "result", "subtype": "success", "is_error": False, "result": "done",
                      "session_id": "s1", "modelUsage": {{"claude-x": {{}}}}}}))
elif name == "codex":
    Path(args[args.index("-o") + 1]).write_text("done")
    print(json.dumps({{"type": "turn.completed", "usage": {{}}}}))
else:
    print(json.dumps({{"session_id": "g1", "response": "done", "stats": {{"models": {{"gemini-x": {{}}}}}}}}))
'''
KEYS = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "ANTHROPIC_BASE_URL", "HOME")


@pytest.fixture
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("claude", "codex", "gemini"):
        path = bin_dir / name
        path.write_text(FAKE.format(python=sys.executable, keys=KEYS), encoding="utf-8")
        path.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("FAKE_LOG", str(tmp_path / "fake.log"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    for var in ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "GEMINI_CLI", *models.CREDENTIALS,
                *models.ROUTE_SETTINGS):
        monkeypatch.delenv(var, raising=False)
    return tmp_path / "fake.log"


def _seat(tmp_path: Path, name: str) -> tuple[Path, Path]:
    workspace = tmp_path / "project" / name
    workspace.mkdir(parents=True)
    (workspace / "paper.md").write_text("original", encoding="utf-8")
    brief = tmp_path / f"{name}.md"
    brief.write_text(f"You are the skeptic. Work only from the files in {workspace}.\n", encoding="utf-8")
    return workspace, brief


@pytest.mark.skipif(os.name == "nt", reason="the fake CLIs are POSIX scripts")
@pytest.mark.parametrize("cli, reads", [("claude", "enforced"), ("codex", "instruction-only"),
                                        ("gemini", "instruction-only")])
def test_provider_keys_never_reach_a_cli_and_the_record_says_how_far_reads_were_kept(
        fakes: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cli: str, reads: str) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-openai")
    monkeypatch.setenv("GEMINI_API_KEY", "secret-gemini")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://gateway.example")
    workspace, brief = _seat(tmp_path, f"ws-{cli}")
    result = runner.invoke(models.app, ["run", cli, "--workspace", str(workspace), "--brief", str(brief)])
    assert result.exit_code == 0, result.output
    [call] = [json.loads(line) for line in fakes.read_text(encoding="utf-8").splitlines()]
    assert call["env"]["OPENAI_API_KEY"] is None and call["env"]["GEMINI_API_KEY"] is None
    assert call["env"]["ANTHROPIC_BASE_URL"] == "https://gateway.example" and call["env"]["HOME"]
    text = (workspace / "seat-run.json").read_text(encoding="utf-8")
    assert "secret" not in text and "gateway.example" not in text
    record = json.loads(text)
    assert record["read_isolation"] == reads and record["write_isolation"] == "enforced"
    assert record["sign_in"] == {"route": "the CLI's own sign-in",
                                 "credential_variables_removed": ["OPENAI_API_KEY", "GEMINI_API_KEY"],
                                 # A gateway for Claude Code is named only for Claude Code: Codex and Gemini never read it.
                                 "route_settings_kept": ["ANTHROPIC_BASE_URL"] if cli == "claude" else []}
    assert f"Isolation: {models.READS[reads]};" in result.output
    # The authors' own setup: left out where the CLI allows it, and said so in the record and the output.
    assert record["standing_instructions"] == models.CLIS[cli].instructions
    assert models.CLIS[cli].instructions in result.output
    argv = record["command"]
    if cli == "claude":
        assert argv[argv.index("--setting-sources") + 1] == "project,local"
    if cli == "codex":
        assert "--ignore-user-config" in argv
    assert "Not passed to the CLI, so that it used its own sign-in: OPENAI_API_KEY, GEMINI_API_KEY." in result.output
    assert ("ANTHROPIC_BASE_URL is set" in result.output) == (cli == "claude")


def test_the_brief_option_says_the_workspace_path_is_replaced() -> None:
    result = runner.invoke(models.app, ["run", "--help"])
    assert "unchanged" not in result.output and "replaced" in result.output


def test_a_cli_starts_in_a_process_group_of_its_own_on_every_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(models, "WINDOWS", False)
    assert models.group_options() == {"start_new_session": True}
    monkeypatch.setattr(models, "WINDOWS", True)
    assert models.group_options() == {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)}


def test_on_windows_a_stopped_cli_takes_its_whole_tree_with_it(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[list[str]] = []
    monkeypatch.setattr(models, "WINDOWS", True)
    monkeypatch.setattr(models.subprocess, "run", lambda argv, **kw: ran.append(argv))
    monkeypatch.setattr(models.os, "killpg", lambda *a: pytest.fail("no process groups on Windows"), raising=False)

    class Process:
        pid, killed = 4242, False

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout: float | None = None) -> int:
            return 1

    process = Process()
    models.stop(process)  # type: ignore[arg-type]
    assert ran == [["taskkill", "/T", "/F", "/PID", "4242"]] and process.killed


def test_the_scripts_make_their_output_utf8_and_name_no_posix_only_call_without_a_branch() -> None:
    for script in (PEER / "scripts" / "check_findings.py", OTHER / "scripts" / "models.py"):
        text = script.read_text(encoding="utf-8")
        assert 'reconfigure(encoding="utf-8", errors="replace")' in text, script.name
        for call in re.finditer(r"subprocess\.run\(", text):
            assert 'encoding="utf-8"' in text[call.start():call.start() + 300], script.name
    source = (OTHER / "scripts" / "models.py").read_text(encoding="utf-8")
    assert "start_new_session=True" not in source.replace('{"start_new_session": True}', "")
    assert "taskkill" in source and "CREATE_NEW_PROCESS_GROUP" in source


# --- links in the panel's instructions resolve ------------------------------------------------------------------

def _slug(heading: str) -> str:
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def _anchors(path: Path) -> set[str]:
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m:
            out.add(_slug(m.group(1)))
    return out


@pytest.mark.parametrize("doc", sorted([*PEER.rglob("*.md"), OTHER / "SKILL.md"], key=str),
                         ids=lambda p: p.relative_to(ROOT).as_posix())
def test_every_link_in_the_panel_instructions_resolves(doc: Path) -> None:
    text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.S)
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z]+:", target):
            continue
        file, _, anchor = target.partition("#")
        path = (doc.parent / file).resolve() if file else doc
        assert path.exists(), f"{doc.name}: {target}"
        if anchor and path.suffix == ".md":
            assert anchor in _anchors(path), f"{doc.name}: {target}"
