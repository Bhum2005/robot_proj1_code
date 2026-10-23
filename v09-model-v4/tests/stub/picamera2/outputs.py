class FileOutput:
    def __init__(self, fileobj): self.fileobj = fileobj


import os as _os
import shutil as _shutil
import socket as _socket
import subprocess as _sp
import threading as _th


class PyavOutput:
    """แทนการส่ง H.264 เข้า MediaMTX ด้วย ffmpeg ภาพทดสอบ 1280x720
    ต่อ MediaMTX ไม่ได้ -> โยน OSError เหมือน av.open ของจริง
    ffmpeg ตาย (MediaMTX ปิด) -> เรียก error_callback เหมือนของจริง"""
    def __init__(self, output_name, format=None, pts=None, options=None):
        self.name = output_name
        self.error_callback = None
        self._p = None

    def start(self):
        hp = self.name.split("://", 1)[1].split("/", 1)[0]
        h, _, p = hp.partition(":")
        _socket.create_connection((h, int(p or 554)), timeout=1).close()
        ff = _shutil.which("ffmpeg")
        if not ff:
            raise OSError("no ffmpeg")
        codec = _os.environ.get("FAKE_H264_CODEC", "libx264")
        args = [ff, "-loglevel", "error", "-re", "-f", "lavfi", "-i",
                "testsrc=size=1280x720:rate=25"]
        if codec == "libx264":
            args += ["-c:v", "libx264", "-preset", "ultrafast", "-tune",
                     "zerolatency", "-profile:v", "baseline", "-g", "25",
                     "-pix_fmt", "yuv420p", "-b:v", "2M"]
        else:
            args += ["-c:v", codec, "-deadline", "realtime", "-g", "25", "-b:v", "2M"]
        args += ["-f", "rtsp", "-rtsp_transport", "tcp", self.name]
        self._p = _sp.Popen(args, stdin=_sp.DEVNULL)

        def watch(p=self._p):
            p.wait()
            if self._p is p and self.error_callback:
                self.error_callback(OSError("ffmpeg ended %s" % p.returncode))
        _th.Thread(target=watch, daemon=True).start()

    def stop(self):
        p, self._p = self._p, None
        if p:
            p.terminate()
            try:
                p.wait(timeout=3)
            except Exception:
                p.kill()
