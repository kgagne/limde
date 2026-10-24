"""Shared drawing helpers for elachisto's icon generators (see README.md for the style)."""
import math
from pathlib import Path

SRC = Path(__file__).resolve().parent / 'src'
HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">\n')


def n(v):
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def f(*values):
    return ' '.join(n(v) for v in values)


def write(name, *elements):
    (SRC / f"{name}.svg").write_text(HEAD + '\n'.join(elements) + '\n</svg>\n')


def path(d):
    return f'<path d="{d}"/>'


def dot(x, y, r=1.1):
    return f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r)}" fill="currentColor" stroke="none"/>'


def circle(x, y, r):
    return f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r)}"/>'


def rect(x, y, w, h, rx=2.25, filled=False):
    extra = ' fill="currentColor" stroke="none"' if filled else ''
    return f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(rx)}"{extra}/>'


def polar(cx, cy, r, degrees):
    a = math.radians(degrees)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def gear(cx, cy, ro, ri, hole, teeth=8, half=0.16, root=0.29):
    """Gear outline with evenly spaced flat-topped teeth, plus its centre hole."""
    pts = []
    for i in range(teeth):
        a = 2 * math.pi * i / teeth - math.pi / 2
        for da, r in ((-root, ri), (-half, ro), (half, ro), (root, ri)):
            pts.append((cx + r * math.cos(a + da), cy + r * math.sin(a + da)))
    return path('M' + ' L'.join(f(x, y) for x, y in pts) + 'Z'), circle(cx, cy, hole)


def arc_arrow(cx, cy, r, start, end, head=4.75):
    """Arc from angle `start` to `end` (degrees, screen orientation), arrowhead at the end."""
    sweep = 1 if end > start else 0
    large = 1 if abs(end - start) > 180 else 0
    x0, y0 = polar(cx, cy, r, start)
    x1, y1 = polar(cx, cy, r, end)
    # Direction of travel at the end point.
    a = math.radians(end)
    tx, ty = (-math.sin(a), math.cos(a)) if sweep else (math.sin(a), -math.cos(a))
    heads = []
    for turn in (140, -140):
        t = math.radians(turn)
        hx = tx * math.cos(t) - ty * math.sin(t)
        hy = tx * math.sin(t) + ty * math.cos(t)
        heads.append((x1 + head * hx, y1 + head * hy))
    return (path(f'M{f(x0, y0)}A{f(r, r)} 0 {large} {sweep} {f(x1, y1)}'),
            path(f'M{f(*heads[0])}L{f(x1, y1)}L{f(*heads[1])}'))


def straight_arrow(name, angle):
    """Arrow pointing at `angle` degrees (0 = right, 90 = down), centred."""
    tip = polar(12, 12, 8, angle)
    tail = polar(12, 12, 8, angle + 180)
    wings = [polar(*tip, 6.5, angle + 180 + s) for s in (45, -45)]
    write(name, path(f'M{f(*tail)}L{f(*tip)}'),
          path(f'M{f(*wings[0])}L{f(*tip)}L{f(*wings[1])}'))



# Shared outlines, so variants stay identical to their base icon.
FILE = [path('M14.5 2H6a1.75 1.75 0 0 0-1.75 1.75v16.5A1.75 1.75 0 0 0 6 22h12'
             'a1.75 1.75 0 0 0 1.75-1.75V7.25z'),
        path('M14.5 2v4.25a1 1 0 0 0 1 1h4.25')]
FOLDER = path('M1.75 6A1.75 1.75 0 0 1 3.5 4.25h5.25l2.25 2.25h9.5a1.75 1.75 0 0 1 1.75 1.75v10'
              'a1.75 1.75 0 0 1-1.75 1.75h-17a1.75 1.75 0 0 1-1.75-1.75z')
SLASH = path('M3.25 3.25l17.5 17.5')


def polygon(cx, cy, r, sides, rotate=0):
    pts = [polar(cx, cy, r, rotate + 360 * i / sides) for i in range(sides)]
    return path('M' + ' L'.join(f(x, y) for x, y in pts) + 'Z')


def star_points(cx, cy, ro, ri):
    return [polar(cx, cy, ro if i % 2 == 0 else ri, -90 + 36 * i) for i in range(10)]


def star(cx, cy, ro, ri, fill=None):
    pts = star_points(cx, cy, ro, ri)
    extra = f' fill="{fill}"' if fill else ''
    return f'<path d="M{" L".join(f(x, y) for x, y in pts)}Z"{extra}/>'


def star_left_half(cx, cy, ro, ri):
    """Filled left half: the bottom inner point, the left points, back to the top point."""
    pts = star_points(cx, cy, ro, ri)
    half = pts[5:] + [pts[0]]
    return f'<path d="M{" L".join(f(x, y) for x, y in half)}Z" fill="currentColor" stroke="none"/>'
