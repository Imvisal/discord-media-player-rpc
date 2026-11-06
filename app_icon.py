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


SUPPORT_COLORS = (                       # (background, text): blue, orange, dark
    ((114, 164, 242), (27, 27, 27)),
    ((255, 100, 51), (255, 255, 255)),
    ((32, 32, 32), (255, 255, 255)),
)
SUPPORT_TEXT = "Support me on Ko-fi"


def _font(size):
    from PIL import ImageFont
    for name in ("segoeuib.ttf", "seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _pill_button(text, bg, fg, icon_func, height):
    """Rounded button: dark tile with an icon on the left, one line of text. The width follows the text."""
    from PIL import ImageDraw
    k = 4                                              # draw 4x bigger, then shrink: smooth edges
    H = height * k
    font = _font(int(H * 0.38))
    tile = int(H * 0.72)                               # dark rounded tile holding the icon
    tx, ty = int(H * 0.2), (H - tile) // 2
    text_x = tx + tile + int(H * 0.2)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    box = probe.textbbox((0, 0), text, font=font)
    W = text_x + (box[2] - box[0]) + int(H * 0.32)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(H * 0.28), fill=bg + (255,))
    d.rounded_rectangle((tx, ty, tx + tile, ty + tile), radius=int(tile * 0.3), fill=(32, 32, 32, 255))
    icon = icon_func(int(tile * 0.86))
    img.alpha_composite(icon, (tx + (tile - icon.width) // 2, ty + (tile - icon.height) // 2))
    d.text((text_x - box[0], (H - (box[3] - box[1])) // 2 - box[1]), text, font=font,
           fill=fg + (255,))
    return img.resize((W // k, H // k), Image.LANCZOS)


def make_support_button(index=0, height=46):
    """The Ko-fi style 'Support me on Ko-fi' button: rounded, cup icon on the left, one line of text.
    index 0/1/2 = blue / orange / dark. The width follows the text."""
    bg, fg = SUPPORT_COLORS[index % len(SUPPORT_COLORS)]
    return _pill_button(SUPPORT_TEXT, bg, fg, make_support_icon, height)


# Discord logo (Simple Icons, CC0), 24x24 viewBox. Drawn with the tiny SVG path reader below,
# so no image file or extra library is needed.
DISCORD_PATH = (
    "M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 "
    "1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 "
    "19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 "
    "0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 "
    "1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-"
    ".0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01."
    "0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 "
    "00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-"
    "3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 "
    "15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 "
    "2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332."
    "9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"
)


def _svg_polygons(d, steps=12):
    """Very small SVG path reader (M L H V C S A Z, absolute + relative) -> list of point lists."""
    import math
    import re
    num = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
    pos, n = 0, len(d)

    def skip():
        nonlocal pos
        while pos < n and d[pos] in " ,\t\r\n":
            pos += 1

    def number():
        nonlocal pos
        skip()
        m = num.match(d, pos)
        pos = m.end()
        return float(m.group())

    def flag():
        nonlocal pos
        skip()
        pos += 1
        return d[pos - 1] == "1"

    def more():
        skip()
        return pos < n and not d[pos].isalpha()

    polys, pts = [], []
    x = y = sx = sy = 0.0
    cmd, last_c = None, None                       # last_c: previous cubic's 2nd control point
    while True:
        skip()
        if pos >= n:
            break
        if d[pos].isalpha():
            cmd = d[pos]
            pos += 1
        rel = cmd.islower()
        c = cmd.upper()
        if c == "Z":
            if pts:
                polys.append(pts)
            pts, x, y, last_c = [], sx, sy, None
            continue
        if c == "M":
            nx, ny = number(), number()
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            if pts:
                polys.append(pts)
            pts, sx, sy, last_c = [(x, y)], x, y, None
            cmd = "l" if rel else "L"              # extra pairs after M are lines
            continue
        if not pts:
            pts = [(x, y)]
        if c == "L":
            nx, ny = number(), number()
            x, y = (x + nx, y + ny) if rel else (nx, ny)
            pts.append((x, y)); last_c = None
        elif c == "H":
            nx = number(); x = x + nx if rel else nx; pts.append((x, y)); last_c = None
        elif c == "V":
            ny = number(); y = y + ny if rel else ny; pts.append((x, y)); last_c = None
        elif c in "CS":
            if c == "C":
                x1, y1 = number(), number()
                if rel:
                    x1, y1 = x + x1, y + y1
            else:
                x1, y1 = (2 * x - last_c[0], 2 * y - last_c[1]) if last_c else (x, y)
            x2, y2, ex, ey = number(), number(), number(), number()
            if rel:
                x2, y2, ex, ey = x + x2, y + y2, x + ex, y + ey
            for i in range(1, steps + 1):
                t = i / steps; u = 1 - t
                pts.append((u**3 * x + 3 * u * u * t * x1 + 3 * u * t * t * x2 + t**3 * ex,
                            u**3 * y + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t**3 * ey))
            last_c, x, y = (x2, y2), ex, ey
        elif c == "A":
            rx, ry, rot = abs(number()), abs(number()), number()
            large, sweep = flag(), flag()
            ex, ey = number(), number()
            if rel:
                ex, ey = x + ex, y + ey
            last_c = None
            if rx == 0 or ry == 0 or (ex, ey) == (x, y):
                pts.append((ex, ey)); x, y = ex, ey
                continue
            phi = math.radians(rot); cp, sp = math.cos(phi), math.sin(phi)
            dx, dy = (x - ex) / 2, (y - ey) / 2
            x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
            lam = x1p**2 / rx**2 + y1p**2 / ry**2
            if lam > 1:
                rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
            num_ = rx**2 * ry**2 - rx**2 * y1p**2 - ry**2 * x1p**2
            den = rx**2 * y1p**2 + ry**2 * x1p**2
            co = math.sqrt(max(0.0, num_ / den)) * (-1 if large == sweep else 1)
            cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
            cx, cy = cp * cxp - sp * cyp + (x + ex) / 2, sp * cxp + cp * cyp + (y + ey) / 2
            th1 = math.atan2((y1p - cyp) / ry, (x1p - cxp) / rx)
            th2 = math.atan2((-y1p - cyp) / ry, (-x1p - cxp) / rx)
            dth = th2 - th1
            if sweep and dth < 0:
                dth += 2 * math.pi
            elif not sweep and dth > 0:
                dth -= 2 * math.pi
            for i in range(1, steps + 1):
                th = th1 + dth * i / steps
                px, py = rx * math.cos(th), ry * math.sin(th)
                pts.append((cp * px - sp * py + cx, sp * px + cp * py + cy))
            x, y = ex, ey
        else:
            raise ValueError("unsupported path command " + cmd)
    if pts:
        polys.append(pts)
    return polys


def make_discord_icon(size=40, color=(255, 255, 255, 255)):
    """The Discord logo (white), for the 'Join our Discord server' button."""
    from PIL import ImageChops, ImageDraw
    big = size * 8
    scale = big / 24.0
    mask = Image.new("1", (big, big), 0)
    for poly in _svg_polygons(DISCORD_PATH):         # even-odd: the eyes are holes
        layer = Image.new("1", (big, big), 0)
        ImageDraw.Draw(layer).polygon([(px * scale, py * scale) for px, py in poly], fill=1)
        mask = ImageChops.logical_xor(mask, layer)
    alpha = mask.convert("L").resize((size, size), Image.LANCZOS)
    img = Image.new("RGBA", (size, size), color[:3] + (0,))
    img.putalpha(alpha)
    return img


DISCORD_COLORS = (                       # (background, text): blurple, darker blurple (mouse over)
    ((88, 101, 242), (255, 255, 255)),
    ((71, 82, 196), (255, 255, 255)),
)
DISCORD_TEXT = "Join our Discord server"


def make_discord_button(index=0, height=46):
    """'Join our Discord server' button, same look as the Ko-fi one. index 0 = normal, 1 = mouse over."""
    bg, fg = DISCORD_COLORS[index % len(DISCORD_COLORS)]
    return _pill_button(DISCORD_TEXT, bg, fg, make_discord_icon, height)


if __name__ == "__main__":
    make_icon_image(256).save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
