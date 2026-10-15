### v0.28.7 Music timeline and title fix
Improved timeline persistence and smoother marquee. Playback progress requires a duration reported by the Windows media session.

### v0.28.6 Music Visualizer performance fix
The lower-left label no longer overlaps another label. The EQ uses a compact 16-bar display region and cached background to reduce USB bandwidth. Real-world FPS depends on USB transport and firmware; it is not guaranteed.

<div align="center">

# TURMO Control

**A customizable Windows dashboard for 3.5-inch USB smart displays.**

Hardware monitoring · Music visualizer · Original themes · Dual-display support

![Platform](https://img.shields.io/badge/platform-Windows%2010%20%2F%2011-0078D4) ![Python](https://img.shields.io/badge/Python-3.11-3776AB) ![License](https://img.shields.io/badge/license-GPL--3.0-blue)

</div>

## Overview

TURMO Control is a Windows desktop application for compatible **480 × 320 USB serial smart displays**. Use one screen for system statistics and a second for a live music visualizer, or give each screen its own theme.

> **Hardware compatibility:** Developed for TURMO/Turing-style 3.5-inch screens detected as USB VID `1A86`, PID `5722`. Other screen variants and firmware may require changes. This project is community-developed and is not an official TURMO application.

## Features

- **Two independent displays** — choose a theme, serial port, orientation and software brightness for each.
- **Live system telemetry** — CPU, GPU, memory and storage metrics, where exposed by Windows and the included sensor bridge.
- **Music visualizer** — current song, album art, scrolling title, progress bar, elapsed time, clock and weather temperature. Uses Windows media sessions; supported playback metadata depends on the player/browser.
- **Themes** — built-in layouts plus adapted original designs: NEXUS 26, APEX 01, NOVA 01, NEXUS MINIMAL and TRUE VIEW 26.
- **Custom theme editor** — arrange widgets, use image/MP4 backgrounds, import/export `.turmo` themes.
- **Weather** — optional city-based weather via Open-Meteo. No default city; your choice is saved locally.
- **Nine interface languages** — English (default), Hungarian, German, French, Spanish, Italian, Polish, Portuguese and Romanian. Your selection is remembered.
- **System tray** — closing the window with **X** hides it to the notification area; the tray menu provides Open, Stop displays and Exit.
- **Windows login autostart** — opt-in; starts the last saved display configuration after sign-in.
- **Efficient rendering** — partial USB screen updates when possible; real refresh rate depends on device throughput.

## Download / build an EXE with GitHub Actions

1. Open the repository's **Actions** tab.
2. Select **Build TURMO Control Windows EXE**.
3. Choose **Run workflow** → **Run workflow**.
4. Wait for the Windows build to complete.
5. Open the completed run and download **TURMO-Control-Windows-x64** from **Artifacts**.
6. Extract `TURMO-Control.exe` and run it on Windows.

> GitHub Actions builds the executable; end users do not need Python or the .NET SDK. The EXE requests administrator privileges for hardware sensor access. Download only from runs you trust.

## Build locally on Windows

**Build prerequisites:** Windows 10/11 x64, [Python 3.11 x64](https://www.python.org/downloads/), [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0), internet access for dependencies.

Run `build_windows.bat` from the project folder. On success, find `dist\TURMO-Control.exe`. The script compiles a self-contained .NET sensor helper, installs Python dependencies and bundles the app using PyInstaller. Python 3.11 is recommended because of the Windows Runtime (WinRT) packages.

## Getting started

1. Connect one or two supported 3.5-inch USB displays. Close other applications using the same COM ports (for example `UsbMonitor.exe`).
2. Launch TURMO Control and click **Detect screens**.
3. Open **Settings**, choose a theme and COM port for each screen, and optionally enter a weather city.
4. Click **Start displays** in the **Dashboard**.
5. Optionally enable **Start with Windows** in Settings. On future Windows sign-ins, the program attempts to restore and start the saved displays automatically.
6. Clicking **X** minimizes to the system tray; use **Exit TURMO Control** in the tray menu to fully quit.

If you enabled autostart in an older version, turn it **off and on again** to update the scheduled task with the new startup argument. Keep the EXE in its installed location after enabling autostart.

## Configuration and privacy

Settings are stored locally in `%APPDATA%\TURMO-Control\settings.json`. There is **no hard-coded default weather location**. A city is sent to the Open-Meteo service only when weather is enabled/configured; the weather provider may receive your network IP address. Music metadata is read from Windows media sessions. The app is **not an anonymity tool**.

Autostart creates a Windows Task Scheduler logon task named `TURMO Control`; disable the checkbox to remove it. Administrator permission may be required.

## Troubleshooting

| Symptom | What to try |
| --- | --- |
| Display not found | Check USB connection, COM port and device VID/PID; close `UsbMonitor.exe`. |
| Music says *Nothing playing* | Check that your browser/player exposes media metadata to Windows. |
| No album art or duration | Some Windows media sessions do not provide thumbnail/timeline data. |
| CPU temperature unavailable | Ensure the sensor bridge is bundled and administrator permission is granted; inspect Diagnostics. |
| Autostart not working | Turn autostart off/on to recreate the task; keep the EXE at the same path. |
| EXE build fails | Use Python **3.11**, .NET **8 SDK**, and inspect the first failing step in the build log. |

## Credits and licensing

This repository includes/adapts third-party themes and artwork. **GPL-3.0** licensing and original attributions must be retained when redistributing modified versions. See [LICENSE](LICENSE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), `NEXUS26-ORIGINAL-LICENSE.txt`, and `MUSIC-VISUALIZER-GPL-LICENSE.txt`.

Music visualizer inspired by [spel987/turing-3.5-screen-music-visualizer](https://github.com/spel987/turing-3.5-screen-music-visualizer) and the [mathoudebine/turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python) ecosystem. Original themes were adapted from user-provided source materials; attribution details are listed in the notices file.

## Project status

**v0.28.3** — community project under active development. Features have been exercised on compatible physical screens, but Windows builds, firmware compatibility, scheduled-task behavior and individual media players may vary. Issues and pull requests are welcome.


### In-app updates (v0.28.3)
Open **Settings → Check for updates**. TURMO checks the latest published GitHub Release of `Reggeri/TURMO-Multiscreen-Control` and, with your confirmation, downloads its attached `TURMO-Control.exe` (or ZIP containing that EXE), replaces the installed EXE and restarts. This requires the packaged Windows build and an accessible GitHub connection. Publish the newly built EXE as a Release asset, not only as an Actions artifact. Keep the installed EXE in a writable location and avoid renaming its release asset to an unrelated name.


### New in v0.28.4
Select **AUTO / SMART MODE** in the theme dropdown to switch based on activity. Actively playing Windows media takes priority, followed by a recognized foreground game, then idle clock after five minutes, otherwise System Neon. Game detection covers a conservative list of common game executable names; unknown games fall back to System Neon. Select **MUSIC VISUALIZER 2.0** for the separate updated media theme. Its animated bars are decorative and do not represent measured sound frequencies.
