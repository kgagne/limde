#!/usr/bin/env python3
"""Import selected brand logos from Simple Icons (simpleicons.org) as solid icons.

usage: import_simple_icons.py PATH_TO_SIMPLE_ICONS_PACKAGE

Simple Icons draws accurate single-colour logos on a 24-unit grid, edge to edge. This
places each one inside elachisto's margin (1.75 units) and files it by the licence
Simple Icons records for it: CC0 into brands/, CC BY-SA into brands/cc-by-sa/, MPL-2.0
into brands/mpl-2.0/. Brands Simple Icons lacks are drawn by draw_brands_apps.py.
Trademark rules still apply; see brands/NOTICE.md.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# elachisto icon name -> Simple Icons slug
WANT = {
    'blender': 'blender', 'gimp': 'gimp', 'inkscape': 'inkscape', 'krita': 'krita',
    'libreoffice-startcenter': 'libreoffice', 'libreoffice-writer': 'libreofficewriter',
    'libreoffice-calc': 'libreofficecalc', 'libreoffice-impress': 'libreofficeimpress',
    'vlc': 'vlcmediaplayer', 'mpv': 'mpv', 'audacity': 'audacity', 'kdenlive': 'kdenlive',
    'obs': 'obsstudio', 'keepassxc': 'keepassxc', 'transmission': 'transmission',
    'vscodium': 'vscodium', 'nvim': 'neovim', 'htop': 'htop',
}
FOLDER = {None: 'brands', 'CC-BY-SA-3.0': 'brands/cc-by-sa', 'CC-BY-SA-4.0': 'brands/cc-by-sa',
          'MPL-2.0': 'brands/mpl-2.0'}

pkg = Path(sys.argv[1])
version = json.loads((pkg / 'package.json').read_text())['version']
data = json.loads((pkg / 'data' / 'simple-icons.json').read_text())
data = data if isinstance(data, list) else data['icons']


def slug_of(icon):
    if 'slug' in icon:
        return icon['slug']
    title = icon['title'].lower().replace('+', 'plus').replace('.', 'dot').replace('&', 'and')
    return re.sub(r'[^a-z0-9]', '', title)


meta = {slug_of(i): i for i in data}
rows = []
for name, slug in WANT.items():
    licence = (meta[slug].get('license') or {}).get('type')
    folder = HERE / FOLDER[licence]
    folder.mkdir(parents=True, exist_ok=True)
    d = re.search(r'<path d="([^"]+)"', (pkg / 'icons' / f'{slug}.svg').read_text()).group(1)
    (folder / f'{name}.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">\n'
        f'<!-- {meta[slug]["title"]}: Simple Icons {version} ("{slug}"), {licence or "CC0-1.0"} -->\n'
        f'<path transform="translate(1.75 1.75) scale(0.854167)" d="{d}"/>\n</svg>\n')
    rows.append((name, meta[slug]['title'], slug, licence or 'CC0-1.0', FOLDER[licence]))
print(f'Simple Icons {version}:')
for r in rows:
    print('  {:24} {:22} {:20} {:13} {}'.format(*r))
