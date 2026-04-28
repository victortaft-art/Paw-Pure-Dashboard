import { useState, useMemo } from 'react'
import { X, ChevronDown, ChevronRight, Target, TrendingUp, Calendar, Lightbulb, Play, Clock, Activity, AlertTriangle, CircleCheck } from 'lucide-react'
import NoData from './components/NoData'

const priorityBadge = {
  CRITICAL: 'bg-red/30 text-red border-red/30',
  HIGH:     'bg-amber/20 text-amber border-amber/20',
  MEDIUM:   'bg-cyan/20 text-cyan border-cyan/20',
  LOW:      'bg-text-dim/20 text-text-dim border-text-dim/20',
}

const listingMeta = {
  fountain: { label: 'Fountain', color: 'text-teal',     bg: 'bg-teal/10',     border: 'border-teal/20',     icon: '🐾' },
  bundle:   { label: 'Bundle',   color: 'text-amber',    bg: 'bg-amber/10',    border: 'border-amber/20',    icon: '📦' },
  filters:  { label: 'Filters',  color: 'text-cyan',     bg: 'bg-cyan/10',     border: 'border-cyan/20',     icon: '🔄' },
  ppc:      { label: 'PPC',      color: 'text-pink',     bg: 'bg-pink/10',     border: 'border-pink/20',     icon: '📢' },
  ops:      { label: 'Ops',      color: 'text-text-dim', bg: 'bg-text-dim/10', border: 'border-text-dim/20', icon: '⚙️' },
  brand:    { label: 'Brand',    color: 'text-green',    bg: 'bg-green/10',    border: 'border-green/20',    icon: '⭐' },
}

const statusColors = {
  TODO:     'bg-amber/20 text-amber border-amber/20',
  RUNNING:  'bg-teal/20 text-teal border-teal/30',
  DECISION: 'bg-pink/20 text-pink border-pink/30',
  QUEUED:   'bg-text-dim/20 text-text-dim border-text-dim/20',
  DONE:     'bg-green/20 text-green border-green/30',
}

