# Gemini Script Hardening Plan

## Goal

Harden the Gemini import pipeline so that failed or malformed inputs do not silently corrupt the generated Open WebUI import data.

This plan is based on a review of the current scripts only. No code changes have been made yet.

## Scope

Scripts in scope:

- `gemini/extract_from_gemini.py`
- `gemini/upload_to_webui.py`
- `gemini/merge_chats.py`
- `gemini/remove_all_uploads.py`
- `gemini/dump_ids.py`

Out of scope for this task set:

- Redesigning the Open WebUI import schema
- Changing the overall Gemini conversion workflow
- UI automation for Open WebUI

## Current Assumptions Confirmed

- The Takeout attachment files are expected to live in one directory, so bare filenames should be unique within one export.
- The exact `safeHtmlItem` shape from Google Takeout is not known in advance and should be treated as untrusted input.

## Priority Order

1. Prevent partial upload runs from destroying retry state.
2. Stop silently generating wrong timestamps and wrong conversation boundaries.
3. Reject invalid merge instructions before mutating chat history.
4. Add safety controls around global cleanup.
5. Clean up usability issues such as stale defaults and diagnostics.

## Task 1: Make Upload Finalization Failure-Safe

### Problem

`gemini/upload_to_webui.py` currently removes `_pending_uploads` from messages and deletes `upload_journal.json` even when some uploads fail or files are missing. That can produce a final JSON that looks complete but is no longer resumable.

### Relevant Code

- `gemini/upload_to_webui.py`, around the `_pending_uploads` removal and final journal cleanup

### Required Changes

- Track whether any upload failed, any file was missing locally, or any API response was incomplete.
- Only remove `_pending_uploads` for a message when all files for that message were successfully resolved into Open WebUI file IDs.
- Only delete `upload_journal.json` after a fully successful run.
- Return a non-zero exit status when the run is incomplete.
- Print a final summary that clearly distinguishes:
  - successful uploads
  - resumed uploads from journal
  - failed uploads
  - missing local files
  - messages still containing pending uploads

### Acceptance Criteria

- Interrupting a run and rerunning it resumes cleanly.
- A run with one failed upload preserves enough state to retry without regenerating the intermediate file.
- The output JSON never silently loses unresolved `_pending_uploads` entries.

## Task 2: Harden Upload Journaling and Identity Tracking

### Problem

The upload journal is currently keyed only by filename. Even if filenames are expected to be unique within one export, the script should not rely on that assumption more than necessary.

### Relevant Code

- `gemini/upload_to_webui.py`, journal load and save logic

### Required Changes

- Replace the bare filename journal key with a stronger identity key.
- Candidate key strategy:
  - relative path if available, plus filename
  - or filename plus file size
  - or filename plus a content hash
- Decide on the cheapest robust option and document it.
- Include backward-compatible handling for an existing journal file if practical, or fail fast with a clear message if the journal format is outdated.

### Acceptance Criteria

- Journal entries are stable across resume attempts.
- The script does not accidentally reuse an uploaded file ID for the wrong local file.
- The journal format is documented in code comments or the workflow documentation.

## Task 3: Stop Silent Timestamp Corruption in the Extractor

### Problem

`gemini/extract_from_gemini.py` currently falls back to the current wall-clock time when timestamp parsing fails. That silently changes ordering and timeout-based chat splitting.

### Relevant Code

- `gemini/extract_from_gemini.py`, `parse_time`

### Required Changes

- Replace the `datetime.now()` fallback with explicit error handling.
- Choose one of these behaviors and document it:
  - skip malformed items and report them
  - fail the run with a clear error message
- Include the offending item context in diagnostics where safe, such as title and raw time string.
- Keep the behavior deterministic.

### Acceptance Criteria

- Invalid timestamps never become synthetic current timestamps.
- Users can tell which Takeout items were skipped or why the run stopped.
- Session grouping remains deterministic across repeated runs.

## Task 4: Validate Semi-Structured Takeout Input Before Indexing

### Problem

The extractor assumes `safeHtmlItem[0]` exists whenever `safeHtmlItem` is present. That is optimistic for Takeout data and can crash on empty or malformed items.

### Relevant Code

- `gemini/extract_from_gemini.py`, activity item parsing

### Required Changes

- Validate that `safeHtmlItem` is a non-empty list before indexing.
- Validate that the first element is a mapping containing an `html` field or a safe default path.
- Add counters or summary output for skipped malformed items.
- Review other similarly optimistic assumptions in the extractor, especially `attachedFiles` and `subtitles`.

### Acceptance Criteria

- Empty or malformed Takeout entries do not crash the run.
- Skipped entries are counted and reported.
- Well-formed entries still produce the same output shape.

