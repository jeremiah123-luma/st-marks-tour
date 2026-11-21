// The real church, public/church.glb, as blender/export_web.py writes it:
// - light is baked: every static mesh carries a lightmap on its second UV set (RGBM WebP files in public/lm,
//   named in each object's userData.lm). Matte surfaces draw albedo x lightmap with an unlit material; glossy
//   ones (varnished wood, glass, metal) add a reflection of the room from a small HDR probe (public/lm/env.hdr),
//   box-projected onto the nave so the chandeliers land in the right place on the ceiling.
// - varnish, glass and metal also show the chandelier lamps as highlights (the lamps are exported as positions);
//   normal maps from the export (pew bevels, the ceiling's board profile, marquetry) shape those highlights.
// - chandelier crystals get a cheap glass shader driven by the per-crystal vertex colour, and each lit chandelier
//   a soft additive glow.
// - tone mapping follows the Cycles check renders (AgX, the scene's exposure).
// Every object named Icon_* or Win_* becomes something a visitor can choose.
import { useEffect, useMemo } from 'react';
import { useLoader, useThree } from '@react-three/fiber';
import {
  AdditiveBlending, AgXToneMapping, CanvasTexture, Color, Group, ImageBitmapLoader, LinearFilter, MeshBasicMaterial,
  MeshStandardMaterial, PMREMGenerator, SRGBColorSpace, ShaderChunk, Sprite, SpriteMaterial, Texture, Vector3, Vector4,
} from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { HDRLoader } from 'three/examples/jsm/loaders/HDRLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';
import { isInspectable, itemKey } from './tour.js';
import { register } from './registry.js';

const withMeshopt = (loader) => loader.setMeshoptDecoder(MeshoptDecoder);
// RGBM keeps its colour and its multiplier (alpha) apart: the browser must not premultiply them
const rgbmOptions = (l) => l.setOptions?.({ imageOrientation: 'none', premultiplyAlpha: 'none', colorSpaceConversion: 'none' }) ?? l;

const CRYSTAL_GAIN = 1.6; // crystal brightness before tone mapping
const GLOW = 0.12; // strength of the soft glow around each lit chandelier (0 turns it off)
const MATTE_SHEEN = 0.035; // share of the surrounding light a matte surface mirrors at a grazing angle
const MATTE_LOSS = 0.4; // and the share of its own colour it gives up there
const SATIN_SPEC = 0.15; // share of the reflections (room and lamps) that satin wood and painted icons keep
const ICON_SPEC = 0.04; // and the share the painted icons and curtains keep: next to none, so they stay readable
const WIN_LEVEL = 0.24; // stained glass at night: its own colours at an even, modest level (a lit white wall is about 0.8)
const WIN_SATURATION = 1.3;
const SANCTUARY_LEVEL = 0.14; // light on the sanctuary's walls (a lit nave wall is about 0.8)
const SPEC_OCC = 6.0; // reflections fade where the baked light is dark (under the pews), full above 1/6 of white

// The chandelier lamps are point lights in Blender, so the probe cannot see them; their highlights on varnish and
// metal (the bright pools on the ceiling in the Cycles renders and the photos) are drawn here. Each lamp is a small
// sphere light with a GGX highlight (Karis' representative point), specular only: the diffuse light is baked.
// Because it follows the shaded normal, the board profile on the ceiling and the pews' bevels shape it, and at a
// grazing view it stretches along the line of sight as it does in the real room.
const MAX_LAMPS = 12;
const LAMP_SIZE = 0.4; // measured on the check renders: the lamps' mirror images are under half as wide as their radius says
const LAMP_GAIN = 1.6; // overall strength of the lamp highlights
const LAMPS_GLSL = `
uniform vec4 uLamps[ ${MAX_LAMPS} ];
uniform float uLampR;
uniform float uLampRough;
uniform float uLampGain;
uniform vec3 uLampColor;
vec3 churchLamps( vec3 n, vec3 v, vec3 p, float rough ) {
  float a = max( rough * rough, 0.003 ), nv = max( dot( n, v ), 0.03 ), acc = 0.0;
  vec3 r = reflect( - v, n );
  for ( int i = 0; i < ${MAX_LAMPS}; i ++ ) {
    vec3 L = uLamps[ i ].xyz - p;
    vec3 c2r = dot( L, r ) * r - L;
    vec3 cp = L + c2r * clamp( uLampR / max( length( c2r ), 1e-4 ), 0.0, 1.0 );
    float d2 = dot( cp, cp ), nl = dot( n, cp ) * inversesqrt( d2 );
    if ( nl <= 0.0 ) continue;
    vec3 h = normalize( cp * inversesqrt( d2 ) + v );
    float nh = clamp( dot( n, h ), 0.0, 1.0 );
    float a2 = clamp( a + 0.5 * uLampR * inversesqrt( d2 ), 0.0, 1.0 );
    float dn = nh * nh * ( a * a - 1.0 ) + 1.0;
    float D = ( a * a / ( 3.14159 * dn * dn ) ) * ( a * a / ( a2 * a2 ) );
    float V = 0.5 / ( nl * ( nv * ( 1.0 - a ) + a ) + nv * ( nl * ( 1.0 - a ) + a ) );
    acc += D * V * nl * uLamps[ i ].w * 3.14159 * uLampR * uLampR / d2;
  }
  return uLampColor * min( acc, 60.0 );
}
`;

