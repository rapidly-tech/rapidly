'use client'

import { CycleRaycast, useCursor } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useRef, useState } from 'react'
import type { Mesh } from 'three'

// Frosted-glass stair scene — twelve translucent panels arranged
// in a spiral. Hover scales a panel with a subtle pulse; click
// toggles a tint. The visual story for Rapidly: layered,
// translucent, private.

interface Props {
  name: string
  index: number
}

const RaycastCyclingStair: React.FC = () => {
  return (
    <>
      <Stage />
      {Array.from({ length: 12 }, (_, i) => (
        <Stair key={i} name={'stair-' + (i + 1)} index={i} />
      ))}

      {/* This component cycles through the raycast intersections, combine it with event.stopPropagation! */}
      <CycleRaycast />
    </>
  )
}

const Stair: React.FC<Props> = ({ index }) => {
  const ref = useRef<Mesh>(null)

  const [hovered, setHovered] = useState(false)
  const [clicked, setClicked] = useState(false)

  useFrame(({ clock }) => {
    if (!ref.current) return
    ref.current.scale.setScalar(
      hovered ? 1 + Math.sin(clock.elapsedTime * 10) / 50 : 1,
    )
  })

  // Sets document.body.style.cursor: useCursor(flag, onPointerOver = 'pointer', onPointerOut = 'auto')
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
        color={clicked ? 'violet' : hovered ? 'aquamarine' : 'white'}
      />
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
      <RaycastCyclingStair />
    </Canvas>
  )
}
