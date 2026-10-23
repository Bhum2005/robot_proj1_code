"""เทรนโมเดลอ่านเลข 4 หลัก  อินพุต/เอาต์พุตเหมือนตัวเดิม: (1,1,40,160) -> 40 logits (4x10)
argv: strips_dir frames_dir train_clips val_clips out.onnx epochs"""
import sys, os, glob, random, time, cv2, numpy as np, torch, torch.nn as nn, torch.nn.functional as Fn
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data, fonts
TRAIN_FONTS, _EVAL_FONTS = fonts.split()        # ★ ฟอนต์ฝั่งสอบห้ามใช้เทรน (ดู evalfonts.py)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pi"))
from meter_ai.preprocess import paper_to_white as P2W
torch.set_num_threads(2); random.seed(0); np.random.seed(0); torch.manual_seed(0)
SD, FD, TR, VA, OUT, EP = sys.argv[1], sys.argv[2], set(sys.argv[3].split(",")), set(sys.argv[4].split(",")) - {""}, sys.argv[5], int(sys.argv[6])

def prep(g):                                                     # เหมือน meter_ai.preprocess
    g = g.astype(np.float32); return (g - g.mean()) / max(float(g.std()), 1.0)

class Net(nn.Module):
    def __init__(s):
        super().__init__()
        def blk(i, o): return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU())
        s.f = nn.Sequential(blk(1, 32), nn.MaxPool2d(2), blk(32, 64), nn.MaxPool2d(2),
                            blk(64, 96), nn.MaxPool2d(2), blk(96, 128), nn.MaxPool2d((5, 1)))   # -> 128x1x20
        s.h = nn.Sequential(nn.Flatten(), nn.Dropout(0.3), nn.Linear(128 * 20, 256), nn.ReLU(), nn.Linear(256, 40))
    def forward(s, x): return s.h(s.f(x))

