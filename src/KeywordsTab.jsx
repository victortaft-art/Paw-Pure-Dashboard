import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { Search, TrendingUp, TrendingDown, AlertTriangle, Zap, Target, DollarSign, Eye, MousePointer, ShoppingCart, Filter } from 'lucide-react'
import NoData from './components/NoData'

const tagColors = {
  core: { bg: 'bg-teal/15', text: 'text-teal', border: 'border-teal/30', label: 'Core' },
  opportunity: { bg: 'bg-cyan/15', text: 'text-cyan', border: 'border-cyan/30', label: 'Opportunity' },
  competitor: { bg: 'bg-pink/15', text: 'text-pink', border: 'border-pink/30', label: 'Competitor' },
  negative: { bg: 'bg-red/15', text: 'text-red', border: 'border-red/30', label: 'Negative' },
}

const statusColors = {
  active: { bg: 'bg-green/15', text: 'text-green', label: 'Active PPC' },
  auto: { bg: 'bg-amber/15', text: 'text-amber', label: 'Auto Campaign' },
  not_indexed: { bg: 'bg-red/15', text: 'text-red', label: 'Not Indexed' },
  not_targeted: { bg: 'bg-text-dim/15', text: 'text-text-dim', label: 'Not Targeted' },
  paused: { bg: 'bg-text-dim/15', text: 'text-text-dim', label: 'Paused' },
}

function RankBadge({ rank, label }) {
  if (rank == null) return (
    <div className="text-center">
      <div className="text-lg font-bold text-text-dim">—</div>
      <div className="text-[9px] text-text-dim uppercase tracking-wider">{label}</div>
    </div>
  )
  const color = rank <= 10 ? 'text-green' : rank <= 30 ? 'text-amber' : 'text-red'
  return (
    <div className="text-center">
      <div className={`text-lg font-extrabold ${color}`}>#{rank}</div>
      <div className="text-[9px] text-text-dim uppercase tracking-wider">{label}</div>
    </div>
  )
}

function KeywordRow({ kw, onClick }) {
  const tag = tagColors[kw.tag] || tagColors.core
  const status = statusColors[kw.ppc_status] || statusColors.not_targeted
  const hasSpend = kw.ppc_spend_7d > 0
  const isWasting = hasSpend && kw.ppc_sales_7d === 0

  return (
    <div
      onClick={() => onClick(kw)}
      className={`glow-card p-4 cursor-pointer hover:border-teal/30 transition-all ${isWasting ? 'glow-red' : ''}`}
    >
      <div className="flex items-start gap-4">
        {/* Keyword + tags */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <h4 className="text-sm font-semibold text-text-bright truncate">{kw.keyword}</h4>
            {isWasting && <AlertTriangle size={14} className="text-red flex-shrink-0" />}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${tag.bg} ${tag.text} ${tag.border}`}>
              {tag.label}
            </span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${status.bg} ${status.text}`}>
              {status.label}
            </span>
            {kw.match_type && (
              <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-bg-dark text-text-dim">
                {kw.match_type}
              </span>
            )}
          </div>
        </div>

        {/* Search volume */}
        <div className="text-center flex-shrink-0 w-16">
          <div className="text-base font-bold text-text-bright">{kw.search_volume ? kw.search_volume.toLocaleString() : '—'}</div>
          <div className="text-[9px] text-text-dim uppercase">Vol</div>
        </div>

        {/* Ranks */}
        <div className="flex gap-4 flex-shrink-0">
          <RankBadge rank={kw.organic_rank} label="Organic" />
          <RankBadge rank={kw.sponsored_rank} label="Sponsored" />
        </div>

        {/* PPC metrics */}
        <div className="flex gap-3 flex-shrink-0 text-center">
          <div className="w-14">
            <div className="text-sm font-bold text-text-bright">{kw.ppc_impressions_7d?.toLocaleString() || '—'}</div>
            <div className="text-[9px] text-text-dim">Impr</div>
          </div>
          <div className="w-10">
            <div className="text-sm font-bold text-text-bright">{kw.ppc_clicks_7d || '—'}</div>
            <div className="text-[9px] text-text-dim">Clicks</div>
          </div>
          <div className="w-14">
            <div className={`text-sm font-bold ${isWasting ? 'text-red' : 'text-text-bright'}`}>
              {kw.ppc_spend_7d ? `$${kw.ppc_spend_7d.toFixed(0)}` : '—'}
            </div>
            <div className="text-[9px] text-text-dim">Spend</div>
          </div>
          <div className="w-14">
            <div className={`text-sm font-bold ${kw.ppc_sales_7d > 0 ? 'text-green' : hasSpend ? 'text-red' : 'text-text-dim'}`}>
              {kw.ppc_sales_7d != null ? `$${kw.ppc_sales_7d.toFixed(0)}` : '—'}
            </div>
            <div className="text-[9px] text-text-dim">Sales</div>
          </div>
        </div>
      </div>

      {kw._notes && (
        <div className="mt-2 text-[11px] text-text-dim pl-0 border-l-2 border-border-dark ml-0 pl-2">
          {kw._notes}
        </div>
      )}
    </div>
  )
}

