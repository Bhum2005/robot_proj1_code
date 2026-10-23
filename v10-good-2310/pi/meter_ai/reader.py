"""Frame -> 4 digits + confidence, using only OpenCV's dnn module (runs on the robot)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from meter_ai.kind import classify as classify_kind
from meter_ai.locate import find_target
from meter_ai.pipeline import _work, find_strips
from meter_ai.preprocess import paper_to_white, preprocess
from meter_ai.strip import Strip, warp_strip

# (ทีมเรา) กรอบแถบที่หาจากกระดาษสีมักเลื่อนขึ้น/ลงไม่กี่พิกเซล (ปลายกระดาษม้วน เงา)
# โมเดลไวต่อกรอบมาก จึงลองขยับกรอบเล็กน้อยแล้วเลือกที่มั่นใจสุด — ใช้กับกระดาษสีเท่านั้น
# (เลื่อน, ขยาย) เป็นสัดส่วนของความสูงแถบ
JITTER = ((0.0, 0.0), (-0.08, 0.0), (0.08, 0.0), (0.0, 0.1), (0.0, -0.08))


# (ทีมเรา) แถบที่หาได้สั้นไปข้างหนึ่ง (ช่องสุดท้ายติดขอบตัวเรือน/แสงสะท้อน) -> ลองยืดปลายซ้าย/ขวา
STRETCH = ((0.0, 0.15), (0.15, 0.0), (0.12, 0.12), (-0.1, 0.1), (0.1, -0.1),
           (0.0, 0.35), (0.35, 0.0))      # 0.35 = แถบที่หาได้ขาดไปหนึ่งช่อง (3 ช่อง -> 4 ช่อง)


def _stretch(quad: np.ndarray, left: float, right: float) -> np.ndarray:
    tl, tr, br, bl = quad
    a, b = tr - tl, br - bl                          # ทิศ "ขวา" ของขอบบน/ล่าง ยาว = ความยาวแถบ
    return np.float32([tl - a * left, tr + a * right, br + b * right, bl - b * left])


def _jitter(quad: np.ndarray, shift: float, grow: float) -> np.ndarray:
    tl, tr, br, bl = quad
    up_l, up_r = tl - bl, tr - br                   # ทิศ "ขึ้น" ของแต่ละปลาย ยาว = ความสูงแถบ
    q = np.float32([tl + up_l * (shift + grow / 2), tr + up_r * (shift + grow / 2),
                    br + up_r * (shift - grow / 2), bl + up_l * (shift - grow / 2)])
    return q

# meter_digits.onnx = รุ่นที่ทีมเราเทรนใหม่ (16 ต.ค.) ; รุ่นเดิมของ robot-update เก็บไว้เป็น
# meter_digits_robot_update.onnx — สลับกลับได้ด้วย ROBOT_METER_MODEL=<ไฟล์>
DEFAULT_MODEL = Path(os.environ.get("ROBOT_METER_MODEL") or Path(__file__).with_name("meter_digits.onnx"))


AMBIG_CONF = 0.3        # (ทีมเรา) สองทิศอ่านได้คนละเลข และทั้งคู่มั่นใจเกินนี้ = ทิศกำกวม
AMBIG_CAP = 0.5         # ... ลดความมั่นใจลงต่ำกว่าเกณฑ์แนะนำ
KIND_MIN_READ = 0.6     # (ทีมเรา) บอกน้ำ/ไฟเฉพาะเมื่ออ่านเลขได้มั่นใจระดับแนะนำแล้ว


@dataclass
class Reading:
    digits: str | None          # most likely digits (not thresholded); None if no strip found
    confidence: float           # product of the 4 per-digit probabilities, 0..1
    strip: Strip | None         # strip.image = what the model actually read
    kind: str | None = None     # (ทีมเรา) "water" ทรงกระบอก / "power" กล่องสี่เหลี่ยม — ดู kind.py
    kconf: float = 0.0          # ความมั่นใจของชนิดมิเตอร์ 0.5..1


class MeterReader:
    def __init__(self, model_path: str | Path = DEFAULT_MODEL):
        self._net = cv2.dnn.readNetFromONNX(str(model_path))

    def _infer(self, img: np.ndarray) -> tuple[str, float]:
        self._net.setInput(preprocess(img))
        logits = self._net.forward().reshape(4, 10)
        p = np.exp(logits - logits.max(axis=1, keepdims=True))
        p /= p.sum(axis=1, keepdims=True)
        return "".join(str(int(d)) for d in p.argmax(axis=1)), float(p.max(axis=1).prod())

    def read(self, frame_bgr: np.ndarray) -> Reading:
        best = self._read_digits(frame_bgr)
        if best.confidence < KIND_MIN_READ:
            # อ่านเลขไม่ออก = ไม่แน่ใจว่าก้อนสีนั้นคือตัวมิเตอร์จริง (อาจเป็นกระดาษ/ของอื่นสีเดียวกัน)
            return best
        try:
            work, _ = _work(frame_bgr)
            t = best.strip.target if best.strip is not None and best.strip.target is not None \
                else find_target(work)
            if t is not None:
                best.kind, best.kconf = classify_kind(t.contour, work.shape)
        except Exception:
            pass
        return best

    def _read_digits(self, frame_bgr: np.ndarray) -> Reading:
        best = Reading(None, 0.0, None)
        for strip in find_strips(frame_bgr):
            if strip.mode == "white":
                # white paper: exactly what the model was trained on — read as is
                cands = [(strip.image, strip.quad)]
            else:
                # the paper may be coloured: also redraw it dark-on-white, and nudge the crop
                cands = [(strip.image, strip.quad)]
                for sh, gr in JITTER:
                    q = strip.quad if (sh, gr) == (0.0, 0.0) else _jitter(strip.quad, sh, gr)
                    cands.append((paper_to_white(warp_strip(frame_bgr, q)), q))
                if strip.target is not None and getattr(strip.target, "band", "blue") != "blue":
                    for lf, rt in STRETCH:
                        q = _stretch(strip.quad, lf, rt)
                        im = warp_strip(frame_bgr, q)
                        cands += [(im, q), (paper_to_white(im), q)]
            base = []
            if strip.upright is None:
                # (ทีมเรา) ไม่รู้ทิศ (ไม่เห็น REAI / ตัวเรือนสีส้มแดง) -> ลองกลับหัวด้วย ใช้ทิศที่มั่นใจกว่า
                base = [(strip.image, strip.quad)]
                if strip.mode != "white":
                    base.append((paper_to_white(strip.image), strip.quad))
                cands += [(cv2.rotate(im, cv2.ROTATE_180), q[[2, 3, 0, 1]]) for im, q in base]
            n_up = len(cands) - (len(base) if strip.upright is None else 0)
            res = [(self._infer(img), img, q, i >= n_up) for i, (img, q) in enumerate(cands)]
            ambiguous = False
            if strip.upright is None:
                # ★ ไม่รู้ทิศแล้วอ่านได้ทั้งสองทิศแต่คนละเลข (เช่นเลข 7 ส่วน 0890 กลับหัว = 0680)
                #   แปลว่าเดาทิศไม่ได้จริง -> ห้ามมั่นใจ (ไม่แนะนำ ไม่ใส่ให้อัตโนมัติ)
                a = max((r for r in res if not r[3]), key=lambda r: r[0][1])
                b = max((r for r in res if r[3]), key=lambda r: r[0][1])
                ambiguous = a[0][0] != b[0][0] and min(a[0][1], b[0][1]) >= AMBIG_CONF
                if ambiguous and strip.hint:
                    # มีป้าย (เช่น REAI สีขาว) บอกทิศ -> เชื่อทิศนั้น ไม่ต้องลดความมั่นใจ
                    res = [r for r in res if r[3] == (strip.hint < 0)]
                    ambiguous = False
            for (digits, conf), img, q, _ in res:
                if ambiguous:
                    conf = min(conf, AMBIG_CAP)
                if conf > best.confidence:
                    best = Reading(digits, conf, Strip(img, q, strip.upright, strip.mode, strip.target))
        return best
