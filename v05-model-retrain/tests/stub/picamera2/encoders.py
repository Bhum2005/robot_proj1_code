class JpegEncoder:
    def __init__(self, q=None, **kw): self.q = q


class LibavH264Encoder:
    """แทน H.264 ของจริง — ตัวงานจริงอยู่ที่ PyavOutput ปลอม (ใช้ ffmpeg)"""
    def __init__(self, bitrate=None, repeat=True, iperiod=30, framerate=30,
                 qp=None, profile=None):
        self.bitrate, self.iperiod, self.framerate = bitrate, iperiod, framerate
        self.profile = profile
