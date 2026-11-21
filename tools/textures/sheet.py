"""Labelled contact sheet / grid preview helpers (PIL; ImageMagick here has no Freetype).

usage: sheet.py out.jpg cell_w cell_h cols file1 file2 ...
       sheet.py --grid src.jpg out.jpg [max_side] [x0 y0 x1 y1]   (coordinate grid overlay,
                 labels are in SOURCE pixels; optional crop box in source pixels)
"""
import sys, os
from PIL import Image, ImageDraw, ImageFont, ImageOps

Image.MAX_IMAGE_PIXELS = None


def font(sz):
    for p in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def sheet(out, cw, ch, cols, files, labels=None):
    rows = (len(files) + cols - 1) // cols
    pad, lab = 6, 18
    W = cols * (cw + pad) + pad
    H = rows * (ch + lab + pad) + pad
    canvas = Image.new("RGB", (W, H), (40, 40, 40))
    d = ImageDraw.Draw(canvas)
    f = font(13)
    for i, fp in enumerate(files):
        im = ImageOps.exif_transpose(Image.open(fp)).convert("RGB")
        im.thumbnail((cw, ch), Image.LANCZOS)
        x = pad + (i % cols) * (cw + pad)
        y = pad + (i // cols) * (ch + lab + pad)
        canvas.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
        name = labels[i] if labels else os.path.splitext(os.path.basename(fp))[0]
        d.text((x + 2, y + ch + 2), name, fill=(235, 235, 235), font=f)
    canvas.save(out, quality=88)


def grid(src, out, max_side=1400, box=None):
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    ox = oy = 0
    if box:
        im = im.crop(box)
        ox, oy = box[0], box[1]
    s = max_side / max(im.size)
    sm = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    d = ImageDraw.Draw(sm)
    span = max(im.size)
    step = next(st for st in (10, 20, 50, 100, 200, 500, 1000) if span / st <= 16)
    f = font(12)
    x = (ox // step + 1) * step
    while x < ox + im.width:
        px = (x - ox) * s
        d.line([(px, 0), (px, sm.height)], fill=(0, 255, 255), width=1)
        d.text((px + 2, 2), str(x), fill=(255, 255, 0), font=f)
        d.text((px + 2, sm.height // 2), str(x), fill=(255, 255, 0), font=f)
        x += step
    y = (oy // step + 1) * step
    while y < oy + im.height:
        py = (y - oy) * s
        d.line([(0, py), (sm.width, py)], fill=(0, 255, 255), width=1)
        d.text((2, py + 2), str(y), fill=(255, 255, 0), font=f)
        d.text((sm.width // 2, py + 2), str(y), fill=(255, 255, 0), font=f)
        y += step
    sm.save(out, quality=85)


def grids(out, H, specs):
    """several gridded views side by side. spec = file or file:x0,y0,x1,y1 (source px crop)"""
    import tempfile
    ims = []
    for sp in specs:
        box = None
        if ":" in sp:
            sp, b = sp.rsplit(":", 1)
            box = tuple(int(v) for v in b.split(","))
        t = tempfile.mktemp(suffix=".jpg")
        im = ImageOps.exif_transpose(Image.open(sp))
        bw, bh = (box[2] - box[0], box[3] - box[1]) if box else im.size
        grid(sp, t, int(H * max(bw, bh) / bh), box)
        ims.append(Image.open(t).convert("RGB"))
    W = sum(i.width for i in ims) + 8 * (len(ims) - 1)
    c = Image.new("RGB", (W, max(i.height for i in ims)), (255, 0, 255))
    x = 0
    for i in ims:
        c.paste(i, (x, 0)); x += i.width + 8
    c.save(out, quality=85)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--grids":
        grids(a[1], int(a[2]), a[3:]); sys.exit()
    if a[0] == "--grid":
        ms = int(a[3]) if len(a) > 3 else 1400
        box = tuple(int(v) for v in a[4:8]) if len(a) >= 8 else None
        grid(a[1], a[2], ms, box)
    else:
        sheet(a[0], int(a[1]), int(a[2]), int(a[3]), a[4:])


def corners(src, out, pts, r=160, cell=620):
    """zoomed, gridded neighbourhoods of points (source px) in one image, for exact corner picking."""
    import tempfile
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    tiles = []
    for (x, y) in pts:
        box = (max(0, x - r), max(0, y - r), min(im.width, x + r), min(im.height, y + r))
        t = tempfile.mktemp(suffix=".jpg")
        grid(src, t, cell, box)
        tiles.append(Image.open(t).convert("RGB"))
    c = Image.new("RGB", (sum(t.width for t in tiles) + 6 * len(tiles), max(t.height for t in tiles)), (255, 0, 255))
    x = 0
    for t in tiles:
        c.paste(t, (x, 0)); x += t.width + 6
    c.save(out, quality=88)
