"""manuscript-coauthors: the co-authors' comments on a round (comments.py) and the rounds on Google Drive (rounds.py).

The Doc exports are built at test time the way Google Docs writes them (checked against a real export, 2026-10-28):
each comment and each reply is a Word comment on the same range with no thread record, a comment over several
ranges is one identical copy per range, and suggested edits are tracked insertions and deletions. Run with
`uv run pytest`."""
from __future__ import annotations

import importlib.util
import json
import tomllib
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "manuscript-coauthors" / "scripts"
sys.path.insert(0, str(ROOT / "skills" / "manuscript-integrity-check" / "scripts"))

import project as projects  # noqa: E402
import runs  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"coauthors_{name}", SKILL / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


comments = _load("comments")
rounds_py = _load("rounds")
NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
ANN, BOB = "Ann Lee", "Bob Ray"

MASTER = """# A Paper

## Abstract

Personal genome analysis requires tools that keep the data local.

## 1. Introduction

Whole genome sequencing costs have fallen from billions of dollars to under a thousand since 2003.

The platform annotates variants with old words in this sentence.

Modules are versioned tables of variants and their evidence.
"""


def run_(*parts: str) -> str:
    return "".join(f'<w:r><w:t xml:space="preserve">{p}</w:t></w:r>' for p in parts)


def comment(cid: int, author: str, date: str, text: str) -> str:
    return (f'<w:comment w:id="{cid}" w:author="{author}" w:date="{date}"><w:p>{run_(text)}</w:p></w:comment>')


def export(path: Path, extra: bool = False, month: str = "10") -> Path:
    """A Google Doc of MASTER with Ann's comment on the Abstract heading and Bob's reply on the same range, Ann's
    comment on "billions of dollars", one comment of Bob's over two ranges, and Ann's suggested replacement."""
    body = (
        f'<w:p>{run_("A Paper")}</w:p>'
        f'<w:p><w:commentRangeStart w:id="0"/><w:commentRangeStart w:id="1"/>{run_("Abstract")}'
        '<w:commentRangeEnd w:id="0"/><w:commentRangeEnd w:id="1"/></w:p>'
        f'<w:p>{run_("Personal genome analysis requires tools that keep the data local.")}</w:p>'
        f'<w:p>{run_("1. Introduction")}</w:p>'
        f'<w:p>{run_("Whole genome sequencing costs have fallen from ")}<w:commentRangeStart w:id="2"/>'
        f'{run_("billions of dollars")}<w:commentRangeEnd w:id="2"/>{run_(" to under a thousand since 2003.")}</w:p>'
        f'<w:p>{run_("The platform annotates variants with ")}'
        f'<w:del w:id="9" w:author="{ANN}" w:date="2026-10-21T10:00:00Z"><w:r><w:delText>old</w:delText></w:r></w:del>'
        f'<w:ins w:id="10" w:author="{ANN}" w:date="2026-10-21T10:00:00Z"><w:r><w:t>new</w:t></w:r></w:ins>'
        f'{run_(" words in this sentence.")}</w:p>'
        f'<w:p><w:commentRangeStart w:id="3"/>{run_("Modules are versioned tables")}<w:commentRangeEnd w:id="3"/>'
        f'{run_(" of variants and ")}<w:commentRangeStart w:id="4"/>{run_("their evidence.")}'
        '<w:commentRangeEnd w:id="4"/></w:p>'
        + (f'<w:p>{run_("A new paragraph Bob comments on later.")}</w:p>' if extra else ""))
    notes = (comment(0, ANN, "2026-10-20T09:00:00Z", "Abstract reads well overall.")
             + comment(1, BOB, "2026-10-20T11:00:00Z", "Agreed, small fixes only.")
             + comment(2, ANN, "2026-10-20T09:30:00Z", "This is not true: that was the whole project's budget.")
             + comment(3, BOB, "2026-10-21T08:00:00Z", "Say which modules.")
             + comment(4, BOB, "2026-10-21T08:00:00Z", "Say which modules.")
             + (comment(5, BOB, "2026-10-22T08:00:00Z", "Cite the registry here.") if extra else ""))
    notes = notes.replace("2026-10-", f"2026-{month}-")  # another Doc's comments: other days
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f'<w:document {NS}><w:body>{body}</w:body></w:document>')
        z.writestr("word/comments.xml", f'<w:comments {NS}>{notes}</w:comments>')
    return path


@pytest.fixture()
def rounds(tmp_path: Path) -> Path:
    (tmp_path / "v0.5").mkdir()
    (tmp_path / "v0.5" / "paper.md").write_text(MASTER, encoding="utf-8")
    return tmp_path


def cli(*args: str) -> int:
    return comments.main([str(a) for a in args])


def ledger_of(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_import_reads_threads_copies_suggestions_and_where_each_sits(rounds: Path, capsys) -> None:
    ledger = rounds / "v0.5" / "comments.yaml"
    assert cli("import", export(rounds / "doc.docx"), "--ledger", ledger, "--master", rounds / "v0.5" / "paper.md",
               "--doc", "https://docs.google.com/document/d/abc/edit") == 0
    result = json.loads(capsys.readouterr().out)
    assert result["new"] == 4 and result["not_located"] == [] and result["round"] == "0.5"
    items = {i["id"]: i for i in ledger_of(ledger)["items"]}
    assert list(items) == ["C1", "C2", "S1", "C3"]  # paper order; suggestions number apart
    assert items["C1"]["anchor"] == "Abstract" and items["C1"]["where"] == "Abstract"
    assert items["C1"]["replies"] == [{"author": BOB, "date": "2026-10-20T11:00:00Z", "text": "Agreed, small fixes only.",
                                       "by": "bobray"}]
    assert items["C2"]["anchor"] == "billions of dollars" and items["C2"]["where"] == "1. Introduction"
    assert items["C2"]["line"] == 9 and items["C2"]["status"] == "open"
    assert items["S1"]["kind"] == "suggestion" and items["S1"]["edits"] == [{"deleted": "old", "inserted": "new"}]
    assert "replace “old” with “new”" in items["S1"]["comment"]
    assert items["C3"]["comment"] == "Say which modules."  # one comment over two ranges, once
    assert ledger_of(ledger)["sources"][0]["doc"].endswith("/abc/edit")


def test_a_docs_commenters_become_people_and_an_ai_marked_comment_names_nobody(rounds: Path, capsys) -> None:
    """Reviewers who only use the Doc are people by default: each gets a handle in rev-marks.toml, their Doc name
    an alias of it. A comment or reply that starts with [ai:NAME] is an agent's, whoever's account posted it."""
    doc = export(rounds / "doc.docx")
    with zipfile.ZipFile(doc) as z:
        files = {n: z.read(n).decode() for n in z.namelist()}
    files["word/comments.xml"] = files["word/comments.xml"].replace(
        "Agreed, small fixes only.", "[ai:claude] Agreed, small fixes only.").replace(
        "Say which modules.", "[AI: Codex] Say which modules.")
    with zipfile.ZipFile(doc, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)
    ledger = rounds / "v0.5" / "comments.yaml"
    assert cli("import", doc, "--ledger", ledger, "--master", rounds / "v0.5" / "paper.md") == 0
    result = json.loads(capsys.readouterr().out)
    assert [(p["name"], p["handle"], p["rule"]) for p in result["people"]] == [(ANN, "annlee", "new")]
    config = tomllib.loads((rounds / "v0.5" / "rev-marks.toml").read_text(encoding="utf-8"))
    assert config["humans"] == ["annlee"] and config["aliases"] == {"annlee": [ANN]}  # Bob only wrote as an agent
    items = {i["id"]: i for i in ledger_of(ledger)["items"]}
    assert items["C1"]["by"] == "annlee" and items["C1"]["replies"][0]["ai"] == "claude"
    assert "by" not in items["C1"]["replies"][0]
    assert items["C3"]["ai"] == "codex" and items["C3"]["status"] == "not-on-point" and "by" not in items["C3"]
    assert cli("status", ledger, "--json") == 0
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["items"]}
    assert rows["C3"]["problems"] == [] and rows["C2"]["problems"]  # the agent's comment asks nothing; Ann's does


