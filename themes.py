from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from hardware_info import cpu_model
W,H=480,320
NAVY=(8,15,27); BLUE=(62,200,250); RED=(255,78,92); WHITE=(241,246,252); MUTED=(151,169,191)

def font(size,bold=False):
    import os
    names=['segoeuib.ttf','arialbd.ttf'] if bold else ['segoeui.ttf','arial.ttf']
    names += ['DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf']
    for n in names:
        try:return ImageFont.truetype(os.path.join('C:/Windows/Fonts',n) if n.endswith('.ttf') and n.startswith('sego') or n.startswith('arial') else n,size)
        except OSError:pass
    return ImageFont.load_default()

def label(d,x,y,text,size=14,color=WHITE,bold=False):d.text((x,y),str(text),font=font(size,bold),fill=color)
def panel(d,rect,color):d.rounded_rectangle(rect,fill=color,radius=13)
def bar(d,x,y,width,pct,color):
    d.rounded_rectangle((x,y,x+width,y+9),radius=4,fill=(48,60,78))
    if pct is not None and pct>0:d.rounded_rectangle((x,y,x+max(5,int(width*min(100,max(0,pct))/100)),y+9),radius=4,fill=color)
def fmt(v,suffix='',dec=0):return f'{v:.{dec}f}{suffix}' if v is not None else '—'
def gib(v):return f'{v/1024**3:.1f} GB' if v is not None else '—'
def header(d,title,color,subtitle):
    d.rectangle((0,0,480,5),fill=color)
    label(d,16,12,title,20,color,True)
    label(d,16,39,subtitle,12,MUTED)
    label(d,407,15,datetime.now().strftime('%H:%M'),17,WHITE,True)

def system(s):
    im=Image.new('RGB',(W,H),NAVY);d=ImageDraw.Draw(im)
    header(d,'SYSTEM  /  MONITOR',BLUE,cpu_model().upper()[:44])
    panel(d,(14,65,234,181),(19,34,53));panel(d,(246,65,466,181),(19,34,53))
    label(d,28,77,'PROCESSOR',13,MUTED,True)
    label(d,28,95,fmt(s.get('cpu'),'%'),38,WHITE,True)
    label(d,28,145,fmt(s.get('cpu_temp'),'°C')+'   '+fmt(s.get('clock'),' MHz'),12,BLUE)
    bar(d,28,166,190,s.get('cpu'),BLUE)
    label(d,260,77,'MEMORY',13,MUTED,True)
    label(d,260,95,fmt(s.get('ram'),'%'),38,WHITE,True)
    label(d,260,145,gib(s.get('ram_used'))+' / '+gib(s.get('ram_total')),12,BLUE)
    bar(d,260,166,190,s.get('ram'),BLUE)
    panel(d,(14,193,466,292),(19,34,53))
    label(d,28,205,'SYSTEM DRIVE  /  C:',13,MUTED,True)
    label(d,28,227,fmt(s.get('disk'),'%'),31,WHITE,True)
    label(d,142,240,gib(s.get('disk_used'))+' / '+gib(s.get('disk_total')),14,BLUE)
    bar(d,28,274,422,s.get('disk'),BLUE)
    label(d,16,301,'TURMO CONTROL',11,MUTED)
    label(d,250,301,'NET  ↓ '+fmt(s.get('rx',0)/1024**2,' MB/s',1)+'  ↑ '+fmt(s.get('tx',0)/1024**2,' MB/s',1),11,MUTED)
    return im

def gpu(s):
    im=Image.new('RGB',(W,H),(20,11,20));d=ImageDraw.Draw(im)
    header(d,'GPU  /  GRAPHICS',RED,'AMD / NVIDIA / INTEL')
    panel(d,(14,65,466,163),(41,24,38))
    label(d,28,77,'GPU UTILIZATION',13,MUTED,True)
    label(d,28,98,fmt(s.get('gpu_load'),'%'),38,WHITE,True)
    label(d,253,88,'CORE CLOCK',12,MUTED,True)
    label(d,253,107,fmt(s.get('gpu_clock'),' MHz'),22,WHITE,True)
    bar(d,28,148,422,s.get('gpu_load'),RED)
    panel(d,(14,176,234,288),(41,24,38));panel(d,(246,176,466,288),(41,24,38))
    label(d,28,189,'TEMPERATURE',12,MUTED,True)
    label(d,28,210,fmt(s.get('gpu_temp'),'°C'),31,WHITE,True)
    label(d,28,261,'HOTSPOT   '+fmt(s.get('gpu_hotspot'),'°C'),14,RED,True)
    label(d,260,189,'BOARD POWER',12,MUTED,True)
    label(d,260,210,fmt(s.get('gpu_power'),' W'),31,WHITE,True)
    label(d,260,261,'FAN   '+fmt(s.get('gpu_fan'),' RPM'),14,RED,True)
    label(d,16,300,'TURMO CONTROL',11,MUTED)
    label(d,226,300,'VRAM   '+gib(s.get('gpu_vram_used')),12,MUTED)
    return im

