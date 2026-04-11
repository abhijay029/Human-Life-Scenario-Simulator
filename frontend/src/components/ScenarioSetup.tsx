'use client'
import { useState } from 'react'
import type { PersonaSchema, SimMode } from '@/lib/types'
import { Panel, Button, Textarea, Input, Badge, Divider } from './ui'
import { GitBranch, Zap, Plus, Trash2 } from 'lucide-react'

export default function ScenarioSetup({
  personas,
  mode,
  onModeChange,
  scenario,
  onScenarioChange,
  decisionPoint,
  onDecisionPointChange,
  decisionBranches,
  onDecisionBranchesChange,
  maxTurns,
  onMaxTurnsChange,
  onBack,
  onRun,
  loading,
}: {
  personas: PersonaSchema[]
  mode: SimMode
  onModeChange: (m: SimMode) => void
  scenario: string
  onScenarioChange: (s: string) => void
  decisionPoint: string
  onDecisionPointChange: (s: string) => void
  decisionBranches: string[]
  onDecisionBranchesChange: (b: string[]) => void
  maxTurns: number
  onMaxTurnsChange: (n: number) => void
  onBack: () => void
  onRun: () => void
  loading: boolean
}) {
  const [newBranch, setNewBranch] = useState('')

  const addBranch = () => {
    if (newBranch.trim() && decisionBranches.length < 6) {
      onDecisionBranchesChange([...decisionBranches, newBranch.trim()])
      setNewBranch('')
    }
  }

  const removeBranch = (i: number) =>
    onDecisionBranchesChange(decisionBranches.filter((_, j) => j !== i))

  const isValid =
    scenario.trim() &&
    (mode === 'single' ? decisionPoint.trim() : decisionBranches.length >= 2)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold text-text-primary">Scenario Setup</h2>
        <p className="text-sm text-text-secondary mt-1">
          Define the situation and how you want to explore it.
        </p>
      </div>

      {/* Active Personas */}
      <Panel label="Active Personas" className="p-4">
        <div className="flex flex-wrap gap-2">
          {personas.map((p, i) => (
            <div key={i} className="flex items-center gap-2 bg-border rounded px-3 py-1.5">
              <div className="w-5 h-5 rounded-full bg-cyan/20 flex items-center justify-center text-[10px] font-mono text-cyan font-bold">
                {p.name[0]}
              </div>
              <div>
                <p className="text-xs font-mono text-text-primary">{p.name}</p>
                <p className="text-[10px] text-text-secondary">{p.occupation}</p>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      {/* Scenario */}
      <Textarea
        label="Scenario Description"
        value={scenario}
        onChange={onScenarioChange}
        rows={3}
        placeholder="Arjun has just told his father Rahul that he wants to drop his engineering career and pursue music full time after graduation…"
      />

      {/* Simulation Mode */}
      <div className="space-y-3">
        <label className="text-[10px] font-mono text-text-secondary tracking-[0.15em] uppercase">
          Simulation Mode
        </label>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => onModeChange('single')}
            className={`panel p-4 text-left transition-all duration-200 ${
              mode === 'single'
                ? 'border-cyan/50 shadow-[0_0_16px_rgba(0,229,255,0.12)]'
                : 'hover:border-border/80'
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <Zap size={16} className={mode === 'single' ? 'text-cyan' : 'text-text-secondary'} />
              <span className="font-mono text-sm font-bold text-text-primary">Single Run</span>
              {mode === 'single' && <Badge variant="cyan">Active</Badge>}
            </div>
            <p className="text-xs text-text-secondary">
              Test one specific decision. Fast, focused analysis.
            </p>
          </button>

          <button
            onClick={() => onModeChange('multiverse')}
            className={`panel p-4 text-left transition-all duration-200 ${
              mode === 'multiverse'
                ? 'border-cyan/50 shadow-[0_0_16px_rgba(0,229,255,0.12)]'
                : 'hover:border-border/80'
            }`}
          >
            <div className="flex items-center gap-2 mb-2">
              <GitBranch
                size={16}
                className={mode === 'multiverse' ? 'text-cyan' : 'text-text-secondary'}
              />
              <span className="font-mono text-sm font-bold text-text-primary">Multiverse</span>
              {mode === 'multiverse' && <Badge variant="cyan">Active</Badge>}
            </div>
            <p className="text-xs text-text-secondary">
              Compare 2–6 decision branches. Best/Worst/Most Likely report.
            </p>
          </button>
        </div>
      </div>

      {/* Decision Input */}
      {mode === 'single' ? (
        <Textarea
          label="Decision Point"
          value={decisionPoint}
          onChange={onDecisionPointChange}
          rows={2}
          placeholder="Arjun decides to be fully honest and reveals he already has a music production deal…"
        />
      ) : (
        <div className="space-y-3">
          <label className="text-[10px] font-mono text-text-secondary tracking-[0.15em] uppercase">
            Decision Branches ({decisionBranches.length}/6)
          </label>

          {decisionBranches.map((b, i) => (
            <div key={i} className="flex items-start gap-2 stagger-child">
              <div className="flex-shrink-0 w-5 h-5 mt-2 rounded bg-cyan/10 border border-cyan/20 flex items-center justify-center text-[10px] font-mono text-cyan">
                {String.fromCharCode(65 + i)}
              </div>
              <div className="flex-1 bg-void border border-border rounded px-3 py-2 text-sm text-text-primary font-body min-h-[36px] flex items-center">
                {b}
              </div>
              <button
                onClick={() => removeBranch(i)}
                className="mt-2 text-text-dim hover:text-red-alert transition-colors"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}

          {decisionBranches.length < 6 && (
            <div className="flex gap-2">
              <input
                value={newBranch}
                onChange={(e) => setNewBranch(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addBranch()}
                placeholder="Describe a decision path…"
                className="flex-1 bg-void border border-border rounded px-3 py-2 text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-cyan/40 transition-all font-body"
              />
              <Button variant="secondary" onClick={addBranch} disabled={!newBranch.trim()}>
                <Plus size={14} />
                Add
              </Button>
            </div>
          )}

          {decisionBranches.length < 2 && (
            <p className="text-xs text-text-dim font-mono">Add at least 2 decision branches.</p>
          )}
        </div>
      )}

      <Divider />

      {/* Max turns */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-mono text-text-secondary">Max Dialogue Turns</p>
          <p className="text-[10px] text-text-dim">Fewer turns = faster results (2–8 recommended)</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onMaxTurnsChange(Math.max(2, maxTurns - 1))}
            className="w-7 h-7 panel flex items-center justify-center text-text-secondary hover:text-cyan transition-colors font-mono"
          >
            −
          </button>
          <span className="w-8 text-center font-mono text-cyan text-sm">{maxTurns}</span>
          <button
            onClick={() => onMaxTurnsChange(Math.min(10, maxTurns + 1))}
            className="w-7 h-7 panel flex items-center justify-center text-text-secondary hover:text-cyan transition-colors font-mono"
          >
            +
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-2">
        <Button variant="ghost" onClick={onBack}>
          ← Back
        </Button>
        <Button
          variant="primary"
          onClick={onRun}
          disabled={!isValid || loading}
          loading={loading}
          className="px-8"
        >
          {loading ? 'Simulating…' : `Run ${mode === 'multiverse' ? 'Multiverse' : 'Simulation'} →`}
        </Button>
      </div>
    </div>
  )
}