function ListingBadge({ listing }) {
  const m = listingMeta[listing] || listingMeta.fountain
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-bold border ${m.bg} ${m.border} ${m.color}`}>
      <span>{m.icon}</span>{m.label}
    </span>
  )
}

/* ─── Variance bar: shows progress from baseline → current → target ─── */
function VarianceBar({ baseline, current, target, direction, unit }) {
  if (baseline == null || target == null) return null
  const min = Math.min(baseline, target)
  const max = Math.max(baseline, target)
  const range = max - min || 1
  const cur = current == null ? null : current
  const pct = cur == null ? 0 : Math.max(0, Math.min(100, ((cur - min) / range) * 100))
  const onTrack = direction === 'down'
    ? (cur != null && cur <= baseline)
    : direction === 'up'
      ? (cur != null && cur >= baseline)
      : null

  const fmt = (v) => v == null ? '—' : `${v}${unit || ''}`

  return (
    <div className="mt-2">
      <div className="relative h-2 bg-bg-dark rounded-full overflow-hidden border border-border-dark">
        {/* Baseline marker */}
        <div className="absolute top-0 bottom-0 w-0.5 bg-text-dim" style={{ left: direction === 'down' ? '100%' : '0%' }} />
        {/* Target marker */}
        <div className="absolute top-0 bottom-0 w-0.5 bg-green" style={{ left: direction === 'down' ? '0%' : '100%' }} />
        {/* Current fill */}
        {cur != null && (
          <div
            className={`absolute top-0 bottom-0 ${onTrack ? 'bg-teal/60' : 'bg-amber/60'}`}
            style={{ width: `${pct}%`, left: 0 }}
          />
        )}
      </div>
      <div className="flex items-center justify-between text-[9px] text-text-dim mt-1">
        <span>baseline {fmt(baseline)}</span>
        <span className={cur == null ? 'text-text-dim' : onTrack ? 'text-teal font-bold' : 'text-amber font-bold'}>
          {cur == null ? 'awaiting data' : `current ${fmt(cur)}`}
        </span>
        <span className="text-green">target {fmt(target)}</span>
      </div>
    </div>
  )
}

/* ─── SECTION 1: Weekly Strategy ─── */
function WeeklyStrategySection({ weeks, onExpClick, backlogIndex }) {
  if (!weeks || weeks.length === 0) return null
  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <Target size={16} className="text-teal" />
        <h2 className="text-base font-bold text-text-bright">Weekly Strategy</h2>
        <span className="text-[10px] text-text-dim">Each week targets one growth metric. Variance vs target is tracked.</span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {weeks.map((w, i) => {
          const isCurrent = w.is_current
          const m = w.target_metric || {}
          return (
            <div
              key={i}
              className={`rounded-2xl border p-5 ${
                isCurrent
                  ? 'border-teal/40 bg-teal/5 shadow-[0_0_25px_rgba(20,184,166,0.08)]'
                  : 'border-border-dark bg-bg-card'
              }`}
            >
              {/* Header */}
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                <Calendar size={12} className={isCurrent ? 'text-teal' : 'text-text-dim'} />
                <span className={`text-[10px] font-bold uppercase tracking-widest ${isCurrent ? 'text-teal' : 'text-text-dim'}`}>
                  {isCurrent ? 'This Week' : w.week_label?.split('—')[0]?.trim() || `Week ${i + 1}`}
                </span>
                {isCurrent && <span className="text-[9px] font-bold bg-teal/20 text-teal px-1.5 py-0.5 rounded">ACTIVE</span>}
              </div>
              <div className="text-[11px] text-text-dim mb-3">{w.week_start} → {w.week_end}</div>

              {/* Target metric */}
              <div className="bg-bg-dark border border-border-dark rounded-xl p-3 mb-3">
                <div className="text-[9px] font-bold text-text-dim uppercase tracking-wider mb-1">Target Metric</div>
                <div className="text-sm font-bold text-text-bright leading-tight">{m.name}</div>
                <div className="flex items-center gap-2 mt-2 text-[11px]">
                  <span className="text-text-dim">{m.baseline}</span>
                  <ChevronRight size={10} className="text-text-dim" />
                  <span className="text-green font-bold">{m.target}</span>
                </div>
              </div>

              {/* Growth lever */}
              <div className="flex items-center gap-1.5 mb-3">
                <TrendingUp size={11} className="text-cyan" />
                <span className="text-[10px] font-bold text-cyan uppercase tracking-wider">{w.growth_lever}</span>
              </div>

              {/* Thesis */}
              <p className="text-[11px] text-text-dim leading-relaxed mb-3">{w.thesis}</p>

              {/* Experiments */}
              <div className="border-t border-border-dark pt-3 space-y-1.5">
                <div className="text-[9px] font-bold text-text-dim uppercase tracking-wider mb-1.5">Experiments ({w.experiments?.length || 0})</div>
                {(w.experiments || []).map((e, j) => {
                  const full = backlogIndex[e.id]
                  return (
                    <button
                      key={j}
                      onClick={() => full && onExpClick(full)}
                      className="w-full text-left flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-bg-dark transition-colors group"
                      disabled={!full}
                    >
                      <span className="text-[9px] font-mono font-bold text-teal bg-teal/10 px-1.5 py-0.5 rounded shrink-0">
                        {e.id}
                      </span>
                      <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded border shrink-0 ${statusColors[e.status] || statusColors.QUEUED}`}>
                        {e.status}
                      </span>
                      <span className="text-[11px] text-text flex-1 truncate group-hover:text-text-bright">{e.title}</span>
                      <span className="text-[9px] text-text-dim shrink-0">{e.scheduled_date?.slice(5)}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ─── SECTION 2: Tracking ─── */
