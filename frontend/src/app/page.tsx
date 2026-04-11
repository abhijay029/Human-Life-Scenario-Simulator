'use client'
import { useState, useRef } from 'react'
import type { PersonaSchema, SimMode, SimulationResponse, MultiverseResponse } from '@/lib/types'
import { runSimulation, runMultiverse } from '@/lib/api'
import CharacterBuilder from '@/components/CharacterBuilder'
import ScenarioSetup from '@/components/ScenarioSetup'
import SimulatingScreen from '@/components/SimulatingScreen'
import ResultsView from '@/components/ResultsView'
import { clsx } from 'clsx'
import { Users, Settings, BarChart2, Cpu } from 'lucide-react'

// ── Step indicator ─────────────────────────────────────────────────────────

const STEPS = [
  { key: 'build', label: 'Characters', icon: Users },
  { key: 'simulate', label: 'Scenario', icon: Settings },
  { key: 'results', label: 'Results', icon: BarChart2 },
]

function StepBar({ current }: { current: string }) {
  const idx = STEPS.findIndex((s) => s.key === current)
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((step, i) => {
        const Icon = step.icon
        const isActive = i === idx
        const isDone = i < idx
        return (
          <div key={step.key} className="flex items-center">
            <div
              className={clsx(
                'flex items-center gap-2 px-4 py-2 text-xs font-mono tracking-wide transition-all duration-300',
                isActive && 'text-cyan',
                isDone && 'text-green-good',
                !isActive && !isDone && 'text-text-dim'
              )}
            >
              <div
                className={clsx(
                  'w-6 h-6 rounded-full border flex items-center justify-center transition-all',
                  isActive && 'border-cyan bg-cyan/10',
                  isDone && 'border-green-good bg-green-good/10',
                  !isActive && !isDone && 'border-border'
                )}
              >
                {isDone ? (
                  <span className="text-green-good text-[10px]">✓</span>
                ) : (
                  <Icon size={11} />
                )}
              </div>
              <span className="hidden sm:inline">{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={clsx('w-8 h-px transition-all duration-500', i < idx ? 'bg-green-good/40' : 'bg-border')} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Default personas ───────────────────────────────────────────────────────

const DEFAULT_PERSONAS: PersonaSchema[] = [
  {
    name: 'Rahul Sharma',
    age: 45,
    occupation: 'Senior Manager at a private firm',
    personality_traits: ['authoritative', 'traditional', 'protective', 'stubborn'],
    values: ['family honour', 'financial stability', 'respect for elders'],
    communication_style: 'direct and assertive, sometimes dismissive',
    emotional_triggers: ['feeling disrespected', 'loss of control', 'public embarrassment'],
    background:
      'Rahul grew up in a middle-class family in Nagpur. He worked hard to reach his position and believes discipline and sacrifice are the keys to success.',
    goals: ['ensure his child makes a safe career choice', 'maintain family harmony on his terms'],
  },
  {
    name: 'Arjun Sharma',
    age: 21,
    occupation: 'Final year engineering student',
    personality_traits: ['passionate', 'idealistic', 'conflict-averse', 'creative'],
    values: ['self-expression', 'following his passion', 'independence'],
    communication_style: 'hesitant but earnest, avoids direct confrontation',
    emotional_triggers: ['being dismissed', 'feeling unheard', 'comparisons to others'],
    background:
      "Arjun has always loved music and secretly produces tracks. He is about to graduate and wants to pursue music full time, but fears his father's reaction deeply.",
    goals: ['convince his father to support his music career', 'avoid a major family conflict'],
  },
]

// ── Main App ───────────────────────────────────────────────────────────────

export default function Home() {
  const [step, setStep] = useState<'build' | 'simulate' | 'running' | 'results'>('build')
  const [personas, setPersonas] = useState<PersonaSchema[]>(DEFAULT_PERSONAS)
  const [mode, setMode] = useState<SimMode>('single')
  const [scenario, setScenario] = useState(
    'Arjun has just told his father Rahul that he wants to drop his engineering career and pursue music full time after graduation.'
  )
  const [decisionPoint, setDecisionPoint] = useState(
    'Arjun decides to be honest and direct: he tells Rahul he has already been offered a music production deal worth ₹3 lakh.'
  )
  const [decisionBranches, setDecisionBranches] = useState<string[]>([
    'Arjun is fully honest: he reveals he already has a music production deal worth ₹3 lakh.',
    "Arjun is evasive: he says he 'just wants to explore options' without committing to anything.",
    'Arjun brings a mediator: he asks his mother to be present and starts the conversation gently.',
  ])
  const [maxTurns, setMaxTurns] = useState(4)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [singleResult, setSingleResult] = useState<SimulationResponse | undefined>()
  const [multiverseResult, setMultiverseResult] = useState<MultiverseResponse | undefined>()

  // Guard against double-invocation (React Strict Mode / double-click)
  const isRunning = useRef(false)

  const handleRun = async () => {
    if (isRunning.current) return          // block if already in flight
    isRunning.current = true

    setError('')
    setLoading(true)
    setStep('running')

    try {
      if (mode === 'single') {
        const res = await runSimulation({
          personas,
          scenario,
          decision_point: decisionPoint,
          max_turns: maxTurns,
          store_memories: true,
        })
        setSingleResult(res)
        setMultiverseResult(undefined)
      } else {
        const res = await runMultiverse({
          personas,
          scenario,
          decision_branches: decisionBranches,
          max_turns: maxTurns,
          store_memories: true,
        })
        setMultiverseResult(res)
        setSingleResult(undefined)
      }
      setStep('results')
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Simulation failed'
      setError(msg)
      setStep('simulate')
    } finally {
      setLoading(false)
      isRunning.current = false            // release lock
    }
  }

  const handleReset = () => {
    setStep('build')
    setSingleResult(undefined)
    setMultiverseResult(undefined)
    setError('')
    isRunning.current = false
  }

  const displayStep = step === 'running' ? 'simulate' : step

  return (
    <div className="min-h-screen grid-bg">
      {/* Top bar */}
      <header className="border-b border-border bg-panel/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded bg-cyan/10 border border-cyan/30 flex items-center justify-center">
              <Cpu size={13} className="text-cyan" />
            </div>
            <div>
              <p className="text-xs font-display font-bold text-text-primary tracking-wide">
                HLSS
              </p>
              <p className="text-[9px] font-mono text-text-dim tracking-wider hidden sm:block">
                Human Life Scenario Simulator
              </p>
            </div>
          </div>

          {step !== 'running' && <StepBar current={displayStep} />}

          <div className="text-[10px] font-mono text-text-dim hidden sm:block">
            v0.3.0
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-5xl mx-auto px-6 py-10">
        {step === 'running' && <SimulatingScreen mode={mode} />}

        {step === 'build' && (
          <CharacterBuilder
            personas={personas}
            onChange={setPersonas}
            onNext={() => setStep('simulate')}
          />
        )}

        {step === 'simulate' && (
          <>
            {error && (
              <div className="mb-4 p-3 bg-red-alert/10 border border-red-alert/30 rounded text-xs font-mono text-red-alert">
                ⚠ {error}
              </div>
            )}
            <ScenarioSetup
              personas={personas}
              mode={mode}
              onModeChange={setMode}
              scenario={scenario}
              onScenarioChange={setScenario}
              decisionPoint={decisionPoint}
              onDecisionPointChange={setDecisionPoint}
              decisionBranches={decisionBranches}
              onDecisionBranchesChange={setDecisionBranches}
              maxTurns={maxTurns}
              onMaxTurnsChange={setMaxTurns}
              onBack={() => setStep('build')}
              onRun={handleRun}
              loading={loading}
            />
          </>
        )}

        {step === 'results' && (
          <ResultsView
            mode={mode}
            singleResult={singleResult}
            multiverseResult={multiverseResult}
            onReset={handleReset}
          />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border mt-20 py-6">
        <p className="text-center text-[10px] font-mono text-text-dim tracking-wider">
          HUMAN LIFE SCENARIO SIMULATOR · Abhijay Tambe · Himanshu Khobragade · Arpit Deshmukh · Guide: Prof. Harshita Patil
        </p>
      </footer>
    </div>
  )
}
