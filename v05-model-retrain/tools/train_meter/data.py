"""ชุดข้อมูลเทรน: แถบเลขจริงจากคลิป + สลับช่องตัวเลขจริง + ตัวเลขวาดจากฟอนต์ + ภาพขยะ (ห้ามมั่นใจ)
ทุกอย่างเป็นภาพเทา 40x160 แบบเดียวกับที่โมเดลเห็นจริง (preprocess ทำเทา+มาตรฐานอีกที)"""
import json, os, glob, random, collections, cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
H, W = 40, 160
X0 = W * 0.12 / 1.24; CW = (W - 2 * X0) / 4          # ตำแหน่งช่องตัวเลขในแถบที่ตัดมา
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/freefont/FreeSans.ttf", "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
         "/usr/share/texmf/fonts/opentype/public/lm/lmsans10-regular.otf",
         "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
FONTS += [f for f in glob.glob("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf")]

def gray(img): return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img

def load_real(sdir, clips):
    rows = json.load(open(os.path.join(sdir, "rows.json")))
    G = collections.defaultdict(list)
    for r in rows:
        if r["clip"] in clips: G[(r["clip"], r["frame"], r["t"])].append(r)
    pos, junk = [], []
    for k, v in G.items():
        b = max(v, key=lambda r: r["margin"])
        ok = b["margin"] >= 4 and max(r["sharp"] for r in v) >= 10
        for r in v:
            g = gray(cv2.imread(os.path.join(sdir, r["img"])))
            if ok and r["margin"] >= 2 and r["sharp"] >= 8:
                pos.append((g, b["best"], r))
            elif r["sharp"] < 6:
                junk.append(g)
    return pos, junk

def cells_of(pos):
    pool = collections.defaultdict(list)
    for g, lab, _ in pos:
        for i, d in enumerate(lab):
            x0, x1 = int(round(X0 + i * CW)), int(round(X0 + (i + 1) * CW))
            pool[d].append(g[:, x0:x1])
    return pool

def recompose(base, pool, digits):
    g = base.copy().astype(np.float32)
    for i, d in enumerate(digits):
        x0, x1 = int(round(X0 + i * CW)), int(round(X0 + (i + 1) * CW))
        c = cv2.resize(random.choice(pool[d]), (x1 - x0, H)).astype(np.float32)
        slot = g[:, x0:x1]
        c = (c - c.mean()) / (c.std() + 1e-3) * (slot.std() + 1e-3) + slot.mean()   # ให้กลืนกับแถบ
        g[:, x0:x1] = c
    return np.clip(g, 0, 255).astype(np.uint8)

def render(digits, rng=random):
    """วาดแถบเลขสังเคราะห์ ขนาด 4 เท่าแล้วย่อ (ให้ขอบนุ่มเหมือนกล้อง)"""
    S = 4; w, h = W * S, H * S
    body = rng.randint(30, 110); paper = rng.randint(150, 255); ink = rng.randint(0, 90)
    if rng.random() < 0.15: paper, ink = ink, paper                         # ตัวเลขขาวบนกระดาษเข้ม
    im = Image.new("L", (w, h), body); dr = ImageDraw.Draw(im)
    py0, py1 = int(h * (0.08 + rng.uniform(-.03, .05))), int(h * (0.92 + rng.uniform(-.05, .03)))
    px0, px1 = int(X0 * S + rng.uniform(-6, 6)), int((W - X0) * S + rng.uniform(-6, 6))
    dr.rectangle([px0 - 8, py0, px1 + 8, py1], fill=paper)
    line = rng.choice([ink, int(paper * 0.6), int(paper * 0.75)]); lw = rng.randint(2, 6)
    if rng.random() < 0.85:
        dr.rectangle([px0, py0 + 6, px1, py1 - 6], outline=line, width=lw)
        for i in range(1, 4):
            x = px0 + (px1 - px0) * i / 4; dr.line([x, py0 + 6, x, py1 - 6], fill=line, width=lw)
    f = ImageFont.truetype(rng.choice(FONTS), rng.randint(int(h * .5), int(h * .72)))
    for i, d in enumerate(digits):
        cx = px0 + (px1 - px0) * (i + .5) / 4 + rng.uniform(-6, 6); cy = (py0 + py1) / 2 + rng.uniform(-6, 6)
        dr.text((cx, cy), d, fill=ink, font=f, anchor="mm")
    g = np.array(im)
    pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    jit = pts + np.float32(np.random.uniform(-w * .03, w * .03, (4, 2)))
    g = cv2.warpPerspective(g, cv2.getPerspectiveTransform(pts, jit), (w, h), borderMode=cv2.BORDER_REPLICATE)
    return cv2.resize(g, (W, H), interpolation=cv2.INTER_AREA)

def augment(g, rng=random):
    g = g.astype(np.float32)
    if rng.random() < .8:                                                   # ขยับ/หมุน/ย่อขยายเล็กน้อย
        M = cv2.getRotationMatrix2D((W / 2, H / 2), rng.uniform(-3, 3), rng.uniform(.92, 1.08))
        M[0, 2] += rng.uniform(-4, 4); M[1, 2] += rng.uniform(-2.5, 2.5)
        g = cv2.warpAffine(g, M, (W, H), borderMode=cv2.BORDER_REPLICATE)
    if rng.random() < .4: g = cv2.GaussianBlur(g, (0, 0), rng.uniform(.4, 1.8))
    if rng.random() < .2:                                                   # เบลอจากการเคลื่อนที่
        k = rng.randint(3, 9); ker = np.zeros((k, k), np.float32); ker[k // 2] = 1 / k
        g = cv2.filter2D(g, -1, cv2.warpAffine(ker, cv2.getRotationMatrix2D((k / 2, k / 2), rng.uniform(0, 180), 1), (k, k)))
    a = rng.uniform(.5, 1.4); g = (g - g.mean()) * a + g.mean() + rng.uniform(-40, 40)
    if rng.random() < .1: g = 255 - g                                       # กลับขาวดำ (กระดาษเข้ม)
    if rng.random() < .25:                                                  # เส้นประ/จุดของหน้าจอทับ
        x = rng.randint(0, W - 1); v = rng.choice([0, 255])
        for y in range(0, H, 4): g[y:y + 2, x:x + 1] = v
    g = g + np.random.normal(0, rng.uniform(0, 8), g.shape)
    g = np.clip(g, 0, 255).astype(np.uint8)
    if rng.random() < .4:
        g = cv2.imdecode(cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, rng.randint(30, 90)])[1], 0)
    return g

def bg_crops(frames, n, rng=random):
    """ชิ้นภาพสุ่มจากพื้น/ผนัง (ไม่ใช่แถบเลข) — สอนให้ "ไม่มั่นใจ" """
    out = []
    while len(out) < n:
        fr = gray(cv2.imread(rng.choice(frames))); h, w = fr.shape
        cw = rng.randint(120, 500); ch = int(cw / rng.uniform(3, 5))
        x, y = rng.randint(0, w - cw), rng.randint(0, h - ch)
        out.append(cv2.resize(fr[y:y + ch, x:x + cw], (W, H), interpolation=cv2.INTER_AREA))
    return out
