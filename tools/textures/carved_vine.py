"""Carved vine-and-leaf scrollwork of the iconostasis top row -> tileable strip.

Source: reference/batch3/IMG_7959.jpg, the pierced panel between St Thomas and
St Matthew (shot nearly square-on, evenly lit). The scroll section of the panel
is cropped, its lighting flattened, and mirrored 2 x 2 so it tiles seamlessly.

Out: textures/patterns/carved_vine.jpg         colour, 2 x 2 mirrored tile
     textures/patterns/carved_vine_height.jpg  height estimate (dark recess = low)

Real size of one output tile: 0.28 m wide x 0.80 m tall (the source panel
opening is about 0.14 m wide).

Run: .venv/bin/python tools/textures/carved_vine.py
"""
import os

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "reference", "batch3", "IMG_7959.jpg")
OUT = os.path.join(ROOT, "textures", "patterns")
# panel opening, scroll section (three leaf roundels), in full-res pixels of the
# upright 4032 x 3024 photo: top-left, top-right, bottom-right, bottom-left
QUAD = np.float32([[1624, 948], [1915, 948], [1919, 1822], [1620, 1822]])
HALF_W, HALF_H = 384, 1100


def main():
    img = cv2.imread(SRC, cv2.IMREAD_COLOR)   # OpenCV applies the EXIF rotation
    assert img is not None and img.shape[1] > img.shape[0], "expected the upright landscape photo"
    dst = np.float32([[0, 0], [HALF_W, 0], [HALF_W, HALF_H], [0, HALF_H]])
    tile = cv2.warpPerspective(img, cv2.getPerspectiveTransform(QUAD, dst), (HALF_W, HALF_H),
                               flags=cv2.INTER_LANCZOS4).astype(np.float32) / 255.0
    # flatten the slow lighting gradient, keep the carving's own light and shade
    lum = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
    low = cv2.GaussianBlur(lum, (0, 0), 90)
    tile = np.clip(tile * (low.mean() / np.maximum(low, 1e-3))[..., None], 0, 1)
    tile = tile ** 1.3            # deepen the recess a little; the flattening lifts it
    # height: bright, lit wood stands proud; the pierced gaps are deep shadow
    lum = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
    lo, hi = np.percentile(lum, 3), np.percentile(lum, 97)
    height = np.clip((lum - lo) / (hi - lo), 0, 1)
    height = cv2.GaussianBlur(height, (0, 0), 2.0)
    height = np.clip(0.15 + 0.85 * height ** 0.7, 0, 1)

    def mirror(a):
        top = np.concatenate([a, a[:, ::-1]], axis=1)
        return np.concatenate([top, top[::-1]], axis=0)

    os.makedirs(OUT, exist_ok=True)
    cv2.imwrite(os.path.join(OUT, "carved_vine.jpg"), (mirror(tile) * 255).astype(np.uint8),
                [cv2.IMWRITE_JPEG_QUALITY, 92])
    cv2.imwrite(os.path.join(OUT, "carved_vine_height.jpg"), (mirror(height) * 255).astype(np.uint8),
                [cv2.IMWRITE_JPEG_QUALITY, 92])
    print("carved_vine: wrote %dx%d colour + height" % (HALF_W * 2, HALF_H * 2))


if __name__ == "__main__":
    main()
