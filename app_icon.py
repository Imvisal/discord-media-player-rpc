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


def make_support_icon(size=40):
    """A coffee cup with a heart (drawn here, no image file): the 'support' button."""
    from PIL import ImageDraw
    big = 512
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cup, heart = (255, 255, 255, 255), (255, 94, 91, 255)
    # steam
    for x in (170, 250, 330):
        d.line([(x, 70), (x - 18, 105), (x + 18, 140), (x, 175)], fill=(255, 255, 255, 140), width=18, joint="curve")
    # handle, cup body, saucer
    d.ellipse((350, 215, 470, 335), outline=cup, width=34)
    d.rounded_rectangle((70, 200, 395, 390), radius=34, fill=cup)
    d.pieslice((70, 200, 395, 440), 0, 180, fill=cup)
    d.rounded_rectangle((60, 435, 420, 470), radius=17, fill=cup)
    # heart on the cup
    cx, cy, r = 232, 290, 38
    d.ellipse((cx - 2 * r + 4, cy - r - 2, cx + 4, cy + r - 2), fill=heart)
    d.ellipse((cx - 4, cy - r - 2, cx + 2 * r - 4, cy + r - 2), fill=heart)
    d.polygon([(cx - 2 * r + 8, cy + 14), (cx + 2 * r - 8, cy + 14), (cx, cy + 2 * r + 4)], fill=heart)
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    make_icon_image(256).save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
