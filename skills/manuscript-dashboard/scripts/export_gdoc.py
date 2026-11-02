# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pydantic>=2.6", "markdown-it-py>=3", "pyyaml>=6"]
# ///
"""The run's review in the authors' own Google Doc: each edit of the corrected version as a suggested edit, and what
needs the authors as comments, written through the Google Docs connector, then read back.

    uv run --script export_gdoc.py plan RUN/manuscript-dashboard/findings.json READ_DOC.json \
        --revision RUN/manuscript-improve/revision [--tab t.0] [--as claude] [--reasons] [--record FILE] [--check]
    uv run --script export_gdoc.py status RUN/manuscript-dashboard/findings.json READ_DOC.json \
        --revision RUN/manuscript-improve/revision [--marks STEM.todo.json] [--mark ID=approved|redundant ...] \
        [--undo RUN/manuscript-dashboard/gdoc-undo.json]

READ_DOC.json is the Google Docs connector's read_doc answer for a Doc that holds the reviewed text (a round's Doc,
or the Doc the authors write in), with commentsIncluded: true, saved as JSON.

`plan` gives the next batch of documents.batchUpdate requests to send with update_doc, one batch at a time: first
the comments (direct, `insertComment`), then the suggested edits (`writeControl.writeMode: SUGGEST`), each batch
guarded by the revision it was planned on (`requiredRevisionId`). After sending a batch, read the Doc again and run
`plan` again: it plans only what the Doc does not hold yet, so it is safe to repeat, and says `done` when nothing is
left (`--check` exits 1 until then).

- Every edit of the corrected version (revise.py's pieces: the applied edits and the proposals in this version) is
  a suggested edit, never a direct change: the authors and co-authors accept or reject it in the Doc. A suggestion
  carries words, not formatting (a new word takes the style around it).
- The comments are the To-do tab's items, as the Word review's: each question on an edit, each proposal's reasoning,
  each decision only the authors can make, each open blocker or major problem nothing else answers (`--reasons`
  adds each applied edit's reasoning). Each opens with `[ai:NAME]`, since it appears under the name of the Google
  account the connector is signed in to, and ends with its ID in parentheses, which is how a later plan knows it.
- A passage is found in the Doc by its words as the Doc shows them (manuscript-coauthors' reading of a master: no
  Markdown, links by their text), aligned with the whole reviewed text, so a sentence that recurs is placed by its
  neighbours. One the Doc does not hold is listed under `not_found` and never guessed at. A comment whose passage is
  missing goes on its section's heading. An edit where a suggestion is already pending (a co-author's) is left
  alone and listed.

`status` reads the Doc back: each suggestion pending, accepted (the Doc reads the new words, no suggestion left),
rejected (it reads the old words again) or edited by hand; each comment with its replies and whether it was
resolved. `--marks` writes what the Doc decided into the To-do marks file the next run reads (STEM.todo.json,
beside the manuscript): an edit that asked a question or a proposal, accepted, is approved, and rejected, redundant,
with the replies on its comment as the reason. Decisions and problems are answered in words, so the agent reads the
replies and records each with `--mark ID=approved|redundant`. A mark the authors already made in the To-do tab is
kept, and listed when the Doc says otherwise. `--undo` writes each plain applied edit the Doc rejected as an edit
that puts the old words back, for runs.py apply.

The record of what was posted (RUN/manuscript-dashboard/gdoc-review.json by default) is what tells a rejected
suggestion from one never posted.

EXIT STATUS 0 done · 1 plan --check: something is left to post · 2 usage, or not a read_doc answer · 3 could not run
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import dashboard as viz  # noqa: E402


def load(name: str, path: Path):
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # its dataclasses resolve their module through sys.modules
        spec.loader.exec_module(module)
    return sys.modules[name]


cm = load("coauthors_comments", HERE.parents[2] / "manuscript-coauthors" / "scripts" / "comments.py")
shade = load("shade_gdoc", HERE.parents[2] / "manuscript-revision-marks" / "scripts" / "gdoc_shade.py")

SEVERITY = {"blocker": "Blocker", "major": "Major", "minor": "Minor", "info": "Optional", "unknown": "Could not be checked"}
WHEN = {"now": "fix now", "writing": "then the writing", "journal": "once you have chosen the journal",
        "final": "before submission, once the code is final", "unknown": "stage not set"}
AGENT = re.compile(r"[a-z0-9][a-z0-9-]{0,30}")


class Failure(Exception):
    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


# --- the Doc -----------------------------------------------------------------------------------------------------


def units(ch: str) -> int:
    return len(ch.encode("utf-16-le")) // 2  # Google counts indices in UTF-16 code units


def doc_tokens(runs: list[dict]) -> tuple[list[tuple[str, int, int]], dict[int, str]]:
    """The Doc's words as it stands, as sync reads it (a pending insertion left out, a pending deletion kept), each
    with its index range; and the character at each index, for the spaces around a range."""
    chars: list[tuple[str, int]] = []
    for run in runs:
        if run["ins"]:
            continue
        at = run["start"]
        for ch in run["text"]:
            chars.append((ch, at))
            at += units(ch)
    tokens, word = [], []
    for ch, at in [*chars, (" ", -1)]:
        if not ch.isspace():
            word.append((ch, at))
            continue
        if word:
            text = "".join(c for c, _ in word).translate(cm.QUOTES)
            if not cm.MARKUP_ONLY.fullmatch(text):
                tokens.append((text, word[0][1], word[-1][1] + units(word[-1][0])))
            word = []
    return tokens, {at: ch for ch, at in chars}


def pending_in(runs: list[dict], a: int, b: int) -> dict[str, dict[str, list[str]]]:
    """The suggestions pending on [a, b] (an insertion at either end counts): each id's inserted and deleted words."""
    found: dict[str, dict[str, list[str]]] = {}
    for run in runs:
        if run["start"] <= b and run["end"] >= a and (run["ins"] or run["del"]):
            for sid in run["ins"]:
                found.setdefault(sid, {"ins": [], "del": []})["ins"] += run["text"].translate(cm.QUOTES).split()
            for sid in run["del"]:
                found.setdefault(sid, {"ins": [], "del": []})["del"] += run["text"].translate(cm.QUOTES).split()
    return found


