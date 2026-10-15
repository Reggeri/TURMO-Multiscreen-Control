"""FFmpeg streaming decoder with bounded memory and newest-frame delivery."""
import subprocess
import threading
from PIL import Image

class VideoSource:
    def __init__(self, path, fps=2, fit='Cover', resolution=480):
        self.path=str(path)
        self.fps=max(1,min(30,int(fps)))
        self.fit=fit if fit in ('Cover','Contain','Stretch') else 'Cover'
        self.resolution=min((160,240,320,480),key=lambda n:abs(n-int(resolution)))
        self.proc=None
        self.lock=threading.Lock()
        self.frame=None
        self.sequence=0
        self.quit=threading.Event()
        self.thread=threading.Thread(target=self._loop,daemon=True)
        self.thread.start()

    def _filter(self):
        w=self.resolution
        h=round(w*2/3)
        # Do the costly scale once at reduced resolution; nearest-neighbour upscale
        # deliberately trades sharpness for CPU. Output must remain 480x320 for USB.
        if self.fit=='Stretch':
            geometry=f'scale={w}:{h}'
        elif self.fit=='Contain':
            geometry=f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2'
        else:
            geometry=f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}'
        return f'fps={self.fps},{geometry},scale=480:320:flags=neighbor,format=rgb24'

    def _loop(self):
        from imageio_ffmpeg import get_ffmpeg_exe
        exe=get_ffmpeg_exe()
        size=480*320*3
        while not self.quit.is_set():
            # -re limits decoding to source time rather than burning CPU decoding ahead.
            args=[exe,'-hide_banner','-loglevel','error','-nostdin',
                  '-stream_loop','-1','-re','-i',self.path,'-an','-sn',
                  '-vf',self._filter(),'-pix_fmt','rgb24','-f','rawvideo','pipe:1']
            try:
                self.proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                    bufsize=0,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                while not self.quit.is_set():
                    buf=bytearray(size)
                    view=memoryview(buf)
                    pos=0
                    while pos<size and not self.quit.is_set():
                        n=self.proc.stdout.readinto(view[pos:])
                        if not n:break
                        pos+=n
                    if pos!=size:break
                    image=Image.frombytes('RGB',(480,320),buf)
                    with self.lock:
                        self.frame=image
                        self.sequence+=1
            except (OSError,ValueError):
                pass
            finally:
                self._kill()
            self.quit.wait(0.5)

    def get(self):
        with self.lock:return self.frame.copy() if self.frame is not None else None

    def get_new(self,last_sequence):
        with self.lock:
            if self.frame is None or self.sequence==last_sequence:
                return None,last_sequence
            return self.frame,self.sequence

    def _kill(self):
        proc=self.proc
        self.proc=None
        if proc is not None:
            try:proc.kill()
            except OSError:pass
            try:proc.wait(timeout=1)
            except (OSError,subprocess.TimeoutExpired):pass

    def close(self):
        self.quit.set()
        self._kill()
