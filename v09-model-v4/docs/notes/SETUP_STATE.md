# สถานะการติดตั้งจริง + config ทั้งหมด

> อัปเดตล่าสุด: 15 ต.ค. 2569 19:30 (แก้แล็ค: ภาพสด WebSocket / ปิด Nagle / ค่ากล้องใหม่ / push ไม่แย่งท่อ / ตัวจริงคือ hotspot มือถือ)
>
> ไฟล์นี้บอก **ของที่ติดตั้งอยู่จริงบนเครื่อง** ว่าอยู่ที่ไหน ตั้งค่าอะไรไว้ จะได้ไม่ต้องไล่ถามใหม่
> ส่วนเหตุผลการออกแบบ บั๊กที่เคยเจอ และงานค้าง อยู่ใน [`SUMMARY.md`](SUMMARY.md)
>
> ★ ไฟล์นี้ **ไม่มีรหัสผ่านหรือโทเคนจริง** (repo อาจถูก push ขึ้น GitHub)
>   ทุกค่าลับเขียนเป็นวิธีดูค่าจากเครื่องแทน

---

## 0. เริ่ม session ใหม่ ให้บอก Claude แค่นี้

> อ่าน `README.md`, `docs/notes/SUMMARY.md` และ `docs/notes/SETUP_STATE.md` ใน repo นี้ก่อน
> แก้โค้ดแล้วรัน `bash tests/run_all.sh` ให้ผ่านก่อนส่งทุกครั้ง
> งานที่ต้องทำต่ออยู่ในข้อ 8 ของ `SETUP_STATE.md`

---

## 1. ภาพรวมเครื่อง

```
  มือถือ/คอมคนนอก ──HTTPS──▶ Tailscale Funnel
                               https://bhum-loptop.<tailnet>.ts.net
                                        │ (proxy -> 127.0.0.1:8080)
                                        ▼
  ┌───────────────────────────────────────────────┐
  │ โน้ตบุ๊ก Ubuntu  bhum-loptop                   │
  │ Tailscale <IP-Tailscale-laptop>   user: bhum           │
  │ meterhub.service  -> hub.py :8080             │
  │   เว็บลูกบ้าน  /                               │
  │   เว็บเจ้าของหอ /<ทางลับเจ้าของหอ>                    │
  │   คุมหุ่น (ซ้อนในหน้าเจ้าของหอ) -> ส่งต่อไป Pi  │
  └───────────────▲───────────────────┬───────────┘
                  │ push.py ทุก 20 วิ │ proxy /frame /status ...
                  │                   ▼
  ┌───────────────┴───────────────────────────────┐
  │ Raspberry Pi 5  raspberrypi.local              │
  │ Tailscale <IP-Tailscale-Pi>   user: pi            │
  │ robot-server.service -> server.py :9000        │
  │ robot-push.service   -> push.py                │
  └───────────────┬───────────────────────────────┘
                  │ USB serial 115200
            ESP32-S3  (esp32/main.cpp)
```

| เครื่อง | ชื่อ | IP Tailscale | user | หน้าที่ |
|---|---|---|---|---|
| โน้ตบุ๊ก Ubuntu | `bhum-loptop` | `<IP-Tailscale-laptop>` | `bhum` | hub (คลังรูป + เว็บลูกบ้าน/เจ้าของหอ) |
| Raspberry Pi 5 | `raspberrypi` / `raspberrypi.local` | `<IP-Tailscale-Pi>` | `pi` | กล้อง จอย คุมหุ่น ส่งรูป |
| ESP32-S3 | — | — | — | ล้อ แปรง แขนกล้อง (ต่อ USB กับ Pi) |

Tailnet: `<tailnet>.ts.net`

### เครือข่ายจริง: hotspot มือถือ (Android, วง `10.115.44.0/24`)
- Pi `10.115.44.100` (wlan0, 5GHz ช่อง 36 ตอนวัด) / โน้ตบุ๊กต่อ hotspot ตัวเดียวกัน
- ★ **ตัวการภาพกระตุก/สายหลุดตัวจริง** — Pi ส่งไปมือถือหาย 53–73% แม้ปิดทุก service
  ปรับ hotspot แล้วเหลือ 0% (ดู SUMMARY "ตัวจริงที่เหลือ — hotspot มือถือ")
