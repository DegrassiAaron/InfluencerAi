#!/usr/bin/env python3
import argparse, os, glob, csv
import numpy as np, cv2
from insightface.app import FaceAnalysis

def blur_score(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def load(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

def embedder():
    app = FaceAnalysis(name='buffalo_l'); app.prepare(ctx_id=0, det_size=(640,640))
    def emb(img):
        faces = app.get(img)
        if not faces: return None
        f = max(faces, key=lambda x: (x.bbox[2]-x.bbox[0])*(x.bbox[3]-x.bbox[1]))
        return f.normed_embedding
    return emb

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True, help="dir with reference images")
    ap.add_argument("--cand", required=True, help="dir with candidate images")
    ap.add_argument("--out", required=True, help="dir for passing images")
    ap.add_argument("--minsim", type=float, default=0.34)
    ap.add_argument("--minblur", type=float, default=80.0)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    emb = embedder()

    refs = []
    for fp in glob.glob(os.path.join(args.ref, "*.*")):
        img = load(fp)
        if img is None: continue
        e = emb(img)
        if e is not None: refs.append(e)
    if not refs:
        raise RuntimeError("No face embeddings in --ref")
    ref_centroid = np.mean(np.stack(refs), axis=0)

    report = [["filename","cos_sim","blur","pass"]]
    def cos(a,b): return float(np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b) + 1e-8))

    for fp in glob.glob(os.path.join(args.cand, "*.*")):
        img = load(fp)
        if img is None: continue
        e = emb(img)
        bs = blur_score(img)
        ok = False
        cs = -1.0
        if e is not None:
            cs = cos(e, ref_centroid)
            ok = (cs >= args.minsim) and (bs >= args.minblur)
        if ok:
            outp = os.path.join(args.out, os.path.basename(fp))
            cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])[1].tofile(outp)
        report.append([os.path.basename(fp), f"{cs:.4f}", f"{bs:.1f}", "1" if ok else "0"])

    with open(os.path.join(args.out, "qc_report.csv"), "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(report)
    print(f"[DONE] QC complete. Passed: {sum(1 for r in report[1:] if r[3]=='1')} / {len(report)-1}")

if __name__ == "__main__":
    main()