function rgbmLightmap(shader) {
  shader.fragmentShader = shader.fragmentShader
    .replace('#include <lights_fragment_maps>', ShaderChunk.lights_fragment_maps)
    .replaceAll('lightMapTexel.rgb * lightMapIntensity', 'lightMapTexel.rgb * lightMapTexel.a * lightMapIntensity');
}

// Glossy surfaces: lightmap for the diffuse part, the probe for reflections only (its diffuse share is already in
// the lightmap), looked up where the reflected ray meets the room's box
function glossy(mat, info, lampRough, lampGain) {
  mat.onBeforeCompile = (shader) => {
    mat.userData.shader = shader;
    shader.uniforms.uLampRough = { value: lampRough };
    shader.uniforms.uLampGain = { value: lampGain };
    shader.uniforms.uBoxMin = { value: info.boxMin };
    shader.uniforms.uBoxMax = { value: info.boxMax };
    shader.uniforms.uProbe = { value: info.probe };
    shader.uniforms.uLamps = { value: info.lamps };
    shader.uniforms.uLampR = { value: info.lampR };
    shader.uniforms.uLampColor = { value: info.lampColor };
    shader.vertexShader = 'varying vec3 vWPos;\n' + shader.vertexShader
      .replace('#include <project_vertex>', '#include <project_vertex>\n\tvWPos = ( modelMatrix * vec4( transformed, 1.0 ) ).xyz;\n\t#ifdef USE_INSTANCING\n\tvWPos = ( modelMatrix * instanceMatrix * vec4( transformed, 1.0 ) ).xyz;\n\t#endif');
    rgbmLightmap(shader);
    shader.fragmentShader = 'varying vec3 vWPos;\nuniform vec3 uBoxMin;\nuniform vec3 uBoxMax;\nuniform vec3 uProbe;\n' + LAMPS_GLSL + shader.fragmentShader
      .replace('iblIrradiance += getIBLIrradiance( geometryNormal );', '')
      .replace('vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );', // the sanctuary's even, dim light: see matte()
        `vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
        if ( vWPos.z < uBoxMin.z - 0.05 ) lightMapTexel = vec4( vec3( 1.0, 0.93, 0.84 ) * ${(SANCTUARY_LEVEL / info.range).toFixed(5)}, 1.0 );`)
      .replace('vec3 iblRadiance = getIBLRadiance( geometryViewDir, geometryNormal, material.roughness );',
        'vec3 iblRadiance = getIBLRadiance( geometryViewDir, geometryNormal, material.roughness );\n' +
        '\tiblRadiance += churchLamps( transformDirectionByInverseViewMatrix( geometryNormal, viewMatrix ), transformDirectionByInverseViewMatrix( geometryViewDir, viewMatrix ), vWPos, uLampRough ) * uLampGain;\n' +
        '#ifdef USE_LIGHTMAP\n\tiblRadiance *= clamp( dot( lightMapIrradiance, vec3( 0.3333 ) ) * ' + (SPEC_OCC / Math.PI).toFixed(3) + ', 0.0, 1.0 );\n#endif')
      .replace('#include <envmap_physical_pars_fragment>', ShaderChunk.envmap_physical_pars_fragment.replace(
        'reflectVec = transformDirectionByInverseViewMatrix( reflectVec, viewMatrix );',
        'reflectVec = transformDirectionByInverseViewMatrix( reflectVec, viewMatrix );\n' +
        '\t\t\tvec3 rbA = ( uBoxMax - vWPos ) / reflectVec; vec3 rbB = ( uBoxMin - vWPos ) / reflectVec;\n' +
        '\t\t\tvec3 rbM = max( rbA, rbB ); float rbT = max( min( min( rbM.x, rbM.y ), rbM.z ), 0.0 );\n' +
        '\t\t\treflectVec = normalize( vWPos + reflectVec * rbT - uProbe );'));
  };
  mat.customProgramCacheKey = () => 'church-glossy';
  return mat;
}

