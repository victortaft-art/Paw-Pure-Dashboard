import { useState } from 'react'
import { Check, X, Clock, ChevronRight, BarChart3 } from 'lucide-react'
import NoData from './components/NoData'

const priorityBadge = {
  HIGH: 'bg-red/20 text-red border-red/20',
  MEDIUM: 'bg-amber/20 text-amber border-amber/20',
  LOW: 'bg-text-dim/20 text-text-dim border-text-dim/20',
}

function daysSince(dateStr) {
  if (!dateStr) return null
  return Math.floor((new Date() - new Date(dateStr)) / 86400000)
}

function ExperimentCard({ exp, onClick }) {
  const days = daysSince(exp.start_date)
  const isActive = exp.status === 'RUNNING'
  const isCompleted = exp.status === 'KEEP' || exp.status === 'REVERT'

  return (
    <div
      onClick={() => onClick(exp)}
      className="glow-card p-4 cursor-pointer hover:border-teal/30 transition-all group"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono font-bold text-teal bg-teal/10 px-2 py-0.5 rounded">{exp.id}</span>
        <ChevronRight size={12} className="text-text-dim group-hover:text-teal transition-colors" />
      </div>
      <h4 className="text-sm font-semibold text-text-bright mb-2 leading-tight">{exp.element}</h4>
      <div className="flex flex-wrap gap-1.5">
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${priorityBadge[exp.priority] || 'bg-text-dim/20 text-text-dim border-text-dim/20'}`}>
          {exp.priority}
        </span>
      </div>
      {isActive && days != null && (
        <div className="flex items-center gap-1 text-[11px] text-teal mt-2">
          <Clock size={10} />
          <span>{days}d running</span>
          {exp.decision_date && <span className="text-text-dim">— decide {exp.decision_date}</span>}
        </div>
      )}
      {isActive && exp.baseline_cvr > 0 && exp.current_cvr > 0 && (
        <div className="mt-2 text-xs">
          <span className="text-text-dim">CVR: </span>
          <span className="font-medium text-text">{exp.baseline_cvr}%</span>
          <span className="text-text-dim mx-1">→</span>
          <span className={`font-bold ${exp.current_cvr > exp.baseline_cvr ? 'text-green' : 'text-red'}`}>
            {exp.current_cvr}%
          </span>
        </div>
      )}
      {isCompleted && (
        <div className={`mt-2 flex items-center gap-1 text-xs font-bold ${exp.status === 'KEEP' ? 'text-green' : 'text-red'}`}>
          {exp.status === 'KEEP' ? <Check size={12} /> : <X size={12} />}
          {exp.status}
        </div>
      )}
    </div>
  )
}

function DetailPanel({ exp, onClose }) {
  if (!exp) return null

  const metrics = [
    { label: 'Sessions', baseline: exp.baseline_sessions, current: exp.current_sessions },
    { label: 'CVR', baseline: exp.baseline_cvr, current: exp.current_cvr, suffix: '%' },
    { label: 'Units/day', baseline: exp.baseline_units_per_day, current: exp.current_units_per_day },
  ]

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-bg-card border border-border-dark rounded-2xl shadow-2xl max-w-lg w-full p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <span className="font-mono font-bold text-teal bg-teal/10 px-3 py-1 rounded-lg">{exp.id}</span>
          <button onClick={onClose} className="text-text-dim hover:text-text-bright p-1">
            <X size={18} />
          </button>
        </div>

        <h3 className="font-bold text-text-bright text-lg mb-3">{exp.element}</h3>

        <div className="space-y-4 text-sm">
          <div>
            <span className="text-[10px] font-bold text-teal uppercase tracking-wider">Hypothesis</span>
            <p className="text-text mt-1 leading-relaxed">{exp.hypothesis}</p>
          </div>

          {exp.data_trigger && (
            <div>
              <span className="text-[10px] font-bold text-cyan uppercase tracking-wider">Data Trigger</span>
              <p className="text-text-dim mt-1">{exp.data_trigger}</p>
            </div>
          )}

          {/* Metrics */}
          <div className="border-t border-border-dark pt-3">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] text-text-dim uppercase tracking-wider">
                  <th className="text-left py-1">Metric</th>
                  <th className="text-right py-1">Baseline</th>
                  <th className="text-right py-1">Current</th>
                  <th className="text-right py-1">Delta</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map((m, i) => {
                  const delta = (m.current || 0) - (m.baseline || 0)
                  return (
                    <tr key={i} className="border-t border-border-dark/50">
                      <td className="py-2 text-text-dim">{m.label}</td>
                      <td className="py-2 text-right text-text">{m.baseline || '—'}{m.baseline ? (m.suffix || '') : ''}</td>
                      <td className="py-2 text-right text-text-bright">{m.current || '—'}{m.current ? (m.suffix || '') : ''}</td>
                      <td className={`py-2 text-right font-bold ${delta > 0 ? 'text-green' : delta < 0 ? 'text-red' : 'text-text-dim'}`}>
                        {m.current ? `${delta > 0 ? '+' : ''}${delta.toFixed(1)}${m.suffix || ''}` : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {exp._notes && (
            <div className="bg-amber/5 border border-amber/20 rounded-xl p-3 text-xs text-amber">
              <strong>Note:</strong> {exp._notes}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default function ExperimentsTab({ data }) {
  const [selectedExp, setSelectedExp] = useState(null)
  const log = data.experimentLog

  if (!log) return <div className="glow-card p-8"><NoData message="No experiment_log.json found" /></div>

  const active = log.active_experiments || []
  const completed = log.completed_experiments || []
  // Deduplicate by experiment ID (same exp can appear in both arrays)
  const seen = new Set()
  const all = [...active, ...completed].filter(e => {
    if (seen.has(e.id)) return false
    seen.add(e.id)
    return true
  })

  const queued = all.filter(e => e.status === 'QUEUED')
  const running = all.filter(e => e.status === 'RUNNING')
  const done = all.filter(e => e.status === 'KEEP' || e.status === 'REVERT')

  const totalCompleted = done.length
  const keepCount = done.filter(e => e.status === 'KEEP').length
  const successRate = totalCompleted > 0 ? ((keepCount / totalCompleted) * 100).toFixed(0) : 0

  return (
    <div className="space-y-6">
      {/* Impact Summary — top bar */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
        {[
          { label: 'Total', value: all.length, color: 'text-text-bright' },
          { label: 'Queued', value: queued.length, color: 'text-text-dim' },
          { label: 'Running', value: running.length, color: 'text-teal' },
          { label: 'Completed', value: totalCompleted, color: 'text-green' },
          { label: 'Success Rate', value: `${successRate}%`, color: 'text-cyan' },
        ].map((stat, i) => (
          <div key={i} className="glow-card p-4 text-center">
            <div className={`text-2xl font-extrabold ${stat.color}`}>{stat.value}</div>
            <div className="text-[10px] text-text-dim uppercase tracking-wider mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Kanban Board */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* QUEUED */}
        <div>
          <div className="flex items-center gap-2 mb-3 px-1">
            <div className="w-2.5 h-2.5 rounded-full bg-text-dim" />
            <h3 className="font-bold text-text text-sm">QUEUED</h3>
            <span className="text-[10px] bg-text-dim/20 text-text-dim px-2 py-0.5 rounded-full font-bold">{queued.length}</span>
          </div>
          <div className="space-y-3">
            {queued.map(exp => <ExperimentCard key={exp.id} exp={exp} onClick={setSelectedExp} />)}
            {queued.length === 0 && <div className="glow-card p-8 text-center text-text-dim text-sm">Empty</div>}
          </div>
        </div>

        {/* RUNNING */}
        <div>
          <div className="flex items-center gap-2 mb-3 px-1">
            <div className="w-2.5 h-2.5 rounded-full bg-teal animate-pulse" />
            <h3 className="font-bold text-text text-sm">RUNNING</h3>
            <span className="text-[10px] bg-teal/20 text-teal px-2 py-0.5 rounded-full font-bold">{running.length}</span>
          </div>
          <div className="space-y-3">
            {running.map(exp => <ExperimentCard key={exp.id} exp={exp} onClick={setSelectedExp} />)}
            {running.length === 0 && <div className="glow-card p-8 text-center text-text-dim text-sm">No active experiments</div>}
          </div>
        </div>

        {/* COMPLETED */}
        <div>
          <div className="flex items-center gap-2 mb-3 px-1">
            <div className="w-2.5 h-2.5 rounded-full bg-green" />
            <h3 className="font-bold text-text text-sm">COMPLETED</h3>
            <span className="text-[10px] bg-green/20 text-green px-2 py-0.5 rounded-full font-bold">{done.length}</span>
          </div>
          <div className="space-y-3">
            {done.map(exp => <ExperimentCard key={exp.id} exp={exp} onClick={setSelectedExp} />)}
            {done.length === 0 && <div className="glow-card p-8 text-center text-text-dim text-sm">No completed experiments yet</div>}
          </div>
        </div>
      </div>

      {/* Experiment Timeline */}
      {all.length > 0 && (
        <div className="glow-card p-6">
          <h3 className="text-base font-bold text-text-bright mb-4">Experiment Timeline</h3>
          <div className="overflow-x-auto pb-2">
            <div className="flex items-center gap-2 min-w-max">
              {all.map((exp, i) => (
                <div key={exp.id} className="flex items-center">
                  <button
                    onClick={() => setSelectedExp(exp)}
                    className={`px-3 py-2 rounded-lg text-[10px] font-bold whitespace-nowrap border transition-all hover:scale-105 ${
                      exp.status === 'RUNNING' ? 'bg-teal/10 border-teal/30 text-teal' :
                      exp.status === 'KEEP' ? 'bg-green/10 border-green/30 text-green' :
                      exp.status === 'REVERT' ? 'bg-red/10 border-red/30 text-red' :
                      'bg-bg-dark border-border-dark text-text-dim'
                    }`}
                  >
                    {exp.status === 'KEEP' && <Check size={8} className="inline mr-1" />}
                    {exp.status === 'REVERT' && <X size={8} className="inline mr-1" />}
                    {exp.status === 'RUNNING' && <Clock size={8} className="inline mr-1" />}
                    {exp.id}
                  </button>
                  {i < all.length - 1 && <div className="w-4 h-px bg-border-dark mx-1" />}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Detail Panel */}
      {selectedExp && <DetailPanel exp={selectedExp} onClose={() => setSelectedExp(null)} />}
    </div>
  )
}
