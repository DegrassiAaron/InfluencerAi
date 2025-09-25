#!/usr/bin/env python3
import os, json, time, argparse, base64, requests, hashlib, yaml, pathlib, re

API_KEY = os.getenv("OPENROUTER_API_KEY")
IMG_URL = "https://openrouter.ai/api/v1/images"       # [Unverified] endpoint immagini
TXT_URL = "https://openrouter.ai/api/v1/chat/completions"

def sha(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()[:10]

def gen_text(prompt, model="openai/gpt-4o-mini"):
    h = {"Authorization": f"Bearer {API_KEY}", "Content-Type":"application/json"}
    p = {"model": model, "messages":[{"role":"user","content":prompt}]}
    r = requests.post(TXT_URL, headers=h, json=p, timeout=120); r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def gen_image(prompt, model="stability-ai/stable-diffusion-xl-base-1.0", width=1024, height=1024, outdir="data/synth_openrouter"):
    h = {"Authorization": f"Bearer {API_KEY}"}
    p = {"model": model, "prompt": prompt, "width": width, "height": height}
    r = requests.post(IMG_URL, headers=h, json=p, timeout=300); r.raise_for_status()
    os.makedirs(outdir, exist_ok=True)
    data = r.json()["data"][0]
    if "b64_json" in data:
        img_bytes = base64.b64decode(data["b64_json"])
        fn = os.path.join(outdir, f"{sha(prompt)}.png")
        open(fn,"wb").write(img_bytes)
        return fn
    elif "url" in data:
        # Fallback se il modello restituisce URL
        import urllib.request
        fn = os.path.join(outdir, f"{sha(prompt)}.png")
        urllib.request.urlretrieve(data["url"], fn)
        return fn
    else:
        raise RuntimeError(f"Unexpected image payload: {data}")

def build_prompt(persona, scene, pose, outfit, light, focal, negatives):
    return (
        f"{persona}\n"
        f"Scene: {scene}\nPose: {pose}\nOutfit: {outfit}\nLighting: {light}\n"
        f"Optics: {focal}, shallow depth of field, photo-real, natural skin texture.\n"
        f"Negative: {negatives}"
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt_bank", required=True)
    ap.add_argument("--out", default="data/synth_openrouter")
    ap.add_argument("--per_scene", type=int, default=12)
    ap.add_argument("--img_model", default="stability-ai/stable-diffusion-xl-base-1.0")
    ap.add_argument("--negatives", default="deformed, extra fingers, extra limbs, lowres, blurry, watermark, text, logo")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    args = ap.parse_args()

    assert API_KEY, "Set OPENROUTER_API_KEY"
    cfg = yaml.safe_load(open(args.prompt_bank, "r", encoding="utf-8"))

    persona = cfg["persona"]
    scenes  = cfg["scenes"]
    lights  = cfg["lighting"]
    poses   = cfg["poses"]
    outfits = cfg["outfits"]
    focals  = cfg["focals"]

    manifest = {}
    for scene in scenes:
        for i in range(args.per_scene):
            pose, outfit = poses[i % len(poses)], outfits[i % len(outfits)]
            focal, light = focals[i % len(focals)], lights[i % len(lights)]
            prompt = build_prompt(cfg["persona"], scene, pose, outfit, light, focal, args.negatives)
            try:
                fn = gen_image(prompt, model=args.img_model, width=args.width, height=args.height, outdir=args.out)
                base = pathlib.Path(fn).stem
                manifest[base] = dict(scene=scene, pose=pose, outfit=outfit, focal=focal, lighting=light, prompt=prompt)
                print("[IMG]", fn)
                time.sleep(0.2)  # rate-limit gentile
            except Exception as e:
                print("[ERR]", e)

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
