"""USB35INCHIPSV2 / Rev-A protocol. No vendor software required."""
import time
import os
from PIL import ImageChops
import serial
from PIL import Image

WIDTH, HEIGHT = 480, 320
NATIVE_WIDTH, NATIVE_HEIGHT = 320, 480

def packet(command, x=0, y=0, x2=0, y2=0):
    return bytes(((x >> 2) & 255, ((x & 3) << 6) | (y >> 4),
                  ((y & 15) << 4) | (x2 >> 6), ((x2 & 63) << 2) | (y2 >> 8),
                  y2 & 255, command))

def encode_region(image):
    """Vectorized RGB565 packing (much faster than per-pixel Python loops)."""
    import numpy as np
    rgb = np.asarray(image.convert('RGB'), dtype=np.uint8)
    r = rgb[:, :, 0].astype(np.uint16)
    g = rgb[:, :, 1].astype(np.uint16)
    b = rgb[:, :, 2].astype(np.uint16)
    packed = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    return packed.astype('<u2', copy=False).tobytes()

def encode_rgb565(image):
    """RGB565 little endian, exactly two bytes per pixel, row major."""
    if image.size not in ((WIDTH, HEIGHT),(NATIVE_WIDTH,NATIVE_HEIGHT)):
        raise ValueError('Expected 480x320 or 320x480 RGB image')
    return encode_region(image)