def test_pattern():
    im=Image.new('RGB',(W,H));d=ImageDraw.Draw(im)
    for i,c in enumerate(((255,0,0),(0,255,0),(0,0,255),(255,255,255))):
        d.rectangle((i*120,0,(i+1)*120-1,319),fill=c)
    d.rectangle((70,110,410,210),fill=(0,0,0))
    label(d,105,135,'480 x 320  /  TEST',24,WHITE,True)
    return im


def neon_system(s):
    """Vivid purple/cyan theme with real system readings."""
    im=Image.new('RGB',(W,H),(13,8,30)); d=ImageDraw.Draw(im)
    purple=(184,101,255); cyan=(74,235,234)
    d.rectangle((0,0,W,5),fill=purple)
    label(d,18,16,'SYSTEM  //  NEON',23,purple,True)
    label(d,18,47,'LIVE TELEMETRY',12,MUTED)
    for x, name, value, pct, col in (
        (16,'CPU',fmt(s.get('cpu'),'%'),s.get('cpu'),purple),
        (246,'RAM',fmt(s.get('ram'),'%'),s.get('ram'),cyan)):
        panel(d,(x,76,x+218,199),(32,21,53))
        label(d,x+15,90,name,15,col,True)
        label(d,x+15,115,value,39,WHITE,True)
        bar(d,x+15,180,188,pct,col)
    label(d,30,212,'CPU TEMP',12,MUTED)
    label(d,30,234,fmt(s.get('cpu_temp'),'°C'),26,purple,True)
    label(d,244,212,'CPU CLOCK',12,MUTED)
    label(d,244,234,fmt(s.get('clock'),' MHz'),24,cyan,True)
    label(d,18,290,'SSD  '+fmt(s.get('disk'),'%')+'     NET ↓ '+fmt((s.get('rx') or 0)/1024**2,' MB/s',1),13,MUTED)
    return im

def neon_gpu(s):
    im=Image.new('RGB',(W,H),(17,9,29));d=ImageDraw.Draw(im)
    pink=(255,89,187);cyan=(76,224,246)
    d.rectangle((0,0,W,5),fill=pink)
    label(d,18,16,'GPU  //  NEON',23,pink,True)
    label(d,18,49,'GRAPHICS TELEMETRY',12,MUTED)
    panel(d,(16,75,464,170),(37,20,49))
    label(d,30,85,'GPU LOAD',14,MUTED,True)
    label(d,30,108,fmt(s.get('gpu_load'),'%'),37,WHITE,True)
    label(d,258,88,'CORE CLOCK',12,MUTED)
    label(d,258,112,fmt(s.get('gpu_clock'),' MHz'),23,cyan,True)
    bar(d,30,151,417,s.get('gpu_load'),pink)
    for x,title,value in (
        (16,'GPU TEMP',fmt(s.get('gpu_temp'),'°C')),
        (246,'HOTSPOT',fmt(s.get('gpu_hotspot'),'°C'))):
        panel(d,(x,183,x+218,263),(37,20,49))
        label(d,x+14,193,title,12,MUTED)
        label(d,x+14,216,value,29,cyan,True)
    label(d,20,280,'POWER  '+fmt(s.get('gpu_power'),' W'),14,pink,True)
    label(d,259,280,'VRAM  '+gib(s.get('gpu_vram_used')),13,MUTED)
    return im

def minimal_system(s):
    im=Image.new('RGB',(W,H),(17,24,32));d=ImageDraw.Draw(im)
    label(d,20,15,'SYSTEM',25,WHITE,True)
    d.line((20,55,460,55),fill=(73,89,101),width=2)
    for i,(name,value,pct) in enumerate((
        ('CPU',fmt(s.get('cpu'),'%'),s.get('cpu')),
        ('RAM',fmt(s.get('ram'),'%'),s.get('ram')),
        ('SSD',fmt(s.get('disk'),'%'),s.get('disk')))):
        y=73+i*75
        label(d,22,y,name,17,MUTED,True)
        label(d,355,y,value,22,WHITE,True)
        bar(d,22,y+34,436,pct,(109,210,175))
    label(d,22,296,'TEMP '+fmt(s.get('cpu_temp'),'°C')+'    CLOCK '+fmt(s.get('clock'),' MHz'),12,MUTED)
    return im

def minimal_gpu(s):
    im=Image.new('RGB',(W,H),(17,24,32));d=ImageDraw.Draw(im)
    label(d,20,15,'GRAPHICS',25,WHITE,True)
    d.line((20,55,460,55),fill=(73,89,101),width=2)
    metrics=[
        ('LOAD',fmt(s.get('gpu_load'),'%')),
        ('TEMP',fmt(s.get('gpu_temp'),'°C')),
        ('HOTSPOT',fmt(s.get('gpu_hotspot'),'°C')),
        ('POWER',fmt(s.get('gpu_power'),' W')),
        ('CLOCK',fmt(s.get('gpu_clock'),' MHz'))]
    for i,(name,value) in enumerate(metrics):
        y=72+i*43
        label(d,22,y,name,16,MUTED,True)
        label(d,292,y,value,20,(109,210,175),True)
    label(d,22,297,'VRAM '+gib(s.get('gpu_vram_used')),12,MUTED)
    return im
