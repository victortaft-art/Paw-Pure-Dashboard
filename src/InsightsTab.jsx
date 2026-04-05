import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Target, MessageSquare, Megaphone, Image, Zap, Eye, ShoppingCart, MousePointer, DollarSign, Star, AlertTriangle } from 'lucide-react'
import KpiCard from './components/KpiCard'
import NoData from './components/NoData'

const priorityColors = { CRITICAL: 'bg-red text-white', HIGH: 'bg-amber text-bg-dark', MEDIUM: 'bg-cyan/20 text-cyan', LOW: 'bg-text-dim/20 text-text-dim' }

// Extract metrics from both old and new SC_Data formats
function extractMetrics(sc) {
  if (!sc) return {}
  const br = sc.business_reports || sc.businessReports
  const cm = sc.campaign_manager || sc.campaignSummary

  let sessions = 0, cvr = null, units = 0
  if (br?.asins) {
    Object.values(br.asins).forEach(a => {
      sessions += a.sessions || 0
      units += a.units_ordered || 0
    })
    cvr = sessions > 0 ? ((units / sessions) * 100) : 0
  }
  if (br?.period_7d) {
    sessions = br.period_7d.sessions || sessions
    units = br.period_7d.unitsOrdered || units
    cvr = br.period_7d.unitSessionPercentage ?? cvr
  }

  let acos = null, adSpend = 0
  if (cm?.campaigns_total) {
    acos = cm.campaigns_total.acos_pct
    adSpend = cm.campaigns_total.spend || 0
  } else if (cm) {
    acos = cm.overallACoS_percent_7d ?? cm.allTime?.acos_percent
    adSpend = cm.totalSpend_7d_estimated || 0
  }

  return { sessions, cvr, units, acos, adSpend }
}

