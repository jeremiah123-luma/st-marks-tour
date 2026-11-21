// The page around the 3D room: the intro, the card for the current stop, the panel for a chosen picture,
// the stop list, and the keyboard. All of its words come from tour.json.
import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import assets from '../generated/assets.json';
import { church, stops, itemInfo, itemKey, stopObjects } from './tour.js';
import { registry } from './registry.js';
import { useStore, set, get, goTo, next, back, begin, inspect, closeInspect } from './store.js';
import { rigApi } from './Rig.jsx';

const Stage = lazy(() => import('./Stage.jsx'));

const Cross = () => (
  <svg className="cross" viewBox="0 0 40 40" aria-hidden="true">
    <path d="M20 4v32M4 20h32M15 6h10M15 34h10M6 15v10M34 15v10" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
  </svg>
);

function Intro() {
  const started = useStore((s) => s.started);
  const [gone, setGone] = useState(false);
  useEffect(() => { if (started) { const t = setTimeout(() => setGone(true), get().reduced ? 0 : 900); return () => clearTimeout(t); } }, [started]);
  if (gone) return null;
  return (
    <section className={'intro' + (started ? ' leaving' : '')} aria-labelledby="intro-title" inert={started ? '' : undefined}>
      <div className="intro-in">
        <Cross />
        <h1 id="intro-title">{church.name}</h1>
        <p className="tagline">{church.tagline}</p>
        <p className="lede">{church.intro}</p>
        <button className="btn primary" onClick={begin} autoFocus>Begin the tour</button>
        <p className="count">{stops.length} stops</p>
      </div>
    </section>
  );
}

// The objects of this stop that exist in the scene, one chip per tour.json entry
function useStopObjects(stop) {
  useStore((s) => s.objects);
  return stopObjects(stop, [...registry.keys()]);
}

function StopCard() {
  const i = useStore((s) => s.stop);
  const stop = stops[i];
  const names = useStopObjects(stop);
  const title = useRef(null);
  const mounted = useRef(false);
  useEffect(() => { if (mounted.current) title.current?.focus({ preventScroll: true }); mounted.current = true; }, [i]);
  const chips = [];
  for (const n of names) { const k = itemKey(n) || n; if (!chips.some((c) => c.k === k)) chips.push({ k, n }); }
  const open = useStore((s) => s.cardOpen);
  return (
    <section className={'card' + (open ? '' : ' closed')} aria-label="Current stop">
      <div className="card-head">
        <div className="card-title">
          <p className="eyebrow">Stop {i + 1} of {stops.length}</p>
          <h2 ref={title} tabIndex={-1}>{stop.title}</h2>
        </div>
        <button className="fold" onClick={() => set({ cardOpen: !open })} aria-expanded={open} aria-controls="stop-text"
          aria-label={open ? 'Hide the text for this stop' : 'Show the text for this stop'}>
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 6l4.5 4.5L12.5 6" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </button>
      </div>
      {open && (
        <div className="card-scroll" id="stop-text" key={stop.id}>
          <p className="body">{stop.text}</p>
          {chips.length > 0 && (
            <div className="chips">
              <p className="chips-h">Look closer</p>
              <ul>
                {chips.map(({ k, n }) => { const it = itemInfo(n); return (
                  <li key={k}><button className="chip" onClick={() => inspect(n)} onPointerEnter={() => set({ hover: n })} onPointerLeave={() => set({ hover: null })}
                    onFocus={() => set({ hover: n })} onBlur={() => set({ hover: null })}>{it.label || it.title}</button></li>
                ); })}
              </ul>
            </div>
          )}
          {i === 0 && <p className="tip">Drag to look around. Choose a framed picture to read about it.</p>}
        </div>
      )}
      <div className="nav">
        <button className="btn" onClick={back} disabled={i === 0}>Back</button>
        <button className="btn primary" onClick={next} disabled={i === stops.length - 1}>Next</button>
      </div>
    </section>
  );
}

