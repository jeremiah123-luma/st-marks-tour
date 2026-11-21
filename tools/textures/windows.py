"""Stained-glass windows -> textures/windows/<name>.jpg

Automatic: find the glass (bright / saturated region), fit its straight left, right and bottom
edges, rectify, black out everything outside the arch, even out exposure between stacked panels.
usage: windows.py [name ...] [--debug DIR]
"""
import sys, os
import cv2
import numpy as np
import lib

SOURCES = {
    "abraham": "windows/IMG_1928.jpeg", "david": "windows/IMG_1929.jpeg",
    "three_youths": "windows/IMG_1930.jpeg", "moses": "windows/IMG_1931.jpeg",
    "daniel": "windows/IMG_1932.jpeg", "storm": "windows/IMG_1926.jpeg",
    "samaritan": "windows/IMG_1925.jpeg", "egypt": "windows/IMG_1922.jpeg",
    "lazarus": "windows/IMG_1923.jpeg", "healing": "windows/IMG_1924.jpeg",
    # IMG_2748 (Gabriel) and IMG_2752 (Mikhail) are sanctuary windows: not delivered (owner, Nov 2026)
}
# per-window overrides: inset (px in output) trimmed off each side after detection,
# max panel gain, notes
OPT = {
    # L / R / top / bot: glass edges (outer lead line) read off 6x crops of the padded diagnostic
    # warp (--debug writes pad_<name>.jpg); see straighten().
    'abraham': dict(L=[(68, 520), (58, 1320), (54, 2090)], R=[(520, 520), (524, 1320), (524, 2090)],
                    top=66, bot=(2108, 2108)),
    'david': dict(L=[(67, 520), (57, 1320), (57, 2090)], R=[(528, 520), (528, 1320), (527, 2090)],
                  top=67, bot=(2109, 2109)),
    'three_youths': dict(L=[(67, 520), (59, 1320), (57, 1995)], R=[(490, 520), (498, 1320), (503, 1995)],
                         top=120, bot=(2005, 2005)),
    'moses': dict(L=[(62, 520), (61, 1320), (63, 2090)], R=[(530, 520), (531, 1320), (529, 2090)],
                  top=81, bot=(2108, 2108)),
    'daniel': dict(quad=[[32, 50], [1563, 50], [1300, 6614], [100, 6614]],
                   L=[(55, 490), (52, 1250), (56, 2080)], R=[(492, 490), (495, 1250), (493, 2080)],
                   top=61, bot=(2121, 2121), max_gain=1.15),
    'storm': dict(L=[(66, 520), (51, 1320), (48, 2090)], R=[(530, 520), (546, 1320), (549, 2090)],
                  top=46, bot=(2105, 2105)),
    'samaritan': dict(L=[(62, 520), (60, 1320), (61, 2090)], R=[(524, 520), (521, 1320), (518, 2090)],
                      top=72, bot=(2099, 2099)),
    'egypt': dict(L=[(60, 520), (53, 1320), (55, 2090)], R=[(523, 520), (527, 1320), (527, 2090)],
                  top=72, bot=(2107, 2107)),
    'lazarus': dict(L=[(62, 520), (62, 1320), (63, 2060)], R=[(522, 520), (532, 1320), (533, 2060)],
                    top=73, bot=(2068, 2068)),
    'healing': dict(L=[(51, 870), (51, 2080)], R=[(931, 870), (931, 2080)], top=33, bot=(2096, 2096)),
}
MAX_H = 2048


