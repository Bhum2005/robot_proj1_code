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
before = json.load(open(side, encoding="utf-8"))
check("ไฟล์ข้อมูลตอนถ่ายยังไม่มีค่า (AI ไม่บันทึกเอง)", "reading" not in before and "ai" not in before, before)

# push รอบแรก (ก่อนคนยืนยันค่า) แบบที่เกิดจริงบ่อย ๆ
env = dict(os.environ, HUB_TOKEN="tok-test")
state = os.path.join(os.path.dirname(PHOTOS), "push_state_" + MODE + ".json")
push = [sys.executable, os.path.join(ROOT, "pi", "push.py"), "--to", HUB, "--dir", PHOTOS,
        "--state", state, "--once", "--live-kbps", "0"]
subprocess.run(push, env=env, capture_output=True, timeout=60)
hubmeta = os.path.join(HUBDIR, "meta", name + ".json")
h1 = json.load(open(hubmeta, encoding="utf-8")) if os.path.exists(hubmeta) else {}
check("hub ได้รูปรอบแรก (ยังไม่มีค่า)", h1.get("name") == name and not h1.get("reading"), h1)

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

print(f"\n{ok} ผ่าน, {fail} ไม่ผ่าน")
sys.exit(1 if fail else 0)
