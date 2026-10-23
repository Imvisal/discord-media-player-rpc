"""
Settings window: what the Discord card shows, and how to switch on the progress bar for
players that need their web interface (VLC, MPC-HC, MPC-BE).

Checkboxes apply immediately: the Discord worker reads the settings on every poll.
"""

import tkinter as tk

import playback
from app_settings import clean_port
from theme import BG, CARD, CARD_HOVER, ERROR, GREEN, MUTED, TEXT

FONT = "Segoe UI"


class SettingsWindow:
    def __init__(self, root, settings):
        self.settings = settings
        self._vars = []          # BooleanVars: tkinter drops them if we don't keep a reference

        self.win = tk.Toplevel(root)
        self.win.title("Media RPC settings")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        try:
            self.win.geometry(f"+{root.winfo_rootx() + 30}+{root.winfo_rooty() + 30}")
        except tk.TclError:
            pass

        body = tk.Frame(self.win, bg=BG, padx=22, pady=16)
        body.pack(fill="both", expand=True)

        self._heading(body, "Discord status")
        self._check(body, "hide_when_paused", "Hide my status while the video is paused",
                    "When off, the card says \"Paused\" and the timer stops.")
        self._check(body, "hide_button", "Hide the \"Get Media RPC\" button")
        self._check(body, "privacy_mode", "Privacy mode: hide the film name",
                    "Discord only shows \"Watching <player>\". The title and poster are not shown, "
                    "and the file name is not looked up online.")
        self._check(body, "show_progress", "Show a progress bar when the player allows it",
                    "Turn off to show a simple elapsed timer instead.")

        self._heading(body, "Progress bar setup", top=14)
        tk.Label(body, text="PotPlayer works automatically. VLC, MPC-HC and MPC-BE only share their "
                            "position through their web interface, so switch it on once:",
                 bg=BG, fg=MUTED, font=(FONT, 9), justify="left", wraplength=400).pack(anchor="w")

        # VLC
        self._sub(body, "VLC")
        self._note(body, "Tools > Preferences > Show settings: All > Interface > Main interfaces: "
                         "tick \"Web\". Then Main interfaces > Lua > Lua HTTP: set a Password. "
                         "Restart VLC.")
        row = tk.Frame(body, bg=BG)
        row.pack(anchor="w", pady=(4, 0))
        self.vlc_port = self._entry(row, "Port", self.settings.get("vlc_port"), 6)
        self.vlc_password = self._entry(row, "Password", self.settings.get("vlc_password"), 14,
                                        show="•")
        self._button(row, "Test", lambda: self._test("vlc")).pack(side="left", padx=(10, 0))

        # MPC
        self._sub(body, "MPC-HC / MPC-BE")
        self._note(body, "View > Options > Player > Web Interface: tick \"Listen on port\" "
                         "(default 13579).")
        row = tk.Frame(body, bg=BG)
        row.pack(anchor="w", pady=(4, 0))
        self.mpc_port = self._entry(row, "Port", self.settings.get("mpc_port"), 6)
        self._button(row, "Test", lambda: self._test("mpc")).pack(side="left", padx=(10, 0))

        self.result = tk.Label(body, text="", bg=BG, fg=MUTED, font=(FONT, 9), justify="left",
                               wraplength=400)
        self.result.pack(anchor="w", pady=(10, 0))

        self._note(body, "These only talk to your own PC (127.0.0.1). The VLC password is saved "
                         "in plain text in your Media RPC settings file.", top=8)

        self._button(body, "Close", self.close, wide=True).pack(pady=(16, 0))
        self.win.protocol("WM_DELETE_WINDOW", self.close)      # X eken close karath save wenawa

    # -- small widget helpers -------------------------------------------------

    def _heading(self, parent, text, top=0):
        tk.Label(parent, text=text.upper(), bg=BG, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(anchor="w", pady=(top, 6))

    def _sub(self, parent, text):
        tk.Label(parent, text=text, bg=BG, fg=TEXT,
                 font=(FONT, 10, "bold")).pack(anchor="w", pady=(10, 0))

    def _note(self, parent, text, top=0):
        tk.Label(parent, text=text, bg=BG, fg=MUTED, font=(FONT, 8), justify="left",
                 wraplength=400).pack(anchor="w", pady=(top, 0))

    def _check(self, parent, key, text, note=None):
        var = tk.BooleanVar(value=bool(self.settings.get(key)))
        self._vars.append(var)
        tk.Checkbutton(parent, text=text, variable=var,
                       command=lambda: self.settings.set(key, bool(var.get())),
                       bg=BG, fg=TEXT, selectcolor=CARD, activebackground=BG,
                       activeforeground=TEXT, highlightthickness=0, bd=0, cursor="hand2",
                       font=(FONT, 10)).pack(anchor="w")
        if note:
            tk.Label(parent, text=note, bg=BG, fg=MUTED, font=(FONT, 8), justify="left",
                     wraplength=380).pack(anchor="w", padx=(24, 0), pady=(0, 6))

    def _entry(self, parent, label, value, width, show=None):
        tk.Label(parent, text=label, bg=BG, fg=TEXT, font=(FONT, 9)).pack(side="left",
                                                                         padx=(0, 4))
        entry = tk.Entry(parent, width=width, bg=CARD, fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=(FONT, 10), show=show or "")
        entry.insert(0, "" if value is None else str(value))
        entry.pack(side="left", padx=(0, 10), ipady=3)
        return entry

    def _button(self, parent, text, command, wide=False):
        return tk.Button(parent, text=text, command=command, bg=CARD, fg=TEXT,
                         activebackground=CARD_HOVER, activeforeground=TEXT, relief="flat",
                         bd=0, cursor="hand2", font=(FONT, 10, "bold"),
                         width=14 if wide else 6, pady=4)

    # -- actions ----------------------------------------------------------------

    def _save_web_fields(self):
        """Port / password fields -> settings. False (and a message) if a port is invalid."""
        ports = {}
        for key, entry in (("vlc_port", self.vlc_port), ("mpc_port", self.mpc_port)):
            port = clean_port(entry.get(), None)
            if port is None:
                self._say("Ports are numbers from 1 to 65535.", ERROR)
                return False
            ports[key] = port
        for key, port in ports.items():
            self.settings.set(key, port)
        self.settings.set("vlc_password", self.vlc_password.get())
        return True

    def close(self):
        self._save_web_fields()          # invalid port: keep the old one, close anyway
        self.win.destroy()

    def _test(self, kind):
        if not self._save_web_fields():
            return
        ok, message = playback.check_web_interface(kind, self.settings)
        self._say(message, GREEN if ok else ERROR)

    def _say(self, text, color):
        self.result.config(text=text, fg=color)

    # -- window state -----------------------------------------------------------

    def alive(self):
        try:
            return bool(self.win.winfo_exists())
        except tk.TclError:
            return False

    def focus(self):
        try:
            self.win.deiconify()
            self.win.lift()
            self.win.focus_force()
        except tk.TclError:
            pass
