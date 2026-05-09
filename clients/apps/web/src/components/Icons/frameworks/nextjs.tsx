/**
 * NextJsIcon - Next.js framework logo.
 * Uses linear gradients for the characteristic fade effect.
 */
const NextJsIcon = ({ size = 40 }: { size?: number }) => {
  // Unique gradient IDs scoped to this component
  const gradientDiagonal = ':S3:paint0_linear_408_134'
  const gradientVertical = ':S3:paint1_linear_408_134'
  const maskId = ':S3:mask0_408_134'

  return (
    <svg
      role="img"
      aria-label="Next.js logomark"
      width={size}
      viewBox="40 40 120 120"
      className="next-mark_root__iLw9v"
    >
      <mask
        id={maskId}
        maskUnits="userSpaceOnUse"
        x="0"
        y="0"
        width="180"
        height="180"
        style={{ maskType: 'alpha' }}
      >
        <circle r="90" cx="90" cy="90"></circle>
      </mask>
      <g mask={`url(#${maskId})`}>
        {/* Diagonal letter N */}
        <path
          fill={`url(#${gradientDiagonal})`}
          d="M149.508 157.52L69.142 54H54V125.97H66.1136V69.3836L139.999 164.845C143.333 162.614 146.509 160.165 149.508 157.52Z"
        ></path>
        {/* Vertical bar */}
        <rect
          x="115"
          y="54"
          width="12"
          height="72"
          fill={`url(#${gradientVertical})`}
        ></rect>
      </g>
      <defs>
        <linearGradient
          id={gradientDiagonal}
          gradientUnits="userSpaceOnUse"
          x1="109"
          y1="116.5"
          x2="144.5"
          y2="160.5"
        >
          <stop stopColor="currentColor"></stop>
          <stop stopColor="currentColor" stopOpacity="0" offset="1"></stop>
        </linearGradient>
        <linearGradient
          id={gradientVertical}
          gradientUnits="userSpaceOnUse"
          x1="121"
          y1="54"
          x2="120.799"
          y2="106.875"
        >
          <stop stopColor="currentColor"></stop>
          <stop stopColor="currentColor" stopOpacity="0" offset="1"></stop>
        </linearGradient>
      </defs>
    </svg>
  )
}

export default NextJsIcon