def test_no_people_and_hand_written_items_leave_rev_marks_alone(rounds: Path, capsys) -> None:
    ledger = rounds / "v0.5" / "comments.yaml"
    assert cli("import", export(rounds / "doc.docx"), "--ledger", ledger, "--master", rounds / "v0.5" / "paper.md",
               "--no-people") == 0
    items = (rounds / "v0.5" / "items.yaml")
    items.write_text(yaml.safe_dump([{"author": "v0.4 changes workbook, open points", "comment": "Still open."}]))
    assert cli("add", items, "--ledger", ledger) == 0
    assert not (rounds / "v0.5" / "rev-marks.toml").exists()
    assert '"people"' not in capsys.readouterr().out


def test_a_second_pull_keeps_ids_and_triage_and_numbers_past_the_project(rounds: Path, capsys) -> None:
    ledger = rounds / "v0.5" / "comments.yaml"
    master = rounds / "v0.5" / "paper.md"
    cli("import", export(rounds / "doc.docx"), "--ledger", ledger, "--master", master)
    data = ledger_of(ledger)
    data["items"][1].update(status="declined", why="The figure is the project's, and the text now says so.")
    ledger.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    (rounds / "v0.3").mkdir()  # an earlier round's ledger already gave out C1..C7
    (rounds / "v0.3" / "comments.yaml").write_text(yaml.safe_dump({"items": [{"id": "C7"}]}), encoding="utf-8")
    capsys.readouterr()
    cli("import", export(rounds / "doc2.docx", extra=True), "--ledger", ledger, "--master", master)
    assert json.loads(capsys.readouterr().out)["new"] == 1
    items = {i["id"]: i for i in ledger_of(ledger)["items"]}
    assert set(items) == {"C1", "C2", "S1", "C3", "C8"} and items["C8"]["comment"] == "Cite the registry here."
    assert items["C2"]["status"] == "declined" and items["C2"]["why"].startswith("The figure")


def test_ids_continue_past_the_masters_revision_marks(rounds: Path) -> None:
    master = rounds / "v0.5" / "paper.md"
    master.write_text(MASTER.replace("Modules are", "<!-- @rev C12a rounds=1 by=ann:2026-10-01 -->\nModules are")
                      .replace("their evidence.\n", "their evidence.\n<!-- @/rev C12a -->\n"), encoding="utf-8")
    ledger = rounds / "v0.5" / "comments.yaml"
    assert cli("import", export(rounds / "doc.docx"), "--ledger", ledger, "--master", master) == 0
    assert [i["id"] for i in ledger_of(ledger)["items"]] == ["C13", "C14", "S1", "C15"]


def answered(rounds: Path) -> tuple[Path, Path]:
    """v0.6 answers v0.5's comments: C2's sentence rewritten in a segment named for it, the rest as it was."""
    ledger = rounds / "v0.5" / "comments.yaml"
    cli("import", export(rounds / "doc.docx"), "--ledger", ledger, "--master", rounds / "v0.5" / "paper.md")
    (rounds / "v0.6").mkdir()
    new = rounds / "v0.6" / "paper.md"
    new.write_text(MASTER.replace(
        "Whole genome sequencing costs have fallen from billions of dollars to under a thousand since 2003.",
        "<!-- @rev C2 rounds=1 by=ann:2026-10-25 -->\nSequencing consumables for a human genome now cost US$80 to"
        " US$200.\n<!-- @/rev C2 -->"), encoding="utf-8")
    return ledger, new


def test_status_maps_each_comment_to_the_new_round_and_checks_the_ledger(rounds: Path, capsys) -> None:
    ledger, new = answered(rounds)
    capsys.readouterr()
    assert cli("status", ledger, "--new", new, "--json") == 0
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["items"]}
    assert rows["C2"]["change"] == "changed" and rows["C2"]["rev_ids"] == ["C2"]
    assert "US$80" in rows["C2"]["after"] and "billions" in rows["C2"]["before"]
    assert rows["C1"]["change"] == "unchanged" and rows["S1"]["change"] == "unchanged"
    assert any("check whether the change answers it" in h for h in rows["C2"]["hints"])
    assert all("needs next" in r["problems"][0] for r in rows.values())  # nothing triaged yet
    assert cli("status", ledger, "--new", new, "--strict") == 1
    data = ledger_of(ledger)
    by = {i["id"]: i for i in data["items"]}
    by["C1"].update(status="not-on-point", why="A general remark; nothing to change.")
    by["C2"].update(status="addressed", now="Sequencing consumables for a human genome now cost US$80 to US$200.")
    by["S1"].update(status="addressed", now="words that are not in the new round")
    by["C3"].update(status="partly", now="Modules are versioned tables", next="Name the modules in Table 1.")
    ledger.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    capsys.readouterr()
    cli("status", ledger, "--new", new, "--json")
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["items"]}
    assert rows["S1"]["problems"] == ["now is not in the new round, verbatim"]
    assert [rows[i]["problems"] for i in ("C1", "C2", "C3")] == [[], [], []]


def test_a_paragraph_that_moved_into_a_segment_named_for_the_comment(rounds: Path, capsys) -> None:
    ledger, new = answered(rounds)
    new.write_text(MASTER.replace(
        "Whole genome sequencing costs have fallen from billions of dollars to under a thousand since 2003.\n\n", "")
        + "\n## Supplementary note\n\n<!-- @rev C2b rounds=1 by=ann:2026-10-25 -->\nThe cost history moved here."
        "\n<!-- @/rev C2b -->\n", encoding="utf-8")
    capsys.readouterr()
    cli("status", ledger, "--new", new, "--json")
    row = next(r for r in json.loads(capsys.readouterr().out)["items"] if r["id"] == "C2")
    assert row["change"] == "moved" and row["after"] == "The cost history moved here." and row["rev_ids"] == ["C2b"]
    assert row["quote"] == "The cost history moved here."  # quoted from where it is now, not where it was


def test_findings_refuse_an_untriaged_ledger_then_write_the_stage_files(rounds: Path, tmp_path: Path, capsys) -> None:
    ledger, new = answered(rounds)
    out = tmp_path / "run" / "manuscript-coauthors" / "findings.json"
    assert cli("findings", ledger, "--new", new, "--out", out) == 1 and not out.exists()
    data = ledger_of(ledger)
    by = {i["id"]: i for i in data["items"]}
    by["C1"].update(status="not-on-point", why="A general remark.")
    by["C2"].update(status="addressed", now="Sequencing consumables for a human genome now cost US$80 to US$200.",
                    why="The cost now quotes the consumables.")
    by["S1"].update(status="open", next="Apply the replacement.")
    by["C3"].update(status="declined", why="The modules are named in Table 1 already.")
    ledger.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert cli("findings", ledger, "--new", new, "--out", out) == 0
    document = json.loads(out.read_text(encoding="utf-8"))
    [finding] = document["findings"]
    assert finding["id"] == "CA-1" and finding["action"] == "Apply the replacement."
    assert finding["quote"] and finding["quote"] in new.read_text(encoding="utf-8")
    digest = (out.parent / "comments.md").read_text(encoding="utf-8")
    assert finding["evidence"][0]["quote"] in digest
    block = document["coauthors"]
    assert block["round"] == "0.5" and block["next_round"] == "0.6" and block["source"] == "comments.yaml"
    items = {i["id"]: i for i in block["items"]}
    assert items["S1"]["finding_ids"] == ["CA-1"] and items["C2"]["finding_ids"] == []
    assert items["C2"]["change"] == "changed" and items["C2"]["rev_ids"] == ["C2"]
    assert items["C1"]["replies"][0]["author"] == BOB


