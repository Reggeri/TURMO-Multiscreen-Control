"""Pixel-accurate NEXUS 26 rendering port.
Drawing code is retained from the user-provided NEXUS_26 renderer (GPL-3.0).
Telemetry and USB transport are supplied by TURMO Control.
"""
import math
import time
import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from hardware_info import cpu_model
W,H=480,320

def draw_centered_text(draw, cx, y, text, font, fill):
    w = draw.textlength(text, font=font)
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def draw_cpu_icon(draw, x, y, color=(168, 85, 247)):
    draw.rectangle([x, y, x + 16, y + 16], outline=color, width=2)
    draw.rectangle([x + 4, y + 4, x + 12, y + 12], fill=color)
    for offset in (4, 8, 12):
        draw.line([(x + offset, y - 2), (x + offset, y)], fill=color, width=1)
        draw.line([(x + offset, y + 16), (x + offset, y + 18)], fill=color, width=1)
        draw.line([(x - 2, y + offset), (x, y + offset)], fill=color, width=1)
        draw.line([(x + 16, y + offset), (x + 18, y + offset)], fill=color, width=1)


def draw_gpu_icon(draw, x, y, color=(168, 85, 247)):
    draw.rectangle([x, y, x + 18, y + 14], outline=color, width=2)
    draw.ellipse([x + 3, y + 3, x + 9, y + 9], outline=color, width=1)
    draw.ellipse([x + 9, y + 3, x + 15, y + 9], outline=color, width=1)


def draw_ram_icon(draw, x, y, color=(168, 85, 247)):
    draw.rectangle([x, y + 3, x + 18, y + 15], outline=color, width=2)
    for offset in range(3, 16, 3):
        draw.line([(x + offset, y + 15), (x + offset, y + 18)], fill=color, width=1)


def draw_ssd_icon(draw, x, y, color=(168, 85, 247)):
    draw.rectangle([x + 2, y, x + 16, y + 18], outline=color, width=2)
    draw.ellipse([x + 6, y + 4, x + 12, y + 10], outline=color, width=1)
    draw.line([(x + 5, y + 14), (x + 13, y + 14)], fill=color, width=2)


def draw_concept_fan_icon(draw, x, y, color=(168, 85, 247)):
    cx, cy = x + 10, y + 10
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline=color, width=1)
    for angle in [0, 90, 180, 270]:
        rad = math.radians(angle)
        rad2 = math.radians(angle + 45)
        x1 = cx + 3 * math.cos(rad)
        y1 = cy + 3 * math.sin(rad)
        x2 = cx + 9 * math.cos(rad2)
        y2 = cy + 9 * math.sin(rad2)
        draw.line([(x1, y1), (x2, y2)], fill=color, width=2)


def draw_concept_network_icon(draw, x, y, color=(168, 85, 247)):
    draw.rectangle([x, y + 2, x + 18, y + 14], outline=color, width=1)
    draw.line([(x + 4, y + 6), (x + 14, y + 6)], fill=color, width=1)
    draw.line([(x + 4, y + 10), (x + 14, y + 10)], fill=color, width=1)


def draw_concept_clock_icon(draw, x, y, color=(168, 85, 247)):
    draw.ellipse([x, y, x + 18, y + 18], outline=color, width=2)
    draw.line([(x + 9, y + 9), (x + 9, y + 4)], fill=color, width=2)
    draw.line([(x + 9, y + 9), (x + 13, y + 9)], fill=color, width=2)


def draw_concept_weather_icon(draw, x, y, condition: str):
    sun = (245, 158, 11)
    cloud = (192, 132, 252)
    rain = (96, 165, 250)

    if condition in {"clear", "sun"}:
        cx, cy = x + 10, y + 10
        draw.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], outline=sun, width=2)
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = cx + 6 * math.cos(rad)
            y1 = cy + 6 * math.sin(rad)
            x2 = cx + 9 * math.cos(rad)
            y2 = cy + 9 * math.sin(rad)
            draw.line([(x1, y1), (x2, y2)], fill=sun, width=1)
        return

    draw.ellipse([x + 1, y + 10, x + 10, y + 19], outline=cloud, width=1)
    draw.ellipse([x + 5, y + 6, x + 17, y + 19], outline=cloud, width=1)
    draw.ellipse([x + 13, y + 10, x + 22, y + 19], outline=cloud, width=1)
    draw.line([(x + 4, y + 19), (x + 20, y + 19)], fill=cloud, width=1)

    if condition == "rain":
        for offset in (7, 14, 21):
            draw.line([(x + offset, y + 22), (x + offset - 2, y + 25)], fill=rain, width=1)


