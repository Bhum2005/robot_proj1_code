"""วัดผลทั้งสาย: ทุกเฟรม -> reader.read (เหมือนบนหุ่น) -> เทียบกับป้ายของมิเตอร์ที่อยู่ตรงนั้น
argv: pi_dir strips_dir frames_dir clips(comma) [model.onnx] [orig]
orig = ใช้ find_strip เดิมของ robot-update (กระดาษขาวอย่างเดียว ไม่มีของเราเสริม)"""
import sys, json, glob, os, collections, cv2, numpy as np
sys.path.insert(0, sys.argv[1])
from meter_ai.reader import MeterReader
from meter_ai import pipeline
S, F, clips = sys.argv[2], sys.argv[3], sys.argv[4].split(",")
R = MeterReader(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] != "-" else MeterReader()
if len(sys.argv) > 6 and sys.argv[6] == "orig":
    import meter_ai.reader as RD
    RD.find_strips = lambda fr: [s for s in [pipeline.find_strip(fr)] if s is not None]
rows = json.load(open(os.path.join(S, "rows.json")))
G = collections.defaultdict(list)
for r in rows: G[(r["clip"], r["frame"], r["t"])].append(r)
lab = collections.defaultdict(list)          # (clip,frame) -> [(cx,cy,label)]
for k, v in G.items():
    b = max(v, key=lambda r: r["margin"])
    if b["margin"] >= 4 and max(r["sharp"] for r in v) >= 10:
        lab[k[:2]].append((b["cx"], b["cy"], b["best"]))
st = collections.Counter(); bad = []
for c in clips:
    for fp in sorted(glob.glob(f"{F}/{c}/f_*.jpg")):
        key = (c, os.path.basename(fp)); rd = R.read(cv2.imread(fp))
        L = lab.get(key, [])
        st["frames"] += 1; st["frames_with_label"] += bool(L)
        if rd.strip is None or rd.confidence < 0.6:
            st["no_suggest_" + ("labeled" if L else "unlabeled")] += 1; continue
        cx, cy = rd.strip.quad[:, 0].mean(), rd.strip.quad[:, 1].mean()
        near = min(L, key=lambda t: (t[0]-cx)**2 + (t[1]-cy)**2) if L else None
        if near and ((near[0]-cx)**2 + (near[1]-cy)**2) ** .5 < 80:
            ok = rd.digits == near[2]; st["suggest_ok" if ok else "suggest_WRONG"] += 1
            if not ok: bad.append((key, rd.digits, near[2], round(rd.confidence, 2)))
        else:
            st["suggest_unverifiable"] += 1; bad.append((key, rd.digits, "?", round(rd.confidence, 2)))
print(dict(st))
for b in bad[:15]: print("  ", b)
