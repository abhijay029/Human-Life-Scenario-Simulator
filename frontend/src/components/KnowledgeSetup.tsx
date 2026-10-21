import React, { useState, useEffect, useRef } from 'react'
import {
  KLPersona,
  KLTopic,
  Level,
  Tone,
  KnowledgeConfig,
  saveKnowledgeConfig,
  generateKLTopics,
  generateKLBriefs,
} from '@/lib/knowledgeLimiterApi'
import type { SimMode } from '@/lib/types'
import { Button } from './ui'
import { Plus, Trash2, Sparkles, BookOpen, Loader2, Pencil, Search, ChevronDown, ChevronRight } from 'lucide-react'

interface KnowledgeSetupProps {
  personas: KLPersona[]
  scenarioId: string
  /** The scenario the user has already written — topics are generated from it. */
  scenarioDescription: string
  /** Decision point (single run) or decision branches (multiverse). */
  decisionPoints: string[]
  tone: Tone
  mode: SimMode
  /** Identifies the inputs above; cached topics are reused only if it still matches. */
  inputKey: string
  cachedTopics: { key: string; topics: KLTopic[] } | null
  onTopicsChange: (key: string, topics: KLTopic[]) => void
  maxTurns: number
  onMaxTurnsChange: (n: number) => void
  running: boolean
  runError?: string
  onBack: () => void
  /** Called with the compiled config, or with nothing when the user skips. */
  onRun: (config?: KnowledgeConfig) => void
}

const LEVELS: Level[] = ['layperson', 'basic', 'advanced', 'expert']
const FACT_LEVELS: Level[] = ['advanced', 'expert']
const isWebResearchable = (topic: KLTopic) =>
  Object.values(topic.levels).some((level) => level === 'advanced' || level === 'expert')

