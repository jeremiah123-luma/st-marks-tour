"""Inlaid lectern (mangalia) -> collection `Lectern`, saved as lectern.blend.

Panelled pedestal on a moulded plinth; two star-lozenge marquetry squares
under a raised bar on the wide faces, three diamond clusters on the narrow
faces; stepped cornice and a sloped reading desk with a rim and book stop.
One mesh object, origin floor centre. The decorated front and the HIGH edge
of the desk face -Y; the reader stands on the +Y side.
Run: Blender -b --python blender/assets/lectern.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common       # noqa: E402
import seat_parts as sp  # noqa: E402

W, D = 0.60, 0.46            # pedestal footprint (x, y)
BODY_TOP = 1.10
DESK_HI, DESK_LO = 1.35, 1.23
TONES = ((0.014, 0.005, 0.003), (0.046, 0.016, 0.008), (0.105, 0.037, 0.016))   # red walnut, IMG_7899


def build():
    coll = common.collection("Lectern")
    d, mi, li = TONES
    wz = sp.wood("LecternWood_Z", d, mi, li, "Z")
    wx = sp.wood("LecternWood_X", d, mi, li, "X", wear=0.6)
    M = dict(field=sp.wood("LecternWood_Field", (0.010, 0.003, 0.002), (0.030, 0.009, 0.004),
                           (0.060, 0.018, 0.008), "Z", wear=0.0, ao_floor=0.85),
             inlay=sp.inlay_material())
    b = sp.B(seed=51)
    hw, hd = W / 2, D / 2

    # moulded plinth
    b.stack([(hw + 0.050, hd + 0.050, 0.0), (hw + 0.050, hd + 0.050, 0.070), (hw + 0.044, hd + 0.044, 0.080),
             (hw + 0.030, hd + 0.030, 0.088), (hw + 0.022, hd + 0.022, 0.104), (hw + 0.010, hd + 0.010, 0.116)],
            0, 0, wx)
    # core + corner posts + rails: every face is a real recessed panel
    core = 0.016
    b.box(-hw + core, hw - core, -hd + core, hd - core, 0.10, BODY_TOP, wz)
    pw = 0.062
    for sx in (-1, 1):
        for sy in (-1, 1):
            xs = sorted((sx * hw, sx * (hw - pw)))
            ys = sorted((sy * hd, sy * (hd - pw)))
            b.box(xs[0], xs[1], ys[0], ys[1], 0.10, BODY_TOP, wz)
    pz0, pz1 = 0.165, BODY_TOP - 0.060
    for z0, z1 in ((0.10, pz0), (pz1, BODY_TOP)):
        b.box(-hw + pw, hw - pw, -hd, -hd + 0.03, z0, z1, wx)
        b.box(-hw + pw, hw - pw, hd - 0.03, hd, z0, z1, wx)
        b.box(-hw, -hw + 0.03, -hd + pw, hd - pw, z0, z1, wx)
        b.box(hw - 0.03, hw, -hd + pw, hd - pw, z0, z1, wx)
    # chamfer moulding round each panel opening
    m = 0.014
    for (O, U, half) in (((0, -hd, 0), (1, 0, 0), hw - pw), ((0, hd, 0), (-1, 0, 0), hw - pw),
                         ((hw, 0, 0), (0, 1, 0), hd - pw), ((-hw, 0, 0), (0, -1, 0), hd - pw)):
        pl = sp.Plane(O, U, (0, 0, 1))
        b.loft([pl.p(-half, pz0), pl.p(half, pz0), pl.p(half, pz1), pl.p(-half, pz1)],
               [pl.p(-half + m, pz0 + m, -core), pl.p(half - m, pz0 + m, -core), pl.p(half - m, pz1 - m, -core),
                pl.p(-half + m, pz1 - m, -core)], wz, outward=True)
    # cornice
    T = BODY_TOP
    b.stack([(hw + 0.004, hd + 0.004, T - 0.004), (hw + 0.010, hd + 0.010, T + 0.010), (hw + 0.022, hd + 0.022, T + 0.018),
             (hw + 0.040, hd + 0.040, T + 0.024), (hw + 0.044, hd + 0.044, T + 0.030), (hw + 0.044, hd + 0.044, T + 0.044),
             (hw + 0.038, hd + 0.038, T + 0.050)], 0, 0, wx)
    b.stack([(hw - 0.035, hd - 0.035, T + 0.048), (hw - 0.035, hd - 0.035, T + 0.080)], 0, 0, wx)
    # desk: tapered box, then the sloped tray with a rim and a book stop on the low (reader) edge
    z0 = T + 0.080
    dy0, dy1 = -hd - 0.045, hd + 0.045
    xw = hw + 0.040
    b.prism([(dy0 + 0.03, z0), (dy1 - 0.03, z0), (dy1, z0 + 0.018), (dy1, DESK_LO - 0.034), (dy0, DESK_HI - 0.034),
             (dy0, z0 + 0.018)], -xw, xw, "x", wx)
    sl = (DESK_LO - DESK_HI) / (dy1 - dy0)
    ey0, ey1, xt = dy0 - 0.040, dy1 + 0.040, hw + 0.095

    def zt(y):
        return DESK_HI + (y - dy0) * sl
    b.prism([(ey0, zt(ey0) - 0.034), (ey1, zt(ey1) - 0.034), (ey1 + 0.004, zt(ey1) - 0.017), (ey1, zt(ey1)),
             (ey0, zt(ey0)), (ey0 - 0.004, zt(ey0) - 0.017)], -xt, xt, "x", wx)
    r = 0.020
    for sx in (-1, 1):                                           # side rims
        xs = sorted((sx * xt, sx * (xt - r)))
        b.prism([(ey0, zt(ey0)), (ey1, zt(ey1)), (ey1, zt(ey1) + 0.014), (ey0, zt(ey0) + 0.014)], xs[0], xs[1], "x", wx)
    b.prism([(ey0, zt(ey0)), (ey0 + r, zt(ey0 + r)), (ey0 + r, zt(ey0 + r) + 0.014), (ey0, zt(ey0) + 0.014)],
            -xt + r, xt - r, "x", wx)
    b.prism([(ey1 - 0.028, zt(ey1 - 0.028)), (ey1, zt(ey1)), (ey1, zt(ey1) + 0.026), (ey1 - 0.022, zt(ey1 - 0.022) + 0.030),
             (ey1 - 0.028, zt(ey1 - 0.028) + 0.024)], -xt + r, xt - r, "x", wx)

    # ---- marquetry ----
    # wide faces (-Y front and +Y back): raised bar on top, then two squares stacked.
    # The squares are the rectified photo (textures/patterns/pew_inlay.jpg); if that
    # file is missing they are built as raised blocks from the generated atlas instead.
    photo = sp.photo_material()
    bar_h = 0.050
    usz = min(W - 2 * pw - 0.036, (pz1 - pz0 - bar_h - 0.060) / 2)
    for sy in (-1, 1):
        y = sy * (hd - core)
        U = (-sy, 0, 0)                                   # U x Z points outward
        base = sp.Plane((0, y, 0), U, (0, 0, 1))
        zc = pz1 - 0.022 - bar_h / 2
        top = [(-usz / 2, zc - bar_h / 2), (usz / 2, zc - bar_h / 2), (usz / 2, zc + bar_h / 2), (-usz / 2, zc + bar_h / 2)]
        b.loft([base.p(u + (0.008 if u > 0 else -0.008), v + (0.008 if v > zc else -0.008), 0) for u, v in top],
               [base.p(u, v, 0.010) for u, v in top], wx, cap_b=True, outward=True)
        z_lo = pz0 + 0.020
        for k in (0, 1):
            pl = sp.Plane((0, y, z_lo + usz / 2 + k * usz), U, (0, 0, 1))
            if photo:
                sp.photo_panel(b, pl, usz, photo, depth=-0.002)
            else:
                sp.inlay_unit(b, pl, usz * 0.96, M, wz, relief=0.010, field=False)
    # narrow faces: three stacked clusters of four diamonds
    dsz = 0.250
    for sx in (-1, 1):
        x = sx * (hw - core)
        for k in (-1, 0, 1):
            zc = (pz0 + pz1) / 2 + k * (dsz * 1.08)
            sp.inlay_cluster(b, sp.Plane((x, 0, zc), (0, sx, 0), (0, 0, 1)), dsz, M, wz, relief=0.008)
    return coll, b.finish("Lectern", coll)


if __name__ == "__main__":
    common.reset_scene()
    coll, ob = build()
    print("LECTERN tris:", sp.tri_count(coll))
    common.save("lectern")
    sp.preview("lectern", (-1.55, -2.35, 1.45), (0.0, 0.0, 0.68), lens=45)
    # same angle as IMG_7899 (for compare_lectern.png)
    sp.preview("cmp_lectern", (-0.62, -1.05, 1.36), (0.04, 0.0, 0.80), lens=26, size=(480, 720), samples=40,
               setup=False)