## Task 5: Validate Merge Maps Before Rewriting Chats

### Problem

`gemini/merge_chats.py` accepts overlapping or repeated chat IDs across merge groups and mutates message objects in place. A bad merge map can produce duplicated or inconsistent history.

### Relevant Code

- `gemini/merge_chats.py`, merge group iteration and message rewiring

### Required Changes

- Pre-validate the merge map before applying any merge.
- Reject these cases with a clear error and non-zero exit status:
  - duplicate chat IDs across groups
  - unknown chat IDs, or at least optionally warn and fail depending on a strict mode
  - merge groups with fewer than two valid IDs
- Avoid mutating original message objects until validation succeeds.
- Consider deep-copying message dictionaries before rewriting parent/child links.

### Acceptance Criteria

- Invalid merge maps are rejected before any output file is written.
- The output graph remains a valid linear history after merging.
- Repeated runs with the same input and merge map are deterministic.

## Task 6: Add Guard Rails to Global Cleanup

### Problem

`gemini/remove_all_uploads.py` calls global delete-all endpoints for files, documents, and knowledge without any confirmation or dry-run behavior.

### Relevant Code

- `gemini/remove_all_uploads.py`, endpoint loop

### Required Changes

- Add an explicit confirmation mechanism, for example a required `--confirm-delete-all` flag.
- Add a dry-run mode that prints the endpoints that would be called and the target base URL without sending requests.
- Fail with a non-zero exit status if any delete request fails.
- Print a structured summary at the end rather than only raw response text.
- Update documentation to make the global scope unmistakable.

### Acceptance Criteria

- The script cannot be run destructively by accident with only URL and API key.
- Operators can test intent safely with dry-run output.
- Failures are clearly visible to calling automation or shell scripts.

## Task 7: Align Defaults and CLI Help With Actual Workflow

### Problem

Some script defaults and help text refer to filenames that do not match the documented workflow and current checked-in examples. That increases operator error.

### Relevant Code

- `gemini/upload_to_webui.py`
- `gemini/dump_ids.py`
- `gemini/merge_chats.py`
- `gemini/extract_from_gemini.py`

### Required Changes

- Standardize default filenames around the actual workflow used in this repo.
- Ensure help text consistently refers to:
  - intermediate JSON
  - merged intermediate JSON if applicable
  - final Open WebUI import JSON
- Update README and `GEMINI_IMPORT.md` if any filenames change.

### Acceptance Criteria

- Running `--help` on each script reflects the documented workflow.
- Defaults do not point to misleading or obsolete filenames.

## Task 8: Improve Diagnostics and Exit Codes Across All Scripts

### Problem

Several scripts print useful information, but success and failure states are not always machine-detectable or consistent.

### Required Changes

- Make all fatal problems exit non-zero.
- Make partial-success states explicit where applicable.
- Add concise end-of-run summaries with counters.
- Keep logs readable enough for manual use without hiding details needed for debugging.

### Acceptance Criteria

- Shell users can detect success or failure through exit codes.
- Logs make it clear whether output files are safe to use.

## Suggested Implementation Sequence

1. Task 1
2. Task 3
3. Task 4
4. Task 5
5. Task 6
6. Task 7
7. Task 8
8. Task 2

Rationale:

- Task 1 removes the highest risk of losing retry state after partial upload failure.
- Tasks 3 and 4 harden input integrity early in the pipeline.
- Task 5 prevents user-provided merge instructions from corrupting history.
- Task 6 reduces operational risk for destructive cleanup.
- Task 7 and Task 8 improve day-to-day usability once correctness is protected.
- Task 2 can be implemented earlier if desired, but it is less urgent given the current assumption that filenames are unique within one export.

## Test Ideas

Use small fixture files rather than large real exports where possible.

- Extractor fixture with:
  - valid items
  - missing `time`
  - invalid `time`
  - empty `safeHtmlItem`
  - missing `html`
  - generated image references with extension fallback
- Upload fixture with:
  - one successful file
  - one missing local file
  - one simulated API failure
  - interrupted run with resume journal present
- Merge fixture with:
  - valid two-chat merge
  - duplicate chat ID across groups
  - unknown chat ID
  - repeated execution to verify determinism
- Cleanup script checks with:
  - dry-run mode
  - missing confirmation flag
  - one failing endpoint

## Definition of Done

The hardening work is complete when:

- partial upload failures are resumable without regenerating the intermediate export
- malformed timestamps and malformed Takeout items do not silently corrupt output
- invalid merge maps are rejected safely
- destructive cleanup requires explicit confirmation
- CLI defaults and documentation match the real workflow
- each script provides reliable exit codes and clear operator-facing summaries
