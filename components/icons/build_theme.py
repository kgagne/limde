#!/usr/bin/env python3
"""Build the installable "elachisto" icon theme from outlined/ (standard library only).

usage: build_theme.py OUTPUT_DIR [--color '#eeeeee']

Writes OUTPUT_DIR/elachisto/ with:
  symbolic/icons/NAME-symbolic.svg  for every icon and alias. GTK recolours these itself.
  24x24/icons/NAME.svg              the same shapes with --color baked in, for programs that
                              do not recolour (and for app icons in launchers and panels).
Aliases (aliases.toml) and brand names (brands.toml) are relative symlinks to the drawn
files. The theme inherits Adwaita and hicolor, so anything elachisto does not draw falls
back to them.
"""
import argparse
import re
import shutil
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTLINED = HERE / 'outlined'
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')

INDEX = """[Icon Theme]
Name=elachisto
Comment=elachisto's own line icons and brand icons
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('output')
    ap.add_argument('--color', default='#888888', help='colour baked into the plain (24x24/) copies')
    args = ap.parse_args()
    if not HEX.match(args.color):
        ap.error('--color must look like #rrggbb')

    theme = Path(args.output) / 'elachisto'
    shutil.rmtree(theme, ignore_errors=True)
    # A category level below each size folder, and the plain icons under a size-named
    # folder: Mako only finds icons in <size>/<category>/ ("scalable" is skipped). The
    # folder is still declared Scalable, so GTK draws the SVGs at any size.
    sym, sca = theme / 'symbolic' / 'icons', theme / '24x24' / 'icons'
    sym.mkdir(parents=True)
    sca.mkdir(parents=True)
    (theme / 'index.theme').write_text(INDEX)

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
        (sca / f'{base}.svg').write_text(text.replace('currentColor', args.color))
        stored[key] = base

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
