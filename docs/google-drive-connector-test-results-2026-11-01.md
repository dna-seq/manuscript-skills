# Google Drive connector test results — 2026-11-01

Manual tests of the Google Drive connector available in this Codex session demonstrated direct text insertion, replacement, deletion, highlighting, comment creation, replies, resolution, and revision reads. Two attempts to create tracked suggestions instead produced direct edits. The user independently confirmed that no suggestions were created.

## Test target and method

- Document: [Claude Code edit test (safe to delete)](https://docs.google.com/document/d/1bFAKtWjcLadp_4A_fZLGsuBgiE57LAYvtYgxbTvlSvA/edit?tab=t.0).
- Target tab: `t.0`.
- Connector tools: `mcp__codex_apps__google_drive_*`.
- Markers: `CODEX-TEST-20261101-A`, `CODEX-SUGGEST-TEST-20261101-B`, and `CODEX-REPLACE-SUGGEST-20261101-C`.
- Mutations were confined to added, marked test text. Existing text, comments, and the pre-existing Claude Code suggestion were preserved.
- Verification used native document and comment readback. The user also checked the suggestion outcomes in the editor. No automated browser or rendered-layout verification was performed.
- Results apply to this connector, account, document, and session on the test date; they do not establish capabilities of other MCP servers or Claude integrations.

Initial access failed: document and comment reads returned 403, and revision listing returned 404. After the user changed access, the same document became accessible and testing proceeded. The initial errors therefore were not treated as feature failures.

## Verified capabilities

| Capability | Operation and evidence | Result |
| --- | --- | --- |
| Read document | `get_document` returned native tab content, text ranges, styles, and a revision ID. | Pass |
| Insert text | `insertText` added the marked test section; readback contained it. | Pass |
| Replace text | `replaceAllText` changed the marked `EDIT: BEFORE.` sentence to `EDIT: AFTER.`; one occurrence changed and readback confirmed it. | Pass |
| Delete text | `deleteContentRange` removed only the added `TEMPORARY_TEXT`; the marked `DELETE:` line remained. | Pass |
| Highlight text | `updateTextStyle` applied yellow to `yellow sample`; readback returned a background RGB color with red and green equal to 1 and blue implicitly 0. | Pass |
| Read comments and replies | `get_document_comments` returned existing and newly created threads, replies, and resolution state. | Pass |
| Create comments | `bulk_update_file_comments` created two marked threads with exact quoted target text. Both appeared in subsequent comment readback. | Pass |
| Reply to a comment | Added a marked reply to the first test thread; readback included the reply. | Pass |
| Resolve a comment | Resolved the first test thread with a closing reply; readback showed `resolved: true` and a reply action of `resolve`. | Pass |
| Read existing tracked suggestions | Native readback exposed `suggestedInsertionIds`, `suggestedDeletionIds`, and suggested style changes for the existing suggestion `suggest.15run3iq4vl4`. | Pass |
| List revisions | `list_file_revisions` returned revision IDs `1` and `9`, modification times, last-modifying-user metadata, and `previousRevisionId: "1"`. | Pass |
| Read historical revision | `fetch_file_revision` retrieved revision `1` as plain text, including the original first and second lines. | Pass |
| Use revision guards | Mutations supplied `write_control.requiredRevisionId` and succeeded against the observed revisions. Rejection of a deliberately stale revision was not tested. | Accepted; conflict handling untested |

### Comment evidence and anchoring

The two created threads were:

| Thread ID | Final state |
| --- | --- |
| `doco.E34r2gWqREJ0tCo4ct98BA` | Resolved, with a test reply and closing reply |
| `doco.kzEWVyD-h3m6yWeZsHkIVA` | Left open as visible test evidence |

Both returned `anchor: null`. Each retained exact target text in `quotedFileContent` and in the comment body. These tests demonstrate file comments with quoted context, not native comments anchored to a selected text range. Existing anchored comments were readable, but creating a native selection anchor was not tested.

## Tracked suggestion creation tests

Tracked suggestions are proposed additions, deletions, or formatting changes that await acceptance or rejection. Reading their metadata is separate from creating them.

Google documents suggestion creation using `writeControl.writeMode: "SUGGEST"` in a `documents.batchUpdate` request. The connector's declared `write_control` object exposed only `requiredRevisionId` and `targetRevisionId`; it did not declare `writeMode`. To test actual behavior rather than infer it solely from the schema, both probes supplied the additional `writeMode` field through the tool call.

### B: Suggested insertion probe

Submitted a marked sentence using:

```json
{
  "write_control": {
    "requiredRevisionId": "<current revision>",
    "writeMode": "SUGGEST"
  },
  "requests": [
    {
      "insertText": {
        "endOfSegmentLocation": {"tabId": "t.0"},
        "text": "[CODEX-SUGGEST-TEST-20261101-B] Proposed sentence: please accept or reject this insertion.\n"
      }
    }
  ]
}
```

The call succeeded. A subsequent document read reported `SUGGESTIONS_INLINE`, but the inserted text had no `suggestedInsertionIds`; it was ordinary text. The probe sentence was replaced with a marked result record.

**Result: failed to create a tracked insertion; produced a direct edit.**

### C: Suggested replacement probe

First inserted a normal marked baseline sentence, then submitted:

```json
{
  "write_control": {
    "requiredRevisionId": "<current revision>",
    "writeMode": "SUGGEST"
  },
  "requests": [
    {
      "replaceAllText": {
        "containsText": {
          "text": "[CODEX-REPLACE-SUGGEST-20261101-C] Original test sentence.",
          "matchCase": true
        },
        "replaceText": "[CODEX-REPLACE-SUGGEST-20261101-C] Revised test sentence.",
        "tabsCriteria": {"tabIds": ["t.0"]}
      }
    }
  ]
}
```

The response reported `occurrencesChanged: 1`. Readback in `SUGGESTIONS_INLINE` mode contained only the revised sentence, with neither `suggestedInsertionIds` nor `suggestedDeletionIds` on that text. A marked result record was appended and read back. The user confirmed that no suggestions were set.

**Result: failed to create a tracked replacement; produced a direct edit.**

### Interpretation

The requested suggestion mode was ineffective through this connector in both probes. The observations do not identify whether argument validation, serialization, the connector backend, or another layer dropped or ignored the field. A successful tool response alone does not demonstrate suggestion creation; native suggestion metadata or editor confirmation is required.

The initial test record described suggestion creation as not exposed and untested. Probes B and C supersede the “untested” status: passing the documented Google option was attempted, but neither operation created a suggestion.

## Not tested

- Accepting, rejecting, or deleting suggestions, including through raw batch request objects. No dedicated tools were exposed for these operations; the raw request surface was not exhaustively tested.
- Creating suggested deletions or suggested formatting changes as separate probes.
- Editing or deleting existing comments, deleting replies, reopening resolved threads, or creating native selection-anchored comments through raw Docs requests.
- Restoring revisions, complete revision-history coverage, or stale-revision conflict rejection.
- Sharing changes, file deletion, image/table insertion, or unrelated Drive operations.

These are limits of the test coverage, not proof that the underlying Google APIs cannot perform the operations.

## References

- [Google Docs: Work with comments and suggestions](https://developers.google.com/workspace/docs/api/how-tos/suggestions).
- [Google Docs: documents.batchUpdate](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate).
- Primary empirical evidence: connector responses, native readbacks, marked records in the test document, and the user's editor confirmation during this session. Raw response dumps and credentials are not included in this report.
