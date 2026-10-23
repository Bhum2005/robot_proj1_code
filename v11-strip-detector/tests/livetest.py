"""ทดสอบภาพสดแบบ WebSocket + ความหน่วงต่อคำขอ (ต.ค. 69)

เคสที่ทดสอบมาจากอาการจริง "แล็คมากแม้ต่อ Pi ตรง":
  1. คำขอเล็ก ๆ (/status /drive) ต้องไม่ติดหน่วง 40ms จาก Nagle + delayed ACK
  2. WebSocket ต่อ Pi ตรงได้ทั้งด้วยรหัส และด้วยกุญแจในหน้าเว็บ กุญแจผิดต้องเข้าไม่ได้
  3. คนดูเร็ว: ได้ใกล้เพดาน fps
  4. คนดูไม่ตอบรับ: หุ่นต้องหยุดส่งที่ 2 ใบ (ไม่กองท่อ)
  5. คนดูช้า: ได้ใบล่าสุดเสมอ (เลขกระโดด) ความหน่วงฝั่ง Pi ต่ำ
  6. ผ่าน hub: ภาพมา คำสั่งขับในสายเดียวกันไปถึงหุ่นจริง
  7. ปิดสายแล้วไม่มีสายค้าง

    python3 tests/livetest.py http://127.0.0.1:9340 http://127.0.0.1:8250
"""
import base64
import hashlib
import json
import os
import socket
import statistics
import struct
import subprocess
import sys
import time
import http.client
import urllib.request
from http.cookiejar import CookieJar

PI = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9340"
HUB = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8250"
USER, PW = "admin", "12345678"
AUTH = "Basic " + base64.b64encode(("%s:%s" % (USER, PW)).encode()).decode()
TOKEN = hashlib.sha256(("ws|%s|%s" % (USER, PW)).encode()).hexdigest()[:32]
ok = fail = 0