- เช็คสุขภาพคลื่นทุกครั้งที่ย้ายที่ / เปลี่ยนมือถือ:
  ```bash
  # บน Pi — ต้องหาย < 5%
  ping -c 30 $(ip route | awk '/default/{print $3; exit}') | tail -n 2
  iw dev wlan0 link | grep -E "freq|signal|tx bitrate"
  iw dev wlan0 station dump | grep "tx failed"   # วัดสองครั้งห่าง 30 วิ ไม่ควรเพิ่มเร็ว
  ```
- หน้าคุมหุ่นแสดง "WiFi ของ Pi" (dBm / Mbit/s / power save) ใน ตั้งค่า → คุณภาพสตรีม

---

## 2. โน้ตบุ๊ก (hub)

### ไฟล์และโฟลเดอร์

| อะไร | ที่อยู่ |
|---|---|
| โค้ด | `/home/bhum/meterhub-app/hub.py` + `pages.py` (ต้องอยู่โฟลเดอร์เดียวกัน) |
| ข้อมูล | `/home/bhum/meterhub/` (`rooms.json` `owner.json` `secret.key` `photos/` `thumbs/` `meta/`) |
| service | `/etc/systemd/system/meterhub.service` |

### service `meterhub` (ค่าที่ใช้อยู่จริง)

```ini
User=bhum
WorkingDirectory=/home/bhum/meterhub-app
Environment=HUB_TOKEN=<ดูด้วย: systemctl cat meterhub | grep HUB_TOKEN>
ExecStart=/usr/bin/python3 /home/bhum/meterhub-app/hub.py \
    --port 8080 \
    --dir /home/bhum/meterhub \
    --owner-path /<ทางลับเจ้าของหอ> \
    --robot http://<IP-Tailscale-Pi>:9000 \
    ...   (บรรทัดที่เหลือดูด้วย systemctl cat meterhub)
```

- `--robot` ชี้ Pi ผ่าน IP Tailscale ไม่ใช่ `raspberrypi.local` → ใช้ได้แม้คนละเครือข่าย
- `--robot-pass` / `ROBOT_PASS` ฝั่งนี้ต้องตรงกับ `ROBOT_PASS` ของ `robot-server` บน Pi
  ไม่ตรง = เปิดหน้าคุมหุ่นได้แต่ภาพไม่ขึ้น
- service เปิดเองตอนบูต (`enabled`) — **ไม่ต้องรัน hub.py ด้วยมือ** ถ้ารันซ้ำจะเจอ `Address already in use`

### ลิงก์

| หน้า | ในเครื่อง | ผ่าน Tailscale (มือถือที่ลงแอป) | สาธารณะ (Funnel) |
|---|---|---|---|
| ลูกบ้าน | `http://localhost:8080/` | `http://<IP-Tailscale-laptop>:8080/` | `https://bhum-loptop.<tailnet>.ts.net/` |
| เจ้าของหอ | `http://localhost:8080/<ทางลับเจ้าของหอ>` | `http://<IP-Tailscale-laptop>:8080/<ทางลับเจ้าของหอ>` | `https://bhum-loptop.<tailnet>.ts.net/<ทางลับเจ้าของหอ>` |
| คุมหุ่น | ปุ่ม "คุมหุ่น" ในหน้าเจ้าของหอ (เปิดซ้อน ลิงก์ไม่เปลี่ยน) | | |

### รหัส

- **รหัสเจ้าของหอ** เก็บเป็นแฮชใน `/home/bhum/meterhub/owner.json` — อ่านกลับไม่ได้
  - เปลี่ยนในเว็บ: ปุ่ม "รหัสของฉัน" ในหน้าเจ้าของหอ
  - ลืม: `cd ~/meterhub-app && python3 hub.py --dir /home/bhum/meterhub --owner-pw <รหัสใหม่> && sudo systemctl restart meterhub`
  - ★ รหัสที่ตั้งตอน session 15 ต.ค. เคยพิมพ์ในแชท — **ต้องเปลี่ยนก่อนให้คนนอกใช้**
- **รหัสลูกบ้าน** ออกจากหน้าเจ้าของหอ (เพิ่มห้อง → แสดงรหัสครั้งเดียว) เก็บเป็นแฮชใน `rooms.json`

### Tailscale Funnel

```bash
sudo tailscale funnel --bg 8080        # เปิด (ค้างไว้แม้รีบูต)
tailscale funnel status                # ต้องเห็น (Funnel on)
sudo tailscale funnel --https=443 off  # ปิด
```

