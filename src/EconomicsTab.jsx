import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, PieChart, Pie, Cell } from 'recharts'
import { Package, AlertTriangle, CheckCircle, DollarSign, Percent, Target, Activity } from 'lucide-react'
import KpiCard from './components/KpiCard'
import NoData from './components/NoData'

function getDaysCoverColor(days) {
  if (days > 30) return 'text-green'
  if (days >= 14) return 'text-amber'
  return 'text-red'
}

// Helper to extract data from both old and new SC_Data formats
function extractSC(sc) {
  if (!sc) return {}

  // New format (2026-04-04+): business_reports.asins, campaign_manager, fba_inventory.asins
  const br = sc.business_reports || sc.businessReports
  const cm = sc.campaign_manager || sc.campaignSummary
  const inv = sc.fba_inventory?.asins || sc.fba_inventory || {}

  // Sessions & units from ASIN breakdown or period summary
  let totalSessions = 0, totalUnits = 0, totalRevenue = 0
  if (br?.asins) {
    Object.values(br.asins).forEach(a => {
      totalSessions += a.sessions || 0
      totalUnits += a.units_ordered || 0
    })
  }
  if (br?.period_7d) {
    totalSessions = br.period_7d.sessions || totalSessions
    totalUnits = br.period_7d.unitsOrdered || totalUnits
    totalRevenue = br.period_7d.orderedProductSales || 0
  }

  // Campaign metrics
  let acos = null, adSpend = 0, adSales = 0, impressions = 0, clicks = 0
  if (cm?.campaigns_total) {
    acos = cm.campaigns_total.acos_pct
    adSpend = cm.campaigns_total.spend || 0
    adSales = cm.campaigns_total.sales || 0
    impressions = cm.campaigns_total.impressions || 0
    clicks = cm.campaigns_total.clicks || 0
  } else if (cm?.overview_metrics) {
    impressions = cm.overview_metrics.impressions || 0
    clicks = cm.overview_metrics.clicks || 0
    adSales = cm.overview_metrics.sales || 0
  }
  if (cm?.totalSpend_7d_estimated) adSpend = cm.totalSpend_7d_estimated
  if (cm?.overallACoS_percent_7d != null) acos = cm.overallACoS_percent_7d
  if (cm?.allTime?.acos_percent != null && acos == null) acos = cm.allTime.acos_percent

  return { totalSessions, totalUnits, totalRevenue, acos, adSpend, adSales, impressions, clicks, inv, br, cm }
}