function InspectPanel() {
  const name = useStore((s) => s.inspect);
  const stop = stops[useStore((s) => s.stop)];
  const names = useStopObjects(stop);
  const close = useRef(null);
  const last = useRef(null);
  useEffect(() => {
    if (name && !last.current) close.current?.focus({ preventScroll: true });
    last.current = name;
  }, [name]);
  if (!name) return null;
  const it = itemInfo(name);
  const at = names.indexOf(name);
  const step = (d) => inspect(names[(at + d + names.length) % names.length]);
  return (
    <aside className="panel" role="dialog" aria-label={it.title}>
      <button ref={close} className="x" onClick={closeInspect} aria-label="Close and return to the stop">
        <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 3l10 10M13 3L3 13" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
      </button>
      <div className="panel-scroll" key={name}>
        <p className="eyebrow">{stop.title}</p>
        <h2>{it.title}</h2>
        <p className="body">{it.text}</p>
      </div>
      {at >= 0 && names.length > 1 && (
        <div className="nav">
          <button className="btn" onClick={() => step(-1)}>Previous</button>
          <span className="of">{at + 1} / {names.length}</span>
          <button className="btn" onClick={() => step(1)}>Next</button>
        </div>
      )}
    </aside>
  );
}

function StopList() {
  const open = useStore((s) => s.listOpen);
  const i = useStore((s) => s.stop);
  const cur = useRef(null);
  useEffect(() => { if (open) cur.current?.focus(); }, [open]);
  return (
    <>
      <button className="btn stops-btn" onClick={() => set({ listOpen: !open })} aria-expanded={open} aria-controls="stop-list">
        Stops <span className="num">{i + 1} / {stops.length}</span>
      </button>
      {open && (
        <>
          <div className="scrim" onClick={() => set({ listOpen: false })} />
          <nav id="stop-list" className="list" aria-label="All stops">
            <ol>
              {stops.map((s, k) => (
                <li key={s.id}>
                  <button ref={k === i ? cur : null} className={k === i ? 'on' : ''} aria-current={k === i ? 'step' : undefined} onClick={() => goTo(k)}>
                    <span className="n">{k + 1}</span>{s.title}
                  </button>
                </li>
              ))}
            </ol>
          </nav>
        </>
      )}
    </>
  );
}

function HoverLabel() {
  const hover = useStore((s) => s.hover);
  const inspected = useStore((s) => s.inspect);
  if (!hover || hover === inspected) return null;
  return <p className="hover-label" aria-hidden="true">{itemInfo(hover).title}</p>;
}

export function App() {
  const started = useStore((s) => s.started);
  const ready = useStore((s) => s.ready);
  const inspected = useStore((s) => s.inspect);
  const hover = useStore((s) => s.hover);
  const stop = stops[useStore((s) => s.stop)];

  useEffect(() => {
    const onKey = (e) => {
      const s = get();
      if (!s.started || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key;
      if (k === 'Escape') { if (s.listOpen) set({ listOpen: false }); else if (s.inspect) closeInspect(); return; }
      if (e.shiftKey && k.startsWith('Arrow')) { // Shift + arrows turn the head
        const a = 0.09;
        rigApi.turn(k === 'ArrowLeft' ? a : k === 'ArrowRight' ? -a : 0, k === 'ArrowUp' ? a : k === 'ArrowDown' ? -a : 0);
        e.preventDefault(); return;
      }
      if (s.listOpen) return; // the list is a plain list of buttons: Tab and Enter
      const d = k === 'ArrowRight' || k === 'PageDown' ? 1 : k === 'ArrowLeft' || k === 'PageUp' ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      if (s.inspect) { // inside a stop, the arrows step through its pictures
        const names = stopObjects(stops[s.stop], [...registry.keys()]);
        const at = names.indexOf(s.inspect);
        if (at >= 0 && names.length > 1) inspect(names[(at + d + names.length) % names.length]);
      } else goTo(s.stop + d);
    };
    addEventListener('keydown', onKey);
    return () => removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className={'tour' + (started ? ' started' : '') + (inspected ? ' inspecting' : '') + (hover ? ' hovering' : '')}>
      <div className={'stage' + (ready ? ' ready' : '')} aria-hidden="true">
        <Suspense fallback={null}><Stage /></Suspense>
      </div>
      {started && (
        <>
          <header className="top">
            <p className="name">{church.name}</p>
            <StopList />
          </header>
          {!inspected && <StopCard />}
          <InspectPanel />
          <HoverLabel />
          {!assets.glb && <p className="preview-note">Preview model</p>}
          <p className="sr" aria-live="polite">{inspected ? itemInfo(inspected).title : stop.title}</p>
        </>
      )}
      <Intro />
    </div>
  );
}
