"""ใช้กับ tests/shottest.sh — กดถ่ายในเบราว์เซอร์จริงแล้วตรวจ (+ ข้อ 5: L+R = รีภาพ)
1. ถ่ายตอนดูวิดีโอ: ไม่ขึ้น "วิดีโอหลุด", ไม่ตกไปใช้ JPEG, วิดีโอกลับมาเอง, ภาพค้างหายเอง
2. กด R บนจอยระหว่างกล่องถามเปิด = บันทึก (ไม่ถ่ายใบใหม่)
3. กด R ตอนไม่มีกล่อง = ถ่าย / ข้ามแล้วกด R = ถ่ายใบใหม่ (ไม่ไปบันทึกใบที่ข้าม)
4. Space = ถ่าย / Space ตอนกล่องเปิด = บันทึก / พิมพ์ในช่องเลขห้องแล้วหุ่นไม่วิ่ง"""
import glob, json, os, sys, time
from playwright.sync_api import sync_playwright

PI, PAD, PHOTOS = sys.argv[1:4]
ok = fail = 0


def check(label, cond, extra=""):
    global ok, fail
    ok, fail = (ok + 1, fail) if cond else (ok, fail + 1)
    print("  %s %s   %s" % ("ok  " if cond else "FAIL", label, "" if cond else extra))


def press_r():
    with open(PAD, "a") as f:
        f.write("1 311 1\n1 311 0\n")


def st(pg):
    return pg.evaluate("""()=>({rtcOn, rtc:!!rtc, fails:rtcFails, frz:!document.querySelector('#vfz').hidden,
      img:!document.querySelector('#v').hidden, ask:document.querySelector('#ask').classList.contains('on'),
      tag:tagName, notes:window.__notes.slice()})""")


def wait(pg, cond, secs):
    t = time.time()
    while time.time() - t < secs:
        s = st(pg)
        if cond(s):
            return time.time() - t, s
        time.sleep(0.2)
    return None, st(pg)


def sides():
    return {os.path.basename(p): json.load(open(p, encoding="utf-8"))
            for p in glob.glob(os.path.join(PHOTOS, "shot_*.json"))}


