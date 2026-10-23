"""ฉากทดสอบทั้งสาย: รูปมิเตอร์จริง 2 แบบ (น้ำทรงกระบอก 2045 / ไฟกล่องติดผนัง 6201)
เปลี่ยน "สีตัวเรือน" + แปะแถบเลขใหม่ (เลขสุ่ม สีกระดาษ/สีตัวเลขสุ่ม ฟอนต์ฝั่งสอบที่ไม่ได้ใช้เทรน)
ลงตำแหน่งแถบเดิมตามมุมมองจริง  -> ใช้วัดว่า AI หาเจอ/อ่านถูก/บอกน้ำไฟถูกไหม เมื่อมิเตอร์เปลี่ยนหน้าตา

  python3 gen_scenes.py ../tests/meter/scenes.npz [ฉากต่อสี]
"""
import sys, os, random, cv2, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "..", "pi"))
import data, fonts
from meter_ai.pipeline import find_strip
from meter_ai.locate import find_target
from meter_ai.pipeline import _work

SRC = [("meter_2045.png", "water"), ("meter_box_6201.jpg", "power")]
BODY = {  # ชื่อ: hue ของ OpenCV (None = ไม่เปลี่ยน) , ความอิ่มสี
    "blue": (None, 1.0), "red": (176, 1.0), "green": (60, 0.9), "yellow": (27, 1.0),
    "purple": (145, 0.9), "orange": (12, 1.0), "cyan": (92, 1.0),
}


def recolor_body(img, hue, sat):
    """เปลี่ยนสีพิกเซลน้ำเงินของตัวเรือนเป็นสีใหม่ เก็บความสว่าง/เงาเดิม"""
    if hue is None:
        return img
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, (92, 50, 20), (138, 255, 255)) > 0
    h = hsv[..., 0].astype(np.int16); s = hsv[..., 1].astype(np.float32)
    h[m] = hue; s[m] = np.clip(s[m] * sat, 0, 255)
    if hue in (27, 12):                       # เหลือง/ส้มเข้มจะดูเป็นน้ำตาล ยกความสว่างขึ้นหน่อย
        v = hsv[..., 2].astype(np.float32); v[m] = np.clip(v[m] * 1.35 + 30, 0, 255); hsv[..., 2] = v
    hsv[..., 0] = h; hsv[..., 1] = s
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def paste_strip(img, quad, strip):
    """แปะภาพแถบ (ตั้งตรง) ลงกรอบ quad (tl,tr,br,bl) ในภาพตามมุมมอง"""
    h, w = strip.shape[:2]
    src = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    M = cv2.getPerspectiveTransform(src, quad.astype(np.float32))
    warped = cv2.warpPerspective(strip, M, (img.shape[1], img.shape[0]), flags=cv2.INTER_AREA)
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), M, (img.shape[1], img.shape[0]))
    mask = cv2.erode(mask, np.ones((3, 3), np.uint8))
    out = img.copy(); out[mask > 0] = warped[mask > 0]
    return out


def main(out, per):
    random.seed(77); np.random.seed(77)
    _, ev = fonts.split()
    X, L, K, D = [], [], [], []
    for fn, kind in SRC:
        base = cv2.imread(os.path.join(HERE, "..", "tests", "meter", fn))
        s = find_strip(base)
        for body_name, (hue, sat) in BODY.items():
            img_b = recolor_body(base, hue, sat)
            # สีตัวเรือนในแถบที่วาด = สีเฉลี่ยของตัวเรือนที่เปลี่ยนแล้ว (ขอบแถบจะได้กลืน)
            work, sc = _work(base); t = find_target(work)
            m = cv2.resize(t.mask, (base.shape[1], base.shape[0])) > 0
            hsv0 = cv2.cvtColor(base, cv2.COLOR_BGR2HSV)
            bm = m & (cv2.inRange(hsv0, (92, 50, 20), (138, 255, 255)) > 0)
            body_col = tuple(int(c) for c in np.median(img_b[bm], axis=0))
            for i in range(per):
                lab = "".join(random.choice("0123456789") for _ in range(4))
                while True:
                    paper, ink = data._rand_col(random), data._rand_col(random)
                    if (np.linalg.norm(data._lab(paper) - data._lab(ink)) >= 55
                            and np.linalg.norm(data._lab(paper) - data._lab(body_col)) >= 35):
                        break
                strip = data.render_color(lab, ev, colors=(body_col, paper, ink), out_scale=4, warp=False)
                img = paste_strip(img_b, s.quad, strip)
                X.append(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes())
                L.append(lab); K.append(kind); D.append(f"{kind}/{body_name}")
    np.savez_compressed(out, X=np.array(X, dtype=object), L=np.array(L), K=np.array(K), D=np.array(D))
    print("ok", out, len(X))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 6)
