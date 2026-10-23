"""
Media player hoyaganna module eka.

Window ekaka title eka kiyawala (process eke exe nama balala) film eke nama gannawa.
Support: PotPlayer, VLC, KMPlayer, MPC-HC, MPC-BE, SMPlayer, mpv, GOM Player.

Player ekak aluthen add karanna ona nam PLAYERS list ekata Player(...) ekak danna.
"""

import ctypes
import os
import re
from ctypes import wintypes
from dataclasses import dataclass

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

VIDEO_EXT = re.compile(
    r"\.(?:mkv|mp4|avi|mov|wmv|flv|webm|m4v|ts|m2ts|mpg|mpeg|ogm|ogv|3gp|rmvb|divx)$", re.I
)
SEP = r"[-–—|]"


@dataclass(frozen=True)
class Player:
    name: str            # UI eke / Discord eke pennana nama
    exe_prefixes: tuple  # process exe eke nama patan gannawa (lowercase)
    app_re: str          # window title eke thiyena player eke nama (regex)


PLAYERS = (
    Player("PotPlayer", ("potplayer",), r"PotPlayer(?: ?(?:64|Mini)[\w ]*)?"),
    Player("VLC", ("vlc",), r"VLC media player"),
    Player("KMPlayer", ("kmplayer",), r"(?:The )?KMPlayer(?: ?64X| ?64)?"),
    Player("MPC-HC", ("mpc-hc",), r"MPC-HC(?: [\d.]+)?"),
    Player("MPC-BE", ("mpc-be",), r"MPC-BE(?: [\w.]+)?"),
    Player("SMPlayer", ("smplayer",), r"SMPlayer"),
    Player("mpv", ("mpv",), r"mpv(?:\.net)?"),
    Player("GOM Player", ("gom",), r"GOM Player(?: [\w .]+)?"),
)


def extract_media_title(player, title):
    """Window title eken film eke nama return karanawa. Film nathnam (idle) None."""
    t = (title or "").strip()
    if not t:
        return None

    # "film.mkv - VLC media player"
    m = re.search(rf"\s+{SEP}\s+{player.app_re}\s*$", t, re.I)
    if m:
        return t[: m.start()].strip() or None

    # "MPC-HC - film.mkv"
    m = re.match(rf"^{player.app_re}\s+{SEP}\s+(.+)$", t, re.I)
    if m:
        return m.group(1).strip() or None

    # "VLC media player" wage player eke nama witharai nam, film nae
    if re.fullmatch(player.app_re, t, re.I):
        return None

    # Sampala players (MPC-HC wage) file nama witharai pennanawa
    if VIDEO_EXT.search(t):
        return t
    return None


# ---------------------------------------------------------------- Windows part

try:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)
    ]
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
except (AttributeError, OSError):      # Windows nowana welawaka (test wala)
    user32 = kernel32 = EnumWindowsProc = None


def _exe_name(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(1024)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
    finally:
        kernel32.CloseHandle(handle)
    return ""


PAUSED_TITLE = re.compile(r"\bpaused\b|\[pause\]|⏸", re.I)

# pycaw (Windows audio sessions) - player eke audio stream eka active da balanna.
# Pause karapu gaman audio session eka inactive wenawa, play karaddi aye active.
try:
    from pycaw.pycaw import AudioUtilities
except Exception:
    AudioUtilities = None


def _audio_state(prefixes):
    """Player eke audio session eka: True = audio yanawa, False = pause/silent stream nathi,
    None = audio session ekak nae (dann nae; video ekata audio nathi wage welawata)."""
    if AudioUtilities is None:
        return None
    try:
        sessions = AudioUtilities.GetAllSessions()
    except Exception:
        return None
    seen = False
    for session in sessions:
        try:
            proc = session.Process
            name = (proc.name() if proc else "").lower()
        except Exception:
            continue
        if not name.startswith(prefixes):
            continue
        seen = True
        try:
            if session.State == 1:      # AudioSessionStateActive
                return True
        except Exception:
            pass
    return False if seen else None


def find_playing():
    """Film thiyena player eka hoyanawa.
    (player_nama, film_nama, paused) ho None. paused = True nam player eka pause karala."""
    found = []

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        exe = _exe_name(hwnd)
        if not exe:
            return True
        for player in PLAYERS:
            if exe.startswith(player.exe_prefixes):
                media = extract_media_title(player, buf.value)
                if media:
                    found.append((player, media, bool(PAUSED_TITLE.search(buf.value))))
                break
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    if not found:
        return None
    player, media, title_paused = found[0]
    # Title eke "paused" thiyenawanam pause. Nathnam audio session eka balanawa
    # (session nathnam playing kiyala hithanawa, false pause wenne nathi wenna).
    paused = title_paused or (_audio_state(player.exe_prefixes) is False)
    return player.name, media, paused
