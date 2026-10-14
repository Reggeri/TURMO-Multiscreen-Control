"""Portable TURMO theme bundles (.turmo). No executable code is imported."""
import copy
import json
import os
import shutil
import uuid
import zipfile
from pathlib import Path

EXTENSIONS={'.mp4','.png','.jpg','.jpeg','.bmp','.webp'}
MAX_MEDIA=500*1024*1024
MAX_CONFIG=64*1024
THEME_DIR=Path(os.environ.get('APPDATA') or Path.home())/'TURMO-Control'/'imported_themes'

class ThemePackageError(ValueError):
    pass

def _validate(config):
    if not isinstance(config,dict):raise ThemePackageError('Invalid theme layout')
    if not isinstance(config.get('widgets'),list) or len(config['widgets'])>60:raise ThemePackageError('Invalid widgets')
    result={'background':config.get('background','#101827'),'media':'','fps':config.get('fps',5),'widgets':[]}
    if not isinstance(result['background'],str) or len(result['background'])>32:raise ThemePackageError('Invalid background')
    try:result['fps']=max(1,min(20,int(result['fps'])))
    except (TypeError,ValueError):raise ThemePackageError('Invalid FPS')
    for item in config['widgets']:
        if not isinstance(item,dict):raise ThemePackageError('Invalid widget')
        try:
            widget={'key':str(item.get('key','cpu'))[:40],
                    'label':str(item.get('label',''))[:60],
                    'x':max(0,min(480,int(item.get('x',0)))),
                    'y':max(0,min(320,int(item.get('y',0)))),
                    'size':max(9,min(70,int(item.get('size',24)))),
                    'color':str(item.get('color','#ffffff'))[:32],
                    'font':str(item.get('font','Segoe UI'))[:40],
                    'label_size':max(8,min(40,int(item.get('label_size',13))))}
        except (TypeError,ValueError):raise ThemePackageError('Invalid widget properties')
        result['widgets'].append(widget)
    return result

def export_theme(config, destination):
    clean=_validate(config)
    media=str(config.get('media','') or '')
    source=Path(media) if media else None
    if source:
        if source.suffix.lower() not in EXTENSIONS or not source.is_file():raise ThemePackageError('Background media file missing or unsupported')
        if source.stat().st_size>MAX_MEDIA:raise ThemePackageError('Media exceeds 500 MB')
        clean['media']='media'+source.suffix.lower()
    clean['format']='turmo-theme';clean['version']=1
    payload=json.dumps(clean,ensure_ascii=False,indent=2).encode('utf-8')
    if len(payload)>MAX_CONFIG:raise ThemePackageError('Theme settings too large')
    destination=Path(destination)
    if destination.suffix.lower()!='.turmo':destination=destination.with_suffix('.turmo')
    with zipfile.ZipFile(destination,'w') as archive:
        archive.writestr('theme.json',payload,compress_type=zipfile.ZIP_DEFLATED)
        if source:
            # Video already compressed; avoid wasting CPU and disk during export.
            archive.write(source,clean['media'],compress_type=zipfile.ZIP_STORED)
    return destination

def import_theme(source):
    source=Path(source)
    try:
        with zipfile.ZipFile(source,'r') as archive:
            entries=archive.infolist()
            if len(entries)>2:raise ThemePackageError('Unexpected files in theme package')
            names={entry.filename for entry in entries}
            if 'theme.json' not in names:raise ThemePackageError('Missing theme.json')
            entry=archive.getinfo('theme.json')
            if entry.file_size>MAX_CONFIG:raise ThemePackageError('Theme settings too large')
            raw=archive.read(entry)
            config=json.loads(raw.decode('utf-8'))
            if config.get('format')!='turmo-theme' or config.get('version')!=1:raise ThemePackageError('Unsupported theme version')
            clean=_validate(config)
            media=config.get('media','')
            if media:
                if not isinstance(media,str) or not media.startswith('media.') or '/' in media or chr(92) in media or Path(media).suffix.lower() not in EXTENSIONS:
                    raise ThemePackageError('Invalid media name')
                if names!={'theme.json',media}:raise ThemePackageError('Unexpected package contents')
                media_info=archive.getinfo(media)
                if media_info.file_size>MAX_MEDIA:raise ThemePackageError('Media exceeds 500 MB')
                # Extract only a fixed filename, never a path supplied by the archive.
                folder=THEME_DIR/uuid.uuid4().hex
                folder.mkdir(parents=True,exist_ok=False)
                target=folder/media
                try:
                    with archive.open(media) as input_file, target.open('wb') as output:
                        shutil.copyfileobj(input_file,output,length=1024*1024)
                    clean['media']=str(target)
                except Exception:
                    shutil.rmtree(folder,ignore_errors=True)
                    raise
            elif names!={'theme.json'}:raise ThemePackageError('Unexpected package contents')
            return clean
    except (zipfile.BadZipFile,UnicodeDecodeError,json.JSONDecodeError,KeyError,OSError) as exc:
        raise ThemePackageError('Cannot read theme package: '+str(exc)) from exc
