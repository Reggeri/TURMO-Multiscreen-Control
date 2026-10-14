"""FFmpeg-powered streaming decoder: supports 1080p+ input, outputs 480x320 RGB."""
import subprocess
import threading
import time
from pathlib import Path
from PIL import Image

class VideoSource:
    def __init__(self,path,fps=2):
        self.path=str(path);self.fps=max(1,min(2,int(fps)))
        self.proc=None;self.lock=threading.Lock();self.frame=None;self.quit=threading.Event()
        self.thread=threading.Thread(target=self._loop,daemon=True)
        self.thread.start()
    def _loop(self):
        from imageio_ffmpeg import get_ffmpeg_exe
        exe=get_ffmpeg_exe()
        size=480*320*3
        while not self.quit.is_set():
            args=[exe,'-hide_banner','-loglevel','error','-nostdin','-stream_loop','-1',
                  '-i',self.path,'-an','-vf',f'fps={self.fps},scale=480:320:force_original_aspect_ratio=increase,crop=480:320',
                  '-pix_fmt','rgb24','-f','rawvideo','-']
            try:
                self.proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                while not self.quit.is_set():
                    buf=bytearray()
                    while len(buf)<size and not self.quit.is_set():
                        chunk=self.proc.stdout.read(size-len(buf))
                        if not chunk:break
                        buf.extend(chunk)
                    if len(buf)!=size:break
                    im=Image.frombytes('RGB',(480,320),bytes(buf))
                    with self.lock:self.frame=im
                self._kill()
            except Exception:
                self._kill()
                self.quit.wait(2)
    def get(self):
        with self.lock:return self.frame.copy() if self.frame is not None else None
    def _kill(self):
        p=self.proc
        if p is not None:
            try:p.kill()
            except OSError:pass
            try:p.wait(timeout=1)
            except Exception:pass
            self.proc=None
    def close(self):
        self.quit.set();self._kill()