def threads(doc: dict) -> list[dict]:
    return [t for t in doc.get("comments") or [] if isinstance(t, dict)]


def said(post: dict) -> str:
    return str((post or {}).get("content") or "")


def thread_for(doc: dict, key: str) -> dict | None:
    """The comment an earlier plan posted for this item: an agent's, ending with the item's ID in parentheses."""
    return next((t for t in threads(doc) if cm.ai_of(said(t.get("headPost"))) and said(t.get("headPost")).rstrip()
                 .endswith(f"({key})")), None)


# --- the reviewed text and its edits -----------------------------------------------------------------------------


def texts(revision: dict | None) -> tuple[str, str, str, list[dict]]:
    """The reviewed text, the corrected version (every edit in), the applied version (the applied edits only) and
    each edit with its span in each."""
    reviewed = corrected = applied = ""
    edits: list[dict] = []
    for piece in (revision or {}).get("pieces", []):
        if "text" in piece:
            reviewed, corrected, applied = reviewed + piece["text"], corrected + piece["text"], applied + piece["text"]
            continue
        now = piece["new"] if piece["status"] == "applied" else piece["old"]
        edits.append({**piece, "key": "edit " + ", ".join(piece["ids"]), "old_span": (len(reviewed), len(reviewed) + len(piece["old"])),
                      "new_span": (len(corrected), len(corrected) + len(piece["new"])),
                      "applied_span": (len(applied), len(applied) + len(now))})
        reviewed, corrected, applied = reviewed + piece["old"], corrected + piece["new"], applied + now
    return reviewed, corrected, applied, edits


def around(tokens: list[tuple[str, int, int]], start: int, end: int) -> list[int]:
    """The tokens an edit at [start, end) touches; for an addition between two spaces, the word before it (or after,
    at the very start), so the change is placed against a word."""
    touched = [i for i, (_, a, b) in enumerate(tokens) if a <= end and b >= start]
    if touched or not tokens:
        return touched
    before = [i for i, (_, _, b) in enumerate(tokens) if b <= start]
    return [before[-1]] if before else [0]


