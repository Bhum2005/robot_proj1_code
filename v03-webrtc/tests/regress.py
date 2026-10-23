"""ทดสอบครบวงก่อนส่งไฟล์ — เน้นเส้นทางที่เคยพังจริง

เคสที่ใส่ไว้เพราะเคยพลาดมาแล้ว ไม่ใช่เคสที่คิดขึ้นเอง:
  1. ถ่ายรูปแล้วสตรีมต่อ -> ตัวเลขความหน่วงต้องไม่วิ่งหนี
  2. คนดูช้า -> ต้องข้ามเฟรม ไม่ใช่ไปรั้งให้ Pi ทิ้งเฟรม
  3. คนดูหายไปเฉย ๆ -> สายต้องถูกปิด ไม่ค้างสะสม
  4. ติดป้ายห้องทีหลัง -> ป้ายต้องไปถึงปลายทาง
  5. ภาพสดแบบขอทีละใบ -> ได้ใบล่าสุดเสมอ ไม่กองคิวจนค้าง
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from http.cookiejar import CookieJar

S = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(S)
PI = "http://127.0.0.1:9340"
HUB = "http://127.0.0.1:8250"
AUTH = ("admin", "12345678")
# ต้องเป็นโฟลเดอร์เดียวกับ --photos ที่ใช้สตาร์ท pi/server.py
PHOTOS = os.path.expanduser(os.environ.get("TEST_PHOTOS", "~/t_photos"))
ok = fail = 0


def check(label, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ok   %s" % label)
    else:
        fail += 1
        print("  FAIL %s   %s" % (label, extra))


def pi(path):
    m = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    m.add_password(None, PI, *AUTH)
    op = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(m))
    with op.open(PI + path, timeout=20) as r:
        b = r.read()
    try:
        return json.loads(b)
    except ValueError:
        return b


def stream_bytes(url, opener, seconds, rate=None):
    """อ่านสตรีมตามเวลาที่กำหนด rate = ไบต์/วินาทีถ้าอยากจำลองคนดูช้า"""
    got = frames = 0
    t0 = time.time()
    with opener.open(url, timeout=20) as r:
        while time.time() - t0 < seconds:
            chunk = r.read(16384)
            if not chunk:
                break
            got += len(chunk)
            frames += chunk.count(b"--FRAME")
            if rate:
                time.sleep(len(chunk) / float(rate))
    return got, frames


print("1. ความหน่วงต้องไม่วิ่งหนีหลังถ่ายรูป (บั๊กที่เพิ่งแก้)")
op = urllib.request.build_opener()
m = urllib.request.HTTPPasswordMgrWithDefaultRealm()
m.add_password(None, PI, *AUTH)
piop = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(m))
stream_bytes(PI + "/stream", piop, 2)
before = pi("/status")["lagMs"]
pi("/photo")
time.sleep(1)
stream_bytes(PI + "/stream", piop, 3)
mid = pi("/status")["lagMs"]
time.sleep(8)
stream_bytes(PI + "/stream", piop, 3)
after = pi("/status")["lagMs"]
print("     lagMs ก่อนถ่าย %s -> หลังถ่าย %s -> อีก 10 วิ %s"
      % (before, mid, after))
check("ไม่โตตามเวลา (ต่างกันไม่เกิน 2000 ms)", abs(after - mid) < 2000,
      "ต่าง %s" % abs(after - mid))

print("\n2. ผ่านตัวส่งต่อ: คนดูเร็วต้องได้เต็ม และ Pi ต้องไม่ต้องทิ้งเฟรม")
cj = CookieJar()
hop = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
req = urllib.request.Request(HUB + "/api/login", method="POST",
                             data=json.dumps({"role": "owner",
                                              "password": "testowner123"}).encode())
req.add_header("Content-Type", "application/json")
hop.open(req, timeout=10).read()
pi("/status")                       # ล้างตัวนับรอบก่อน
time.sleep(1.2)
got, fr = stream_bytes(HUB + "/stream", hop, 5)
st = pi("/status")
print("     ได้ %d เฟรม ใน 5 วิ | dropHz %s | lagMs %s"
      % (fr, st["dropHz"], st["lagMs"]))
check("ได้เฟรมใกล้เต็ม (>= 45 ใน 5 วิ ที่ 12fps)", fr >= 45, "ได้ %d" % fr)
check("Pi ไม่ต้องทิ้งเฟรม (dropHz < 2)", st["dropHz"] < 2, st["dropHz"])

print("\n3. คนดูช้า: ต้องข้ามเฟรม ไม่ใช่ไปรั้ง Pi")
got, fr = stream_bytes(HUB + "/stream", hop, 8, rate=120000)
st = pi("/status")
print("     คนดูช้าได้ %d เฟรม ใน 8 วิ | dropHz %s | lagMs %s"
      % (fr, st["dropHz"], st["lagMs"]))
check("ได้น้อยกว่าเต็ม แปลว่าข้ามเฟรมจริง", 0 < fr < 70, "ได้ %d" % fr)
check("Pi ยังไม่ต้องทิ้งเฟรม (dropHz < 3)", st["dropHz"] < 3, st["dropHz"])
check("ความหน่วงฝั่ง Pi ยังต่ำ (< 3000 ms)", st["lagMs"] < 3000, st["lagMs"])

print("\n4. คนดูเลิกดู: สายต้องถูกปิด ไม่ค้างสะสม")
time.sleep(3)
out = subprocess.run(
    ["bash", "-c",
     "ss -tn state established '( dport = :9340 )' 2>/dev/null | tail -n +2 | wc -l"],
    capture_output=True, text=True).stdout.strip()
check("ไม่มีสายค้างกับ Pi", out == "0", "เหลือ %s เส้น" % out)

print("\n5. ติดป้ายห้องทีหลังต้องไปถึงปลายทาง")
name = pi("/photo")["name"]
subprocess.run(["python3", os.path.join(ROOT, "pi", "push.py"), "--to", HUB,
                "--token", "tok-test", "--dir", PHOTOS,
                "--state", S + "/reg.json", "--once"],
               capture_output=True)
pi("/tag?f=%s&room=901&kind=power" % name)
time.sleep(1.1)
subprocess.run(["python3", os.path.join(ROOT, "pi", "push.py"), "--to", HUB,
                "--token", "tok-test", "--dir", PHOTOS,
                "--state", S + "/reg.json", "--once"],
               capture_output=True)
with hop.open(HUB + "/api/owner/photos?room=901", timeout=10) as r:
    rows = json.load(r)
check("รูปเข้าห้อง 901 หลังติดป้าย",
      any(x["name"] == name and x["kind"] == "power" for x in rows),
      [x["name"] for x in rows])

print("\n6. ภาพสดแบบขอทีละใบ (/frame) — ตัวแก้อาการค้างแม้ต่อ Pi ตรง")


def pull(opener, base, after):
    with opener.open("%s/frame?id=rg&after=%d" % (base, after), timeout=10) as r:
        return r.status, r.headers.get("X-Frame-Seq"), r.read()


s, seq, body = pull(piop, PI, 0)
check("ต่อ Pi ตรง ได้ภาพพร้อมเลขเฟรม",
      s == 200 and len(body) > 1000 and seq is not None, (s, seq))
s2, seq2, _ = pull(piop, PI, int(seq or 0))
check("ขอ after=เลขเดิม ได้เฟรมที่ใหม่กว่าเสมอ ไม่ซ้ำใบเดิม",
      s2 == 200 and int(seq2 or 0) > int(seq or 0), (seq, seq2))

s, seq, body = pull(hop, HUB, 0)
check("ผ่านตัวส่งต่อ เลขเฟรมยังมาถึงเบราว์เซอร์ (X-Frame-Seq)",
      s == 200 and seq is not None and len(body) > 1000, (s, seq))

# คนดูเร็ว: ดึงต่อกันรัว ๆ ต้องได้ใกล้ fps ของกล้อง
t0, n, last = time.time(), 0, int(seq or 0)
while time.time() - t0 < 4:
    s, q, _ = pull(hop, HUB, last)
    if s == 200:
        n, last = n + 1, int(q)
check("คนดูเร็วผ่านตัวส่งต่อได้ใกล้เต็ม (>= 30 ใน 4 วิ ที่ 12fps)", n >= 30,
      "ได้ %d" % n)

# คนดูช้า (จอแสดงใบละ 400ms): ต้องได้ "ใบล่าสุด" ข้ามใบเก่า ไม่ใช่ได้ทีละใบตามคิว
jumps = []
for _ in range(6):
    time.sleep(0.4)
    s, q, _ = pull(hop, HUB, last)
    if s == 200:
        jumps.append(int(q) - last)
        last = int(q)
st = pi("/status")
print("     คนดูช้า เลขเฟรมกระโดดทีละ %s | lagMs %s" % (jumps, st["lagMs"]))
check("คนดูช้าได้เฟรมล่าสุดเสมอ (เลขกระโดด >= 3 ทุกครั้ง)",
      jumps and min(jumps) >= 3, jumps)
check("ความหน่วงฝั่ง Pi ยังต่ำ (< 500 ms)", st["lagMs"] < 500, st["lagMs"])
check("ตัวนับ txN ของยามเฝ้าเดินตามเฟรมที่ดึงไป",
      (pi("/status?id=rg").get("txN") or 0) >= n, pi("/status?id=rg").get("txN"))

print("\n[6] ตัวเข้ารหัส H.264 ต้องเปิด sliced-threads (ไม่กักเฟรม 5 เฟรม = 200 ms)")
import ast  # noqa: E402
src = open(os.path.join(ROOT, "pi", "server.py"), encoding="utf-8").read()
fn = next(n for n in ast.parse(src).body
          if isinstance(n, ast.FunctionDef) and n.name == "lowlat_h264")
ns = {"os": os}
exec(compile(ast.Module([fn], []), "lowlat_h264", "exec"), ns)


class _CC:
    def __init__(self):
        self.options = {}


class _Base:                       # หน้าตาเหมือน LibavH264Encoder ของ picamera2
    def __init__(self, **kw):
        self.kw = kw

    def _start(self):
        self._stream = type("S", (), {})()
        self._stream.codec_context = _CC()
        self._stream.codec_context.options["preset"] = "ultrafast"


e = ns["lowlat_h264"](_Base)(bitrate=1)
e._start()
o = e._stream.codec_context.options
check("ตั้ง x264-params sliced-threads=1", o.get("x264-params") == "sliced-threads=1", o)
check("ยังคง preset ของ picamera2 + tune zerolatency",
      o.get("preset") == "ultrafast" and o.get("tune") == "zerolatency", o)
os.environ["ROBOT_H264_SLICED"] = "0"
check("ROBOT_H264_SLICED=0 ย้อนกลับเป็นตัวเดิม", ns["lowlat_h264"](_Base) is _Base)
del os.environ["ROBOT_H264_SLICED"]

print("\n%d ผ่าน, %d ไม่ผ่าน" % (ok, fail))
sys.exit(1 if fail else 0)
