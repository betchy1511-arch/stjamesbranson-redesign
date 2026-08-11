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
FADE = 26           # px of soft fade so the stem does not end on a hard edge

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
    rows = np.nonzero(alpha.max(axis=1) > 8)[0]
    print('%-18s %dx%d  canvas kept, opaque now ends y=%d (was %d)'
          % (name, W, H, rows.max(), H - 1))


for n in ('glass-empty.png', 'glass-full.png'):
    strip(n)

print('done - canvas heights unchanged, so the CSS mask-position values still hold')