- เปิดสิทธิ์ Funnel ใน tailnet แล้ว (กดยืนยันผ่านลิงก์ `login.tailscale.com/f/funnel?...` ตอน 15 ต.ค.)
- ★ ตอนจบ session: คอมเปิดได้ แต่เครื่องอื่นขึ้น "This site can't be reached"
  น่าจะรอ DNS กระจาย — เช็ค `dig +short bhum-loptop.<tailnet>.ts.net @1.1.1.1` (ต้องได้ IP ที่ไม่ใช่ 100.x)

### คำสั่งที่ใช้บ่อย

```bash
sudo systemctl restart meterhub
systemctl status meterhub --no-pager | head -n 5
journalctl -u meterhub -n 50 --no-pager
systemctl cat meterhub                 # ดู config ทั้งหมด
sudo ss -ltnp | grep :8080             # ใครจับพอร์ตอยู่
```

---

## 3. Raspberry Pi

### ไฟล์และโฟลเดอร์

| อะไร | ที่อยู่ |
|---|---|
| โค้ด | `/home/pi/server/server.py`, `/home/pi/server/push.py` |
| รูปที่ถ่าย | `/home/pi/robot_photos/` (`.jpg` + `.json` คู่กัน) |
| สถานะการส่งรูป | ไฟล์ state ของ push.py ในโฟลเดอร์เดียวกับโค้ด |
| สำรองตัวเก่า | `/home/pi/server/server.py.bak` |

★ บน Pi มีโฟลเดอร์ `~/meterhub-app` ที่สร้างผิดเครื่องตอน 15 ต.ค. (ว่าง ไม่ได้ใช้) ลบทิ้งได้

### service `robot-server`

```ini
User=pi
WorkingDirectory=/home/pi/server
Environment=ROBOT_USER=admin
Environment=ROBOT_PASS=<ดูด้วย: systemctl cat robot-server | grep ROBOT_PASS>
ExecStart=/usr/bin/python3 /home/pi/server/server.py \
    --port 9000 \
    --photos /home/pi/robot_photos
    (+ ค่าที่ตั้งเพิ่มบนเครื่อง ดูด้วย systemctl cat robot-server)
ExecStartPre=/bin/sleep 8
ExecStartPre=-+/usr/sbin/iw dev wlan0 set power_save off     # ← เพิ่ม 15 ต.ค. ค่ำ
```

ค่าภาพสดเริ่มต้นตอนนี้คือ 854x480 q65 กล้อง 25fps ส่งออกไม่เกิน 20fps (ไม่ต้องใส่อะไร)
★ ถ้าใน service ยังมี `--stream-size 1280x720` ค้างอยู่ ให้ลบออก
ถ้าเน็ตแย่มาก: `--stream-size 640x360 --stream-quality 50`
ปรับเฟรมเรตตัวกล้องได้ด้วย `Environment=ROBOT_CAM_FPS=25` (ค่าเริ่มต้น)

### ปิด WiFi power save ให้ถาวร (ทำครั้งเดียว)

service ปิดให้ทุกครั้งที่เปิดอยู่แล้ว แต่ถ้า WiFi หลุดแล้วต่อใหม่ NetworkManager จะเปิดกลับ ให้ตั้งที่ต้นทางด้วย:

```bash
printf '[connection]\nwifi.powersave = 2\n' | sudo tee /etc/NetworkManager/conf.d/99-wifi-powersave-off.conf
sudo systemctl restart NetworkManager
iw dev wlan0 get power_save          # ต้องได้ Power save: off
```

### service `robot-push` (ค่าที่ใช้อยู่จริง)

```ini
ExecStart=/usr/bin/python3 /home/pi/server/push.py \
    --to http://<IP-Tailscale-laptop>:8080 \
    --token <ต้องตรงกับ HUB_TOKEN ของ meterhub> \
    --dir /home/pi/robot_photos \
    --every 20
```

### คำสั่งที่ใช้บ่อย

```bash
sudo systemctl restart robot-server
sudo systemctl status robot-server --no-pager | head -n 5
journalctl -u robot-push -n 20 --no-pager     # ดูว่าส่งรูปผ่านไหม
curl -s -m 5 http://<IP-Tailscale-laptop>:8080/healthz  # Pi คุยกับ hub ได้ไหม
md5sum ~/server/server.py                      # เช็คเวอร์ชันก่อนรันทุกครั้ง
hostname -I
```

