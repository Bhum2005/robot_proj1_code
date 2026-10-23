"""ทดสอบ AI อ่านเลขมิเตอร์ "ทั้งสาย": กดถ่าย -> AI อ่าน -> คนยืนยัน -> ไฟล์ข้อมูล -> push.py -> hub

    python3 tests/aitest.py <pi_url> <photos_dir> <hub_url> <hub_dir> <mode>
mode: on   = มี AI (ภาพนิ่งจำลองเป็นรูปมิเตอร์ 2045 ขนาด 64MP)
      off  = ROBOT_METER_AI=0  ต้องถ่ายได้ปกติ แค่ไม่มีค่าแนะนำ
      nocv = ไม่มี opencv บน Pi  ต้องถ่ายได้ปกติ แค่ไม่มีค่าแนะนำ
"""
import glob
import json
import os
import subprocess
import sys
import time
import urllib.request

PI, PHOTOS, HUB, HUBDIR, MODE = sys.argv[1:6]
AUTH = ("admin", "12345678")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = fail = 0


def check(label, cond, extra=""):
    global ok, fail
    ok += bool(cond)
    fail += not cond
    print(("  ok   " if cond else "  FAIL ") + label + ("" if cond else f"   {extra}"))


m = urllib.request.HTTPPasswordMgrWithDefaultRealm()
m.add_password(None, PI, *AUTH)
op = urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(m))


def get(path, raw=False):
    with op.open(PI + path, timeout=30) as r:
        b = r.read()
        return (b, r.headers.get("Content-Type")) if raw else json.loads(b)


def wait_ai(name, limit=25):
    t0 = time.time()
    while time.time() - t0 < limit:
        r = get("/ai?f=" + name)
        if r.get("state") not in ("busy",):
            return r, time.time() - t0
        time.sleep(0.2)
    return r, time.time() - t0


# รอให้โมเดลโหลดเสร็จ (โหลดในเธรดแยก)
for _ in range(50):
    st = get("/status")
    if not str(st.get("aiState", "")).startswith("กำลังโหลด"):
        break
    time.sleep(0.2)
print(f"[{MODE}] aiState = {st.get('aiState')}")

t = time.time()
shot = get("/photo")
took = time.time() - t
name = shot["name"]
check("กดถ่ายได้ปกติ", bool(name), shot)
r, waited = wait_ai(name)
print(f"     /ai -> {r}  (รอ {waited:.1f} วิ, ถ่าย {took:.1f} วิ)")

if MODE == "on":
    check("สถานะ AI = พร้อม", str(st.get("aiState", "")).startswith("พร้อม"), st.get("aiState"))
    check("AI อ่านได้ 2045 และผ่านเกณฑ์แนะนำ", r.get("state") == "done" and r.get("digits") == "2045", r)
    check("ภาพ 64MP ถอดครึ่งเดียว + อ่านเสร็จใน 10 วิ", waited < 10, waited)
    b, ct = get("/ai?img=1&f=" + name, raw=True)
    check("ได้ภาพแถบเลขที่ AI อ่าน (JPEG)", ct == "image/jpeg" and b[:2] == b"\xff\xd8", ct)
    check("/status บอกเวลาที่ AI ใช้", isinstance(get("/status").get("aiMs"), int))
else:
    check("ไม่มี AI -> state off พร้อมเหตุผล", r.get("state") == "off" and r.get("why"), r)
    check("สถานะ AI บอกว่าใช้ไม่ได้/ปิด", not str(st.get("aiState", "")).startswith("พร้อม"), st.get("aiState"))

check("รูปที่ไม่มีอยู่ -> state none", get("/ai?f=shot_19990101_000000.jpg").get("state") == "none")
check("ชื่อไฟล์แปลก ๆ ไม่พัง", get("/ai?f=../../etc/passwd").get("state") == "none")

side = os.path.join(PHOTOS, os.path.splitext(name)[0] + ".json")
time.sleep(0.3)
before = json.load(open(side, encoding="utf-8"))
check("AI ไม่บันทึกค่าจริงเอง (ไม่มี reading)", "reading" not in before, before)
if MODE == "on":
    check("AI จดสิ่งที่เดาลงไฟล์ข้อมูล (ai.guess = 2045)",
          (before.get("ai") or {}).get("guess") == "2045", before)
