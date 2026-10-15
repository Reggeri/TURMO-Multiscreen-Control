"""Detect the CPU of the computer running TURMO (never a build-machine default)."""
import os
import platform
import re
from functools import lru_cache

@lru_cache(maxsize=1)
def cpu_model():
    name = ''
    if os.name == 'nt':
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                name = winreg.QueryValueEx(key, 'ProcessorNameString')[0]
        except (OSError, ImportError, ValueError):
            pass
    if not name:
        name = platform.processor() or platform.uname().processor or ''
    name = re.sub(r'\s+', ' ', str(name)).strip()
    return name or 'CPU MODEL UNAVAILABLE'
