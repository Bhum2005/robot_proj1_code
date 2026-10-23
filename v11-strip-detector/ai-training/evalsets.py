"""ชุดสอบ 3 แบบ จากคลิป 4 (ที่ไม่ได้ใช้เทรน) — บันทึกเป็น npz
A อ่านออก   : แถบชัดพอที่คนอ่านได้ -> ต้องอ่านถูก
B เลขใหม่   : เอาช่องตัวเลขจริงของคลิป 4 มาสลับเป็นเลขที่ไม่ใช่ 6 ตัวเดิม + แถบวาดที่มีเลข 3
             -> วัดว่าอ่าน "ตัวเลข" ได้จริง ไม่ใช่จำเลขทั้งชุด
C อ่านไม่ออก: แถบเบลอ/เลือน -> ห้ามแนะนำเลข"""
import sys, json, os, random, collections, cv2, numpy as np
sys.path.insert(0, "."); import data
SD = sys.argv[1]; random.seed(3); np.random.seed(3)
KNOWN = {"7527", "2045", "8785", "5977", "6201", "2664"}
rows = json.load(open(os.path.join(SD, "rows.json")))
G = collections.defaultdict(list)
for r in rows:
    if r["clip"] == "c4": G[(r["frame"], r["t"])].append(r)
def ham(a, b): return sum(x != y for x, y in zip(a, b))
A, C = [], []
for k, v in G.items():
    b = max(v, key=lambda r: r["margin"])
    for r in v:
        g = data.gray(cv2.imread(os.path.join(SD, r["img"])))
        if b["margin"] >= 4 and r["sharp"] >= 150 and ham(r["free"], b["best"]) <= 1:
            A.append((g, b["best"]))
        elif r["sharp"] < 40:
            C.append(g)
pool = data.cells_of([(g, l, None) for g, l in A])
B = []
while len(B) < 600:
    lab = "".join(random.choice(sorted(pool)) for _ in range(4))
    if lab in KNOWN: continue
    B.append((data.recompose(random.choice(A)[0], pool, lab), lab))
for _ in range(300):                       # แถบวาด มีเลข 3 แน่ ๆ
    lab = "".join(random.choice("0123456789") for _ in range(4)); lab = lab[:2] + "3" + lab[3]
    B.append((data.augment(data.render(lab)), lab))
np.savez_compressed(sys.argv[2], A=np.stack([g for g, _ in A]), Al=np.array([l for _, l in A]),
                    B=np.stack([g for g, _ in B]), Bl=np.array([l for _, l in B]), C=np.stack(C))
print("A", len(A), "B", len(B), "C", len(C))
