"""รูปใหม่ขึ้น hub เร็ว + AI มั่นใจ >= 75% ใส่ค่าให้เลย  (ใช้กับ tests/fastpush.sh)
    python3 tests/fastpush.py <pi_url> <photos> <hub_url> <hub_dir> <live_flag>
push.py รันค้างอยู่เบื้องหลังแบบของจริง (รอบ 20 วิ) — วัดว่ารูปขึ้นเร็วเพราะถูกปลุก ไม่ใช่เพราะรอบพอดี"""
import glob, json, os, sys, threading, time, urllib.request, urllib.error, http.cookiejar

PI, PHOTOS, HUB, HUBDIR, LIVE = sys.argv[1:6]
ok = fail = 0


def check(label, cond, extra=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print(("  ok   " if cond else "  FAIL ") + label + ("" if cond else f"   {extra}"))


pm = urllib.request.HTTPPasswordMgrWithDefaultRealm()
pm.add_password(None, PI, "admin", "12345678")
pi = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(pm))
hub = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def pget(path):
    with pi.open(PI + path, timeout=60) as r:
        return json.loads(r.read())


def hpost(path, body):
    rq = urllib.request.Request(HUB + path, data=json.dumps(body).encode(), method="POST",
                                headers={"Content-Type": "application/json"})
    with hub.open(rq, timeout=10) as r:
        return json.loads(r.read())


def hget(path):
    with hub.open(HUB + path, timeout=10) as r:
        return json.loads(r.read())


def hmeta(name):
    p = os.path.join(HUBDIR, "meta", name + ".json")
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def wait(fn, secs):
    t = time.time()
    while time.time() - t < secs:
        v = fn()
        if v:
            return time.time() - t, v
        time.sleep(0.3)
    return None, fn()


hpost("/api/login", {"role": "owner", "password": "testowner123"})
hpost("/api/owner/add-room", {"room": "104"})
pget("/ctx?room=104&kind=power&ask=0")
time.sleep(25)          # ให้ push.py ผ่านรอบแรก (รูปเก่าที่มีอยู่) แล้วไปนอนรอรอบ 20 วิ

print("1. ถ่ายตอนไม่มีคนดูภาพสด -> รูปเต็มขึ้น hub ภายในไม่กี่วิ (ไม่ต้องรอรอบ 20 วิ)")
v0 = hget("/api/owner/ver")["ver"]
name = pget("/photo")["name"]
t, m = wait(lambda: hmeta(name).get("name") and not hmeta(name).get("preview") and hmeta(name), 15)
print(f"     ขึ้นใน {t if t is None else round(t, 1)} วิ")
check("รูปขึ้น hub ภายใน 8 วิ", t is not None and t < 8, (t, m))
check("เลขรุ่นข้อมูลเปลี่ยน (หน้าเจ้าของหอจะโหลดเอง)", hget("/api/owner/ver")["ver"] != v0)
full = os.path.getsize(os.path.join(PHOTOS, name))
check("เป็นรูปเต็ม (ขนาดตรงกับบน Pi)", m.get("size") == full, (m.get("size"), full))

print("2. AI มั่นใจ >= 75% + ครบ 4 หลัก -> ขึ้นเป็นค่าจริงเลย")
t, m = wait(lambda: hmeta(name).get("reading") and hmeta(name), 15)
ai = m.get("ai") or {}
print(f"     AI {ai}  reading={m.get('reading')} rsrc={m.get('rsrc')}")
check("AI อ่าน 2045 มั่นใจ >= 0.75", ai.get("guess") == "2045" and ai.get("conf", 0) >= 0.75, ai)
check("ค่าจริง = 2045 ใส่โดย AI", m.get("reading") == "2045" and m.get("rsrc") == "ai", m)
top = [r for r in hget("/api/owner/room?room=104")["readings"]["power"]
       if r["month"] == time.strftime("%Y-%m")]
check("ช่องไฟข้างบน = 2045 (ติดป้ายว่าค่าจาก AI)", top and top[0]["value"] == 2045 and top[0]["src"] == "ai", top)

