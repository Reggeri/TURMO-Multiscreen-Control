"""Premium, clean 480x320 smart clock and weather dashboard."""
from datetime import datetime
from pathlib import Path
import math
import sys
from PIL import Image, ImageDraw, ImageFont

W, H = 480, 320
FONTS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'nexus26_assets'

def font(size, bold=False):
    try:
        return ImageFont.truetype(str(FONTS / ('Roboto-Bold.ttf' if bold else 'Roboto-Regular.ttf')), size)
    except OSError:
        return ImageFont.load_default()

class SmartWeatherClock:
    def __init__(self):
        self.clock = font(91, True)
        self.temp = font(49, True)
        self.head = font(17, True)
        self.body = font(15)
        self.small = font(12)
        self.mini = font(11, True)
        self.base = self._background()

    def _background(self):
        img = Image.new('RGB', (W,H))
        p = img.load()
        for y in range(H):
            for x in range(W):
                glow = max(0, 1 - math.hypot((x-415)/440, (y-30)/320))
                p[x,y] = (round(7+8*glow), round(13+19*glow), round(26+35*glow))
        return img

    @staticmethod
    def ellipsis(draw, text, f, width):
        text = str(text or '')
        if draw.textlength(text,font=f) <= width: return text
        while text and draw.textlength(text+'…',font=f)>width: text=text[:-1]
        return text+'…'

    def render(self, data):
        data = data or {}
        img = self.base.copy()
        g = ImageDraw.Draw(img)
        white = (246,249,255)
        muted = (143,163,190)
        cyan = (104,221,244)
        now = datetime.now()
        g.rounded_rectangle((16,15,464,216),radius=22,fill=(17,30,48),outline=(37,57,80),width=1)
        g.rounded_rectangle((16,229,464,304),radius=18,fill=(19,33,52),outline=(37,57,80),width=1)
        g.text((33,30),'SMART  /  WEATHER',font=self.mini,fill=cyan)
        city = str(data.get('weather_city') or 'YOUR CITY').upper()
        g.text((447,30),self.ellipsis(g,city,self.mini,172),font=self.mini,fill=muted,anchor='ra')
        g.text((26,51),now.strftime('%H:%M'),font=self.clock,fill=white)
        g.text((35,156),now.strftime('%A, %d %B %Y'),font=self.body,fill=muted)
        g.line((282,66,282,182),fill=(52,74,96),width=2)
        temp = data.get('weather_temp')
        try: temp_text = f'{round(float(temp))}°'
        except (ValueError,TypeError): temp_text = '--°'
        g.text((305,75),temp_text,font=self.temp,fill=cyan)
        condition = str(data.get('weather_condition') or 'Weather unavailable')
        g.text((307,142),self.ellipsis(g,condition,self.body,137),font=self.body,fill=white)
        g.text((307,166),'LOCAL WEATHER',font=self.mini,fill=muted)
        # Minimal sensor cards with honest unavailable placeholders.
        def fmt(key, unit):
            try:
                v=data.get(key)
                return f'{round(float(v))}{unit}' if v is not None else '--'
            except (TypeError,ValueError): return '--'
        for x,label,value,accent in ((33,'CPU',fmt('cpu_temp','°C'),cyan),
                                     (178,'GPU',fmt('gpu_temp','°C'),(180,159,255)),
                                     (326,'RAM',fmt('ram','%'),(123,225,184))):
            g.text((x,242),label,font=self.mini,fill=accent)
            g.text((x,258),value,font=self.head,fill=white)
        g.line((161,242,161,289),fill=(49,68,88))
        g.line((308,242,308,289),fill=(49,68,88))
        return img
