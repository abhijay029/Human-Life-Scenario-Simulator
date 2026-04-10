'use client'
import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  MarkerType,
  Position,
  Handle,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { SimulationResponse, ComparisonReport } from '@/lib/types'
import { clsx } from 'clsx'

// ── Custom Node Types ──────────────────────────────────────────────────────

function ScenarioNode({ data }: { data: { label: string } }) {
  return (
    <div className="px-4 py-3 bg-panel border border-cyan/40 rounded shadow-cyan-glow max-w-[240px]">
      <Handle type="source" position={Position.Bottom} style={{ background: '#00e5ff', border: 'none', width: 8, height: 8 }} />
      <div className="text-[9px] font-mono text-cyan tracking-[0.2em] uppercase mb-1">Scenario</div>
      <div className="text-xs text-text-primary font-body leading-snug">{data.label}</div>
    </div>
  )
}

function BranchNode({ data }: {
  data: {
    label: string
    letter: string
    outcome?: string
    prob?: number
    isHighlight?: boolean
    highlightType?: string
  }
}) {
  const probColor = (p?: number) => {
    if (!p) return 'text-text-secondary'
    if (p >= 0.65) return 'text-green-good'
    if (p >= 0.35) return 'text-amber-sim'
    return 'text-red-alert'
  }

  const borderClass = data.isHighlight
    ? data.highlightType === 'best'
      ? 'border-green-good/50 shadow-[0_0_16px_rgba(0,229,160,0.2)]'
      : data.highlightType === 'worst'
      ? 'border-red-alert/50 shadow-[0_0_16px_rgba(255,59,92,0.2)]'
      : 'border-amber-sim/50 shadow-[0_0_16px_rgba(255,170,0,0.2)]'
    : 'border-border'

  return (
    <div className={clsx('px-3 py-2.5 bg-panel border rounded max-w-[200px] transition-all', borderClass)}>
      <Handle type="target" position={Position.Top} style={{ background: '#00e5ff', border: 'none', width: 8, height: 8 }} />
      <Handle type="source" position={Position.Bottom} style={{ background: '#00e5ff', border: 'none', width: 8, height: 8 }} />
      <div className="flex items-center gap-2 mb-1.5">
        <div className="w-5 h-5 rounded bg-cyan/10 border border-cyan/20 flex items-center justify-center text-[10px] font-mono text-cyan font-bold">
          {data.letter}
        </div>
        {data.isHighlight && (
          <span className={clsx(
            'text-[9px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border',
            data.highlightType === 'best' && 'text-green-good border-green-good/30 bg-green-good/10',
            data.highlightType === 'worst' && 'text-red-alert border-red-alert/30 bg-red-alert/10',
            data.highlightType === 'likely' && 'text-amber-sim border-amber-sim/30 bg-amber-sim/10',
          )}>
            {data.highlightType === 'best' ? 'Best' : data.highlightType === 'worst' ? 'Worst' : 'Likely'}
          </span>
        )}
      </div>
      <p className="text-[10px] text-text-secondary font-body leading-snug line-clamp-3">{data.label}</p>
      {data.prob !== undefined && (
        <div className="mt-2 flex items-center justify-between">
          <span className="text-[9px] font-mono text-text-dim">success</span>
          <span className={clsx('text-[11px] font-mono font-bold', probColor(data.prob))}>
            {Math.round(data.prob * 100)}%
          </span>
        </div>
      )}
    </div>
  )
}

function OutcomeNode({ data }: {
  data: { outcome: string; summary: string; type: 'best' | 'worst' | 'likely' }
}) {
  const styles = {
    best: 'border-green-good/40 bg-green-good/5',
    worst: 'border-red-alert/40 bg-red-alert/5',
    likely: 'border-amber-sim/40 bg-amber-sim/5',
  }
  const textStyles = {
    best: 'text-green-good',
    worst: 'text-red-alert',
    likely: 'text-amber-sim',
  }
  const labels = { best: 'Best Case', worst: 'Worst Case', likely: 'Most Likely' }

  return (
    <div className={clsx('px-4 py-3 border rounded max-w-[220px]', styles[data.type])}>
      <Handle type="target" position={Position.Top} style={{ background: '#1a2535', border: 'none', width: 8, height: 8 }} />
      <div className={clsx('text-[9px] font-mono tracking-[0.2em] uppercase mb-1', textStyles[data.type])}>
        {labels[data.type]}
      </div>
      <p className="text-[10px] text-text-primary font-body leading-snug">{data.summary}</p>
    </div>
  )
}

