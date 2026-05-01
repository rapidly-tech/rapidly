'use client'

import { BakeShadows, CycleRaycast, useCursor } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useRef, useState } from 'react'
import type { Mesh } from 'three'

// Adapted from Paul Henschel's "raycast cycling stair" R3F demo
// (pmh-showcase-main/src/components/canvas/raycast-cycling-stair.tsx).
// Twelve frosted-glass panels arranged in a spiral — hover scales
// the panel, click toggles the colour. The visual story for
// Rapidly: layered, translucent, private — you can sense the shape
// of what's moving but not see through it.
//
// Pure decoration in this first cut. Chamber semantics (one panel
// per chamber, click → navigate) are a follow-up.

interface PanelProps {
  index: number
}

function Panel({ index }: PanelProps) {
  const ref = useRef<Mesh>(null)
  const [hovered, setHovered] = useState(false)
  const [clicked, setClicked] = useState(false)

  useFrame(({ clock }) => {
    if (!ref.current) return
    ref.current.scale.setScalar(
      hovered ? 1 + Math.sin(clock.elapsedTime * 10) / 50 : 1,
    )
  })

  // Sets document.body.style.cursor on hover.
  useCursor(hovered)

  return (
    <mesh
      rotation={[-Math.PI / 2, 0, index / Math.PI / 2]}
      position={[
        2 - Math.sin(index / 5) * 5,
        index * 0.5,
        2 - Math.cos(index / 5) * 5,
      ]}
      ref={ref}
      receiveShadow
      castShadow
      onClick={(e) => {
        e.stopPropagation()
        setClicked(!clicked)
      }}
      onPointerOver={(e) => {
        e.stopPropagation()
        setHovered(true)
      }}
      onPointerOut={() => setHovered(false)}
    >
      <boxGeometry args={[2, 6, 0.075]} />
      <meshStandardMaterial
        roughness={1}
        metalness={1}
        transparent
        opacity={0.6}
        // Click cycles a soft warm tint; hover hints emerald
        // (Rapidly's accent); idle stays close to the page so the
        // scene reads as ""glass on cream"" not ""coloured shapes"".
        color={clicked ? '#d97757' : hovered ? '#10b981' : '#ffffff'}
      />
    </mesh>
  )
}

interface StageProps {
  isDark: boolean
}

function Stage({ isDark }: StageProps) {
  return (
    <>
      {/* Fill light */}
      <ambientLight intensity={isDark ? 0.3 : 0.5} />

      {/* Main directional — casts shadows. Tighter frustum +
          higher-res shadow map = cleaner penumbra without ramping
          up cost. */}
      <directionalLight
        position={[5, 12, 5]}
        intensity={isDark ? 1.5 : 1.2}
        shadow-camera-far={50}
        shadow-camera-left={-8}
        shadow-camera-right={8}
        shadow-camera-top={8}
        shadow-camera-bottom={-8}
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0005}
        castShadow
      />

      {/* Strip / rim light from the back */}
      <directionalLight position={[-10, -10, 2]} intensity={2} />

      {/* Ground plane to receive the shadow — opacity dialled down
          so the shadow reads as ambient grounding, not a
          dominant blob. */}
      <mesh receiveShadow rotation-x={-Math.PI / 2} position={[0, -0.75, 0]}>
        <planeGeometry args={[30, 30]} />
        <shadowMaterial opacity={isDark ? 0.2 : 0.12} />
      </mesh>

      {/* Freezes shadow map — fast, model is static so it's safe */}
      <BakeShadows />
    </>
  )
}

interface RapidlyStairProps {
  isDark?: boolean
}

export function RapidlyStair({ isDark = false }: RapidlyStairProps) {
  return (
    <Canvas
      // ``shadows="soft"`` selects PCFSoftShadowMap which uses the
      // current Three.js shadow shader. We dropped drei's
      // ``<SoftShadows />`` because its injected shader still calls
      // ``unpackRGBAToDepth``, removed in Three r163+.
      shadows="soft"
      // 3/4 view from upper-right — matches the original demo's
      // composition where the spiral travels away into the frame.
      camera={{ position: [10, 8, 10], fov: 35 }}
      gl={{ antialias: true, alpha: true }}
      style={{ width: '100%', height: '100%' }}
    >
      <Stage isDark={isDark} />
      {Array.from({ length: 12 }, (_, i) => (
        <Panel key={i} index={i} />
      ))}
      {/* Cycles raycast intersections so click events go to the
          panel under the cursor even when others overlap. */}
      <CycleRaycast />
    </Canvas>
  )
}
