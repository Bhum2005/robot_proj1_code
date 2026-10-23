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
        # FAKE_JPEG=<ไฟล์> ใช้ภาพจริง (ไม่ฝังเวลา) — สำหรับทดสอบหน้าเว็บในเบราว์เซอร์
        self._real = None
        if os.environ.get("FAKE_JPEG"):
            with open(os.environ["FAKE_JPEG"], "rb") as f:
                self._real = f.read()

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
        # FAKE_RACE=1 จำลองบั๊กที่เจอบนหุ่นจริง: ขอข้อมูลกล้องระหว่างสลับโหมดถ่ายภาพนิ่ง = ค้างตลอดไป
        if os.environ.get("FAKE_RACE") and getattr(self, "_switching", False):
            self._meta_hit = True          # ตัวสลับโหมดจะค้างด้วย (รอกันไปมาแบบของจริง)
            while True:
                time.sleep(1)
        time.sleep(0.05)
        return {"LensPosition": 3.33, "FocusFoM": 1000}

    def autofocus_cycle(self, wait=True):
        return True

    def switch_mode_and_capture_file(self, cfg, buf, format="jpeg"):
        self._switching = True
        try:
            self._switch_capture(cfg, buf, format)
        finally:
            self._switching = False

    def _switch_capture(self, cfg, buf, format="jpeg"):
        self._meta_hit = False
        time.sleep(0.4)
        if os.environ.get("FAKE_RACE") and self._meta_hit:
            while True:                    # ค้างแบบที่เห็นใน log ของหุ่น (รอ job ไม่จบ)
                time.sleep(1)
        if os.environ.get("FAKE_STILL_HANG"):          # จำลองกล้องค้างตอนถ่าย (เหมือนบนหุ่นจริง)
            while True:
                time.sleep(1)
        # FAKE_STILL=<ไฟล์> ภาพนิ่งจริง (เช่นรูปมิเตอร์) — ใช้ทดสอบ AI อ่านเลข
        if os.environ.get("FAKE_STILL"):
            with open(os.environ["FAKE_STILL"], "rb") as f:
                buf.write(f.read())
            return
        buf.write(b"\xff\xd8" + b"S" * 20000 + b"\xff\xd9")

    # ---- ตัวเข้ารหัสหลายตัว (แบบ picamera2 จริง) ----
    def camera_configuration(self):
        return getattr(self, "_cfg", {})

    def start_encoder(self, encoder, output, name=None):
        from .encoders import LibavH264Encoder
        if isinstance(encoder, LibavH264Encoder):
            output.start()                 # ต่อ MediaMTX ไม่ได้ = โยนข้อผิดพลาดแบบของจริง
            encoder._output = output
            self._encs = getattr(self, "_encs", set()) | {encoder}
            return
        if name == "lores" and os.environ.get("FAKE_FAIL_LORES"):
            raise RuntimeError("จำลอง: กล้องไม่ยอมเปิด JPEG บนสตรีมรอง")
        self._out = output.fileobj if hasattr(output, "fileobj") else output
        self._encs = getattr(self, "_encs", set()) | {encoder}

    def stop_encoder(self, encoders=None):
        encs = getattr(self, "_encs", set())
        if encoders is None:
            todo = set(encs)
        elif isinstance(encoders, (set, list)):
            todo = set(encoders)
        else:
            todo = {encoders}
        for e in todo:
            out = getattr(e, "_output", None)
            if out is not None:
                out.stop()
        self._encs = encs - todo

    def start(self):
        if not self._run and getattr(self, "_out", None) is not None:
            self._loop_start()

    def stop(self):
        self._run = False
        if self._t:
            self._t.join(timeout=1)

    # ---- สตรีม ----
    def start_recording(self, encoder, output):
        self.start_encoder(encoder, output)
        self.start()

    def _loop_start(self):
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
                if self._real is not None:
                    self._out.write(self._real)
                    nxt += 1.0 / max(1.0, self._fps)
                    d = nxt - time.time()
                    if d > 0:
                        time.sleep(d)
                    else:
                        nxt = time.time()
                    continue
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
        self.stop()
        self.stop_encoder()
