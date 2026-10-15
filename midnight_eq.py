"""Compact, low-bandwidth monochrome audio visualizer with Windows media title."""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont
from audio_spectrum import spectrum

class MidnightEQ:
    def __init__(self):
        assets=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))/'music_visualizer_assets'
        try:
            self.title_font=ImageFont.truetype(str(assets/'Roboto-Black.ttf'),25)
            self.artist_font=ImageFont.truetype(str(assets/'Roboto-Medium.ttf'),17)
            self.label_font=ImageFont.truetype(str(assets/'Roboto-Medium.ttf'),13)
        except OSError:
            self.title_font=self.artist_font=self.label_font=ImageFont.load_default()
        self.base=None
        self.identity=None
        self.smoothed=[0.0]*20
        self.peaks=[0.0]*20

    def _fit(self, draw, text, font, limit):
        text=str(text or '')
        if draw.textlength(text,font=font)<=limit:return text
        while text and draw.textlength(text+'…',font=font)>limit:text=text[:-1]
        return text.rstrip()+'…'

    def render(self,data):
        title=data.get('music_title') or 'No music playing'
        artist=data.get('music_artist') or 'Play audio on your computer'
        playing=bool(data.get('music_playing'))
        identity=(title,artist,playing)
        if self.base is None or identity!=self.identity:
            self.identity=identity
            self.base=Image.new('RGB',(480,320),(7,11,19))
            d=ImageDraw.Draw(self.base)
            d.rounded_rectangle((22,22,458,296),radius=18,outline=(29,42,56),width=2)
            d.text((39,35),'MIDNIGHT / AUDIO',font=self.label_font,fill=(105,152,169))
            d.text((39,65),self._fit(d,title,self.title_font,402),font=self.title_font,fill=(239,246,250))
            d.text((40,102),self._fit(d,artist,self.artist_font,400),font=self.artist_font,fill=(137,160,177))
            d.line((40,266,440,266),fill=(31,49,62),width=1)
            d.text((40,276),'LIVE SPECTRUM' if playing else 'AUDIO STANDBY',font=self.label_font,fill=(96,136,151))
            d.ellipse((421,278,428,285),fill=(111,208,221) if playing else (66,79,91))
        frame=self.base.copy()
        d=ImageDraw.Draw(frame)
        bands,_=spectrum.get()
        # 20 bars in a moderate-height area. Only this rectangle changes between frames.
        for i in range(20):
            # Combine neighbouring frequency bins: no bar depends on a single
            # potentially silent/dead FFT bin (notably the third column).
            start=int(i*len(bands)/20)
            end=max(start+1,int((i+1)*len(bands)/20))
            neighbours=[max(0.0,float(v)) for v in bands[max(0,start-1):min(len(bands),end+1)]]
            level=max(0.0,min(1.0,max(neighbours,default=0.0)))
            self.smoothed[i]=max(level, self.smoothed[i]*0.70+level*0.30) if level>self.smoothed[i] else self.smoothed[i]*0.72+level*0.28
            self.peaks[i]=max(self.smoothed[i],self.peaks[i]-0.035)
            x=44+i*20
            h=max(3,round(self.smoothed[i]*105))
            d.rounded_rectangle((x,251-h,x+11,251),radius=3,fill=(112,194,208))
            peak_y=251-round(self.peaks[i]*105)
            d.line((x,peak_y,x+11,peak_y),fill=(230,242,245),width=2)
        return frame
