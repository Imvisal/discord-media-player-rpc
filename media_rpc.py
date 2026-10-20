"""
Media RPC - Discord Rich Presence for video players (GUI)

PotPlayer, VLC, KMPlayer, MPC-HC, MPC-BE, SMPlayer, mpv, GOM Player wage players walin
film / TV series episode eka hoyagena, poster ekka Discord status ekata yawanawa.
Windows walata witharai.
"""

import inspect
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox

from pypresence import Presence

import app_icon
import media_info
import players
import system_integration as sysint

try:
    import pystray
except Exception:             # tray nathuwa wada karanna puluwan (X eken app eka close wenawa)
    pystray = None
try:
    from PIL import ImageTk
except Exception:
    ImageTk = None
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

APP_TITLE = "Media RPC"

# Discord card eke "Get Media RPC" button eka yana link eka (Steam eke "Get on Steam" wage).
# Repo eka rename kalath old link eka GitHub eken redirect karanawa.
PROJECT_URL = "https://github.com/Imvisal/potplayer-discord-rpc"
PROJECT_BUTTON = "Get Media RPC"
POLL_SECONDS = 5      # player check karana gaman (seconds)
RETRY_SECONDS = 5     # Discord connect wenne nathnam aye try karana gaman

UPDATE_PARAMS = set(inspect.signature(Presence.update).parameters)


# ---------------------------------------------------------------- Discord activity

def build_activity(media, started_at, player_name):
    details = media.display_title()
    state = media.subtitle()
    kwargs = {
        "details": details[:128].ljust(2),
        "state": state[:128].ljust(2),
        "start": started_at,
    }
    if media.poster and len(media.poster) <= 256:
        kwargs["large_image"] = media.poster
        kwargs["large_text"] = f"{details} · {player_name}"[:128]
    # Card eke yata "Get Media RPC" button eka (Discord eka button 2k wenakan danna puluwan)
    if "buttons" in UPDATE_PARAMS:
        kwargs["buttons"] = [{"label": PROJECT_BUTTON, "url": PROJECT_URL}]
    # "Watching ..." card eka (Crunchyroll wage) pennanna
    if ActivityType is not None and "activity_type" in UPDATE_PARAMS:
        kwargs["activity_type"] = ActivityType.WATCHING
    # Member list eke app eke nama wenuwata film nama pennanna
    if StatusDisplayType is not None and "status_display_type" in UPDATE_PARAMS:
        details_mode = getattr(StatusDisplayType, "DETAILS", None)
        if details_mode is not None:
            kwargs["status_display_type"] = details_mode
    return kwargs


# ---------------------------------------------------------------- Background worker