// Matte surfaces (plaster, carpet, cushions): albedo x lightmap, plus the pale sheen a rough surface shows at
// grazing angles (in the Cycles renders the far carpet and the cushions are visibly less red than their paint).
// The sheen reflects the light around it, for which the lightmap itself is a fair stand-in.
// The sanctuary behind the iconostasis is an unlit room seen through the arch: only spill light reaches it, which
// bakes into a noisy, too-bright lightmap. Its walls take one dim, even, slightly warm level instead.
function matte(mat, info) {
  mat.onBeforeCompile = (shader) => {
    rgbmLightmap(shader);
    shader.uniforms.uSanctZ = { value: info.boxMin.z };
    shader.vertexShader = 'varying vec3 vVP;\nvarying float vWZ;\n' + shader.vertexShader
      .replace('#include <project_vertex>', '#include <project_vertex>\n\tvVP = - mvPosition.xyz;\n\tvWZ = ( modelMatrix * vec4( transformed, 1.0 ) ).z;');
    shader.fragmentShader = 'varying vec3 vVP;\nvarying float vWZ;\nuniform float uSanctZ;\n' + shader.fragmentShader
      .replace('vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );',
        `vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
        if ( vWZ < uSanctZ - 0.05 ) lightMapTexel = vec4( vec3( 1.0, 0.93, 0.84 ) * ${(SANCTUARY_LEVEL / info.range).toFixed(5)}, 1.0 );`)
      .replace('vec3 outgoingLight = reflectedLight.indirectDiffuse;', `
        vec3 mN = normalize( cross( dFdx( vVP ), dFdy( vVP ) ) );
        float mGraze = 0.4 + 0.6 * pow( 1.0 - abs( dot( mN, normalize( vVP ) ) ), 3.0 );
        vec3 outgoingLight = reflectedLight.indirectDiffuse * ( 1.0 - ${MATTE_LOSS.toFixed(2)} * mGraze ) + lightMapTexel.rgb * lightMapTexel.a * lightMapIntensity * RECIPROCAL_PI * ${MATTE_SHEEN.toFixed(3)} * mGraze;`);
  };
  mat.customProgramCacheKey = () => 'church-matte';
  return mat;
}

// Stained glass in the evening: no daylight behind it, so it shows as its own picture, evenly and modestly lit,
// colours deep and the lead lines dark. It takes no reflection of the room, no lamp glare and no lightmap: the
// glass in Blender is a dark, mirror-smooth surface (base colour x 0.16), and as a real reflector its faint colour
// drowned under a milky image of the white walls.
function stainedGlass(map) {
  if (map) map.anisotropy = 8;
  const m = new MeshBasicMaterial({ map });
  m.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader.replace('vec3 outgoingLight = reflectedLight.indirectDiffuse;', `
        float wLum = dot( diffuseColor.rgb, vec3( 0.2126, 0.7152, 0.0722 ) );
        vec3 outgoingLight = max( mix( vec3( wLum ), diffuseColor.rgb, ${WIN_SATURATION.toFixed(2)} ), 0.0 ) * ${WIN_LEVEL.toFixed(2)};`);
  };
  m.customProgramCacheKey = () => 'church-glass';
  return m;
}

