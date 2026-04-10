/**
 * Icon - badge-style wrapper that renders a React element
 * inside a compact rounded container with custom styling.
 */
interface IconProps {
  classes: string
  icon: React.ReactElement
}

const Icon = ({ icon, classes }: IconProps) => (
  <div
    className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${classes}`}
  >
    {icon}
  </div>
)

export default Icon
