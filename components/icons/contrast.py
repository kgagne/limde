"""Colour contrast helpers (standard library only), shared by the icon theme and the
appearance checks.

Contrast is WCAG 2.2's ratio: text needs 4.5:1 (1.4.3) and icons and other graphics
3:1 (1.4.11). fit() moves a colour's OKLCH lightness, keeping its hue, only as far as it
must go to reach a ratio against every given background.
"""
import math
import re

TEXT = 4.5
GRAPHICS = 3.0
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def rgb(colour):
    return [int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def to_hex(channels):
    return '#' + ''.join(f'{round(min(1, max(0, c)) * 255):02x}' for c in channels)


def luminance(colour):
    r, g, b = map(_lin, rgb(colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    x, y = sorted((luminance(a), luminance(b)))
    return (y + 0.05) / (x + 0.05)


def brightness(colour, factor):
    """What GTK's -gtk-icon-filter: brightness(factor) makes of a colour."""
    return to_hex([c * factor for c in rgb(colour)])


def _oklch(colour):
    r, g, b = map(_lin, rgb(colour))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    lightness = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    b2 = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return lightness, math.hypot(a, b2), math.atan2(b2, a)


def _from_oklch(lightness, chroma, hue):
    for _ in range(60):  # shrink chroma until the colour is inside sRGB
        a, b = chroma * math.cos(hue), chroma * math.sin(hue)
        l = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
        m = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
        s = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
        rgb_lin = (4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                   -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                   -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)
        if all(-1e-4 <= c <= 1 + 1e-4 for c in rgb_lin):
            return to_hex([_gamma(max(0, c)) for c in rgb_lin])
        chroma *= 0.9
    return to_hex([_gamma(max(0, min(1, lightness ** 3)))] * 3)


def fit(colour, backgrounds, minimum=GRAPHICS, also=lambda c: True):
    """The colour itself if it reaches `minimum` on every background (and passes `also`),
    else the same hue at the nearest OKLCH lightness that does; None if none does."""
    def ok(c):
        return all(ratio(c, bg) >= minimum for bg in backgrounds) and also(c)
    if ok(colour):
        return colour.lower()
    start, chroma, hue = _oklch(colour)
    best = None
    for step in range(1001):
        lightness = step / 1000
        candidate = _from_oklch(lightness, chroma, hue)
        if ok(candidate):
            if best is None or abs(lightness - start) < abs(best[0] - start):
                best = (lightness, candidate)
    return best[1] if best else None
