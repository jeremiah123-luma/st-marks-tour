// Writes the camera of every stop into src/tour.json from src/cameras.js, so the positions always follow the
// dimensions. Run after changing dimensions.js, layout.js or cameras.js: `npm run cameras`.
import { readFileSync, writeFileSync } from 'node:fs';
import { CAMERAS } from '../src/cameras.js';

const file = new URL('../src/tour.json', import.meta.url);
const tour = JSON.parse(readFileSync(file, 'utf8'));
const missing = [];
for (const stop of tour.stops) {
  if (CAMERAS[stop.id]) stop.camera = CAMERAS[stop.id]; else missing.push(stop.id);
}
// Keep each camera on one line so the text stays the thing a reader sees in the file
let out = JSON.stringify(tour, null, 2);
out = out.replace(/"(pos|look)": \[\s*([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\s*\]/g, '"$1": [$2, $3, $4]');
out = out.replace(/"items": \[([^\]]*)\]/g, (m, a) => `"items": [${a.split(',').map((s) => s.trim()).filter(Boolean).join(', ')}]`);
writeFileSync(file, out + '\n');
console.log(`cameras written for ${tour.stops.length - missing.length} stops` + (missing.length ? `; no camera for: ${missing.join(', ')}` : ''));
