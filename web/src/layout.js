// Where every inspectable picture sits in the placeholder room, worked out from dimensions.js (Blender
// coordinates, metres). The real GLB carries its own positions; this file only feeds the placeholder and the
// camera stops. `face` is the wall the picture hangs on, which gives the direction it looks.
// Positions the spec does not give (icon sizes, the exact x of each iconostasis icon) are guesses.
import * as D from './dimensions.js';

const HW = D.NAVE_W / 2;
const GAP = 0.03; // off the wall, so nothing z-fights
const items = [];
const add = (name, tex, pos, size, face) => items.push({ name, tex, pos, size, face });

// Stained glass
const winZ = (sill) => (sill + D.WINDOW_TOP) / 2;
D.LEFT_WINDOWS.forEach((n, i) => add('Win_' + n, 'windows/' + n, [-HW + GAP, D.WINDOW_Y[i], winZ(D.WINDOW_SILL)], [D.WINDOW_W, D.WINDOW_TOP - D.WINDOW_SILL], 'left'));
D.RIGHT_WINDOWS.forEach((n, i) => {
  const sill = n === 'healing' ? D.SHORT_WINDOW_SILL : D.WINDOW_SILL;
  add('Win_' + n, 'windows/' + n, [HW - GAP, D.WINDOW_Y[i], winZ(sill)], [D.WINDOW_W, D.WINDOW_TOP - sill], 'right');
});

// Wall shrines: the icon sits inside the carved frame
export const SHRINE_D = 0.22;
const shrineZ = D.SHRINE_Z + D.SHRINE_H * 0.5;
D.LEFT_SHRINES.forEach(([y, n]) => add('Icon_' + n, 'icons/' + n, [-HW + SHRINE_D + GAP, y, shrineZ], [0.62, 0.9], 'left'));
D.RIGHT_SHRINES.forEach(([y, n]) => add('Icon_' + n, 'icons/' + n, [HW - SHRINE_D - GAP, y, shrineZ], [0.62, 0.9], 'right'));

// Back wall: the St. Mark relief above the doors, an icon stand each side of the doors (Theotokos on the
// left, Christ on the right, facing the altar). St Mina and Abba Abraam are side-wall shrines near the back.
export const STAND_X = D.DOOR_W + 0.1;
add('Icon_stmark_relief', 'icons/stmark_relief', [0, GAP, 4.2], [0.9, 1.9], 'back');
add('Icon_stand_theotokos', null, [-STAND_X, 0.32, 1.65], [0.55, 0.75], 'back');
add('Icon_stand_christ', null, [STAND_X, 0.32, 1.65], [0.55, 0.75], 'back');

// Iconostasis. Its front face is at y = NAVE_L and it stands on the chorus platform.
const FY = D.NAVE_L - GAP;
const base = D.CHORUS_H;
const tripFrom = D.SIDE_DOOR_X + D.DOOR_W / 2 + 0.12; // from the side door's frame to the side wall
const tripStep = (HW - 0.12 - tripFrom) / 3;
export const TRIPTYCH_X = [0, 1, 2].map((i) => tripFrom + tripStep * (i + 0.5)); // centre outward
const tripW = Math.min(0.6, tripStep - 0.06);
const lower = base + 1.45;
['annunciation_panel', 'mikhail', 'mark'].forEach((n, i) => add('Icon_' + n, 'icons/' + n, [-TRIPTYCH_X[i], FY, lower], [tripW, tripW * 2], 'front'));
['john_baptist', 'george', 'mina_panel'].forEach((n, i) => add('Icon_' + n, 'icons/' + n, [TRIPTYCH_X[i], FY, lower], [tripW, tripW * 2], 'front'));
export const MAIN_ICON_X = (D.DOOR_W / 2 + D.SIDE_DOOR_X - D.DOOR_W / 2) / 2; // halfway between the royal door and a side door
add('Icon_theotokos', 'icons/theotokos', [-MAIN_ICON_X, FY, lower + 0.05], [0.8, 1.25], 'front');
add('Icon_christ', 'icons/christ', [MAIN_ICON_X, FY, lower + 0.05], [0.8, 1.25], 'front');
const curtainZ = base + D.DOOR_H / 2;
add('Icon_curtain_christ', 'icons/curtain_christ', [0, FY, curtainZ], [D.DOOR_W, D.DOOR_H], 'front');
add('Icon_curtain_mary', 'icons/curtain_mary', [-D.SIDE_DOOR_X, FY, curtainZ], [D.DOOR_W, D.DOOR_H], 'front');
add('Icon_curtain_right', 'icons/curtain_right', [D.SIDE_DOOR_X, FY, curtainZ], [D.DOOR_W, D.DOOR_H], 'front');

