"""รายการฟอนต์ที่มีตัวเลขครบ 0-9 + แบ่งฟอนต์สำหรับเทรน / สำหรับสอบ (ห้ามปนกัน)

ใช้: python3 fonts.py  -> พิมพ์จำนวนฟอนต์ทั้งสองกลุ่ม
ฟอนต์สอบเลือกจาก "ชื่อตระกูล" (hash) ไม่ใช่ทีละไฟล์ — ตัวหนา/เอียงของตระกูลเดียวกันจะได้ไม่หลุดไปอยู่ฝั่งเทรน
"""
import hashlib, subprocess, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SKIP = ("Math", "Emoji", "Symbol", "Dingbat", "Caps", "Quotation", "Dunhill")


@functools.lru_cache(None)
def all_fonts():
    out = subprocess.run(["fc-list", ":lang=en", "family", "file"], capture_output=True, text=True).stdout
    seen, res = set(), []
    for line in out.splitlines():
        path, _, fam = line.partition(":")
        path, fam = path.strip(), fam.strip().split(",")[0]
        if not path.lower().endswith((".ttf", ".otf", ".ttc")) or path in seen:
            continue
        if any(s in fam or s in path for s in SKIP):
            continue
        seen.add(path)
        if _digits_ok(path):
            res.append((fam, path))
    return sorted(res)


def _digits_ok(path):
    """ฟอนต์ต้องวาดเลข 0-9 ได้จริง และแต่ละตัวต่างกัน (กันฟอนต์ที่ไม่มี glyph แล้วได้กล่องเปล่า)"""
    try:
        f = ImageFont.truetype(path, 40)
    except Exception:
        return False
    imgs = []
    for d in "0123456789":
        im = Image.new("L", (48, 56), 0)
        ImageDraw.Draw(im).text((24, 28), d, fill=255, font=f, anchor="mm")
        a = np.array(im)
        if a.sum() < 255 * 20:
            return False
        imgs.append(a > 127)
    for i in range(10):
        for j in range(i + 1, 10):
            if (imgs[i] ^ imgs[j]).sum() < 25:
                return False
    return True


def is_eval(fam):
    return int(hashlib.md5(fam.encode()).hexdigest(), 16) % 5 == 0


def split():
    fs = all_fonts()
    return [p for f, p in fs if not is_eval(f)], [p for f, p in fs if is_eval(f)]


if __name__ == "__main__":
    tr, ev = split()
    fams = sorted({f for f, _ in all_fonts()})
    print(f"ฟอนต์ทั้งหมด {len(all_fonts())} ไฟล์ {len(fams)} ตระกูล  เทรน {len(tr)}  สอบ {len(ev)}")
    print("ตระกูลสอบ:", sorted({f for f, _ in all_fonts() if is_eval(f)}))
