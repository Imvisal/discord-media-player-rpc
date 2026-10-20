"""
Windows walata special dewal: auto-start (Windows on wenakota run wenna), single instance, settings.
"""

import ctypes
import json
import os
import sys

try:
    import winreg
except ImportError:       # Windows nowana welawaka import wenne nae
    winreg = None

APP_NAME = "PotPlayerRPC"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

SETTINGS_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PotPlayerRPC")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.json")

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


def is_autostart_enabled():
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except OSError:
        return False


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
        return True
    except OSError:
        return False


# ---------------------------------------------------------------- single instance

def acquire_single_instance():
    """Aye app eka run wenawanam False. Palaweni instance nam True."""
    global _mutex_handle
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, "Local\\PotPlayerRPC_SingleInstance")
        already_running = ctypes.get_last_error() == 183      # ERROR_ALREADY_EXISTS
        if already_running:
            return False
        _mutex_handle = handle
        return True
    except Exception:
        return True       # check karanna ba unoth wada karanna denawa


# ---------------------------------------------------------------- settings

def is_first_run():
    return not os.path.exists(SETTINGS_FILE)


def mark_first_run_done():
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"first_run_done": True}, f)
    except OSError:
        pass
