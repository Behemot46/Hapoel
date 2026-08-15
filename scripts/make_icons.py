"""Generate the PWA icon set from the club crest.

The crest lives at app/icons/crest.png. It is the club's own mark, used here
in an unofficial fan app that says so on every screen.

The source is 160x160, the largest that could be found; the club's own
favicon is 48x48 and there is no public vector. So the icons are built to
keep it as sharp as the source allows: the 192 is drawn at close to native
size, and the 512 is upscaled with LANCZOS, which is soft at full size but
is displayed far smaller than that in practice (Android uses the 192 on the
home screen; the 512 is for splash and listings).

If crest.png is missing the script says so and leaves the icons alone,
rather than silently shipping a blank badge.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(HERE, "..", "app", "icons")
CREST = os.path.join(ICONS, "crest.png")

# white, because the crest's own outer ring is near-black: on a dark tile the
# edge of the badge would disappear into the background
BG = (255, 255, 255, 255)

# how much of the tile the crest fills. A maskable icon can have up to 20%
# trimmed off each edge, so the mark stays inside the safe zone.
FILL = 0.78
FILL_MASKABLE = 0.62


def load_crest():
    if not os.path.exists(CREST):
        print(f"no crest at {CREST}, icons left untouched.")
        print("Drop the club crest there as a square PNG and run this again.")
        return None
    im = Image.open(CREST).convert("RGBA")
    # trim any transparent margin so 'fill' means the mark, not the padding
    box = im.split()[-1].getbbox()
    if box:
        im = im.crop(box)
    return im


def make(crest, size, fill, bg=BG):
    tile = Image.new("RGBA", (size, size), bg)
    side = max(1, int(size * fill))
    # keep the aspect ratio; the crest is square but do not assume it
    w, h = crest.size
    scale = side / max(w, h)
    new = (max(1, round(w * scale)), max(1, round(h * scale)))
    art = crest.resize(new, Image.LANCZOS)
    tile.paste(art, ((size - new[0]) // 2, (size - new[1]) // 2), art)
    return tile.convert("RGB")


def main():
    crest = load_crest()
    if crest is None:
        return 1
    print(f"crest: {crest.size[0]}x{crest.size[1]} (after trimming transparent margin)")
    out = [
        ("icon-192.png", 192, FILL),
        ("icon-512.png", 512, FILL),
        ("icon-512-maskable.png", 512, FILL_MASKABLE),
        ("apple-touch-icon.png", 180, FILL),
    ]
    for name, size, fill in out:
        img = make(crest, size, fill)
        path = os.path.join(ICONS, name)
        img.save(path, "PNG", optimize=True)
        upscale = (size * fill) / max(crest.size)
        note = "native or down" if upscale <= 1.05 else f"{upscale:.1f}x upscale"
        print(f"  {name:<26} {size}x{size}  crest at {int(size*fill)}px  ({note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
