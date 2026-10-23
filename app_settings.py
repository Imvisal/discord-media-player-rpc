"""
User settings shared between the window (Tk thread) and the Discord worker thread.

Values live in memory (so the worker never reads the disk every few seconds) and are
saved to settings.json through system_integration whenever they change.
"""

import threading

import system_integration as sysint

DEFAULTS = {
    "show_progress": True,       # show a progress bar when the player can report its position
    "hide_when_paused": False,   # remove the Discord status while the video is paused
    "hide_button": False,        # hide the "Get Media RPC" button
    "privacy_mode": False,       # never show the title / poster: only "Watching <player>"
    "vlc_port": 8080,            # VLC web interface
    "vlc_password": "",
    "mpc_port": 13579,           # MPC-HC / MPC-BE web interface
}


def clean_port(value, default):
    """int port (1-65535) or `default` if `value` isn't one."""
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return port if 1 <= port <= 65535 else default


class Settings:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {key: sysint.get_setting(key, default) for key, default in DEFAULTS.items()}

    def get(self, key):
        with self._lock:
            return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        with self._lock:
            self._data[key] = value
        sysint.set_setting(key, value)