with sync_playwright() as p:
    exe = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
    b = p.chromium.launch(executable_path=exe if os.path.exists(exe) else None)
    pg = b.new_context(http_credentials={"username": "admin", "password": "12345678"}).new_page()
    pg.add_init_script("""window.__notes=[]; new MutationObserver(()=>{const n=document.querySelector('#note');
      if(n&&n.textContent) window.__notes.push(n.textContent)}).observe(document,{subtree:true,childList:true,characterData:true});""")
    pg.goto(PI + "/")
    t, s = wait(pg, lambda s: s["rtcOn"], 20)
    check("เปิดหน้าแล้วได้วิดีโอ", t is not None, s)
    pg.evaluate("fetch('/ctx?room=104&kind=water&ask=1')"); time.sleep(0.5)
    pg.evaluate("ctxAsk=true")

    print("1. ถ่ายจากปุ่มบนจอ ตอนดูวิดีโอ")
    vgen0 = pg.evaluate("fetch('/status').then(r=>r.json()).then(j=>j.vGen)")
    pg.evaluate("window.__notes=[]")
    pg.click("#shutter")
    t_frz, s = wait(pg, lambda s: s["frz"], 3)
    check("ค้างภาพสุดท้ายไว้ทันทีที่กด", t_frz is not None, s)
    t_ask, s = wait(pg, lambda s: s["ask"], 10)
    check("กล่องถามเลขห้องขึ้น", t_ask is not None, s)
    t_back, s = wait(pg, lambda s: s["rtcOn"] and s["rtc"] and not s["frz"], 15)
    vgen1 = pg.evaluate("fetch('/status').then(r=>r.json()).then(j=>j.vGen)")
    print(f"     วิดีโอกลับมาใน {t_back if t_back is None else round(t_back, 1)} วิ  vGen {vgen0}->{vgen1}  ข้อความ {s['notes']}")
    check("วิดีโอเริ่มใหม่ฝั่ง Pi (vGen เปลี่ยน)", vgen1 != vgen0, (vgen0, vgen1))
    check("วิดีโอกลับมาเอง ภาพค้างหายเอง", t_back is not None, s)
    check("ไม่ขึ้น 'วิดีโอหลุด'", not any("หลุด" in n for n in s["notes"]), s["notes"])
    check("ไม่นับเป็นความล้มเหลว (rtcFails = 0)", s["fails"] == 0, s["fails"])
    check("ไม่ตกไปใช้ JPEG", not s["img"], s)

    print("2. กด R บนจอยระหว่างกล่องเปิด = บันทึก")
    n_before = len(sides()); name = st(pg)["tag"]
    pg.fill("#aRoom", "104"); pg.fill("#aRead", "1234")
    press_r()
    t, s = wait(pg, lambda s: not s["ask"], 6)
    check("กล่องปิดเอง", t is not None, s)
    time.sleep(1.0)
    sd = sides()
    check("ไม่ถ่ายใบใหม่", len(sd) == n_before, (n_before, len(sd)))
    meta = sd.get(name.replace(".jpg", ".json"), {})
    check("บันทึกห้อง + ค่าแล้ว", meta.get("room") == "104" and meta.get("reading") == "1234", meta)

    print("3. กด R ตอนไม่มีกล่อง = ถ่าย / ข้ามแล้วกด R = ถ่ายใหม่")
    wait(pg, lambda s: s["rtcOn"] and not s["frz"], 15)
    press_r()
    t, s = wait(pg, lambda s: s["ask"], 12)
    check("R ถ่ายรูปใหม่ + กล่องขึ้น", t is not None and len(sides()) == n_before + 1, (t, len(sides())))
    skipped = s["tag"]
    pg.click("#aCancel"); time.sleep(0.8)
    wait(pg, lambda s: s["rtcOn"] and not s["frz"], 15)
    press_r()
    t, s = wait(pg, lambda s: s["ask"] and s["tag"] != skipped, 12)
    check("ข้ามแล้วกด R = ถ่ายใบใหม่", t is not None, (skipped, s["tag"]))
    check("ใบที่ข้ามไม่ถูกบันทึกค่า", "reading" not in sides().get(skipped.replace(".jpg", ".json"), {}),
          sides().get(skipped.replace(".jpg", ".json")))

    print("4. แป้นพิมพ์")
    pg.fill("#aRoom", ""); pg.click("#aRoom"); pg.keyboard.type("wwdd105")
    time.sleep(0.4)
    drv = pg.evaluate("fetch('/status').then(r=>r.json()).then(j=>[j.cmdL,j.cmdR])")
    check("พิมพ์ในช่องเลขห้อง หุ่นไม่วิ่ง", drv in ([0, 0], [None, None]), drv)
    name = st(pg)["tag"]
    pg.focus("#aTake"); pg.keyboard.press(" ")
    t, s = wait(pg, lambda s: not s["ask"], 6)
    time.sleep(0.8)
    check("Space ตอนกล่องเปิด = บันทึก", t is not None
          and sides().get(name.replace(".jpg", ".json"), {}).get("room") == "wwdd105", sides().get(name.replace(".jpg", ".json")))
    n0 = len(sides())
    wait(pg, lambda s: s["rtcOn"] and not s["frz"], 15)
    pg.mouse.click(5, 400); pg.keyboard.press(" ")
    t, s = wait(pg, lambda s: s["ask"], 12)
    check("Space ตอนไม่มีกล่อง = ถ่าย", t is not None and len(sides()) == n0 + 1, (t, len(sides())))

    print("5. L+R พร้อมกัน = รีภาพ (กล้องปกติ)")
    pg.keyboard.press("Escape"); time.sleep(0.5)
    wait(pg, lambda s: s["rtcOn"] and not s["frz"], 15)
    n0 = len(sides()); pg.evaluate("window.__notes=[]")
    with open(PAD, "a") as f:                      # L ลง, R ลง, ปล่อยทั้งคู่
        f.write("1 310 1\n1 311 1\n1 311 0\n1 310 0\n")
    t, s = wait(pg, lambda s: any("รีภาพ" in n for n in s["notes"]), 5)
    check("หน้าเว็บขึ้น 'รีภาพ…'", t is not None, s["notes"])
    t, s = wait(pg, lambda s: s["rtcOn"] and s["rtc"], 20)
    check("วิดีโอกลับมาเองหลังรีภาพ", t is not None, s)
    time.sleep(1.0)
    check("L+R ไม่ถ่ายรูป", len(sides()) == n0, (n0, len(sides())))
    stt = json.loads(pg.evaluate("fetch('/status').then(r=>r.text())"))
    check("L+R ไม่สั่งโฟกัส/สแกน", not stt.get("afBusy") and not stt.get("scan"), (stt.get("afBusy"), stt.get("scan")))
    with open(PAD, "a") as f:                      # R ถึงก่อน L เล็กน้อย ก็ต้องนับเป็น L+R
        f.write("1 311 1\n1 310 1\n1 311 0\n1 310 0\n")
    time.sleep(2.0)
    check("R ถึงก่อน L ก็ยังเป็นรีภาพ ไม่ถ่าย", len(sides()) == n0, (n0, len(sides())))
    b.close()

print(f"\n{ok} ผ่าน, {fail} ไม่ผ่าน")
sys.exit(1 if fail else 0)
