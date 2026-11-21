"""Tileable pattern textures -> textures/patterns/

  marquetry_cross.jpg (+ _height)  cross-and-star marquetry, 2 x 2 lattice periods, tiles in U and V
  bead_lattice.jpg    (+ _height)  turned-bead lattice, 4 x 4 lattice periods, tiles in U and V
  runner.jpg                       aisle runner, full width, tiles along its length (V) only
  carpet_red.jpg                   plain red carpet, tiles in U and V
  pew_inlay.jpg                    square inlaid panel (not tileable)

usage: patterns.py [name ...] [--debug DIR]     (no names = everything + manifest part)

Method for the two wood lattices: detect the repeating elements (light crosses / beads), fit ONE
homography from ideal lattice coordinates to the photo, render an exact whole number of periods plus
a margin, and cross-fade the margin (the true continuation of the pattern) over the opposite edge.
"""
import sys, os
import cv2
import numpy as np
import lib

DEBUG = None
SIZE = 1024


def dbg(name, im):
    if DEBUG:
        cv2.imwrite(os.path.join(DEBUG, name), im)


# ---------------------------------------------------------------- generic helpers
def render(im, H, u0, v0, u1, v1, ppu, ss=2):
    """Render the ideal-coordinate window [u0,u1] x [v0,v1] at ppu pixels per unit.
    H maps ideal (u, v) -> source pixel."""
    w, h = int(round((u1 - u0) * ppu)), int(round((v1 - v0) * ppu))
    k = ppu * ss
    T = np.array([[1 / k, 0, u0], [0, 1 / k, v0], [0, 0, 1]], np.float64)
    big = cv2.warpPerspective(im, H @ T, (w * ss, h * ss), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP,
                              borderMode=cv2.BORDER_REFLECT)
    return cv2.resize(big, (w, h), interpolation=cv2.INTER_AREA) if ss > 1 else big


def wrap_blend(ext, n, m, axis):
    """ext covers n + m pixels along axis: one exact tile of n px followed by m px of its
    continuation. Returns the n px tile whose first m px fade from the continuation into the tile,
    so the tile's end joins its start with no seam."""
    f = np.moveaxis(ext.astype(np.float32), axis, 0)
    a = np.linspace(0, 1, m, dtype=np.float32)
    a = (0.5 - 0.5 * np.cos(a * np.pi)).reshape((m,) + (1,) * (f.ndim - 1))
    out = f[:n].copy()
    out[:m] = f[n:n + m] * (1 - a) + f[:m] * a
    return np.moveaxis(out, 0, axis)


def flatten(im, sigma, strength=1.0):
    """Divide out the large-scale illumination (per channel-luma), keep the mean colour."""
    f = im.astype(np.float32) + 1
    lum = f.mean(axis=2)
    low = cv2.GaussianBlur(lum, (0, 0), sigma, borderType=cv2.BORDER_REFLECT)
    g = (low.mean() / low) ** strength
    return np.clip(f * g[..., None] - 1, 0, 255)


def wrap_filter(im, fn, pad):
    """Apply fn to a wrap-padded copy so the result stays tileable."""
    p = np.pad(im, ((pad, pad), (pad, pad)) + ((0, 0),) * (im.ndim - 2), mode="wrap")
    return fn(p)[pad:-pad, pad:-pad]


def height_from(tile, grain_sigma, lo=2, hi=98, gamma=1.0):
    """Grayscale relief estimate from a tileable colour tile: light = raised, dark = recessed.
    Wood grain is smoothed away with an edge-preserving filter; stays tileable."""
    g = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
    pad = 64

    def f(p):
        p = cv2.bilateralFilter(p, 0, 28, grain_sigma)
        p = cv2.bilateralFilter(p, 0, 22, grain_sigma)
        return cv2.GaussianBlur(p, (0, 0), 1.2)
    g = wrap_filter(g, f, pad).astype(np.float32)
    a, b = np.percentile(g, lo), np.percentile(g, hi)
    g = np.clip((g - a) / (b - a), 0, 1) ** gamma
    return (g * 255 + 0.5).astype(np.uint8)


