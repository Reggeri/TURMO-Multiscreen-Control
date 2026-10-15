"""LAN-only companion web UI for TURMO. No external service or cloud."""
import html
import os
from pathlib import Path
import io
import json
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from PIL import Image

PORT = 8765
THEME_WHITELIST = ()

def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('192.0.2.1', 80))
        return s.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        s.close()

class PreviewCache:
    """Latest actual screen frames. JPEG is encoded only when a paired phone requests it."""
    def __init__(self):
        self.lock = threading.Lock()
        self.frames = [None, None]
        self.revisions = [0, 0]
        self.jpeg = [None, None]
        self.jpeg_time = [0., 0.]
        self.jpeg_revision = [-1, -1]

    def publish(self, index, frame):
        if index not in (0, 1):
            return
        with self.lock:
            self.frames[index] = frame  # immutable after render; no copying or encoding
            self.revisions[index] += 1

    def clear(self):
        with self.lock:
            self.frames = [None, None]
            self.jpeg = [None, None]
            self.jpeg_revision = [-1, -1]

    def get(self, index):
        now = time.monotonic()
        with self.lock:
            frame = self.frames[index]
            revision = self.revisions[index]
            if frame is None:
                return None
            # Maximum one JPEG encoding per display per 1.5 seconds.
            if self.jpeg[index] is not None and (now - self.jpeg_time[index] < 1.5 or self.jpeg_revision[index] == revision):
                return self.jpeg[index]
            # Encoding while locked avoids duplicate work from multiple phones.
            out = io.BytesIO()
            frame.convert('RGB').save(out, 'JPEG', quality=58, optimize=False)
            self.jpeg[index] = out.getvalue()
            self.jpeg_time[index] = now
            self.jpeg_revision[index] = revision
            return self.jpeg[index]


