"""ใช้กับ tests/webrtctest.sh — เปิดหน้าจริงใน Chromium แล้วตรวจวิดีโอ WebRTC"""
import json, os, subprocess, sys, time
from playwright.sync_api import sync_playwright

PI, HUB, OWNER, MTX = sys.argv[1:5]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = fail = 0


def check(label, cond, extra=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print("  %s %s   %s" % ("ok  " if cond else "FAIL", label, "" if cond else extra))


def st(pg):
    return pg.evaluate("""()=>({mode:document.querySelector('#lmVal').textContent, rtcOn,
      vw:document.querySelector('#vv').videoWidth, t:document.querySelector('#vv').currentTime,
      img:!document.querySelector('#v').hidden, src:document.querySelector('#v').src})""")


def wait(pg, cond, secs):
    t = time.time()
    while time.time() - t < secs:
        if cond(st(pg)):
            return time.time() - t
        time.sleep(0.4)
    return None


exe = None
for c in ("/opt/pw-browsers/chromium-1194/chrome-linux/chrome",):
    if os.path.exists(c):
        exe = c
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
    ctx = b.new_context(http_credentials={"username": "admin", "password": "12345678"})
    pg = ctx.new_page()
    pg.goto(PI + "/")
    print("1. ต่อ Pi ตรง")
    t = wait(pg, lambda s: s["rtcOn"], 15)
    check("วิดีโอขึ้นภายใน 15 วิ", t is not None, st(pg))
    a = st(pg); time.sleep(1.5); b2 = st(pg)
    check("วิดีโอเดินจริง", b2["t"] > a["t"] and b2["vw"] == 1280, (a, b2))
    check("ซ่อนภาพ JPEG ระหว่างเล่นวิดีโอ", not b2["img"])
    import re as _re
    time.sleep(2.5)
    perf = pg.evaluate("document.querySelector('#pPerf').textContent")
    m = _re.search(r"วิดีโอ (\d+) fps · (\d+) ms", perf)
    check("ป้าย fps/ความหน่วงของวิดีโอขึ้นตัวเลข", m and int(m.group(1)) > 0, perf)
    pg.keyboard.down("w"); time.sleep(0.5)
    s = json.loads(pg.evaluate("fetch('/status').then(r=>r.text())"))
    pg.keyboard.up("w")
    check("ขับได้ระหว่างเล่นวิดีโอ", (s["cmdL"], s["src"]) == (200, "web"), s["src"])

    print("2. ถ่ายรูประหว่างเล่นวิดีโอ")
    # 16 ต.ค.: เดิมถ่ายแล้ววิดีโอหลุดไปใช้ JPEG — ตอนนี้ต้องค้างภาพไว้แล้วต่อวิดีโอใหม่เอง ไม่ตกไป JPEG
    t0 = st(pg)["t"]
    pg.evaluate("fetch('/photo')")
    seen_jpeg = False; t = time.time()
    while time.time() - t < 15:
        s = st(pg); seen_jpeg |= (not s["rtcOn"] and s["img"]); time.sleep(0.3)
        if time.time() - t > 4 and s["rtcOn"] and s["t"] > t0 + 1: break
    check("ถ่ายรูปแล้วไม่ตกไปใช้ JPEG", not seen_jpeg)
    a = st(pg); time.sleep(1.5); b2 = st(pg)
    check("วิดีโอเดินต่อหลังถ่าย", b2["rtcOn"] and b2["t"] > a["t"], (a, b2))

    print("3. MediaMTX ดับ")
    subprocess.run(["pkill", "-x", "mediamtx"])
    check("สลับเป็น JPEG ใน 8 วิ", wait(pg, lambda s: not s["rtcOn"] and s["img"], 8) is not None)
    a = st(pg)["src"]; time.sleep(1.5)
    check("ภาพ JPEG ยังเดิน", st(pg)["src"] != a)
    time.sleep(2.5)
    perf = pg.evaluate("document.querySelector('#pPerf').textContent")
    m = _re.search(r"JPEG (\d+) fps · (\d+) ms", perf)
    check("ป้าย fps/ความหน่วงของ JPEG ขึ้นตัวเลข (ต่ำกว่า 500 ms)",
          m and int(m.group(1)) > 0 and int(m.group(2)) < 500, perf)
    subprocess.Popen([MTX, os.path.join(ROOT, "pi", "mediamtx.yml")],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    check("MediaMTX กลับมา วิดีโอกลับมาเองใน 45 วิ", wait(pg, lambda s: s["rtcOn"], 45) is not None)
    ctx.close()

    print("4. ผ่าน hub (หน้าเจ้าของหอ)")
    ctx = b.new_context()
    pg = ctx.new_page()
    pg.goto(HUB + OWNER)
    pg.evaluate("""fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
                 body:JSON.stringify({role:'owner',password:'testowner123'})})""")
    pg.goto(HUB + OWNER); time.sleep(1)
    pg.evaluate("openRobot()")
    fr = pg.frame_locator("#robotFrame").locator("body")
    t0, got = time.time(), False
    while time.time() - t0 < 20 and not got:
        time.sleep(1)
        try:
            got = fr.evaluate("()=>rtcOn && document.querySelector('#vv').videoWidth>0")
        except Exception:
            pass
    check("วิดีโอขึ้นผ่าน hub", got)
    b.close()
print("\n%d ผ่าน, %d ไม่ผ่าน" % (ok, fail))
sys.exit(1 if fail else 0)
