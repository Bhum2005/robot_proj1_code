"""Frame of any resolution -> upright digit strip.

Locating runs at WORK_WIDTH (the resolution the thresholds were tuned on and that is
fast on the Pi); the strip itself is cut from the full-resolution frame, so a 1280x960
capture gives sharper digits for far meters.
"""
from __future__ import annotations

import cv2
import numpy as np

from meter_ai.locate import find_target, find_targets_other
from meter_ai.strip import MODES, Strip, strip_quad, warp_strip

WORK_WIDTH = 640


def _work(frame_bgr: np.ndarray):
    h, w = frame_bgr.shape[:2]
    scale = WORK_WIDTH / w if w > WORK_WIDTH else 1.0
    work = frame_bgr if scale == 1.0 else cv2.resize(
        frame_bgr, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return work, scale


def _cut(frame_bgr, work, scale, target, mode, rank=0) -> Strip | None:
    found = strip_quad(work, target, mode, rank)
    if found is None:
        return None
    quad, upright = found
    quad_full = ((quad + 0.5) / scale - 0.5).astype(np.float32)   # pixel-centre mapping
    from meter_ai.strip import STRIP_HINT
    return Strip(image=warp_strip(frame_bgr, quad_full), quad=quad_full, upright=upright,
                 mode=mode, target=target, hint=STRIP_HINT[0])


def find_strip(frame_bgr: np.ndarray) -> Strip | None:
    """Original behaviour: white paper only."""
    work, scale = _work(frame_bgr)
    target = find_target(work)
    return None if target is None else _cut(frame_bgr, work, scale, target, "white")


def find_strips(frame_bgr: np.ndarray) -> list[Strip]:
    """Every candidate strip: the white-paper finder first, then the any-colour finders.
    The reader keeps whichever the model is most sure about."""
    work, scale = _work(frame_bgr)
    target = find_target(work)
    out = _strips_of(frame_bgr, work, scale, target) if target is not None else []
    if not out and target is not None:
        t2 = find_target(work, strong=True)      # (ทีมเรา) ตัวเรือนติดกับของสีเดียวกัน -> ตัดสะพานแล้วลองใหม่
        if t2 is not None:
            out = _strips_of(frame_bgr, work, scale, t2)
    if not out:
        # (ทีมเรา) ไม่เจอตัวเรือนสีน้ำเงิน หรือเจอแต่ไม่มีแถบเลข -> ลองตัวเรือนสีอื่น
        for t in find_targets_other(work):
            out += _strips_of(frame_bgr, work, scale, t)
    return out


def _strips_of(frame_bgr, work, scale, target) -> list[Strip]:
    out = []
    # (ทีมเรา) ตัวเรือนสีอื่นลองก้อนอันดับ 2-3 ด้วย (REAI สีขาวบนตัวเรือนเข้มใหญ่กว่าแถบเลขได้)
    ranks = (0,) if target.band == "blue" else (0, 1, 2)
    modes = MODES if target.band == "blue" else MODES + ("any_orange_b",)
    for mode in modes:
        for rank in ranks:
            s = _cut(frame_bgr, work, scale, target, mode, rank)
            if s is not None and not any(np.abs(s.quad - o.quad).max() < 2.0 for o in out):
                out.append(s)
    return out
