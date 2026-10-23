#!/usr/bin/env bash
# ทดสอบการถ่ายรูปในเบราว์เซอร์จริง: วิดีโอไม่หลุดตอนถ่าย + R บนจอย/Space = บันทึก
#   bash tests/shottest.sh /path/to/mediamtx
set -u
cd "$(dirname "$0")/.."
MTX=${1:?ใส่ที่อยู่ไฟล์ mediamtx}
T=$(mktemp -d); mkdir -p "$T/p"; : > "$T/pad"
python3 - <<PY > "$T/test.jpg"
import sys; from PIL import Image
im=Image.new('RGB',(854,480),(30,60,90)); im.save(sys.stdout.buffer,'JPEG')
PY
"$MTX" pi/mediamtx.yml >"$T/mtx.log" 2>&1 &
FAKE_PAD="$T/pad" FAKE_H264_CODEC=libvpx FAKE_JPEG="$T/test.jpg" ROBOT_CALIB="$T/c.json" ROBOT_METER_AI=0 \
  PYTHONPATH=tests/stub python3 pi/server.py --port 9395 --photos "$T/p" --webrtc on >"$T/pi.log" 2>&1 &
P=$!
trap 'kill $P 2>/dev/null; pkill -x mediamtx; pkill -f "testsrc=size=1280x720"; wait 2>/dev/null' EXIT
sleep 4
python3 -u tests/shot_browser.py http://127.0.0.1:9395 "$T/pad" "$T/p"; rc=$?
[ $rc -ne 0 ] && tail -n 30 "$T/pi.log"
exit $rc
