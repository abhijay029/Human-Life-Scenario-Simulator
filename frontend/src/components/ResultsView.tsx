'use client'
import { useState } from 'react'
import type { SimulationResponse, MultiverseResponse, SimMode } from '@/lib/types'
import DialogueViewer from './DialogueViewer'
import AnalysisPanel from './AnalysisPanel'
import ComparisonReportPanel from './ComparisonReport'
import { Panel, Button, Badge } from './ui'
import { MessageSquare, BarChart2, GitBranch, RefreshCw } from 'lucide-react'
import dynamic from 'next/dynamic'
import { clsx } from 'clsx'

// React Flow needs client-only rendering
const DecisionTree = dynamic(() => import('./DecisionTree'), { ssr: false })

type Tab = 'dialogue' | 'analysis' | 'tree' | 'report'

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        'flex items-center gap-1.5 px-4 py-2.5 text-xs font-mono tracking-wide border-b-2 transition-all duration-200',
        active
          ? 'border-cyan text-cyan'
          : 'border-transparent text-text-secondary hover:text-text-primary hover:border-border'
      )}
    >
      {children}
    </button>
  )
}

// ── Single Result ──────────────────────────────────────────────────────────

function SingleResult({
  result,
  onReset,
}: {
  result: SimulationResponse
  onReset: () => void
}) {
  const [tab, setTab] = useState<'dialogue' | 'analysis'>('dialogue')

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-text-primary">Simulation Results</h2>
          <p className="text-xs text-text-secondary font-mono mt-1">
            {result.dialogue_log.length} turns · single branch
          </p>
        </div>
        <div className="flex items-center gap-2">
          {result.analysis && (
            <Badge variant={
              result.analysis.outcome_category === 'Best Case' ? 'success' :
              result.analysis.outcome_category === 'Worst Case' ? 'danger' : 'warning'
            }>
              {result.analysis.outcome_category}
            </Badge>
          )}
          <Button variant="ghost" onClick={onReset}>
            <RefreshCw size={13} />
            New Simulation
          </Button>
        </div>
      </div>

      {/* Decision point summary */}
      <Panel className="px-4 py-3">
        <p className="text-[10px] font-mono text-text-secondary tracking-[0.15em] uppercase mb-1">Decision</p>
        <p className="text-sm text-text-primary font-body">{result.decision_point}</p>
      </Panel>

      {/* Tabs */}
      <div className="border-b border-border flex">
        <TabBtn active={tab === 'dialogue'} onClick={() => setTab('dialogue')}>
          <MessageSquare size={12} /> Dialogue
        </TabBtn>
        {result.analysis && (
          <TabBtn active={tab === 'analysis'} onClick={() => setTab('analysis')}>
            <BarChart2 size={12} /> Analysis
          </TabBtn>
        )}
      </div>

      {tab === 'dialogue' && (
        <DialogueViewer
          log={result.dialogue_log}
          sentiments={result.analysis?.turn_sentiments}
          decisionPoint={result.decision_point}
        />
      )}
      {tab === 'analysis' && result.analysis && (
        <AnalysisPanel analysis={result.analysis} />
      )}
    </div>
  )
}

// ── Multiverse Result ──────────────────────────────────────────────────────

function MultiverseResult({
  result,
  onReset,
}: {
  result: MultiverseResponse
  onReset: () => void
}) {
  const [tab, setTab] = useState<Tab>('report')
  const [selectedBranch, setSelectedBranch] = useState(0)
  const branch = result.branches[selectedBranch]

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="font-display text-2xl font-bold text-text-primary">Multiverse Results</h2>
          <p className="text-xs text-text-secondary font-mono mt-1">
            {result.branches.length} branches simulated · comparative analysis complete
          </p>
        </div>
        <Button variant="ghost" onClick={onReset}>
          <RefreshCw size={13} />
          New Simulation
        </Button>
      </div>

      {/* Tabs */}
      <div className="border-b border-border flex overflow-x-auto">
        <TabBtn active={tab === 'report'} onClick={() => setTab('report')}>
          <BarChart2 size={12} /> Comparison Report
        </TabBtn>
        <TabBtn active={tab === 'tree'} onClick={() => setTab('tree')}>
          <GitBranch size={12} /> Decision Tree
        </TabBtn>
        <TabBtn active={tab === 'dialogue'} onClick={() => setTab('dialogue')}>
          <MessageSquare size={12} /> Dialogue
        </TabBtn>
        {branch?.analysis && (
          <TabBtn active={tab === 'analysis'} onClick={() => setTab('analysis')}>
            <BarChart2 size={12} /> Branch Analysis
          </TabBtn>
        )}
      </div>

      {/* Comparison Report */}
      {tab === 'report' && (
        <ComparisonReportPanel report={result.comparison_report} />
      )}

      {/* Decision Tree */}
      {tab === 'tree' && (
        <div className="space-y-3">
          <p className="text-xs text-text-secondary font-body">
            Interactive decision tree. Drag to pan, scroll to zoom. Highlighted nodes show ranked outcomes.
          </p>
          <DecisionTree
            scenario={result.scenario}
            branches={result.branches}
            report={result.comparison_report}
          />
        </div>
      )}

      {/* Dialogue with branch selector */}
      {(tab === 'dialogue' || tab === 'analysis') && (
        <div className="space-y-4">
          {/* Branch selector */}
          <div className="flex flex-wrap gap-2">
            {result.branches.map((b, i) => (
              <button
                key={i}
                onClick={() => setSelectedBranch(i)}
                className={clsx(
                  'flex items-center gap-2 px-3 py-2 rounded border text-xs font-mono transition-all',
                  selectedBranch === i
                    ? 'border-cyan/50 bg-cyan/10 text-cyan'
                    : 'border-border text-text-secondary hover:border-border/80 hover:text-text-primary'
                )}
              >
                <span className="w-4 h-4 rounded bg-cyan/20 flex items-center justify-center text-[10px]">
                  {String.fromCharCode(65 + i)}
                </span>
                <span className="max-w-[180px] truncate">{b.decision_point}</span>
                {b.analysis?.outcome_category && (
                  <Badge variant={
                    b.analysis.outcome_category === 'Best Case' ? 'success' :
                    b.analysis.outcome_category === 'Worst Case' ? 'danger' : 'warning'
                  }>
                    {b.analysis.outcome_category}
                  </Badge>
                )}
              </button>
            ))}
          </div>

          {tab === 'dialogue' && branch && (
            <DialogueViewer
              log={branch.dialogue_log}
              sentiments={branch.analysis?.turn_sentiments}
              decisionPoint={branch.decision_point}
              label={`Branch ${String.fromCharCode(65 + selectedBranch)}`}
            />
          )}
          {tab === 'analysis' && branch?.analysis && (
            <AnalysisPanel analysis={branch.analysis} />
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Export ────────────────────────────────────────────────────────────

export default function ResultsView({
  mode,
  singleResult,
  multiverseResult,
  onReset,
}: {
  mode: SimMode
  singleResult?: SimulationResponse
  multiverseResult?: MultiverseResponse
  onReset: () => void
}) {
  if (mode === 'single' && singleResult) {
    return <SingleResult result={singleResult} onReset={onReset} />
  }
  if (mode === 'multiverse' && multiverseResult) {
    return <MultiverseResult result={multiverseResult} onReset={onReset} />
  }
  return null
}
