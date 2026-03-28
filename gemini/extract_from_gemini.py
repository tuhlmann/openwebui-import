import argparse
import html
import json
import re
import uuid
import os
import base64
from datetime import datetime

EXCLUDE_LIST = ["alarmiere mich"]

def clean_html_to_markdown(html_content):
    text = html_content.replace("</p>", "\n\n")
    text = text.replace("</li>", "\n")
    text = text.replace("<li>", "- ")
    text = text.replace("<br>", "\n").replace("<br/>", "\n")
    text = text.replace("</h3>", "\n\n").replace("</h2>", "\n\n")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()

def parse_time(time_str):
    try:
        dt_obj = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return int(dt_obj.timestamp())
    except Exception:
        return int(datetime.now().timestamp())

def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

parser = argparse.ArgumentParser(description="Convert Gemini Takeout to Intermediate Open WebUI format.")
parser.add_argument("-i", "--input", default="MyActivity.json", help="Input JSON file from Google Takeout")
parser.add_argument("-o", "--output", default="intermediate_openwebui.json", help="Intermediate output JSON file")
parser.add_argument("--timeout", type=int, default=30, help="Minutes of inactivity for new thread.")
args = parser.parse_args()

input_dir = os.path.dirname(os.path.abspath(args.input))

with open(args.input, "r", encoding="utf-8") as f:
    gemini_data = json.load(f)

processed_items = []
for item in gemini_data:
    if "title" not in item or "safeHtmlItem" not in item:
        continue

    original_title = item["title"]
    if any(ex.lower() in original_title.lower() for ex in EXCLUDE_LIST):
        continue

    prompt = original_title.replace("Eingegebener Prompt: ", "", 1).strip()
    raw_html = item["safeHtmlItem"][0].get("html", "")
    response = clean_html_to_markdown(raw_html)

    generated_images = []
    pending_uploads = []

    if "attachedFiles" in item:
        subtitles = item.get("subtitles", [])
        is_upload = any("url" in sub for sub in subtitles)

        for filename in item["attachedFiles"]:
            if is_upload:
                pending_uploads.append(filename)
            elif f'src="{filename}"' in raw_html:
                generated_images.append(filename)

    # Process Generated Images (Base64 embed)
    for filename in generated_images:
        original_img_path = os.path.join(input_dir, filename)
        actual_img_path = None

        if os.path.exists(original_img_path):
            actual_img_path = original_img_path
        else:
            base_name = os.path.splitext(filename)[0]
            for ext in ['.jpg', '.jpeg', '.webp']:
                fallback_path = os.path.join(input_dir, base_name + ext)
                if os.path.exists(fallback_path):
                    actual_img_path = fallback_path
                    break

        if actual_img_path:
            ext = os.path.splitext(actual_img_path)[1].lower().replace(".", "")
            mime = f"image/{ext}" if ext in ["png", "jpg", "jpeg", "gif", "webp"] else "image/png"
            if mime == "image/jpg": mime = "image/jpeg"

            b64_str = get_base64_image(actual_img_path)
            response += f"\n\n![Gemini Generated Image](data:{mime};base64,{b64_str})"

    if not response or not prompt:
        continue

    processed_items.append({
        "prompt": prompt,
        "response": response,
        "timestamp": parse_time(item.get("time")),
        "pending_uploads": pending_uploads
    })

processed_items.sort(key=lambda x: x["timestamp"])
timeout_seconds = args.timeout * 60
sessions, current_session = [], []

for item in processed_items:
    if not current_session:
        current_session.append(item)
    else:
        if item["timestamp"] - current_session[-1]["timestamp"] <= timeout_seconds:
            current_session.append(item)
        else:
            sessions.append(current_session)
            current_session = [item]

if current_session: sessions.append(current_session)

openwebui_export = []
for session in sessions:
    chat_id = str(uuid.uuid4())
    safe_title = session[0]["prompt"].replace("\n", " ").replace("\r", "")
    display_title = (safe_title[:47] + "...") if len(safe_title) > 50 else safe_title

    messages = {}
    last_msg_id = None

    for item in session:
        user_msg_id, asst_msg_id = str(uuid.uuid4()), str(uuid.uuid4())

        if last_msg_id:
            messages[last_msg_id]["childrenIds"].append(user_msg_id)

        user_msg = {
            "id": user_msg_id,
            "parentId": last_msg_id,
            "childrenIds": [asst_msg_id],
            "role": "user",
            "content": item["prompt"],
            "timestamp": item["timestamp"],
        }

        # Inject the pending uploads exactly here
        if item.get("pending_uploads"):
            user_msg["_pending_uploads"] = item["pending_uploads"]

        messages[user_msg_id] = user_msg

        messages[asst_msg_id] = {
            "id": asst_msg_id,
            "parentId": user_msg_id,
            "childrenIds": [],
            "role": "assistant",
            "content": item["response"],
            "timestamp": item["timestamp"] + 1,
        }
        last_msg_id = asst_msg_id

    openwebui_export.append({
        "id": chat_id,
        "title": display_title,
        "timestamp": session[0]["timestamp"],
        "updated_at": session[-1]["timestamp"],
        "chat": {
            "title": display_title,
            "models": ["gemini-takeout"],
            "history": {"currentId": last_msg_id, "messages": messages},
        },
    })

with open(args.output, "w", encoding="utf-8") as f:
    json.dump(openwebui_export, f, indent=2)
print(f"Created intermediate file: {args.output}")
