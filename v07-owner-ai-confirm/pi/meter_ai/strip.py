"""Cut the white digit strip out of a located meter and warp it upright.

Orientation comes from the orange "REAI" lettering, which is printed above the strip:
the meter may be seen from any side (water meters face the ceiling), so the strip can be
rotated by any angle in the frame, including upside down (where 6 and 9 swap).
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from meter_ai.locate import Target

STRIP_W, STRIP_H = 160, 40

WHITE_MAX_SAT = 70
WHITE_MIN_VAL = 120
MIN_STRIP_FRAC = 0.02       # strip must cover >= 2% of the meter body
MIN_ORANGE_PX = 30          # fewer orange pixels than this -> orientation unknown
CORNER_TIE_PX = 1.5         # hull points this close to the extreme count as the same corner
SLIVER_FRAC = 0.5           # glare slivers thinner than half the strip's thickness are removed
END_MARGIN = 0.12           # crop extends 12% of the strip length past each end
SIDE_MARGIN = 0.08          # ... and 8% of its thickness past each long side
AA_SHRINK = 1.5          # pre-shrink with INTER_AREA when the strip is >1.5x the output size
MIN_ASPECT = 2.0           # real strips are ~4-5:1, still >2.5:1 when foreshortened


@dataclass
class Strip:
    image: np.ndarray           # STRIP_H x STRIP_W BGR, digits read left-to-right
    quad: np.ndarray            # 4x2 float32 in frame coords: tl, tr, br, bl (after orientation)
    upright: bool | None        # True: oriented by REAI; None: REAI not seen, guessed image-up
                                # (never False: when REAI is found the strip is always turned upright)
    mode: str = "white"         # which finder cut it (see MODES)


def orange_mask(frame_bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    low = cv2.inRange(hsv, (0, 90, 100), (22, 255, 255))
    # small/far REAI letters blur towards pink (hue ~160); blue body is 100-130 so this is safe
    high = cv2.inRange(hsv, (155, 70, 100), (179, 255, 255))
    return cv2.bitwise_or(low, high)


def _white_blob(frame_bgr: np.ndarray, target: Target) -> np.ndarray | None:
    """Largest white region inside the meter body, as a contour."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, (0, 0, WHITE_MIN_VAL), (179, WHITE_MAX_SAT, 255))
    white = cv2.bitwise_and(white, target.mask)
    # Blurry REAI letters leave a pale halo that reads as "white"; keep it out of the strip.
    halo = cv2.dilate(orange_mask(frame_bgr), np.ones((3, 3), np.uint8))
    white[halo > 0] = 0
    return _clean_blob(white, target)


# ---- กระดาษสีอื่น (เพิ่มโดยทีมเรา) ----
# แถบเลขอาจเปลี่ยนเป็นกระดาษสี/ตัวเลขสีอื่น จึงหาแถบแบบไม่ต้องพึ่งสีขาว:
# ในตัวมิเตอร์ ทุกอย่างที่ "ไม่ใช่สีน้ำเงินของตัวเรือน" คือแถบเลข (+ ตัวอักษร REAI)
# ใช้ช่วงสีน้ำเงินกว้างกว่าตอนหาตัวเรือน เพื่อให้ขอบ/เงาของตัวเรือนไม่ถูกนับเป็นกระดาษ
BODY_LO = np.array([95, 60, 25], np.uint8)
BODY_HI = np.array([135, 255, 255], np.uint8)


