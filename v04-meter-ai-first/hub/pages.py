# -*- coding: utf-8 -*-
"""หน้าเว็บทั้งสามของระบบจดมิเตอร์

แยกไฟล์ออกมาจาก hub.py เพราะเป็นคนละเรื่องกัน แก้หน้าตาไม่ต้องแตะตรรกะ

แนวคิดการออกแบบ (ปรับใหม่ 15 ต.ค. 2569)
  ตัวเอก: "ล้อตัวเลขมิเตอร์" — ช่องตัวเลขสีเข้มแบบหน้าปัดมิเตอร์จริง
  ทศนิยมเป็นล้อสีแดงเหมือนมิเตอร์น้ำ ตอนตัวเลขขึ้นจอ ล้อจะหมุนมาหยุดที่ค่า
  นั่นคือการเคลื่อนไหวเดียวที่เกิดเอง ที่เหลือขยับเฉพาะตอนผู้ใช้กดอะไร
  (เปิดกล่อง ลบรูป บันทึกเลข) เพื่อบอกว่าเกิดอะไรขึ้น

  สี: ผนังปูนเย็น ๆ ของทางเดินหอ + ล้อตัวเลขสีกรมเข้ม
      น้ำ = เขียวน้ำทะเลเข้ม  ไฟ = เหลืองอำพัน  แยกด้วยสีตลอดทุกหน้า
  ตัวอักษร: Chakra Petch (เหลี่ยมแบบหน้าปัดเครื่องวัด) ใช้กับเลขห้องและตัวเลข
            Anuphan ใช้กับข้อความทั่วไป
"""

HEAD = """<!DOCTYPE html>
<html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>%s</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anuphan:wght@400;500;600&family=Chakra+Petch:wght@500;600;700&display=swap" rel="stylesheet">
<style>%s</style></head><body>"""

CSS = """
:root{
  --wall:#E3E8EB; --card:#FBFCFC; --ink:#17222A; --dim:#5B6870;
  --line:#C9D1D6; --soft:#EEF2F4;
  --drum:#1C2830; --drum-ink:#F1F4F5; --dec:#D3263B;
  --water:#0B6E87; --power:#B26A00; --warn:#B3261E; --ok:#1F7A4A;
  --f:"Anuphan","Noto Sans Thai",system-ui,sans-serif;
  --fd:"Chakra Petch","Anuphan",system-ui,sans-serif;
  --ease:cubic-bezier(.2,.8,.2,1);
}
@media (prefers-color-scheme:dark){:root{
  --wall:#0F161B; --card:#162027; --ink:#E2E9ED; --dim:#8B9AA4;
  --line:#26343D; --soft:#1C2830;
  --drum:#070C10; --drum-ink:#EAF0F2; --dec:#FF5468;
  --water:#4BB6D2; --power:#F0A63A; --warn:#FF8A80; --ok:#6CD39A;}}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{background:var(--wall);color:var(--ink);font-family:var(--f);
  line-height:1.55;-webkit-text-size-adjust:100%;font-size:15px}
a{color:inherit}
button,input,select{font-family:inherit;font-size:inherit;color:inherit}
button{cursor:pointer}
.wrap{max-width:1080px;margin:0 auto;padding:0 16px}
h1,h2,h3{font-weight:600;line-height:1.25}

/* ---- ล้อตัวเลขมิเตอร์ — ตัวเอกของทุกหน้า ---- */
.meter{display:inline-flex;gap:2px;padding:4px;background:var(--drum);
  border-radius:6px;box-shadow:inset 0 0 0 1px rgba(255,255,255,.06);
  border-bottom:3px solid currentColor}
.meter b{position:relative;display:block;width:.78em;height:1.2em;
  overflow:hidden;font:700 30px/1.2 var(--fd);color:var(--drum-ink);
  text-align:center;border-radius:2px;
  background:linear-gradient(#0000 0 46%,rgba(255,255,255,.07) 50%,#0000 54%),
             linear-gradient(rgba(0,0,0,.45),#0000 30% 70%,rgba(0,0,0,.45))}
.meter b.dec{color:#fff;background-color:var(--dec)}
.meter .reel{display:flex;flex-direction:column;
  transform:translateY(calc(var(--d) * -10%));
  animation:roll 1.1s var(--ease) both;animation-delay:calc(var(--i) * 70ms)}
.meter .reel span{height:1.2em}
@keyframes roll{from{transform:translateY(0)}}
.meter.sm{padding:2px;border-bottom-width:2px;border-radius:4px}
.meter.sm b{font-size:17px}
.meter.sm .reel{animation:none}
.meter.empty b{color:var(--drum-ink);opacity:.35;font-weight:500}
.water{color:var(--water)}
.power{color:var(--power)}

/* ---- ส่วนประกอบทั่วไป ---- */
.card{background:var(--card);border:1px solid var(--line);border-radius:12px}
.btn{display:inline-flex;align-items:center;gap:6px;justify-content:center;
  background:var(--ink);color:var(--card);border:1px solid var(--ink);
  border-radius:9px;padding:10px 16px;font-weight:600;text-decoration:none;
  transition:transform .12s var(--ease),background .15s,opacity .15s}
.btn:active{transform:scale(.97)}
.btn.ghost{background:transparent;color:var(--ink);border-color:var(--line);
  font-weight:500}
.btn.ghost:hover{background:var(--soft)}
.btn.danger{background:var(--warn);border-color:var(--warn);color:var(--card)}
.btn.ghost.danger{background:transparent;color:var(--warn);
  border-color:color-mix(in srgb,var(--warn) 45%,var(--line))}
.btn.ghost.danger:hover{background:color-mix(in srgb,var(--warn) 10%,transparent)}
.btn.sm{padding:6px 11px;font-size:13.5px;border-radius:8px}
.btn:disabled{opacity:.4;cursor:not-allowed}
.btn svg{width:16px;height:16px;flex:0 0 auto}
input,select{background:var(--card);border:1px solid var(--line);
  border-radius:9px;padding:9px 11px;width:100%;
  transition:border-color .15s,box-shadow .15s}
input:focus,select:focus{outline:none;border-color:var(--water);
  box-shadow:0 0 0 3px color-mix(in srgb,var(--water) 22%,transparent)}
button:focus-visible,a:focus-visible{outline:2px solid var(--water);
  outline-offset:2px}
label{display:block;font-size:13px;color:var(--dim);margin:0 0 5px}
.muted{color:var(--dim)}
.err{color:var(--warn);font-size:14px;min-height:20px;margin:6px 0}
dialog{border:1px solid var(--line);border-radius:14px;padding:20px;
  background:var(--card);color:var(--ink);max-width:360px;width:92%}
dialog[open]{animation:pop .22s var(--ease)}
dialog::backdrop{background:rgba(10,16,20,.55);backdrop-filter:blur(2px)}
@keyframes pop{from{opacity:0;transform:translateY(8px) scale(.97)}}
@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation:none!important;transition:none!important}}
"""

