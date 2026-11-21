// The 3D part of the page: the canvas, the room (the real model when public/church.glb was there at build
// time, the placeholder otherwise), the camera rig and the gold frames. Loaded as its own chunk.
import { Component, Suspense, lazy } from 'react';
import { Canvas } from '@react-three/fiber';
import assets from '../generated/assets.json';
import * as D from '../dimensions.js';
import { CHANDELIERS } from '../layout.js';
import { Placeholder } from './Placeholder.jsx';
import { Rig } from './Rig.jsx';
import { Outlines } from './Outlines.jsx';
import { set } from './store.js';

const Model = lazy(() => import('./Model.jsx').then((m) => ({ default: m.Model })));

// If the model fails to load, the placeholder room takes its place
class Fallback extends Component {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch(e) { console.warn('church.glb could not be shown, using the placeholder room:', e?.message); }
  render() { return this.state.failed ? this.props.fallback : this.props.children; }
}

// Plain lights for the placeholder, and for a model whose materials are not baked: warm and even
function Lights() {
  const lit = CHANDELIERS.filter((c) => c.dome || c.r > 0.5);
  return (
    <>
      <ambientLight intensity={0.8} color="#ffe2c4" />
      <hemisphereLight args={['#fff1dc', '#3a1c14', 0.6]} />
      {lit.map((c, i) => <pointLight key={i} position={D.toThree([c.pos[0], c.pos[1], c.pos[2] - 0.6])} intensity={c.dome ? 70 : 40} decay={2} color="#ffd9a6" />)}
    </>
  );
}

export default function Stage() {
  return (
    <Canvas frameloop="demand" dpr={[1, 2]} camera={{ fov: 50, near: 0.1, far: 90 }} gl={{ antialias: true, powerPreference: 'high-performance' }}
      onCreated={() => requestAnimationFrame(() => set({ ready: true }))}>
      <color attach="background" args={['#120e0a']} />
      {/* the real model carries its own baked light: the plain lights are only for the placeholder room */}
      {assets.glb
        ? <Fallback fallback={<><Lights /><Placeholder /></>}><Suspense fallback={null}><Model /></Suspense></Fallback>
        : <><Lights /><Placeholder /></>}
      <Rig />
      <Outlines />
    </Canvas>
  );
}
