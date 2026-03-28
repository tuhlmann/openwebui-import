import argparse
import json
import os
import time
import requests
import mimetypes

parser = argparse.ArgumentParser(description="Upload pending files to Open WebUI with Resume/Journaling.")
parser.add_argument("-i", "--input", default="intermediate_openwebui.json", help="Intermediate JSON file")
parser.add_argument("-o", "--output", default="final_openwebui_import.json", help="Final output JSON file")
parser.add_argument("-d", "--dir", required=True, help="Directory containing the actual uploaded files from Takeout")
parser.add_argument("--url", required=True, help="Base URL of your Open WebUI instance")
parser.add_argument("--key", required=True, help="Open WebUI API Key (Bearer Token)")
parser.add_argument("--delay", type=int, default=5, help="Seconds to wait between successful uploads")
args = parser.parse_args()

# Setup paths and URL
base_url = args.url.rstrip("/")
# Upload files but do not process them- its history
api_endpoint = f"{base_url}/api/v1/files/?process=false"
output_dir = os.path.dirname(os.path.abspath(args.output))
journal_path = os.path.join(output_dir, "upload_journal.json")

headers = {
    "Authorization": f"Bearer {args.key}",
    "Accept": "application/json"
}

# 1. Load the Journal (if resuming)
journal = {}
if os.path.exists(journal_path):
    with open(journal_path, "r", encoding="utf-8") as jf:
        journal = json.load(jf)
    print(f"--- Resuming Session: Found {len(journal)} previously uploaded files in journal ---")

# 2. Load the Intermediate Data
with open(args.input, "r", encoding="utf-8") as f:
    data = json.load(f)

total_uploads = 0
successful_uploads = 0
skipped_uploads = 0

# 3. Process Uploads
for chat in data:
    messages = chat.get("chat", {}).get("history", {}).get("messages", {})

    for msg_id, msg in messages.items():
        if "_pending_uploads" in msg:
            uploaded_files_meta = []

            for filename in msg["_pending_uploads"]:
                total_uploads += 1

                # Check Journal First
                if filename in journal:
                    print(f"Skipping: {filename} (Already uploaded, ID: {journal[filename]})")
                    uploaded_files_meta.append({
                        "type": "file",
                        "id": journal[filename],
                        "name": filename
                    })
                    skipped_uploads += 1
                    continue

                # If not in journal, proceed to upload
                file_path = os.path.join(args.dir, filename)

                if os.path.exists(file_path):
                    print(f"Uploading: {filename}...")

                    try:
                        # Guess the MIME type, fallback to binary if unknown
                        mime_type, _ = mimetypes.guess_type(filename)
                        if mime_type is None:
                            mime_type = 'application/octet-stream'

                        with open(file_path, 'rb') as upload_file:
                            # Pass the MIME type as the third item in the tuple
                            files = {'file': (filename, upload_file, mime_type)}
                            response = requests.post(api_endpoint, headers=headers, files=files)

                            response.raise_for_status()
                            result = response.json()

                            file_id = result.get("id")
                            if file_id:
                                uploaded_files_meta.append({
                                    "type": "file",
                                    "id": file_id,
                                    "name": filename
                                })
                                successful_uploads += 1
                                print(f"  -> Success! File ID: {file_id}. Waiting {args.delay}s...")

                                # Instantly write to journal to lock the state
                                journal[filename] = file_id
                                with open(journal_path, "w", encoding="utf-8") as jf:
                                    json.dump(journal, jf, indent=2)

                                time.sleep(args.delay)
                            else:
                                print(f"  -> API returned 200 but no ID was found in response: {result}")

                    except requests.exceptions.RequestException as e:
                        print(f"  -> Network/API Error uploading {filename}: {e}")
                        if 'response' in locals() and response is not None:
                            print(f"  -> Response content: {response.text}")
                else:
                    print(f"  -> Error: File not found locally at {file_path}")

            # Update the JSON schema for this specific message
            if uploaded_files_meta:
                msg["files"] = uploaded_files_meta

            # Remove the temporary marker
            del msg["_pending_uploads"]

# 4. Finalize and Cleanup
with open(args.output, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2)

if os.path.exists(journal_path):
    os.remove(journal_path)
    print("\nCleaned up temporary journal file.")

print("\n--- Upload Complete ---")
print(f"Total Files Found: {total_uploads} | Uploaded This Run: {successful_uploads} | Skipped (from prior runs): {skipped_uploads}")
print(f"Final import-ready file saved to: {args.output}")
