"""
Media RPC - Discord Rich Presence for video players (GUI)

PotPlayer, VLC, KMPlayer, MPC-HC, MPC-BE, SMPlayer, mpv, GOM Player wage players walin
film / TV series episode eka hoyagena, poster ekka Discord status ekata yawanawa.
Windows walata witharai.
"""

import inspect
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox

from pypresence import Presence

import app_icon
import app_version
import media_info
import players
import system_integration as sysint
import updater

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
PROJECT_URL = "https://github.com/Imvisal/discord-media-player-rpc"
PROJECT_BUTTON = "Get Media RPC"
# Poster nathi welawata pennana image eka: Discord Developer Portal > oyage application >
# Rich Presence > Art Assets walata "default_poster" kiyana nama image ekak upload karanna.
# Upload karala nathnam Discord eka "?" pennanawa (kalin wage).
FALLBACK_IMAGE = "default_poster"
POLL_SECONDS = 5      # player check karana gaman (seconds)
RETRY_SECONDS = 5     # Discord connect wenne nathnam aye try karana gaman
POSTER_RETRY_SECONDS = 30   # poster nathnam aye hoyala balana gaman (seconds)
UPDATE_CHECK_SECONDS = 6 * 3600   # aluth version ekak thiyenawada balana gaman
UPDATE_FIRST_CHECK_MS = 5000      # app eka open wela tikak passe palaweni check eka

UPDATE_PARAMS = set(inspect.signature(Presence.update).parameters)


# ---------------------------------------------------------------- Discord activity

def build_generic_activity(started_at, player_name):
    """Film / series ekak hambune nathnam: file nama pennanne nae, 'Watching PotPlayer' witharai."""
    kwargs = {"start": started_at}
    if "name" in UPDATE_PARAMS:
        # aluth pypresence: card eke header eka 'Watching PotPlayer' wenawa
        kwargs["name"] = player_name
    else:
        kwargs["details"] = f"Watching {player_name}"[:128].ljust(2)
    if FALLBACK_IMAGE:
        kwargs["large_image"] = FALLBACK_IMAGE
        kwargs["large_text"] = player_name
    if "buttons" in UPDATE_PARAMS:
        kwargs["buttons"] = [{"label": PROJECT_BUTTON, "url": PROJECT_URL}]
    if ActivityType is not None and "activity_type" in UPDATE_PARAMS:
        kwargs["activity_type"] = ActivityType.WATCHING
    if StatusDisplayType is not None and "status_display_type" in UPDATE_PARAMS:
        name_mode = getattr(StatusDisplayType, "NAME", None)
        if name_mode is not None:
            kwargs["status_display_type"] = name_mode
    return kwargs


