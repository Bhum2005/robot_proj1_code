#!/usr/bin/env bash
# รันชุดทดสอบทั้งสองชุดในคำสั่งเดียว — ใช้โฟลเดอร์ชั่วคราวใหม่ทุกครั้ง ไม่ต้องเปิดหลายหน้าต่าง
#   bash tests/run_all.sh
set -u
cd "$(dirname "$0")/.."
T=$(mktemp -d)
PI_PORT=9340; HUB_PORT=8250
mkdir -p "$T/photos"

python3 hub/hub.py --dir "$T/hub" --owner-pw testowner123 >/dev/null
PYTHONPATH=tests/stub python3 pi/server.py --port $PI_PORT --photos "$T/photos" >"$T/pi.log" 2>&1 &
PI=$!
HUB_TOKEN=tok-test python3 hub/hub.py --port $HUB_PORT --dir "$T/hub" \
    --robot http://127.0.0.1:$PI_PORT >"$T/hub.log" 2>&1 &
HUB=$!
trap 'kill $PI $HUB 2>/dev/null; wait 2>/dev/null' EXIT

# รอให้ทั้งสองตัวเปิดพอร์ต
for i in $(seq 1 30); do
    python3 - <<EOF 2>/dev/null && break
import urllib.request
urllib.request.urlopen("http://127.0.0.1:$PI_PORT/status", timeout=1)
urllib.request.urlopen("http://127.0.0.1:$HUB_PORT/", timeout=1)
EOF
    sleep 0.5
done
if ! kill -0 $PI 2>/dev/null || ! kill -0 $HUB 2>/dev/null; then
    echo "เซิร์ฟเวอร์เปิดไม่ขึ้น (พอร์ต $PI_PORT/$HUB_PORT ถูกใช้อยู่?) ดู log ที่ $T"
    tail -n 5 "$T/pi.log" "$T/hub.log"
    exit 1
fi

rc=0
echo "===== regress.py ====="
TEST_PHOTOS="$T/photos" python3 tests/regress.py || rc=1
echo "===== hubtest.py ====="
python3 tests/hubtest.py http://127.0.0.1:$HUB_PORT "$T/hub" || rc=1
echo "===== livetest.py ====="
python3 tests/livetest.py http://127.0.0.1:$PI_PORT http://127.0.0.1:$HUB_PORT || rc=1

if [ $rc -eq 0 ]; then echo "ผ่านทั้งสามชุด"; else echo "มีข้อที่ไม่ผ่าน — log อยู่ที่ $T"; fi
exit $rc
