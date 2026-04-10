'use client'
import type { DialogueTurn, TurnSentiment } from '@/lib/types'
import { clsx } from 'clsx'

function sentimentColor(s: string) {
  if (s === 'positive') return 'text-green-good border-green-good/30 bg-green-good/5'
  if (s === 'negative') return 'text-red-alert border-red-alert/30 bg-red-alert/5'
  return 'text-text-secondary border-border bg-void'
}

function sentimentDot(s: string) {
  if (s === 'positive') return 'bg-green-good shadow-[0_0_6px_rgba(0,229,160,0.6)]'
  if (s === 'negative') return 'bg-red-alert shadow-[0_0_6px_rgba(255,59,92,0.6)]'
  return 'bg-text-secondary'
}

function scoreBar(score: number) {
  // score ranges -1 to +1; display absolute width, color by sign
  const pct = Math.abs(score) * 100
  const color = score > 0.1 ? 'bg-green-good' : score < -0.1 ? 'bg-red-alert' : 'bg-text-secondary'
  return { pct, color }
}

export default function DialogueViewer({
  log,
  sentiments,
  decisionPoint,
  label,
}: {
  log: DialogueTurn[]
  sentiments?: TurnSentiment[]
  decisionPoint: string
  label?: string
}) {
  const getSentiment = (turn: number) =>
    sentiments?.find((s) => s.turn === turn + 1)

  return (
    <div className="space-y-3">
      {/* Decision point header */}
      <div className="flex items-start gap-3 p-3 bg-cyan/5 border border-cyan/15 rounded">
        <div className="flex-shrink-0 mt-0.5">
          <div className="w-2 h-2 rounded-full bg-cyan neon-pulse" />
        </div>
        <div>
          {label && (
            <p className="text-[10px] font-mono text-cyan tracking-[0.15em] uppercase mb-1">
              {label}
            </p>
          )}
          <p className="text-xs text-text-secondary font-body leading-relaxed">{decisionPoint}</p>
        </div>
      </div>

      {/* Dialogue turns */}
      <div className="space-y-2">
        {log.map((turn, i) => {
          const sentiment = getSentiment(i)
          const { pct, color } = sentiment ? scoreBar(sentiment.score) : { pct: 0, color: '' }
          const isEven = i % 2 === 0

          return (
            <div
              key={i}
              className={clsx(
                'group relative flex gap-3 p-3 rounded border transition-all duration-200',
                'hover:border-border/80',
                isEven ? 'bg-panel border-border' : 'bg-void border-transparent',
                'stagger-child'
              )}
            >
              {/* Avatar */}
              <div className="flex-shrink-0">
                <div
                  className={clsx(
                    'w-7 h-7 rounded-full border flex items-center justify-center text-[11px] font-mono font-bold',
                    isEven
                      ? 'bg-amber-sim/10 border-amber-sim/30 text-amber-sim'
                      : 'bg-cyan/10 border-cyan/20 text-cyan'
                  )}
                >
                  {turn.speaker.charAt(0)}
                </div>
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[11px] font-mono font-bold text-text-primary">
                    {turn.speaker}
                  </span>
                  <span className="text-[10px] font-mono text-text-dim">turn {i + 1}</span>
                  {sentiment && (
                    <div className="flex items-center gap-1.5 ml-auto">
                      <div className={clsx('w-1.5 h-1.5 rounded-full', sentimentDot(sentiment.sentiment))} />
                      <span
                        className={clsx(
                          'text-[10px] font-mono px-1.5 py-0.5 rounded border',
                          sentimentColor(sentiment.sentiment)
                        )}
                      >
                        {sentiment.sentiment}
                      </span>
                    </div>
                  )}
                </div>

                <p className="text-sm text-text-primary font-body leading-relaxed">{turn.message}</p>

                {/* Sentiment note + score bar */}
                {sentiment && (
                  <div className="mt-2 space-y-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    <p className="text-[10px] text-text-secondary font-body italic">{sentiment.note}</p>
                    <div className="flex items-center gap-2">
                      <span className="text-[9px] font-mono text-text-dim w-12">intensity</span>
                      <div className="flex-1 h-1 bg-border rounded-full overflow-hidden">
                        <div
                          className={clsx('h-full rounded-full transition-all duration-700', color)}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-[9px] font-mono text-text-dim w-8 text-right">
                        {Math.abs(sentiment.score).toFixed(2)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
