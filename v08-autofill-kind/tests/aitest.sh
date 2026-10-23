#!/usr/bin/env bash
# ทดสอบ AI อ่านเลขมิเตอร์ทั้งหมด (ต้องมี python3 opencv + numpy ในเครื่องที่รัน)
#   bash tests/aitest.sh
# 1. metertest.py  ตัว AI เอง (รูปจริง / กระดาษสีอื่น / ภาพที่ไม่ควรได้เลข)
# 2. aitest.py x3  ทั้งสายบนเซิร์ฟเวอร์จริง: มี AI / ปิด AI / ไม่มี opencv
set -u
cd "$(dirname "$0")/.."
T=$(mktemp -d)
rc=0
echo "===== metertest.py ====="
python3 tests/metertest.py || rc=1

# ภาพนิ่งจำลองขนาด 64MP จากรูปมิเตอร์จริง (เหมือนกล้อง Arducam 9248 กว้าง)
python3 - "$T/still.jpg" <<'EOF'
import sys, cv2
im = cv2.imread("tests/meter/meter_2045.png")
cv2.imwrite(sys.argv[1], cv2.resize(im, (9248, 6936), interpolation=cv2.INTER_CUBIC),
            [cv2.IMWRITE_JPEG_QUALITY, 92])
EOF
# opencv ปลอมที่ import ไม่ได้ (จำลอง Pi ที่ไม่ได้ลง python3-opencv)
mkdir -p "$T/nocv/cv2"
echo 'raise ImportError("No module named cv2 (จำลอง)")' > "$T/nocv/cv2/__init__.py"

port=9460
for mode in on off nocv; do
    port=$((port + 1)); hport=$((port + 100))
    mkdir -p "$T/$mode/photos"
    # รูปเก่าที่ถ่ายก่อนมี AI (ไฟล์ข้อมูลไม่มีช่อง ai) -> ต้องถูกอ่านย้อนหลังตอนหุ่นว่าง
    cp "$T/still.jpg" "$T/$mode/photos/shot_20261001_120000.jpg"
    echo '{"room": "104", "kind": "other", "ts": 1790000000, "src": "จอย"}' \
        > "$T/$mode/photos/shot_20261001_120000.json"
    pp="tests/stub"; extra=""
    [ "$mode" = nocv ] && pp="$T/nocv:tests/stub"
    [ "$mode" = off ] && extra="ROBOT_METER_AI=0"
    env $extra ROBOT_METER_BACKFILL_GAP=0.5 FAKE_STILL="$T/still.jpg" ROBOT_WEBRTC=off PYTHONPATH="$pp" \
        python3 pi/server.py --port $port --photos "$T/$mode/photos" --no-pad >"$T/$mode/pi.log" 2>&1 &
    PI=$!
    python3 hub/hub.py --dir "$T/$mode/hub" --owner-pw testowner123 >/dev/null   # ตั้งรหัสแล้วออก
    HUB_TOKEN=tok-test python3 hub/hub.py --port $hport --dir "$T/$mode/hub" \
        >"$T/$mode/hub.log" 2>&1 &
    HUB=$!
    for i in $(seq 1 40); do
        python3 -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:$hport/',timeout=1)" 2>/dev/null \
          && curl -s -o /dev/null -u admin:12345678 http://127.0.0.1:$port/status && break
        sleep 0.25
    done
    echo "===== aitest.py ($mode) ====="
    python3 tests/aitest.py http://127.0.0.1:$port "$T/$mode/photos" http://127.0.0.1:$hport \
        "$T/$mode/hub" $mode || { rc=1; tail -n 15 "$T/$mode/pi.log"; }
    kill $PI $HUB 2>/dev/null; wait $PI $HUB 2>/dev/null
done
if [ $rc -eq 0 ]; then echo "ผ่านทุกชุด (AI)"; else echo "มีข้อที่ไม่ผ่าน — log อยู่ที่ $T"; fi
exit $rc