class Display:
    def __init__(self, port, orientation=1, transport="Native portrait CW", video_mode=False):
        self.port=port;self.orientation=orientation;self.transport=transport;self.ser=None
        self.video_mode=video_mode
        self.video_window=(96,72)
        self.video_fullscreen=False
        self._last_image=None
        self.last_stats=None
    def __enter__(self):
        # Some USB CDC bridges ignore baud, others respect it. Test only with
        # explicit TURMO_BAUD; keep the proven default for normal users.
        try:
            baud=int(os.environ.get('TURMO_VIDEO_BAUD','115200') if self.video_mode else os.environ.get('TURMO_BAUD','115200'))
        except ValueError:
            baud=115200
        if baud not in (115200,230400,460800,921600,1000000,2000000):
            baud=115200
        self.ser=serial.Serial(self.port,baud,timeout=1.5,write_timeout=15,rtscts=True)
        time.sleep(.25)
        self.ser.reset_input_buffer()
        self.ser.write(b'\x45'*6)
        answer=self.ser.read(6)
        if answer not in (b'\x01'*6, b''):
            raise RuntimeError(f'Unexpected display handshake: {answer.hex()}')
        # 16-byte landscape command: width and height in big-endian.
        orientation=bytearray(16)
        orientation[:6]=packet(121)
        # Native portrait transport avoids firmware landscape coordinate mismatch.
        native = self.transport.startswith('Native portrait')
        actual_orientation = 0 if native else self.orientation
        width,height = (NATIVE_WIDTH,NATIVE_HEIGHT) if native else (WIDTH,HEIGHT)
        orientation[6]=100+actual_orientation
        orientation[7:11]=bytes((width>>8,width&255,height>>8,height&255))
        self.ser.write(orientation)
        self.ser.flush()
        time.sleep(.15)
        self.ser.write(packet(109))
        self.ser.flush()
        return self
    def send_video(self, image, stop=None):
        """Video-only compact, atomic frames; no visible tile/scanline assembly.

        The display's protocol sends raw RGB565. Lower decode resolution
        does not help unless the USB *rectangle* is also smaller. Send one
        complete, centered selectable rectangle per frame, rather
        than a 320x240 rectangle (150 KiB). Keep the normal send() untouched.
        """
        started=time.perf_counter()
        if stop is not None and stop.is_set():
            return
        # Clear the previous image only once when entering video mode.
        if not getattr(self, '_video_window_initialized', False):
            self.send(Image.new('RGB',(WIDTH,HEIGHT),(0,0,0)),stop)
            self._video_window_initialized=True
            self._video_last=None
        # Fixed small window means full-frame updates, with no tearing from
        # out-of-order tiles and no bandwidth wasted on black margins.
        w,h=getattr(self,'video_window',(96,72))
        if (w,h) not in ((96,72),(128,96),(160,120),(192,144),(160,110)):
            w,h=96,72
        frame=image.convert('RGB')
        frame.thumbnail((w,h),Image.Resampling.BILINEAR)
        region=Image.new('RGB',(w,h),(0,0,0))
        region.paste(frame,((w-frame.width)//2,(h-frame.height)//2))
        if self.video_fullscreen:
            # Low-detail fullscreen: upscale locally; the device has no verified hardware scaling command.
            region=region.resize((WIDTH,HEIGHT),Image.Resampling.NEAREST)
            w,h=WIDTH,HEIGHT
        if self.transport == 'Native portrait CW':
            region=region.transpose(Image.Transpose.ROTATE_270)
            x0,y0=(NATIVE_WIDTH-region.width)//2,(NATIVE_HEIGHT-region.height)//2
        elif self.transport == 'Native portrait CCW':
            region=region.transpose(Image.Transpose.ROTATE_90)
            x0,y0=(NATIVE_WIDTH-region.width)//2,(NATIVE_HEIGHT-region.height)//2
        else:
            x0,y0=(WIDTH-w)//2,(HEIGHT-h)//2
        payload=encode_region(region)
        if payload==getattr(self,'_video_last',None):
            self.last_stats={'seconds':time.perf_counter()-started,'bytes':0,'mode':'video-unchanged'}
            return
        if stop is not None and stop.is_set():
            return
        self.ser.write(packet(197,x0,y0,x0+region.width-1,y0+region.height-1))
        # The proven bounded write size is preserved for compatibility.
        for pos in range(0,len(payload),65536):
            block=payload[pos:pos+65536]
            if self.ser.write(block)!=len(block):
                self._video_last=None
                raise IOError('Incomplete video USB write')
        self.ser.flush()
        self._video_last=payload
        self.last_stats={'seconds':time.perf_counter()-started,'bytes':len(payload)+6,'mode':'video-compact-frame'}

    def send_photo(self,image,stop=None):
        """Phone photo only: bounded 16-row transfers to avoid one 300 KiB write.

        Normal themes, EQ and video paths remain unchanged. Each stripe uses
        the established command 197, no undocumented compression/commands.
        """
        started=time.perf_counter()
        if self.transport == 'Native portrait CW':
            image=image.transpose(Image.Transpose.ROTATE_270)
        elif self.transport == 'Native portrait CCW':
            image=image.transpose(Image.Transpose.ROTATE_90)
        image=image.convert('RGB')
        width,height=image.size
        if (width,height) not in ((WIDTH,HEIGHT),(NATIVE_WIDTH,NATIVE_HEIGHT)):
            raise ValueError('Invalid phone image dimensions: '+str(image.size))
        if self._last_image is not None and self._last_image.size==image.size:
            if ImageChops.difference(image,self._last_image).getbbox() is None:
                self.last_stats={'seconds':time.perf_counter()-started,'bytes':0,'mode':'phone-unchanged'}
                return
        total=0
        # 16 native rows = at most 15 KiB. This avoids a large pending
        # Windows serial write that can time out on some TURMO devices.
        for y in range(0,height,16):
            if stop is not None and stop.is_set(): return
            y2=min(height,y+16)
            payload=encode_region(image.crop((0,y,width,y2)))
            self.ser.write(packet(197,0,y,width-1,y2-1))
            sent=self.ser.write(payload)
            if sent!=len(payload): raise IOError('Incomplete phone photo write')
            self.ser.flush()
            total+=len(payload)+6
            time.sleep(0.004)
        self._last_image=image
        self.last_stats={'seconds':time.perf_counter()-started,'bytes':total,'mode':'phone-photo-stripes'}

    def send(self,image,stop=None):
        """Send only changed rectangle when useful; never interrupt a frame.

        The TURMO command 197 accepts native portrait pixel coordinates.
        Full-motion video may change every pixel, in which case a full frame
        is still required. Actual transfer time is measured, not assumed.
        """
        started=time.perf_counter()
        if self.transport == 'Native portrait CW':
            image=image.transpose(Image.Transpose.ROTATE_270)
        elif self.transport == 'Native portrait CCW':
            image=image.transpose(Image.Transpose.ROTATE_90)
        image=image.convert('RGB')
        width,height=image.size
        if (width,height) not in ((WIDTH,HEIGHT),(NATIVE_WIDTH,NATIVE_HEIGHT)):
            raise ValueError(f'Invalid frame size: {image.size}')
        # MIDNIGHT EQ: bar-by-bar dirty rectangles in display-native coordinates.
        # Each narrow column is independent; text changes use the ordinary full
        # image diff, but bar animation never expands into a full-width rectangle.
        if getattr(self, 'midnight_sparse', False) and time.monotonic() - getattr(self, '_midnight_last_resync', 0.0) >= 30:
            self._last_image = None
            self._midnight_last_resync = time.monotonic()
        if getattr(self, 'midnight_sparse', False) and self._last_image is not None and self._last_image.size == image.size:
            import numpy as np
            current=np.asarray(image)
            previous=np.asarray(self._last_image)
            # A title/artist change is rare: send the changed text as a separate
            # rectangle, then return to small bar updates on subsequent frames.
            if self.transport.startswith('Native portrait'):
                bar_axis_is_y=True
            else:
                bar_axis_is_y=False
            # For each bar, use exact changed bounds, with 8px gaps omitted.
            rectangles=[]
            for i in range(20):
                left=44+i*20;right=left+12
                if self.transport == 'Native portrait CW':
                    # ROTATE_270: source x -> native y, source y -> native x
                    crop=(69, left, 184, right)  # native x=320-source_y; y=source_x
                elif self.transport == 'Native portrait CCW':
                    crop=(136, 480-right, 251, 480-left)
                else:
                    crop=(left,136,right,251)
                x0,y0,x1,y1=crop
                patchdiff=np.any(current[y0:y1,x0:x1] != previous[y0:y1,x0:x1],axis=2)
                yy,xx=np.nonzero(patchdiff)
                if xx.size:
                    rectangles.append((x0+int(xx.min()),y0+int(yy.min()),x0+int(xx.max())+1,y0+int(yy.max())+1))
            # Other pixels (track metadata, borders) must not be silently lost.
            mask=np.any(current!=previous,axis=2)
            for x0,y0,x1,y1 in rectangles:mask[y0:y1,x0:x1]=False
            yy,xx=np.nonzero(mask)
            if xx.size:rectangles.append((int(xx.min()),int(yy.min()),int(xx.max())+1,int(yy.max())+1))
            if not rectangles:
                self.last_stats={'seconds':time.perf_counter()-started,'bytes':0,'mode':'midnight-unchanged'}
                return
            total_area=sum((x1-x0)*(y1-y0) for x0,y0,x1,y1 in rectangles)
            if total_area < width*height*0.80:
                total_bytes=0
                for x0,y0,x1,y1 in rectangles:
                    if stop is not None and stop.is_set():return
                    payload=encode_region(image.crop((x0,y0,x1,y1)))
                    self.ser.write(packet(197,x0,y0,x1-1,y1-1))
                    self.ser.write(payload)
                    total_bytes+=len(payload)+6
                self.ser.flush()
                self._last_image=image
                self.last_stats={'seconds':time.perf_counter()-started,'bytes':total_bytes,'mode':'midnight-bars'}
                return
        # EQ: transmit changed sub-rectangles rather than one huge bounding box.
        # In native portrait orientation the 24 vertical EQ columns become rows.
        if getattr(self, 'eq_sparse', False) and self._last_image is not None and self._last_image.size == image.size:
            import numpy as np
            cur = np.asarray(image)
            old = np.asarray(self._last_image)
            changed = np.any(cur != old, axis=2)
            horizontal = width == NATIVE_WIDTH
            slices = 24
            rectangles = []
            for i in range(slices):
                if horizontal:
                    lo = int(i * height / slices); hi = int((i+1) * height / slices)
                    ys, xs = np.nonzero(changed[lo:hi, :])
                    if xs.size:
                        rectangles.append((int(xs.min()), lo + int(ys.min()), int(xs.max())+1, lo + int(ys.max())+1))
                else:
                    lo = int(i * width / slices); hi = int((i+1) * width / slices)
                    ys, xs = np.nonzero(changed[:, lo:hi])
                    if xs.size:
                        rectangles.append((lo + int(xs.min()), int(ys.min()), lo + int(xs.max())+1, int(ys.max())+1))
            # All 24 bars can change at once. Never force a full-frame write
            # merely because more than 12 stripes are active; USB bandwidth
            # depends primarily on pixel count, not this arbitrary threshold.
            total_area = sum((x1-x0)*(y1-y0) for x0,y0,x1,y1 in rectangles)
            if rectangles and total_area < width*height*0.92:
                total_bytes=0
                for x0,y0,x1,y1 in rectangles:
                    payload=encode_region(image.crop((x0,y0,x1,y1)))
                    self.ser.write(packet(197,x0,y0,x1-1,y1-1))
                    self.ser.write(payload)
                    total_bytes += len(payload)+6
                self.ser.flush()
                self._last_image=image
                self.last_stats={'seconds':time.perf_counter()-started,'bytes':total_bytes,'mode':'eq-sparse'}
                return
            if not rectangles:
                self.last_stats={'seconds':time.perf_counter()-started,'bytes':0,'mode':'unchanged'}
                return
        bbox=None
        if self._last_image is not None and self._last_image.size==image.size:
            bbox=ImageChops.difference(image,self._last_image).getbbox()
            if bbox is None:
                self.last_stats={'seconds':time.perf_counter()-started,'bytes':0,'mode':'unchanged'}
                return
        if bbox is None:
            bbox=(0,0,width,height)
        x0,y0,x1,y1=bbox
        if (x1-x0)*(y1-y0)>width*height*0.85:
            x0,y0,x1,y1=0,0,width,height
        region=image.crop((x0,y0,x1,y1))
        payload=encode_region(region)
        self.ser.write(packet(197,x0,y0,x1-1,y1-1))
        block_size=65536
        for pos in range(0,len(payload),block_size):
            block=payload[pos:pos+block_size]
            written=self.ser.write(block)
            if written!=len(block):raise IOError('Incomplete serial write')
        self.ser.flush()
        self._last_image=image
        self.last_stats={'seconds':time.perf_counter()-started,'bytes':len(payload)+6,
                         'mode':'partial' if len(payload)<width*height*2 else 'full'}

    def __exit__(self,*args):
        if self.ser:self.ser.close()