def test_the_changelog_takes_why_from_the_comment_a_segment_answers(rounds: Path, capsys) -> None:
    ledger, new = answered(rounds)
    data = ledger_of(ledger)
    data["items"][1]["why"] = "The cost now quotes the consumables."
    ledger.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    capsys.readouterr()
    assert cli("changelog", "--base", rounds / "v0.5" / "paper.md", "--new", new, "--ledger", ledger,
               "--seen", rounds / "v0.5" / "paper.md") == 0
    table = capsys.readouterr().out
    row = next(line for line in table.splitlines() if line.startswith("| C2 |"))
    assert f"C2 ({ANN}): “This is not true" in row and "The cost now quotes the consumables." in row
    assert row.rstrip().endswith("| New since then |")


# --- rounds.py: the settings and the Drive ---------------------------------------------------------------


def configure(folder: Path, *args: str):
    return CliRunner().invoke(projects.app, ["configure", str(folder), "--manuscript", "paper.md", "--no-code",
                                              "--output-dir", "reviews", *args])


def rounds_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SKILL / "rounds.py"), *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8", check=False)


def test_the_drive_settings_are_a_saved_project_choice(rounds: Path) -> None:
    folder = rounds / "v0.5"
    bad = configure(folder, "--drive", "rclone", "--drive-remote", "gdrive")
    assert bad.exit_code == 2 and "folder_id" in bad.output
    assert configure(folder, "--drive", "rclone", "--drive-remote", "gdrive", "--drive-folder-id",
                     "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp", "--release-doc",
                     "paper.md=Paper (v{round})", "--release-file", "build/*.pdf").exit_code == 0
    saved = projects.read(folder / ".manuscript-skills.yaml")["coauthors"]
    assert saved == {"drive": "rclone", "remote": "gdrive", "folder_id": "1AbCdEfGhIjKlMnOp",
                     "release": {"docs": ["paper.md=Paper (v{round})"], "files": ["build/*.pdf"]},
                     "round_folder": "v{round}"}
    assert configure(folder, "--round-folder", "round-{round}").exit_code == 0
    assert configure(folder, "--round-folder", "rounds").exit_code == 2
    assert configure(folder, "--no-coauthors", "--drive", "folder").exit_code == 2
    assert configure(folder, "--no-coauthors").exit_code == 0
    assert "coauthors" not in projects.read(folder / ".manuscript-skills.yaml")
    (folder / ".manuscript-skills.yaml").write_text("schema_version: 1\ncoauthors: {drive: dropbox}\n", encoding="utf-8")
    with pytest.raises(projects.ProjectError, match="coauthors.drive"):
        projects.read(folder / ".manuscript-skills.yaml")


def test_push_prints_the_rclone_commands_and_runs_nothing(rounds: Path) -> None:
    configure(rounds / "v0.5", "--drive", "rclone", "--drive-remote", "gdrive", "--drive-folder-id", "1AbCdEfGhIjKlMnOp",
              "--release-doc", "paper.md=Paper (v{round})")
    done = rounds_cli("push", "0.5", "--project", rounds / "v0.5")
    assert done.returncode == 0, done.stderr
    plan = json.loads(done.stdout)
    assert plan["dry_run"] and plan["destination"] == "v0.5"
    assert plan["build"] == [f"pandoc {rounds / 'v0.5' / 'paper.md'} -o {rounds / 'v0.5' / 'build' / 'paper.docx'}"]
    [upload] = plan["upload"]
    assert "rclone copyto" in upload and "'gdrive:v0.5/Paper (v0.5).docx'" in upload
    assert "--drive-root-folder-id 1AbCdEfGhIjKlMnOp --drive-import-formats docx" in upload


def test_open_copies_the_round_without_its_outputs_and_refuses_twice(rounds: Path) -> None:
    folder = rounds / "v0.5"
    configure(folder, "--drive", "connector")
    (folder / "reviews").mkdir()
    (folder / "comments.yaml").write_text("items: []\n", encoding="utf-8")
    (folder / "paper.dashboard.html").write_text("<html></html>", encoding="utf-8")
    (folder / "paper.md").write_text(MASTER.replace("# A Paper", "# A Paper (draft v0.5)"), encoding="utf-8")
    done = rounds_cli("open", "0.6", "--project", folder)
    assert done.returncode == 0, done.stderr
    opened = json.loads(done.stdout)
    assert sorted(p.name for p in (rounds / "v0.6").iterdir()) == [".manuscript-skills.yaml", "paper.md"]
    assert sorted(opened["left_behind"]) == ["comments.yaml", "paper.dashboard.html", "reviews"]
    assert opened["mentions_of_the_old_round"] == ["paper.md:1: # A Paper (draft v0.5)"]
    assert "0.6" in projects.read(rounds / "v0.6" / ".manuscript-skills.yaml")["coauthors"]["rounds"]
    assert rounds_cli("open", "0.6", "--project", folder).returncode == 1


def test_push_into_a_synced_folder_never_replaces_without_asking(rounds: Path, tmp_path: Path) -> None:
    folder = rounds / "v0.5"
    drive = tmp_path / "Google Drive" / "Manuscript"
    configure(folder, "--drive", "folder", "--drive-folder", str(drive), "--release-doc", "paper.md",
              "--release-file", "build/*.pdf", "--release-build", f'"{sys.executable}" -c pass')
    (folder / "build").mkdir()
    (folder / "build" / "paper.docx").write_bytes(b"docx")
    (folder / "build" / "paper.pdf").write_bytes(b"pdf")
    first = rounds_cli("push", "0.5", "--go", "--project", folder)
    assert first.returncode == 0, first.stderr
    assert sorted(p.name for p in (drive / "v0.5").iterdir()) == ["paper.docx", "paper.pdf"]
    assert "Convert uploads" in json.loads(first.stdout)["note"]
    assert projects.read(folder / ".manuscript-skills.yaml")["coauthors"]["rounds"]["0.5"]["released"]
    again = rounds_cli("push", "0.5", "--go", "--project", folder)
    assert again.returncode == 1 and "detach the co-authors' comments" in again.stderr
    assert rounds_cli("push", "0.5", "--go", "--replace", "--project", folder).returncode == 0


def test_record_and_pull_without_rclone_say_what_to_do(rounds: Path, tmp_path: Path) -> None:
    folder = rounds / "v0.5"
    configure(folder, "--drive", "connector", "--release-doc", "paper.md=Paper")
    assert rounds_cli("pull", "0.5", "--out", tmp_path, "--project", folder).returncode == 2  # no Docs recorded
    assert rounds_cli("record", "0.5", "--doc", "Paper=https://docs.google.com/document/d/1xYz0123456789abcdefghij/edit",
                      "--project", folder).returncode == 0
    plan = json.loads(rounds_cli("pull", "0.5", "--out", tmp_path, "--project", folder).stdout)
    [step] = plan["steps"]
    assert step["master"] == (folder / "paper.md").as_posix() and "download_file_content" in plan["by_hand"]
    assert "1xYz0123456789abcdefghij" in step["commands"][0]


