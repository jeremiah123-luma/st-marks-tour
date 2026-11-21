// Thin gold frames around the pictures a visitor can choose: faint on the ones that belong to this stop,
// bright on the one under the pointer. Works on any object, so the real model needs nothing extra.
import { useMemo } from 'react';
import { Box3, BoxGeometry, EdgesGeometry, Vector3 } from 'three';
import { stops, stopObjects } from './tour.js';
import { registry } from './registry.js';
import { useStore } from './store.js';

const unit = new EdgesGeometry(new BoxGeometry(1, 1, 1));

function Frame({ obj, strong }) {
  const { c, s } = useMemo(() => {
    obj.updateWorldMatrix(true, true);
    const b = new Box3().setFromObject(obj);
    return { c: b.getCenter(new Vector3()), s: b.getSize(new Vector3()).addScalar(strong ? 0.07 : 0.05) };
  }, [obj, strong]);
  return (
    <lineSegments geometry={unit} position={c} scale={s} renderOrder={5}>
      <lineBasicMaterial color={strong ? '#f0cf85' : '#c9a35a'} transparent opacity={strong ? 1 : 0.5} toneMapped={false} />
    </lineSegments>
  );
}

export function Outlines() {
  const stop = useStore((s) => s.stop);
  const started = useStore((s) => s.started);
  const hover = useStore((s) => s.hover);
  const inspected = useStore((s) => s.inspect);
  useStore((s) => s.objects);
  if (!started) return null;
  const names = inspected ? [] : stopObjects(stops[stop], [...registry.keys()]);
  return (
    <>
      {names.filter((n) => n !== hover).map((n) => <Frame key={n} obj={registry.get(n)} />)}
      {hover && hover !== inspected && registry.get(hover) && <Frame key={'h' + hover} obj={registry.get(hover)} strong />}
    </>
  );
}