class RemoteServer:
    def __init__(self, submit, themes, previews=None):
        self.submit = submit
        self.themes = list(themes)
        self.previews = previews
        self.pin = f'{secrets.randbelow(1000000):06d}'
        self.sessions = {}  # random opaque session token -> last activity timestamp
        self.failures = {}  # IP -> recent invalid pairing attempts
        self.httpd = None
        self.thread = None

    def start(self):
        remote = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                pass
            def _reply(self, status, payload, content_type='application/json; charset=utf-8', cookie=None):
                data = payload if isinstance(payload, bytes) else (payload.encode('utf-8') if isinstance(payload, str) else json.dumps(payload).encode('utf-8'))
                self.send_response(status)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")
                if cookie:self.send_header('Set-Cookie',cookie)
                self.end_headers()
                self.wfile.write(data)
            def _auth(self):
                raw=self.headers.get('Cookie','')
                token=next((v[6:] for v in raw.split('; ') if v.startswith('turmo=')),None)
                now=time.time()
                with remote.lock:
                    remote.sessions={k:v for k,v in remote.sessions.items() if now-v<86400}
                    if token in remote.sessions:
                        remote.sessions[token]=now
                        return True
                return False
            def do_GET(self):
                if urlparse(self.path).path == '/':
                    self._reply(200, PAGE, 'text/html; charset=utf-8')
                elif urlparse(self.path).path.startswith('/api/preview/'):
                    if not self._auth():
                        return self._reply(401, {'error':'Pair first'})
                    tail=urlparse(self.path).path.rsplit('/', 1)[-1]
                    if tail not in ('0', '1') or remote.previews is None:
                        return self._reply(404, {'error':'No preview'})
                    data=remote.previews.get(int(tail))
                    if data is None:
                        return self._reply(404, {'error':'Display inactive'})
                    self._reply(200, data, 'image/jpeg')
                elif urlparse(self.path).path == '/api/status':
                    self._reply(200, {'authenticated':self._auth(),'themes':remote.themes if self._auth() else []})
                else:self._reply(404,{'error':'Not found'})
            def do_POST(self):
                if self.headers.get('Origin') not in (None, f'http://{self.headers.get("Host", "")}'):
                    return self._reply(403,{'error':'Origin mismatch'})
                path=urlparse(self.path).path
                if path=='/api/upload-image':
                    if not self._auth():return self._reply(401,{'error':'Pair first'})
                    if self.headers.get('Content-Type','').split(';')[0]!='image/jpeg' and self.headers.get('Content-Type','').split(';')[0]!='image/png':
                        return self._reply(415,{'error':'Only JPEG or PNG'})
                    try:
                        size=int(self.headers.get('Content-Length','0'))
                        index=int(self.headers.get('X-Display','-1'))
                        if not 0<size<=8*1024*1024 or index not in (0,1):raise ValueError()
                        raw=self.rfile.read(size)
                        from PIL import ImageOps
                        with Image.open(io.BytesIO(raw)) as img:
                            img.load()
                            if img.width*img.height>20000000:raise ValueError()
                            img=ImageOps.exif_transpose(img).convert('RGB')
                            # Bound stored image resolution and CPU costs.
                            img.thumbnail((1920,1280),Image.Resampling.LANCZOS)
                            folder=Path(os.environ.get('APPDATA') or Path.home())/'TURMO-Control'/'phone_images'
                            folder.mkdir(parents=True,exist_ok=True)
                            target=folder/f'display_{index}.jpg'
                            tmp=folder/f'display_{index}.tmp'
                            img.save(tmp,'JPEG',quality=86)
                            os.replace(tmp,target)
                        remote.submit({'action':'phone_image','display':index,'path':str(target)})
                        return self._reply(202,{'queued':True})
                    except (ValueError,TypeError,OSError,Image.DecompressionBombError):
                        return self._reply(400,{'error':'Invalid image or size'})
                try:
                    n=int(self.headers.get('Content-Length','0'))
                    if not 0<n<=4096:raise ValueError('Invalid length')
                    body=json.loads(self.rfile.read(n))
                    if not isinstance(body,dict):raise ValueError('Invalid data')
                except (ValueError,TypeError):return self._reply(400,{'error':'Invalid request'})
                if path=='/api/pair':
                    ip=self.client_address[0]
                    now=time.time()
                    with remote.lock:
                        attempts=[t for t in remote.failures.get(ip,[]) if now-t<300]
                        remote.failures[ip]=attempts
                        blocked=len(attempts)>=8
                    if blocked:return self._reply(429,{'error':'Too many attempts. Try later.'})
                    if str(body.get('pin',''))!=remote.pin:
                        with remote.lock:remote.failures[ip].append(time.time())
                        time.sleep(.35)
                        return self._reply(403,{'error':'Incorrect PIN'})
                    with remote.lock:remote.failures.pop(ip,None)
                    token=secrets.token_urlsafe(32)
                    with remote.lock:remote.sessions[token]=time.time()
                    return self._reply(200,{'ok':True},cookie=f'turmo={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400')
                if not self._auth():return self._reply(401,{'error':'Pair first'})
                action=body.get('action')
                if action=='theme':
                    if type(body.get('display')) is not int or body['display'] not in (0,1) or body.get('theme') not in remote.themes:
                        return self._reply(400,{'error':'Invalid theme/display'})
                elif action=='brightness':
                    if type(body.get('display')) is not int or body['display'] not in (0,1) or type(body.get('value')) is not int or not 0<=body['value']<=100:
                        return self._reply(400,{'error':'Invalid brightness'})
                elif action not in ('start','stop'):
                    return self._reply(400,{'error':'Invalid action'})
                remote.submit(body)
                self._reply(202,{'queued':True})
        self.lock=threading.Lock()
        self.httpd=ThreadingHTTPServer(('0.0.0.0',PORT),Handler)
        self.httpd.daemon_threads=True
        self.thread=threading.Thread(target=self.httpd.serve_forever,daemon=True)
        self.thread.start()
    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd=None
        with self.lock:self.sessions.clear()

