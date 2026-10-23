"""Frame -> 4 digits + confidence, using only OpenCV's dnn module (runs on the robot)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from meter_ai.pipeline import find_strips
from meter_ai.preprocess import paper_to_white, preprocess
from meter_ai.strip import Strip, warp_strip

# (ทีมเรา) กรอบแถบที่หาจากกระดาษสีมักเลื่อนขึ้น/ลงไม่กี่พิกเซล (ปลายกระดาษม้วน เงา)
# โมเดลไวต่อกรอบมาก จึงลองขยับกรอบเล็กน้อยแล้วเลือกที่มั่นใจสุด — ใช้กับกระดาษสีเท่านั้น
# (เลื่อน, ขยาย) เป็นสัดส่วนของความสูงแถบ
JITTER = ((0.0, 0.0), (-0.08, 0.0), (0.08, 0.0), (0.0, 0.1), (0.0, -0.08))


def _jitter(quad: np.ndarray, shift: float, grow: float) -> np.ndarray:
    tl, tr, br, bl = quad
    up_l, up_r = tl - bl, tr - br                   # ทิศ "ขึ้น" ของแต่ละปลาย ยาว = ความสูงแถบ
    q = np.float32([tl + up_l * (shift + grow / 2), tr + up_r * (shift + grow / 2),
                    br + up_r * (shift - grow / 2), bl + up_l * (shift - grow / 2)])
    return q

DEFAULT_MODEL = Path(__file__).with_name("meter_digits.onnx")


@dataclass
class Reading:
    digits: str | None          # most likely digits (not thresholded); None if no strip found
    confidence: float           # product of the 4 per-digit probabilities, 0..1
    strip: Strip | None         # strip.image = what the model actually read


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
            for img, q in cands:
                digits, conf = self._infer(img)
                if conf > best.confidence:
                    best = Reading(digits, conf, Strip(img, q, strip.upright, strip.mode))
        return best
