"""(ทีมเรา 17 ต.ค.) ตัวหาแถบเลขแบบเรียนรู้ — ไม่พึ่งสีตัวเรือน/สีกระดาษ

โมเดล strip_det.onnx (U-Net เล็ก เทรนจากฉากจำลองที่สุ่มสี/ทรง/ฟอนต์/พื้นหลัง + เฟรมจริงจากคลิป)
อินพุตภาพย่อ 320x240 -> แผนที่ 2 ช่องขนาด 160x120: [0] ตรงไหนเป็นกระดาษแถบเลข [1] ตรงไหนเป็นป้ายชื่อ (REAI)
ใช้ "เสริม" ตัวหาแบบกฎสี (pipeline.find_strips) — reader อ่านทุกแถบแล้วเลือกที่มั่นใจสุด
ไม่มีไฟล์โมเดล = ไม่ใช้ (ทำงานเหมือนเดิมทุกอย่าง)
"""
from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np

from meter_ai.strip import Strip, _add_margin, warp_strip

IW, IH, OS = 320, 240, 2
MODEL = Path(os.environ.get("ROBOT_STRIP_DET") or Path(__file__).with_name("strip_det.onnx"))
MIN_PX = 8              # ก้อนเล็กกว่านี้ (ในแผนที่ 160x120) ไม่นับ
THR = 0.5
_net = None


def available() -> bool:
    return MODEL.exists() and os.environ.get("ROBOT_STRIP_DET", "1") != "0"


def _get():
    global _net
    if _net is None:
        _net = cv2.dnn.readNetFromONNX(str(MODEL))
    return _net


def _letterbox(frame):
    h, w = frame.shape[:2]
    s = min(IW / w, IH / h)
    nw, nh = int(round(w * s)), int(round(h * s))
    out = np.zeros((IH, IW, 3), np.uint8)
    x0, y0 = (IW - nw) // 2, (IH - nh) // 2
    out[y0:y0 + nh, x0:x0 + nw] = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
    return out, s, x0, y0


def detect(frame_bgr: np.ndarray, top: int = 3) -> list[Strip]:
    if not available():
        return []
    lb, s, x0, y0 = _letterbox(frame_bgr)
    net = _get()
    net.setInput(cv2.dnn.blobFromImage(lb))            # BGR 0..255 ตามที่เทรน (โมเดลหาร 255 เอง)
    out = net.forward()[0]
    p = 1.0 / (1.0 + np.exp(-out))
    strip_m = (p[0] > THR).astype(np.uint8)
    label_m = p[1] > THR
    n, lab, st, _ = cv2.connectedComponentsWithStats(strip_m, connectivity=8)
    order = sorted(range(1, n), key=lambda i: -st[i, cv2.CC_STAT_AREA])[:top]
    res = []
    for i in order:
        if st[i, cv2.CC_STAT_AREA] < MIN_PX:
            continue
        ys, xs = np.nonzero(lab == i)
        pts = np.stack([xs, ys], 1).astype(np.float32) * OS + OS / 2      # -> พิกัดภาพ 320x240
        (cx, cy), (rw, rh), ang = cv2.minAreaRect(pts)
        if max(rw, rh) < 1.6 * max(min(rw, rh), 1):
            continue                                                      # ไม่ยาวพอจะเป็นแถบ 4 ช่อง
        th = np.deg2rad(ang)
        ax = np.array([np.cos(th), np.sin(th)])
        long_ax = ax if rw >= rh else np.array([-ax[1], ax[0]])
        L, H = max(rw, rh) + OS, min(rw, rh) + OS                        # ชดเชยความหยาบของแผนที่
        normal = np.array([long_ax[1], -long_ax[0]])
        up = normal if normal[1] < 0 else -normal                         # เดาไว้ก่อน: ด้านบนของภาพ
        hint = 0
        ly, lx = np.nonzero(label_m)
        if len(lx) >= 4:
            lp = np.stack([lx, ly], 1).astype(np.float32) * OS + OS / 2 - (cx, cy)
            d = lp @ normal; near = np.abs(lp @ long_ax) < L * .7
            a, b = int((d[near] > 0).sum()), int((d[near] < 0).sum())
            if max(a, b) >= 4 and max(a, b) >= 3 * max(min(a, b), 1):
                lab_up = normal if a > b else -normal
                hint = 1 if lab_up @ up > 0 else -1
        right = np.array([-up[1], up[0]])
        c = np.array([cx, cy])
        q = np.float32([c - right * L / 2 + up * H / 2, c + right * L / 2 + up * H / 2,
                        c + right * L / 2 - up * H / 2, c - right * L / 2 - up * H / 2])
        q = ((q - np.float32([x0, y0])) / s).astype(np.float32)          # -> พิกัดภาพจริง
        q = _add_margin(q)
        res.append(Strip(image=warp_strip(frame_bgr, q), quad=q, upright=None, mode="det",
                         target=None, hint=hint))
    return res
