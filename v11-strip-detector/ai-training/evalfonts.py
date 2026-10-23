"""ชุดสอบ "ฟอนต์/สีที่ไม่เคยเห็น": แถบเลขสีวาดด้วยฟอนต์ฝั่งสอบเท่านั้น (fonts.is_eval) ตั้ง seed คงที่
  python3 evalfonts.py make out.npz [n]        สร้างชุดสอบ
  python3 evalfonts.py score out.npz a.onnx [b.onnx ...]   วัดผลแบบเดียวกับ reader (เลือกทางที่มั่นใจสุด)"""
import sys, os, random, cv2, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pi"))
import data, fonts
from meter_ai.preprocess import paper_to_white, preprocess


def make(out, n):
    random.seed(1234); np.random.seed(1234)
    _, ev = fonts.split()
    X, L = [], []
    for i in range(n):
        lab = "".join(random.choice("0123456789") for _ in range(4))
        g = data.render_color(lab, ev)
        if random.random() < .5:
            g = cv2.GaussianBlur(g, (0, 0), random.uniform(.4, 1.2))
        g = cv2.imdecode(cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, random.randint(50, 90)])[1], 1)
        X.append(g); L.append(lab)
    np.savez_compressed(out, X=np.stack(X), L=np.array(L))
    print("ok", out, n)


def score(path, model):
    d = np.load(path); net = cv2.dnn.readNetFromONNX(model)
    res = {"ok": 0, "s60": 0, "w60": 0, "s75": 0, "w75": 0}
    for img, lab in zip(d["X"], d["L"]):
        best = (None, -1)
        for v in (img, paper_to_white(img)):
            net.setInput(preprocess(v)); lg = net.forward().reshape(4, 10)
            p = np.exp(lg - lg.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
            dg = "".join(map(str, p.argmax(1))); c = float(p.max(1).prod())
            if c > best[1]: best = (dg, c)
        dg, c = best; res["ok"] += dg == lab
        for t in (60, 75):
            if c >= t / 100: res[f"s{t}"] += 1; res[f"w{t}"] += dg != lab
    n = len(d["L"])
    print(f"{os.path.basename(model):34s} ถูก {res['ok']/n:6.1%} | มั่นใจ>=60%: แนะนำ {res['s60']/n:6.1%} ผิด {res['w60']} | "
          f">=75% (ใส่ให้เลย): {res['s75']/n:6.1%} ผิด {res['w75']}")


if __name__ == "__main__":
    if sys.argv[1] == "make":
        make(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 800)
    else:
        for m in sys.argv[3:]:
            score(sys.argv[2], m)
