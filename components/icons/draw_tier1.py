#!/usr/bin/env python3
"""Draw tier 1 of elachisto's icons (the panel set) into src/.

The SVG files in src/ are the source of truth; this script records how they were drawn,
so families (battery levels, Wi-Fi strength, volume, brightness, file and folder types)
stay identical apart from what distinguishes them. Re-running it overwrites tier 1 files.
Style rules: README.md.
"""
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
    (SRC / f'{name}.svg').write_text(HEAD + '\n'.join(elements) + '\n</svg>\n')


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


# --- arrows -------------------------------------------------------------------------
straight_arrow('arrow-right', 0)
straight_arrow('arrow-down', 90)
straight_arrow('arrow-left', 180)
straight_arrow('arrow-up', 270)
write('arrow-rotate-right', *arc_arrow(12, 12.5, 8, 150, 375))   # redo
write('arrow-rotate-left', *arc_arrow(12, 12.5, 8, 30, -195))    # undo
write('rotate-right', *arc_arrow(12, 12, 8.5, -60, 240))         # refresh

# --- battery family -----------------------------------------------------------------
BATTERY = [rect(1.75, 6.25, 18, 11.5), path('M22.25 10v4')]
for name, fraction in (('battery-empty', 0), ('battery-quarter', .25), ('battery-half', .5),
                       ('battery-three-quarters', .75), ('battery-full', 1)):
    level = [rect(4.25, 8.75, 13 * fraction, 6.5, 1, filled=True)] if fraction else []
    write(name, *BATTERY, *level)
write('battery-bolt', *BATTERY, path('M12 8.5L8.75 12.25H12.75L9.5 16'))
write('battery-exclamation', *BATTERY, path('M10.75 8.75v3.75'), dot(10.75, 15))

# --- Wi-Fi family -------------------------------------------------------------------
def wifi_arcs(count):
    arcs = []
    for r in (4, 8, 12)[:count]:
        dx, dy = r * math.sin(math.radians(50)), r * math.cos(math.radians(50))
        arcs.append(path(f'M{f(12 - dx, 19.5 - dy)}A{f(r, r)} 0 0 1 {f(12 + dx, 19.5 - dy)}'))
    return arcs + [dot(12, 19.5)]

write('wifi', *wifi_arcs(3))
write('wifi-fair', *wifi_arcs(2))
write('wifi-weak', *wifi_arcs(1))
write('wifi-slash', *wifi_arcs(3), path('M3.5 3.5L20.5 20.5'))

# --- volume family ------------------------------------------------------------------
SPEAKER = path('M2.75 9h3.75l5-4.5v15l-5-4.5H2.75z')
WAVE_NEAR = path('M15.25 9a4.25 4.25 0 0 1 0 6')
WAVE_FAR = path('M18.25 6a8.5 8.5 0 0 1 0 12')
write('volume-high', SPEAKER, WAVE_NEAR, WAVE_FAR)
write('volume-low', SPEAKER, WAVE_NEAR)
write('volume-off', SPEAKER)
write('volume-xmark', SPEAKER, path('M15.5 9.5l5 5M20.5 9.5l-5 5'))

# --- brightness family (dim to bright) ----------------------------------------------
def sun(core_filled, ray_from, ray_to, dots=False):
    parts = [f'<circle cx="12" cy="12" r="3.75"{" fill=\"currentColor\"" if core_filled else ""}/>']
    for i in range(8):
        a = i * 45
        if dots:
            parts.append(dot(*polar(12, 12, ray_from, a), 1))
        else:
            parts.append(path(f'M{f(*polar(12, 12, ray_from, a))}L{f(*polar(12, 12, ray_to, a))}'))
    return parts

write('brightness-low', *sun(False, 7.25, 0, dots=True))
write('brightness', *sun(False, 6.75, 8))
write('sun', *sun(False, 6.5, 9))
write('sun-bright', *sun(True, 6.5, 10))

# --- files --------------------------------------------------------------------------
FILE = [path('M14.5 2H6a1.75 1.75 0 0 0-1.75 1.75v16.5A1.75 1.75 0 0 0 6 22h12'
             'a1.75 1.75 0 0 0 1.75-1.75V7.25z'),
        path('M14.5 2v4.25a1 1 0 0 0 1 1h4.25')]
write('file', *FILE)
write('file-lines', *FILE, path('M8 12h8M8 15h8M8 18h5'))
write('file-code', *FILE, path('M10.25 12.5L7.75 15l2.5 2.5M13.75 12.5l2.5 2.5-2.5 2.5'))
write('file-image', *FILE, circle(9.75, 12, 1.25), path('M7.5 18.5l3-3.25 2 2 1.5-1.5 2.5 2.75'))
write('file-audio', *FILE, circle(10, 17.25, 1.75), path('M11.75 17.25V11.5l3.5 1'))
write('file-video', *FILE, path('M10 12v6.5l5-3.25z'))
write('file-pdf', *FILE, path('M7.25 18.25V13.5h1.5a1.25 1.25 0 0 1 0 2.5h-1.5'),
      path('M11.25 13.5v4.75h.5a2.375 2.375 0 0 0 0-4.75z'), path('M15.25 18.25V13.5h2M15.25 15.75h1.5'))
