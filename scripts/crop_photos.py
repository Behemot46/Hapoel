"""Normalise player photos that were added by hand.

Photos downloaded by the updater are already cropped to the head. A file
dropped into app/img/players/ manually is not, so run this once after adding
one:

    python scripts/crop_photos.py

It only touches images that are not already square, so running it twice is
harmless. For a cut-out on a flat background it finds the head; for an
ordinary photo it says so and leaves the file alone rather than guessing and
cutting somebody's face in half.
"""
import pathlib
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from photo_crop import crop_to_face, find_head  # noqa: E402

PHOTO_DIR = pathlib.Path(__file__).resolve().parent.parent / "app" / "img" / "players"


def main():
    files = sorted(PHOTO_DIR.glob("*.jpg")) + sorted(PHOTO_DIR.glob("*.png"))
    if not files:
        print("no photos in", PHOTO_DIR)
        return 0
    for f in files:
        im = Image.open(f).convert("RGB")
        w, h = im.size
        if w == h:
            print(f"  {f.name}: already square ({w}x{h}), left alone")
            continue
        head = find_head(im)
        if not head:
            print(f"  {f.name}: not a cut-out on a flat background, crop it by "
                  f"hand to a square around the face, then re-run")
            continue
        out = crop_to_face(im)
        out.save(f, "JPEG", quality=85, optimize=True)
        print(f"  {f.name}: {w}x{h} -> {out.size[0]}x{out.size[1]} (head at {head})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
