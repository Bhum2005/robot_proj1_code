"""libcamera ปลอม — แค่พอให้ server.py อ้างถึงได้"""
class _Af:
    Manual, Auto, Continuous = 0, 1, 2
class _Range:
    Normal, Macro, Full = 0, 1, 2
class controls:
    AfModeEnum = _Af
    AfRangeEnum = _Range
    class AfMeteringEnum:
        Auto, Windows = 0, 1
    class AfSpeedEnum:
        Normal, Fast = 0, 1
def Transform(**kw): return kw