def words_with_breaks(text: str) -> list[tuple[str, str]]:
    """Each shown word of *text* with what separates it from the one before: a new paragraph, or a space."""
    out: list[tuple[str, str]] = []
    last = None
    for tok, start, end in cm.shown_tokens(text):
        gap = text[last:start] if last is not None else ""
        out.append((tok, "\n" if gap.count("\n") >= 2 else " "))
        last = end
    return out


def joined(words: list[tuple[str, str]]) -> str:
    return "".join((sep if n else "") + tok for n, (tok, sep) in enumerate(words))


def aligned(a: list[tuple[str, int, int]], b: list[tuple[str, int, int]]) -> dict[int, int]:
    match: dict[int, int] = {}
    for i, j, n in SequenceMatcher(None, [t[0] for t in a], [t[0] for t in b], autojunk=False).get_matching_blocks():
        match.update({i + k: j + k for k in range(n)})
    return match


def placed(indices: list[int], match: dict[int, int]) -> list[int] | None:
    """The Doc tokens of these text tokens, when every one is in the Doc and they stand together."""
    js = [match.get(i) for i in indices]
    if not js or None in js or any(y - x != 1 for x, y in zip(js, js[1:])):
        return None
    return js


class Reading:
    """The Doc and the run's texts, read together: where each edit's words stand in the Doc."""

    def __init__(self, doc: dict, tab: str | None, revision: dict | None) -> None:
        self.doc = doc
        self.runs = cm.gdoc_runs(doc, tab)
        self.tab = tab or str((doc["tabs"][0].get("tabProperties") or {}).get("tabId") or "")
        self.dtoks, self.chars = doc_tokens(self.runs)
        self.reviewed, self.corrected, self.applied, self.edits = texts(revision)
        self.rtoks = cm.shown_tokens(self.reviewed)
        self.ctoks = cm.shown_tokens(self.corrected)
        self.rmatch = aligned(self.rtoks, self.dtoks) if self.rtoks else {}
        self.cmatch = aligned(self.ctoks, self.dtoks) if self.ctoks else {}

    def span(self, js: list[int]) -> tuple[int, int]:
        return self.dtoks[js[0]][1], self.dtoks[js[-1]][2]

    def suggestion(self, edit: dict) -> dict:
        """The hunks that turn the edit's old words in the Doc into its new ones, or why it cannot be placed."""
        s, e = edit["old_span"]
        touched = around(self.rtoks, s, e)
        js = placed(touched, self.rmatch)
        if js is None:
            return {"why": "the Doc reads differently here"}
        lo = min(self.rtoks[touched[0]][1], s)
        hi = max(self.rtoks[touched[-1]][2], e)
        old = [self.rtoks[i][0] for i in touched]
        new = words_with_breaks(self.reviewed[lo:s] + edit["new"] + self.reviewed[e:hi])
        hunks, gone, came = [], [], []
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, old, [w for w, _ in new], autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            gone += old[i1:i2]
            came += [w for w, _ in new[j1:j2]]
            if i2 > i1:
                a, b = self.dtoks[js[i1]][1], self.dtoks[js[i2 - 1]][2]
                if j2 == j1:  # a deletion takes one space with it, so no double space is left
                    if self.chars.get(b) == " ":
                        b += 1
                    elif self.chars.get(a - 1) == " ":
                        a -= 1
                    hunks.append({"delete": [a, b]})
                else:
                    hunks.append({"insert": joined(new[j1:j2]), "at": b, "delete": [a, b]})
            elif i1 > 0:  # new words after the word before them
                hunks.append({"insert": new[j1][1] + joined(new[j1:j2]), "at": self.dtoks[js[i1 - 1]][2]})
            else:  # new words before the first word of the passage
                hunks.append({"insert": joined(new[j1:j2]) + " ", "at": self.dtoks[js[0]][1]})
        if not hunks:
            return {"why": "nothing the Doc shows changes (markup only)", "nothing": True}
        return {"hunks": hunks, "range": list(self.span(js)), "gone": gone, "came": came}

    def state(self, edit: dict, planned: dict) -> tuple[str, list[str]]:
        """Where the edit stands in the Doc: "to post" while the Doc reads its old words and nothing is pending there;
        "pending" with our suggestion's ids (its words are the edit's); a co-author's suggestion pending there;
        "accepted" once the Doc reads the new words; else the Doc reads differently there."""
        if "hunks" in planned:
            if (ids := self.ours(planned["hunks"])) is not None:
                return "pending", ids
            spots = [(h["at"], h["at"]) if "delete" not in h else tuple(h["delete"]) for h in planned["hunks"]]
            theirs = {sid for a, b in spots for sid in pending_in(self.runs, a, b)}
            return ("a co-author's suggestion is pending here", sorted(theirs)) if theirs else ("to post", [])
        if placed(around(self.ctoks, *edit["new_span"]), self.cmatch) is not None:
            return "accepted", []
        return "the Doc reads differently here", []

    def ours(self, hunks: list[dict]) -> list[str] | None:
        """The ids of the suggestions an earlier plan made, when every hunk is in the Doc as planned: its words
        inserted where it put them (just after its place, or just before it for words that open the passage) and
        its words struck."""
        ids: set[str] = set()
        for hunk in hunks:
            if "insert" in hunk:
                want = hunk["insert"].translate(cm.QUOTES).split()
                reach = sum(units(c) for c in hunk["insert"])
                near = [r for r in self.runs if r["ins"] and r["start"] < hunk["at"] + reach and r["end"] > hunk["at"] - reach]
                got = [w for r in near for w in r["text"].translate(cm.QUOTES).split()]
                if not any(got[k:k + len(want)] == want for k in range(len(got) - len(want) + 1)):
                    return None
                ids |= {sid for r in near for sid in r["ins"]}
            if "delete" in hunk:
                a, b = hunk["delete"]
                inside = [r for r in self.runs if r["start"] < b and r["end"] > a and not r["ins"] and r["text"].strip()]
                if not inside or not all(r["del"] for r in inside):
                    return None
                ids |= {sid for r in inside for sid in r["del"]}
        return sorted(ids)

    def find(self, text: str | None) -> tuple[tuple[int, int] | None, str]:
        words = [t for t, _, _ in cm.shown_tokens(text or "")]
        if not words:
            return None, "no passage"
        return shade.locate(words, self.dtoks)

    def heading(self, section: str) -> tuple[int, int] | None:
        first = (section or "").split(",")[0].strip()
        return self.find(f"# {first}")[0] if first else None  # as a heading: its number is not a list's marker