else:
    check("ไม่มี AI -> ไม่มีช่อง ai ในไฟล์ข้อมูล", "ai" not in before, before)

# push รอบแรก (ก่อนคนยืนยันค่า) แบบที่เกิดจริงบ่อย ๆ
env = dict(os.environ, HUB_TOKEN="tok-test")
state = os.path.join(os.path.dirname(PHOTOS), "push_state_" + MODE + ".json")
push = [sys.executable, os.path.join(ROOT, "pi", "push.py"), "--to", HUB, "--dir", PHOTOS,
        "--state", state, "--once", "--live-kbps", "0"]
subprocess.run(push, env=env, capture_output=True, timeout=60)
hubmeta = os.path.join(HUBDIR, "meta", name + ".json")
h1 = json.load(open(hubmeta, encoding="utf-8")) if os.path.exists(hubmeta) else {}
if MODE == "on":
    check("hub ได้สิ่งที่ AI เดาไปด้วย", (h1.get("ai") or {}).get("guess") == "2045", h1)
    check("AI มั่นใจ >= 75% -> hub ใส่ค่าให้เลยตั้งแต่รอบแรก (rsrc ai)",
          h1.get("reading") == "2045" and h1.get("rsrc") == "ai", h1)
else:
    check("hub ได้รูปรอบแรก (ยังไม่มีค่า)", h1.get("name") == name and not h1.get("reading"), h1)
recv1 = h1.get("recv")

# คนกดบันทึก: ห้อง 104 ไฟ ค่า 2045 (ใส่ตัวอักษรขยะปนมา ต้องถูกกรองทิ้ง)
j = get("/tag?f=" + name + "&room=104&kind=power&reading=20%2045x")
check("/tag คืนค่าที่บันทึก (กรองเหลือเลข)", j.get("ok") and j.get("reading") == "2045", j)
after = json.load(open(side, encoding="utf-8"))
check("ไฟล์ข้อมูลมีห้อง/ชนิด/ค่า", (after.get("room"), after.get("kind"), after.get("reading"))
      == ("104", "power", "2045"), after)
check("เวลาถ่ายเดิมไม่หาย", after.get("ts") == before.get("ts"), (before, after))
if MODE == "on":
    check("เก็บสิ่งที่ AI เดาไว้ตรวจย้อนหลัง", (after.get("ai") or {}).get("guess") == "2045", after)
else:
    check("ไม่มี AI ก็ไม่มีช่อง ai", "ai" not in after, after)

# ติดป้ายใหม่โดยไม่ส่ง reading -> ค่าเดิมต้องอยู่
get("/tag?f=" + name + "&room=105&kind=power")
again = json.load(open(side, encoding="utf-8"))
check("แก้ห้องทีหลัง ค่ามิเตอร์ไม่หาย", again.get("room") == "105" and again.get("reading") == "2045", again)

# push รอบสอง: hub ต้องได้ค่า
subprocess.run(push, env=env, capture_output=True, timeout=60)
h2 = json.load(open(hubmeta, encoding="utf-8")) if os.path.exists(hubmeta) else {}
if not h2:
    cands = glob.glob(os.path.join(HUBDIR, "meta", "*.json"))
    h2 = next((json.load(open(c, encoding="utf-8")) for c in cands
               if json.load(open(c, encoding="utf-8")).get("name") == name), {})
check("hub ได้ค่ามิเตอร์ 2045 หลังส่งซ้ำ", h2.get("reading") == "2045" and h2.get("room") == "105", h2)
check("ส่งซ้ำแบบข้อมูลอย่างเดียว ไม่ส่งรูป 3MB ซ้ำ (recv เดิม)", h2.get("recv") == recv1, (recv1, h2.get("recv")))
check("hub จำว่าค่านี้มาจากหุ่น", h2.get("rsrc") == "robot", h2)

# ---------- เจ้าของหอ ----------
import http.cookiejar
cj = http.cookiejar.CookieJar()
ho = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def hpost(path, body):
    rq = urllib.request.Request(HUB + path, data=json.dumps(body).encode(), method="POST",
                                headers={"Content-Type": "application/json"})
    try:
        with ho.open(rq, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"http": e.code}


def hget(path):
    with ho.open(HUB + path, timeout=10) as r:
        return json.loads(r.read())