def glass_mask(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32)
    s, v = hsv[..., 1] / 255, hsv[..., 2] / 255
    # coloured, lit glass only: the plaster reveal is duller (s < 0.55) even where the window lights it
    m = (s > 0.60) & (v > 0.45)
    m = m.astype(np.uint8) * 255
    k = max(9, int(im.shape[1] * 0.06)) | 1
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    ko = max(9, int(im.shape[1] * 0.03)) | 1
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((ko, ko), np.uint8))
    # bridge the grey mullion bars between the stacked panels
    kv = int(im.shape[0] * 0.035) | 1
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((kv, 1), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        big = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
        m = (lab == big).astype(np.uint8) * 255
    return m


def robust_line(t, x, iters=4):
    """fit x = a*t + b ignoring outliers"""
    t, x = np.asarray(t, np.float64), np.asarray(x, np.float64)
    keep = np.ones(len(t), bool)
    for _ in range(iters):
        a, b = np.polyfit(t[keep], x[keep], 1)
        r = x - (a * t + b)
        sd = max(1.0, np.median(np.abs(r[keep])) * 1.5)
        keep = np.abs(r) < 2.5 * sd
    return a, b


def detect_quad(im, m):
    ys, xs = np.where(m > 0)
    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    H = y1 - y0
    W = x1 - x0
    # side edges: rows in the straight part (below the arch)
    rows = np.arange(int(y0 + 0.75 * W), int(y1 - 0.03 * H), 4)
    L, R, T = [], [], []
    for y in rows:
        c = np.where(m[y] > 0)[0]
        if len(c) > 0.5 * W:
            L.append(c.min()); R.append(c.max()); T.append(y)
    aL, bL = robust_line(T, L)
    aR, bR = robust_line(T, R)
    # bottom edge: columns in the middle 80 %
    cols = np.arange(int(x0 + 0.1 * W), int(x1 - 0.1 * W), 4)
    B = [np.where(m[:, x] > 0)[0].max() for x in cols]
    aB, bB = 0.0, float(np.percentile(B, 60))  # photos are level: keep the sill horizontal

    def side(a, b, yy):
        return a * yy + b
    # top: horizontal line parallel to bottom through the arch apex
    xm = (x0 + x1) / 2
    cc = slice(int(xm - 0.1 * W), int(xm + 0.1 * W))
    apex = float(np.median([np.where(m[:, x] > 0)[0].min() for x in range(cc.start, cc.stop, 3)]))
    top_b = apex - aB * xm

    def inter(a, b, s, c):  # x = a*y + b ; y = s*x + c
        y = (s * b + c) / (1 - s * a)
        return [a * y + b, y]
    tl, tr = inter(aL, bL, aB, top_b), inter(aR, bR, aB, top_b)
    bl, br = inter(aL, bL, aB, bB), inter(aR, bR, aB, bB)
    return np.float32([tl, tr, br, bl])


def arch_mask(mw, spring_override=None):
    """warped glass mask -> clean arch mask: rectangle below the springing, half-ellipse above it
    (full width, apex at the top edge). The springing height is fitted to the detected glass."""
    h, w = mw.shape
    top = int(w * 0.8)
    ref = mw[:top] > 0
    yy, xx = np.mgrid[0:top, 0:w]
    best, spring = -1, w // 2
    for s in range(int(0.30 * w), int(0.72 * w), 2):
        e = (((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - s) / s) ** 2 <= 1) | (yy >= s)
        iou = (e & ref).sum() / max(1, (e | ref).sum())
        if iou > best:
            best, spring = iou, s
    if spring_override:
        spring = spring_override
    yy, xx = np.mgrid[0:h, 0:w]
    out = ((((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - spring) / spring) ** 2 <= 1) | (yy >= spring))
    return out.astype(np.uint8) * 255, spring


def find_bars(im, valid):
    """rows that are grey mullion bars (low saturation, mid value, uniform across the width)."""
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32)
    h, w = im.shape[:2]
    c0, c1 = int(w * 0.12), int(w * 0.88)
    s = hsv[:, c0:c1, 1] / 255
    v = hsv[:, c0:c1, 2] / 255
    is_bar = (np.median(s, axis=1) < 0.25) & (v.std(axis=1) < 0.09) & (np.median(v, axis=1) > 0.12) \
        & (np.median(v, axis=1) < 0.75)
    is_bar = cv2.morphologyEx(is_bar.astype(np.uint8)[:, None], cv2.MORPH_CLOSE, np.ones((5, 1), np.uint8))[:, 0]
    bars, y = [], 0
    while y < h:
        if is_bar[y]:
            e = y
            while e < h and is_bar[e]:
                e += 1
            if 6 <= e - y <= 0.03 * h and 0.05 * h < y < 0.97 * h:
                bars.append((y, e))
            y = e
        else:
            y += 1
    return bars


