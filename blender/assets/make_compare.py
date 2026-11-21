"""Side-by-sides of reference photo crop (left) and render (right) for the
seating assets -> blender/previews/compare_{pew,bench,lectern}.png.

Plain Python + Pillow (not Blender):  python3 blender/assets/make_compare.py
Run after pew.py, deacon_bench.py and lectern.py have written their cmp_* previews.
"""
import os
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REF = os.path.join(ROOT, "reference")
PREV = os.path.join(ROOT, "blender", "previews")

# name -> (photo, crop box as fractions of the upright photo: x0, y0, x1, y1)
JOBS = {
    "pew": ("icons/MVIMG_20190817_111919.jpg", (0.2865, 0.7737, 0.3998, 1.0)),
    "bench": ("IMG_7910.jpg", (0.3294, 0.6235, 0.6660, 1.0)),
    "lectern": ("IMG_7899.jpg", (0.6855, 0.5682, 1.0, 0.9234)),
}
W, H = 480, 720

for name, (photo, box) in JOBS.items():
    render = os.path.join(PREV, "cmp_%s.png" % name)
    if not os.path.exists(render):
        print("skip", name, "(no render)")
        continue
    im = ImageOps.exif_transpose(Image.open(os.path.join(REF, photo))).convert("RGB")
    w, h = im.size
    left = ImageOps.fit(im.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))), (W, H),
                        Image.LANCZOS)
    right = ImageOps.fit(Image.open(render).convert("RGB"), (W, H), Image.LANCZOS)
    out = Image.new("RGB", (2 * W, H))
    out.paste(left, (0, 0))
    out.paste(right, (W, 0))
    out.save(os.path.join(PREV, "compare_%s.png" % name))
    print("wrote compare_%s.png" % name)
