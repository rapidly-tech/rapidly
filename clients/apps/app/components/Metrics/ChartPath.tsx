/**
 * SVG line path for a time-series chart.
 *
 * Maps data points to x/y coordinates within the given chart dimensions,
 * normalised between the provided min and max value bounds, then joins
 * them into an SVG <Path> element.
 */
import { Path } from 'react-native-svg'

interface DataPoint {
  value: number
  date: Date
}

export interface ChartPathProps {
  dataPoints: DataPoint[]
  width: number
  chartHeight: number
  strokeWidth: number
  strokeColor: string
  minValue: number
  maxValue: number
}

/** Converts a data point to its SVG x/y position. */
function pointToCoords(
  point: DataPoint,
  index: number,
  total: number,
  width: number,
  height: number,
  min: number,
  max: number,
): { x: number; y: number } {
  const x = index === 0 ? 1 : (index / (total - 1)) * (width - 2)
  const range = Math.abs(max - min) || 1
  const y = height - 2 - ((point.value - min) / range) * (height - 4)
  return { x, y }
}

export const ChartPath = ({
  dataPoints,
  width,
  chartHeight,
  strokeWidth,
  strokeColor,
  minValue,
  maxValue,
}: ChartPathProps) => {
  const total = dataPoints.length

  const d = dataPoints
    .map((pt, idx) => {
      const { x, y } = pointToCoords(
        pt,
        idx,
        total,
        width,
        chartHeight,
        minValue,
        maxValue,
      )
      const command = idx === 0 ? 'M' : 'L'
      return `${command} ${x} ${y}`
    })
    .join(' ')

  return (
    <Path d={d} stroke={strokeColor} strokeWidth={strokeWidth} fill="none" />
  )
}
