'use client'
import type { ObserverSSEState, ConversationScorecard } from '@/lib/types'
import { Panel, ProgressBar } from './ui'
import { AlertTriangle, Lightbulb } from 'lucide-react'
import { clsx } from 'clsx'

const METRIC_LABELS: Record<string, string> = {
  persona_consistency: 'Persona Consistency',
  emotional_realism: 'Emotional Realism',
  conversational_coherence: 'Conversational Coherence',
  goal_alignment: 'Goal Alignment',
  conflict_realism: 'Conflict Realism',
  social_plausibility: 'Social Plausibility',
  overall_realism: 'Overall Realism',
}

function ScorecardView({ sc }: { sc: ConversationScorecard }) {
  const metrics = Object.entries(METRIC_LABELS).map(([key, label]) => ({
    key,
    label,
    value: sc[key as keyof ConversationScorecard] as number,
  }))

  return (
    <div className="space-y-4">
      {sc.summary && <p className="text-xs text-zinc-400 font-body italic">{sc.summary}</p>}

      <div className="space-y-2.5">
        {metrics.map(({ key, label, value }) => (
          <div key={key}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[11px] font-mono text-zinc-400">{label}</span>
              <span className={clsx(
                'text-[11px] font-mono font-bold',
                value >= 8 ? 'text-green-400' : value >= 6 ? 'text-amber-400' : 'text-red-400'
              )}>
                {value.toFixed(1)}
              </span>
            </div>
            <ProgressBar value={value / 10} />
          </div>
        ))}
      </div>

      {sc.key_turning_points.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-mono text-zinc-500 tracking-wider uppercase">Key Turning Points</p>
          {sc.key_turning_points.map((pt, i) => (
            <div key={i} className="flex items-start gap-2">
              <AlertTriangle size={10} className="text-amber-400 mt-0.5 flex-shrink-0" />
              <p className="text-[11px] text-zinc-400 font-body leading-snug">{pt}</p>
            </div>
          ))}
        </div>
      )}

      {sc.recommendations.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-[10px] font-mono text-zinc-500 tracking-wider uppercase">Recommendations</p>
          {sc.recommendations.map((r, i) => (
            <div key={i} className="flex items-start gap-2">
              <Lightbulb size={10} className="text-cyan-400 mt-0.5 flex-shrink-0" />
              <p className="text-[11px] text-zinc-300 font-body leading-snug">{r}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function ObserverPanel({ observer }: { observer: ObserverSSEState }) {
  return (
    <div className="space-y-4">
      {observer.scorecard ? (
        <Panel label="Conversation Scorecard" className="p-4">
          <ScorecardView sc={observer.scorecard} />
        </Panel>
      ) : (
        <p className="text-xs text-zinc-500 font-mono">Preparing conversation scorecard…</p>
      )}
    </div>
  )
}
