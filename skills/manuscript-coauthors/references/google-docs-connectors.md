# Google Docs through connectors: what each one can do

A round's Google Doc can be read and written through three connectors. They differ in what they can do, and a
call that returns success does not prove the change happened. This page lists what each connector does, the
exact requests to send, and how to confirm each change by reading the Doc back. Everything below was tested on
one shared Doc on 2026-11-01 (section "The joint test"). Re-test before relying on a row marked otherwise.

## Which connector to turn on

- **Claude (claude.ai, Claude Desktop, Claude Code): the Google Docs connector.** It is separate from the
  Google Drive connector: Drive searches, uploads and shares files; Docs edits them. Turn it on in a claude.ai
  chat with **+ → Connectors → Google Docs** (Sheets and Slides have their own). Claude Code loads claude.ai
  connectors when a session starts, so start a new session afterwards (`/exit`, then `claude --continue`).
  On Team and Enterprise plans an Owner enables it for the organisation first. Anthropic's instructions:
  <https://support.claude.com/en/articles/10166901-use-google-workspace-connectors>.
- **Codex: the Google Drive app** (ChatGPT apps). Its tools (`mcp__codex_apps__google_drive_*`) are deferred
  behind Codex's tool search, so a brief tells Codex to search for "google drive" first.

**Each connector writes as its own Google account.** On the test Doc, Claude's writes appeared as one account
and Codex's as another person's account, because each connector was signed in separately. A comment or reply an
agent posts carries a person's name, so its text starts with `[ai:NAME]` (`[ai:claude]`, `[ai:codex]`): the
pull then reads it as an agent's, not the account owner's. When the
revision-marks policy (`rev-marks.toml`) decides who is a person, an agent's comment under a person's name
counts as that person. A connector also reaches only the Docs its account can open: Codex got 403 on the test
Doc until it was shared with Codex's account.

## What each connector can do

| In an existing Google Doc | Claude: Google Docs | Claude: Google Drive | Codex: Google Drive app |
| --- | --- | --- | --- |
| Read the text | yes (`read_doc`, structured) | yes (`read_file_content`, plain text) | yes (`get_document`) |
| Read highlights and other styles | yes | bold and italic as Markdown; no highlights or colours | yes |
| Read comments: text, author, replies | yes | yes | yes |
| Read the words a comment is anchored on | yes (`plainTextQuote`, range) | inline markers in the text | yes (`quotedFileContent`, anchor) |
| Read whether a thread is resolved | yes (`status`) | yes (`status`) | yes (`resolved`) |
| Read suggested edits | yes, with a "Replace: X with Y" summary per suggestion | **no**: shown as if accepted and rejected at once (inserted text, suggested bold and the text a suggestion deletes all appear, unmarked) | yes, inline ids on the text |
| Insert, replace, delete text | yes | no (whole files only) | yes |
| Highlight or colour text | yes | no | yes |
| Make a suggested edit (insertion, deletion, formatting) | **yes** (`writeMode: SUGGEST`) | no | **no**: its schema has no write mode; the field is dropped or the call refused |
| Add a comment anchored on words | yes (`insertComment`) | no | yes (`insertComment` as a raw request) |
| Reply to a comment | yes (`addCommentReply`) | no | yes |
| Resolve a comment | yes (`addCommentReply` with `RESOLVE`) | no | yes |
| Accept or reject a suggestion | no: Google's API has no request for it | no | no |
| List and read past revisions | not exposed | fetch one by id (`download_file_content` `revisionId`), no listing | yes |

Claude's Google Docs connector covers everything the authors need for a round. Codex's app adds revision
history. Claude's Drive connector reads comments, but it loses suggested edits.

## The requests

Claude's `update_doc` passes its `requests` straight to Google's `documents.batchUpdate`. Its tool description
is cut short, so it lists only some request types, but any request in Google's `Request` union works. Look a
request up in Google's reference before deciding that something cannot be done:
<https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request>. A guessed name fails the
whole batch (`Cannot find field: createComment`); the real name is `insertComment`. Codex's
`batch_update_document` takes the same request objects.

Read with comments and suggestions (Claude):

```json
read_doc {"documentId": "DOC_ID", "commentsIncluded": true}
```

Saved as JSON, that answer is what `comments.py import-gdoc` merges into the round's ledger.

