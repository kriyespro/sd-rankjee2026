import requests
import json

resp = requests.get("https://openrouter.ai/api/v1/models")
models = resp.json().get("data", [])

free_models = [m["id"] for m in models if m.get("pricing", {}).get("prompt") == "0" and m.get("pricing", {}).get("completion") == "0"]

print("Free Models:")
for m in free_models:
    if "free" in m.lower():
        print(m)