ลิงก์ตรงเข้า Pi (ไม่ผ่าน hub): `http://raspberrypi.local:9000` หรือ `http://<IP-Tailscale-Pi>:9000`
หน้าสุขภาพ: `http://raspberrypi.local:9000/status` (ดู `kbps` `dropHz` `lagMs` `wifiPs` `wifiDbm`)

---

## 4. ESP32-S3

- โค้ด: `esp32/main.cpp` ใน repo
- serial 115200 ที่ `/dev/ttyACM*` บน Pi
- **รุ่นที่ต้องใช้: fw v9** (มีคำสั่ง `X` หยุดฉุกเฉิน ล้อ+แปรง+แขน และดับแปรงเองเมื่อไม่ได้ `#M` จาก Pi เกิน 2 วิ)
- เช็ครุ่น: ส่ง `?` ทาง serial ต้องตอบ `# robot fw v9 ...`
- ★ ตอนจบ session ยัง **ไม่ได้แฟลช v9** — บนบอร์ดยังเป็น v8 ปุ่มหยุดฉุกเฉินดับแค่ล้อ
- ก่อนแฟลชต้อง `sudo systemctl stop robot-server` บน Pi (มันจับพอร์ตอยู่) แฟลชเสร็จค่อย `start`

ขา/ค่าสำคัญใน `main.cpp`: I2C SDA 8 / SCL 9 (PCA9685 0x40, pan ช่อง 7, tilt ช่อง 4),
ล้อ MDD3A ขา 42/41 (ซ้าย) 40/39 (ขวา), แปรง DRV8833 ขา 15/16/17/18,
`SWAP_LR=false` เพราะสลับซ้ายขวาที่ `server.py` แล้ว (ห้ามสลับสองที่)

---

## 5. ค่าที่ต้องตรงกันข้ามเครื่อง (พลาดบ่อยที่สุด)

| ค่า | ฝั่ง hub (โน้ตบุ๊ก) | ฝั่ง Pi | ไม่ตรงแล้วเป็นยังไง |
|---|---|---|---|
| โทเคนส่งรูป | `HUB_TOKEN` ใน `meterhub.service` | `--token` ใน `robot-push.service` | push ขึ้น `คลังปฏิเสธ (403)` |
| รหัสหน้าคุมหุ่น | `--robot-pass` / `ROBOT_PASS` ใน `meterhub.service` | `ROBOT_PASS` ใน `robot-server.service` | หน้าคุมหุ่นเปิดได้แต่ภาพไม่ขึ้น |
| ที่อยู่ hub | — | `--to http://<IP-Tailscale-laptop>:8080` | push ขึ้น `timed out` |
| ที่อยู่ Pi | `--robot http://<IP-Tailscale-Pi>:9000` | — | หน้าคุมหุ่นขึ้น 502 "ต่อหุ่นไม่ได้" |

ตอนจบ session 15 ต.ค. — โทเคนและที่อยู่ทั้งสองฝั่งตรงกันแล้ว (เช็คจาก `systemctl cat` ทั้งสองเครื่อง)

---

## 6. เวอร์ชันไฟล์ที่ติดตั้ง (md5)

เช็คด้วย `md5sum <ไฟล์>` ก่อนรันทุกครั้ง (เบราว์เซอร์ชอบเซฟเป็น `server(1).py`)

