"""ทดสอบ AI อ่านเลขมิเตอร์ (pi/meter_ai) — รันในเครื่องได้ ต้องมี opencv + numpy

1. รูปจริงของ robot-update (2045) ต้องอ่านถูก ทั้ง 4 ทิศ
2. รูปเดียวกันที่เปลี่ยนสีกระดาษ/ตัวเลข 12 แบบ x 4 ทิศ: แนะนำถูก >= 42/48 และ "ไม่มีเลขแนะนำผิด"
   (โมเดลรุ่นเดิม 46/48 — รุ่นใหม่ระวังตัวกว่ากับกระดาษสี แลกกับไม่เดาภาพเบลอ ดูข้อ 4)
3. ภาพที่ไม่ควรได้เลข (กระดาษเปล่า/ไม่มีแถบ/เบลอ/ไม่มีมิเตอร์/สัญญาณรบกวน): ห้ามมีเลขแนะนำ
4. แถบเลขจริงจากคลิป 4 ของผู้ใช้ (ไม่ได้ใช้เทรน) — tests/meter/evalsets_c4.npz
   A อ่านออก 951 แถบ: ถูก >= 95% แนะนำผิด 0 / C เบลอจนอ่านไม่ออก 248 แถบ: ห้ามแนะนำ
"""
import os, subprocess, sys, tempfile
import cv2, numpy as np
S = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(S)
sys.path.insert(0, os.path.join(ROOT, "pi"))
from meter_ai import SUGGEST_THRESHOLD, read_meter  # noqa: E402
ok = fail = 0
def check(label, cond, extra=""):
    global ok, fail
    ok += bool(cond); fail += not cond
    print(("  ok   " if cond else "  FAIL ") + label + ("" if cond else f"   {extra}"))
ROT = [None, cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE]
rots = lambda im: [im if k is None else cv2.rotate(im, k) for k in ROT]
src_path = os.path.join(S, "meter", "meter_2045.png"); src = cv2.imread(src_path)

print("1. รูปจริง")
res = [read_meter(x)[:2] for x in rots(src)]
check("อ่าน 2045 ได้ทั้ง 4 ทิศ (ผ่านเกณฑ์แนะนำ)", all(d == "2045" for d, _ in res), res)

print("1.1 น้ำหรือไฟ (ดูจากรูปทรง)")
from meter_ai.reader import MeterReader as _MR  # noqa: E402
_rd = _MR()
box = cv2.imread(os.path.join(S, "meter", "meter_box_6201.jpg"))
r1, r2 = _rd.read(src), _rd.read(box)
check("ทรงกระบอก 2045 = มิเตอร์น้ำ มั่นใจ >= 0.75", r1.kind == "water" and r1.kconf >= 0.75, (r1.kind, r1.kconf))
check("กล่องติดผนัง 6201 = มิเตอร์ไฟ มั่นใจ >= 0.75 และอ่านเลขถูก",
      r2.kind == "power" and r2.kconf >= 0.75 and r2.digits == "6201", (r2.kind, r2.kconf, r2.digits))

print("1.2 รูปจริงจากหุ่น 16 ต.ค. (ถ่ายภาพมิเตอร์แบบใหม่บนจอมือถือ): ตัวเรือนเขียวเข้ม / น้ำเงินที่ติดขอบเคสน้ำเงิน")
for fn in ("meter_disc_green_6834.jpg", "meter_disc_blue_6834.jpg",
           "meter_green_redpaper_6834.jpg", "meter_green_white_6834.jpg",
           "meter_phone_green_red_6834.jpg", "meter_phone_green_white_3cells_6834.jpg"):
    r = _rd.read(cv2.imread(os.path.join(S, "meter", fn)))
    check(f"{fn}: อ่าน 6834 มั่นใจ >= 0.75", r.digits == "6834" and r.confidence >= .75, (r.digits, r.confidence))

print("2. กระดาษ/ตัวเลขสีอื่น")
tmp = tempfile.mkdtemp()
subprocess.run([sys.executable, os.path.join(S, "meter", "gen_colours.py"), os.path.join(ROOT, "pi"),
                src_path, tmp], check=True, capture_output=True)
right = wrong = n = 0
for f in sorted(os.listdir(tmp)):
    for x in rots(cv2.imread(os.path.join(tmp, f))):
        d, c, _ = read_meter(x); n += 1
        right += d == "2045"; wrong += d is not None and d != "2045"
print(f"     แนะนำถูก {right}/{n}  แนะนำผิด {wrong}")
check("แนะนำถูก >= 42/48", right >= 42, right)
check("ไม่มีเลขแนะนำผิด", wrong == 0, wrong)

print("3. ภาพที่ไม่ควรได้เลข")
hsv = cv2.cvtColor(src, cv2.COLOR_BGR2HSV)
paper = np.abs(cv2.imread(os.path.join(tmp, "yellow_black.png")).astype(np.int16)
               - src.astype(np.int16)).sum(axis=2) > 0