export default function InsightsTab({ data }) {
  const sc = data.sc?.current
  const priorSc = data.sc?.prior
  const ci = data.ci?.current
  const voc = data.voc?.current
  const ppc = data.ppc?.current
  const copyData = data.copy?.current

  const curr = extractMetrics(sc)
  const prior = extractMetrics(priorSc)

  const wastedSpend = ppc?.summary?.wasted_spend ?? null

  // PPC action plan — new format has rank/action/recommended_change
  const actionPlan = ppc?.action_plan || sc?.diagnosis?.urgentActions?.map((a, i) => ({
    priority: i === 0 ? 'CRITICAL' : i < 3 ? 'HIGH' : 'MEDIUM',
    action: a,
  })) || []

  // One-action-this-week highlight
  const oneAction = ppc?.one_action_this_week

  // VoC themes — handle both object format {theme: count} and array format
  function getThemes(themes, limit = 5) {
    if (!themes) return []
    if (Array.isArray(themes)) return themes.slice(0, limit).map(t => typeof t === 'string' ? { name: t, count: null } : { name: t.theme || t.name, count: t.count })
    // Object format: { quiet_operation: 3, ... }
    return Object.entries(themes).slice(0, limit).map(([name, count]) => ({
      name: name.replace(/_/g, ' '),
      count
    }))
  }

  const positiveThemes = getThemes(voc?.paw_pure?.positive_themes || voc?.positive_themes)
  const negativeThemes = getThemes(voc?.paw_pure?.negative_themes || voc?.negative_themes)

  // Copy angles from VoC
  const copyAngles = voc?.copy_angles || voc?.paw_pure?.copy_language || []

  // WoW data
  const wowData = []
  if (curr.sessions) {
    wowData.push(
      { metric: 'Sessions', current: curr.sessions, prior: prior.sessions || 0 },
      { metric: 'Units', current: curr.units, prior: prior.units || 0 },
    )
  }

  // Competitor average
  const compAvgPrice = ci?.competitors ? (ci.competitors.reduce((s, c) => s + c.price, 0) / ci.competitors.length) : null
  const compAvgReviews = ci?.competitors ? Math.round(ci.competitors.reduce((s, c) => s + c.reviews, 0) / ci.competitors.length) : null

  return (
    <div className="space-y-6">
      {/* One Action This Week — hero callout */}
      {oneAction && (
        <div className="glow-card glow-amber p-5">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={16} className="text-amber" />
            <span className="text-sm font-bold text-amber uppercase tracking-wide">This Week's #1 Action</span>
            {oneAction.expected_weekly_savings > 0 && (
              <span className="ml-auto text-xs font-bold text-green bg-green/10 px-2 py-0.5 rounded">Save ${oneAction.expected_weekly_savings}/week</span>
            )}
          </div>
          <p className="text-sm text-text-bright font-medium">{oneAction.action}</p>
          <p className="text-xs text-text-dim mt-1">{oneAction.rationale}</p>
        </div>
      )}

      {/* KPI Scorecard */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard title="Sessions" value={curr.sessions || null} format="num" target={100} prior={prior.sessions} glow="cyan" icon={Eye} />
        <KpiCard title="CVR" value={curr.cvr} format="%" target={8} prior={prior.cvr} glow={curr.cvr >= 8 ? 'green' : 'amber'} icon={MousePointer} />
        <KpiCard title="Units Sold" value={curr.units || null} format="num" prior={prior.units} glow="teal" icon={ShoppingCart} />
        <KpiCard title="ACoS" value={curr.acos} format="%" target={25} invertColor prior={prior.acos} glow="red" icon={Target} />
        <KpiCard title="Wasted Spend" value={wastedSpend} format="$" glow="pink" icon={DollarSign} />
        <KpiCard title="Reviews" value={voc?.paw_pure?.total_ratings ?? ci?.pawPure?.reviews ?? 20} format="num" glow="amber" icon={Star} />
      </div>

      {/* Two-column: CI + VoC */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Competitive Intel */}
        <div className="glow-card glow-cyan p-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 bg-cyan-glow rounded-lg flex items-center justify-center">
              <Target size={14} className="text-cyan" />
            </div>
            <h3 className="text-base font-bold text-text-bright">Competitive Intel</h3>
          </div>
          {ci?.keyFindings ? (
            <>
              <ul className="space-y-2.5 text-sm">
                {ci.keyFindings.slice(0, 5).map((f, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan mt-2 flex-shrink-0" />
                    <span className="text-text">{f}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-5 pt-4 border-t border-border-dark grid grid-cols-2 gap-4">
                <div className="glow-card p-3 text-center">
                  <div className="text-lg font-bold text-teal">${ci.pawPure?.price || 49.99}</div>
                  <div className="text-[10px] text-text-dim">Our Price</div>
                </div>
                <div className="glow-card p-3 text-center">
                  <div className="text-lg font-bold text-text-bright">${compAvgPrice?.toFixed(2) || '—'}</div>
                  <div className="text-[10px] text-text-dim">Avg Competitor</div>
                </div>
                <div className="glow-card p-3 text-center">
                  <div className="text-lg font-bold text-red">{ci.pawPure?.reviews || voc?.paw_pure?.total_ratings || 20}</div>
                  <div className="text-[10px] text-text-dim">Our Reviews</div>
                </div>
                <div className="glow-card p-3 text-center">
                  <div className="text-lg font-bold text-text-bright">{compAvgReviews?.toLocaleString() || '—'}</div>
                  <div className="text-[10px] text-text-dim">Avg Competitor</div>
                </div>
              </div>
            </>
          ) : <NoData />}
        </div>

        {/* Voice of Customer */}
        <div className="glow-card glow-pink p-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-7 h-7 bg-pink-glow rounded-lg flex items-center justify-center">
              <MessageSquare size={14} className="text-pink" />
            </div>
            <h3 className="text-base font-bold text-text-bright">Voice of Customer</h3>
            {voc?.paw_pure && <span className="ml-auto text-xs text-text-dim">{voc.paw_pure.total_reviews_scraped} reviews scraped</span>}
          </div>
          {voc ? (
            <div className="space-y-4">
              <div>
                <span className="text-[10px] font-semibold text-green uppercase tracking-wide">Positive Themes</span>
                <div className="flex flex-wrap gap-2 mt-2">
                  {positiveThemes.length > 0 ? positiveThemes.map((t, i) => (
                    <span key={i} className="px-3 py-1.5 bg-green-glow border border-green/20 text-green text-xs rounded-lg font-medium">
                      {t.name} {t.count ? <span className="opacity-60">({t.count})</span> : ''}
                    </span>
                  )) : <span className="text-text-dim text-sm">No data</span>}
                </div>
              </div>
              <div>
                <span className="text-[10px] font-semibold text-red uppercase tracking-wide">Negative Themes</span>
                <div className="flex flex-wrap gap-2 mt-2">
                  {negativeThemes.length > 0 ? negativeThemes.map((t, i) => (
                    <span key={i} className="px-3 py-1.5 bg-red-glow border border-red/20 text-red text-xs rounded-lg font-medium">
                      {t.name} {t.count ? <span className="opacity-60">({t.count})</span> : ''}
                    </span>
                  )) : <span className="text-text-dim text-sm">No data</span>}
                </div>
              </div>
              {/* Top copy angle */}
              {copyAngles.length > 0 && (
                <div className="border-t border-border-dark pt-3">
                  <span className="text-[10px] font-semibold text-amber uppercase tracking-wide">Top Customer Quotes for Copy</span>
                  <div className="mt-2 space-y-2">
                    {copyAngles.slice(0, 3).map((a, i) => (
                      <div key={i} className="p-2 bg-bg-dark/50 rounded-lg text-xs">
                        <span className="text-text-bright italic">"{a.quote}"</span>
                        <span className="block text-text-dim mt-0.5">→ {a.placement || a.angle}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : <NoData message="Run the review scraper agent first" />}
        </div>
      </div>

      {/* PPC Action Plan */}
      <div className="glow-card glow-amber p-6">
        <div className="flex items-center gap-2 mb-4">
          <div className="w-7 h-7 bg-amber-glow rounded-lg flex items-center justify-center">
            <Megaphone size={14} className="text-amber" />
          </div>
          <h3 className="text-base font-bold text-text-bright">PPC Action Plan</h3>
          {ppc?.summary && (
            <span className="ml-auto text-xs text-text-dim">
              Spend: ${ppc.summary.total_spend} | Sales: ${ppc.summary.total_sales} | Wasted: {ppc.summary.wasted_spend_pct}%
            </span>
          )}
        </div>
        {actionPlan.length > 0 ? (
          <div className="space-y-3">
            {actionPlan.slice(0, 7).map((action, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-bg-dark/50 rounded-xl border border-border-dark/50">
                <span className="flex-shrink-0 w-7 h-7 bg-teal/20 text-teal rounded-lg flex items-center justify-center text-xs font-bold">{action.rank || i + 1}</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${priorityColors[action.priority] || 'bg-text-dim/20 text-text-dim'}`}>
                      {action.priority || 'HIGH'}
                    </span>
                    {action.keyword && <span className="text-[10px] text-cyan font-mono">{action.keyword}</span>}
                    {action.expected_weekly_savings > 0 && <span className="text-[10px] text-green font-medium ml-auto">Save ${action.expected_weekly_savings}/wk</span>}
                  </div>
                  <p className="text-sm text-text">{action.recommended_change || action.action || action.description || (typeof action === 'string' ? action : '')}</p>
                  {action.rationale && <p className="text-xs text-text-dim mt-1">{action.rationale}</p>}
                </div>
              </div>
            ))}
          </div>
        ) : <NoData message="No PPC analysis data yet" />}
      </div>

      {/* Listing Changes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glow-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Zap size={16} className="text-teal" />
            <h3 className="text-base font-bold text-text-bright">Copy Changes</h3>
          </div>
          {copyData?.variants || copyData?.keyword_priority_list ? (
            <div className="space-y-2 text-sm">
              {(copyData.variants || []).slice(0, 3).map((v, i) => (
                <div key={i} className="p-3 bg-bg-dark/50 rounded-lg border border-border-dark/50">
                  <div className="font-medium text-text-bright">{v.element || v.name}</div>
                  <div className="text-xs text-text-dim mt-1">{v.description || v.hypothesis}</div>
                </div>
              ))}
              {copyData.keyword_priority_list?.title_keywords && (
                <div className="p-3 bg-bg-dark/50 rounded-lg border border-border-dark/50">
                  <div className="font-medium text-text-bright text-xs">Keyword Priority — Title</div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {copyData.keyword_priority_list.title_keywords.map((k, i) => (
                      <span key={i} className="text-[10px] px-2 py-0.5 bg-teal/10 text-teal rounded">{k.keyword} ({k.sv?.toLocaleString()})</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : <NoData message="No copy variants queued" />}
        </div>
        <div className="glow-card p-6">
          <div className="flex items-center gap-2 mb-4">
            <Image size={16} className="text-teal" />
            <h3 className="text-base font-bold text-text-bright">Image Changes</h3>
          </div>
          <NoData message="No image briefs queued" />
        </div>
      </div>
    </div>
  )
}