write('file-zipper', *FILE, path('M10.5 3.5h1.5M12 5.5h1.5M10.5 7.5h1.5M12 9.5h1.5'),
      rect(10.25, 11.5, 3.5, 4.5, 1))

# --- folders ------------------------------------------------------------------------
FOLDER = path('M1.75 6A1.75 1.75 0 0 1 3.5 4.25h5.25l2.25 2.25h9.5a1.75 1.75 0 0 1 1.75 1.75v10'
              'a1.75 1.75 0 0 1-1.75 1.75h-17a1.75 1.75 0 0 1-1.75-1.75z')
write('folder', FOLDER)
write('folder-plus', FOLDER, path('M12 10.5v6M9 13.5h6'))
write('folder-arrow-down', FOLDER, path('M12 10v6.25M9.25 13.5L12 16.25l2.75-2.75'))
write('folder-image', FOLDER, circle(15, 11.25, 1.1), path('M5.5 17.25l3.5-4 2.5 2.75 1.75-1.75 3.75 3'))
write('folder-music', FOLDER, circle(10.25, 16, 1.6), path('M11.85 16v-5.5l3.15.85'))
write('folder-open',
      path('M3.5 19.75A1.75 1.75 0 0 1 1.75 18V6A1.75 1.75 0 0 1 3.5 4.25h5.25l2.25 2.25h7.5'
           'a1.75 1.75 0 0 1 1.75 1.75V10'),
      path('M3.5 19.75l2.7-8.1a1.5 1.5 0 0 1 1.42-1.02h13.24a1 1 0 0 1 .95 1.32l-2.45 6.78'
           'a1.5 1.5 0 0 1-1.41 1.02z'))

# --- objects and actions ------------------------------------------------------------
write('bell', path('M5.25 16.75V11a6.75 6.75 0 0 1 13.5 0v5.75l2 2H3.25z'),
      path('M9.75 21a2.25 2.25 0 0 0 4.5 0'), path('M12 2.25v2'))
write('lock', rect(4, 10, 16, 11.75), path('M7.5 10V7a4.5 4.5 0 0 1 9 0v3'), path('M12 14.5v2.75'))
write('terminal', rect(1.75, 3.75, 20.5, 16.5), path('M6 9l3.5 3-3.5 3'), path('M12.5 15.5h5.5'))
_r, _c = 9, (12, 12.75)
_d = _r * math.sqrt(.5)
write('power-off', path('M12 2.25v8.5'),
      path(f'M{f(_c[0] - _d, _c[1] - _d)}A{_r} {_r} 0 1 0 {f(_c[0] + _d, _c[1] - _d)}'))
write('gear', *gear(12, 12, 10.25, 7.75, 3.25))
write('gears', *gear(8.75, 8.75, 6.75, 5, 2), *gear(17.25, 17.25, 5, 3.6, 1.5, teeth=6, half=.22, root=.4))
write('box-archive', rect(1.75, 3.5, 20.5, 4.75, 1.25),
      path('M3.75 8.25v10.25A1.75 1.75 0 0 0 5.5 20.25h13a1.75 1.75 0 0 0 1.75-1.75V8.25'),
      path('M9.75 12h4.5'))
write('chart-simple', rect(3, 12, 4.5, 8.75, 1.25), rect(9.75, 3.25, 4.5, 17.5, 1.25),
      rect(16.5, 8.25, 4.5, 12.5, 1.25))
write('circle-info', circle(12, 12, 9.75), path('M12 11v5.5'), dot(12, 7.75))
write('computer-mouse', rect(5.75, 2.25, 12.5, 19.5, 6.25), path('M12 6.25v3.5'))
write('copy', rect(8.25, 8.25, 13.5, 13.5),
      path('M15.75 8.25V4A1.75 1.75 0 0 0 14 2.25H4A1.75 1.75 0 0 0 2.25 4v10A1.75 1.75 0 0 0 4 15.75h4.25'))
write('paste', path('M8.5 3.75H6.25a2 2 0 0 0-2 2V19.75a2 2 0 0 0 2 2h11.5a2 2 0 0 0 2-2V5.75'
                    'a2 2 0 0 0-2-2H15.5'),
      rect(8.5, 2.25, 7, 3.5, 1))
write('desktop', rect(1.75, 3.25, 20.5, 13.5), path('M12 16.75v4M8.5 20.75h7'))
write('eject', path('M12 3.75l7.75 8.5H4.25z'), path('M4.25 18.5h15.5'))
write('eye', path('M1.75 12C4 7.5 7.75 5.25 12 5.25s8 2.25 10.25 6.75C20 16.5 16.25 18.75 12 18.75'
                  'S4 16.5 1.75 12z'), circle(12, 12, 3.25))
