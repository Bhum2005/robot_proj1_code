"""วัดระดับแถบ (ชุด c4 เดียวกับตอนเทรน) ด้วยไฟล์ ONNX ผ่าน OpenCV dnn — แบบเดียวกับบน Pi"""
import sys, cv2, numpy as np
sys.path.insert(0, ".")
import data
val = data.load_real(sys.argv[1], set(sys.argv[2].split(",")))[0]
for m in sys.argv[3:]:
    net = cv2.dnn.readNetFromONNX(m); ok = sug = bad = 0
    for g, lab, _ in val:
        x = g.astype(np.float32); x = ((x - x.mean()) / max(float(x.std()), 1.0))[None, None]
        net.setInput(x); lg = net.forward().reshape(4, 10)
        p = np.exp(lg - lg.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
        d = "".join(map(str, p.argmax(1))); c = p.max(1).prod(); ok += d == lab
        if c >= .6: sug += 1; bad += d != lab
    print(f"{m.split('/')[-1]:22} exact {ok}/{len(val)} ({ok/len(val):.1%})  แนะนำ {sug}  แนะนำผิด {bad}")
