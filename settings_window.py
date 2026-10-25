"""
Settings window, in three tabs so it fits on a small screen:

  Status        what the Discord card shows (pause, button, privacy, progress bar)
  Websites      detect films in browser tabs of the sites you list
  Progress bar  how to switch on the web interface of VLC / MPC-HC / MPC-BE

Checkboxes apply immediately: the Discord worker reads the settings on every poll.
Text fields (ports, password, site list) are saved by Test / Check / Close.
"""

import tkinter as tk

import playback
import players
import web_tabs
from app_settings import clean_port
from theme import BG, CARD, CARD_HOVER, ERROR, GREEN, MUTED, TEXT

FONT = "Segoe UI"
WRAP = 420
TABS = (("status", "Status"), ("websites", "Websites"), ("progress", "Progress bar"))


class SettingsWindow:
    def __init__(self, root, settings):
        self.settings = settings
        self._vars = []          # BooleanVars: tkinter drops them if we don't keep a reference
        self._tab_buttons = {}
        self._pages = {}

        self.win = tk.Toplevel(root)
        self.win.title("Media RPC settings")
        self.win.configure(bg=BG)
        self.win.resizable(False, False)
        try:
            self.win.geometry(f"+{root.winfo_rootx() + 30}+{root.winfo_rooty() + 30}")
        except tk.TclError:
            pass

        outer = tk.Frame(self.win, bg=BG, padx=22, pady=16)
        outer.pack(fill="both", expand=True)

        bar = tk.Frame(outer, bg=BG)
        bar.pack(fill="x", pady=(0, 14))
        for key, label in TABS:
            button = tk.Button(bar, text=label, command=lambda k=key: self._show(k), relief="flat",
                               bd=0, cursor="hand2", font=(FONT, 10, "bold"), padx=14, pady=6,
                               activeforeground=TEXT)
            button.pack(side="left", padx=(0, 6))
            self._tab_buttons[key] = button

        self.stage = tk.Frame(outer, bg=BG, width=WRAP + 10, height=1)
        self.stage.pack(fill="both", expand=True)
        for key, _label in TABS:
            self._pages[key] = tk.Frame(self.stage, bg=BG)
        self._build_status(self._pages["status"])
        self._build_websites(self._pages["websites"])
        self._build_progress(self._pages["progress"])

        # One line under the active page for results of Test / Check
        self.result = tk.Label(outer, text="", bg=BG, fg=MUTED, font=(FONT, 9), justify="left",
                               wraplength=WRAP, anchor="w")
        self.result.pack(fill="x", pady=(10, 0))

        self._button(outer, "Close", self.close, wide=True).pack(pady=(14, 0))
        self.win.protocol("WM_DELETE_WINDOW", self.close)      # X eken close karath save wenawa
        self._show("status")

    # -- pages ------------------------------------------------------------------

    def _build_status(self, page):
        self._check(page, "hide_when_paused", "Hide my status while the video is paused",
                    "When off, the card says \"Paused\" and the timer stops.")
        self._check(page, "hide_button", "Hide the \"Get Media RPC\" button")
        self._check(page, "privacy_mode", "Privacy mode: hide the film name",
                    "Discord only shows \"Watching <player>\". The title and poster are not shown, "
                    "and a local file's name is not looked up online.")
        self._check(page, "show_progress", "Show a progress bar when the player allows it",
                    "Turn off to show a simple elapsed timer instead.")

    def _build_websites(self, page):
        self._check(page, "web_enabled", "Detect films on websites in my browser",
                    "Reads the tab title of Chrome, Edge, Firefox, Brave, Opera and Vivaldi. Leave the "
                    "list empty to detect any site: only a tab that is playing sound is looked at, "
                    "and only a real film or series is shown.")
        self._check(page, "web_youtube", "Also detect films and series on YouTube",
                    "Off by default. Only a YouTube tab that is playing sound is looked at, and "
                    "only a real film or series is shown.")
        tk.Label(page, text="Optional: only these sites, one per line, as written in the tab title:",
                 bg=BG, fg=TEXT, font=(FONT, 9), justify="left", wraplength=WRAP).pack(anchor="w",
                                                                                     pady=(6, 4))
        self.sites_box = tk.Text(page, height=5, width=42, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                 relief="flat", font=(FONT, 10), wrap="none", padx=8, pady=6)
        self.sites_box.insert("1.0", "\n".join(self.settings.get("web_sites") or []))
        self.sites_box.pack(anchor="w")
        row = tk.Frame(page, bg=BG)
        row.pack(anchor="w", pady=(8, 0))
        self._button(row, "What do I see now?", self._scan, width=18).pack(side="left")
        self._note(page, "A title from a listed site is checked online to confirm it's a real film or "
                         "series before anything is shown on Discord. Home pages, search pages and "
                         "other tabs are ignored.", top=10)
        self._note(page, "Limits: sites that don't put the film name in the tab title (Netflix shows "
                         "just \"Netflix\") can't be detected, and a browser can't share the video "
                         "position, so the card shows an elapsed timer instead of a progress bar. "
                         "Only the tab you're looking at in each window is visible.", top=6)

    def _build_progress(self, page):
        tk.Label(page, text="PotPlayer works automatically. VLC, MPC-HC and MPC-BE only share their "
                            "position through their web interface, so switch it on once:",
                 bg=BG, fg=MUTED, font=(FONT, 9), justify="left", wraplength=WRAP).pack(anchor="w")

        self._sub(page, "VLC")
        self._note(page, "Tools > Preferences > Show settings: All > Interface > Main interfaces: "
                         "tick \"Web\". Then Main interfaces > Lua > Lua HTTP: set a Password. "
                         "Restart VLC.")
        row = tk.Frame(page, bg=BG)
        row.pack(anchor="w", pady=(4, 0))
        self.vlc_port = self._entry(row, "Port", self.settings.get("vlc_port"), 6)
        self.vlc_password = self._entry(row, "Password", self.settings.get("vlc_password"), 14,
                                        show="•")
        self._button(row, "Test", lambda: self._test("vlc")).pack(side="left", padx=(10, 0))

        self._sub(page, "MPC-HC / MPC-BE")
        self._note(page, "View > Options > Player > Web Interface: tick \"Listen on port\" "
                         "(default 13579).")
        row = tk.Frame(page, bg=BG)
        row.pack(anchor="w", pady=(4, 0))
        self.mpc_port = self._entry(row, "Port", self.settings.get("mpc_port"), 6)
        self._button(row, "Test", lambda: self._test("mpc")).pack(side="left", padx=(10, 0))

        self._note(page, "These only talk to your own PC (127.0.0.1). The VLC password is saved "
                         "in plain text in your Media RPC settings file.", top=10)

    # -- small widget helpers -------------------------------------------------

    def _sub(self, parent, text):
        tk.Label(parent, text=text, bg=BG, fg=TEXT,
                 font=(FONT, 10, "bold")).pack(anchor="w", pady=(10, 0))

    def _note(self, parent, text, top=0):
        tk.Label(parent, text=text, bg=BG, fg=MUTED, font=(FONT, 8), justify="left",
                 wraplength=WRAP).pack(anchor="w", pady=(top, 0))

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
                     wraplength=WRAP - 20).pack(anchor="w", padx=(24, 0), pady=(0, 8))

    def _entry(self, parent, label, value, width, show=None):
        tk.Label(parent, text=label, bg=BG, fg=TEXT, font=(FONT, 9)).pack(side="left",
                                                                         padx=(0, 4))
        entry = tk.Entry(parent, width=width, bg=CARD, fg=TEXT, insertbackground=TEXT,
                         relief="flat", font=(FONT, 10), show=show or "")
        entry.insert(0, "" if value is None else str(value))
        entry.pack(side="left", padx=(0, 10), ipady=3)
        return entry

    def _button(self, parent, text, command, wide=False, width=6):
        return tk.Button(parent, text=text, command=command, bg=CARD, fg=TEXT,
                         activebackground=CARD_HOVER, activeforeground=TEXT, relief="flat",
                         bd=0, cursor="hand2", font=(FONT, 10, "bold"),
                         width=14 if wide else width, pady=4)

    # -- tabs -------------------------------------------------------------------

    def _show(self, key):
        for name, page in self._pages.items():
            page.pack_forget()
            active = name == key
            self._tab_buttons[name].config(bg=CARD if active else BG, fg=TEXT if active else MUTED,
                                           activebackground=CARD_HOVER)
        self._pages[key].pack(fill="both", expand=True)
        self._say("", MUTED)

    # -- actions ----------------------------------------------------------------

    def _save_web_fields(self):
        """Ports, password and site list -> settings. False (and a message) if a port is invalid."""
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
        self._save_sites()
        return True

    def _save_sites(self):
        sites = web_tabs.parse_sites(self.sites_box.get("1.0", "end"))
        self.settings.set("web_sites", sites)
        return sites

    def _test(self, kind):
        if not self._save_web_fields():
            return
        ok, message = playback.check_web_interface(kind, self.settings)
        self._say(message, GREEN if ok else ERROR)

    def _scan(self):
        """'What do I see now?': the active tab of every browser window and what would match."""
        sites = self._save_sites()
        try:
            tabs = players.browser_tabs()
        except Exception:
            self._say("Can't read browser windows here.", ERROR)
            return
        if not tabs:
            self._say("No browser window found. Open the site in Chrome, Edge, Firefox, Brave, "
                      "Opera or Vivaldi first.", MUTED)
            return
        lines, hit = [], False
        for browser, tab in tabs[:6]:
            match = web_tabs.match_site(tab, sites) if sites else None
            shown = tab if len(tab) <= 60 else tab[:57] + "..."
            if match:
                hit = True
                lines.append(f"{browser}: \"{shown}\"  ->  {match[1]}")
            else:
                lines.append(f"{browser}: \"{shown}\"  (not on your list)")
        if not sites:
            lines.append("Add the site's name above (as it appears in the tab title) to detect it.")
        self._say("\n".join(lines), GREEN if hit else MUTED)

    def _say(self, text, color):
        self.result.config(text=text, fg=color)

    def close(self):
        self._save_web_fields()          # invalid port: keep the old one, close anyway
        self.win.destroy()

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
