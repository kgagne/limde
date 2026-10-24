#!/usr/bin/env python3
"""Draw the Craft app brand icons into brands/ (except PhotoCraft and VectorCraft; see below).

CADCraft (set square) is a line version of Keith's own tile (2026-10-23). The other Craft apps get original glyphs for what each app
does; none of storytold's artwork is traced. Style rules: README.md.
"""
import math
from pathlib import Path

from _draw import circle, dot, f, path, polar, rect, write

BRANDS = Path(__file__).resolve().parent / 'brands'


def brand(name, *elements):
    write(name, *elements, folder=BRANDS)


# Keith's tiles ------------------------------------------------------------------------
# PhotoCraft and VectorCraft are not drawn here: brands/photocraft.svg and
# brands/vectorcraft.svg were traced from Keith's Lumo line-art references with
# tools/centerline.py and finished by hand (see README.md).

_cx, _cy, _r = 13.75, 11.25, 6.75
brand('cadcraft',
      path('M3 3.5V20.5h17z'),                       # set square
      path('M6.25 11.25v6h6z'),                      # its inner triangle
      path('M3 7h1.75M3 10h1.25M3 13h1.75M3 16h1.25'),  # ruler ticks
      path(f'M{f(_cx, _cy - _r)}A{f(_r, _r)} 0 0 1 {f(_cx + _r, _cy)}'),  # arc
      dot(_cx, _cy, 1), dot(_cx + _r, _cy + 1.5, 1.1))

# Original glyphs for the rest of the suite ---------------------------------------------
brand('anicraft', circle(5.75, 16.75, 2.75), circle(11.25, 12.75, 3.5), circle(17.25, 8, 4.25))
brand('deckcraft', rect(2.25, 3.25, 19.5, 12.5), path('M12 15.75v2.5M8 21.25l4-3 4 3'),
      path('M7 12.25v-2M10.5 12.25V7.75M14 12.25v-3M17.5 12.25V6.5'))
brand('designcraft', rect(4.25, 2.25, 15.5, 19.5), rect(7.25, 5.25, 9.5, 5.5, 1),
      path('M7.25 14h9.5M7.25 17.25h6'))
brand('effectcraft',
      path('M11 4.5c.6 4.5 2.5 6.9 7 8.25-4.5 1.35-6.4 3.75-7 8.25-.6-4.5-2.5-6.9-7-8.25 4.5-1.35 6.4-3.75 7-8.25z'),
      path('M18.5 2.5v4M16.5 4.5h4'))
brand('figcraft', '<rect x="2.75" y="2.75" width="13" height="13" rx="2" stroke-dasharray="2.5 2.5"/>',
      path('M12.5 12.5l8.75 3.25-3.75 1.5-1.5 3.75z'))
brand('filmcraft', rect(2.75, 10, 18.5, 11.25),
      path('M3.15 9.6l16.9-4.55a1 1 0 0 1 1.23.7l.65 2.42L3.4 13.2'),
      path('M8.5 7.6l1.75 3.15M13.25 6.3L15 9.45M18 5l1.75 3.15'))
brand('gridcraft', rect(2.25, 3.25, 19.5, 17.5),
      '<path d="M3 4h18v4.75H3z" fill="currentColor" stroke="none" opacity="0.35"/>',
      path('M2.25 8.75h19.5M2.25 14.75h19.5M9 3.25v17.5M15.5 3.25v17.5'))
# Aperture: six blades drawn as chords inside the ring.
_blades = []
for i in range(6):
    a = 60 * i
    x0, y0 = polar(12, 12, 9.75, a)
    x1, y1 = polar(12, 12, 4.5, a + 100)
    _blades.append(f'M{f(x0, y0)}L{f(x1, y1)}')
brand('lightcraft', circle(12, 12, 9.75), path(''.join(_blades)))
brand('pdfcraft', path('M13.5 2H6a1.75 1.75 0 0 0-1.75 1.75v16.5A1.75 1.75 0 0 0 6 22h5'),
      path('M13.5 2v4.25a1 1 0 0 0 1 1h4.25V11'), path('M13.5 2l5.25 5.25'),
      path('M17.5 13.25l3.5 3.5-5.25 5.25H12.25v-3.5z'), path('M15.75 15l3.5 3.5'))
brand('soundcraft', path('M3.25 10.5v3M6.5 7.5v9M9.75 4v16M13 8.5v7M16.25 5.75v12.5M19.5 9.75v4.5'))
brand('wordcraft', path('M20.5 3C13 3 8 8 7.25 15.5L5.5 20.5'),
      path('M20.5 3c0 6-3 10.5-8.75 12.5l-4.5 0'), path('M15.5 8.5L9.25 14.75'))
brand('artcraft',
      path('M12 2.75C6.6 2.75 2.75 6.75 2.75 11.75c0 5 4 9.5 8.75 9.5 1.5 0 2.25-.85 2.25-2.1'
           ' 0-1.6-1.6-2.4-.6-3.65.6-.75 1.6-.85 3.1-.85h2.1c1.9 0 2.9-1.4 2.9-3.4 0-4.75-4.1-8.5-9.25-8.5z'),
      dot(7.5, 11, 1.4), dot(10, 6.75, 1.4), dot(15, 6.75, 1.4), dot(18, 10.25, 1.4))
brand('craft-launcher',
      path('M12 2.5c3.25 2.25 4.75 5.75 4.75 9.5v5.25h-9.5V12c0-3.75 1.5-7.25 4.75-9.5z'),
      circle(12, 9.75, 1.75), path('M7.25 13.5l-3 3.25v3.5l3-1.75M16.75 13.5l3 3.25v3.5l-3-1.75'),
      path('M10.25 20v1.75M13.75 20v1.75'))

if __name__ == '__main__':
    print(f'{len(list(BRANDS.glob("*.svg")))} brand icons in {BRANDS}')
