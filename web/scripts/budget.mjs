// Size report for the build, and a check that nothing the page references would 404 on the host.
// The first page (HTML, CSS and the small app chunk) must stay light so the intro shows before the 3D arrives.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const dist = fileURLToPath(new URL('../dist/', import.meta.url));
const gz = (f) => gzipSync(readFileSync(f), { level: 9 }).length;
const kb = (n) => (n / 1024).toFixed(1) + 'KB';
const files = [];
(function walk(d) { for (const f of readdirSync(d)) { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : files.push(p); } })(dist);

const html = readFileSync(join(dist, 'index.html'), 'utf8');
const refs = [...html.matchAll(/(?:src|href)="\.\/([^"]+)"/g)].map((m) => m[1]);
const missing = refs.filter((r) => !existsSync(join(dist, r)));
const code = files.filter((f) => /\.(js|css)$/.test(f));
const three = code.filter((f) => /[\\/]three-/.test(f));
const total = code.reduce((s, f) => s + gz(f), 0);
const tex = files.filter((f) => f.includes('/tex/')).reduce((s, f) => s + statSync(f).size, 0);
const glb = files.filter((f) => f.endsWith('.glb')).reduce((s, f) => s + statSync(f).size, 0);

for (const f of code) console.log(`  ${f.replace(dist, '').padEnd(34)} ${kb(gz(f))} gz`);
console.log(`code (gz): ${kb(total)}  of which three: ${kb(three.reduce((s, f) => s + gz(f), 0))}`);
console.log(`textures: ${(tex / 1048576).toFixed(1)}MB   model: ${glb ? (glb / 1048576).toFixed(1) + 'MB' : 'none (placeholder room)'}`);

const CAP = 420 * 1024; // all code, gzipped: three is about 265KB of it
let bad = false;
if (missing.length) { console.error('index.html references missing files: ' + missing.join(', ')); bad = true; }
if (total > CAP) { console.error(`code is over budget: ${kb(total)} > ${kb(CAP)}`); bad = true; }
if (bad) process.exit(1);
console.log('budget ok');