def even_panels(im, mask, bars, max_gain=2.2):
    h, w = im.shape[:2]
    edges = [0] + [v for b in bars for v in b] + [h]
    panels = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]
    lum = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    stat = []
    for a, b in panels:
        v = lum[a:b][mask[a:b] > 0]
        stat.append(np.percentile(v, 92) if len(v) else 200)
    target = float(np.max(stat)) if len(stat) < 3 else float(np.sort(stat)[-2])
    target = min(target, 235)
    gains = [float(np.clip(target / max(s, 1), 0.85, max_gain)) for s in stat]
    grow = np.ones(h, np.float32)
    for (a, b), g in zip(panels, gains):
        grow[a:b] = g
    grow = cv2.GaussianBlur(grow[:, None], (1, 0), sigmaX=0.1, sigmaY=2)[:, 0] if False else grow
    f = (im.astype(np.float32) / 255) ** 2.2
    f *= (grow[:, None, None] ** 2.2)
    # soft shoulder so boosted highlights do not clip flat
    f = np.where(f > 0.8, 0.8 + (1 - np.exp(-(f - 0.8) / 0.2)) * 0.2, f)
    out = (np.clip(f, 0, 1) ** (1 / 2.2) * 255 + 0.5).astype(np.uint8)
    return out, panels, gains, stat


PAD = 60  # margin (output px) of the "padded" rectification used to refine edges by eye


def padded(im, quad, ow, oh):
    """warp the auto quad with a PAD margin all round; returns image and homography src->padded"""
    dst = np.float32([[PAD, PAD], [PAD + ow, PAD], [PAD + ow, PAD + oh], [PAD, PAD + oh]])
    H = cv2.getPerspectiveTransform(np.float32(quad), dst)
    k = 2
    S = np.diag([k, k, 1.0])
    big = cv2.warpPerspective(im, S @ H, ((ow + 2 * PAD) * k, (oh + 2 * PAD) * k), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 0, 255))
    return cv2.resize(big, (ow + 2 * PAD, oh + 2 * PAD), interpolation=cv2.INTER_AREA), H


