#!/usr/bin/env python3
"""Draw the CADCraft and AniCraft brand icons into brands/ (the other Craft apps: see below).

CADCraft (set square) is a line version of Keith's own tile (2026-10-23). AniCraft has no
upstream icon yet, so it gets an original glyph. Style rules: README.md.
"""
from pathlib import Path

from _draw import circle, dot, f, path, write

BRANDS = Path(__file__).resolve().parent / 'brands'


def brand(name, *elements):
    write(name, *elements, folder=BRANDS)


# Keith's tiles ------------------------------------------------------------------------
# The other 13 Craft icons are not drawn here: they are hand-edited files in brands/,
# drawn from Keith's Lumo line-art references (see README.md). PhotoCraft and VectorCraft
# started as tools/centerline.py traces; the rest were drawn by hand on the 24-unit grid.

_cx, _cy, _r = 13.75, 11.25, 6.75
brand('cadcraft',
      path('M3 3.5V20.5h17z'),                       # set square
      path('M6.25 11.25v6h6z'),                      # its inner triangle
      path('M3 7h1.75M3 10h1.25M3 13h1.75M3 16h1.25'),  # ruler ticks
      path(f'M{f(_cx, _cy - _r)}A{f(_r, _r)} 0 0 1 {f(_cx + _r, _cy)}'),  # arc
      dot(_cx, _cy, 1), dot(_cx + _r, _cy + 1.5, 1.1))

# Original glyph ------------------------------------------------------------------------
# A ball with two fading onion-skin outlines trailing behind it.
brand('anicraft', circle(16.25, 8.25, 5),
      path('M10 9.75a3.75 3.75 0 0 0 0 7.5'), path('M4.5 15.75a2.75 2.75 0 0 0 0 5.5'))

if __name__ == '__main__':
    print(f'{len(list(BRANDS.glob("*.svg")))} brand icons in {BRANDS}')
