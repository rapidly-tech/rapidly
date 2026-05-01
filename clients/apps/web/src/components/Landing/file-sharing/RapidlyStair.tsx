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

      {/* Main directional — casts soft shadows */}
      <directionalLight
        position={[1, 10, -2]}
        intensity={isDark ? 1.5 : 1}
        shadow-camera-far={70}
        shadow-camera-left={-10}
        shadow-camera-right={10}
        shadow-camera-top={10}
        shadow-camera-bottom={-10}
        shadow-mapSize={[1024, 1024]}
        castShadow
      />

      {/* Strip / rim light from the back */}
      <directionalLight position={[-10, -10, 2]} intensity={3} />

      {/* Ground plane to receive the shadow */}
      <mesh receiveShadow rotation-x={-Math.PI / 2} position={[0, -0.75, 0]}>
        <planeGeometry args={[20, 20]} />
        <shadowMaterial opacity={isDark ? 0.35 : 0.2} />
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
      camera={{ position: [-10, 5, 12], fov: 35 }}
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
