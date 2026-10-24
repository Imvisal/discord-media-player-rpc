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
import app_settings
import app_version
import media_info
import playback
import players
import settings_window
import system_integration as sysint
import updater
import web_tabs
from theme import (ACCENT, ACCENT_HOVER, BG, CARD, CARD_HOVER, ERROR, GREEN, MUTED, RED,
                   RED_HOVER, TEXT, YELLOW)

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
POLL_SECONDS = 3      # player check karana gaman (seconds)
PAUSE_CONFIRM_POLLS = 2   # pause kiyala hithanna kalin thiyenna ona consecutive polls
                          # (player eka thamai pause kiyala kiwwoth 1k ma pawsa)
MIN_UPDATE_SECONDS = 5    # Discord ekata update yawana weni weni athare minimum gaman
TIMESTAMP_TOLERANCE = 3   # seconds: me tharamak wenas unoth witharai aluth timestamp ekak yawanne
                          # (seek karaddi wenas wenawa, 1s rounding wage dewal ignore wenawa)
RETRY_SECONDS = 5     # Discord connect wenne nathnam aye try karana gaman
POSTER_RETRY_SECONDS = 30   # poster nathnam aye hoyala balana gaman (seconds)
UPDATE_CHECK_SECONDS = 6 * 3600   # aluth version ekak thiyenawada balana gaman
UPDATE_FIRST_CHECK_MS = 5000      # app eka open wela tikak passe palaweni check eka

UPDATE_PARAMS = set(inspect.signature(Presence.update).parameters)


# ---------------------------------------------------------------- Discord activity

def _watching_extras(kwargs, mode_name):
    """Card eka 'Watching ...' widiyata, member list eke nama / details pennanna."""
    if ActivityType is not None and "activity_type" in UPDATE_PARAMS:
        kwargs["activity_type"] = ActivityType.WATCHING
    if StatusDisplayType is not None and "status_display_type" in UPDATE_PARAMS:
        mode = getattr(StatusDisplayType, mode_name, None)
        if mode is not None:
            kwargs["status_display_type"] = mode


def _timestamps(kwargs, started_at, end, paused):
    """start = timer, start + end = progress bar. Pause karapu welawe kisima ekak nae."""
    if not paused and started_at is not None:
        kwargs["start"] = started_at
        if end is not None:
            kwargs["end"] = end


def build_generic_activity(started_at, player_name, paused=False, end=None, hide_button=False):
    """Film eke nama pennanne nae: 'Watching PotPlayer' witharai (privacy mode / film nowana video)."""
    kwargs = {}
    _timestamps(kwargs, started_at, end, paused)
    if "name" in UPDATE_PARAMS:
        # aluth pypresence: card eke header eka 'Watching PotPlayer' wenawa
        kwargs["name"] = player_name
    else:
        kwargs["details"] = f"Watching {player_name}"[:128].ljust(2)
    if paused:
        kwargs["state"] = "Paused"
    if FALLBACK_IMAGE:
        kwargs["large_image"] = FALLBACK_IMAGE
        kwargs["large_text"] = player_name
    if "buttons" in UPDATE_PARAMS and not hide_button:
        kwargs["buttons"] = [{"label": PROJECT_BUTTON, "url": PROJECT_URL}]
    _watching_extras(kwargs, "NAME")
    return kwargs


def build_activity(media, started_at, end, player_name, paused=False, privacy=False,
                   hide_button=False):
    """Discord card eka. started_at / end = timer / progress bar (None nam kisima ekak nae)."""
    if privacy or not media.matched:
        return build_generic_activity(started_at, player_name, paused, end, hide_button)
    details = media.display_title()
    state = media.subtitle()
    if paused:
        state = f"Paused \u00b7 {state}"
    kwargs = {
        "details": details[:128].ljust(2),
        "state": state[:128].ljust(2),
    }
    _timestamps(kwargs, started_at, end, paused)
    if media.poster and len(media.poster) <= 256:
        kwargs["large_image"] = media.poster
        kwargs["large_text"] = f"{details} \u00b7 {player_name}"[:128]
    elif FALLBACK_IMAGE:
        kwargs["large_image"] = FALLBACK_IMAGE
        kwargs["large_text"] = f"{details} \u00b7 {player_name}"[:128]
    # Card eke yata "Get Media RPC" button eka
    if "buttons" in UPDATE_PARAMS and not hide_button:
        kwargs["buttons"] = [{"label": PROJECT_BUTTON, "url": PROJECT_URL}]
    _watching_extras(kwargs, "DETAILS")
    return kwargs


def same_activity(a, b):
    """Discord ekata kalin yawapu eka samanai da (timestamps TIMESTAMP_TOLERANCE athule nam samanai)."""
    if a is None or b is None or a.keys() != b.keys():
        return False
    for key, value in a.items():
        if key in ("start", "end"):
            if abs(value - b[key]) > TIMESTAMP_TOLERANCE:
                return False
        elif value != b[key]:
            return False
    return True


