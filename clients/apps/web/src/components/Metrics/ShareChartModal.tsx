/**
 * ShareChartModal - export a Rapidly metric chart as a PNG image.
 *
 * Renders a branded chart preview with selectable theme variants,
 * then converts the DOM node to an image for clipboard copy or download.
 */

import { ParsedMetricsResponse } from '@/hooks/api/metrics'
import { schemas } from '@rapidly-tech/client'
import Button from '@rapidly-tech/ui/components/forms/Button'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@rapidly-tech/ui/components/primitives/tooltip'
import { useCallback, useRef, useState } from 'react'
import { twMerge } from 'tailwind-merge'
import LogoType from '../Brand/LogoType'
import { toast } from '../Toast/use-toast'
import MetricChartBox from './MetricChartBox'

// ── Constants ──

const EXPORT_SCALE = 3
const EXPORT_FILENAME = 'rapidly-chart.png'

// ── Types ──

type ChartThemeVariant = 'light' | 'dark'

const THEME_BACKGROUNDS: Record<ChartThemeVariant, string> = {
  light:
    'linear-gradient(135deg, oklch(0.984 0.005 75), oklch(0.968 0.008 75), oklch(0.929 0.012 70), oklch(0.968 0.008 75))',
  dark: 'linear-gradient(135deg, oklch(0.279 0.018 60), oklch(0.208 0.015 60), oklch(0.279 0.018 60), oklch(0.129 0.012 60))',
}

interface ShareChartModalProps {
  metric: keyof schemas['Metrics']
  interval: schemas['TimeInterval']
  data: ParsedMetricsResponse
  previousData?: ParsedMetricsResponse
}

// ── Helpers ──

/** Build dom-to-image render params from a DOM element at a given scale. */
function captureParams(el: HTMLDivElement) {
  return {
    height: el.offsetHeight * EXPORT_SCALE,
    width: el.offsetWidth * EXPORT_SCALE,
    quality: 1,
    style: {
      transform: `scale(${EXPORT_SCALE})`,
      transformOrigin: 'top left',
      width: `${el.offsetWidth}px`,
      height: `${el.offsetHeight}px`,
      borderRadius: '0px',
      border: 'none',
    },
  }
}

// ── Theme Selector Chip ──

interface ThemeChipProps {
  label: string
  variant: ChartThemeVariant
  active: boolean
  onSelect: (variant: ChartThemeVariant) => void
}

const ThemeChip = ({ label, variant, active, onSelect }: ThemeChipProps) => (
  <Tooltip>
    <TooltipTrigger asChild>
      <div
        onClick={() => onSelect(variant)}
        className={twMerge(
          'h-8 w-8 cursor-pointer rounded-full border-2 transition-opacity hover:opacity-50',
          active ? 'border-slate-400 dark:border-slate-500' : '',
        )}
        style={{
          background: THEME_BACKGROUNDS[variant],
        }}
      />
    </TooltipTrigger>
    <TooltipContent>
      <span className="text-sm">{label}</span>
    </TooltipContent>
  </Tooltip>
)

// ── Main Component ──

export const ShareChartModal = ({
  metric,
  interval,
  data,
  previousData,
}: ShareChartModalProps) => {
  const canvasRef = useRef<HTMLDivElement>(null)
  const [activeTheme, setActiveTheme] = useState<ChartThemeVariant>('light')

  const saveAsFile = useCallback(async () => {
    if (!canvasRef.current) return
    const domtoimage = (await import('dom-to-image')).default
    const params = captureParams(canvasRef.current)

    const blob = await domtoimage.toBlob(canvasRef.current, params)
    if (!blob) return
    const anchor = document.createElement('a')
    anchor.href = URL.createObjectURL(blob)
    anchor.download = EXPORT_FILENAME
    anchor.click()
    toast({
      title: 'Downloaded Image',
      description: 'Chart image downloaded',
    })
  }, [])

  const copyImage = useCallback(async () => {
    if (!canvasRef.current) return
    const domtoimage = (await import('dom-to-image')).default
    const params = captureParams(canvasRef.current)

    const blob = await domtoimage.toBlob(canvasRef.current, params)
    if (!blob) return
    navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })])
    toast({
      title: 'Copied to Clipboard',
      description: 'Chart image copied to clipboard',
    })
  }, [])

  return (
    <div className="relative flex w-full max-w-4xl flex-col items-center justify-center overflow-y-auto p-16">
      <div className="flex flex-col items-start gap-8">
        {/* Preview canvas */}
        <div
          ref={canvasRef}
          className="flex w-full max-w-4xl flex-col items-center justify-center gap-12 rounded-4xl bg-slate-100 p-12 dark:bg-slate-950"
          style={{
            background: THEME_BACKGROUNDS[activeTheme],
          }}
        >
          <MetricChartBox
            className="dark:border-slate-700/50"
            data={data}
            previousData={previousData}
            interval={interval}
            metric={metric}
            shareable={false}
            height={200}
            width={560}
            simple
            chartType="line"
          />
          <LogoType
            className={activeTheme === 'dark' ? 'text-white' : 'text-slate-800'}
            height={48}
          />
        </div>

        {/* Controls */}
        <div className="flex w-full flex-row items-center justify-between gap-6">
          <div className="flex flex-row gap-4">
            <ThemeChip
              label="Light"
              variant="light"
              active={activeTheme === 'light'}
              onSelect={setActiveTheme}
            />
            <ThemeChip
              label="Dark"
              variant="dark"
              active={activeTheme === 'dark'}
              onSelect={setActiveTheme}
            />
          </div>
          <div className="flex flex-row gap-2">
            <Button fullWidth variant="ghost" onClick={copyImage}>
              Copy
            </Button>
            <Button fullWidth onClick={saveAsFile}>
              Download
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
