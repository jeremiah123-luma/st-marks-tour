// A stand-in room built from dimensions.js until the real model (public/church.glb) exists: floor, walls,
// ceiling, boxes for the furniture, and a flat panel for every window and icon. A panel shows its real
// texture from ../textures when the file is there, and its name on a plain ground when it is not.
import { useEffect, useMemo, useRef, useState } from 'react';
import { useThree } from '@react-three/fiber';
import { CanvasTexture, SRGBColorSpace, TextureLoader } from 'three';
import * as D from '../dimensions.js';
import * as L from '../layout.js';
import assets from '../generated/assets.json';
import { itemInfo } from './tour.js';
import { register } from './registry.js';

const HW = D.NAVE_W / 2;
const { toThree } = D;
const C = { carpet: '#6e1a1a', runner: '#8a4a2c', wall: '#e9e3d8', dark: '#35200f', wood: '#6a4424', pew: '#472a17', oak: '#b68750', ceiling: '#2b1a0f', velvet: '#5c1322', black: '#0c0b0a' };

// A box given the Blender way: centre [x, y, z] and size [along x, along y, along z]
function B({ at, size, color, rough = 0.85, ...rest }) {
  return (
    <mesh position={toThree(at)} {...rest}>
      <boxGeometry args={[size[0], size[2], size[1]]} />
      <meshStandardMaterial color={color} roughness={rough} />
    </mesh>
  );
}

const ROT = { left: Math.PI / 2, right: -Math.PI / 2, back: Math.PI, front: 0 };
function labelTexture(text, w, h, glass) {
  const c = document.createElement('canvas');
  c.width = 256; c.height = Math.round((256 * h) / w);
  const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 0, c.height);
  grad.addColorStop(0, glass ? '#3d5f95' : '#b48a45'); grad.addColorStop(1, glass ? '#223a66' : '#8a6630');
  g.fillStyle = grad; g.fillRect(0, 0, c.width, c.height);
  g.strokeStyle = 'rgba(255,255,255,.35)'; g.lineWidth = 4; g.strokeRect(8, 8, c.width - 16, c.height - 16);
  g.fillStyle = 'rgba(255,255,255,.92)'; g.textAlign = 'center'; g.textBaseline = 'middle';
  const words = text.split(' '), lines = []; let size = 26;
  g.font = `${size}px Georgia, serif`;
  let line = '';
  for (const wd of words) { const t = line ? line + ' ' + wd : wd; if (g.measureText(t).width > c.width - 40 && line) { lines.push(line); line = wd; } else line = t; }
  lines.push(line);
  lines.forEach((ln, i) => g.fillText(ln, c.width / 2, c.height / 2 + (i - (lines.length - 1) / 2) * size * 1.25));
  const t = new CanvasTexture(c); t.colorSpace = SRGBColorSpace;
  return t;
}

function Picture({ item }) {
  const ref = useRef();
  const invalidate = useThree((s) => s.invalidate);
  const file = item.tex && assets.tex[item.tex];
  const glass = item.name.startsWith('Win_');
  const label = useMemo(() => labelTexture(itemInfo(item.name).title, item.size[0], item.size[1], glass), [item, glass]);
  const [map, setMap] = useState(null);
  useEffect(() => {
    if (!file) return;
    let live = true;
    new TextureLoader().load('./tex/' + file, (t) => { t.colorSpace = SRGBColorSpace; t.anisotropy = 8; if (live) { setMap(t); invalidate(); } }, undefined, () => {});
    return () => { live = false; };
  }, [file, invalidate]);
  useEffect(() => register(ref.current), []);
  const tex = map || label;
  return (
    <mesh ref={ref} name={item.name} position={toThree(item.pos)} rotation-y={ROT[item.face]}>
      <planeGeometry args={item.size} />
      {glass
        ? <meshBasicMaterial key={tex.uuid} map={tex} toneMapped={false} />
        : <meshStandardMaterial key={tex.uuid} map={tex} emissive="#ffffff" emissiveMap={tex} emissiveIntensity={0.28} roughness={0.6} />}
    </mesh>
  );
}