def diag(pad, path, ow, oh):
    """edge-inspection composite of the padded warp: 3x crops of the apex, both side edges just
    below the springing, and both bottom corners; grid every 10 px labelled in padded px"""
    Z = 3

    def crop(x0, y0, w, h):
        x0, y0 = int(max(0, x0)), int(max(0, y0))
        c = pad[y0:y0 + h, x0:x0 + w]
        c = cv2.resize(c, None, fx=Z, fy=Z, interpolation=cv2.INTER_CUBIC)
        for X in range((x0 // 10 + 1) * 10, x0 + w, 10):
            px = (X - x0) * Z
            cv2.line(c, (px, 0), (px, c.shape[0]), (255, 255, 0), 1)
            if X % 20 == 0:
                cv2.putText(c, str(X), (px + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        for Y in range((y0 // 10 + 1) * 10, y0 + h, 10):
            py = (Y - y0) * Z
            cv2.line(c, (0, py), (c.shape[1], py), (255, 255, 0), 1)
            if Y % 20 == 0:
                cv2.putText(c, str(Y), (2, py - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        out = np.zeros((150 * Z, 200 * Z, 3), np.uint8)
        out[:c.shape[0], :c.shape[1]] = c[:150 * Z, :200 * Z]
        return cv2.copyMakeBorder(out, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    ya = PAD + int(0.8 * ow)
    cx = PAD + ow // 2
    r1 = np.hstack([crop(PAD - 50, ya, 200, 150), crop(cx - 100, PAD - 60, 200, 150), crop(PAD + ow - 150, ya, 200, 150)])
    r2 = np.hstack([crop(PAD - 50, PAD + oh - 110, 200, 150), crop(cx - 100, PAD + oh - 110, 200, 150),
                    crop(PAD + ow - 150, PAD + oh - 110, 200, 150)])
    ym = PAD + int(0.62 * oh)
    rm = np.hstack([crop(PAD - 50, ym, 200, 150), crop(cx - 100, ym, 200, 150), crop(PAD + ow - 150, ym, 200, 150)])
    cv2.imwrite(path, np.vstack([r1, rm, r2]))


def straighten(im, m, H, quad, oh, opt):
    """Final rectification from glass edges read off the padded warp (diag image, padded px):
    opt['L'], opt['R'] = [(x, y), ...] points down the left / right outer lead line (polyline, so a
    slightly bowed edge of these tall stitched phone photos comes out straight),
    opt['top'] = y of the arch apex, opt['bot'] = (y at left, y at right) of the bottom lead line."""
    def edge(pts):
        pts = sorted(pts, key=lambda p: p[1])
        ys = np.array([p[1] for p in pts], np.float64); xs = np.array([p[0] for p in pts], np.float64)

        def f(y):
            x = np.interp(y, ys, xs)
            lo, hi = y < ys[0], y > ys[-1]
            x = np.where(lo, xs[0] + (y - ys[0]) * (xs[1] - xs[0]) / (ys[1] - ys[0]), x)
            x = np.where(hi, xs[-1] + (y - ys[-1]) * (xs[-1] - xs[-2]) / (ys[-1] - ys[-2]), x)
            return x
        return f
    fl, fr = edge(opt['L']), edge(opt['R'])
    yt = opt['top']; ybl, ybr = opt['bot']
    yy = np.linspace(yt, (ybl + ybr) / 2, 50)
    wpad = float(np.mean(fr(yy) - fl(yy)))
    hpad = (ybl + ybr) / 2 - yt
    r = lib.quad_size(quad)[1] / oh            # source px per padded px
    OH = int(min(MAX_H, round(hpad * r)))
    OW = int(round(OH * wpad / hpad))
    k = 2
    v, u = np.mgrid[0:OH * k, 0:OW * k].astype(np.float64)
    u = (u + 0.5) / (OW * k); v = (v + 0.5) / (OH * k)
    y = yt + v * ((ybl + (ybr - ybl) * u) - yt)
    x = fl(y) + u * (fr(y) - fl(y))
    Hi = np.linalg.inv(H)
    d = Hi[2, 0] * x + Hi[2, 1] * y + Hi[2, 2]
    mx = ((Hi[0, 0] * x + Hi[0, 1] * y + Hi[0, 2]) / d).astype(np.float32)
    my = ((Hi[1, 0] * x + Hi[1, 1] * y + Hi[1, 2]) / d).astype(np.float32)
    sc = hpad * r / (OH * k)
    src = cv2.GaussianBlur(im, (0, 0), max(0.01, 0.35 * sc)) if sc > 1.1 else im
    big = cv2.remap(src, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    out = cv2.resize(big, (OW, OH), interpolation=cv2.INTER_AREA)
    mw = cv2.resize(cv2.remap(m, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT), (OW, OH),
                    interpolation=cv2.INTER_AREA)
    return out, mw


def process(name, debug=None):
    src = SOURCES[name]
    opt = OPT.get(name, {})
    im = lib.load(src)
    m = glass_mask(im)
    quad = np.float32(opt['quad']) if 'quad' in opt else detect_quad(im, m)
    w, h = lib.quad_size(quad)
    ow, oh = lib.fit_size(w, h, max_h=MAX_H)
    if debug or 'L' in opt:
        pad, H = padded(im, quad, ow, oh)
        if debug:
            cv2.imwrite(os.path.join(debug, f"pad_{name}.jpg"), pad)
            diag(pad, os.path.join(debug, f"diag_{name}.jpg"), ow, oh)
    if 'L' in opt:
        out, mw = straighten(im, m, H, quad, oh, opt)
        ow, oh = out.shape[1], out.shape[0]
    else:
        out = lib.warp(im, quad, ow, oh)
        mw = lib.warp(cv2.cvtColor(m, cv2.COLOR_GRAY2BGR), quad, ow, oh)[..., 0]
    mw = (mw > 127).astype(np.uint8) * 255
    am, spring = arch_mask(mw, opt.get("spring"))
    e = opt.get("erode", 2)
    if e:
        am = cv2.erode(am, np.ones((2 * e + 1, 2 * e + 1), np.uint8), borderValue=255)
    if name in RETOUCH:
        out = RETOUCH[name](out, am)
        if name == 'daniel':
            import daniel_guide            # pass 2: lion / floor colour from the night photo IMG_7972
            out2, ok = daniel_guide.apply(out)
            out2[am == 0] = out[am == 0]
            out = out2
    bars = find_bars(out, am)
    out, panels, gains, stat = even_panels(out, am, bars, opt.get("max_gain", 2.2))
    raw_top = out[:int(ow * 0.7)].copy()
    out[am == 0] = 0
    lib.save(f"windows/{name}.jpg", out)
    if debug:
        d = cv2.resize(raw_top, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        for sp, col in ((spring, (0, 255, 0)), (ow // 2, (0, 0, 255))):
            cv2.ellipse(d, (ow - 1, 2 * sp), (ow, 2 * sp), 0, 180, 360, col, 1)
        cv2.imwrite(os.path.join(debug, f"arch_{name}.jpg"), d)
    print(name, out.shape[1], out.shape[0], "spring", spring, "bars", bars,
          "p92", [int(s) for s in stat], "gains", [round(g, 2) for g in gains])
    note = ("rectified to the glass only (outer lead line of the wheat border), black outside the arch, "
            f"mullion bars kept; panel exposure gains {[round(g, 2) for g in gains]}. ")
    return lib.entry(f"windows/{name}.jpg", out, "reference/" + src, opt.get("quality", "good"),
                     note + opt.get("note", ""))


def _lab(bgr8):
    return cv2.cvtColor(bgr8.astype(np.float32) / 255.0, cv2.COLOR_BGR2Lab)


def _unlab(lab):
    return np.clip(cv2.cvtColor(lab.astype(np.float32), cv2.COLOR_Lab2BGR) * 255.0, 0, 255)


def _poly(shape, pts, feather):
    m = np.zeros(shape[:2], np.uint8)
    cv2.fillPoly(m, [np.int32(pts)], 255)
    m = m.astype(np.float32) / 255
    return cv2.GaussianBlur(m, (0, 0), feather) if feather else m


def _ab_lut(lab, mask):
    """median (a, b) of the reference pixels for every L bin (0..100), gaps interpolated, smoothed"""
    L = np.clip(lab[..., 0][mask], 0, 100).astype(np.int32)
    A, B = lab[..., 1][mask], lab[..., 2][mask]
    lut = np.full((101, 2), np.nan, np.float32)
    for v in range(101):
        k = np.abs(L - v) <= 2
        if k.sum() >= 30:
            lut[v] = (np.median(A[k]), np.median(B[k]))
    idx = np.arange(101)
    for c in range(2):
        ok = ~np.isnan(lut[:, c])
        lut[:, c] = np.interp(idx, idx[ok], lut[ok, c])
        lut[:, c] = np.convolve(np.pad(lut[:, c], 4, mode='edge'), np.ones(9) / 9, 'valid')
    return lut


def _match_L(L, mask, ref, strength=1.0):
    """quantile-match L inside mask to the reference L values"""
    src = L[mask]
    q = np.linspace(0, 100, 41)
    xs, ys = np.percentile(src, q), np.percentile(ref, q)
    xs = np.maximum.accumulate(xs + np.arange(len(xs)) * 1e-4)
    return L + strength * (np.interp(L, xs, ys) - L)


def retouch_daniel(img, am):
    """IMG_1932 was taken with the lower two thirds of the window in outside shade: below a soft
    edge at y~985 the glass is dim, greyed by a reflection of the lit interior, Daniel's lower robe
    is a dark smudge and the pale floor tiles show the trees outside. Retouch (pixels only):
      1. reflection: the lead lines should be black; their local brightness (min filter) is the
         additive veil, subtracted per channel;
      2. shade: a smooth gain brings the local brightness envelope up to that of the lit panel;
      3. colour: the shaded pieces get their colour back from lit pieces of the same glass
         (robe <- lit robe, wheat border <- lit border, lions/ground <- lit lions/ground) with an
         L-indexed colour table, so lead lines (dark) stay dark and in place;
      4. floor tiles under Daniel's feet: outside scene flattened to pale cream glass, lead lines
         re-drawn from the photo (black-hat).
    Guide for the design and piece colours: reference/batch3/IMG_7972.jpg (night, no glare).
    Coordinates below are output pixels of the 436 x 2048 rectification."""
    h, w = img.shape[:2]
    sx, sy = w / 436.0, h / 2048.0

    def P(pts):
        return [(x * sx, y * sy) for x, y in pts]
    d = img.astype(np.float32)
    bars = find_bars(img, am)
    valid = (am > 0).astype(np.float32)
    for a, b in bars:
        valid[max(0, a - 9):b + 5] = 0
    b1 = bars[0][0] if bars else int(783 * sy)          # first mullion bar
    b2 = bars[1][0] if len(bars) > 1 else int(1405 * sy)

    def nblur(x, sig):
        v = valid[..., None] if x.ndim == 3 else valid
        den = cv2.GaussianBlur(valid, (0, 0), sig) + 1e-4
        return cv2.GaussianBlur(x * v, (0, 0), sig) / (den[..., None] if x.ndim == 3 else den)
    yy = np.arange(h, dtype=np.float32)[:, None] * np.ones((1, w), np.float32)
    sw = np.clip((yy - 965 * sy) / (40 * sy), 0, 1)     # shade weight
    lit = slice(int(250 * sy), b1 - 20)                 # rows of the fully lit top panel

    # 1. veil
    t = d.copy(); t[valid == 0] = 255
    mn = cv2.erode(t, np.ones((33, 33), np.uint8)); mn[valid == 0] = 0
    B = nblur(mn, 16)
    b0 = np.median(B[lit].reshape(-1, 3), axis=0)
    a = np.clip(d - np.clip(B - b0, 0, None) * sw[..., None], 0, 255)
    # 2. shade gain
    V = a.max(axis=2); V[valid == 0] = 0
    E = nblur(cv2.dilate(V, np.ones((45, 45), np.uint8)), 22)
    g = np.clip(np.median(E[lit]) / np.maximum(E, 1), 1, 4.0)
    g = (1 + (g - 1) * sw) * valid + (1 - valid)
    c = np.clip(a * g[..., None], 0, 255)

    # 3. colour from lit pieces of the same glass
    lab = _lab(c)
    L = lab[..., 0].copy()
    inside = valid > 0
    xx = np.ones((h, 1), np.float32) * np.arange(w, dtype=np.float32)[None, :]
    border = (xx < 27 * sx) | (xx > 409 * sx)
    robe_w = _poly(img.shape, P([(134, 960), (345, 960), (351, 1035), (353, 1100), (346, 1121),
                                 (281, 1121), (279, 1087), (260, 1065), (252, 1070), (252, 1109),
                                 (215, 1089), (170, 1051), (136, 1020)]), 1.5 * sx)
    tiles_w = _poly(img.shape, P([(172, 1124), (262, 1121), (276, 1150), (302, 1192), (312, 1216),
                                  (250, 1219), (220, 1196), (198, 1160)]), 1.5 * sx)
    # references (lit, same glass)
    lit_robe = (_poly(img.shape, P([(100, 815), (330, 815), (350, 975), (140, 975)]), 0) > 0.5) \
        & (lab[..., 1] > 25)
    lit_robe = cv2.dilate(lit_robe.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0   # + its lead lines
    lit_border = border & inside & (yy > 300 * sy) & (yy < b1 - 10)
    lion_ref = (_poly(img.shape, P([(318, 835), (372, 835), (378, 905), (350, 940), (322, 905)]), 0) > 0.5)
    out = lab.copy()

    def blend(wt, new):
        wt = (wt * sw * valid)[..., None]
        out[:] = out * (1 - wt) + new * wt

    def lut_colour(Ln, ref, k):
        lut = _ab_lut(lab, ref)
        i = np.clip(Ln, 0, 100).astype(np.int32)
        return np.dstack([Ln, lab[..., 1] + k * (lut[i, 0] - lab[..., 1]),
                          lab[..., 2] + k * (lut[i, 1] - lab[..., 2])])

    # lions, feet, ground: warm tan of the lit lion, chroma fading to 0 in the lead lines
    a0, b0_ = np.median(lab[..., 1][lion_ref]), np.median(lab[..., 2][lion_ref])
    f = np.clip((L - 12) / 40, 0, 1) * (1 - 0.45 * np.clip((L - 70) / 25, 0, 1))
    Lt = np.clip(L * 1.06, 0, 97)
    tan = np.dstack([Lt, lab[..., 1] + 0.8 * (a0 * f - lab[..., 1]), lab[..., 2] + 0.8 * (b0_ * f - lab[..., 2])])
    blend(((yy < b2) & ~border).astype(np.float32), tan)
    # robe: clamp the white reflection blob, lift to the lit robe's level, lit-robe colour table
    rm = (robe_w > 0.5) & (sw > 0.9)
    Lr = np.minimum(L, np.percentile(L[rm], 85))
    sc = min(1.7, np.percentile(lab[..., 0][lit_robe], 60) / max(1.0, np.percentile(Lr[rm], 60)))
    blend(robe_w, lut_colour(np.clip(Lr * sc, 0, 100), lit_robe, 0.95))
    # wheat border
    bm = border & inside & (sw > 0.9)
    sc = min(1.6, np.percentile(lab[..., 0][lit_border], 90) / max(1.0, np.percentile(L[bm], 90)))
    blend((border & inside).astype(np.float32), lut_colour(np.clip(L * sc, 0, 100), lit_border, 0.85))
    # 4. floor tiles: flat pale glass + the real lead lines (long thin dark structures only)
    k = max(3, int(9 * sx)) | 1
    L8 = np.clip(L * 2.55, 0, 255).astype(np.uint8)
    bh = cv2.morphologyEx(L8, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    cand = ((bh > 30) & (tiles_w > 0.05)).astype(np.uint8)
    n, lbl, st, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
    line = np.zeros((h, w), np.float32)
    for i in range(1, n):
        if max(st[i, cv2.CC_STAT_WIDTH], st[i, cv2.CC_STAT_HEIGHT]) >= 22 * sx:
            line[lbl == i] = 1
    line = cv2.GaussianBlur(line, (0, 0), 0.8)
    base = cv2.medianBlur(L8, 31).astype(np.float32) / 2.55
    tm = tiles_w > 0.5
    Lt = np.clip(74 + 0.25 * (base - np.mean(base[tm])), 60, 86)
    Lt = Lt * (1 - line) + 10 * line
    ft = np.clip((Lt - 12) / 40, 0, 1) * 0.8
    blend(tiles_w, np.dstack([Lt, a0 * ft, b0_ * ft]))

    res = _unlab(out)
    # bottom ornament panel: only veil + shade gain, plus the saturation the shade took away
    low = ((yy > b2) & inside & ~border).astype(np.float32)[..., None]
    grey = res.mean(axis=2, keepdims=True)
    res = res * (1 - low) + np.clip(grey + (res - grey) * 1.25, 0, 255) * low
    keep = (valid == 0)
    res[keep] = d[keep]
    return np.clip(res + 0.5, 0, 255).astype(np.uint8)


RETOUCH = {'daniel': retouch_daniel}


if __name__ == "__main__":
    args = sys.argv[1:]
    debug = None
    if "--debug" in args:
        i = args.index("--debug"); debug = args[i + 1]; del args[i:i + 2]
    names = args or list(SOURCES)
    entries = [process(n, debug) for n in names]
    if not args:
        lib.write_part("windows", entries)
