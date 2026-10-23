"""
Playback position and duration of the playing video, for the Discord progress bar.

  PotPlayer  : Windows messages (works out of the box).
  VLC        : web interface, http://127.0.0.1:<port>/requests/status.json (needs a password).
  MPC-HC/BE  : web interface, http://127.0.0.1:<port>/variables.html.

The other players don't expose their position, so Media RPC shows an elapsed timer for them.
Everything here is best-effort: any failure just means "no progress bar", never an exception.
"""

import base64
import ctypes
import json
import re
import urllib.error
import urllib.request
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional

from app_settings import clean_port

try:
    _user32 = ctypes.windll.user32
    _user32.SendMessageTimeoutW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
    ]
    _user32.SendMessageTimeoutW.restype = ctypes.c_ssize_t
except (AttributeError, OSError):          # not Windows (tests)
    _user32 = None

# PotPlayer remote commands: SendMessage(hwnd, WM_USER, <command>, 0)
WM_USER = 0x0400
POT_GET_TOTAL_TIME = 0x5002       # milliseconds
POT_GET_CURRENT_TIME = 0x5004     # milliseconds
POT_GET_PLAY_STATUS = 0x5006      # -1 stopped, 1 paused, 2 playing
SMTO_ABORTIFHUNG = 0x0002
MESSAGE_TIMEOUT_MS = 250

HTTP_TIMEOUT = 1.0
VLC_DEFAULT_PORT = 8080
MPC_DEFAULT_PORT = 13579

PLAYERS_WITH_PROGRESS = ("PotPlayer", "VLC", "MPC-HC", "MPC-BE")
NEEDS_WEB_INTERFACE = ("VLC", "MPC-HC", "MPC-BE")

# No proxy for localhost, whatever the system proxy settings are
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass(frozen=True)
class Playback:
    position: float                 # seconds
    duration: float                 # seconds, 0 = unknown (live stream / still loading)
    paused: Optional[bool] = None   # None = the player didn't say
    source: str = ""


class PlayerUnavailable(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason        # "auth" or "unreachable"


# ---------------------------------------------------------------- PotPlayer

def _pot_call(hwnd, command):
    if _user32 is None or not hwnd:
        return None
    result = ctypes.c_size_t(0)
    ok = _user32.SendMessageTimeoutW(
        hwnd, WM_USER, command, 0, SMTO_ABORTIFHUNG, MESSAGE_TIMEOUT_MS, ctypes.byref(result)
    )
    if not ok:
        return None
    value = result.value & 0xFFFFFFFF            # the player answers with a 32-bit int
    return value - (1 << 32) if value >= 0x80000000 else value


def _read_potplayer(hwnd):
    total = _pot_call(hwnd, POT_GET_TOTAL_TIME)
    current = _pot_call(hwnd, POT_GET_CURRENT_TIME)
    status = _pot_call(hwnd, POT_GET_PLAY_STATUS)
    if total is None or current is None:
        return None
    if status not in (-1, 1, 2):
        if total <= 0:                           # no sensible answer at all
            return None
        status = None
    paused = None if status is None else status != 2
    return Playback(max(current, 0) / 1000.0, max(total, 0) / 1000.0, paused, "PotPlayer")


# ---------------------------------------------------------------- web interfaces

def _http_get(url, password=None):
    request = urllib.request.Request(url)
    if password is not None:                     # VLC: empty user name + password
        token = base64.b64encode(f":{password}".encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {token}")
    try:
        with _OPENER.open(request, timeout=HTTP_TIMEOUT) as response:
            return response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise PlayerUnavailable("auth" if exc.code in (401, 403) else "unreachable") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise PlayerUnavailable("unreachable") from exc


def parse_vlc(text):
    """VLC /requests/status.json: time and length are seconds, state is playing/paused/stopped."""
    data = json.loads(text)
    state = str(data.get("state", "")).lower()
    if state not in ("playing", "paused", "stopped"):
        return None
    position = max(float(data.get("time") or 0), 0.0)
    duration = max(float(data.get("length") or 0), 0.0)
    return Playback(position, duration, state != "playing", "VLC")


_MPC_FIELD = re.compile(r'<p\s+id="(\w+)"\s*>(.*?)</p>', re.S | re.I)


def parse_mpc(html, source="MPC-HC"):
    """MPC-HC/BE variables.html: position and duration are milliseconds,
    state is -1 no file, 0 stopped, 1 paused, 2 playing."""
    fields = {key.lower(): value.strip() for key, value in _MPC_FIELD.findall(html)}
    try:
        position = int(fields["position"])
        duration = int(fields["duration"])
    except (KeyError, ValueError):
        return None
    try:
        state = int(fields.get("state", ""))
    except ValueError:
        state = None
    paused = (state != 2) if state in (0, 1, 2) else None
    return Playback(max(position, 0) / 1000.0, max(duration, 0) / 1000.0, paused, source)


def _vlc_url(cfg):
    port = clean_port(cfg.get("vlc_port"), VLC_DEFAULT_PORT)
    return f"http://127.0.0.1:{port}/requests/status.json"


def _mpc_url(cfg):
    port = clean_port(cfg.get("mpc_port"), MPC_DEFAULT_PORT)
    return f"http://127.0.0.1:{port}/variables.html"


def _read_vlc(cfg):
    return parse_vlc(_http_get(_vlc_url(cfg), password=str(cfg.get("vlc_password") or "")))


def _read_mpc(cfg, source):
    return parse_mpc(_http_get(_mpc_url(cfg)), source)


# ---------------------------------------------------------------- public API

def read(player_name, hwnd, cfg):
    """Playback for the player, or None when it can't tell. Never raises."""
    try:
        if player_name == "PotPlayer":
            return _read_potplayer(hwnd)
        if player_name == "VLC":
            return _read_vlc(cfg)
        if player_name in ("MPC-HC", "MPC-BE"):
            return _read_mpc(cfg, player_name)
    except Exception:
        return None
    return None


def hint(player_name, playback, enabled=True):
    """One line for the window: whether the progress bar works for this player."""
    if not enabled:
        return "Progress bar is off (Settings)"
    if playback is not None:
        return f"Progress bar: on ({playback.source})"
    if player_name in NEEDS_WEB_INTERFACE:
        return f"Progress bar needs the {player_name} web interface: see Settings"
    if player_name == "PotPlayer":
        return "PotPlayer didn't report its position (showing elapsed time)"
    return f"{player_name} can't report its position (showing elapsed time)"


def check_web_interface(kind, cfg):
    """Settings 'Test' button. kind is "vlc" or "mpc". Returns (ok, message)."""
    name = "VLC" if kind == "vlc" else "MPC-HC / MPC-BE"
    try:
        if kind == "vlc":
            result = _read_vlc(cfg)
        else:
            result = _read_mpc(cfg, "MPC-HC")
    except PlayerUnavailable as exc:
        if exc.reason == "auth":
            return False, "VLC rejected the password. Check the Lua HTTP password."
        return False, f"Can't reach {name}. Is it open, with the web interface switched on?"
    except Exception:
        return False, f"{name} answered, but not in a format I understand."
    if result is None:
        return False, f"{name} answered, but not in a format I understand."
    return True, f"Connected to {name}."
