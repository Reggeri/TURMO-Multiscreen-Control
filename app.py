"""TURMO Control v0.9: two independent displays and one shared live telemetry poller."""
import os
import queue
import sys
import threading
import time
import traceback
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from serial.tools import list_ports
from pathlib import Path
from updater import VERSION, check_and_update
from remote_control import RemoteServer, PreviewCache, lan_ip, PORT
import json
from PIL import Image, ImageDraw, ImageTk, ImageEnhance
from editor import default_layout, render as render_custom, load_background
from theme_editor_ui import ThemeEditor
from media import VideoSource
from driver import Display
from sensors import Reader
from weather import WeatherService
from nexus26_native import Nexus26
from original_adapter import OriginalTheme, NAMES as ORIGINAL_NAMES
from smart_weather_theme import SmartWeatherClock
from music_visualizer_theme import MusicVisualizer
from music_visualizer_v2 import MusicVisualizerV2
from full_screen_eq import FullScreenEQ
from midnight_eq import MidnightEQ
from auto_theme import select_theme
from now_playing import NowPlaying
from themes import system, gpu, test_pattern, neon_system, neon_gpu, minimal_system, minimal_gpu

RENDER = {'System': system, 'GPU': gpu, 'System Neon': neon_system, 'GPU Neon': neon_gpu, 'System Minimal': minimal_system, 'GPU Minimal': minimal_gpu, 'Test': lambda _: test_pattern(), 'Custom': None, 'NEXUS 26 (Original)': None, 'SMART WEATHER CLOCK': None, 'MUSIC VISUALIZER': None, 'MUSIC VISUALIZER 2.0': None, 'FULL SCREEN COLOR EQ': None, 'MIDNIGHT EQ': None, 'AUTO / SMART MODE': None, 'VIDEO PLAYER': None, **{name:None for name in ORIGINAL_NAMES}}
USB_VID, USB_PID = 0x1A86, 0x5722
SETTINGS = Path(os.environ.get('APPDATA') or Path.home()) / 'TURMO-Control' / 'settings.json'

def discover_screens():
    """Only show verified TURMO USB serial devices; never guess COM numbers."""
    found = []
    for p in list_ports.comports():
        if p.vid == USB_VID and p.pid == USB_PID:
            found.append(p)
    return sorted(found, key=lambda p: ((p.serial_number or '').lower(),
                                       (p.location or '').lower(), p.device.lower()))

def load_settings():
    try:
        data = json.loads(SETTINGS.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}

def save_settings(data):
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        temp = SETTINGS.with_suffix('.tmp')
        temp.write_text(json.dumps(data, indent=2), encoding='utf-8')
        temp.replace(SETTINGS)
    except OSError:
        pass


# Elevated sensor access is required by the bundled executable. A Windows
# Task Scheduler logon task avoids the UAC restrictions of HKCU Run entries.
STARTUP_TASK = 'TURMO Control'

def startup_is_enabled():
    if sys.platform != 'win32':
        return False
    try:
        result=subprocess.run(['schtasks','/Query','/TN',STARTUP_TASK],
                              capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=10)
        return result.returncode == 0
    except (OSError,subprocess.TimeoutExpired):
        return False

def set_startup(enabled):
    if sys.platform != 'win32':
        raise RuntimeError('Windows only')
    if enabled:
        if not getattr(sys,'frozen',False):
            raise RuntimeError('Build and run TURMO-Control.exe first to enable autostart.')
        exe=str(Path(sys.executable).resolve())
        # Quote path as part of /TR argument for spaces in installation folder.
        cmd=['schtasks','/Create','/F','/SC','ONLOGON','/RL','HIGHEST',
             '/TN',STARTUP_TASK,'/TR',f'\\"{exe}\\" --autostart']
    else:
        cmd=['schtasks','/Delete','/F','/TN',STARTUP_TASK]
        if not startup_is_enabled():return
    result=subprocess.run(cmd,capture_output=True,text=True,errors='replace',
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=20)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip() or f'schtasks error {result.returncode}')

class Telemetry(threading.Thread):
    def __init__(self, events, stop):
        super().__init__(daemon=True)
        self.events, self.stop = events, stop
        self.latest = None
        self.lock = threading.Lock()
    def get(self):
        with self.lock:
            return self.latest.copy() if self.latest is not None else None
    def run(self):
        try:
            import pythoncom
            pythoncom.CoInitialize()
            try:
                reader = Reader()
                previous = None
                while not self.stop.is_set():
                    values = reader.sample()
                    with self.lock:
                        self.latest = values
                    if reader.last_error != previous:
                        self.events.put(('Sensors', reader.last_error or ('Connected to ' + str(reader.namespace))))
                        previous = reader.last_error
                    self.stop.wait(2.0)
            finally:
                reader.bridge.close()
                pythoncom.CoUninitialize()
        except Exception as exc:
            self.events.put(('Sensors', 'ERROR: ' + str(exc)))