// Top row: six apostles, the Last Supper, six apostles
export const TOP_Z = D.ICONO_H - 0.55;
export const SUPPER_W = D.DOOR_W + 0.1;
const apStep = (HW - 0.15 - SUPPER_W / 2 - 0.1) / 6;
export const APOSTLE_X = [0, 1, 2, 3, 4, 5].map((i) => SUPPER_W / 2 + 0.1 + apStep * (i + 0.5)); // centre outward
const apW = Math.min(0.55, apStep - 0.12);
add('Icon_last_supper', 'icons/last_supper', [0, FY, TOP_Z], [SUPPER_W, 0.75], 'front');
for (let i = 0; i < 6; i++) {
  const n = (k) => String(k).padStart(2, '0');
  add('Icon_apostle_' + n(i + 1), 'icons/apostle_' + n(i + 1), [-APOSTLE_X[5 - i], FY, TOP_Z], [apW, 0.75], 'front');
  add('Icon_apostle_' + n(i + 7), 'icons/apostle_' + n(i + 7), [APOSTLE_X[i], FY, TOP_Z], [apW, 0.75], 'front');
}

// The crucifix in the arch above the centre
export const CRUCIFIX_Z = (D.ICONO_H + D.WALL_H) / 2 + 0.1;
const crossH = Math.min(2.1, D.WALL_H - D.ICONO_H - 0.3);
add('Icon_crucifix', 'icons/crucifix', [0, D.NAVE_L + 0.1, CRUCIFIX_Z], [1.3, crossH], 'front');
add('Icon_crucifix_mary', 'icons/crucifix_mary', [-1.15, D.NAVE_L + 0.1, CRUCIFIX_Z - crossH * 0.14], [0.6, crossH * 0.72], 'front');
add('Icon_crucifix_john', 'icons/crucifix_john', [1.15, D.NAVE_L + 0.1, CRUCIFIX_Z - crossH * 0.14], [0.6, crossH * 0.72], 'front');

// The two lecterns stand on the chorus either side of the royal door, a couple of metres in front of the
// screen (read off the real model)
export const LECTERN = { x: D.DOOR_W / 2 + 0.35, y: D.NAVE_L - 2.4 };

// The dome chandelier over the chorus: where its bowl hangs lowest (read off the real model)
export const DOME = { y: (D.CHORUS_Y + D.NAVE_L) / 2, low: 4.1 };

// The bishop's throne: front-left, against the side wall, looking across the chorus (from the 2007 photo)
export const THRONE = { x: -HW + 0.55, y: D.NAVE_L - 1.15, w: 0.95, d: 0.9, h: 2.9 };
add('Icon_throne_christ', 'icons/throne_christ', [-HW + 0.2, THRONE.y, base + 1.75], [0.5, 0.7], 'left');

// Chandeliers: a shallow dome over the chorus, big ones down the centre, smaller ones down each side
export const CHANDELIERS = [
  { pos: [0, (D.CHORUS_Y + D.NAVE_L) / 2, D.CEIL_H - 1.3], r: 1.4, dome: true },
  ...[0.2, 0.5, 0.8].map((f) => ({ pos: [0, D.CHORUS_Y * f, D.CEIL_H - 2.2], r: 0.7 })),
  ...D.BRACKET_Y.slice(0, 4).flatMap((y) => [-HW * 0.6, HW * 0.6].map((x) => ({ pos: [x, y - 1.5, D.WALL_H - 0.9], r: 0.4 }))),
];

export const ITEMS = items;
export const itemPos = (name) => items.find((i) => i.name === name).pos;