export default function KnowledgeSetup({
  personas,
  scenarioId,
  scenarioDescription,
  decisionPoints,
  tone,
  mode,
  inputKey,
  cachedTopics,
  onTopicsChange,
  maxTurns,
  onMaxTurnsChange,
  running,
  runError,
  onBack,
  onRun,
}: KnowledgeSetupProps) {
  // Reuse topics (and any manual edits) only if the scenario inputs haven't changed
  // since they were generated; otherwise generate fresh ones for the current scenario.
  const cacheHit = cachedTopics !== null && cachedTopics.key === inputKey
  const [topics, setTopics] = useState<KLTopic[]>(cacheHit ? cachedTopics!.topics : [])
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(!cacheHit)
  const [error, setError] = useState('')
  const [researching, setResearching] = useState(false)
  const [researchNote, setResearchNote] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const persist = useRef(cacheHit)
  const started = useRef(false)

  const handleGenerateTopics = async () => {
    setGenerating(true)
    setError('')
    try {
      const res = await generateKLTopics({
        scenario_description: scenarioDescription,
        tone,
        decision_points: decisionPoints,
        personas: personas.map((p) => ({
          name: p.name,
          profession: p.profession,
          background_summary: p.background_summary,
        })),
      })
      if (res.topics && res.topics.length > 0) {
        const remapped = res.topics.map((t) => {
          const lvls: Record<string, Level> = {}
          personas.forEach((p) => {
            lvls[p.id] = t.levels[p.name] || t.levels[p.id] || p.default_level
          })
          return { ...t, levels: lvls }
        })
        persist.current = true
        setTopics(remapped)
        setExpanded({})
        setResearchNote('')
        await handleResearchTopics(remapped)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to generate topics')
    } finally {
      setGenerating(false)
    }
  }

  useEffect(() => {
    // Generate scenario-tailored topics on first load, unless we have a valid cache.
    // The ref guards against React Strict Mode running this effect twice in dev.
    if (started.current) return
    started.current = true
    if (!cacheHit) {
      handleGenerateTopics()
    } else if (topics.some((topic) => isWebResearchable(topic) && !topic.brief?.grounded)) {
      handleResearchTopics(topics)
    }
  }, [])

  useEffect(() => {
    // Keep the parent's cache in sync so edits survive going back and forth.
    if (persist.current) onTopicsChange(inputKey, topics)
  }, [topics])

  // New topic form state
  const [newTopicName, setNewTopicName] = useState('')
  const [newTopicDomain, setNewTopicDomain] = useState('')
  const [newTopicConcepts, setNewTopicConcepts] = useState('')

  const handleLevelChange = (topicId: string, personaId: string, level: Level) => {
    const currentTopic = topics.find((topic) => topic.id === topicId)
    if (!currentTopic) return
    const updatedTopic = {
      ...currentTopic,
      levels: { ...currentTopic.levels, [personaId]: level },
    }
    setTopics((prev) => prev.map((topic) => topic.id === topicId ? updatedTopic : topic))
    if (isWebResearchable(updatedTopic) && !updatedTopic.brief?.grounded) {
      handleResearchTopics([updatedTopic])
    }
  }

  const handleBulkSetNonDomain = (persona: KLPersona) => {
    setTopics((prev) =>
      prev.map((t) => {
        if (t.domain !== persona.own_domain) {
          return {
            ...t,
            levels: {
              ...t.levels,
              [persona.id]: 'layperson',
            },
          }
        }
        return t
      })
    )
  }

  // Only topics with advanced/expert personas need web research.
  const researchable = topics.filter(isWebResearchable)

  const handleResearchTopics = async (topicsToResearch: KLTopic[]) => {
    const eligibleTopics = topicsToResearch.filter(isWebResearchable)
    if (eligibleTopics.length === 0) return

    setResearching(true)
    setError('')
    setResearchNote('')
    try {
      const res = await generateKLBriefs(eligibleTopics)
      const ids = Object.keys(res.briefs)
      persist.current = true
      setTopics((prev) => prev.map((t) => (res.briefs[t.id] ? { ...t, brief: res.briefs[t.id] } : t)))
      const web = ids.filter((id) => res.briefs[id].grounded).length
      const failed = Object.keys(res.errors).length
      const parts = [`Researched ${ids.length} topic${ids.length === 1 ? '' : 's'}`]
      if (ids.length > 0) parts.push(`${web} backed by web sources`)
      if (failed > 0) parts.push(`${failed} failed`)
      if (res.skipped.length > 0) parts.push(`${res.skipped.length} skipped`)
      setResearchNote(parts.join(' — ') + '. Review the facts below before confirming.')
    } catch (e: unknown) {
      setResearchNote(`Web research could not be completed: ${e instanceof Error ? e.message : 'Unknown error'}`)
    } finally {
      setResearching(false)
    }
  }

  const handleResearchBriefs = () => handleResearchTopics(researchable)

  const updateBriefFact = (
    topicId: string,
    index: number,
    patch: Partial<{ text: string; min_level: Level }>
  ) => {
    setTopics((prev) =>
      prev.map((t) =>
        t.id === topicId && t.brief
          ? {
              ...t,
              brief: {
                ...t.brief,
                facts: t.brief.facts.map((f, i) => (i === index ? { ...f, ...patch } : f)),
              },
            }
          : t
      )
    )
  }

  const removeBriefFact = (topicId: string, index: number) => {
    setTopics((prev) =>
      prev.map((t) =>
        t.id === topicId && t.brief
          ? { ...t, brief: { ...t.brief, facts: t.brief.facts.filter((_, i) => i !== index) } }
          : t
      )
    )
  }

  const handleRemoveTopic = (topicId: string) => {
    setTopics((prev) => prev.filter((t) => t.id !== topicId))
  }

  const handleAddTopic = () => {
    if (!newTopicName.trim() || !newTopicDomain.trim()) return

    const conceptsList = newTopicConcepts
      .split(',')
      .map((c) => c.trim())
      .filter(Boolean)
      .map((term) => ({ term, min_level: 'basic' as Level }))

    const defaultLevels: Record<string, Level> = {}
    personas.forEach((p) => {
      defaultLevels[p.id] = p.own_domain === newTopicDomain ? 'expert' : p.default_level
    })

    const newTopic: KLTopic = {
      id: `custom_${Date.now()}`,
      name: newTopicName.trim(),
      domain: newTopicDomain.trim().toLowerCase(),
      concepts: conceptsList,
      levels: defaultLevels,
    }

    setTopics((prev) => [...prev, newTopic])
    if (isWebResearchable(newTopic)) handleResearchTopics([newTopic])
    setNewTopicName('')
    setNewTopicDomain('')
    setNewTopicConcepts('')
  }

  const handleConfirm = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await saveKnowledgeConfig({
        scenario_id: scenarioId,
        personas,
        topics,
      })
      onRun(res.knowledge_config)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to save configuration')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-panel/90 border border-border rounded-xl p-6 shadow-xl backdrop-blur-sm max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4 mb-6">
        <div>
          <div className="flex items-center gap-2">
            <BookOpen className="text-cyan w-5 h-5" />
            <h2 className="text-lg font-display font-bold text-text-primary">
              Knowledge Profiles & Boundaries
            </h2>
          </div>
          <p className="text-xs text-text-dim mt-1">
            Review and fine-tune what each persona is allowed to know. Default is layperson outside their field.
          </p>
          <p className="text-xs text-text-dim mt-0.5">
            Advanced/expert topics get sourced facts from web search. Layperson/basic personas use the LLM&apos;s
            general knowledge with level-specific instructions. Search uses topic names and concepts, not the scenario.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleResearchBriefs}
            disabled={researchable.length === 0 || generating || researching || loading || running}
            className="text-xs font-mono bg-cyan/15 border border-cyan/40 text-cyan hover:bg-cyan/30 px-3.5 py-1.5 rounded flex items-center gap-1.5 transition font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
            title={`Search the web for advanced/expert facts across ${researchable.length} topic${researchable.length === 1 ? '' : 's'}`}
          >
            {researching ? (
              <>
                <Loader2 size={13} className="animate-spin text-cyan" /> Researching...
              </>
            ) : (
              <>
                <Search size={13} className="text-cyan" /> Research Advanced/Expert Again
              </>
            )}
          </button>
          <button
            onClick={handleGenerateTopics}
            disabled={generating || researching || loading || running}
            className="text-xs font-mono bg-cyan/15 border border-cyan/40 text-cyan hover:bg-cyan/30 px-3.5 py-1.5 rounded flex items-center gap-1.5 transition font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
            title="Generate 8-12 topics customized to this scenario and persona professions"
          >
            {generating ? (
              <>
                <Loader2 size={13} className="animate-spin text-cyan" /> Generating...
              </>
            ) : (
              <>
                <Sparkles size={13} className="text-cyan" /> Regenerate Topics
              </>
            )}
          </button>
        </div>
      </div>

      {(error || runError) && (
        <div className="mb-4 p-3 bg-red-alert/10 border border-red-alert/30 rounded text-xs font-mono text-red-alert">
          ⚠ {error || runError}
        </div>
      )}

      {researchNote && (
        <div className="mb-4 p-3 bg-cyan/10 border border-cyan/30 rounded text-xs font-mono text-cyan">
          {researchNote}
        </div>
      )}

      {/* What the topics below are based on */}
      <div className="mb-4 p-3 bg-black/20 rounded-lg border border-border/50 text-xs">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1.5 min-w-0">
            <p className="text-[10px] font-mono text-text-dim">Topics are based on this scenario</p>
            <p className="text-text-primary">{scenarioDescription}</p>
            <p className="text-text-secondary">
              <span className="font-mono text-text-dim">
                {mode === 'multiverse' ? 'Decision branches: ' : 'Decision point: '}
              </span>
              {decisionPoints.length > 0 ? decisionPoints.join(' / ') : 'none set'}
            </p>
            <p className="text-text-secondary">
              <span className="font-mono text-text-dim">Tone: </span>
              {tone}
            </p>
          </div>
          <button
            onClick={onBack}
            disabled={running}
            className="flex-shrink-0 text-[11px] font-mono text-cyan hover:text-text-primary flex items-center gap-1.5 transition disabled:opacity-40"
          >
            <Pencil size={12} /> Edit scenario
          </button>
        </div>
      </div>

      {/* Bulk actions */}
      <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-black/20 rounded-lg border border-border/50">
        <span className="text-[11px] font-mono text-text-dim flex items-center gap-1 mr-2">
          <Sparkles size={13} className="text-cyan" /> Quick Bulk Presets:
        </span>
        {personas.map((p) => (
          <button
            key={p.id}
            onClick={() => handleBulkSetNonDomain(p)}
            className="text-[11px] font-mono px-2.5 py-1 bg-border/40 hover:bg-border/70 rounded text-text-primary transition"
          >
            Reset {p.name}&apos;s non-{p.own_domain} topics to layperson
          </button>
        ))}
      </div>

      {/* Topics Grid */}
      <div className="overflow-x-auto border border-border rounded-lg mb-6">
        <table className="w-full text-left text-xs">
          <thead className="bg-panel border-b border-border font-mono text-text-dim uppercase text-[10px]">
            <tr>
              <th className="p-3 w-1/3">Topic & Key Concepts</th>
              <th className="p-3 w-1/6">Domain</th>
              {personas.map((p) => (
                <th key={p.id} className="p-3 text-center">
                  <span className="text-cyan">{p.name}</span>
                  <div className="text-[9px] font-normal normal-case text-text-dim">
                    {p.profession} ({p.own_domain})
                  </div>
                </th>
              ))}
              <th className="p-3 w-12 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {topics.length === 0 && (
              <tr>
                <td colSpan={personas.length + 3} className="p-6 text-center text-text-dim font-mono">
                  {generating ? (
                    <span className="inline-flex items-center gap-2">
                      <Loader2 size={13} className="animate-spin text-cyan" /> Generating topics for this scenario…
                    </span>
                  ) : (
                    'No topics yet. Regenerate topics, or add a custom one below.'
                  )}
                </td>
              </tr>
            )}
            {topics.map((t) => (
              <React.Fragment key={t.id}>
              <tr className="hover:bg-cyan/5 transition-colors">
                <td className="p-3">
                  <div className="font-semibold text-text-primary">{t.name}</div>
                  <div className="text-[10px] text-text-dim mt-0.5">
                    {t.concepts.map((c) => (
                      <span
                        key={c.term}
                        className="inline-block mr-1.5 px-1.5 py-0.5 rounded bg-border/40 text-[9px] font-mono"
                      >
                        {c.term} ({c.min_level})
                      </span>
                    ))}
                  </div>
                  {t.brief && t.brief.facts.length > 0 && (
                    <button
                      onClick={() => setExpanded((prev) => ({ ...prev, [t.id]: !prev[t.id] }))}
                      className="mt-1.5 text-[10px] font-mono text-cyan hover:text-text-primary flex items-center gap-1 transition"
                      aria-expanded={!!expanded[t.id]}
                    >
                      {expanded[t.id] ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                      Researched knowledge: {t.brief.facts.length} fact{t.brief.facts.length === 1 ? '' : 's'}
                      {t.brief.grounded ? ' (web-sourced)' : ' (unverified)'}
                    </button>
                  )}
                </td>
                <td className="p-3 font-mono text-[11px] text-text-dim">
                  <span className="px-2 py-0.5 rounded bg-border/30 border border-border/50">
                    {t.domain}
                  </span>
                </td>
                {personas.map((p) => {
                  const currentLevel = t.levels[p.id] || p.default_level
                  return (
                    <td key={p.id} className="p-3 text-center">
                      <select
                        value={currentLevel}
                        onChange={(e) =>
                          handleLevelChange(t.id, p.id, e.target.value as Level)
                        }
                        className="bg-black/40 border border-border rounded px-2 py-1 text-xs font-mono text-text-primary focus:border-cyan outline-none"
                      >
                        {LEVELS.map((lvl) => (
                          <option key={lvl} value={lvl}>
                            {lvl}
                          </option>
                        ))}
                      </select>
                    </td>
                  )
                })}
                <td className="p-3 text-center">
                  <button
                    onClick={() => handleRemoveTopic(t.id)}
                    className="text-text-dim hover:text-red-alert p-1 rounded transition"
                    title="Remove Topic"
                  >
                    <Trash2 size={13} />
                  </button>
                </td>
              </tr>
              {expanded[t.id] && t.brief && (
                <tr className="bg-black/20">
                  <td colSpan={personas.length + 3} className="p-4">
                    <p className="text-[10px] text-text-dim mb-3">
                      Each persona only uses facts at or below their own level for this topic. Edit, re-level
                      or delete anything that looks wrong.
                    </p>
                    <div className="space-y-2">
                      {t.brief.facts.map((f, i) => (
                        <div key={i} className="flex items-start gap-2">
                          <select
                            value={f.min_level}
                            onChange={(e) => updateBriefFact(t.id, i, { min_level: e.target.value as Level })}
                            className="bg-black/40 border border-border rounded px-2 py-1 text-xs font-mono text-text-primary focus:border-cyan outline-none"
                            aria-label="Minimum level for this fact"
                          >
                            {FACT_LEVELS.map((lvl) => (
                              <option key={lvl} value={lvl}>
                                {lvl}
                              </option>
                            ))}
                          </select>
                          <textarea
                            value={f.text}
                            rows={2}
                            onChange={(e) => updateBriefFact(t.id, i, { text: e.target.value })}
                            className="flex-1 bg-black/30 border border-border rounded px-2 py-1 text-xs text-text-primary outline-none focus:border-cyan resize-y"
                          />
                          <button
                            onClick={() => removeBriefFact(t.id, i)}
                            className="text-text-dim hover:text-red-alert p-1 rounded transition"
                            title="Remove fact"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      ))}
                    </div>
                    {t.brief.sources.length > 0 && (
                      <div className="mt-3 text-[10px] text-text-dim">
                        Sources:{' '}
                        {t.brief.sources.map((src, i) => (
                          <a
                            key={src.url}
                            href={src.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-cyan hover:underline mr-2"
                          >
                            {src.title || `source ${i + 1}`}
                          </a>
                        ))}
                      </div>
                    )}
                  </td>
                </tr>
              )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Add Custom Topic */}
      <div className="border border-border/70 rounded-lg p-4 bg-black/20">
        <h4 className="text-xs font-mono font-semibold text-text-primary mb-3 flex items-center gap-1.5">
          <Plus size={14} className="text-cyan" /> Add Custom Topic
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
          <input
            type="text"
            placeholder="Topic Name (e.g. Clinical Trials)"
            value={newTopicName}
            onChange={(e) => setNewTopicName(e.target.value)}
            className="bg-black/30 border border-border rounded px-3 py-1.5 text-xs text-text-primary outline-none focus:border-cyan"
          />
          <input
            type="text"
            placeholder="Domain (e.g. medicine)"
            value={newTopicDomain}
            onChange={(e) => setNewTopicDomain(e.target.value)}
            className="bg-black/30 border border-border rounded px-3 py-1.5 text-xs text-text-primary outline-none focus:border-cyan"
          />
          <input
            type="text"
            placeholder="Key concepts (comma separated)"
            value={newTopicConcepts}
            onChange={(e) => setNewTopicConcepts(e.target.value)}
            className="bg-black/30 border border-border rounded px-3 py-1.5 text-xs text-text-primary outline-none focus:border-cyan"
          />
        </div>
        <button
          onClick={handleAddTopic}
          className="text-xs font-mono bg-border/40 hover:bg-border/70 text-text-primary px-3 py-1.5 rounded transition"
        >
          Add to Grid
        </button>
      </div>

      {/* Final step: run settings and launch */}
      <div className="mt-6 pt-5 border-t border-border space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-mono text-text-secondary">Max Dialogue Turns</p>
            <p className="text-[10px] text-text-dim">Fewer turns = faster results (2–20 recommended)</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onMaxTurnsChange(Math.max(2, maxTurns - 1))}
              className="w-7 h-7 panel flex items-center justify-center text-text-secondary hover:text-cyan transition-colors font-mono"
              aria-label="Fewer turns"
            >
              −
            </button>
            <span className="w-8 text-center font-mono text-cyan text-sm">{maxTurns}</span>
            <button
              onClick={() => onMaxTurnsChange(Math.min(20, maxTurns + 1))}
              className="w-7 h-7 panel flex items-center justify-center text-text-secondary hover:text-cyan transition-colors font-mono"
              aria-label="More turns"
            >
              +
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <Button variant="ghost" onClick={onBack} disabled={loading || running}>
            ← Back
          </Button>
          <div className="flex items-center gap-3">
            <Button variant="secondary" onClick={() => onRun()} disabled={loading || running || generating || researching}>
              Skip profiles &amp; run
            </Button>
            <Button
              variant="primary"
              onClick={handleConfirm}
              disabled={generating || researching || running}
              loading={loading}
              className="px-8"
            >
              {loading ? 'Compiling…' : `Confirm & run ${mode === 'multiverse' ? 'multiverse' : 'simulation'} →`}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
