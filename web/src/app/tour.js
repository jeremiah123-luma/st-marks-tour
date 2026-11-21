// The tour's data (tour.json) and how an object in the scene finds its text.
import tour from '../tour.json';

export const church = tour.church;
export const stops = tour.stops;
const keys = Object.keys(tour.items).sort((a, b) => b.length - a.length); // longest first

// An object's text: its exact name, or else the longest item key its name starts with. That covers the
// twelve apostles sharing one entry (Icon_apostle_07 -> Icon_apostle) and Blender's numbered copies
// (Icon_mark.001 arrives from the GLB as Icon_mark001).
export function itemKey(name) {
  if (tour.items[name]) return name;
  return keys.find((k) => name.startsWith(k)) || null;
}
export function itemInfo(name) {
  const k = itemKey(name);
  if (k) return tour.items[k];
  const plain = name.replace(/^(Icon|Win)_/, '').replace(/[_\d]+/g, ' ').trim();
  return { title: plain.charAt(0).toUpperCase() + plain.slice(1), text: 'The description of this item is still to be written.' };
}
export const isInspectable = (name) => /^(Icon|Win)_/.test(name || '');

// The objects of a stop, in tour order, out of the names that exist in the scene right now
export function stopObjects(stop, names) {
  const out = [];
  for (const key of stop.items) {
    const hit = names.filter((n) => n === key || (itemKey(n) === key && n !== key)).sort();
    for (const n of hit) if (!out.includes(n)) out.push(n);
  }
  return out;
}
