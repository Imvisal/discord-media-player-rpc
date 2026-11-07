"""
Anonymous usage count, so the author can see how many installs are in use.

Sent: a random install id (made once, not linked to your PC, name or account), the app version.
Never sent: film titles, file names, what you watch, your IP address is not stored.
Can be switched off in Settings > Status ("Send an anonymous usage count"). Everything is best-effort:
any failure is ignored.
"""

import json
import re
import urllib.request
import uuid

import app_version
import system_integration as sysint

PING_URL = "https://discord-media-player-rpc-site.vercel.app/api/ping"
PING_EVERY_MS = 30 * 60 * 1000           # the admin page counts "using it now" as seen in the last 45 min
TIMEOUT = 8


def install_id():
    """Random id made on first use and kept in settings.json. Not derived from any hardware."""
    value = str(sysint.get_setting("install_id", "") or "")
    if not re.fullmatch(r"[0-9a-f]{32}", value):
        value = uuid.uuid4().hex
        sysint.set_setting("install_id", value)
    return value


def ping():
    """One request. Returns True if the server accepted it."""
    version = str(getattr(app_version, "__version__", "") or "")
    if not re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}", version):
        return False                      # a dev build, not a release: don't count it
    body = json.dumps({"id": install_id(), "v": version}).encode("utf-8")
    request = urllib.request.Request(
        PING_URL, data=body, method="POST",
        headers={"Content-Type": "application/json", "User-Agent": f"MediaRPC/{version}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status == 200
    except Exception:
        return False