# --- what goes into the Doc --------------------------------------------------------------------------------------


def ids_text(ids: list[str]) -> str:
    return ", ".join(dict.fromkeys(ids))


def comment_text(item: dict, data: viz.Inventory) -> str:
    """What a To-do item says in the margin, as the Word review says it; its ID closes it, in parentheses."""
    questions = item["questions"]
    asks = (f"Question for the authors: {questions[0]}" if len(questions) == 1 else
            f"{len(questions)} questions for the authors: " + " ".join(f"{n}. {q}" for n, q in enumerate(questions, 1))
            if questions else "")
    if item["kind"] == "question":
        body = asks
    elif item["kind"] == "proposal":
        summary = item["summary"].rstrip(".")
        if item["status"] == "in this version":
            body = f"Proposed: {summary}." + (f" Why: {item['why']}" if item["why"] else "") + (f" {asks}" if asks else "")
        elif questions:
            body = f"The proposal “{summary}” is left out of this version until you answer. {asks}"
        else:
            body = f"The proposal “{summary}” is not in this version." + (f" Why: {item['why']}" if item["why"] else "")
    elif item["kind"] == "decision":
        body = f"A decision only you can make: {item['summary'].rstrip('.')}." + (f" {item['detail']}" if item["detail"] else "") \
               + (f" Problems: {ids_text(item['finding_ids'])}." if item["finding_ids"] else "")
    else:
        body = (f"{item['summary'].rstrip('.')} ({SEVERITY.get(item['severity'], item['severity'])}, "
                f"{WHEN.get(item['stage'], item['stage'] or 'stage not set')})." + (f" {item['detail']}" if item["detail"] else "")
                + (f" Fix: {item['action']}" if item["action"] else ""))
    return f"{body.strip()} ({item['id']})"


