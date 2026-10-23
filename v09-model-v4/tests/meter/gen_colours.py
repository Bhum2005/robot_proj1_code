"""สร้างภาพมิเตอร์จำลองที่เปลี่ยนสีกระดาษ/ตัวเลข จากรูปจริงของ robot-update"""
import sys, cv2, numpy as np
sys.path.insert(0, sys.argv[1])            # โฟลเดอร์ที่มี meter_ai ต้นฉบับ
from meter_ai.pipeline import find_strip
src = cv2.imread(sys.argv[2]); out = sys.argv[3]
s = find_strip(src)
poly = np.zeros(src.shape[:2], np.uint8)
cv2.fillConvexPoly(poly, np.round(s.quad).astype(np.int32), 255)
hsv = cv2.cvtColor(src, cv2.COLOR_BGR2HSV)
region = (poly > 0) & (hsv[..., 1] < 80)
L = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(np.float32)
lo, hi = np.percentile(L[region], 4), np.percentile(L[region], 85)
t = np.clip((L - lo) / max(hi - lo, 1), 0, 1)[..., None]
V = {  # ชื่อ: (กระดาษ RGB, ตัวเลข RGB)
 "white_black": ((255,255,255),(0,0,0)),
 "yellow_black": ((255,228,80),(20,20,20)),
 "pink_navy": ((255,165,200),(20,30,140)),
 "green_red": ((140,225,140),(200,20,20)),
 "black_white": ((25,25,25),(245,245,245)),
 "red_white": ((200,30,30),(250,250,250)),
 "gray_black": ((150,150,150),(10,10,10)),
 "yellow_red": ((255,235,90),(210,25,25)),
 "white_red": ((255,255,255),(210,20,20)),
 "white_green": ((255,255,255),(20,150,40)),
 "cyan_black": ((120,230,240),(10,10,10)),
 "purple_yellow": ((110,40,150),(255,230,60)),
}
for name, (p, d) in V.items():
    P = np.array(p[::-1], np.float32); D = np.array(d[::-1], np.float32)
    shade = np.clip(0.8 + 0.2 * L / max(hi, 1), 0.8, 1.05)[..., None]   # เก็บเงา/แสงเดิมไว้นิดหน่อย
    new = (D + (P - D) * t) * shade
    img = src.astype(np.float32).copy()
    img[region] = new[region]
    cv2.imwrite(f"{out}/{name}.png", np.clip(img, 0, 255).astype(np.uint8))
print("ok", len(V))