def _any_blob(frame_bgr: np.ndarray, target: Target, drop_orange: bool) -> np.ndarray | None:
    """Largest non-blue region inside the meter body (paper of any colour but blue).

    drop_orange=True  removes the REAI lettering (normal case)
    drop_orange=False keeps orange/red pixels, for red or orange paper (REAI is still found
                      afterwards because the strip area is masked out when looking for it)
    """
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    paper = cv2.bitwise_not(cv2.inRange(hsv, BODY_LO, BODY_HI))
    inner = target.mask
    paper = cv2.bitwise_and(paper, inner)
    if drop_orange:
        halo = cv2.dilate(orange_mask(frame_bgr), np.ones((5, 5), np.uint8))
        paper[halo > 0] = 0
    else:
        # กระดาษแดง/ส้ม/ชมพูกลืนสีเดียวกับ REAI จึงลบสีส้มทิ้งไม่ได้ — แยกด้วยรูปร่างแทน:
        # กระดาษ (รวมตัวเลขที่อยู่บนมัน) เป็นก้อนเดียวต่อกันที่ใหญ่สุด ส่วนตัวอักษร REAI
        # เป็นก้อนเล็กแยกกันโดยมีพื้นน้ำเงินคั่น  ตัดสะพานบาง ๆ ก่อนแล้วเก็บก้อนใหญ่สุด
        paper = cv2.morphologyEx(paper, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(paper, connectivity=4)
        if n <= 1:
            return None
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        paper = np.where(lab == big, 255, 0).astype(np.uint8)
    return _clean_blob(paper, target)


def _clean_blob(white: np.ndarray, target: Target) -> np.ndarray | None:
    """Bridge digits/box lines, drop glare slivers, return the strip contour or None."""
    # Bridge the dark digits and box lines so the strip is one blob. Scale the kernel to the
    # meter's size: a fixed kernel either fails to bridge near meters or over-merges far ones.
    body = min(target.bbox[2:])
    close_k = max(3, int(body / 25) | 1)
    white = cv2.morphologyEx(white, cv2.MORPH_CLOSE, np.ones((close_k, close_k), np.uint8), iterations=2)
    blob = _largest(cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)))
    if blob is None:
        return None
    # Shave off glare slivers on the rim that touch the strip. Size the opening by the strip's
    # own thickness (not the body's): a far, foreshortened strip can be only ~8 px thick, and
    # an opening sized by the body erased it entirely.
    thickness = min(cv2.minAreaRect(blob)[1])
    open_k = max(3, int(thickness * SLIVER_FRAC) | 1)
    shaved = _largest(cv2.morphologyEx(white, cv2.MORPH_OPEN,
                                       cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_k, open_k))))
    blob = shaved if shaved is not None else blob
    if cv2.contourArea(blob) < MIN_STRIP_FRAC * cv2.countNonZero(target.mask):
        return None
    return blob


def _largest(mask: np.ndarray) -> np.ndarray | None:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return max(contours, key=cv2.contourArea) if contours else None


def _reai_direction(frame_bgr, target, blob, centre) -> np.ndarray | None:
    """Unit vector from strip centre towards the REAI lettering, or None."""
    strip_area = np.zeros(frame_bgr.shape[:2], np.uint8)
    cv2.fillConvexPoly(strip_area, cv2.convexHull(blob), 255)
    orange = orange_mask(frame_bgr)
    # ★ (ทีมเรา) กระดาษสีแดง/ส้ม/ชมพู ถูกนับเป็น "สีส้ม" ด้วย ขอบกระดาษที่เลยแถบออกมา
    #   จะดึงจุดศูนย์กลางของ REAI ไปผิดด้าน -> ตัดขอบแถบกว้างขึ้น + ลบเส้นบาง ๆ ทิ้ง
    #   กระดาษขาวปกติไม่เข้าเงื่อนไขนี้ ทำงานเหมือนเดิมทุกอย่าง
    inside = orange[strip_area > 0]
    paper_orange = inside.size and np.count_nonzero(inside) > 0.3 * inside.size
    if paper_orange:
        k = max(7, int(min(cv2.minAreaRect(blob)[1]) * 0.3) | 1)
        strip_area = cv2.dilate(strip_area, np.ones((k, k), np.uint8))
        orange = cv2.morphologyEx(orange, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    else:
        strip_area = cv2.dilate(strip_area, np.ones((7, 7), np.uint8))  # box lines touch the edge
    orange[(target.mask == 0) | (strip_area > 0)] = 0
    ys, xs = np.nonzero(orange)
    if len(xs) < MIN_ORANGE_PX:
        return None
    v = np.array([xs.mean(), ys.mean()]) - centre
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else None


def extract_strip(frame_bgr: np.ndarray, target: Target) -> Strip | None:
    found = strip_quad(frame_bgr, target)
    if found is None:
        return None
    quad, upright = found
    return Strip(image=warp_strip(frame_bgr, quad), quad=quad, upright=upright)


def warp_strip(frame_bgr: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """Warp the quad (tl, tr, br, bl) to STRIP_W x STRIP_H, area-averaging if it is shrunk a lot."""
    quad = quad.astype(np.float32)
    length = np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])
    height = np.linalg.norm(quad[3] - quad[0]) + np.linalg.norm(quad[2] - quad[1])
    shrink = min(length / (2 * STRIP_W), height / (2 * STRIP_H))
    src = frame_bgr
    if shrink > AA_SHRINK:
        # warpPerspective point-samples; pre-shrink the region with INTER_AREA to avoid aliasing
        x, y, w, h = cv2.boundingRect(np.round(quad).astype(np.int32))
        x0, y0 = max(x - 2, 0), max(y - 2, 0)
        x1, y1 = min(x + w + 2, src.shape[1]), min(y + h + 2, src.shape[0])
        roi = src[y0:y1, x0:x1]
        size = (max(1, round(roi.shape[1] / shrink)), max(1, round(roi.shape[0] / shrink)))
        src = cv2.resize(roi, size, interpolation=cv2.INTER_AREA)
        quad = (quad - np.float32([x0, y0]) + 0.5) * np.float32(
            [size[0] / roi.shape[1], size[1] / roi.shape[0]]) - 0.5
    dst = np.array([[0, 0], [STRIP_W - 1, 0], [STRIP_W - 1, STRIP_H - 1], [0, STRIP_H - 1]], np.float32)
    m = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    return cv2.warpPerspective(src, m, (STRIP_W, STRIP_H), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)


