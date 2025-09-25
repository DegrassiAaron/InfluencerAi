#!/usr/bin/env python3
import argparse, os, glob, json
import cv2, numpy as np
from albumentations import (
    Compose, HorizontalFlip, RandomBrightnessContrast, RGBShift,
    GaussNoise, CLAHE, MotionBlur, Sharpen, ImageCompression, RandomResizedCrop
)

def pipeline():
    return Compose([
        RandomResizedCrop(height=1024, width=1024, scale=(0.9,1.0), ratio=(0.9,1.1), p=0.5),
        HorizontalFlip(p=0.5),
        RandomBrightnessContrast(p=0.3),
        RGBShift(p=0.2),
        GaussNoise(p=0.1),
        CLAHE(p=0.1),
        MotionBlur(blur_limit=3, p=0.1),
        Sharpen(alpha=(0.05,0.15), lightness=(0.9,1.1), p=0.2),
        ImageCompression(quality_lower=80, quality_upper=95, p=0.5)
    ], p=1.0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--captions", dest="captions", required=True)
    ap.add_argument("--num_aug", type=int, default=1)
    ap.add_argument("--meta", dest="meta", help="json with per-image metadata (prompt, seed, scene, lighting)", default=None)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.captions, exist_ok=True)
    aug = pipeline()
    meta = {}
    if args.meta and os.path.exists(args.meta):
        with open(args.meta, "r", encoding="utf-8") as f:
            meta = json.load(f)

    count = 0
    files = [f for f in glob.glob(os.path.join(args.inp, "*.*")) if f.lower().endswith((".jpg",".jpeg",".png",".webp"))]
    for fp in files:
        img = cv2.imdecode(np.fromfile(fp, dtype=np.uint8), cv2.IMREAD_COLOR)
        base = os.path.splitext(os.path.basename(fp))[0]

        # save original to out
        cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])[1].tofile(os.path.join(args.out, base + ".jpg"))

        for i in range(args.num_aug):
            auged = aug(image=img)["image"]
            outp = os.path.join(args.out, f"{base}_aug{i+1}.jpg")
            cv2.imencode(".jpg", auged, [int(cv2.IMWRITE_JPEG_QUALITY), 95])[1].tofile(outp)
            count += 1

        m = meta.get(base, {})
        scene = m.get("scene", "lifestyle scene")
        lighting = m.get("lighting", "soft light")
        outfit = m.get("outfit", "casual outfit")
        focal = m.get("focal", "50mm")
        cap = f"portrait photo of the AI influencer, {scene}, {lighting}, wearing {outfit}, shot on {focal}, photorealistic, natural skin texture"
        with open(os.path.join(args.captions, base + ".txt"), "w", encoding="utf-8") as f:
            f.write(cap)

    print(f"[DONE] Augmented {count} images, captions written to {args.captions}")

if __name__ == "__main__":
    main()