export default function EconomicsTab({ data }) {
  const sc = data.sc?.current
  const pl = data.pl?.current
  const plConfig = data.plConfig
  const priorSc = data.sc?.prior

  const curr = extractSC(sc)
  const prior = extractSC(priorSc)
  const products = plConfig?.products || {}

  // Use PL_Data directly if available
  const plData = pl?.pl_7day
  const plTotals = plData?.totals

  const revenue7d = plTotals?.revenue || curr.totalRevenue || null
  const revenue30d = sc?.businessReports?.period_30d?.orderedProductSales || null
  const revenueTarget = revenue30d ? Number((revenue30d / 4.3).toFixed(2)) : (revenue7d ? Number((revenue7d).toFixed(2)) : null)
  const priorRevenue = prior.totalRevenue || null

  const trueContrib = plTotals?.true_contribution_margin ?? null
  const trueContribPct = plTotals?.contribution_margin_pct ?? (trueContrib != null && revenue7d ? ((trueContrib / revenue7d) * 100) : null)

  const acos = curr.acos
  const adSpend = plTotals?.ad_spend || curr.adSpend || 0

  const razorRatio = pl?.pl_7day?.razor_blade_ratio ?? null

  // Build P&L table from PL_Data
  const plRows = []
  if (plData) {
    const f = plData.fountain || {}
    const fl = plData.filters || {}
    const b = plData.bundle || {}
    const t = plTotals || {}

    plRows.push(
      { label: 'Revenue', fountain: f.revenue || 0, filters: fl.revenue || 0, bundle: b.revenue || 0, total: t.revenue || 0, isMoney: true },
      { label: 'Amazon Fees', fountain: -(f.amazon_fee || 0), filters: -(fl.amazon_fee || 0), bundle: -(b.amazon_fee || 0), total: -((f.amazon_fee || 0) + (fl.amazon_fee || 0) + (b.amazon_fee || 0)), isMoney: true },
      { label: 'COGS', fountain: -(f.cogs || 0), filters: -(fl.cogs || 0), bundle: -(b.cogs || 0), total: -((f.cogs || 0) + (fl.cogs || 0) + (b.cogs || 0)), isMoney: true },
      { label: 'Gross Profit', fountain: f.gross_profit || 0, filters: fl.gross_profit || 0, bundle: b.gross_profit || 0, total: t.gross_profit || ((f.gross_profit || 0) + (fl.gross_profit || 0) + (b.gross_profit || 0)), isMoney: true, isBold: true },
      { label: 'Gross Margin', fountain: f.margin_pct || 0, filters: fl.margin_pct || 0, bundle: b.margin_pct || 0, total: t.revenue ? ((t.gross_profit || 0) / t.revenue * 100) : 0, isPct: true },
      { label: 'Ad Spend', fountain: 0, filters: 0, bundle: 0, total: -(t.ad_spend || adSpend), isMoney: true },
      { label: 'True Contribution', fountain: f.gross_profit || 0, filters: fl.gross_profit || 0, bundle: b.gross_profit || 0, total: t.true_contribution_margin ?? 0, isMoney: true, isBold: true, isBottom: true },
      { label: 'CM %', fountain: f.margin_pct || 0, filters: fl.margin_pct || 0, bundle: b.margin_pct || 0, total: t.contribution_margin_pct ?? 0, isPct: true, isBottom: true },
    )
  }

  // Revenue trend from history
  const historyData = (data.sc?.history || []).map(h => {
    const hpl = data.pl?.history?.find(p => p.date === h.date)
    const rev = hpl?.data?.pl_7day?.totals?.revenue || h.data?.businessReports?.period_7d?.orderedProductSales || 0
    return { date: h.date, revenue: rev }
  }).filter(d => d.revenue > 0)

  // Inventory from new SC_Data fba_inventory.asins
  const invData = curr.inv || {}
  const inventoryCards = Object.entries(products).map(([key, prod]) => {
    const inv = invData[prod.asin] || {}
    const available = inv.available ?? null
    const unitsSold30d = inv.units_sold_30day ?? null
    const velocity = unitsSold30d != null ? (unitsSold30d / 30) : null
    const daysCover = (available != null && velocity && velocity > 0) ? Math.floor(available / velocity) : null
    const stockoutDate = daysCover != null ? new Date(Date.now() + daysCover * 86400000).toLocaleDateString() : null
    const totalFees = inv.total_fees_per_unit ?? prod.amazon_total_fee ?? null
    const fbaFee = inv.fba_fee_per_unit ?? null

    return {
      key, name: prod.name, asin: prod.asin,
      available, velocity: velocity?.toFixed(1),
      daysCover, stockoutDate,
      margin: prod.margin_pct, asp: prod.asp,
      leadTime: prod.supply_chain?.total_lead_time_days || 90,
      safetyDays: prod.safety_stock_days || 30,
      totalFees, fbaFee,
      salesRank: inv.sales_rank,
    }
  })

  // Fee breakdown
  const feeItems = []
  if (sc?.amazon_fees?.net_proceeds_breakdown) {
    const np = sc.amazon_fees.net_proceeds_breakdown
    if (np.amazon_fees) feeItems.push({ name: 'Amazon Fees', value: Math.abs(np.amazon_fees), color: '#e74c3c' })
    if (np.promo_rebates) feeItems.push({ name: 'Promo/Rebates', value: Math.abs(np.promo_rebates), color: '#9b59b6' })
    const adCost = np.expenses_total ? Math.abs(np.expenses_total) - Math.abs(np.amazon_fees || 0) - Math.abs(np.promo_rebates || 0) : adSpend
    if (adCost > 0) feeItems.push({ name: 'Advertising', value: adCost, color: '#f39c12' })
  } else {
    const totalRev = revenue7d || 0
    if (totalRev > 0) feeItems.push({ name: 'Referral Fees', value: totalRev * 0.15, color: '#e74c3c' })
    if (adSpend > 0) feeItems.push({ name: 'Ad Spend', value: adSpend, color: '#f39c12' })
  }

  // Alerts from PL_Data
  const alerts = pl?.alerts || {}

  return (
    <div className="space-y-6">
      {/* Critical Alerts */}
      {alerts.critical?.length > 0 && (
        <div className="glow-card glow-red p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={16} className="text-red" />
            <span className="text-sm font-bold text-red">Critical Alerts</span>
          </div>
          <div className="space-y-1">
            {alerts.critical.map((a, i) => (
              <div key={i} className="text-xs text-text">{a}</div>
            ))}
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard title="Weekly Revenue" value={revenue7d} format="$" target={revenueTarget} targetLabel="(30d avg)" prior={priorRevenue} glow="teal" icon={DollarSign} />
        <KpiCard title="True Contribution" value={trueContrib} format="$" subtitle={trueContribPct != null ? `${trueContribPct.toFixed(1)}% of revenue` : ''} glow={trueContrib > 0 ? 'green' : 'red'} icon={Activity} />
        <KpiCard title="ACoS" value={acos} format="%" target={25} subtitle={acos == null ? 'Infinite — $0 ad sales' : acos > 33.5 ? 'Above break-even!' : acos > 25 ? 'Above target' : 'On target'} invertColor glow={acos == null || acos > 33.5 ? 'red' : acos > 25 ? 'amber' : 'green'} icon={Target} />
        <KpiCard title="Razor-Blade Ratio" value={razorRatio} format="ratio" target={1.0} subtitle="Filters per fountain" glow={razorRatio >= 1 ? 'green' : razorRatio >= 0.5 ? 'amber' : 'pink'} icon={Percent} />
      </div>

      {/* P&L Table + Revenue Chart */}
      <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
        <div className="xl:col-span-3 glow-card p-6">
          <h3 className="text-base font-bold text-text-bright mb-4">P&L Income Statement — 7-Day</h3>
          {plRows.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border-dark">
                    <th className="py-2 px-3 text-left text-xs font-semibold text-text-dim uppercase tracking-wide">Line Item</th>
                    <th className="py-2 px-3 text-right text-xs font-semibold text-text-dim">Fountain</th>
                    <th className="py-2 px-3 text-right text-xs font-semibold text-text-dim">Filters</th>
                    <th className="py-2 px-3 text-right text-xs font-semibold text-text-dim">Bundle</th>
                    <th className="py-2 px-3 text-right text-xs font-semibold text-teal">TOTAL</th>
                  </tr>
                </thead>
                <tbody>
                  {plRows.map((row, ri) => (
                    <tr key={ri} className={`border-b border-border-dark/50 ${row.isBottom ? 'bg-teal-glow/30' : ''}`}>
                      <td className={`py-2.5 px-3 text-left ${row.isBold ? 'font-bold text-text-bright' : 'text-text-dim'}`}>{row.label}</td>
                      {['fountain', 'filters', 'bundle', 'total'].map(col => {
                        const val = row[col]
                        const isTotal = col === 'total'
                        const color = row.isBottom ? (val >= 0 ? 'text-green' : 'text-red') : isTotal ? 'text-text-bright' : 'text-text'
                        return (
                          <td key={col} className={`py-2.5 px-3 text-right tabular-nums ${color} ${row.isBold || isTotal ? 'font-semibold' : ''}`}>
                            {row.isPct ? `${val.toFixed(1)}%` : `$${val.toFixed(2)}`}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <NoData message="No P&L data — run the P&L agent" />}
        </div>

        <div className="xl:col-span-2 glow-card p-6">
          <h3 className="text-base font-bold text-text-bright mb-4">Revenue Trend</h3>
          {historyData.length > 1 ? (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={historyData}>
                <defs>
                  <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2dd4a8" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#2dd4a8" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2e3a" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#8892a4' }} />
                <YAxis tick={{ fontSize: 10, fill: '#8892a4' }} tickFormatter={v => `$${v}`} />
                <Tooltip contentStyle={{ background: '#1a1d27', border: '1px solid #2a2e3a', borderRadius: 8 }} formatter={v => [`$${Number(v).toFixed(2)}`, 'Revenue']} />
                <Area type="monotone" dataKey="revenue" stroke="#2dd4a8" strokeWidth={2.5} fill="url(#revGrad)" dot={{ r: 4, fill: '#2dd4a8', stroke: '#1a1d27', strokeWidth: 2 }} />
              </AreaChart>
            </ResponsiveContainer>
          ) : <NoData message="Need 2+ weeks for trend" />}
        </div>
      </div>

      {/* Inventory Cards */}
      <div>
        <h3 className="text-base font-bold text-text-bright mb-4">Inventory Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {inventoryCards.map(prod => (
            <div key={prod.key} className={`glow-card p-5 ${prod.daysCover != null && prod.daysCover < 14 ? 'glow-red' : prod.daysCover != null && prod.daysCover < 30 ? 'glow-amber' : ''}`}>
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h4 className="font-semibold text-text-bright text-sm">{prod.name}</h4>
                  <span className="text-[10px] text-text-dim font-mono">{prod.asin}</span>
                </div>
                <Package size={18} className="text-teal" />
              </div>

              {prod.available != null ? (
                <>
                  <div className="text-3xl font-extrabold text-text-bright mb-1">
                    {prod.available}
                    <span className="text-sm font-normal text-text-dim ml-1">units</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-3 text-center">
                    <div>
                      <div className="text-sm font-bold text-text-bright">{prod.velocity || '—'}</div>
                      <div className="text-[9px] text-text-dim">Units/day</div>
                    </div>
                    <div>
                      <div className={`text-sm font-bold ${prod.daysCover != null ? getDaysCoverColor(prod.daysCover) : 'text-text-dim'}`}>{prod.daysCover ?? '—'}</div>
                      <div className="text-[9px] text-text-dim">Days Cover</div>
                    </div>
                    <div>
                      <div className="text-sm font-bold text-teal">{prod.margin}%</div>
                      <div className="text-[9px] text-text-dim">Margin</div>
                    </div>
                  </div>
                  {prod.daysCover != null && (
                    <div className="mt-3">
                      <div className="flex justify-between text-[10px] text-text-dim mb-1">
                        <span>0</span>
                        <span>{prod.leadTime}d lead time</span>
                      </div>
                      <div className="h-2 bg-border-dark rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${prod.daysCover > 30 ? 'bg-green' : prod.daysCover >= 14 ? 'bg-amber' : 'bg-red'}`}
                          style={{ width: `${Math.min(100, (prod.daysCover / prod.leadTime) * 100)}%` }} />
                      </div>
                    </div>
                  )}
                  {prod.daysCover != null && prod.daysCover >= 30 && (
                    <div className="flex items-center gap-1 text-green text-xs font-medium mt-2">
                      <CheckCircle size={12} /> Healthy — {prod.daysCover} days cover
                    </div>
                  )}
                  {prod.salesRank && (
                    <div className="text-[10px] text-text-dim mt-2">BSR: #{prod.salesRank.toLocaleString()}</div>
                  )}
                </>
              ) : (
                <div className="mt-2 space-y-2">
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div><div className="text-lg font-bold text-text-bright">${prod.asp}</div><div className="text-[9px] text-text-dim">ASP</div></div>
                    <div><div className="text-lg font-bold text-teal">{prod.margin}%</div><div className="text-[9px] text-text-dim">Margin</div></div>
                    <div><div className="text-lg font-bold text-text-dim">—</div><div className="text-[9px] text-text-dim">Units</div></div>
                  </div>
                  <div className="text-[10px] text-amber">Check Seller Central for inventory</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Fee Breakdown */}
      {feeItems.length > 0 && (
        <div className="glow-card p-6">
          <h3 className="text-base font-bold text-text-bright mb-4">Cost Breakdown</h3>
          <div className="flex flex-col lg:flex-row items-center gap-8">
            <div className="w-52 h-52">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={feeItems} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={45} outerRadius={80} paddingAngle={3}>
                    {feeItems.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: '#1a1d27', border: '1px solid #2a2e3a', borderRadius: 8 }} formatter={v => `$${Number(v).toFixed(2)}`} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="space-y-3 flex-1">
              {feeItems.map((d, i) => (
                <div key={i} className="flex items-center gap-3 text-sm">
                  <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: d.color }} />
                  <span className="text-text-dim w-28">{d.name}</span>
                  <span className="font-semibold text-text-bright">${d.value.toFixed(2)}</span>
                  <div className="flex-1 h-1.5 bg-border-dark rounded-full overflow-hidden ml-2">
                    <div className="h-full rounded-full" style={{ backgroundColor: d.color, width: `${(d.value / feeItems.reduce((s, x) => s + x.value, 0)) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
