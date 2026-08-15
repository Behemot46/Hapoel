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
HEAD_TO_CROP = 1.6     # crop side as a multiple of head width
HEADROOM = 0.12        # air above the head, as a fraction of the crop side

# The head ends up filling 1/HEAD_TO_CROP of the frame, so 1.6 puts it at just
# over 60% — the face filling most of the circle, which is the point.
# This only holds because find_head measures the head at its widest. It used to
# measure a fixed band at the top of the silhouette, which reads hair rather
# than head: one player came out at 32% of his canvas and another at 14%, and
# the clamps below then quietly decided both crops instead of this constant.


def _background(px, w, h):
    """Average the corners — but weight the top ones, and use a median so one
    dirty corner cannot drag the answer. In a head-and-shoulders cut-out the
    shoulders often reach the bottom edge, and averaging all four corners then
    returns a blend of background and jersey, against which nothing reads as
    foreground. The top corners are empty by definition here: an image whose
    top row is already full of subject is rejected as not a cut-out."""
    cs = [px[x, y] for x in (0, 1, 2, w - 3, w - 2, w - 1)
          for y in (0, 1, 2)]
    return tuple(sorted(c[i] for c in cs)[len(cs) // 2] for i in range(3))


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

    # The head is the widest the silhouette gets before the neck pinches in.
    # Measuring a fixed band at the very top instead reads whatever the hair
    # happens to be doing up there: voluminous curls span the true head width
    # straight away, a flat-top fade spans a third of it, and the same player
    # would be framed differently for having different hair.
    widest, widest_at, run = 0, top, 0
    for y in range(top, min(h, top + int(h * 0.6))):
        xs = [x for x in range(w) if fg(x, y)]
        if not xs:
            continue
        wide = xs[-1] - xs[0]
        if wide > widest:
            widest, widest_at, run = wide, y, 0
        elif wide < widest * 0.9:
            # narrowing: the neck. A few stray rows are noise, a run is real,
            # and past it the shoulders would only widen again.
            run += 1
            if run >= 4:
                break
        else:
            run = 0
    if not widest:
        return None
    xs = [x for x in range(w) if fg(x, widest_at)]
    return (xs[0] + xs[-1]) // 2, top, widest


def crop_to_face(im, size=320, skip_square=True):
    """Square crop centred on the head. Returns the image unchanged when the
    head cannot be located, and by default skips images that are already
    square — so running this twice over stored files does not crop twice.

    Pass skip_square=False for bytes just pulled off the network: some sources
    publish the cut-out on a square canvas, and there the head still sits high
    with empty space below it. Nothing has been cropped yet, so there is no
    double-crop to guard against."""
    w, h = im.size
    if w == h and skip_square:
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
    # backstops only, for when the head reading is nonsense — the head rule
    # above is what should decide the crop. The ceiling used to be 0.62h,
    # tight enough that it, not the head, framed most pictures.
    side = max(int(h * 0.34), min(side, int(h * 0.85), w, h))
    y0 = max(0, int(top - side * HEADROOM))
    y0 = min(y0, h - side)
    x0 = min(max(0, cx - side // 2), w - side)
    return im.crop((x0, y0, x0 + side, y0 + side)).resize((size, size))