FOOT = "</body></html>"

# ไอคอนเส้นเล็ก ๆ ใช้ซ้ำหลายที่ (ไม่โหลดไลบรารีเพิ่ม)
ICON_TRASH = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="2" stroke-linecap="round" aria-hidden="true">'
              '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>'
              '</svg>')


# =====================================================================
# หน้าเข้าสู่ระบบ — แยกคนละหน้าระหว่างลูกบ้านกับเจ้าของหอ
# ---------------------------------------------------------------------
# แยกเพราะเป็นคนละงานกันจริง ๆ ลูกบ้านเข้าจากลิงก์ที่ติดหน้าห้อง
# เจ้าของหอเข้าจากทางที่ไม่ประกาศให้ใครรู้ ตั้งชื่อทางเองได้ด้วย --owner-path
# ผลพลอยได้ที่สำคัญ: หน้าลูกบ้านไม่มีอะไรบอกใบ้เลยว่าทางเข้าของเจ้าของหออยู่ไหน
LOGIN_BASE = (HEAD % ("เข้าสู่ระบบ · มิเตอร์หอพัก", CSS + """
body{display:grid;place-items:center;min-height:100dvh;padding:20px}
.box{width:100%;max-width:380px}
.mark{display:flex;justify-content:center;margin:0 0 22px}
.mark .meter b{font-size:40px}
.plate{padding:24px}
h1{font:600 24px/1.2 var(--fd);margin:0 0 4px;letter-spacing:-.01em}
.sub{color:var(--dim);font-size:14.5px;margin:0 0 20px}
.f{margin:0 0 14px}
.hint{font-size:13px;color:var(--dim);margin:16px 0 0}
#btnLogin{width:100%;padding:12px}
""") + """
<div class="box">
  <div class="mark">__MARK__</div>
  <div class="card plate">
    <h1>__TITLE__</h1>
    <p class="sub">__SUB__</p>
    <form onsubmit="go(event)">
      <div class="f" id="roomf">
        <label for="room">เลขห้อง</label>
        <input id="room" autocomplete="username" inputmode="text"
          placeholder="เช่น 101">
      </div>
      <div class="f">
        <label for="pw">รหัสผ่าน</label>
        <input id="pw" type="password" autocomplete="current-password">
      </div>
      <p class="err" id="err" role="alert"></p>
      <button class="btn" id="btnLogin">เข้าสู่ระบบ</button>
    </form>
    <p class="hint">__HINT__</p>
  </div>
</div>
<script>
const role='__ROLE__';
if(role==='owner') document.getElementById('roomf').remove();
async function go(e){
  e.preventDefault();
  const b=document.getElementById('btnLogin'); b.disabled=true;
  const err=document.getElementById('err'); err.textContent='';
  try{
    const r=await fetch('/api/login',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({role:role,
        room:(document.getElementById('room')||{value:''}).value.trim(),
        password:document.getElementById('pw').value})});
    const j=await r.json();
    if(j.ok){location.href='__HOME__';return;}
    err.textContent=j.error||'เข้าสู่ระบบไม่สำเร็จ';
  }catch(ex){ err.textContent='ต่อเซิร์ฟเวอร์ไม่ได้ ลองใหม่อีกครั้ง'; }
  b.disabled=false;
}
(document.getElementById('room')||document.getElementById('pw')).focus();
</script>""" + FOOT)


def _mark(text, cls):
    """ล้อตัวเลขสำหรับโลโก้หน้าล็อกอิน (หมุนมาหยุดที่ตัวอักษรนั้น)"""
    out = '<div class="meter %s">' % cls
    for i, c in enumerate(text):
        if c.isdigit():
            reel = "".join("<span>%d</span>" % k for k in range(10))
            out += ('<b><span class="reel" style="--d:%s;--i:%d">%s</span></b>'
                    % (c, i, reel))
        else:
            out += "<b>%s</b>" % c
    return out + "</div>"


def login_page(role, owner_path="/owner"):
    """สร้างหน้าล็อกอินของแต่ละฝั่งจากแม่แบบเดียวกัน"""
    if role == "tenant":
        sub = {"__ROLE__": "tenant", "__HOME__": "/",
               "__TITLE__": "มิเตอร์หอพัก",
               "__SUB__": "ดูเลขน้ำเลขไฟของห้องคุณ",
               "__HINT__": "รหัสของห้องขอได้ที่เจ้าของหอ",
               "__MARK__": _mark("0427", "water")}
    else:
        sub = {"__ROLE__": "owner", "__HOME__": owner_path,
               "__TITLE__": "สำหรับเจ้าของหอ",
               "__SUB__": "จัดการห้อง จดมิเตอร์ และคุมหุ่น",
               "__HINT__": "รหัสแรกเข้าอยู่ในหน้าจอตอนเปิดระบบครั้งแรก",
               "__MARK__": _mark("3398", "power")}
    out = LOGIN_BASE.replace(
        "<title>เข้าสู่ระบบ · มิเตอร์หอพัก</title>",
        "<title>%s</title>" % ("เข้าสู่ระบบ · มิเตอร์หอพัก" if role == "tenant"
                               else "เจ้าของหอ · มิเตอร์หอพัก"))
    for k, v in sub.items():
        out = out.replace(k, v)
    return out


