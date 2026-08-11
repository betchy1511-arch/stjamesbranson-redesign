"""
Strip the synthetic "foot" off the branded St. James glass cut-out.

make-glass-assets.py draws a foot onto glass-empty.png / glass-full.png because
the real foot is buried in the plate of ice in the source photo. At render size
that drawn foot reads as a flat grey COASTER sitting under a severed stem, which
is exactly what Beth flagged on 2026-08-12.

This script erases it in place and leaves everything else untouched.

CRITICAL: the canvas height is NOT cropped. add_foot() pads the image by
EXTRA=80px, and the CSS mask-position percentages in index.html (@keyframes
sjFillB) are computed against that padded height H. Cropping the image would
silently shift the wine level on the middle glass. So the foot band is made
transparent and the 80px of empty space is kept.

Re-runnable, but it is idempotent-unsafe: it works off the ORIGINALS in
img/_orig/, which it creates on first run. Run again and it re-derives from
those backups rather than eating further into an already-stripped file.
"""
import os
import sys
from PIL import Image, ImageFilter
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, '..', 'img')
ORIG = os.path.join(IMG, '_orig')

EXTRA = 80          # must match make-glass-assets.py

# add_foot() starts its drawn taper at h0-6, so the real photographed stem is
# solid right up to there. FADE was 26 on the first pass, which dissolved 26
# rows of REAL stem and left the glass visibly ending in mid-air above the
# shelf line. Keep it short: just enough to avoid a guillotine edge.
FADE = 4

os.makedirs(ORIG, exist_ok=True)


def strip(name):
    src = os.path.join(IMG, name)
    bak = os.path.join(ORIG, name)

    # first run: keep a pristine copy so this stays re-runnable
    if not os.path.exists(bak):
        Image.open(src).save(bak)
        print('backed up  %s' % name)

    im = Image.open(bak).convert('RGBA')
    W, H = im.size
    h0 = H - EXTRA                      # bottom of the real photographed glass
    cut = h0 - 6                        # add_foot()'s taper polygon starts here

    a = np.asarray(im).astype(np.float32).copy()

    # hard-clear everything from the taper down
    a[cut:, :, 3] = 0.0

    # feather the last FADE rows of real glass into that, so the stem fades out
    # instead of ending on a guillotine line
    y = np.arange(cut - FADE, cut)
    ramp = np.linspace(1.0, 0.0, FADE).astype(np.float32)[:, None]
    a[cut - FADE:cut, :, 3] *= ramp

    out = Image.fromarray(a.astype(np.uint8), 'RGBA')

    # a whisper of blur on the fade band only, to kill any banding
    band = out.crop((0, cut - FADE - 4, W, cut + 4)).filter(ImageFilter.GaussianBlur(1.1))
    out.paste(band, (0, cut - FADE - 4))

    out.save(src, optimize=True)

    alpha = np.asarray(out)[:, :, 3]
    rowmax = alpha.max(axis=1)
    solid = int(np.nonzero(rowmax > 250)[0].max())   # last fully-opaque row
    print('%-18s %dx%d  solid stem now ends y=%d, faint tail to y=%d'
          % (name, W, H, solid, int(np.nonzero(rowmax > 8)[0].max())))
    return H, solid


heights = [strip(n) for n in ('glass-empty.png', 'glass-full.png')]

# ---- the CSS number, derived rather than assumed --------------------------
# The transparent tail below the stem is real layout space, and .pour-row is
# flex-end aligned, so the glass hangs that far off the shelf line. The first
# pass hard-coded 80px for this and under-corrected, because the stripped
# image's solid edge is nowhere near h0-80. Measure it instead.
H, solid = heights[0]
tail_frac = (H - solid) / H
IMG_W, IMG_H = 620, 1154                 # intrinsic size of the cut-out
CSS_W = 200                              # .v-patio .pi-lg width, in --u units
rendered_h = CSS_W * (IMG_H / IMG_W)     # height in --u units
pull = rendered_h * tail_frac

print()
print('tail = %d px of %d  (%.3f%% of height)' % (H - solid, H, tail_frac * 100))
print('CSS  -> .v-patio .rg.pi-lg      { margin-bottom: calc(-%.2fpx * var(--u)); }' % pull)
print('CSS  -> .v-patio .pi-lg .rg-shadow { bottom: calc(%.2fpx * var(--u) + .2%%); }' % pull)
print()
print('canvas heights unchanged, so the sjFillA mask-position values still hold')