def reason_text(edit: dict, data: viz.Inventory) -> str:
    changes = {c.id: c for c in data.changes}
    lines = []
    for cid in edit["ids"]:
        change = changes.get(cid)
        if change:
            why = change.why or " ".join(f"{f.summary}." for f in data.findings if f.id in change.finding_ids)
            lines.append(f"{change.summary.rstrip('.')}." + (f" Why: {why}" if why else ""))
    return f"{' '.join(lines) or 'An edit of this run.'} ({edit['key']})"


def comment_request(content: str, where: tuple[int, int], tab: str) -> dict:
    return {"insertComment": {"content": content, "range": {"startIndex": where[0], "endIndex": where[1],
                                                            **({"tabId": tab} if tab else {})}}}


def edit_requests(hunks: list[dict], tab: str) -> list[dict]:
    """Requests for the suggestions, last place first, so an earlier one never moves a later range; an insertion
    goes at the end of the words it replaces, before they are struck."""
    on_tab = {"tabId": tab} if tab else {}
    out = []
    for hunk in sorted(hunks, key=lambda h: max(h.get("at", 0), *(h.get("delete") or [0])), reverse=True):
        if "insert" in hunk:
            out.append({"insertText": {"text": hunk["insert"], "location": {"index": hunk["at"], **on_tab}}})
        if "delete" in hunk:
            a, b = hunk["delete"]
            out.append({"deleteContentRange": {"range": {"startIndex": a, "endIndex": b, **on_tab}}})
    return out


def write_control(doc: dict, suggest: bool) -> dict:
    return {**({"requiredRevisionId": doc["revisionId"]} if doc.get("revisionId") else {}),
            **({"writeMode": "SUGGEST"} if suggest else {})}


# --- plan and status ---------------------------------------------------------------------------------------------


