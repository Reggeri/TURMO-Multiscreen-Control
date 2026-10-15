"""Opt-in GitHub Release updater for the Windows one-file build."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile

VERSION = '0.28.30'
REPOSITORY = 'Reggeri/TURMO-Multiscreen-Control'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
MAX_DOWNLOAD = 250 * 1024 * 1024


def version_tuple(value):
    value = str(value).strip().lstrip('vV')
    if not re.fullmatch(r'\d+(?:\.\d+){1,3}', value):
        raise ValueError('Invalid release version')
    return tuple(int(x) for x in value.split('.'))


def latest_release():
    req = urllib.request.Request(API_URL, headers={'User-Agent': 'TURMO-Control-Updater', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.load(response)
    if not isinstance(data, dict) or not data.get('tag_name'):
        raise ValueError('No published release found')
    return data


def choose_asset(release):
    assets = release.get('assets') or []
    # Only accept official GitHub-hosted asset download URLs from this repository.
    for ext in ('.exe', '.zip'):
        for asset in assets:
            name = str(asset.get('name', ''))
            url = str(asset.get('browser_download_url', ''))
            if (name.lower().endswith(ext) and 'turmo' in name.lower()
                    and url.startswith(f'https://github.com/{REPOSITORY}/releases/download/')):
                return asset
    raise ValueError('No TURMO Windows EXE or ZIP attached to the release')


def download_asset(asset, directory):
    name = asset['name']
    dest = Path(directory) / ('release' + Path(name).suffix.lower())
    req = urllib.request.Request(asset['browser_download_url'], headers={'User-Agent': 'TURMO-Control-Updater'})
    total = 0
    with urllib.request.urlopen(req, timeout=45) as response, dest.open('wb') as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_DOWNLOAD:
                raise ValueError('Release download exceeds safety limit')
            output.write(chunk)
    if total < 100_000:
        raise ValueError('Downloaded EXE appears incomplete')
    if dest.suffix == '.exe':
        return dest
    with zipfile.ZipFile(dest) as zf:
        candidates = [entry for entry in zf.infolist() if not entry.is_dir()
                      and Path(entry.filename).name.lower() == 'turmo-control.exe']
        if len(candidates) != 1 or candidates[0].file_size > MAX_DOWNLOAD:
            raise ValueError('ZIP must contain one TURMO-Control.exe')
        exe = Path(directory) / 'TURMO-Control-new.exe'
        with zf.open(candidates[0]) as src, exe.open('wb') as out:
            import shutil
            shutil.copyfileobj(src, out)
        return exe


def stage_install(new_exe):
    if sys.platform != 'win32' or not getattr(sys, 'frozen', False):
        raise RuntimeError('Automatic installation works only in the packaged Windows EXE')
    current = Path(sys.executable).resolve()
    new_exe = Path(new_exe).resolve()
    # PowerShell waits for the old process to exit, replaces it, then relaunches.
    # Script is placed in the same temporary directory as the downloaded file.
    script = new_exe.parent / 'install-update.ps1'
    def ps_quote(value):
        return "'" + str(value).replace("'", "''") + "'"
    script.write_text(
        '$ErrorActionPreference = "Stop"\n'
        f'$oldPid = {os.getpid()}\n'
        f'$target = {ps_quote(current)}\n'
        f'$source = {ps_quote(new_exe)}\n'
        'try { Wait-Process -Id $oldPid -Timeout 40 -ErrorAction SilentlyContinue } catch {}\n'
        'Start-Sleep -Seconds 2\n'
        'Copy-Item -LiteralPath $source -Destination $target -Force\n'
        'Start-Process -FilePath $target\n', encoding='utf-8')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    subprocess.Popen(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                     creationflags=flags, close_fds=True)


def check_and_update(root, on_status, on_close):
    """Call from Tk main thread; network work runs in background."""
    from tkinter import messagebox
    if not getattr(sys, 'frozen', False) or sys.platform != 'win32':
        messagebox.showinfo('TURMO Update', 'Automatic updates are available in the Windows EXE build.')
        return
    on_status('Checking GitHub Releases…')
    def worker():
        try:
            release = latest_release()
            remote = release['tag_name']
            if version_tuple(remote) <= version_tuple(VERSION):
                root.after(0, lambda: (on_status('You are up to date.'), messagebox.showinfo('TURMO Update', f'You already have the latest version (v{VERSION}).')))
                return
            asset = choose_asset(release)
            def confirm():
                on_status(f'New version {remote} available')
                if not messagebox.askyesno('TURMO Update', f'New version {remote} is available.\n\nDownload and install it now?\nThe app will restart.'):
                    return
                on_status('Downloading update…')
                def download_worker():
                    try:
                        folder = tempfile.mkdtemp(prefix='turmo-update-')
                        exe = download_asset(asset, folder)
                        def install():
                            try:
                                stage_install(exe)
                                on_close()
                            except Exception as exc:
                                messagebox.showerror('TURMO Update', str(exc))
                        root.after(0, install)
                    except Exception as exc:
                        root.after(0, lambda error=str(exc): (on_status('Update failed'), messagebox.showerror('TURMO Update', error)))
                threading.Thread(target=download_worker, daemon=True).start()
            root.after(0, confirm)
        except Exception as exc:
            root.after(0, lambda error=str(exc): (on_status('Update check failed'), messagebox.showerror('TURMO Update', error)))
    threading.Thread(target=worker, daemon=True).start()