MODES = ("white", "any", "any_orange")


def strip_quad(frame_bgr: np.ndarray, target: Target,
               mode: str = "white") -> tuple[np.ndarray, bool | None] | None:
    """Corners (tl, tr, br, bl, in reading order) of the digit strip, and whether REAI fixed the
    orientation. None if the meter shows no strip-shaped region.

    mode "white" = original white-paper finder; "any" / "any_orange" = paper of any colour."""
    if mode == "white":
        blob = _white_blob(frame_bgr, target)
    else:
        blob = _any_blob(frame_bgr, target, drop_orange=(mode == "any"))
    if blob is None:
        return None
    (cx, cy), (rw, rh), angle = cv2.minAreaRect(blob)
    if max(rw, rh) < MIN_ASPECT * min(rw, rh):
        return None                     # square-ish white patch: glare/sticker, not the strip
    centre = np.array([cx, cy])
    theta = np.deg2rad(angle)
    axis_w = np.array([np.cos(theta), np.sin(theta)])       # direction of the rect's "width" side
    long_axis = axis_w if rw >= rh else np.array([-axis_w[1], axis_w[0]])
    normal = np.array([long_axis[1], -long_axis[0]])        # perpendicular to the strip

    reai = _reai_direction(frame_bgr, target, blob, centre)
    if reai is not None:
        up, upright = (normal if normal @ reai > 0 else -normal), True
    else:
        up, upright = (normal if normal[1] < 0 else -normal), None  # guess: image-up
    right = np.array([-up[1], up[0]])                       # reading direction for this "up"

    # Perspective-aware corners: the hull point furthest along each diagonal direction.
    hull = cv2.convexHull(blob).reshape(-1, 2).astype(np.float32)

    def corner(d: np.ndarray) -> np.ndarray:
        # average near-ties instead of argmax, whose tie-break depends on hull point order
        # (which changes when the same scene is seen rotated)
        proj = hull @ (d / np.linalg.norm(d))
        return hull[proj >= proj.max() - CORNER_TIE_PX].mean(axis=0)

    quad = np.array([corner(-right + up), corner(right + up),
                     corner(right - up), corner(-right - up)], np.float32)
    return _add_margin(quad), upright


def _add_margin(quad: np.ndarray) -> np.ndarray:
    """Widen the crop by a fixed fraction at each end and side.

    The white blob can stop short of the paper (paper overhanging a cylinder's rim, a curled
    corner, glare), which chopped off an end digit. The model is trained on crops framed this
    loosely, so a fixed margin is safer than trying to find the exact paper edge.
    """
    tl, tr, br, bl = quad
    m, t = END_MARGIN, SIDE_MARGIN
    tl2, tr2 = tl + (tl - tr) * m, tr + (tr - tl) * m
    bl2, br2 = bl + (bl - br) * m, br + (br - bl) * m
    return np.float32([tl2 + (tl2 - bl2) * t, tr2 + (tr2 - br2) * t,
                       br2 + (br2 - tr2) * t, bl2 + (bl2 - tl2) * t])