def blobs(mask, amin, amax):
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask)
    return np.array([cen[i] for i in range(1, n) if amin <= st[i, cv2.CC_STAT_AREA] <= amax], np.float64)


def apply_h(H, pts):
    p = cv2.perspectiveTransform(np.float64(pts).reshape(-1, 1, 2), H)
    return p.reshape(-1, 2)


def tile3(im):
    return np.tile(im, (3, 3, 1) if im.ndim == 3 else (3, 3))


def save(name, im, src, quality, note, entries):
    im = np.clip(im, 0, 255).astype(np.uint8)
    lib.save(f"patterns/{name}.jpg", im, q=93)
    entries.append(lib.entry(f"patterns/{name}.jpg", im, src, quality, note))
    print(name, im.shape[1], im.shape[0], quality)
    return im


# ---------------------------------------------------------------- marquetry
MARQ_SRC = "IMG_4812.jpg"
# approximate centres of the light crosses, rows top->bottom, 4 columns each (source px)
_s = lambda x, y: (900 + x * 2.115, 2650 + y * 2.115)
MARQ_SEEDS = {
    (0, 0): _s(238, 160), (1, 0): _s(572, 177), (2, 0): _s(912, 188), (3, 0): _s(1262, 198),
    (0, 1): _s(180, 497), (1, 1): _s(552, 510), (2, 1): _s(925, 522), (3, 1): _s(1310, 540),
    (0, 2): _s(105, 905), (1, 2): _s(527, 925), (2, 2): _s(945, 945), (3, 2): _s(1385, 965),
}


def marquetry_h(im):
    ideal = np.float64(list(MARQ_SEEDS.keys()))
    src = np.float64(list(MARQ_SEEDS.values()))
    H, _ = cv2.findHomography(ideal, src, 0)
    for it in range(3):
        ppu = 300
        u0, v0, u1, v1 = -0.5, -0.45, 3.6, 2.45
        r = render(im, H, u0, v0, u1, v1, ppu, ss=1)
        g = flatten(r, ppu * 0.8).astype(np.uint8)
        hsv = cv2.cvtColor(g, cv2.COLOR_BGR2HSV)
        # the crosses are the pale, less saturated wood
        m = ((hsv[..., 2] > 150) & (hsv[..., 1] < 150)).astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        if it == 0:
            dbg("marq_rough.jpg", g); dbg("marq_mask.png", m)
        # cross centre = where its two straight arms intersect: the arm shows as the peak of the
        # column sums (vertical arm) and of the row sums (horizontal arm) inside each lattice cell
        uv, tgt = [], []
        for (i, j) in MARQ_SEEDS:
            cx, cy = (i - u0) * ppu, (j - v0) * ppu
            w = int(0.40 * ppu)
            x0, y0 = int(cx - w), int(cy - w)
            if x0 < 0 or y0 < 0 or x0 + 2 * w > m.shape[1] or y0 + 2 * w > m.shape[0]:
                continue
            win = (m[y0:y0 + 2 * w, x0:x0 + 2 * w] > 0).astype(np.float32)
            cs, rs = win.sum(axis=0), win.sum(axis=1)
            if cs.max() < 1.0 * w or rs.max() < 1.0 * w:
                continue
            xs = np.where(cs > 0.6 * cs.max())[0]
            ys = np.where(rs > 0.6 * rs.max())[0]
            uv.append(((x0 + xs.mean()) / ppu + u0, (y0 + ys.mean()) / ppu + v0))
            tgt.append((i, j))
        uv, tgt = np.float64(uv), np.float64(tgt)
        if len(uv) < 8:
            print("  marquetry: only", len(uv), "crosses measured, keeping seed fit")
            break
        srcp = apply_h(H, uv)
        H2, inl = cv2.findHomography(tgt, srcp, cv2.RANSAC, 8.0)
        err = np.linalg.norm(apply_h(H2, tgt) - srcp, axis=1)
        print(f"  marquetry fit {it}: {len(uv)} crosses, inliers {int(inl.sum())}, "
              f"median err {np.median(err):.1f} px, max {err.max():.1f}")
        H = H2
    return H


