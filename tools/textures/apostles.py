"""Apostle icons of the iconostasis top row -> textures/icons/apostle_01..12.jpg (left to right).

Each panel: rectified from the best photo to a fixed 0.79 aspect, black outside the round arch, name
plate kept. The red lamp hanging in front is removed: where a second photo from another angle shows the
paint behind it, that photo is registered and used; the rest is inpainted (OpenCV Telea).
usage: apostles.py [n ...] [--raw]   (--raw: skip lamp removal, for tuning quads)
"""
import sys, os
import cv2
import numpy as np
import lib
import icons

B3 = "batch3/"
ASPECT = 0.79
H_OUT = 1024
# n: (name, [(photo, quad TL TR BR BL), ...])  first = base, others = fill candidates (quad optional)
AP = {
    1: ("name plate not legible (panel is hidden behind the bishop's throne canopy in today's photos)",
        [("icons/20070525_191312_017.jpg", [(88, 353), (155, 353), (155, 439), (88, 439)])]),
    2: ("Philip", [("IMG_4812.jpg", [(1705, 1585), (2650, 1585), (2660, 2545), (1680, 2545)])]),
    3: ("Simon", [("IMG_4812.jpg", [(3185, 1595), (4230, 1595), (4280, 2585), (3160, 2585)]),
                  ("IMG_4813.jpg", None)]),
    4: ("Bartholomew", [("IMG_4814.jpg", [(1345, 1595), (1915, 1665), (1970, 2575), (1315, 2440)]),
                        ("IMG_4813.jpg", None)]),
    5: ("James son of Alphaeus", [("IMG_4814.jpg", [(2262, 2010), (2665, 2125), (2790, 2935), (2310, 2790)])]),
    6: ("John", [("IMG_7899.jpg", [(478, 1452), (905, 1452), (905, 1992), (478, 1992)])]),
    7: ("Peter", [(B3 + "IMG_7963.jpg", [(2345, 470), (3400, 500), (3440, 2060), (2305, 2150)]),
                  ("IMG_7899.jpg", None)]),
    8: ("Andrew", [(B3 + "IMG_7958.jpg", [(1985, 590), (3370, 590), (3385, 2270), (1975, 2270)]),
                   (B3 + "IMG_7962.jpg", None)]),
    9: ("Thomas", [(B3 + "IMG_7962.jpg", [(2120, 480), (3540, 480), (3600, 2120), (2090, 2180)]),
                   (B3 + "IMG_7959.jpg", None)]),
    10: ("Matthew", [(B3 + "IMG_7959.jpg", [(2145, 680), (3600, 680), (3615, 2440), (2135, 2440)]),
                     (B3 + "IMG_7960.jpg", None)]),
    11: ("James son of Zebedee", [(B3 + "IMG_7961.jpg", [(60, 845), (1320, 935), (1335, 2420), (45, 2330)]),
                                  (B3 + "IMG_7960.jpg", None)]),
    12: ("Matthias", [(B3 + "IMG_7961.jpg", [(1965, 1030), (2995, 1130), (3150, 2610), (2040, 2500)])]),
}
QUALITY = {1: "low", 2: "ok", 3: "ok", 4: "low", 5: "low", 6: "ok", 7: "ok", 8: "ok", 9: "ok", 10: "ok", 11: "ok", 12: "ok"}
REFINE = {}      # n -> tuple of sides to snap; default left/right/bottom
ADJ = {}         # n -> (l, t, r, b) trims in output px
_cache = {}
CHAINS = True
NO_CHAINS = tuple(range(1, 13))   # chains cross the face at an angle here: removing them smears the face, left in


def smooth_fill(im, mask):
    """fill mask by diffusion from the surrounding paint (push-pull); soft, no streaks."""
    f = im.astype(np.float32)
    k = (mask == 0).astype(np.float32)
    out = f.copy()
    todo = mask > 0
    for sig in (3, 6, 12, 24, 48, 96):
        num = cv2.GaussianBlur(f * k[..., None], (0, 0), sig)
        den = cv2.GaussianBlur(k, (0, 0), sig)
        ok = todo & (den > 0.08)
        out[ok] = (num / (den[..., None] + 1e-6))[ok]
        todo = todo & ~ok
    if todo.any():
        out[todo] = (num / (den[..., None] + 1e-6))[todo]
    a = cv2.GaussianBlur((mask > 0).astype(np.float32), (0, 0), 2.0)[..., None]
    return np.clip(f * (1 - a) + out * a + 0.5, 0, 255).astype(np.uint8)



def photo(p):
    if p not in _cache:
        _cache[p] = lib.load(p)
    return _cache[p]