def draw_concept_smooth_wave_graph(draw, box, history, line_color=(192, 132, 252), fill_color=(50, 20, 85)):
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    real = [(i, v) for i, v in enumerate(history) if v is not None]
    if len(real) < 2 or w <= 0 or h <= 0:
        draw.line([(x0, y1), (x1, y1)], fill=(60, 60, 60), width=1)
        return

    num = len(history)
    line_pts = []
    for i, val in real:
        px = x0 + int((i / (num - 1)) * w)
        py = y1 - int(((max(0.0, min(100.0, float(val))) / 100.0) * (h - 2)))
        py = max(y0, min(y1, py))
        line_pts.append((px, py))

    poly_pts = line_pts + [(x1, y1), (x0, y1)]
    draw.polygon(poly_pts, fill=fill_color)
    draw.line(line_pts, fill=line_color, width=2)


def draw_concept_rgb_pill_bar(draw, box, percent):
    x0, y0, x1, y1 = box
    total_segments = 14
    gap = 2
    seg_w = ((x1 - x0) - (gap * (total_segments - 1))) // total_segments
    active_count = max(0, min(total_segments, int(round((percent / 100.0) * total_segments))))

    for i in range(total_segments):
        sx0 = x0 + i * (seg_w + gap)
        sx1 = sx0 + seg_w
        if i < active_count:
            if i < 8:
                seg_color = (0, 229, 255)
            elif i < 11:
                seg_color = (168, 85, 247)
            else:
                seg_color = (245, 158, 11)
        else:
            seg_color = (25, 27, 55)
        draw.rectangle([sx0, y0, sx1, y1], fill=seg_color)


def draw_heart_icon(draw, cx, y, color=(192, 132, 252)):
    pts = [
        (cx, y + 14),
        (cx - 6, y + 8),
        (cx - 7, y + 4),
        (cx - 5, y + 1),
        (cx - 2, y + 1),
        (cx, y + 4),
        (cx + 2, y + 1),
        (cx + 5, y + 1),
        (cx + 7, y + 4),
        (cx + 6, y + 8),
        (cx, y + 14)
    ]
    draw.polygon(pts, outline=color, fill=None)


def draw_up_arrow(draw, x, y, color=(168, 85, 247)):
    draw.polygon([(x+2, y), (x, y+5), (x+4, y+5)], fill=color)


def draw_down_arrow(draw, x, y, color=(168, 85, 247)):
    draw.polygon([(x, y), (x+4, y), (x+2, y+5)], fill=color)


def draw_fan_value(draw, right_x, y, rpm, value_font, unit_font, compact_font, value_color, unit_color):
    if rpm is None:
        text = "N/A"
        width = math.ceil(draw.textlength(text, font=value_font))
        left_x = right_x - width
        draw.text((left_x, y), text, fill=value_color, font=value_font)
        return left_x, right_x

    number = str(rpm) if rpm < 10_000 else f"{min(99, round(rpm / 1000))}K"
    gap = 3
    number_width = math.ceil(draw.textlength(number, font=value_font))
    unit_width = math.ceil(draw.textlength("RPM", font=unit_font))
    total_width = number_width + gap + unit_width

    if total_width <= 55:
        left_x = right_x - total_width
        draw.text((left_x, y), number, fill=value_color, font=value_font)
        draw.text((left_x + number_width + gap, y + 5), "RPM", fill=unit_color, font=unit_font)
    else:
        text = f"{number} RPM"
        width = math.ceil(draw.textlength(text, font=compact_font))
        left_x = right_x - width
        draw.text((left_x, y + 2), text, fill=value_color, font=compact_font)
    return left_x, right_x


