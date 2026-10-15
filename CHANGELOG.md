## v0.28.31
- MIDNIGHT EQ: per-bar dirty USB updates instead of a large shared changed rectangle.
- No changes to Full Screen Color EQ or video player.

## v0.28.30
- New MIDNIGHT EQ theme with track title and artist, restrained audio bars, and partial-frame updates.
- Existing themes unchanged.

## v0.28.17 – Theme Editor image fitting + phone photo upload
- Cover, contain, stretch, zoom and drag-to-position for image backgrounds.
- PIN-protected phone JPEG/PNG upload (8 MB maximum), one-click display assignment.
- Image preprocessing only on upload or theme edit; existing EQ renderer untouched.

## v0.28.15
- Opt-in local phone remote web interface with PIN pairing and QR code.
- Independent display theme/brightness controls; start and stop.
- Previous EQ optimizations retained.

## v0.28.14
- Full Screen Color EQ: cached blurred album-art background, cover thumbnail, title and artist.
- No playback progress bar.
- Preserves the fast 24-column sparse USB updates from v0.28.13.

## v0.28.12
- Vectorized RGB565 conversion using NumPy to eliminate slow Python pixel loops.
- Full Screen EQ: optional 24-stripe dirty-rectangle USB updates when they save at least 28% of pixel traffic.
- Kept audio FFT, colors, and all other themes unchanged.
- USB FPS is hardware-dependent; test on Windows.

## v0.28.11
- New independent FULL SCREEN COLOR EQ theme: 24 rainbow bands fill the 480x320 display, no text or artwork.
- Live Windows system-output audio FFT; responsive attack and smooth decay, peak markers.
- 25 ms target loop; actual USB FPS depends on device and frame changes.

## v0.28.10
- Restored the proven 650 ms title/timeline refresh interval from v0.28.8 to prioritize the real-time audio EQ.
- This is a stability rollback, not a complete solution for simultaneous smooth text and EQ; that requires independent partial-region scheduling.

## v0.28.9
- Music Visualizer 2.0: marquee/timeline redraw interval tuned from 650 ms to 320 ms for smoother scrolling while keeping compact EQ updates.
- Marquee speed tuned to 17 px/s; actual FPS remains dependent on USB throughput.

## v0.28.8
- Reduced full-width music marquee and timeline redraws to approximately 1.5 per second so compact EQ updates can use the USB bandwidth.
- EQ retains a separate ~40 Hz target loop, bounded by real USB transfer speed.

## v0.28.7
- Music Visualizer 2.0: more frequent text/timeline refresh (150 ms vs 800 ms), slower smoother title marquee.
- Windows media session polling every second; retain valid timeline if same track temporarily stops reporting it.
- The progress bar only appears when Windows provides a real duration.

## v0.28.6
- Fix overlapping Music Visualizer 2.0 footer text.
- Reduce EQ USB transfer rectangle to improve actual display FPS.
- Cache expensive album-art/text render; keep live FFT updates separate.
- NOTE: USB actual FPS remains limited by the screen firmware and serial link.

## v0.28.5
- Redesigned Smart Weather Clock: refined typography, gradient, cleaner weather and CPU/GPU/RAM cards.
- Music Visualizer 2.0: real system audio FFT from Windows WASAPI loopback (no microphone or uploading audio).
- Fast 25 ms target frame pacing (~40 FPS target), limited by USB transfer speed and screen hardware.
- Graceful silent spectrum when system loopback is unavailable.

## v0.28.4
- AUTO / SMART MODE as an independent theme: active music → Music Visualizer 2.0; recognized foreground game → GPU Neon; 5 minutes of inactivity → Smart Weather Clock; otherwise System Neon.
- Separate MUSIC VISUALIZER 2.0 theme with animated decorative bars. Bars are NOT actual audio frequency measurements.
- Automatic mode does not transmit or store application activity.
- Retains existing update button.

# Changelog

## v0.28.3
- Added manual GitHub Releases update checking and confirmed in-place Windows EXE replacement with restart.
- Uses background downloads and keeps user settings in AppData.

## v0.28.2
- Fixed CPU model shown on other computers: detect the local CPU at runtime instead of displaying a hard-coded Ryzen 7 7800X3D.
- Removed the hard-coded DDR5 label from the System theme.

## v0.28.1
- Fixed the `pystray` requirement format for Windows builds.

## v0.28
- Added Windows notification-area behavior when closing the main window.
- Added opt-in Windows login startup of the saved screen configuration.

## v0.27
- Reorganized the GUI into Dashboard, Settings and Diagnostics.

## v0.26.2
- English default language; persist user-selected language.

## v0.26.1
- Remember an explicitly selected weather city; no preconfigured default.

## v0.25
- Added nine interface languages.

## v0.24.5
- Improved music title scrolling smoothness and rendering efficiency.

## v0.24.3–v0.24.4
- Added music artwork, progress indicator and elapsed time handling.

## v0.22
- Added original theme adaptations.

## v0.28.16 – Phone Remote live preview
- Authenticated JPEG snapshots of the actual display frames for both screens.
- No extra screen rendering: preview shares the frame already sent to USB.
- JPEG generated only on demand, at most once per 1.5 seconds per screen; no background encoder.
- Pauses requests when the phone tab is hidden; 58% JPEG quality.
- Existing EQ rendering and USB transfer logic unchanged.

## v0.28.18 – Video player
- Dedicated Video tab for both displays; fit mode, decode resolution, target FPS and local video selection.
- Streaming FFmpeg decoder keeps only the latest frame, avoids backlog and supports 25/30 FPS target.
- Reduced-resolution nearest-neighbour preprocessing to reduce scaling cost; native RGB565 USB output unchanged.
- Diagnostics continue to report real USB transfer FPS and throughput; 25 FPS depends on device throughput.


## v0.28.19 – Video-only fast serial experiment
- VIDEO PLAYER uses dedicated 2,000,000 baud serial setting (TURMO_VIDEO_BAUD override).
- VIDEO PLAYER sends each RGB565 rectangle as one serial write instead of 64 KiB blocks.
- All other themes keep their previous serial settings and send logic.
- This is an experimental transport optimization: real FPS depends on firmware and hardware; 25 FPS is not guaranteed.

## v0.28.20
- Video startup compatibility fix: default 115200 baud and proven chunked USB write path restored for VIDEO PLAYER only.

## v0.28.21
- VIDEO PLAYER only: prioritized 32x16 tiled partial updates with 12 KiB transfer budget; no changes to normal themes or EQ.

## v0.28.22
- Video-only: replace 32x16 tile priority mosaic with sequential full-width scanline regions.
- Preserve working baud, packet protocol and normal/EQ transport.

## v0.28.23
- Video-only coherent centered 320x240 window; no tile or scanline assembly.

## v0.28.24
- Experimental VIDEO PLAYER changed-row RGB565 transfers; no changes to other themes.

## v0.28.25
- Video-only compact 96x72 atomic RGB565 frames to reduce USB bandwidth and remove visible tiles/scanlines.

## v0.28.26
- Selectable video window size per display (96x72 / 128x96 / 160x120 / 192x144).
- No changes to non-video transport.

## v0.28.32
- MIDNIGHT EQ: szomszédos spektrumértékek összesítése, időszakos teljes kijelző-szinkronizálás.

## v0.28.33
- Studio UI: refreshed dark palette, typography, navigation, cards and controls. Display functionality unchanged.

## v0.28.34
- Version synchronization and safe updater process shutdown, desktop shortcut, post-update relaunch.