def do_marquetry(entries):
    im = lib.load(MARQ_SRC)
    H = marquetry_h(im)
    ppu = SIZE // 2                     # 2 x 2 periods in 1024 px
    u0, v0, m = 0.62, -0.40, 0.78       # tile origin (lattice units) and blend margin
    ext = render(im, H, u0 - 0.5, v0, u0 + 2 + m + 0.02, v0 + 2 + m + 0.02, ppu, ss=2)
    ext = flatten(ext, ppu * 0.9)
    ext = ext[:, int(0.5 * ppu):]       # the extra half period on the left was only for the flatten
    dbg("marq_ext.jpg", ext.astype(np.uint8))
    n, mm = 2 * ppu, int(m * ppu)
    t = wrap_blend(ext, n, mm, 1)
    t = wrap_blend(t, n, mm, 0)
    t = np.clip(t, 0, 255).astype(np.uint8)
    t = lib.levels(t, black=0.02, white=0.97, gamma=1.0, sat=1.0)
    note = ("cross-and-star marquetry, exactly 2 x 2 lattice periods (one period = one cross spacing), "
            "tiles in both directions; rectified from a low viewpoint, lighting flattened, "
            "seam cross-faded with the true continuation of the pattern")
    t = save("marquetry_cross", t, "reference/" + MARQ_SRC, "good", note, entries)
    hmap = height_from(t, 5, gamma=0.9)
    save("marquetry_cross_height", cv2.cvtColor(hmap, cv2.COLOR_GRAY2BGR), "reference/" + MARQ_SRC, "ok",
         "height estimate from luminance (light cross = high, dark grooves/mouldings = low), grain smoothed; "
         "same tiling as marquetry_cross.jpg; a guess, not measured relief", entries)
    dbg("marq_3x3.jpg", cv2.resize(tile3(t), (1500, 1500), interpolation=cv2.INTER_AREA))
    dbg("marq_h_3x3.jpg", cv2.resize(tile3(hmap), (1000, 1000), interpolation=cv2.INTER_AREA))


# ---------------------------------------------------------------- bead lattice
BEAD_SRC = "batch3/IMG_7951.jpg"       # close view from below of the lattice under the Last Supper
BEAD_ROI = (0, 2980, 2450, 3950)       # x0, y0, x1, y1
BEAD_SEED = (1228, 425)                # one bead centre inside the ROI (template seed)
BEAD_REF = ("IMG_7899.jpg", (150, 2110, 1050, 2740))   # straight-on view: colour reference only


