#!/usr/bin/env bash
# ทดสอบวิดีโอ WebRTC ครบเส้นในเบราว์เซอร์จริง (ไม่ต้องมีหุ่น)
#   bash tests/webrtctest.sh /path/to/mediamtx
# ต้องมี: mediamtx (v1.9.3), ffmpeg ที่มี libvpx, python3-playwright + chromium
# ★ Chromium ของ Playwright เล่น H.264 ไม่ได้ ตัวส่งจำลองจึงส่ง VP8 แทน
#   ทดสอบทางเดินทั้งหมด (WHEP ผ่าน server.py/hub -> MediaMTX -> WebRTC -> หน้าเว็บ)
#   ส่วนการเล่น H.264 จริงต้องดูบน Chrome/Safari ของจริง
set -u
cd "$(dirname "$0")/.."
MTX=${1:?ใส่ที่อยู่ไฟล์ mediamtx}
T=$(mktemp -d); mkdir -p "$T/p"
python3 hub/hub.py --dir "$T/hub" --owner-pw testowner123 >/dev/null
python3 - <<PY > "$T/test.jpg"
import sys; from PIL import Image
im=Image.new('RGB',(854,480),(30,60,90)); im.save(sys.stdout.buffer,'JPEG')
PY
"$MTX" pi/mediamtx.yml >"$T/mtx.log" 2>&1 &
M=$!
FAKE_H264_CODEC=libvpx FAKE_JPEG="$T/test.jpg" ROBOT_CALIB="$T/c.json" PYTHONPATH=tests/stub \
  python3 pi/server.py --port 9391 --photos "$T/p" --no-pad --webrtc on >"$T/pi.log" 2>&1 &
P=$!
HUB_TOKEN=t python3 hub/hub.py --port 8291 --dir "$T/hub" --robot http://127.0.0.1:9391 \
  --owner-path /jod-x >"$T/hub.log" 2>&1 &
H=$!
trap 'kill $P $H 2>/dev/null; pkill -x mediamtx; pkill -f "testsrc=size=1280x720"; wait 2>/dev/null' EXIT
sleep 4
python3 -u tests/webrtc_browser.py http://127.0.0.1:9391 http://127.0.0.1:8291 /jod-x "$MTX"
