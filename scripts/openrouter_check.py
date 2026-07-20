import os

import requests

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
if not OPENROUTER_KEY:
    raise SystemExit("Set OPENROUTER_API_KEY in your environment before running this script.")

headers = {
    "Authorization": f"Bearer {OPENROUTER_KEY.strip()}",
    "Content-Type": "application/json",
    "HTTP-Referer": "http://127.0.0.1:8000/",
    "X-Title": "RankJee Local"
}
data = {
    "model": "google/gemini-2.5-flash:free",
    "messages": [{"role": "user", "content": "Hello"}]
}

print("Testing OpenRouter API...")
resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text}")
