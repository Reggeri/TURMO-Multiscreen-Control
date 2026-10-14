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
    """RGB565 for any rectangle size."""
    raw=image.convert('RGB').tobytes()
    out=bytearray(len(raw)//3*2)
    for i in range(0,len(raw),3):
        r,g,b=raw[i],raw[i+1],raw[i+2]
        val=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
        j=(i//3)*2
        out[j]=val & 255;out[j+1]=val>>8
    return out

def encode_rgb565(image):
    """RGB565 little endian, exactly two bytes per pixel, row major."""
    if image.size not in ((WIDTH, HEIGHT),(NATIVE_WIDTH,NATIVE_HEIGHT)):
        raise ValueError('Expected 480x320 or 320x480 RGB image')
    return encode_region(image)

class Display:
    def __init__(self, port, orientation=1, transport="Native portrait CW"):
        self.port=port;self.orientation=orientation;self.transport=transport;self.ser=None
        self._last_image=None
        self.last_stats=None
    def __enter__(self):
        # Some USB CDC bridges ignore baud, others respect it. Test only with
        # explicit TURMO_BAUD; keep the proven default for normal users.
        try:
            baud=int(os.environ.get('TURMO_BAUD','115200'))
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
        bbox=None
        if self._last_image is not None and self._last_image.size==image.size:
            bbox=ImageChops.difference(image,self._last_image).getbbox()
            if bbox is None:
                self.last_stats={'seconds':time.perf_counter()-started,'bytes':0,'mode':'unchanged'}
                return
        if bbox is None:
            bbox=(0,0,width,height)
        x0,y0,x1,y1=bbox
        # Cropping a tiny changed region greatly reduces traffic on static themes.
        # When most of the screen changed, avoid overhead and use a full frame.
        if (x1-x0)*(y1-y0)>width*height*0.85:
            x0,y0,x1,y1=0,0,width,height
        region=image.crop((x0,y0,x1,y1))
        payload=encode_rgb565(region) if region.size in ((WIDTH,HEIGHT),(NATIVE_WIDTH,NATIVE_HEIGHT)) else encode_region(region)
        self.ser.write(packet(197,x0,y0,x1-1,y1-1))
        block_size=65536  # fewer Python-to-driver writes; device may still throttle
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
