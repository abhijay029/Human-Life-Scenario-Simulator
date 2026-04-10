'use client'
import { clsx } from 'clsx'
import { ReactNode } from 'react'

// ── Panel ──────────────────────────────────────────────────────────────────
export function Panel({
  children,
  className,
  label,
}: {
  children: ReactNode
  className?: string
  label?: string
}) {
  return (
    <div className={clsx('relative panel', className)}>
      {label && (
        <div className="absolute -top-px left-4 px-2 bg-void text-[10px] font-mono text-text-secondary tracking-[0.2em] uppercase transform -translate-y-1/2">
          {label}
        </div>
      )}
      {children}
    </div>
  )
}

// ── Button ─────────────────────────────────────────────────────────────────
export function Button({
  children,
  onClick,
  variant = 'primary',
  disabled,
  loading,
  className,
  type = 'button',
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  disabled?: boolean
  loading?: boolean
  className?: string
  type?: 'button' | 'submit'
}) {
  const base = 'inline-flex items-center gap-2 px-4 py-2 font-mono text-sm tracking-wide transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed'
  const variants = {
    primary: 'bg-cyan text-void font-bold hover:shadow-cyan-glow hover:scale-[1.02] active:scale-[0.98]',
    secondary: 'border border-cyan/30 text-cyan hover:border-cyan/60 hover:bg-cyan-glow',
    ghost: 'text-text-secondary hover:text-text-primary hover:bg-white/5',
    danger: 'border border-red-alert/30 text-red-alert hover:border-red-alert/60 hover:bg-red-alert/10',
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={clsx(base, variants[variant], className)}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  )
}

// ── Input ──────────────────────────────────────────────────────────────────
export function Input({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  className,
}: {
  label?: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  type?: string
  className?: string
}) {
  return (
    <div className={clsx('flex flex-col gap-1.5', className)}>
      {label && (
        <label className="text-[10px] font-mono text-text-secondary tracking-[0.15em] uppercase">
          {label}
        </label>
      )}
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-void border border-border rounded px-3 py-2 text-sm text-text-primary font-body placeholder:text-text-dim focus:outline-none focus:border-cyan/50 focus:shadow-[0_0_12px_rgba(0,229,255,0.1)] transition-all"
      />
    </div>
  )
}

// ── Textarea ───────────────────────────────────────────────────────────────
export function Textarea({
  label,
  value,
  onChange,
  placeholder,
  rows = 3,
  className,
}: {
  label?: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  rows?: number
  className?: string
}) {
  return (
    <div className={clsx('flex flex-col gap-1.5', className)}>
      {label && (
        <label className="text-[10px] font-mono text-text-secondary tracking-[0.15em] uppercase">
          {label}
        </label>
      )}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="bg-void border border-border rounded px-3 py-2 text-sm text-text-primary font-body placeholder:text-text-dim focus:outline-none focus:border-cyan/50 focus:shadow-[0_0_12px_rgba(0,229,255,0.1)] transition-all resize-none"
      />
    </div>
  )
}

// ── Badge ──────────────────────────────────────────────────────────────────
export function Badge({
  children,
  variant = 'default',
}: {
  children: ReactNode
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'cyan'
}) {
  const variants = {
    default: 'bg-border text-text-secondary',
    success: 'bg-green-good/10 text-green-good border border-green-good/20',
    warning: 'bg-amber-sim/10 text-amber-sim border border-amber-sim/20',
    danger: 'bg-red-alert/10 text-red-alert border border-red-alert/20',
    cyan: 'bg-cyan/10 text-cyan border border-cyan/20',
  }
  return (
    <span className={clsx('inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono tracking-wider uppercase', variants[variant])}>
      {children}
    </span>
  )
}

// ── Tag ────────────────────────────────────────────────────────────────────
export function Tag({ label, onRemove }: { label: string; onRemove?: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 px-2 py-1 bg-border rounded text-xs font-mono text-text-secondary">
      {label}
      {onRemove && (
        <button
          onClick={onRemove}
          className="ml-1 text-text-dim hover:text-red-alert transition-colors"
        >
          ×
        </button>
      )}
    </span>
  )
}

// ── TagInput ───────────────────────────────────────────────────────────────
export function TagInput({
  label,
  tags,
  onChange,
  placeholder,
}: {
  label: string
  tags: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
}) {
  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      const val = (e.target as HTMLInputElement).value.trim()
      if (val && !tags.includes(val)) {
        onChange([...tags, val])
        ;(e.target as HTMLInputElement).value = ''
      }
    }
  }
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-[10px] font-mono text-text-secondary tracking-[0.15em] uppercase">
        {label}
      </label>
      <div className="min-h-[42px] bg-void border border-border rounded px-3 py-2 flex flex-wrap gap-1.5 focus-within:border-cyan/50 transition-all">
        {tags.map((t, i) => (
          <Tag key={i} label={t} onRemove={() => onChange(tags.filter((_, j) => j !== i))} />
        ))}
        <input
          onKeyDown={handleKey}
          placeholder={tags.length === 0 ? placeholder : '+ add…'}
          className="flex-1 min-w-[80px] bg-transparent text-sm text-text-primary placeholder:text-text-dim focus:outline-none font-body"
        />
      </div>
      <p className="text-[10px] text-text-dim">Press Enter or comma to add</p>
    </div>
  )
}

// ── Spinner ────────────────────────────────────────────────────────────────
export function Spinner({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = { sm: 'w-3 h-3', md: 'w-5 h-5', lg: 'w-8 h-8' }
  return (
    <span className={clsx('border-2 border-cyan/20 border-t-cyan rounded-full animate-spin inline-block', sizes[size])} />
  )
}

// ── Divider ────────────────────────────────────────────────────────────────
export function Divider({ label }: { label?: string }) {
  if (!label) return <div className="border-t border-border my-4" />
  return (
    <div className="flex items-center gap-3 my-4">
      <div className="flex-1 border-t border-border" />
      <span className="text-[10px] font-mono text-text-dim tracking-[0.2em] uppercase">{label}</span>
      <div className="flex-1 border-t border-border" />
    </div>
  )
}

// ── Progress bar ───────────────────────────────────────────────────────────
export function ProgressBar({
  value,
  max = 1,
  color = 'cyan',
}: {
  value: number
  max?: number
  color?: 'cyan' | 'green' | 'amber' | 'red'
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const colors = {
    cyan: 'bg-cyan',
    green: 'bg-green-good',
    amber: 'bg-amber-sim',
    red: 'bg-red-alert',
  }
  const colorForValue = value >= 0.65 ? 'green' : value >= 0.35 ? 'amber' : 'red'
  const barColor = color === 'cyan' ? 'cyan' : colorForValue
  return (
    <div className="h-1.5 bg-border rounded-full overflow-hidden">
      <div
        className={clsx('h-full rounded-full transition-all duration-700', colors[barColor])}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}