def check(label, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ok   %s" % label)
    else:
        fail += 1
        print("  FAIL %s   %s" % (label, extra))


def hostport(url):
    hp = url.split("://", 1)[1].rstrip("/")
    h, _, p = hp.partition(":")
    return h, int(p or 80)


class WS:
    def __init__(self, base, path, headers=None):
        h, p = hostport(base)
        self.s = socket.create_connection((h, p), timeout=5)
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ["GET %s HTTP/1.1" % path, "Host: %s:%d" % (h, p),
               "Upgrade: websocket", "Connection: Upgrade",
               "Sec-WebSocket-Key: " + key, "Sec-WebSocket-Version: 13"]
        for k, v in (headers or {}).items():
            req.append("%s: %s" % (k, v))
        self.s.sendall(("\r\n".join(req) + "\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            c = self.s.recv(4096)
            if not c:
                break
            buf += c
        head, _, self.rest = buf.partition(b"\r\n\r\n")
        self.status = int(head.split(b" ")[1]) if head else 0

    def _recvn(self, n):
        while len(self.rest) < n:
            c = self.s.recv(65536)
            if not c:
                raise EOFError
            self.rest += c
        d, self.rest = self.rest[:n], self.rest[n:]
        return d

    def recv(self, timeout=3):
        self.s.settimeout(timeout)
        h = self._recvn(2)
        op, n = h[0] & 15, h[1] & 127
        if n == 126:
            n = struct.unpack("!H", self._recvn(2))[0]
        elif n == 127:
            n = struct.unpack("!Q", self._recvn(8))[0]
        return op, self._recvn(n)

    def send(self, text):
        d = text.encode()
        m = os.urandom(4)
        self.s.sendall(struct.pack("!BB", 0x81, 0x80 | len(d)) + m +
                       bytes(b ^ m[i & 3] for i, b in enumerate(d)))

    def frame(self, timeout=3):
        """เฟรมภาพถัดไป -> (seq, ขนาด jpeg) ข้ามข้อความตัวอักษร"""
        while True:
            op, d = self.recv(timeout)
            if op == 2:
                self.last_ft = struct.unpack("!d", d[4:12])[0]   # เวลาเข้ารหัสบน Pi
                return struct.unpack("!I", d[:4])[0], len(d) - 12, d
            if op == 8:
                raise EOFError

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def get_json(base, path, extra=None):
    h, p = hostport(base)
    c = http.client.HTTPConnection(h, p, timeout=10)
    c.request("GET", path, headers=extra or {"Authorization": AUTH})
    r = c.getresponse()
    return json.loads(r.read())


def latency(base, path, headers, n=30):
    h, p = hostport(base)
    c = http.client.HTTPConnection(h, p, timeout=10)
    ts = []
    for _ in range(n):
        t = time.perf_counter()
        c.request("GET", path, headers=headers)
        c.getresponse().read()
        ts.append((time.perf_counter() - t) * 1000)
    c.close()
    return statistics.median(ts)


# ---- เตรียมคุกกี้เจ้าของหอสำหรับทางผ่าน hub ----
cj = CookieJar()
hop = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
req = urllib.request.Request(HUB + "/api/login", method="POST",
                             data=json.dumps({"role": "owner",
                                              "password": "testowner123"}).encode())
req.add_header("Content-Type", "application/json")
hop.open(req, timeout=10).read()
COOKIE = "; ".join("%s=%s" % (c.name, c.value) for c in cj)

print("1. คำขอเล็กต้องไม่ติดหน่วงของ Nagle (เดิม 44ms คงที่)")
d_pi = latency(PI, "/drive?l=0&r=0", {"Authorization": AUTH})
s_pi = latency(PI, "/status", {"Authorization": AUTH})
s_hub = latency(HUB, "/status", {"Cookie": COOKIE})
print("     Pi /drive %.1fms  Pi /status %.1fms  hub /status %.1fms"
      % (d_pi, s_pi, s_hub))
check("/drive ตรง < 15ms", d_pi < 15, d_pi)
check("/status ตรง < 15ms", s_pi < 15, s_pi)
check("/status ผ่าน hub < 25ms", s_hub < 25, s_hub)

print("\n2. เปิดสายภาพสด")
w = WS(PI, "/ws?id=lt1", {"Authorization": AUTH})
check("ด้วยรหัส Basic ได้ 101", w.status == 101, w.status)
w.close()
w = WS(PI, "/ws?id=lt1&t=" + TOKEN)
check("ด้วยกุญแจในหน้าเว็บได้ 101 (Safari ไม่แนบรหัสให้)", w.status == 101,
      w.status)
w.close()
w = WS(PI, "/ws?id=lt1&t=wrong")
check("กุญแจผิดเข้าไม่ได้ (401)", w.status == 401, w.status)
w.close()
w = WS(PI, "/ws?id=lt1")
check("ไม่มีอะไรเลยเข้าไม่ได้ (401)", w.status == 401, w.status)
w.close()
# หน้าเว็บต้องมีกุญแจฝังอยู่จริง
h, p = hostport(PI)
c = http.client.HTTPConnection(h, p, timeout=10)
c.request("GET", "/", headers={"Authorization": AUTH})
page = c.getresponse().read().decode()
check("หน้าเว็บฝังกุญแจแล้ว ไม่เหลือ __WS_TOKEN__",
      TOKEN in page and "__WS_TOKEN__" not in page)

print("\n3. คนดูเร็ว ต่อ Pi ตรง")
st = get_json(PI, "/status")
cap = min(st["streamFps"], st.get("camFps", 30))
w = WS(PI, "/ws?id=lt3&win=2", {"Authorization": AUTH})
n, t0, sizes = 0, time.time(), []
while time.time() - t0 < 3:
    seq, size, _ = w.frame()
    sizes.append(size)
    w.send("a")
    n += 1
fps = n / (time.time() - t0)
print("     ได้ %.1f fps (เพดาน %s) เฟรมละ %d ไบต์" % (fps, cap, sizes[-1]))
check("ใกล้เพดาน fps (>= 80%)", fps >= cap * 0.8, "%.1f" % fps)
check("ภาพเป็น JPEG", sizes and sizes[-1] > 1000)
age = (time.time() - w.last_ft) * 1000
check("หัวเฟรมมีเวลาเข้ารหัสจริง (อายุ 0-500 ms)", 0 <= age < 500, "%.0f ms" % age)
st2 = get_json(PI, "/status")
check("/status บอกนาฬิกา Pi (srvTime)", abs(st2.get("srvTime", 0) - time.time()) < 2,
      st2.get("srvTime"))
tx = get_json(PI, "/status?id=lt3").get("txN") or 0
check("ตอบรับไปนับเป็น txN ของยามเฝ้า", tx >= n - 2, (tx, n))

print("\n4. คนดูไม่ตอบรับ -> หุ่นหยุดส่งที่ 2 ใบ")
w2 = WS(PI, "/ws?id=lt4&win=2", {"Authorization": AUTH})
got = 0
try:
    while True:
        w2.frame(timeout=1.5)
        got += 1
except (socket.timeout, EOFError):
    pass
check("ได้ไม่เกิน 2 ใบแล้วหยุด", got == 2, got)
w2.send("a")
try:
    w2.frame(timeout=1.5)
    resumed = True
except (socket.timeout, EOFError):
    resumed = False
check("ตอบรับหนึ่งใบ ได้ใบใหม่ต่อทันที", resumed)
w2.close()

print("\n5. คนดูช้า (ใช้เวลาแสดงใบละ 400ms)")
jumps, last = [], None
for _ in range(6):
    seq, _, _ = w.frame()
    if last is not None:
        jumps.append(seq - last)
    last = seq
    time.sleep(0.4)
    w.send("a")
st = get_json(PI, "/status")
print("     เลขเฟรมกระโดด %s | lagMs %s" % (jumps, st["lagMs"]))
check("ได้ภาพใหม่ ไม่ใช่ภาพคิวเก่า (กระโดด >= 3 เกือบทุกครั้ง)",
      sorted(jumps)[1] >= 3, jumps)
check("ความหน่วงฝั่ง Pi ต่ำ (< 200ms)", st["lagMs"] < 200, st["lagMs"])
w.close()

print("\n6. ผ่าน hub (หน้าเจ้าของหอ)")
w = WS(HUB, "/ws?id=lt6&win=2", {"Cookie": COOKIE})
check("hub ส่งต่อการจับมือได้ 101", w.status == 101, w.status)
n, t0 = 0, time.time()
while time.time() - t0 < 3:
    w.frame()
    w.send("a")
    n += 1
fps = n / (time.time() - t0)
print("     ผ่าน hub ได้ %.1f fps" % fps)
check("ผ่าน hub ใกล้เพดาน fps (>= 80%)", fps >= cap * 0.8, "%.1f" % fps)
w.send("d120,-80")
time.sleep(0.15)
st = get_json(PI, "/status")
check("คำสั่งขับในสายภาพไปถึงหุ่น", (st["cmdL"], st["cmdR"], st["src"]) ==
      (120, -80, "web"), (st["cmdL"], st["cmdR"], st["src"]))
w.send("d0,0")
w.send("n5,0")
arm = None
t0 = time.time()
while time.time() - t0 < 2:
    op, d = w.recv()
    if op == 1:
        arm = json.loads(d).get("arm")
        break
    w.send("a")
check("สั่งแขนในสายภาพ ได้มุมตอบกลับทางสายเดียวกัน", arm and "pan" in arm, arm)
w.close()
w = WS(HUB, "/ws?id=lt6b")
check("ไม่ได้ล็อกอิน hub ไม่ให้ผ่าน", w.status in (401, 404), w.status)
w.close()

print("\n7. ปิดแล้วไม่มีสายค้าง")
time.sleep(1.5)
port = hostport(PI)[1]
out = subprocess.run(
    ["bash", "-c", "ss -tn state established '( dport = :%d )' 2>/dev/null "
     "| tail -n +2 | wc -l" % port], capture_output=True, text=True).stdout.strip()
check("ไม่มีสายค้างกับ Pi", out == "0", "เหลือ %s เส้น" % out)

print("\n7.1 เล่นวิดีโอ WebRTC อยู่: สั่งหยุด JPEG ได้ และกลับมาส่งต่อได้")
w = WS(PI, "/ws?id=lt71", {"Authorization": AUTH})
w.frame(); w.send("a")
w.send("v0")
time.sleep(0.3)
got = 0
try:
    while True:                         # เก็บใบที่ค้างท่อก่อนสั่งหยุด
        w.frame(timeout=0.3)
except (socket.timeout, EOFError):
    pass
try:
    w.frame(timeout=1.5)
    stopped = False
except (socket.timeout, EOFError):
    stopped = True
check("v0 แล้ว JPEG หยุดส่ง", stopped)
w.send("d50,50")
time.sleep(0.15)
st = get_json(PI, "/status")
check("หยุด JPEG แล้วคำสั่งขับยังใช้ได้", (st["cmdL"], st["cmdR"]) == (50, 50),
      (st["cmdL"], st["cmdR"]))
w.send("d0,0")
w.send("v1")
try:
    w.frame(timeout=2)
    resumed = True
except (socket.timeout, EOFError):
    resumed = False
check("v1 แล้ว JPEG กลับมาทันที", resumed)
w.close()
check("/status บอกสถานะวิดีโอ (webrtc)", "webrtc" in st, list(st)[:5])

print("\n8. ตัวส่งรูปต้องไม่แย่งท่อภาพสด")
import tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
flag = "/dev/shm/robot-live" if os.path.isdir("/dev/shm") else "/tmp/robot-live"
w = WS(PI, "/ws?id=lt8", {"Authorization": AUTH})
for _ in range(5):
    w.frame(); w.send("a")
time.sleep(0.2)
age = time.time() - os.path.getmtime(flag) if os.path.exists(flag) else 99
check("หุ่นแตะไฟล์บอกว่ามีคนดูภาพสดอยู่", age < 2, "%.1f วิ" % age)
w.close()
td = tempfile.mkdtemp()
pf = os.path.join(td, "flag")


def push_time(name, live_now):
    with open(os.path.join(td, name), "wb") as f:
        f.write(b"\xff\xd8" + os.urandom(120000) + b"\xff\xd9")
    if live_now:
        open(pf, "a").close(); os.utime(pf, None)
    elif os.path.exists(pf):
        os.remove(pf)
    t = time.time()
    r = subprocess.run(["python3", os.path.join(ROOT, "pi", "push.py"), "--to", HUB,
                        "--token", "tok-test", "--dir", td, "--state",
                        os.path.join(td, "st.json"), "--once", "--live-kbps", "400"],
                       capture_output=True, text=True,
                       env=dict(os.environ, ROBOT_LIVE_FLAG=pf))
    return time.time() - t, r


t_idle, r1 = push_time("shot_20261015_100000.jpg", False)
t_live, r2 = push_time("shot_20261015_100001.jpg", True)
print("     ส่งรูป 120KB: ไม่มีคนดู %.1f วิ / มีคนดู %.1f วิ" % (t_idle, t_live))
check("ไม่มีคนดู ส่งเต็มที่ (< 2 วิ)", t_idle < 2, (t_idle, r1.stderr[-200:]))
check("มีคนดู ส่งช้าลงตามเพดาน 400kbit/s (>= 2 วิ)", t_live >= 2, t_live)
st = json.load(open(os.path.join(td, "st.json")))
check("จดสถานะครบทุกใบ", len(st) == 2, st)

print("\n%d ผ่าน, %d ไม่ผ่าน" % (ok, fail))
sys.exit(1 if fail else 0)
