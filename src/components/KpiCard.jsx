import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

function formatDelta(current, prior, isPercent = false, invertColor = false) {
  if (current == null || prior == null) return null
  const delta = current - prior
  const isPositive = invertColor ? delta < 0 : delta > 0
  const isNegative = invertColor ? delta > 0 : delta < 0
  const color = isPositive ? 'text-green' : isNegative ? 'text-red' : 'text-text-dim'
  const Icon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus
  const sign = delta > 0 ? '+' : ''
  const formatted = isPercent ? `${sign}${delta.toFixed(1)}pp` : `${sign}${Number(delta).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`

  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold ${color}`}>
      <Icon size={12} />
      {formatted}
    </span>
  )
}

export default function KpiCard({ title, value, format, subtitle, target, targetLabel, prior, invertColor = false, glow = 'teal', icon: Icon }) {
  const displayValue = value == null ? '—' : format === '$'
    ? `$${Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : format === '%'
    ? `${Number(value).toFixed(1)}%`
    : format === 'ratio'
    ? Number(value).toFixed(2)
    : Number(value).toLocaleString()

  return (
    <div className={`glow-card glow-${glow} p-5 relative overflow-hidden`}>
      {/* Subtle gradient accent */}
      <div className={`absolute top-0 right-0 w-24 h-24 rounded-full opacity-10 blur-2xl ${
        glow === 'teal' ? 'bg-teal' : glow === 'cyan' ? 'bg-cyan' : glow === 'pink' ? 'bg-pink' : glow === 'amber' ? 'bg-amber' : glow === 'red' ? 'bg-red' : 'bg-green'
      }`} />

      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-text-dim uppercase tracking-wider">{title}</span>
        {Icon && <Icon size={16} className={`text-${glow}`} />}
      </div>

      <div className="text-3xl font-extrabold text-text-bright tracking-tight">{displayValue}</div>

      {subtitle && <div className="text-xs text-text-dim mt-1">{subtitle}</div>}

      <div className="mt-3 flex items-center gap-3 flex-wrap">
        {target != null && (
          <span className="text-xs text-text-dim">
            Target: {format === '$' ? `$${target}` : format === '%' ? `${target}%` : target}
            {targetLabel ? ` ${targetLabel}` : ''}
          </span>
        )}
        {formatDelta(value, prior, format === '%', invertColor)}
      </div>
    </div>
  )
}