function Pews() {
  const rows = [];
  const cx = D.AISLE_W / 2 + D.PEW_LEN / 2;
  for (let i = 0; i < D.PEW_ROWS; i++) for (const side of [-1, 1]) {
    const y = D.PEW_FIRST_Y + i * D.PEW_PITCH;
    rows.push(<B key={`s${i}${side}`} at={[side * cx, y + 0.24, D.PEW_SEAT_H - 0.03]} size={[D.PEW_LEN, 0.42, 0.06]} color={C.pew} />);
    rows.push(<B key={`b${i}${side}`} at={[side * cx, y, D.PEW_BACK_H / 2]} size={[D.PEW_LEN, 0.06, D.PEW_BACK_H]} color={C.pew} />);
    rows.push(<B key={`e${i}${side}`} at={[side * (D.AISLE_W / 2 + 0.03), y + 0.2, D.PEW_BACK_H / 2]} size={[0.06, 0.5, D.PEW_BACK_H]} color={C.pew} />);
  }
  return rows;
}

function Chandelier({ pos, r, dome }) {
  const p = toThree(pos);
  return (
    <group position={p}>
      <mesh position={[0, (D.CEIL_H - pos[2]) / 2, 0]}><cylinderGeometry args={[0.015, 0.015, D.CEIL_H - pos[2], 6]} /><meshBasicMaterial color="#8a7448" /></mesh>
      {dome
        ? <mesh scale={[1, 0.38, 1]}><sphereGeometry args={[r, 32, 16]} /><meshBasicMaterial color="#ffeccb" toneMapped={false} /></mesh>
        : [0, 1, 2].map((i) => (
          <mesh key={i} position={[0, -i * r * 0.55, 0]}><cylinderGeometry args={[r * (1 - i * 0.28), r * (0.72 - i * 0.28), r * 0.5, 20]} /><meshBasicMaterial color="#ffe9c4" toneMapped={false} /></mesh>
        ))}
    </group>
  );
}