The answer carries `comments[]` (each with `commentId`, `anchorId`, `plainTextQuote`, `status`, `headPost`,
`replies[]`), `suggestions[]` (each with `suggestionId`, `status`, `summaryText`) and `commentAnchors` (each
anchor's index range). In the body, a suggested insertion is text with `suggestedInsertionIds`, a suggested
deletion is text with `suggestedDeletionIds`, and a suggested style change is a `suggestedTextStyleChanges`
entry. A highlight is `textStyle.backgroundColor.color.rgbColor` (a channel at 0 is left out).

Highlight a range (direct edit):

```json
{"updateTextStyle": {"range": {"startIndex": 3604, "endIndex": 3617, "tabId": "t.0"},
  "textStyle": {"backgroundColor": {"color": {"rgbColor": {"red": 1, "green": 0.65, "blue": 0}}}},
  "fields": "backgroundColor"}}
```

Suggested edits: the same requests, with the batch's write mode set (Claude's `update_doc` argument):

```json
"writeControl": {"writeMode": "SUGGEST"}
```

One batch can carry a suggested insertion (`insertText`), a suggested deletion (`deleteContentRange`) and a
suggested style change (`updateTextStyle`); each gets its own `suggest.*` id. A style change in a SUGGEST
batch is a suggestion (tested with bold), so a highlight meant to stay goes in a separate, direct batch.

An anchored comment, a reply, and a reply that resolves:

```json
{"insertComment": {"content": "…", "range": {"startIndex": 3770, "endIndex": 3815, "tabId": "t.0"}}}
{"addCommentReply": {"commentId": "doco.…", "post": {"content": "…"}}}
{"addCommentReply": {"commentId": "doco.…", "post": {"content": "…", "commentAction": "RESOLVE"}}}
```

Shading the unreviewed passages, and colouring what changed since a revision, are planned by
`manuscript-revision-marks/scripts/gdoc_shade.py`: it prints the `updateTextStyle` requests to send, in two
reserved colours, and checks the readback.

A run's review is planned the same way by `manuscript-dashboard/scripts/export_gdoc.py`: the corrected version's
edits as `insertText` and `deleteContentRange` in one `SUGGEST` batch (last place first; a replacement is an
insertion at the end of the old words, then their deletion, so it may show as two suggestions), the questions for
the authors as `insertComment` in a direct batch before it, each batch guarded by `requiredRevisionId`; `plan`
is repeated after each batch and adds only what the Doc lacks, and `status` reads back what was accepted or
rejected.

### Rules that keep it safe

- **Read back every change.** Pass or fail is decided by `read_doc`, never by the call's success: a suggestion
  must show a `suggest.*` id on its text, and a comment must have an `anchorId`. Codex's
  `bulk_update_file_comments` creates comments with `anchor: null`. The API reads them, but they did not show
  in the editor; only `insertComment` comments did.
- **Indices are UTF-16 offsets into the current revision.** Take them from a fresh read, never from arithmetic
  on an older read: another person or agent may have edited in between. Send several range requests in one
  batch in descending index order, so an earlier insertion does not move a later range. Comments do not move
  indices.
- **Guard concurrent edits** with `writeControl.requiredRevisionId` from the read: Google refuses the batch if
  the Doc changed, and you read it again.
- **Never touch a co-author's text directly.** A change to their prose goes in as a suggestion, so they
  accept or reject it. Never resolve a co-author's thread; that is theirs to do.
- **Mark test text.** Tests write only text tagged with a marker (`[CLAUDE-T-YYYYMMDD]`, `[CODEX-T-…]`) and
  edit only text with their own marker.

## Running Codex as a second seat

From Claude Code, Codex runs headless (the Codex CLI on this machine, signed in, with the Google Drive app):

```bash
codex exec -m gpt-6.1-sol -c 'model_reasoning_effort="medium"' --skip-git-repo-check \
  -C SCRATCH -o SCRATCH/answer.md "$(cat SCRATCH/brief.md)"
```

Plain `codex exec` reads the Doc, but refuses each write with "MCP tool call requires approval, but approval
policy is never", because nobody is there to approve it. Setting
`-c 'apps.google_drive.default_tools_approval_mode="approve"'` alone did not change that (Codex 0.163.0). What
worked is `--approve-for-me`, which sends each approval to Codex's automatic reviewer; the brief opened with
"The document owner explicitly authorised these test writes to this test document":

