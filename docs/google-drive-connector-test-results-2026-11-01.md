# Google Drive connector test results — 2026-11-01

Manual tests of the Google Drive connector available in this Codex session demonstrated direct text insertion, replacement, deletion, highlighting, native anchored comment creation, replies, resolution, and revision reads. The user confirmed that the native anchored comment and reply worked in the editor. Earlier unanchored comments were readable through the API but the user could not see them in the editor. Two attempts to create tracked suggestions instead produced direct edits; the user independently confirmed that no suggestions were created.

## Test target and method

- Document: [Claude Code edit test (safe to delete)](https://docs.google.com/document/d/1bFAKtWjcLadp_4A_fZLGsuBgiE57LAYvtYgxbTvlSvA/edit?tab=t.0).
- Target tab: `t.0`.
- Connector tools: `mcp__codex_apps__google_drive_*`.
- Markers: `CODEX-TEST-20261101-A`, `CODEX-SUGGEST-TEST-20261101-B`, `CODEX-REPLACE-SUGGEST-20261101-C`, `CODEX-COMMENT-RETEST-20261101-D` (including the `-NATIVE` variant), and `CODEX-COMMENT-RESOLVE-20261101-E`.
- Text mutations were confined to added, marked test text. Existing text and the pre-existing Claude Code suggestion were preserved. A marked reply was added to the user's existing comment without resolving it.
- Verification used native document and comment readback. The user also checked suggestion outcomes and confirmed the native comment/reply test in the editor. The later creation-and-resolution test E was verified through API readback only. No automated browser or rendered-layout verification was performed.
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
| Create unanchored file comments | `bulk_update_file_comments` created marked threads with exact quoted target text and `anchor: null`. API readback succeeded, but the user reported the earlier comments were not visible in the editor. | API pass; editor visibility not demonstrated |
| Create native anchored comments | Raw `insertComment` through `batch_update_document`, with a text range and tab ID, returned a native `kix.*` anchor. Comment readback confirmed it; the user confirmed test D worked in the editor. | Pass |
| Reply to a comment | Added replies to a test thread and, in test D, to the user's existing anchored “Blabla BLA” thread. Readback confirmed the replies; the user confirmed test D worked. | Pass |
| Resolve a comment | The bulk tool resolved the first unanchored thread. In test E, native `addCommentReply` with `commentAction: "RESOLVE"` resolved a newly created anchored thread; readback showed `resolved: true`. | Pass |
| Read existing tracked suggestions | Native readback exposed `suggestedInsertionIds`, `suggestedDeletionIds`, and suggested style changes for the existing suggestion `suggest.15run3iq4vl4`. | Pass |
| List revisions | `list_file_revisions` returned revision IDs `1` and `9`, modification times, last-modifying-user metadata, and `previousRevisionId: "1"`. | Pass |
| Read historical revision | `fetch_file_revision` retrieved revision `1` as plain text, including the original first and second lines. | Pass |
| Use revision guards | Current revision guards succeeded. The first native-comment attempt in test D was rejected because its required revision no longer matched; rereading and retrying succeeded. This was an observed stale-revision conflict, not a deliberately induced one. | Pass |

### Comment evidence and anchoring

The initial two created threads were:

| Thread ID | Final state |
| --- | --- |
| `doco.E34r2gWqREJ0tCo4ct98BA` | Resolved, with a test reply and closing reply |
| `doco.kzEWVyD-h3m6yWeZsHkIVA` | Left open; API-readable, editor visibility not demonstrated |

Both returned `anchor: null`. Each retained exact target text in `quotedFileContent` and in the comment body. The user subsequently reported that these comments were not visible. The initial “Pass” therefore established API persistence only, not useful editor visibility.

### D: Comment visibility retest and reply to the user

The bulk tool created another unanchored comment, `doco.s67j_bo_MI1cDonE-PSWZw`, and added reply `doco.ENCJLFG1cjYjysc46ePC3g` to the user's existing “Blabla BLA” thread, `doco.xZ9cjPkAUrF6c11Ere21cA`. That existing thread retained its native anchor, `kix.hd42w841oend`, and was left open. Both writes were confirmed by comment readback.

To test a native anchor, a raw Docs `insertComment` request was then sent through `batch_update_document`:

```json
{
  "requests": [
    {
      "insertComment": {
        "content": "[CODEX-COMMENT-RETEST-20261101-D-NATIVE] Native anchored comment test on the quoted target.",
        "range": {
          "startIndex": "<observed integer start index>",
          "endIndex": "<observed integer end index>",
          "tabId": "t.0"
        }
      }
    }
  ]
}
```

The index placeholders above stand for integer UTF-16 offsets obtained from current document readback. The actual target was the marked `COMMENT: open thread target.` sentence. After a stale-revision rejection and a fresh read, the request succeeded:

- Comment ID: `doco.fcQH89e_RXl92LUWrNMS1Q`.
- Native anchor: `kix.2685nhmdeoxl`.
- Returned status: `OPEN`.
- Subsequent Drive comment readback retained the same anchor and quoted target.
- The user responded “worked” after being asked to check the native anchored comment and reply.

**Result: native anchored comment creation and replying to an existing user thread passed.** The bulk comment wrapper's unanchored output should not be treated as equivalent to a visible native review comment. The raw batch request route exposes useful capabilities beyond the dedicated comment wrapper.

### E: Create and resolve an owned native anchored comment

Created a separate comment on the marked `COMMENT: reply and resolution target.` sentence using `insertComment`:

- Marker: `CODEX-COMMENT-RESOLVE-20261101-E`.
- Comment ID: `doco.F3hTQVBiHBWDqEdf1RxA2Q`.
- Native anchor: `kix.g74y8jm3cmpr`.
- Author: the connected account, with `me: true`.
- Initial returned status: `OPEN`.

Resolved it in a subsequent native batch request:

```json
{
  "requests": [
    {
      "addCommentReply": {
        "commentId": "doco.F3hTQVBiHBWDqEdf1RxA2Q",
        "post": {
          "content": "[CODEX-COMMENT-RESOLVE-20261101-E] Resolving my own native anchored comment after creation.",
          "commentAction": "RESOLVE"
        }
      }
    }
  ]
}
```

The response returned a closing post with `commentAction: "RESOLVE"`. Independent comment readback showed the same thread and anchor, `resolved: true`, and a closing reply with `action: "resolve"`.

**Result: creation and resolution of an owned native anchored comment passed through API readback.** Separate editor confirmation for test E was not recorded.

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
- Editing or deleting existing comments, deleting replies, or reopening resolved threads.
- Restoring revisions or complete revision-history coverage.
- Sharing changes, file deletion, image/table insertion, or unrelated Drive operations.

These are limits of the test coverage, not proof that the underlying Google APIs cannot perform the operations.

## References

- [Google Docs: Work with comments and suggestions](https://developers.google.com/workspace/docs/api/how-tos/suggestions).
- [Google Docs: documents.batchUpdate](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate).
- Primary empirical evidence: connector responses, native readbacks, marked records in the test document, and the user's editor confirmation during this session. Raw response dumps and credentials are not included in this report.
