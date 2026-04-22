/**
 * PartPreview3D — proxy 3D visualisation of an uploaded CAD part.
 *
 * We don't render the real STEP mesh (that requires heavy server-side
 * conversion or a WASM library in the browser). Instead we render a
 * sketched "blueprint" proxy using the geometry metadata our extractor
 * already captures:
 *
 *   • bounding_box_estimate → proxy shape dimensions
 *   • geometry.circles vs geometry.lines → shape classification (cylinder vs box)
 *   • appearance.colours_rgb[0] → hint colour
 *
 * Style: cream parchment background, sepia wireframe edges, ghost-fill,
 * axes helper and grid. Fits the warm old-paper aesthetic of the app.
 */

import { Suspense, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Edges, GizmoHelper, GizmoViewport, Html } from '@react-three/drei';
import * as THREE from 'three';
import type { ExtractionResult } from '../../api/types';

interface PartPreview3DProps {
  result: ExtractionResult | null | undefined;
  className?: string;
}

// ── Palette (matches the warm paper theme) ───────────────────────────────────
const SEPIA_INK   = '#3D2F1F';
const SEPIA_SOFT  = '#6B5A3F';
const PAPER_BG    = '#F3E7CE';
const PAPER_LIGHT = '#F8F0DC';
const TERRACOTTA  = '#C66A4E';

// ── Proxy shape classification ────────────────────────────────────────────────
type ProxyKind = 'cylinder' | 'box' | 'thin-plate' | 'sphere';

function classifyProxy(result: ExtractionResult | null | undefined): {
  kind: ProxyKind;
  dims: [number, number, number]; // normalised dims, longest axis = 1
  rawDims: { x: number; y: number; z: number } | null;
} {
  const bb = result?.spatial?.bounding_box_estimate;
  const geom = result?.geometry;

  // Fallback if we have no bbox
  const fallback: { x: number; y: number; z: number } = { x: 1, y: 1, z: 1 };
  const raw = bb && bb.x > 0 && bb.y > 0 && bb.z > 0 ? bb : null;
  const base = raw ?? fallback;

  // Normalise: longest axis = 1.4 (fills view nicely), shorter axes proportional
  const max = Math.max(base.x, base.y, base.z);
  const scale = 1.4 / max;
  const dims: [number, number, number] = [base.x * scale, base.y * scale, base.z * scale];

  // Shape classifier
  const circles = (geom?.circles ?? 0) as number;
  const lines = (geom?.lines ?? 0) as number;
  const ratio = Math.max(base.x, base.y) / Math.max(base.z, 0.01);

  let kind: ProxyKind = 'box';
  if (circles > lines * 1.5 && circles > 4) {
    // Mostly cylindrical surfaces
    if (ratio > 3 || ratio < 0.33) kind = 'cylinder';
    else kind = 'sphere';
  } else if (base.z > 0 && base.z < Math.min(base.x, base.y) * 0.15) {
    kind = 'thin-plate';
  } else {
    kind = 'box';
  }

  return { kind, dims, rawDims: raw };
}

// ── Animated proxy mesh ───────────────────────────────────────────────────────
function PartMesh({ kind, dims }: { kind: ProxyKind; dims: [number, number, number] }) {
  const group = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (group.current) {
      group.current.rotation.y += dt * 0.12; // slow idle spin
    }
  });

  const [dx, dy, dz] = dims;

  let geometry: React.ReactNode;
  if (kind === 'cylinder') {
    // Cylinder: radius from shorter axis, height from longest
    const h = Math.max(dx, dy, dz);
    const r = Math.min(dx, dy, dz) * 0.5;
    geometry = (
      <mesh castShadow>
        <cylinderGeometry args={[r, r, h, 48, 1]} />
        <meshStandardMaterial
          color={PAPER_LIGHT}
          roughness={0.85}
          metalness={0.05}
          transparent
          opacity={0.92}
        />
        <Edges threshold={15} color={SEPIA_INK} />
      </mesh>
    );
  } else if (kind === 'sphere') {
    const r = Math.max(dx, dy, dz) * 0.5;
    geometry = (
      <mesh>
        <sphereGeometry args={[r, 48, 32]} />
        <meshStandardMaterial
          color={PAPER_LIGHT}
          roughness={0.85}
          metalness={0.05}
          transparent
          opacity={0.92}
        />
        <Edges threshold={15} color={SEPIA_INK} />
      </mesh>
    );
  } else {
    geometry = (
      <mesh>
        <boxGeometry args={[dx, dy, dz]} />
        <meshStandardMaterial
          color={PAPER_LIGHT}
          roughness={0.85}
          metalness={0.05}
          transparent
          opacity={0.92}
        />
        <Edges threshold={1} color={SEPIA_INK} />
      </mesh>
    );
  }

  return <group ref={group}>{geometry}</group>;
}

