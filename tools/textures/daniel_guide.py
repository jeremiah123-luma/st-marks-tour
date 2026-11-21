"""Second retouch pass for windows/daniel.jpg: colour of the shaded lions / floor from the night photo
reference/batch3/IMG_7972.jpg (no glare), registered to the texture (SIFT, then ECC on the lead lines).
Lightness and lead lines stay from the daylight photo; only chroma (and, on the pale floor tiles where the
daylight photo shows the trees outside, lightness too) comes from the guide, rescaled to daylight levels."""
import cv2
import numpy as np
import lib
import icons


def lines(im, dark):
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    m = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT if dark else cv2.MORPH_TOPHAT, k).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 2.0)
    return m / (m.max() + 1e-3)


def apply(out, debug=None):
    h, w = out.shape[:2]
    g = lib.load("batch3/IMG_7972.jpg")[:, 1300:3100]
    H, inl = icons.register(g, out, min_inliers=12, scale_to=2400)
    if H is None:
        print("daniel guide: registration failed, pass skipped")
        return out, False
    G, valid = icons.warp_to(g, H, (w, h))
    # SIFT matches sit mostly in the ornament panel, so the fit drifts sideways in the middle panel:
    # search the horizontal scale/offset (and a small vertical shift) that best overlays the lead lines
    ya, yb = int(0.49 * h), int(0.68 * h)
    A0 = lines(out, True)[ya:yb]
    B0 = lines(G, False)
    best = (-1, None)
    for xa in range(-24, 28, 4):
        for xb in range(412, 464, 4):
            for dy in (-8, -4, 0, 4, 8):
                A = np.float64([[w / (xb - xa + 1.0), 0, -xa * w / (xb - xa + 1.0)], [0, 1, dy], [0, 0, 1]])
                Bw = cv2.warpPerspective(B0, A, (w, h))[ya:yb]
                c = float((A0 * Bw).sum() / (np.linalg.norm(A0) * np.linalg.norm(Bw) + 1e-6))
                if c > best[0]:
                    best = (c, A, xa, xb, dy)
    print("daniel guide: x fit", best[2:], round(best[0], 3))
    H = best[1] @ H
    G, valid = icons.warp_to(g, H, (w, h))
    y0, y1 = int(0.40 * h), int(0.70 * h)
    # refine on the lead lines of the middle of the window
    try:
        a = lines(out, True)[y0:y1]
        b = lines(G, False)[y0:y1]
        W = np.eye(3, dtype=np.float32)
        crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6)
        cc, W = cv2.findTransformECC(a, b, W, cv2.MOTION_HOMOGRAPHY, crit, None, 15)
        T = np.float64([[1, 0, 0], [0, 1, y0], [0, 0, 1]])
        Wf = T @ np.linalg.inv(W.astype(np.float64)) @ np.linalg.inv(T)
        G2, valid2 = icons.warp_to(g, Wf @ H, (w, h))
        print("daniel guide: ECC", round(float(cc), 3))
        if cc > 0.3:
            G, valid = G2, valid2
    except cv2.error as e:
        print("daniel guide: ECC failed", str(e)[:80])
    lo = cv2.cvtColor(out, cv2.COLOR_BGR2LAB).astype(np.float32)
    lg = cv2.cvtColor(G, cv2.COLOR_BGR2LAB).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    sx, sy = w / 436.0, h / 2048.0
    region = (yy > 985 * sy) & (yy < 1400 * sy) & (xx > 30 * sx) & (xx < 406 * sx) & (valid > 0)
    bar = (yy > 1203 * sy) & (yy < 1214 * sy)          # thin horizontal saddle bar
    red = (lo[..., 1] - 128 > 28)                      # the rebuilt red robe stays
    red = cv2.dilate(red.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    m = (region & ~red & ~bar).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 3.0)
    # chroma from the guide, boosted to the saturation of the lit lion at the top of the panel
    ga = cv2.GaussianBlur(lg[..., 1] - 128, (0, 0), 2.5)
    gb = cv2.GaussianBlur(lg[..., 2] - 128, (0, 0), 2.5)
    k = 1.7
    Lo = lo[..., 0]
    f = np.clip((Lo - 25) / 60, 0, 1)                  # lead lines stay neutral/dark
    new = lo.copy()
    new[..., 1] = 128 + ga * k * f
    new[..., 2] = 128 + gb * k * f
    # floor tiles (cream / brown checker) under Daniel's feet: lightness from the guide as well
    tiles = cv2.fillPoly(np.zeros((h, w), np.uint8), [np.int32([(172 * sx, 1124 * sy), (262 * sx, 1121 * sy),
                         (276 * sx, 1150 * sy), (302 * sx, 1192 * sy), (312 * sx, 1216 * sy), (250 * sx, 1219 * sy),
                         (220 * sx, 1196 * sy), (198 * sx, 1160 * sy)])], 255)
    tm = cv2.GaussianBlur(tiles.astype(np.float32) / 255, (0, 0), 2.0) * (valid > 0)
    Lg = lg[..., 0]
    r = region & (tiles == 0) & ~red
    gain = np.percentile(Lo[r], 80) / max(1.0, np.percentile(Lg[r], 80))
    new[..., 0] = Lo * (1 - tm) + np.clip(Lg * gain, 0, 240) * tm
    res = lo * (1 - m[..., None]) + new * m[..., None]
    res = cv2.cvtColor(np.clip(res, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)
    if debug:
        cv2.imwrite(debug, np.hstack([out[int(.33 * h):int(.72 * h)], G[int(.33 * h):int(.72 * h)], res[int(.33 * h):int(.72 * h)]]))
    return res, True