function TrackingSection({ tracking, onExpClick, backlogIndex }) {
  if (!tracking || tracking.length === 0) return null
  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <Activity size={16} className="text-pink" />
        <h2 className="text-base font-bold text-text-bright">Tracking</h2>
        <span className="text-[10px] text-text-dim">Running experiments — expected vs actual. Learnings feed backlog reviews.</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {tracking.map((t) => {
          const full = backlogIndex[t.id]
          const decisionSoon = t.days_until_decision != null && t.days_until_decision <= 3
          return (
            <div
              key={t.id}
              onClick={() => full && onExpClick(full)}
              className={`rounded-2xl border p-4 cursor-pointer hover:border-teal/30 transition-colors ${
                decisionSoon ? 'border-pink/30 bg-pink/5' : 'border-border-dark bg-bg-card'
              }`}
            >
              <div className="flex items-center gap-2 mb-2 flex-wrap">
                <span className="text-[10px] font-mono font-bold text-teal bg-teal/10 px-2 py-0.5 rounded">{t.id}</span>
                <span className="text-[9px] font-bold bg-teal/20 text-teal px-1.5 py-0.5 rounded">RUNNING</span>
                <span className="text-[9px] text-text-dim ml-auto flex items-center gap-1">
                  <Clock size={9} /> Day {t.days_running} · decide in {t.days_until_decision}d
                </span>
              </div>
              <h3 className="text-sm font-bold text-text-bright mb-3 leading-tight">{t.title}</h3>

              {/* Metric variance */}
              <div className="bg-bg-dark border border-border-dark rounded-xl p-3 mb-3">
                <div className="text-[9px] font-bold text-text-dim uppercase tracking-wider mb-1">{t.target_metric}</div>
                <VarianceBar
                  baseline={t.baseline_value}
                  current={t.current_value}
                  target={t.target_value}
                  direction={t.direction}
                  unit={t.unit === '%' ? '%' : t.unit ? ` ${t.unit}` : ''}
                />
                {t.current_value_label && (
                  <div className="text-[10px] text-text-dim mt-1.5 italic">{t.current_value_label}</div>
                )}
              </div>

              {/* Expected vs actual */}
              <div className="space-y-2 text-[11px]">
                <div>
                  <span className="text-[9px] font-bold text-green uppercase tracking-wider">Expected</span>
                  <p className="text-text leading-snug mt-0.5">{t.expected}</p>
                </div>
                <div>
                  <span className="text-[9px] font-bold text-amber uppercase tracking-wider">Actual</span>
                  <p className="text-text leading-snug mt-0.5">{t.actual}</p>
                </div>
                {t.learning && (
                  <div className="pt-2 border-t border-border-dark/50">
                    <span className="text-[9px] font-bold text-cyan uppercase tracking-wider flex items-center gap-1">
                      <Lightbulb size={9} /> Learning
                    </span>
                    <p className="text-text-dim italic leading-snug mt-0.5">{t.learning}</p>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ─── SECTION 3: Backlog ─── */
function BacklogSection({ backlog, onExpClick }) {
  const [filter, setFilter] = useState('all')
  if (!backlog || backlog.length === 0) return null

  const listingCounts = {}
  backlog.forEach(b => { if (b.listing) listingCounts[b.listing] = (listingCounts[b.listing] || 0) + 1 })
  const filterOpts = [
    { key: 'all', label: 'All', icon: '🗂', count: backlog.length },
    ...Object.entries(listingMeta)
      .filter(([key]) => listingCounts[key])
      .map(([key, m]) => ({ key, label: m.label, icon: m.icon, count: listingCounts[key] })),
  ]

  const filtered = filter === 'all' ? backlog : backlog.filter(b => b.listing === filter)

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <Play size={16} className="text-cyan" />
        <h2 className="text-base font-bold text-text-bright">Backlog</h2>
        <span className="text-[10px] text-text-dim">Click any row to see step-by-step execution.</span>
        <span className="text-[10px] text-text-dim ml-auto">{filtered.length} items</span>
      </div>

      <div className="flex flex-wrap gap-2 mb-3">
        {filterOpts.map(opt => (
          <button
            key={opt.key}
            onClick={() => setFilter(opt.key)}
            className={`flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold border transition-all ${
              filter === opt.key
                ? 'bg-teal/20 text-teal border-teal/40'
                : 'bg-bg-dark text-text-dim border-border-dark hover:text-text'
            }`}
          >
            <span>{opt.icon}</span>
            <span>{opt.label}</span>
            <span className="opacity-60 text-[10px]">({opt.count})</span>
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {filtered.map((b) => (
          <button
            key={b.id}
            onClick={() => onExpClick(b)}
            className="w-full text-left bg-bg-card border border-border-dark rounded-xl p-4 hover:border-teal/30 transition-colors group"
          >
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className="text-[10px] font-mono font-bold text-teal bg-teal/10 px-2 py-0.5 rounded">{b.id}</span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${priorityBadge[b.priority] || priorityBadge.MEDIUM}`}>
                {b.priority}
              </span>
              {b.listing && <ListingBadge listing={b.listing} />}
              {b.growth_metric && (
                <span className="text-[9px] font-bold text-cyan bg-cyan/10 border border-cyan/20 px-1.5 py-0.5 rounded">
                  {b.growth_metric}
                </span>
              )}
              <span className="text-[9px] text-text-dim ml-auto flex items-center gap-1">
                <Calendar size={9} /> {b.scheduled_date}
              </span>
              <ChevronRight size={12} className="text-text-dim group-hover:text-teal transition-colors" />
            </div>
            <h3 className="text-sm font-bold text-text-bright mb-2 leading-tight">{b.title}</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px]">
              <div>
                <div className="text-[9px] font-bold text-text-dim uppercase tracking-wider mb-0.5">Assumption</div>
                <p className="text-text leading-snug line-clamp-3">{b.assumption}</p>
              </div>
              <div>
                <div className="text-[9px] font-bold text-cyan uppercase tracking-wider mb-0.5">Why</div>
                <p className="text-text-dim leading-snug line-clamp-3">{b.rationale}</p>
              </div>
              <div>
                <div className="text-[9px] font-bold text-green uppercase tracking-wider mb-0.5">Expected Change</div>
                <p className="text-green/90 leading-snug line-clamp-3">{b.expected_change}</p>
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

/* ─── Detail Panel: full execution steps on click ─── */
function DetailPanel({ exp, onClose }) {
  if (!exp) return null
  const m = listingMeta[exp.listing] || listingMeta.fountain

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-start justify-center z-50 p-4 pt-8 overflow-y-auto" onClick={onClose}>
      <div className="bg-bg-card border border-border-dark rounded-2xl shadow-2xl max-w-2xl w-full my-4" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-6 pb-0">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-mono font-bold text-teal bg-teal/10 px-3 py-1 rounded-lg text-sm">{exp.id}</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${priorityBadge[exp.priority] || priorityBadge.MEDIUM}`}>
              {exp.priority}
            </span>
            {exp.listing && <ListingBadge listing={exp.listing} />}
            {exp.growth_metric && (
              <span className="text-[9px] font-bold text-cyan bg-cyan/10 border border-cyan/20 px-1.5 py-0.5 rounded">
                {exp.growth_metric}
              </span>
            )}
          </div>
          <button onClick={onClose} className="text-text-dim hover:text-text-bright p-1 rounded-lg hover:bg-bg-dark">
            <X size={18} />
          </button>
        </div>

        <div className="p-6 space-y-5">
          <h3 className="font-bold text-text-bright text-lg leading-tight">{exp.title}</h3>

          {/* Schedule */}
          <div className={`rounded-xl border p-3 flex items-center gap-3 flex-wrap ${m.bg} ${m.border}`}>
            <Calendar size={14} className={m.color} />
            <span className={`text-xs font-bold ${m.color}`}>Scheduled {exp.scheduled_date}</span>
          </div>

          {/* Why */}
          {exp.rationale && (
            <div className="bg-teal/5 border border-teal/15 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Lightbulb size={14} className="text-teal" />
                <span className="text-[10px] font-bold text-teal uppercase tracking-wider">Why</span>
              </div>
              <p className="text-text text-sm leading-relaxed">{exp.rationale}</p>
            </div>
          )}

          {/* Assumption */}
          {exp.assumption && (
            <div>
              <span className="text-[10px] font-bold text-text-dim uppercase tracking-wider">Assumption</span>
              <p className="text-text text-sm mt-1 leading-relaxed">{exp.assumption}</p>
            </div>
          )}

          {/* Expected change */}
          {exp.expected_change && (
            <div className="bg-green/5 border border-green/15 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <TrendingUp size={14} className="text-green" />
                <span className="text-[10px] font-bold text-green uppercase tracking-wider">Expected Change</span>
              </div>
              <p className="text-text text-sm leading-relaxed">{exp.expected_change}</p>
            </div>
          )}

          {/* Execution steps */}
          {exp.execution_steps && exp.execution_steps.length > 0 && (
            <div className="border-t border-border-dark pt-4">
              <div className="flex items-center gap-2 mb-3">
                <Play size={14} className="text-teal" />
                <span className="text-xs font-bold text-teal uppercase tracking-wider">
                  Step-by-Step ({exp.execution_steps.length} steps)
                </span>
              </div>
              <ol className="space-y-2">
                {exp.execution_steps.map((step, i) => (
                  <li key={i} className="flex gap-3 text-sm">
                    <span className="shrink-0 w-6 h-6 rounded-full bg-teal/10 border border-teal/20 text-teal text-[11px] font-bold flex items-center justify-center">
                      {i + 1}
                    </span>
                    <span className="text-text leading-relaxed pt-0.5 whitespace-pre-wrap">{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Main Tab ─── */
export default function ExperimentsTab({ data }) {
  const [selectedExp, setSelectedExp] = useState(null)
  const tracker = data.activeTracker

  if (!tracker || !tracker.weekly_strategy) {
    return (
      <div className="glow-card p-8">
        <NoData message="No active_tracker.json found or schema is outdated. Expected v2.0 schema with weekly_strategy / tracking / backlog sections." />
      </div>
    )
  }

  // Build an index of backlog entries by id so weekly_strategy and tracking
  // entries can resolve full details on click.
  const backlogIndex = useMemo(() => {
    const idx = {}
    ;(tracker.backlog || []).forEach(b => { idx[b.id] = b })
    return idx
  }, [tracker.backlog])

  const freshness = tracker.data_freshness

  return (
    <div className="space-y-8">
      {/* Top meta row */}
      <div className="flex items-center gap-3 flex-wrap text-[10px] text-text-dim">
        <span className="font-bold uppercase tracking-widest text-text-dim">Generated {tracker.generated}</span>
        {freshness && (
          <>
            <span className="opacity-50">•</span>
            <span>Ads API: {freshness.ads_api}</span>
            <span className="opacity-50">•</span>
            <span>SP Finances: {freshness.sp_finances}</span>
          </>
        )}
      </div>

      <WeeklyStrategySection
        weeks={tracker.weekly_strategy}
        onExpClick={setSelectedExp}
        backlogIndex={backlogIndex}
      />

      <TrackingSection
        tracking={tracker.tracking}
        onExpClick={setSelectedExp}
        backlogIndex={backlogIndex}
      />

      <BacklogSection
        backlog={tracker.backlog}
        onExpClick={setSelectedExp}
      />

      {selectedExp && (
        <DetailPanel
          exp={selectedExp}
          onClose={() => setSelectedExp(null)}
        />
      )}
    </div>
  )
}
