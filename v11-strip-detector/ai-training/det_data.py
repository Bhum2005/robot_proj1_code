"""ข้อมูลเทรน "ตัวหาแถบเลข" (detector) — ฉากจำลองที่สุ่มทุกอย่าง + เฟรมจริงจากคลิป

ฉากจำลอง: พื้นหลังจากเฟรมจริง (ตัดส่วนที่ไม่มีมิเตอร์) หรือพื้นสุ่ม
  -> ตัวมิเตอร์สุ่มทรง (แผ่นกลม / ทรงกระบอก / กล่อง) สีสุ่ม มีเงา ลายเส้นพิมพ์ 3D แสงสะท้อน
  -> แถบเลข (data.render_color: กระดาษ/ตัวเลขสีสุ่ม ฟอนต์ฝั่งเทรน 7 ส่วน ล้อตัวเลข) หมุนได้ทุกมุม
  -> ป้ายชื่อ "REAI" สีสุ่มข้างแถบ + ของหลอก (สี่เหลี่ยม/ตัวอักษรอื่น)
  -> เบลอ สัญญาณรบกวน ลายจอ (ถ่ายผ่านจอมือถือ) JPEG
เป้าหมาย 2 ช่องที่ความละเอียด 1/2: [0] พื้นที่กระดาษแถบเลข  [1] พื้นที่ป้ายชื่อ (ใช้บอกทิศ)
"""
import glob, math, os, random, sys
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import data, fonts

IW, IH = 320, 240          # อินพุตของ detector (4:3)
OS = 2                     # เอาต์พุตย่อ 1/2 -> 160x120


def _rand_bgr(rng, sat_min=0):
    h = rng.randint(0, 179); s = rng.randint(sat_min, 255); v = rng.randint(30, 255)
    return tuple(int(c) for c in cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)[0, 0])


def background(rng, frames):
    if frames and rng.random() < 0.7:
        fr = cv2.imread(rng.choice(frames))
        if fr is not None:
            h, w = fr.shape[:2]
            cw = rng.randint(int(w * 0.25), int(w * 0.6)); ch = int(cw * IH / IW)
            ch = min(ch, h - 1)
            x, y = rng.randint(0, w - cw), rng.randint(0, h - ch)
            return cv2.resize(fr[y:y + ch, x:x + cw], (IW, IH), interpolation=cv2.INTER_AREA)
    c1, c2 = np.array(_rand_bgr(rng)), np.array(_rand_bgr(rng))
    t = np.linspace(0, 1, IW)[None, :, None] if rng.random() < .5 else np.linspace(0, 1, IH)[:, None, None]
    bg = (c1 * (1 - t) + c2 * t) * np.ones((IH, IW, 1))
    return np.clip(bg + np.random.normal(0, rng.uniform(2, 12), bg.shape), 0, 255).astype(np.uint8)


def shade(img, mask, col, rng):
    """ระบายตัวมิเตอร์: สีพื้น + ไล่แสง + ลายเส้นพิมพ์ 3D + จุดสะท้อน"""
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = rng.uniform(0, 2 * math.pi)
    g = (np.cos(a) * xx + np.sin(a) * yy); g = (g - g.min()) / max(float(np.ptp(g)), 1)
    f = rng.uniform(0.6, 1.0) + rng.uniform(0, 0.5) * g
    if rng.random() < .6:                                           # ลายเส้นพิมพ์ 3D
        b = rng.uniform(0, math.pi); per = rng.uniform(2, 5)
        f = f * (1 + rng.uniform(.03, .1) * np.sin((np.cos(b) * xx + np.sin(b) * yy) * 2 * math.pi / per))
    body = np.clip(np.array(col, np.float32)[None, None] * f[..., None], 0, 255)
    if rng.random() < .5:                                           # แสงสะท้อน
        cx, cy = rng.randint(0, w), rng.randint(0, h); r = rng.uniform(8, 50)
        d = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r))[..., None]
        body = body * (1 - d * .7) + 255 * d * .7
    img[mask > 0] = body[mask > 0].astype(np.uint8)