# ---------------------------------------------------------------- Background worker

class RpcWorker(threading.Thread):
    """Discord ekata connect wela player eke film eka yawana thread eka."""

    def __init__(self, events, settings):
        super().__init__(daemon=True)
        self.events = events
        self.settings = settings
        self.stop_event = threading.Event()

    def emit(self, kind, payload=None):
        self.events.put((kind, payload))

    def run(self):
        cfg = self.settings
        rpc = None
        last_key = None
        media = None
        player_name = ""
        last_lookup = 0.0
        # Pause / resume tracking: play una welawa witharai gananawa, resume karaddi
        # kalin thibba thanin patan gannawa. (Player eken position ganna ba nam meka use wenawa.)
        played = 0.0          # pause wenakan play una seconds
        play_since = None     # dan play wenawanam patan gaththa welawa
        paused = False
        pause_seen_at = 0.0
        pause_polls = 0       # pause kiyala hithanna consecutive polls (flicker nawaththanna)
        last_sent = None      # Discord ekata kalin yawapu activity eka (duplicate nawaththanna)
        last_sent_at = 0.0
        shown = False         # Discord eke dan status ekak thiyenawada (last_sent reset una unath wenas wenne nae)
        last_cfg = None

        while not self.stop_event.is_set():
            try:
                if rpc is None:
                    self.emit("status", "connecting")
                    rpc = Presence(CLIENT_ID)
                    rpc.connect()
                    self.emit("status", "connected")
                    last_sent, shown = None, False

                # Card eka penna widiya wenas karana settings wenas unoth aye yawanna
                cfg_now = (bool(cfg.get("hide_button")), bool(cfg.get("hide_when_paused")),
                           bool(cfg.get("show_progress")))
                if cfg_now != last_cfg:
                    last_cfg, last_sent = cfg_now, None

                web_sites = web_tabs.parse_sites(cfg.get("web_sites")) if cfg.get("web_enabled") else None
                playing = players.find_playing(web_sites or None)
                if playing is not None and playing.site and not media_info.resolve(playing.title).matched:
                    # Listed site, but this tab isn't a film or series (home page, search, ...): ignore it.
                    # The lookup is cached, so this doesn't hit the network on every poll.
                    playing = None
                if playing is None:
                    if last_key is not None:
                        rpc.clear()
                        last_key = media = last_sent = None
                        shown = False
                        self.emit("watching", None)
                else:
                    player_name, raw = playing.player.name, playing.title
                    privacy = bool(cfg.get("privacy_mode"))
                    key = (player_name, raw, privacy)
                    if key != last_key:
                        # Privacy mode: film nama online hoyanne nae (file nama kisima thanakata yanne nae)
                        media = media_info.Media(title="") if privacy else media_info.resolve(raw)
                        played, play_since = 0.0, time.time()
                        paused, pause_polls = False, 0
                        last_key, last_lookup, last_sent = key, time.time(), None
                        self.emit("watching", (media, player_name, privacy))
                    elif (not privacy and not (media.matched and media.poster)
                          and time.time() - last_lookup >= POSTER_RETRY_SECONDS):
                        # poster hambuna nae: network fail wela wage nam aye try karanna
                        # (media_info eke cache eka nisa hamadama network ekata yanne nae)
                        last_lookup = time.time()
                        retry = media_info.resolve(raw)
                        if retry != media:
                            media, last_sent = retry, None
                            self.emit("watching", (media, player_name, privacy))

                    # Player eken position + duration (progress bar ekata)
                    show_progress = bool(cfg.get("show_progress"))
                    is_web = bool(playing.site)       # a browser tab can't tell us the position
                    pb = (playback.read(player_name, playing.hwnd, cfg)
                          if show_progress and not is_web else None)
                    self.emit("progress", (pb, playback.hint(player_name, pb, show_progress, is_web)))

                    # pause / resume. Player eka thamai pause kiyala kiwwoth eka dan ma shiyawenawa.
                    now = time.time()
                    api_paused = pb.paused if pb is not None else None
                    paused_now = playing.paused if api_paused is None else api_paused
                    confirm = 1 if api_paused is not None else PAUSE_CONFIRM_POLLS
                    pause_polls = pause_polls + 1 if paused_now else 0
                    if pause_polls == 1:
                        pause_seen_at = now      # pause wuna kiyala palaweni wara dakka welawa
                    if not paused and pause_polls >= confirm:
                        played += pause_seen_at - play_since
                        play_since, paused = None, True
                    elif paused and not paused_now:
                        play_since, paused = now, False

                    if paused and cfg.get("hide_when_paused"):
                        # "Pause wunama hide karanna": status eka ain karala resume wenakan inna
                        if shown:
                            rpc.clear()
                            shown = False
                        last_sent = None
                    else:
                        started_at = end = None
                        if not paused:
                            if pb is not None:
                                # Real position: seek karath hari, timer eka hari thanata enawa
                                started_at = int(now - pb.position)
                                if pb.duration > 0:
                                    end = int(now - pb.position + pb.duration)
                            else:
                                started_at = int((play_since or now) - played)
                        activity = build_activity(media, started_at, end, player_name, paused,
                                                  privacy, bool(cfg.get("hide_button")))
                        if (not same_activity(activity, last_sent)
                                and (last_sent is None or now - last_sent_at >= MIN_UPDATE_SECONDS)):
                            rpc.update(**activity)
                            last_sent, last_sent_at, shown = activity, now, True
            except Exception:
                # Discord close una / restart una wage welawal
                try:
                    if rpc:
                        rpc.close()
                except Exception:
                    pass
                rpc = None
                last_key = media = last_sent = None
                shown = False
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
        self.settings = app_settings.Settings()
        self.settings_win = None
        self.progress = None             # player eken ena position / duration (playback.Playback)
        self.progress_at = 0.0           # eka kiyawapu welawa (tick eke extrapolate karanna)

        root.title(APP_TITLE)
        root.geometry("380x570")
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
        self.hint_label = tk.Label(card, text="", bg=CARD, fg=MUTED, font=("Segoe UI", 8),
                                   anchor="w", justify="left", wraplength=310)
        self.hint_label.pack(fill="x", pady=(2, 0))

        # start / stop + settings buttons
        button_row = tk.Frame(root, bg=BG)
        button_row.pack(pady=(18, 8))
        self.button = tk.Button(button_row, text="Start", command=self.toggle, bg=ACCENT,
                                fg="white", activebackground=ACCENT_HOVER,
                                activeforeground="white", relief="flat", bd=0, cursor="hand2",
                                font=("Segoe UI", 11, "bold"), width=12, pady=8)
        self.button.pack(side="left", padx=(0, 8))
        tk.Button(button_row, text="Settings", command=self.open_settings, bg=CARD, fg=TEXT,
                  activebackground=CARD_HOVER, activeforeground=TEXT, relief="flat", bd=0,
                  cursor="hand2", font=("Segoe UI", 11, "bold"), width=12,
                  pady=8).pack(side="left")

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
        media, player_name, privacy = payload if payload else (None, "", False)
        if media is None:
            self.progress, self.progress_at = None, 0.0
            self.hint_label.config(text="")
        hidden = media is not None and (privacy or not media.matched)    # Discord ekata title eka yanne nae
        if self.tray is not None:
            try:      # tray icon eke hover tooltip eka (127 akuru wala sima ekak thiyenawa)
                tip = APP_TITLE
                if media is not None:
                    tip = (f"Watching {player_name}" if hidden
                           else f"{media.display_title()} {media.subtitle()}")
                self.tray.title = tip[:127]
            except Exception:
                pass
        if hidden:
            self.heading_label.config(text=f"NOW WATCHING · {player_name.upper()}")
            self.title_label.config(text=f"Watching {player_name}")
            self.sub_label.config(text="")
            self.poster_label.config(
                text="Privacy mode: title hidden on Discord" if privacy
                else "Not a movie / TV series (title hidden on Discord)")
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
        self.worker = RpcWorker(self.events, self.settings)
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
                pystray.MenuItem("Settings",
                                 lambda icon, item: self.commands.put("settings")),
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

    def open_settings(self):
        if self.settings_win is not None and self.settings_win.alive():
            self.settings_win.focus()
            return
        self.settings_win = settings_window.SettingsWindow(self.root, self.settings)

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
                elif cmd == "settings":
                    self.show_window()
                    self.open_settings()
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
                elif kind == "progress":
                    self.set_progress(payload)
        except queue.Empty:
            pass
        self.root.after(200, self.process_events)

    def set_progress(self, payload):
        self.progress, hint = payload
        self.progress_at = time.time()
        self.hint_label.config(text=hint or "")
        self.refresh_elapsed()

    @staticmethod
    def clock(seconds):
        h, rem = divmod(max(int(seconds), 0), 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}"

    def refresh_elapsed(self):
        """Real position / duration (player eken) nathnam elapsed timer eka."""
        if self.watch_started is None:
            return
        pb = self.progress
        if pb is None:
            text = f"Elapsed {self.clock(time.time() - self.watch_started)}"
        else:
            position = pb.position + (0 if pb.paused else time.time() - self.progress_at)
            if pb.duration > 0:
                text = f"{self.clock(min(position, pb.duration))} / {self.clock(pb.duration)}"
            else:
                text = self.clock(position)
            if pb.paused:
                text += "  ·  Paused"
        self.elapsed_label.config(text=text)

    def tick(self):
        self.refresh_elapsed()
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
        # Desktop shortcut eka (background thread ekak: PowerShell eka tikak welawak yanawa)
        threading.Thread(target=sysint.create_desktop_shortcut, daemon=True).start()

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
