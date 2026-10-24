#!/usr/bin/env python3
"""Draw line versions of the third-party app logos that Simple Icons does not have
(darktable, RawTherapee, btop, foot, GNOME Papers); import_simple_icons.py brings in the
rest as solid icons. Each is a simplified, single-colour redraw of the app's own logo,
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
