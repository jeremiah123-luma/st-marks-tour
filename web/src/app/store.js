// A very small store (no library): where the visitor is in the tour and what they are looking at.
import { useSyncExternalStore } from 'react';
import { stops } from './tour.js';

const fromHash = () => Math.max(0, stops.findIndex((s) => s.id === decodeURIComponent(location.hash.slice(1))));

let state = {
  started: false, // "Begin the tour" was pressed
  stop: fromHash(), // index into the stops
  inspect: null, // name of the object being looked at closely, or null
  hover: null, // name of the object under the pointer
  listOpen: false, // the stop list
  cardOpen: true, // the stop card shows its text (false: only its title and the Back / Next buttons)
  arrived: true, // the camera has finished its move
  ready: false, // the room is on screen
  objects: 0, // counts changes to the set of inspectable objects (registry.js)
  reduced: matchMedia('(prefers-reduced-motion: reduce)').matches,
};
const subs = new Set();
export function set(patch) {
  const next = { ...state, ...patch };
  if (Object.keys(patch).every((k) => next[k] === state[k])) return;
  state = next;
  subs.forEach((f) => f());
}
export const get = () => state;
const subscribe = (f) => { subs.add(f); return () => subs.delete(f); };
export const useStore = (pick) => useSyncExternalStore(subscribe, () => pick(state));

matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => set({ reduced: e.matches }));

// The address keeps the stop (#royal-door), so a link can open the tour at any stop. One entry: Back leaves.
export function goTo(i) {
  if (i < 0 || i >= stops.length) return;
  history.replaceState(null, '', '#' + stops[i].id);
  set({ stop: i, inspect: null, hover: null, listOpen: false });
}
export const next = () => goTo(state.stop + 1);
export const back = () => goTo(state.stop - 1);
export const begin = () => set({ started: true });
export const inspect = (name) => set({ inspect: name, hover: null, listOpen: false });
export const closeInspect = () => set({ inspect: null });
addEventListener('hashchange', () => { const i = fromHash(); if (stops[i].id === decodeURIComponent(location.hash.slice(1))) set({ stop: i, inspect: null }); });
