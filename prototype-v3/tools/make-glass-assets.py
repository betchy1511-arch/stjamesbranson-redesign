"""
Builds the three pour assets for the St. James v3 Patio hero, from one photo.

  img/glass-empty.png  the branded glass, cut out, interior made see-through
  img/glass-full.png   the same glass with its real wine
  img/wine-mask.png    2x-tall CSS mask: transparent above a curved surface,
                       opaque below it. Sliding it up raises the wine level.

Source: ABH02512.jpg (St. James branded glass on a plate of ice). The glass
foot is buried in the ice and is not in the photo, so a foot is drawn on in
the stem's own colour rather than cut from the picture.

Run:  python3 tools/make-glass-assets.py
"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from PIL import Image, ImageDraw, ImageFilter
import numpy as np, math

HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = r'C:\Users\betch\Downloads\02_Skills-and-Plugins\ABH02512.jpg'
OUT  = os.path.join(os.path.dirname(HERE), 'img')

# ---- silhouette, traced off the photo in source pixels ---------------------
X0, Y0 = 1000, 1150                      # working crop origin
LEFT = [(1352,1330),(1322,1400),(1300,1470),(1279,1560),(1258,1650),(1242,1750),
        (1230,1860),(1218,1960),(1203,2060),(1189,2160),(1185,2260),(1196,2360),
        (1216,2455),(1250,2555),(1300,2655),(1374,2752),(1462,2830),(1560,2900),
        (1636,2975),(1678,3040),(1692,3110),(1686,3190),(1680,3255)]
RIGHT= [(2192,1330),(2232,1400),(2258,1470),(2278,1560),(2298,1650),(2318,1750),
        (2330,1860),(2342,1960),(2345,2060),(2350,2160),(2347,2260),(2336,2360),
        (2316,2455),(2282,2555),(2238,2655),(2154,2752),(2062,2830),(1966,2900),
        (1888,2975),(1846,3040),(1832,3110),(1828,3190),(1824,3255)]
RIM_CX, RIM_CY, RIM_RY = 1772, 1336, 106
LIQ_TOP, LIQ_BOT = 1352, 2965            # wine surface / bottom of the bowl
W_OUT = 620                              # exported width
SS = 2                                   # supersample for a clean edge


def catmull(P, n=14):
    P = [P[0]] + list(P) + [P[-1]]
    out = []
    for i in range(len(P) - 3):
        p0, p1, p2, p3 = P[i], P[i+1], P[i+2], P[i+3]
        for j in range(n):
            t = j / n; t2, t3 = t*t, t*t*t
            out.append((
                0.5*((2*p1[0]) + (-p0[0]+p2[0])*t + (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2
                     + (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3),
                0.5*((2*p1[1]) + (-p0[1]+p2[1])*t + (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2
                     + (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)))
    out.append(P[-1]); return out


def main():
    sharp = Image.open(SRC).crop((X0, Y0, 2600, 3450))
    rx = (RIGHT[0][0] - LEFT[0][0]) / 2

    def raster(poly, blur):
        m = Image.new('L', (sharp.width*SS, sharp.height*SS), 0)
        ImageDraw.Draw(m).polygon([((x-X0)*SS, (y-Y0)*SS) for x, y in poly], fill=255)
        return m.resize(sharp.size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur))

    top  = [(RIM_CX + rx*math.cos(math.pi*t/72), RIM_CY - RIM_RY*math.sin(math.pi*t/72))
            for t in range(73)]
    alpha = raster(top + catmull(LEFT) + catmull(RIGHT)[::-1], 1.2)

    # the liquid body, inset from the silhouette so the glass walls stay real
    inner = [(RIM_CX + (rx-34)*math.cos(math.pi*t/72), 1372 - 30*math.sin(math.pi*t/72))
             for t in range(73)]
    imask = raster(inner
                   + catmull([(x+34, y) for x, y in LEFT  if LIQ_TOP <= y <= 2990])
                   + catmull([(x-34, y) for x, y in RIGHT if LIQ_TOP <= y <= 2990])[::-1], 26)

    a   = np.asarray(sharp).astype(np.float32)
    lum = (0.30*a[:,:,0] + 0.60*a[:,:,1] + 0.10*a[:,:,2]) / 255.0
    w   = np.asarray(imask).astype(np.float32) / 255.0

    # EMPTY: drain the colour out of the bowl, and make the flat areas
    # see-through so the page background reads through the glass. Detail
    # (the printed logo, the specular highlights) stays opaque.
    tint  = np.array([236, 233, 226], dtype=np.float32)
    drain = np.clip(tint[None,None,:] * (0.50 + 0.72*lum)[:,:,None], 0, 255)
    rgb_e = np.clip(a*(1 - (w*0.90)[:,:,None]) + drain*(w*0.90)[:,:,None], 0, 255)
    detail = np.clip(0.30 + 1.25*np.abs(lum - 0.62), 0, 1)
    a_e = np.asarray(alpha).astype(np.float32) * (1 - w) + \
          np.asarray(alpha).astype(np.float32) * w * detail

    empty = Image.fromarray(rgb_e.astype(np.uint8)).convert('RGBA')
    empty.putalpha(Image.fromarray(a_e.astype(np.uint8), 'L'))
    fullc = sharp.convert('RGBA'); fullc.putalpha(alpha)

    box = alpha.getbbox()
    empty, fullc = empty.crop(box), fullc.crop(box)
    h0 = round(empty.height * W_OUT / empty.width)
    empty = empty.resize((W_OUT, h0), Image.LANCZOS)
    fullc = fullc.resize((W_OUT, h0), Image.LANCZOS)

    # ---- draw the foot (buried in ice in the photo, so it has to be added) --
    src_y0 = Y0 + box[1]
    stem = np.asarray(fullc)[int(h0*.93):h0-3, 272:332, :3].reshape(-1, 3).mean(axis=0)
    EXTRA, H = 80, h0 + 80
    CXf, fy, frx, fry = 301, h0 + 34, 118, 27

    def add_foot(im):
        out = Image.new('RGBA', (W_OUT, H), (0,0,0,0)); out.paste(im, (0,0))
        lay = Image.new('RGBA', (W_OUT*SS*2, H*SS*2), (0,0,0,0)); d = ImageDraw.Draw(lay)
        S2 = SS*2
        c  = (int(stem[0]), int(stem[1]), int(stem[2]))
        d.polygon([(267*S2,(h0-6)*S2),(336*S2,(h0-6)*S2),((CXf+46)*S2,(fy-4)*S2),((CXf-46)*S2,(fy-4)*S2)],
                  fill=c + (150,))
        d.ellipse([(CXf-frx)*S2,(fy-fry)*S2,(CXf+frx)*S2,(fy+fry)*S2],
                  fill=(int(c[0]*.96), int(c[1]*.96), int(c[2]*.97), 168))
        d.ellipse([(CXf-frx+7)*S2,(fy-fry+5)*S2,(CXf+frx-7)*S2,(fy+fry-9)*S2],
                  fill=tuple(min(255,int(v*1.14)) for v in c) + (118,))
        d.arc([(CXf-frx)*S2,(fy-fry)*S2,(CXf+frx)*S2,(fy+fry)*S2], 200, 340, fill=(255,255,255,190), width=3*S2)
        d.arc([(CXf-frx)*S2,(fy-fry)*S2,(CXf+frx)*S2,(fy+fry)*S2],  20, 160, fill=(90,70,55,120),  width=2*S2)
        lay = lay.resize((W_OUT, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(.7))
        return Image.alpha_composite(out, lay)

    add_foot(empty).save(os.path.join(OUT, 'glass-empty.png'), optimize=True)
    add_foot(fullc).save(os.path.join(OUT, 'glass-full.png'),  optimize=True)

    # ---- the wine-surface mask --------------------------------------------
    MH, rise, cx, mrx, band = H*2, 58, 310, 312, 10
    yy = np.arange(MH)[:, None] * np.ones((1, W_OUT))
    xx = np.ones((MH, 1)) * np.arange(W_OUT)[None, :]
    bound = H - rise*np.sqrt(np.clip(1 - ((xx-cx)/mrx)**2, 0, 1))
    al = np.where(yy > bound+band, 255.0, np.where(yy > bound, 132.0, 0.0))
    m = Image.fromarray(al.astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(1.4))
    Image.merge('RGBA', [Image.new('L', (W_OUT, MH), 255)]*3 + [m]) \
         .save(os.path.join(OUT, 'wine-mask.png'), optimize=True)

    # ---- the two numbers the CSS needs ------------------------------------
    sy = (src_y0, src_y0 + round(box[3]-box[1]))
    top_px = (LIQ_TOP - sy[0]) * h0 / (box[3]-box[1])
    bot_px = (LIQ_BOT - sy[0]) * h0 / (box[3]-box[1])
    print('exported %dx%d (with foot %dx%d)' % (W_OUT, h0, W_OUT, H))
    print('mask-position empty = %.2f%%' % ((1 - bot_px/H) * 100))
    print('mask-position full  = %.2f%%' % ((1 - top_px/H) * 100))


if __name__ == '__main__':
    main()
