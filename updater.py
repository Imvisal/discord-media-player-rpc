"""
Online updates: GitHub Releases walin aluth version ekak thiyenawada balala, download karala,
running exe eka replace karanawa.

- Check    : GitHub API (releases/latest). Key one nae, personal data yawanne nae.
- Download : Release eke MediaRPC.exe saha MediaRPC.exe.sha256. Checksum eka match unoth witharai install karanne.
- Install  : running exe eka rename karala (Windows walata puluwan), aluth eka thanata damma restart karanawa.

Source walin run karaddi / app folder eka write karanna ba nam, install wenuwata release page eka open wenawa.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional

import app_version

REPO = "Imvisal/discord-media-player-rpc"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases"
ASSET_EXE = "MediaRPC.exe"
ASSET_SHA = "MediaRPC.exe.sha256"

NEW_NAME = "MediaRPC.update.exe"      # download karana thana (exe eka thiyena folder eke)
OLD_SUFFIX = ".old"                   # replace karapu paraana exe eka

USER_AGENT = f"MediaRPC/{app_version.__version__} (+https://github.com/{REPO})"
TIMEOUT = 10
MIN_BYTES = 1_000_000                 # sachchara exe ekak meka ekata wada loku
MAX_BYTES = 300_000_000


@dataclass
class UpdateInfo:
    version: str          # "1.6.0"
    tag: str              # "v1.6.0"
    exe_url: str
    sha_url: str
    page_url: str         # release page eka (manual download walata)


# ---------------------------------------------------------------- versions

def parse_version(text):
    """"v1.6.0" / "1.6" -> (1, 6, 0) wage tuple ekak. Wada nathnam None."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+){0,3})", str(text or ""))
    if not m:
        return None
    return tuple(int(p) for p in m.group(1).split("."))


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


# ---------------------------------------------------------------- safe network

def _check_url(url, asset=False):
    """HTTPS saha GitHub hosts witharai allow karanne. Wena thanakata redirect wunoth nawathinawa."""
    p = urllib.parse.urlparse(url)
    host = (p.hostname or "").lower()
    if p.scheme != "https":
        raise ValueError("insecure URL")
    if not (host in ("api.github.com", "github.com") or host.endswith(".githubusercontent.com")):
        raise ValueError("unexpected host")
    if asset and not (host == "github.com"
                      and p.path.lower().startswith(f"/{REPO.lower()}/releases/download/")):
        raise ValueError("unexpected asset URL")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_SafeRedirect)


def _open(url, accept="application/octet-stream", asset=False):
    _check_url(url, asset=asset)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    return _OPENER.open(req, timeout=TIMEOUT)


def _get_json(url):
    with _open(url, accept="application/vnd.github+json") as resp:
        return json.load(resp)


# ---------------------------------------------------------------- check

def is_dev_build(version=None):
    """Source walin run karaddi / tag nathi build ekak ("0.0.0-dev") update check karanne nae."""
    return "dev" in str(version or app_version.__version__).lower()


def check_for_update(current=None):
    """Aluth version ekak thiyenawanam UpdateInfo, nathnam None. Network error unoth raise karanawa."""
    current = current or app_version.__version__
    if is_dev_build(current):
        return None
    data = _get_json(API_URL)
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name") or ""
    if not is_newer(tag, current):
        return None
    assets = {a.get("name"): a.get("browser_download_url") for a in data.get("assets") or []}
    exe_url, sha_url = assets.get(ASSET_EXE), assets.get(ASSET_SHA)
    if not exe_url or not sha_url:
        return None       # Release eka publish una, namuth exe eka build wenawa thama. Passe aye balanawa.
    return UpdateInfo(
        version=".".join(str(n) for n in parse_version(tag)),
        tag=tag,
        exe_url=exe_url,
        sha_url=sha_url,
        page_url=data.get("html_url") or RELEASES_URL,
    )


# ---------------------------------------------------------------- download + install

def can_self_update():
    """Exe eka replace karanna puluwanda (frozen exe + folder eka write karanna puluwan)."""
    if not getattr(sys, "frozen", False) or sys.platform != "win32":
        return False
    try:
        fd, probe = tempfile.mkstemp(dir=os.path.dirname(sys.executable), prefix=".mrpc-")
        os.close(fd)
        os.remove(probe)
        return True
    except OSError:
        return False


def _read_expected_sha(url):
    with _open(url, asset=True) as resp:
        text = resp.read(4096).decode("utf-8", "ignore")
    m = re.search(r"\b[0-9a-fA-F]{64}\b", text)
    if not m:
        raise ValueError("bad checksum file")
    return m.group(0).lower()


def download(info, progress=None, exe_path=None):
    """Aluth exe eka download karala checksum eka balanawa. Download una file eke path eka return karanawa."""
    exe = exe_path or sys.executable
    expected = _read_expected_sha(info.sha_url)
    target = os.path.join(os.path.dirname(exe), NEW_NAME)
    digest = hashlib.sha256()
    got = 0
    try:
        with _open(info.exe_url, asset=True) as resp, open(target, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                got += len(chunk)
                if got > MAX_BYTES:
                    raise ValueError("file too large")
                out.write(chunk)
                digest.update(chunk)
                if progress and total:
                    progress(min(100, got * 100 // total))
        if total and got != total:
            raise ValueError("incomplete download")
        if got < MIN_BYTES:
            raise ValueError("file too small")
        if digest.hexdigest() != expected:
            raise ValueError("checksum mismatch")
        with open(target, "rb") as f:
            if f.read(2) != b"MZ":
                raise ValueError("not a Windows exe")
    except BaseException:
        try:
            os.remove(target)
        except OSError:
            pass
        raise
    return target


def apply_update(new_path, exe_path=None, minimized=False, spawn=True):
    """
    Running exe eka rename karala (Windows walata puluwan), aluth eka thanata damma, aluth eka start karanawa.
    Aluth process eka "--wait-for-previous" ekka start wenawa: paraana process eka iwara wenakan balan inna.
    """
    exe = exe_path or sys.executable
    old = exe + OLD_SUFFIX
    try:
        os.remove(old)
    except FileNotFoundError:
        pass
    os.replace(exe, old)
    try:
        os.replace(new_path, exe)
    except OSError:
        os.replace(old, exe)        # rollback: paraana eka aye thanata
        raise
    if not spawn:
        return
    args = [exe, "--wait-for-previous"] + (["--minimized"] if minimized else [])
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"      # onefile exe eka ayeth start karanakota parana temp folder eka use nokarana
    flags = 0
    if sys.platform == "win32":
        flags = 0x00000008 | 0x00000200             # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, env=env, close_fds=True, cwd=os.path.dirname(exe), creationflags=flags)


def cleanup_old_files():
    """Kalin update ekakin ithuru una files ain karanawa."""
    if not getattr(sys, "frozen", False):
        return
    exe = sys.executable
    for path in (exe + OLD_SUFFIX, os.path.join(os.path.dirname(exe), NEW_NAME)):
        try:
            os.remove(path)
        except OSError:
            pass
