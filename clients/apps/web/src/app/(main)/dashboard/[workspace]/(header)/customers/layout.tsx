import { PropsWithChildren } from 'react'

/** Passthrough layout for the customers section. */
export default function Layout(props: PropsWithChildren) {
  return <>{props.children}</>
}
