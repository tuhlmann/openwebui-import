import argparse
import json
from datetime import datetime, timezone

parser = argparse.ArgumentParser(
    description="Extract chat IDs, prompt counts, timestamps, and titles to a text file."
)
parser.add_argument(
    "-i",
    "--input",
    default="openwebui_direct_import.json",
    help="Input Open WebUI JSON file.",
)
parser.add_argument(
    "-o",
    "--output",
    default="chat_ids.txt",
    help="Output text file (default: chat_ids.txt).",
)
args = parser.parse_args()

try:
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)
except FileNotFoundError:
    print(f"Could not find {args.input}. Please make sure you have generated it first.")
    exit(1)

with open(args.output, "w", encoding="utf-8") as f:
    # Header
    f.write(f"{'CHAT ID':<38} | {'PROMPTS':<7} | {'TIMESTAMP (ISO)':<22} | TITLE\n")
    f.write("-" * 210 + "\n")

    for chat in data:
        chat_id = chat.get("id", "UNKNOWN_ID")

        # Count user prompts
        prompt_count = 0
        try:
            messages = chat.get("chat", {}).get("history", {}).get("messages", {})
            prompt_count = sum(
                1 for msg in messages.values() if msg.get("role") == "user"
            )
        except Exception:
            prompt_count = 0

        # Grab the title, sanitize newlines, and truncate to 130 chars
        raw_title = chat.get("title", "No Title").replace("\n", " ").replace("\r", "")
        title = (raw_title[:127] + "...") if len(raw_title) > 130 else raw_title

        # Convert Unix timestamp to ISO string
        ts = chat.get("timestamp", 0)
        try:
            iso_time = datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        except Exception:
            iso_time = "UNKNOWN_TIME"

        # Output the formatted row
        f.write(f"{chat_id:<38} | {prompt_count:<7} | {iso_time:<22} | {title}\n")

print(f"Successfully dumped {len(data)} chat summaries to {args.output}")
