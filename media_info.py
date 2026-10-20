"""
File nama eken film / TV series / episode eka hoyagena poster eka online hoyana module eka.

- Nama parse karanawa (S01E01, 1x01, "Show - 05", year, quality tags ain karala).
- TV series walata TVmaze (key one nae), film walata iTunes Search (key one nae) use karanawa.
- Network fail unath app eka nawathinne nae, poster nathuwa wada karanawa.
"""

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from typing import Optional

VIDEO_EXT = re.compile(r"\.(mkv|mp4|avi|mov|wmv|flv|webm|m4v|ts|mpg|mpeg)$", re.I)

QUALITY = re.compile(
    r"\b(?:480p|576p|720p|1080p|1440p|2160p|4k|uhd|blu-?ray|brrip|bdrip|web-?rip|web-?dl|"
    r"hdrip|hdtv|dvdrip|dvdscr|dvd|cam|x264|x265|h ?26[45]|hevc|avc|aac|ac3|dts|10bit|"
    r"remux|proper|repack|extended|unrated|sinhala|sub|subs|dual|multi)\b",
    re.I,
)

# (season, episode) deka ena patterns, nathnam (episode) witharai
EPISODE_PATTERNS = [
    re.compile(r"\bS(\d{1,2})\s?E(\d{1,3})(?!\d)", re.I),
    re.compile(r"\bSeason\s*(\d{1,2})\s*Episode\s*(\d{1,3})(?!\d)", re.I),
    re.compile(r"\b(\d{1,2})x(\d{2,3})(?!\d)", re.I),
    re.compile(r"\s-\s(\d{1,3})(?:v\d)?(?=\s|$)"),          # anime: "Show - 05"
]

YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?![\dxXpP])")

USER_AGENT = {"User-Agent": "MediaRPC/1.0 (+https://github.com/Imvisal/discord-media-player-rpc)"}
TIMEOUT = 5


@dataclass
class Media:
    title: str
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_title: Optional[str] = None
    poster: Optional[str] = None
    info_url: Optional[str] = None      # Discord button eka yana page eka (TVmaze / Apple TV)
    info_label: Optional[str] = None    # button eke nama

    @property
    def is_series(self):
        return self.episode is not None

    def display_title(self):
        if self.is_series:
            return self.title
        return f"{self.title} ({self.year})" if self.year else self.title

    def subtitle(self):
        if not self.is_series:
            return "Movie"
        bits = []
        if self.season is not None:
            bits.append(f"S{self.season}")
        bits.append(f"E{self.episode}")
        text = " ".join(bits)
        if self.episode_title:
            text += f" · {self.episode_title}"
        return text


# ---------------------------------------------------------------- parsing

def _tidy(text):
    text = re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", " ", text)
    text = re.sub(r"[\[\]\(\)\{\}]", " ", text)
    return re.sub(r"\s+", " ", text).strip(" -–")


def parse_filename(raw):
    s = VIDEO_EXT.sub("", raw.strip())
    s = re.sub(r"[._]+", " ", s)
    s = re.sub(r"^\s*\[[^\]]*\]\s*", "", s)          # [ReleaseGroup] ain karanna

    season = episode = year = None
    title_part = None

    for pat in EPISODE_PATTERNS:
        m = pat.search(s)
        if m and m.start() > 0:
            groups = m.groups()
            if len(groups) == 2:
                season, episode = int(groups[0]), int(groups[1])
            else:
                episode = int(groups[0])
            title_part = s[: m.start()]
            break

    if title_part is None:
        for ym in YEAR.finditer(s):
            if ym.start() > 0:
                title_part = s[: ym.start()]
                year = int(ym.group(1))
                break

    if title_part is None:
        qm = QUALITY.search(s)
        title_part = s[: qm.start()] if qm and qm.start() > 0 else s

    # "Show (2005) S01E01" wage welawal title eke year eka ain karanna
    for ym in YEAR.finditer(title_part):
        if ym.start() > 0:
            year = year or int(ym.group(1))
            title_part = title_part[: ym.start()]
            break

    title = _tidy(title_part) or _tidy(s) or raw
    return Media(title=title, year=year, season=season, episode=episode)


# ---------------------------------------------------------------- online lookup

def _get_json(url):
    req = urllib.request.Request(url, headers=USER_AGENT)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


def _tvmaze(media):
    show = _get_json(
        "https://api.tvmaze.com/singlesearch/shows?q=" + urllib.parse.quote(media.title)
    )
    image = show.get("image") or {}
    found = replace(
        media,
        title=show.get("name") or media.title,
        poster=image.get("original") or image.get("medium"),
        info_url=show.get("url"),
        info_label="View on TVmaze",
    )
    if media.season is not None and media.episode is not None:
        try:
            ep = _get_json(
                f"https://api.tvmaze.com/shows/{show['id']}/episodebynumber"
                f"?season={media.season}&number={media.episode}"
            )
            found = replace(found, episode_title=ep.get("name"))
        except Exception:
            pass
    return found


def _itunes_movie(media):
    term = media.title + (f" {media.year}" if media.year else "")
    data = _get_json(
        "https://itunes.apple.com/search?media=movie&entity=movie&limit=5&term="
        + urllib.parse.quote(term)
    )
    results = data.get("results") or []
    if not results:
        return None
    pick = results[0]
    if media.year:
        for r in results:
            if str(r.get("releaseDate", "")).startswith(str(media.year)):
                pick = r
                break
    art = pick.get("artworkUrl100")
    if not art:
        return None
    return replace(
        media,
        title=pick.get("trackName") or media.title,
        poster=art.replace("100x100bb", "600x600bb"),
        info_url=pick.get("trackViewUrl"),
        info_label="View on Apple TV",
    )


def _lookup(media):
    if media.is_series:
        return _tvmaze(media)
    found = None
    try:
        found = _itunes_movie(media)
    except Exception:
        pass
    if found is None:
        try:
            found = _tvmaze(media)
            # series match una, namuth meka film ekak (episode nae) nisa episode data nae
        except Exception:
            pass
    return found or media


_cache = {}


def resolve(raw):
    """File nama eken Media object ekak return karanawa (poster ekka). Nothing raise karanne nae."""
    parsed = parse_filename(raw)
    key = (parsed.title.lower(), parsed.year, parsed.season, parsed.episode)
    if key in _cache:
        return _cache[key]
    media = parsed
    try:
        media = _lookup(parsed)
    except Exception:
        pass
    _cache[key] = media
    return media
