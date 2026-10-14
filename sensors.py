"""Windows telemetry: psutil and optional LibreHardwareMonitor/OpenHardwareMonitor WMI.
Never invent readings. WMI must be used from a COM-initialized thread.
"""
import os
import ctypes
import struct
import re
import time
import psutil

NAMESPACES = (r'root\LibreHardwareMonitor', r'root\OpenHardwareMonitor')

import json
import subprocess
import sys
import threading
import queue
from pathlib import Path

class EmbeddedSensors:
    """Read JSON lines from bundled, self-contained LibreHardwareMonitorLib bridge.
    No external installation, no WMI namespace, no download, no setup button.
    """
    def __init__(self):
        self.rows = []
        self.error = ''
        self.lock = threading.Lock()
        self.proc = None
        self.retry_at = 0
        self.last_diagnostic = ''
        self._launch()

    def _path(self):
        root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        return root / 'SensorBridge.exe'

    def _launch(self):
        path = self._path()
        if not path.is_file():
            self.error = 'Embedded SensorBridge.exe missing: rebuild using build_windows.bat'
            self.retry_at = time.monotonic() + 15
            return
        try:
            self.proc = subprocess.Popen([str(path)], stdout=subprocess.PIPE,
                stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.error = ''
            threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
        except Exception as exc:
            self.error = 'Embedded sensor start failed: ' + str(exc)
            self.retry_at = time.monotonic() + 15

    def _read(self, proc):
        try:
            for line in proc.stdout:
                try:
                    obj = json.loads(line)
                    if 'error' in obj:
                        with self.lock: self.error = obj['error']
                        continue
                    rows = []
                    for r in obj.get('sensors', []):
                        rows.append((str(r['name']).lower(), str(r['identifier']).lower(),
                            str(r['type']).lower(), float(r['value']),
                            str(r.get('hardwareType', '')).lower(),
                            str(r.get('hardwareName', ''))))
                    with self.lock:
                        self.rows = rows
                        self.error = ''
                    self._save_gpu_diagnostics(rows)
                    self._save_cpu_diagnostics(rows)
                except (ValueError, KeyError, TypeError):
                    continue
        finally:
            with self.lock:
                self.rows = []
                self.error = 'Embedded sensor process stopped'
                self.retry_at = time.monotonic() + 10

    def _save_gpu_diagnostics(self, rows):
        """Write actual discovered GPU sensors to a local diagnostic file."""
        try:
            gpu_rows = [r for r in rows if is_gpu_sensor(r)]
            lines = ['TURMO GPU diagnostics - detected sensor values',
                     'GPU sensor count: ' + str(len(gpu_rows)),
                     'If zero, the bundled LHM library/driver is not exposing GPU sensors.',
                     '']
            for name, ident, typ, value, hw_type, hw_name in gpu_rows:
                lines.append(f'{hw_name} [{hw_type}] | {ident} | {typ} | {name} = {value}')
            report = '\\n'.join(lines) + '\\n'
            if report == self.last_diagnostic:
                return
            self.last_diagnostic = report
            path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'TURMO-Control' / 'gpu-diagnostics.txt'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report, encoding='utf-8')
        except (OSError, ValueError):
            pass

    def _save_cpu_diagnostics(self, rows):
        """Write raw CPU and temperature sensors for diagnosis; no fake values."""
        try:
            lines = ['TURMO CPU temperature diagnostics',
                     'Total sensor count: ' + str(len(rows)),
                     'CPU/temperature sensors:']
            matches = [r for r in rows if (r[2] == 'temperature' or
                       r[4].lower().startswith('cpu') or
                       any(x in r[1] for x in ('/cpu/', '/amdcpu/', '/intelcpu/')))]
            for name, ident, typ, value, hw_type, hw_name in matches:
                lines.append(f'{hw_name} [{hw_type}] | {ident} | {typ} | {name} = {value}')
            if not matches:
                lines.append('NO CPU OR TEMPERATURE SENSORS REPORTED')
            report = '\n'.join(lines) + '\n'
            if report == getattr(self, 'last_cpu_diagnostic', None):
                return
            self.last_cpu_diagnostic = report
            path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'TURMO-Control' / 'cpu-diagnostics.txt'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(report, encoding='utf-8')
        except (OSError, ValueError):
            pass

    def get(self):
        if (self.proc is None or self.proc.poll() is not None) and time.monotonic() >= self.retry_at:
            self._launch()
        with self.lock:
            return list(self.rows), self.error

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

