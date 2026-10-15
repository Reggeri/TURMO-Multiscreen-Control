"""Interactive 480x320 editor: drag text fields, image/MP4 background and colors."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
from themes import font

FIELDS=['time','date','cpu','cpu_temp','clock','ram','ram_used','disk','gpu_load','gpu_temp','gpu_hotspot','gpu_clock','gpu_power','gpu_fan','gpu_vram_used','rx','tx','weather_temp','weather_feels','weather_humidity','weather_wind','weather_condition','weather_city']
UNITS={'cpu':'%','cpu_temp':'°C','clock':' MHz','ram':'%','disk':'%',
       'gpu_load':'%','gpu_temp':'°C','gpu_hotspot':'°C','gpu_clock':' MHz',
       'gpu_power':' W','gpu_fan':' RPM','weather_temp':'°C','weather_feels':'°C','weather_humidity':'%','weather_wind':' km/h'}

def default_layout():
    return {'background':'#101827','media':'','fps':20,'widgets':[
        {'key':'cpu','x':24,'y':45,'size':32,'color':'#ffffff','label':'CPU'},
        {'key':'gpu_temp','x':24,'y':112,'size':28,'color':'#60d4ef','label':'GPU TEMP'},
        {'key':'ram','x':24,'y':182,'size':28,'color':'#ffffff','label':'RAM'}]}

FONTS={'Segoe UI':'segoeui.ttf','Arial':'arial.ttf','Consolas':'consola.ttf','Verdana':'verdana.ttf','Tahoma':'tahoma.ttf'}
def widget_font(name,size,bold=False):
    from pathlib import Path
    candidate=FONTS.get(name,'segoeui.ttf')
    path=Path('C:/Windows/Fonts')/candidate
    try:return ImageFont.truetype(str(path),size)
    except OSError:return font(size,bold)

def fit_background(image, config):
    """Transform static or video media to 480x320, with editable crop and placement."""
    mode=config.get('media_fit','cover')
    image=image.convert('RGB')
    if mode=='stretch':return image.resize((480,320),Image.Resampling.LANCZOS)
    if mode=='contain':
        canvas=Image.new('RGB',(480,320),config.get('background','#101827'))
        thumb=ImageOps.contain(image,(480,320),Image.Resampling.LANCZOS)
        canvas.paste(thumb,((480-thumb.width)//2,(320-thumb.height)//2))
        return canvas
    zoom=max(1.,min(4.,float(config.get('media_zoom',1.0))))
    ratio=max(480/image.width,320/image.height)*zoom
    w=max(480,round(image.width*ratio));h=max(320,round(image.height*ratio))
    scaled=image.resize((w,h),Image.Resampling.LANCZOS)
    # 0..100 is the position of the image inside its overflow (50=center).
    px=max(0.,min(1.,float(config.get('media_x',50))/100))
    py=max(0.,min(1.,float(config.get('media_y',50))/100))
    left=round((w-480)*px);top=round((h-320)*py)
    return scaled.crop((left,top,left+480,top+320))

def render(config,values,background=None):
    from themes import fmt,gib
    if background is not None:
        im=fit_background(background,config)
    else:
        try:im=Image.new('RGB',(480,320),config.get('background','#101827'))
        except ValueError:im=Image.new('RGB',(480,320),'#101827')
    d=ImageDraw.Draw(im)
    for w in config.get('widgets',[]):
        key=w.get('key','cpu');v=values.get(key)
        if key == 'time':
            from datetime import datetime
            value=datetime.now().strftime('%H:%M:%S')
        elif key == 'date':
            from datetime import datetime
            value=datetime.now().strftime('%Y.%m.%d')
        elif key in ('weather_condition','weather_city'):value=str(v) if v is not None else '—'
        elif key in ('ram_used','gpu_vram_used'):value=gib(v)
        elif key in ('rx','tx'):value=fmt(v/1024**2 if v is not None else None,' MB/s',1)
        else:value=fmt(v,UNITS.get(key,''))
        x=int(w.get('x',10));y=int(w.get('y',10));size=max(9,min(70,int(w.get('size',24))))
        color=w.get('color','#ffffff');label=str(w.get('label',key.upper()))
        family=w.get('font','Segoe UI');label_size=max(8,min(40,int(w.get('label_size',13))))
        try:d.text((x,y),label,font=widget_font(family,label_size,True),fill=color)
        except ValueError:pass
        try:d.text((x,y+label_size+4),value,font=widget_font(family,size,True),fill=color)
        except ValueError:pass
    return im

def load_background(config):
    path=config.get('media','')
    if not path or Path(path).suffix.lower()=='.mp4':return None
    try:
        with Image.open(path) as im:
            from PIL import ImageOps
            return im.convert('RGB').copy()
    except (OSError,ValueError):return None
