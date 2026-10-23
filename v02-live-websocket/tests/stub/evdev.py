"""evdev ปลอมเท่าที่ server.py ใช้ — ไว้ทดสอบตรรกะจอยโดยไม่ต้องมีจอยจริง"""
class _Codes:
    EV_ABS = 3
    EV_KEY = 1
    ABS_X = 0; ABS_Y = 1; ABS_Z = 2
    ABS_RX = 3; ABS_RY = 4; ABS_RZ = 5
    ABS_HAT0X = 16; ABS_HAT0Y = 17
    BTN_SOUTH = 304; BTN_EAST = 305; BTN_NORTH = 307; BTN_WEST = 308
    BTN_TL = 310; BTN_TR = 311
ecodes = _Codes()

class InputDevice:
    def __init__(self, path): raise OSError("ไม่มีจอยจริง")

def list_devices(): return []
