"""Smart Weather Clock: original 480x320 TURMO theme, TRUE VIEW inspired."""
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import math,sys

W,H=480,320
ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'original_themes'/'TRUE_VIEW_26'/'fonts'

def font(size,bold=False):
    for file in (('Roboto-Bold.ttf' if bold else 'Roboto-Regular.ttf'),'Roboto-Bold.ttf'):
        try:return ImageFont.truetype(str(ROOT/file),size)
        except OSError:pass
    return ImageFont.load_default()

class SmartWeatherClock:
    def __init__(self):
        self.big=font(78,True);self.medium=font(28,True);self.body=font(16,True)
        self.small=font(13);self.tiny=font(11);self.micro=font(10,True)
    def render(self,data):
        d=data or {}
        img=Image.new('RGB',(W,H),(9,18,34));g=ImageDraw.Draw(img)
        # Subtle sky gradient
        for y in range(H):
            t=y/H
            g.line((0,y,W,y),fill=(int(10+7*t),int(23+9*t),int(43+12*t)))
        CYAN=(115,224,249);WHITE=(235,247,255);MUTED=(142,170,194);LINE=(54,79,104)
        now=datetime.now()
        g.text((19,12),'WEATHER  /  SMART CLOCK',font=self.micro,fill=CYAN)
        city=str(d.get('weather_city') or '').upper()[:23]
        g.text((460,12),city,font=self.micro,fill=MUTED,anchor='ra')
        g.line((18,33,462,33),fill=LINE,width=1)
        g.text((18,41),now.strftime('%H:%M'),font=self.big,fill=WHITE,stroke_width=0)
        g.text((23,128),now.strftime('%A  •  %Y.%m.%d'),font=self.small,fill=MUTED)
        condition=str(d.get('weather_condition') or 'Weather unavailable')
        c=condition.lower()
        icon='☀' if 'clear' in c or 'sun' in c else ('☂' if 'rain' in c or 'shower' in c else ('❄' if 'snow' in c else '☁'))
        temp=d.get('weather_temp')
        try:temperature=f'{float(temp):.0f}°' if temp is not None else '--°'
        except (ValueError,TypeError):temperature='--°'
        g.text((460,46),temperature,font=self.medium,fill=CYAN,anchor='ra')
        g.text((458,86),condition[:23],font=self.small,fill=WHITE,anchor='ra')
        feel=d.get('weather_feels');humidity=d.get('weather_humidity')
        details=[]
        if feel is not None:
            try:details.append(f'Feels {float(feel):.0f}°')
            except (ValueError,TypeError):pass
        if humidity is not None:
            try:details.append(f'Humidity {float(humidity):.0f}%')
            except (ValueError,TypeError):pass
        g.text((458,109),'  ·  '.join(details),font=self.tiny,fill=MUTED,anchor='ra')
        # Compact sensor ribbon
        g.rounded_rectangle((16,160,464,224),radius=11,fill=(20,37,57),outline=LINE,width=1)
        def fmt(k,unit='%',dec=0):
            v=d.get(k)
            try:return f'{float(v):.{dec}f}{unit}' if v is not None else '--'
            except (TypeError,ValueError):return '--'
        blocks=[('CPU',fmt('cpu'),fmt('cpu_temp','°C')),('GPU',fmt('gpu_load'),fmt('gpu_temp','°C'))]
        for i,(label,load,t) in enumerate(blocks):
            x=32+i*222
            g.text((x,172),label,font=self.micro,fill=CYAN)
            g.text((x,188),load,font=self.body,fill=WHITE)
            g.text((x+112,190),t,font=self.small,fill=MUTED)
            if i==0:g.line((240,170,240,213),fill=LINE,width=1)
        # Music strip, with clipping/truncation to preserve 480x320 geometry
        g.rounded_rectangle((16,235,464,305),radius=12,fill=(24,42,65),outline=(57,91,119),width=1)
        g.text((30,245),'♫  NOW PLAYING',font=self.micro,fill=CYAN)
        title=str(d.get('music_title') or '')
        artist=str(d.get('music_artist') or '')
        if not title:
            title='No active media'
            artist='Play music in a Windows media app'
        def fit(s,f,maxw):
            while s and g.textlength(s,font=f)>maxw:s=s[:-1]
            return s if len(s)==0 or s==str(s) and g.textlength(s,font=f)<=maxw else s
        def ellipsis(s,f,maxw):
            if g.textlength(s,font=f)<=maxw:return s
            while s and g.textlength(s+'…',font=f)>maxw:s=s[:-1]
            return s+'…'
        g.text((30,263),ellipsis(title,self.body,414),font=self.body,fill=WHITE)
        g.text((30,285),ellipsis(artist,self.tiny,414),font=self.tiny,fill=MUTED)
        return img
