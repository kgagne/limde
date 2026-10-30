# UI sizing rules

How big to make things in Tinybar and its popovers, so a new widget fits without a
design review. The numbers are the ones limDE already uses; this file writes them down.
Colours, radii and borders come from `components/appearance/appearance.toml`; padding,
gaps and font sizes live in `components/appearance/templates/tinybar.css.in` and in the
`spacing=` of the boxes in `components/tinybar/tinybar.py`.

Check any change with a screenshot (`tests/vm/vm shot`) of the popover before and after.

## Text

| Role | Size | Line height |
|---|---|---|
| Panel text (clock), tooltips | 16 px | 22 |
| Panel labels (task names, values) | 13 px | 18 |
| Popover text: titles, rows, buttons, entries, empty states | 13 px | 18 |
| Graph labels | 11 px | — |

Set a size on the label itself (a class on the `Gtk.Label`, or `selector > label`), not on
its container: the base `* { font-size: 16px }` rule matches every node, so a size on a
button or box never reaches the text inside.

Today every label in a panel popover renders at 13 px, because
`.system-info label:not(.status-icon)` reaches into popovers (a popover is a CSS child of
its panel button). The 12 px meant for detail lines and section headings never applies.
Whether those should drop to 12 px is open; until then, use 13 px.

## Spacing

Scale: 1, 2, 4, 6, 8, 12, 16 px.
- Popover card padding 8; 6 between blocks; 4 between rows of a list.
- Row padding `6px 8px`; text starts 8 px from a row or card edge; 8 between an icon and
  its text (`panel_row`).
- 1 only between a title and its detail line.
- Panel: margins 12 at the sides and 5 top and bottom, 12 between groups, 4 between
  items. Panel buttons use `1px 7px` with a `-7px` margin so their highlight lines up.

## Controls in popovers

Every control must fit the 18 px line of 13 px text, so rows stay 30 px (one line) or
48 px (two lines) whatever they hold. A GTK control left unstyled takes GTK's own size
(a 50×26 switch, 34 px entries and buttons), which is too big here.

| Control | Size | How |
|---|---|---|
| One-line row | 30 tall | `.panel-row`: 6 + 18 + 6 |
| Two-line row | 48 tall | title, 1 px gap, detail |
| Switch | 34 × 18 | `popover switch`, knob 14 with 1 px margin |
| Entry | 26 tall | `popover entry`, 13 px text and placeholder |
| Framed text button | 26 tall | `.network-action`: `min-height: 0; padding: 3px 10px` |
| Icon button | 20 tall | `padding: 2px 6px`, no frame (`.power-arrow`, `.volume-mute`) |
| Slider | 18 tall | `.volume-slider`: knob 14, no border |

Sizing rules for switches and entries already apply to every popover; reuse the classes
above for buttons and sliders instead of new values.

## Icons

16 px in the panel, for a row's leading icon (in a 20 px column) and in menus
(`[icons] panel_size`, `menu_size`); 13 px for trailing marks and glyphs inside controls
(`small_size`); 32 px in the launcher.

## Shape

`control_radius` for anything inside a surface, `popup_radius` for surfaces, half the
height for pills (the switch), `border_width` for every framed control. No other radius or
border numbers.

## Known differences, not yet settled

- The power menu uses card padding 6 and a row gap of 2 (ported as is).
- The panel grows 2 px when the bell shows a count; its height is not fixed.
- Walker, Mako and labwc have their own sizes (10 px paddings, 10–11 pt text).