import urllib.error
check("เจ้าของหอเข้าระบบได้", hpost("/api/login", {"role": "owner", "password": "testowner123"}).get("ok"))
tenant_pw = hpost("/api/owner/add-room", {"room": "105"}).get("password")
ph = [p for p in hget("/api/owner/photos?room=105") if p["name"] == name]
check("หน้าเจ้าของหอได้ช่อง ai", bool(ph) and ("ai" in ph[0]), ph)
if MODE == "on":
    check("ai บนหน้าเจ้าของหอ = 2045", ph and (ph[0].get("ai") or {}).get("guess") == "2045", ph)

# เจ้าของหอแก้ค่าเอง -> หุ่นยืนยันค่าอื่นทีหลังต้องทับไม่ได้
r = hpost("/api/owner/set-photo", {"name": name, "room": "105", "kind": "power", "reading": "2046"})
check("เจ้าของหอบันทึกค่าเองได้", r.get("reading") == "2046", r)
get("/tag?f=" + name + "&room=105&kind=power&reading=2047")
subprocess.run(push, env=env, capture_output=True, timeout=60)
cand = [json.load(open(c, encoding="utf-8")) for c in glob.glob(os.path.join(HUBDIR, "meta", "*.json"))]
h3 = next((c for c in cand if c.get("name") == name), {})
check("ค่าที่เจ้าของหอแก้เอง หุ่นทับไม่ได้", h3.get("reading") == "2046", h3)

# ค่าขึ้นข้างบน: ใบที่ "ยืนยันล่าสุด" ชนะ แม้ถ่ายก่อน
shot2 = get("/photo")["name"]
wait_ai(shot2)
get("/tag?f=" + shot2 + "&room=105&kind=power&reading=3000")
subprocess.run(push, env=env, capture_output=True, timeout=60)
top = hget("/api/owner/room?room=105")["readings"]["power"]
check("ใบที่ถ่ายใหม่กว่า + ยืนยันทีหลัง ขึ้นข้างบน (3000)", top and top[-1]["value"] == 3000, top)
time.sleep(1.1)
hpost("/api/owner/set-photo", {"name": name, "room": "105", "kind": "power", "reading": "2045"})
top = hget("/api/owner/room?room=105")["readings"]["power"]
check("กดยืนยันใบเก่าทีหลัง -> ใบนั้นขึ้นข้างบนแทน (2045)", top and top[-1]["value"] == 2045, top)

# ลบรูปใน hub แล้วหุ่นแก้ข้อมูล -> ไม่ส่งรูปกลับมาใหม่
hpost("/api/owner/del-photos", {"names": [shot2]})
get("/tag?f=" + shot2 + "&room=105&kind=power&reading=3001")
subprocess.run(push, env=env, capture_output=True, timeout=60)
check("รูปที่เจ้าของหอลบแล้ว ไม่กลับมาเอง",
      not any(json.load(open(c, encoding="utf-8")).get("name") == shot2
              for c in glob.glob(os.path.join(HUBDIR, "meta", "*.json"))))

# ลูกบ้านต้องไม่เห็นช่อง ai (เห็นแค่ค่าที่ยืนยันแล้ว)
tj = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
tj.open(urllib.request.Request(HUB + "/api/login", method="POST",
        data=json.dumps({"room": "105", "password": tenant_pw}).encode(),
        headers={"Content-Type": "application/json"}), timeout=10).read()
me = json.loads(tj.open(HUB + "/api/me", timeout=10).read())
check("ลูกบ้านเห็นรูปห้องตัวเอง แต่ไม่เห็นช่อง ai",
      me.get("photos") and all("ai" not in p for p in me["photos"]), me.get("photos"))

# รูปเก่าที่ AI ยังไม่เคยอ่าน -> อ่านย้อนหลังตอนหุ่นว่าง
if MODE == "on":
    oldside = os.path.join(PHOTOS, "shot_20261001_120000.json")
    t0 = time.time()
    while time.time() - t0 < 30:
        m = json.load(open(oldside, encoding="utf-8"))
        if "ai" in m:
            break
        time.sleep(0.5)
    check("รูปเก่าถูกอ่านย้อนหลัง (ai.guess = 2045)", (m.get("ai") or {}).get("guess") == "2045", m)
    check("อ่านย้อนหลังแล้วห้องเดิมไม่หาย", m.get("room") == "104", m)

print(f"\n{ok} ผ่าน, {fail} ไม่ผ่าน")
sys.exit(1 if fail else 0)