FAKE_RCLONE = '''#!{python}
"""rclone as Drive answers it: a Google Doc is listed as "Title.docx" (a Sheet as "Title.xlsx"), like a Word
file, and only --drive-skip-gdocs tells them apart. Every call is logged."""
import json, sys
from pathlib import Path
log = Path({log!r})
log.write_text(log.read_text() + " ".join(sys.argv[1:]) + "\\n" if log.exists() else " ".join(sys.argv[1:]) + "\\n")
if sys.argv[1] == "lsjson":
    entries = [{{"Path": "Paper (v0.5).docx", "Name": "Paper (v0.5).docx", "ID": "1DocDocDocDocDocDocDocDoc", "IsDir": False}},
               {{"Path": "Paper (v0.5).pdf", "Name": "Paper (v0.5).pdf", "ID": "1PdfPdfPdfPdfPdfPdfPdf", "IsDir": False}},
               {{"Path": "Figures", "Name": "Figures", "ID": "1FolderFolderFolder", "IsDir": True}}]
    if "--drive-skip-gdocs" in sys.argv:
        entries = entries[1:]
    print(json.dumps(entries))
'''


def drive_project(rounds: Path, tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    """v0.5 with a paper, a changes workbook, a figure and data files, released by rclone to a fake Drive."""
    folder = rounds / "v0.5"
    (folder / "figures").mkdir()
    (folder / "figures" / "figure-1.png").write_bytes(b"png")
    (folder / "data").mkdir()
    for name in ("S4.csv", "S5.csv"):
        (folder / "data" / name).write_text("a,b\n", encoding="utf-8")
    (folder / "build").mkdir()
    (folder / "build" / "paper.docx").write_bytes(b"docx")
    (folder / "build" / "paper.pdf").write_bytes(b"pdf")
    (folder / "build" / "changes-from-v0.4.xlsx").write_bytes(b"xlsx")
    configure(folder, "--drive", "rclone", "--drive-remote", "gdrive", "--drive-folder-id", "1AbCdEfGhIjKlMnOp",
              "--release-doc", "paper.md=Paper (v{round})", "--release-doc",
              "build/changes-from-v{previous}.xlsx=Changes from v{previous} to v{round}",
              "--release-file", "build/paper.pdf=Paper (v{round}).pdf", "--release-file", "figures/*=Figures/",
              "--release-file", "data/*.csv=Supplementary data files/", "--release-build", f'"{sys.executable}" -c pass')
    (rounds / "v0.4").mkdir()
    bin_dir, log = tmp_path / "bin", tmp_path / "rclone.log"
    bin_dir.mkdir()
    fake = bin_dir / "rclone"
    fake.write_text(FAKE_RCLONE.format(python=sys.executable, log=str(log)), encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return folder, log


def test_a_release_takes_sheets_subfolders_and_new_names(rounds: Path, tmp_path: Path, monkeypatch) -> None:
    folder, _ = drive_project(rounds, tmp_path, monkeypatch)
    plan = json.loads(rounds_cli("push", "0.5", "--project", folder).stdout)
    assert len(plan["build"]) == 1  # the workbook is uploaded as it is
    upload = "\n".join(plan["upload"])
    assert "'gdrive:v0.5/Changes from v0.4 to v0.5.xlsx'" in upload and "--drive-import-formats xlsx" in upload
    assert "'gdrive:v0.5/Paper (v0.5).pdf'" in upload
    assert " gdrive:v0.5/Figures/figure-1.png " in upload
    assert "'gdrive:v0.5/Supplementary data files/S4.csv'" in upload and "data files/S5.csv'" in upload


def test_push_sees_a_google_doc_rclone_lists_as_docx_and_will_not_duplicate_it(rounds: Path, tmp_path: Path,
                                                                                monkeypatch) -> None:
    folder, log = drive_project(rounds, tmp_path, monkeypatch)
    refused = rounds_cli("push", "0.5", "--go", "--project", folder)
    assert refused.returncode == 1 and "Paper (v0.5)" in refused.stderr and "Paper (v0.5).pdf" in refused.stderr
    assert "copyto" not in log.read_text(encoding="utf-8")
    done = rounds_cli("push", "0.5", "--go", "--replace", "--project", folder)
    assert done.returncode == 0, done.stderr
    calls = log.read_text(encoding="utf-8")
    assert calls.count("copyto") == 6 and "--ignore-times" in calls
    recorded = projects.read(folder / ".manuscript-skills.yaml")["coauthors"]["rounds"]["0.5"]
    assert recorded["docs"] == {"Paper (v0.5)": "https://docs.google.com/document/d/1DocDocDocDocDocDocDocDoc/edit"}


def test_record_and_circulated_take_a_round_released_by_hand(rounds: Path) -> None:
    folder = rounds / "v0.5"
    configure(folder, "--drive", "connector")
    assert rounds_cli("record", "0.5", "--base", "966c29f", "--released", "2026-10-19", "--project", folder).returncode == 0
    assert rounds_cli("circulated", "0.5", "--commit", "2d6aae5", "--date", "2026-10-26", "--project", folder).returncode == 0
    assert rounds_cli("record", "0.5", "--released", "19 October", "--project", folder).returncode == 2
    entry = projects.read(folder / ".manuscript-skills.yaml")["coauthors"]["rounds"]["0.5"]
    assert entry == {"base": "966c29f", "released": "2026-10-19", "circulated": [{"date": "2026-10-26", "commit": "2d6aae5"}]}


def test_comments_on_a_second_doc_keep_their_own_master(rounds: Path, capsys) -> None:
    """The supplement's Doc pulled after the paper's: its comments are found in the supplement, the paper's are not
    reported gone, and status maps each to its own file in the next round."""
    folder = rounds / "v0.5"
    ledger = folder / "comments.yaml"
    supplement = "# Supplement\n\n## Abstract\n\nTables of every module.\n\n## 1. Introduction\n\n" \
                 "Whole genome sequencing costs have fallen from billions of dollars to under a thousand since 2003.\n"
    (folder / "supplement.md").write_text(supplement, encoding="utf-8")
    cli("import", export(rounds / "paper.docx"), "--ledger", ledger, "--master", folder / "paper.md")
    capsys.readouterr()
    cli("import", export(rounds / "supplement.docx", extra=True, month="11"), "--ledger", ledger, "--master", folder / "supplement.md")
    result = json.loads(capsys.readouterr().out)
    assert result["not_in_this_pull"] == [] and result["new"] == 5
    data = ledger_of(ledger)
    assert data["master"] == "paper.md"
    own = [i for i in data["items"] if i.get("master") == "supplement.md"]
    assert len(own) == 5 and [i["id"] for i in data["items"][:4]] == ["C1", "C2", "S1", "C3"]
    (rounds / "v0.6").mkdir()
    (rounds / "v0.6" / "paper.md").write_text(MASTER, encoding="utf-8")
    (rounds / "v0.6" / "supplement.md").write_text(supplement.replace("billions of dollars", "US$80"), encoding="utf-8")
    capsys.readouterr()
    cli("status", ledger, "--new", rounds / "v0.6" / "paper.md", "--json")
    rows = {r["id"]: r for r in json.loads(capsys.readouterr().out)["items"]}
    billions = next(i["id"] for i in own if i.get("anchor") == "billions of dollars")
    assert rows[billions]["change"] == "changed" and "US$80" in rows[billions]["after"]
    assert rows["C2"]["change"] == "unchanged"  # the paper's own sentence did not change


# --- did the run that produced the round catch the comments (comments.py gaps) ---------------------------------

def run_inventory() -> dict:
    """What the run that produced v0.5 recorded: a problem about the cost sentence, a dismissed flag, a problem the
    co-authors stage made from a comment, and the applied edit that wrote the modules sentence."""
    evidence = [{"path": "stage-report.md", "quote": "x"}]
    def finding(fid: str, summary: str, skills: list[str], assessment: str = "confirmed", quote: str = "") -> dict:
        return {"id": fid, "category": "Claims and evidence", "section": "1. Introduction", "summary": summary,
                "severity": "major", "assessment": assessment, "resolution": "open", "skills": skills,
                "quote": quote, "action": "", "evidence": evidence}
    return {"schema_version": 2, "run_id": "20261020T090000Z-abc", "findings": [
        finding("IC-1", "The sequencing cost quoted is a whole project's budget, not a genome's", ["manuscript-integrity-check"],
                quote="billions of dollars"),
        finding("PE-2", "A list of modules is promised and never given", ["manuscript-prose-edit"], "dismissed"),
        finding("CA-1", "C3 (Bob Ray): Say which modules.", ["manuscript-coauthors"])],
        "changes": [{"id": "IC-C1", "status": "applied", "section": "1. Introduction", "summary": "Define modules",
                     "before": "Modules are files.", "after": "Modules are versioned tables of variants and their evidence."},
                    {"id": "IC-C2", "status": "proposed", "section": "1. Introduction", "summary": "Name the modules",
                     "before": "x", "after": "y"}],
        "dismissed": [{"skill": "manuscript-prose-edit", "summary": "The versioned tables of modules are never named",
                       "why": "Table 1 lists the modules."}], "not_checked": [], "coverage": []}


def gap_file(path: Path, items: dict, run: str = "20261020T090000Z-abc") -> Path:
    path.write_text(yaml.safe_dump({"run": run, "matched_by": "the coordinating agent", "items": items}), encoding="utf-8")
    return path


def test_the_gap_worksheet_names_the_edit_that_wrote_a_passage_and_the_problems_near_it(rounds: Path, tmp_path: Path) -> None:
    ledger = rounds / "v0.5" / "comments.yaml"
    cli("import", export(rounds / "doc.docx"), "--ledger", ledger, "--master", rounds / "v0.5" / "paper.md")
    # The run's records reach the worksheet from its dashboard as well as from its findings.json.
    page = tmp_path / "paper.dashboard.html"
    page.write_text('<html><script type="application/json" id="inventory">'
                    + json.dumps({"inventory": run_inventory(), "summary": {}}) + "</script></html>", encoding="utf-8")
    sheet = tmp_path / "sheet.md"
    assert cli("gaps", ledger, "--inventory", page, "--out", sheet) == 0
    text = sheet.read_text(encoding="utf-8")
    sections = {part.split(" ", 1)[0]: part for part in text.split("\n## ")[1:]}
    assert set(sections) == {"C1", "C2", "S1", "C3"}
    assert "Written by the run's edit IC-C1" in sections["C3"] and "IC-C2" not in text  # applied edits only
    assert "Problem IC-1" in sections["C2"] and "Problem IC-1" not in sections["C3"]
    assert "Dismissed by manuscript-prose-edit" in sections["C3"]
    assert "CA-1" not in text  # made from the comments, so never a candidate for having caught them
    assert "Written by the run" not in sections["C2"]  # its sentence is the authors', unchanged by the run


def test_gap_records_merge_only_when_they_name_the_runs_records(rounds: Path, tmp_path: Path, capsys) -> None:
    ledger, new = answered(rounds)
    inventory = tmp_path / "findings.json"
    inventory.write_text(json.dumps(run_inventory()), encoding="utf-8")
    before = ledger.read_text(encoding="utf-8")
    bad = gap_file(tmp_path / "bad.yaml", {
        "C2": {"verdict": "caught", "findings": ["PE-2"]},  # a dismissed flag is never a match
        "C3": {"verdict": "caught", "findings": ["CA-1"]},  # nor a problem made from the comment itself
        "S1": {"verdict": "introduced", "changes": ["IC-C2"], "miss_reason": "skill-did-not-look", "note": "n"},
        "C1": {"verdict": "missed", "note": "No reason given."},
        "C9": {"verdict": "missed"}})
    assert cli("gaps", ledger, "--inventory", inventory, "--merge", bad) == 1
    err = capsys.readouterr().err
    for words in ("PE-2 is a dismissed flag", "CA-1 was made from the co-authors' comments", "IC-C2 was only proposed",
                  "C1: missed: say why", "skill-did-not-look: name the skill", "C9: not a comment of this ledger"):
        assert words in err
    assert ledger.read_text(encoding="utf-8") == before  # nothing written
    assert cli("gaps", ledger, "--inventory", inventory, "--merge", gap_file(tmp_path / "other.yaml", {}, run="another-run")) == 1
    good = gap_file(tmp_path / "gaps.yaml", {
        "C2": {"verdict": "caught", "findings": ["IC-1"]},
        "C3": {"verdict": "introduced", "changes": ["IC-C1"], "miss_reason": "judged-differently",
               "owner": "manuscript-improve", "note": "The run wrote the sentence  the comment asks about."}})
    capsys.readouterr()
    assert cli("gaps", ledger, "--inventory", inventory, "--merge", good) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["by_verdict"] == {"caught": 1, "partly": 0, "missed": 0, "introduced": 1}
    assert result["not_judged"] == ["C1", "S1"] and result["problems"] == []
    data = ledger_of(ledger)
    assert data["gap_run"] == "20261020T090000Z-abc" and data["gap_matched_by"] == "the coordinating agent"
    by = {i["id"]: i for i in data["items"]}
    assert by["C3"]["gap"]["note"] == "The run wrote the sentence the comment asks about."  # spaces folded
    assert cli("gaps", ledger, "--inventory", inventory, "--check") == 0  # two not judged yet: listed, not a problem
    assert cli("gaps", ledger, "--inventory", inventory, "--check", "--strict") == 1
    by["C1"].update(status="not-on-point", why="A general remark.")  # needs no verdict
    by["S1"]["gap"] = {"verdict": "missed", "miss_reason": "wording-preference", "note": "A preferred word."}
    by["C2"].update(status="addressed", now="Sequencing consumables for a human genome now cost US$80 to US$200.",
                    why="The cost now quotes the consumables.")
    by["S1"].update(status="open", next="Apply the replacement.")
    by["C3"].update(status="declined", why="The modules are named in Table 1 already.")
    ledger.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert cli("gaps", ledger, "--inventory", inventory, "--check", "--strict") == 0
    out = tmp_path / "run" / "manuscript-coauthors" / "findings.json"
    assert cli("findings", ledger, "--new", new, "--out", out) == 0
    block = json.loads(out.read_text(encoding="utf-8"))["coauthors"]
    assert block["gap_run"] == "20261020T090000Z-abc"
    items = {i["id"]: i for i in block["items"]}
    assert items["C2"]["gap"] == {"verdict": "caught", "finding_ids": ["IC-1"], "change_ids": [], "miss_reason": None,
                                  "owner": "", "note": ""}
    assert items["C3"]["gap"]["change_ids"] == ["IC-C1"] and items["C1"]["gap"] is None


def test_a_gap_outside_the_scale_is_a_malformed_ledger(rounds: Path) -> None:
    ledger = rounds / "v0.5" / "comments.yaml"
    cli("import", export(rounds / "doc.docx"), "--ledger", ledger, "--master", rounds / "v0.5" / "paper.md")
    data = ledger_of(ledger)
    data["items"][0]["gap"] = {"verdict": "spotted"}
    ledger.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert cli("status", ledger) == 2


# --- the Google Docs connector's read_doc, as JSON --------------------------------------------------------------


def gdoc_json(path: Path, resolved_by: str = ANN) -> Path:
    """A read_doc answer (commentsIncluded) for MASTER, made up: Ann's comment on "billions of dollars" with Bob's
    reply and Ann's own reply resolving it, an [ai:claude] comment, Bob's suggested replacement old -> new, and his
    suggested bold. Indices are UTF-16 offsets, as Google gives them."""
    paragraphs = [["A Paper\n"], ["Abstract\n"], ["Personal genome analysis requires tools that keep the data local.\n"],
                  ["1. Introduction\n"],
                  ["Whole genome sequencing costs have fallen from ", "billions of dollars",
                   " to under a thousand since 2003.\n"],
                  ["The platform annotates variants with ", ("new", "ins"), ("old", "del"), " words in this sentence.\n"],
                  ["Modules are ", ("versioned", "style"), " tables of variants and their evidence.\n"]]
    content, index, spots = [{"endIndex": 1, "sectionBreak": {}}], 1, {}
    for para in paragraphs:
        elements = []
        for part in para:
            text, kind = (part, "") if isinstance(part, str) else part
            run = {"content": text, "textStyle": {}}
            if kind == "ins":
                run["suggestedInsertionIds"] = ["suggest.r1"]
            elif kind == "del":
                run["suggestedDeletionIds"] = ["suggest.r1"]
            elif kind == "style":
                run["suggestedTextStyleChanges"] = {"suggest.b1": {"textStyle": {"bold": True}}}
            elements.append({"startIndex": index, "endIndex": index + len(text), "textRun": run})
            spots[text] = (index, index + len(text))
            index += len(text)
        content.append({"startIndex": elements[0]["startIndex"], "endIndex": index, "paragraph": {"elements": elements}})

    def post(who: str, when: str, said: str, action: str = "NO_COMMENT_ACTION_CHANGE") -> dict:
        return {"author": {"displayName": who}, "createTime": when, "content": said, "commentAction": action}
    start, end = spots["billions of dollars"]
    doc = {"documentId": "fake", "commentsViewMode": "COMMENTS_VIEW_MODE_INCLUDED", "title": "A Paper (v0.5)",
           "comments": [
               {"commentId": "doco.c1", "anchorId": "kix.a1", "status": "RESOLVED", "plainTextQuote": "billions of dollars",
                "headPost": post(ANN, "2026-10-20T09:30:00.000Z", "This is not true: that was the whole project's budget."),
                "replies": [post(BOB, "2026-10-20T11:00:00.000Z", "Agreed."),
                            post(resolved_by, "2026-10-25T08:00:00.000Z", "Fixed in v0.6, thanks.", "RESOLVE")]},
               {"commentId": "doco.c2", "anchorId": "kix.a2", "status": "OPEN", "plainTextQuote": "Abstract",
                "headPost": post("Ann Lee", "2026-10-20T10:00:00.000Z", "[ai:claude] Consider a shorter title.")}],
           "commentAnchors": {"kix.a1": {"ranges": [{"startIndex": start, "endIndex": end}]},
                              "kix.a2": {"ranges": [{"startIndex": spots["Abstract\n"][0], "endIndex": spots["Abstract\n"][1] - 1}]}},
           "suggestions": [
               {"suggestionId": "suggest.r1", "status": "OPEN", "summaryText": "Replace: “old” with “new”",
                "headPost": {"author": {"displayName": BOB}, "createTime": "2026-10-21T10:00:00.000Z"}},
               {"suggestionId": "suggest.b1", "status": "OPEN", "summaryText": "Format: bold",
                "headPost": {"author": {"displayName": BOB}, "createTime": "2026-10-21T10:05:00.000Z"}}],
           "tabs": [{"tabProperties": {"tabId": "t.0"}, "documentTab": {"body": {"content": content}}}]}
    path.write_text(json.dumps({"content": doc}), encoding="utf-8")
    return path


def test_import_gdoc_reads_ranges_resolution_suggestions_and_people(rounds: Path, capsys) -> None:
    ledger = rounds / "v0.5" / "comments.yaml"
    assert cli("import-gdoc", gdoc_json(rounds / "read.json"), "--ledger", ledger,
               "--master", rounds / "v0.5" / "paper.md") == 0
    result = json.loads(capsys.readouterr().out)
    assert result["new"] == 4 and result["not_located"] == []
    assert {(p["name"], p["handle"]) for p in result["people"]} == {(ANN, "annlee"), (BOB, "bobray")}
    items = {i["id"]: i for i in ledger_of(ledger)["items"]}
    assert [i["id"] for i in ledger_of(ledger)["items"]] == ["C1", "C2", "S1", "S2"]  # paper order
    ai, ann = items["C1"], items["C2"]
    assert ai["ai"] == "claude" and ai["status"] == "not-on-point" and ai["where"] == "Abstract"
    assert ann["anchor"] == "billions of dollars" and ann["where"] == "1. Introduction" and ann["line"] == 9
    assert ann["resolved"] is True and ann["resolved_by"] == "annlee" and ann["gdoc_id"] == "doco.c1"
    assert ann["resolved_on"] == "2026-10-25"
    assert [r["by"] for r in ann["replies"]] == ["bobray", "annlee"]
    assert items["S1"]["edits"] == [{"deleted": "old", "inserted": "new"}] and items["S1"]["by"] == "bobray"
    assert items["S1"]["anchor"] == "old" and items["S1"]["where"] == "1. Introduction"
    assert "bold" in items["S2"]["comment"] and items["S2"]["anchor"] == "versioned"


def test_a_pull_by_the_other_route_knows_each_comment_again(rounds: Path, capsys) -> None:
    """Pulled first as .docx (Google writes a shortened author name there), then through the connector: the same
    comment is one item, matched by the person's handle, the minute and its first words."""
    folder = rounds / "v0.5"
    (folder / "rev-marks.toml").write_text('humans = ["annlee"]\n\n[aliases]\nannlee = ["A Lee"]\n', encoding="utf-8")
    ledger = folder / "comments.yaml"
    doc = export(rounds / "doc.docx")
    with zipfile.ZipFile(doc) as z:
        files = {n: z.read(n).decode() for n in z.namelist()}
    with zipfile.ZipFile(doc, "w") as z:
        for name, text in files.items():
            z.writestr(name, text.replace(f'w:author="{ANN}"', 'w:author="A Lee"'))
    cli("import", doc, "--ledger", ledger, "--master", folder / "paper.md")
    capsys.readouterr()
    cli("import-gdoc", gdoc_json(rounds / "read.json"), "--ledger", ledger, "--master", folder / "paper.md")
    result = json.loads(capsys.readouterr().out)
    budget = [i for i in ledger_of(ledger)["items"] if i.get("anchor") == "billions of dollars"]
    assert len(budget) == 1 and budget[0]["gdoc_id"] == "doco.c1" and budget[0]["by"] == "annlee"
    assert next(p for p in result["people"] if p["name"] == ANN)["rule"] in ("author", "initials", "alias")


def test_import_gdoc_refuses_a_read_without_comments(rounds: Path, capsys) -> None:
    path = gdoc_json(rounds / "read.json")
    data = json.loads(path.read_text())
    data["content"]["commentsViewMode"] = "COMMENTS_VIEW_MODE_OMITTED"
    path.write_text(json.dumps(data))
    assert cli("import-gdoc", path, "--ledger", rounds / "v0.5" / "comments.yaml") == 2
    assert "commentsIncluded" in capsys.readouterr().err


# --- port: a round's comments from Google Docs to the run's dashboard; names a file system takes ---------------


def test_pull_names_each_export_so_every_file_system_takes_it(rounds: Path, tmp_path: Path) -> None:
    """A Drive title with a colon could not be written on NTFS; the local file is renamed, the Drive title kept."""
    folder = rounds / "v0.5"
    configure(folder, "--drive", "rclone", "--drive-remote", "gdrive", "--drive-folder-id", "1AbCdEfGhIjKlMnOp",
              "--release-doc", "paper.md=1. Supplementary Data: Tables (v{round})")
    rounds_cli("record", "0.5", "--doc", "1. Supplementary Data: Tables (v0.5)=https://docs.google.com/document/d/"
               "1xYz0123456789abcdefghij/edit", "--project", folder)
    [step] = json.loads(rounds_cli("pull", "0.5", "--out", tmp_path / "exports", "--project", folder).stdout)["steps"]
    assert step["export"].endswith("/1. Supplementary Data- Tables (v0.5).docx")
    assert step["doc"] == "1. Supplementary Data: Tables (v0.5)"
    assert "'" + step["export"] + "'" in step["commands"][0]
    assert rounds_py.file_name('a<b>c:"d"/e\\f|g?h*.') == "a-b-c--d--e-f-g-h-"



def fake_run(run: Path) -> Path:
    """A run that already has a dashboard, a corrected version and the Word file, as run.json records them."""
    def cmd(script: str, *args: str) -> dict:
        return {"argv": ["uv", "run", "--script", f"scripts/{script}", *args], "exit_code": 0, "state": "finished"}
    d, i = run / "manuscript-dashboard", run / "manuscript-improve"
    for path in (d / "findings.json", d / "findings.2.json", d / "merges.json", d / "manuscript-review.docx"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    for folder in (d / "dashboard", i / "revision", i / "revision.2"):
        folder.mkdir(parents=True)
    data = {"skills": {
        "manuscript-dashboard": {"commands": [
            cmd("collect.py", str(run), "--output", str(d / "findings.2.json"), "--merge", str(d / "merges.json"),
                "--version", "v0.5"),
            cmd("export_docx.py", str(d / "findings.2.json"), "--revision", str(i / "revision.2"), "--output",
                str(d / "manuscript-review.docx"))]},
        "manuscript-improve": {"commands": [
            cmd("revise.py", "orig.md", "work.md", str(d / "findings.2.json"), "--choices", "choices.json",
                "--output-dir", str(i / "revision.2"))]}}}
    (run / "run.json").write_text(json.dumps(data), encoding="utf-8")
    return run


def test_port_replays_the_runs_own_commands_on_the_next_attempts(rounds: Path, tmp_path: Path) -> None:
    folder = rounds / "v0.5"
    configure(folder, "--drive", "connector", "--release-doc", "paper.md=A Paper (v{round})")
    run = fake_run(tmp_path / "run")
    done = rounds_cli("port", "0.5", "--run", run, "--gdoc", gdoc_json(tmp_path / "read.json"), "--project", folder)
    assert done.returncode == 0, done.stderr
    steps = {s["step"]: s["command"] for s in json.loads(done.stdout)["steps"]}
    assert list(steps) == ["pull", "findings", "collect", "corrected version", "dashboard", "export docx"]
    assert all(f"exec {run} --skill" in c for c in steps.values())  # the run records every step
    assert "import-gdoc" in steps["pull"] and "--master " + str(folder / "paper.md") in steps["pull"]
    assert "--untriaged" in steps["findings"] and "--next-round" not in steps["findings"]
    d, i = run / "manuscript-dashboard", run / "manuscript-improve"
    assert f"--output {d / 'findings.3.json'}" in steps["collect"] and f"--merge {d / 'merges.json'}" in steps["collect"]
    assert "manuscript-dashboard/scripts/collect.py" in steps["collect"]
    assert f"{d / 'findings.3.json'} --choices choices.json --output-dir {i / 'revision.3'}" in steps["corrected version"]
    assert f"--output-dir {d / 'dashboard.2'} --revision {i / 'revision.3'}" in steps["dashboard"]
    assert f"--revision {i / 'revision.3'} --output {d / 'manuscript-review.2.docx'}" in steps["export docx"]


def test_port_runs_pull_and_findings_through_the_run(rounds: Path, tmp_path: Path, monkeypatch) -> None:
    """A run with no dashboard yet: port pulls the Doc, records the commenters, and writes the co-authors' findings
    with every comment still open, each step recorded by runs.py."""
    monkeypatch.setenv("MANUSCRIPT_SKILLS_CONFIG", str(tmp_path / "global"))
    folder = rounds / "v0.5"
    configure(folder, "--drive", "connector", "--release-doc", "paper.md=A Paper (v{round})")
    started = CliRunner().invoke(runs.app, ["start", str(folder / "paper.md"), "--skill", "manuscript-coauthors"])
    assert started.exit_code == 0, started.output
    run = Path(started.output.strip())
    done = rounds_cli("port", "0.5", "--run", run, "--gdoc", gdoc_json(tmp_path / "read.json"), "--go",
                      "--project", folder)
    assert done.returncode == 0, done.stdout + done.stderr
    result = json.loads(done.stdout)
    assert [s["step"] for s in result["done"]] == ["pull", "findings"] and "--no-pull" in result["next"]
    found = json.loads((run / "manuscript-coauthors" / "findings.json").read_text())
    assert found["coauthors"]["next_round"] is None and len(found["coauthors"]["items"]) == 4
    assert all(i["change"] is None and i["after"] is None for i in found["coauthors"]["items"])  # never "Unchanged"
    page = (ROOT / "skills" / "manuscript-dashboard" / "assets" / "dashboard.html").read_text(encoding="utf-8")
    assert "pending ? 'Not answered yet' : 'Now'" in page and "c.change && to ?" in page
    assert all("Not triaged yet" in f["action"] for f in found["findings"])
    assert all(i["next"].startswith("Not triaged yet") for i in found["coauthors"]["items"] if i["status"] == "open")
    sys.path.insert(0, str(ROOT / "skills" / "manuscript-dashboard" / "scripts"))
    import dashboard as viz  # the dashboard reads these items as they are
    viz.Coauthors.model_validate(found["coauthors"] | {"items": [
        {k: v for k, v in i.items() if k in viz.CoauthorComment.model_fields} for i in found["coauthors"]["items"]]})
    assert (folder / "rev-marks.toml").is_file()
    recorded = json.loads((run / "run.json").read_text())["skills"]["manuscript-coauthors"]["commands"]
    assert len(recorded) == 2 and all(c["exit_code"] == 0 for c in recorded)


# --- sign-off from the review itself: a resolved thread or a taken suggestion is a co-author having seen it -----

SIGNED = """# A Paper

## 1. Introduction

<!-- @rev C1a rounds=1 by=claude:2026-10-25 -->
Whole genome sequencing costs have fallen to under a thousand dollars since 2003.
<!-- @/rev C1a -->

<!-- @rev C9 rounds=1 by=codex:2026-10-25 -->
The platform annotates variants with new words in this sentence.
<!-- @/rev C9 -->

<!-- @rev C10 rounds=1 by=codex:2026-10-25 -->
Modules are versioned tables of variants and their evidence.
<!-- @/rev C10 -->
"""


def signed_round(rounds: Path) -> tuple[Path, Path]:
    (rounds / "rev-marks.toml").write_text('humans = ["annlee", "bobray"]\n', encoding="utf-8")
    (rounds / ".git").mkdir(exist_ok=True)
    (rounds / "v0.6").mkdir()
    master = rounds / "v0.6" / "paper.md"
    master.write_text(SIGNED, encoding="utf-8")
    ledger = rounds / "v0.5" / "comments.yaml"
    ledger.write_text(yaml.safe_dump({"round": "0.5", "items": [
        {"id": "C1", "kind": "comment", "author": ANN, "by": "annlee", "comment": "Not true.", "status": "addressed",
         "resolved": True, "resolved_by": "annlee", "resolved_on": "2026-10-30"},
        {"id": "C2", "kind": "comment", "author": BOB, "by": "bobray", "comment": "Say which modules.",
         "status": "addressed", "resolved": True, "resolved_by": "[ai:claude]",
         "now": "Modules are versioned tables of variants"},
        {"id": "S1", "kind": "suggestion", "author": BOB, "by": "bobray", "comment": "replace old with new",
         "status": "addressed", "now": "annotates variants with new words"},
        {"id": "C3", "kind": "comment", "author": ANN, "by": "annlee", "comment": "A reminder to myself.",
         "status": "open", "resolved": False}]}), encoding="utf-8")
    return ledger, master


def test_a_resolved_thread_and_a_taken_suggestion_sign_off_the_passages_that_answer_them(rounds: Path, capsys) -> None:
    ledger, master = signed_round(rounds)
    assert cli("signoffs", ledger, "--new", master) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["dry_run"] and plan["unsigned_before"] == 3 and plan["of"] == 3
    assert [(s["segment"], s["by"], s["because"]) for s in plan["signoffs"]] == [
        ("C1a", "annlee", "resolved C1"), ("C9", "bobray", "suggested edit S1 taken")]
    assert [s["item"] for s in plan["skipped"]] == ["C2"]  # an agent closed it: nobody's sign-off
    assert master.read_text(encoding="utf-8") == SIGNED  # a dry run writes nothing
    assert cli("signoffs", ledger, "--new", master, "--go") == 0
    done = json.loads(capsys.readouterr().out)
    assert done["unsigned_after"] == 1
    text = master.read_text(encoding="utf-8")
    assert "@rev C1a rounds=2 by=claude:2026-10-25,annlee:2026-10-30 -->" in text  # dated when she resolved it
    assert "@rev C9 rounds=2 by=codex:2026-10-25,bobray:" in text
    assert ledger_of(ledger)["items"][0]["signed"] == [{"segment": "C1a", "by": "annlee", "on": "2026-10-30"}]
    rm = comments.rev_marks()  # someone else writes after her: her sign-off is still recorded, never added twice
    master.write_text(rm.bump_segment(master.read_text(encoding="utf-8"), "C1a", rm.Entry("claude", rm.date(2026, 11, 1))),
                      encoding="utf-8")
    assert cli("signoffs", ledger, "--new", master) == 0
    assert json.loads(capsys.readouterr().out)["signoffs"] == []  # once only


def test_the_changelog_and_the_release_say_how_many_passages_nobody_signed(rounds: Path, capsys) -> None:
    ledger, master = signed_round(rounds)
    base = rounds / "v0.5" / "paper.md"
    out = rounds / "changes.md"
    assert cli("changelog", "--base", base, "--new", master, "--ledger", ledger, "--out", out) == 0
    assert out.read_text(encoding="utf-8").startswith(
        "> 3 of 3 marked passages were last written by an AI or agent, with no person's sign-off recorded since")
    configure(rounds / "v0.6", "--drive", "connector", "--release-doc", "paper.md=Paper (v{round})")
    plan = json.loads(rounds_cli("push", "0.6", "--project", rounds / "v0.6").stdout)
    assert plan["no_sign_off"] == {"paper.md": "3 of 3 marked passages were last written by an AI or agent with no "
                                                "person's sign-off since"}


def test_a_changelog_asked_for_as_xlsx_is_a_real_workbook(rounds: Path) -> None:
    """The release uploads build/changes-from-v{previous}.xlsx as a Google Sheet; Markdown in a file with that name
    could not be imported."""
    from openpyxl import load_workbook
    ledger, master = signed_round(rounds)
    out = rounds / "build" / "changes-from-v0.5.xlsx"
    assert cli("changelog", "--base", rounds / "v0.5" / "paper.md", "--new", master, "--ledger", ledger,
               "--out", out) == 0
    book = load_workbook(out)
    assert book.sheetnames == ["Changes", "Record"]
    rows = [[c.value for c in row] for row in book["Changes"].iter_rows()]
    assert rows[0][0].startswith("3 of 3 marked passages") and ["Id", "Where", "Was", "Now", "Why"] in rows
    assert book["Record"].max_row >= 1


def test_push_stops_when_the_build_left_a_figure_out(rounds: Path, tmp_path: Path) -> None:
    """pandoc warns "Could not convert image" (no rsvg-convert for an SVG) and still writes the Doc; the release
    would have gone up without the figure."""
    folder = rounds / "v0.5"
    drive = tmp_path / "Google Drive"
    warn = "import sys; sys.stderr.write('[WARNING] Could not convert image figures/fig1.svg: check rsvg-convert')"
    configure(folder, "--drive", "folder", "--drive-folder", str(drive), "--release-doc", "paper.md",
              "--release-build", f'"{sys.executable}" -c "{warn}"')
    (folder / "build").mkdir()
    (folder / "build" / "paper.docx").write_bytes(b"docx")
    done = rounds_cli("push", "0.5", "--go", "--project", folder)
    assert done.returncode == 3 and "figures/fig1.svg" in done.stderr and "rsvg-convert" in done.stderr
    assert not (drive / "v0.5").exists()


def test_a_findings_quote_never_crosses_a_revision_mark_or_a_table_cell(rounds: Path, capsys) -> None:
    """stage_check refuses a quote with a revision mark inside it, and one across table cells is not in the master
    as written; findings takes a clean stretch of the commented passage instead."""
    folder = rounds / "v0.5"
    marked = MASTER.replace(
        "Whole genome sequencing costs have fallen from billions of dollars to under a thousand since 2003.",
        "Whole genome sequencing costs have <!-- @rev C90 rounds=1 by=claude:2026-10-01 -->fallen from billions of "
        "dollars<!-- @/rev C90 --> to under a thousand since 2003.") + "\n| Tool | Speed |\n|---|---|\n| SoilTrace | fast |\n"
    (folder / "paper.md").write_text(marked, encoding="utf-8")
    ledger = folder / "comments.yaml"
    ledger.write_text(yaml.safe_dump({"round": "0.5", "master": "paper.md", "items": [
        {"id": "C1", "kind": "comment", "author": ANN, "anchor": "costs have fallen from billions",
         "context_before": "Whole genome sequencing", "context_after": "of dollars to under", "comment": "Source?",
         "status": "open", "next": "Cite the cost source."},
        {"id": "C2", "kind": "comment", "author": ANN, "anchor": "Speed SoilTrace fast", "context_before": "Tool",
         "context_after": "", "comment": "Measured how?", "status": "open", "next": "Say how speed was measured."}]}))
    assert cli("findings", ledger, "--new", folder / "paper.md", "--out", rounds / "f.json") == 0
    quotes = [f["quote"] for f in json.loads((rounds / "f.json").read_text())["findings"]]
    assert all(q and len(q.split()) >= 3 and "|" not in q and q in " ".join(marked.split()) for q in quotes if q), quotes
