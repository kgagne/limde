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

Style samples (10 icons, 2026-10-24), awaiting review before the rest of the set is drawn.