| ไฟล์ | md5 (เวอร์ชัน 15 ต.ค. ค่ำ — แก้แล็ค) | อยู่ที่ |
|---|---|---|
| `pi/server.py` | `e20a11e91255f6f17c52ff049cd92958` | Pi `/home/pi/server/` (16 ต.ค. บ่าย: AI จดสิ่งที่เดาลงไฟล์ข้อมูลคู่รูป + อ่านรูปเก่าย้อนหลังตอนหุ่นว่าง) |
| `pi/meter_ai/` (ส่งเป็น `meter_ai.zip` md5 `67e25f79b7b234c84e56b7a093aa59ac` — โมเดลเทรนใหม่ 16 ต.ค.) | — | Pi `/home/pi/server/meter_ai/` ต้องมี `python3-opencv` |
| `pi/webrtc/setup_webrtc.sh` + `pi/webrtc/mediamtx.yml` + `pi/webrtc/mediamtx.service` | (ใหม่) | Pi `/home/pi/server/` — รัน setup_webrtc.sh ครั้งเดียว |
| `pi/push.py` | `9e2b555308ae9aa4f2698409044dea0a` | Pi `/home/pi/server/` (16 ต.ค. บ่าย: รูปเคยส่งแล้ว ส่งแค่ข้อมูลที่เปลี่ยนไป /push-meta) |
| `hub/hub.py` | `1dd2bb8345f480526c3cc9bfea151abf` | โน้ตบุ๊ก `/home/bhum/meterhub-app/` (16 ต.ค. บ่าย: /push-meta, ช่อง ai, ค่าที่เจ้าของหอแก้หุ่นทับไม่ได้, ยืนยันล่าสุดขึ้นข้างบน) |
| `hub/pages.py` | `901a72e68c902a29986e0a3a1f4bc78b` | โน้ตบุ๊ก `/home/bhum/meterhub-app/` (16 ต.ค. บ่าย: แถบ AI อ่านได้ + ปุ่มยืนยัน, ปุ่มบันทึกบอกเหตุผล, ดาวน์โหลดรูปเต็ม) |

รุ่นก่อนหน้า (15 ต.ค. บ่าย): server.py `e84cbf6f...` / hub.py `3371c12a...` — ถ้า md5 ตรงสองตัวนี้ = ยังไม่ได้อัปเดต

★ `hub.py`/`pages.py` ตัวนี้เป็นรุ่นลบรูป+ดีไซน์ใหม่ ต้องติดตั้งทับแล้ว restart meterhub ส่วน `server.py` scp ไปถึง Pi แล้ว
  แต่ยังไม่แน่ใจว่ารีสตาร์ท `robot-server` แล้วหรือยัง — เช็ค md5 แล้ว `sudo systemctl restart robot-server`

---

## 7. ขั้นตอนอัปเดตโค้ด (ทำซ้ำได้ทุกครั้ง)

**บนโน้ตบุ๊ก** (Terminal ปกติ ไม่ใช่หน้าต่าง ssh — prompt ต้องเป็น `bhum@bhum-loptop`)

```bash
cd ~/Downloads
md5sum hub.py pages.py server.py               # เทียบกับตารางข้อ 6 (หรือค่าที่ Claude ให้)
cp ~/meterhub-app/hub.py ~/meterhub-app/hub.py.bak
cp hub.py pages.py ~/meterhub-app/
sudo systemctl restart meterhub
scp server.py pi@raspberrypi.local:/home/pi/server/server.py
```

**บน Pi** (`ssh pi@raspberrypi.local` — prompt ต้องเป็น `pi@raspberrypi`)

```bash
md5sum ~/server/server.py
sudo systemctl restart robot-server
```

ครั้งแรกของรุ่น 15 ต.ค. ค่ำ — เพิ่มบรรทัดปิด WiFi power save เข้า service เดิม
(ใช้ไฟล์เสริม ไม่ต้องแก้ไฟล์ service ที่มีรหัสอยู่):

```bash
sudo mkdir -p /etc/systemd/system/robot-server.service.d
printf '[Service]\nExecStartPre=-+/usr/sbin/iw dev wlan0 set power_save off\n' | sudo tee /etc/systemd/system/robot-server.service.d/wifi.conf
sudo systemctl daemon-reload && sudo systemctl restart robot-server
```

**เปิดเว็บแล้วกด Ctrl+Shift+R** — เวอร์ชันใหม่ (15 ต.ค. ค่ำ) เช็คได้สองทาง
- ตั้งค่า → คุณภาพสตรีม → "ภาพสดวิ่งทาง" ต้องขึ้น **WebSocket** (ถ้าขึ้น "HTTP (สำรอง)" = WebSocket ผ่านไม่ได้ ภาพยังมาแต่ช้ากว่า)
- F12 → Network → WS ต้องเห็น `ws?id=...` เส้นเดียว และ **ไม่มี** `frame?id=` / `drive?` วิ่งรัว ๆ
- แถว "WiFi ของ Pi" ต้องขึ้น "ประหยัดไฟปิดแล้ว" และสัญญาณดีกว่า -70 dBm

**ย้อนกลับ**

```bash
# โน้ตบุ๊ก
cp ~/meterhub-app/hub.py.bak ~/meterhub-app/hub.py && sudo systemctl restart meterhub
# Pi
cp ~/server/server.py.bak ~/server/server.py && sudo systemctl restart robot-server
```

