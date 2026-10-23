class SerialException(Exception): pass
class Serial:
    def __init__(self,*a,**k):
        self.port=None; self.baudrate=0; self.timeout=0; self.dtr=False; self.rts=False
    def open(self): raise SerialException("stub: no device")
    def read(self,n): return b""
    def write(self,b): return len(b)
    def reset_input_buffer(self): pass
    def close(self): pass
