// The camera for every stop, worked out from dimensions.js and layout.js (Blender coordinates, metres).
// `npm run cameras` writes these into tour.json, which is what the app reads. `yaw` is how far (degrees) a
// visitor may turn left or right from the framed view at that stop.
import * as D from './dimensions.js';
import * as L from './layout.js';

const HW = D.NAVE_W / 2;
const EYE = 1.6; // standing eye height. Every position below is a formula over dimensions.js, never a fixed number.
const UP = EYE + D.CHORUS_H; // standing on the chorus platform
const midY = D.WINDOW_Y[2]; // the middle window
const winZ = (D.WINDOW_SILL + D.WINDOW_TOP) / 2;
const r = (v) => v.map((n) => Math.round(n * 100) / 100);
const cam = (pos, look, yaw) => ({ pos: r(pos), look: r(look), ...(yaw ? { yaw } : {}) });

const SCREEN = D.NAVE_L; // the front face of the iconostasis
const tripZ = D.CHORUS_H + 1.25; // the triptychs hang low on the screen
// Standing on the chorus just outside a lectern and behind it, turned toward the triptych at that end of the
// screen: clear of the deacons' benches, with the bishop's throne to the left of the left triptych
const patron = (side) => cam([side * (L.LECTERN.x + 0.95), L.LECTERN.y - 0.2, UP], [side * L.TRIPTYCH_X[1], SCREEN, tripZ], 60);

export const CAMERAS = {
  entrance: cam([0, D.PEW_FIRST_Y + 4.6, EYE], [0, 0, 2.1], 70),
  nave: cam([0, 1.6, EYE + 0.1], [0, SCREEN, D.ICONO_H * 0.7], 80),
  // from the centre aisle, so the row of side chandeliers hangs above the windows and not across them
  'glass-old-testament': cam([D.AISLE_W / 2 - 0.45, midY, EYE], [-HW, midY, winZ - 0.3], 75),
  'glass-new-testament': cam([-D.AISLE_W / 2 + 0.45, midY, EYE], [HW, midY, winZ - 0.3], 75),
  'feast-icons': cam([0, (D.BRACKET_Y[0] + D.BRACKET_Y[2]) / 2 - 2.2, EYE], [-HW, D.BRACKET_Y[1] + 1, D.SHRINE_Z + D.SHRINE_H / 2], 180),
  chorus: cam([0, D.CHORUS_Y - 3.5, EYE + 0.2], [0, SCREEN - 2.5, 1.2], 60),
  // close enough that the dome chandelier over the chorus stays above the frame
  iconostasis: cam([0, SCREEN - 7, EYE + 0.2], [0, SCREEN, D.ICONO_H * 0.6], 50),
  // on the chorus, between the two lecterns
  'royal-door': cam([0, L.LECTERN.y + 0.1, UP], [0, SCREEN, D.CHORUS_H + D.DOOR_H / 2 + 0.05], 60),
  'theotokos-and-christ': cam([0, L.LECTERN.y - 0.8, UP], [0, SCREEN, D.CHORUS_H + 1.4], 45),
  'apostles-last-supper': cam([0, SCREEN - HW * 1.3, EYE + 0.2], [0, SCREEN, L.TOP_Z], 55),
  // A raised view, the way a window is inspected: floating just under the dome chandelier's bowl and a little
  // past its lowest point, so the bowl is above and behind the frame. From the nave the bowl hides the cross at
  // any height (tried 3.0 to 4.0 m in front of the chorus edge), so the camera has to be beyond it.
  crucifix: cam([0, L.DOME.y + 0.2, L.DOME.low - 0.6], [0, SCREEN, D.ICONO_H + 0.5], 40),
  'patron-icons-left': patron(-1),
  'patron-icons-right': patron(1),
  'bishops-throne': cam([-L.LECTERN.x - 1.1, L.THRONE.y - 1.5, UP], [L.THRONE.x, L.THRONE.y, 1.9], 50),
  chandeliers: cam([0, D.CHORUS_Y * 0.32, EYE], [0, D.CHORUS_Y + 1, D.CEIL_H - 1.6], 70),
};
