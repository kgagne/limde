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
- Tiers 2 and 3 (164 icons): system concepts and text-editing controls, drawn 2026-10-24 by
  `draw_tier2.py`. `sparkle` and `agent-threads` (the agent-web window: chat bubble with a
  sparkle, Keith's pick of four drafts) added 2026-10-26. `aliases.toml` maps 378 freedesktop icon names onto the 239 drawings.
  Against GNOME's Adwaita symbolic set (498 names, excluding legacy and right-to-left), 355
  are covered. The rest are skipped on purpose: emoji faces, weather, presence states,
  screen orientation, cellular generations, and Apple-specific devices.
- Tier 4 (brands), in `brands/` (39 icons; `brands.toml` maps them to app icon names):
  - The 16 Craft apps are original line glyphs. PhotoCraft (fox) and VectorCraft
    (dragon) were traced from Keith's Lumo line-art references with `tools/centerline.py`.
    LightCraft is a light bulb, so it doesn't clash with darktable's aperture logo.
  - 18 third-party logos are solid icons from Simple Icons (`import_simple_icons.py`).
    That's deliberate: they are accurate and CC0 or openly licensed, and Keith's desktop
    already pairs line system icons with solid brand logos.
  - darktable, RawTherapee, btop, foot and Papers, which Simple Icons lacks, are line
    drawings (`draw_brands_apps.py`).
  - Licences follow each logo: CC BY-SA files are in `brands/cc-by-sa/` (credits in
    `CREDITS.md`), MPL-2.0 files in `brands/mpl-2.0/`. Trademarks and the not-included
    list are in `brands/NOTICE.md`.

Generators: `_draw.py` (shared helpers and outlines), `draw_tier1.py`, `draw_tier2.py`,
`draw_brands_craft.py`, `draw_brands_apps.py`, `import_simple_icons.py`.
