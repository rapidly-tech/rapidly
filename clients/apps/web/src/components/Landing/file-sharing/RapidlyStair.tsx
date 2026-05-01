'use client'

import { CHAMBERS } from '@/components/Revolver/chambers'
import { CycleRaycast, Text, useCursor } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useRouter } from 'next/navigation'
import { useRef, useState } from 'react'
import type { Mesh } from 'three'

// Frosted-glass spiral stair where each panel = one chamber. Click
// a panel to navigate to that chamber. Hover scales with a pulse.
// The visual story: six chambers stacked into one stair — pick the
// kind of share you want and walk into it.

interface PanelProps {
  index: number
  label: string
  href: string
  tagline: string
}

function Panel({ index, label, href, tagline }: PanelProps) {
  const router = useRouter()
  const ref = useRef<Mesh>(null)
  const [hovered, setHovered] = useState(false)

  useFrame(({ clock }) => {
    if (!ref.current) return
    ref.current.scale.setScalar(
      hovered ? 1 + Math.sin(clock.elapsedTime * 10) / 50 : 1,
    )
  })

  useCursor(hovered)

  // Spread 6 panels across what was originally a 12-step spiral so
  // the curve is still visible. Effective ``stride`` of 2x lays
  // out the same arc with half as many treads.
  const stride = index * 2

  return (
    <mesh
      rotation={[-Math.PI / 2, 0, stride / Math.PI / 2]}
      position={[
        2 - Math.sin(stride / 5) * 5,
        index * 0.9,
        2 - Math.cos(stride / 5) * 5,
      ]}
      ref={ref}
      onClick={(e) => {
        e.stopPropagation()
        router.push(href)
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
        opacity={0.65}
        color={hovered ? 'aquamarine' : 'white'}
      />
      {/* Chamber label — chamber name + small tagline.
          Positioned just off the panel surface so it isn't
          z-fighting. Inherits the panel's rotation, so it lies
          flat with the panel. */}
      <Text
        position={[0, 0, 0.05]}
        fontSize={0.6}
        color="#1f2937"
        anchorX="center"
        anchorY="middle"
        maxWidth={5.5}
      >
        {label}
      </Text>
      <Text
        position={[0, -0.85, 0.05]}
        fontSize={0.22}
        color="#475569"
        anchorX="center"
        anchorY="middle"
        maxWidth={5.5}
      >
        {tagline}
      </Text>
    </mesh>
  )
}

const Stage: React.FC = () => {
  return (
    <>
      {/* Fill */}
      <ambientLight intensity={0.5} />

      {/* Main */}
      <directionalLight position={[1, 10, -2]} intensity={1} />

      {/* Strip */}
      <directionalLight position={[-10, -10, 2]} intensity={3} />
    </>
  )
}

export function RapidlyStair() {
  return (
    <Canvas
      camera={{ position: [-10, 10, 5], fov: 50 }}
      dpr={[1, 1.5]}
      style={{ width: '100%', height: '100%' }}
    >
      <Stage />
      {CHAMBERS.slice(0, 6).map((chamber, i) => (
        <Panel
          key={chamber.id}
          index={i}
          label={chamber.label}
          href={chamber.href}
          tagline={chamber.tagline}
        />
      ))}
      <CycleRaycast />
    </Canvas>
  )
}
