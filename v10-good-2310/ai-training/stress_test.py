"""ทดสอบหนัก: มิเตอร์ "สีอื่น ฟอนต์อื่น" ที่ AI ไม่เคยเห็น
ฐานเป็นรูปจริง 3 แบบ (ทรงกระบอกน้ำเงิน / กล่องไฟน้ำเงิน / แผ่นกลมเขียวเข้มของจริง)
-> เปลี่ยนสีตัวเรือน 8 สี + แปะแถบเลขใหม่ (เลขสุ่ม, ฟอนต์ฝั่งสอบที่ไม่ได้ใช้เทรน หรือ 7 ส่วน,
   กระดาษ/ตัวเลขสีสุ่ม หรือแบบ "ช่องสี เลขขาว") ลงตำแหน่งแถบเดิมตามมุมมองจริง
  python3 stress_test.py <outdir> [ฉากต่อชุด] [seed]
ได้: ตารางผลแยกตามสีตัวเรือน / แบบตัวเลข / แบบกระดาษ + ภาพตัวอย่าง"""
import sys, os, random, collections, cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "pi"))
import data, fonts
from meter_ai.reader import MeterReader
from meter_ai.pipeline import find_strips
from gen_scenes import paste_strip

BASES = [("meter_2045.png", "water", (92, 138)), ("meter_box_6201.jpg", "power", (92, 138)),
         ("meter_green_white_6834.jpg", "water", (70, 100))]          # (ชื่อ, ชนิด, ช่วง hue ของตัวเรือนเดิม)
BODY = {"น้ำเงิน": None, "แดง": 176, "ส้ม": 12, "เหลือง": 27, "เขียว": 60, "เขียวเข้ม": 75,
        "ฟ้า": 92, "ม่วง": 145}
OUT, PER, SEED = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3, int(sys.argv[3]) if len(sys.argv) > 3 else 2026


def recolor(img, hue_rng, hue, dark):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (hue_rng[0], 35, 15), (hue_rng[1], 255, 255)) > 0
    if hue is None:
        return img, m
    h = hsv[..., 0].copy(); s = hsv[..., 1].astype(np.float32); v = hsv[..., 2].astype(np.float32)
    h[m] = hue; s[m] = np.clip(np.maximum(s[m], 120) * (0.6 if dark else 1.0), 0, 255)
    v[m] = np.clip(v[m] * (0.55 if dark else 1.1) + (0 if dark else 20), 0, 255)
    hsv[..., 0] = h; hsv[..., 1] = s.astype(np.uint8); hsv[..., 2] = v.astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), m


def main():
    random.seed(SEED); np.random.seed(SEED)
    _, ev = fonts.split()
    R = MeterReader()
    os.makedirs(OUT, exist_ok=True)
    st = collections.defaultdict(collections.Counter); samples = []
    for fn, kind, hr in BASES:
        base = cv2.imread(os.path.join(HERE, "..", "tests", "meter", fn))
        s0 = max(find_strips(base), key=lambda s: R._infer(s.image)[1])   # แถบเดิมของรูปจริง
        for bname, hue in BODY.items():
            img_b, bm = recolor(base, hr, hue, bname == "เขียวเข้ม")
            body_col = tuple(int(c) for c in np.median(img_b[bm], axis=0))
            for i in range(PER):
                lab = "".join(random.choice("0123456789") for _ in range(4))
                style = random.choice(["กระดาษสี", "ช่องสีเลขขาว", "กระดาษขาว"])
                while True:
                    if style == "กระดาษขาว":
                        paper, ink = (random.randint(225, 255),) * 3, data._rand_col(random)
                    elif style == "ช่องสีเลขขาว":
                        paper = tuple(random.randint(0, 200) for _ in range(3)); ink = (250, 250, 250)
                    else:
                        paper, ink = data._rand_col(random), data._rand_col(random)
                    if (np.linalg.norm(data._lab(paper) - data._lab(ink)) >= 55
                            and np.linalg.norm(data._lab(paper) - data._lab(body_col)) >= 35):
                        break
                strip = data.render_color(lab, ev, colors=(body_col, paper, ink), out_scale=4, warp=False)
                img = paste_strip(img_b, s0.quad, strip)
                img = cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])[1], 1)
                for rot in (None, cv2.ROTATE_180):
                    im = img if rot is None else cv2.rotate(img, rot)
                    r = R.read(im)
                    auto = r.confidence >= .75 and r.digits is not None
                    for key in ("รวม", "ตัวเรือน " + bname, "แบบ " + style, "มิเตอร์ " + kind):
                        c = st[key]; c["n"] += 1; c["ok"] += r.digits == lab
                        c["auto"] += auto; c["wrong"] += auto and r.digits != lab
                        c["kauto"] += r.kconf >= .75; c["kwrong"] += r.kconf >= .75 and r.kind != kind
                    if rot is None and len(samples) < 48 and i == 0:
                        t = cv2.resize(img, (320, round(img.shape[0] * 320 / img.shape[1])))[:240]
                        t = cv2.copyMakeBorder(t, 0, 240 - t.shape[0], 0, 0, cv2.BORDER_CONSTANT)
                        txt = f"{lab} -> {r.digits or '-'} {r.confidence:.2f}"
                        col = (0, 170, 0) if (auto and r.digits == lab) else (0, 0, 255) if auto else (0, 140, 255)
                        cv2.rectangle(t, (0, 208), (320, 240), (255, 255, 255), -1)
                        cv2.putText(t, txt, (6, 232), cv2.FONT_HERSHEY_SIMPLEX, .62, col, 2)
                        samples.append(t)
    rows = [np.hstack(samples[i:i + 6]) for i in range(0, len(samples) - len(samples) % 6, 6)]
    cv2.imwrite(os.path.join(OUT, "samples.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    lines = [f"{'กลุ่ม':18s} {'ภาพ':>4s} {'อ่านถูก':>7s} {'ใส่ให้เอง':>9s} {'ใส่ผิด':>6s} {'บอกน้ำ/ไฟ':>9s} {'ผิด':>4s}"]
    for k in sorted(st, key=lambda k: (k != "รวม", k)):
        c = st[k]; n = c["n"]
        lines.append(f"{k:18s} {n:4d} {c['ok']/n:7.0%} {c['auto']/n:9.0%} {c['wrong']:6d} {c['kauto']/n:9.0%} {c['kwrong']:4d}")
    open(os.path.join(OUT, "result.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
