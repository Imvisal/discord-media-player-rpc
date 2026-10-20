"""
PotPlayer -> Discord Rich Presence (GUI)

PotPlayer window title eka kiyawala, film / TV series episode eka hoyagena
poster ekka Discord status ekata yawanawa. Windows walata witharai.
"""

import ctypes
import inspect
import queue
import re
import threading
import time
import tkinter as tk
from ctypes import wintypes

from pypresence import Presence

import media_info

try:
    from pypresence import ActivityType
except ImportError:           # pypresence passe version walata witharai thiyenne
    ActivityType = None
try:
    from pypresence import StatusDisplayType
except ImportError:
    StatusDisplayType = None

# Discord Application ID (secret ekak nemei, public wenna puluwan)
CLIENT_ID = "1561956752105283635"

POLL_SECONDS = 5      # PotPlayer check karana gaman (seconds)
RETRY_SECONDS = 5     # Discord connect wenne nathnam aye try karana gaman
TITLE_SUFFIX = " - PotPlayer"

UPDATE_PARAMS = set(inspect.signature(Presence.update).parameters)

# ---------------------------------------------------------------- Win32 helpers

user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def find_potplayer_title():
    """PotPlayer window eke title eka return karanawa. Nathnam None."""
    found = []

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if title.endswith(TITLE_SUFFIX):
            found.append(title[: -len(TITLE_SUFFIX)])
            return False
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return found[0] if found else None


# ---------------------------------------------------------------- Discord activity

def build_activity(media, started_at):
    details = media.display_title()
    state = media.subtitle()
    kwargs = {
        "details": details[:128].ljust(2),
        "state": state[:128].ljust(2),
        "start": started_at,
    }
    if media.poster and len(media.poster) <= 256:
        kwargs["large_image"] = media.poster
        kwargs["large_text"] = details[:128].ljust(2)
    # "Watching ..." card eka (Crunchyroll wage) pennanna
    if ActivityType is not None and "activity_type" in UPDATE_PARAMS:
        kwargs["activity_type"] = ActivityType.WATCHING
    # Member list eke "PotPlayer" wenuwata film nama pennanna
    if StatusDisplayType is not None and "status_display_type" in UPDATE_PARAMS:
        details_mode = getattr(StatusDisplayType, "DETAILS", None)
        if details_mode is not None:
            kwargs["status_display_type"] = details_mode
    return kwargs


# ---------------------------------------------------------------- Background worker

class RpcWorker(threading.Thread):
    """Discord ekata connect wela PotPlayer title eka yawana thread eka."""

    def __init__(self, events):
        super().__init__(daemon=True)
        self.events = events
        self.stop_event = threading.Event()

    def emit(self, kind, payload=None):
        self.events.put((kind, payload))

    def run(self):
        rpc = None
        last_raw = None
        media = None
        started_at = None

        while not self.stop_event.is_set():
            try:
                if rpc is None:
                    self.emit("status", "connecting")
                    rpc = Presence(CLIENT_ID)
                    rpc.connect()
                    self.emit("status", "connected")

                raw = find_potplayer_title()
                if raw is None:
                    if last_raw is not None:
                        rpc.clear()
                        last_raw = None
                        media = None
                        self.emit("watching", None)
                else:
                    if raw != last_raw:
                        # parse + poster hoyanna (palaweni wara tikak welawak yanawa)
                        media = media_info.resolve(raw)
                        started_at = int(time.time())
                        last_raw = raw
                        self.emit("watching", media)
                    rpc.update(**build_activity(media, started_at))
            except Exception:
                # Discord close una / restart una wage welawal
                try:
                    if rpc:
                        rpc.close()
                except Exception:
                    pass
                rpc = None
                last_raw = None
                media = None
                self.emit("status", "error")
                self.emit("watching", None)
                self.stop_event.wait(RETRY_SECONDS)
                continue

            self.stop_event.wait(POLL_SECONDS)

        try:
            if rpc:
                rpc.clear()
                rpc.close()
        except Exception:
            pass


# ---------------------------------------------------------------- GUI

BG = "#1e1f22"
CARD = "#2b2d31"
TEXT = "#f2f3f5"
MUTED = "#949ba4"
ACCENT = "#5865f2"
ACCENT_HOVER = "#4752c4"
RED = "#da373c"
RED_HOVER = "#a12828"
GREEN = "#23a55a"
YELLOW = "#f0b232"
ERROR = "#f23f43"

STATUS = {
    "connecting": ("Connecting to Discord...", YELLOW),
    "connected": ("Connected to Discord", GREEN),
    "error": ("Discord not found, retrying...", ERROR),
    "stopped": ("Stopped", MUTED),
}


