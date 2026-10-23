"""Find the meter body (blue 3D-printed box/cylinder) in a BGR frame.

Runtime dependency: OpenCV + numpy only (works with the Pi's OpenCV 4.6).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# HSV range for the blue meter body (OpenCV hue is 0-179)
BLUE_LO = np.array([100, 80, 40], np.uint8)
BLUE_HI = np.array([130, 255, 255], np.uint8)

MIN_AREA_FRAC = 0.004      # ignore blobs smaller than 0.4% of the frame
EDGE_PENALTY = 0.25        # score multiplier for blobs cut off by the frame edge
EDGE_MARGIN = 3            # px
MERGE_MARGIN = 0.3         # grow the winner's bbox by this fraction when re-joining pieces
MERGE_GROW = 1.45         # (ทีมเรา) รวมชิ้นแล้วกรอบโตเกินผลรวมชิ้นได้ไม่เกินนี้
MIN_PIECE_AREA = 40        # px; smaller blue specks are not merged


# ---- (ทีมเรา 16 ต.ค.) ตัวเรือนสีอื่น ----
# ผู้ใช้: "ฐานอาจเปลี่ยนสี" — ถ้าไม่เจอตัวเรือนสีน้ำเงิน ลองหาก้อนสีสดสีอื่นแทน
# (ช่วง HSV ของ OpenCV: hue 0-179) ใช้เฉพาะตอนที่หาสีน้ำเงินไม่เจอ ของเดิมจึงไม่เปลี่ยน
BANDS = {
    "blue": [(BLUE_LO, BLUE_HI)],
    "red": [((0, 100, 60), (7, 255, 255)), ((170, 100, 60), (179, 255, 255))],
    "orange": [((7, 100, 70), (20, 255, 255))],
    "yellow": [((20, 90, 70), (35, 255, 255))],
    "green": [((35, 40, 35), (85, 255, 255))],          # เขียวเข้ม (สีขวดเขียว) ความอิ่มสีต่ำ
    "cyan": [((80, 35, 35), (100, 255, 255))],
    "purple": [((130, 70, 40), (170, 255, 255))],
}
# ตัวเรือนที่สีชนกับตัวอักษร REAI สีส้ม -> ใช้ REAI หาทิศไม่ได้ (reader จะลองทั้งสองทิศแทน)
ORANGEISH = ("red", "orange")


def band_mask(frame_bgr: np.ndarray, band: str, wide: bool = False) -> np.ndarray:
    """สีของตัวเรือน wide=True ขยายช่วงสี (ใช้ตอนตัดตัวเรือนออกจากกระดาษ ให้ขอบ/เงาไม่หลุดมา)"""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    m = np.zeros(hsv.shape[:2], np.uint8)
    ranges = BANDS[band]
    if wide and band in ORANGEISH:
        # แดงกับส้มต่อกันเป็นช่วงเดียว ตัวเรือนส้มอมแดงมีทั้งสองสีปน -> ตัดออกทั้งคู่
        ranges = BANDS["red"] + BANDS["orange"]
    for lo, hi in ranges:
        lo, hi = np.array(lo, np.int16), np.array(hi, np.int16)
        if wide:
            lo = lo - (5, 20, 15); hi = hi + (5, 0, 0)
            if band == "red":
                lo[0], hi[0] = max(lo[0], 0) if lo[0] < 90 else lo[0], min(hi[0], 179)
        lo = np.clip(lo, 0, 255).astype(np.uint8); hi = np.clip(hi, 0, 255).astype(np.uint8)
        hi[0] = min(int(hi[0]), 179)
        m |= cv2.inRange(hsv, lo, hi)
    return m


@dataclass
class Target:
    contour: np.ndarray               # convex hull of the (re-joined) body
    bbox: tuple[int, int, int, int]   # x, y, w, h
    mask: np.ndarray                  # uint8 0/255, filled convex hull of the body
    band: str = "blue"                # (ทีมเรา) สีของตัวเรือน
    score: float = 0.0


def blue_mask(frame_bgr: np.ndarray, band: str = "blue") -> np.ndarray:
    if band == "blue":
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, BLUE_LO, BLUE_HI)
    else:
        mask = band_mask(frame_bgr, band)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)


def _score(contour: np.ndarray, frame_w: int, frame_h: int) -> float:
    area = cv2.contourArea(contour)
    x, y, w, h = cv2.boundingRect(contour)
    cx, cy = x + w / 2, y + h / 2
    # distance from frame centre, normalised to 0 (centre) .. 1 (corner)
    dist = np.hypot((cx - frame_w / 2) / (frame_w / 2), (cy - frame_h / 2) / (frame_h / 2)) / np.sqrt(2)
    score = area * (1.0 - 0.5 * dist)
    touches_edge = (x <= EDGE_MARGIN or y <= EDGE_MARGIN
                    or x + w >= frame_w - EDGE_MARGIN or y + h >= frame_h - EDGE_MARGIN)
    return score * (EDGE_PENALTY if touches_edge else 1.0)


def _near(main: np.ndarray, other: np.ndarray, margin: float) -> bool:
    if cv2.contourArea(other) < MIN_PIECE_AREA:
        return False
    x, y, w, h = cv2.boundingRect(main)
    gx = gy = max(w, h) * margin  # a piece may be a thin slice, so measure by its long side
    ox, oy, ow, oh = cv2.boundingRect(other)
    return not (ox > x + w + gx or ox + ow < x - gx or oy > y + h + gy or oy + oh < y - gy)


def find_target(frame_bgr: np.ndarray, band: str = "blue", strong: bool = False) -> Target | None:
    """Return the most likely meter body, or None if nothing meter-sized is blue.

    strong=True (ทีมเรา): เปิดหน้ากากสีแรงขึ้น ตัดสะพานบาง ๆ ที่เชื่อมตัวเรือนกับของสีเดียวกันข้าง ๆ
    (ขอบเคสโทรศัพท์ เงาสะท้อน) ใช้เป็นรอบสองเมื่อรอบปกติหาแถบไม่เจอ"""
    h, w = frame_bgr.shape[:2]
    m = blue_mask(frame_bgr, band)
    if strong:
        k = max(9, int(min(h, w) / 30) | 1)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = MIN_AREA_FRAC * w * h
    candidates = [c for c in contours if cv2.contourArea(c) >= min_area]
    if not candidates:
        return None
    best = max(candidates, key=lambda c: _score(c, w, h))
    # The white digit strip often cuts the body in two; re-join blue pieces next to the winner.
    # Neighbouring meters are >= 1.5 body-widths apart, so a 30% margin cannot reach them.
    # (ทีมเรา) ชิ้นที่จะรวมต้อง "ใหญ่พอ" หรือ "อยู่ในกรอบตัวเรือน" — กันเศษสีน้ำเงินรอบ ๆ
    # (ขอบโทรศัพท์ ของสีเดียวกันข้าง ๆ) ถูกรวมจนกรอบตัวเรือนบวมไปกินพื้นหลังสีขาว
    bx, by, bw, bh = cv2.boundingRect(best)
    big = cv2.contourArea(best)

    def _belongs(c):
        x, y, w_, h_ = cv2.boundingRect(c)
        cx, cy = x + w_ / 2, y + h_ / 2
        a = cv2.contourArea(c)
        solid = a / max(cv2.contourArea(cv2.convexHull(c)), 1.0)
        if a >= 0.1 * big and solid < 0.6:
            return False            # ชิ้นใหญ่แต่โหว่/โค้งเป็นแถบบาง (ขอบเคส) ไม่ใช่ครึ่งตัวเรือน
        return a >= 0.1 * big or (bx <= cx <= bx + bw and by <= cy <= by + bh)
    pieces = [best]
    for c in sorted((c for c in contours if c is not best and _near(best, c, MERGE_MARGIN)
                     and _belongs(c)), key=cv2.contourArea, reverse=True):
        # ชิ้นที่ถูกแถบเลขตัดขาดจริง รวมแล้วกรอบแค่ "ปิดช่องแถบ" ไม่บวมเกิน
        # ส่วนของสีเดียวกันที่อยู่ข้าง ๆ (ขอบเคส ฯลฯ) รวมแล้วเกิดช่องว่างใหญ่ -> ไม่รวม
        cur = cv2.convexHull(np.vstack(pieces))
        both = cv2.contourArea(cv2.convexHull(np.vstack(pieces + [c])))
        if both <= MERGE_GROW * (cv2.contourArea(cur) + cv2.contourArea(cv2.convexHull(c))):
            pieces.append(c)
    hull = cv2.convexHull(np.vstack(pieces))
    mask = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(mask, hull, 255)
    return Target(contour=hull, bbox=cv2.boundingRect(hull), mask=mask, band=band,
                  score=_score(best, w, h))


def find_targets_other(frame_bgr: np.ndarray, top: int = 3) -> list[Target]:
    """(ทีมเรา) ตัวเรือนสีอื่นที่ไม่ใช่น้ำเงิน — ก้อนที่น่าจะเป็นตัวมิเตอร์มากสุดของแต่ละสี เรียงตามคะแนน"""
    out = [t for t in (find_target(frame_bgr, b) for b in BANDS if b != "blue") if t is not None]
    return sorted(out, key=lambda t: -t.score)[:top]
