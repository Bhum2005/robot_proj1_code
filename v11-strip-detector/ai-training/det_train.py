"""เทรน "ตัวหาแถบเลข" (U-Net เล็ก) — อินพุต 320x240 BGR, เอาต์พุต 2x120x160 [แถบเลข, ป้ายชื่อ]
  python3 det_train.py out.onnx epochs real.npz syn_0.npz syn_1.npz ...
ไฟล์ .npz จาก det_data.py (ฉากจำลอง) และเฟรมจริงที่ติดป้ายด้วย AI ตัวเดิม"""
import sys, time, random, numpy as np, torch, torch.nn as nn, torch.nn.functional as F
torch.set_num_threads(2); torch.manual_seed(0); random.seed(0); np.random.seed(0)
OUT, EP, FILES = sys.argv[1], int(sys.argv[2]), sys.argv[3:]


def cbr(i, o, s=1, d=1):
    return nn.Sequential(nn.Conv2d(i, o, 3, s, padding=d, dilation=d, bias=False), nn.BatchNorm2d(o), nn.ReLU())


class Det(nn.Module):
    def __init__(s):
        super().__init__()
        s.e1 = nn.Sequential(cbr(3, 16, 2), cbr(16, 16))            # 120x160
        s.e2 = nn.Sequential(cbr(16, 32, 2), cbr(32, 32))           # 60x80
        s.e3 = nn.Sequential(cbr(32, 64, 2), cbr(64, 64))           # 30x40
        s.e4 = nn.Sequential(cbr(64, 96, 2), cbr(96, 96, d=2), cbr(96, 96, d=4))   # 15x20
        s.up = nn.Upsample(scale_factor=2, mode="nearest")
        s.d3 = cbr(96 + 64, 64); s.d2 = cbr(64 + 32, 32); s.d1 = cbr(32 + 16, 16)
        s.out = nn.Conv2d(16, 2, 1)

    def forward(s, x):
        x = x / 255.0
        a = s.e1(x); b = s.e2(a); c = s.e3(b); d = s.e4(c)
        y = s.d3(torch.cat([s.up(d), c], 1))
        y = s.d2(torch.cat([s.up(y), b], 1))
        y = s.d1(torch.cat([s.up(y), a], 1))
        return s.out(y)


def load(fs):
    """โหลดลงอาร์เรย์ที่จองไว้ก่อน (ไม่ต่อก้อน -> ไม่กินแรมสองเท่า)  ไฟล์ซ้ำ = ใช้ซ้ำโดยอ้างดัชนี"""
    uniq = list(dict.fromkeys(fs))
    sizes = {f: len(np.load(f, mmap_mode=None)["Y"]) for f in uniq}
    n = sum(sizes.values())
    X = np.empty((n, 240, 320, 3), np.uint8); Y = np.empty((n, 2, 120, 160), np.uint8)
    rng = {}; k = 0
    for f in uniq:
        d = np.load(f)
        m = sizes[f]; X[k:k + m] = d["X"]; Y[k:k + m] = d["Y"]; rng[f] = (k, k + m); k += m
        del d
        print("โหลด", f, m, flush=True)
    idx = np.concatenate([np.arange(*rng[f]) for f in fs])     # ไฟล์ที่ใส่ซ้ำ = สุ่มเจอบ่อยขึ้น
    return X, Y, idx


def aug(x, y):
    if random.random() < .5:
        x = x[:, ::-1]; y = y[:, :, ::-1]          # กลับซ้ายขวา (ทิศป้ายยังสัมพันธ์กับแถบเหมือนเดิม)
    if random.random() < .5:
        x = x[::-1, ::-1]; y = y[:, ::-1, ::-1]    # หมุน 180
    return np.ascontiguousarray(x), np.ascontiguousarray(y)


def loss_fn(lo, y):
    p = torch.sigmoid(lo)
    bce0 = F.binary_cross_entropy_with_logits(lo[:, 0], y[:, 0], pos_weight=torch.tensor(4.0))
    inter = (p[:, 0] * y[:, 0]).sum((1, 2)); den = p[:, 0].sum((1, 2)) + y[:, 0].sum((1, 2))
    dice = 1 - (2 * inter + 1) / (den + 1)
    bce1 = F.binary_cross_entropy_with_logits(lo[:, 1], y[:, 1], pos_weight=torch.tensor(3.0))
    return bce0 + dice.mean() + 0.5 * bce1


if __name__ == "__main__":
    X, Y, pool = load(FILES)
    n = len(X); perm = np.random.permutation(n); nval = 400
    va = perm[:nval]; vset = set(va.tolist())
    tr = np.array([i for i in pool if i not in vset])
    net = Det(); opt = torch.optim.AdamW(net.parameters(), 3e-3, weight_decay=1e-4)
    B = 24; steps = EP * (len(tr) // B)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=steps)
    t0 = time.time()
    for ep in range(EP):
        net.train(); np.random.shuffle(tr); tot = 0
        for k in range(len(tr) // B):
            bi = tr[k * B:(k + 1) * B]
            xs, ys = zip(*(aug(X[i], Y[i]) for i in bi))
            x = torch.tensor(np.stack(xs)).permute(0, 3, 1, 2).float()
            y = torch.tensor(np.stack(ys)).float()
            l = loss_fn(net(x), y)
            opt.zero_grad(); l.backward(); opt.step(); sched.step(); tot += l.item()
        net.eval(); iou = []
        with torch.no_grad():
            for k in range(0, nval, 50):
                bi = va[k:k + 50]
                p = torch.sigmoid(net(torch.tensor(X[bi]).permute(0, 3, 1, 2).float()))[:, 0] > .5
                y = torch.tensor(Y[bi][:, 0]).bool()
                for a, b in zip(p, y):
                    u = (a | b).sum().item()
                    if u: iou.append((a & b).sum().item() / u)
        print(f"ep {ep+1}/{EP} loss {tot/(len(tr)//B):.3f} val IoU แถบ {np.mean(iou):.3f} [{time.time()-t0:.0f}s]", flush=True)
        torch.save(net.state_dict(), OUT + ".pt")
    net.eval()
    torch.onnx.export(net, torch.zeros(1, 3, 240, 320), OUT, opset_version=11,
                      input_names=["x"], output_names=["y"], dynamo=False)
    print("saved", OUT)
