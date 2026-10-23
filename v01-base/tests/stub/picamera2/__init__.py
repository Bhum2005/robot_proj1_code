"""picamera2 ปลอม — สร้างเฟรม JPEG ขนาดใกล้ของจริง

รุ่นนี้เพิ่มสองอย่างที่ของเดิมไม่มี:
  1. เคารพ FrameDurationLimits จริง (ทั้งตอน configure และ set_controls)
     ของเดิม set_controls เป็น no-op เลยวัดเรื่องเฟรมเรตกล้องไม่ได้
  2. จำลองต้นทุนซีพียูของการเข้ารหัส JPEG ด้วยซีพียู (Pi 5 ไม่มีฮาร์ดแวร์)
     แล้วนับจำนวนครั้งที่เข้ารหัส + เวลาซีพียูที่ใช้ไป
     อ่านผลได้ทาง picamera2.ENCODES / ENCODE_CPU_S
"""
import threading, time, os, zlib

FRAME_BYTES = int(os.environ.get("FAKE_FRAME_BYTES", "90000"))
CAM_FPS_MAX = float(os.environ.get("FAKE_CAM_FPS", "30"))   # เพดานของเซนเซอร์
# งานจำลองต่อเฟรม — ปรับให้ใกล้ต้นทุน JPEG 720p บน Cortex-A76
ENCODE_WORK = int(os.environ.get("FAKE_ENCODE_WORK", "240000"))

ENCODES = [0]          # นับทุกเฟรมที่ "เข้ารหัส" ไม่ใช่ที่ส่งออก
ENCODE_CPU_S = [0.0]   # เวลาซีพียูรวมที่ใช้เข้ารหัส


def reset_counters():
    ENCODES[0] = 0
    ENCODE_CPU_S[0] = 0.0


class Picamera2:
    def __init__(self):
        self.camera_properties = {"ScalerCropMaximum": (0, 0, 4608, 2592),
                                  "PixelArraySize": (4608, 2592)}
        self._out = None
        self._run = False
        self._t = None
        self._n = 0
        self._fps = CAM_FPS_MAX
        self._payload = (b"\xff\xd8" + os.urandom(FRAME_BYTES - 4) + b"\xff\xd9")

    # ---- การตั้งค่า ----
    def create_video_configuration(self, **kw):
        return dict(kw)

    def create_still_configuration(self, **kw):
        return dict(kw)

    def configure(self, cfg):
        self._cfg = cfg
        self._apply(cfg.get("controls") or {})

    def set_controls(self, c):
        self._apply(c or {})

    def _apply(self, c):
        """FrameDurationLimits เป็นไมโครวินาที (ต่ำสุด, สูงสุด)
        ของจริง ISP จะยึดช่วงนี้ เฟรมเรตจึงเท่ากับ 1/สูงสุด"""
        fd = c.get("FrameDurationLimits")
        if fd:
            us = max(fd) if isinstance(fd, (list, tuple)) else fd
            if us and us > 0:
                self._fps = min(CAM_FPS_MAX, 1000000.0 / float(us))

    @property
    def cam_fps(self):
        return self._fps

    def capture_metadata(self):
        time.sleep(0.05)
        return {"LensPosition": 3.33, "FocusFoM": 1000}

    def autofocus_cycle(self, wait=True):
        return True

    def switch_mode_and_capture_file(self, cfg, buf, format="jpeg"):
        time.sleep(0.4)
        buf.write(b"\xff\xd8" + b"S" * 20000 + b"\xff\xd9")

    # ---- สตรีม ----
    def start_recording(self, encoder, output):
        self._out = output.fileobj if hasattr(output, "fileobj") else output
        self._run = True

        def loop():
            nxt = time.time()
            while self._run:
                t0 = time.process_time()
                # จำลองงานเข้ารหัส JPEG ด้วยซีพียู — ของจริงก็กินตรงนี้
                zlib.crc32(self._payload[:ENCODE_WORK])
                ENCODE_CPU_S[0] += time.process_time() - t0
                ENCODES[0] += 1
                self._n += 1
                # ฝังเวลาที่สร้างเฟรมไว้ 20 ไบต์แรก เพื่อให้ปลายทางอ่านกลับได้
                # ใช้วัดความหน่วงจริงตั้งแต่เฟรมเกิด ถึงเฟรมถึงมือลูกค้า
                stamp = ("T%018.6f" % time.time()).encode()
                self._out.write(stamp + self._payload[len(stamp):])
                nxt += 1.0 / max(1.0, self._fps)
                d = nxt - time.time()
                if d > 0:
                    time.sleep(d)
                else:
                    nxt = time.time()

        self._t = threading.Thread(target=loop, daemon=True)
        self._t.start()

    def stop_recording(self):
        self._run = False
        if self._t:
            self._t.join(timeout=1)
