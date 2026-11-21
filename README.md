# St. Mark's Coptic Orthodox Church — 3D tour

A guided 3D tour of St. Mark's Coptic Orthodox Church in Jersey City, for visitors who have never been inside an Orthodox church. Live at https://st-marks-tour.jeremysleman.workers.dev

## Layout

- `reference/` source photos of the church
- `textures/` icons, windows and wood patterns cut from those photos (`textures/manifest.json`); scripts in `tools/textures/`
- `blender/common.py` every room dimension, in one place
- `blender/assets/*.py` one headless script per asset (room, pews, iconostasis, throne, shrines, icon stands, chandeliers) → `blender/assets/*.blend`
- `blender/assemble.py` builds `blender/church.blend` and renders check views
- `blender/export_web.py` bakes albedo + lightmaps and writes `web/public/church.glb` and `web/public/lm/`
- `web/` the tour (Vite + React + three.js); stops and all text in `web/src/tour.json`
- `docs/tour-text-for-review.md` the tour text for review

## Rebuild

```sh
B=/Applications/Blender.app/Contents/MacOS/Blender
$B -b --python blender/assets/<asset>.py      # after changing an asset
$B -b --python blender/assemble.py -- --no-render
$B -b --python blender/export_web.py          # ~20 min; `quick` / `reuse` for faster passes
cd web && npm install && npm run build && npm run verify
npx wrangler deploy                           # publishes web/dist
```

`npm run dev` serves the tour on http://127.0.0.1:5320. `npm run text` regenerates the review document; `npm run cameras` recomputes stop cameras after a dimension change.
