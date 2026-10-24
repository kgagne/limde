# elachisto icons

elachisto's own icon set: hand-written SVG, MIT-licensed like the rest of the project.
No icon font is used anywhere in elachisto; fonts are for text only.

## Style rules

Every icon in `src/` follows these, so the set reads as one family:

- `viewBox="0 0 24 24"`, drawn on whole and half pixels.
- Strokes, not fills: `stroke-width="1.5"`, round caps and joins, `fill="none"`.
  Small solid details (a battery's charge, a Wi-Fi dot) are filled shapes with no stroke.
- Colour is always `currentColor`; whatever draws the icon decides the colour.
- Content fills the box to about 1.75 px from each edge; corners use a 2.25 px radius
  (1.75 px on folders and files, 1 px on small inner shapes).
- Families (battery levels, Wi-Fi strength, volume) share one outline and differ only in
  what is filled or shown.
- Brand logos are never redrawn here; apps keep their own icons.

## Status

- Tier 1, the panel set (75 icons): drawn 2026-10-24 by `draw_tier1.py`; Keith approved the style from 10 samples.
- Tiers 2 and 3 (162 icons): system concepts and text-editing controls, drawn 2026-10-24 by
  `draw_tier2.py`. `aliases.toml` maps 378 freedesktop icon names onto the 237 drawings.
  Against GNOME's Adwaita symbolic set (498 names, excluding legacy and right-to-left), 355
  are covered. The rest are skipped on purpose: emoji faces, weather, presence states,
  screen orientation, cellular generations, and Apple-specific devices.
- Tier 4 (brands), in `brands/`, drawn by `draw_brands_craft.py`:
  - All 16 Craft icons drafted 2026-10-24. CADCraft follows Keith's set-square tile; the other
    thirteen are original glyphs.
  - PhotoCraft (kitsune) and VectorCraft (dragon) come from Keith's Lumo line-art
    references, composed for icon size: the fox's face and tails, the dragon's head.
    - The fox was traced with `tools/centerline.py`, then its diamond and eye enlarged.
      Keith chose it over a hand-drawn version.
    - The dragon was hand-drawn on a grid over the reference, with its mouth curved and
      shortened at Keith's request.
    - The references stay in Keith's own machine repository, not here.
  - AniCraft needs a redesign: it reads as a chain link.
  - Third-party logos only after their owner's logo policy has been checked.

Generators: `_draw.py` (shared helpers and outlines), `draw_tier1.py`, `draw_tier2.py`.