def inputs(inventory: Path, read: Path, revision_dir: Path | None) -> tuple[viz.Inventory, dict, dict | None]:
    try:
        data = viz.Inventory.model_validate_json(inventory.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise Failure(f"{inventory}: cannot read: {exc}", 3) from None
    except ValueError as exc:
        raise Failure(f"{inventory}: not an adjudicated inventory ({exc})") from None
    revision = None
    if revision_dir is not None:
        try:
            revision = json.loads((revision_dir / "revision.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise Failure(f"{revision_dir}: no corrected version to read ({exc}).", 3) from None
        if "pieces" not in revision:
            raise Failure("This corrected version was built before exports were possible: rebuild it with revise.py.")
        if revision.get("inventory_sha256") != hashlib.sha256(inventory.read_bytes()).hexdigest():
            raise Failure("The corrected version was built from another inventory; rebuild it with revise.py from this one.")
    try:
        doc = cm.gdoc_document(read)
    except cm.Failure as exc:
        raise Failure(str(exc), exc.code) from None
    return data, doc, revision


def read_record(path: Path, doc: dict, data: viz.Inventory) -> dict:
    if path.is_file():
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise Failure(f"{path}: cannot read the record of what was posted ({exc}).", 3) from None
        if record.get("doc") not in (None, doc.get("documentId")):
            raise Failure(f"{path} records another Doc ({record.get('title')!r}); give this Doc its own --record.")
        return record
    return {"schema_version": 1, "run_id": data.run_id, "doc": doc.get("documentId"), "title": doc.get("title"), "posted": {}}


def survey(data: viz.Inventory, doc: dict, revision: dict | None, tab: str | None, agent: str, reasons: bool,
           record: dict) -> tuple[Reading, list[dict]]:
    """Every item of the review with its place in the Doc and whether it is there yet."""
    reading = Reading(doc, tab, revision)
    todo = viz.todo_items(data, revision)
    by_change = {cid: edit for edit in reading.edits for cid in edit["ids"]}
    items: list[dict] = []
    planned_edits: dict[str, dict] = {}
    for edit in reading.edits:
        plan = reading.suggestion(edit)
        planned_edits[edit["key"]] = plan
        if plan.get("nothing"):
            continue
        posted = edit["key"] in record["posted"]
        status, ids = reading.state(edit, plan)
        if status == "to post" and posted:  # posted once, and the Doc reads the old words again with nothing pending
            status = "rejected"
        elif status == "accepted" and not posted:
            status = "in the Doc already"
        elif status == "the Doc reads differently here" and not posted:
            status = "not found"
        items.append({"key": edit["key"], "kind": "suggestion", "ids": edit["ids"], "edit_status": edit["status"],
                      "status": status, "suggestion_ids": ids, "why": plan.get("why", ""), "plan": plan})
    for item in todo:
        if item["kind"] in ("question", "proposal") and item["id"] in by_change:
            plan = planned_edits[by_change[item["id"]]["key"]]
            where, how = ((tuple(plan["range"]), "on its edit") if plan.get("range") else
                          reading.find(item["before"] or item["anchor"]))
        else:
            where, how = reading.find(item["quote"] or item["before"] or item["anchor"])
        if where is None and (heading := reading.heading(item["section"])):
            where, how = heading, "on its section's heading"
        items.append(comment_item(item["id"], f"[ai:{agent}] {comment_text(item, data)}", where, how, doc, item))
    if reasons:
        for edit in reading.edits:
            plan = planned_edits[edit["key"]]
            if edit["status"] == "applied" and plan.get("range"):
                items.append(comment_item(edit["key"], f"[ai:{agent}] {reason_text(edit, data)}", tuple(plan["range"]),
                                          "on its edit", doc, None))
    return reading, items


def comment_item(key: str, content: str, where, how: str, doc: dict, todo: dict | None) -> dict:
    thread = thread_for(doc, key)
    replies = [{"by": str(((p.get("author") or {}).get("displayName")) or ""), "text": said(p),
                "resolved": p.get("commentAction") == "RESOLVE"} for p in (thread or {}).get("replies") or []]
    return {"key": key, "kind": "comment", "content": content, "todo": todo,
            "status": "posted" if thread else "to post" if where else "not found",
            "where": list(where) if where else None, "placed": how if where else "", "why": "" if where else how,
            "comment_id": (thread or {}).get("commentId"), "resolved": (thread or {}).get("status") == "RESOLVED",
            "replies": [r for r in replies if r["text"].strip() and not cm.ai_of(r["text"])]}


def remember(record: dict, items: list[dict]) -> None:
    today = date.today().isoformat()
    for item in items:
        if item["status"] in ("posted", "pending") and item["key"] not in record["posted"]:
            entry = {"kind": item["kind"], "on": today}
            if item["kind"] == "suggestion":
                entry |= {"range": item["plan"]["range"], "gone": item["plan"]["gone"], "came": item["plan"]["came"],
                          "suggestion_ids": item["suggestion_ids"]}
            else:
                entry["comment_id"] = item["comment_id"]
            record["posted"][item["key"]] = entry


def plan(data: viz.Inventory, doc: dict, revision: dict | None, tab: str | None, agent: str, reasons: bool,
         record: dict) -> dict:
    reading, items = survey(data, doc, revision, tab, agent, reasons, record)
    remember(record, items)
    comments = [i for i in items if i["kind"] == "comment" and i["status"] == "to post"]
    edits = [i for i in items if i["kind"] == "suggestion" and i["status"] == "to post"]
    if comments:
        batch = {"what": "comments", "count": len(comments), "writeControl": write_control(doc, False),
                 "requests": [comment_request(i["content"], tuple(i["where"]), reading.tab) for i in comments]}
    elif edits:
        batch = {"what": "suggested edits", "count": len(edits), "writeControl": write_control(doc, True),
                 "requests": edit_requests([h for i in edits for h in i["plan"]["hunks"]], reading.tab)}
    else:
        batch = None
    report = [{k: v for k, v in i.items() if k in ("key", "kind", "status", "why", "placed")} for i in items]
    return {"doc": doc.get("documentId"), "title": doc.get("title"), "tab": reading.tab, "batch": batch,
            "left": len(comments) + len(edits), "done": batch is None,
            "counts": {s: sum(1 for i in items if i["status"] == s) for s in dict.fromkeys(i["status"] for i in items)},
            "not_found": [r for r in report if r["status"] == "not found"],
            "left_alone": [r for r in report if "pending here" in r["status"]],
            "send": ("update_doc with batch.requests and batch.writeControl; then read_doc (commentsIncluded) and plan "
                     "again" if batch else "nothing left: every item is in the Doc or listed under not_found"),
            "items": report}


def marks_from(items: list[dict], data: viz.Inventory, answers: dict[str, str]) -> list[viz.Mark]:
    """What the Doc decided, as To-do marks: an edit that asked or a proposal, accepted or rejected; any item the
    agent answered from its replies (`answers`)."""
    by_change = {cid: i for i in items if i["kind"] == "suggestion" for cid in i["ids"]}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    for item in items:
        todo = item.get("todo")
        if item["kind"] != "comment" or not todo:
            continue
        said_ = " / ".join(f"{r['by']}: {' '.join(r['text'].split())}" for r in item["replies"])
        mark = answers.get(todo["id"])
        if mark is None and todo["kind"] in ("question", "proposal") and todo["id"] in by_change:
            decided = by_change[todo["id"]]["status"]
            mark = {"accepted": "approved", "rejected": "redundant"}.get(decided)
            if mark and not said_:
                said_ = f"{decided.capitalize()} in the Google Doc."
        if mark is None:
            continue
        out.append(viz.Mark(run_id=data.run_id, kind=todo["kind"], id=todo["id"], mark=mark, reason=said_, marked_at=now,
                            summary=todo["summary"], section=todo["section"], category=todo["category"],
                            quote=todo["quote"], action=todo["action"], before=todo["before"], after=todo["after"],
                            anchor=todo["anchor"], finding_ids=todo["finding_ids"]))
    return out


def write_marks(path: Path, marks: list[viz.Mark], manuscript: str) -> dict:
    found = viz.MarksFile(schema_version=1, manuscript=manuscript)
    if path.is_file():
        try:
            found = viz.MarksFile.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise Failure(f"{path}: the marks file does not read ({exc}); it is never written over.", 3) from None
    have = {viz.mark_key(m.run_id, m.kind, m.id): m for m in found.marks}
    added, kept = [], []
    for mark in marks:
        key = viz.mark_key(mark.run_id, mark.kind, mark.id)
        if key in have:  # the authors' own mark in the To-do tab stands
            if have[key].mark != mark.mark:
                kept.append({"id": mark.id, "kept": have[key].mark, "the_doc_says": mark.mark})
            continue
        found.marks.append(mark)
        added.append({"id": mark.id, "mark": mark.mark})
    if added:
        path.write_text(json.dumps(found.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"file": str(path), "added": added, "kept_from_the_tab": kept}


def undo_edits(reading: Reading, items: list[dict], data: viz.Inventory) -> list[dict]:
    """Each plain applied edit the Doc rejected, as an edit that puts its old words back in the applied version:
    the whole paragraph, as runs.py apply takes it."""
    asking = {i["todo"]["id"] for i in items if i.get("todo") and i["todo"]["kind"] == "question"}
    sections = {c.id: c.section for c in data.changes}
    out = []
    for edit in reading.edits:
        item = next((i for i in items if i["key"] == edit["key"]), None)
        if not item or item["status"] != "rejected" or edit["status"] != "applied" or asking & set(edit["ids"]):
            continue
        s, e = edit["applied_span"]
        lo = reading.applied.rfind("\n", 0, s) + 1
        hi = reading.applied.find("\n", e)
        hi = len(reading.applied) if hi < 0 else hi
        out.append({"before": reading.applied[lo:hi], "after": reading.applied[lo:s] + edit["old"] + reading.applied[e:hi],
                    "reason": f"Rejected in the Google Doc ({edit['key']}).", "section": sections.get(edit["ids"][0], "")})
    return out


def status(data: viz.Inventory, doc: dict, revision: dict | None, tab: str | None, agent: str, record: dict) -> tuple[Reading, list[dict], dict]:
    reading, items = survey(data, doc, revision, tab, agent, False, record)
    remember(record, items)
    report = []
    for item in items:
        if item["kind"] == "suggestion":
            report.append({k: item[k] for k in ("key", "kind", "edit_status", "status", "why")})
        else:
            report.append({k: item[k] for k in ("key", "kind", "status", "resolved", "replies", "why")})
    counts = {f"{i['kind']}s {i['status']}": 0 for i in items}
    for i in items:
        counts[f"{i['kind']}s {i['status']}"] += 1
    return reading, items, {"doc": doc.get("documentId"), "title": doc.get("title"), "counts": counts, "items": report}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="export_gdoc.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("plan", "status"):
        s = sub.add_parser(name)
        s.add_argument("inventory", type=Path, help="the adjudicated inventory, RUN/manuscript-dashboard/findings.json")
        s.add_argument("doc", type=Path, help="the Doc's read_doc answer (commentsIncluded), saved as JSON")
        s.add_argument("--revision", type=Path, help="revise.py's output folder: its edits become suggestions")
        s.add_argument("--tab", help="the Doc tab's id (default: the first tab)")
        s.add_argument("--as", dest="agent", default="claude", help="the agent's name in [ai:NAME] (default: claude)")
        s.add_argument("--record", type=Path, help="what was posted (default: gdoc-review.json beside the inventory)")
        if name == "plan":
            s.add_argument("--reasons", action="store_true", help="also a comment with each applied edit's reasoning")
            s.add_argument("--check", action="store_true", help="exit 1 while something is left to post")
            s.add_argument("--out", type=Path, help="write the plan here instead of printing it")
        else:
            s.add_argument("--marks", type=Path, help="the To-do marks file to add the Doc's decisions to (STEM.todo.json)")
            s.add_argument("--mark", action="append", default=[], metavar="ID=approved|redundant",
                           help="an item the agent answered from its replies; repeat")
            s.add_argument("--undo", type=Path, help="write the rejected plain applied edits here, for runs.py apply")
    args = ap.parse_args(argv)
    try:
        if not AGENT.fullmatch(args.agent):
            raise Failure(f"--as is a short lowercase name such as claude, not {args.agent!r}.")
        data, doc, revision = inputs(args.inventory, args.doc, args.revision)
        record_path = args.record or args.inventory.resolve().parent / "gdoc-review.json"
        record = read_record(record_path, doc, data)
        if args.command == "plan":
            result = plan(data, doc, revision, args.tab, args.agent, args.reasons, record)
        else:
            answers = {}
            for given in args.mark:
                key, _, value = given.partition("=")
                if value not in ("approved", "redundant"):
                    raise Failure(f"--mark {given!r}: ID=approved or ID=redundant.")
                answers[key.strip()] = value
            reading, items, result = status(data, doc, revision, args.tab, args.agent, record)
            known = {i["todo"]["id"] for i in items if i.get("todo")}
            if unknown := sorted(set(answers) - known):
                raise Failure(f"--mark names no item of this review in the Doc: {', '.join(unknown)}.")
            if args.marks:
                result["marks"] = write_marks(args.marks, marks_from(items, data, answers),
                                              data.manuscript.path if data.manuscript else "")
            elif answers:
                raise Failure("--mark needs --marks, the file to write the marks into.")
            if args.undo:
                undo = undo_edits(reading, items, data)
                if undo:
                    args.undo.write_text(json.dumps(undo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                result["undo"] = {"file": str(args.undo) if undo else None, "edits": len(undo)}
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Failure as exc:
        print(f"export_gdoc.py: {exc}", file=sys.stderr)
        return exc.code
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if getattr(args, "out", None):
        args.out.write_text(text + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in result.items() if k not in ("batch", "items")}
                         | {"requests": len((result.get("batch") or {}).get("requests", [])), "out": str(args.out)},
                         ensure_ascii=False))
    else:
        print(text)
    return 1 if getattr(args, "check", False) and result.get("left") else 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # UTF-8 on every platform, a Windows console included
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
