// Captures every stop exactly as a visitor sees it (the stop card at full strength) to
// web/screenshots/stop-NN-<id>.png, at a desktop size. Run after `npm run build`: `node scripts/stops.mjs`.
// DUMP=1 also prints where the model's furniture and pictures are (Blender coordinates), for framing cameras.
// ONLY=8,12 captures just those stops. Playwright is borrowed from the studio's test install, like verify.mjs.
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const pwDir = process.env.PLAYWRIGHT_DIR || join(homedir(), '.cache/studio-test');
const { chromium } = createRequire(join(pwDir, 'package.json'))('playwright');
const shots = fileURLToPath(new URL('../screenshots/', import.meta.url));
mkdirSync(shots, { recursive: true });
process.env.PORT = process.env.PORT || '5324';
const { server } = await import('./serve.mjs');
const tour = JSON.parse(readFileSync(new URL('../src/tour.json', import.meta.url), 'utf8'));
const only = process.env.ONLY ? process.env.ONLY.split(',').map(Number) : null;

let browser;
try {
  browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=metal', '--enable-gpu'] });
  const p = await (await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' })).newPage();
  p.on('pageerror', (e) => console.log('page error:', e.message));
  await p.goto(`http://127.0.0.1:${process.env.PORT}/`);
  await p.waitForSelector('.stage.ready', { timeout: 30000 });
  await p.waitForFunction(() => window.__tourScene || document.querySelector('.preview-note') !== null || true, null, { timeout: 60000 });
  await p.waitForTimeout(2500);
  await p.getByRole('button', { name: 'Begin the tour' }).click();
  await p.waitForTimeout(1200);
  if (process.env.DUMP) {
    const rows = await p.evaluate(async () => {
      const s = window.__tourScene; if (!s) return ['no model (placeholder room)'];
      const THREE = window.__tourTHREE; const out = [];
      const box = (o) => { let min = [1e9, 1e9, 1e9], max = [-1e9, -1e9, -1e9];
        o.updateWorldMatrix(true, true);
        o.traverse((m) => { if (!m.isMesh) return; const g = m.geometry; if (!g.boundingBox) g.computeBoundingBox();
          const b = g.boundingBox; for (const x of [b.min.x, b.max.x]) for (const y of [b.min.y, b.max.y]) for (const z of [b.min.z, b.max.z]) {
            const e = m.matrixWorld.elements; const w = [e[0] * x + e[4] * y + e[8] * z + e[12], e[1] * x + e[5] * y + e[9] * z + e[13], e[2] * x + e[6] * y + e[10] * z + e[14]];
            for (let i = 0; i < 3; i++) { min[i] = Math.min(min[i], w[i]); max[i] = Math.max(max[i], w[i]); } } });
        return { min, max }; };
      const f = (n) => n.toFixed(2);
      s.traverse((o) => { if (!o.name || o === s) return; if (o.parent !== s && !/^(Icon|Win)_/.test(o.name)) return;
        const b = box(o); if (b.min[0] > 1e8) return;
        // three (x, y, z) -> Blender (x, -z, y)
        out.push(`${o.name.padEnd(30)} x ${f(b.min[0])}..${f(b.max[0])}  y ${f(-b.max[2])}..${f(-b.min[2])}  z ${f(b.min[1])}..${f(b.max[1])}`); });
      return out;
    });
    console.log(rows.join('\n'));
  }
  for (let i = 0; i < tour.stops.length; i++) {
    await p.waitForTimeout(500);
    if (!only || only.includes(i + 1)) await p.screenshot({ path: join(shots, `stop-${String(i + 1).padStart(2, '0')}-${tour.stops[i].id}.png`) });
    await p.keyboard.press('ArrowRight');
  }
} finally {
  await browser?.close();
  server.close();
}