export function Placeholder() {
  const base = D.CHORUS_H;
  const midY = D.NAVE_L / 2, FY = D.NAVE_L;
  const shrines = [...D.LEFT_SHRINES.map(([y]) => [-1, y]), ...D.RIGHT_SHRINES.map(([y]) => [1, y])];
  const doorY = D.WINDOW_Y[D.WINDOW_Y.length - 1]; // the right wall's back door, under the short window
  const topRow = [...L.APOSTLE_X.flatMap((x) => [x, -x]), 0];
  return (
    <group>
      {/* floor, runner, chorus platform */}
      <B at={[0, midY, -0.05]} size={[D.NAVE_W, D.NAVE_L + 1, 0.1]} color={C.carpet} rough={1} />
      <B at={[0, D.CHORUS_Y / 2, 0.005]} size={[D.RUNNER_W, D.CHORUS_Y - 0.6, 0.01]} color={C.runner} rough={1} />
      <B at={[0, D.CHORUS_Y - 0.17, base / 4]} size={[D.NAVE_W, 0.34, base / 2]} color={C.carpet} rough={1} />
      <B at={[0, (D.CHORUS_Y + FY) / 2, base / 2]} size={[D.NAVE_W, FY - D.CHORUS_Y, base]} color={C.carpet} rough={1} />

      {/* walls, wainscot, the flat wood ceiling and its beams */}
      {[-1, 1].map((s) => (
        <group key={s}>
          <B at={[s * (HW + 0.1), midY, D.WALL_H / 2]} size={[0.2, D.NAVE_L + 1, D.WALL_H]} color={C.wall} />
          <B at={[s * (HW - 0.03), midY, D.WAINSCOT_H / 2]} size={[0.06, D.NAVE_L, D.WAINSCOT_H]} color={C.wood} />
          {D.BRACKET_Y.map((y) => <B key={y} at={[s * (HW - 0.12), y, D.WALL_H - 0.5]} size={[0.2, 0.2, 1.3]} color={C.dark} />)}
        </group>
      ))}
      <B at={[0, midY, D.CEIL_H + 0.05]} size={[D.NAVE_W + 0.4, D.NAVE_L + 1, 0.1]} color={C.ceiling} />
      {D.BRACKET_Y.map((y) => <B key={y} at={[0, y, D.CEIL_H - 0.1]} size={[D.NAVE_W, 0.2, 0.2]} color={C.dark} />)}
      <B at={[0, -0.1, D.CEIL_H / 2]} size={[D.NAVE_W + 0.4, 0.2, D.CEIL_H]} color={C.wall} />

      {/* back wall: steps and double doors, icon stands, exit doors */}
      {[0, 1, 2].map((i) => <B key={i} at={[0, 0.45 - i * 0.15 + 0.15, 0.075 + i * 0.15]} size={[2.6, 0.3 + (2 - i) * 0.3, 0.15]} color={C.carpet} rough={1} />)}
      <B at={[0, 0.04, 0.45 + 1.15]} size={[1.8, 0.08, 2.3]} color={C.dark} />
      {[-1, 1].map((s) => (
        <group key={s}>
          <B at={[s * L.STAND_X, 0.15, 1.3]} size={[0.85, 0.3, 2.6]} color={C.wood} />
          <B at={[s * (HW - 0.9), 0.04, 1.03]} size={[0.91, 0.08, 2.05]} color={C.wood} />
          <mesh position={toThree([s * (HW - 0.9), 0.06, 2.25])} rotation-y={Math.PI}><planeGeometry args={[0.32, 0.16]} /><meshBasicMaterial color="#b3261e" /></mesh>
        </group>
      ))}

      <B at={[HW - 0.05, doorY, 1.03]} size={[0.1, 0.91, 2.05]} color={C.wood} />

      {/* wall shrines */}
      {shrines.map(([s, y]) => <B key={s + '_' + y} at={[s * (HW - L.SHRINE_D / 2), y, D.SHRINE_Z + D.SHRINE_H / 2]} size={[L.SHRINE_D, D.SHRINE_W, D.SHRINE_H]} color={C.dark} />)}

      <Pews />

      {/* chorus: deacon benches facing each other, two lecterns, the bishop's throne */}
      {[-1, 1].map((s) => (
        <group key={s}>
          <B at={[s * (HW - 1.75), (D.CHORUS_Y + FY) / 2 - 0.3, base + 0.42]} size={[0.45, 2.6, 0.06]} color={C.pew} />
          <B at={[s * (HW - 1.5), (D.CHORUS_Y + FY) / 2 - 0.3, base + 0.46]} size={[0.06, 2.6, 0.92]} color={C.pew} />
          <B at={[s * L.LECTERN.x, L.LECTERN.y, base + 0.55]} size={[0.45, 0.4, 1.1]} color={C.wood} />
        </group>
      ))}
      <B at={[-HW + 0.08, L.THRONE.y, base + L.THRONE.h / 2]} size={[0.16, L.THRONE.w, L.THRONE.h]} color={C.oak} />
      <B at={[-HW + 0.5, L.THRONE.y, base + 0.3]} size={[0.8, L.THRONE.w, 0.6]} color={C.oak} />
      <B at={[-HW + 0.5, L.THRONE.y, base + 0.62]} size={[0.7, L.THRONE.w - 0.15, 0.05]} color={C.velvet} />
      <B at={[-HW + 0.5, L.THRONE.y, base + L.THRONE.h - 0.2]} size={[0.9, L.THRONE.w + 0.1, 0.4]} color={C.oak} />

      {/* iconostasis: the screen, the panelling above it, the two screens over the side doors */}
      <B at={[0, FY + D.ICONO_D / 2, D.ICONO_H / 2]} size={[D.NAVE_W, D.ICONO_D, D.ICONO_H]} color={C.dark} />
      <B at={[0, FY - 0.03, D.ICONO_H]} size={[D.NAVE_W, 0.2, 0.12]} color={C.wood} />
      <B at={[0, FY + D.ICONO_D + 0.1, D.CEIL_H / 2]} size={[D.NAVE_W + 0.4, 0.2, D.CEIL_H]} color={C.pew} />
      {[-1, 1].map((s) => <mesh key={s} position={toThree([s * D.SIDE_DOOR_X, FY - 0.05, base + D.DOOR_H + 0.3])}><planeGeometry args={[0.8, 0.45]} /><meshStandardMaterial color={C.black} roughness={0.3} /></mesh>)}
      {topRow.map((x) => <mesh key={x} position={toThree([x, FY - 0.28, L.TOP_Z - 0.52])}><sphereGeometry args={[0.045, 12, 8]} /><meshBasicMaterial color="#d2372c" toneMapped={false} /></mesh>)}

      {L.ITEMS.map((it) => <Picture key={it.name} item={it} />)}
      {L.CHANDELIERS.map((c, i) => <Chandelier key={i} {...c} />)}
    </group>
  );
}