// ── Scene ─────────────────────────────────────────────────────────────────────
function Scene({ result }: { result: ExtractionResult | null | undefined }) {
  const { kind, dims, rawDims } = useMemo(() => classifyProxy(result), [result]);

  return (
    <>
      {/* Lights — warm key, cool fill, soft ambient */}
      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 5, 3]} intensity={0.85} color="#FFE9B8" />
      <directionalLight position={[-3, 2, -4]} intensity={0.35} color="#C8D8E0" />

      <Suspense fallback={null}>
        <PartMesh kind={kind} dims={dims} />
      </Suspense>

      {/* Ground grid — paper colour */}
      <gridHelper
        args={[8, 16, TERRACOTTA, SEPIA_SOFT]}
        position={[0, -Math.max(...dims) * 0.55, 0]}
      />

      {/* Axes helper */}
      <axesHelper args={[1.2]} />

      {/* Dimension overlay (SVG-in-html so it rotates with camera) */}
      {rawDims && (
        <Html position={[0, Math.max(...dims) * 0.7, 0]} center>
          <div
            className="text-[10px] font-mono whitespace-nowrap px-2 py-0.5 rounded"
            style={{
              color: SEPIA_INK,
              background: PAPER_BG,
              border: `1px solid ${SEPIA_SOFT}40`,
              opacity: 0.9,
            }}
          >
            {rawDims.x.toFixed(1)} × {rawDims.y.toFixed(1)} × {rawDims.z.toFixed(1)}
          </div>
        </Html>
      )}
    </>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export function PartPreview3D({ result, className }: PartPreview3DProps) {
  const hasBbox = !!result?.spatial?.bounding_box_estimate;

  return (
    <div
      className={className}
      style={{
        position: 'relative',
        width: '100%',
        minHeight: 360,
        background: `radial-gradient(ellipse at center, ${PAPER_LIGHT} 0%, ${PAPER_BG} 100%)`,
        border: '1px solid #E8D6AC',
        borderRadius: 10,
        overflow: 'hidden',
      }}
    >
      {/* Paper grain noise overlay */}
      <svg
        aria-hidden="true"
        style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.08, mixBlendMode: 'multiply' }}
        width="100%" height="100%"
      >
        <filter id="pp3d-noise">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" stitchTiles="stitch" />
          <feColorMatrix values="0 0 0 0 0.24   0 0 0 0 0.18   0 0 0 0 0.12   0 0 0 0.55 0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#pp3d-noise)" />
      </svg>

      {!hasBbox && (
        <div
          className="absolute inset-0 flex flex-col items-center justify-center text-center px-6"
          style={{ color: SEPIA_SOFT }}
        >
          <p className="font-display text-[15px] italic mb-1">No geometry captured yet</p>
          <p className="text-[11px]">Bounding box missing — proxy preview unavailable</p>
        </div>
      )}

      {hasBbox && (
        <Canvas
          camera={{ position: [2.4, 1.8, 2.8], fov: 40 }}
          dpr={[1, 2]}
          style={{ position: 'relative' }}
        >
          <Scene result={result} />
          <OrbitControls
            enablePan
            enableZoom
            enableRotate
            autoRotate={false}
            minDistance={1.5}
            maxDistance={10}
          />
          <GizmoHelper alignment="bottom-right" margin={[70, 70]}>
            <GizmoViewport
              axisColors={['#B63F2A', '#5E7E52', '#5B6FA3']}
              labelColor={SEPIA_INK}
            />
          </GizmoHelper>
        </Canvas>
      )}

      {/* Caption — "Proxy preview" disclosure */}
      <div
        className="absolute bottom-2 left-3 text-[10px] font-display italic pointer-events-none"
        style={{ color: SEPIA_SOFT, opacity: 0.75 }}
      >
        proxy preview · derived from extracted geometry
      </div>
    </div>
  );
}