function KeywordDetail({ kw, onClose }) {
  if (!kw) return null
  const tag = tagColors[kw.tag] || tagColors.core
  const status = statusColors[kw.ppc_status] || statusColors.not_targeted
  const hasSpend = kw.ppc_spend_7d > 0
  const isWasting = hasSpend && kw.ppc_sales_7d === 0

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-bg-card border border-border-dark rounded-2xl shadow-2xl max-w-md w-full p-6" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <Search size={16} className="text-teal" />
          <button onClick={onClose} className="text-text-dim hover:text-text-bright text-sm">Close</button>
        </div>

        <h3 className="text-lg font-bold text-text-bright mb-3">{kw.keyword}</h3>

        <div className="flex gap-2 mb-4">
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${tag.bg} ${tag.text} ${tag.border}`}>{tag.label}</span>
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${status.bg} ${status.text}`}>{status.label}</span>
        </div>

        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="glow-card p-3 text-center">
            <div className="text-xl font-extrabold text-text-bright">{kw.search_volume?.toLocaleString() || '—'}</div>
            <div className="text-[9px] text-text-dim uppercase">Search Vol</div>
          </div>
          <div className="glow-card p-3 text-center">
            <RankBadge rank={kw.organic_rank} label="Organic" />
          </div>
          <div className="glow-card p-3 text-center">
            <RankBadge rank={kw.sponsored_rank} label="Sponsored" />
          </div>
        </div>

        {/* PPC Performance */}
        <div className="border-t border-border-dark pt-3 mb-3">
          <div className="text-[10px] font-bold text-teal uppercase tracking-wider mb-2">PPC Performance (7d)</div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            {[
              ['Impressions', kw.ppc_impressions_7d?.toLocaleString()],
              ['Clicks', kw.ppc_clicks_7d],
              ['CTR', kw.ppc_ctr_pct ? `${kw.ppc_ctr_pct}%` : null],
              ['CVR', kw.ppc_cvr_pct != null ? `${kw.ppc_cvr_pct}%` : null],
              ['Spend', kw.ppc_spend_7d ? `$${kw.ppc_spend_7d.toFixed(2)}` : null],
              ['Sales', kw.ppc_sales_7d != null ? `$${kw.ppc_sales_7d.toFixed(2)}` : null],
              ['ACoS', kw.ppc_acos_7d != null ? `${kw.ppc_acos_7d}%` : null],
              ['Campaign', kw.campaign],
            ].map(([label, val], i) => (
              <div key={i} className="flex justify-between py-1 border-b border-border-dark/30">
                <span className="text-text-dim">{label}</span>
                <span className="font-medium text-text-bright">{val || '—'}</span>
              </div>
            ))}
          </div>
        </div>

        {isWasting && (
          <div className="bg-red/10 border border-red/20 rounded-xl p-3 text-xs text-red mb-3">
            <AlertTriangle size={12} className="inline mr-1" />
            <strong>Wasting spend:</strong> ${kw.ppc_spend_7d?.toFixed(2)} spent with $0 in sales. Consider pausing or adding as negative.
          </div>
        )}

        {kw.tag === 'opportunity' && (
          <div className="bg-cyan/10 border border-cyan/20 rounded-xl p-3 text-xs text-cyan mb-3">
            <Zap size={12} className="inline mr-1" />
            <strong>Opportunity:</strong> {kw.search_volume?.toLocaleString()} monthly searches. Not currently targeted in PPC or indexed organically.
          </div>
        )}

        {kw._notes && (
          <div className="bg-amber/5 border border-amber/20 rounded-xl p-3 text-xs text-amber">
            <strong>Note:</strong> {kw._notes}
          </div>
        )}
      </div>
    </div>
  )
}

