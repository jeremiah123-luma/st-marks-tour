// Copies the icon, window and pattern textures from ../textures into public/tex and writes
// src/generated/assets.json: which textures exist, and whether public/church.glb is there. The app shows the
// real GLB when it is present and the placeholder room otherwise; a missing texture becomes a labelled panel.
// Runs before `dev` and `build`. TEX_SRC points it at another folder (used to test with sample files).
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { join, extname, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const web = fileURLToPath(new URL('../', import.meta.url));
const src = process.env.TEX_SRC || join(web, '../textures');
const out = join(web, 'public/tex');
const OK = new Set(['.jpg', '.jpeg', '.png', '.webp']);

rmSync(out, { recursive: true, force: true });
const tex = {};
for (const dir of ['icons', 'windows', 'patterns']) {
  const from = join(src, dir);
  if (!existsSync(from)) continue;
  for (const f of readdirSync(from).sort()) {
    if (!OK.has(extname(f).toLowerCase())) continue;
    mkdirSync(join(out, dir), { recursive: true });
    cpSync(join(from, f), join(out, dir, f));
    tex[`${dir}/${basename(f, extname(f))}`] = `${dir}/${f}`;
  }
}
const glb = existsSync(join(web, 'public/church.glb'));
mkdirSync(join(web, 'src/generated'), { recursive: true });
writeFileSync(join(web, 'src/generated/assets.json'), JSON.stringify({ glb, tex }, null, 2) + '\n');
console.log(`sync: ${Object.keys(tex).length} textures, church.glb ${glb ? 'found' : 'not found (placeholder room)'}`);
