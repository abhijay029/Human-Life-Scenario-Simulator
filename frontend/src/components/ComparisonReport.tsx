'use client'
import type { ComparisonReport } from '@/lib/types'
import { Panel, ProgressBar } from './ui'
import { Trophy, AlertOctagon, Activity } from 'lucide-react'
import { clsx } from 'clsx'

function ReportCard({
  type,
  data,
}: {
  type: 'best' | 'worst' | 'likely'
  data: { decision_point: string; outcome_category?: string; outcome_summary?: string; avg_success_probability: number }
}) {
  const config = {
    best: {
      icon: Trophy,
      label: 'Best Case',
      border: 'border-green-good/30',
      bg: 'bg-green-good/5',
      iconColor: 'text-green-good',
      headerBg: 'bg-green-good/10',
    },
    worst: {
      icon: AlertOctagon,
      label: 'Worst Case',
      border: 'border-red-alert/30',
      bg: 'bg-red-alert/5',
      iconColor: 'text-red-alert',
      headerBg: 'bg-red-alert/10',
    },
    likely: {
      icon: Activity,
      label: 'Most Likely',
      border: 'border-amber-sim/30',
      bg: 'bg-amber-sim/5',
      iconColor: 'text-amber-sim',
      headerBg: 'bg-amber-sim/10',
    },
  }

  const c = config[type]
  const Icon = c.icon
  const pct = Math.round(data.avg_success_probability * 100)

  return (
    <div className={clsx('rounded border overflow-hidden', c.border, c.bg)}>
      <div className={clsx('flex items-center gap-2 px-4 py-2.5', c.headerBg)}>
        <Icon size={14} className={c.iconColor} />
        <span className={clsx('text-xs font-mono font-bold tracking-wide', c.iconColor)}>
          {c.label}
        </span>
        <span className={clsx('ml-auto text-sm font-mono font-bold', c.iconColor)}>{pct}%</span>
      </div>
      <div className="px-4 py-3 space-y-2">
        <ProgressBar value={data.avg_success_probability} color="cyan" />
        <p className="text-[11px] font-mono text-text-secondary leading-relaxed line-clamp-2">
          {data.decision_point}
        </p>
        {data.outcome_summary && (
          <p className="text-[11px] text-text-primary font-body leading-relaxed">
            {data.outcome_summary}
          </p>
        )}
      </div>
    </div>
  )
}

export default function ComparisonReportPanel({ report }: { report: ComparisonReport }) {
  return (
    <div className="space-y-4">
      {/* The three headline cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <ReportCard type="best" data={report.best_case} />
        <ReportCard type="likely" data={report.most_likely} />
        <ReportCard type="worst" data={report.worst_case} />
      </div>

      {/* Rankings table */}
      {report.all_branches_ranked.length > 1 && (
        <Panel label="All Branches Ranked" className="overflow-hidden">
          <table className="w-full text-xs font-mono">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-2.5 text-text-secondary font-normal tracking-wider uppercase text-[10px]">
                  Rank
                </th>
                <th className="text-left px-4 py-2.5 text-text-secondary font-normal tracking-wider uppercase text-[10px]">
                  Decision Branch
                </th>
                <th className="text-left px-4 py-2.5 text-text-secondary font-normal tracking-wider uppercase text-[10px]">
                  Outcome
                </th>
                <th className="text-right px-4 py-2.5 text-text-secondary font-normal tracking-wider uppercase text-[10px]">
                  Success
                </th>
              </tr>
            </thead>
            <tbody>
              {report.all_branches_ranked.map((b, i) => {
                const pct = Math.round(b.avg_success_probability * 100)
                const rankColor =
                  i === 0
                    ? 'text-green-good'
                    : i === report.all_branches_ranked.length - 1
                    ? 'text-red-alert'
                    : 'text-amber-sim'
                return (
                  <tr key={i} className="border-b border-border/50 hover:bg-white/[0.02] transition-colors">
                    <td className={clsx('px-4 py-3 font-bold', rankColor)}>#{i + 1}</td>
                    <td className="px-4 py-3 text-text-secondary max-w-xs">
                      <p className="truncate">{b.decision_point}</p>
                    </td>
                    <td className="px-4 py-3">
                      {b.outcome_category && (
                        <span
                          className={clsx(
                            'text-[10px] px-1.5 py-0.5 rounded border',
                            b.outcome_category === 'Best Case' &&
                              'text-green-good border-green-good/30 bg-green-good/10',
                            b.outcome_category === 'Most Likely' &&
                              'text-amber-sim border-amber-sim/30 bg-amber-sim/10',
                            b.outcome_category === 'Worst Case' &&
                              'text-red-alert border-red-alert/30 bg-red-alert/10'
                          )}
                        >
                          {b.outcome_category}
                        </span>
                      )}
                    </td>
                    <td className={clsx('px-4 py-3 text-right font-bold', rankColor)}>{pct}%</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  )
}
