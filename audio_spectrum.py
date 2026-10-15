"""Opt-in, local-only Windows WASAPI loopback FFT. No audio recording or upload."""
import threading
import time

class AudioSpectrum:
    def __init__(self):
        self.lock = threading.Lock()
        self.bands = [0.0] * 24
        self.status = 'Waiting for audio'
        self._started = False
        self._stop = threading.Event()

    def start(self):
        if not self._started:
            self._started = True
            threading.Thread(target=self._worker, daemon=True, name='TURMO audio spectrum').start()

    def get(self):
        self.start()
        with self.lock:
            return list(self.bands), self.status

    def _worker(self):
        try:
            import numpy as np
            import soundcard as sc
        except ImportError:
            with self.lock: self.status = 'Audio FFT dependencies missing'
            return
        # Sample Windows default output, never the microphone.
        while not self._stop.is_set():
            try:
                speaker = sc.default_speaker()
                if speaker is None: raise RuntimeError('No default playback device')
                mic = sc.get_microphone(id=str(speaker.id), include_loopback=True)
                if mic is None: raise RuntimeError('WASAPI loopback unavailable')
                with mic.recorder(samplerate=24000, blocksize=1024) as rec:
                    with self.lock: self.status = 'Live system audio'
                    while not self._stop.is_set():
                        samples = rec.record(numframes=1024)
                        mono = np.asarray(samples, dtype=np.float32)
                        if mono.ndim == 2: mono = mono.mean(axis=1)
                        if mono.size < 128: continue
                        mono = mono - mono.mean()
                        windowed = mono * np.hanning(mono.size)
                        fft = np.abs(np.fft.rfft(windowed)) / max(1, mono.size)
                        hz = np.fft.rfftfreq(mono.size, 1/24000)
                        edges = np.geomspace(45, 11000, 25)
                        rms = float(np.sqrt(np.mean(mono**2)))
                        raw = []
                        for lo, hi in zip(edges[:-1], edges[1:]):
                            chunk = fft[(hz >= lo) & (hz < hi)]
                            peak = float(np.max(chunk)) if chunk.size else 0
                            raw.append(min(1.0, (peak * 75)**0.55) if rms > 0.0002 else 0.0)
                        with self.lock:
                            self.bands = [max(v * 0.72, n * 0.38 + v * 0.62) if n < v else n * 0.65 + v * 0.35
                                          for v, n in zip(self.bands, raw)]
            except Exception as exc:
                with self.lock:
                    self.status = 'Audio unavailable: ' + str(exc)[:75]
                    self.bands = [0.0] * 24
                self._stop.wait(3)

spectrum = AudioSpectrum()
