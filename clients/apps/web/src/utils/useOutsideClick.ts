'use client'

import { RefObject, useCallback, useEffect, useRef } from 'react'

type NullableRef = RefObject<HTMLElement | null> | undefined

const isScrollbarClick = (event: MouseEvent): boolean =>
  event.target === document.documentElement &&
  event.clientX >= document.documentElement.offsetWidth

const isContainedInRef = (ref: NullableRef, target: Node): boolean =>
  Boolean(ref?.current?.contains(target))

const isClickInsideAnyRef = (refs: NullableRef[], target: Node): boolean =>
  refs.some((ref) => isContainedInRef(ref, target))

export function useOutsideClick(refs: NullableRef[], handler?: () => void) {
  const refsRef = useRef(refs)
  refsRef.current = refs

  const handleMouseDown = useCallback(
    (event: MouseEvent) => {
      if (!handler) return
      if (isScrollbarClick(event)) return

      const target = event.target as Node
      if (!isClickInsideAnyRef(refsRef.current, target)) {
        handler()
      }
    },
    [handler],
  )

  useEffect(() => {
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [handleMouseDown])
}
