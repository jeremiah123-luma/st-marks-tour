"""Shared helpers for the texture prep scripts (OpenCV + numpy).

All coordinates are in pixels of the EXIF-oriented source photo (what you see in a viewer).
"""
import os, json
import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF = os.path.join(ROOT, "reference")
TEX = os.path.join(ROOT, "textures")
MANIFEST_PARTS = os.path.join(os.path.dirname(__file__), "_manifest_parts")


def load(rel):
    """Load a reference photo (path relative to reference/), EXIF orientation applied, BGR uint8."""
    p = rel if os.path.isabs(rel) else os.path.join(REF, rel)
    im = cv2.imread(p, cv2.IMREAD_COLOR)  # applies EXIF orientation
    if im is None:
        raise FileNotFoundError(p)
    return im


def save(rel, im, q=92):
    p = os.path.join(TEX, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    cv2.imwrite(p, im, [cv2.IMWRITE_JPEG_QUALITY, q])
    return p


def fit_size(w, h, max_side=None, max_h=None):
    s = 1.0
    if max_side:
        s = min(s, max_side / max(w, h))
    if max_h:
        s = min(s, max_h / h)
    return max(1, int(round(w * s))), max(1, int(round(h * s)))


def quad_size(q):
    """Natural width/height of a quad given TL, TR, BR, BL."""
    q = np.float32(q)
    w = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    h = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    return w, h


def warp(im, quad, out_w, out_h):
    """Perspective-rectify quad (TL, TR, BR, BL) to out_w x out_h."""
    src = np.float32(quad)
    dst = np.float32([[0, 0], [out_w, 0], [out_w, out_h], [0, out_h]])
    M = cv2.getPerspectiveTransform(src, dst)
    sw, sh = quad_size(quad)
    interp = cv2.INTER_AREA if (sw > out_w * 1.3) else cv2.INTER_CUBIC
    if interp == cv2.INTER_AREA:
        # warpPerspective has no true area filter: supersample then shrink
        k = int(min(4, np.ceil(sw / out_w)))
        M2 = cv2.getPerspectiveTransform(src, dst * k)
        big = cv2.warpPerspective(im, M2, (out_w * k, out_h * k), flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_REPLICATE)
        return cv2.resize(big, (out_w, out_h), interpolation=cv2.INTER_AREA)
    return cv2.warpPerspective(im, M, (out_w, out_h), flags=interp, borderMode=cv2.BORDER_REPLICATE)


def rectify(im, quad, max_side=1536, aspect=None):
    """Warp quad to its natural size (optionally forcing width/height aspect), capped at max_side,
    never upscaled beyond the source resolution."""
    w, h = quad_size(quad)
    if aspect:
        w = h * aspect
    ow, oh = fit_size(w, h, max_side=max_side)
    return warp(im, quad, ow, oh)


def wb_gain(im, gains, strength=1.0):
    """Multiply B,G,R by gains (linear-light approximation with gamma 2.2), blended by strength."""
    f = (im.astype(np.float32) / 255.0) ** 2.2
    g = np.array(gains, np.float32)
    g = 1 + (g - 1) * strength
    f = f * g
    return (np.clip(f, 0, 1) ** (1 / 2.2) * 255 + 0.5).astype(np.uint8)


def levels(im, black=0.0, white=1.0, gamma=1.0, sat=1.0):
    f = im.astype(np.float32) / 255.0
    f = np.clip((f - black) / (white - black), 0, 1) ** (1.0 / gamma)
    if sat != 1.0:
        l = f.mean(axis=2, keepdims=True)
        f = np.clip(l + (f - l) * sat, 0, 1)
    return (f * 255 + 0.5).astype(np.uint8)


def unsharp(im, radius=1.2, amount=0.5):
    b = cv2.GaussianBlur(im, (0, 0), radius)
    return cv2.addWeighted(im, 1 + amount, b, -amount, 0)


def make_tileable(im, blend=0.18):
    """Make an image wrap seamlessly by cross-fading its edges with the wrapped opposite side.
    Works best when im is already (close to) one exact period of the pattern."""
    f = im.astype(np.float32)
    h, w = f.shape[:2]
    bw, bh = max(2, int(w * blend)), max(2, int(h * blend))
    # horizontal: output width w - bw
    a = np.linspace(0, 1, bw, dtype=np.float32)[None, :, None]
    left, right = f[:, :bw], f[:, w - bw:]
    f = np.concatenate([right * (1 - a) + left * a, f[:, bw:w - bw]], axis=1)
    a = np.linspace(0, 1, bh, dtype=np.float32)[:, None, None]
    top, bot = f[:bh], f[h - bh:]
    f = np.concatenate([bot * (1 - a) + top * a, f[bh:h - bh]], axis=0)
    return np.clip(f + 0.5, 0, 255).astype(np.uint8)


def flatten_light(im, sigma_frac=0.35, strength=1.0):
    """Remove large-scale lighting gradients (keeps mean colour)."""
    f = im.astype(np.float32) + 1
    s = max(im.shape[:2]) * sigma_frac
    low = cv2.GaussianBlur(f, (0, 0), s, borderType=cv2.BORDER_REFLECT)
    mean = f.reshape(-1, 3).mean(axis=0)
    out = f * ((mean / low) ** strength)
    return np.clip(out - 1 + 0.5, 0, 255).astype(np.uint8)


def write_part(name, entries):
    os.makedirs(MANIFEST_PARTS, exist_ok=True)
    with open(os.path.join(MANIFEST_PARTS, name + ".json"), "w") as f:
        json.dump(entries, f, indent=1)


def entry(rel, im, source, quality, note=""):
    h, w = im.shape[:2]
    return {"path": "textures/" + rel, "width": int(w), "height": int(h), "source": source,
            "quality": quality, "note": note}