def meter_body(rng):
    """มาสก์ตัวมิเตอร์ (ทรงสุ่ม) + ขอบเขตหน้าที่ติดแถบ (สำหรับวางแถบ)"""
    m = np.zeros((IH, IW), np.uint8)
    cx, cy = rng.uniform(.25, .75) * IW, rng.uniform(.25, .75) * IH
    size = rng.uniform(60, 200)
    kind = rng.choice(["disc", "cyl", "box", "box"])
    if kind == "disc":
        ax = (size / 2, size / 2 * rng.uniform(.6, 1.0)); ang = rng.uniform(0, 180)
        cv2.ellipse(m, ((cx, cy), (ax[0] * 2, ax[1] * 2), ang), 255, -1)
        face = (cx, cy, size * .8, ang)
    elif kind == "cyl":
        rx, ry = size / 2, size / 2 * rng.uniform(.35, .7); hh = size * rng.uniform(.4, .9)
        cv2.ellipse(m, ((cx, cy + hh), (rx * 2, ry * 2), 0), 255, -1)
        cv2.rectangle(m, (int(cx - rx), int(cy)), (int(cx + rx), int(cy + hh)), 255, -1)
        cv2.ellipse(m, ((cx, cy), (rx * 2, ry * 2), 0), 255, -1)
        face = (cx, cy, size * .85, rng.uniform(-30, 30))
    else:
        w, h = size, size * rng.uniform(.7, 1.3); ang = rng.uniform(-25, 25)
        box = cv2.boxPoints(((cx, cy), (w, h), ang))
        box = box + np.random.uniform(-.06, .06, box.shape) * size
        cv2.fillConvexPoly(m, box.astype(np.int32), 255)
        face = (cx, cy, w * .85, ang)
    return m, face


