# St. Mark church tour: build spec

A web 3D tour of the inside of a Coptic Orthodox church, for people who know
little about it. They move between stops and inspect things. Built in Blender,
baked, shown in the browser with react-three-fiber (same approach as
`~/dev/portfolio/studio`, which is the reference for how the web side is done).

Goal for the look: photoreal. Match the reference photos, not a generic church.
The sanctuary behind the iconostasis is NOT shown; curtains stay closed.

## Folders

- `reference/` IMG_78xx = 0.5x overviews (Nov 2026), IMG_48xx = close-ups of the
  left iconostasis, bishop's throne, Mary door curtain.
- `reference/windows/` the stained-glass windows as they are today, straight-on.
- `reference/icons/` older photos (2007, 2019). The icons are still current.
  The WINDOWS in these old photos are the old plain ones; ignore them.
  `PANO_20190107_143123.vr.jpg` is the best single view of the whole nave in
  daylight. `20070525_185906_010.jpg` is a straight-on view of the iconostasis.
- `blender/common.py` dimensions + helpers. Import it; never copy numbers.
- `blender/assets/<name>.py` one script per asset, run headless, saves
  `blender/assets/<name>.blend` and a preview in `blender/previews/`.
- `textures/` icons, windows, patterns (see Texture names).
- `web/` the tour app.

## Rules for Blender scripts

- Run headless: `/Applications/Blender.app/Contents/MacOS/Blender -b --python blender/assets/<name>.py`
  (Blender 5.2). Start with `sys.path.insert(0, <blender dir>)`, `import common`,
  `common.reset_scene()`.
- Do NOT use the `mcp__blender__*` tools. One live Blender is shared and is
  reserved for final assembly.
- Put everything in ONE collection named after the asset (e.g. `Pew`). Asset
  origin = floor centre of the object, facing -Y (toward the congregation) unless
  the brief says otherwise. Apply scale. Real-world metres.
- Scripts must be re-runnable from scratch and deterministic.
- The final scene gets baked and exported to GLB for the web, so: clean UV-able
  meshes, no boolean leftovers, no n-gons with holes. Stay inside the triangle
  budget in your brief. Use instances (linked duplicates) for repeats.
- Materials: Principled BSDF, real PBR values. Look shader nodes up by type,
  not by name. Procedural wood/velvet/brass is fine; icon and window art comes
  from `textures/` via `common.image_material` (it falls back to a flat colour
  if the file is not there yet).
- Check your work by eye: render a preview with `common.render_preview`, open the
  PNG with the Read tool, put it next to the reference photos, fix what is off
  (proportions first, then detail, then material). Repeat until it reads as the
  same object. Keep previews at 960 px and under about 64 samples; several
  agents are rendering on this Mac at once.
- Do not `git commit`. Do not touch files outside your brief.
- Finish with a short report: what was built, tri counts, what you could not
  see in the photos and had to guess.

## Layout (facing the altar)

Rectangle nave, numbers in `common.py`. Dark stained plank ceiling: flat centre,
coved to the side walls, carried on dark arched wood brackets with a gold cross
on each bracket foot. White plaster walls, wood wainscot with white heater
covers. Red carpet everywhere, patterned runner down the centre aisle.

Side walls, front to back, windows alternate with carved wood shrines:

- Left: Abraham window, Annunciation shrine, David, Nativity shrine, Three
  Youths, St Antony shrine, Moses, (no shrine), Daniel, St Mina shrine, door.
- Right: Storm, Pentecost shrine, Samaritan woman, Ascension shrine, Flight to
  Egypt, Resurrection shrine, Lazarus, (no shrine), short Healing window above a
  stair landing with a black iron railing, Abba Abraam shrine, door.

Back wall: centre arched alcove three steps up with dark double doors, a copper
St. Mark relief above them, a canopied icon stand each side of the alcove
(Theotokos on the left, Christ on the right as you face the altar), a wood door
near each corner with a red EXIT sign.

Front: raised chorus platform (red carpet), deacon benches facing each other on
both sides, two inlaid lecterns, the carved light-oak bishop's throne in the
front-left corner against the iconostasis.

Iconostasis (full width, dark carved wood), left to right:
triptych St Mark / Archangel Mikhail / Annunciation, left door (burgundy velvet
curtain embroidered with St Mary, TV above), Theotokos icon, centre royal door
(burgundy curtain with Christ), Christ icon, right door (curtain, TV above),
triptych John the Baptist / St George / St Mina. Background panels: cross-and-
star marquetry on the outer thirds, turned-bead lattice on the centre third.
Top row: 6 apostle icons in round arches, Last Supper panel in the centre, 6
more apostles, a red glass lamp hanging in front of each. Above the centre: a
scalloped (multifoil) arch opening holding a crucifix flanked by St Mary and St
John, set in vertical wood panelling that runs up to the ceiling.

Lighting: one very large shallow crystal dome chandelier over the chorus, a row
of big tiered crystal chandeliers down the centre, smaller tiered ones down
each side (see IMG_7905, IMG_7928, the PANO).

## Texture names

`textures/icons/<name>.jpg` (rectified, cropped to the painted panel):
`mark, mikhail, annunciation_panel, theotokos, christ, john_baptist, george,
mina_panel` (iconostasis lower row), `apostle_01..12`, `last_supper`,
`crucifix`, `throne_christ`, shrine icons `annunciation, nativity, antony, mina,
abraam, pentecost, ascension, resurrection`, curtains `curtain_mary,
curtain_christ`, `stmark_relief`.

`textures/windows/<name>.jpg`: `abraham, david, three_youths, moses, daniel,
storm, samaritan, egypt, lazarus, healing`.

`textures/patterns/`: `marquetry_cross.jpg`, `bead_lattice.jpg`, `runner.jpg`,
`carpet_red.jpg`, `pew_inlay.jpg` (tileable where it makes sense).

`textures/manifest.json` lists every file with its pixel size and source photo.
