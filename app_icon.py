"""
App icon / logo eka code walinma hadanawa (image file ekak one nae).
Tray icon, window icon, exe icon dekata use wenawa.

Design: gradient rounded square (pata wenas karanna puluwan), "play" triangle saha ewa langin "broadcast" arcs
(film eka Discord ekata pennanawa kiyana idea eka).
Loku image ekak hadala kuduwata kuda karanawa (anti-aliasing), kuda size walatath lassanata penna.
"""

import math

from PIL import Image, ImageDraw

# Pata set (udin, yatin). DEFAULT wenas karala logo eke pata wenas karanna puluwan.
PALETTES = {
    "sunset": ((255, 138, 76), (226, 52, 98)),      # orange -> pink-red
    "emerald": ((52, 211, 153), (5, 122, 105)),     # green -> teal
    "violet": ((192, 132, 252), (112, 48, 190)),    # purple
    "midnight": ((72, 78, 96), (24, 26, 36)),       # dark charcoal
}
DEFAULT = "emerald"
WHITE = (255, 255, 255)


def _gradient(size, top, bottom):
    """Udin yatata blurple gradient ekak."""
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for y in range(size):
        t = y / max(1, size - 1)
        color = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(size):
            px[x, y] = color + (255,)
    return img


def _rounded_triangle(draw, pts, r, fill):
    """Kona gollu karapu triangle ekak."""
    cx = sum(p[0] for p in pts) / 3
    cy = sum(p[1] for p in pts) / 3
    inset = []
    for x, y in pts:                      # kona ethulata r gaman ganna
        dx, dy = cx - x, cy - y
        d = math.hypot(dx, dy)
        k = (r * 2) / d
        inset.append((x + dx * k, y + dy * k))
    draw.polygon(inset, fill=fill)
    for i in range(3):
        a, b = inset[i], inset[(i + 1) % 3]
        draw.line([a, b], fill=fill, width=int(r * 2))
        draw.ellipse((a[0] - r, a[1] - r, a[0] + r, a[1] + r), fill=fill)


def _arc(draw, center, radius, width, start, end, fill):
    """Rounded cap thiyena arc ekak."""
    cx, cy = center
    outer = radius + width / 2        # PIL arc width eka bbox eken ethulata draw wenawa
    box = (cx - outer, cy - outer, cx + outer, cy + outer)
    draw.arc(box, start, end, fill=fill, width=int(width))
    for ang in (start, end):
        x = cx + radius * math.cos(math.radians(ang))
        y = cy + radius * math.sin(math.radians(ang))
        r = width / 2
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)


def make_icon_image(size=256, palette=None):
    top, bottom = PALETTES.get(palette or DEFAULT, PALETTES[DEFAULT])
    big = 1024
    s = big

    # background: gradient + rounded square mask
    base = _gradient(big, top, bottom)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, big - 1, big - 1), radius=int(s * 0.225), fill=255)
    base.putalpha(mask)

    fg = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(fg)

    # play triangle (idirimata balana)
    tri = [(s * 0.215, s * 0.28), (s * 0.215, s * 0.72), (s * 0.545, s * 0.50)]
    _rounded_triangle(d, tri, r=s * 0.03, fill=WHITE + (255,))

    # broadcast arcs (triangle eken pita wenawa wage)
    c = (s * 0.365, s * 0.50)
    _arc(d, c, s * 0.325, s * 0.068, -40, 40, WHITE + (255,))
    _arc(d, c, s * 0.455, s * 0.068, -40, 40, WHITE + (150,))

    out = Image.alpha_composite(base, fg)
    return out.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    make_icon_image(256).save("icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