# ฟังก์ชัน JS ที่ใช้ร่วมกันทั้งหน้าลูกบ้านและหน้าเจ้าของหอ
# ★ อยู่ในสตริง Python ธรรมดา: ถ้าจะใส่ \ ใน JS ต้องเขียน \\ (เคยพังมาแล้ว)
JS_COMMON = """
const TH={water:'น้ำ',power:'ไฟ',other:'อื่น ๆ'};
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function reel(c,i){
  if(!/[0-9]/.test(c)) return '<b>'+esc(c)+'</b>';
  let s=''; for(let k=0;k<10;k++) s+='<span>'+k+'</span>';
  return '<span class="reel" style="--d:'+c+';--i:'+i+'">'+s+'</span>';
}
function digits(v,cls,sm){
  // ล้อตัวเลขทีละหลักเหมือนหน้าปัดมิเตอร์จริง ทศนิยมเป็นล้อสีแดง
  const k='meter '+cls+(sm?' sm':'');
  if(v===null||v===undefined||v===''){
    return '<div class="'+k+' empty"><b>–</b><b>–</b><b>–</b><b>–</b></div>';}
  const s=String(v).replace(/[.]0+$/,'');
  const [ip,dp]=s.split('.');
  let h='<div class="'+k+'" role="img" aria-label="'+esc(s)+'">', n=0;
  String(ip).padStart(4,'0').split('').forEach(c=>{
    const r=reel(c,n++); h+=r.startsWith('<b>')?r:'<b>'+r+'</b>';});
  if(dp) dp.split('').forEach(c=>{
    const r=reel(c,n++); h+=r.startsWith('<b>')?r.replace('<b>','<b class="dec">')
      :'<b class="dec">'+r+'</b>';});
  return h+'</div>';
}
function monthTH(m,short){
  if(!m) return '';
  const [y,mm]=m.split('-');
  const n=['ม.ค.','ก.พ.','มี.ค.','เม.ย.','พ.ค.','มิ.ย.',
           'ก.ค.','ส.ค.','ก.ย.','ต.ค.','พ.ย.','ธ.ค.'];
  const by=parseInt(y,10)+543;
  return n[parseInt(mm,10)-1]+' '+(short?String(by).slice(2):by);
}
function zoom(n){document.getElementById('lbimg').src='/p/'+encodeURIComponent(n);
  document.getElementById('lb').classList.add('on');}
"""

LIGHTBOX_CSS = """
#lb{position:fixed;inset:0;background:rgba(5,9,12,.94);display:none;z-index:9}
#lb.on{display:grid;grid-template-rows:1fr auto;animation:fade .2s}
#lb img{width:100%;height:100%;object-fit:contain;min-height:0;
  animation:pop .25s var(--ease)}
#lb div{padding:12px;text-align:center;color:#9AA7AF;font-size:14px}
@keyframes fade{from{opacity:0}}
"""

# =====================================================================
# หน้าลูกบ้าน
# ---------------------------------------------------------------------
# เปิดมาต้องเห็นคำตอบทันทีว่าเดือนนี้ใช้ไปเท่าไหร่ ไม่ต้องกดอะไรก่อน
# รูปมิเตอร์วางไว้ให้กดดูได้ เพราะเป็นหลักฐานว่าเลขที่คีย์มาจากไหน
TENANT = (HEAD % ("ห้องของฉัน · มิเตอร์หอพัก", CSS + LIGHTBOX_CSS + """
header{background:var(--drum);color:var(--drum-ink)}
.hrow{display:flex;align-items:center;gap:12px;padding-block:16px}
.room{font:700 28px/1.1 var(--fd);letter-spacing:.01em}
.room small{display:block;font:400 13px/1.4 var(--f);opacity:.7;margin-top:3px}
header .btn.ghost{color:var(--drum-ink);border-color:rgba(255,255,255,.22)}
header .btn.ghost:hover{background:rgba(255,255,255,.08)}
main.wrap{padding-top:22px;padding-bottom:56px}
.two{display:grid;gap:14px;grid-template-columns:1fr 1fr}
@media(max-width:700px){.two{grid-template-columns:1fr}}
.util{padding:18px;border-top:4px solid currentColor}
.util>*{color:var(--ink)}
.util .meter{color:inherit}
.uhead{display:flex;align-items:baseline;gap:9px;margin:0 0 14px}
.uhead h2{font:600 18px/1 var(--fd);margin:0}
.uhead span{font-size:13px;color:var(--dim)}
.used{margin:14px 0 0;font-size:14px;color:var(--dim)}
.used b{font:700 30px/1 var(--fd);margin:0 3px}
.proof{margin:14px 0 0}
.proof img{width:100%;max-height:220px;object-fit:cover;border-radius:9px;
  display:block;cursor:zoom-in;border:1px solid var(--line)}
h3{font:600 16px/1.3 var(--fd);margin:28px 0 10px}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px;min-width:440px}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line)}
tr:last-child td{border-bottom:0}
th{font-size:12.5px;color:var(--dim);font-weight:500}
td.n{text-align:right;font:600 15px var(--fd)}
.none{padding:30px 16px;text-align:center;color:var(--dim);font-size:14px}
""") + """
<header><div class="wrap hrow">
  <div class="room" id="room">—<small id="rname">ห้องของฉัน</small></div>
  <span style="flex:1"></span>
  <a class="btn ghost sm" href="/out?to=/">ออกจากระบบ</a>
</div></header>
<main class="wrap">
  <div class="two">
    <section class="card util water" id="u-water"></section>
    <section class="card util power" id="u-power"></section>
  </div>
  <h3>ย้อนหลัง</h3>
  <div class="card scroll" id="hist"></div>
</main>
<div id="lb" onclick="this.classList.remove('on')">
  <img id="lbimg" alt=""><div>แตะเพื่อปิด</div></div>
<script>""" + JS_COMMON + """
function card(kind,series,photos){
  const last=series.length?series[series.length-1]:null;
  let h='<div class="uhead"><h2>'+TH[kind]+'</h2>'+
    '<span>'+(last?monthTH(last.month):'ยังไม่มีข้อมูล')+'</span></div>';
  h+=digits(last?last.value:null,kind);
  if(last&&last.used!==null&&last.used!==undefined){
    h+='<p class="used">ใช้ไป<b class="'+kind+'">'+last.used+'</b>หน่วย</p>';
  }else if(last){
    h+='<p class="used">เดือนแรกที่จด ยังเทียบกับเดือนก่อนไม่ได้</p>';
  }else{
    h+='<p class="used">ยังไม่มีการจดมิเตอร์</p>';
  }
  const p=photos.find(x=>x.kind===kind);
  if(p) h+='<div class="proof"><img loading="lazy" src="/t/'+
    encodeURIComponent(p.name)+'" alt="รูปมิเตอร์'+TH[kind]+
    '" data-zoom="'+esc(p.name)+'"></div>';
  return h;
}
document.addEventListener('click',e=>{
  const z=e.target.closest('[data-zoom]'); if(z) zoom(z.dataset.zoom);});

(async function(){
  const d=await (await fetch('/api/me')).json();
  if(d.role!=='tenant'){location.href='/';return;}
  document.getElementById('room').firstChild.textContent='ห้อง '+d.room;
  document.getElementById('rname').textContent=d.name||'ห้องของฉัน';
  document.title='ห้อง '+d.room+' · มิเตอร์หอพัก';
  for(const k of ['water','power'])
    document.getElementById('u-'+k).innerHTML=card(k,d.readings[k],d.photos);

  const months={};
  for(const k of ['water','power'])
    d.readings[k].forEach(r=>{months[r.month]=months[r.month]||{};
      months[r.month][k]=r;});
  const keys=Object.keys(months).sort().reverse();
  const hist=document.getElementById('hist');
  if(!keys.length){hist.innerHTML='<p class="none">ยังไม่มีประวัติ '+
    'เมื่อเจ้าของหอจดมิเตอร์แล้วจะขึ้นที่นี่</p>';return;}
  let h='<table><tr><th>เดือน</th><th>น้ำ</th><th class="n">ใช้ไป</th>'+
    '<th>ไฟ</th><th class="n">ใช้ไป</th></tr>';
  keys.forEach(m=>{const w=months[m].water,p=months[m].power;
    h+='<tr><td>'+monthTH(m,1)+'</td>'+
      '<td>'+digits(w?w.value:null,'water',1)+'</td>'+
      '<td class="n water">'+(w&&w.used!=null?w.used:'–')+'</td>'+
      '<td>'+digits(p?p.value:null,'power',1)+'</td>'+
      '<td class="n power">'+(p&&p.used!=null?p.used:'–')+'</td></tr>';});
  hist.innerHTML=h+'</table>';
})();
</script>""" + FOOT)