const nodeTypes = {
  scenario: ScenarioNode,
  branch: BranchNode,
  outcome: OutcomeNode,
}

// ── Layout calculation ─────────────────────────────────────────────────────

function buildGraph(
  scenario: string,
  branches: SimulationResponse[],
  report?: ComparisonReport
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = []
  const edges: Edge[] = []

  const BRANCH_SPACING = 260
  const totalWidth = (branches.length - 1) * BRANCH_SPACING
  const startX = 400

  // Scenario root
  nodes.push({
    id: 'scenario',
    type: 'scenario',
    position: { x: startX, y: 0 },
    data: { label: scenario.slice(0, 120) + (scenario.length > 120 ? '…' : '') },
  })

  // Helper: is this branch the best/worst/likely?
  const bestDp = report?.best_case?.decision_point
  const worstDp = report?.worst_case?.decision_point
  const likelyDp = report?.most_likely?.decision_point

  branches.forEach((branch, i) => {
    const x = startX - totalWidth / 2 + i * BRANCH_SPACING
    const branchId = `branch-${i}`

    const avgProb =
      branch.analysis?.persona_goal_success?.reduce((s, p) => s + p.success_probability, 0) /
        (branch.analysis?.persona_goal_success?.length || 1) || undefined

    const isBest = branch.decision_point === bestDp
    const isWorst = branch.decision_point === worstDp
    const isLikely = branch.decision_point === likelyDp

    nodes.push({
      id: branchId,
      type: 'branch',
      position: { x, y: 160 },
      data: {
        label: branch.decision_point.slice(0, 100) + (branch.decision_point.length > 100 ? '…' : ''),
        letter: String.fromCharCode(65 + i),
        prob: avgProb,
        isHighlight: isBest || isWorst || isLikely,
        highlightType: isBest ? 'best' : isWorst ? 'worst' : isLikely ? 'likely' : undefined,
      },
    })

    edges.push({
      id: `e-scenario-${branchId}`,
      source: 'scenario',
      target: branchId,
      markerEnd: { type: MarkerType.ArrowClosed, color: '#00e5ff', width: 16, height: 16 },
      style: { stroke: '#00e5ff', strokeWidth: 1.5, opacity: 0.5 },
      animated: true,
    })

    // Outcome node for each branch
    const outcome = branch.analysis?.outcome_category
    if (outcome) {
      const type = outcome === 'Best Case' ? 'best' : outcome === 'Worst Case' ? 'worst' : 'likely'
      const outcomeId = `outcome-${i}`
      nodes.push({
        id: outcomeId,
        type: 'outcome',
        position: { x, y: 380 },
        data: {
          outcome,
          summary: (branch.analysis?.outcome_summary || '').slice(0, 120),
          type,
        },
      })
      edges.push({
        id: `e-${branchId}-${outcomeId}`,
        source: branchId,
        target: outcomeId,
        markerEnd: { type: MarkerType.ArrowClosed, color: '#1a2535', width: 14, height: 14 },
        style: { stroke: '#1a2535', strokeWidth: 1.5 },
      })
    }
  })

  return { nodes, edges }
}

// ── Main Component ─────────────────────────────────────────────────────────

export default function DecisionTree({
  scenario,
  branches,
  report,
}: {
  scenario: string
  branches: SimulationResponse[]
  report?: ComparisonReport
}) {
  const { nodes, edges } = useMemo(
    () => buildGraph(scenario, branches, report),
    [scenario, branches, report]
  )

  return (
    <div className="w-full h-[520px] rounded border border-border overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        defaultEdgeOptions={{ animated: false }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#1a2535" />
        <Controls showInteractive={false} />
        <MiniMap
          nodeColor={(n) => {
            if (n.type === 'scenario') return '#00e5ff'
            if (n.type === 'outcome') return '#1a2535'
            return '#0d1420'
          }}
          maskColor="rgba(8,12,18,0.8)"
        />
      </ReactFlow>
    </div>
  )
}
