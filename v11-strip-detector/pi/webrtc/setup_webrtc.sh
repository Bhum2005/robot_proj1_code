#!/usr/bin/env bash
# ติดตั้งวิดีโอ WebRTC ให้หน้าคุมหุ่น — รันบน Pi ครั้งเดียว:
#     bash setup_webrtc.sh
# ทำสามอย่าง:
#   1. ลง python3-av (picamera2 ใช้ส่ง H.264)
#   2. ลง MediaMTX v1.9.3 ไว้ที่ /usr/local/bin + config ที่ /etc/mediamtx.yml + service
#   3. ให้ robot-server รอ MediaMTX ก่อนเปิด แล้วรีสตาร์ททั้งคู่
# ย้อนกลับ: sudo systemctl disable --now mediamtx  (server.py จะกลับไปใช้ JPEG เอง)
set -euo pipefail
cd "$(dirname "$0")"
VER=v1.9.3

case "$(uname -m)" in
  aarch64) ARCH=linux_arm64v8 ;;
  armv7l)  ARCH=linux_armv7 ;;
  x86_64)  ARCH=linux_amd64 ;;
  *) echo "ไม่รู้จักเครื่องแบบ $(uname -m)"; exit 1 ;;
esac

echo "==> 1/3 ลง python3-av + เช็ค picamera2"
sudo apt-get install -y -qq python3-av
# ★ ต้องมี PyavOutput (picamera2 รุ่นใหม่) — ไม่มีก็ไม่พัง แค่ใช้ JPEG ต่อไป
#   ไม่อัปเกรดให้เอง: กล้อง Arducam 64MP ผูกกับ libcamera รุ่นที่ลงไว้
#   อัปเกรดเองถ้าจำเป็น: sudo apt update && sudo apt install --only-upgrade python3-picamera2
if python3 -c "from picamera2.outputs import PyavOutput; from picamera2.encoders import LibavH264Encoder" 2>/dev/null; then
  echo "    picamera2 รองรับวิดีโอ H.264 แล้ว"
else
  echo "    ⚠ picamera2 รุ่นนี้ยังไม่มี PyavOutput — วิดีโอจะยังไม่เปิด (ภาพ JPEG ใช้ได้ปกติ)"
  echo "      รุ่นที่ลงไว้: $(dpkg-query -W -f='${Version}' python3-picamera2 2>/dev/null)"
fi

echo "==> 2/3 ลง MediaMTX $VER ($ARCH)"
if ! /usr/local/bin/mediamtx --help 2>&1 | grep -q "$VER"; then
  TMP=$(mktemp -d)
  wget -q -O "$TMP/mtx.tgz" \
    "https://github.com/bluenviron/mediamtx/releases/download/$VER/mediamtx_${VER}_${ARCH}.tar.gz"
  tar -xzf "$TMP/mtx.tgz" -C "$TMP" mediamtx
  sudo install -m 755 "$TMP/mediamtx" /usr/local/bin/mediamtx
  rm -rf "$TMP"
fi
sudo install -m 644 mediamtx.yml /etc/mediamtx.yml
sudo install -m 644 mediamtx.service /etc/systemd/system/mediamtx.service

echo "==> 3/3 ให้ robot-server เปิดหลัง MediaMTX"
sudo mkdir -p /etc/systemd/system/robot-server.service.d
printf '[Unit]\nAfter=mediamtx.service\nWants=mediamtx.service\n' |
  sudo tee /etc/systemd/system/robot-server.service.d/webrtc.conf >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx
sudo systemctl restart mediamtx
sleep 1
sudo systemctl restart robot-server

sleep 12
echo
systemctl is-active mediamtx >/dev/null && echo "MediaMTX: ทำงานอยู่" || echo "MediaMTX: ไม่ทำงาน — ดู journalctl -u mediamtx -n 30"
journalctl -u robot-server -n 40 --no-pager | grep -E "วิดีโอ H.264|webrtc|MediaMTX" | tail -n 3
echo "เปิดหน้าคุมหุ่น -> ตั้งค่า -> คุณภาพสตรีม -> 'ภาพสดวิ่งทาง' ต้องขึ้น WebRTC"