# =====================================================================
# หน้าเจ้าของหอ
# ---------------------------------------------------------------------
# งานจริงของหน้านี้คือ "คีย์เลขให้ครบทุกห้องภายในวันเดียว"
# ทุกอย่างจึงจัดให้เห็นว่าห้องไหนยังขาด แล้วคีย์ต่อกันรวดเดียวได้
# รูปที่หุ่นถ่ายมาแต่ยังไม่รู้ว่าห้องไหน จะถูกดันขึ้นมาไว้บนสุด
#
# ลบรูป: ทีละใบ (ปุ่มถังขยะบนรูป) / เลือกหลายใบ / ลบทั้งหมดที่แสดงอยู่
#   ★ "ลบทั้งหมด" หมายถึงรูปที่แสดงอยู่ตรงหน้า (ห้องนี้ เดือนนี้ หรือรูปค้าง)
#     ไม่ใช่ทั้งคลัง และทุกแบบต้องยืนยันในกล่องที่บอกจำนวนรูปก่อนเสมอ
OWNER = (HEAD % ("เจ้าของหอ · มิเตอร์หอพัก", CSS + LIGHTBOX_CSS + """
header{background:var(--drum);color:var(--drum-ink);position:sticky;top:0;
  z-index:4}
.hrow{display:flex;align-items:center;gap:10px;padding-block:11px;flex-wrap:wrap}
.hrow h1{font:700 19px/1 var(--fd);margin:0 6px 0 0;letter-spacing:.01em}
header select{width:auto;background:rgba(255,255,255,.08);color:var(--drum-ink);
  border-color:rgba(255,255,255,.2);padding:6px 10px}
header select option{color:#17222A}
header .btn.ghost{color:var(--drum-ink);border-color:rgba(255,255,255,.22)}
header .btn.ghost:hover{background:rgba(255,255,255,.08)}
header .btn.go{background:var(--power);border-color:var(--power);color:#1A1200}
main.wrap{padding-top:18px;padding-bottom:70px}
.cols{display:grid;gap:16px;grid-template-columns:290px 1fr;align-items:start}
@media(max-width:820px){.cols{grid-template-columns:1fr}}
.panel{padding:16px}
.panel h2{font:600 16px/1.3 var(--fd);margin:0}
.ph{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:0 0 13px}
.ph .grow{flex:1}
.count{font-size:13px;color:var(--dim)}
.rooms{display:flex;flex-direction:column;gap:2px}
.rm{display:flex;align-items:center;gap:9px;padding:9px 10px;background:none;
  border:0;border-radius:9px;width:100%;text-align:left;
  transition:background .15s}
.rm:hover{background:var(--soft)}
.rm[aria-current=true]{background:var(--drum);color:var(--drum-ink)}
.rm .no{font:600 17px/1 var(--fd);min-width:50px}
.rm .nm{font-size:13px;color:var(--dim);flex:1;overflow:hidden;
  text-overflow:ellipsis;white-space:nowrap}
.rm[aria-current=true] .nm{color:inherit;opacity:.65}
.pip{width:10px;height:10px;border-radius:50%;border:2px solid currentColor;
  flex:0 0 auto}
.pip.on{background:currentColor}
.legend{display:flex;gap:12px;font-size:12.5px;color:var(--dim);margin:0 0 10px}
.legend span{display:flex;gap:5px;align-items:center}
.inbox{display:flex;gap:12px;align-items:center;flex-wrap:wrap;
  padding:12px 14px;margin:0 0 16px;border-left:4px solid var(--power)}
.inbox b{font:700 20px/1 var(--fd);color:var(--power)}
.sum{display:flex;gap:30px;flex-wrap:wrap;align-items:flex-start;padding:18px;
  margin:0 0 14px}
.sum .blk h3{margin:0 0 9px;font-size:13.5px;font-weight:500;color:var(--dim)}
.sum .use{margin:10px 0 0;font-size:13.5px;color:var(--dim)}
.sum .use b{font:700 20px var(--fd);margin:0 3px}
.sum .acts{display:flex;gap:7px;padding-top:24px;flex-wrap:wrap}

/* ---- แถบเลือก/ลบรูป ---- */
.selbar{display:none;align-items:center;gap:8px;flex-wrap:wrap;
  padding:9px 10px;margin:0 0 12px;border-radius:10px;background:var(--soft)}
.selmode .selbar{display:flex;animation:pop .2s var(--ease)}
.selbar .n{font-weight:600;margin-right:auto}
.shots{display:grid;gap:12px;
  grid-template-columns:repeat(auto-fill,minmax(232px,1fr))}
.shot{position:relative;border:1px solid var(--line);border-radius:11px;
  overflow:hidden;background:var(--card);
  transition:border-color .15s,box-shadow .15s,opacity .25s,transform .25s}
.shot .pic{position:relative}
.shot img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;
  background:var(--soft);cursor:zoom-in}
.shot .del{position:absolute;top:8px;right:8px;width:34px;height:34px;
  display:grid;place-items:center;border-radius:9px;border:0;
  background:rgba(12,18,22,.62);color:#fff;backdrop-filter:blur(3px);
  transition:background .15s,transform .12s}
.shot .del:hover{background:var(--warn)}
.shot .del:active{transform:scale(.92)}
.shot .del svg{width:17px;height:17px}
.shot .pick{position:absolute;top:8px;left:8px;width:26px;height:26px;
  display:none;place-items:center;border-radius:7px;
  border:2px solid #fff;background:rgba(12,18,22,.45)}
.selmode .shot .pick{display:grid}
.selmode .shot .del{display:none}
.selmode .shot img{cursor:pointer}
.shot.sel{border-color:var(--warn);
  box-shadow:0 0 0 2px color-mix(in srgb,var(--warn) 55%,transparent)}
.shot.sel .pick{background:var(--warn);border-color:var(--warn)}
.shot.sel .pick::after{content:"";width:6px;height:11px;border:solid #fff;
  border-width:0 2.5px 2.5px 0;transform:translateY(-1px) rotate(45deg)}
.shot.gone{opacity:0;transform:scale(.94)}
.shot.flash{border-color:var(--ok);
  box-shadow:0 0 0 2px color-mix(in srgb,var(--ok) 45%,transparent)}
.shot .f{padding:10px;display:flex;flex-direction:column;gap:7px}
.shot .when{font-size:12.5px;color:var(--dim)}
.rowf{display:flex;gap:6px}
.rowf input,.rowf select{padding:7px 9px;border-radius:8px;font-size:14px}
.rowf [data-save]{flex:0 0 auto}
.saved{color:var(--ok);font-size:12.5px;min-height:17px}
.none{padding:32px 14px;text-align:center;color:var(--dim);font-size:14px}
.pw{font:700 30px/1 var(--fd);letter-spacing:.12em;text-align:center;
  padding:16px;border:1.5px dashed var(--line);border-radius:10px;margin:14px 0}
.dlgh{margin:0 0 12px;font:600 18px/1.3 var(--fd)}
.dlgacts{display:flex;gap:8px;justify-content:flex-end;margin-top:6px}
#toast{position:fixed;left:50%;bottom:22px;transform:translate(-50%,140%);
  background:var(--drum);color:var(--drum-ink);padding:10px 16px;
  border-radius:10px;font-size:14px;z-index:7;opacity:0;visibility:hidden;
  transition:transform .3s var(--ease),opacity .3s,visibility .3s;
  box-shadow:0 8px 24px rgba(0,0,0,.25)}
#toast.on{transform:translate(-50%,0);opacity:1;visibility:visible}
#robotView{position:fixed;inset:0;z-index:8;background:#000;display:none}
#robotView.on{display:block;animation:rise .3s var(--ease)}
#robotView iframe{width:100%;height:100%;border:0;display:block}
@keyframes rise{from{transform:translateY(24px);opacity:0}}
""") + """
<header><div class="wrap hrow">
  <h1>มิเตอร์หอพัก</h1>
  <select id="month" aria-label="เดือน" onchange="loadRooms()"></select>
  <span style="flex:1"></span>
  <button class="btn sm go" id="robotLink" onclick="openRobot()">คุมหุ่น</button>
  <button class="btn ghost sm" onclick="dlgAdd.showModal()">เพิ่มห้อง</button>
  <button class="btn ghost sm" onclick="dlgPw.showModal()">รหัสของฉัน</button>
  <a class="btn ghost sm" href="/out?to=__OWNER_PATH__">ออก</a>
</div></header>
<main class="wrap">
  <div id="inbox"></div>
  <div class="cols">
    <section class="card panel">
      <div class="ph"><h2>ห้องทั้งหมด</h2></div>
      <div class="legend">
        <span><i class="pip water on"></i>จดน้ำแล้ว</span>
        <span><i class="pip power on"></i>จดไฟแล้ว</span>
      </div>
      <div class="rooms" id="rooms"></div>
    </section>
    <section id="detail"></section>
  </div>
</main>

<dialog id="dlgAdd"><form method="dialog" onsubmit="addRoom(event)">
  <h2 class="dlgh">เพิ่มห้อง</h2>
  <div style="margin:0 0 12px"><label for="nroom">เลขห้อง</label>
    <input id="nroom" placeholder="101"></div>
  <div style="margin:0 0 12px"><label for="nname">ชื่อผู้เช่า (ไม่ใส่ก็ได้)</label>
    <input id="nname"></div>
  <p class="err" id="adderr"></p>
  <div class="dlgacts">
    <button class="btn ghost" type="button" onclick="dlgAdd.close()">ยกเลิก</button>
    <button class="btn">เพิ่มห้อง</button></div>
</form></dialog>

<dialog id="dlgShow"><div>
  <h2 class="dlgh" id="showTitle"></h2>
  <p class="muted" style="font-size:13.5px;margin:0">
    รหัสนี้แสดงครั้งเดียว จดใส่กระดาษให้ลูกบ้านก่อนปิด</p>
  <div class="pw" id="showPw"></div>
  <div class="dlgacts">
    <button class="btn" onclick="dlgShow.close()">จดแล้ว</button></div>
</div></dialog>

<dialog id="dlgPw"><form method="dialog" onsubmit="setOwnerPw(event)">
  <h2 class="dlgh">เปลี่ยนรหัสเจ้าของหอ</h2>
  <div style="margin:0 0 12px"><label for="opw">รหัสใหม่ อย่างน้อย 8 ตัว</label>
    <input id="opw" type="password" autocomplete="new-password"></div>
  <p class="err" id="pwerr"></p>
  <div class="dlgacts">
    <button class="btn ghost" type="button" onclick="dlgPw.close()">ยกเลิก</button>
    <button class="btn">เปลี่ยนรหัส</button></div>
</form></dialog>

<!-- กล่องยืนยันกลาง ใช้กับการลบทุกแบบ (แทน confirm() ของเบราว์เซอร์) -->
<dialog id="dlgAsk"><div>
  <h2 class="dlgh" id="askTitle"></h2>
  <p class="muted" style="font-size:14px;margin:0 0 14px" id="askBody"></p>
  <div class="dlgacts">
    <button class="btn ghost" type="button" onclick="askDone(false)">ยกเลิก</button>
    <button class="btn danger" type="button" id="askOk"
      onclick="askDone(true)"></button></div>
</div></dialog>

<div id="toast" role="status" aria-live="polite"></div>

<!-- หน้าคุมหุ่นเปิดซ้อนอยู่ในหน้านี้ ลิงก์บนแถบที่อยู่ไม่เปลี่ยน -->
<div id="robotView"><iframe id="robotFrame" title="คุมหุ่น"
  allow="fullscreen; gamepad; screen-wake-lock"></iframe></div>

<div id="lb" onclick="this.classList.remove('on')">
  <img id="lbimg" alt=""><div>แตะเพื่อปิด</div></div>

<script>""" + JS_COMMON + """
const TRASH='""" + ICON_TRASH + """';
let month='', rooms=[], cur=null, shown=[];

function when(ts){return new Date(ts*1000).toLocaleString('th-TH',
  {day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});}
function post(url,body){return fetch(url,{method:'POST',
  headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});}
let toastT=0;
function toast(msg){const t=document.getElementById('toast');
  t.textContent=msg; t.classList.add('on'); clearTimeout(toastT);
  toastT=setTimeout(()=>t.classList.remove('on'),2400);}

/* กล่องยืนยัน — คืน Promise<true/false> */
let askRes=null;
function ask(title,body,okText){
  document.getElementById('askTitle').textContent=title;
  document.getElementById('askBody').textContent=body;
  document.getElementById('askOk').textContent=okText;
  dlgAsk.showModal();
  return new Promise(r=>askRes=r);
}
function askDone(v){dlgAsk.close(); if(askRes){askRes(v); askRes=null;}}
dlgAsk.addEventListener('cancel',()=>{if(askRes){askRes(false);askRes=null;}});

function fillMonths(){
  const sel=document.getElementById('month'); const now=new Date();
  let h='';
  for(let i=0;i<13;i++){
    const d=new Date(now.getFullYear(),now.getMonth()-i,1);
    const k=d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0');
    h+='<option value="'+k+'">'+monthTH(k)+'</option>';}
  sel.innerHTML=h; month=sel.value;}

async function loadRooms(){
  month=document.getElementById('month').value;
  const d=await (await fetch('/api/owner/rooms?month='+month)).json();
  rooms=d.rooms;
  const el=document.getElementById('rooms');
  if(!rooms.length){
    el.innerHTML='<p class="none">ยังไม่มีห้อง<br>กด "เพิ่มห้อง" ด้านบนเพื่อเริ่ม</p>';
  }else{
    el.innerHTML=rooms.map(r=>
      '<button class="rm" aria-current="'+(cur===r.room)+'" data-room="'+
      esc(r.room)+'">'+
      '<span class="no">'+esc(r.room)+'</span>'+
      '<span class="nm">'+esc(r.name||'')+'</span>'+
      '<span class="pip water'+(r.water?' on':'')+'" title="น้ำ"></span>'+
      '<span class="pip power'+(r.power?' on':'')+'" title="ไฟ"></span>'+
      '</button>').join('');
  }
  const ib=document.getElementById('inbox');
  ib.innerHTML = d.inbox ? '<div class="card inbox">'+
    '<span>มีรูป <b>'+d.inbox+'</b> ใบที่ยังไม่ได้ระบุห้อง</span>'+
    '<button class="btn sm" onclick="openInbox()">จัดเข้าห้อง</button></div>' : '';
  if(cur) openRoom(cur); else if(d.inbox) openInbox();
  else if(rooms.length) openRoom(rooms[0].room);
  else document.getElementById('detail').innerHTML='';
}
document.getElementById('rooms').addEventListener('click',e=>{
  const b=e.target.closest('.rm'); if(b) openRoom(b.dataset.room);});

/* ส่วนรูป: หัวกล่อง + แถบเลือก + ตารางรูป ใช้ร่วมกันทั้งห้องและรูปค้าง */
function gallery(title,ph,empty){
  shown=ph.map(p=>p.name);
  if(!ph.length) return '<div class="card panel"><div class="ph"><h2>'+title+
    '</h2></div><p class="none">'+empty+'</p></div>';
  return '<div class="card panel" id="gal">'+
    '<div class="ph"><h2>'+title+'</h2><span class="count">'+ph.length+
      ' ใบ</span><span class="grow"></span>'+
      '<button class="btn ghost sm" onclick="selMode(true)">เลือก</button>'+
      '<button class="btn ghost sm danger" onclick="delAll()">'+TRASH+
      'ลบทั้งหมด</button></div>'+
    '<div class="selbar"><span class="n" id="selN">ยังไม่ได้เลือก</span>'+
      '<button class="btn ghost sm" onclick="selAll()">เลือกทั้งหมด</button>'+
      '<button class="btn sm danger" id="selDel" onclick="delSel()" disabled>'+
      TRASH+'ลบที่เลือก</button>'+
      '<button class="btn ghost sm" onclick="selMode(false)">เสร็จ</button></div>'+
    '<div class="shots">'+ph.map(shot).join('')+'</div></div>';
}

async function openInbox(){
  cur=null;
  document.querySelectorAll('.rm').forEach(b=>b.setAttribute('aria-current',false));
  const ph=await (await fetch('/api/owner/photos?inbox=1')).json();
  document.getElementById('detail').innerHTML=
    gallery('รูปที่ยังไม่ได้ระบุห้อง',ph,'ไม่มีรูปค้าง ทุกใบเข้าห้องเรียบร้อย');
}

async function openRoom(room){
  cur=room;
  document.querySelectorAll('.rm').forEach(b=>
    b.setAttribute('aria-current', b.dataset.room===room));
  const d=await (await fetch('/api/owner/room?room='+encodeURIComponent(room))).json();
  if(d.error){document.getElementById('detail').innerHTML=
    '<div class="card panel"><p class="none">'+esc(d.error)+'</p></div>';return;}
  // โชว์เลขของ "เดือนที่เลือกอยู่" ไม่ใช่เลขล่าสุดเสมอ
  // ไม่งั้นย้อนดูเดือนก่อนแล้วเลขข้างบนยังเป็นของเดือนนี้ จะเข้าใจผิดทันที
  const cm={};
  ['water','power'].forEach(k=>{
    cm[k]=d.readings[k].find(r=>r.month===month)||null;});
  const start=new Date(month+'-01T00:00:00').getTime();
  const e0=new Date(month+'-01T00:00:00'); e0.setMonth(e0.getMonth()+1);
  const ph=d.photos.filter(p=>p.ts*1000>=start && p.ts*1000<e0.getTime());

  let h='<div class="card sum">';
  ['water','power'].forEach(k=>{
    h+='<div class="blk"><h3>'+TH[k]+' · '+monthTH(month)+'</h3>'+
      digits(cm[k]?cm[k].value:null,k);
    if(cm[k]&&cm[k].used!=null)
      h+='<p class="use">ใช้ไป<b class="'+k+'">'+cm[k].used+'</b>หน่วย</p>';
    else if(cm[k]) h+='<p class="use">ไม่มีเดือนก่อนให้เทียบ</p>';
    else h+='<p class="use">ยังไม่ได้จด</p>';
    h+='</div>';});
  h+='<span style="flex:1"></span><div class="acts">'+
    '<button class="btn ghost sm" data-act="reset">ตั้งรหัสใหม่</button>'+
    '<button class="btn ghost sm danger" data-act="delroom">ลบห้อง</button>'+
    '</div></div>';
  h+=gallery('รูปห้อง '+esc(room)+' · '+monthTH(month),ph,'ยังไม่มีรูปของเดือนนี้');
  document.getElementById('detail').innerHTML=h;
}

function shot(p){
  const opts=['water','power','other'].map(k=>
    '<option value="'+k+'"'+(p.kind===k?' selected':'')+'>'+TH[k]+'</option>'
  ).join('');
  const roomOpts='<option value="">เลือกห้อง</option>'+rooms.map(r=>
    '<option value="'+esc(r.room)+'"'+(p.room===r.room?' selected':'')+'>'+
    esc(r.room)+'</option>').join('');
  // เลือกห้อง เลือกชนิด พิมพ์เลข แล้วค่อยกดบันทึกทีเดียว
  // ถ้าบันทึกทันทีที่เลือกห้อง รูปจะย้ายออกจากหน้าจอไปก่อนที่จะได้พิมพ์เลข
  return '<div class="shot" data-n="'+esc(p.name)+'">'+
    '<div class="pic"><img loading="lazy" src="/t/'+encodeURIComponent(p.name)+
      '" alt="รูปมิเตอร์ '+when(p.ts)+'">'+
      '<span class="pick" aria-hidden="true"></span>'+
      '<button class="del" type="button" title="ลบรูปนี้" '+
      'aria-label="ลบรูปนี้">'+TRASH+'</button></div>'+
    '<div class="f"><span class="when">'+when(p.ts)+'</span>'+
    '<div class="rowf"><select data-k="room" aria-label="ห้อง">'+roomOpts+
      '</select><select data-k="kind" aria-label="ชนิดมิเตอร์">'+opts+
      '</select></div>'+
    '<div class="rowf"><input data-k="reading" inputmode="decimal" '+
      'aria-label="เลขที่อ่านได้" placeholder="เลขที่อ่านได้" value="'+
      esc(p.reading||'')+'">'+
      '<button class="btn sm" data-save disabled>บันทึก</button></div>'+
    '<span class="saved"></span>'+
    '</div></div>';
}

/* เหตุการณ์ทั้งหมดของส่วนรายละเอียด รวมไว้ที่เดียว (ไม่ต้องฝังชื่อไฟล์ใน onclick) */
const detail=document.getElementById('detail');
detail.addEventListener('click',e=>{
  const act=e.target.closest('[data-act]');
  if(act){ if(act.dataset.act==='reset') resetPw(cur);
           else delRoom(cur); return; }
  const box=e.target.closest('.shot'); if(!box) return;
  if(e.target.closest('.del')){ delOne(box); return; }
  if(e.target.closest('[data-save]')){ save(box); return; }
  if(e.target.closest('.pic')){
    if(document.getElementById('gal').classList.contains('selmode'))
      toggleSel(box);
    else zoom(box.dataset.n);
  }
});
detail.addEventListener('input',e=>{
  const box=e.target.closest('.shot'); if(box && e.target.dataset.k) dirty(box);});
detail.addEventListener('change',e=>{
  const box=e.target.closest('.shot'); if(box && e.target.dataset.k) dirty(box);});
detail.addEventListener('keydown',e=>{
  if(e.key==='Enter' && e.target.dataset.k==='reading') save(e.target.closest('.shot'));});

function dirty(box){
  box.querySelector('[data-save]').disabled=false;
  box.querySelector('.saved').textContent='';
}

async function save(box){
  const btn=box.querySelector('[data-save]');
  const tag=box.querySelector('.saved');
  const body={name:box.dataset.n};
  box.querySelectorAll('[data-k]').forEach(f=>{body[f.dataset.k]=f.value;});
  btn.disabled=true; tag.textContent='กำลังบันทึก…';
  const r=await post('/api/owner/set-photo',body);
  if(r.ok){ tag.textContent='บันทึกแล้ว'; box.classList.add('flash');
    setTimeout(()=>{box.classList.remove('flash'); loadRooms();},700);
  }else{ tag.textContent='บันทึกไม่สำเร็จ ลองอีกครั้ง'; btn.disabled=false; }
}

/* ---- ลบรูป ---- */
function selMode(on){
  const g=document.getElementById('gal'); if(!g) return;
  g.classList.toggle('selmode',on);
  if(!on) g.querySelectorAll('.shot.sel').forEach(s=>s.classList.remove('sel'));
  selCount();
}
function toggleSel(box){box.classList.toggle('sel'); selCount();}
function selAll(){
  const all=[...document.querySelectorAll('#gal .shot')];
  const every=all.every(s=>s.classList.contains('sel'));
  all.forEach(s=>s.classList.toggle('sel',!every)); selCount();
}
function selCount(){
  const n=document.querySelectorAll('#gal .shot.sel').length;
  const t=document.getElementById('selN'); if(!t) return;
  t.textContent=n?('เลือกแล้ว '+n+' ใบ'):'แตะรูปเพื่อเลือก';
  document.getElementById('selDel').disabled=!n;
}
async function removeShots(names){
  const r=await post('/api/owner/del-photos',{names:names});
  const j=await r.json().catch(()=>({}));
  if(!r.ok||!j.ok){toast('ลบไม่สำเร็จ ลองอีกครั้ง'); return;}
  names.forEach(n=>{
    const b=[...document.querySelectorAll('.shot')].find(s=>s.dataset.n===n);
    if(b) b.classList.add('gone');});
  toast('ลบแล้ว '+j.deleted+' ใบ');
  setTimeout(loadRooms,280);       /* รอให้รูปจางหายก่อนค่อยวาดใหม่ */
}
async function delOne(box){
  if(await ask('ลบรูปนี้?','รูปจะถูกลบออกจากคลังถาวร กู้คืนไม่ได้','ลบรูป'))
    removeShots([box.dataset.n]);
}
async function delSel(){
  const names=[...document.querySelectorAll('#gal .shot.sel')].map(s=>s.dataset.n);
  if(!names.length) return;
  if(await ask('ลบ '+names.length+' รูปที่เลือก?',
      'รูปจะถูกลบออกจากคลังถาวร กู้คืนไม่ได้','ลบ '+names.length+' รูป'))
    removeShots(names);
}
async function delAll(){
  if(!shown.length) return;
  const where=cur?('ห้อง '+cur+' เดือน '+monthTH(month)):'รูปที่ยังไม่ได้ระบุห้อง';
  if(await ask('ลบทั้งหมด '+shown.length+' รูป?',
      'ลบทุกรูปของ'+where+' ออกจากคลังถาวร กู้คืนไม่ได้ '+
      'รูปของห้องหรือเดือนอื่นจะไม่ถูกแตะ','ลบทั้งหมด'))
    removeShots(shown.slice());
}

async function addRoom(e){
  e.preventDefault();
  const r=await post('/api/owner/add-room',{
    room:document.getElementById('nroom').value.trim(),
    name:document.getElementById('nname').value.trim()});
  const j=await r.json();
  if(j.error){document.getElementById('adderr').textContent=j.error;
    dlgAdd.showModal();return;}
  document.getElementById('nroom').value='';
  document.getElementById('nname').value='';
  document.getElementById('adderr').textContent='';
  showPw('ห้อง '+j.room,j.password);
  cur=j.room; loadRooms();
}
async function resetPw(room){
  if(!await ask('ตั้งรหัสใหม่ให้ห้อง '+room+'?',
      'รหัสเดิมจะใช้ไม่ได้ทันที ต้องให้รหัสใหม่กับลูกบ้าน','ตั้งรหัสใหม่')) return;
  const j=await (await post('/api/owner/reset-pw',{room:room})).json();
  if(j.password) showPw('ห้อง '+room,j.password);
}
function showPw(title,pw){
  document.getElementById('showTitle').textContent=title;
  document.getElementById('showPw').textContent=pw;
  dlgShow.showModal();
}
async function delRoom(room){
  if(!await ask('ลบห้อง '+room+'?',
      'ลบห้องออกจากระบบ ลูกบ้านจะเข้าไม่ได้ รูปที่ถ่ายไว้ยังอยู่ในรูปค้าง','ลบห้อง'))
    return;
  await post('/api/owner/del-room',{room:room});
  cur=null; toast('ลบห้อง '+room+' แล้ว'); loadRooms();
}
async function setOwnerPw(e){
  e.preventDefault();
  const j=await (await post('/api/owner/set-owner-pw',
    {password:document.getElementById('opw').value})).json();
  if(j.error){document.getElementById('pwerr').textContent=j.error;
    dlgPw.showModal();return;}
  document.getElementById('opw').value='';
  document.getElementById('pwerr').textContent='';
  toast('เปลี่ยนรหัสเจ้าของหอแล้ว');
}

fillMonths(); loadRooms();

/* ---- คุมหุ่นในหน้าเดียวกัน ----
   ★ เปิดหน้าคุมหุ่นซ้อนเต็มจอแทนการเปลี่ยนหน้า ลิงก์จึงคงเดิม
   ★ ปิดแล้วล้าง src ทิ้ง ภาพสดจะหยุดดึง ไม่กินเน็ตตอนกลับมาดูรายการห้อง
   ★ ปุ่ม "กลับ" ในหน้าคุมหุ่นส่งข้อความ robot:close มาบอกให้ปิด */
const robotView=document.getElementById('robotView'),
      robotFrame=document.getElementById('robotFrame');
function openRobot(){
  robotFrame.src='__OWNER_PATH__/robot';
  robotView.classList.add('on');
  document.body.style.overflow='hidden';
  robotFrame.onload=()=>{ try{ robotFrame.contentWindow.focus(); }catch(e){} };
}
function closeRobot(){
  robotView.classList.remove('on');
  robotFrame.src='about:blank';
  document.body.style.overflow='';
  loadRooms();              /* รูปที่เพิ่งถ่ายจะขึ้นทันทีที่กลับมา */
}
addEventListener('message',e=>{
  if(e.origin===location.origin && e.data==='robot:close') closeRobot();
});
</script>""" + FOOT)
