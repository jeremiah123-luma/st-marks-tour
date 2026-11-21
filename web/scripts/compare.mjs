// Renders the built tour from the same cameras as the Cycles check views (blender/assemble.py), so the web
// picture can be set beside blender/previews/church_*.png, and reports the scene's size and frame rate.
// Run after `npm run build`: `node scripts/compare.mjs`. Writes web/screenshots/compare-*.png.
// Playwright is borrowed from the studio's test install, like verify.mjs.
import { createRequire } from 'node:module';
import { mkdirSync, readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as D from '../src/dimensions.js';

const pwDir = process.env.PLAYWRIGHT_DIR || join(homedir(), '.cache/studio-test');
const { chromium } = createRequire(join(pwDir, 'package.json'))('playwright');
const shots = fileURLToPath(new URL('../screenshots/', import.meta.url));
mkdirSync(shots, { recursive: true });
process.env.PORT = process.env.PORT || '5323';
const { server } = await import('./serve.mjs');

const L = D.NAVE_L, W = D.NAVE_W, RW = 1280, RH = 853;
const vfov = (lens) => (2 * Math.atan((18 / lens) * (RH / RW)) * 180) / Math.PI; // 36 mm sensor, as Blender
const VIEWS = {
  toward_altar: { pos: [0, 1.2, 1.65], look: [0, L, 2.6], fov: vfov(17) },
  iconostasis: { pos: [0, L - 7.5, 1.65], look: [0, L, 2.3], fov: vfov(20) },
  left_wall: { pos: [W / 2 - 1.2, 9.0, 1.6], look: [-W / 2, 13.5, 3.0], fov: vfov(17) },
  toward_back: { pos: [0, L - 4.0, 1.9], look: [0, 0, 2.4], fov: vfov(17) },
  ...(process.env.EXTRA ? JSON.parse(process.env.EXTRA) : {}),
};
let browser;
try {
  browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=metal', '--enable-gpu'] });
  for (const [label, opts] of [['desktop', { viewport: { width: RW, height: RH } }], ['phone', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }]]) {
    const p = await (await browser.newContext(opts)).newPage();
    p.on('pageerror', (e) => console.log('page error:', e.message));
    p.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('console:', m.text().slice(0, 300)); });
    const t0 = Date.now();
    await p.goto(`http://127.0.0.1:${process.env.PORT}/`);
    await p.waitForSelector('.stage.ready', { timeout: 30000 });
    await p.waitForFunction(() => window.__tourScene, null, { timeout: 60000 });
    console.log(label, 'model on screen after', Date.now() - t0, 'ms');
    await p.getByRole('button', { name: 'Begin the tour' }).click();
    await p.waitForTimeout(1500);
    await p.addStyleTag({ content: '.card, .top, header, .stops-btn, .hud, .intro { display: none !important; }' });
    if (label === 'desktop') {
      for (const [name, v] of Object.entries(VIEWS)) {
        await p.evaluate((v) => { window.__tourFixedView = v; window.__tourInvalidate(); }, v);
        await p.waitForTimeout(500);
        await p.locator('canvas').screenshot({ path: join(shots, `compare-${name}.png`) });
      }
      const info = await p.evaluate(() => {
        let tris = 0, meshes = 0; const mats = new Set(), names = [];
        window.__tourScene.traverse((o) => {
          if (/^(Icon|Win)_/.test(o.name)) names.push(o.name);
          if (!o.isMesh) return;
          meshes++; mats.add(o.material.uuid);
          const n = (o.geometry.index ? o.geometry.index.count : o.geometry.attributes.position.count) / 3;
          tris += n * (o.isInstancedMesh ? o.count : 1);
        });
        return { tris, meshes, materials: mats.size, names: names.sort() };
      });
      console.log('scene:', info.tris, 'triangles,', info.meshes, 'draw calls (meshes),', info.materials, 'materials');
      console.log('inspectable:', info.names.join(' '));
    }
    // frame rate: turn the camera a little every frame for 3 seconds
    const fps = await p.evaluate(async () => {
      const v = window.__tourFixedView || { pos: [0, 1.2, 1.65], look: [0, 17.5, 2.6], fov: 60 };
      let n = 0, worst = 0, last = performance.now(); const start = last;
      while (performance.now() - start < 3000) {
        window.__tourFixedView = { ...v, look: [Math.sin(n / 40) * 4, v.look[1], v.look[2]] };
        window.__tourInvalidate();
        await new Promise((r) => requestAnimationFrame(r));
        const now = performance.now(); worst = Math.max(worst, now - last); last = now; n++;
      }
      window.__tourFixedView = v;
      return { fps: Math.round((n * 1000) / (performance.now() - start)), worst: Math.round(worst) };
    });
    console.log(label, 'frame rate:', fps.fps, 'fps (worst frame', fps.worst, 'ms)');
  }
  // every stop as a visitor sees it (STOPS=1): web/screenshots/stop-NN-<id>.png
  if (process.env.STOPS) {
    const tour = JSON.parse(readFileSync(new URL('../src/tour.json', import.meta.url), 'utf8'));
    const p = await (await browser.newContext({ viewport: { width: 960, height: 600 }, reducedMotion: 'reduce' })).newPage();
    await p.goto(`http://127.0.0.1:${process.env.PORT}/`);
    await p.waitForFunction(() => window.__tourScene, null, { timeout: 60000 });
    await p.getByRole('button', { name: 'Begin the tour' }).click();
    await p.waitForTimeout(1200);
    await p.addStyleTag({ content: '.card { opacity: 0.25 !important; }' });
    for (let i = 0; i < tour.stops.length; i++) {
      await p.waitForTimeout(450);
      await p.screenshot({ path: join(shots, `stop-${String(i + 1).padStart(2, '0')}-${tour.stops[i].id}.png`) });
      await p.keyboard.press('ArrowRight');
    }
  }
} finally {
  await browser?.close();
  server.close();
}
