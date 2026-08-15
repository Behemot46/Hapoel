"""Generate the PWA icon set and the share card from the club crest.

The crest lives at app/icons/crest.png. It is the club's own mark, used here
in an unofficial fan app that says so on every screen.

Inside the app the crest never appears alone: the name sits next to it in
the top bar. Outside the app it used to, and that is the whole reason this
script draws a banner. A home-screen tile, a splash screen and a WhatsApp
preview card carry no surrounding text, so a bare crest there reads as the
club's own app. Every icon produced here therefore carries the app's name
across it, which is what a fan project's mark should look like.

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

from PIL import features, Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(HERE, "..", "app", "icons")
CREST = os.path.join(ICONS, "crest.png")

NAME = "יושב סופר את הדקות"
SUB = "מיזם אוהדים לא רשמי"
HOST = "hapoel.site"

# white, because the crest's own outer ring is near-black: on a dark tile the
# edge of the badge would disappear into the background
BG = (255, 255, 255, 255)
BLACK = (23, 9, 13, 255)
RED = (228, 0, 43, 255)
INK = (255, 246, 247, 255)
MUTED = (168, 150, 155, 255)

# How much of the space above the banner the crest fills. The maskable tile
# gets a bigger share because that whole composition is already shrunk into
# the safe zone, and shrinking it twice left the crest lost in white.
FILL = 0.74
FILL_MASKABLE = 0.92
BAND = 0.23          # share of the mark's height taken by the name banner

# Whether Hebrew comes out in the right order depends on how Pillow was
# built. With Raqm it lays the text out itself and the string is handed over
# as written; without it, Pillow draws glyphs in the order given and the
# string has to be reversed by hand. Reversing is enough for Hebrew, whose
# letters do not join, and getting this backwards is not subtle: the whole
# banner reads inside out.
FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


BIDI = features.check("raqm")


def rtl(s):
    return s if BIDI else s[::-1]


def font_path():
    for p in FONTS:
        if os.path.exists(p):
            return p
    raise SystemExit(
        "no font with Hebrew letters found. Install fonts-liberation or "
        "fonts-dejavu and run again: the banner is the point of this script.")


def fit(text, max_w, max_h):
    """The largest size at which the name still fits the banner."""
    path = font_path()
    size = max_h
    while size > 6:
        f = ImageFont.truetype(path, size)
        box = f.getbbox(text)
        if (box[2] - box[0]) <= max_w and (box[3] - box[1]) <= max_h:
            return f
        size -= 1
    return ImageFont.truetype(path, 7)


def centred(draw, text, font, cx, cy, fill):
    box = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (box[2] + box[0]) / 2, cy - (box[3] + box[1]) / 2),
              text, font=font, fill=fill)


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


def paste_fitted(tile, crest, box, fill):
    """Drop the crest into a box, scaled to `fill` of it and centred."""
    x0, y0, x1, y1 = box
    side = max(1, int(min(x1 - x0, y1 - y0) * fill))
    w, h = crest.size
    scale = side / max(w, h)
    new = (max(1, round(w * scale)), max(1, round(h * scale)))
    art = crest.resize(new, Image.LANCZOS)
    tile.paste(art, (int(x0 + (x1 - x0 - new[0]) / 2),
                     int(y0 + (y1 - y0 - new[1]) / 2)), art)


def make(crest, size, fill, inset=False):
    """A tile: the crest above, the app's name on a band across the bottom."""
    tile = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(tile)

    # a maskable icon may be cropped up to 20% on every edge, so the whole
    # composition, banner included, is drawn inside the safe zone
    m = int(size * 0.20) if inset else 0
    x0, y0, x1, y1 = m, m, size - m, size - m
    inner_h = y1 - y0

    band_h = max(10, int(inner_h * BAND))
    band_top = y1 - band_h
    rule = max(1, int(inner_h * 0.012))

    paste_fitted(tile, crest, (x0, y0, x1, band_top - rule), fill)

    if inset:
        r = max(4, int(band_h * 0.28))
        draw.rounded_rectangle([x0, band_top, x1 - 1, y1 - 1], radius=r, fill=BLACK)
        draw.rounded_rectangle([x0, band_top - rule, x1 - 1, band_top + r],
                               radius=r, fill=RED)
        draw.rectangle([x0, band_top, x1 - 1, band_top + r], fill=BLACK)
    else:
        draw.rectangle([x0, band_top - rule, x1, band_top], fill=RED)
        draw.rectangle([x0, band_top, x1, y1], fill=BLACK)

    f = fit(rtl(NAME), (x1 - x0) * 0.88, band_h * 0.56)
    centred(draw, rtl(NAME), f, (x0 + x1) / 2, band_top + band_h / 2, INK)
    return tile.convert("RGB")


def make_card(crest, w=1200, h=630):
    """The picture WhatsApp shows when the link is pasted. It used to be the
    bare 512 icon, which is exactly the case this script exists to fix."""
    card = Image.new("RGBA", (w, h), BLACK)
    draw = ImageDraw.Draw(card)

    # the crest sits on a white rounded square: its outer ring is near-black
    # and would vanish straight into this background
    plate = int(h * 0.46)
    px, py = int(w * 0.5 - plate / 2), int(h * 0.16)
    draw.rounded_rectangle([px, py, px + plate, py + plate],
                           radius=int(plate * 0.22), fill=BG)
    paste_fitted(card, crest, (px, py, px + plate, py + plate), 0.76)

    f_name = fit(rtl(NAME), w * 0.8, h * 0.13)
    centred(draw, rtl(NAME), f_name, w / 2, py + plate + int(h * 0.13), INK)

    f_sub = fit(rtl(SUB + " · " + HOST), w * 0.7, h * 0.055)
    centred(draw, rtl(SUB + " · " + HOST), f_sub, w / 2,
            py + plate + int(h * 0.235), MUTED)
    return card.convert("RGB")


def main():
    crest = load_crest()
    if crest is None:
        return 1
    print(f"crest: {crest.size[0]}x{crest.size[1]} (after trimming transparent margin)")
    print(f"banner: ״{NAME}״ using {os.path.basename(font_path())}"
          + (", bidi by raqm" if BIDI else ", reversed by hand"))
    out = [
        ("icon-192.png", 192, FILL, False),
        ("icon-512.png", 512, FILL, False),
        ("icon-512-maskable.png", 512, FILL_MASKABLE, True),
        ("apple-touch-icon.png", 180, FILL, False),
    ]
    for name, size, fill, inset in out:
        img = make(crest, size, fill, inset)
        img.save(os.path.join(ICONS, name), "PNG", optimize=True)
        print(f"  {name:<26} {size}x{size}  banner across the bottom"
              + ("  (inside the maskable safe zone)" if inset else ""))
    card = make_card(crest)
    card.save(os.path.join(ICONS, "og.png"), "PNG", optimize=True)
    print(f"  {'og.png':<26} {card.size[0]}x{card.size[1]}  the share preview card")
    return 0


if __name__ == "__main__":
    sys.exit(main())