pos, junk = data.load_real(SD, TR)
# ★ v2: แถบจริงที่ใช้สอนต้อง "อ่านออกจริง" — ป้ายของแถบเลือน ๆ มาจากการเดาจากชุด 6 เลข
#   ถ้าเอามาสอน โมเดลจะเรียนการเดาเลขที่จำได้แทนการอ่าน (เจอแล้วในรอบแรก)
def ham(a, b): return sum(x != y for x, y in zip(a, b))
lowq = [g for g, l, r in pos if r["sharp"] < 30]
pos = [p for p in pos if p[2]["sharp"] >= 60 and ham(p[2]["free"], p[1]) <= 1]
pool = data.cells_of(pos)
frames = [f for c in TR for f in glob.glob(f"{FD}/{c}/f_*.jpg")]
val = data.load_real(SD, VA)[0] if VA else []
print(f"train real {len(pos)}  lowq {len(lowq)}  junk {len(junk)}  val {len(val)}", flush=True)
EV = np.load(os.environ.get("EVALSETS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "meter", "evalsets_c4.npz")))

def heavy_blur(g):
    if random.random() < .5: return cv2.GaussianBlur(g, (0, 0), random.uniform(3.5, 6))
    k = random.randint(15, 25); ker = np.zeros((k, k), np.float32); ker[k // 2] = 1 / k
    ker = cv2.warpAffine(ker, cv2.getRotationMatrix2D((k / 2, k / 2), random.uniform(0, 180), 1), (k, k))
    return cv2.filter2D(g, -1, ker / max(ker.sum(), 1e-6))

LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"
def sample():
    r = random.random()
    if r < .85:
        g, lab, colored = _pos()
        if r >= .78: g, lab = heavy_blur(g), None          # เบลอจนอ่านไม่ออก -> ห้ามมั่นใจ
        g = data.augment(g)
        if not colored and random.random() < .2:            # v3: หน้าตาหลังแปลงกระดาษสี (paper_to_white)
            g = data.gray(P2W(cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)))
        return prep(g), lab
    j = random.random()
    if j < .3:      # v4: แถบสีที่ไม่ใช่ตัวเลข (ตัวอักษร เช่น REAI / กระดาษเปล่า) -> ห้ามมั่นใจ
        txt = "REAI" if random.random() < .3 else "".join(random.choice(LETTERS + "    ") for _ in range(4))
        return prep(data.augment(data.as_model_view(data.render_color(txt, TRAIN_FONTS), P2W))), None
    g = random.choice(lowq) if (lowq and j < .4) else (random.choice(junk) if junk and j < .55 else data.bg_crops(frames, 1)[0])
    return prep(data.augment(g)), None

def _pos():
    r = random.random()
    if r < .2: g, lab = random.choice(pos)[:2]
    elif r < .45:
        lab = "".join(random.choice([d for d in "0123456789" if d in pool]) for _ in range(4))
        g = data.recompose(random.choice(pos)[0], pool, lab)
    elif r < .58:
        lab = "".join(random.choice("0123456789") for _ in range(4)); g = data.render(lab)
    else:           # v4: สีสุ่มทุกส่วน + ฟอนต์ ~180 ไฟล์ + 7 ส่วน + ล้อตัวเลข
        lab = "".join(random.choice("0123456789") for _ in range(4))
        return data.as_model_view(data.render_color(lab, TRAIN_FONTS), P2W), lab, True
    return g, lab, False

net = Net(); opt = torch.optim.AdamW(net.parameters(), 2e-3, weight_decay=1e-4)
N = 16000; steps = EP * (N // 64); sched = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=steps)
def evaluate():
    if not val: return ""
    net.eval(); ok = sug = bad = 0
    with torch.no_grad():
        for i in range(0, len(val), 256):
            b = val[i:i + 256]; x = torch.tensor(np.stack([prep(g) for g, _, _ in b]))[:, None]
            p = Fn.softmax(net(x).view(-1, 4, 10), -1); conf = p.max(-1).values.prod(-1); pr = p.argmax(-1)
            for j, (_, lab, _) in enumerate(b):
                d = "".join(map(str, pr[j].tolist())); ok += d == lab
                if conf[j] >= .6: sug += 1; bad += d != lab
    res = f"val {ok/len(val):.1%} wrong {bad}"
    with torch.no_grad():
        for k in ("A", "B", "C"):
            x = torch.tensor(np.stack([prep(g) for g in EV[k]]))[:, None]
            p = Fn.softmax(net(x).view(-1, 4, 10), -1); conf = p.max(-1).values.prod(-1); pr = p.argmax(-1)
            d = ["".join(map(str, q.tolist())) for q in pr]
            if k == "C": res += f" | C แนะนำ {(conf >= .6).sum().item()}/{len(d)}"; continue
            L = EV[k + "l"]; ok = sum(a == b for a, b in zip(d, L))
            res += f" | {k} {ok/len(L):.1%} ผิด {sum(bool(c >= .6) and a != b for a, b, c in zip(d, L, conf))}"
    EF = os.environ.get("EVALFONTS")
    if EF:
        d = np.load(EF); best_d, best_c = None, None
        with torch.no_grad():
            for view in (lambda im: data.gray(im), lambda im: data.gray(P2W(im))):
                x = torch.tensor(np.stack([prep(view(im)) for im in d["X"]]))[:, None]
                p = Fn.softmax(net(x).view(-1, 4, 10), -1); c = p.max(-1).values.prod(-1); pr = p.argmax(-1)
                if best_c is None: best_c, best_d = c, pr
                else:
                    m = c > best_c; best_c = torch.where(m, c, best_c); best_d = torch.where(m[:, None], pr, best_d)
        dd = ["".join(map(str, q.tolist())) for q in best_d]
        okf = sum(a == b for a, b in zip(dd, d["L"]))
        w75 = sum(bool(c >= .75) and a != b for a, b, c in zip(dd, d["L"], best_c))
        res += f" | ฟอนต์ใหม่ {okf/len(dd):.1%} ใส่ให้ {(best_c >= .75).float().mean():.1%} ผิด {w75}"
    net.train(); return res
t0 = time.time()
for ep in range(EP):
    tot = 0
    for it in range(N // 64):
        xs, ys, js = [], [], []
        for _ in range(64):
            x, lab = sample(); xs.append(x)
            ys.append([int(c) for c in lab] if lab else [0] * 4); js.append(lab is None)
        x = torch.tensor(np.stack(xs))[:, None]; y = torch.tensor(ys); jk = torch.tensor(js)
        lp = Fn.log_softmax(net(x).view(-1, 4, 10), -1)
        ce = -(0.95 * lp.gather(-1, y[..., None])[..., 0] + 0.05 * lp.mean(-1)).sum(-1)   # label smoothing 5%
        uni = -lp.mean(-1).sum(-1)                                     # ภาพขยะ: ให้กระจายเท่ากันทุกเลข
        loss = torch.where(jk, uni, ce).mean()
        opt.zero_grad(); loss.backward(); opt.step(); sched.step(); tot += loss.item()
    print(f"ep {ep+1}/{EP} loss {tot/(N//64):.3f}  {evaluate()}  [{time.time()-t0:.0f}s]", flush=True)
net.eval(); torch.save(net.state_dict(), OUT + ".pt")
torch.onnx.export(net, torch.zeros(1, 1, 40, 160), OUT, opset_version=11, input_names=["x"], output_names=["y"], dynamo=False)
print("saved", OUT)
