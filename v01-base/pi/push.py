#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ตัวส่งรูปจาก Pi ไปเก็บที่ระบบมิเตอร์หอพัก — รันบน Pi คู่กับ server.py

หน้าที่เดียว: รูปไหนยังไม่ได้ส่ง ส่งให้หมด แล้วรอดูรูปใหม่

ออกแบบให้ "ทนการหลุด" เป็นหลัก เพราะหุ่นอยู่นอกบ้าน เน็ตหลุดเป็นเรื่องปกติ
  - จำว่าส่งอะไรไปแล้วลงไฟล์ ปิดเครื่องแล้วเปิดใหม่ก็ไม่ส่งซ้ำ
  - ส่งไม่ได้ก็รอแล้วลองใหม่ ไม่ตาย ไม่ข้ามรูป
  - รูปที่ยังเขียนไม่เสร็จจะไม่ถูกส่ง (ดูจากขนาดที่ยังเปลี่ยนอยู่)
ใช้ของที่มากับ Python ล้วน ๆ ไม่ต้อง pip install อะไรเลย

  python3 push.py --to http://192.168.1.50:8080 --token robot-push-change-me

ให้รันตลอดเวลา ใช้ไฟล์ robot-push.service ที่อยู่ข้าง ๆ กัน
"""
import argparse
import base64
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request

NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,120}\.jpg$")
DEF_DIR = os.path.expanduser(os.environ.get("ROBOT_PHOTOS", "~/robot_photos"))
DEF_STATE = os.path.expanduser("~/.robot_push.json")


def mark(full, side):
    """ลายเซ็นของรูปหนึ่งใบ = ขนาดไฟล์ + เวลาที่ไฟล์ข้อมูลถูกแก้ล่าสุด

    ★ ต้องรวมไฟล์ข้อมูลเข้าไปด้วย เพราะตอนนี้คนถ่ายจะติดป้ายเลขห้องทีหลัง
      ถ้าดูแต่ขนาดรูป ป้ายที่ติดเพิ่มจะไม่มีวันถูกส่งขึ้นไป
      รูปจะไปกองอยู่ในกล่อง "ยังไม่ได้ระบุห้อง" ตลอดกาล
    """
    try:
        sz = os.path.getsize(full)
    except OSError:
        return None
    try:
        mt = int(os.path.getmtime(side))
    except OSError:
        mt = 0
    return "%d:%d" % (sz, mt)


def load_state(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return {}
        # ไฟล์สถานะรุ่นเก่าเก็บแค่ขนาดเป็นตัวเลข แปลงให้เข้ารูปแบบใหม่
        # รูปเก่าที่ไม่มีไฟล์ข้อมูลจะได้ลายเซ็นตรงกัน ไม่ถูกส่งซ้ำ
        return {k: (v if isinstance(v, str) else "%d:0" % v)
                for k, v in d.items()}
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    tmp = path + ".part"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, path)
    except OSError as e:
        print("เขียนไฟล์สถานะไม่ได้:", e, file=sys.stderr)


def settled(path, wait=0.6):
    """เช็คว่าไฟล์เขียนเสร็จแล้วจริง

    server.py เขียนรูปด้วย open().write() ตรง ๆ ถ้าเราไปอ่านตอนกำลังเขียน
    จะได้ไฟล์ครึ่งเดียวแล้วส่งขึ้นคลังไปเลย ซึ่งกู้ไม่ได้
    วิธีเช็คคือดูขนาดสองครั้งห่างกันนิดหนึ่ง ถ้าเท่ากันแปลว่าหยุดเขียนแล้ว
    """
    try:
        a = os.path.getsize(path)
        time.sleep(wait)
        return a > 0 and a == os.path.getsize(path)
    except OSError:
        return False


def post(url, token, name, data, kind="full", meta=None, timeout=30):
    req = urllib.request.Request(url.rstrip("/") + "/push", data=data,
                                 method="POST")
    req.add_header("Content-Type", "image/jpeg")
    req.add_header("Content-Length", str(len(data)))
    req.add_header("X-Token", token)
    req.add_header("X-Name", name)
    req.add_header("X-Kind", kind)
    if meta:
        req.add_header("X-Meta", base64.b64encode(
            json.dumps(meta, ensure_ascii=False).encode("utf-8")).decode())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status == 200


def reachable(url, timeout=4):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/healthz",
                                    timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, socket.timeout, OSError):
        return False


def send_one(args, state, name):
    full = os.path.join(args.dir, name)
    thumb = os.path.join(args.dir, ".thumbs", name)
    side = os.path.splitext(full)[0] + ".json"
    sig = mark(full, side)
    if sig is None:
        return False
    if not settled(full):
        return False                      # ยังเขียนไม่เสร็จ เดี๋ยวรอบหน้าค่อยเอา

    with open(full, "rb") as f:
        data = f.read()
    meta = {"ts": int(os.path.getmtime(full)), "src": socket.gethostname()}
    # server.py เขียนไฟล์ข้อมูลคู่กับรูปไว้ บอกว่ารูปนี้เป็นของห้องไหน
    # มิเตอร์อะไร ส่งไปด้วยเพื่อให้รูปเข้าห้องถูกตั้งแต่ต้น
    try:
        with open(side, encoding="utf-8") as f:
            side_meta = json.load(f)
        for k in ("room", "kind", "note"):
            if side_meta.get(k):
                meta[k] = side_meta[k]
    except (OSError, ValueError):
        pass
    post(args.to, args.token, name, data, "full", meta)

    # รูปย่อส่งตามไปแยกต่างหาก ถ้าไม่มีก็ไม่เป็นไร คลังสร้างเองได้
    if os.path.exists(thumb):
        try:
            with open(thumb, "rb") as f:
                post(args.to, args.token, name, f.read(), "thumb")
        except (OSError, urllib.error.URLError):
            pass

    state[name] = sig
    return True


def sweep(args, state):
    """ส่งทุกไฟล์ที่ยังไม่เคยส่ง คืนจำนวนที่ส่งสำเร็จ"""
    try:
        names = sorted(n for n in os.listdir(args.dir) if NAME_RE.match(n))
    except OSError as e:
        print("อ่านโฟลเดอร์รูปไม่ได้:", e, file=sys.stderr)
        return 0, 0

    todo = []
    for n in names:
        full = os.path.join(args.dir, n)
        sig = mark(full, os.path.splitext(full)[0] + ".json")
        if sig is None or state.get(n) == sig:
            continue
        todo.append(n)
    if not todo:
        return 0, 0

    sent = fail = 0
    for n in todo:
        try:
            if send_one(args, state, n):
                sent += 1
                print("ส่งแล้ว %s  (เหลือ %d)" % (n, len(todo) - sent - fail))
            else:
                fail += 1
        except urllib.error.HTTPError as e:
            # 403 = โทเคนผิด ลองใหม่กี่ทีก็ไม่ผ่าน บอกให้รู้แล้วหยุดรอบนี้
            print("คลังปฏิเสธ (%s): %s" % (e.code, n), file=sys.stderr)
            if e.code == 403:
                return sent, -1
            fail += 1
        except (urllib.error.URLError, socket.timeout, OSError) as e:
            print("ส่งไม่สำเร็จ %s: %s" % (n, e), file=sys.stderr)
            return sent, -1              # เน็ตมีปัญหา หยุดรอบนี้ไว้ก่อน
    if sent:
        save_state(args.state, state)
    return sent, fail


def main():
    ap = argparse.ArgumentParser(description="ส่งรูปจาก Pi ขึ้นคลังภาพ")
    ap.add_argument("--to", required=True,
                    help="ที่อยู่ระบบมิเตอร์ เช่น http://192.168.1.50:8080")
    ap.add_argument("--token", default=os.environ.get("HUB_TOKEN",
                                                      "robot-push-change-me"))
    ap.add_argument("--dir", default=DEF_DIR, help="โฟลเดอร์รูปบน Pi")
    ap.add_argument("--state", default=DEF_STATE)
    ap.add_argument("--every", type=float, default=20.0,
                    help="วินาทีต่อรอบตรวจรูปใหม่")
    ap.add_argument("--once", action="store_true", help="ส่งรอบเดียวแล้วออก")
    args = ap.parse_args()
    args.dir = os.path.expanduser(args.dir)

    state = load_state(args.state)
    print("ส่งจาก %s -> %s" % (args.dir, args.to))
    print("เคยส่งไปแล้ว %d รูป" % len(state))

    backoff = args.every
    while True:
        if reachable(args.to):
            sent, fail = sweep(args, state)
            if fail == -1:
                backoff = min(backoff * 2, 300)   # มีปัญหา ถอยห่างขึ้นเรื่อย ๆ
            else:
                backoff = args.every
                if sent:
                    print("รอบนี้ส่ง %d รูป" % sent)
        else:
            backoff = min(backoff * 2, 300)
            print("ยังต่อคลังไม่ได้ รออีก %.0f วิ" % backoff)
        if args.once:
            return
        time.sleep(backoff)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nหยุดส่ง")
