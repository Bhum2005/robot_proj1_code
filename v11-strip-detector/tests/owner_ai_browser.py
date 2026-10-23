"""หน้าเจ้าของหอ: ค่าที่ AI อ่านได้ + ปุ่มยืนยัน (เปิดเบราว์เซอร์จริง)
    python3 tests/owner_ai_browser.py <outdir>
เปิด hub ชั่วคราวเอง ส่งรูป 4 แบบเข้าไป แล้วกดจริง"""
import base64, json, os, socket, subprocess, sys, tempfile, time, urllib.request
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
os.makedirs(OUT, exist_ok=True)
T = tempfile.mkdtemp()
PORT = 8391
HUB = f"http://127.0.0.1:{PORT}"
ok = fail = 0


def check(label, cond, extra=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print("  %s %s   %s" % ("ok  " if cond else "FAIL", label, "" if cond else extra))


subprocess.run([sys.executable, os.path.join(ROOT, "hub/hub.py"), "--dir", T, "--owner-pw", "testowner123"],
               capture_output=True)
hub = subprocess.Popen([sys.executable, os.path.join(ROOT, "hub/hub.py"), "--dir", T, "--port", str(PORT),
                        "--owner-path", "/jod"], env=dict(os.environ, HUB_TOKEN="tok"),
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(40):
    try:
        urllib.request.urlopen(HUB + "/healthz", timeout=1); break
    except OSError:
        time.sleep(0.25)

img = open(os.path.join(ROOT, "tests/meter/meter_2045.png"), "rb").read()
import cv2, numpy as np
jpg = cv2.imencode(".jpg", cv2.imdecode(np.frombuffer(img, np.uint8), 1))[1].tobytes()


def topval(pg):
    """ค่าไฟของเดือนนี้ที่หน้าเว็บใช้วาดข้างบน (ตัวเลขเป็นวงล้อหมุน อ่านจากข้อความไม่ได้)"""
    j = pg.evaluate("fetch('/api/owner/room?room=104').then(r=>r.json())")
    cur = [r for r in j["readings"]["power"] if r["month"] == time.strftime("%Y-%m")]
    return cur[0]["value"] if cur else None


def push(name, meta):
    rq = urllib.request.Request(HUB + "/push", data=jpg, method="POST", headers={
        "X-Token": "tok", "X-Name": name, "X-Kind": "full", "Content-Type": "image/jpeg",
        "X-Meta": base64.b64encode(json.dumps(meta).encode()).decode()})
    urllib.request.urlopen(rq, timeout=10).read()


day = time.strftime("%Y%m%d")
push(f"shot_{day}_090000.jpg", {"room": "104", "kind": "other", "ai": {"guess": "6227", "conf": 0.93}})
push(f"shot_{day}_090100.jpg", {"room": "104", "kind": "power", "ai": {"guess": "3733", "conf": 0.41}})
push(f"shot_{day}_090200.jpg", {"room": "104", "kind": "other", "ai": {"guess": "", "conf": 0.1}})
push(f"shot_{day}_090300.jpg", {"room": "104", "kind": "other"})

with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    b = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None)
    for scheme, vp in (("light", (1280, 900)), ("dark", (390, 844))):
        ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, color_scheme=scheme,
                            accept_downloads=True)
        pg = ctx.new_page()
        pg.goto(HUB + "/jod")
        pg.request.post(HUB + "/api/login", data=json.dumps({"role": "owner", "password": "testowner123"}),
                        headers={"Content-Type": "application/json"})
        if scheme == "light":
            pg.request.post(HUB + "/api/owner/add-room", data=json.dumps({"room": "104"}),
                            headers={"Content-Type": "application/json"})
        pg.goto(HUB + "/jod")
        pg.wait_for_selector(".shot .ai", timeout=8000)
        cards = pg.locator(".shot")
        if scheme == "light":
            check("การ์ดแรก (6227 93%) มีปุ่มยืนยันเป็นน้ำ/ไฟ",
                  pg.locator(".shot[data-ai='6227'] [data-ok=water]").count() == 1
                  and pg.locator(".shot[data-ai='6227'] [data-ok=power]").count() == 1)
            check("การ์ด 3733 41% ขึ้น 'ไม่แน่ใจ' + กรอบประ",
                  pg.locator(".shot[data-ai='3733'] .ai.low").count() == 1
                  and "ไม่แน่ใจ" in pg.locator(".shot[data-ai='3733'] .ac").inner_text())
            check("รูปที่ AI หาเลขไม่เจอ บอกให้พิมพ์เอง", pg.locator(".ai.nf").count() == 1)
            check("รูปที่ไม่มีข้อมูล AI ไม่มีแถบ AI", cards.count() == 4 and pg.locator(".shot .ai").count() == 3)
            pg.screenshot(path=os.path.join(OUT, "owner_ai_before.png"), full_page=True)

            # เปลี่ยนชนิดเป็นไฟ -> เหลือปุ่มยืนยันปุ่มเดียว
            pg.select_option(".shot[data-ai='6227'] [data-k=kind]", "power")
            check("เลือกชนิดเป็นไฟ -> เหลือปุ่ม 'ยืนยัน' ปุ่มเดียว",
                  pg.locator(".shot[data-ai='6227'] [data-ok]").count() == 1)
            pg.select_option(".shot[data-ai='6227'] [data-k=kind]", "other")

            # กดยืนยันเป็นไฟ -> ขึ้นข้างบน
            pg.click(".shot[data-ai='6227'] [data-ok=power]")
            time.sleep(1.5)
            top = topval(pg)
            check("กดยืนยันเป็นไฟ -> ค่า 6227 ขึ้นช่องไฟข้างบน", top == 6227, top)
            check("การ์ดขึ้น '✓ ยืนยันแล้ว'", pg.locator(".shot[data-ai='6227'] .ai.ok").count() == 1)
            pip = pg.locator(".rm[data-room='104'] .pip.power.on").count()
            check("จุดไฟของห้อง 104 ติด (จดไฟแล้ว)", pip == 1)

            # ความมั่นใจต่ำ -> ถามก่อน; กดยกเลิกต้องไม่บันทึก
            pg.click(".shot[data-ai='3733'] [data-ok=power]")
            pg.wait_for_selector("dialog[open]", timeout=3000)
            check("AI ไม่แน่ใจ -> มีกล่องถามก่อนยืนยัน", "3733" in pg.locator("dialog[open]").inner_text())
            pg.screenshot(path=os.path.join(OUT, "owner_ai_lowconf.png"))
            pg.keyboard.press("Escape"); time.sleep(0.8)
            top = topval(pg)
            check("กดยกเลิก -> ค่าข้างบนยังเป็น 6227", top == 6227, top)
            # ยืนยันจริง -> ใบนี้กลายเป็นค่าข้างบนแทน (ยืนยันล่าสุดชนะ)
            pg.click(".shot[data-ai='3733'] [data-ok=power]")
            pg.wait_for_selector("dialog[open]", timeout=3000)
            pg.click("#askOk"); time.sleep(1.5)
            top = topval(pg)
            check("ยืนยันใบที่สอง -> ค่าข้างบนเปลี่ยนเป็น 3733", top == 3733, top)
            pg.screenshot(path=os.path.join(OUT, "owner_ai_after.png"), full_page=True)

            # พิมพ์เลขเอง + กดบันทึก บนรูปที่ชนิดยังเป็น "อื่น ๆ" -> ต้องบอกให้เลือกน้ำ/ไฟ ไม่เงียบ
            c = f".shot[data-n='shot_{day}_090300.jpg']"
            check("ปุ่มบันทึกกดได้ตั้งแต่แรก (ไม่เป็นสีเทา)", not pg.locator(c + " [data-save]").is_disabled())
            pg.fill(c + " [data-k=reading]", "5555")
            pg.click(c + " [data-save]"); time.sleep(0.4)
            check("ชนิดเป็น 'อื่น ๆ' -> บอกให้เลือกน้ำ/ไฟ + ช่องชนิดขึ้นกรอบแดง",
                  pg.locator(c + " [data-k=kind].need").count() == 1
                  and "น้ำหรือไฟ" in pg.locator(c + " .saved").inner_text())
            check("ยังไม่บันทึกจริง (ค่าข้างบนยังเป็น 3733)", topval(pg) == 3733, topval(pg))
            pg.select_option(c + " [data-k=kind]", "power")
            check("เลือกชนิดแล้วกรอบแดงหาย", pg.locator(c + " .need").count() == 0)
            time.sleep(1.1)
            pg.click(c + " [data-save]"); time.sleep(0.3)
            check("กดบันทึก -> ขึ้นข้อความยืนยันพร้อมค่า",
                  "5555" in pg.locator("#toast").inner_text(), pg.locator("#toast").inner_text())
            time.sleep(1.2)
            check("ค่าที่พิมพ์เองขึ้นข้างบน (5555)", topval(pg) == 5555, topval(pg))
            pg.screenshot(path=os.path.join(OUT, "owner_manual_saved.png"))

            # ดาวน์โหลดรูปเต็มจากหน้าซูม
            pg.click(".shot[data-ai='3733'] .pic img", force=True)
            pg.wait_for_selector("#lb.on", timeout=3000)
            with pg.expect_download(timeout=8000) as dl:
                pg.click("#lbdl")
            d = dl.value
            path = d.path()
            check("ดาวน์โหลดรูปเต็มได้ (ไฟล์ JPEG ชื่อเดิม)",
                  d.suggested_filename.endswith("090100.jpg") and open(path, "rb").read(2) == b"\xff\xd8",
                  d.suggested_filename)
            check("หน้าซูมยังเปิดอยู่หลังกดดาวน์โหลด", pg.locator("#lb.on").count() == 1)
            pg.keyboard.press("Escape"); pg.click("#lb", force=True); time.sleep(0.3)

            # ---- รูปใหม่จากหุ่นขึ้นเองโดยไม่ต้องรีเฟรช + AI มั่นใจ >= 75% ใส่ค่าให้ ----
            n0 = pg.locator(".shot").count()
            newname = "shot_" + time.strftime("%Y%m%d_%H%M%S") + ".jpg"
            push(newname, {"room": "104", "kind": "power", "ai": {"guess": "7001", "conf": 0.91}})
            try:
                pg.wait_for_function(f"document.querySelectorAll('.shot').length>{n0}", timeout=9000)
                appeared = True
            except Exception:
                appeared = False
            check("รูปใหม่จากหุ่นขึ้นเองภายใน 9 วิ ไม่ต้องรีเฟรช", appeared)
            time.sleep(0.8)
            c2 = f".shot[data-n='{newname}']"
            check("การ์ดบอกว่า AI ใส่ค่าให้แล้ว + มีปุ่ม 'ถูกต้อง'",
                  pg.locator(c2 + " .ai.auto").count() == 1 and pg.locator(c2 + " [data-ok=power]").count() == 1)
            check("ช่องไฟข้างบน = 7001 ติดป้าย 'ค่าจาก AI'", topval(pg) == 7001
                  and "ค่าจาก AI" in pg.locator(".sum .blk").nth(1).inner_text(), topval(pg))
            pg.screenshot(path=os.path.join(OUT, "owner_ai_auto.png"))
            pg.click(c2 + " [data-ok=power]"); time.sleep(1.6)
            check("กด 'ถูกต้อง' -> กลายเป็นยืนยันแล้ว ป้าย AI ข้างบนหาย",
                  pg.locator(c2 + " .ai.ok").count() == 1
                  and "ค่าจาก AI" not in pg.locator(".sum .blk").nth(1).inner_text())

            # กำลังพิมพ์อยู่ -> ไม่โหลดทับ ขึ้นแถบให้กดเอง
            pg.fill(f".shot[data-n='shot_{day}_090200.jpg'] [data-k=reading]", "12")
            n1 = pg.locator(".shot").count()
            push("shot_" + time.strftime("%Y%m%d_%H%M%S", time.localtime(time.time() + 1)) + ".jpg",
                 {"room": "104", "kind": "other"})
            time.sleep(6)
            check("กำลังพิมพ์อยู่ -> ไม่โหลดทับ (ช่องที่พิมพ์ยังอยู่)",
                  pg.locator(".shot").count() == n1
                  and pg.input_value(f".shot[data-n='shot_{day}_090200.jpg'] [data-k=reading]") == "12")
            check("ขึ้นแถบ 'มีรูป/ข้อมูลใหม่' ให้กดเอง", pg.locator("#newbar.on").count() == 1)
            pg.screenshot(path=os.path.join(OUT, "owner_newbar.png"))
            pg.click("#newbar"); time.sleep(1.2)
            check("กดแถบแล้วรูปใหม่ขึ้น", pg.locator(".shot").count() == n1 + 1)
        else:
            pg.screenshot(path=os.path.join(OUT, "owner_ai_phone_dark.png"), full_page=True)
            w = pg.evaluate("document.documentElement.scrollWidth")
            check("มือถือ 390px ไม่มีเลื่อนแนวนอน", w <= 390, w)
        ctx.close()
    b.close()
hub.terminate()
print(f"\n{ok} ผ่าน, {fail} ไม่ผ่าน   (ภาพอยู่ที่ {OUT})")
sys.exit(1 if fail else 0)
