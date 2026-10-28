#!/usr/bin/env python3
"""Build the installable "limde" icon theme from outlined/ (standard library only).

usage: build_theme.py OUTPUT_DIR [--name limde] [--color '#888888']
                        [--backgrounds '#1e1e1e,#262626,#343434']
                        [--selected '#eeeeee' --selected-brightness 0.65]

Writes OUTPUT_DIR/NAME/ with:
  symbolic/icons/NAME-symbolic.svg  for every icon and alias. GTK recolours these itself.
  24x24/icons/NAME.svg              the same shapes with --color baked in, for programs that
                              do not recolour (and for app icons in launchers and panels).
                              Brand icons get their colour from brand-colours.toml instead,
                              fitted to reach 3:1 on every --backgrounds colour (contrast.py).
With --selected, the build also checks each plain icon on that selected-row colour, after
the -gtk-icon-filter: brightness() the appearance applies there, and fails below 3:1.

    build_theme.py OUTPUT_DIR --appearance DEFAULTS.toml [--user USER.toml] --mode dark|light

takes all of those from limde's appearance settings instead: the mode's palette (the
muted colour for plain icons; background, surface and hover; the selection) and the
icon theme name ("limde", or "limde-light" for the light mode).
Aliases (aliases.toml) and brand names (brands.toml) are relative symlinks to the drawn
files. The theme inherits Adwaita and hicolor, so anything limde does not draw falls
back to them.
"""
import argparse
import re
import shutil
import tomllib
from pathlib import Path

import contrast

HERE = Path(__file__).resolve().parent
OUTLINED = HERE / 'outlined'
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')

INDEX = """[Icon Theme]
Name={name}
Comment=limde's own line icons and brand icons
Inherits=Adwaita,hicolor
Directories=symbolic/icons,24x24/icons

[symbolic/icons]
Context=Actions
Size=16
MinSize=8
MaxSize=512
Type=Scalable

[24x24/icons]
Context=Applications
Size=48
MinSize=8
MaxSize=512
Type=Scalable
"""


def from_appearance(args):
    config = tomllib.loads(args.appearance.read_text())
    if args.user and args.user.is_file():
        for group, entries in tomllib.loads(args.user.read_text()).items():
            if isinstance(entries, dict) and group in config:
                config[group].update(entries)
    colours = {k: v[:7] for k, v in config['colors' if args.mode == 'dark' else 'colors_light'].items()}
    theme = config['icons']['theme']
    args.name = theme if args.mode == 'dark' else theme + '-light'
    args.color = colours['muted']
    args.backgrounds = ','.join(colours[k] for k in ('background', 'surface', 'hover'))
    args.selected = colours['selection']
    args.selected_brightness = float(config['icons']['selected_brightness']) if args.mode == 'dark' else 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('output')
    ap.add_argument('--name', default='limde', help='theme name (folder and index.theme)')
    ap.add_argument('--color', default='#888888', help='colour baked into the plain (24x24/) copies')
    ap.add_argument('--backgrounds', default='#1e1e1e,#262626,#343434',
                    help='comma-separated colours brand icons must read on (3:1)')
    ap.add_argument('--selected', help='selected-row background to check plain icons on')
    ap.add_argument('--selected-brightness', type=float, default=1.0,
                    help='the brightness() filter applied to icons on selected rows')
    ap.add_argument('--appearance', type=Path, help="appearance.toml with limde's defaults")
    ap.add_argument('--user', type=Path, help="the user's appearance.toml, if any")
    ap.add_argument('--mode', choices=('dark', 'light'), default='dark')
    args = ap.parse_args()
    if args.appearance:
        from_appearance(args)
    backgrounds = args.backgrounds.split(',')
    for colour in [args.color, *backgrounds, *([args.selected] if args.selected else [])]:
        if not HEX.match(colour):
            ap.error(f'{colour}: colours must look like #rrggbb')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.name):
        ap.error('--name: letters, digits, - and _ only')

    colours = {}  # brand file key -> fitted colour
    table = tomllib.loads((HERE / 'brand-colours.toml').read_text())
    light = table.pop('light', {})
    for rel, choice in light.items():
        if choice != 'plain':
            raise SystemExit(f'{rel}: [light] entries are "plain"')
    for group in table.values():
        for rel, colour in group.items():
            if args.mode == 'light' and rel in light:
                continue
            fitted = contrast.fit(colour, backgrounds, also=lambda c: not args.selected or contrast.ratio(
                contrast.brightness(c, args.selected_brightness), args.selected) >= contrast.GRAPHICS)
            if fitted is None:
                raise SystemExit(f'{rel}: no shade of {colour} reaches 3:1 on {args.backgrounds}'
                                 + (f' and on {args.selected} when selected' if args.selected else ''))
            colours['brand:' + rel] = fitted
    failures = []

    theme = Path(args.output) / args.name
    shutil.rmtree(theme, ignore_errors=True)
    # A category level below each size folder, and the plain icons under a size-named
    # folder: Mako only finds icons in <size>/<category>/ ("scalable" is skipped). The
    # folder is still declared Scalable, so GTK draws the SVGs at any size.
    sym, sca = theme / 'symbolic' / 'icons', theme / '24x24' / 'icons'
    sym.mkdir(parents=True)
    sca.mkdir(parents=True)
    (theme / 'index.theme').write_text(INDEX.format(name=args.name))

    drawn = {}  # icon name -> outlined file
    for f in sorted((OUTLINED / 'src').glob('*.svg')):
        drawn[f.stem] = f
    names = {}  # every name the theme answers to -> drawn file key
    for name in drawn:
        names[name] = name
    for group in tomllib.loads((HERE / 'aliases.toml').read_text()).values():
        for alias, target in group.items():
            names.setdefault(alias, target)
    for group in tomllib.loads((HERE / 'brands.toml').read_text()).values():
        for rel, app_names in group.items():
            key = 'brand:' + rel
            drawn[key] = OUTLINED / 'brands' / rel
            for app in app_names:
                names[app] = key

    stored = {}
    for key, src in drawn.items():
        if not src.exists():
            raise SystemExit(f'missing outlined icon: {src}')
        base = re.sub(r'[^A-Za-z0-9._-]', '_', key.replace('brand:', 'brand-').replace('/', '-')[:-4]
                      if key.startswith('brand:') else key)
        text = src.read_text()
        (sym / f'{base}-symbolic.svg').write_text(text)
        colour = colours.get(key, args.color)
        (sca / f'{base}.svg').write_text(text.replace('currentColor', colour))
        stored[key] = base
        if args.selected:
            shown = contrast.brightness(colour, args.selected_brightness)
            if contrast.ratio(shown, args.selected) < contrast.GRAPHICS:
                failures.append(f'{key}: {colour} shows as {shown} on {args.selected}, '
                                f'{contrast.ratio(shown, args.selected):.2f}:1')
    unused = set(colours) - set(drawn)
    if unused or failures:
        raise SystemExit('\n'.join([f'{k}: in brand-colours.toml but not in brands.toml' for k in sorted(unused)]
                                   + failures))

    count = 0
    for name, key in sorted(names.items()):
        if key not in stored:
            raise SystemExit(f'{name} points at {key}, which is not drawn')
        base = stored[key]
        for folder, suffix in ((sym, '-symbolic'), (sca, '')):
            link = folder / f'{name}{suffix}.svg'
            if link.name != f'{base}{suffix}.svg':
                link.symlink_to(f'{base}{suffix}.svg')
        count += 1
    print(f'{theme}: {len(stored)} drawn icons, {count} names (each also as -symbolic)')


if __name__ == '__main__':
    main()
