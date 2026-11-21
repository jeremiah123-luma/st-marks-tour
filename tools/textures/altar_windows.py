"""Sanctuary windows (backdrop seen through the arch above the iconostasis) -> textures/windows/altar_*.jpg
Same conventions as windows.py: glass only, keystone fixed, black outside the arch, max 2048 px tall.
Quads (TL, TR, BR, BL of the glass's bounding rectangle, source px) were picked by hand with corners.py."""
import cv2
import numpy as np
import lib
import windows

W = {
    "altar_christ": dict(src="windows/IMG_2128.jpg", quad=[(1523, 510), (2422, 510), (2482, 2378), (1448, 2378)], spring=490,
        quality="good", note="Christ enthroned, centre window of the sanctuary wall. In IMG_2128 the three windows sit on one "
        "wall: this tall one in the centre, a small arched window each side, set low (their sills level with this "
        "window's sill, their tops at about 37% of its height); centre-to-centre spacing about 1.2x this window's "
        "width, each small one about 0.37x its height. Shot from below: height may be slightly "
        "compressed."),
    "altar_small_left": dict(src="windows/IMG_2128.jpg", quad=[(527, 1690), (960, 1690), (905, 2372), (487, 2372)], spring=220,
        quality="low", note="small window left of Christ (angel and lion = two of the four living creatures). Separate pane in "
        "its own deep niche; seen obliquely, the right wheat border is hidden by the niche wall, so the crop is not "
        "the full width."),
    "altar_small_right": dict(src="windows/IMG_2128.jpg", quad=[(3020, 1735), (3331, 1735), (3385, 2372), (3030, 2372)], spring=175,
        quality="low", note="small window right of Christ (eagle and ox). Separate pane in its own deep niche; seen obliquely, "
        "the left wheat border and part of the glass are hidden by the niche wall, so the crop is not the full width."),
    "altar_gabriel": dict(src="windows/IMG_2748.jpg", quad=[(38, 245), (832, 245), (840, 3838), (38, 3838)],
        quality="good", note="Archangel Gabriel, full window with two mullion bars and the ornament panel. Photo shows only "
        "this window and its plaster reveal; its place relative to the other sanctuary windows is not visible."),
    "altar_mikhail": dict(src="windows/IMG_2752.jpg", quad=[(43, 150), (1145, 150), (1190, 2706), (25, 2706)],
        quality="ok", note="Archangel Mikhail. The photo ends at the lower wheat border with its corner crosses (a few px "
        "of that border may be missing); nothing below it is in the photo and nothing was added. Unlike Gabriel it "
        "shows no ornament panel, so it is either a shorter window or the lower part is outside the frame."),
}


def process(name):
    sp = W[name]
    im = lib.load(sp["src"])
    q = sp["quad"]
    w, h = lib.quad_size(q)
    ow, oh = lib.fit_size(w, h, max_h=2048)
    out = lib.warp(im, q, ow, oh)
    m = lib.warp(cv2.cvtColor(windows.glass_mask(im), cv2.COLOR_GRAY2BGR), q, ow, oh)[..., 0]
    am, spring = windows.arch_mask((m > 127).astype(np.uint8) * 255, sp.get("spring"))
    out[am == 0] = 0
    lib.save(f"windows/{name}.jpg", out)
    print(name, ow, oh, "spring", spring)
    return lib.entry(f"windows/{name}.jpg", out, "reference/" + sp["src"], sp["quality"],
                     f"glass only, black outside the arch; width:height = 1:{oh / ow:.2f}. " + sp["note"])


if __name__ == "__main__":
    lib.write_part("altar_windows", [process(n) for n in W])
