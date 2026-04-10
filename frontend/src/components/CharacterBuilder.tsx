'use client'
import { useState } from 'react'
import { buildPersona } from '@/lib/api'
import type { PersonaSchema } from '@/lib/types'
import { Panel, Button, Input, Textarea, TagInput, Divider, Spinner } from './ui'
import { Sparkles, User, Plus, Trash2, ChevronDown, ChevronUp } from 'lucide-react'

const EMPTY_PERSONA = (): PersonaSchema => ({
  name: '',
  age: 25,
  occupation: '',
  personality_traits: [],
  values: [],
  communication_style: '',
  emotional_triggers: [],
  background: '',
  goals: [],
})

function PersonaCard({
  persona,
  index,
  onChange,
  onRemove,
}: {
  persona: PersonaSchema
  index: number
  onChange: (p: PersonaSchema) => void
  onRemove: () => void
}) {
  const [expanded, setExpanded] = useState(true)
  const [aiDesc, setAiDesc] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiError, setAiError] = useState('')

  const handleAiBuild = async () => {
    if (!aiDesc.trim()) return
    setAiLoading(true)
    setAiError('')
    try {
      const res = await buildPersona(aiDesc)
      onChange(res.persona)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'AI build failed'
      setAiError(msg)
    } finally {
      setAiLoading(false)
    }
  }

  const set = <K extends keyof PersonaSchema>(k: K, v: PersonaSchema[K]) =>
    onChange({ ...persona, [k]: v })

  return (
    <Panel
      className="overflow-hidden"
      label={`Persona ${index + 1}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-cyan/10 border border-cyan/20 flex items-center justify-center">
            <User size={14} className="text-cyan" />
          </div>
          <div>
            <p className="font-display font-semibold text-text-primary text-sm">
              {persona.name || `Unnamed Persona ${index + 1}`}
            </p>
            <p className="text-[11px] text-text-secondary font-mono">
              {persona.occupation || 'No occupation set'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-text-dim hover:text-text-secondary transition-colors"
          >
            {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
          {index > 0 && (
            <button onClick={onRemove} className="text-text-dim hover:text-red-alert transition-colors">
              <Trash2 size={14} />
            </button>
          )}
        </div>
      </div>

      {expanded && (
        <div className="p-4 space-y-5">
          {/* AI Quick Build */}
          <div className="bg-cyan/5 border border-cyan/15 rounded p-3 space-y-2">
            <div className="flex items-center gap-2 text-[10px] font-mono text-cyan tracking-[0.15em] uppercase">
              <Sparkles size={11} />
              AI Quick Build
            </div>
            <div className="flex gap-2">
              <input
                value={aiDesc}
                onChange={(e) => setAiDesc(e.target.value)}
                placeholder="Describe this person in plain language…"
                className="flex-1 bg-void border border-border rounded px-3 py-1.5 text-sm text-text-primary placeholder:text-text-dim focus:outline-none focus:border-cyan/40 transition-all font-body"
                onKeyDown={(e) => e.key === 'Enter' && handleAiBuild()}
              />
              <Button
                variant="primary"
                onClick={handleAiBuild}
                loading={aiLoading}
                disabled={!aiDesc.trim()}
              >
                Build
              </Button>
            </div>
            {aiError && <p className="text-xs text-red-alert font-mono">{aiError}</p>}
          </div>

          <Divider label="or fill manually" />

          {/* Basic fields */}
          <div className="grid grid-cols-2 gap-3">
            <Input label="Full Name" value={persona.name} onChange={(v) => set('name', v)} placeholder="Rahul Sharma" />
            <Input label="Age" type="number" value={String(persona.age)} onChange={(v) => set('age', parseInt(v) || 0)} />
          </div>
          <Input label="Occupation" value={persona.occupation} onChange={(v) => set('occupation', v)} placeholder="Senior Manager" />
          <Input
            label="Communication Style"
            value={persona.communication_style}
            onChange={(v) => set('communication_style', v)}
            placeholder="direct and assertive, sometimes dismissive"
          />

          {/* Tag fields */}
          <TagInput
            label="Personality Traits"
            tags={persona.personality_traits}
            onChange={(v) => set('personality_traits', v)}
            placeholder="authoritative, traditional…"
          />
          <TagInput
            label="Core Values"
            tags={persona.values}
            onChange={(v) => set('values', v)}
            placeholder="family honour, stability…"
          />
          <TagInput
            label="Emotional Triggers"
            tags={persona.emotional_triggers}
            onChange={(v) => set('emotional_triggers', v)}
            placeholder="feeling disrespected…"
          />
          <TagInput
            label="Goals in this Situation"
            tags={persona.goals}
            onChange={(v) => set('goals', v)}
            placeholder="ensure safe career choice…"
          />
          <Textarea
            label="Background (2-3 sentences)"
            value={persona.background}
            onChange={(v) => set('background', v)}
            rows={3}
            placeholder="Grew up in Nagpur, worked hard to reach his position…"
          />
        </div>
      )}
    </Panel>
  )
}

export default function CharacterBuilder({
  personas,
  onChange,
  onNext,
}: {
  personas: PersonaSchema[]
  onChange: (personas: PersonaSchema[]) => void
  onNext: () => void
}) {
  const addPersona = () => onChange([...personas, EMPTY_PERSONA()])
  const removePersona = (i: number) => onChange(personas.filter((_, j) => j !== i))
  const updatePersona = (i: number, p: PersonaSchema) => {
    const copy = [...personas]
    copy[i] = p
    onChange(copy)
  }

  const isValid = personas.length >= 2 && personas.every(
    (p) => p.name.trim() && p.occupation.trim() && p.goals.length > 0
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold text-text-primary">
          Character Builder
        </h2>
        <p className="text-sm text-text-secondary mt-1">
          Define the personas who will participate in the simulation. Minimum 2 required.
        </p>
      </div>

      {/* Persona Cards */}
      <div className="space-y-4">
        {personas.map((p, i) => (
          <div key={i} className="stagger-child">
            <PersonaCard
              persona={p}
              index={i}
              onChange={(updated) => updatePersona(i, updated)}
              onRemove={() => removePersona(i)}
            />
          </div>
        ))}
      </div>

      {/* Add + Next */}
      <div className="flex items-center justify-between pt-2">
        <Button variant="ghost" onClick={addPersona} className="gap-2">
          <Plus size={14} />
          Add Persona
        </Button>
        <Button
          variant="primary"
          onClick={onNext}
          disabled={!isValid}
          className="gap-2 px-6"
        >
          Continue to Scenario →
        </Button>
      </div>

      {!isValid && (
        <p className="text-xs text-text-dim font-mono text-center">
          Each persona needs a name, occupation, and at least one goal. Minimum 2 personas required.
        </p>
      )}
    </div>
  )
}
