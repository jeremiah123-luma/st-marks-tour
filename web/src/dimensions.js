// Room dimensions in metres, ported from ../blender/common.py (scale v3, Nov 20). common.py is the source: when a number changes
// there, change it here too, then run `npm run cameras` so the stops in tour.json follow.
// Blender axes: +Y toward the altar, +X to the right (facing the altar), +Z up. Origin = floor, centre of the
// nave, at the inside face of the back wall. toThree() below converts to three's Y-up axes (what the GLB uses).

// ---- room
export const NAVE_W = 11.0; // inside width
export const NAVE_L = 17.5; // back wall to the front face of the iconostasis
export const WALL_H = 6.6; // white wall height (the ceiling is flat, so this equals CEIL_H)
export const CEIL_H = 6.6; // the flat wood ceiling
export const WAINSCOT_H = 1.0;

// ---- floor
export const AISLE_W = 1.5;
export const RUNNER_W = 1.1;
export const CHORUS_Y = 12.9; // front edge of the raised chorus platform
export const CHORUS_H = 0.3;

// ---- pews
export const PEW_ROWS = 12; // per block
export const PEW_PITCH = 0.8;
export const PEW_FIRST_Y = 2.6; // back-most row
export const PEW_LEN = 3.85; // x from +-0.75 to +-4.6
export const PEW_SEAT_H = 0.44;
export const PEW_BACK_H = 0.92;

// ---- side walls (front = near the altar)
export const WINDOW_Y = [15.7, 12.2, 8.7, 5.2, 1.7]; // front -> back, both walls
export const WINDOW_W = 1.0;
export const WINDOW_SILL = 1.15;
export const WINDOW_TOP = 5.05;
export const SHORT_WINDOW_SILL = 3.2; // right wall, back-most window (above the stairs)
export const BRACKET_Y = [13.95, 10.45, 6.95, 3.45];
export const SHRINE_Z = 1.75; // bottom shelf of a wall shrine
export const SHRINE_W = 0.95;
export const SHRINE_H = 1.85;

export const LEFT_WINDOWS = ['abraham', 'david', 'three_youths', 'moses', 'daniel'];
export const RIGHT_WINDOWS = ['storm', 'samaritan', 'egypt', 'lazarus', 'healing'];
export const LEFT_SHRINES = [[13.95, 'annunciation'], [10.45, 'nativity'], [6.95, 'antony'], [2.9, 'mina']];
// St Mina and Abba Abraam hang on the side walls near the back (y 2.9), as in the real model.
export const RIGHT_SHRINES = [[13.95, 'pentecost'], [10.45, 'ascension'], [6.95, 'resurrection'], [2.9, 'abraam']];

// ---- iconostasis
export const ICONO_H = 3.9; // top of the apostle row cornice
export const ICONO_D = 0.3;
export const DOOR_W = 1.3;
export const DOOR_H = 2.2;
export const SIDE_DOOR_X = 2.5;

// Blender (x, y, z) -> three (x, z, -y)
export const toThree = ([x, y, z]) => [x, z, -y];
