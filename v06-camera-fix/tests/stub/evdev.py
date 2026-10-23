"""evdev ปลอมเท่าที่ server.py ใช้ — ไว้ทดสอบตรรกะจอยโดยไม่ต้องมีจอยจริง

FAKE_PAD=<ไฟล์>  สร้างจอยปลอม 1 ตัว อ่านปุ่มจากไฟล์นั้น บรรทัดละ "type code value"
                 เช่น  echo "1 311 1" >> ไฟล์   = กด R  (EV_KEY BTN_TR กดลง)
ไม่ตั้ง FAKE_PAD = ไม่มีจอยเลย (เหมือนเดิม)"""
import os


class _Codes:
    EV_ABS = 3
    EV_KEY = 1
    ABS_X = 0; ABS_Y = 1; ABS_Z = 2
    ABS_RX = 3; ABS_RY = 4; ABS_RZ = 5
    ABS_HAT0X = 16; ABS_HAT0Y = 17
    BTN_SOUTH = 304; BTN_EAST = 305; BTN_NORTH = 307; BTN_WEST = 308
    BTN_TL = 310; BTN_TR = 311


ecodes = _Codes()


class _AbsInfo:
    def __init__(self, lo=-32768, hi=32767):
        self.min, self.max = lo, hi


class _Ev:
    def __init__(self, t, c, v):
        self.type, self.code, self.value = t, c, v


class InputDevice:
    def __init__(self, path):
        if not os.environ.get("FAKE_PAD") or path != os.environ["FAKE_PAD"]:
            raise OSError("ไม่มีจอยจริง")
        self.path, self.name, self._pos, self._q = path, "จอยปลอม (ทดสอบ)", 0, []

    def capabilities(self):
        e = ecodes
        return {e.EV_ABS: [(c, _AbsInfo()) for c in (0, 1, 3, 4, 16, 17)]
                + [(c, _AbsInfo(0, 1023)) for c in (2, 5)],
                e.EV_KEY: [304, 305, 307, 308, 310, 311]}

    def read_one(self):
        if not self._q:
            try:
                with open(self.path, encoding="utf-8") as f:
                    f.seek(self._pos)
                    data = f.read()
                    self._pos = f.tell()
            except OSError:
                return None
            for ln in data.splitlines():
                p = ln.split()
                if len(p) == 3:
                    self._q.append(_Ev(int(p[0]), int(p[1]), int(p[2])))
        return self._q.pop(0) if self._q else None


def list_devices():
    return [os.environ["FAKE_PAD"]] if os.environ.get("FAKE_PAD") else []
