"""
Films playing on websites, found through the browser's window title.

A browser window's title is "<tab title> - <browser name>" and only shows the ACTIVE tab.
Media RPC only looks at tabs whose title contains one of the site names the user listed in
Settings, and the title it extracts is still confirmed online as a real film or series before
anything is shown on Discord (see media_rpc.py). Other tabs are ignored.

Limits: sites that don't put the film name in the tab title (Netflix shows just "Netflix")
can't be detected this way, and the position of the video isn't available.
"""

import re
from dataclasses import dataclass

MAX_SITES = 30


@dataclass(frozen=True)
class Browser:
    name: str
    exe_prefixes: tuple     # process exe name starts with one of these (lowercase)
    app_re: str             # browser name at the end of the window title (regex)


BROWSERS = (
    Browser("Chrome", ("chrome",), r"Google Chrome"),
    Browser("Edge", ("msedge",), r"Microsoft[​\s]*Edge"),     # Edge puts a zero-width space in
    Browser("Firefox", ("firefox",), r"Mozilla Firefox"),
    Browser("Brave", ("brave",), r"Brave"),
    Browser("Opera", ("opera",), r"Opera(?: GX)?"),
    Browser("Vivaldi", ("vivaldi",), r"Vivaldi"),
)

SEPARATORS = "-–—|:·•"            # - en dash, em dash, | : middle dot, bullet
_EDGE_PUNCT = re.compile(rf"^[\s{re.escape(SEPARATORS)}]+|[\s{re.escape(SEPARATORS)}]+$")
_DOUBLE_SEP = re.compile(rf"\s*[{re.escape(SEPARATORS)}]\s*(?:[{re.escape(SEPARATORS)}]\s*)+")

# Words sites add around a film name. "full movie" only: a bare "movie" can be part of a title.
_NOISE = re.compile(
    r"\b(?:watch(?:ing)?|online|free|full movie|streaming|stream|download|"
    r"(?:sinhala|english|hindi|tamil)\s+sub(?:title)?s?|subtitles?)\b",
    re.I,
)


def browser_for_exe(exe):
    """Browser for a process exe name (lowercase), or None."""
    for browser in BROWSERS:
        if exe.startswith(browser.exe_prefixes):
            return browser
    return None


def tab_title(browser, window_title):
    """Active tab title from a browser window title, or None if it isn't a normal browser title."""
    text = (window_title or "").strip()
    match = re.search(rf"\s+[-–—]\s+{browser.app_re}\s*$", text, re.I)
    if not match:
        return None
    tab = text[: match.start()]
    # Edge: "Title and 3 more pages - Profile"
    tab = re.sub(r"\s+and \d+ more pages?(?:\s+[-\u2013\u2014]\s+[^-\u2013\u2014]{1,30})?$", "", tab)
    tab = re.sub(r"^\(\d+\)\s+", "", tab)                    # "(3) Title": unread counters
    return tab.strip() or None


def parse_sites(value):
    """Site names from a list or a multi-line string: trimmed, unique, 2-60 characters."""
    if isinstance(value, str):
        value = value.splitlines()
    sites, seen = [], set()
    for item in value or []:
        name = " ".join(str(item).split())
        key = name.lower()
        if 2 <= len(name) <= 60 and key not in seen:
            seen.add(key)
            sites.append(name)
    return sites[:MAX_SITES]


def extract_title(tab, site):
    """Tab title with the site name, separators and filler words ("Watch", "Online") removed."""
    index = tab.lower().find(site.lower())
    if index < 0:
        return None
    before, after = tab[:index], tab[index + len(site):]
    # "Film - Site - tagline": the film is what comes before the site name. Only when nothing
    # useful is before it ("Site - Film") use what comes after it.
    for part in (before, after):
        text = _DOUBLE_SEP.sub(" - ", part)
        text = _NOISE.sub(" ", text)
        text = _DOUBLE_SEP.sub(" - ", re.sub(r"\s+", " ", text))
        text = _EDGE_PUNCT.sub("", text).strip()
        if len(text) >= 2:
            return text
    return None


def guess_title(tab):
    """Film name from a tab title on a site we don't know: the part before the first
    " - " / " | " (that is where sites put their own name), minus filler words."""
    first = re.split(r"\s[-\u2013\u2014|\u00b7\u2022]\s", tab.strip(), 1)[0]
    text = re.sub(r"\s+", " ", _NOISE.sub(" ", first))
    text = _EDGE_PUNCT.sub("", text).strip()
    return text if 2 <= len(text) <= 100 else None


def match_site(tab, sites):
    """(site, title) for the first listed site found in the tab title, else None."""
    for site in sites:
        title = extract_title(tab, site)
        if title:
            return site, title
    return None
