// Every inspectable object in the scene, by name. The placeholder room registers its pictures; the GLB
// registers any object named Icon_* or Win_*.
import { get, set } from './store.js';

export const registry = new Map();
export function register(obj) {
  registry.set(obj.name, obj);
  set({ objects: get().objects + 1 });
  return () => { if (registry.get(obj.name) === obj) { registry.delete(obj.name); set({ objects: get().objects + 1 }); } };
}
// The registered object a ray hit belongs to (the hit itself, or the nearest registered parent)
export function owner(obj) {
  for (let o = obj; o; o = o.parent) if (registry.get(o.name) === o) return o;
  return null;
}
