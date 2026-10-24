#!/usr/bin/env python3
"""Copy one file out of an ISO 9660 image without mounting it (no root needed).

Usage: iso-extract.py IMAGE PATH_IN_ISO DEST
Names are matched case-insensitively, ignoring ISO 9660 version suffixes (";1") and
trailing dots, so "casper/vmlinuz" finds "CASPER/VMLINUZ.;1".
"""
import sys

SECTOR = 2048


def records(f, extent, size):
    """Yield (name, extent, size, is_dir) for each entry in a directory."""
    f.seek(extent * SECTOR)
    data = f.read(size)
    pos = 0
    while pos < len(data):
        length = data[pos]
        if length == 0:  # records never cross a sector boundary; skip padding
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        rec = data[pos:pos + length]
        name_len = rec[32]
        name = rec[33:33 + name_len]
        if name not in (b'\x00', b'\x01'):
            yield (name.decode('ascii', 'replace').split(';')[0].rstrip('.').lower(),
                   int.from_bytes(rec[2:6], 'little'),
                   int.from_bytes(rec[10:14], 'little'),
                   bool(rec[25] & 2))
        pos += length


def main(image, path, dest):
    with open(image, 'rb') as f:
        f.seek(16 * SECTOR)
        pvd = f.read(SECTOR)
        if pvd[1:6] != b'CD001' or pvd[0] != 1:
            sys.exit(f'{image}: no ISO 9660 primary volume descriptor')
        root = pvd[156:156 + 34]
        extent = int.from_bytes(root[2:6], 'little')
        size = int.from_bytes(root[10:14], 'little')
        parts = [p.lower() for p in path.strip('/').split('/')]
        for i, part in enumerate(parts):
            match = next((r for r in records(f, extent, size) if r[0] == part), None)
            if match is None:
                sys.exit(f'{path}: "{part}" not found in {image}')
            _, extent, size, is_dir = match
            if is_dir != (i < len(parts) - 1):
                sys.exit(f'{path}: "{part}" is not the expected type')
        f.seek(extent * SECTOR)
        with open(dest, 'wb') as out:
            remaining = size
            while remaining:
                chunk = f.read(min(remaining, 1 << 20))
                out.write(chunk)
                remaining -= len(chunk)


if __name__ == '__main__':
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