**ทดสอบก่อนส่งโค้ด** (บนเครื่องไหนก็ได้ ไม่ต้องมีหุ่น): `bash tests/run_all.sh` — ต้องได้ 15/15, 37/37 และ 25/25

---

## 8. สิ่งที่ค้างอยู่ (เรียงตามความสำคัญ)

0.0 **วิดีโอ WebRTC** (หุ่นไกลแล้วค้าง) — ติดตั้ง `server.py` ใหม่ + `bash setup_webrtc.sh` บน Pi
   เช็ค: ตั้งค่า → คุณภาพสตรีม → "ภาพสดวิ่งทาง" ต้องขึ้น `WebRTC (วิดีโอ H.264)`
   ถ้าขึ้น "วิดีโอ: ..." ต่อท้าย = เหตุผลที่เปิดไม่ได้ (เช่น picamera2 เก่า) ภาพยังใช้ JPEG ได้
   Funnel: ยังเข้าไม่ได้จากเน็ต AIS (TLS ถูกตัดหลัง ClientHello) — รอผล check-host.net
0.1 ✅ ติดตั้งตัวแก้แล็คแล้ว + ปรับ hotspot มือถือ → ping Pi หาย 0% ภาพลื่นขึ้นมาก (19:20)
   ★ จดด้วยว่าปรับ hotspot อะไรไป (ย้ายที่ / ปิด power saving / สลับคลื่น) — ยังไม่ได้บันทึก
0.2 **ปิด WiFi power save ของโน้ตบุ๊ก** (ถ้ายังไม่ได้ทำ) — วัดได้หน่วงพุ่ง 158ms
   `sudo sed -i 's/wifi.powersave = 3/wifi.powersave = 2/' /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf && sudo systemctl restart NetworkManager`
0.3 **ทดลองผ่าน Tailscale / Funnel** — ดูวิธีในข้อ 2 ตาราง "ลิงก์" + `tailscale ping` ต้องขึ้น `direct`
0. **ติดตั้งตัวแก้แล็ค (15 ต.ค. ค่ำ) แล้วลองกับหุ่นจริง** — `server.py` + `push.py` + `robot-server.service` บน Pi (รีสตาร์ททั้ง robot-server และ robot-push), `hub.py` บนโน้ตบุ๊ก (md5 ข้อ 6)
   ทำข้อ "ปิด WiFi power save ให้ถาวร" ในข้อ 3 ด้วย แล้วเช็คตามข้อ 7
   ถ้ายังแล็คผ่าน Funnel: `tailscale ping <IP-Tailscale-Pi>` จากโน้ตบุ๊ก — ถ้าขึ้น `via DERP` แปลว่าโน้ตบุ๊กกับ Pi ไม่ได้ต่อกันตรง

1. **แฟลช fw v9 ลง ESP32** แล้วทดสอบ (ยกล้อลอยก่อน)
   - สั่งเดิน + เปิดแปรง → กดหยุดฉุกเฉิน → ล้อหยุดทันที แปรงดับ
   - เปิดแปรง → `sudo systemctl stop robot-server` → แปรงดับเองใน 2 วิ
2. **ยืนยัน Funnel** เข้าได้จากมือถือที่ใช้เน็ตมือถือ (ไม่ลงแอป Tailscale)
3. **เปลี่ยนรหัสเจ้าของหอ** (ตัวเดิมเคยพิมพ์ในแชท) — จำเป็นก่อนให้คนนอกใช้เพราะ Funnel เปิดสาธารณะแล้ว
4. **รีสตาร์ท robot-server** ถ้ายังไม่ได้ทำ (ข้อ 6)
4.1 **ติดตั้ง hub.py + pages.py รุ่นลบรูป/ดีไซน์ใหม่** บนโน้ตบุ๊ก (md5 ในข้อ 6) แล้ว `sudo systemctl restart meterhub`
4.2 หน้าคุมหุ่นใน `server.py` ยังเป็นดีไซน์เดิม — ถ้าจะให้เข้าชุดกับหน้าใหม่ ต้องทำแยกและลองกับหุ่นจริงทันที
4.3 skill frontend-design: บนเครื่อง B รัน `npx claude-code-templates@latest --skill creative-design/frontend-design` เอง (ใน session Claude ติดตั้งผ่าน npx ไม่ได้ GitHub API 403)
5. ภาพหยุด 1–3 วิตอนกดถ่าย — แก้ได้ด้วยสตรีมคู่ main+lores แบบ `robot-update` (ต้องลองกับกล้องจริง)
6. ตัวลบรูปเก่าอัตโนมัติบน Pi (เช่นเกิน 7 วันและส่งขึ้น hub แล้ว)
7. ย้าย hub ไปเครื่องที่เปิดตลอด (ตอนนี้ถ้าโน้ตบุ๊กปิด/หลับ เว็บลูกบ้านและ Funnel ล่ม)
8. **push ขึ้น GitHub** — Claude ไม่มีสิทธิ์เขียน repo `Bhum2005/pi_esp_control_server`
   ใช้ `git am all-fixes.patch` แล้ว push เอง หรือติดตั้ง Claude GitHub App ให้ repo นี้

