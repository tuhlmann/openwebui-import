# Gemini Takeout to Open WebUI

This repository contains a Gemini-specific conversion pipeline:

1. Export Gemini activity from Google Takeout.
2. Convert the Takeout JSON into an intermediate Open WebUI chat export.
3. Optionally inspect chat IDs and merge conversations that were split by the timeout rule.
4. Upload user-provided attachments to Open WebUI and inject the returned file IDs into the export.
5. Batch-import the final JSON file through the Open WebUI UI.

## Recommended Safety Strategy

Before importing Gemini chats, export your existing Open WebUI chats first. That gives you a clean rollback path if you want to delete the imported Gemini chats and restore your earlier state.

Also keep the original intermediate JSON file. If attachment upload goes wrong, it is safer to re-run from the intermediate file than to reuse a partially processed final file.

## Prerequisites

- Python 3
- The `requests` package for the upload and cleanup scripts
- An Open WebUI account that is allowed to create API keys and upload files

Example setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install requests
```

## 1. Export Gemini Data with Google Takeout

1. Open Google Takeout.
2. Deselect everything.
3. Select the activity export that contains Gemini history.
4. In the format/details dialog, make sure Gemini activity is included and the export format is JSON.
5. Create the export, download it, and extract the archive.
6. Locate the Gemini activity folder. In many Takeout exports this is under a path similar to `Takeout/My Activity/Gemini/`.

What you need from the extracted folder:

- The Gemini activity JSON file, usually named `MyActivity.json`
- Any attached files referenced by the activity entries
- Any Gemini-generated image files that appear alongside the JSON

The conversion script reads the JSON and looks for referenced files relative to the JSON file location. The easiest approach is to point the script directly at the extracted `MyActivity.json` inside the Gemini folder.

## 2. Create the Intermediate Open WebUI Export

Run the extractor from the repository root and pass explicit file names rather than relying on script defaults:

```bash
python gemini/extract_from_gemini.py \
  -i "/path/to/Takeout/My Activity/Gemini/MyActivity.json" \
  -o gemini/openwebui_intermediate.json \
  --timeout 30
```

What this script does:

- Converts Gemini prompts and HTML answers into a simplified markdown-like message format
- Groups consecutive prompt/response pairs into one conversation if the gap is less than or equal to `--timeout` minutes
- Embeds Gemini-generated images directly into assistant messages as base64 data URLs
- Marks user-uploaded assets as pending uploads so they can be uploaded to Open WebUI later

What `--timeout` means:

- If the gap between two Gemini prompts is more than the timeout, the script starts a new chat thread
- If Gemini split what you consider one conversation into two files, you can merge them later with `merge_chats.py`

Code-specific notes:

- Titles containing `alarmiere mich` are currently excluded by a hardcoded filter in `extract_from_gemini.py`
- If your Takeout JSON is not named `MyActivity.json`, pass the real path with `-i`

## 3. Inspect Chats and Identify Split Conversations

To get a readable list of chat IDs, prompt counts, timestamps, and titles:

```bash
python gemini/dump_ids.py \
  -i gemini/openwebui_intermediate.json \
  -o gemini/chat_ids.txt
```

Open `gemini/chat_ids.txt` and look for conversations that should really be one thread.

## 4. Merge Conversations Manually

Create a JSON file that contains arrays of chat IDs to merge. Example:

```json
[
  [
    "11111111-1111-1111-1111-111111111111",
    "22222222-2222-2222-2222-222222222222"
  ],
  [
    "33333333-3333-3333-3333-333333333333",
    "44444444-4444-4444-4444-444444444444",
    "55555555-5555-5555-5555-555555555555"
  ]
]
```

Then run:

```bash
python gemini/merge_chats.py \
  -i gemini/openwebui_intermediate.json \
  -m gemini/merge_map.json \
  -o gemini/openwebui_intermediate_merged.json