def lamp_mask(im):
    """red glass lamp + its brass basket, and the thin chains above it."""
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    hh, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    redh = (hh < 8) | (hh > 170)
    loose = cv2.morphologyEx((redh & (s > 150) & (v > 100)).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    strict = redh & (s > 185) & (v > 135)
    n, lab, st, _ = cv2.connectedComponentsWithStats(loose)
    m = np.zeros(im.shape[:2], np.uint8)
    if n < 2:
        return m, None
    h, w = m.shape
    score = [(strict & (lab == i)).sum() + 0.01 * st[i, cv2.CC_STAT_AREA] for i in range(1, n)]
    big = 1 + int(np.argmax(score))
    if st[big, cv2.CC_STAT_AREA] < 0.002 * h * w:
        return m, None
    x, y, bw, bh = st[big, :4]
    if bw > 0.17 * w:                      # glow merged in: keep the part around the bright glass
        xs = np.where(strict & (lab == big))[1]
        cx = np.median(xs) if len(xs) else x + bw / 2
        x, bw = int(cx - 0.085 * w), int(0.17 * w)
    bw = max(bw, int(0.10 * w))
    y0, y1 = max(0, y - int(0.15 * bw)), min(h, y + int(3.9 * bw))
    x0, x1 = max(0, x - int(0.35 * bw)), min(w, x + bw + int(0.35 * bw))
    y0, y1 = max(0, y - int(0.15 * bw)), min(h, y + int(3.3 * bw))
    m[y0:y1, x0:x1] = 255
    body = m.copy()
    # chains: thin near-vertical bright/dark lines in the column above the lamp
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(7, w // 60) | 1, 1))
    th = np.maximum(cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k), cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k))
    ch = (th > 30).astype(np.uint8)
    ch = cv2.morphologyEx(ch, cv2.MORPH_OPEN, np.ones((25, 1), np.uint8))      # keep vertical runs
    band = np.zeros_like(ch)
    cx0, cx1 = max(0, x - int(0.6 * bw)), min(w, x + bw + int(0.6 * bw))
    band[:y0 + 4, cx0:cx1] = 1
    ch = cv2.dilate(ch & band, np.ones((3, 3), np.uint8))
    if CHAINS:
        m[ch > 0] = 255
    return m, (x0, y0, x1, y1)


def arch(im):
    h, w = im.shape[:2]
    sp = w / 2.0
    yy, xx = np.mgrid[0:h, 0:w]
    inside = (((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - sp) / sp) ** 2 <= 1) | (yy >= sp)
    a = cv2.GaussianBlur(inside.astype(np.float32), (0, 0), 1.0)[..., None]
    return (im * a + 0.5).astype(np.uint8)


def build(n, raw=False):
    name, srcs = AP[n]
    p0, q0 = srcs[0]
    im = photo(p0)
    sides = REFINE.get(n, ())
    q = icons.refine_quad(im, q0, sides=sides, band=0.04) if sides else q0
    ow = int(round(H_OUT * ASPECT))
    big = lib.warp(im, q, ow, H_OUT)
    l, t, r, b = ADJ.get(n, (0, 0, 0, 0))
    if any((l, t, r, b)):
        big = cv2.resize(big[t:H_OUT - b, l:ow - r], (ow, H_OUT), interpolation=cv2.INTER_CUBIC)
    if p0.startswith("icons/2007"):
        big = icons.fix2007(big)
    used, how = [p0], "lamp left in"
    global CHAINS
    CHAINS = n not in NO_CHAINS
    if not raw:
        m, box = lamp_mask(big)
        if box is not None:
            rest = m.copy()
            for p1, _ in srcs[1:]:
                o = photo(p1)
                Hm, inl = icons.register(o, big, min_inliers=30, scale_to=2600)
                if Hm is None:
                    print("  ", n, "no registration with", p1, inl)
                    continue
                O, valid = icons.warp_to(o, Hm, (ow, H_OUT))
                mo, _ = lamp_mask(O)
                ok = (valid > 0) & (cv2.dilate(mo, np.ones((9, 9), np.uint8)) == 0)
                fill = ((rest > 0) & ok).astype(np.float32)
                if fill.sum() < 50:
                    continue
                fill = cv2.GaussianBlur(cv2.dilate(fill, np.ones((5, 5), np.uint8)) * ok, (0, 0), 1.5)
                big = icons.fill_from(big, O, np.clip(fill, 0, 1), sigma=18)
                rest[fill > 0.5] = 0
                used.append(p1)
                print("  ", n, "filled from", p1, "inliers", inl, "left", int((rest > 0).sum()))
            if (rest > 0).any():
                n_, lab_, st_, _ = cv2.connectedComponentsWithStats(rest)
                thin = np.zeros_like(rest)
                for i in range(1, n_):
                    if st_[i, cv2.CC_STAT_WIDTH] < 0.035 * ow:
                        thin[lab_ == i] = 255
                if thin.any():
                    big = cv2.inpaint(big, thin, 3, cv2.INPAINT_TELEA)
                blob = cv2.dilate(rest & ~thin, np.ones((7, 7), np.uint8))
                if blob.any():
                    big = smooth_fill(big, blob)
            how = ("lamp removed: " + ("paint behind it taken from " + ", ".join(os.path.basename(u) for u in used[1:]) + "; "
                                      if len(used) > 1 else "") +
                   ("remaining area behind the lamp filled smoothly from the surrounding paint (blurred patch: hide it behind the 3D lamp)" if (rest > 0).any() else "no inpainting needed"))
    out = arch(big)
    note = f"{name}; top row position {n} from the left; {how}" + ("; lamp chains left in (they cross the face; removing them smeared it)" if n > 1 else "; small 2007 lamp left in")
    return out, " + ".join("reference/" + u for u in used), QUALITY[n], note


if __name__ == "__main__":
    args = sys.argv[1:]
    raw = "--raw" in args
    args = [a for a in args if a != "--raw"]
    ns = [int(a) for a in args] or list(AP)
    entries = []
    for n in ns:
        out, src, q, note = build(n, raw)
        rel = f"icons/apostle_{n:02d}.jpg"
        lib.save(rel, out)
        entries.append(lib.entry(rel, out, src, q, note))
        print(n, out.shape[1], out.shape[0], q, note[:110])
    if not args and not raw:
        lib.write_part("apostles", entries)
