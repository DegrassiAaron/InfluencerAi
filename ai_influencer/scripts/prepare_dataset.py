#!/usr/bin/env python3
import argparse, os, glob
import cv2
import numpy as np
from rembg import remove
from insightface.app import FaceAnalysis

def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

def load_img(path):
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    return img

def save_img(path, img):
    ext = os.path.splitext(path)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".png"
        path = path + ext
    cv2.imencode(ext, img)[1].tofile(path)

def do_rembg(img):
    result = remove(img, alpha_matting=True)
    if result.shape[2] == 4:
        bgr = cv2.cvtColor(result, cv2.COLOR_BGRA2BGR)
        return bgr
    return result

def face_cropper():
    app = FaceAnalysis(name='buffalo_l')
    app.prepare(ctx_id=0, det_size=(640,640))
    def crop(img, margin=20):
        faces = app.get(img)
        if not faces:
            return None
        f = max(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
        x1,y1,x2,y2 = map(int, f.bbox)
        h, w = img.shape[:2]
        x1 = max(0, x1 - margin); y1 = max(0, y1 - margin)
        x2 = min(w, x2 + margin); y2 = min(h, y2 + margin)
        return img[y1:y2, x1:x2].copy()
    return crop

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--do_rembg", action="store_true")
    ap.add_argument("--do_facecrop", action="store_true")
    args = ap.parse_args()

    ensure_dir(args.out)
    crop = face_cropper() if args.do_facecrop else None

    files = []
    for ext in ("*.jpg","*.jpeg","*.png","*.webp"):
        files += glob.glob(os.path.join(args.inp, ext))

    for fp in files:
        img = load_img(fp)
        if img is None:
            print(f"[WARN] Cannot read {fp}")
            continue
        if args.do_rembg:
            try:
                img = do_rembg(img)
            except Exception as e:
                print(f"[rembg fail] {fp}: {e}")
        if crop:
            c = crop(img)
            if c is not None:
                img = c
        outp = os.path.join(args.out, os.path.basename(fp))
        save_img(outp, img)
        print(f"[OK] {outp}")

if __name__ == "__main__":
    main()