def format_network_rate(rate_mb_s: float) -> str:
    rate = max(0.0, rate_mb_s)
    if rate < 100:
        return f"{rate:.1f}"
    if rate < 1000:
        return f"{rate:.0f}"
    return f"{min(99.9, rate / 1000):.1f}K"


def format_uptime(uptime_seconds: int) -> tuple[str, str]:
    seconds = max(0, uptime_seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    if days >= 1000:
        return f"{days / 365.25:.1f}y", f"{hours}h {minutes}m"
    return f"{days}d {hours}h", f"{minutes}m"


def draw_wide_center_dot_matrix_visualizer(draw, x_start, y_base, per_core, color=(168, 85, 247)):
    num_cols = 28
    core_levels = [max(0.0, min(100.0, float(value))) for value in (per_core or [0.0])]

    for col_idx in range(num_cols):
        col_x = x_start + col_idx * 4

        if len(core_levels) == 1:
            core_val = core_levels[0]
        else:
            source_pos = col_idx * (len(core_levels) - 1) / (num_cols - 1)
            left_idx = int(source_pos)
            right_idx = min(left_idx + 1, len(core_levels) - 1)
            blend = source_pos - left_idx
            core_val = (
                core_levels[left_idx] * (1.0 - blend)
                + core_levels[right_idx] * blend
            )
        load_factor = max(0.0, min(1.0, core_val / 100.0))
        dots_count = max(1, min(8, int(load_factor * 8.0) + 1))
        
        for dot_i in range(dots_count):
            dot_y = y_base - dot_i * 3
            dot_color = (255, 255, 255) if dot_i == dots_count - 1 and dots_count > 3 else color
            draw.ellipse([col_x - 1, dot_y - 1, col_x + 1, dot_y + 1], fill=dot_color)


def draw_quantum_breathing_pulse_core(draw, cx, cy, monotonic_time, is_warning=False):
    num_dots = 48
    pulse = 0.5 + 0.5 * math.sin(monotonic_time * (2 * math.pi / 2.4))
    
    for i in range(num_dots):
        dot_angle = i * (2 * math.pi / num_dots)
        cos_a = math.cos(dot_angle)
        sin_a = math.sin(dot_angle)
        is_cardinal = (i % (num_dots // 4) == 0)

        for step, r in enumerate([73, 78, 83, 88]):
            dx = int(cx + r * cos_a)
            dy = int(cy + r * sin_a)
            layer_pulse = pulse if step in [1, 2] else (1.0 - pulse)
            
            if is_cardinal:
                base_c = (192, 132, 252)
                glow_c = (255, 255, 255)
            else:
                if step == 0: base_c = (110, 55, 175)
                elif step == 1: base_c = (70, 25, 120)
                elif step == 2: base_c = (40, 10, 75)
                else: base_c = (18, 4, 40)
                glow_c = (168, 85, 247)
                
            if is_warning:
                glow_c = (245, 158, 11)
                
            r_c = int(base_c[0] * (1.0 - layer_pulse * 0.5) + glow_c[0] * (layer_pulse * 0.5))
            g_c = int(base_c[1] * (1.0 - layer_pulse * 0.5) + glow_c[1] * (layer_pulse * 0.5))
            b_c = int(base_c[2] * (1.0 - layer_pulse * 0.5) + glow_c[2] * (layer_pulse * 0.5))
            
            draw.ellipse([dx - 1, dy - 1, dx + 1, dy + 1], fill=(r_c, g_c, b_c))


def create_clean_base_bg():
    bg = Image.new("RGB", (W, H), (7, 7, 20))
    d = ImageDraw.Draw(bg)
    d.rounded_rectangle([12, 44, 240, 238], radius=8, fill=(12, 13, 30), outline=(25, 27, 55), width=1)
    d.line([(12, 44), (12, 238)], fill=(120, 60, 220), width=1)
    for y_joint in [44, 92, 140, 188, 238]:
        d.ellipse([10, y_joint - 2, 14, y_joint + 2], fill=(168, 85, 247))
    d.line([(14, 92), (238, 92)], fill=(25, 27, 55), width=1)
    d.line([(14, 140), (238, 140)], fill=(25, 27, 55), width=1)
    d.line([(14, 188), (238, 188)], fill=(25, 27, 55), width=1)

    d.rounded_rectangle([12, 244, 468, 312], radius=8, fill=(12, 13, 30), outline=(25, 27, 55), width=1)
    for div_x in [108, 252, 356]:
        d.line([(div_x, 255), (div_x, 301)], fill=(27, 30, 58), width=1)
    return bg


class Nexus26:
    def __init__(self):
        self.assets=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'nexus26_assets'
        self.base_bg=create_clean_base_bg()
        self.cpu_history=[0.0]*24
        self.gpu_history=[None]*24
        self.smooth_per_core=[]
        self.fonts={}
        for name,size,filename in [
            ('fTitle',18,'Roboto-Bold.ttf'),('fHeaderTime',30,'Roboto-Bold.ttf'),
            ('fBigVal',24,'Roboto-Bold.ttf'),('fCardVal',14,'Roboto-Bold.ttf'),
            ('fSystemGood',32,'Roboto-Bold.ttf'),('fMedium',12,'Roboto-Bold.ttf'),
            ('fSmall',11,'Roboto-Regular.ttf'),('fMicro',10,'Roboto-Bold.ttf'),
            ('fNano',9,'Roboto-Regular.ttf')]:
            try:self.fonts[name]=ImageFont.truetype(str(self.assets/filename),size)
            except OSError:self.fonts[name]=ImageFont.load_default()
        self.logo=Image.open(self.assets/'windows_logo.png').convert('RGBA')

    def render(self,data):
        def num(key,default=0):
            try:
                v=data.get(key)
                return float(v) if v is not None else default
            except (TypeError,ValueError):return default
        def gb(key):return num(key)/(1024**3)
        cpu=int(num('cpu'))
        gpu=int(num('gpu_load')) if data.get('gpu_load') is not None else None
        rp=int(num('ram'))
        dp=int(num('disk'))
        cpu_temp='--' if data.get('cpu_temp') is None else f"{num('cpu_temp'):.0f}"
        gpu_temp='--' if data.get('gpu_temp') is None else f"{num('gpu_temp'):.0f}"
        per_core=(cpu,)
        self.cpu_history=(self.cpu_history+[cpu])[-24:]
        self.gpu_history=(self.gpu_history+[gpu])[-24:]
        if len(self.smooth_per_core)!=len(per_core):
            self.smooth_per_core=list(per_core)
        else:
            self.smooth_per_core=[a+(b-a)*.18 for a,b in zip(self.smooth_per_core,per_core)]
        cpu_history=self.cpu_history
        gpu_history=self.gpu_history
        smooth_per_core=self.smooth_per_core
        is_warn=(num('cpu_temp')>=95 or num('gpu_temp')>=95 or cpu>=95 or (gpu is not None and gpu>=95) or rp>=95)
        sys_status='HOT' if max(num('cpu_temp'),num('gpu_temp'))>=95 else 'HEAVY' if cpu>=95 or (gpu is not None and gpu>=95) else 'MEMORY' if rp>=95 else 'GOOD'
        sys_sub1,sys_sub2=('Thermal limit','approaching') if sys_status=='HOT' else ('Resource load','elevated') if sys_status=='HEAVY' else ('Memory use','critically high') if sys_status=='MEMORY' else ('All systems','operational')
        sys_color=(245,158,11) if is_warn else (192,132,252)
        WHITE=(255,255,255)
        PURPLE_NEON=(168,85,247)
        PURPLE_LIGHT=(192,132,252)
        GRAY_TEXT=(148,163,184)
        fTitle=self.fonts['fTitle']
        fHeaderTime=self.fonts['fHeaderTime']
        fBigVal=self.fonts['fBigVal']
        fCardVal=self.fonts['fCardVal']
        fSystemGood=self.fonts['fSystemGood']
        fMedium=self.fonts['fMedium']
        fSmall=self.fonts['fSmall']
        fMicro=self.fonts['fMicro']
        fNano=self.fonts['fNano']
        real_model=cpu_model().upper()
        real_os='Windows'
        os_logo_img=self.logo
        m_now=time.monotonic()
        rg=gb('ram_used')
        du=gb('disk_used')
        dt2=gb('disk_total')
        fan_rpm=int(num('gpu_fan')) if data.get('gpu_fan') is not None else None
        up=num('tx')/1048576
        dn=num('rx')/1048576
        us=int(time.monotonic())
        condition=str(data.get('weather_condition') or 'unknown')
        class Weather:
            pass
        weather_snapshot=Weather()
        weather_snapshot.temperature=(f"{num('weather_temp'):.0f}°C" if data.get('weather_temp') is not None else '--°C')
        weather_snapshot.description=condition.upper()[:14] if condition!='unknown' else 'NO DATA'
        cond=condition.lower()
        weather_snapshot.condition=('rain' if 'rain' in cond or 'shower' in cond else 'snow' if 'snow' in cond else 'clear' if 'clear' in cond or 'sun' in cond else 'cloudy')
        class Snapshot:
            pass
        snapshot=Snapshot()
        snapshot.gpu_percent=gpu
        snapshot.gpu_temp_c=data.get('gpu_temp')
        snapshot.ram_used_gb=rg
        snapshot.ram_total_gb=gb('ram_total')
        snapshot.disk_used_gb=du
        snapshot.disk_total_gb=dt2
        snapshot.fan_rpm=fan_rpm
        snapshot.net_up_mb_s=up
        snapshot.net_down_mb_s=dn
        snapshot.uptime_seconds=us
        img=self.base_bg.copy()
        d=ImageDraw.Draw(img)
        header_measure=ImageDraw.Draw(self.base_bg)
        viz_width=28*4
        viz_left_edge=50+int(header_measure.textlength(real_model,font=fTitle))+8
        viz_right_edge=int(468-header_measure.textlength('00:00',font=fHeaderTime))-8
        viz_x_start=((viz_left_edge+viz_right_edge)//2)-(viz_width//2)
        # ── 1. HEADER ──
        img.paste(os_logo_img, (12, 4), os_logo_img)
        d.text((50, 6), real_model, fill=WHITE, font=fTitle)
        d.text((50, 26), real_os, fill=GRAY_TEXT, font=fSmall)

        draw_wide_center_dot_matrix_visualizer(d, viz_x_start, 30, smooth_per_core, PURPLE_NEON)

        time_str = time.strftime("%H:%M")
        date_str = time.strftime("%a %d %b %Y").upper()
        w_time = d.textlength(time_str, font=fHeaderTime)
        d.text((468 - w_time, 0), time_str, fill=WHITE, font=fHeaderTime)
        w_date = d.textlength(date_str, font=fMicro)
        d.text((468 - w_date, 30), date_str, fill=PURPLE_NEON, font=fMicro)

        # ── 2. LEFT PANEL CARDS ──
        draw_cpu_icon(d, 20, 54, PURPLE_NEON)
        d.text((46, 48), "CPU", fill=GRAY_TEXT, font=fMicro)
        d.text((46, 60), f"{cpu}%", fill=WHITE, font=fBigVal)
        d.text((106, 48), f"{cpu_temp}°C" if cpu_temp != "--" else "--°C", fill=PURPLE_LIGHT, font=fMedium)
        draw_concept_smooth_wave_graph(d, [142, 52, 230, 86], cpu_history, line_color=PURPLE_LIGHT, fill_color=(50, 20, 85))

        gpu_temp = "--" if snapshot.gpu_temp_c is None else f"{snapshot.gpu_temp_c:.0f}"
        draw_gpu_icon(d, 20, 102, PURPLE_NEON)
        d.text((46, 96), "GPU", fill=GRAY_TEXT, font=fMicro)
        d.text((46, 108), f"{gpu}%" if snapshot.gpu_percent is not None else "N/A", fill=WHITE, font=fBigVal)
        d.text((106, 96), f"{gpu_temp}°C" if gpu_temp != "--" else "--°C", fill=PURPLE_LIGHT, font=fMedium)
        draw_concept_smooth_wave_graph(d, [142, 100, 230, 134], gpu_history, line_color=PURPLE_LIGHT, fill_color=(50, 20, 85))

        rg = snapshot.ram_used_gb
        draw_ram_icon(d, 20, 150, PURPLE_NEON)
        d.text((46, 144), "RAM", fill=GRAY_TEXT, font=fMicro)
        d.text((46, 156), f"{rp}%", fill=WHITE, font=fBigVal)
        ram_text = f"{rg:.1f} / {snapshot.ram_total_gb:.0f} GiB"
        w_ram = d.textlength(ram_text, font=fMedium)
        d.text((230 - w_ram, 144), ram_text, fill=PURPLE_LIGHT, font=fMedium)
        draw_concept_rgb_pill_bar(d, [108, 166, 230, 175], rp)

        du = snapshot.disk_used_gb
        dt2 = snapshot.disk_total_gb
        draw_ssd_icon(d, 20, 198, PURPLE_NEON)
        d.text((46, 192), "SSD", fill=GRAY_TEXT, font=fMicro)
        d.text((46, 204), f"{dp}%", fill=WHITE, font=fBigVal)
        ssd_text = f"{du:.0f} / {dt2:.0f} GB"
        w_ssd = d.textlength(ssd_text, font=fMedium)
        d.text((230 - w_ssd, 192), ssd_text, fill=PURPLE_LIGHT, font=fMedium)
        draw_concept_rgb_pill_bar(d, [108, 214, 230, 223], dp)

        # ── 3. RIGHT QUANTUM BREATHING PULSE CORE RING ──
        rcx, rcy = 360, 142
        draw_quantum_breathing_pulse_core(d, rcx, rcy, m_now, is_warning=is_warn)
        draw_centered_text(d, rcx, 83, "SYSTEM", fMicro, sys_color)
        d.fontmode = "1"
        status_font = fSystemGood if len(sys_status) <= 5 else fBigVal
        draw_centered_text(d, rcx, 98, sys_status, status_font, WHITE)
        d.fontmode = "L"
        draw_centered_text(d, rcx, 137, sys_sub1, fMicro, GRAY_TEXT)
        draw_centered_text(d, rcx, 148, sys_sub2, fMicro, GRAY_TEXT)
        draw_heart_icon(d, rcx, 162, sys_color)

        # ── 4. BOTTOM UTILITY BAR CARDS ──
        fan_rpm = snapshot.fan_rpm
        fan_status = "NO SENSOR" if fan_rpm is None else ("SILENT" if fan_rpm == 0 else "ACTIVE")
        draw_concept_fan_icon(d, 22, 266, PURPLE_NEON)
        d.text((54, 257), "FAN", fill=PURPLE_LIGHT, font=fMicro)
        draw_fan_value(d, 104, 271, fan_rpm, fCardVal, fNano, fMicro, WHITE, GRAY_TEXT)
        d.text((54, 289), fan_status, fill=PURPLE_LIGHT, font=fMicro)

        up = snapshot.net_up_mb_s
        dn = snapshot.net_down_mb_s
        draw_concept_network_icon(d, 120, 267, PURPLE_NEON)
        d.text((150, 257), "NETWORK", fill=PURPLE_LIGHT, font=fMicro)
        draw_up_arrow(d, 150, 273, PURPLE_NEON)
        d.text((157, 270), format_network_rate(up), fill=WHITE, font=fCardVal)
        draw_down_arrow(d, 198, 273, PURPLE_NEON)
        d.text((205, 270), format_network_rate(dn), fill=WHITE, font=fCardVal)
        d.text((157, 288), "MB/s", fill=GRAY_TEXT, font=fNano)
        d.text((205, 288), "MB/s", fill=GRAY_TEXT, font=fNano)

        us = snapshot.uptime_seconds
        ust_h, ust_m = format_uptime(us)
        draw_concept_clock_icon(d, 264, 266, PURPLE_NEON)
        d.text((294, 257), "UPTIME", fill=PURPLE_LIGHT, font=fMicro)
        d.text((294, 271), ust_h, fill=WHITE, font=fCardVal)
        d.text((294, 289), ust_m, fill=WHITE, font=fCardVal)

        draw_concept_weather_icon(d, 366, 266, weather_snapshot.condition)
        d.text((398, 257), "WEATHER", fill=PURPLE_LIGHT, font=fMicro)
        d.text((398, 271), weather_snapshot.temperature, fill=WHITE, font=fCardVal)
        d.text((398, 289), weather_snapshot.description, fill=GRAY_TEXT, font=fNano)

        return img