def core_temp_shared_temperature():
    """Optional fallback: read Core Temp's documented Windows shared memory.

    Requires the separate Core Temp application to be running. No Core Temp
    DLL or Python package is required. Never create a mapping or fake values.
    """
    if os.name != 'nt':
        return None
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
    kernel.OpenFileMappingW.restype = ctypes.c_void_p
    kernel.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                     ctypes.c_uint32, ctypes.c_size_t]
    kernel.MapViewOfFile.restype = ctypes.c_void_p
    kernel.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    kernel.UnmapViewOfFile.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    # CoreTempMappingObjectEx retains the legacy structure at its start.
    for mapping_name in ('CoreTempMappingObjectEx', 'CoreTempMappingObject'):
        handle = kernel.OpenFileMappingW(0x0004, 0, mapping_name)  # FILE_MAP_READ
        if not handle:
            continue
        try:
            ptr = kernel.MapViewOfFile(handle, 0x0004, 0, 0, 0)
            if not ptr:
                continue
            try:
                # uiLoad[256], uiTjMax[128], uiCoreCnt, uiCPUCnt, fTemp[256].
                # All offsets are 4-byte aligned in Core Temp's C SDK.
                count, cpus = struct.unpack_from('<II', ctypes.string_at(ptr, 1544), 1536)
                if not (1 <= count <= 256 and 1 <= cpus <= 128):
                    continue
                raw = ctypes.string_at(ptr + 1544, min(count, 256)*4)
                temps = struct.unpack('<'+'f'*count, raw)
                flags = ctypes.string_at(ptr + 1544 + 1024 + 16 + 100, 2)
                fahrenheit, delta = flags[0], flags[1]
                tjmax = struct.unpack('<I', ctypes.string_at(ptr+1024, 4))[0]
                valid=[]
                for t in temps:
                    if not (-100 < t < 300):
                        continue
                    if delta:
                        if not (50 <= tjmax <= 125): continue
                        t = tjmax - t
                    elif fahrenheit:
                        t = (t-32)*5/9
                    if 5 < t < 115:
                        valid.append(t)
                if valid:
                    return round(max(valid),1)
            finally:
                kernel.UnmapViewOfFile(ptr)
        finally:
            kernel.CloseHandle(handle)
    return None


class Reader:
    def __init__(self):
        self.bridge = EmbeddedSensors()
        self.last_error = ''
        self.namespace = 'embedded LibreHardwareMonitorLib'
        self.prev_net = psutil.net_io_counters()
        self.prev_time = time.monotonic()
        psutil.cpu_percent(interval=None)

    def sample(self):
        now = time.monotonic()
        mem = psutil.virtual_memory()
        try: disk = psutil.disk_usage(os.environ.get('SystemDrive', 'C:') + '\\')
        except (OSError, ValueError): disk = None
        try: freq = psutil.cpu_freq()
        except Exception: freq = None
        net = psutil.net_io_counters()
        dt = max(.01, now - self.prev_time)
        rx = max(0, net.bytes_recv - self.prev_net.bytes_recv) / dt
        tx = max(0, net.bytes_sent - self.prev_net.bytes_sent) / dt
        self.prev_net, self.prev_time = net, now
        s = {'cpu': psutil.cpu_percent(interval=None), 'clock':freq.current if freq else None,
             'cpu_temp':None, 'ram':mem.percent, 'ram_used':mem.used,'ram_total':mem.total,
             'disk':disk.percent if disk else None,'disk_used':disk.used if disk else None,
             'disk_total':disk.total if disk else None, 'rx':rx,'tx':tx,
             'gpu_load':None,'gpu_temp':None,'gpu_hotspot':None,'gpu_power':None,
             'gpu_fan':None,'gpu_vram_used':None,'gpu_vram_total':None,'gpu_clock':None}
        rows, self.last_error = self.bridge.get()
        s.update(parse_hardware_sensors(rows))
        if s.get('cpu_temp') is None:
            try:
                s['cpu_temp'] = core_temp_shared_temperature()
            except (OSError, ValueError, OverflowError):
                pass
        return s

