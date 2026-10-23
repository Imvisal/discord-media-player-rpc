"""
Windows walata special dewal: auto-start (Windows on wenakota run wenna), single instance, settings.
"""

import ctypes
import json
import os
import sys
import time

try:
    import winreg
except ImportError:       # Windows nowana welawaka import wenne nae
    winreg = None

APP_NAME = "MediaRPC"
LEGACY_APP_NAME = "PotPlayerRPC"      # palaya nama
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"

_APPDATA = os.environ.get("APPDATA", os.path.expanduser("~"))
SETTINGS_DIR = os.path.join(_APPDATA, "MediaRPC")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")
LEGACY_SETTINGS_FILE = os.path.join(_APPDATA, "PotPlayerRPC", "settings.json")

_mutex_handle = None      # process eka iwara wenakan thiyaganna


# ---------------------------------------------------------------- auto-start

def _autostart_command():
    if getattr(sys, "frozen", False):                 # PyInstaller exe eka
        return f'"{sys.executable}" --minimized'
    python = sys.executable
    pythonw = os.path.join(os.path.dirname(python), "pythonw.exe")
    if os.path.exists(pythonw):
        python = pythonw
    script = os.path.abspath(sys.argv[0])
    return f'"{python}" "{script}" --minimized'


def _registered_command():
    """Run key eke thiyena command eka, nathnam None."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, APP_NAME)[0]
    except OSError:
        return None


def _windows_allows_autostart():
    """
    Task Manager > Startup apps (ho Settings > Apps > Startup) eken Disable karala nam False.
    Run key eka thiyenawa kiyala witharak podi na: Windows eka StartupApproved walin block karanna puluwan.
    Record ekak nathnam (default) True.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY) as key:
            data = winreg.QueryValueEx(key, APP_NAME)[0]
    except OSError:
        return True
    if isinstance(data, (bytes, bytearray)) and data:
        return data[0] % 2 == 0          # 02 / 06 = enabled, 03 = disabled
    return True


def _clear_startup_block():
    """Task Manager eken disable karala thibunoth eka ain karanawa (Start with Windows on karaddi)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, APPROVED_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except OSError:
        pass            # record ekak nathnam hari, key eka nathnam hari: wadak na


def is_autostart_enabled():
    """Run key eka thiyenawa AND Windows eka eka block karala nae nam witharak True."""
    if winreg is None:
        return False
    return _registered_command() is not None and _windows_allows_autostart()


def set_autostart(enabled):
    """True return karanawa wada una nam."""
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _autostart_command())
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        if enabled:
            _clear_startup_block()
        return True
    except OSError:
        return False


def refresh_autostart():
    """
    App eka open wenakota: auto-start on nam saha Run key eke path eka dan run wena exe / script eken wenas nam
    (exe eka move karala, folder eka rename karala wage) aluth path eka damma hadanawa.
    Task Manager eken user disable karala nam eka aye on karanne nae.
    """
    if winreg is None:
        return
    registered = _registered_command()
    if registered is None or registered == _autostart_command():
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _autostart_command())
    except OSError:
        pass


# ---------------------------------------------------------------- single instance

def acquire_single_instance(wait_seconds=0):
    """
    Aye app eka run wenawanam False. Palaweni instance nam True.
    wait_seconds > 0 nam (update ekakin passe restart wenakota) paraana eka iwara wenakan thawa balan innawa.
    """
    global _mutex_handle
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        deadline = time.time() + wait_seconds
        while True:
            handle = kernel32.CreateMutexW(None, False, "Local\\MediaRPC_SingleInstance")
            already_running = ctypes.get_last_error() == 183      # ERROR_ALREADY_EXISTS
            if not already_running:
                _mutex_handle = handle
                return True
            kernel32.CloseHandle(handle)      # handle eka hold karanawanam mutex eka kawadawath nathi wenne nae
            if time.time() >= deadline:
                return False
            time.sleep(0.5)
    except Exception:
        return True       # check karanna ba unoth wada karanna denawa


# ---------------------------------------------------------------- settings

def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get_setting(key, default=None):
    return load_settings().get(key, default)


def set_setting(key, value):
    """Wena settings nathi nokara ekak save karanawa."""
    try:
        data = load_settings()
        data[key] = value
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return True
    except OSError:
        return False


def migrate_legacy():
    """Palaya "PotPlayerRPC" version eken enawanam auto-start eka saha settings aluth nama ekata gannawa."""
    if winreg is None:
        return
    legacy_autostart = False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as key:
            try:
                winreg.QueryValueEx(key, LEGACY_APP_NAME)
                legacy_autostart = True
                winreg.DeleteValue(key, LEGACY_APP_NAME)
            except FileNotFoundError:
                pass
    except OSError:
        pass
    if (legacy_autostart or os.path.exists(LEGACY_SETTINGS_FILE)) and is_first_run():
        mark_first_run_done()
        if legacy_autostart:
            set_autostart(True)


def is_first_run():
    return not load_settings().get("first_run_done")


def mark_first_run_done():
    set_setting("first_run_done", True)
