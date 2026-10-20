"""
App icon eka code walinma hadanawa (image file ekak one nae).
Tray icon, window icon, exe icon dekata use wenawa.
"""

from PIL import Image, ImageDraw


def make_icon_image(size=256):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 5, fill=(88, 101, 242, 255))
    s = size
    draw.polygon(
        [(s * 0.38, s * 0.27), (s * 0.38, s * 0.73), (s * 0.75, s * 0.50)],
        fill=(255, 255, 255, 255),
    )
    return img


if __name__ == "__main__":
    make_icon_image(256).save("icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
