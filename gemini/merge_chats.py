import argparse
import json

parser = argparse.ArgumentParser(
    description="Merge specific Open WebUI chat threads based on an array of IDs."
)
parser.add_argument(
    "-i",
    "--input",
    required=True,
    help="Input Open WebUI JSON file (e.g., openwebui_direct_import.json)",
)
parser.add_argument(
    "-m",
    "--map",
    required=True,
    help="JSON map file containing arrays of IDs to merge.",
)
parser.add_argument(
    "-o",
    "--output",
    default="openwebui_merged_import.json",
    help="Output JSON file path.",
)
args = parser.parse_args()

try:
    with open(args.input, "r", encoding="utf-8") as f:
        export_data = json.load(f)
    with open(args.map, "r", encoding="utf-8") as f:
        merge_map = json.load(f)
except FileNotFoundError as e:
    print(f"Error loading files: {e}")
    exit(1)

chats_by_id = {chat["id"]: chat for chat in export_data}
ids_to_remove = set()
merged_chats_to_add = []

for id_group in merge_map:
    if not id_group or len(id_group) < 2:
        continue

    all_messages = []
    valid_group_ids = []

    for chat_id in id_group:
        if chat_id in chats_by_id:
            valid_group_ids.append(chat_id)
            all_messages.extend(
                chats_by_id[chat_id]["chat"]["history"]["messages"].values()
            )

    if not valid_group_ids:
        continue

    all_messages.sort(key=lambda x: x["timestamp"])
    new_messages_dict = {}
    last_msg_id = None

    for msg in all_messages:
        msg_id = msg["id"]
        if last_msg_id:
            msg["parentId"] = last_msg_id
            new_messages_dict[last_msg_id]["childrenIds"] = [msg_id]
        else:
            msg["parentId"] = None

        msg["childrenIds"] = []
        new_messages_dict[msg_id] = msg
        last_msg_id = msg_id

    base_chat = chats_by_id[valid_group_ids[0]]
    merged_chats_to_add.append(
        {
            "id": base_chat["id"],
            "title": base_chat["title"],
            "timestamp": all_messages[0]["timestamp"],
            "updated_at": all_messages[-1]["timestamp"],
            "chat": {
                "title": base_chat["chat"]["title"],
                "models": base_chat["chat"].get("models", ["gemini-takeout"]),
                "history": {"currentId": last_msg_id, "messages": new_messages_dict},
            },
        }
    )
    ids_to_remove.update(valid_group_ids)

final_export = [c for c in export_data if c["id"] not in ids_to_remove]
final_export.extend(merged_chats_to_add)
final_export.sort(key=lambda x: x["timestamp"])

with open(args.output, "w", encoding="utf-8") as f:
    json.dump(final_export, f, indent=2)

print(
    f"Merged {len(ids_to_remove)} chats into {len(merged_chats_to_add)} threads. Exported to {args.output}"
)
