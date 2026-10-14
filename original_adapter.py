"""Original theme renderer integration (GPL licensed upstream source).
The actual pixel drawing functions live in original_themes/<package>/renderer.py.
"""
from collections import deque
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import time
from PIL import ImageFont
from original_themes.apex01 import renderer as apex
from original_themes.nova01 import renderer as nova
from original_themes.nexusminimal import renderer as minimal
from original_themes.trueview26 import renderer as trueview

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'original_themes'
NAMES=('APEX 01 (Original)','NOVA 01 (Original)','NEXUS MINIMAL (Original)','TRUE VIEW 26 (Original)')
FOLDERS=('APEX_01','NOVA_01','NEXUS_MINIMAL','TRUE_VIEW_26')

def value(data,key,default=0):
    try:
        v=data.get(key)
        return float(v) if v is not None else default
    except (TypeError,ValueError):return default

class OriginalTheme:
    def __init__(self,name):
        self.name=name
        folder=FOLDERS[NAMES.index(name)]
        self.font_dir=ROOT/folder/'fonts'
        self.config=NS(fonts_dir=self.font_dir)
        self.system=NS(kind='windows',model='RYZEN 7 7800X3D',os_version='Windows')
        self.cpu=deque([0.]*30,maxlen=30)
        self.temp=deque([0.]*30,maxlen=30)
        self.proc=deque([0.]*30,maxlen=30)
        self.fonts={}
        if name==NAMES[0]:
            sizes={'fTitle':13,'fClock':52,'fHeaderTime':23,'fBigVal':20,
                   'fWeatherTemp':24,'fWeatherCond':10,'fCardVal':14,
                   'fMedium':11,'fSmall':10,'fMicro':9,'fNano':8}
            for key,size in sizes.items():
                self.fonts[key]=ImageFont.truetype(str(self.font_dir/('Roboto-Regular.ttf' if key in ('fSmall','fMicro','fNano') else 'Roboto-Bold.ttf')),size)

    def render(self,data):
        d=data or {}
        cpu=value(d,'cpu')
        temp=d.get('cpu_temp')
        self.cpu.append(cpu)
        self.temp.append(value(d,'cpu_temp'))
        self.proc.append(value(d,'process_count',150))
        snap=NS(
            cpu_percent=cpu,per_core=(cpu,)*8,
            cpu_frequency_ghz=value(d,'cpu_clock')/1000 or None,
            cpu_temp_c=float(temp) if temp is not None else None,
            gpu_percent=value(d,'gpu_load'),gpu_temp_c=d.get('gpu_temp'),
            ram_percent=value(d,'ram'),ram_used_gb=value(d,'ram_used')/1073741824,
            ram_total_gb=value(d,'ram_total')/1073741824,
            disk_percent=value(d,'disk'),disk_used_gb=value(d,'disk_used')/1073741824,
            disk_total_gb=value(d,'disk_total')/1073741824,
            net_up_mb_s=value(d,'tx')/1048576,net_down_mb_s=value(d,'rx')/1048576,
            fan_rpm=value(d,'gpu_fan') or None,uptime_seconds=int(time.monotonic()),
            process_count=int(value(d,'process_count',150)),network_interface='Ethernet',
            load_average_1m=cpu/100,load_average_1=cpu/100,load_average_5=cpu/100,load_average_15=cpu/100)
        weather_temp=d.get('weather_temp')
        cond=str(d.get('weather_condition') or 'Clear')
        wc=cond.lower()
        condition=('rain' if 'rain' in wc or 'shower' in wc else
                   'snow' if 'snow' in wc else 'clear' if 'clear' in wc or 'sun' in wc else 'cloudy')
        w=NS(location=str(d.get('weather_city') or ''),
             temperature=(f"{float(weather_temp):.0f}°" if weather_temp is not None else '--°'),
             description=cond,condition=condition,
             high_c='--°',low_c='--°',humidity=f"{value(d,'weather_humidity'):.0f}%",
             forecast_days=[])
        if self.name==NAMES[0]:
            return apex.render_frame(self.config,snap,w,self.system,list(self.cpu),list(self.temp),self.fonts)
        if self.name==NAMES[1]:
            return nova.render_frame_turmo(snap,w,self.system,self.cpu,self.temp,self.proc,self.font_dir)
        if self.name==NAMES[2]:
            return minimal.render_frame(self.config,snap,self.system,self.cpu)
        return trueview.render_frame(self.config,snap,w,self.system,self.cpu)
