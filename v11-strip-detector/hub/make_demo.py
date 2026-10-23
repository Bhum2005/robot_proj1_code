#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""สร้างเว็บเดโมจากหน้าเว็บจริง ไม่ได้เขียนหน้าใหม่

วิธี: เอา HTML ของจริงจาก pages.py มาทั้งดุ้น แล้วแทรกตัวปลอม fetch
ไว้ข้างหน้าสุด ให้ตอบข้อมูลสมมุติแทนการยิงไปเซิร์ฟเวอร์

ทำแบบนี้เพราะถ้าเขียนหน้าเดโมแยก มันจะเพี้ยนจากของจริงทันทีที่แก้โค้ด
แล้วเดโมจะกลายเป็นของหลอกตัวเอง
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pages  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "demo"
now = time.time()


def month(back):
    t = time.localtime(now)
    y, m = t.tm_year, t.tm_mon - back
    while m < 1:
        m += 12
        y -= 1
    return "%04d-%02d" % (y, m)


M0, M1, M2 = month(0), month(1), month(2)
TS0 = int(now - 3600 * 5)
TS1 = int(now - 3600 * 5 - 60)


def ts_in(mk, offset=0):
    return int(time.mktime(time.strptime(mk + "-14 08:00", "%Y-%m-%d %H:%M"))
               ) + offset


# ---------- ข้อมูลสมมุติ ----------
TENANT = {
    "role": "tenant", "room": "101", "name": "พี่หมู",
    "readings": {
        "water": [
            {"month": M2, "value": 98, "used": None, "ts": ts_in(M2),
             "photo": "w2.jpg"},
            {"month": M1, "value": 120, "used": 22, "ts": ts_in(M1),
             "photo": "w1.jpg"},
            {"month": M0, "value": 138.5, "used": 18.5, "ts": TS0,
             "photo": "w0.jpg"}],
        "power": [
            {"month": M2, "value": 1890, "used": None, "ts": ts_in(M2),
             "photo": "p2.jpg"},
            {"month": M1, "value": 1962, "used": 72, "ts": ts_in(M1),
             "photo": "p1.jpg"},
            {"month": M0, "value": 2045, "used": 83, "ts": TS1,
             "photo": "p0.jpg"}]},
    "photos": [
        {"name": "w0.jpg", "ts": TS0, "room": "101", "kind": "water",
         "reading": "138.5", "note": "", "size": 240000},
        {"name": "p0.jpg", "ts": TS1, "room": "101", "kind": "power",
         "reading": "2045", "note": "", "size": 238000}],
}

ROOMS = [
    {"room": "101", "name": "พี่หมู", "w": 138.5, "wu": 18.5,
     "p": 2045, "pu": 83},
    {"room": "102", "name": "น้องแนน", "w": 412, "wu": 9, "p": None,
     "pu": None},
    {"room": "103", "name": "", "w": 77, "wu": 4, "p": 1204, "pu": 61},
    {"room": "201", "name": "ครอบครัวเจริญสุข", "w": None, "wu": None,
     "p": None, "pu": None},
    {"room": "202", "name": "", "w": None, "wu": None, "p": 880, "pu": 35},
]

OWNER_PHOTOS = {
    "101": [{"name": "w0.jpg", "ts": TS0, "room": "101", "kind": "water",
             "reading": "138.5", "note": "", "size": 240000},
            {"name": "p0.jpg", "ts": TS1, "room": "101", "kind": "power",
             "reading": "2045", "note": "", "size": 238000}],
    "102": [{"name": "w1.jpg", "ts": TS0 - 400, "room": "102",
             "kind": "water", "reading": "412", "note": "", "size": 231000}],
    "103": [{"name": "w2.jpg", "ts": TS0 - 900, "room": "103",
             "kind": "water", "reading": "77", "note": "", "size": 229000},
            {"name": "p1.jpg", "ts": TS0 - 940, "room": "103",
             "kind": "power", "reading": "1204", "note": "", "size": 244000}],
    "201": [], "202": [{"name": "p2.jpg", "ts": TS0 - 1500, "room": "202",
                        "kind": "power", "reading": "880", "note": "",
                        "size": 236000}],
}
INBOX = [
    {"name": "x0.jpg", "ts": TS0 - 120, "room": "", "kind": "water",
     "reading": "", "note": "", "size": 233000},
    {"name": "x1.jpg", "ts": TS0 - 150, "room": "", "kind": "other",
     "reading": "", "note": "", "size": 230000},
]

