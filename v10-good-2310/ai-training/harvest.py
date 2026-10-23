"""ทุกเฟรม -> ทุกมิเตอร์ในเฟรม -> แถบเลข (หลายแบบ) + ป้ายเฉลยจากชุดเลขที่รู้ (6 ตัว)

ป้ายเฉลย: ให้โมเดลเดิมให้คะแนนรายหลัก แล้วเลือก "เลขในชุดที่รู้" ที่ได้คะแนนสูงสุด
(ถอดรหัสแบบมีข้อจำกัด) รับเฉพาะเมื่อชนะอันดับสองขาดลอย — ตรวจด้วยตาอีกรอบทีหลัง
"""
import sys, os, glob, json, cv2, numpy as np
sys.path.insert(0, sys.argv[1])                     # .../work/pi
from meter_ai.locate import blue_mask, _score, _near, MIN_AREA_FRAC, MERGE_MARGIN, Target
from meter_ai.pipeline import _work
from meter_ai.strip import MODES, strip_quad, warp_strip
from meter_ai.preprocess import preprocess, paper_to_white
from meter_ai.reader import MeterReader
KNOWN = ["7527", "2045", "8785", "5977", "6201", "2664"]
OUT = sys.argv[3]; os.makedirs(OUT, exist_ok=True)
R = MeterReader()

def probs(img):
    R._net.setInput(preprocess(img)); lg = R._net.forward().reshape(4, 10)
    p = np.exp(lg - lg.max(1, keepdims=True)); return p / p.sum(1, keepdims=True)

def targets(work):
    h, w = work.shape[:2]
    cs, _ = cv2.findContours(blue_mask(work), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cand = sorted([c for c in cs if cv2.contourArea(c) >= MIN_AREA_FRAC * w * h],
                  key=lambda c: -_score(c, w, h))
    used = np.zeros((h, w), np.uint8); out = []
    for best in cand:
        x, y, bw, bh = cv2.boundingRect(best)
        if used[y + bh // 2, x + bw // 2]:
            continue
        pieces = [best] + [c for c in cs if c is not best and _near(best, c, MERGE_MARGIN)]
        hull = cv2.convexHull(np.vstack(pieces)); m = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(m, hull, 255); used |= m
        out.append(Target(contour=hull, bbox=cv2.boundingRect(hull), mask=m))
    return out

rows = []
for fp in sorted(glob.glob(sys.argv[2] + "/c*/f_*.jpg")):
    clip = fp.split("/")[-2]; fr = cv2.imread(fp); work, sc = _work(fr)
    for ti, t in enumerate(targets(work)):
        for mode in MODES:
            f = strip_quad(work, t, mode)
            if f is None: continue
            q, up = f; qf = ((q + 0.5) / sc - 0.5).astype(np.float32)
            raw = warp_strip(fr, qf)
            for view, img in (("raw", raw), ("p2w", paper_to_white(raw))):
                if mode == "white" and view == "p2w": continue
                p = probs(img)
                free = "".join(str(d) for d in p.argmax(1)); fconf = float(p.max(1).prod())
                lp = np.log(p + 1e-9)
                sc_k = sorted(((sum(lp[i, int(k[i])] for i in range(4)), k) for k in KNOWN), reverse=True)
                rows.append(dict(clip=clip, frame=os.path.basename(fp), t=ti, mode=mode, view=view,
                                 up=up, free=free, conf=round(fconf, 4), best=sc_k[0][1],
                                 margin=round(float(sc_k[0][0] - sc_k[1][0]), 2),
                                 cx=float(qf[:, 0].mean()), cy=float(qf[:, 1].mean())))
                name = f"{clip}_{os.path.basename(fp)[:-4]}_t{ti}_{mode}_{view}.png"
                cv2.imwrite(os.path.join(OUT, name), img); rows[-1]["img"] = name
json.dump(rows, open(os.path.join(OUT, "rows.json"), "w"))
print(len(rows), "strips")
