"""manuscript-coauthors: the co-authors' comments on a round (comments.py) and the rounds on Google Drive (rounds.py).

The Doc exports are built at test time the way Google Docs writes them (checked against a real export, 2026-10-28):
each comment and each reply is a Word comment on the same range with no thread record, a comment over several
ranges is one identical copy per range, and suggested edits are tracked insertions and deletions. Run with
`uv run pytest`."""
from __future__ import annotations

import importlib.util
import json
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


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"coauthors_{name}", SKILL / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


comments = _load("comments")
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
    assert items["C1"]["replies"] == [{"author": BOB, "date": "2026-10-20T11:00:00Z", "text": "Agreed, small fixes only."}]
    assert items["C2"]["anchor"] == "billions of dollars" and items["C2"]["where"] == "1. Introduction"
    assert items["C2"]["line"] == 9 and items["C2"]["status"] == "open"
    assert items["S1"]["kind"] == "suggestion" and items["S1"]["edits"] == [{"deleted": "old", "inserted": "new"}]
    assert "replace “old” with “new”" in items["S1"]["comment"]
    assert items["C3"]["comment"] == "Say which modules."  # one comment over two ranges, once
    assert ledger_of(ledger)["sources"][0]["doc"].endswith("/abc/edit")


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
