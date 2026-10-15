"""Album art driven theme adapted from the user-supplied GPL-3 music visualizer."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
import sys
import time
from PIL import Image,ImageDraw,ImageFont,ImageFilter,ImageOps

class MusicVisualizer:
    def __init__(self):
        assets=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'music_visualizer_assets'
        self.unknown=Image.open(assets/'unknown.jpg').convert('RGB')
        self.bold=ImageFont.truetype(str(assets/'Roboto-Black.ttf'),27)
        self.medium=ImageFont.truetype(str(assets/'Roboto-Medium.ttf'),21)
        self.small=ImageFont.truetype(str(assets/'Roboto-Medium.ttf'),16)
        self.tiny=ImageFont.truetype(str(assets/'Roboto-Medium.ttf'),13)
        self.last_art=None
        self.cached_art=None
        self.cached_bg=None
        self._title_cache_key=None
        self._title_strip=None
        self._marquee_started=time.monotonic()

    def _text(self,d,xy,text,font,color,max_width):
        text=str(text or '')
        while text and d.textlength(text,font=font)>max_width:
            text=text[:-1]
        if text and text!=str(text or ''):text=text.rstrip()+'…'
        d.text(xy,text,font=font,fill=color)

    def render(self,data):
        art_bytes=data.get('music_art')
        if art_bytes!=self.last_art or self.cached_bg is None:
            self.last_art=art_bytes
            try:art=Image.open(BytesIO(art_bytes)).convert('RGB') if art_bytes else self.unknown.copy()
            except Exception:art=self.unknown.copy()
            self.cached_art=ImageOps.fit(art,(175,175),method=Image.Resampling.LANCZOS)
            background=ImageOps.fit(art,(480,320),method=Image.Resampling.LANCZOS)
            background=background.filter(ImageFilter.GaussianBlur(42)).convert('RGB')
            background=Image.blend(background,Image.new('RGB',(480,320),'#060a11'),0.47)
            self.cached_bg=background
        image=self.cached_bg.copy()
        art=self.cached_art
        colors=art.resize((30,30)).getcolors(900) or []
        color=max(colors,key=lambda x:x[0])[1] if colors else (120,160,210)
        accent=tuple(min(255,int(c*.65+115)) for c in color)
        # Keep white text legible regardless of album-cover dominant color.
        text=(247,249,255)
        d=ImageDraw.Draw(image)
        d.rounded_rectangle((26,65,226,265),radius=20,fill=(14,18,28))
        mask=Image.new('L',(175,175),0)
        ImageDraw.Draw(mask).rounded_rectangle((0,0,174,174),radius=14,fill=255)
        image.paste(art,(39,77),mask)
        d=ImageDraw.Draw(image)
        playing=bool(data.get('music_playing'))
        title=data.get('music_title') or 'Nothing playing'
        artist=data.get('music_artist') or 'Start music on your PC'
        d.text((239,82),'NOW PLAYING' if playing else 'MEDIA',font=self.tiny,fill=accent)
        # Smooth looping marquee inside the 213px right-side viewport.
        # Render onto an RGBA strip, crop, and composite: no text leaks
        # beyond the right edge even for extremely long YouTube titles.
        title=str(title)
        viewport_w=212
        full_w=int(d.textlength(title,font=self.bold))
        if full_w<=viewport_w:
            d.text((239,112),title,font=self.bold,fill=text)
        else:
            gap=55
            cache_key=(title,full_w)
            if cache_key!=self._title_cache_key:
                self._title_cache_key=cache_key
                self._marquee_started=time.monotonic()
                strip=Image.new('RGBA',(full_w*2+gap+8,43),(0,0,0,0))
                strip_draw=ImageDraw.Draw(strip)
                strip_draw.text((0,0),title,font=self.bold,fill=(*text,255))
                strip_draw.text((full_w+gap,0),title,font=self.bold,fill=(*text,255))
                self._title_strip=strip
            # ~20 px/sec at ~8 FPS = 2-3 px per frame. Avoid
            # rebuilding the text strip on each screen refresh.
            speed=17.0
            offset=int((time.monotonic()-self._marquee_started)*speed)%(full_w+gap)
            segment=self._title_strip.crop((offset,0,offset+viewport_w,43))
            image.paste(segment,(239,108),segment)
            d=ImageDraw.Draw(image)
        self._text(d,(240,159),artist,self.medium,(218,228,243),218)
        if not playing and data.get('music_title'):
            d.text((241,194),'PAUSED',font=self.tiny,fill=accent)
        # Right-hand playback timeline and mm:ss / mm:ss counter.
        # When the media source does not publish a duration, do not fake one.
        position=data.get('music_position')
        duration=data.get('music_duration')
        if position is not None and duration is not None and duration>0:
            position=max(0,min(float(position),float(duration)))
            duration=float(duration)
            x1,x2,y=241,451,221
            d.rounded_rectangle((x1,y,x2,y+5),radius=2,fill=(75,86,106))
            filled=x1+round((x2-x1)*position/duration)
            if filled>x1:
                d.rounded_rectangle((x1,y,filled,y+5),radius=2,fill=accent)
            d.ellipse((filled-3,y-2,filled+3,y+7),fill=text)
            def stamp(seconds):
                sec=int(seconds)
                return f'{sec//60}:{sec%60:02d}'
            d.text((x1,235),stamp(position),font=self.tiny,fill=text)
            end=stamp(duration)
            d.text((x2-d.textlength(end,font=self.tiny),235),end,font=self.tiny,fill=text)
        elif data.get('music_title'):
            d.text((241,231),'LIVE  •  TIME UNAVAILABLE',font=self.tiny,fill=(193,201,215))
        # clock + current weather occupy the same clean top and bottom bands
        d.text((28,15),datetime.now().strftime('%H:%M'),font=self.bold,fill=text)
        city=str(data.get('weather_city') or 'WEATHER').upper()
        weather=data.get('weather_temp')
        temperature=f"{round(float(weather))}°C" if weather is not None else '--°C'
        label=f'{city}  {temperature}'
        width=d.textlength(label,font=self.small)
        d.text((465-width,21),label,font=self.small,fill=text)
        d.line((25,57,455,57),fill=accent,width=2)
        d.line((25,276,455,276),fill=accent,width=2)
        d.text((28,288),'TURMO  •  MUSIC VISUALIZER',font=self.tiny,fill=(221,229,239))
        return image
