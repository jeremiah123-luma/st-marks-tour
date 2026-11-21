// Loads the built tour in headless Chrome and walks it the way a visitor would, at a desktop and a phone
// size: the intro, every stop (Next button and arrow keys), a picture chosen by clicking it in the room and
// by its chip, Esc back to the stop. Fails on any page error, console error or failed request, and saves
// screenshots to web/screenshots/. Run after `npm run build`: `npm run verify`.
// Playwright is not a dependency of this app: it is borrowed from the studio's test install
// (~/.cache/studio-test, PLAYWRIGHT_DIR overrides) and drives the installed Google Chrome.
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const pwDir = process.env.PLAYWRIGHT_DIR || join(homedir(), '.cache/studio-test');
const { chromium } = createRequire(join(pwDir, 'package.json'))('playwright');
const shots = fileURLToPath(new URL('../screenshots/', import.meta.url));
mkdirSync(shots, { recursive: true });

process.env.PORT = process.env.PORT || '5322';
const { server } = await import('./serve.mjs');
const url = `http://127.0.0.1:${process.env.PORT}/`;
const problems = [];
const note = (ok, what) => { console.log((ok ? '  ok   ' : '  FAIL ') + what); if (!ok) problems.push(what); };

let browser;
try {
  browser = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-angle=metal', '--enable-gpu'] });
  for (const [label, opts] of [
    ['desktop', { viewport: { width: 1440, height: 900 } }],
    ['phone', { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true }],
  ]) {
    console.log(label);
    const ctx = await browser.newContext(opts);
    const p = await ctx.newPage();
    const errs = [];
    p.on('pageerror', (e) => errs.push('page error: ' + e.message));
    p.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
    p.on('requestfailed', (r) => errs.push('request failed: ' + r.url()));
    p.on('response', (r) => { if (r.status() >= 400) errs.push(`HTTP ${r.status()}: ${r.url()}`); });
    const settle = async () => { await p.waitForTimeout(150); await p.waitForFunction(() => !window.__tourMoving, null, { timeout: 8000 }); await p.waitForTimeout(350); };
    const shot = (name) => p.screenshot({ path: join(shots, `${label}-${name}.png`) });
    const title = () => p.locator('.card h2').innerText();
    const phone = label === 'phone';

    await p.goto(url);
    await p.waitForSelector('.stage.ready', { timeout: 20000 });
    await p.waitForTimeout(1800);
    await shot('1-intro');
    await p.getByRole('button', { name: 'Begin the tour' }).click();
    await p.waitForTimeout(1100); await settle();
    note((await title()) === 'The entrance', 'begins at the entrance');
    await shot('2-entrance');

    // Next twice, by button then by key
    await p.getByRole('button', { name: 'Next', exact: true }).click(); await settle();
    await p.keyboard.press('ArrowRight'); await settle();
    note((await title()).startsWith('Stained glass: the Old'), 'Next button and right arrow reach stop 3');
    await shot('3-stained-glass');

    // Look around by dragging, and check the view turned
    const before = await p.evaluate(() => window.__tourPoint('Win_three_youths'));
    if (phone) {
      const cdp = await ctx.newCDPSession(p);
      const touch = (type, x, y) => cdp.send('Input.dispatchTouchEvent', { type, touchPoints: type === 'touchEnd' ? [] : [{ x, y }] });
      await touch('touchStart', 200, 240); for (let i = 1; i <= 8; i++) await touch('touchMove', 200 - i * 12, 240); await touch('touchEnd');
    } else {
      await p.mouse.move(700, 300); await p.mouse.down(); await p.mouse.move(560, 300, { steps: 8 }); await p.mouse.up();
    }
    await p.waitForTimeout(300);
    const after = await p.evaluate(() => window.__tourPoint('Win_three_youths'));
    note(Math.abs(after.x - before.x) > 40, `dragging turns the view (${Math.round(before.x)} -> ${Math.round(after.x)} px)`);
    note(await p.locator('.panel').count() === 0, 'a drag does not open a picture');

    // Choose a window by clicking it in the room
    const at = await p.evaluate(() => window.__tourPoint('Win_three_youths'));
    if (phone) await p.touchscreen.tap(at.x, at.y); else { await p.mouse.move(at.x, at.y); await p.waitForTimeout(200); if (!(await p.locator('.hover-label').count())) note(false, 'hover label shows'); await p.mouse.click(at.x, at.y); }
    await p.waitForSelector('.panel'); await settle();
    note((await p.locator('.panel h2').innerText()) === 'The three youths in the furnace', 'clicking a window opens its text');
    await shot('4-inspect-window');
    await p.keyboard.press('ArrowRight'); await settle();
    note((await p.locator('.panel h2').innerText()) === 'Moses', 'right arrow steps to the next window');
    await p.keyboard.press('Escape'); await settle();
    note(await p.locator('.panel').count() === 0 && (await title()).startsWith('Stained glass'), 'Esc returns to the stop');

    // The stop list, then the iconostasis and one of its icons by chip
    await p.getByRole('button', { name: /^Stops/ }).click();
    await p.getByRole('button', { name: /The iconostasis$/ }).click(); await settle();
    note((await title()) === 'The iconostasis', 'the stop list jumps to a stop');
    await shot('5-iconostasis');
    await p.locator('.chip', { hasText: 'The Last Supper' }).click(); await p.waitForSelector('.panel'); await settle();
    await shot('6-inspect-icon');
    await p.getByRole('button', { name: 'Close and return to the stop' }).click(); await settle();

    // Every stop opens, has text, and its listed pictures exist
    const n = await p.evaluate(() => document.querySelector('.stops-btn .num').textContent.split('/')[1].trim());
    await p.getByRole('button', { name: /^Stops/ }).click(); await p.locator('.list li button').first().click(); await settle();
    let seen = 1;
    for (let i = 1; i < Number(n); i++) { await p.keyboard.press('ArrowRight'); await settle(); if ((await p.locator('.card .body').innerText()).length > 60) seen++; }
    note(seen === Number(n), `all ${n} stops open with text`);
    await shot('7-last-stop');
    note(await p.getByRole('button', { name: 'Next', exact: true }).isDisabled(), 'Next is disabled at the last stop');
    note(errs.length === 0, 'no errors or failed requests' + (errs.length ? ': ' + errs.slice(0, 5).join(' | ') : ''));
    await ctx.close();
  }

  // Reduced motion: moves are cuts
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' });
  const p = await ctx.newPage();
  await p.goto(url + '#crucifix'); await p.waitForSelector('.stage.ready');
  await p.getByRole('button', { name: 'Begin the tour' }).click(); await p.waitForTimeout(400);
  note((await p.locator('.card h2').innerText()) === 'The crucifix above', 'a link with #crucifix opens at that stop');
  await p.keyboard.press('ArrowRight'); await p.waitForTimeout(250);
  note(await p.evaluate(() => !window.__tourMoving), 'with reduced motion the camera cuts instead of gliding');
  await ctx.close();
} catch (e) {
  note(false, 'verify stopped: ' + e.message);
} finally {
  await browser?.close();
  server.close();
}
console.log(problems.length ? `\n${problems.length} problem(s)` : '\nverify ok');
process.exit(problems.length ? 1 : 0);
