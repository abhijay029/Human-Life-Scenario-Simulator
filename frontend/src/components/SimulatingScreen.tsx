'use client'
import { useEffect, useState } from 'react'
import type { SimMode } from '@/lib/types'

const SINGLE_STEPS = [
  'Initialising persona agents…',
  'Loading character memories from vector store…',
  'Building simulation graph with LangGraph…',
  'Running dialogue turns…',
  'Observer Agent analysing outcomes…',
  'Generating sentiment scores…',
  'Compiling final report…',
]

const MULTI_STEPS = [
  'Initialising persona agents…',
  'Loading character memories from vector store…',
  'Spawning decision branches…',
  'Simulating Branch A…',
  'Simulating Branch B…',
  'Simulating Branch C…',
  'Observer Agent scoring each branch…',
  'Ranking outcomes by success probability…',
  'Generating comparison report…',
]

export default function SimulatingScreen({ mode }: { mode: SimMode }) {
  const steps = mode === 'multiverse' ? MULTI_STEPS : SINGLE_STEPS
  const [currentStep, setCurrentStep] = useState(0)
  const [dots, setDots] = useState('.')

  useEffect(() => {
    const stepInterval = setInterval(() => {
      setCurrentStep((s) => Math.min(s + 1, steps.length - 1))
    }, mode === 'multiverse' ? 4000 : 3000)
    return () => clearInterval(stepInterval)
  }, [steps.length, mode])

  useEffect(() => {
    const dotInterval = setInterval(() => {
      setDots((d) => (d.length >= 3 ? '.' : d + '.'))
    }, 500)
    return () => clearInterval(dotInterval)
  }, [])

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-8">
      {/* Animated core */}
      <div className="relative w-24 h-24">
        {/* Outer ring */}
        <div className="absolute inset-0 rounded-full border-2 border-cyan/20 animate-spin"
             style={{ animationDuration: '3s' }} />
        {/* Inner ring */}
        <div className="absolute inset-3 rounded-full border border-cyan/40 animate-spin"
             style={{ animationDuration: '1.5s', animationDirection: 'reverse' }} />
        {/* Core dot */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-6 h-6 rounded-full bg-cyan/20 border border-cyan/60 neon-pulse" />
        </div>
      </div>

      {/* Status */}
      <div className="text-center space-y-2">
        <p className="font-display text-xl font-bold text-text-primary">
          {mode === 'multiverse' ? 'Simulating Multiverse' : 'Running Simulation'}
          {dots}
        </p>
        <p className="text-xs font-mono text-text-secondary tracking-wide">
          This may take 1–3 minutes due to API rate limits
        </p>
      </div>

      {/* Step log */}
      <div className="w-full max-w-sm space-y-2">
        {steps.map((step, i) => (
          <div
            key={i}
            className={`flex items-center gap-3 px-4 py-2 rounded transition-all duration-500 ${
              i < currentStep
                ? 'opacity-40'
                : i === currentStep
                ? 'bg-cyan/5 border border-cyan/15'
                : 'opacity-20'
            }`}
          >
            <div
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                i < currentStep
                  ? 'bg-green-good'
                  : i === currentStep
                  ? 'bg-cyan neon-pulse'
                  : 'bg-border'
              }`}
            />
            <p
              className={`text-xs font-mono ${
                i === currentStep ? 'text-cyan' : 'text-text-secondary'
              }`}
            >
              {step}
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