def is_gpu_sensor(row):
    name, ident, typ, value, *extra = row
    hw_type = str(extra[0]).lower() if extra else ''
    return (hw_type.startswith('gpu') or
            any(part in ident.lower() for part in
                ('/gpu-', '/atigpu/', '/nvidiagpu/', '/intelgpu/', '/gpu/')))


def parse_hardware_sensors(readings):
    """Normalize LibreHardwareMonitor sensors from AMD, NVIDIA and Intel.

    Older versions used identifiers such as /atigpu/0, /nvidiagpu/0.
    Matching only '/gpu' dropped ALL AMD/NVIDIA readings.
    """
    out = {}
    gpu = []
    for row in readings:
        name, ident, typ, val = row[:4]
        n = re.sub(r'[_\\-]+', ' ', name.lower())
        if (('/cpu' in ident or '/amdcpu' in ident or (len(row)>4 and str(row[4]).lower().startswith('cpu'))) and typ == 'temperature') and any(
            x in n for x in ('package', 'tctl', 'tdie', 'core (tctl')):
            if out.get('cpu_temp') is None and 5 < val < 115:
                out['cpu_temp'] = val
        if is_gpu_sensor(row):
            gpu.append((n, typ, val, ident))
    # Keep all metrics on the same GPU; identifier prefixes vary by vendor.
    groups = {}
    for n, t, v, ident in gpu:
        pieces = ident.strip('/').split('/')
        root = '/'.join(pieces[:2]) if len(pieces) >= 2 else ident
        groups.setdefault(root, []).append((n, t, v, ident))
    # CPU temperature fallback: newer AMD Ryzen/Intel sensors can expose
    # 'CPU CCD1 (Tdie)', 'CPU Die (average)', or generic CPU temperature.
    # Prefer package/Tctl above; use fallback only if not found.
    if out.get('cpu_temp') is None:
        cpu_candidates=[]
        for row in readings:
            name, ident, typ, val = row[:4]
            n=name.lower()
            ident=ident.lower()
            if typ != 'temperature' or not (any(t in ident for t in ('/cpu/','/amdcpu/','/intelcpu/')) or (len(row)>4 and str(row[4]).lower().startswith('cpu'))):
                continue
            priority=(0 if ('tdie' in n or 'cpu die' in n) else
                      1 if ('ccd' in n or 'core average' in n) else
                      2 if ('core' in n or 'cpu' in n) else 3)
            if 5 < val < 115:
                cpu_candidates.append((priority,val))
        if cpu_candidates:
            out['cpu_temp']=sorted(cpu_candidates,key=lambda x:x[0])[0][1]

    if groups:
        # Prefer discrete AMD/NVIDIA cards to integrated GPUs.
        root = sorted(groups, key=lambda k: (
            0 if ('atigpu' in k or 'nvidiagpu' in k or 'gpu-amd' in k or 'gpu-nvidia' in k) else 1,
            -len(groups[k]), k))[0]
        gpu = groups[root]

    def pick(key, typ, exact=(), contains=(), excludes=()):
        for name, t, v, _ in gpu:
            if t == typ and name in exact:
                out[key] = v
                return
        for needle in contains:
            for name, t, v, _ in gpu:
                if t == typ and needle in name and not any(x in name for x in excludes):
                    out[key] = v
                    return

    pick('gpu_load', 'load', ('gpu core', 'gpu total', 'gpu'),
         ('gpu core', 'gpu total', 'gpu usage', '3d'), ('memory', 'video engine'))
    pick('gpu_temp', 'temperature', ('gpu core', 'gpu temperature'),
         ('gpu core', 'gpu temperature', 'edge'), ('hotspot', 'hot spot', 'junction'))
    pick('gpu_hotspot', 'temperature', (), ('hot spot', 'hotspot', 'junction'))
    pick('gpu_power', 'power', ('gpu package', 'gpu total', 'gpu board', 'gpu power'),
         ('board', 'package', 'total', 'gpu power'))
    pick('gpu_fan', 'fan', (), ('gpu', 'fan'))
    pick('gpu_clock', 'clock', ('gpu core',), ('gpu core', 'gpu clock'))
    for name, typ, val, _ in gpu:
        if typ not in ('smalldata', 'data'):
            continue
        if 'memory used' in name or 'vram used' in name:
            out['gpu_vram_used'] = val * 1024**2
        elif 'memory total' in name or 'vram total' in name:
            out['gpu_vram_total'] = val * 1024**2
    return out