---

## 9. สิ่งที่ทำใน session 15 ต.ค. (สั้น ๆ)

| commit | ทำอะไร |
|---|---|
| tests: run_all.sh | รันสองชุดทดสอบคำสั่งเดียว / hubtest ไม่ตกเมื่อรันต่อจาก regress |
| ภาพสดแบบขอทีละใบ | `/frame?after=N` แทน MJPEG — แก้ภาพค้างแม้ต่อ Pi ตรง (ยืนยันบนหุ่นจริงแล้ว) |
| คุมหุ่นในหน้าเจ้าของหอ | เปิดซ้อนเต็มจอ ลิงก์ไม่เปลี่ยน / hub ใส่ `X-Frame-Options: SAMEORIGIN` |
| esp32 main.cpp v8 → v9 | คำสั่ง `X` + ดับแปรงเมื่อ Pi เงียบ |
| docs | SUMMARY ข้อ 6.1 + ไฟล์นี้ |
| ลบรูป + ดีไซน์ใหม่ | หน้าเจ้าของหอลบรูปได้ทีละใบ/เลือกหลายใบ/ลบทั้งหมดที่แสดงอยู่ (`/api/owner/del-photos`) และปรับดีไซน์หน้าล็อกอิน ลูกบ้าน เจ้าของหอ ใหม่ทั้งหมด (ล้อตัวเลขมิเตอร์หมุน, ฟอนต์ Chakra Petch + Anuphan) — หน้าคุมหุ่นใน server.py ยังเป็นดีไซน์เดิม |

| แก้แล็ค (ค่ำ) | ภาพสด WebSocket `/ws` + คำสั่งขับในสายเดียวกัน / ปิด Nagle (Pi + hub) / hub ส่งต่อ WebSocket / ค่ากล้องใหม่ / `/status` เบา / รายงาน+ปิด WiFi power save / `tests/livetest.py` — รายละเอียด SUMMARY สาเหตุที่ 6 |

นอกโค้ด: เปิด Tailscale Funnel, ติดตั้ง hub/pages (รุ่นคุมหุ่นซ้อน) บนโน้ตบุ๊ก, scp server.py ไป Pi
ทดสอบ: `bash tests/run_all.sh` ผ่าน 15/15 + 37/37 + 25/25 ณ commit สุดท้าย

รายละเอียดเชิงเหตุผล (ทำไมภาพค้าง, ทำไมไม่ย้ายทุกอย่างไป Pi) อยู่ใน `SUMMARY.md` ข้อ 3 สาเหตุที่ 5

### drop-in ของ robot-server ที่ต้องมี (16 ต.ค. บ่าย)
```bash
# เปิดใหม่เองเมื่อโปรแกรมปิดตัว (ยามถ่ายภาพค้าง / L+R ตอนกล้องค้าง ใช้วิธีนี้)
printf '[Service]\nRestart=always\nRestartSec=1\n' | sudo tee /etc/systemd/system/robot-server.service.d/restart.conf
# log ออกทันที + พิมพ์ตำแหน่งที่ค้างได้ (ใช้หาต้นเหตุกล้องค้าง)
printf '[Service]\nEnvironment=PYTHONUNBUFFERED=1\nEnvironment=PYTHONFAULTHANDLER=1\n' | sudo tee /etc/systemd/system/robot-server.service.d/debug.conf
sudo systemctl daemon-reload && sudo systemctl restart robot-server
```
ดูตอนกล้องค้าง: `journalctl -u robot-server --no-pager | grep -A30 "ค้าง"` ; เวลาถ่ายแต่ละขั้น: `journalctl -u robot-server | grep "still:"`
