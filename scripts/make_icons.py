"""Generate the PWA icon set: a white basketball on Hapoel red."""
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

    return img.resize((size, size), Image.LANCZOS)

os.makedirs(OUT, exist_ok=True)
for name, size in [("icon-512.png", 512), ("icon-192.png", 192), ("apple-touch-icon.png", 180)]:
    make(size).convert("RGB").save(os.path.join(OUT, name))
    print("wrote", name)