```

How merging works:

- Messages from the selected chats are combined and sorted by timestamp
- The merged chat keeps the ID and title of the first chat in each group
- The original chats in the group are removed from the output

If no merges are needed, keep using `gemini/openwebui_intermediate.json` in the next step.

## 5. Create an Open WebUI API Key

You need a personal API key because `upload_to_webui.py` uploads pending files through the Open WebUI API.

In Open WebUI:

1. Open your account or settings area.
2. Create a personal API key.
3. Copy the key and store it securely.

If your user cannot create API keys, your Open WebUI instance is not configured to allow it for that account. In that case, ask the instance administrator to enable API key usage and file uploads for your user before continuing.

## 6. Upload Referenced Files to Open WebUI

Use the intermediate file from the previous steps and point `-d` at the Gemini Takeout directory that contains the referenced uploaded files.

If you merged chats, use the merged intermediate file:

```bash
python gemini/upload_to_webui.py \
  -i gemini/openwebui_intermediate_merged.json \
  -o gemini/openwebui_final.json \
  -d "/path/to/Takeout/My Activity/Gemini" \
  --url "https://openwebui.example.com" \
  --key "YOUR_API_KEY" \
  --delay 5
```

If you did not merge chats, use `gemini/openwebui_intermediate.json` as the input.

What this script does:

- Finds every message marked with `_pending_uploads`
- Uploads each referenced file to Open WebUI using the files API
- Writes a temporary `upload_journal.json` next to the output file so an interrupted run can resume
- Replaces `_pending_uploads` with the `files` metadata expected by the import JSON
- Writes the final import file

Operational notes:

- Re-running the same upload command after an interruption will reuse the journal and skip files that were already uploaded
- The script uploads to `/api/v1/files/?process=false`
- The final JSON contains the file IDs returned by Open WebUI for those uploads

Important limitations from the current implementation:

- The resume journal is keyed only by filename, so do not combine different Takeout folders with colliding file names in one run
- If some uploads fail, the script still writes the output file and removes the temporary pending markers from messages
- Because of that behavior, if you see upload errors, go back to the original intermediate JSON and rerun from there after fixing the problem

## 7. Batch Import the Final JSON into Open WebUI

After the upload script finishes successfully, import the resulting `gemini/openwebui_final.json` through the Open WebUI batch import UI.

At that point:

- The chat history should appear as imported Gemini conversations
- Gemini-generated images should already be embedded inside the imported assistant messages
- User-uploaded files should be linked through the uploaded Open WebUI file IDs

## 8. If You Need to Start Over

There are two separate cleanup paths:

### Delete Imported Chats

If the chat import itself is wrong, you can bulk-delete chats in the Open WebUI UI and then re-import from a corrected JSON export.

This is the preferred reset path if the problem is only in the imported conversations.

### Remove Uploaded Files, Documents, and Knowledge

The script `gemini/remove_all_uploads.py` is much broader and should be treated as a full cleanup tool, not a Gemini-only cleanup tool.

Run it only if you explicitly want to trigger Open WebUI's global delete-all endpoints:

```bash
python gemini/remove_all_uploads.py \
  --url "https://openwebui.example.com" \
  --key "YOUR_API_KEY"
```

What it actually calls:

- `/api/v1/files/all`
- `/api/v1/documents/all`
- `/api/v1/knowledge/all`

Implications:

- It is not scoped to files uploaded by this Gemini workflow
- It may remove unrelated uploads, documents, and knowledge entries that exist in the target Open WebUI instance or scope visible to that API key
- Use it carefully, ideally only when you intentionally want a broad cleanup

## Suggested End-to-End Workflow

1. Export your current Open WebUI chats as a backup.
2. Download and extract the Gemini Takeout archive.
3. Run `extract_from_gemini.py` to create `gemini/openwebui_intermediate.json`.
4. Run `dump_ids.py` to inspect chat IDs.
5. If needed, merge split conversations with `merge_chats.py`.
6. Create an Open WebUI API key.
7. Run `upload_to_webui.py` to create `gemini/openwebui_final.json`.
8. Import the final JSON through the Open WebUI UI.
9. If the result is wrong, bulk-delete the imported chats and retry from the intermediate JSON.
10. Only use `remove_all_uploads.py` if you intentionally want to wipe all uploads/documents/knowledge accessible to that API key.