"""Music Visualizer 2.0: live audio spectrum with minimal USB updates.

The album art, text, timeline and marquee are refreshed at a modest rate,
while the small equalizer region is redrawn for every available USB frame.
This avoids transferring the whole title/timeline area on every audio tick.
"""
import time
from PIL import ImageDraw
from music_visualizer_theme import MusicVisualizer
from audio_spectrum import spectrum

class MusicVisualizerV2(MusicVisualizer):
    def __init__(self):
        super().__init__()
        self._base = None
        self._base_at = 0.0
        self._last_identity = None
        self._last_progress = None

    def render(self, data):
        now = time.monotonic()
        identity = (data.get('music_title'), data.get('music_artist'),
                    data.get('music_art'), data.get('music_playing'),
                    data.get('weather_temp'), data.get('weather_city'),
                    data.get('music_duration'))
        # Refresh title and timeline independently of the fast EQ frames.
        # 650ms cap protects the EQ from expensive large-area USB updates;
        # the small EQ area remains independent and updates on every frame.
        if self._base is None or identity != self._last_identity or now - self._base_at >= 0.65:
            self._base = super().render(data)
            self._base_at = now
            self._last_identity = identity
        image = self._base.copy()
        draw = ImageDraw.Draw(image)
        bands, _ = spectrum.get()
        # Base theme already owns the lower-left 'MUSIC VISUALIZER' label.
        # EQ is restricted to the far right of the bottom band (y 292..313).
        # This keeps the label unobstructed and changes a tiny USB rectangle.
        for i in range(16):
            level = max(bands[i], bands[min(23, i+8)] * 0.65)
            x = 374 + i * 4
            h = max(2, round(max(0.0, min(1.0, level)) * 18))
            draw.rectangle((x, 312-h, x+2, 312),
                                   fill=(75 + round(level*85), 175 + round(level*60), 245))
        return image
