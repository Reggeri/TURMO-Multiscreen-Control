"""Smooth full-screen audio EQ with cached blurred album art and track label.

Static song header/background are cached: only the EQ bars change per audio frame,
allowing the driver's existing 24-column sparse USB updates to remain effective.
"""
import math
import time
from io import BytesIO
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from audio_spectrum import spectrum

WIDTH, HEIGHT = 480, 320

class FullScreenEQ:
    def __init__(self):
        self.levels = [0.0] * 24
        self.peaks = [0.0] * 24
        self.last = time.monotonic()
        self.palette = [self._hsv(i / 24) for i in range(24)]
        self._identity = None
        self._background = None
        assets = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'music_visualizer_assets'
        self._unknown = Image.open(assets / 'unknown.jpg').convert('RGB')
        font = assets / 'Roboto-Medium.ttf'
        self._title_font = ImageFont.truetype(str(font), 22)
        self._artist_font = ImageFont.truetype(str(font), 15)

    @staticmethod
    def _hsv(h):
        import colorsys
        r, g, b = colorsys.hsv_to_rgb((0.77 - h * 0.77) % 1, 0.9, 1.0)
        return (int(r * 255), int(g * 255), int(b * 255))

    @staticmethod
    def _fit_text(draw, text, font, width):
        text = str(text or '')
        if draw.textlength(text, font=font) <= width:
            return text
        while text and draw.textlength(text + '…', font=font) > width:
            text = text[:-1]
        return text.rstrip() + '…' if text else ''

    def _make_background(self, data):
        art_bytes = data.get('music_art')
        try:
            art = Image.open(BytesIO(art_bytes)).convert('RGB') if art_bytes else self._unknown.copy()
        except (OSError, ValueError, TypeError):
            art = self._unknown.copy()
        bg = ImageOps.fit(art, (WIDTH, HEIGHT), method=Image.Resampling.BILINEAR)
        bg = bg.filter(ImageFilter.GaussianBlur(23))
        bg = Image.blend(bg, Image.new('RGB', (WIDTH, HEIGHT), (5, 8, 16)), 0.58)
        # Darker top header makes the text readable over any cover.
        overlay = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        d.rounded_rectangle((12, 12, 468, 112), radius=13, fill=(4, 7, 13, 164))
        bg = Image.alpha_composite(bg.convert('RGBA'), overlay)
        cover = ImageOps.fit(art, (82, 82), method=Image.Resampling.LANCZOS)
        mask = Image.new('L', (82, 82), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, 81, 81), radius=10, fill=255)
        bg.paste(cover, (22, 21), mask)
        d = ImageDraw.Draw(bg)
        title = data.get('music_title') or 'Nothing playing'
        artist = data.get('music_artist') or 'Start music on your PC'
        d.text((118, 35), self._fit_text(d, title, self._title_font, 333), font=self._title_font, fill=(248, 249, 255))
        d.text((119, 72), self._fit_text(d, artist, self._artist_font, 330), font=self._artist_font, fill=(209, 220, 234))
        return bg.convert('RGB')

    def render(self, data=None):
        data = data or {}
        # Rebuild the expensive blur only on song/cover changes, never each EQ tick.
        identity = (data.get('music_art'), data.get('music_title'), data.get('music_artist'))
        if self._background is None or identity != self._identity:
            self._background = self._make_background(data)
            self._identity = identity
        bands, _ = spectrum.get()
        now = time.monotonic()
        dt = min(0.15, max(0.001, now - self.last))
        self.last = now
        image = self._background.copy()
        draw = ImageDraw.Draw(image)
        for i in range(24):
            target = max(0.0, min(1.0, float(bands[i])))
            speed = 23.0 if target > self.levels[i] else 8.0
            self.levels[i] += (target - self.levels[i]) * (1.0 - math.exp(-speed * dt))
            self.peaks[i] = max(self.levels[i], self.peaks[i] - dt * 0.65)
            x0 = 5 + i * 20
            x1 = x0 + 14
            # Bars begin below the album/title header, preserving readability.
            h = max(3, round(self.levels[i] * 195))
            y0 = HEIGHT - 5 - h
            draw.rounded_rectangle((x0, y0, x1, HEIGHT - 5), radius=3, fill=self.palette[i])
            py = HEIGHT - 5 - round(self.peaks[i] * 195)
            draw.line((x0, py, x1, py), fill=(225, 233, 250), width=2)
        return image