def put_text(img, text, centre, height, angle, col, font):
    """วาดข้อความหมุนได้ลงภาพ คืนมาสก์ของข้อความ"""
    f = ImageFont.truetype(font, max(8, int(height * 2)))
    tw = f.getbbox(text)[2] + 10; th = int(height * 3)
    pi = Image.new("L", (tw, th), 0); ImageDraw.Draw(pi).text((5, th // 2), text, fill=255, font=f, anchor="lm")
    a = np.array(pi)
    M = cv2.getRotationMatrix2D((tw / 2, th / 2), angle, 1.0)
    M[0, 2] += centre[0] - tw / 2; M[1, 2] += centre[1] - th / 2
    m = cv2.warpAffine(a, M, (IW, IH))
    img[m > 100] = col
    return (m > 100).astype(np.uint8) * 255


def scene(rng, frames, train_fonts):
    img = background(rng, frames)
    tgt = np.zeros((2, IH // OS, IW // OS), np.uint8)
    if rng.random() < 0.08:                                         # ภาพไม่มีมิเตอร์เลย
        return finish(img, rng), tgt
    body, (fx, fy, fw, fang) = meter_body(rng)
    bcol = _rand_bgr(rng, sat_min=rng.choice([0, 60, 120]))
    shade(img, body, bcol, rng)
    # แถบเลข
    lab = "".join(rng.choice("0123456789") for _ in range(4))
    while True:
        paper, ink = data._rand_col(rng), data._rand_col(rng)
        if np.linalg.norm(data._lab(paper) - data._lab(ink)) >= 45:
            break
    st = data.render_color(lab, train_fonts, rng, colors=(bcol, paper, ink), out_scale=4, warp=False)
    L = fw * rng.uniform(.55, .95); Hs = L / rng.uniform(3.6, 4.8)
    ang = fang + rng.choice([0, 0, 90, 180, rng.uniform(-180, 180)])
    up = np.array([math.sin(math.radians(ang)), -math.cos(math.radians(ang))])
    sx, sy = fx + rng.uniform(-.1, .1) * fw, fy + rng.uniform(-.1, .1) * fw
    full = cv2.boxPoints(((sx, sy), (L * 1.24, Hs / .84), ang))     # กรอบแถบแบบเดียวกับ warp_strip
    # เรียงมุม tl tr br bl ตามทิศของแถบ
    c = full.mean(0); right = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
    q = sorted(full, key=lambda p: ((p - c) @ up < 0, (p - c) @ right))
    tl, tr = sorted(q[:2], key=lambda p: (p - c) @ right); bl, br = sorted(q[2:], key=lambda p: (p - c) @ right)
    quad = np.float32([tl, tr, br, bl]) + np.random.uniform(-.04, .04, (4, 2)).astype(np.float32) * L
    sh, sw = st.shape[:2]
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [sw, 0], [sw, sh], [0, sh]]), quad)
    warped = cv2.warpPerspective(st, M, (IW, IH), flags=cv2.INTER_AREA)
    wm = cv2.warpPerspective(np.full((sh, sw), 255, np.uint8), M, (IW, IH))
    img[wm > 0] = warped[wm > 0]
    # เป้าหมาย: เฉพาะส่วนกระดาษ (ไม่รวมขอบตัวเรือนที่ติดมากับภาพแถบ)
    X0 = data.X0 * 4 / (data.W * 4); paper_q = np.float32([[X0 * sw, .08 * sh], [(1 - X0) * sw, .08 * sh],
                                                           [(1 - X0) * sw, .92 * sh], [X0 * sw, .92 * sh]])
    pq = cv2.perspectiveTransform(paper_q[None], M)[0]
    pm = np.zeros((IH, IW), np.uint8); cv2.fillConvexPoly(pm, pq.astype(np.int32), 255)
    # ป้ายชื่อข้างแถบ ("REAI" สีสุ่ม) ด้านบนของแถบ
    lm = np.zeros((IH, IW), np.uint8)
    if rng.random() < .85:
        lc = (sx, sy) + up * Hs * rng.uniform(1.0, 1.6)
        lcol = _rand_bgr(rng) if rng.random() < .6 else rng.choice([(250, 250, 250), (40, 90, 240)])
        lm = put_text(img, rng.choice(["REAI", "REAI", "MTR", "WATER", "PEA"]), lc, Hs * rng.uniform(.4, .7),
                      -ang, lcol, rng.choice(train_fonts))
    # ของหลอก: สี่เหลี่ยมสี/ตัวอักษรที่อื่น
    for _ in range(rng.randint(0, 2)):
        p = (rng.uniform(0, IW), rng.uniform(0, IH))
        if rng.random() < .5:
            put_text(img, "".join(rng.choice("ABCDEFGHKLMNPRSTUVXYZ") for _ in range(rng.randint(2, 6))),
                     p, rng.uniform(4, 12), rng.uniform(-90, 90), _rand_bgr(rng), rng.choice(train_fonts))
        else:
            cv2.rectangle(img, (int(p[0]), int(p[1])), (int(p[0] + rng.uniform(10, 60)), int(p[1] + rng.uniform(5, 20))),
                          _rand_bgr(rng), -1)
    tgt[0] = cv2.resize(pm, (IW // OS, IH // OS), interpolation=cv2.INTER_AREA) > 127
    tgt[1] = cv2.resize(lm, (IW // OS, IH // OS), interpolation=cv2.INTER_AREA) > 60
    return finish(img, rng), tgt


def finish(img, rng):
    img = img.astype(np.float32)
    if rng.random() < .3:                                           # ถ่ายผ่านจอมือถือ: ลายจอ + สีเพี้ยน
        yy, xx = np.mgrid[0:IH, 0:IW]
        img *= (1 + .06 * np.sin((xx * rng.uniform(.5, 1.5) + yy * rng.uniform(.5, 1.5)) * rng.uniform(1, 2.5)))[..., None]
        img = img * np.array([rng.uniform(.8, 1.1), rng.uniform(.8, 1.1), rng.uniform(.9, 1.2)])
    img = img * rng.uniform(.5, 1.3) + rng.uniform(-30, 30)
    if rng.random() < .5:
        img = cv2.GaussianBlur(img, (0, 0), rng.uniform(.3, 1.5))
    img = img + np.random.normal(0, rng.uniform(0, 8), img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)
    return cv2.imdecode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(40, 92)])[1], 1)


def letterbox(frame):
    """ภาพขนาดใดก็ได้ -> 320x240 (เติมขอบดำ ไม่บิดสัดส่วน) + ค่าแปลงกลับ"""
    h, w = frame.shape[:2]
    s = min(IW / w, IH / h)
    nw, nh = int(round(w * s)), int(round(h * s))
    out = np.zeros((IH, IW, 3), np.uint8)
    x0, y0 = (IW - nw) // 2, (IH - nh) // 2
    out[y0:y0 + nh, x0:x0 + nw] = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    return out, s, x0, y0


if __name__ == "__main__":
    # สร้างชุดข้อมูลลงไฟล์: python3 det_data.py <frames_glob> <out.npz> <n> <seed>
    frames = glob.glob(sys.argv[1]); out, n, seed = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    rng = random.Random(seed); np.random.seed(seed)
    tr, _ = fonts.split()
    X = np.zeros((n, IH, IW, 3), np.uint8); Y = np.zeros((n, 2, IH // OS, IW // OS), np.uint8)
    for i in range(n):
        X[i], Y[i] = scene(rng, frames, tr)
    np.savez_compressed(out, X=X, Y=Y)
    print("ok", out, n)
