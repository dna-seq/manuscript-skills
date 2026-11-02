"""The run's review in the authors' own Google Doc: the corrected version's edits as suggested edits, what needs the
authors as comments, sent a batch at a time and read back. A small model of a Google Doc stands in for the
connector: it applies the planned requests as Google does (a suggested insertion is new text, a suggested deletion
stays until decided, a comment moves no index) and lets a test accept or reject a suggestion."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


viz = load("dashboard", ROOT / "skills/manuscript-dashboard/scripts/dashboard.py")
revise = load("revise", ROOT / "skills/manuscript-improve/scripts/revise.py")
gdoc = load("export_gdoc", ROOT / "skills/manuscript-dashboard/scripts/export_gdoc.py")

ORIGINAL = """# A tool

## 1. Introduction

Genomes are cheap. This tool plays a crucial role in annotation. We use HuggingFace for data.

| Engine | Time |
|---|---|
| PLINK2 | 5.7 s |

## 2. Methods

The pipeline joins by rsID. It is fast. See [the code](https://example.org/code).
"""
# The same paper as its Google Doc shows it: no Markdown, the table as cells, the link by its text.
DOC = ["A tool", "1. Introduction", "Genomes are cheap. This tool plays a crucial role in annotation. We use HuggingFace for data.",
       "Engine", "Time", "PLINK2", "5.7 s", "2. Methods", "The pipeline joins by rsID. It is fast. See the code."]


def evidence() -> list[dict]:
    return [{"path": "review.md", "quote": "The review."}]


@pytest.fixture()
def run(tmp_path: Path) -> Path:
    (tmp_path / "review.md").write_text("The review.")
    (tmp_path / "original.md").write_text(ORIGINAL)
    (tmp_path / "working.md").write_text(ORIGINAL.replace("HuggingFace", "Hugging Face"))
    inventory = {
        "schema_version": 2, "title": "Review", "run_id": "run-1", "scope": "Whole paper.",
        "coverage": [{"skill": skill, "status": "completed", "note": "All.", "evidence": evidence()}
                     for skill in ("manuscript-improve", "manuscript-integrity-check")],
        "findings": [
            {"id": "IC-1", "category": "Text versus code", "section": "2. Methods", "summary": "The join key contradicts the code",
             "severity": "major", "assessment": "confirmed", "resolution": "open", "stage": "now",
             "skills": ["manuscript-integrity-check"], "evidence": evidence(), "quote": "The pipeline joins by rsID."},
            {"id": "IC-2", "category": "Claims", "section": "2. Methods", "summary": "Speed is claimed without a number",
             "severity": "major", "assessment": "confirmed", "resolution": "open", "stage": "now", "detail": "No timing is given.",
             "action": "Give the runtime.", "skills": ["manuscript-integrity-check"], "evidence": evidence(),
             "quote": "It is fast."},
            {"id": "IC-3", "category": "Scope", "section": "1. Introduction", "summary": "Whether to claim clinical use",
             "severity": "major", "assessment": "confirmed", "resolution": "open", "stage": "now",
             "skills": ["manuscript-integrity-check"], "evidence": evidence(), "quote": "Genomes are cheap."},
        ],
        "decisions": [{"id": "D1", "summary": "Decide whether the paper claims clinical use", "finding_ids": ["IC-3"]}],
        "manuscript": {"title": "A tool", "path": "original.md", "sections": ["1. Introduction", "2. Methods"]},
        "changes": [
            {"id": "prose-edit.C1", "kind": "Applied edit", "section": "1. Introduction", "summary": "Spell the company's name",
             "status": "applied", "before": "We use HuggingFace for data.", "after": "We use Hugging Face for data.",
             "evidence": evidence()},
            {"id": "IC-C1", "kind": "Proposed edit", "section": "2. Methods", "summary": "Name the real join key", "status": "proposed",
             "finding_ids": ["IC-1"], "before": "The pipeline joins by rsID.",
             "after": "The pipeline joins by position and genotype [AUTHORS: which genome build?].", "evidence": evidence(),
             "why": "The code joins on position and genotype."},
            {"id": "ST-C1", "kind": "Story edit", "section": "1. Introduction", "summary": "Say what the tool does",
             "status": "proposed", "before": "This tool plays a crucial role in annotation.", "after": "This tool annotates variants.",
             "evidence": evidence()},
        ],
    }
    (tmp_path / "findings.json").write_text(json.dumps(inventory))
    result = CliRunner().invoke(revise.app, [str(tmp_path / "original.md"), str(tmp_path / "working.md"),
                                             str(tmp_path / "findings.json"), "--output-dir", str(tmp_path / "revision")])
    assert result.exit_code == 0, result.output
    return tmp_path


class Doc:
    """A Google Doc as read_doc shows it, and as update_doc changes it: characters with the suggestion that inserted
    or would delete each, comments on index ranges, and a revision id that changes with every batch."""

    def __init__(self, paragraphs: list[str]) -> None:
        self.chars = [{"c": c, "ins": None, "del": None} for p in paragraphs for c in p + "\n"]
        self.comments: list[dict] = []
        self.revision, self.suggestions = 1, 0

    def index(self, n: int) -> int:
        return 1 + sum(len(ch["c"].encode("utf-16-le")) // 2 for ch in self.chars[:n])

    def position(self, index: int) -> int:
        n = 0
        while n < len(self.chars) and self.index(n) < index:
            n += 1
        assert self.index(n) == index, f"index {index} falls inside a character"
        return n

    def send(self, batch: dict) -> None:
        control = batch["writeControl"]
        assert control.get("requiredRevisionId") in (None, f"rev{self.revision}"), "the Doc changed since the read"
        suggest = control.get("writeMode") == "SUGGEST"
        for request in batch["requests"]:
            (kind, body), = request.items()
            if kind == "insertComment":
                start, end = body["range"]["startIndex"], body["range"]["endIndex"]
                quote = "".join(ch["c"] for ch in self.chars[self.position(start):self.position(end)])
                self.comments.append({"commentId": f"doco.{len(self.comments) + 1}", "anchorId": f"kix.{len(self.comments) + 1}",
                                      "status": "OPEN", "plainTextQuote": quote, "range": (start, end), "replies": [],
                                      "headPost": {"author": {"displayName": "Ann Lee"}, "content": body["content"],
                                                   "createTime": "2026-11-02T10:00:00Z"}})
                continue
            assert suggest, "the text of a shared Doc changes only by suggestion"
            self.suggestions += 1
            sid = f"suggest.{self.suggestions}"
            if kind == "insertText":
                at = self.position(body["location"]["index"])
                self.chars[at:at] = [{"c": c, "ins": sid, "del": None} for c in body["text"]]
            else:
                a, b = self.position(body["range"]["startIndex"]), self.position(body["range"]["endIndex"])
                for ch in self.chars[a:b]:
                    ch["del"] = sid
        self.revision += 1

    def decide(self, words: str, accept: bool) -> None:
        """Accept or reject the suggestion whose text holds these words, with the one beside it: a replacement sent
        as an insertion and a deletion is two suggestions, and a person decides both."""
        ids = {sid for ch in self.chars for sid in (ch["ins"], ch["del"])
               if sid and words in self.text(lambda c, s=sid: s in (c["ins"], c["del"]))}
        assert ids, words
        for n, ch in enumerate(self.chars):
            if ch["ins"] in ids or ch["del"] in ids:
                for near in self.chars[max(n - 1, 0):n + 2]:
                    ids |= {sid for sid in (near["ins"], near["del"]) if sid}
        kept = []
        for ch in self.chars:
            if ch["ins"] in ids:
                if accept:
                    kept.append(ch | {"ins": None})
            elif ch["del"] in ids:
                if not accept:
                    kept.append(ch | {"del": None})
            else:
                kept.append(ch)
        self.chars = kept
        self.revision += 1

    def text(self, keep=lambda ch: True) -> str:
        return "".join(ch["c"] for ch in self.chars if keep(ch))

    def accepted_all(self) -> str:
        return self.text(lambda ch: not ch["del"])

    def read(self, path: Path) -> Path:
        content, paragraph, start = [{"endIndex": 1, "sectionBreak": {}}], [], 1
        n = 0
        while n < len(self.chars):
            m = n
            while m < len(self.chars) and (self.chars[m]["ins"], self.chars[m]["del"]) == (self.chars[n]["ins"], self.chars[n]["del"]) \
                    and (m == n or self.chars[m - 1]["c"] != "\n"):
                m += 1
            run = {"content": "".join(ch["c"] for ch in self.chars[n:m]), "textStyle": {}}
            if self.chars[n]["ins"]:
                run["suggestedInsertionIds"] = [self.chars[n]["ins"]]
            if self.chars[n]["del"]:
                run["suggestedDeletionIds"] = [self.chars[n]["del"]]
            paragraph.append({"startIndex": self.index(n), "endIndex": self.index(m), "textRun": run})
            if self.chars[m - 1]["c"] == "\n":
                content.append({"startIndex": paragraph[0]["startIndex"], "endIndex": self.index(m),
                                "paragraph": {"elements": paragraph}})
                paragraph = []
            n = m
        doc = {"documentId": "1DocDocDocDocDocDocDocDocDoc", "title": "A tool (v0.7)", "revisionId": f"rev{self.revision}",
               "commentsViewMode": "COMMENTS_VIEW_MODE_INCLUDED",
               "comments": [{k: v for k, v in c.items() if k != "range"} for c in self.comments],
               "commentAnchors": {c["anchorId"]: {"ranges": [{"startIndex": c["range"][0], "endIndex": c["range"][1]}]}
                                  for c in self.comments},
               "suggestions": [], "tabs": [{"tabProperties": {"tabId": "t.0"}, "documentTab": {"body": {"content": content}}}]}
        path.write_text(json.dumps({"content": doc}), encoding="utf-8")
        return path


def plan(run: Path, doc: Doc, *extra: str) -> tuple[int, dict]:
    code = gdoc.main(["plan", str(run / "findings.json"), str(doc.read(run / "read.json")), "--revision", str(run / "revision"),
                      "--out", str(run / "plan.json"), *extra])
    return code, json.loads((run / "plan.json").read_text(encoding="utf-8"))


def status(run: Path, doc: Doc, capsys, *extra: str) -> dict:
    capsys.readouterr()
    assert gdoc.main(["status", str(run / "findings.json"), str(doc.read(run / "read.json")), "--revision",
                      str(run / "revision"), *extra]) == 0
    return json.loads(capsys.readouterr().out)


def post_all(run: Path, doc: Doc) -> list[dict]:
    batches = []
    for _ in range(4):
        code, result = plan(run, doc, "--check")
        if result["done"]:
            assert code == 0
            return batches
        assert code == 1 and result["left"]
        batches.append(result["batch"])
        doc.send(result["batch"])
    raise AssertionError("the plan never finished")


def test_the_review_goes_in_as_comments_first_then_suggested_edits_and_a_second_plan_adds_nothing(run: Path) -> None:
    doc = Doc(DOC)
    comments, edits = post_all(run, doc)
    assert comments["what"] == "comments" and "writeMode" not in comments["writeControl"]
    assert edits["what"] == "suggested edits" and edits["writeControl"]["writeMode"] == "SUGGEST"
    assert comments["writeControl"]["requiredRevisionId"] == "rev1" and edits["writeControl"]["requiredRevisionId"] == "rev2"
    on = {c["headPost"]["content"].rsplit("(", 1)[1].rstrip(")"): c for c in doc.comments}
    # the To-do tab's items, as the Word review has them: proposals with their reasoning and questions, the decision
    assert set(on) == {"D1", "IC-C1", "ST-C1", "IC-2"}
    assert all(c["headPost"]["content"].startswith("[ai:claude] ") for c in doc.comments)
    assert on["IC-C1"]["plainTextQuote"] == "rsID." and "which genome build?" in on["IC-C1"]["headPost"]["content"]
    assert on["ST-C1"]["plainTextQuote"] == "plays a crucial role in annotation."
    assert on["D1"]["plainTextQuote"] == "Genomes are cheap." and "A decision only you can make" in on["D1"]["headPost"]["content"]
    assert on["IC-2"]["plainTextQuote"] == "It is fast." and "Give the runtime." in on["IC-2"]["headPost"]["content"]
    # every edit of the corrected version is a suggestion; accepted, the Doc reads as the corrected version
    accepted = doc.accepted_all()
    assert "This tool annotates variants. We use Hugging Face for data." in accepted
    assert "The pipeline joins by position and genotype. It is fast. See the code." in accepted
    assert doc.text(lambda ch: not ch["ins"]) == "\n".join(DOC) + "\n"  # rejected, it reads as before
    _, again = plan(run, doc)
    assert again["done"] and again["counts"] == {"pending": 3, "posted": 4}
    record = json.loads((run / "gdoc-review.json").read_text(encoding="utf-8"))
    assert record["doc"] == "1DocDocDocDocDocDocDocDocDoc" and len(record["posted"]) == 7


def test_the_doc_decides_the_edits_and_the_answers_become_to_do_marks(run: Path, capsys) -> None:
    doc = Doc(DOC)
    post_all(run, doc)
    doc.decide("position and genotype", accept=True)
    doc.decide("annotates variants", accept=False)
    doc.decide("Hugging Face", accept=False)
    decision = next(c for c in doc.comments if c["headPost"]["content"].endswith("(D1)"))
    decision["replies"] = [{"author": {"displayName": "Bob Ray"}, "content": "No clinical claim; keep it research only.",
                            "createTime": "2026-11-03T09:00:00Z"}]
    marks_file = run / "original.todo.json"
    result = status(run, doc, capsys, "--marks", str(marks_file), "--mark", "D1=redundant", "--undo", str(run / "undo.json"))
    by_key = {i["key"]: i for i in result["items"]}
    assert by_key["edit IC-C1"]["status"] == "accepted" and by_key["edit ST-C1"]["status"] == "rejected"
    assert by_key["edit prose-edit.C1"]["status"] == "rejected"
    assert by_key["D1"]["replies"] == [{"by": "Bob Ray", "text": "No clinical claim; keep it research only.", "resolved": False}]
    marks = {m.id: m for m in viz.MarksFile.model_validate_json(marks_file.read_text(encoding="utf-8")).marks}
    assert (marks["IC-C1"].mark, marks["IC-C1"].kind, marks["IC-C1"].reason) == ("approved", "proposal", "Accepted in the Google Doc.")
    assert marks["ST-C1"].mark == "redundant" and marks["ST-C1"].before == "This tool plays a crucial role in annotation."
    assert (marks["D1"].mark, marks["D1"].reason) == ("redundant", "Bob Ray: No clinical claim; keep it research only.")
    assert "IC-2" not in marks  # a problem nobody answered stays open
    # the plain applied edit the Doc rejected goes back, as an edit for runs.py apply on the applied version
    [undo] = json.loads((run / "undo.json").read_text(encoding="utf-8"))
    assert undo["before"].endswith("We use Hugging Face for data.") and undo["after"].endswith("We use HuggingFace for data.")
    # a mark the authors made in the To-do tab stands; the Doc's other answer is listed
    data = json.loads(marks_file.read_text(encoding="utf-8"))
    data["marks"] = [m | {"mark": "approved"} if m["id"] == "ST-C1" else m for m in data["marks"] if m["id"] != "IC-C1"]
    marks_file.write_text(json.dumps(data), encoding="utf-8")
    again = status(run, doc, capsys, "--marks", str(marks_file))
    assert again["marks"]["added"] == [{"id": "IC-C1", "mark": "approved"}]
    assert again["marks"]["kept_from_the_tab"] == [{"id": "ST-C1", "kept": "approved", "the_doc_says": "redundant"}]


def test_a_co_authors_pending_suggestion_and_a_drifted_passage_are_left_alone(run: Path) -> None:
    # a word beside an edit may change (it is placed by its own words); the edited word itself may not
    drifted = [p.replace("joins by rsID.", "now joins by rs ID.") for p in DOC]
    doc = Doc(drifted)
    doc.send({"writeControl": {"writeMode": "SUGGEST"}, "requests": [{"insertText": {"text": "Huggingface ", "location": {
        "index": doc.index(doc.text().index("HuggingFace"))}}}]})
    _, first = plan(run, doc)
    statuses = {i["key"]: i["status"] for i in first["items"]}
    assert statuses["edit prose-edit.C1"] == "a co-author's suggestion is pending here"
    assert statuses["edit IC-C1"] == "not found" and first["not_found"][0]["why"] == "the Doc reads differently here"
    assert [i["key"] for i in first["left_alone"]] == ["edit prose-edit.C1"]
    post_all(run, doc)
    # only the story edit went in as a suggestion; the drifted passage's comment found its section's heading
    assert "annotates variants" in doc.accepted_all() and "Hugging Face" not in doc.accepted_all()
    ic = next(c for c in doc.comments if c["headPost"]["content"].endswith("(IC-C1)"))
    assert ic["plainTextQuote"] == "2. Methods"


def test_a_read_without_comments_and_another_docs_record_are_refused(run: Path, capsys) -> None:
    doc = Doc(DOC)
    path = doc.read(run / "read.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["content"]["comments"], data["content"]["commentsViewMode"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert gdoc.main(["plan", str(run / "findings.json"), str(path)]) == 2
    assert "commentsIncluded" in capsys.readouterr().err
    (run / "gdoc-review.json").write_text(json.dumps({"doc": "another", "title": "Other", "posted": {}}))
    assert gdoc.main(["plan", str(run / "findings.json"), str(doc.read(run / "read.json"))]) == 2
    assert "another Doc" in capsys.readouterr().err
    assert gdoc.main(["plan", str(run / "findings.json"), str(doc.read(run / "read.json")), "--as", "Claude Code",
                      "--record", str(run / "r.json")]) == 2


def test_deletions_additions_new_paragraphs_and_markup_only_edits_land_as_the_corrected_version_reads(tmp_path: Path) -> None:
    reviewed = ("Genomes are cheap. This tool plays a crucial role in annotation. We use HuggingFace for data.\n\n"
                "The pipeline joins by rsID. It is *fast*.\n")
    pieces = [{"text": "Genomes are cheap. This tool plays a "},
              {"old": "crucial ", "new": "", "ids": ["DS-C1"], "status": "applied"},  # a deletion
              {"text": "role in annotation. We use "},
              {"old": "HuggingFace", "new": "Hugging Face", "ids": ["PE-C1"], "status": "applied"},  # right before the next
              {"text": " for "},
              {"old": "", "new": "all the ", "ids": ["PE-C2"], "status": "applied"},  # words before a word
              {"text": "data.\n\nThe pipeline joins by rsID. It is "},
              {"old": "*fast*", "new": "fast", "ids": ["PE-C3"], "status": "applied"},  # markup only: nothing a Doc shows
              {"text": "."},
              {"old": "", "new": "\n\nA new paragraph follows here.", "ids": ["ST-C2"], "status": "applied"},
              {"text": "\n"}]
    assert "".join(p.get("text", p.get("old", "")) for p in pieces) == reviewed
    changes = [{"id": p["ids"][0], "kind": "Applied edit", "section": "Body", "summary": "An edit", "status": "applied",
                "before": p["old"] or None, "after": p["new"] or None, "anchor": "data." if not p["old"] else None,
                "evidence": evidence()} for p in pieces if "ids" in p]
    (tmp_path / "review.md").write_text("The review.")
    inventory = {"schema_version": 2, "title": "Review", "run_id": "run-2", "scope": "Whole paper.",
                 "coverage": [{"skill": "manuscript-improve", "status": "completed", "note": "All.", "evidence": evidence()}],
                 "findings": [], "changes": changes}
    (tmp_path / "findings.json").write_text(json.dumps(inventory))
    import hashlib
    (tmp_path / "revision").mkdir()
    (tmp_path / "revision" / "revision.json").write_text(json.dumps({
        "pieces": pieces, "applied": [c["id"] for c in changes], "comments": [], "held": [],
        "inventory_sha256": hashlib.sha256((tmp_path / "findings.json").read_bytes()).hexdigest()}))
    doc = Doc(["Genomes are cheap. This tool plays a crucial role in annotation. We use HuggingFace for data.",
               "The pipeline joins by rsID. It is fast."])
    [edits] = post_all(tmp_path, doc)
    assert doc.accepted_all() == ("Genomes are cheap. This tool plays a role in annotation. We use Hugging Face for all the "
                                  "data.\nThe pipeline joins by rsID. It is fast.\nA new paragraph follows here.\n")
    _, again = plan(tmp_path, doc)
    statuses = {i["key"]: i["status"] for i in again["items"]}
    assert statuses == {"edit DS-C1": "pending", "edit PE-C1": "pending", "edit PE-C2": "pending", "edit ST-C2": "pending"}


def test_reasons_add_a_comment_on_each_applied_edit_and_none_on_a_proposal(run: Path) -> None:
    doc = Doc(DOC)
    for _ in range(3):
        _, result = plan(run, doc, "--reasons")
        if result["done"]:
            break
        doc.send(result["batch"])
    reasons = [c for c in doc.comments if "(edit " in c["headPost"]["content"]]
    assert [c["headPost"]["content"] for c in reasons] == ["[ai:claude] Spell the company's name. (edit prose-edit.C1)"]
    assert reasons[0]["plainTextQuote"] == "HuggingFace"