negs = {}
for col in ((240, 240, 240), (80, 228, 255), (30, 30, 200), (25, 25, 25)):
    im = src.copy(); im[paper] = col; negs[f"กระดาษเปล่า {col}"] = im
nb = src.copy(); nb[paper] = (160, 50, 10); negs["ไม่มีแถบเลข"] = nb
negs["เบลอหนัก"] = cv2.GaussianBlur(src, (0, 0), 6)
negs["ไม่มีมิเตอร์"] = cv2.resize(src[0:150, 400:640], (640, 480))
negs["สัญญาณรบกวน"] = np.random.default_rng(1).integers(0, 255, src.shape, dtype=np.uint8)
for k, im in negs.items():
    out = [read_meter(x)[0] for x in rots(im)]
    check(f"{k}: ไม่มีเลขแนะนำ", all(d is None for d in out), out)
print("4. แถบเลขจริงจากคลิป (ไม่ได้ใช้เทรน)")
from meter_ai.reader import MeterReader  # noqa: E402
from meter_ai.preprocess import preprocess  # noqa: E402
net = MeterReader()._net
E = np.load(os.path.join(S, "meter", "evalsets_c4.npz"))
def infer(g):
    net.setInput(preprocess(cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)))
    lg = net.forward().reshape(4, 10); p = np.exp(lg - lg.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
    return "".join(map(str, p.argmax(1))), float(p.max(1).prod())
outA = [infer(g) for g in E["A"]]
accA = sum(d == l for (d, _), l in zip(outA, E["Al"])) / len(outA)
badA = sum(c >= SUGGEST_THRESHOLD and d != l for (d, c), l in zip(outA, E["Al"]))
print(f"     A: ถูก {accA:.1%}  แนะนำผิด {badA}")
check("แถบชัด: อ่านถูก >= 95%", accA >= 0.95, accA)
check("แถบชัด: ไม่มีเลขแนะนำผิด", badA == 0, badA)
sugC = sum(infer(g)[1] >= SUGGEST_THRESHOLD for g in E["C"])
check(f"แถบเบลอ {len(E['C'])} แถบ: ไม่มีเลขแนะนำ", sugC == 0, sugC)
print("5. ฟอนต์/สีที่ไม่เคยเห็นตอนเทรน (800 แถบ, ฟอนต์ฝั่งสอบ 39 ไฟล์ + 7 ส่วน + ล้อตัวเลข)")
from meter_ai.preprocess import paper_to_white  # noqa: E402
F = np.load(os.path.join(S, "meter", "evalfonts.npz"))
fo = fw = fs = 0
for img, lab in zip(F["X"], F["L"]):
    best = max((infer(cv2.cvtColor(v, cv2.COLOR_BGR2GRAY)) for v in (img, paper_to_white(img))), key=lambda r: r[1])
    fo += best[0] == lab; fs += best[1] >= .75; fw += best[1] >= .75 and best[0] != lab
print(f"     อ่านถูก {fo/len(F['L']):.1%}  ใส่ให้อัตโนมัติ {fs/len(F['L']):.1%}  ใส่ผิด {fw}")
check("ฟอนต์ใหม่: อ่านถูก >= 90%", fo / len(F["L"]) >= .9, fo)
check("ฟอนต์ใหม่: มั่นใจ >= 75% แล้วไม่มีผิด", fw == 0, fw)

print("6. ฉากเปลี่ยนสีตัวเรือน 7 สี x น้ำ/ไฟ + แถบเลขสี/ฟอนต์ใหม่ (84 ฉาก x 2 ทิศ)")
D = np.load(os.path.join(S, "meter", "scenes.npz"), allow_pickle=True)
so = sw = ss = kw = kn = 0
for x, lab, kind in zip(D["X"], D["L"], D["K"]):
    im0 = cv2.imdecode(np.frombuffer(x, np.uint8), 1)
    for im in (im0, cv2.rotate(im0, cv2.ROTATE_180)):
        r = _rd.read(im)
        so += r.digits == lab; ss += r.confidence >= .75; sw += r.confidence >= .75 and r.digits != lab
        kn += r.kconf >= .75; kw += r.kconf >= .75 and r.kind != kind
n6 = 2 * len(D["L"])
print(f"     อ่านถูก {so/n6:.0%}  ใส่ให้อัตโนมัติ {ss/n6:.0%} (ผิด {sw})  บอกน้ำ/ไฟ {kn/n6:.0%} (ผิด {kw})")
check("ฉากเปลี่ยนสี: ใส่ให้อัตโนมัติ >= 50%", ss / n6 >= .5, ss)
check("ฉากเปลี่ยนสี: ค่าที่ใส่ให้อัตโนมัติไม่มีผิด", sw == 0, sw)
check("ฉากเปลี่ยนสี: บอกน้ำ/ไฟไม่มีผิด", kw == 0, kw)

print(f"\n{ok} ผ่าน, {fail} ไม่ผ่าน   (เกณฑ์แนะนำ {SUGGEST_THRESHOLD})")
sys.exit(1 if fail else 0)
