"""
File nama eken film / TV series / episode eka hoyagena poster eka online hoyana module eka.

- Nama parse karanawa (S01E01, 1x01, "Show - 05", year) saha quality / language / site tags
  (720p, x265, English, WEB-[CineSubz.com] wage) ain karanawa.
- TV series: TVmaze -> IMDb. Film: iTunes Search -> IMDb -> Wikipedia. (API key one nae)
- Hoyagaththa nama file eke namata hariyatama sasandenawa. Hariyata sasanda nathnam poster eka
  denne nae (wen film / series ekak pennanawata wada poster nathuwa title witharak pennana eka better).
- Network fail unath app eka nawathinne nae. Poster nathnam parana tika welawakin aye try karanawa.
"""

import difflib
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from typing import Optional

VIDEO_EXT = re.compile(
    r"\.(?:mkv|mp4|avi|mov|wmv|flv|webm|m4v|ts|m2ts|mpg|mpeg|ogm|ogv|3gp|rmvb|divx)$", re.I
)

# Hariyatama quality / release tags. Meka hambuna thanin passe okkoma title eken ain wenawa.
STRONG_TAGS = re.compile(
    r"\b(?:480p|576p|720p|1080p|1440p|2160p|4k|uhd|blu-?ray|brrip|bdrip|web-?rip|web-?dl|"
    r"hdrip|hdtv|dvdrip|dvdscr|hdcam|hdts|hdtc|camrip|x264|x265|h ?26[45]|hevc|avc|aac\d?|ac3|"
    r"eac3|ddp ?\d|dts|atmos|10bit|hdr10?|remux|amzn|dsnp|hmax|yify|yts|rarbg)\b",
    re.I,
)

# Bhasha / sub tags. Meka title ekata passe (iwarawe) thiyenakota witharai ain karanne,
# "The English Patient" wage nam wala weralata ain wenna epa.
LANG_TAGS = {
    "english", "hindi", "tamil", "telugu", "malayalam", "kannada", "korean", "japanese",
    "chinese", "french", "spanish", "german", "russian", "turkish", "thai", "urdu", "punjabi",
    "bengali", "sinhala", "sinhalasub", "dubbed", "subbed", "esub", "esubs", "subs",
    "subtitle", "subtitles", "dual", "multi",
}
WEAK_TAGS = LANG_TAGS | {
    "web", "hd", "hq", "full", "movie", "film", "cam", "dvd", "extended", "unrated", "uncut",
    "proper", "repack", "imax", "sub", "dub", "audio",
}

# (season, episode) deka ena patterns, nathnam (episode) witharai
EPISODE_PATTERNS = [
    re.compile(r"\bS(\d{1,2})\s?E(\d{1,3})(?!\d)", re.I),
    re.compile(r"\bSeason\s*(\d{1,2})\s*Episode\s*(\d{1,3})(?!\d)", re.I),
    re.compile(r"\b(\d{1,2})x(\d{1,3})(?!\d)", re.I),
    re.compile(r"\s-\s(\d{1,3})(?:v\d)?(?=\s|$)"),          # anime: "Show - 05"
]

YEAR = re.compile(r"(?<!\d)((?:19|20)\d{2})(?![\dxXpP])")
PAREN_YEAR = re.compile(r"[\(\[]\s*((?:19|20)\d{2})\s*[\)\]]")

USER_AGENT = {"User-Agent": "MediaRPC/1.1 (+https://github.com/Imvisal/discord-media-player-rpc)"}
TIMEOUT = 4

RETRY_AFTER_ERROR = 60        # network error ekak unoth aye try karanna (seconds)
RETRY_AFTER_NO_MATCH = 600    # hoyagaththe nae nam aye try karanna (seconds)


@dataclass
class Media:
    title: str
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    episode_title: Optional[str] = None
    poster: Optional[str] = None
    info_url: Optional[str] = None      # TVmaze / Apple TV / IMDb page eka
    info_label: Optional[str] = None
    matched: bool = False               # True = online (TVmaze/iTunes/IMDb/Wikipedia) film / series ekak widihata hambuna

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
    return re.sub(r"\s+", " ", text).strip(" -–—:,")


def _bare(word):
    return re.sub(r"^[\W_]+|[\W_]+$", "", word).lower()


def _strip_trailing_tags(text, force):
    """Title eke iwarawe thiyena language / quality tags ain karanawa (Avengers Endgame English WEB)."""
    words = text.split()
    i = len(words)
    tags = []
    while i > 0:
        w = _bare(words[i - 1])
        if not w:                       # "-" wage ekalu akuru
            i -= 1
            continue
        if w in WEAK_TAGS or STRONG_TAGS.fullmatch(w):
            tags.append(w)
            i -= 1
            continue
        break
    if i == 0 or not tags:
        return text
    # tag 2k ho ewa, nathnam tag ekak bracket / strong tag ekak langin thiyenakota (language ekak nam)
    if len(tags) >= 2 or (force and tags[0] in LANG_TAGS):
        return " ".join(words[:i])
    return text


