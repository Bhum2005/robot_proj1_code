#!/usr/bin/env bash
# รูปใหม่ขึ้น hub เร็ว (ปลุก push.py + รูปย่อก่อนตอนมีคนดูภาพสด) + AI ใส่ค่าให้เมื่อมั่นใจ >= 75%
#   bash tests/fastpush.sh      (ต้องมี python3 opencv + numpy)
set -u
cd "$(dirname "$0")/.."
T=$(mktemp -d); PIP=9471; HP=9571
mkdir -p "$T/photos"
python3 - "$T/still.jpg" <<'PY'
import sys, cv2
im = cv2.imread("tests/meter/meter_2045.png")
cv2.imwrite(sys.argv[1], cv2.resize(im, (9248, 6936), interpolation=cv2.INTER_CUBIC),
            [cv2.IMWRITE_JPEG_QUALITY, 92])
PY
export ROBOT_LIVE_FLAG="$T/live" ROBOT_PUSH_KICK="$T/kick"
FAKE_STILL="$T/still.jpg" ROBOT_WEBRTC=off PYTHONPATH=tests/stub \
    python3 pi/server.py --port $PIP --photos "$T/photos" --no-pad >"$T/pi.log" 2>&1 &
PI=$!
python3 hub/hub.py --dir "$T/hub" --owner-pw testowner123 >/dev/null
HUB_TOKEN=tok-test python3 hub/hub.py --port $HP --dir "$T/hub" >"$T/hub.log" 2>&1 &
HUB=$!
for i in $(seq 1 40); do
    curl -s -o /dev/null http://127.0.0.1:$HP/healthz && curl -s -o /dev/null -u admin:12345678 http://127.0.0.1:$PIP/status && break
    sleep 0.25
done
HUB_TOKEN=tok-test python3 -u pi/push.py --to http://127.0.0.1:$HP --dir "$T/photos" \
    --state "$T/push_state.json" --every 20 --live-kbps 500 >"$T/push.log" 2>&1 &
PUSH=$!
trap 'kill $PI $HUB $PUSH 2>/dev/null; wait 2>/dev/null' EXIT
python3 tests/fastpush.py http://127.0.0.1:$PIP "$T/photos" http://127.0.0.1:$HP "$T/hub" "$T/live"
rc=$?
[ $rc -ne 0 ] && { echo "--- push.log"; tail -n 20 "$T/push.log"; echo "--- pi.log"; tail -n 10 "$T/pi.log"; }
exit $rc
