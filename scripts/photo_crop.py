"""Crop a squad headshot down to the head.

The competition publishes waist-up cut-outs on a flat background, 3:4. Shown
in a round frame with object-fit:cover that centres on the chest and leaves
the face small and high. Cropping at download time is better than scaling in
CSS: the stored pixels are the ones actually displayed.

No face detector needed. The subject is a cut-out on a flat background, so
the top of the silhouette *is* the top of the head, and the widest part of
that top band is the head. Measured across the squad the framing is
consistent to within a couple of percent, which is what makes this safe.
"""

BG_TOLERANCE = 60      # colour distance that counts as "not background"
HEAD_TO_CROP = 2.5     # crop side as a multiple of head width
HEADROOM = 0.12        # air above the head, as a fraction of the crop side


def _background(px, w, h):
    cs = [px[x, y] for x in (0, 1, 2, w - 3, w - 2, w - 1)
          for y in (0, 1, 2, h - 3, h - 2, h - 1)]
    return tuple(sum(c[i] for c in cs) // len(cs) for i in range(3))


def find_head(im):
    """(centre_x, top_y, head_width) in pixels, or None if the image is not a
    cut-out we can read — a busy photo would give nonsense, so say so."""
    im = im.convert("RGB")
    w, h = im.size
    px = im.load()
    bg = _background(px, w, h)

    def fg(x, y):
        p = px[x, y]
        return abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > BG_TOLERANCE

    # a real cut-out has a mostly-empty top row; if the very first row is
    # already full of subject, this is a normal photo and we should not guess
    if sum(1 for x in range(0, w, 2) if fg(x, 0)) > w * 0.25:
        return None

    top = None
    for y in range(h):
        if sum(1 for x in range(0, w, 2) if fg(x, y)) > w * 0.01:
            top = y
            break
    if top is None or top > h * 0.35:
        return None

    band = range(top, min(h, top + int(h * 0.16)))
    xs = [x for x in range(w) if any(fg(x, y) for y in band)]
    if not xs:
        return None
    return (xs[0] + xs[-1]) // 2, top, xs[-1] - xs[0]


def crop_to_face(im, size=320):
    """Square crop centred on the head. Returns the image unchanged when the
    head cannot be located, and skips images that are already square — so
    running this twice does not crop twice."""
    w, h = im.size
    if w == h:
        return im
    found = find_head(im)
    if not found:
        # fall back to the top-centre square, which is still better than the
        # middle for a standing portrait
        side = min(w, h)
        left = max(0, (w - side) // 2)
        return im.crop((left, 0, left + side, side)).resize((size, size))

    cx, top, head_w = found
    side = int(head_w * HEAD_TO_CROP)
    side = max(int(h * 0.34), min(side, int(h * 0.62), w, h))
    y0 = max(0, int(top - side * HEADROOM))
    y0 = min(y0, h - side)
    x0 = min(max(0, cx - side // 2), w - side)
    return im.crop((x0, y0, x0 + side, y0 + side)).resize((size, size))