export default function KeywordsTab({ data }) {
  const [selectedKw, setSelectedKw] = useState(null)
  const [filterTag, setFilterTag] = useState('all')
  const [sortBy, setSortBy] = useState('volume')

  const kwData = data.kw?.current
  const ppcData = data.ppc?.current

  // Merge keywords from kw_data + PPC_Analysis
  let keywords = []
  let summary = {}

  if (kwData) {
    keywords = kwData.tracked_keywords || []
    summary = kwData.summary || {}
  }

  // Enrich or build from PPC_Analysis if available
  if (ppcData) {
    const ppcKeywords = ppcData.keyword_analysis || []
    const ppcGaps = ppcData.keyword_gap_opportunities || []

    // Merge PPC keyword data into existing keywords
    ppcKeywords.forEach(pk => {
      const existing = keywords.find(k => k.keyword === pk.keyword)
      if (existing) {
        // Update with fresher PPC data
        if (pk.ppc_impressions_7d != null) existing.ppc_impressions_7d = pk.ppc_impressions_7d
        if (pk.ppc_clicks_7d != null) existing.ppc_clicks_7d = pk.ppc_clicks_7d
        if (pk.ppc_spend_7d != null) existing.ppc_spend_7d = pk.ppc_spend_7d
        if (pk.ppc_sales_7d != null) existing.ppc_sales_7d = pk.ppc_sales_7d
        if (pk.ppc_ctr != null) existing.ppc_ctr_pct = pk.ppc_ctr
        if (pk.ppc_cvr != null) existing.ppc_cvr_pct = pk.ppc_cvr
        if (pk.flag) existing._notes = pk.flag
        if (pk.organic_rank != null) existing.organic_rank = pk.organic_rank
      } else {
        keywords.push({
          keyword: pk.keyword, search_volume: pk.search_volume,
          organic_rank: pk.organic_rank, sponsored_rank: null,
          ppc_status: 'active', ppc_impressions_7d: pk.ppc_impressions_7d,
          ppc_clicks_7d: pk.ppc_clicks_7d, ppc_spend_7d: pk.ppc_spend_7d,
          ppc_sales_7d: pk.ppc_sales_7d, ppc_ctr_pct: pk.ppc_ctr,
          ppc_cvr_pct: pk.ppc_cvr, match_type: pk.match_type,
          campaign: pk.campaign, tag: 'core',
          _notes: pk.flag,
        })
      }
    })

    // Add gap opportunities
    ppcGaps.forEach(gap => {
      if (!keywords.find(k => k.keyword === gap.keyword)) {
        keywords.push({
          keyword: gap.keyword, search_volume: gap.search_volume,
          organic_rank: null, sponsored_rank: null,
          ppc_status: 'not_indexed', ppc_impressions_7d: 0,
          ppc_clicks_7d: 0, ppc_spend_7d: 0, ppc_sales_7d: 0,
          tag: 'opportunity', _notes: gap.recommendation,
          priority: gap.priority,
        })
      }
    })

    // Update summary from PPC data
    if (ppcData.summary) {
      summary.total_ppc_spend_7d = ppcData.summary.total_spend
      summary.total_ppc_sales_7d = ppcData.summary.total_sales
      summary.wasted_spend = ppcData.summary.wasted_spend
      summary.keyword_gaps_identified = ppcData.summary.keyword_gaps_identified
    }
  }

  if (keywords.length === 0) return <div className="glow-card p-8"><NoData message="No keyword data yet — run the Helium 10 bot or PPC Analysis agent" /></div>

  summary.total_tracked = keywords.length

  // Filter
  const filtered = filterTag === 'all' ? keywords : keywords.filter(k => k.tag === filterTag)

  // Sort
  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'volume') return (b.search_volume || 0) - (a.search_volume || 0)
    if (sortBy === 'spend') return (b.ppc_spend_7d || 0) - (a.ppc_spend_7d || 0)
    if (sortBy === 'rank') return (a.organic_rank || 999) - (b.organic_rank || 999)
    return 0
  })

  // Chart: search volume by keyword
  const volumeChart = keywords
    .filter(k => k.search_volume > 0)
    .sort((a, b) => b.search_volume - a.search_volume)
    .slice(0, 8)
    .map(k => ({
      keyword: k.keyword.length > 25 ? k.keyword.slice(0, 22) + '...' : k.keyword,
      volume: k.search_volume,
      tag: k.tag,
    }))

  // Stats
  const coreKws = keywords.filter(k => k.tag === 'core')
  const opps = keywords.filter(k => k.tag === 'opportunity')
  const wasting = keywords.filter(k => k.ppc_spend_7d > 0 && k.ppc_sales_7d === 0)
  const totalOppVolume = opps.reduce((s, k) => s + (k.search_volume || 0), 0)

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="glow-card glow-teal p-4 text-center">
          <div className="text-2xl font-extrabold text-text-bright">{summary.total_tracked || keywords.length}</div>
          <div className="text-[10px] text-text-dim uppercase tracking-wider mt-1">Tracked</div>
        </div>
        <div className="glow-card glow-green p-4 text-center">
          <div className="text-2xl font-extrabold text-green">{summary.active_in_ppc || coreKws.length}</div>
          <div className="text-[10px] text-text-dim uppercase tracking-wider mt-1">Active PPC</div>
        </div>
        <div className="glow-card glow-cyan p-4 text-center">
          <div className="text-2xl font-extrabold text-cyan">{opps.length}</div>
          <div className="text-[10px] text-text-dim uppercase tracking-wider mt-1">Opportunities</div>
        </div>
        <div className="glow-card glow-red p-4 text-center">
          <div className="text-2xl font-extrabold text-red">{wasting.length}</div>
          <div className="text-[10px] text-text-dim uppercase tracking-wider mt-1">Wasting $</div>
        </div>
        <div className="glow-card glow-amber p-4 text-center">
          <div className="text-2xl font-extrabold text-amber">${summary.total_ppc_spend_7d?.toFixed(0) || 0}</div>
          <div className="text-[10px] text-text-dim uppercase tracking-wider mt-1">KW Spend 7d</div>
        </div>
        <div className="glow-card glow-pink p-4 text-center">
          <div className="text-2xl font-extrabold text-pink">{totalOppVolume.toLocaleString()}</div>
          <div className="text-[10px] text-text-dim uppercase tracking-wider mt-1">Opp Volume</div>
        </div>
      </div>

      {/* Search Volume Chart */}
      <div className="glow-card p-6">
        <h3 className="text-base font-bold text-text-bright mb-4">Search Volume by Keyword</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={volumeChart} layout="vertical" margin={{ left: 150 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2e3a" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10, fill: '#8892a4' }} tickFormatter={v => v.toLocaleString()} />
            <YAxis type="category" dataKey="keyword" tick={{ fontSize: 11, fill: '#e2e8f0' }} width={150} />
            <Tooltip contentStyle={{ background: '#1a1d27', border: '1px solid #2a2e3a', borderRadius: 8, color: '#e2e8f0' }} formatter={v => v.toLocaleString()} />
            <Bar dataKey="volume" radius={[0, 6, 6, 0]}>
              {volumeChart.map((entry, i) => (
                <Cell key={i} fill={entry.tag === 'core' ? '#2dd4a8' : entry.tag === 'opportunity' ? '#47bfff' : '#e84393'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Filter + Sort bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1">
          <Filter size={14} className="text-text-dim" />
          <span className="text-xs text-text-dim mr-1">Filter:</span>
          {['all', 'core', 'opportunity', 'competitor'].map(tag => (
            <button
              key={tag}
              onClick={() => setFilterTag(tag)}
              className={`px-3 py-1 rounded-lg text-[11px] font-medium transition-colors ${
                filterTag === tag ? 'bg-teal/20 text-teal' : 'bg-bg-card text-text-dim hover:text-text border border-border-dark'
              }`}
            >
              {tag === 'all' ? 'All' : tagColors[tag]?.label || tag}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-1">
          <span className="text-xs text-text-dim mr-1">Sort:</span>
          {[
            { key: 'volume', label: 'Volume' },
            { key: 'spend', label: 'Spend' },
            { key: 'rank', label: 'Rank' },
          ].map(s => (
            <button
              key={s.key}
              onClick={() => setSortBy(s.key)}
              className={`px-3 py-1 rounded-lg text-[11px] font-medium transition-colors ${
                sortBy === s.key ? 'bg-teal/20 text-teal' : 'bg-bg-card text-text-dim hover:text-text border border-border-dark'
              }`}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Keyword List */}
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-center gap-4 px-4 text-[10px] text-text-dim uppercase tracking-wider">
          <div className="flex-1">Keyword</div>
          <div className="w-16 text-center">Volume</div>
          <div className="w-24 text-center">Organic / Sponsored</div>
          <div className="flex gap-3 text-center">
            <div className="w-14">Impr</div>
            <div className="w-10">Clicks</div>
            <div className="w-14">Spend</div>
            <div className="w-14">Sales</div>
          </div>
        </div>

        {sorted.map((kw, i) => (
          <KeywordRow key={i} kw={kw} onClick={setSelectedKw} />
        ))}
      </div>

      {/* Helium 10 Bot Status */}
      <div className="glow-card glow-cyan p-6">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 bg-cyan/15 rounded-lg flex items-center justify-center">
            <Zap size={16} className="text-cyan" />
          </div>
          <div>
            <h3 className="text-base font-bold text-text-bright">Helium 10 Bot</h3>
            <p className="text-xs text-text-dim">Automated keyword research + rank tracking</p>
          </div>
          <span className="ml-auto px-3 py-1 bg-amber/15 text-amber text-[10px] font-bold rounded-lg">NOT CONFIGURED</span>
        </div>
        <p className="text-sm text-text-dim">
          Once built, the bot will run weekly to: pull organic + sponsored ranks from Cerebro, discover new keyword opportunities from Magnet, merge PPC performance data, and save to <code className="text-teal bg-teal/10 px-1.5 py-0.5 rounded text-xs">kw_data/KW_Data_[date].json</code>
        </p>
      </div>

      {/* Detail Modal */}
      {selectedKw && <KeywordDetail kw={selectedKw} onClose={() => setSelectedKw(null)} />}
    </div>
  )
}