def parse_filename(raw):
    s = VIDEO_EXT.sub("", raw.strip())
    s = re.sub(r"^\s*\[\d+\s*/\s*\d+\]\s*", "", s)                       # PotPlayer playlist "[1/5]"
    s = re.sub(
        r"^\s*www\.[\w.-]*?\.(?:com|net|org|lk|xyz|club|info|site|vip|to|cc|ws|me|tv|in|co|biz|top|pw|live)"
        r"\b[\s._-]*",
        "", s, flags=re.I,
    )                                                                     # "www.Site.com - " ain karanna
    # "CineSubz.com - Title", "Site.net_Title" wage (www nathi) site nama ain karanna.
    # Site nama ekata passe separator ekak ("-", "_", space) thiyenna ona.
    s = re.sub(
        r"^\s*[\w-]+\.(?:com|net|org|lk|xyz|club|info|site|vip|to|cc|ws|me|tv|in|co|biz|top|pw|live)"
        r"(?=[\s._-])[\s._-]*",
        "", s, flags=re.I,
    )
    trailing_group = bool(re.search(r"[\]\)\}]\s*$", s))                  # "...WEB-[CineSubz.com]"
    s = re.sub(r"[._]+", " ", s)
    s = re.sub(r"^(?:\s*\[[^\]]*\])+\s*", "", s)                          # [ReleaseGroup] ain karanna

    season = episode = year = None
    cut = None
    kind = None          # title eka kapapu thana: episode / year / tag

    for pat in EPISODE_PATTERNS:
        m = pat.search(s)
        if m and m.start() > 0:
            groups = m.groups()
            if len(groups) == 2:
                season, episode = int(groups[0]), int(groups[1])
            else:
                episode = int(groups[0])
            cut, kind = m.start(), "episode"
            break

    if cut is None:
        pm = PAREN_YEAR.search(s)
        if pm and pm.start() > 0:                       # "Title (2025)" -> hariyatama year eka
            year, cut, kind = int(pm.group(1)), pm.start(), "year"
        else:
            sq = STRONG_TAGS.search(s)
            limit = sq.start() if sq and sq.start() > 0 else len(s)
            years = [y for y in YEAR.finditer(s) if 0 < y.start() < limit]
            if years:                                   # "Blade Runner 2049 2017 ..." -> aluthma year eka
                ym = years[-1]
                year, cut, kind = int(ym.group(1)), ym.start(), "year"
            elif sq and sq.start() > 0:
                cut, kind = sq.start(), "tag"

    title_part = s[:cut] if cut is not None else s

    # "Show (2005) S01E01" wage welawal series title eke year eka ain karanna
    if episode is not None:
        for ym in YEAR.finditer(title_part):
            if ym.start() > 0:
                year = year or int(ym.group(1))
                title_part = title_part[: ym.start()]
                break

    title = _tidy(title_part)
    if kind in (None, "tag"):
        title = _strip_trailing_tags(title, force=(kind == "tag" or trailing_group))

    title = title.strip(" -–—:,") or _tidy(s) or raw
    return Media(title=title, year=year, season=season, episode=episode)


# ---------------------------------------------------------------- title matching

def _norm_words(text):
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " and ")
    words = re.findall(r"[a-z0-9]+", text)
    if len(words) > 1 and words[0] in ("the", "a", "an"):
        words = words[1:]
    return words


def _same_title(wanted, found):
    """File eke nama hoyagaththa nama ekka hariyatama samanada balanawa."""
    wa, wb = _norm_words(wanted), _norm_words(found)
    if not wa or not wb:
        return False
    ja, jb = "".join(wa), "".join(wb)
    if ja == jb:
        return True
    # "Zootopia" saha "Zootopia 2" wage ewa wenas film. Ilakkam samana wenna ona.
    if [w for w in wa if w.isdigit()] != [w for w in wb if w.isdigit()]:
        return False
    return difflib.SequenceMatcher(None, ja, jb).ratio() >= 0.88


def _year_of(text):
    m = re.match(r"\s*((?:19|20)\d{2})", str(text or ""))
    return int(m.group(1)) if m else None


def _year_ok(wanted, found):
    return not wanted or not found or abs(wanted - found) <= 1


# ---------------------------------------------------------------- online lookup

def _get_json(url):
    req = urllib.request.Request(url, headers=USER_AGENT)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.load(resp)


