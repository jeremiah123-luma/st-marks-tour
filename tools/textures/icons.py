"""Icons -> textures/icons/<name>.jpg

usage: icons.py                 build everything, write manifest part
       icons.py name [name...]  build some
       icons.py --preview DIR name [...]   write DIR/pv_<name>.jpg: the rectified panel with a 6 %
                                           margin and the crop boundary drawn in green, for tuning.

Quads are TL, TR, BR, BL in EXIF-oriented source pixels. `adj` = (left, top, right, bottom) pixels
(in nominal output pixels) to move each edge inward (+) or outward (-) after rectification.
"""
import sys, os, json
import cv2
import numpy as np
import lib

MAXS = 1536
I7 = "icons/20070525_"
B3 = "batch3/"

# ----------------------------------------------------------------------------- colour helpers


def lab_stats(im, mask=None):
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    px = lab[mask > 0] if mask is not None else lab.reshape(-1, 3)
    return px.mean(axis=0), px.std(axis=0) + 1e-3


def lab_transfer(im, src_stats, dst_stats, strength=1.0, max_scale=1.6):
    """Reinhard colour transfer: move mean/std of each Lab channel from src_stats to dst_stats."""
    (ms, ss), (md, sd) = src_stats, dst_stats
    lab = cv2.cvtColor(im, cv2.COLOR_BGR2LAB).astype(np.float32)
    sc = np.clip(sd / ss, 1 / max_scale, max_scale)
    out = (lab - ms) * sc + md
    out = lab + (out - lab) * strength
    return cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def register(src, dst, min_inliers=25, scale_to=1400):
    """Homography mapping src pixels -> dst pixels (SIFT + RANSAC). Returns (H, inliers)."""
    def prep(im):
        s = min(1.0, scale_to / max(im.shape[:2]))
        g = cv2.cvtColor(cv2.resize(im, None, fx=s, fy=s, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        g = cv2.createCLAHE(2.0, (8, 8)).apply(g)
        return g, s
    a, sa = prep(src)
    b, sb = prep(dst)
    sift = cv2.SIFT_create(8000, contrastThreshold=0.02)
    ka, da = sift.detectAndCompute(a, None)
    kb, db = sift.detectAndCompute(b, None)
    m = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [x for x, y in m if x.distance < 0.75 * y.distance]
    if len(good) < min_inliers:
        return None, len(good)
    pa = np.float32([ka[g.queryIdx].pt for g in good]) / sa
    pb = np.float32([kb[g.trainIdx].pt for g in good]) / sb
    H, inl = cv2.findHomography(pa, pb, cv2.RANSAC, 4.0 / min(sa, sb))
    n = int(inl.sum()) if inl is not None else 0
    return (H if n >= min_inliers else None), n


def warp_to(src, H, size, with_mask=True):
    w, h = size
    out = cv2.warpPerspective(src, H, (w, h), flags=cv2.INTER_AREA if False else cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_CONSTANT)
    mask = cv2.warpPerspective(np.full(src.shape[:2], 255, np.uint8), H, (w, h), flags=cv2.INTER_NEAREST)
    return out, mask


def expand_quad(quad, m):
    """grow a quad by fraction m of its size on every side (projectively correct)."""
    q = np.float32(quad)
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]), q)
    pts = np.float32([[-m, -m], [1 + m, -m], [1 + m, 1 + m], [-m, 1 + m]]).reshape(-1, 1, 2)
    return cv2.perspectiveTransform(pts, M).reshape(4, 2)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def rectify_adj(im, quad, adj=(0, 0, 0, 0), max_side=MAXS, aspect=None, preview=False):
    """Rectify quad; apply adj; return final image (or preview with margin + boundary)."""
    w, h = lib.quad_size(quad)
    if aspect:
        w = h * aspect
    ow, oh = lib.fit_size(w, h, max_side=max_side)
    m = 0.06
    big = lib.warp(im, expand_quad(quad, m), int(round(ow * (1 + 2 * m))), int(round(oh * (1 + 2 * m))))
    ox, oy = int(round(ow * m)), int(round(oh * m))
    l, t, r, b = adj
    x0, y0, x1, y1 = ox + l, oy + t, ox + ow - r, oy + oh - b
    if preview:
        pv = big.copy()
        cv2.rectangle(pv, (x0, y0), (x1 - 1, y1 - 1), (0, 255, 0), 1)
        for k in range(0, pv.shape[1], 100):
            cv2.putText(pv, str(k - ox), (k, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
            cv2.line(pv, (k, 14), (k, 22), (255, 255, 0), 1)
        for k in range(0, pv.shape[0], 100):
            cv2.putText(pv, str(k - oy), (2, k + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
        return pv
    return big[y0:y1, x0:x1].copy()


def refine_quad(im, quad, m=0.06, band=0.045, spans=None, inner=0.5, debug=None, max_tilt=0.07, passes=2, outer=(), sides=("left", "right", "top", "bottom")):
    """Snap a roughly picked quad to the long straight frame/painting junction on each side.
    For every side: search +-band around the nominal edge (and small tilts) for straight lines with a
    strong gradient along most of their length, and take the innermost strong one.
    spans = {side: (a, b)} fraction of the side length to look at (to avoid flowers etc)."""
    if passes > 1:
        quad = refine_quad(im, quad, m, band, spans, inner, None, max_tilt, passes - 1, outer, sides)
        max_tilt, band = 0.02, band * 0.6
    spans = spans or {}
    w0, h0 = lib.quad_size(quad)
    s = 1100 / max(w0, h0)
    W, H = int(w0 * s), int(h0 * s)
    eq = expand_quad(quad, m)
    BW, BH = int(round(W * (1 + 2 * m))), int(round(H * (1 + 2 * m)))
    big = lib.warp(im, eq, BW, BH)
    ox, oy = int(round(W * m)), int(round(H * m))
    lab = cv2.cvtColor(cv2.GaussianBlur(big, (0, 0), 1.0), cv2.COLOR_BGR2LAB).astype(np.float32)
    gx = np.abs(cv2.Sobel(lab, cv2.CV_32F, 1, 0, ksize=3)).sum(axis=2)
    gy = np.abs(cv2.Sobel(lab, cv2.CV_32F, 0, 1, ksize=3)).sum(axis=2)
    lines = {}
    for side in ("left", "right", "top", "bottom"):
        vert = side in ("left", "right")
        g = gx if vert else gy.T          # now the edge runs along axis 0 (index t), offset along axis 1
        L, Wd = (BH, BW) if vert else (BW, BH)
        o0 = (ox if side == "left" else ox + W) if vert else (oy if side == "top" else oy + H)
        if side not in sides:
            lines[side] = (o0, 0.0, 0.0)
            continue
        t_off, t_len = (oy, H) if vert else (ox, W)
        a0, a1 = spans.get(side, (0.12, 0.88))
        ts = np.arange(int(t_off + a0 * t_len), int(t_off + a1 * t_len))
        bw = int(band * max(W, H))
        best = []
        for tilt in np.linspace(-max_tilt, max_tilt, int(max_tilt * 800) | 1):
            offs = np.arange(o0 - bw, o0 + bw + 1)
            xs = offs[None, :] + np.round(tilt * (ts[:, None] - ts.mean())).astype(int)
            xs = np.clip(xs, 0, Wd - 1)
            prof = np.percentile(g[ts[:, None], xs], 40, axis=0)
            for o, v in zip(offs, prof):
                best.append((v, o, tilt))
        best = np.array(best)
        vmax = best[:, 0].max()
        strong = best[best[:, 0] >= inner * vmax]
        # innermost = largest offset for left/top, smallest for right/bottom; among near-equal offsets best score
        sign = 1 if side in ("left", "top") else -1
        if side in outer:      # take the outermost strong line instead (e.g. a shadow edge lies inside)
            sign = -sign
        o_in = (strong[:, 1] * sign).max() * sign
        cand = strong[np.abs(strong[:, 1] - o_in) <= 2]
        v, o, tilt = cand[np.argmax(cand[:, 0])]
        lines[side] = (o, tilt, ts.mean())
    def pt(vs, hs):
        # vertical line: x = o + tilt*(y - c); horizontal: y = o + tilt*(x - c)
        (ov, tv, cv_), (oh, th, ch) = lines[vs], lines[hs]
        y = (oh + th * (ov - tv * cv_ - ch)) / (1 - th * tv)
        x = ov + tv * (y - cv_)
        return [x, y]
    pv = np.float32([pt("left", "top"), pt("right", "top"), pt("right", "bottom"), pt("left", "bottom")])
    M = cv2.getPerspectiveTransform(np.float32([[0, 0], [BW, 0], [BW, BH], [0, BH]]), np.float32(eq))
    out = cv2.perspectiveTransform(pv.reshape(-1, 1, 2), M).reshape(4, 2)
    if debug:
        d = big.copy()
        cv2.polylines(d, [pv.astype(np.int32)], True, (0, 255, 0), 1)
        cv2.imwrite(debug, d)
    return out


# ----------------------------------------------------------------------------- 2007 colour profile
# The 2007 photos (tungsten, strong orange cast) are mapped to the colour of the same icons as they
# look today (IMG_4802/4803/4805, Nov 2026), using one common transform so all icons stay consistent.

_PROFILE = None
PROFILE_PAIRS = [("184521_003", "IMG_4802.jpg"), ("184556_004", "IMG_4803.jpg"), ("184748_005", "IMG_4805.jpg")]
PROFILE_CACHE = os.path.join(os.path.dirname(__file__), "_profile2007.json")


def profile2007():
    global _PROFILE
    if _PROFILE is not None:
        return _PROFILE
    if os.path.exists(PROFILE_CACHE):
        d = json.load(open(PROFILE_CACHE))
        _PROFILE = tuple((np.float32(a), np.float32(b)) for a, b in d)
        return _PROFILE
    S, D = [], []
    for old, new in PROFILE_PAIRS:
        o = lib.load(f"{I7}{old}.jpg")
        n = lib.load(new)
        H, inl = register(n, o)
        print("profile pair", old, new, "inliers", inl)
        if H is None:
            continue
        nw, mask = warp_to(n, H, (o.shape[1], o.shape[0]))
        mask = cv2.erode(mask, np.ones((41, 41), np.uint8))
        mask[: int(o.shape[0] * 0.12)] = 0   # wood arch
        mask[int(o.shape[0] * 0.90):] = 0    # title band
        S.append(lab_stats(o, mask)); D.append(lab_stats(nw, mask))
    ms = np.mean([s[0] for s in S], axis=0); ss = np.mean([s[1] for s in S], axis=0)
    md = np.mean([s[0] for s in D], axis=0); sd = np.mean([s[1] for s in D], axis=0)
    _PROFILE = ((ms, ss), (md, sd))
    json.dump([[ms.tolist(), ss.tolist()], [md.tolist(), sd.tolist()]], open(PROFILE_CACHE, "w"))
    print("2007 profile: src", ms, ss, "dst", md, sd)
    return _PROFILE


def fix2007(im, strength=0.85):
    s, d = profile2007()
    return lab_transfer(im, s, d, strength)


# ----------------------------------------------------------------------------- shrine icons
# base = today's photo (sharper, full panel, today's colour); the 2007 photo, registered onto it,
# supplies even lighting (removes canopy shadow / lamp glare) and the strip hidden by flowers.

def shrine(spec, preview=False):
    t = lib.load(spec["src"])
    if spec.get("refine", True):
        spec = dict(spec, quad=refine_quad(t, spec["quad"], spans=spec.get("spans"), inner=spec.get("inner", 0.5), outer=spec.get("outer", ()),
                                           sides=spec.get("sides", ("left", "right", "top", "bottom")),
                                           debug=spec.get("debug")))
    if preview:
        return rectify_adj(t, spec["quad"], spec.get("adj", (0, 0, 0, 0)), preview=True), {}
    T = rectify_adj(t, spec["quad"], spec.get("adj", (0, 0, 0, 0)))
    info = {"base": "today"}
    old = spec.get("old")
    if not old:
        return T, info
    o = lib.load(old)
    H, inl = register(o, T)
    info["inliers"] = inl
    if H is None:
        info["old_used"] = False
        return T, info
    h, w = T.shape[:2]
    O, valid = warp_to(o, H, (w, h))
    valid = cv2.erode(valid, np.ones((15, 15), np.uint8))
    # colour: 2007 -> today's colour, statistics from the evenly lit middle band
    band = valid.copy()
    band[: int(h * spec.get("band", (0.22, 0.72))[0])] = 0
    band[int(h * spec.get("band", (0.22, 0.72))[1]):] = 0
    Om = lab_transfer(O, lab_stats(O, band), lab_stats(T, band), 1.0)
    # illumination transfer: low frequencies of the 2007 photo, detail of today's
    sig = max(w, h) * spec.get("sigma", 0.035)
    eps = 4.0
    Tf, Of = T.astype(np.float32) + eps, Om.astype(np.float32) + eps
    vf = (valid > 0).astype(np.float32)
    def nblur(x):
        num = cv2.GaussianBlur(x * vf[..., None], (0, 0), sig)
        den = cv2.GaussianBlur(vf, (0, 0), sig)[..., None] + 1e-4
        return num / den
    ratio = nblur(Of) / nblur(Tf)
    lum = ratio.mean(axis=2, keepdims=True)
    cs = spec.get("chroma", 0.6)       # how much of the colour (not just brightness) ratio to apply
    ratio = lum * (ratio / lum) ** cs
    ratio = np.clip(ratio, 0.55, 2.2)
    wgt = cv2.GaussianBlur(cv2.erode(valid, np.ones((int(sig) | 1, int(sig) | 1), np.uint8)).astype(np.float32) / 255,
                           (0, 0), sig / 2)[..., None] * spec.get("light", 1.0)
    out = Tf * (1 + (ratio - 1) * wgt) - eps
    # regions where today's photo is occluded (flowers) -> 2007 pixels. boxes in fractions (x0,y0,x1,y1)
    for (x0, y0, x1, y1) in spec.get("old_patch", []):
        pm = np.zeros((h, w), np.float32)
        pm[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)] = 1
        pm = cv2.GaussianBlur(pm, (0, 0), max(2, h * 0.006)) * (valid > 0)
        out = out * (1 - pm[..., None]) + Om.astype(np.float32) * pm[..., None]
    info["old_used"] = True
    return np.clip(out + 0.5, 0, 255).astype(np.uint8), info


# ----------------------------------------------------------------------------- table

LOWER = {  # 2007 close-ups, already straight-on: crop box (x0,y0,x1,y1)
    "annunciation_panel": ("184521_003", (0, 68, 922, 1921)),
    "mikhail": ("184556_004", (0, 60, 905, 1936)),
    "mark": ("184748_005", (0, 40, 885, 1920)),
    "theotokos": ("185113_002", (0, 20, 1005, 1897)),
    "christ": ("185301_001", (8, 15, 995, 1800)),
    "john_baptist": ("185423_006", (8, 0, 874, 1725)),
    "george": ("185546_007", (0, 45, 900, 1915)),
    "mina_panel": ("185625_009", (0, 25, 900, 1816)),
}

SHRINES = {
    "annunciation": dict(src=B3 + "IMG_7965.jpg", quad=[(505, 1375), (2250, 1380), (2258, 3630), (512, 3630)],
                         old=I7 + "190502_011.jpg"),
    "nativity": dict(src=B3 + "IMG_7967.jpg", quad=[(790, 1335), (2120, 1335), (2125, 3075), (795, 3075)],
                     old=I7 + "190630_013.jpg", adj=(0, 0, 0, 62)),
    "antony": dict(src=B3 + "IMG_7969.jpg", quad=[(1215, 2572), (2550, 2420), (2575, 4300), (1195, 4335)],
                   old=I7 + "190617_012.jpg", refine=False, adj=(4, 4, 4, 30)),
    "mina": dict(src=B3 + "IMG_7974.jpg", quad=[(1076, 2064), (2624, 2064), (2684, 4100), (1040, 4100)],
                 old=I7 + "190804_014.jpg"),
    "abraam": dict(src=B3 + "IMG_7979.jpg", quad=[(1192, 1585), (3500, 1365), (3630, 4450), (1036, 4570)],
                   old=I7 + "191010_015.jpg"),
    "resurrection": dict(src=B3 + "IMG_7983.jpg", quad=[(670, 825), (2340, 822), (2350, 2950), (660, 2950)],
                         old=I7 + "191737_020.jpg", adj=(30, 0, 14, 22), old_patch=[(0, 0.94, 1, 1)]),
    "ascension": dict(src=B3 + "IMG_7985.jpg", quad=[(1180, 2458), (2485, 2458), (2490, 4250), (1175, 4250)],
                      old=I7 + "191706_019.jpg", old_patch=[(0, 0.94, 1, 1)]),
    "pentecost": dict(src=B3 + "IMG_7989.jpg", quad=[(830, 1182), (2175, 1182), (2182, 2960), (825, 2960)],
                      old=I7 + "192128_021.jpg", adj=(12, 0, 46, 64)),
}


def arch_fill(im, spring_frac, colour=None):
    """Fill everything outside a round arch (half-ellipse above spring_frac*height) with a colour
    (default: the median colour of the panel centre)."""
    h, w = im.shape[:2]
    sp = spring_frac * h
    yy, xx = np.mgrid[0:h, 0:w]
    inside = (((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - sp) / sp) ** 2 <= 1) | (yy >= sp)
    if colour is None:
        c = im[int(h * 0.35):int(h * 0.65), int(w * 0.1):int(w * 0.3)].reshape(-1, 3)
        colour = np.median(c, axis=0)
    a = cv2.GaussianBlur(inside.astype(np.float32), (0, 0), 1.2)[..., None]
    return (im * a + np.float32(colour) * (1 - a) + 0.5).astype(np.uint8)


def height_from_relief(im, blur=2.0):
    """Grayscale height estimate for hammered metal relief: local brightness (raised parts catch the
    light, the pitted ground is dark), large-scale lighting removed."""
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = cv2.GaussianBlur(g, (0, 0), blur)
    low = cv2.GaussianBlur(g, (0, 0), max(im.shape[:2]) * 0.12)
    d = g - low
    # broad forms (figure vs ground) + finer chasing
    broad = cv2.GaussianBlur(d, (0, 0), max(im.shape[:2]) * 0.012)
    hgt = 0.65 * broad + 0.35 * d
    lo, hi = np.percentile(hgt, (1, 99))
    return (np.clip((hgt - lo) / (hi - lo), 0, 1) * 255 + 0.5).astype(np.uint8)


# other single-photo items. kind: "today" = Nov 2026 iPhone photo (colour as shot)
GENERIC = {
    "throne_christ": dict(src="IMG_4808.jpg", quad=rect(1010, 935, 3079, 4570), refine=False, adj=(14, 0, 6, 24),
                          note="bishop's throne icon; arched top: upper corners show the carved arch"),
    "curtain_mary": dict(src="IMG_4819.jpg", quad=rect(790, 835, 3403, 5500), refine=False, arch=0.28, adj=(22, 0, 0, 0),
                         note="left door curtain (St Mary); outside of the arch filled with velvet colour"),
    "curtain_christ": dict(src="IMG_7899.jpg", quad=rect(1300, 2386, 2640, 4180), refine=False, arch=0.375, adj=(30, 0, 30, 0),
                           quality="ok", note="centre royal door curtain (Christ), from a straight-on overview; "
                           "outside of the arch filled with velvet colour"),
    "curtain_right": dict(src=B3 + "IMG_7956.jpg", quad=[(1528, 1822), (1905, 1822), (1905, 2398), (1528, 2398)],
                          refine=False, arch=0.26, quality="low",
                          note="right door curtain (St Mark with lion), velvet only: small (curtain is ~340 px wide in "
                          "the only view), cut off above the lion's feet where a bench rail covers it, right "
                          "edge is where the curtain is drawn back; outside of the arch filled with velvet colour"),
    "stmark_relief": dict(src=B3 + "IMG_7990.jpg", quad=[(714, 1195), (1996, 1273), (2286, 3841), (545, 3941)],
                          aspect=0.5, height=True, flatten=0.5,
                          note="hammered-copper St Mark relief above the back doors, rectified from below, "
                          "forced to 1:2; matching height map stmark_relief_height.jpg"),
}


def generic(name, preview=False):
    sp = dict(GENERIC[name])
    im = lib.load(sp["src"])
    q = sp["quad"]
    if sp.get("refine", True):
        q = refine_quad(im, q, spans=sp.get("spans"), inner=sp.get("inner", 0.5), outer=sp.get("outer", ()),
                        sides=sp.get("sides", ("left", "right", "top", "bottom")),
                        debug=os.path.join(os.environ["ICON_DEBUG"], f"rq_{name}.jpg") if os.environ.get("ICON_DEBUG") else None)
    out = rectify_adj(im, q, sp.get("adj", (0, 0, 0, 0)), aspect=sp.get("aspect"), preview=preview)
    if preview:
        return out, "", "", "", {}
    if sp.get("flatten"):
        out = lib.flatten_light(out, 0.4, sp["flatten"])
    if sp.get("arch"):
        out = arch_fill(out, sp["arch"])
    extra = {}
    if sp.get("height"):
        extra[f"{name}_height"] = (cv2.cvtColor(height_from_relief(out), cv2.COLOR_GRAY2BGR),
                                   "grayscale height estimate from the photo's light/dark relief (bright = raised)")
    return out, "reference/" + sp["src"], sp.get("quality", "good"), sp.get("note", ""), extra


# ----------------------------------------------------------------------------- cut-outs in the arch
# crucifix and its two flanking panels are free-standing cut-outs against the dark recess, shot from
# below (IMG_7954). ROI -> bright-shape mask -> tight box -> stretched to the true proportions measured
# on the distant straight-on view IMG_7899 -> background black.
CUTOUTS = {
    "crucifix": dict(roi=(700, 600, 2600, 2345), aspect=0.796, note="crucifix cut-out (cross panel without its post)"),
    "crucifix_mary": dict(roi=(0, 1650, 830, 2466), aspect=0.65, thr=105, deskew=True, note="St Mary panel left of the crucifix"),
    "crucifix_john": dict(roi=(2500, 1700, 3260, 2512), aspect=0.65, deskew=True, note="St John panel right of the crucifix"),
}


def cutout(name):
    sp = CUTOUTS[name]
    im = lib.load(B3 + "IMG_7954.jpg")
    x0, y0, x1, y1 = sp["roi"]
    roi = im[y0:y1, x0:x1]
    g = cv2.cvtColor(cv2.GaussianBlur(roi, (0, 0), 2), cv2.COLOR_BGR2GRAY)
    m = (g > sp.get("thr", 70)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    big = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
    m = (lab == big).astype(np.uint8) * 255
    cnt, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    m = np.zeros_like(m)
    cv2.drawContours(m, cnt, -1, 255, -1)          # fill: dark beams inside the outline stay
    m = cv2.erode(m, np.ones((5, 5), np.uint8))
    ys, xs = np.where(m > 0)
    bx0, bx1, by0, by1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    crop, mk = roi[by0:by1, bx0:bx1], m[by0:by1, bx0:bx1]
    if sp.get("deskew"):
        # straighten the leaning side edges (keystone): fit the mask's left/right edges below the arch
        hh = mk.shape[0]
        rows = np.arange(int(hh * 0.4), int(hh * 0.92), 3)
        L = [np.where(mk[y] > 0)[0].min() for y in rows]
        Rr = [np.where(mk[y] > 0)[0].max() for y in rows]
        aL, bL = np.polyfit(rows, L, 1)
        aR, bR = np.polyfit(rows, Rr, 1)
        q = [(bL, 0), (bR, 0), (aR * hh + bR, hh), (aL * hh + bL, hh)]
        wq = int(round(((bR - bL) + (aR * hh + bR - aL * hh - bL)) / 2))
        crop = lib.warp(crop, q, wq, hh)
        mk = lib.warp(cv2.cvtColor(mk, cv2.COLOR_GRAY2BGR), q, wq, hh)[..., 0]
    h = crop.shape[0] * (crop.shape[1] / crop.shape[0]) / sp["aspect"]   # stretch height to true aspect
    ow, oh = lib.fit_size(crop.shape[1], h, max_side=MAXS)
    out = cv2.resize(crop, (ow, oh), interpolation=cv2.INTER_AREA if ow < crop.shape[1] else cv2.INTER_CUBIC)
    mk = cv2.resize(mk, (ow, oh), interpolation=cv2.INTER_LINEAR)
    a = cv2.GaussianBlur(mk.astype(np.float32) / 255, (0, 0), 1.0)[..., None]
    out = (out * a + 0.5).astype(np.uint8)
    return out, "reference/" + B3 + "IMG_7954.jpg", "ok", sp["note"] + \
        "; shot from below, height stretched to the proportions seen in the straight-on IMG_7899; background black"


# ----------------------------------------------------------------------------- last supper
def fill_from(T, O, fill, sigma=14.0):
    """Replace T where fill>0 by O, after matching O's local colour/brightness to T's surroundings
    (low-frequency ratio computed from the pixels of T that are NOT being replaced). fill is float 0..1."""
    keep = (fill < 0.02).astype(np.float32)
    Tf, Of = T.astype(np.float32) + 4, O.astype(np.float32) + 4
    def nb(x, wgt):
        return cv2.GaussianBlur(x * wgt[..., None], (0, 0), sigma) / (cv2.GaussianBlur(wgt, (0, 0), sigma)[..., None] + 1e-4)
    have = cv2.GaussianBlur(keep, (0, 0), sigma) > 0.02
    ratio = np.where(have[..., None], nb(Tf, keep) / nb(Of, keep), 1.0)
    # far from any kept pixel: fall back to the global ratio
    g = (Tf * keep[..., None]).sum(axis=(0, 1)) / (Of * keep[..., None]).sum(axis=(0, 1))
    ratio = np.where(have[..., None], np.clip(ratio, 0.4, 2.5), g)
    Om = Of * ratio
    out = Tf * (1 - fill[..., None]) + Om * fill[..., None] - 4
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def last_supper(preview=False):
    """Frame = the 2007 straight-on photo (true proportions). Pixels = today's sharp from-below photo
    registered into that frame; the egg cord and the part outside today's photo come from 2007."""
    o = lib.load(I7 + "191502_018.jpg")
    q = refine_quad(o, rect(624, 886, 2474, 1502), outer=("bottom",),
                    debug=os.path.join(os.environ["ICON_DEBUG"], "rq_last_supper.jpg") if os.environ.get("ICON_DEBUG") else None)
    if preview:
        return rectify_adj(o, q, preview=True), "", "", ""
    O = rectify_adj(o, q, LS_ADJ)
    h, w = O.shape[:2]
    tp = lib.load(B3 + "IMG_7952.jpg")
    H, inl = register(tp, O, scale_to=2400)
    print("last_supper registration inliers", inl)
    if H is None:
        return fix2007(O), f"reference/{I7}191502_018.jpg", "ok", "2007 photo only (registration of today's photo failed)"
    T, valid = warp_to(tp, H, (w, h))
    fill = (cv2.erode(valid, np.ones((25, 25), np.uint8)) == 0).astype(np.float32)
    x, wd = LS_CORD_TODAY
    fill[:, x - wd:x + wd + 1] = 1          # egg cord in today's photo (it sits ~8 px left of that in 2007)
    fill = cv2.GaussianBlur(fill, (0, 0), 1.5)
    fill[:, x - wd + 2:x + wd - 1] = 1
    out = fill_from(T, O, fill)
    return out, f"reference/{B3}IMG_7952.jpg + reference/{I7}191502_018.jpg", "good", \
        "today's photo (from below) registered into the straight-on 2007 view; the hanging egg cord and " \
        f"{100 * float((valid == 0).mean()):.0f}% of the panel outside today's frame are filled from the 2007 " \
        "photo, colour-matched locally"


LS_ADJ = (0, 0, 0, 0)
LS_CORD_TODAY = (790, 6)

NOTES = {"john_baptist": "; title band at the bottom is cut off in the source photo"}
QUALITY = {}


def build(name, preview=False):
    """returns (image, source string, quality, note)"""
    if name in LOWER:
        code, box = LOWER[name]
        im = lib.load(f"{I7}{code}.jpg")
        q = rect(*box)
        if preview:
            return rectify_adj(im, q, preview=True), "", "", ""
        out = fix2007(rectify_adj(im, q))
        return out, f"reference/{I7}{code}.jpg", "good", \
            "2007 close-up, straight-on; orange cast mapped to today's colour (profile from IMG_4802/4803/4805); " \
            "arched top: the two upper corners show the wood arch moulding" + NOTES.get(name, "")
    if name in SHRINES:
        sp = dict(SHRINES[name])
        if os.environ.get("ICON_DEBUG"):
            sp["debug"] = os.path.join(os.environ["ICON_DEBUG"], f"rq_{name}.jpg")
        out, info = shrine(sp, preview)
        if preview:
            return out, "", "", ""
        src = "reference/" + sp["src"] + (" + reference/" + sp["old"] if info.get("old_used") else "")
        note = "today's photo rectified (today's colour)" + (
            f"; lighting evened with the registered 2007 photo ({info.get('inliers')} matches)" if info.get("old_used")
            else "; 2007 photo could not be registered, lighting as shot")
        return out, src, QUALITY.get(name, "good"), note + NOTES.get(name, "")
    if name in GENERIC:
        out, src, q, note, extra = generic(name, preview)
        EXTRA.update({k: (v[0], src, q, v[1]) for k, v in extra.items()})
        return out, src, q, note
    if name in CUTOUTS:
        return cutout(name)
    if name == "last_supper":
        return last_supper(preview)
    raise KeyError(name)


EXTRA = {}   # additional outputs produced while building (height maps etc.)
ALL = list(LOWER) + list(SHRINES) + list(GENERIC) + list(CUTOUTS) + ["last_supper"]

if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--preview":
        d = args[1]
        for n in args[2:]:
            pv, *_ = build(n, preview=True)
            cv2.imwrite(os.path.join(d, f"pv_{n}.jpg"), pv, [cv2.IMWRITE_JPEG_QUALITY, 88])
        sys.exit()
    names = args or ALL
    entries = []
    for n in names:
        out, src, q, note = build(n)
        lib.save(f"icons/{n}.jpg", out)
        entries.append(lib.entry(f"icons/{n}.jpg", out, src, q, note))
        print(n, out.shape[1], out.shape[0], q, note[:90])
        for k, (o2, s2, q2, n2) in list(EXTRA.items()):
            lib.save(f"icons/{k}.jpg", o2)
            entries.append(lib.entry(f"icons/{k}.jpg", o2, s2, q2, n2))
            del EXTRA[k]
    if not args:
        lib.write_part("icons", entries)
