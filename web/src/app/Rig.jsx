// The camera. It stands at one framed stop at a time and glides between them with an ease-in-out move; at a
// stop the visitor can turn their head by dragging, within limits. Choosing a picture flies the camera up to
// it. With reduced motion every move is an instant cut. The render loop is on demand, so this asks for frames
// only while something is moving.
import { useEffect, useMemo, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import { Box3, Raycaster, Vector2, Vector3 } from 'three';
import { NAVE_L, NAVE_W, CEIL_H, toThree } from '../dimensions.js';
import { stops } from './tour.js';
import { registry, owner } from './registry.js';
import { useStore, set, get, inspect, closeInspect } from './store.js';

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const rad = (d) => (d * Math.PI) / 180;
const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
export const PHONE = 760; // below this width the panels are bottom sheets
export const panelWidth = (w) => Math.min(440, Math.max(360, w * 0.32));
const SHEET = 0.46; // the inspect sheet covers this much of a phone screen
const CARD = 0.3; // roughly what the stop card covers on a phone (0.14 when it is collapsed)

// Every stop was framed for a landscape window. On a tall one, widen the vertical field of view so the
// horizontal view stays the same and nothing is cut off at the sides.
function fovFor(aspect) {
  const BASE = 1.25, F = 50;
  if (aspect >= BASE) return F;
  const h = 2 * Math.atan(Math.tan(rad(F) / 2) * BASE);
  return Math.min(86, (2 * Math.atan(Math.tan(h / 2) / aspect) * 180) / Math.PI);
}
// Which way to turn to look from a to b: yaw about the vertical, pitch up or down
function aim(a, b) {
  const d = b.clone().sub(a);
  return { yaw: Math.atan2(-d.x, -d.z), pitch: Math.atan2(d.y, Math.hypot(d.x, d.z)) };
}
function stopView(stop) {
  const pos = new Vector3(...toThree(stop.camera.pos));
  return { pos, ...aim(pos, new Vector3(...toThree(stop.camera.look))), limYaw: rad(stop.camera.yaw ?? 55), limPitch: rad(28) };
}
// Stand in front of a picture, far enough back that all of it fits in the part of the screen the text panel
// leaves free. "In front" is along the picture's thin side, on the side that faces into the room.
const box = new Box3(), size = new Vector3(), centre = new Vector3();
function inspectView(obj, w, h) {
  obj.updateWorldMatrix(true, true);
  box.setFromObject(obj); box.getSize(size); box.getCenter(centre);
  const alongX = size.x <= size.z; // the thin horizontal side is the way it faces
  const n = alongX ? new Vector3(1, 0, 0) : new Vector3(0, 0, 1);
  const toRoom = new Vector3(0, centre.y, -NAVE_L / 2).sub(centre);
  if (n.dot(toRoom) < 0) n.negate();
  const width = alongX ? size.z : size.x, height = size.y, depth = alongX ? size.x : size.z;
  const phone = w < PHONE, aspect = w / h;
  const tan = Math.tan(rad(fovFor(aspect)) / 2);
  const freeW = phone ? 1 : (w - panelWidth(w)) / w, freeH = phone ? 1 - SHEET : 1;
  let dist = Math.max(height / 2 / (tan * freeH), width / 2 / (tan * aspect * freeW)) * 1.22 + depth / 2;
  dist = clamp(dist, 0.8, 9);
  const pos = centre.clone().addScaledVector(n, dist);
  pos.x = clamp(pos.x, -NAVE_W / 2 + 0.4, NAVE_W / 2 - 0.4);
  pos.z = clamp(pos.z, -NAVE_L + 0.4, -0.4);
  pos.y = clamp(pos.y, 0.7, CEIL_H - 0.8);
  return { pos, ...aim(pos, centre), limYaw: rad(14), limPitch: rad(10) };
}

// The drag and keyboard look-around reach the rig through here
export const rigApi = { turn: () => {} };

export function Rig() {
  const stop = useStore((s) => s.stop);
  const started = useStore((s) => s.started);
  const inspected = useStore((s) => s.inspect);
  const objects = useStore((s) => s.objects);
  const reduced = useStore((s) => s.reduced);
  const cardOpen = useStore((s) => s.cardOpen);
  const { camera, size, invalidate, gl } = useThree();
  const phone = size.width < PHONE;

  const s = useRef(null);
  const first = useRef(true);
  const obj = inspected ? registry.get(inspected) : null; // read again whenever the set of objects changes
  const view = useMemo(() => {
    if (obj) return inspectView(obj, size.width, size.height);
    return stopView(started ? stops[stop] : stops.find((x) => x.id === 'nave') || stops[0]); // the intro looks down the nave
  }, [stop, started, obj, objects, size.width, size.height]); // eslint-disable-line react-hooks/exhaustive-deps
  // the text panel sits on the right, the stop card on the left: slide the picture into what is left free
  const targetShift = phone ? 0 : obj ? panelWidth(size.width) / 2 : started && cardOpen ? -Math.min(196, size.width * 0.153) : 0; // half the card's width
  const targetLift = !phone || !started ? 0 : (size.height * (obj ? SHEET : cardOpen ? CARD : 0.14)) / 2;

  useEffect(() => {
    camera.fov = fovFor(size.width / size.height);
    camera.updateProjectionMatrix();
    invalidate();
  }, [size.width, size.height, camera, invalidate]);

  useEffect(() => {
    if (first.current) { // the first view is a cut, not a move
      first.current = false;
      s.current = { pos: view.pos.clone(), yaw: view.yaw, pitch: view.pitch, offYaw: 0, offPitch: 0, shift: targetShift, lift: targetLift, tween: null, view };
      invalidate();
      return;
    }
    const c = s.current;
    const fromYaw = c.yaw + c.offYaw, fromPitch = c.pitch + c.offPitch;
    const toYaw = view.yaw + Math.PI * 2 * Math.round((fromYaw - view.yaw) / (Math.PI * 2)); // turn the short way round
    const far = c.pos.distanceTo(view.pos) + Math.abs(toYaw - fromYaw) * 3;
    c.tween = { t: 0, dur: 1.0 + Math.min(1.3, far * 0.09), fromPos: c.pos.clone(), toPos: view.pos, fromYaw, toYaw, fromPitch, toPitch: view.pitch,
      fromShift: c.shift, toShift: targetShift, fromLift: c.lift, toLift: targetLift };
    c.offYaw = 0; c.offPitch = 0; c.yaw = fromYaw; c.pitch = fromPitch; c.view = view;
    set({ arrived: false });
    invalidate();
  }, [view, targetShift, targetLift]); // eslint-disable-line react-hooks/exhaustive-deps

  // Looking around: a drag turns the head, a click (a press that does not move) chooses a picture
  useEffect(() => {
    const el = gl.domElement;
    const ray = new Raycaster(), ndc = new Vector2();
    let down = null;
    const pick = (e) => {
      const r = el.getBoundingClientRect();
      ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, camera);
      const hit = ray.intersectObjects([...registry.values()], true)[0];
      return hit ? owner(hit.object)?.name ?? null : null;
    };
    const turn = (dYaw, dPitch) => {
      const c = s.current;
      if (!c || c.tween) return;
      c.offYaw = clamp(c.offYaw + dYaw, -c.view.limYaw, c.view.limYaw);
      c.offPitch = clamp(c.offPitch + dPitch, Math.max(-c.view.limPitch, -1.1 - c.pitch), Math.min(c.view.limPitch, 1.2 - c.pitch));
      invalidate();
    };
    rigApi.turn = turn;
    window.__tourInvalidate = invalidate;
    // For scripts/verify.mjs: where an object's centre is on screen
    window.__tourPoint = (name) => {
      const o = registry.get(name);
      if (!o) return null;
      const r = el.getBoundingClientRect(), p = new Box3().setFromObject(o).getCenter(new Vector3()).project(camera);
      return { x: r.left + ((p.x + 1) / 2) * r.width, y: r.top + ((1 - p.y) / 2) * r.height };
    };
    const onDown = (e) => {
      if (!get().started || (e.pointerType === 'mouse' && e.button !== 0)) return;
      down = { x: e.clientX, y: e.clientY, lx: e.clientX, ly: e.clientY, moved: false, id: e.pointerId };
      el.setPointerCapture?.(e.pointerId);
    };
    const onMove = (e) => {
      if (down && e.pointerId === down.id) {
        if (!down.moved && Math.hypot(e.clientX - down.x, e.clientY - down.y) > 6) { down.moved = true; el.classList.add('dragging'); set({ hover: null }); }
        if (down.moved) {
          const k = rad(camera.fov) / el.clientHeight; // the picture follows the finger
          turn((e.clientX - down.lx) * k, (e.clientY - down.ly) * k);
        }
        down.lx = e.clientX; down.ly = e.clientY;
      } else if (e.pointerType === 'mouse' && get().started) {
        set({ hover: pick(e) });
      }
    };
    const onUp = (e) => {
      if (!down || e.pointerId !== down.id) return;
      const wasClick = !down.moved;
      down = null; el.classList.remove('dragging');
      if (!wasClick) return;
      const name = pick(e);
      if (name) inspect(name); else if (get().inspect) closeInspect();
    };
    const onCancel = () => { down = null; el.classList.remove('dragging'); };
    const onLeave = () => { if (!down) set({ hover: null }); };
    el.addEventListener('pointerdown', onDown);
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerup', onUp);
    el.addEventListener('pointercancel', onCancel);
    el.addEventListener('pointerleave', onLeave);
    return () => {
      el.removeEventListener('pointerdown', onDown); el.removeEventListener('pointermove', onMove); el.removeEventListener('pointerup', onUp);
      el.removeEventListener('pointercancel', onCancel); el.removeEventListener('pointerleave', onLeave);
    };
  }, [gl, camera, invalidate]);

  useFrame((_, dt) => {
    const c = s.current;
    if (!c) return;
    const tw = c.tween;
    if (tw) {
      tw.t = reduced ? 1 : Math.min(1, tw.t + Math.min(dt, 0.1) / tw.dur);
      const k = ease(tw.t);
      c.pos.lerpVectors(tw.fromPos, tw.toPos, k);
      c.yaw = tw.fromYaw + (tw.toYaw - tw.fromYaw) * k;
      c.pitch = tw.fromPitch + (tw.toPitch - tw.fromPitch) * k;
      c.shift = tw.fromShift + (tw.toShift - tw.fromShift) * k;
      c.lift = tw.fromLift + (tw.toLift - tw.fromLift) * k;
      if (tw.t >= 1) { c.tween = null; set({ arrived: true }); } else invalidate();
    }
    camera.position.copy(c.pos);
    camera.rotation.set(c.pitch + c.offPitch, c.yaw + c.offYaw, 0, 'YXZ');
    camera.setViewOffset(size.width, size.height, c.shift, c.lift, size.width, size.height);
    window.__tourMoving = !!c.tween;
    // For scripts/compare.mjs: a fixed view { pos, look, fov } in Blender coordinates, to set beside a Cycles render
    const fixed = window.__tourFixedView;
    if (fixed) {
      camera.clearViewOffset();
      camera.position.set(...toThree(fixed.pos));
      camera.lookAt(...toThree(fixed.look));
      if (camera.fov !== fixed.fov) { camera.fov = fixed.fov; camera.updateProjectionMatrix(); }
    }
  });
  return null;
}
