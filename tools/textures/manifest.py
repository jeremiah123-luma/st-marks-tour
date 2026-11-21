"""Merge tools/textures/_manifest_parts/*.json into textures/manifest.json (sizes re-read from disk)
and build the two contact sheets. Run after windows.py, icons.py, apostles.py, patterns.py."""
import json, os, glob
import cv2
import lib
import sheet

OVERRIDE = {
    "textures/windows/daniel.jpg": ("ok", " RETOUCHED (owner request): source IMG_1932 had the lower two thirds in shade with an "
        "interior reflection. Pass 1: reflection veil subtracted, shade gain, robe / wheat border colour rebuilt from the lit "
        "pieces of the same glass. Pass 2: lion and floor-tile colour taken from the night photo reference/batch3/IMG_7972.jpg "
        "(registered; lightness and lead lines stay from the daylight photo). Lower robe is still blotchy and the lions paler "
        "than the real glass; a straight-on daylight photo with the whole window lit would replace the retouch."),
    "textures/windows/healing.jpg": (None, " Checked against reference/batch3/IMG_7978.jpg: this is the short right-rear window "
        "above the white door (same design: angel in the arch, Christ touching the kneeling man's eyes, one mullion bar)."),
    "textures/windows/moses.jpg": (None, " Owner confirmed the subject is Moses."),
    "textures/patterns/carpet_red.jpg": ("ok", ""),
}


def main():
    entries = []
    for part in ("windows", "altar_windows", "icons", "apostles", "patterns"):
        entries += json.load(open(os.path.join(lib.MANIFEST_PARTS, part + ".json")))
    out = []
    for e in entries:
        f = os.path.join(lib.ROOT, e["path"])
        if not os.path.exists(f):
            continue
        im = cv2.imread(f)
        e["height"], e["width"] = int(im.shape[0]), int(im.shape[1])
        q, n = OVERRIDE.get(e["path"], (None, ""))
        if q:
            e["quality"] = q
        e["note"] = (e.get("note", "") + n).strip()
        out.append(e)
    listed = {e["path"] for e in out}
    for f in sorted(glob.glob(os.path.join(lib.TEX, "*", "*.jpg"))):
        rel = os.path.relpath(f, lib.ROOT)
        if rel not in listed:
            print("NOT IN MANIFEST:", rel)
    json.dump({"files": out}, open(os.path.join(lib.TEX, "manifest.json"), "w"), indent=1, ensure_ascii=False)
    print(len(out), "files in manifest")
    ic = sorted(glob.glob(os.path.join(lib.TEX, "icons", "*.jpg")))
    sheet.sheet(os.path.join(lib.TEX, "_contact_icons.jpg"), 230, 300, 8, ic)
    wn = sorted(glob.glob(os.path.join(lib.TEX, "windows", "*.jpg")))
    sheet.sheet(os.path.join(lib.TEX, "_contact_windows.jpg"), 200, 640, 10, wn)


if __name__ == "__main__":
    main()
