#!/usr/bin/env bash
# จำลองบั๊กกล้องค้างที่เจอบนหุ่นจริง (ขอข้อมูลกล้องระหว่างสลับโหมดถ่าย) แล้วถ่ายรัว 15 รูป
# ต้องถ่ายครบทุกรูป ไม่ค้าง  ใช้: bash tests/racetest.sh [ไฟล์ server.py]
set -u
cd "$(dirname "$0")/.."
SRV=${1:-pi/server.py}
T=$(mktemp -d); mkdir -p "$T/p"
FAKE_RACE=1 ROBOT_STILL_TIMEOUT=0 ROBOT_WEBRTC=off ROBOT_METER_AI=0 PYTHONPATH=tests/stub \
  python3 "$SRV" --port 9511 --photos "$T/p" --no-pad >"$T/log" 2>&1 &
P=$!; trap 'kill $P 2>/dev/null' EXIT; sleep 3
ok=0
for i in $(seq 1 15); do
  c=$(timeout 8 curl -s -o /dev/null -w "%{http_code}" -u admin:12345678 http://127.0.0.1:9511/photo)
  [ "$c" = 200 ] && ok=$((ok+1)) || { echo "  รูปที่ $i ค้าง/ล้มเหลว ($c)"; break; }
  sleep 0.$((RANDOM % 9))
done
echo "ถ่ายสำเร็จ $ok/15"
[ $ok -eq 15 ]
