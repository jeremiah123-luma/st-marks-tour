// Opens the deployed tour in headless Chrome (desktop + phone), checks the real model loaded,
// and saves screenshots to web/screenshots/live-*.png. Usage: node scripts/live-check.mjs [url]
import { createRequire } from 'node:module';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const url = process.argv[2] || 'https://st-marks-tour.jeremysleman.workers.dev/';
const pwDir = process.env.PLAYWRIGHT_DIR || join(homedir(), '.cache/studio-test');
const { chromium } = createRequire(join(pwDir, 'package.json'))('playwright');
const shots = fileURLToPath(new URL('../screenshots/', import.meta.url));

const browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=metal', '--enable-gpu'] });
try {
  for (const [name, vp, mobile] of [['desktop', { width: 1280, height: 800 }, false], ['phone', { width: 390, height: 844 }, true]]) {
    const ctx = await browser.newContext({ viewport: vp, isMobile: mobile, hasTouch: mobile, deviceScaleFactor: mobile ? 2 : 1 });
    const p = await ctx.newPage();
    const errors = [];
    p.on('pageerror', (e) => errors.push(e.message));
    p.on('requestfailed', (r) => errors.push('failed ' + r.url()));
    const t0 = Date.now();
    await p.goto(url);
    await p.waitForSelector('.stage.ready', { timeout: 60000 });
    await p.waitForTimeout(3000);
    await p.screenshot({ path: join(shots, `live-${name}-intro.png`) });
    await p.getByRole('button', { name: 'Begin the tour' }).click();
    await p.waitForTimeout(2500);
    await p.keyboard.press('ArrowRight');
    await p.waitForTimeout(3500);
    const hasModel = await p.evaluate(() => !!window.__tourScene);
    await p.screenshot({ path: join(shots, `live-${name}-stop2.png`) });
    console.log(name, 'ready in', ((Date.now() - t0) / 1000).toFixed(1) + 's', 'model:', hasModel, 'errors:', errors.length ? errors : 'none');
    await ctx.close();
  }
} finally {
  await browser.close();
}