class RpcWorker(threading.Thread):
    """Discord ekata connect wela player eke film eka yawana thread eka."""

    def __init__(self, events):
        super().__init__(daemon=True)
        self.events = events
        self.stop_event = threading.Event()

    def emit(self, kind, payload=None):
        self.events.put((kind, payload))

    def run(self):
        rpc = None
        last_key = None
        media = None
        player_name = ""
        started_at = None

        while not self.stop_event.is_set():
            try:
                if rpc is None:
                    self.emit("status", "connecting")
                    rpc = Presence(CLIENT_ID)
                    rpc.connect()
                    self.emit("status", "connected")

                playing = players.find_playing()
                if playing is None:
                    if last_key is not None:
                        rpc.clear()
                        last_key = None
                        media = None
                        self.emit("watching", None)
                else:
                    player_name, raw = playing
                    key = (player_name, raw)
                    if key != last_key:
                        # parse + poster hoyanna (palaweni wara tikak welawak yanawa)
                        media = media_info.resolve(raw)
                        started_at = int(time.time())
                        last_key = key
                        self.emit("watching", (media, player_name))
                    rpc.update(**build_activity(media, started_at, player_name))
            except Exception:
                # Discord close una / restart una wage welawal
                try:
                    if rpc:
                        rpc.close()
                except Exception:
                    pass
                rpc = None
                last_key = None
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
    def __init__(self, root, start_hidden=False):
        self.root = root
        self.events = queue.Queue()      # worker -> UI
        self.commands = queue.Queue()    # tray menu -> UI (Tk thread-safe nathi nisa)
        self.worker = None
        self.watch_started = None
        self.tray = None
        self.tray_notified = False
        self.quitting = False

        root.title(APP_TITLE)
        root.geometry("380x440")
        root.resizable(False, False)
        root.configure(bg=BG)
        if ImageTk is not None:
            try:
                self.window_icon = ImageTk.PhotoImage(app_icon.make_icon_image(64))
                root.iconphoto(True, self.window_icon)
            except Exception:
                pass

        tk.Label(root, text=APP_TITLE, bg=BG, fg=TEXT,
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
        self.heading_label = tk.Label(card, text="NOW WATCHING", bg=CARD, fg=MUTED,
                                      font=("Segoe UI", 8, "bold"), anchor="w")
        self.heading_label.pack(fill="x")
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

        self.autostart_var = tk.BooleanVar(value=sysint.is_autostart_enabled())
        tk.Checkbutton(root, text="Start with Windows", variable=self.autostart_var,
                       command=self.on_autostart_checkbox, bg=BG, fg=TEXT,
                       selectcolor=CARD, activebackground=BG, activeforeground=TEXT,
                       highlightthickness=0, bd=0, cursor="hand2",
                       font=("Segoe UI", 10)).pack(pady=(2, 6))

        tk.Label(root, text="Works with PotPlayer, VLC, KMPlayer, MPC-HC, MPC-BE,\n"
                            "SMPlayer, mpv and GOM Player. Keep Discord (desktop app) open.\n"
                            "Closing this window keeps the app running in the system tray.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), justify="center").pack()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(200, self.process_events)
        self.root.after(1000, self.tick)

        self.setup_tray()
        self.start()   # open karanakotama auto-start
        if start_hidden and self.tray is not None:
            root.withdraw()    # Windows eka start wenakota tray ekata witharai

    # -- state ---------------------------------------------------------------

    def set_status(self, key):
        text, color = STATUS[key]
        self.status_label.config(text=text)
        self.dot.itemconfig(self.dot_item, fill=color)

    def set_watching(self, payload):
        media, player_name = payload if payload else (None, "")
        if self.tray is not None:
            try:      # tray icon eke hover tooltip eka (127 akuru wala sima ekak thiyenawa)
                tip = APP_TITLE
                if media is not None:
                    tip = f"{media.display_title()} {media.subtitle()}"
                self.tray.title = tip[:127]
            except Exception:
                pass
        if media is not None:
            self.heading_label.config(text=f"NOW WATCHING · {player_name.upper()}")
            self.title_label.config(text=media.display_title())
            self.sub_label.config(text=media.subtitle())
            self.poster_label.config(
                text="Poster found" if media.poster else "No poster found (title only)"
            )
            self.watch_started = time.time()
        else:
            self.heading_label.config(text="NOW WATCHING")
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

    # -- tray / window / autostart -------------------------------------------

    def setup_tray(self):
        if pystray is None:
            return
        try:
            menu = pystray.Menu(
                pystray.MenuItem("Show window",
                                 lambda icon, item: self.commands.put("show"), default=True),
                pystray.MenuItem(lambda item: "Stop" if self.running() else "Start",
                                 lambda icon, item: self.commands.put("toggle")),
                pystray.MenuItem("Start with Windows",
                                 lambda icon, item: self.commands.put("autostart"),
                                 checked=lambda item: sysint.is_autostart_enabled()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", lambda icon, item: self.commands.put("quit")),
            )
            self.tray = pystray.Icon("MediaRPC", app_icon.make_icon_image(64), APP_TITLE, menu)
            self.tray.run_detached()
        except Exception:
            self.tray = None

    def refresh_tray(self):
        if self.tray is not None:
            try:
                self.tray.update_menu()
            except Exception:
                pass

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except tk.TclError:
            pass

    def hide_window(self):
        self.root.withdraw()
        if not self.tray_notified and self.tray is not None:
            self.tray_notified = True
            try:
                self.tray.notify("Still running in the system tray. "
                                 "Right-click the tray icon to quit.", APP_TITLE)
            except Exception:
                pass

    def on_close(self):
        # X click karama tray ekata, tray nathnam app eka close
        if self.tray is not None:
            self.hide_window()
        else:
            self.quit_app()

    def quit_app(self):
        if self.quitting:
            return
        self.quitting = True
        self.stop()
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.root.destroy()

    def on_autostart_checkbox(self):
        wanted = self.autostart_var.get()
        if not sysint.set_autostart(wanted):
            self.autostart_var.set(sysint.is_autostart_enabled())
            messagebox.showwarning(APP_TITLE, "Could not change the Windows startup setting.")
        self.refresh_tray()

    def toggle_autostart(self):
        wanted = not sysint.is_autostart_enabled()
        sysint.set_autostart(wanted)
        self.autostart_var.set(sysint.is_autostart_enabled())
        self.refresh_tray()

    def handle_commands(self):
        try:
            while True:
                cmd = self.commands.get_nowait()
                if cmd == "show":
                    self.show_window()
                elif cmd == "toggle":
                    self.toggle()
                    self.refresh_tray()
                elif cmd == "autostart":
                    self.toggle_autostart()
                elif cmd == "quit":
                    self.quit_app()
                    return
        except queue.Empty:
            pass

    # -- periodic jobs --------------------------------------------------------

    def process_events(self):
        self.handle_commands()
        if self.quitting:
            return
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
    if not sysint.acquire_single_instance():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(APP_TITLE,
                            f"{APP_TITLE} is already running.\n"
                            "Check the system tray (the ^ arrow next to the clock).")
        root.destroy()
        return

    # palaya nama (PotPlayerRPC) walin enawanam auto-start/settings karagannawa
    sysint.migrate_legacy()

    # palaweni wara run karaddi Windows start wenakota auto-start wenna on karanawa
    # (window eke "Start with Windows" eken off karanna puluwan)
    if sysint.is_first_run():
        sysint.set_autostart(True)
        sysint.mark_first_run_done()

    root = tk.Tk()
    App(root, start_hidden="--minimized" in sys.argv)
    root.mainloop()


if __name__ == "__main__":
    main()