write('film', rect(2.25, 2.75, 19.5, 18.5), path('M7 2.75v18.5M17 2.75v18.5'),
      path('M2.25 7.5H7M2.25 12H7M2.25 16.5H7M17 7.5h4.75M17 12h4.75M17 16.5h4.75'))
write('floppy-disk',
      path('M2.75 4.5A1.75 1.75 0 0 1 4.5 2.75h11.75l5 5V19.5a1.75 1.75 0 0 1-1.75 1.75h-15'
           'a1.75 1.75 0 0 1-1.75-1.75z'),
      path('M7 2.75v4a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-4'), circle(12, 15, 2.75))
write('hard-drive', rect(1.75, 4.5, 20.5, 15), path('M1.75 13h20.5'), dot(17.75, 16.25),
      path('M5.75 16.25h5.5'))
write('house', path('M2.25 11L12 2.75 21.75 11'),
      path('M5 9v10.5a1.5 1.5 0 0 0 1.5 1.5h11a1.5 1.5 0 0 0 1.5-1.5V9'),
      path('M9.75 21v-5.25a1 1 0 0 1 1-1h2.5a1 1 0 0 1 1 1V21'))
write('keyboard', rect(1.75, 5.25, 20.5, 13.5),
      path('M5.75 9.25h.5M9.25 9.25h.5M12.75 9.25h.5M16.25 9.25h.5'
           'M7.5 12.25h.5M11 12.25h.5M14.5 12.25h.5M18 12.25h.5'),
      path('M7.5 15.25h9'))
write('list', dot(4.25, 6), dot(4.25, 12), dot(4.25, 18), path('M8.5 6h12M8.5 12h12M8.5 18h12'))
LENS = [circle(10.25, 10.25, 7.5), path('M15.75 15.75l6 6')]
write('magnifying-glass', *LENS)
write('magnifying-glass-plus', *LENS, path('M7.25 10.25h6M10.25 7.25v6'))
write('magnifying-glass-minus', *LENS, path('M7.25 10.25h6'))
write('memory', rect(1.75, 6.25, 20.5, 10, 1.75),
      path('M5.5 16.25v2.75M9.5 16.25v2.75M14.5 16.25v2.75M18.5 16.25v2.75'),
      rect(5, 9, 3.5, 4.5, .75), rect(10.25, 9, 3.5, 4.5, .75), rect(15.5, 9, 3.5, 4.5, .75))
write('microchip', rect(5.75, 5.75, 12.5, 12.5), rect(9.25, 9.25, 5.5, 5.5, 1),
      path('M9.5 2.25v3.5M14.5 2.25v3.5M9.5 18.25v3.5M14.5 18.25v3.5'
           'M2.25 9.5h3.5M2.25 14.5h3.5M18.25 9.5h3.5M18.25 14.5h3.5'))
write('minus', path('M4.25 12h15.5'))
write('plus', path('M12 4.25v15.5M4.25 12h15.5'))
write('xmark', path('M5.5 5.5l13 13M18.5 5.5l-13 13'))
write('network-wired', rect(9, 2.25, 6, 5, 1.25), rect(2.25, 16.75, 6, 5, 1.25),
      rect(15.75, 16.75, 6, 5, 1.25), path('M12 7.25V12M5.25 16.75V12h13.5v4.75'))
write('scissors', circle(6, 6.25, 3), circle(6, 17.75, 3),
      path('M8.5 8L21 18.5M8.5 16L21 5.5'))
write('sliders', path('M2.75 6h3M10.25 6h11M2.75 12h9.5M16.75 12h4.5M2.75 18h4.5M11.75 18h9.5'),
      circle(8, 6, 2.25), circle(14.5, 12, 2.25), circle(9.5, 18, 2.25))
write('table-cells', rect(2.25, 3.25, 19.5, 17.5), path('M2.25 9h19.5M2.25 15h19.5M8.75 3.25v17.5M15.25 3.25v17.5'))
write('trash-can', path('M3.25 6h17.5'), path('M9 6V3.75A1 1 0 0 1 10 2.75h4a1 1 0 0 1 1 1V6'),
      path('M5.25 6l1 14.1a1.75 1.75 0 0 0 1.75 1.65h8a1.75 1.75 0 0 0 1.75-1.65l1-14.1'),
      path('M10 10.5v6.5M14 10.5v6.5'))
write('usb-drive', rect(6.25, 8.5, 11.5, 13.25), path('M8.25 8.5V2.5h7.5v6'),
      rect(10, 4.5, 1.25, 1.75, .25, filled=True), rect(12.75, 4.5, 1.25, 1.75, .25, filled=True))

if __name__ == '__main__':
    print(f'{len(list(SRC.glob("*.svg")))} icons in {SRC}')