def bead_h(im):
    """homography from ideal lattice coords (u = half bead pitch along a row, v = row) to source px.
    Beads sit at (u + v) even; dark blocks at (u + v) odd."""
    x0, y0, x1, y1 = BEAD_ROI
    g = cv2.cvtColor(im[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    h = 75

    def peaks(tpl, thr):
        r = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
        d = cv2.dilate(r, np.ones((121, 121)))
        ys, xs = np.where((r == d) & (r > thr))
        return np.stack([xs + h, ys + h], 1).astype(np.float64), r[ys, xs]
    cx, cy = BEAD_SEED
    p, s = peaks(g[cy - h:cy + h, cx - h:cx + h], 0.6)
    acc, k = np.zeros((2 * h, 2 * h), np.float32), 0
    for (x, y) in p.astype(int):
        if y - h >= 0 and x - h >= 0 and y + h <= g.shape[0] and x + h <= g.shape[1]:
            acc += g[y - h:y + h, x - h:x + h]; k += 1
    p, s = peaks((acc / k).astype(np.uint8), 0.8)
    # rows: cluster by y
    order = np.argsort(p[:, 1]); p = p[order]
    rows, cur = [], [p[0]]
    for q in p[1:]:
        if q[1] - cur[-1][1] > 60:
            rows.append(np.array(cur)); cur = [q]
        else:
            cur.append(q)
    rows.append(np.array(cur))
    rows = [r[np.argsort(r[:, 0])] for r in rows]
    pitch = np.median(np.concatenate([np.diff(r[:, 0]) for r in rows]))
    ideal, src = [], []
    prev = None
    for v, r in enumerate(rows):
        if prev is None:
            u = np.round((r[:, 0] - r[0, 0]) / (pitch / 2) / 2) * 2
        else:
            u = []
            for x in r[:, 0]:
                j = np.argmin(np.abs(prev[0] - x))
                step = np.round((x - prev[0][j]) / (pitch / 2))
                if step % 2 == 0:       # must land on the other parity
                    step += 1 if x >= prev[0][j] else -1
                u.append(prev[1][j] + step)
            u = np.array(u)
        prev = (r[:, 0], u)
        for (x, y), uu in zip(r, u):
            ideal.append((uu, v)); src.append((x + x0, y + y0))
    ideal, src = np.float64(ideal), np.float64(src)
    H, inl = cv2.findHomography(ideal, src, cv2.RANSAC, 5.0)
    err = np.linalg.norm(apply_h(H, ideal) - src, axis=1)
    print(f"  beads: {len(src)} in {len(rows)} rows, inliers {int(inl.sum())}, median err {np.median(err):.1f} px,"
          f" pitch {pitch:.0f} px")
    return H, ideal


def match_colour(tile, ref, strength=0.8):
    """shift the tile's Lab mean / spread toward a reference patch of the same material"""
    a = cv2.cvtColor(tile, cv2.COLOR_BGR2LAB).astype(np.float32)
    b = cv2.cvtColor(ref, cv2.COLOR_BGR2LAB).astype(np.float32)
    for c in range(3):
        ma, sa, mb, sb = a[..., c].mean(), a[..., c].std(), b[..., c].mean(), b[..., c].std()
        k = 1 + (np.clip(sb / sa, 0.7, 1.4) - 1) * strength
        a[..., c] = (a[..., c] - ma) * k + ma + (mb - ma) * strength
    return cv2.cvtColor(np.clip(a, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def do_beads(entries):
    im = lib.load(BEAD_SRC)
    H, ideal = bead_h(im)
    ppu = SIZE // 8                     # 8 cells (4 bead pitches) across 1024 px
    m = 0.75                            # blend margin in cells
    n, mm = 4 * ppu, int(m * ppu)       # one band = 4 rows
    bands = []
    for ua in (0.5, 4.5):               # two bands of rows 1..4 taken 2 bead pitches apart
        ext = render(im, H, ua, 0.5, ua + 8 + m + 0.02, 4.5 + m + 0.02, ppu, ss=2)
        ext = flatten(ext, ppu * 3.0)
        dbg(f"bead_ext_{ua}.jpg", ext.astype(np.uint8))
        bands.append(wrap_blend(ext, 8 * ppu, mm, 1))      # horizontal wrap; still n + mm rows tall
    A, B = bands
    a = np.linspace(0, 1, mm, dtype=np.float32)
    a = (0.5 - 0.5 * np.cos(a * np.pi))[:, None, None]
    TA, TB = A[:n].copy(), B[:n].copy()
    TA[:mm] = B[n:n + mm] * (1 - a) + A[:mm] * a          # continuation of B fades into A
    TB[:mm] = A[n:n + mm] * (1 - a) + B[:mm] * a          # continuation of A fades into B
    t = np.clip(np.concatenate([TA, TB], axis=0), 0, 255).astype(np.uint8)
    ref = lib.load(BEAD_REF[0])
    x0, y0, x1, y1 = BEAD_REF[1]
    t = match_colour(t, ref[y0:y1, x0:x1], 0.4)
    t = lib.unsharp(t, 1.0, 0.35)
    note = ("turned-bead lattice, 8 x 8 cells = 4 x 4 lattice periods (one period = bead, block, bead "
            "offset by half a pitch on the next row), tiles in both directions; rectified from a close shot "
            "taken from below, so the beads show a little of their underside; colour moved part-way toward the "
            "straight-on view in IMG_7899")
    t = save("bead_lattice", t, "reference/" + BEAD_SRC, "good", note, entries)
    # height: backing board lowest, flat dark blocks a mid plateau, beads/rods high.
    # Beads and rods are the pale wood (bright, weakly saturated); the board is orange and dimmer.
    hsv = cv2.cvtColor(t, cv2.COLOR_BGR2HSV).astype(np.float32) / 255
    pale = (hsv[..., 2] * (1 - hsv[..., 1]) * 255).astype(np.uint8)

    def sm(p_):
        p_ = cv2.bilateralFilter(p_, 0, 30, 4)
        return cv2.GaussianBlur(p_, (0, 0), 1.5)
    pale = wrap_filter(pale, sm, 32).astype(np.float32)
    lo, hi = np.percentile(pale, 55), np.percentile(pale, 99.5)
    hm = np.clip((pale - lo) / (hi - lo), 0, 1) ** 0.8 * 255
    el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(ppu * 0.30),) * 2)
    hm = wrap_filter(hm, lambda p_: cv2.morphologyEx(p_, cv2.MORPH_CLOSE, el), 64)   # fill the dimple on each bead
    # the blocks sit on the known lattice: cells where (column + row) is odd
    blk = np.zeros(t.shape[:2], np.float32)
    half = int(ppu * 0.36)
    for j in range(8):
        for i in range(8):
            if (i + j) % 2 == 1:
                cx, cy = int((i + 0.5) * ppu), int((j + 0.5) * ppu)
                blk[cy - half:cy + half, cx - half:cx + half] = 140
    hm = np.maximum(hm, blk)
    hm = wrap_filter(hm, lambda p_: cv2.GaussianBlur(p_, (0, 0), 1.2), 16)
    hm = np.clip(hm, 0, 255).astype(np.uint8)
    save("bead_lattice_height", cv2.cvtColor(hm, cv2.COLOR_GRAY2BGR), "reference/" + BEAD_SRC, "ok",
         "height estimate: backing board low, dark square blocks a flat mid plateau, beads and rods high "
         "(from brightness); same tiling as bead_lattice.jpg; a guess, not measured relief", entries)
    dbg("bead_3x3.jpg", cv2.resize(tile3(t), (1500, 1500), interpolation=cv2.INTER_AREA))
    dbg("bead_h_3x3.jpg", cv2.resize(tile3(hm), (1000, 1000), interpolation=cv2.INTER_AREA))


# ---------------------------------------------------------------- aisle runner
RUN_SRC = "IMG_7885.jpg"               # 0.5x overview looking down the aisle, runner centred
# outer cream edges of the runner in the photo, x = a*y + b (fitted to the saturation step, rows 3000-4020)
RUN_L = (-0.3776135740332594, 2168.3930415258324)
RUN_R = (0.23752583826095794, 924.193261155634)
RUN_F35 = 14.0                         # EXIF FocalLengthIn35mmFilm
RUN_W = 768                            # output width (px), incl. the dark red binding each side
RUN_REPEATS = 3


def runner_strip(im):
    """metric rectification of the floor: the two parallel runner edges give the vanishing point,
    the camera is level, so with the focal length the ground-plane coordinates of every pixel follow."""
    (aL, bL), (aR, bR) = RUN_L, RUN_R
    hh, ww = im.shape[:2]
    f = RUN_F35 / 43.27 * np.hypot(ww, hh)
    yh = (bL - bR) / (aR - aL); xv = aR * yh + bR; cx = ww / 2
    d = np.array([(xv - cx) / f, 1.0]); d /= np.linalg.norm(d)
    e = np.array([d[1], -d[0]])

    def plane(x, y):
        P = np.array([(x - cx) / (y - yh), f / (y - yh)])
        return np.array([P @ e, P @ d])
    pi, pp = [], []
    for y in (2850, 3200, 3600, 4030):
        for a, b in ((aL, bL), (aR, bR)):
            pi.append((a * y + b, y)); pp.append(plane(a * y + b, y))
    pi, pp = np.float64(pi), np.float64(pp)
    sL, sR = pp[0::2, 0].mean(), pp[1::2, 0].mean()
    W = sR - sL
    t_near, t_far = pp[-1, 1], pp[0, 1]
    H, _ = cv2.findHomography(pp, pi, 0)
    pad = 0.03                                    # dark red binding outside the cream edge
    ppu = RUN_W / (W * (1 + 2 * pad))
    h = int((t_far - t_near) * ppu)
    T = np.array([[1 / ppu, 0, sL - pad * W], [0, -1 / ppu, t_far], [0, 0, 1]])   # far end at the top
    r = cv2.warpPerspective(im, H @ T, (RUN_W, h), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP)
    return r, (t_far - t_near) / W


def best_period(g, lo, hi):
    """lag (rows) with the highest normalised autocorrelation in [lo, hi], sub-pixel"""
    s = g - g.mean()
    best = []
    for lag in range(lo, hi):
        a, b = s[:-lag], s[lag:]
        best.append((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))
    best = np.array(best); i = int(np.argmax(best))
    if 0 < i < len(best) - 1:
        y0, y1, y2 = best[i - 1:i + 2]
        i = i + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)
    return lo + i, float(best.max())


def do_runner(entries):
    im = lib.load(RUN_SRC)
    r, ratio = runner_strip(im)
    dbg("run_rect.jpg", r)
    g = cv2.cvtColor(r, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g -= cv2.GaussianBlur(g, (0, 0), 25)
    p1, c1 = best_period(g, int(RUN_W * 0.20), int(RUN_W * 0.30))     # one border repeat ~ width / 4
    pn, cn = best_period(g, int(p1 * RUN_REPEATS - 8), int(p1 * RUN_REPEATS + 8))
    period = pn / RUN_REPEATS
    print(f"  runner: border repeat {period:.2f} px at width {RUN_W} (corr {c1:.2f}/{cn:.2f}); "
          f"rectified strip length/width {ratio:.2f}")
    # even out exposure along the length (row means of luminance), keep colour
    f = r.astype(np.float32)
    lum = f.mean(axis=2)
    rowm = cv2.GaussianBlur(lum[20:-30].mean(axis=1)[:, None], (0, 0), period)[:, 0]
    rowm = np.concatenate([np.full(20, rowm[0]), rowm, np.full(30, rowm[-1])])
    f *= (np.median(rowm) / rowm)[:, None, None]
    n = int(round(pn)); m = int(period * 0.3)
    end = r.shape[0] - 28                         # skip the photo's bottom edge
    ext = f[end - m - n:end]                      # nearest (sharpest) stretch: tile then continuation
    t = wrap_blend(ext, n, m, 0)
    t = np.clip(t, 0, 255).astype(np.uint8)
    # dim tungsten light: lift exposure, pull the yellow-green cast off the cream moderately
    t = lib.wb_gain(t, (1.16, 1.02, 1.0), 1.0)
    t = lib.levels(t, black=0.03, white=0.80, gamma=1.08, sat=1.05)
    t = lib.unsharp(t, 1.2, 0.5)
    note = (f"aisle runner, full width (cream border to cream border plus ~3% dark red binding each side), "
            f"tiles along its length (V) only; contains {RUN_REPEATS} repeats of the border motif "
            f"(= {RUN_REPEATS * 4} rows-pairs of the small field motif); real aspect of this tile "
            f"width:length = 1:{n / RUN_W:.3f}, so one border repeat is about {period / RUN_W:.3f} x the runner "
            f"width (~23 cm if the runner is ~0.9 m wide); rectified from a 0.5x overview with EXIF focal "
            f"length, +-5% on the aspect; soft because the source is a dim wide-angle shot")
    save("runner", t, "reference/" + RUN_SRC, "ok", note, entries)
    dbg("run_3x.jpg", np.tile(t, (3, 1, 1)))


# ---------------------------------------------------------------- red carpet
CARPET_SRC = "IMG_7899.jpg"
CARPET_F35 = 26.0


def do_carpet(entries):
    im = lib.load(CARPET_SRC)
    hh, ww = im.shape[:2]
    f = CARPET_F35 / 43.27 * np.hypot(ww, hh)
    cx, yh = ww / 2, hh / 2                       # level camera: horizon through the image centre
    m = 0.15
    side = 0.70                                   # tile edge in camera heights (~1 m of carpet)
    X0, Z0 = -0.52, 1.508

    def img(X, Z):
        return (cx + X * f / Z, yh + f / Z)
    e = side * (1 + m)
    src = np.float32([img(X0, Z0 + e), img(X0 + e, Z0 + e), img(X0 + e, Z0), img(X0, Z0)])
    n = SIZE; mm = int(n * m)
    ext = lib.warp(im, src, n + mm, n + mm)
    dbg("carpet_ext.jpg", ext)
    # remove the few light specks of lint
    g = cv2.cvtColor(ext, cv2.COLOR_BGR2GRAY)
    med = cv2.medianBlur(g, 21)
    spk = ((g.astype(np.int16) - med) > 28).astype(np.uint8) * 255
    spk = cv2.dilate(spk, np.ones((7, 7), np.uint8))
    ext = cv2.inpaint(ext, spk, 5, cv2.INPAINT_TELEA)
    ext = flatten(ext, 18)                        # take out vacuum marks / light falloff, keep the pile
    t = wrap_blend(ext, n, mm, 1)
    t = wrap_blend(t, n, mm, 0)
    t = np.clip(t, 0, 255).astype(np.uint8)
    # the photo is exposed bright (pinkish): bring it down to the deep red seen across the nave shots
    t = lib.levels(t, black=0.0, white=1.0, gamma=0.80, sat=1.12)
    t = lib.unsharp(t, 1.0, 0.4)
    note = ("plain red carpet, about 1 m x 1 m, tiles in both directions; floor patch in front of the royal "
            "door rectified with the EXIF focal length, lint specks inpainted, vacuum marks and light falloff "
            "flattened; pile detail is fine-grained only")
    t = save("carpet_red", t, "reference/" + CARPET_SRC, "good", note, entries)
    dbg("carpet_3x3.jpg", cv2.resize(tile3(t), (1500, 1500), interpolation=cv2.INTER_AREA))


# ---------------------------------------------------------------- inlaid panel
PEW_SRC = "IMG_7899.jpg"
# centres of the four inlaid lozenges (top, bottom, left, right) of the lower square panel on the
# front of the right lectern; they sit at the middle of the square's sides
PEW_LOZ = [(3873, 4767), (3906, 5259), (3654, 5028), (4109, 5007)]


def do_pew(entries):
    im = lib.load(PEW_SRC)
    dst = np.float32([(500, 250), (500, 750), (250, 500), (750, 500)])
    M = cv2.getPerspectiveTransform(np.float32(PEW_LOZ), dst)
    r = cv2.warpPerspective(im, M, (1000, 1000), flags=cv2.INTER_CUBIC)
    t = r[130:910, 130:910]
    t = lib.levels(t, black=0.01, white=0.80, gamma=1.25, sat=1.0)
    t = lib.unsharp(t, 1.2, 0.4)
    note = ("square inlaid panel (four diagonal inlaid bars and four lozenges with mother-of-pearl in a "
            "moulded star), rectified and cropped to the panel incl. its star points. Taken from the front of "
            "the right LECTERN, which carries the same inlay design as the pew ends: no photo shows a pew end "
            "close or straight enough (they are small, dark and oblique in every shot). Dark exposure lifted. "
            "A straight-on close-up of one pew end would replace this.")
    save("pew_inlay", t, "reference/" + PEW_SRC, "ok", note, entries)


JOBS = {"marquetry": do_marquetry, "beads": do_beads, "runner": do_runner, "carpet": do_carpet, "pew": do_pew}



if __name__ == "__main__":
    args = sys.argv[1:]
    if "--debug" in args:
        i = args.index("--debug"); DEBUG = args[i + 1]; del args[i:i + 2]
        os.makedirs(DEBUG, exist_ok=True)
    entries = []
    for n in (args or list(JOBS)):
        JOBS[n](entries)
    if not args:
        lib.write_part("patterns", entries)
