#!/usr/bin/env python3
# [Unverified] Leonardo.ai API usage may change. Fill API key and endpoints as per official docs.
import os, json, time, argparse, requests, hashlib

API_KEY = os.getenv("LEONARDO_API_KEY", "")
BASE_URL = "https://cloud.leonardo.ai/api/rest/v1"  # [Unverified] check docs

def sha(s): 
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]

def create_generation(prompt, image_ref=None, params=None):
    url = f"{BASE_URL}/generations"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"prompt": prompt}
    if params: 
        payload.update(params)
    if image_ref:
        payload["image_prompts"] = [image_ref]  # [Unverified] replace with correct field for img2img/face ref
    r = requests.post(url, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def get_generation(gen_id):
    url = f"{BASE_URL}/generations/{gen_id}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()

def download(url, outdir, name):
    os.makedirs(outdir, exist_ok=True)
    data = requests.get(url, timeout=120).content
    fp = os.path.join(outdir, f"{name}.jpg")
    with open(fp, "wb") as f:
        f.write(data)
    return fp

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt_bank", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--per_scene", type=int, default=12)
    ap.add_argument("--negative", default="deformed, extra fingers, lowres, blurry, watermark, text, logo")
    args = ap.parse_args()

    assert API_KEY, "Set LEONARDO_API_KEY env var"
    with open(args.prompt_bank, "r", encoding="utf-8") as f:
        import yaml
        cfg = yaml.safe_load(f)

    persona = cfg["persona"]
    scenes = cfg["scenes"]
    lighting = cfg["lighting"]
    poses = cfg["poses"]
    outfits = cfg["outfits"]
    focals = cfg["focals"]

    manifest = {}

    for scene in scenes:
        for i in range(args.per_scene):
            pose = poses[i % len(poses)]
            outfit = outfits[i % len(outfits)]
            focal = focals[i % len(focals)]
            light = lighting[i % len(lighting)]
            prompt = (
                f"{persona}\n"
                f"Scene: {scene}\n"
                f"Pose: {pose}\n"
                f"Outfit: {outfit}\n"
                f"Lighting: {light}\n"
                f"Optics: {focal}, shallow depth of field, photo-real.\n"
                f"Negative: {args.negative}"
            )
            try:
                job = create_generation(prompt, params={"num_images": 1})  # [Unverified] param name
                gen_id = job.get("sdGenerationJob", {}).get("generationId") or job.get("generationId")
                # Poll
                for _ in range(60):
                    time.sleep(3)
                    res = get_generation(gen_id)
                    images = res.get("images") or res.get("generations_by_pk", {}).get("generated_images", [])
                    if images:
                        url = images[0].get("url") or images[0].get("url_small")
                        name = sha(prompt + str(i))
                        fp = download(url, args.out, name)
                        manifest[name] = {"scene": scene, "pose": pose, "outfit": outfit, "focal": focal, "lighting": light, "prompt": prompt}
                        print(f"[DL] {fp}")
                        break
            except Exception as e:
                print(f"[ERR] {e}")

    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