```bash
codex exec --approve-for-me -m gpt-6.1-sol -c 'model_reasoning_effort="medium"' \
  -c 'apps.google_drive.default_tools_approval_mode="approve"' --skip-git-repo-check \
  -C SCRATCH -o SCRATCH/answer.md "$(cat SCRATCH/brief.md)"
```

The `default_tools_approval_mode` setting is kept from the earlier attempt: alone it did nothing, and whether
`--approve-for-me` needs it was not tested.

This lets an unattended agent write to a Google account, so run it only on the authors' explicit request for
that Doc. Claude Code's auto mode blocks starting such a run until the person allows it. The other way is to
paste the brief into an interactive Codex session, where the person approves each write.

## The joint test (2026-11-01)

One Doc ("Claude Code edit test (safe to delete)", tab `t.0`), with Claude's Google Docs connector and Codex's
Google Drive app writing as two different accounts. Codex's own report of its first session is
[docs/google-drive-connector-test-results-2026-11-01.md](../../../docs/google-drive-connector-test-results-2026-11-01.md).

Claude's writes, and what each side read back:

| Write by Claude | Claude's own readback | Codex's readback |
| --- | --- | --- |
| Insert, replace, delete text | pass | pass (the text) |
| Orange highlight on "orange sample" | pass | pass: `{"red":1,"green":0.6509804}` |
| Suggested insertion " plus a suggested addition" | pass: "Add: “plus a suggested addition”" | pass: `suggest.j3a0py4q37du` on the text |
| Suggested deletion "drop-this-word " | pass: "Delete: “drop-this-word”" | pass: `suggest.rg2rfffhrcuw` on the text |
| Suggested bold on "bold-me" | pass: "Format: bold, font" | pass: `suggest.uolsabwm3p5d`, `boldSuggested: true` |
| Anchored comment | pass: `kix.vei4lw6sc1qb` | pass: same anchor, author shown, open |
| Reply in a co-author's thread | pass | pass: the reply, author shown |
| Resolve its own comment | pass | pass: `resolved: true` |
| `createComment` (wrong name) | refused: no such request | — |

Codex's writes (its interactive session, whose report gives the ids, then `codex exec --approve-for-me`), and
what Claude read back:

| Write by Codex | Codex's readback | Claude's readback |
| --- | --- | --- |
| Insert, replace, delete text | pass | pass |
| Yellow highlight; light blue on "blue sample" | pass | pass: `{"red":1,"green":1}`; `{"red":0.6,"green":0.8,"blue":1}` |
| Anchored comment (`insertComment`) | pass, seen in the editor | pass: `kix.tm79whho3yea`, quoted words, author |
| Reply in Claude's thread | pass | pass: the reply under Claude's comment, thread still open |
| Anchored comment, then resolved | pass | pass: `kix.1e4sqk5iy32z`, `status: RESOLVED` |
| Unanchored comment (`bulk_update_file_comments`) | pass in the API | read, with `plainTextQuote` but no `anchorId`; not seen in the editor |
| Reply in a co-author's thread, resolve its own | pass | pass: replies, `status: RESOLVED` |
| Suggestion with `write_control.writeMode` | fail: the field was dropped, the edit landed directly | plain text, no suggestion id |
| Suggestion with top-level `writeControl` or `write_control.write_mode` | refused: `InvalidActionArgumentsError` | nothing landed |
| Writes from plain `codex exec` | refused: approval policy is never | nothing landed |

`gdoc_shade.py` on the same Doc, live (2026-11-02): `plan` on a marked master with one unreviewed and one
person-signed segment gave one request (the unreviewed line, found exactly; the signed one left alone); the
connector applied it; `verify` on the readback passed, Google having stored the colour as
`{"red":1,"green":0.9254902,"blue":0.7019608}`, within the 1/255 tolerance; `clear` gave one request, and after it
the range was plain while every other highlight in the Doc (yellow, green, orange, light blue) stayed.

Not tested: accepting or rejecting a suggestion (no request exists), editing or deleting a comment, reopening a
resolved thread, restoring a revision, and the Google Sheets and Slides connectors.
