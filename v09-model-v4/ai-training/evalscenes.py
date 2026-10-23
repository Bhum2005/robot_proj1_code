"""วัดผลทั้งสายบนฉากทดสอบ (gen_scenes.py): หาแถบ + อ่านเลข + บอกน้ำ/ไฟ  แยกตามสีตัวเรือน
  python3 evalscenes.py ../tests/meter/scenes.npz [model.onnx]"""
import sys, os, collections, cv2, numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pi"))
from meter_ai.reader import MeterReader
d = np.load(sys.argv[1], allow_pickle=True)
R = MeterReader(sys.argv[2]) if len(sys.argv) > 2 else MeterReader()
st = collections.defaultdict(collections.Counter)
for x, lab, kind, desc in zip(d["X"], d["L"], d["K"], d["D"]):
    img = cv2.imdecode(np.frombuffer(x, np.uint8), 1)
    for rot in (None, cv2.ROTATE_180):
        im = img if rot is None else cv2.rotate(img, rot)
        r = R.read(im); c = st[desc.split("/")[1]]; a = st["รวม"]
        for s in (c, a):
            s["n"] += 1
            s["found"] += r.strip is not None
            s["ok"] += r.digits == lab
            s["s75"] += r.confidence >= .75; s["w75"] += r.confidence >= .75 and r.digits != lab
            s["s60"] += r.confidence >= .6; s["w60"] += r.confidence >= .6 and r.digits != lab
            s["k75"] += r.kconf >= .75; s["kw"] += r.kconf >= .75 and r.kind != kind
print(f"{'สีตัวเรือน':10s} {'หาแถบเจอ':>8s} {'อ่านถูก':>7s} {'>=75% ใส่ให้':>11s} {'ผิด':>4s} {'>=60%':>6s} {'ผิด':>4s} {'บอกน้ำไฟ':>8s} {'ผิด':>4s}")
for k in list(st):
    s = st[k]; n = s["n"]
    print(f"{k:10s} {s['found']/n:8.0%} {s['ok']/n:7.0%} {s['s75']/n:11.0%} {s['w75']:4d} {s['s60']/n:6.0%} {s['w60']:4d} {s['k75']/n:8.0%} {s['kw']:4d}")
