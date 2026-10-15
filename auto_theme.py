"""Activity-aware theme selection. No data is uploaded or stored.

Priority: actively playing media > foreground game > idle clock > system.
Game detection uses a conservative known executable list, not GPU usage guesses.
"""
import ctypes
import sys
import time
import psutil

GAME_EXES = {
    'cs2.exe','csgo.exe','valorant-win64-shipping.exe','fortniteclient-win64-shipping.exe',
    'gta5.exe','gta5_enhanced.exe','rdr2.exe','minecraft.exe','javaw.exe',
    'eldenring.exe','cyberpunk2077.exe','league of legends.exe','overwatch.exe',
    'robloxplayerbeta.exe','rocketleague.exe','theforest.exe','sons of the forest.exe',
    'raft.exe','palworld-win64-shipping.exe','cod.exe','hl2.exe','dota2.exe',
    'apex.exe','pubg.exe','tslgame.exe','terraria.exe','stardew valley.exe'
}

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]


def idle_seconds():
    if sys.platform != 'win32':
        return 0
    try:
        info=LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0
        ticks=ctypes.windll.kernel32.GetTickCount() & 0xffffffff
        return ((ticks-info.dwTime) & 0xffffffff)/1000
    except Exception:
        return 0


def foreground_process():
    if sys.platform != 'win32':
        return ''
    try:
        hwnd=ctypes.windll.user32.GetForegroundWindow()
        if not hwnd:
            return ''
        pid=ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        return psutil.Process(pid.value).name().lower()
    except (psutil.Error, OSError, ValueError):
        return ''


def select_theme(data, *, idle_threshold=300):
    if data.get('music_playing'):
        return 'MUSIC VISUALIZER 2.0'
    if foreground_process() in GAME_EXES:
        return 'GPU Neon'
    if idle_seconds() >= idle_threshold:
        return 'SMART WEATHER CLOCK'
    return 'System Neon'
