@"
#!/usr/bin/env python3
import os, requests, sys, base64, urllib.request, json, pathlib
api = os.getenv("OPENROUTER_API_KEY")
if not api: sys.exit("OPENROUTER_API_KEY mancante")
H = {"Authorization": f"Bearer {api}","Content-Type":"application/json",
     "HTTP-Referer":"http://localhost","X-Title":"ai-influencer"}
P = {"model":"stability-ai/stable-diffusion-xl-base-1.0",
     "prompt":"portrait photorealistic ai influencer, soft light, 50mm",
     "width":1024,"height":1024}
r = requests.post("https://openrouter.ai/api/v1/images",
                  headers=H, json=P, timeout=180)
print("HTTP:", r.status_code); txt = r.text; print(txt[:600])
if not r.ok: sys.exit(1)
data = r.json(); rec = (data.get("data") or [{}])[0]
outdir = "/workspace/data/synth_openrouter"; pathlib.Path(outdir).mkdir(parents=True, exist_ok=True)
fn = outdir + "/test_openrouter.png"
if "b64_json" in rec and rec["b64_json"]:
    open(fn,"wb").write(base64.b64decode(rec["b64_json"])); print("Saved:", fn)
elif "url" in rec and rec["url"]:
    urllib.request.urlretrieve(rec["url"], fn); print("Saved:", fn)
else:
    print("Payload inatteso:", json.dumps(data)[:400])
"@ | Set-Content -Encoding UTF8 .\scripts\test_openrouter_image.py