// Crystals as glass, in one unlit pass. A facet is dark glass with a pale rim; it lights up where it faces the
// viewer (the lamp inside shining through), and it flashes when its mirror direction passes one of a few sharp
// angles that differ per crystal (the seeds are in the vertex colour: R = sparkle, G = a second phase). The
// flashes carry a little spectral colour, as cut crystal does, and since they depend on the view direction the
// chandeliers twinkle whenever the camera moves.
function crystal() {
  const m = new MeshBasicMaterial({ vertexColors: true, color: '#ffffff' });
  m.onBeforeCompile = (shader) => {
    shader.vertexShader = 'varying vec3 vVP;\n' + shader.vertexShader
      .replace('#include <project_vertex>', '#include <project_vertex>\n\tvVP = - mvPosition.xyz;');
    shader.fragmentShader = 'varying vec3 vVP;\n' + shader.fragmentShader
      .replace('vec3 outgoingLight = reflectedLight.indirectDiffuse;', `
        vec3 cN = normalize( cross( dFdx( vVP ), dFdy( vVP ) ) );
        vec3 cV = normalize( vVP );
        float cFace = abs( dot( cN, cV ) );
        float cSeed = vColor.r, cSeed2 = vColor.g;
        vec3 cR = reflect( - cV, cN );
        vec3 cBody = vec3( 0.07, 0.075, 0.085 ) + vec3( 0.6, 0.62, 0.66 ) * pow( 1.0 - cFace, 3.0 );
        float cThrough = pow( cFace, 4.0 ) * ( 0.45 + 0.55 * cSeed2 );
        float cPh = dot( cR, vec3( 31.0, 47.0, 23.0 ) ) + cSeed * 61.0;
        float cPh2 = dot( cR, vec3( - 53.0, 29.0, 67.0 ) ) + cSeed2 * 37.0;
        float cFlash = pow( 0.5 + 0.5 * sin( cPh ), 24.0 );
        float cSpark = pow( 0.5 + 0.5 * sin( cPh2 ), 70.0 ) * ( 1.0 + 4.0 * step( 0.8, cSeed ) );
        vec3 cHue = 0.5 + 0.5 * cos( 6.2831 * ( cPh * 0.07 + cSeed2 + vec3( 0.0, 0.33, 0.67 ) ) );
        vec3 outgoingLight = cBody + vec3( 1.0, 0.94, 0.84 ) * cThrough * 3.2
          + mix( vec3( 1.0, 0.97, 0.92 ), cHue, 0.45 ) * cFlash * 7.0 + mix( vec3( 1.0 ), cHue, 0.3 ) * cSpark * 22.0;
        outgoingLight *= ${CRYSTAL_GAIN.toFixed(2)};`);
  };
  m.customProgramCacheKey = () => 'church-crystal';
  return m;
}

// A soft glow around each lit chandelier, standing in for the bloom a camera gives them: one additive sprite per lamp
function glowSprites(info) {
  const c = document.createElement('canvas');
  c.width = c.height = 128;
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, 'rgba(255,255,255,1)'); grad.addColorStop(0.3, 'rgba(255,255,255,0.62)');
  grad.addColorStop(0.6, 'rgba(255,255,255,0.24)'); grad.addColorStop(0.85, 'rgba(255,255,255,0.05)'); grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad; g.fillRect(0, 0, 128, 128);
  const map = new CanvasTexture(c);
  const mat = new SpriteMaterial({ map, color: new Color().setRGB(1, 0.9, 0.74).multiplyScalar(GLOW), blending: AdditiveBlending, depthWrite: false, transparent: true });
  const group = new Group();
  group.name = 'ChandelierGlow';
  for (const l of info.lamps) {
    if (!l.w) continue;
    const watts = l.w * LAMP_SIZE * LAMP_SIZE * 4 * Math.PI * Math.PI * info.lampRadius * info.lampRadius;
    const s = new Sprite(mat);
    s.position.set(l.x, l.y + 0.15, l.z);
    s.scale.setScalar(1.6 + 0.12 * Math.sqrt(watts));
    s.renderOrder = 10;
    group.add(s);
  }
  return { group, dispose: () => { map.dispose(); mat.dispose(); } };
}

function lightmapOf(o) {
  for (let p = o; p; p = p.parent) if (p.userData?.lm) return p.userData.lm;
  return null;
}