class ScreenThread(threading.Thread):
    def __init__(self, port, theme, transport, telemetry, events, stop, config=None, brightness=None, preview_cache=None, display_index=None):
        super().__init__(daemon=True)
        self.port,self.theme,self.transport,self.telemetry,self.events,self.stop = port,theme,transport,telemetry,events,stop
        self.config=config or default_layout()
        self.brightness=brightness
        self.preview_cache=preview_cache
        self.display_index=display_index
        self.auto_visualizers={'MUSIC VISUALIZER 2.0':MusicVisualizerV2(), 'GPU Neon':None, 'SMART WEATHER CLOCK':SmartWeatherClock(), 'System Neon':None} if theme=='AUTO / SMART MODE' else {}
        self.midnight=MidnightEQ() if theme=='MIDNIGHT EQ' else None
        self.nexus=Nexus26() if theme=='NEXUS 26 (Original)' else (OriginalTheme(theme) if theme in ORIGINAL_NAMES else (SmartWeatherClock() if theme=='SMART WEATHER CLOCK' else (MusicVisualizer() if theme=='MUSIC VISUALIZER' else (MusicVisualizerV2() if theme=='MUSIC VISUALIZER 2.0' else (FullScreenEQ() if theme=='FULL SCREEN COLOR EQ' else None)))))
    def run(self):
        video=None
        video_sequence=0
        try:
            orientation = 3 if self.transport == 'Firmware reverse' else 1
            if self.theme=='VIDEO PLAYER':
                video=VideoSource(self.config['video_path'], fps=self.config.get('video_fps',25),
                                  fit=self.config.get('video_fit','Cover'),
                                  resolution=self.config.get('video_resolution',240))
            elif self.theme=='Custom' and self.config.get('media','').lower().endswith('.mp4'):
                video=VideoSource(self.config['media'],min(2,self.config.get('fps',2)))
            background=load_background(self.config) if self.theme=='Custom' else None
            if self.theme=='Custom' and self.config.get('phone_photo'):
                self.events.put((self.port, 'Phone photo file: '+str(self.config.get('media'))+' | loaded='+str(background is not None)))
                if background is None: raise FileNotFoundError('Phone photo cannot be opened: '+str(self.config.get('media'))) 
            with Display(self.port,orientation,self.transport,video_mode=self.theme=='VIDEO PLAYER') as display:
                display.eq_sparse = self.theme == 'FULL SCREEN COLOR EQ'
                display.midnight_sparse = self.theme == 'MIDNIGHT EQ'
                if self.theme=='VIDEO PLAYER':
                    display.video_window=(160,110) if self.config.get('video_window')=='110p FULLSCREEN' else tuple(map(int,self.config.get('video_window','96x72').split('x')))
                    display.video_fullscreen=self.config.get('video_window')=='110p FULLSCREEN'
                stats_at=time.monotonic()
                frames_sent=0
                bytes_sent=0
                self.events.put((self.port, 'Connected: '+self.theme+' / '+self.transport))
                while not self.stop.is_set():
                    data = self.telemetry.get() or {}
                    if self.theme == 'VIDEO PLAYER':
                        frame,video_sequence=video.get_new(video_sequence) if video else (None,video_sequence)
                        if frame is None:
                            self.stop.wait(0.015)
                            continue
                    elif self.theme == 'Test':
                        frame = test_pattern()
                    elif self.theme == 'Custom':
                        bg=video.get() if video else background
                        frame=render_custom(self.config,data,bg)
                    elif self.theme=='AUTO / SMART MODE':
                        chosen=select_theme(data)
                        renderer=self.auto_visualizers[chosen]
                        frame=renderer.render(data) if renderer else RENDER[chosen](data)
                    elif self.theme=='NEXUS 26 (Original)' or self.theme in ORIGINAL_NAMES or self.theme=='SMART WEATHER CLOCK' or self.theme in ('MUSIC VISUALIZER','MUSIC VISUALIZER 2.0','FULL SCREEN COLOR EQ','MIDNIGHT EQ'):
                        frame=self.midnight.render(data) if self.theme=='MIDNIGHT EQ' else self.nexus.render(data)
                    elif not data:
                        self.stop.wait(.3)
                        continue
                    else:
                        frame = RENDER[self.theme](data)
                    if self.brightness is not None:
                        level=self.brightness.get()
                        if level<100:frame=ImageEnhance.Brightness(frame).enhance(level/100.0)
                    # Publish only the reference to the frame already rendered for USB.
                    # No extra rendering, polling, or JPEG work in the display loop.
                    if self.preview_cache is not None:
                        self.preview_cache.publish(self.display_index, frame)
                    if self.theme == 'VIDEO PLAYER':
                        display.send_video(frame,self.stop)
                    elif self.theme == 'Custom' and self.config.get('phone_photo'):
                        display.send_photo(frame,self.stop)
                    else:
                        display.send(frame,self.stop)
                    st=display.last_stats or {}
                    if st.get('bytes',0):
                        frames_sent+=1
                        bytes_sent+=st['bytes']
                    now=time.monotonic()
                    if now-stats_at>=5:
                        elapsed=now-stats_at
                        self.events.put((self.port,
                            f'USB actual: {frames_sent/elapsed:.2f} FPS | '
                            f'{bytes_sent/elapsed/1024:.0f} KiB/s | '
                            f'last transfer {st.get("seconds",0):.2f}s | '
                            f'{st.get("mode","unknown")}'))
                        frames_sent=0;bytes_sent=0;stats_at=now
                    # Music marquee needs frequent small partial USB updates.
                    # Other themes retain the ECO refresh cadence.
                    self.stop.wait(0.001 if self.theme=='VIDEO PLAYER' else (0.025 if (self.theme in ('MUSIC VISUALIZER 2.0','FULL SCREEN COLOR EQ','MIDNIGHT EQ') or (self.theme=='AUTO / SMART MODE' and chosen=='MUSIC VISUALIZER 2.0')) else (0.12 if self.theme=='MUSIC VISUALIZER' else (1.0 if self.theme=='AUTO / SMART MODE' or video else 2.0))))
        except Exception as exc:
            self.events.put((self.port, 'ERROR: '+str(exc)+' | '+traceback.format_exc(limit=1).strip()))
        finally:
            if video:video.close()
            self.events.put((self.port, 'Stopped'))