def build_activity(media, started_at, player_name):
    if not media.matched:
        return build_generic_activity(started_at, player_name)
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
    elif FALLBACK_IMAGE:
        kwargs["large_image"] = FALLBACK_IMAGE
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
        last_lookup = 0.0

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
                        last_lookup = time.time()
                        self.emit("watching", (media, player_name))
                    elif (not (media.matched and media.poster)
                          and time.time() - last_lookup >= POSTER_RETRY_SECONDS):
                        # poster hambuna nae: network fail wela wage nam aye try karanna
                        # (media_info eke cache eka nisa hamadama network ekata yanne nae)
                        last_lookup = time.time()
                        retry = media_info.resolve(raw)
                        if retry != media:
                            media = retry
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
        self.ui_queue = queue.Queue()    # update thread -> UI (worker events walin wen karala)
        self.update_info = None
        self.update_busy = False
        self.notified_version = None     # tray notification eka eka version ekata ekak witharai

        root.title(APP_TITLE)
        root.geometry("380x540")
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
                       font=("Segoe UI", 10)).pack(pady=(2, 2))

        self.autoupdate_var = tk.BooleanVar(value=bool(sysint.get_setting("auto_update_check", True)))
        tk.Checkbutton(root, text="Check for updates automatically", variable=self.autoupdate_var,
                       command=self.on_autoupdate_checkbox, bg=BG, fg=TEXT,
                       selectcolor=CARD, activebackground=BG, activeforeground=TEXT,
                       highlightthickness=0, bd=0, cursor="hand2",
                       font=("Segoe UI", 10)).pack(pady=(0, 4))

        # version + update (aluth version ekak thiyenakota button eka pennanawa)
        self.update_box = tk.Frame(root, bg=BG)
        self.update_box.pack(pady=(2, 8))
        self.update_label = tk.Label(self.update_box, text=self.version_text(), bg=BG, fg=MUTED,
                                     font=("Segoe UI", 9))
        self.update_label.pack()
        self.update_button = tk.Button(self.update_box, text="", command=self.install_update,
                                       bg=GREEN, fg="white", activebackground="#1a8247",
                                       activeforeground="white", relief="flat", bd=0,
                                       cursor="hand2", font=("Segoe UI", 10, "bold"),
                                       padx=14, pady=5)

        tk.Label(root, text="Works with PotPlayer, VLC, KMPlayer, MPC-HC, MPC-BE,\n"
                            "SMPlayer, mpv and GOM Player. Keep Discord (desktop app) open.\n"
                            "Closing this window keeps the app running in the system tray.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), justify="center").pack()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(200, self.process_events)
        self.root.after(1000, self.tick)
        self.root.after(UPDATE_FIRST_CHECK_MS, self.auto_check_updates)

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
                    tip = (f"{media.display_title()} {media.subtitle()}" if media.matched
                           else f"Watching {player_name}")
                self.tray.title = tip[:127]
            except Exception:
                pass
        if media is not None and not media.matched:
            self.heading_label.config(text=f"NOW WATCHING · {player_name.upper()}")
            self.title_label.config(text=f"Watching {player_name}")
            self.sub_label.config(text="")
            self.poster_label.config(text="Not a movie / TV series (title hidden on Discord)")
            self.watch_started = time.time()
        elif media is not None:
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
                pystray.MenuItem("Check for updates",
                                 lambda icon, item: self.commands.put("check_update")),
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

    # -- online updates -------------------------------------------------------

    @staticmethod
    def version_text():
        v = app_version.__version__
        return "Development build (no auto-update)" if updater.is_dev_build(v) else f"Version {v}"

    def on_autoupdate_checkbox(self):
        sysint.set_setting("auto_update_check", bool(self.autoupdate_var.get()))

    def auto_check_updates(self):
        """Palaweni check eka + paya 6k pasuwa pasuwa. Checkbox eka off nam check karanne nae."""
        if self.quitting:
            return
        if self.autoupdate_var.get():
            self.check_updates(manual=False)
        self.root.after(UPDATE_CHECK_SECONDS * 1000, self.auto_check_updates)

    def check_updates(self, manual=False):
        if self.update_busy or self.quitting:
            return
        self.update_busy = True

        def work():
            try:
                self.ui_queue.put(("update_check", (updater.check_for_update(), manual, None)))
            except Exception as exc:
                self.ui_queue.put(("update_check", (None, manual, exc)))

        threading.Thread(target=work, daemon=True).start()

    def show_update(self, info, manual=False):
        self.update_info = info
        self.update_label.config(text=f"Update available: v{info.version}", fg=GREEN)
        label = "Update and restart" if updater.can_self_update() else "Open download page"
        self.update_button.config(text=label, state="normal")
        self.update_button.pack(pady=(6, 0))
        # Auto check ekakin aluth version ekak hambunoth tray notification ekak (eka version ekata ekakin witharai)
        if not manual and self.tray is not None and self.notified_version != info.version:
            self.notified_version = info.version
            try:
                self.tray.notify(f"Version {info.version} is available. "
                                 "Open Media RPC and click \"Update and restart\".",
                                 f"{APP_TITLE} update")
            except Exception:
                pass

    def install_update(self):
        info = self.update_info
        if info is None or self.update_busy:
            return
        if not updater.can_self_update():
            webbrowser.open(info.page_url)      # source walin run karanawa / folder eka write karanna ba
            return
        self.update_busy = True
        self.update_button.config(text="Downloading... 0%", state="disabled")

        def work():
            try:
                path = updater.download(
                    info, progress=lambda pct: self.ui_queue.put(("update_progress", pct)))
                self.ui_queue.put(("update_ready", path))
            except Exception as exc:
                self.ui_queue.put(("update_error", exc))

        threading.Thread(target=work, daemon=True).start()

    def finish_update(self, path):
        """Download + checksum ok. Presence eka nawathala, exe eka replace karala aluth eka start karanawa."""
        minimized = self.root.state() == "withdrawn"
        self.stop()
        try:
            updater.apply_update(path, minimized=minimized)
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
            self.update_busy = False
            self.update_button.config(text="Update and restart", state="normal")
            messagebox.showwarning(APP_TITLE, "Could not install the update automatically.\n"
                                              "Use the download page instead.")
            webbrowser.open(self.update_info.page_url)
            self.start()
            return
        self.quit_app()          # aluth process eka "--wait-for-previous" ekka balan inne

    def handle_ui_events(self):
        try:
            while True:
                kind, payload = self.ui_queue.get_nowait()
                if kind == "update_check":
                    self.update_busy = False
                    info, manual, error = payload
                    if info is not None:
                        self.show_update(info, manual)
                    elif manual:
                        if error is not None:
                            self.update_label.config(text="Couldn't check for updates (offline?)", fg=ERROR)
                        elif updater.is_dev_build():
                            self.update_label.config(text=self.version_text(), fg=MUTED)
                        else:
                            self.update_label.config(text=f"{self.version_text()} (up to date)", fg=GREEN)
                elif kind == "update_progress":
                    self.update_button.config(text=f"Downloading... {payload}%")
                elif kind == "update_ready":
                    self.finish_update(payload)
                elif kind == "update_error":
                    self.update_busy = False
                    self.update_button.config(text="Retry update", state="normal")
                    self.update_label.config(text="Update download failed. Try again.", fg=ERROR)
        except queue.Empty:
            pass

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
                elif cmd == "check_update":
                    self.show_window()
                    self.update_label.config(text="Checking for updates...", fg=MUTED)
                    self.check_updates(manual=True)
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
        self.handle_ui_events()
        if self.quitting:        # update install eken passe app eka iwara wenawa
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
    # Update ekakin passe aluth exe eka start wenakota paraana eka iwara wenakan tikak balan innawa
    wait = 20 if "--wait-for-previous" in sys.argv else 0
    if not sysint.acquire_single_instance(wait_seconds=wait):
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(APP_TITLE,
                            f"{APP_TITLE} is already running.\n"
                            "Check the system tray (the ^ arrow next to the clock).")
        root.destroy()
        return

    updater.cleanup_old_files()      # kalin update ekakin ithuru una MediaRPC.exe.old wage files ain karanawa

    # palaya nama (PotPlayerRPC) walin enawanam auto-start/settings karagannawa
    sysint.migrate_legacy()
    sysint.refresh_autostart()       # exe eka move karapu nam Run key eke path eka aluth karanawa

    # palaweni wara run karaddi Windows start wenakota auto-start wenna on karanawa
    # (window eke "Start with Windows" eken off karanna puluwan)
    if sysint.is_first_run():
        sysint.set_autostart(True)
        sysint.mark_first_run_done()

    root = tk.Tk()
    App(root, start_hidden="--minimized" in sys.argv)
    root.mainloop()


def _log_crash():
    """--noconsole / pythonw walin run karaddi error pennanne nae. Meka error.log ekata liyanawa."""
    import traceback
    try:
        os.makedirs(sysint.SETTINGS_DIR, exist_ok=True)
        with open(os.path.join(sysint.SETTINGS_DIR, "error.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + traceback.format_exc() + "\n")
    except OSError:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        _log_crash()
        raise