def _tvmaze(media):
    results = _get_json("https://api.tvmaze.com/search/shows?q=" + urllib.parse.quote(media.title))
    best = None
    for r in results or []:
        show = r.get("show") or {}
        if not _same_title(media.title, show.get("name")):
            continue
        sy = _year_of(show.get("premiered"))
        if not _year_ok(media.year, sy):
            continue
        score = 0 if (media.year and sy == media.year) else 1
        if best is None or score < best[0]:
            best = (score, show)
    if best is None:
        return None
    show = best[1]
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
    data = _get_json(
        "https://itunes.apple.com/search?media=movie&entity=movie&limit=15&term="
        + urllib.parse.quote(media.title)
    )
    best = None
    for r in data.get("results") or []:
        if not _same_title(media.title, r.get("trackName")):
            continue
        ry = _year_of(r.get("releaseDate"))
        if not _year_ok(media.year, ry):
            continue
        art = r.get("artworkUrl100")
        if not art:
            continue
        score = 0 if (media.year and ry == media.year) else 1
        if best is None or score < best[0]:
            best = (score, r, art)
    if best is None:
        return None
    _, pick, art = best
    return replace(
        media,
        title=pick.get("trackName") or media.title,
        poster=art.replace("100x100bb", "600x600bb"),
        info_url=pick.get("trackViewUrl"),
        info_label="View on Apple TV",
    )


def _imdb(media, series):
    """IMDb eke search suggestions (API key one nae)."""
    q = unicodedata.normalize("NFKD", media.title).encode("ascii", "ignore").decode().lower()
    q = re.sub(r"[^a-z0-9 ]", "", q).strip()
    if not q:
        return None
    first = q[0] if q[0].isalnum() else "x"
    data = _get_json(
        f"https://v2.sg.media-imdb.com/suggestion/titles/{first}/{urllib.parse.quote(q)}.json"
    )
    kinds = {"tvSeries", "tvMiniSeries"} if series else {"movie", "tvMovie"}
    best = None
    for r in data.get("d") or []:
        if r.get("qid") not in kinds or not _same_title(media.title, r.get("l")):
            continue
        if not _year_ok(media.year, r.get("y")):
            continue
        img = (r.get("i") or {}).get("imageUrl")
        if not img:
            continue
        score = 0 if (media.year and r.get("y") == media.year) else 1
        if best is None or score < best[0]:
            best = (score, r, img)
    if best is None:
        return None
    _, pick, img = best
    return replace(
        media,
        title=pick.get("l") or media.title,
        poster=img,
        info_url=f"https://www.imdb.com/title/{pick.get('id')}/" if pick.get("id") else None,
        info_label="View on IMDb",
    )


def _wikipedia_film(media):
    term = f"{media.title} {media.year} film" if media.year else f"{media.title} film"
    data = _get_json(
        "https://en.wikipedia.org/w/api.php?action=query&format=json&generator=search&gsrlimit=6"
        "&prop=pageimages&piprop=thumbnail&pithumbsize=600&gsrsearch=" + urllib.parse.quote(term)
    )
    pages = sorted(((data.get("query") or {}).get("pages") or {}).values(),
                   key=lambda p: p.get("index", 99))
    for p in pages:
        full = p.get("title") or ""
        name = re.sub(r"\s*\([^)]*\)\s*$", "", full)
        if not _same_title(media.title, name):
            continue
        suffix = re.search(r"\(([^)]*)\)\s*$", full)
        if suffix:
            # "(2025 film)" wage nam witharai; "(song)", "(TV series)" wage ewa ain karanna
            if not re.search(r"film|movie", suffix.group(1), re.I):
                continue
            if not _year_ok(media.year, _year_of(suffix.group(1))):
                continue
        thumb = (p.get("thumbnail") or {}).get("source")
        if not thumb:
            continue
        return replace(
            media,
            title=name,
            poster=thumb,
            info_url="https://en.wikipedia.org/wiki/" + urllib.parse.quote(full.replace(" ", "_")),
            info_label="View on Wikipedia",
        )
    return None


def _lookup(media):
    """(Media, kalin aye hoyanna ona welawa) return karanawa. Welawa None nam hari."""
    if media.is_series:
        sources = [_tvmaze, lambda m: _imdb(m, True)]
    else:
        sources = [_itunes_movie, lambda m: _imdb(m, False), _wikipedia_film]

    failed = 0
    best = None
    for source in sources:
        try:
            found = source(media)
        except Exception:
            failed += 1
            continue
        if found is None:
            continue
        found = replace(found, matched=True)     # online hambuna = hari film / series ekak
        if found.poster:
            if best is not None:                 # TVmaze: episode nama thiyenawa, poster nae
                found = replace(best, poster=found.poster)
            return found, None
        best = found

    wait = RETRY_AFTER_ERROR if failed else RETRY_AFTER_NO_MATCH
    return (best or media), time.time() + wait      # best nathnam matched=False (gamanma video ekak)


_cache = {}


def resolve(raw):
    """File nama eken Media object ekak return karanawa (poster ekka). Nothing raise karanne nae."""
    parsed = parse_filename(raw)
    key = (parsed.title.lower(), parsed.year, parsed.season, parsed.episode)
    hit = _cache.get(key)
    if hit and (hit[1] is None or time.time() < hit[1]):
        return hit[0]
    try:
        media, retry_at = _lookup(parsed)
    except Exception:
        media, retry_at = parsed, time.time() + RETRY_AFTER_ERROR
    _cache[key] = (media, retry_at)
    return media