PAGE=r"""<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta charset="utf-8"><title>TURMO Remote</title><style>
*{box-sizing:border-box}body{margin:0;background:#0b1220;color:#e9f2ff;font:15px system-ui,Arial}main{max-width:530px;margin:auto;padding:22px}h1{font-size:28px;margin:0}p{color:#9fb2cb}.card{background:#172438;border:1px solid #2b3e58;border-radius:19px;padding:18px;margin:18px 0}label{display:block;margin:13px 0 6px;color:#b2c6dd}select,input{width:100%;padding:12px;border:1px solid #37516e;border-radius:10px;background:#253750;color:white;font:inherit}button{border:0;border-radius:12px;padding:13px 18px;background:#4bbde9;color:#06101c;font-weight:700;margin:8px 8px 0 0;cursor:pointer}button.secondary{background:#31465f;color:white}input[type=range]{padding:0;accent-color:#4bbde9}.screen{width:100%;max-width:480px;aspect-ratio:3/2;object-fit:contain;border-radius:12px;background:#080e18;display:block;margin:10px auto}#message{min-height:24px;color:#88dcb7}.muted{color:#8ea6c2;font-size:12px}
</style></head><body><main><h1>TURMO <span style="color:#55c9f4">Remote</span></h1><p>Local Wi-Fi display controller</p><div id="pair" class="card"><h2>Pair your phone</h2><p>Enter the six-digit PIN shown in TURMO Control on your PC.</p><input id="pin" inputmode="numeric" maxlength="6" placeholder="6-digit PIN"><button onclick="pair()">Connect</button></div><div id="controls" style="display:none"><div id="displays"></div><div class="card"><button onclick="send({action:'start'})">Start displays</button><button class="secondary" onclick="send({action:'stop'})">Stop displays</button></div></div><p id="message"></p><p class="muted">Only available while TURMO Control runs on the same local network.</p></main><script>
const msg=document.getElementById('message');
async function request(path,data){let r=await fetch(path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});let v=await r.json();if(!r.ok)throw Error(v.error||'Request failed');return v}
async function pair(){try{await request('/api/pair',{pin:document.getElementById('pin').value});await init();msg.textContent='Paired successfully'}catch(e){msg.textContent=e.message}}
async function send(data){try{await request('/api/action',data);msg.textContent='Command sent'}catch(e){msg.textContent=e.message}}
async function init(){try{const s=await request('/api/status');if(!s.authenticated)return;document.getElementById('pair').style.display='none';document.getElementById('controls').style.display='block';let holder=document.getElementById('displays');holder.replaceChildren();for(let i=0;i<2;i++){let c=document.createElement('div');c.className='card';let h=document.createElement('h2');h.textContent='Display '+(i+1);c.append(h);
let image=document.createElement('img');image.className='screen';image.alt='Live preview for display '+(i+1);image.style.display='none';c.append(image);
let note=document.createElement('p');note.className='muted';note.textContent='Preview updates every 1.5s to save CPU';c.append(note);
function updateImage(){if(document.hidden)return;let url='/api/preview/'+i+'?t='+Date.now();let next=new Image();next.onload=()=>{image.src=url;image.style.display='block';note.style.display='none'};next.onerror=()=>{image.style.display='none';note.style.display='block'};next.src=url}
updateImage();setInterval(updateImage,1500);let label=document.createElement('label');label.textContent='Theme';c.append(label);let select=document.createElement('select');for(let theme of s.themes){let o=document.createElement('option');o.value=theme;o.textContent=theme;select.append(o)}select.onchange=()=>send({action:'theme',display:i,theme:select.value});c.append(select);let upLabel=document.createElement('label');upLabel.textContent='Send a photo to this display';c.append(upLabel);
let upload=document.createElement('input');upload.type='file';upload.accept='image/jpeg,image/png';c.append(upload);
let upButton=document.createElement('button');upButton.textContent='Send photo';upButton.onclick=async()=>{let file=upload.files[0];if(!file){msg.textContent='Choose a photo first';return}if(file.size>8*1024*1024){msg.textContent='Maximum 8 MB';return}try{let r=await fetch('/api/upload-image',{method:'POST',headers:{'Content-Type':file.type,'X-Display':String(i)},body:file});let v=await r.json();if(!r.ok)throw Error(v.error||'Upload failed');msg.textContent='Photo sent to display '+(i+1)}catch(e){msg.textContent=e.message}};c.append(upButton);
let bl=document.createElement('label');bl.textContent='Brightness';c.append(bl);let range=document.createElement('input');range.type='range';range.min=0;range.max=100;range.value=100;range.onchange=()=>send({action:'brightness',display:i,value:Number(range.value)});c.append(range);holder.append(c)}}catch(e){msg.textContent=e.message}}
init();</script></body></html>"""