class BrightnessValue:
    def __init__(self,value=100):
        self._value=max(0,min(100,int(value)))
        self.lock=threading.Lock()
    def get(self):
        with self.lock:return self._value
    def set(self,value):
        with self.lock:self._value=max(0,min(100,int(float(value))))

class App:
    def __init__(self,root):
        self.root=root
        root.title(f'TURMO Control v{VERSION}')
        root.geometry('1120x790')
        root.minsize(900,680)
        root.configure(bg='#0A0F19')
        self._setup_style(root)
        self.events=queue.Queue()
        self.stop=threading.Event()
        self.threads=[]
        self.remote_commands=queue.Queue()
        self.remote_server=None
        self.remote_previews=PreviewCache()
        self.telemetry=None
        self.images=[]
        self.tray_icon=None
        self.tray_thread=None
        self.tray_error=False
        self.settings=load_settings()
        # Initialize translations BEFORE creating any translated widget.
        # For one-file PyInstaller builds, bundled data lives in _MEIPASS.
        base=Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        locale_path=base/'locales.json'
        self.locales=json.loads(locale_path.read_text(encoding='utf-8'))
        self.lang=self.settings.get('language','en')
        if self.lang not in self.locales:
            self.lang='en'
        self.translatable=[]
        self.language_var=tk.StringVar(value=self.lang)
        self.custom_configs=self.settings.get('custom_configs',[default_layout(),default_layout()])
        if not isinstance(self.custom_configs,list) or len(self.custom_configs)!=2:self.custom_configs=[default_layout(),default_layout()]
        self.preview_videos=[None,None]
        self.video_configs=self.settings.get('video_configs',[{},{}])
        if not isinstance(self.video_configs,list) or len(self.video_configs)!=2:self.video_configs=[{},{}]
        self.nexus_previews=[Nexus26(),Nexus26()]
        self.original_previews=[{} for _ in range(2)]
        self.smart_previews=[SmartWeatherClock(),SmartWeatherClock()]
        self.music_previews=[MusicVisualizer(),MusicVisualizer()]
        self.music_v2_previews=[MusicVisualizerV2(),MusicVisualizerV2()]
        self.full_eq_previews=[FullScreenEQ(),FullScreenEQ()]
        self.midnight_previews=[MidnightEQ(),MidnightEQ()]
        self.port_boxes=[]
        saved_brightness=self.settings.get('brightness',[100,100])
        if not isinstance(saved_brightness,list) or len(saved_brightness)!=2:saved_brightness=[100,100]
        self.brightness=[BrightnessValue(x) for x in saved_brightness]
        self.brightness_vars=[]
        # No hard-coded city: use only a city explicitly chosen by this user.
        self.weather_city=tk.StringVar(value=self.settings.get('weather_city',''))
        self.weather_stop=threading.Event()
        self.weather=WeatherService(self.weather_stop,self.events,self.weather_city.get())
        self.weather.start()
        self.music_stop=threading.Event()
        self.music=NowPlaying(self.music_stop,self.events)
        self.music.start()
        # v0.27: simple header, a monitoring dashboard, a settings tab,
        # and a separate diagnostics tab. The underlying screen logic is unchanged.
        bg='#0A0F19';panel='#141E2D';fg='#F2F6FC';muted='#91A5BC';accent='#63E2D2'
        header=tk.Frame(root,bg=bg)
        header.pack(fill='x',padx=28,pady=(21,14))
        titlebox=tk.Frame(header,bg=bg)
        titlebox.pack(side='left',fill='x',expand=True)
        tk.Label(titlebox,text='TURMO',font=('Segoe UI',27,'bold'),bg=bg,fg=fg).pack(anchor='w')
        tk.Label(titlebox,text=f'MULTISCREEN STUDIO    •    VERSION {VERSION}',font=('Segoe UI',9,'bold'),bg=bg,fg=accent).pack(anchor='w',pady=(3,0))
        langbox=tk.Frame(header,bg=bg);langbox.pack(side='right')
        self._label(langbox,'language',bg=bg,fg=muted,font=('Segoe UI',9)).pack(anchor='w',pady=(0,4))
        self.language_combo=ttk.Combobox(langbox,state='readonly',width=21,
                                        values=[f'{k.upper()} — {v["language_name"]}' for k,v in self.locales.items()])
        self.language_combo.set(f'{self.lang.upper()} — {self.locales[self.lang]["language_name"]}')
        self.language_combo.pack()
        self.language_combo.bind('<<ComboboxSelected>>',self._language_changed)

        # Fine accent divider anchors the dashboard without a bulky banner.
        tk.Frame(root,bg=accent,height=2).pack(fill='x',padx=28,pady=(0,12))
        tabs=ttk.Notebook(root,style='TNotebook')
        tabs.pack(fill='both',expand=True,padx=24,pady=(0,16))
        dashboard=tk.Frame(tabs,bg=bg)
        settings_tab=tk.Frame(tabs,bg=bg)
        logs_tab=tk.Frame(tabs,bg=bg)
        remote_tab=tk.Frame(tabs,bg=bg)
        video_tab=tk.Frame(tabs,bg=bg)
        tabs.add(dashboard,text='  '+self._tr('dashboard')+'  ')
        tabs.add(settings_tab,text='  '+self._tr('settings_tab')+'  ')
        tabs.add(logs_tab,text='  '+self._tr('diagnostics')+'  ')
        tabs.add(remote_tab,text='  Phone Remote  ')
        tabs.add(video_tab,text='  Video  ')
        self.tabs=tabs

        toolbar=tk.Frame(dashboard,bg=bg)
        toolbar.pack(fill='x',padx=14,pady=(18,10))
        def action(key,command,primary=False):
            return self._button(toolbar,key,command=command,bg=accent if primary else '#23344B',
                fg='#07151C' if primary else fg,font=('Segoe UI',10,'bold'),
                activebackground='#95F2E6' if primary else '#314962',
                activeforeground='#07151C' if primary else fg,
                relief='flat',borderwidth=0,padx=16,pady=10,cursor='hand2')
        action('start',self.start,True).pack(side='left',padx=(0,8))
        action('stop',self.halt).pack(side='left',padx=(0,8))
        action('detect',self.detect_screens).pack(side='left',padx=(0,8))
        action('refresh',self.preview).pack(side='left')

        preview_heading=tk.Frame(dashboard,bg=bg)
        preview_heading.pack(fill='x',padx=18,pady=(12,8))
        tk.Label(preview_heading,text='LIVE PREVIEW',font=('Segoe UI',11,'bold'),bg=bg,fg=accent).pack(side='left')
        self.pvlabels=[]
        pv=tk.Frame(dashboard,bg=bg)
        pv.pack(fill='both',expand=True,padx=12,pady=(0,12))
        for i in range(2):
            pane=tk.Frame(pv,bg=panel,highlightbackground='#2A4057',highlightthickness=1)
            pane.pack(side='left',fill='both',expand=True,padx=6)
            self._label(pane,'preview',n=i+1,bg=panel,fg=muted,
                        font=('Segoe UI',10,'bold')).pack(anchor='w',padx=14,pady=(13,9))
            lbl=tk.Label(pane,bg='#0C1522',width=365,height=243)
            lbl.pack(expand=True,padx=10,pady=(0,16))
            self.pvlabels.append(lbl)
        self.status=self._label(dashboard,'status_wait',bg=bg,fg=muted,anchor='w',font=('Segoe UI',9))
        self.status.pack(fill='x',padx=18,pady=(0,14))

        # Configuration is kept off the dashboard so everyday use is uncluttered.
        config_top=tk.Frame(settings_tab,bg=bg)
        config_top.pack(fill='x',padx=18,pady=(18,4))
        tk.Label(config_top,text='DISPLAY CONFIGURATION',font=('Segoe UI',11,'bold'),bg=bg,fg=accent).pack(anchor='w')
        devices=discover_screens()
        ports=[p.device for p in devices]
        preferred=self.settings.get('ports',[])
        if isinstance(preferred,list) and len(preferred)==2 and all(x in ports for x in preferred) and preferred[0]!=preferred[1]:
            ports=preferred+[x for x in ports if x not in preferred]
        self.pvars=[];self.tvars=[];self.ovars=[]
        for i in range(2):
            card=tk.Frame(settings_tab,bg=panel,highlightbackground='#2A4057',highlightthickness=1)
            card.pack(fill='x',padx=18,pady=7)
            self._label(card,'screen',n=i+1,bg=panel,fg=fg,font=('Segoe UI',11,'bold')).pack(anchor='w',padx=14,pady=(10,7))
            fields=tk.Frame(card,bg=panel);fields.pack(fill='x',padx=12,pady=(0,8))
            pvar=tk.StringVar(value=ports[i] if i<len(ports) else '');self.pvars.append(pvar)
            port=ttk.Combobox(fields,textvariable=pvar,values=ports,state='readonly',width=9)
            port.pack(side='left',padx=(0,9));self.port_boxes.append(port)
            saved_themes=self.settings.get('themes',['System','GPU'])
            theme=(saved_themes[i] if isinstance(saved_themes,list) and len(saved_themes)==2 and saved_themes[i] in RENDER else ('System' if i==0 else 'GPU'))
            tvar=tk.StringVar(value=theme);self.tvars.append(tvar)
            theme_box=ttk.Combobox(fields,textvariable=tvar,values=list(RENDER),state='readonly',width=23)
            theme_box.pack(side='left',padx=(0,9));theme_box.bind('<<ComboboxSelected>>',lambda event:self._theme_changed())
            saved_orient=self.settings.get('orientations',['Native portrait CW']*2)
            valid_orient=['Native portrait CW','Native portrait CCW','Firmware landscape','Firmware reverse']
            orientation=saved_orient[i] if isinstance(saved_orient,list) and len(saved_orient)==2 and saved_orient[i] in valid_orient else valid_orient[0]
            ovar=tk.StringVar(value=orientation);self.ovars.append(ovar)
            ttk.Combobox(fields,textvariable=ovar,values=valid_orient,state='readonly',width=21).pack(side='left',padx=(0,9))
            self._button(fields,'edit_theme',command=lambda index=i:self.edit_theme(index),
                         bg='#304a66',fg=fg,relief='flat',padx=10,pady=6).pack(side='left')
            bright=tk.Frame(card,bg=panel);bright.pack(fill='x',padx=12,pady=(0,9))
            self._label(bright,'brightness',n=i+1,bg=panel,fg=muted).pack(side='left',padx=(0,12))
            bv=tk.IntVar(value=self.brightness[i].get());self.brightness_vars.append(bv)
            tk.Scale(bright,from_=0,to=100,variable=bv,orient='horizontal',length=240,
                     command=lambda v,index=i:self._brightness_changed(index,v),bg=panel,fg=fg,
                     troughcolor='#293b52',highlightthickness=0,bd=0).pack(side='left')

        extras=tk.Frame(settings_tab,bg=panel,highlightbackground='#2A4057',highlightthickness=1)
        extras.pack(fill='x',padx=18,pady=(8,6))
        weatherbar=tk.Frame(extras,bg=panel);weatherbar.pack(fill='x',padx=12,pady=(12,5))
        self._label(weatherbar,'weather_city',bg=panel,fg=fg).pack(side='left',padx=(0,10))
        tk.Entry(weatherbar,textvariable=self.weather_city,width=25,bg='#23354b',fg=fg,
                 insertbackground=fg,relief='flat').pack(side='left',ipady=6,padx=(0,9))
        self._button(weatherbar,'search_update',command=self.update_weather,bg='#304a66',fg=fg,
                     relief='flat',padx=10,pady=6).pack(side='left')
        self._label(extras,'updates',bg=panel,fg=muted,font=('Segoe UI',8)).pack(anchor='w',padx=14,pady=(0,8))
        update_row=tk.Frame(extras,bg=panel);update_row.pack(fill='x',padx=12,pady=(0,9))
        tk.Button(update_row,text='Check for updates',command=self.check_updates,
                  bg='#304a66',fg=fg,activebackground='#426584',relief='flat',
                  padx=12,pady=7,cursor='hand2').pack(side='left')
        self.update_status=tk.StringVar(value=f'Installed version: v{VERSION}')
        tk.Label(update_row,textvariable=self.update_status,bg=panel,fg=muted,
                 font=('Segoe UI',9)).pack(side='left',padx=12)
        startup_row=tk.Frame(extras,bg=panel);startup_row.pack(fill='x',padx=12,pady=(2,12))
        self.startup_enabled=tk.BooleanVar(value=startup_is_enabled())
        self.startup_checkbox=tk.Checkbutton(startup_row,text=self._tr('startup'),variable=self.startup_enabled,
            command=self._toggle_startup,bg=panel,fg=fg,activebackground=panel,
            activeforeground=fg,selectcolor='#1C3044')
        self.startup_checkbox.pack(side='left')
        self.translatable.append((self.startup_checkbox,'startup',{}))
        self._label(startup_row,'startup_note',bg=panel,fg=muted).pack(side='left',padx=10)

        # Dedicated video player. Settings are independent for the two displays.
        tk.Label(video_tab,text='VIDEO PLAYER  /  USB PERFORMANCE',bg=bg,fg=fg,
                 font=('Segoe UI',13,'bold')).pack(anchor='w',padx=22,pady=(20,8))
        tk.Label(video_tab,text='Choose a local video and target display. Playback loops silently. Actual USB FPS is shown in Diagnostics.',
                 bg=bg,fg=muted,wraplength=760,justify='left').pack(anchor='w',padx=22,pady=(0,10))
        self.video_controls=[]
        for i in range(2):
            cfg=self.video_configs[i]
            card=tk.Frame(video_tab,bg=panel,highlightbackground='#2A4057',highlightthickness=1)
            card.pack(fill='x',padx=22,pady=8)
            tk.Label(card,text=f'DISPLAY {i+1}',bg=panel,fg=fg,font=('Segoe UI',11,'bold')).pack(anchor='w',padx=12,pady=(10,6))
            path=tk.StringVar(value=cfg.get('video_path',''))
            row=tk.Frame(card,bg=panel);row.pack(fill='x',padx=12,pady=4)
            tk.Entry(row,textvariable=path,bg='#23354b',fg=fg,insertbackground=fg,relief='flat').pack(side='left',fill='x',expand=True,ipady=7)
            tk.Button(row,text='Browse video',command=lambda v=path:self._browse_video(v),bg='#304a66',fg=fg,relief='flat').pack(side='left',padx=8)
            options=tk.Frame(card,bg=panel);options.pack(fill='x',padx=12,pady=(8,12))
            fit=tk.StringVar(value=cfg.get('video_fit','Cover'))
            resolution=tk.StringVar(value=str(cfg.get('video_resolution',240)))
            fps=tk.StringVar(value=str(cfg.get('video_fps',25)))
            window=tk.StringVar(value=cfg.get('video_window','96x72'))
            for caption,var,choices in [('Fit',fit,['Cover','Contain','Stretch']),
                                        ('Decode width',resolution,['160','240','320','480']),
                                        ('Target FPS',fps,['15','20','25','30']),
                                        ('Video size',window,['96x72','128x96','160x120','192x144','110p FULLSCREEN'])]:
                tk.Label(options,text=caption,bg=panel,fg=muted).pack(side='left',padx=(0,5))
                ttk.Combobox(options,textvariable=var,values=choices,state='readonly',width=9).pack(side='left',padx=(0,18))
            tk.Button(options,text='Play on display',bg='#315c70',fg=fg,relief='flat',padx=10,pady=6,
                      command=lambda j=i:self._play_video(j)).pack(side='right')
            self.video_controls.append((path,fit,resolution,fps,window))
        tk.Label(video_tab,text='110p FULLSCREEN upscales a 160x110 source to 480x320 on the PC. USB still sends 300 KiB/frame, so this mode is much slower. Other sizes keep fast compact transfer.',
                 bg=bg,fg=muted,wraplength=780,justify='left').pack(anchor='w',padx=22,pady=8)

        # Phone remote: opt-in LAN server; QR code includes address only, never PIN.
        remote_box=tk.Frame(remote_tab,bg=panel,highlightbackground='#2A4057',highlightthickness=1)
        remote_box.pack(fill='x',padx=18,pady=(22,10))
        tk.Label(remote_box,text='PHONE REMOTE / QR',bg=panel,fg=fg,font=('Segoe UI',11,'bold')).pack(anchor='w',padx=12,pady=(9,4))
        self.remote_info=tk.StringVar(value='Remote disabled')
        tk.Label(remote_box,textvariable=self.remote_info,bg=panel,fg=muted,justify='left').pack(anchor='w',padx=12)
        self.remote_qr=tk.Label(remote_box,bg=panel)
        self.remote_qr.pack(side='right',padx=16,pady=6)
        tk.Button(remote_box,text='Enable remote + QR',command=self.enable_remote,bg='#304a66',fg=fg,relief='flat',padx=10,pady=7).pack(side='left',padx=12,pady=9)
        tk.Button(remote_box,text='Disable remote',command=self.disable_remote,bg='#304a66',fg=fg,relief='flat',padx=10,pady=7).pack(side='left',padx=4,pady=9)

        self._label(logs_tab,'log',bg=bg,fg=fg,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=18,pady=(18,10))
        self.logbox=tk.Text(logs_tab,bg='#111d2e',fg='#b7d8ee',font=('Consolas',9),
                            height=16,relief='flat',wrap='word',padx=12,pady=12)
        self.logbox.pack(fill='both',expand=True,padx=18,pady=(0,18))
        self.log(f'Auto-detect: {len(devices)} TURMO display(s) found: '+(', '.join(p.device for p in devices) or 'none'))
        self.log('Close UsbMonitor.exe before starting displays.')
        self.log('Missing sensor readings appear as a dash.')
        root.after(200,self.poll)
        root.protocol('WM_DELETE_WINDOW',self.hide_to_tray)
        # Only the Windows logon task starts the saved displays automatically.
        # Manual launches still open normally and wait for the Start button.
        if '--autostart' in sys.argv:
            root.after(1000,self._autostart_session)
    def enable_remote(self):
        if self.remote_server:return
        server=RemoteServer(self.remote_commands.put,RENDER.keys(),self.remote_previews)
        try:
            server.start()
            self.remote_server=server
            url=f'http://{lan_ip()}:{PORT}/'
            self.remote_info.set(f'Open on phone: {url}\nPairing PIN: {server.pin} (keep private)')
            try:
                import qrcode
                qr=qrcode.QRCode(box_size=4,border=2)
                qr.add_data(url);qr.make(fit=True)
                self.remote_qr_photo=ImageTk.PhotoImage(qr.make_image(fill_color='black',back_color='white').convert('RGB'))
                self.remote_qr.configure(image=self.remote_qr_photo)
            except ImportError:
                self.remote_info.set(self.remote_info.get()+'\nQR dependency missing (qrcode)')
            self.log('Phone remote enabled: '+url)
        except OSError as exc:
            messagebox.showerror('TURMO Remote','Cannot start local web server: '+str(exc))

    def disable_remote(self):
        server=self.remote_server
        self.remote_server=None
        if server:threading.Thread(target=server.stop,daemon=True).start()
        self.remote_info.set('Remote disabled')
        self.remote_qr.configure(image='')
        self.remote_qr_photo=None

    def _remote_action(self,action):
        kind=action.get('action')
        if kind=='stop':self.halt()
        elif kind=='start':self.start(quiet=True)
        elif kind=='brightness':
            i=action['display'];v=action['value']
            self.brightness_vars[i].set(v)
            self._brightness_changed(i,v)
        elif kind=='phone_image':
            i=action['display']
            self.custom_configs[i]=dict(default_layout(),widgets=[],media=action['path'],media_fit='contain',phone_photo=True)
            self.tvars[i].set('Custom')
            self.remember_settings()
            self.log(f'Phone image received for display {i+1}: {action["path"]}')
            if any(t.is_alive() for t in self.threads) or (self.telemetry is not None and self.telemetry.is_alive()):
                self.halt()
                self.root.after(150,self._remote_restart)
            else:
                self.preview()
                self.start(quiet=True)
        elif kind=='theme':
            i=action['display'];theme=action['theme']
            self.tvars[i].set(theme)
            self.remember_settings()
            # The active display thread has a fixed renderer; restart to apply.
            if any(t.is_alive() for t in self.threads):
                self.halt()
                self.root.after(700,self._remote_restart)
            else:self.preview()

    def _remote_restart(self):
        if any(t.is_alive() for t in self.threads) or (self.telemetry is not None and self.telemetry.is_alive()):
            self.root.after(250,self._remote_restart)
        else:
            self.log('Phone remote: restarting displays with new image/theme')
            self.start(quiet=True)

    def check_updates(self):
        check_and_update(self.root, self.update_status.set, self.close)

    def _tr(self,key,**kwargs):
        template=self.locales.get(self.lang,self.locales['en']).get(key,self.locales['en'].get(key,key))
        return template.format(**kwargs)

    def _label(self,parent,key,**kwargs):
        n=kwargs.pop('n',None)
        widget=tk.Label(parent,text=self._tr(key,**({'n':n} if n is not None else {})),**kwargs)
        self.translatable.append((widget,key,{'n':n} if n is not None else {}))
        return widget

    def _button(self,parent,key,**kwargs):
        widget=tk.Button(parent,text=self._tr(key),**kwargs)
        self.translatable.append((widget,key,{}))
        return widget

    def _language_changed(self,event=None):
        selected=self.language_combo.get().split(' — ',1)[0].lower()
        if selected not in self.locales:return
        self.lang=selected
        for widget,key,params in self.translatable:
            try:widget.configure(text=self._tr(key,**params))
            except tk.TclError:pass
        for i,key in enumerate(('dashboard','settings_tab','diagnostics')):
            self.tabs.tab(i,text='  '+self._tr(key)+'  ')
        self.remember_settings()
        self.preview()

    def _setup_style(self, root):
        style=ttk.Style(root)
        style.theme_use('clam')
        style.configure('TNotebook',background='#0A0F19',borderwidth=0,tabmargins=(0,0,0,0))
        style.configure('TNotebook.Tab',background='#18283A',foreground='#A9BFD2',
                        font=('Segoe UI',10,'bold'),padding=(23,13),borderwidth=0)
        style.map('TNotebook.Tab',background=[('selected','#285568')],
                  foreground=[('selected','#ffffff')])
        style.configure('TFrame',background='#0A0F19')
        style.configure('TLabel',background='#0A0F19',foreground='#F2F6FC',font=('Segoe UI',10))
        style.configure('TSeparator',background='#2A4057')
        style.configure('TCheckbutton',background='#141E2D',foreground='#F2F6FC',font=('Segoe UI',10))
        style.map('TCheckbutton',background=[('active','#141E2D')],foreground=[('active','#63E2D2')])
        style.configure('TCombobox',foreground='#F2F6FC',fieldbackground='#1C3044',
                        background='#1C3044',arrowcolor='#7BE7D8',padding=6)
        style.map('TCombobox',fieldbackground=[('readonly','#1C3044')],
                  selectbackground=[('readonly','#1C3044')],
                  selectforeground=[('readonly','#F2F6FC')])

    def log(self,msg):
        self.logbox.insert('end',msg+'\n');self.logbox.see('end')
    def _brightness_changed(self,index,value):
        self.brightness[index].set(value)
        self.remember_settings()

    def _toggle_startup(self):
        enabled=self.startup_enabled.get()
        try:
            set_startup(enabled)
            self.log(self._tr('startup_on' if enabled else 'startup_off'))
        except Exception as exc:
            self.startup_enabled.set(startup_is_enabled())
            messagebox.showerror('TURMO',self._tr('startup_error')+'\n'+str(exc))

    def update_weather(self):
        self.weather.set_city(self.weather_city.get())
        self.remember_settings()
        self.log('Weather lookup requested' if self.weather_city.get().strip() else 'Weather disabled (no city entered)')

    def readings(self):
        values=self.telemetry.get() if self.telemetry else None
        values=values or {}
        values.update(self.weather.get())
        values.update(self.music.get())
        return values

    def preview(self):
        values=self.readings()
        if values is None:
            self.status.configure(text=self._tr('status_missing'))
            values={}
        else:
            self.status.configure(text=self._tr('status_live',state=self._tr('available' if values.get('gpu_temp') is not None else 'unavailable')))
        self.images=[]
        self.tray_icon=None
        self.tray_thread=None
        self.tray_error=False
        for i,lbl in enumerate(self.pvlabels):
            theme=self.tvars[i].get()
            if theme=='VIDEO PLAYER':
                
                with self.remote_previews.lock:
                    im=self.remote_previews.frames[i]
                if im is None:im=Image.new('RGB',(480,320),'#0C1522')
            elif theme=='Custom':
                cfg=self.custom_configs[i]
                media=cfg.get('media','')
                active=self.preview_videos[i]
                if media.lower().endswith('.mp4'):
                    if active is None or active.path!=media:
                        if active:active.close()
                        active=self.preview_videos[i]=VideoSource(media,min(2,cfg.get('fps',2)))
                    bg=active.get()
                else:
                    if active:active.close();self.preview_videos[i]=None
                    bg=load_background(cfg)
                im=render_custom(cfg,values,bg)
            else:
                if active:=self.preview_videos[i]:active.close();self.preview_videos[i]=None
                if theme=='AUTO / SMART MODE':
                    chosen=select_theme(values)
                    if chosen=='MUSIC VISUALIZER 2.0':
                        im=self.music_v2_previews[i].render(values)
                    elif chosen=='SMART WEATHER CLOCK':
                        im=self.smart_previews[i].render(values)
                    else:
                        im=RENDER[chosen](values)
                elif theme=='MUSIC VISUALIZER 2.0':
                    im=self.music_v2_previews[i].render(values)
                elif theme=='MIDNIGHT EQ':
                    im=self.midnight_previews[i].render(values)
                elif theme=='FULL SCREEN COLOR EQ':
                    im=self.full_eq_previews[i].render(values)
                elif theme=='MUSIC VISUALIZER':
                    im=self.music_previews[i].render(values)
                elif theme=='SMART WEATHER CLOCK':
                    im=self.smart_previews[i].render(values)
                elif theme=='NEXUS 26 (Original)':
                    im=self.nexus_previews[i].render(values)
                elif theme in ORIGINAL_NAMES:
                    if theme not in self.original_previews[i]:
                        self.original_previews[i][theme]=OriginalTheme(theme)
                    im=self.original_previews[i][theme].render(values)
                else:
                    im=RENDER[theme](values)
            level=self.brightness[i].get()
            if level<100:im=ImageEnhance.Brightness(im).enhance(level/100.0)
            im.thumbnail((365,243))
            photo=ImageTk.PhotoImage(im)
            lbl.configure(image=photo,width=365,height=243)
            self.images.append(photo)
    def edit_theme(self,index):
        def save(cfg):
            self.custom_configs[index]=cfg
            self.tvars[index].set('Custom')
            self.remember_settings()
            self.preview()
        editor=ThemeEditor(self.root,self.custom_configs[index],save,
                           self.readings)
        editor.open_video()

    def _browse_video(self,variable):
        path=filedialog.askopenfilename(parent=self.root,title='Choose video',
                                        filetypes=[('Video files','*.mp4 *.mkv *.mov *.avi *.webm'),('All files','*.*')])
        if path:variable.set(path)

    def _play_video(self,index):
        path,fit,resolution,fps,window=self.video_controls[index]
        video=path.get().strip()
        if not Path(video).is_file():
            messagebox.showerror('Video','Select an existing video file first.')
            return
        self.video_configs[index]={'video_path':video,'video_fit':fit.get(),
                                   'video_resolution':int(resolution.get()),'video_fps':int(fps.get()),
                                   'video_window':window.get()}
        self.tvars[index].set('VIDEO PLAYER')
        self.remember_settings()
        if any(t.is_alive() for t in self.threads):
            self.halt()
            self.root.after(800,self._restart_video_when_stopped)
        else:self.start()

    def _restart_video_when_stopped(self):
        if any(t.is_alive() for t in self.threads):
            self.root.after(250,self._restart_video_when_stopped)
        else:self.start()

    def detect_screens(self):
        devices=discover_screens()
        available=[p.device for p in devices]
        for i, combo in enumerate(self.port_boxes):
            combo.configure(values=available)
            old=self.pvars[i].get()
            if old not in available or (i==1 and old==self.pvars[0].get()):
                used={self.pvars[j].get() for j in range(i)}
                self.pvars[i].set(next((x for x in available if x not in used), ''))
        self.log('Detected TURMO displays: '+(', '.join(available) or 'none'))
        if len(available)<1:
            self.status.configure(text=self._tr('not_detected'))

    def _theme_changed(self):
        self.remember_settings()
        self.preview()

    def remember_settings(self):
        save_settings({'ports':[v.get() for v in self.pvars],
                       'themes':[v.get() for v in self.tvars],
                       'orientations':[v.get() for v in self.ovars],
                       'custom_configs':self.custom_configs,
                       'video_configs':self.video_configs,
                       'brightness':[b.get() for b in self.brightness],
                       'language':self.lang,
                       'weather_city':self.weather_city.get().strip()})

    def start(self,quiet=False):
        if any(t.is_alive() for t in self.threads) or (self.telemetry is not None and self.telemetry.is_alive()):
            if not quiet:messagebox.showinfo('TURMO',self._tr('stop_first'))
            return
        self.detect_screens()
        ports=[v.get().strip().upper() for v in self.pvars]
        active=[(i,port) for i,port in enumerate(ports) if port]
        if not active:
            self.log(self._tr('connect'))
            if not quiet:messagebox.showerror('Ports',self._tr('connect'))
            return
        if len(set(port for _,port in active)) != len(active):
            self.log(self._tr('different_ports'))
            if not quiet:messagebox.showerror('Ports',self._tr('different_ports'))
            return
        self.remember_settings()
        self.stop=threading.Event()
        self.remote_previews.clear()
        self.telemetry=Telemetry(self.events,self.stop)
        self.telemetry.start()
        original_get=self.telemetry.get
        def merged_get():
            data=original_get() or {}
            data.update(self.weather.get())
            data.update(self.music.get())
            return data
        self.telemetry.get=merged_get
        self.threads=[]
        for i,port in active:
            t=ScreenThread(port,self.tvars[i].get(),self.ovars[i].get(),self.telemetry,self.events,self.stop,(self.video_configs[i] if self.tvars[i].get()=='VIDEO PLAYER' else self.custom_configs[i]),self.brightness[i],self.remote_previews,i)
            self.threads.append(t);t.start()
        self.log('Started: '+', '.join(port for _,port in active))
    def halt(self):
        self.stop.set()
        self.remote_previews.clear()
        self.log('Stopping after current frame...')
    def poll(self):
        while not self.remote_commands.empty():
            try:self._remote_action(self.remote_commands.get_nowait())
            except Exception as exc:self.log("Remote action error: "+str(exc))
        while not self.events.empty():
            port,msg=self.events.get()
            self.log(f'{port}: {msg}')
        self.preview()
        self.root.after(2000,self.poll)
    def _tray_image(self):
        image=Image.new('RGB',(64,64),'#0C1522')
        draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((5,8,59,52),radius=9,fill='#223a53',outline='#63E2D2',width=3)
        draw.rectangle((14,18,50,42),fill='#63E2D2')
        draw.rectangle((24,54,40,58),fill='#63E2D2')
        return image

    def _ensure_tray(self):
        if self.tray_icon is not None:
            return True
        try:
            import pystray
            menu=pystray.Menu(
                pystray.MenuItem('Open TURMO Control',lambda icon,item:self.root.after(0,self.restore_from_tray),default=True),
                pystray.MenuItem('Stop displays',lambda icon,item:self.root.after(0,self.halt)),
                pystray.MenuItem('Exit TURMO Control',lambda icon,item:self.root.after(0,self.close)))
            self.tray_icon=pystray.Icon('TURMO-Control',self._tray_image(),'TURMO Control',menu)
            self.tray_thread=threading.Thread(target=self.tray_icon.run,daemon=True)
            self.tray_thread.start()
            return True
        except Exception as exc:
            self.log('System tray unavailable: '+repr(exc))
            self.tray_icon=None
            return False

    def hide_to_tray(self):
        # Never hide an app without a working tray icon to restore it.
        if self._ensure_tray():
            self.root.withdraw()
        else:
            self.root.iconify()

    def restore_from_tray(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _autostart_session(self):
        # Scheduled Task login: use saved themes, brightness and orientation.
        # The normal start() method rechecks connected USB devices and handles
        # missing ports. Keep app hidden only if the tray is available.
        if self._ensure_tray():
            self.root.withdraw()
        self.log('Windows login: starting saved display configuration...')
        self.start(quiet=True)

    def close(self):
        if self.remote_server:
            self.remote_server.httpd.shutdown()
            self.remote_server.httpd.server_close()
            self.remote_server=None
        if self.tray_icon is not None:
            try:self.tray_icon.stop()
            except Exception:pass
            self.tray_icon=None
        self.remember_settings()
        self.stop.set()
        self.music_stop.set()
        self.weather_stop.set()
        self.weather.wake.set()
        for video in self.preview_videos:
            if video:video.close()
        self.root.destroy()

if __name__=='__main__':
    root=tk.Tk()
    App(root)
    root.mainloop()