BANNER = """
<div id="demobar" style="position:fixed;left:0;right:0;bottom:0;z-index:99;
  background:#A8560C;color:#fff;font:500 12.5px/1.45 system-ui,sans-serif;
  padding:7px 12px;text-align:center">
  เดโม · ข้อมูลสมมุติทั้งหมด แก้อะไรก็ได้ ไม่กระทบของจริง
  <button onclick="this.parentElement.remove()" style="background:none;
    border:1px solid rgba(255,255,255,.55);color:#fff;border-radius:5px;
    margin-left:8px;padding:1px 7px;cursor:pointer">ซ่อน</button></div>
<style>body{padding-bottom:34px}</style>"""


def mock_js(role, extra=""):
    return """<script>
/* ตัวปลอมของ fetch — ตอบข้อมูลสมมุติแทนการยิงไปเซิร์ฟเวอร์จริง */
(function(){
const S = %s;
const ROLE = '%s';
function J(o){return new Response(JSON.stringify(o),
  {status:200,headers:{'Content-Type':'application/json'}});}
const real = window.fetch;
window.fetch = function(url, opt){
  url = String(url); opt = opt || {};
  const body = opt.body ? JSON.parse(opt.body) : {};
  const q = (k)=>{const m=url.match(new RegExp('[?&]'+k+'=([^&]*)'));
    return m?decodeURIComponent(m[1]):null;};
  return new Promise(res=>setTimeout(()=>res(handle(url,body,q)), 120));
};
function handle(url, body, q){
%s
  return J({});
}
})();
</script>""" % (extra or "{}", role, mock_body(role))


def mock_body(role):
    if role == "tenant":
        return """
  if(url.startsWith('/api/login')) return J({ok:true,role:'tenant',room:'101'});
  if(url.startsWith('/api/me'))    return J(S.me);
"""
    return """
  if(url.startsWith('/api/login'))
    return J(body.password ? {ok:true,role:'owner'}
                           : {error:'ใส่รหัสอะไรก็ได้ นี่คือเดโม'});
  if(url.startsWith('/api/owner/rooms')){
    const m=q('month')||S.month;
    return J({month:m, inbox:S.inbox.length, rooms:S.rooms.map(r=>({
      room:r.room, name:r.name,
      shots:(S.photos[r.room]||[]).length,
      water: r.w==null?null:{month:m,value:r.w,used:r.wu},
      power: r.p==null?null:{month:m,value:r.p,used:r.pu}}))});
  }
  if(url.startsWith('/api/owner/photos')) return J(S.inbox);
  if(url.startsWith('/api/owner/room')){
    const r=q('room'), row=S.rooms.find(x=>x.room===r);
    if(!row) return J({error:'ไม่มีห้องนี้'});
    const mk=(v,u)=>v==null?[]:[{month:S.month,value:v,used:u,ts:0,photo:''}];
    return J({room:r, readings:{water:mk(row.w,row.wu),
      power:mk(row.p,row.pu)}, photos:S.photos[r]||[]});
  }
  if(url.startsWith('/api/owner/set-photo')){
    let p=null;
    for(const k in S.photos){const f=S.photos[k].find(x=>x.name===body.name);
      if(f)p=f;}
    if(!p) p=S.inbox.find(x=>x.name===body.name);
    if(!p) return J({error:'ไม่มีรูปนี้'});
    Object.assign(p, body);
    const row=S.rooms.find(x=>x.room===p.room);
    if(row && body.reading!==undefined && body.reading!==''){
      const v=parseFloat(body.reading);
      if(!isNaN(v)){ if(p.kind==='water'){row.w=v;} if(p.kind==='power'){row.p=v;} }
    }
    if(body.room!==undefined){
      S.inbox = S.inbox.filter(x=>x.name!==p.name);
      if(body.room){ S.photos[body.room]=(S.photos[body.room]||[]);
        if(!S.photos[body.room].includes(p)) S.photos[body.room].push(p);}
    }
    return J(p);
  }
  if(url.startsWith('/api/owner/add-room')){
    if(S.rooms.find(x=>x.room===body.room)) return J({error:'มีห้องนี้อยู่แล้ว'});
    if(!/^[A-Za-z0-9][A-Za-z0-9\\-\\/]{0,15}$/.test(body.room||''))
      return J({error:'เลขห้องใช้ได้เฉพาะตัวอักษร ตัวเลข - และ /'});
    S.rooms.push({room:body.room,name:body.name||'',w:null,wu:null,
      p:null,pu:null});
    S.photos[body.room]=[];
    return J({ok:true,room:body.room,password:'K7PQ2M'});
  }
  if(url.startsWith('/api/owner/reset-pw'))
    return J({ok:true,room:body.room,password:'R4XD9T'});
  if(url.startsWith('/api/owner/del-room')){
    S.rooms=S.rooms.filter(x=>x.room!==body.room); return J({ok:true});
  }
  if(url.startsWith('/api/owner/set-owner-pw'))
    return J(body.password && body.password.length>=8
             ? {ok:true} : {error:'รหัสต้องยาวอย่างน้อย 8 ตัว'});
"""


