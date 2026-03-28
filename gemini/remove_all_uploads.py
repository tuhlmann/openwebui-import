import argparse
import requests

parser = argparse.ArgumentParser(description="Trigger the master 'Delete All' endpoints in Open WebUI.")
parser.add_argument("--url", required=True, help="Base URL (e.g., http://localhost:8080)")
parser.add_argument("--key", required=True, help="API Key (Bearer Token)")
args = parser.parse_args()

base_url = args.url.rstrip("/")
headers = {
    "Authorization": f"Bearer {args.key}",
    "Accept": "application/json"
}

# The master endpoints triggered by the UI's "Delete All" buttons
endpoints = [
    "/api/v1/files/all",
    "/api/v1/documents/all",
    "/api/v1/knowledge/all"  # Catching the newer Open WebUI architecture
]

print("⚠️  Triggering Master Deletion Endpoints...")

for endpoint in endpoints:
    full_url = f"{base_url}{endpoint}"
    print(f"\n--- Hitting {endpoint} ---")

    try:
        res = requests.delete(full_url, headers=headers)

        # Print the raw text so we can catch "silent" errors
        print(f"HTTP Status: {res.status_code}")
        print(f"Server Response: {res.text}")

    except requests.exceptions.RequestException as e:
        print(f"Network error trying to reach {endpoint}: {e}")

print("\n=== Master Cleanup Finished ===")
