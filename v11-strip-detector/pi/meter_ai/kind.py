"""มิเตอร์น้ำหรือมิเตอร์ไฟ — ดูจากรูปทรงของตัวมิเตอร์สีน้ำเงิน (ทีมเราเพิ่ม 16 ต.ค. 2569)

  มิเตอร์น้ำ = ทรงกระบอกวางพื้น  -> ขอบโค้ง เข้ากับวงรีได้ดี
  มิเตอร์ไฟ = กล่องสี่เหลี่ยมติดผนัง -> ขอบตรง มีมุม เหลือไม่กี่เหลี่ยมเมื่อทำให้เรียบ

ใช้ 3 ค่าจากเส้นขอบ (convex hull ที่ locate.find_target หาไว้แล้ว ไม่ต้องคำนวณภาพใหม่)
  ie = IoU กับวงรีที่ fit ได้        (น้ำ 0.84–0.97 · ไฟ 0.59–0.85)
  v1 = จำนวนมุมเมื่อทำให้เรียบ 1%    (น้ำ 6–14   · ไฟ 4–7)
  ir = IoU กับสี่เหลี่ยมหมุนที่เล็กสุด
น้ำหนัก = logistic regression จากเฟรมจริง 298 เฟรม (คลิป 1–4 ของทีม: น้ำ 7527 2045 8785 · ไฟ 5977 6201 2664)
ทดสอบแบบกันคลิปออกทีละคลิป: ถูก 294/298 อีก 4 เฟรมที่ผิดมั่นใจแค่ ~0.52 (ตัวมิเตอร์โดนขอบภาพตัด)
=> ที่ความมั่นใจ >= 0.75 ไม่มีเฟรมไหนทายผิด
"""
from __future__ import annotations

import math

import cv2
import numpy as np

W = (1.0985, 0.6687, -0.1988)
B = -1.4219
EDGE_MARGIN = 3
EDGE_SHRINK = 0.8       # ตัวมิเตอร์โดนขอบภาพตัด: รูปทรงเชื่อได้น้อยลง ลดความมั่นใจลงหน่อย


def features(contour: np.ndarray, shape_hw) -> dict:
    h, w = shape_hw[:2]
    per = cv2.arcLength(contour, True)
    v1 = len(cv2.approxPolyDP(contour, 0.01 * per, True))
    m = np.zeros((h, w), np.uint8)
    cv2.fillConvexPoly(m, contour, 255)
    a = m > 0
    ie = 0.0
    if len(contour) >= 5:
        me = np.zeros_like(m)
        cv2.ellipse(me, cv2.fitEllipse(contour), 255, -1)
        e = me > 0
        ie = float((a & e).sum()) / max(float((a | e).sum()), 1.0)
    mr = np.zeros_like(m)
    cv2.fillConvexPoly(mr, cv2.boxPoints(cv2.minAreaRect(contour)).astype(np.int32), 255)
    r = mr > 0
    ir = float((a & r).sum()) / max(float((a | r).sum()), 1.0)
    x, y, bw, bh = cv2.boundingRect(contour)
    edge = (x <= EDGE_MARGIN or y <= EDGE_MARGIN
            or x + bw >= w - EDGE_MARGIN or y + bh >= h - EDGE_MARGIN)
    return {"ie": ie, "v1": v1, "ir": ir, "edge": edge}


def classify(contour: np.ndarray, shape_hw) -> tuple[str, float]:
    """-> ("water" | "power", ความมั่นใจ 0.5..1)"""
    f = features(contour, shape_hw)
    z = (W[0] * (f["ie"] - 0.8) / 0.05 + W[1] * (f["v1"] - 7) / 2.0
         + W[2] * (f["ir"] - 0.88) / 0.05 + B)
    p = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))
    kind = "water" if p >= 0.5 else "power"
    conf = max(p, 1.0 - p)
    if f["edge"]:
        conf = 0.5 + (conf - 0.5) * EDGE_SHRINK
    return kind, conf