print("3. คนยืนยันค่าอื่นบนหุ่น -> ทับค่าที่ AI ใส่ได้")
pget("/tag?f=" + name + "&room=104&kind=power&reading=2046")
t, m = wait(lambda: hmeta(name).get("reading") == "2046" and hmeta(name), 10)
check("ค่าจากคนบนหุ่นทับค่า AI (2046, rsrc robot)", m and m.get("rsrc") == "robot", hmeta(name))
r = hpost("/api/owner/set-photo", {"name": name, "room": "104", "kind": "power", "reading": "2046"})
check("เจ้าของหอกดบันทึกค่าเดิม -> นับเป็นเจ้าของหอตรวจแล้ว", hmeta(name).get("rsrc") in ("owner", "robot"), hmeta(name))

print("4. ไม่ได้บอกชนิดมิเตอร์ -> AI ดูรูปทรง (ทรงกระบอก = น้ำ) แล้วใส่ชนิด + ค่าให้")
pget("/ctx?room=104&kind=other&ask=0")
n2 = pget("/photo")["name"]
t, m = wait(lambda: hmeta(n2).get("reading") and hmeta(n2), 15)
ai = (m or hmeta(n2)).get("ai") or {}
check("AI บอกว่าเป็นมิเตอร์น้ำ มั่นใจ >= 0.75", ai.get("kind") == "water" and ai.get("kconf", 0) >= .75, ai)
check("hub ตั้งชนิด = น้ำ (ksrc ai) + ค่า 2045", m and m.get("kind") == "water" and m.get("ksrc") == "ai"
      and m.get("reading") == "2045", m or hmeta(n2))
r = hpost("/api/owner/set-photo", {"name": n2, "room": "104", "kind": "power"})
pget("/tag?f=" + n2 + "&room=104&kind=other")
time.sleep(4)
check("เจ้าของหอแก้ชนิดเป็นไฟเอง -> AI/หุ่นทับไม่ได้", hmeta(n2).get("kind") == "power", hmeta(n2))

print("5. มีคนดูภาพสด -> ส่งรูปย่อขนาดกลางก่อน แล้วรูปเต็มตามมาตอนเลิกดู")
pget("/ctx?room=104&kind=power&ask=0")
stop = threading.Event()


def viewer():
    while not stop.is_set():
        with open(LIVE, "a"):
            pass
        os.utime(LIVE, None)
        time.sleep(0.5)


th = threading.Thread(target=viewer, daemon=True)
th.start()
time.sleep(1)
n3 = pget("/photo")["name"]
t, m = wait(lambda: hmeta(n3).get("preview") and hmeta(n3), 20)
print(f"     รูปย่อขึ้นใน {t if t is None else round(t, 1)} วิ  ({(m or {}).get('size', 0) // 1024} KB)")
check("ระหว่างดูภาพสด การ์ดขึ้นภายใน 12 วิ (รูปย่อ)", t is not None and t < 12, (t, m))
check("รูปย่อเล็กกว่า 600 KB", m and m.get("size", 1 << 30) < 600 * 1024, m)
time.sleep(3)
check("ยังดูภาพสดอยู่ -> ยังไม่ส่งรูปเต็ม", hmeta(n3).get("preview") == 1, hmeta(n3))
stop.set()
t, m = wait(lambda: hmeta(n3).get("name") and not hmeta(n3).get("preview") and hmeta(n3), 40)
full = os.path.getsize(os.path.join(PHOTOS, n3))
print(f"     เลิกดูแล้วรูปเต็มตามมาใน {t if t is None else round(t, 1)} วิ")
check("เลิกดูภาพสด -> รูปเต็มตามมา (ขนาดเท่าบน Pi)", m and m.get("size") == full, (m, full))
check("ค่าจาก AI ยังอยู่หลังรูปเต็มมาแทน", hmeta(n3).get("reading") == "2045", hmeta(n3))

print(f"\n{ok} ผ่าน, {fail} ไม่ผ่าน")
sys.exit(1 if fail else 0)
