#!/usr/bin/env python3
"""Draw line versions of the third-party app logos that Simple Icons does not have
(darktable, RawTherapee, btop, foot, GNOME Papers), and Tinybar's two Tailscale state icons
from Simple Icons' geometry; import_simple_icons.py brings in the rest as solid icons. Each is a simplified, single-colour redraw of the app's own logo,
used only to identify that app. The logo owners' policies were checked on 2026-10-24 (see
brands/NOTICE.md); owners who forbid redraws (Mozilla, Microsoft's VS Code, Signal,
Valve, Anthropic, Canonical) are not drawn. Logos under CC BY-SA are adaptations and
live in brands/cc-by-sa/ under that licence, with credits in brands/cc-by-sa/CREDITS.md.
"""
import math
from pathlib import Path

from _draw import circle, dot, f, path, polar, rect, write  # noqa: F401

HERE = Path(__file__).resolve().parent
MIT = HERE / 'brands'
SA = HERE / 'brands' / 'cc-by-sa'
SA.mkdir(exist_ok=True)


def mit(name, *elements):
    write(name, *elements, folder=MIT)


def sa(name, *elements):
    write(name, *elements, folder=SA)


# --- CC BY-SA adaptations ------------------------------------------------------------
sa('foot',  # terminal window with a footprint and a cursor
   rect(1.75, 3.75, 20.5, 16.5),
   '<ellipse cx="7.25" cy="12.25" rx="1.6" ry="2.4" fill="currentColor" stroke="none"/>',
   dot(5.75, 8.5, .6), dot(7.1, 8, .6), dot(8.5, 8.25, .6), dot(9.5, 9, .55),
   path('M12.5 15.5h5.5'))
sa('papers',  # document with reading glasses
   path('M14.5 2H6a1.75 1.75 0 0 0-1.75 1.75v16.5A1.75 1.75 0 0 0 6 22h12a1.75 1.75 0 0 0 1.75-1.75V7.25z'),
   path('M14.5 2v4.25a1 1 0 0 0 1 1h4.25'), path('M7.75 9.5h5'),
   circle(8.75, 15.75, 2.25), circle(15.25, 15.75, 2.25), path('M11 15.75h2'))

# --- MIT (no licence on the logo artwork, or a licence that does not reach redraws) ---
mit('btop',  # a "b" built from blocks
    path('M6 2.75v18.5h8.75a4.5 4.5 0 0 0 0-9H6'), path('M6 8h5.5M6 17h8.75'))
_blades = []
for i in range(6):
    a = 60 * i
    x0, y0 = polar(12, 12, 9.75, a)
    x1, y1 = polar(12, 12, 3.25, a + 120)
    _blades.append(f'M{f(x0, y0)}Q{f(*polar(12, 12, 5.5, a + 40))} {f(x1, y1)}')
mit('darktable', circle(12, 12, 9.75), path(''.join(_blades)), dot(12, 12, 1))
_spokes = ''.join(f'M{f(*polar(12, 12, 4.75, a))}L{f(*polar(12, 12, 9.75, a))}' for a in range(0, 360, 30))
mit('rawtherapee', circle(12, 12, 9.75), circle(12, 12, 4.75), path(_spokes))

if __name__ == '__main__':
    print(f'{len(list(MIT.glob("*.svg")))} MIT brand icons, {len(list(SA.glob("*.svg")))} CC BY-SA')


# --- Tailscale (Tinybar's optional Tailscale button) ----------------------------------
# Simple Icons 16.35.0's "tailscale" geometry (CC0-1.0): nine dots of radius 3 on a 9-unit
# grid, placed inside limDE's margin like the imported logos. Simple Icons draws the
# grey dots as rings to stay one colour; Tailscale's brand toolkit (press kit, 2025) asks
# for them as grey by opacity, so they are filled at 35 % here. Off follows Tailscale's
# own tray (tailscale/tailscale client/systray/logo.go: "disconnected is all gray dots")
# with limDE's Wi-Fi slash on top. Both are drawn at 75 % of the margin box, centred, so
# the full-length slash reaches past the corner dots (Keith, 2026-10-29); on stays the
# same size so the logo does not jump when toggled. Tailscale is a trademark of
# Tailscale Inc.; see NOTICE.
TAILSCALE_SIZE = 0.75


def tailscale_dots(bright):
    scale, grid = 0.854167 * TAILSCALE_SIZE, (3, 12, 21)
    offset = 12 - 12 * scale
    dots = []
    for row, y in enumerate(grid):
        for col, x in enumerate(grid):
            faint = '' if (row, col) in bright else ' fill-opacity="0.35"'
            dots.append(f'<circle cx="{f(offset + x * scale)}" cy="{f(offset + y * scale)}" '
                        f'r="{f(3 * scale)}" fill="currentColor" stroke="none"{faint}/>')
    return dots

TAILSCALE_T = {(1, 0), (1, 1), (1, 2), (2, 1)}   # the bright "T" of the connected logo
mit('tailscale', '<!-- Tailscale: Simple Icons 16.35.0 ("tailscale") geometry, CC0-1.0 -->',
    *tailscale_dots(TAILSCALE_T))
mit('tailscale-slash', '<!-- Tailscale, off: Simple Icons 16.35.0 geometry, CC0-1.0; slash as wifi-slash -->',
    *tailscale_dots(set()), path('M3.5 3.5L20.5 20.5'))
