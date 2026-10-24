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
from typing import NamedTuple

import web_tabs

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


class Playing(NamedTuple):
    player: Player      # which player
    title: str          # film / file name taken from the window title
    paused: bool        # best guess from the title / audio session
    hwnd: int           # the player's window (PotPlayer's position is read through it)
    site: str = ""      # set when this is a website in a browser (player.name is then the site name)


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


def _visible_windows():
    """[(hwnd, window title, process exe name)] for every visible window that has a title."""
    windows = []

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        exe = _exe_name(hwnd)
        if exe:
            windows.append((hwnd, buf.value, exe))
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return windows


def find_playing(web_sites=None, any_site=False):
    """Film thiyena player eka hoyanawa.
    Playing(player, title, paused, hwnd, site) ho None. paused = True nam player eka pause karala.
    web_sites = browser tab walin balanna ona site nam (Settings); None nam browsers balanne nae.
    any_site = site list eka nathuwa: sound eka enawa browser tab ekak film ekak da kiyala balanawa.
    Video player ekak thiyenawanam eka ma issellama; browser eka passe."""
    found = []
    web_found = []

    for hwnd, title, exe in _visible_windows():
        for player in PLAYERS:
            if exe.startswith(player.exe_prefixes):
                media = extract_media_title(player, title)
                if media:
                    found.append((player, media, bool(PAUSED_TITLE.search(title)), hwnd))
                break
        else:
            browser = web_tabs.browser_for_exe(exe) if (web_sites or any_site) else None
            tab = web_tabs.tab_title(browser, title) if browser else None
            hit = web_tabs.match_site(tab, web_sites) if (tab and web_sites) else None
            if hit:
                web_found.append((browser, hit[0], hit[1], hwnd))
            elif tab and any_site and not web_sites:
                # Only a tab that is making sound is looked at: nothing is searched for silent tabs
                guess = web_tabs.guess_title(tab)
                if guess and _audio_state(browser.exe_prefixes) is True:
                    web_found.append((browser, browser.name, guess, hwnd))

    if found:
        player, media, title_paused, hwnd = found[0]
        # Title eke "paused" thiyenawanam pause. Nathnam audio session eka balanawa
        # (session nathnam playing kiyala hithanawa, false pause wenne nathi wenna).
        paused = title_paused or (_audio_state(player.exe_prefixes) is False)
        return Playing(player, media, paused, hwnd)
    if web_found:
        browser, site, title, hwnd = web_found[0]
        # Browser eke tab eka audio play karanawada kiyala pause guess ekak
        paused = _audio_state(browser.exe_prefixes) is False
        return Playing(Player(site, browser.exe_prefixes, ""), title, paused, hwnd, site)
    return None


def browser_tabs():
    """[(browser name, active tab title)] for every browser window. Used by the Settings 'check' button."""
    tabs = []
    for _hwnd, title, exe in _visible_windows():
        browser = web_tabs.browser_for_exe(exe)
        tab = web_tabs.tab_title(browser, title) if browser else None
        if tab:
            tabs.append((browser.name, tab))
    return tabs
