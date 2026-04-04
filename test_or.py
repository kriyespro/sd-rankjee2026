import requests

OPENROUTER_KEY = "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"

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