class App:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.worker = None
        self.watch_started = None

        root.title("PotPlayer RPC")
        root.geometry("380x370")
        root.resizable(False, False)
        root.configure(bg=BG)

        tk.Label(root, text="PotPlayer RPC", bg=BG, fg=TEXT,
                 font=("Segoe UI", 18, "bold")).pack(pady=(18, 2))
        tk.Label(root, text="Show what you're watching on Discord", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack()

        # status row
        status_row = tk.Frame(root, bg=BG)
        status_row.pack(pady=(16, 8))
        self.dot = tk.Canvas(status_row, width=12, height=12, bg=BG, highlightthickness=0)
        self.dot_item = self.dot.create_oval(1, 1, 11, 11, fill=MUTED, outline="")
        self.dot.pack(side="left", padx=(0, 8))
        self.status_label = tk.Label(status_row, text="Stopped", bg=BG, fg=TEXT,
                                     font=("Segoe UI", 10, "bold"))
        self.status_label.pack(side="left")

        # now watching card
        card = tk.Frame(root, bg=CARD, padx=16, pady=14)
        card.pack(fill="x", padx=24)
        tk.Label(card, text="NOW WATCHING", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        self.title_label = tk.Label(card, text="Nothing playing", bg=CARD, fg=TEXT,
                                    font=("Segoe UI", 12, "bold"), anchor="w",
                                    justify="left", wraplength=310)
        self.title_label.pack(fill="x", pady=(6, 2))
        self.sub_label = tk.Label(card, text="", bg=CARD, fg=TEXT,
                                  font=("Segoe UI", 10), anchor="w",
                                  justify="left", wraplength=310)
        self.sub_label.pack(fill="x")
        self.poster_label = tk.Label(card, text="", bg=CARD, fg=MUTED,
                                     font=("Segoe UI", 8), anchor="w")
        self.poster_label.pack(fill="x", pady=(4, 0))
        self.elapsed_label = tk.Label(card, text="", bg=CARD, fg=MUTED,
                                      font=("Segoe UI", 9), anchor="w")
        self.elapsed_label.pack(fill="x", pady=(2, 0))

        # start / stop button
        self.button = tk.Button(root, text="Start", command=self.toggle, bg=ACCENT, fg="white",
                                activebackground=ACCENT_HOVER, activeforeground="white",
                                relief="flat", bd=0, cursor="hand2",
                                font=("Segoe UI", 11, "bold"), width=18, pady=8)
        self.button.pack(pady=(18, 8))

        tk.Label(root, text="Keep Discord (desktop app) open while using this.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(200, self.process_events)
        self.root.after(1000, self.tick)

        self.start()   # open karanakotama auto-start

    # -- state ---------------------------------------------------------------

    def set_status(self, key):
        text, color = STATUS[key]
        self.status_label.config(text=text)
        self.dot.itemconfig(self.dot_item, fill=color)

    def set_watching(self, media):
        if media is not None:
            self.title_label.config(text=media.display_title())
            self.sub_label.config(text=media.subtitle())
            self.poster_label.config(
                text="Poster found" if media.poster else "No poster found (title only)"
            )
            self.watch_started = time.time()
        else:
            self.title_label.config(text="Nothing playing")
            self.sub_label.config(text="")
            self.poster_label.config(text="")
            self.elapsed_label.config(text="")
            self.watch_started = None

    def running(self):
        return self.worker is not None

    def start(self):
        if self.running():
            return
        self.worker = RpcWorker(self.events)
        self.worker.start()
        self.button.config(text="Stop", bg=RED, activebackground=RED_HOVER)
        self.set_status("connecting")

    def stop(self):
        if not self.running():
            return
        self.worker.stop_event.set()
        self.worker.join(timeout=3)
        self.worker = None
        # parana events ain karanna
        while not self.events.empty():
            try:
                self.events.get_nowait()
            except queue.Empty:
                break
        self.button.config(text="Start", bg=ACCENT, activebackground=ACCENT_HOVER)
        self.set_status("stopped")
        self.set_watching(None)

    def toggle(self):
        if self.running():
            self.stop()
        else:
            self.start()

    def on_close(self):
        self.stop()
        self.root.destroy()

    # -- periodic jobs --------------------------------------------------------

    def process_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if not self.running():
                    continue
                if kind == "status":
                    self.set_status(payload)
                elif kind == "watching":
                    self.set_watching(payload)
        except queue.Empty:
            pass
        self.root.after(200, self.process_events)

    def tick(self):
        if self.watch_started is not None:
            secs = int(time.time() - self.watch_started)
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            self.elapsed_label.config(text=f"Elapsed {h}:{m:02d}:{s:02d}")
        self.root.after(1000, self.tick)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
