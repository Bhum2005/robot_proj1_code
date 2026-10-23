import sys, cv2, numpy as np
E = np.load(sys.argv[1])
def run(net, gs):
    out = []
    for g in gs:
        x = g.astype(np.float32); x = ((x - x.mean()) / max(float(x.std()), 1.0))[None, None]
        net.setInput(x); lg = net.forward().reshape(4, 10)
        p = np.exp(lg - lg.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
        out.append(("".join(map(str, p.argmax(1))), float(p.max(1).prod())))
    return out
for m in sys.argv[2:]:
    net = cv2.dnn.readNetFromONNX(m); s = m.split("/")[-1][:20]
    for th in (0.6, 0.8):
        line = f"{s:20} th{th}"
        for k in ("A", "B"):
            o = run(net, E[k]); L = E[k + "l"]
            ok = sum(d == l for (d, _), l in zip(o, L)); sug = sum(c >= th for _, c in o)
            bad = sum(c >= th and d != l for (d, c), l in zip(o, L))
            line += f" | {k}: ถูก {ok/len(L):.1%} แนะนำ {sug/len(L):.0%} ผิด {bad}"
        o = run(net, E["C"]); line += f" | C เบลอ: แนะนำ {sum(c >= th for _, c in o)}/{len(o)}"
        print(line)
