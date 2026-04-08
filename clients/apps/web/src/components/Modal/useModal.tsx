import { useCallback, useState } from 'react'

export const useModal = (startVisible: boolean = false) => {
  const [isShown, setIsShown] = useState(startVisible)

  const show = useCallback(() => setIsShown(true), [])
  const hide = useCallback(() => setIsShown(false), [])
  const toggle = useCallback(() => setIsShown((prev) => !prev), [])

  return { isShown, toggle, show, hide }
}
