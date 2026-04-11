'use client'
import type { ObserverAnalysis } from '@/lib/types'
import { Panel, Badge, ProgressBar } from './ui'
import { TrendingUp, TrendingDown, Minus, Target, Lightbulb, AlertTriangle } from 'lucide-react'
import { clsx } from 'clsx'

function TrajectoryIcon({ t }: { t: string }) {
  if (t === 'improving') return <TrendingUp size={14} className="text-green-good" />
  if (t === 'deteriorating') return <TrendingDown size={14} className="text-red-alert" />
  return <Minus size={14} className="text-text-secondary" />
}

function outcomeVariant(cat: string): 'success' | 'warning' | 'danger' | 'default' {
  if (cat === 'Best Case') return 'success'
  if (cat === 'Most Likely') return 'warning'
  if (cat === 'Worst Case') return 'danger'
  return 'default'
}

function probColor(p: number) {
  if (p >= 0.65) return 'text-green-good'
  if (p >= 0.35) return 'text-amber-sim'
  return 'text-red-alert'
}

export default function AnalysisPanel({ analysis }: { analysis: ObserverAnalysis }) {
  return (
    <div className="space-y-4">
      {/* Outcome header */}
      <Panel label="Observer Analysis" className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              <Badge variant={outcomeVariant(analysis.outcome_category)}>
                {analysis.outcome_category}
              </Badge>
              <div className="flex items-center gap-1.5 text-xs font-mono">
                <TrajectoryIcon t={analysis.relationship_trajectory} />
                <span
                  className={clsx(
                    analysis.relationship_trajectory === 'improving' && 'text-green-good',
                    analysis.relationship_trajectory === 'deteriorating' && 'text-red-alert',
                    analysis.relationship_trajectory === 'stable' && 'text-text-secondary'
                  )}
                >
                  {analysis.relationship_trajectory}
                </span>
              </div>
            </div>
            <p className="text-sm text-text-primary font-body leading-relaxed">
              {analysis.outcome_summary}
            </p>
            <p className="text-xs text-text-secondary font-body mt-2 italic">
              {analysis.trajectory_explanation}
            </p>
          </div>
        </div>
      </Panel>

      {/* Goal Success */}
      <Panel label="Goal Success Probability" className="p-4">
        <div className="space-y-4">
          {analysis.persona_goal_success.map((pg, i) => (
            <div key={i} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Target size={12} className="text-text-dim" />
                  <span className="text-xs font-mono font-bold text-text-primary">{pg.persona}</span>
                </div>
                <span className={clsx('text-sm font-mono font-bold', probColor(pg.success_probability))}>
                  {Math.round(pg.success_probability * 100)}%
                </span>
              </div>
              <ProgressBar value={pg.success_probability} />
              <p className="text-[11px] text-text-secondary font-body leading-relaxed">
                <span className="text-text-dim">Goal: </span>{pg.goal_summary}
              </p>
              <p className="text-[11px] text-text-dim font-body italic">{pg.reasoning}</p>
            </div>
          ))}
        </div>
      </Panel>

      {/* Key Turning Points */}
      {analysis.key_turning_points.length > 0 && (
        <Panel label="Key Turning Points" className="p-4">
          <div className="space-y-2">
            {analysis.key_turning_points.map((pt, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <div className="flex-shrink-0 w-5 h-5 mt-0.5 rounded border border-amber-sim/30 bg-amber-sim/10 flex items-center justify-center">
                  <AlertTriangle size={10} className="text-amber-sim" />
                </div>
                <p className="text-xs text-text-secondary font-body leading-relaxed">{pt}</p>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {/* Recommendations */}
      {analysis.recommendations.length > 0 && (
        <Panel label="Recommendations" className="p-4">
          <div className="space-y-2">
            {analysis.recommendations.map((r, i) => (
              <div key={i} className="flex items-start gap-2.5">
                <div className="flex-shrink-0 w-5 h-5 mt-0.5 rounded border border-cyan/20 bg-cyan/5 flex items-center justify-center">
                  <Lightbulb size={10} className="text-cyan" />
                </div>
                <p className="text-xs text-text-primary font-body leading-relaxed">{r}</p>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  )
}