export function Model() {
  const gltf = useLoader(GLTFLoader, './church.glb', withMeshopt);
  const { gl, invalidate } = useThree();
  const info = useMemo(() => {
    const u = gltf.scene.userData;
    return {
      range: u.lm_range ?? 8,
      exposure: u.exposure ?? -1.2,
      env: './' + (u.env ?? 'lm/env.hdr'),
      probe: new Vector3(...(u.probe ?? [0, 3.2, -8.75])),
      boxMin: new Vector3(...(u.box_min ?? [-5.5, 0, -17.8])),
      boxMax: new Vector3(...(u.box_max ?? [5.5, 6.6, 0])),
      lamps: Array.from({ length: MAX_LAMPS }, (_, i) => { const l = u.lamps || []; return new Vector4(l[i * 5] ?? 0, l[i * 5 + 1] ?? 0, l[i * 5 + 2] ?? 0, (l[i * 5 + 3] ?? 0) / (LAMP_SIZE * LAMP_SIZE)); }),
      lampR: (u.lamps?.[4] ?? 0.35) * LAMP_SIZE,
      lampRadius: u.lamps?.[4] ?? 0.35,
      lampColor: new Color().setRGB(...(u.lamp_color ?? [1, 0.86, 0.72])),
    };
  }, [gltf]);
  const lmFiles = useMemo(() => {
    const s = new Set();
    gltf.scene.traverse((o) => { if (o.userData?.lm) s.add(o.userData.lm); });
    return [...s];
  }, [gltf]);
  const bitmaps = useLoader(ImageBitmapLoader, lmFiles.map((f) => './' + f), rgbmOptions);
  const hdr = useLoader(HDRLoader, info.env);

  // Tone mapping as in the Cycles check renders
  useEffect(() => {
    const keep = [gl.toneMapping, gl.toneMappingExposure];
    gl.toneMapping = AgXToneMapping;
    gl.toneMappingExposure = 2 ** info.exposure;
    invalidate();
    return () => { [gl.toneMapping, gl.toneMappingExposure] = keep; };
  }, [gl, info, invalidate]);

  // Materials
  useEffect(() => {
    const pmrem = new PMREMGenerator(gl);
    const env = pmrem.fromEquirectangular(hdr).texture;
    pmrem.dispose();
    const lms = {};
    lmFiles.forEach((f, i) => {
      const t = new Texture(bitmaps[i]);
      t.colorSpace = SRGBColorSpace; t.premultiplyAlpha = false; t.flipY = false; t.channel = 1;
      t.generateMipmaps = false; t.minFilter = LinearFilter; t.needsUpdate = true; // mips would average RGBM across island edges
      lms[f] = t;
    });
    const made = new Map();
    const crystalMat = crystal();
    const convert = (src, lm) => {
      const key = src.uuid + '|' + (lm || '');
      if (made.has(key)) return made.get(key);
      const kind = src.userData?.kind;
      let m;
      if (kind === 'crystal') m = crystalMat;
      else if (/^P_Win_/.test(src.name)) m = stainedGlass(src.map);
      else {
        const lightMap = lm ? lms[lm] : null;
        const metal = src.metalness >= 0.5;
        const flat = !metal && src.roughness > 0.5 && !(src.emissiveIntensity > 0 && src.emissive.getHex());
        const color = src.color.clone();
        if (Array.isArray(src.userData?.tint)) color.multiply(new Color().setRGB(...src.userData.tint));
        if (src.map) src.map.anisotropy = 8;
        if (flat && lightMap) {
          m = matte(new MeshBasicMaterial({ map: src.map, color, lightMap, lightMapIntensity: Math.PI * info.range }), info);
        } else {
          // Mirrors (glass, screens), metal and clear-coated wood (ceiling, pews, shrines) reflect at full strength.
          // Plain satin wood and the painted icons show far less of it in the Cycles renders than their roughness
          // alone would give (their bump breaks the reflection up), so they take a fraction.
          const full = metal || src.roughness <= 0.15 || src.userData?.coat > 0;
          const icon = !full && !!lm && lm.includes('lm_pics'); // a painted icon or curtain: keep it clear of glare
          const spec = full ? 1 : icon ? ICON_SPEC : SATIN_SPEC;
          m = glossy(new MeshStandardMaterial({
            map: src.map, color, roughness: src.roughness, metalness: src.metalness,
            normalMap: src.normalMap, normalScale: src.normalScale,
            emissive: src.emissive, emissiveMap: src.emissiveMap, emissiveIntensity: src.emissiveIntensity,
            lightMap: metal ? null : lightMap, lightMapIntensity: Math.PI * info.range, envMap: env,
            envMapIntensity: spec,
          }), info, src.userData?.coat || src.roughness, spec * LAMP_GAIN);
        }
      }
      m.name = src.name;
      made.set(key, m);
      return m;
    };
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      if (!o.userData.srcMaterial) o.userData.srcMaterial = o.material;
      o.material = convert(o.userData.srcMaterial, lightmapOf(o));
    });
    const glow = GLOW > 0 ? glowSprites(info) : null;
    if (glow) gltf.scene.add(glow.group);
    window.__tourScene = gltf.scene; // for scripts/compare.mjs
    invalidate();
    return () => {
      if (glow) { gltf.scene.remove(glow.group); glow.dispose(); }
      made.forEach((m) => m.dispose());
      Object.values(lms).forEach((t) => t.dispose());
      env.dispose();
    };
  }, [gltf, gl, hdr, bitmaps, lmFiles, info, invalidate]);

  // Things a visitor can choose; a named group counts once, not once per mesh inside it
  useEffect(() => {
    const undo = [];
    gltf.scene.traverse((o) => {
      if (!isInspectable(o.name) || !itemKey(o.name)) return; // only what the tour has text for (not the altar windows)
      for (let p = o.parent; p; p = p.parent) if (isInspectable(p.name)) return; // its parent already stands for it
      undo.push(register(o));
    });
    invalidate();
    return () => undo.forEach((f) => f());
  }, [gltf, invalidate]);
  return <primitive object={gltf.scene} />;
}
