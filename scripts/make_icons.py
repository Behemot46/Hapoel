"""Generate the PWA icon set: the lion-and-ball mark in club colours.

The club's own crest is its trademark and is not reproduced here — this is an
original mark drawn for the project, echoing the mascot and the lion of
Jerusalem. To use the real crest, replace these files by hand.
"""
from PIL import Image, ImageDraw
import os

OUT = os.path.join(os.path.dirname(__file__), "..", "app", "icons")
RED = (228, 0, 43, 255)
DARK = (23, 9, 13, 255)
WHITE = (255, 255, 255, 255)

def make(size):
    s = 4  # supersample for smooth edges
    W = size * s
    img = Image.new("RGBA", (W, W), RED)
    d = ImageDraw.Draw(img)

    # subtle dark corner stripe for kit identity
    d.polygon([(0, 0), (int(W * 0.28), 0), (0, int(W * 0.28))], fill=DARK)

    # basketball
    m = int(W * 0.20)
    lw = max(s * 2, int(W * 0.035))
    box = [m, m, W - m, W - m]
    d.ellipse(box, outline=WHITE, width=lw)
    cx = W // 2
    d.line([(cx, m), (cx, W - m)], fill=WHITE, width=lw)
    d.line([(m, cx), (W - m, cx)], fill=WHITE, width=lw)

    # side seams: big circles left/right of the ball, clipped to the ball interior
    r = (W - 2 * m) // 2
    seams = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ds = ImageDraw.Draw(seams)
    R = int(r * 1.5)
    for scx in (cx - int(r * 1.9), cx + int(r * 1.9)):
        ds.ellipse([scx - R, cx - R, scx + R, cx + R], outline=WHITE, width=lw)
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).ellipse([m + lw // 2, m + lw // 2, W - m - lw // 2, W - m - lw // 2], fill=255)
    img.paste(seams, (0, 0), Image.composite(seams.split()[3], Image.new("L", (W, W), 0), mask))

    # the lion: a maned head over the ball, matching the wordmark emblem
    import math
    lion = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lion)
    face_r = int(W * 0.135)
    mane_out, mane_in = int(W * 0.235), int(W * 0.168)
    pts = []
    for i in range(14):
        a = math.pi * 2 * i / 14 - math.pi / 2
        rr = mane_out if i % 2 == 0 else mane_in
        pts.append((cx + rr * math.cos(a), cx - int(W * 0.020) + rr * math.sin(a)))
    dl.polygon(pts, fill=WHITE)
    fy = cx - int(W * 0.020)
    dl.ellipse([cx - face_r, fy - face_r, cx + face_r, fy + face_r], fill=WHITE)
    # eyes and muzzle, cut in the club's black
    ew = int(W * 0.026)
    for ex in (cx - int(W * 0.052), cx + int(W * 0.052)):
        dl.polygon([(ex - ew, fy - int(W * 0.032)), (ex + ew, fy - int(W * 0.032)),
                    (ex, fy - int(W * 0.002))], fill=DARK)
    mw, my = int(W * 0.038), fy + int(W * 0.030)
    dl.polygon([(cx - mw, my), (cx + mw, my), (cx, my + int(W * 0.042))], fill=DARK)
    img.alpha_composite(lion)

    return img.resize((size, size), Image.LANCZOS)

os.makedirs(OUT, exist_ok=True)
for name, size in [("icon-512.png", 512), ("icon-192.png", 192), ("apple-touch-icon.png", 180)]:
    make(size).convert("RGB").save(os.path.join(OUT, name))
    print("wrote", name)
