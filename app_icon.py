"""
App icon: the Media RPC logo, embedded in icon_data.py so the exe needs no extra files.
Used for the window, the tray icon and the exe icon (`python app_icon.py` writes icon.ico).
"""

import base64
import io

from PIL import Image

import icon_data


def make_icon_image(size=256, palette=None):
    """The logo as an RGBA image of size x size. (`palette` is kept for old callers and ignored.)"""
    image = Image.open(io.BytesIO(base64.b64decode(icon_data.PNG_BASE64))).convert("RGBA")
    if size != image.width:
        image = image.resize((size, size), Image.LANCZOS)
    return image


if __name__ == "__main__":
    make_icon_image(256).save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
