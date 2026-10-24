#!/usr/bin/env python3
"""Convert the icon sources (strokes) into filled outlines in outlined/.

GTK recolours "-symbolic" icons by forcing a fill colour onto every shape, which would
turn a stroked circle into a disc. Converting strokes to outlines once, here, makes the
icons render the same in every toolkit. Runs on a maintainer's machine, not at install:

    uv run --no-project --with picosvg python tools/outline.py

It rewrites outlined/ completely and records each source's sha256 in outlined/SOURCES.json,
so scripts/check can tell when a source changed without re-running this.
"""
import hashlib
import json
import shutil
from pathlib import Path

from picosvg.svg import SVG

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'outlined'
SOURCES = [HERE / 'src', HERE / 'brands']

shutil.rmtree(OUT, ignore_errors=True)
record = {}
for root in SOURCES:
    for src in sorted(root.rglob('*.svg')):
        rel = src.relative_to(HERE)
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        svg = SVG.parse(str(src)).topicosvg()
        text = svg.tostring(pretty_print=False)
        # Single colour everywhere: whatever draws the icon decides it.
        text = text.replace('fill="black"', 'fill="currentColor"')
        if 'fill=' not in text.split('<path', 1)[-1]:
            text = text.replace('<path ', '<path fill="currentColor" ')
        dest.write_text(text + '\n')
        record[str(rel)] = hashlib.sha256(src.read_bytes()).hexdigest()
(OUT / 'SOURCES.json').write_text(json.dumps(record, indent=1, sort_keys=True) + '\n')
print(f'{len(record)} icons outlined into {OUT}')
