"""
PotPlayer -> Discord Rich Presence
PotPlayer window title eka kiyawala, film/episode nama Discord status ekata yawanawa.
Windows walata witharai.
"""

import ctypes
import os
import re
import sys
import time
from ctypes import wintypes

from pypresence import Presence

# Discord Developer Portal eken hadapu Application ID eka methanata danna
# (README eke 1 step eka balanna). Environment variable ekakuth danna puluwan.
CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "YOUR_APPLICATION_ID_HERE")

POLL_SECONDS = 5          # PotPlayer check karana gaman (seconds)
TITLE_SUFFIX = " - PotPlayer"

user32 = ctypes.windll.user32
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
GetWindowTextW = user32.GetWindowTextW
GetWindowTextLengthW = user32.GetWindowTextLengthW
IsWindowVisible = user32.IsWindowVisible


def find_potplayer_title():
    """PotPlayer window eke title eka return karanawa. Nathnam None."""
    found = []

    def callback(hwnd, _lparam):
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if title.endswith(TITLE_SUFFIX):
            found.append(title[: -len(TITLE_SUFFIX)])
            return False  # hambuna, nawathinna
        return True

    EnumWindows(EnumWindowsProc(callback), 0)
    return found[0] if found else None


def clean_title(raw):
    """File extension, [tags], dots, underscores ain karala lassana nama ekak hadanawa."""
    name = re.sub(r"\.(mkv|mp4|avi|mov|wmv|flv|webm|m4v|ts)$", "", raw, flags=re.I)
    name = re.sub(r"[\[\(][^\]\)]*[\]\)]", "", name)   # [1080p] (2020) wage dewal
    name = re.sub(r"[._]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" -")
    return name or raw


def connect():
    rpc = Presence(CLIENT_ID)
    rpc.connect()
    return rpc


def main():
    if CLIENT_ID == "YOUR_APPLICATION_ID_HERE":
        print("CLIENT_ID eka danna one. README eke step 1 balanna.")
        sys.exit(1)

    rpc = None
    last_title = None
    started_at = None

    print("PotPlayer RPC wada karanawa. Nawathinna Ctrl+C.")
    while True:
        try:
            if rpc is None:
                rpc = connect()
                print("Discord ekata connect una.")

            raw = find_potplayer_title()

            if raw is None:
                if last_title is not None:
                    rpc.clear()
                    last_title = None
                    print("PotPlayer nadda / film nadda. Status eka clear kala.")
            else:
                title = clean_title(raw)
                if title != last_title:
                    started_at = int(time.time())
                    last_title = title
                    print(f"Now watching: {title}")
                rpc.update(
                    details=title[:128],
                    state="Watching in PotPlayer",
                    start=started_at,
                )
        except KeyboardInterrupt:
            break
        except Exception as exc:  # Discord close una wage welawal reconnect karanna
            print(f"Error: {exc}. Tikakin passe aye try karanawa...")
            try:
                if rpc:
                    rpc.close()
            except Exception:
                pass
            rpc = None
            last_title = None

        time.sleep(POLL_SECONDS)

    try:
        if rpc:
            rpc.clear()
            rpc.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
