#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ระบบจดมิเตอร์หอพัก — รันบนเครื่องที่เปิดตลอด ไม่ใช่บน Pi

หุ่นถ่ายรูปมิเตอร์ -> push.py ส่งมาที่นี่ -> เก็บแยกตามห้องและเดือน
เจ้าของหอเข้ามาคีย์เลขที่อ่านได้ ลูกบ้านเข้ามาดูเฉพาะห้องตัวเอง

ที่เก็บข้อมูลเป็นไฟล์ธรรมดาทั้งหมด ไม่มีฐานข้อมูล ตั้งใจให้กู้ง่าย
ถ้าโปรแกรมนี้พังในอนาคต รูปยังเรียงอยู่ในโฟลเดอร์ห้องให้เปิดดูได้ตามปกติ

    python3 hub.py --port 8080 --dir ~/meterhub

ครั้งแรกจะสุ่มรหัสเจ้าของหอมาให้ จดไว้ให้ดี
"""
import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import select
import shutil
import socket
import sys
import http.client
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote

import pages

PUSH_TOKEN = os.environ.get("HUB_TOKEN", "robot-push-change-me")
NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,120}\.jpg$")
ROOM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-/]{0,15}$")
KINDS = ("water", "power", "other")
# ★ AI มั่นใจถึงเกณฑ์นี้ + อ่านได้ครบ 4 หลัก -> ใส่เป็นค่าจริงให้เลย (rsrc = "ai")
#   คนยืนยัน/แก้ทีหลังได้เสมอ และค่าที่คนใส่ AI ทับไม่ได้  ตั้งด้วย --ai-auto (0 = ปิด)
AI_AUTO = float(os.environ.get("HUB_AI_AUTO", "0.75"))
KIND_TH = {"water": "น้ำ", "power": "ไฟ", "other": "อื่น ๆ"}
THUMB_W = 420
SESSION_HOURS = 12
PBKDF_ROUNDS = 200000

try:
    from PIL import Image
except ImportError:
    Image = None


# ================= รหัสผ่าน =================
def hash_pw(pw, salt=None):
    """เก็บรหัสเป็นแฮช ไม่เก็บตัวจริง

    ระบบนี้จะอยู่บนอินเทอร์เน็ตจริงผ่าน Cloudflare ถ้าไฟล์หลุด
    รหัสลูกบ้านทุกห้องจะหลุดตามไปด้วย การแฮชทำให้ไฟล์ที่หลุดไม่มีค่า
    """
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"),
                            salt.encode("utf-8"), PBKDF_ROUNDS)
    return salt, binascii.hexlify(h).decode()


def check_pw(pw, salt, want):
    _, got = hash_pw(pw, salt)
    return hmac.compare_digest(got, want)        # เทียบแบบไม่ให้จับเวลาได้


def new_pw(n=6):
    """รหัสลูกบ้าน — ตัดตัวที่อ่านสับสนออก (0/O, 1/l/I) เพราะต้องเขียนใส่กระดาษให้เขา"""
    return "".join(secrets.choice("23456789ABCDEFGHJKLMNPQRSTUVWXYZ")
                   for _ in range(n))


# ================= ข้อมูล =================
class Data:
    def __init__(self, root):
        self.root = os.path.expanduser(root)
        self.photos = os.path.join(self.root, "photos")
        self.thumbs = os.path.join(self.root, "thumbs")
        self.meta = os.path.join(self.root, "meta")
        for d in (self.root, self.photos, self.thumbs, self.meta):
            os.makedirs(d, exist_ok=True)
        self.lock = threading.Lock()
        # เลขรุ่นของข้อมูลรูป — เปลี่ยนทุกครั้งที่มีรูปเข้า/แก้/ลบ หน้าเจ้าของหอถามทุกไม่กี่วิ
        # ถ้าเลขเปลี่ยนค่อยโหลดใหม่ รูปที่หุ่นเพิ่งถ่ายจึงขึ้นเองโดยไม่ต้องรีเฟรช
        self.boot = secrets.token_hex(3)
        self.n = 0
        self.rooms_path = os.path.join(self.root, "rooms.json")
        self.owner_path = os.path.join(self.root, "owner.json")
        self.secret = self._secret()

    # ---- ไฟล์เล็ก ๆ ----
    def _secret(self):
        p = os.path.join(self.root, "secret.key")
        try:
            with open(p, "rb") as f:
                k = f.read().strip()
            if len(k) >= 32:
                return k
        except OSError:
            pass
        k = secrets.token_bytes(32)
        with open(p, "wb") as f:
            f.write(k)
        os.chmod(p, 0o600)
        return k

    @staticmethod
    def _load(path, default):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    @staticmethod
    def _save(path, obj):
        tmp = path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)

    # ---- เจ้าของหอ ----
    def owner(self):
        return self._load(self.owner_path, {})

    def set_owner_pw(self, pw):
        salt, h = hash_pw(pw)
        self._save(self.owner_path, {"salt": salt, "hash": h,
                                     "set": int(time.time())})

    # ---- ห้อง ----
    def rooms(self):
        return self._load(self.rooms_path, {})

    def room_list(self):
        r = self.rooms()
        return sorted(r.keys(), key=lambda s: (len(s), s))

    def add_room(self, room, name="", pw=None):
        with self.lock:
            rooms = self.rooms()
            pw = pw or new_pw()
            salt, h = hash_pw(pw)
            rooms[room] = {"name": name, "salt": salt, "hash": h,
                           "created": rooms.get(room, {}).get(
                               "created", int(time.time()))}
            self._save(self.rooms_path, rooms)
        return pw

    def set_room(self, room, name=None):
        with self.lock:
            rooms = self.rooms()
            if room not in rooms:
                return False
            if name is not None:
                rooms[room]["name"] = name
            self._save(self.rooms_path, rooms)
        return True

    def del_room(self, room):
        with self.lock:
            rooms = self.rooms()
            if rooms.pop(room, None) is None:
                return False
            self._save(self.rooms_path, rooms)
        return True

    # ---- รูปและข้อมูลประกอบ ----
    @staticmethod
    def safe_name(n):
        b = os.path.basename(n or "")
        return b if NAME_RE.match(b) else None

    @staticmethod
    def month_of(ts):
        return time.strftime("%Y-%m", time.localtime(ts))

    @staticmethod
    def ts_from_name(name):
        m = re.search(r"(\d{8})_(\d{6})", name)
        if not m:
            return None
        try:
            return int(time.mktime(time.strptime(m.group(1) + m.group(2),
                                                 "%Y%m%d%H%M%S")))
        except ValueError:
            return None

    def rel_path(self, m):
        """รูปอยู่ที่ไหนในโฟลเดอร์ — แยกตามห้องและเดือนให้คนเปิดดูเองได้"""
        room = m.get("room") or "_inbox"
        return os.path.join(room, self.month_of(m["ts"]), m["name"])

    def full_path(self, m):
        return os.path.join(self.photos, self.rel_path(m))

    def meta_path(self, name):
        return os.path.join(self.meta, name + ".json")

    def meta_of(self, name):
        return self._load(self.meta_path(name), None)

    def bump(self):
        self.n += 1

    @property
    def ver(self):
        return "%s-%d" % (self.boot, self.n)

    @staticmethod
    def clean_ai(v):
        """ช่อง ai จากหุ่น (สิ่งที่ AI เดา) — รับเฉพาะรูปแบบที่ถูกต้อง"""
        if not isinstance(v, dict):
            return None
        guess = "".join(c for c in str(v.get("guess") or "") if c.isdigit())[:10]
        try:
            conf = max(0.0, min(1.0, float(v.get("conf") or 0)))
        except (TypeError, ValueError):
            conf = 0.0
        out = {"guess": guess, "conf": round(conf, 3)}
        if v.get("err"):
            out["err"] = 1
        if v.get("kind") in ("water", "power"):       # AI ดูจากรูปทรงว่าเป็นมิเตอร์อะไร
            out["kind"] = v["kind"]
            try:
                out["kconf"] = round(max(0.0, min(1.0, float(v.get("kconf") or 0))), 3)
            except (TypeError, ValueError):
                out["kconf"] = 0.0
        return out

    @staticmethod
    def clean_reading(v):
        return "".join(c for c in str(v or "") if c.isdigit() or c == ".")[:10]

    def merge_robot(self, m, inc):
        """เอาข้อมูลที่หุ่นส่งมา (เฉพาะช่องที่มี) ทับลง m

        กติกา:
          ★ ช่องที่เจ้าของหอแก้เองในเว็บ (m["owner_set"]) หุ่นทับไม่ได้
          ★ ห้อง/ชนิด: ค่าใหม่จากหุ่นชนะ ถ้าไม่ว่าง (คนถ่ายติดป้ายทีหลัง = ตั้งใจแก้)
            ส่งมาว่าง = คงของเดิม กันการเผลอลบงานที่จัดไว้แล้ว
          ★ ค่ามิเตอร์: รับจากหุ่นถ้าช่องยังว่าง หรือค่าเดิมก็มาจากหุ่นเอง
            (รูปมักถูกส่งรอบแรกก่อนคนกดยืนยันค่า แล้วตามมาด้วยค่าทีหลัง)
            ค่าที่เจ้าของหอกรอก/ยืนยันเองในเว็บ หุ่นทับไม่ได้
          ★ ai (สิ่งที่ AI เดา): ของใหม่ชนะเสมอ ไม่ใช่ค่าจริง แค่ให้เจ้าของหอกดยืนยัน
          ★ หมายเหตุ: ของเดิมชนะ"""
        own = set(m.get("owner_set") or ())
        room = str(inc.get("room") or "")
        if room and ROOM_RE.match(room) and "room" not in own:
            m["room"] = room
        if inc.get("kind") in KINDS and "kind" not in own:
            if inc["kind"] != "other":
                m["kind"] = inc["kind"]       # คนเลือกน้ำ/ไฟบนหุ่นเอง ชนะที่ AI เดา
                m.pop("ksrc", None)
            elif m.get("ksrc") != "ai":
                m["kind"] = "other"
        rd = self.clean_reading(inc.get("reading"))
        # ★ คนยืนยันบนหุ่นเลขเดียวกับที่ AI ใส่ไว้ = ตรวจแล้ว (rsrc เปลี่ยนเป็น robot)
        if rd and (rd != m.get("reading") or m.get("rsrc") == "ai") and (
                not m.get("reading") or m.get("rsrc") in ("robot", "ai")):
            m["reading"], m["rsrc"], m["rset"] = rd, "robot", int(time.time())
        if not m.get("note") and inc.get("note"):
            m["note"] = str(inc["note"])[:200]
        if "ai" in inc:
            ai = self.clean_ai(inc["ai"])
            if ai is not None:
                m["ai"] = ai
        self.auto_ai(m, own)
        return m

    @staticmethod
    def auto_ai(m, own):
        """AI มั่นใจพอ -> ใส่ชนิดมิเตอร์/ค่าให้เลย ไม่ต้องรอคนกด

        ★ ใส่เฉพาะช่องที่ยังว่าง หรือที่ AI ใส่ไว้เองก่อนหน้า — ไม่ทับค่าที่คนใส่
        ★ เวลายืนยัน (rset) ของค่าจาก AI = เวลาถ่าย ไม่ใช่เวลาที่อ่าน
          เพราะ AI อ่านรูปเก่าย้อนหลังได้ ถ้าใช้เวลาอ่าน รูปเก่าจะไปทับค่าที่คนยืนยันไว้ใหม่กว่า"""
        ai = m.get("ai") or {}
        if AI_AUTO <= 0 or ai.get("err"):
            return
        if (ai.get("kind") in ("water", "power") and (ai.get("kconf") or 0) >= AI_AUTO
                and "kind" not in own and m.get("kind") in ("other", None, "")
                or (m.get("ksrc") == "ai" and ai.get("kind") in ("water", "power")
                    and "kind" not in own)):
            m["kind"], m["ksrc"] = ai["kind"], "ai"
        g = ai.get("guess") or ""
        if (len(g) == 4 and g.isdigit() and (ai.get("conf") or 0) >= AI_AUTO
                and m.get("kind") in ("water", "power")     # ไม่รู้ว่าน้ำหรือไฟ = ขึ้นแดชบอร์ดไม่ได้
                and "reading" not in own
                and (not m.get("reading") or m.get("rsrc") == "ai")):
            m["reading"], m["rsrc"], m["rset"] = g, "ai", int(m.get("ts") or time.time())

    def put_photo(self, name, data, meta):
        ts = self.ts_from_name(name) or int(meta.get("ts") or time.time())
        with self.lock:
            old = self.meta_of(name)
            if old:                                   # ส่งซ้ำ: รักษาค่าที่คีย์ไว้แล้ว
                m = dict(old)
                m.update({"size": len(data), "recv": int(time.time())})
                try:
                    os.remove(self.full_path(old))
                except OSError:
                    pass
            else:
                m = {"name": name, "ts": ts, "room": "", "kind": "other",
                     "size": len(data), "recv": int(time.time()),
                     "reading": "", "note": ""}
            self.merge_robot(m, meta)
            p = self.full_path(m)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p + ".part", "wb") as f:
                f.write(data)
            os.replace(p + ".part", p)
            if meta.get("preview"):     # รูปย่อขนาดกลางมาก่อนตอนมีคนดูภาพสด รูปเต็มตามมาทีหลัง
                m["preview"] = 1
            else:
                m.pop("preview", None)
            self._save(self.meta_path(name), m)
            self.bump()
        if not os.path.exists(os.path.join(self.thumbs, name)):
            self._thumb(name, data)
        return m

    def update_meta(self, name, inc):
        """หุ่นส่งมาแค่ข้อมูล (รูปเคยส่งแล้ว) — None ถ้า hub ไม่มีรูปนี้แล้ว"""
        with self.lock:
            m = self.meta_of(name)
            if not m:
                return None
            old_path = self.full_path(m)
            self.merge_robot(m, inc)
            new_path = self.full_path(m)
            if new_path != old_path:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                try:
                    shutil.move(old_path, new_path)
                except OSError:
                    pass
            self._save(self.meta_path(name), m)
            self.bump()
        return m

    def put_thumb(self, name, data):
        p = os.path.join(self.thumbs, name)
        with open(p + ".part", "wb") as f:
            f.write(data)
        os.replace(p + ".part", p)
        self.bump()

    def _thumb(self, name, data):
        if Image is None:
            return
        try:
            import io
            im = Image.open(io.BytesIO(data))
            im.thumbnail((THUMB_W, THUMB_W))
            im.convert("RGB").save(os.path.join(self.thumbs, name),
                                   "JPEG", quality=78)
        except Exception as e:
            print("thumb:", name, e, file=sys.stderr)

    def update_photo(self, name, patch):
        with self.lock:
            m = self.meta_of(name)
            if not m:
                return None
            moved = ("room" in patch and patch["room"] != m.get("room"))
            old_path = self.full_path(m)
            if "reading" in patch:
                patch["reading"] = self.clean_reading(patch["reading"])
            own = set(m.get("owner_set") or ())
            for k in ("room", "kind", "reading", "note"):
                if k in patch:
                    # ★ กดบันทึก/ยืนยันค่าที่ AI ใส่ให้ = เจ้าของหอตรวจแล้ว แม้เลขเท่าเดิม
                    verify = (k == "reading" and patch[k] and m.get("rsrc") == "ai")
                    if k == "kind" and m.get("ksrc") == "ai" and patch[k] in ("water", "power"):
                        verify = True
                    if patch[k] != m.get(k, "") or verify:
                        own.add(k)         # เจ้าของหอแก้เอง -> หุ่น/AI ทับไม่ได้อีก
                        if k == "reading":
                            m["rsrc"], m["rset"] = "owner", int(time.time())
                        if k == "kind":
                            m.pop("ksrc", None)
                    m[k] = patch[k]
            m["owner_set"] = sorted(own)
            if m.get("room") and not ROOM_RE.match(m["room"]):
                m["room"] = ""
            if m.get("kind") not in KINDS:
                m["kind"] = "other"
            if moved:
                new_path = self.full_path(m)
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                try:
                    shutil.move(old_path, new_path)
                except OSError:
                    pass
            self._save(self.meta_path(name), m)
            self.bump()
        return m

    def delete_photo(self, name):
        m = self.meta_of(name)
        if not m:
            return False
        for p in (self.full_path(m), os.path.join(self.thumbs, name),
                  self.meta_path(name)):
            try:
                os.remove(p)
            except OSError:
                pass
        self.bump()
        return True

    def all_meta(self):
        out = []
        try:
            names = os.listdir(self.meta)
        except OSError:
            return out
        for n in names:
            if not n.endswith(".json"):
                continue
            m = self._load(os.path.join(self.meta, n), None)
            if m and m.get("name"):
                out.append(m)
        out.sort(key=lambda m: m["ts"], reverse=True)
        return out

    def photos_of(self, room=None, kind=None, month=None, unassigned=False,
                  limit=300):
        # "ยังไม่ได้จัดเข้าห้อง" รวมถึงรูปที่ระบุห้องมาแต่เป็นห้องที่ไม่มีในระบบ
        # เช่นพิมพ์เลขห้องผิดตอนถ่าย ไม่งั้นรูปจะหายไปเลย ไม่โผล่ที่ไหน
        known = set(self.rooms()) if unassigned else None
        out = []
        for m in self.all_meta():
            if unassigned and m.get("room") and m["room"] in known:
                continue
            if room is not None and m.get("room") != room:
                continue
            if kind and m.get("kind") != kind:
                continue
            if month and self.month_of(m["ts"]) != month:
                continue
            out.append(m)
            if len(out) >= limit:
                break
        return out

    def readings(self, room):
        """ค่ามิเตอร์ของห้องหนึ่ง เรียงตามเดือน พร้อมหน่วยที่ใช้ไป

        หน่วยที่ใช้ = เลขเดือนนี้ ลบ เลขเดือนก่อน ซึ่งคำนวณให้เลยเพราะ
        เป็นตัวเลขที่ทั้งเจ้าของหอและลูกบ้านอยากรู้จริง ๆ ไม่ใช่เลขหน้าปัด
        """
        by = {}
        for m in self.all_meta():
            if m.get("room") != room or m.get("kind") not in ("water", "power"):
                continue
            val = str(m.get("reading", "")).strip()
            if not val:
                continue
            try:
                num = float(val)
            except ValueError:
                continue
            mk = self.month_of(m["ts"])
            k = (m["kind"], mk)
            # เดือนเดียวกันมีหลายใบ: เอาใบที่ "ยืนยันค่าล่าสุด" (กดยืนยันใบไหน ใบนั้นขึ้นข้างบน)
            # รูปเก่าที่ไม่มีเวลายืนยัน ใช้เวลาถ่ายแทน
            when = (m.get("rset") or m["ts"], m["ts"])
            if k not in by or when > by[k]["when"]:
                by[k] = {"ts": m["ts"], "value": num, "photo": m["name"],
                         "when": when, "src": m.get("rsrc") or ""}

        out = {}
        for kind in ("water", "power"):
            rows = sorted(((mk, v) for (k, mk), v in by.items() if k == kind),
                          key=lambda r: r[0])
            series = []
            prev = None
            for mk, v in rows:
                used = round(v["value"] - prev, 2) if prev is not None else None
                series.append({"month": mk, "value": v["value"], "used": used,
                               "ts": v["ts"], "photo": v["photo"], "src": v["src"]})
                prev = v["value"]
            out[kind] = series
        return out


# ================= เซสชัน =================
def sign(secret, payload):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    b = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = hmac.new(secret, b.encode(), hashlib.sha256).hexdigest()[:32]
    return b + "." + sig


def unsign(secret, tok):
    try:
        b, _, sig = (tok or "").partition(".")
        want = hmac.new(secret, b.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, want):
            return None
        pad = "=" * (-len(b) % 4)
        p = json.loads(base64.urlsafe_b64decode(b + pad))
        if p.get("exp", 0) < time.time():
            return None
        return p
    except Exception:
        return None


# ---- กันเดารหัส ----
_tries = {}
_tries_lock = threading.Lock()


def throttled(ip):
    with _tries_lock:
        t = _tries.get(ip)
        if not t:
            return False
        if t["until"] > time.time():
            return True
        if time.time() - t["last"] > 900:
            _tries.pop(ip, None)
        return False


def note_fail(ip):
    with _tries_lock:
        t = _tries.setdefault(ip, {"n": 0, "until": 0, "last": 0})
        t["n"] += 1
        t["last"] = time.time()
        if t["n"] >= 6:
            # ล็อกนานขึ้นเรื่อย ๆ 1, 2, 4 ... นาที สูงสุดครึ่งชั่วโมง
            t["until"] = time.time() + min(1800, 60 * 2 ** (t["n"] - 6))


def note_ok(ip):
    with _tries_lock:
        _tries.pop(ip, None)


# ================= เซิร์ฟเวอร์ =================
class Handler(BaseHTTPRequestHandler):
    server_version = "MeterHub/1.0"
    protocol_version = "HTTP/1.1"
    # ★ ปิด Nagle ทุกสายที่ต่อเข้ามา — http.server ส่งหัวกับเนื้อความแยกสองครั้ง
    #   ก้อนที่สองถูกกลั้นรอการตอบรับซึ่งอีกฝั่งหน่วงไว้ 40ms (Linux) ถึง 200ms
    #   (Windows) ทุกคำขอที่ผ่าน hub จึงช้าเพิ่มทั้งที่ไม่มีใครทำงานอยู่เลย
    disable_nagle_algorithm = True
    data = None
    verbose = False
    owner_path = "/owner"
    robot_url = "http://raspberrypi.local:9000"
    robot_auth = ""

    def log_message(self, fmt, *a):
        if self.verbose:
            super().log_message(fmt, *a)

    # ---- พื้นฐาน ----
    def client_ip(self):
        # อยู่หลัง Cloudflare จะเห็น IP ของ Cloudflare ถ้าไม่อ่านหัวนี้
        # ซึ่งทำให้การกันเดารหัสไปล็อกคนทั้งโลกพร้อมกัน
        for h in ("CF-Connecting-IP", "X-Forwarded-For"):
            v = self.headers.get(h)
            if v:
                return v.split(",")[0].strip()
        return self.client_address[0]

    def https(self):
        return (self.headers.get("X-Forwarded-Proto", "").lower() == "https")

    def send(self, code, body=b"", ctype="text/plain; charset=utf-8",
             extra=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        # ฝังหน้าเราในเว็บอื่นไม่ได้ (กันหลอกให้กด) แต่ฝังในเว็บตัวเองได้
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def jsend(self, obj, code=200, extra=None):
        self.send(code, json.dumps(obj, ensure_ascii=False),
                  "application/json; charset=utf-8", extra)

    def html(self, s):
        self.send(200, s, "text/html; charset=utf-8",
                  {"Cache-Control": "no-store"})

    def body_bytes(self, limit=32 * 1024 * 1024):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            return None
        return self.rfile.read(n) if n else b""

    def body_json(self):
        try:
            return json.loads(self.body_bytes(1 << 20) or b"{}")
        except ValueError:
            return {}

    # ---- เซสชัน ----
    def session(self):
        raw = ""
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "mh":
                raw = v
        return unsign(self.data.secret, raw)

    def set_session(self, payload):
        tok = sign(self.data.secret, payload)
        bits = ["mh=" + tok, "Path=/", "HttpOnly", "SameSite=Lax",
                "Max-Age=%d" % (SESSION_HOURS * 3600)]
        if self.https():
            bits.append("Secure")
        return {"Set-Cookie": "; ".join(bits)}

    def clear_session(self):
        return {"Set-Cookie": "mh=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"}

    def need(self, role=None):
        s = self.session()
        if not s or (role and s.get("role") != role):
            self.jsend({"error": "ต้องเข้าสู่ระบบก่อน"}, 401)
            return None
        return s


    # ---- ส่งต่อไปหน้าคุมหุ่นบน Pi ----
    # ★ ทำไมต้องส่งต่อ ไม่ใช่แค่ลิงก์ไปที่ Pi ตรง ๆ:
    #   ถ้าเข้าเว็บจากนอกบ้านผ่าน Cloudflare ลิงก์ที่ชี้ไป raspberrypi.local
    #   จะเปิดไม่ได้เลย เพราะชื่อนั้นมีอยู่แค่ในวงบ้าน
    #   ส่งต่อผ่านตัวเองทำให้หน้าคุมหุ่นเปิดได้จากทุกที่ และได้ด่านรหัส
    #   ของเจ้าของหอมาคุ้มให้ฟรี ๆ ไม่ต้องเปิดพอร์ต 9000 ออกเน็ต
    #
    # ★ ทำไมดักทุกเส้นทางที่ไม่ใช่ของตัวเอง แทนที่จะใส่ไว้ใต้ /owner/robot/:
    #   หน้าคุมหุ่นเรียก /stream /status /photo แบบเส้นทางเต็มจากรากเว็บ
    #   ถ้าย้ายไปอยู่ใต้โฟลเดอร์ย่อย ทุกคำขอจะยิงผิดที่หมด
    #   ต้องไปไล่แก้ที่อยู่ในหน้าเว็บของหุ่นซึ่งเปราะมาก
    ROBOT_SKIP = ("/api/", "/t/", "/p/", "/push", "/out", "/healthz")

    def robot_claims(self, path):
        if path in ("/", self.owner_path) or path.startswith(self.ROBOT_SKIP):
            return False
        return True

    def up_conn(self, fresh=False, timeout=15):
        """สายไปหาหุ่น ใช้ซ้ำได้ตราบที่เบราว์เซอร์ยังใช้สายเดิมคุยกับเรา

        ★ หน้าคุมหุ่นถาม /status ทุก 250 มิลลิวินาที ถ้าเปิดสาย TCP ใหม่ทุกครั้ง
          จะเป็นวินาทีละสี่สาย คูณด้วยเวลาจับมือของ TCP ที่วิ่งข้ามเน็ตไปหา Pi
          คำขอจะเริ่มซ้อนกันจนตอบไม่ทัน แล้วหน้าเว็บจะคิดว่าหุ่นตายทั้งที่ยังดีอยู่
        """
        c = getattr(self, "_up", None)
        if fresh and c is not None:
            try:
                c.close()
            except Exception:
                pass
            c = None
        if c is None:
            u = self.robot_url.split("://", 1)[-1]
            host, _, port = u.partition(":")
            c = http.client.HTTPConnection(host, int(port or 80),
                                           timeout=timeout)
            self._up = c
        return c

    def proxy_robot(self, path):
        s = self.session()
        if not s or s.get("role") != "owner":
            return self.send(404, "ไม่มีหน้านี้")
        # ต้องส่งต่อทั้งเส้นทางและพารามิเตอร์หลัง ? ด้วย
        # ไม่งั้นคำสั่งอย่าง /ctx?room=305 จะกลายเป็น /ctx เปล่า ๆ
        # แล้วค่าที่ตั้งจะไม่ถูกส่งไปถึงหุ่นเลย
        head, sep, qs = path.partition("?")
        if head == self.owner_path + "/robot":
            head = "/"
        path = head + sep + qs
        if "websocket" in (self.headers.get("Upgrade") or "").lower():
            return self.proxy_ws(path)
        # สตรีมภาพไม่มีวันจบเอง ต้องแยกสายของตัวเองและไม่ตั้งเวลาหมดอายุสั้น ๆ
        stream = path.startswith("/stream")
        hdrs = {}
        if self.robot_auth:
            hdrs["Authorization"] = "Basic " + self.robot_auth
        body = None
        if self.command == "POST":
            body = self.body_bytes(8 * 1024 * 1024) or b""
            hdrs["Content-Type"] = self.headers.get(
                "Content-Type", "application/octet-stream")
            hdrs["Content-Length"] = str(len(body))

        conn = r = None
        err = ""
        # ลองสองรอบ เพราะสายที่ใช้ซ้ำอาจถูกอีกฝั่งปิดไปแล้วระหว่างที่ว่าง
        # ซึ่งจะรู้ก็ต่อเมื่อส่งคำขอออกไปแล้วเจอปลายสายปิด
        for attempt in (0, 1):
            try:
                if stream:
                    u = self.robot_url.split("://", 1)[-1]
                    host, _, port = u.partition(":")
                    conn = http.client.HTTPConnection(host, int(port or 80),
                                                      timeout=None)
                else:
                    conn = self.up_conn(fresh=bool(attempt))
                conn.request(self.command, path, body, hdrs)
                r = conn.getresponse()
                break
            except (OSError, http.client.HTTPException) as e:
                err = str(e)
                r = None
                if stream:
                    break
        if r is None:
            self._up = None
            return self.send(
                502, "ต่อหุ่นไม่ได้ — หุ่นอาจปิดอยู่หรือไม่ได้ต่อเน็ต\n%s" % err,
                "text/plain; charset=utf-8")

        ctype = r.getheader("Content-Type", "application/octet-stream")
        clen = r.getheader("Content-Length")
        if ctype.startswith("multipart/x-mixed-replace"):
            return self.pipe_mjpeg(r, conn, ctype)
        self.send_response(r.status)
        self.send_header("Content-Type", ctype)
        if clen is not None:
            self.send_header("Content-Length", clen)
        else:
            # ไม่รู้ความยาว (เช่นสตรีมภาพ) จบด้วยการปิดการเชื่อมต่อแทน
            self.send_header("Connection", "close")
            self.close_connection = True
        self.send_header("Cache-Control", "no-store")
        # /frame บอกเลขเฟรมทางหัวนี้ ถ้าไม่ส่งต่อ หน้าเว็บจะขอเฟรมเดิมซ้ำ
        seq = r.getheader("X-Frame-Seq")
        if seq is not None:
            self.send_header("X-Frame-Seq", seq)
        self.end_headers()
        if self.command == "HEAD":
            r.read()
            return
        try:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except OSError:
            self._up = None     # สายพัง รอบหน้าค่อยเปิดใหม่
            try:
                conn.close()
            except Exception:
                pass

    # ข้อมูลประจำตัวของเบราว์เซอร์ที่ห้ามส่งต่อไปถึงหุ่น
    WS_DROP = ("host", "cookie", "authorization", "content-length")

    def proxy_ws(self, path):
        """ส่งต่อสาย WebSocket (ภาพสด + คำสั่งขับ) ไปหุ่นแบบท่อตรง

        ★ หลังจับมือเสร็จ hub ไม่แตะข้อมูลเลย แค่ส่งไบต์ต่อสองทิศ
          การตอบรับเฟรมของเบราว์เซอร์จึงวิ่งกลับไปถึงหุ่นจริง หุ่นคุมจังหวะ
          ส่งได้เองว่าท่อทั้งเส้น (หุ่น -> hub -> Funnel -> มือถือ) ว่างหรือยัง
          ไม่มีเฟรมไปกองที่ hub ได้เลย
        """
        u = self.robot_url.split("://", 1)[-1].rstrip("/")
        host, _, port = u.partition(":")
        try:
            up = socket.create_connection((host, int(port or 80)), timeout=10)
            up.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as e:
            return self.send(502, "ต่อหุ่นไม่ได้ — %s" % e)
        lines = ["GET %s HTTP/1.1" % path, "Host: %s" % u]
        for k, v in self.headers.items():
            if k.lower() not in self.WS_DROP:
                lines.append("%s: %s" % (k, v))
        if self.robot_auth:
            lines.append("Authorization: Basic " + self.robot_auth)
        buf = b""
        try:
            up.sendall(("\r\n".join(lines) + "\r\n\r\n").encode("latin-1"))
            while b"\r\n\r\n" not in buf:
                chunk = up.recv(4096)
                if not chunk or len(buf) > 16384:
                    raise OSError("หุ่นตอบการจับมือไม่ครบ")
                buf += chunk
        except (OSError, UnicodeError) as e:
            up.close()
            return self.send(502, "ต่อหุ่นไม่ได้ — %s" % e)
        self.close_connection = True
        cli = self.connection
        try:
            cli.sendall(buf)                 # หัวตอบกลับ 101 + ข้อมูลที่ติดมา
        except OSError:
            up.close()
            return
        if not buf.startswith((b"HTTP/1.1 101", b"HTTP/1.0 101")):
            up.close()                       # หุ่นปฏิเสธ (401/503) — ส่งคำตอบไปแล้ว จบ
            return
        up.settimeout(None)
        try:
            cli.settimeout(None)
        except OSError:
            pass

        def up_from_browser():
            # อ่านผ่าน rfile เพราะอาจมีไบต์ค้างอยู่ในบัฟเฟอร์ของมันแล้ว
            try:
                while True:
                    d = self.rfile.read1(65536)
                    if not d:
                        break
                    up.sendall(d)
            except (OSError, ValueError):
                pass
            finally:
                try:
                    up.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

        t = threading.Thread(target=up_from_browser, daemon=True)
        t.start()
        try:
            while True:
                d = up.recv(65536)
                if not d:
                    break
                cli.sendall(d)
        except OSError:
            pass
        finally:
            for sk in (cli, up):
                try:
                    sk.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            t.join(timeout=2)
            up.close()

    def pipe_mjpeg(self, r, conn, ctype):
        """ส่งต่อภาพสตรีม โดยแยก "คนอ่านจากหุ่น" กับ "คนเขียนลงเบราว์เซอร์"

        ★ ทำไมต้องแยกเป็นสองเธรด ทั้งที่อ่านแล้วเขียนในลูปเดียวดูง่ายกว่า:
          การเขียนลง socket เป็นการรอจนกว่าจะเขียนออกได้ ถ้าเบราว์เซอร์ช้า
          ลูปจะค้างอยู่ตรงนั้น ซึ่งแปลว่าระหว่างนั้นเราหยุดอ่านจาก Pi ด้วย
          Pi จึงเขียนไม่ออก ทิ้งทุกเฟรม แล้วเฟรมที่หลุดไปได้ก็เก่าไปแล้ว
          วัดจากของจริง: ภาพที่ออกไปเก่ากว่าความจริงถึง 153 วินาที
        ★ แยกแล้วคนอ่านจะดูดจาก Pi เต็มความเร็วเสมอ Pi จึงเห็นว่าปลายทางไหว
          ส่วนคนเขียนหยิบเฉพาะเฟรมล่าสุดไปส่ง เฟรมที่ส่งไม่ทันถูกข้ามทิ้งไปเอง
          ยอมให้ภาพขาดดีกว่าปล่อยให้ภาพเก่าค้างสะสม
        """
        sock = self.connection
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(15)      # เขียนค้างนานเกินไป = ปลายทางตายแล้ว
        except OSError:
            pass

        latest = {"buf": None, "n": 0}
        # ★ ใช้ Condition ไม่ใช่ Lock เปล่า ๆ เพราะคนเขียนต้องถูกปลุกทันที
        #   ที่เฟรมใหม่มาถึง ถ้าให้มันวนเช็คเองทุก 4 มิลลิวินาที
        #   จะมีช่วงรอเปล่า ๆ ติดมาทุกเฟรม ซึ่งสะสมเป็นความหน่วงที่ตาจับได้
        cond = threading.Condition()
        stop = threading.Event()

        def reader():
            try:
                while not stop.is_set():
                    line = r.readline(512)
                    if not line:
                        break
                    if not line.startswith(b"--"):
                        continue
                    n = 0
                    while True:          # อ่านหัวเฟรมจนถึงบรรทัดว่าง
                        h = r.readline(512)
                        if not h or h in (b"\r\n", b"\n"):
                            break
                        if h[:15].lower() == b"content-length:":
                            try:
                                n = int(h.split(b":", 1)[1])
                            except ValueError:
                                n = 0
                    if n <= 0 or n > 32 * 1024 * 1024:
                        continue
                    data = r.read(n)
                    if len(data) < n:
                        break
                    with cond:
                        latest["buf"] = data
                        latest["n"] += 1
                        cond.notify_all()
            except (OSError, http.client.HTTPException):
                pass
            finally:
                stop.set()
                with cond:
                    cond.notify_all()

        t = threading.Thread(target=reader, daemon=True)
        t.start()

        sent = 0
        sized = False
        try:
            while not stop.is_set():
                with cond:
                    if latest["n"] == sent and not stop.is_set():
                        cond.wait(1.0)       # ถูกปลุกทันทีที่เฟรมใหม่มาถึง
                    n, data = latest["n"], latest["buf"]
                if data is None or n == sent:
                    continue
                sent = n
                if not sized:
                    # จำกัดคิวฝั่งเราเอง ไม่งั้นระบบปฏิบัติการจะขยายให้
                    # เป็นหลายเมกะไบต์ แล้วคิวจะอมเฟรมได้อีกหลายสิบใบ
                    # ★ ตั้งให้พอดีหนึ่งเฟรม ไม่ใช่เผื่อไว้เยอะ ๆ
                    #   ทุกไบต์ที่คิวอมไว้ได้เกินหนึ่งเฟรม คือภาพเก่าที่ค้างรอคิว
                    #   128 กิโลไบต์กับเฟรม 90 กิโลไบต์ = อมได้เฟรมครึ่ง
                    #   ซึ่งแปลว่าเพิ่มความหน่วงไปครึ่งเฟรมฟรี ๆ
                    try:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF,
                                        max(32 * 1024, len(data)))
                    except OSError:
                        pass
                    sized = True
                head = (b"--FRAME\r\nContent-Type: image/jpeg\r\n"
                        + ("Content-Length: %d\r\n\r\n" % len(data)).encode())
                self.wfile.write(head + data + b"\r\n")
        except (OSError, socket.timeout):
            pass                 # ปิดแท็บไปแล้ว เรื่องปกติของสตรีม
        finally:
            stop.set()
            try:
                conn.close()     # ตัดสายฝั่ง Pi ด้วย ไม่ปล่อยค้าง
            except Exception:
                pass

    # ---- เส้นทาง ----
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        path, _, qs = self.path.partition("?")
        q = {k: v[0] for k, v in parse_qs(qs).items()}
        d = self.data
        s = self.session()

        if path == "/healthz":
            # meta = รู้จัก /push-meta (push.py ส่งเฉพาะข้อมูลที่เปลี่ยน ไม่ส่งรูปซ้ำ)
            return self.jsend({"ok": True, "meta": 1})

        # เว็บลูกบ้านกับเว็บเจ้าของหอแยกทางเข้ากันคนละทาง
        # หน้าลูกบ้านไม่มีอะไรบอกใบ้ว่าทางเข้าเจ้าของหออยู่ตรงไหน
        if path == "/":
            if s and s.get("role") == "tenant":
                return self.html(pages.TENANT)
            return self.html(pages.login_page("tenant"))

        if path == self.owner_path:
            if s and s.get("role") == "owner":
                return self.html(
                    pages.OWNER.replace("__OWNER_PATH__", self.owner_path))
            return self.html(pages.login_page("owner", self.owner_path))

        if path == "/out":
            to = q.get("to", "/")
            if not to.startswith("/") or to.startswith("//"):
                to = "/"
            return self.send(302, b"", "text/plain",
                             dict(Location=to, **self.clear_session()))

        # ---- รูป ----
        if path.startswith("/p/") or path.startswith("/t/"):
            name = d.safe_name(unquote(path.split("/", 2)[2]))
            m = d.meta_of(name) if name else None
            if not m:
                return self.send(404, "ไม่มีรูปนี้")
            if not s:
                return self.send(403, "ต้องเข้าสู่ระบบก่อน")
            if s.get("role") == "tenant" and m.get("room") != s.get("room"):
                return self.send(403, "ดูได้เฉพาะห้องของตัวเอง")
            p = (os.path.join(d.thumbs, name) if path.startswith("/t/")
                 else d.full_path(m))
            if not os.path.exists(p):
                p = d.full_path(m)
            try:
                with open(p, "rb") as f:
                    body = f.read()
            except OSError:
                return self.send(404, "ไฟล์หาย")
            return self.send(200, body, "image/jpeg",
                             {"Cache-Control": "private, max-age=86400"})

        # ---- ข้อมูลฝั่งลูกบ้าน ----
        if path == "/api/me":
            if not s:
                return self.jsend({"role": None})
            if s["role"] == "tenant":
                room = s["room"]
                info = d.rooms().get(room, {})
                return self.jsend({
                    "role": "tenant", "room": room,
                    "name": info.get("name", ""),
                    "readings": d.readings(room),
                    "photos": [self._pub(m, owner=False)
                               for m in d.photos_of(room=room)],
                })
            return self.jsend({"role": "owner"})

        # ---- ข้อมูลฝั่งเจ้าของหอ ----
        if path.startswith("/api/owner/"):
            if not self.need("owner"):
                return
            what = path[len("/api/owner/"):]

            if what == "rooms":
                rooms = d.rooms()
                month = q.get("month") or d.month_of(time.time())
                out = []
                for r in d.room_list():
                    rd = d.readings(r)
                    done = {}
                    for kind in ("water", "power"):
                        cur = [x for x in rd[kind] if x["month"] == month]
                        done[kind] = cur[0] if cur else None
                    shots = len(d.photos_of(room=r, month=month))
                    out.append({"room": r, "name": rooms[r].get("name", ""),
                                "shots": shots, **{k: done[k] for k in done}})
                return self.jsend({"month": month, "rooms": out,
                                   "inbox": len(d.photos_of(unassigned=True))})

            if what == "ver":
                return self.jsend({"ver": d.ver})

            if what == "photos":
                ph = d.photos_of(room=q.get("room"), kind=q.get("kind"),
                                 month=q.get("month"),
                                 unassigned=q.get("inbox") == "1")
                return self.jsend([self._pub(m) for m in ph])

            if what == "room":
                r = q.get("room", "")
                if r not in d.rooms():
                    return self.jsend({"error": "ไม่มีห้องนี้"}, 404)
                return self.jsend({"room": r, "readings": d.readings(r),
                                   "photos": [self._pub(m)
                                              for m in d.photos_of(room=r)]})

        if self.robot_claims(path):
            return self.proxy_robot(self.path)
        return self.send(404, "ไม่มีหน้านี้")

    @staticmethod
    def _pub(m, owner=True):
        # ai (สิ่งที่ AI เดา) ให้เจ้าของหอเห็นเท่านั้น ลูกบ้านเห็นแค่ค่าที่ยืนยันแล้ว
        keys = ("name", "ts", "room", "kind", "reading", "note", "size") + (
            ("ai", "rsrc", "ksrc", "preview") if owner else ())
        return {k: m.get(k) for k in keys}

    def do_POST(self):
        path = self.path.partition("?")[0]
        d = self.data

        # ---- หุ่นส่งรูปเข้ามา ----
        if path == "/push":
            # เทียบเป็นไบต์ เพราะหัวข้อความที่มีอักขระนอก ASCII
            # จะทำให้ compare_digest แบบสตริงโยน TypeError แล้วกลายเป็น 500
            got = (self.headers.get("X-Token") or "").encode("utf-8", "replace")
            if not hmac.compare_digest(got, PUSH_TOKEN.encode("utf-8")):
                return self.send(403, "โทเคนไม่ถูก")
            name = d.safe_name(self.headers.get("X-Name"))
            if not name:
                return self.send(400, "ชื่อไฟล์ไม่ถูกต้อง")
            body = self.body_bytes()
            if not body:
                return self.send(400, "ไม่มีข้อมูล")
            if self.headers.get("X-Kind") == "thumb":
                d.put_thumb(name, body)
                return self.jsend({"ok": True, "kind": "thumb"})
            meta = {}
            raw = self.headers.get("X-Meta")
            if raw:
                try:
                    meta = json.loads(base64.b64decode(raw).decode("utf-8"))
                except Exception:
                    meta = {}
            m = d.put_photo(name, body, meta)
            return self.jsend({"ok": True, "room": m["room"],
                               "kind": m["kind"]})

        # ---- หุ่นส่งมาแค่ข้อมูล (รูปเคยส่งแล้ว) ----
        if path == "/push-meta":
            got = (self.headers.get("X-Token") or "").encode("utf-8", "replace")
            if not hmac.compare_digest(got, PUSH_TOKEN.encode("utf-8")):
                return self.send(403, "โทเคนไม่ถูก")
            j = self.body_json()
            name = d.safe_name(j.get("name"))
            inc = j.get("meta")
            if not name or not isinstance(inc, dict):
                return self.send(400, "ข้อมูลไม่ถูกต้อง")
            m = d.update_meta(name, inc)
            if m is None:
                return self.jsend({"error": "ไม่มีรูปนี้"}, 404)
            return self.jsend({"ok": True, "room": m["room"], "kind": m["kind"]})

        # ---- เข้าสู่ระบบ ----
        if path == "/api/login":
            ip = self.client_ip()
            if throttled(ip):
                return self.jsend(
                    {"error": "ลองผิดหลายครั้งเกินไป รอสักครู่แล้วลองใหม่"}, 429)
            j = self.body_json()
            pw = str(j.get("password", ""))
            if j.get("role") == "owner":
                o = d.owner()
                if o and check_pw(pw, o["salt"], o["hash"]):
                    note_ok(ip)
                    return self.jsend({"ok": True, "role": "owner"}, 200,
                                      self.set_session({
                                          "role": "owner",
                                          "exp": time.time() + SESSION_HOURS * 3600}))
            else:
                room = str(j.get("room", "")).strip()
                info = d.rooms().get(room)
                if info and check_pw(pw, info["salt"], info["hash"]):
                    note_ok(ip)
                    return self.jsend({"ok": True, "role": "tenant",
                                       "room": room}, 200,
                                      self.set_session({
                                          "role": "tenant", "room": room,
                                          "exp": time.time() + SESSION_HOURS * 3600}))
            note_fail(ip)
            time.sleep(0.4)        # หน่วงนิดหนึ่ง ให้ยิงรัวไม่คุ้ม
            return self.jsend({"error": "เลขห้องหรือรหัสไม่ถูกต้อง"}, 401)

        if path == "/api/logout":
            return self.jsend({"ok": True}, 200, self.clear_session())

        # ---- คำสั่งฝั่งเจ้าของหอ ----
        if path.startswith("/api/owner/"):
            if not self.need("owner"):
                return
            what = path[len("/api/owner/"):]
            j = self.body_json()

            if what == "add-room":
                room = str(j.get("room", "")).strip()
                if not ROOM_RE.match(room):
                    return self.jsend({"error": "เลขห้องใช้ได้เฉพาะตัวอักษร ตัวเลข - และ /"}, 400)
                if room in d.rooms():
                    return self.jsend({"error": "มีห้องนี้อยู่แล้ว"}, 400)
                pw = d.add_room(room, str(j.get("name", "")).strip())
                return self.jsend({"ok": True, "room": room, "password": pw})

            if what == "reset-pw":
                room = str(j.get("room", ""))
                if room not in d.rooms():
                    return self.jsend({"error": "ไม่มีห้องนี้"}, 404)
                pw = str(j.get("password", "")).strip() or new_pw()
                d.add_room(room, d.rooms()[room].get("name", ""), pw)
                return self.jsend({"ok": True, "room": room, "password": pw})

            if what == "set-room":
                room = str(j.get("room", ""))
                if not d.set_room(room, str(j.get("name", ""))):
                    return self.jsend({"error": "ไม่มีห้องนี้"}, 404)
                return self.jsend({"ok": True})

            if what == "del-room":
                return self.jsend({"ok": d.del_room(str(j.get("room", "")))})

            if what == "set-photo":
                name = d.safe_name(j.get("name"))
                if not name:
                    return self.jsend({"error": "ชื่อไฟล์ไม่ถูกต้อง"}, 400)
                patch = {k: str(j[k]).strip() for k in
                         ("room", "kind", "reading", "note") if k in j}
                m = d.update_photo(name, patch)
                if not m:
                    return self.jsend({"error": "ไม่มีรูปนี้"}, 404)
                return self.jsend(self._pub(m))

            if what == "del-photo":
                name = d.safe_name(j.get("name"))
                return self.jsend({"ok": bool(name) and d.delete_photo(name)})

            if what == "del-photos":
                # ลบหลายใบในคำขอเดียว — ใช้ทั้ง "ลบที่เลือก" และ "ลบทั้งหมด"
                # หน้าเว็บส่งชื่อไฟล์มาเป็นรายการ ฝั่งนี้ไม่มีคำสั่ง "ลบทุกอย่าง"
                # แบบไม่ระบุชื่อ กดพลาดครั้งเดียวจะได้ไม่หายทั้งคลัง
                names = j.get("names")
                if not isinstance(names, list) or len(names) > 2000:
                    return self.jsend({"error": "รายการรูปไม่ถูกต้อง"}, 400)
                n = 0
                for raw in names:
                    name = d.safe_name(raw)
                    if name and d.delete_photo(name):
                        n += 1
                return self.jsend({"ok": True, "deleted": n})

            if what == "set-owner-pw":
                pw = str(j.get("password", ""))
                if len(pw) < 8:
                    return self.jsend({"error": "รหัสต้องยาวอย่างน้อย 8 ตัว"}, 400)
                d.set_owner_pw(pw)
                return self.jsend({"ok": True})

        if self.robot_claims(path):
            return self.proxy_robot(self.path)
        return self.send(404, "ไม่มีหน้านี้")


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(description="ระบบจดมิเตอร์หอพัก")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--dir", default="~/meterhub")
    ap.add_argument("--owner-pw", help="ตั้งรหัสเจ้าของหอใหม่แล้วออก")
    ap.add_argument("--owner-path", default="/owner",
                    help="ทางเข้าเว็บเจ้าของหอ ตั้งให้เดายากก็ได้ เช่น /jod-mitter")
    ap.add_argument("--robot", default="http://raspberrypi.local:9000",
                    help="ที่อยู่หน้าคุมหุ่นบน Pi")
    ap.add_argument("--robot-user", default=os.environ.get("ROBOT_USER",
                                                           "admin"))
    ap.add_argument("--robot-pass", default=os.environ.get("ROBOT_PASS",
                                                           "12345678"))
    ap.add_argument("--ai-auto", type=float, default=None,
                    help="AI มั่นใจเท่านี้ขึ้นไป + ครบ 4 หลัก -> ใส่ค่าให้เลย (ค่าเริ่ม 0.75, 0 = ปิด)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    if a.ai_auto is not None:
        globals()["AI_AUTO"] = a.ai_auto
    d = Data(a.dir)
    if a.owner_pw:
        d.set_owner_pw(a.owner_pw)
        print("ตั้งรหัสเจ้าของหอเรียบร้อย")
        return
    if not d.owner():
        pw = new_pw(10)
        d.set_owner_pw(pw)
        print("=" * 52)
        print(" เปิดครั้งแรก — รหัสเจ้าของหอคือ   %s" % pw)
        print(" จดไว้ก่อน แล้วเข้าไปเปลี่ยนในหน้าตั้งค่า")
        print("=" * 52)

    Handler.data = d
    Handler.verbose = a.verbose
    op = "/" + a.owner_path.strip("/")
    if op in ("/", "/out", "/push", "/healthz") or op.startswith("/api"):
        print("--owner-path ชนกับเส้นทางที่ระบบใช้อยู่ ใช้ /owner แทน")
        op = "/owner"
    Handler.owner_path = op
    Handler.robot_url = a.robot
    Handler.robot_auth = base64.b64encode(
        ("%s:%s" % (a.robot_user, a.robot_pass)).encode()).decode()
    srv = ThreadingHTTPServer(("0.0.0.0", a.port), Handler)
    srv.daemon_threads = True
    print("ข้อมูลอยู่ที่ %s" % d.root)
    print("  ห้องทั้งหมด %d ห้อง  รูป %d ใบ"
          % (len(d.rooms()), len(d.all_meta())))
    print("  เว็บลูกบ้าน   http://%s:%d/" % (lan_ip(), a.port))
    print("  เว็บเจ้าของหอ http://%s:%d%s" % (lan_ip(), a.port, op))
    print("  คุมหุ่น       http://%s:%d%s/robot  (ส่งต่อไป %s)"
          % (lan_ip(), a.port, op, a.robot))
    print("  หุ่นส่งเข้าที่ http://%s:%d/push  (โทเคน %s)"
          % (lan_ip(), a.port, PUSH_TOKEN))
    if Image is None:
        print("  ไม่มี Pillow — ใช้รูปย่อที่หุ่นส่งมา")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nปิดระบบ")


if __name__ == "__main__":
    main()
