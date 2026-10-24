"""Centre-line trace of a line drawing's main strokes → a 24-unit stroke icon.

usage: centerline.py IMAGE OUT.svg [min_width_px] [min_len_px] [tolerance_px] [dilate_px]

Keeps only strokes at least min_width_px wide, finds their centre lines, drops strokes
shorter than min_len_px, simplifies them (tolerance_px) and smooths them into curves
fitted to the 24-unit box. Cyan accents become filled shapes. Run it in a throwaway
environment, e.g. `uv run --no-project --with pillow --with numpy --with scikit-image
--with skan python tools/centerline.py ...`. The output is a starting point; finish by hand.
PhotoCraft used: 7 140 10 0, then the accents enlarged 1.9x around their centres.
"""
import sys
import numpy as np
from PIL import Image
from skimage import morphology, measure
from skan import Skeleton

img = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int)
out = sys.argv[2]
min_w = int(sys.argv[3]) if len(sys.argv) > 3 else 9
min_len = float(sys.argv[4]) if len(sys.argv) > 4 else 60
tol = float(sys.argv[5]) if len(sys.argv) > 5 else 3
gray = img.mean(-1)
dark = gray < 110
# Keep strokes at least min_w px wide: opening removes thinner lines.
thick = morphology.binary_opening(dark, morphology.disk(min_w // 2))
thick = morphology.remove_small_objects(thick, 400)
dil = int(sys.argv[6]) if len(sys.argv) > 6 else 2
if dil: thick = morphology.binary_dilation(thick, morphology.disk(dil))
skel = morphology.skeletonize(thick)
sk = Skeleton(skel)
paths = []
for i in range(sk.n_paths):
    c = sk.path_coordinates(i)
    if len(c) < 2:
        continue
    length = np.sum(np.hypot(*np.diff(c, axis=0).T))
    if length < min_len:
        continue
    paths.append(measure.approximate_polygon(c, tolerance=tol))
# Coloured accents (cyan): filled shapes.
r, g, b = img[..., 0], img[..., 1], img[..., 2]
accent = (b > 150) & (r < 150) & (b - r > 60)
accent = morphology.remove_small_objects(accent, 80)
fills = []
lab = measure.label(accent)
for reg in measure.regionprops(lab):
    cont = measure.find_contours((lab == reg.label).astype(float), 0.5)
    if cont:
        fills.append(measure.approximate_polygon(max(cont, key=len), tolerance=2))
allp = np.vstack([p for p in paths] + [f for f in fills])
y0, x0 = allp.min(0); y1, x1 = allp.max(0)
scale = 20.5 / max(y1 - y0, x1 - x0)
ox = 1.75 + (20.5 - (x1 - x0) * scale) / 2
oy = 1.75 + (20.5 - (y1 - y0) * scale) / 2
T = lambda p: (ox + (p[1] - x0) * scale, oy + (p[0] - y0) * scale)
def smooth(pts):
    """Catmull-Rom → cubic Bézier through the simplified points."""
    pts = [T(p) for p in pts]
    if len(pts) == 2:
        return f'M{pts[0][0]:.2f} {pts[0][1]:.2f}L{pts[1][0]:.2f} {pts[1][1]:.2f}'
    d = f'M{pts[0][0]:.2f} {pts[0][1]:.2f}'
    for i in range(len(pts) - 1):
        p0 = pts[max(i - 1, 0)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f'C{c1[0]:.2f} {c1[1]:.2f} {c2[0]:.2f} {c2[1]:.2f} {p2[0]:.2f} {p2[1]:.2f}'
    return d
el = [f'<path d="{smooth(p)}"/>' for p in paths]
el += ['<path d="M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in map(T, f)) + 'Z" fill="currentColor" stroke="none"/>' for f in fills]
open(out, 'w').write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                     'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">\n' + '\n'.join(el) + '\n</svg>\n')
print(out, len(paths), 'strokes,', len(fills), 'fills')