ROBOT_PAGE = (pages.HEAD % ("เว็บเจ้าของหอ (เดโม)", pages.CSS + """
body{display:grid;place-items:center;min-height:100dvh;padding:22px}
.box{max-width:430px;text-align:center}
h1{font-size:21px;margin:0 0 8px;font-weight:700}
p{color:var(--dim);font-size:14.5px;margin:0 0 16px;line-height:1.6}
img{width:100%;max-width:300px;border-radius:12px;border:1px solid var(--line);
  display:block;margin:0 auto 18px}
""") + """
<div class="box">
  <h1>หน้าคุมหุ่น</h1>
  <p>ปุ่มนี้ในของจริงจะเปิดหน้าคุมหุ่นขึ้นมาอีกแท็บ ส่งต่อผ่านเซิร์ฟเวอร์เดียวกัน
     จึงเปิดได้จากนอกบ้านด้วย และต้องล็อกอินเป็นเจ้าของหอก่อนเสมอ<br><br>
     ในเดโมเปิดของจริงไม่ได้เพราะต้องมีหุ่นเปิดอยู่ ภาพข้างล่างคือหน้าจริง</p>
  <img src="robot-shot.jpg" alt="หน้าคุมหุ่นบนมือถือ">
  <p>ช่องเลขห้องกับปุ่มน้ำ/ไฟ อยู่ติดปุ่มชัตเตอร์
     ตั้งครั้งเดียวแล้วถ่ายได้หลายรูปติดกัน</p>
  <a class="btn" href="portal.html">กลับหน้าเจ้าของหอ</a>
</div>""" + pages.FOOT)


def build(html, role, state, home, back):
    """แทรกตัวปลอมและแก้เส้นทางให้เปิดได้โดยไม่มีเซิร์ฟเวอร์"""
    html = html.replace("<body>", "<body>" + mock_js(role, state), 1)
    html = html.replace("'/t/'", "'t/'").replace("'/p/'", "'p/'")
    html = html.replace('href="/owner/robot"', 'href="robot.html"')
    html = html.replace("location.href='%s'" % home, "location.href='%s'"
                        % "portal.html")
    html = html.replace('href="/out?to=%s"' % back, 'href="index.html"')
    html = html.replace("</body>", BANNER + "</body>", 1)
    # ตั้งชื่อหน้าให้แยกกันชัด ๆ เวลาเปิดสองเดโมพร้อมกันจะได้ไม่งง
    label = "เว็บลูกบ้าน (เดโม)" if role == "tenant" else "เว็บเจ้าของหอ (เดโม)"
    import re as _re
    html = _re.sub(r"<title>[^<]*</title>", "<title>%s</title>" % label,
                   html, count=1)
    return html


def main():
    os.makedirs(OUT, exist_ok=True)
    import json

    tstate = json.dumps({"me": TENANT}, ensure_ascii=False)
    ostate = json.dumps({"month": M0, "rooms": ROOMS, "photos": OWNER_PHOTOS,
                         "inbox": INBOX}, ensure_ascii=False)

    jobs = [
        ("tenant", "index.html", pages.login_page("tenant"), tstate, "/", "/"),
        ("tenant", "portal.html", pages.TENANT, tstate, "/", "/"),
        ("owner", "index.html", pages.login_page("owner", "/owner"), ostate,
         "/owner", "__OWNER_PATH__"),
        ("owner", "portal.html",
         pages.OWNER.replace("__OWNER_PATH__", "/owner"), ostate, "/owner",
         "/owner"),
    ]
    for role, fn, html, state, home, back in jobs:
        d = os.path.join(OUT, role)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, fn), "w", encoding="utf-8") as f:
            f.write(build(html, role, state, home, back))
        print("%s/%s" % (role, fn))

    with open(os.path.join(OUT, "owner", "robot.html"), "w",
              encoding="utf-8") as f:
        f.write(ROBOT_PAGE)
    print("owner/robot.html")


if __name__ == "__main__":
    main()
