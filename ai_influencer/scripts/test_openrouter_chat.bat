@"
#!/usr/bin/env python3
import os, requests, sys
api = os.getenv("OPENROUTER_API_KEY")
if not api: sys.exit("OPENROUTER_API_KEY mancante")
H = {"Authorization": f"Bearer {api}","Content-Type":"application/json",
     "HTTP-Referer":"http://localhost","X-Title":"ai-influencer"}
P = {"model":"openai/gpt-4o-mini",
     "messages":[{"role":"user","content":"scrivi: ok"}]}
r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                  headers=H, json=P, timeout=60)
print("HTTP:", r.status_code); print(r.text[:600])
"@ | Set-Content -Encoding UTF8 .\scripts\test_openrouter_chat.py
