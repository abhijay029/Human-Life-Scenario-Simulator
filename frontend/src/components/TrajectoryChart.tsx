'use client'
import type { TrajectorySummary } from '@/lib/types'
import { clsx } from 'clsx'

// ─── Constants ────────────────────────────────────────────────────────────────

const DIMENSIONS = ['trust', 'rapport', 'tension', 'respect', 'power_balance'] as const
type Dim = (typeof DIMENSIONS)[number]

const DIM_COLORS: Record<string, string> = {
  trust: '#167a57',         // green
  rapport: '#2585a5',       // blue
  tension: '#bd3f54',       // red-alert
  respect: '#a85e00',       // amber
  power_balance: '#7659a8', // violet
}

const DIM_LABEL: Record<string, string> = {
  trust: 'Trust',
  rapport: 'Rapport',
  tension: 'Tension',
  respect: 'Respect',
  power_balance: 'Power Balance',
}

// For power_balance the neutral midpoint is 0, rest are 0-100
const DIM_NEUTRAL: Record<string, number> = {
  trust: 50, rapport: 50, tension: 50, respect: 50, power_balance: 0,
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/** Build an SVG polyline path from an array of (x, y) points. */
function polyPath(points: Array<[number, number]>): string {
  if (points.length < 2) return ''
  return 'M ' + points.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(' L ')
}

function trendIcon(label: string, dim: string) {
  const isTension = dim === 'tension'
  if (label === 'improving') return isTension ? '↓' : '↑'
  if (label === 'deteriorating') return isTension ? '↑' : '↓'
  return '→'
}

function trendColor(label: string, dim: string) {
  if (label === 'improving') return 'text-green-400'
  if (label === 'deteriorating') return 'text-red-400'
  return 'text-zinc-400'
}

// ─── MiniChart ────────────────────────────────────────────────────────────────

interface MiniChartProps {
  dim: Dim
  values: number[]      // full history array
  label: string         // 'improving' | 'stable' | 'deteriorating'
  current: number
  start: number
  turningPointIndices: Set<number>
}

const SVG_W = 320
const SVG_H = 72
const PAD_LEFT = 36   // room for Y-axis labels
const PAD_RIGHT = 8
const PAD_TOP = 8
const PAD_BOT = 20    // room for X-axis labels

const PLOT_W = SVG_W - PAD_LEFT - PAD_RIGHT
const PLOT_H = SVG_H - PAD_TOP - PAD_BOT

function MiniChart({ dim, values, label, current, start, turningPointIndices }: MiniChartProps) {
  const color = DIM_COLORS[dim] ?? '#888'

  // ── Auto-scale Y-axis: zoom into actual data range with 10% padding
  const rawMin = Math.min(...values)
  const rawMax = Math.max(...values)
  const span = rawMax - rawMin

  // Minimum visible span so near-flat lines still show some space
  const minSpan = dim === 'power_balance' ? 8 : 6
  const paddedSpan = Math.max(span, minSpan)
  const center = (rawMin + rawMax) / 2
  const yMin = center - paddedSpan / 2 - paddedSpan * 0.15
  const yMax = center + paddedSpan / 2 + paddedSpan * 0.15
  const yRange = yMax - yMin

  // Helpers
  const toX = (i: number) =>
    PAD_LEFT + (values.length < 2 ? PLOT_W / 2 : (i / (values.length - 1)) * PLOT_W)
  const toY = (v: number) =>
    PAD_TOP + PLOT_H - ((v - yMin) / yRange) * PLOT_H

  // Build line points
  const pts: Array<[number, number]> = values.map((v, i) => [toX(i), toY(v)])

  // Y-axis ticks: 4 evenly-spaced labels
  const yTicks = 4
  const yTickVals = Array.from({ length: yTicks }, (_, k) => {
    return yMin + (k / (yTicks - 1)) * yRange
  })

  // X-axis labels
  const xLabels: Array<{ i: number; label: string }> = []
  if (values.length >= 2) {
    xLabels.push({ i: 0, label: 'T0' })
    xLabels.push({ i: values.length - 1, label: `T${values.length - 1}` })
    // Add midpoint label if turns ≥ 4
    if (values.length >= 4) {
      const mid = Math.round((values.length - 1) / 2)
      xLabels.push({ i: mid, label: `T${mid}` })
    }
  }

  const neutralY = toY(DIM_NEUTRAL[dim] ?? 50)
  const showNeutral = neutralY > PAD_TOP && neutralY < PAD_TOP + PLOT_H

  return (
    <div className="rounded border border-zinc-800 bg-zinc-950 overflow-hidden">
      {/* Header row */}
      <div className="flex items-center justify-between px-2 pt-1.5 pb-0.5">
        <div className="flex items-center gap-1.5">
          <span
            className="inline-block w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: color }}
          />
          <span className="text-[11px] font-semibold text-zinc-300 tracking-wide">
            {DIM_LABEL[dim]}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono" style={{ color }}>
            {current.toFixed(1)}
          </span>
          <span className={clsx('text-[11px] font-mono', trendColor(label, dim))}>
            {trendIcon(label, dim)}
          </span>
          <span className="text-[10px] font-mono text-zinc-500">
            Δ{(current - start >= 0 ? '+' : '')}{(current - start).toFixed(1)}
          </span>
        </div>
      </div>

      {/* SVG chart */}
      <svg
        viewBox={`0 0 ${SVG_W} ${SVG_H}`}
        width="100%"
        height={SVG_H}
        className="overflow-visible"
      >
        {/* ── Y-axis tick lines and labels ── */}
        {yTickVals.map((v, k) => {
          const y = toY(v)
          return (
            <g key={k}>
              <line
                x1={PAD_LEFT} y1={y} x2={SVG_W - PAD_RIGHT} y2={y}
                stroke="#d7e1eb" strokeWidth={0.5} strokeDasharray="3,3"
              />
              <text
                x={PAD_LEFT - 3} y={y + 3.5}
                textAnchor="end"
                fontSize={8}
                fill="#6f8192"
                fontFamily="monospace"
              >
                {v.toFixed(0)}
              </text>
            </g>
          )
        })}

        {/* ── Neutral reference line (dashed, subtle) ── */}
        {showNeutral && (
          <line
            x1={PAD_LEFT} y1={neutralY}
            x2={SVG_W - PAD_RIGHT} y2={neutralY}
            stroke="#aebdca" strokeWidth={0.8} strokeDasharray="4,2"
          />
        )}

        {/* ── Plot border ── */}
        <rect
          x={PAD_LEFT} y={PAD_TOP}
          width={PLOT_W} height={PLOT_H}
          fill="none" stroke="#d7e1eb" strokeWidth={0.5}
        />

        {/* ── Area fill under the line (subtle) ── */}
        {pts.length >= 2 && (
          <path
            d={
              `M ${pts[0][0]},${PAD_TOP + PLOT_H} ` +
              pts.map(([x, y]) => `L ${x},${y}`).join(' ') +
              ` L ${pts[pts.length - 1][0]},${PAD_TOP + PLOT_H} Z`
            }
            fill={color}
            fillOpacity={0.06}
          />
        )}

        {/* ── Main trend line ── */}
        {pts.length >= 2 && (
          <path
            d={polyPath(pts)}
            fill="none"
            stroke={color}
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}

        {/* ── Data point dots ── */}
        {pts.map(([x, y], i) => (
          <circle
            key={i}
            cx={x} cy={y} r={turningPointIndices.has(i) ? 3.5 : 2}
            fill={turningPointIndices.has(i) ? color : '#ffffff'}
            stroke={color}
            strokeWidth={turningPointIndices.has(i) ? 1 : 1.2}
            opacity={0.9}
          />
        ))}

        {/* ── X-axis labels ── */}
        {xLabels.map(({ i, label: xl }) => (
          <text
            key={i}
            x={toX(i)} y={SVG_H - 4}
            textAnchor="middle"
            fontSize={8}
            fill="#6f8192"
            fontFamily="monospace"
          >
            {xl}
          </text>
        ))}
      </svg>
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

interface Props {
  trajectories: TrajectorySummary[]
  pairKey: string   // e.g. "Arjun->Rahul"
  height?: number   // kept for API compat, ignored (each mini-chart is self-sizing)
}

export default function TrajectoryChart({ trajectories, pairKey }: Props) {
  // Collect per-dimension data
  const dimData: Partial<Record<Dim, {
    values: number[]
    label: string
    current: number
    start: number
    tpIndices: Set<number>
  }>> = {}

  for (const dim of DIMENSIONS) {
    const t = trajectories.find((t) => t.dyad_pair === pairKey && t.dimension === dim)
    if (!t) continue

    // Prefer the history array from backend; fall back to reconstructing from turning points
    let values: number[]
    if (t.history && t.history.length >= 1) {
      values = t.history
    } else {
      values = [t.start]
      for (const tp of t.turning_points) {
        values.push(tp.value_after)
      }
      if (values[values.length - 1] !== t.current) values.push(t.current)
    }

    // Find which indices correspond to turning points
    const tpIndices = new Set<number>()
    for (const tp of t.turning_points) {
      // Find the first index where the value is close to value_after
      const idx = values.findIndex(
        (v, i) => i > 0 && Math.abs(v - tp.value_after) < 0.15
      )
      if (idx >= 0) tpIndices.add(idx)
    }

    dimData[dim] = { values, label: t.label, current: t.current, start: t.start, tpIndices }
  }

  const activeDims = DIMENSIONS.filter((d) => d in dimData)

  if (activeDims.length === 0) {
    return (
      <div className="flex items-center justify-center h-16 text-xs text-zinc-500 font-mono">
        Waiting for observations…
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {activeDims.map((dim) => {
        const d = dimData[dim]!
        return (
          <MiniChart
            key={dim}
            dim={dim}
            values={d.values}
            label={d.label}
            current={d.current}
            start={d.start}
            turningPointIndices={d.tpIndices}
          />
        )
      })}
    </div>
  )
}
