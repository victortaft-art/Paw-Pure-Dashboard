import { useState, useEffect } from 'react'
import { DollarSign, BarChart3, FlaskConical, RefreshCw, AlertCircle, TrendingUp, Package, Zap, Search } from 'lucide-react'
import { loadAllData } from './utils/dataLoader'
import EconomicsTab from './EconomicsTab'
import InsightsTab from './InsightsTab'
import ExperimentsTab from './ExperimentsTab'
import KeywordsTab from './KeywordsTab'

const tabs = [
  { id: 'economics', label: 'Economics', sublabel: 'P&L & Inventory', icon: DollarSign },
  { id: 'insights', label: 'Intelligence', sublabel: 'Weekly Insights', icon: TrendingUp },
  { id: 'keywords', label: 'Keywords', sublabel: 'Rank & PPC Tracker', icon: Search },
  { id: 'experiments', label: 'Experiments', sublabel: 'A/B Testing', icon: FlaskConical },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('economics')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [lastLoaded, setLastLoaded] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)

  async function fetchData() {
    setLoading(true)
    setError(null)
    try {
      const result = await loadAllData()
      setData(result)
      setLastLoaded(new Date())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const dataDate = data?.sc?.currentDate || data?.ci?.currentDate || null

  return (
    <div className="flex min-h-screen bg-bg-dark">
      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-56' : 'w-16'} flex-shrink-0 bg-bg-card border-r border-border-dark flex flex-col transition-all duration-200`}>
        {/* Logo */}
        <div className="p-4 border-b border-border-dark">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-teal to-cyan rounded-xl flex items-center justify-center flex-shrink-0">
              <span className="text-white font-black text-xs">PP</span>
            </div>
            {sidebarOpen && (
              <div>
                <div className="text-sm font-bold text-text-bright">Paw Pure</div>
                <div className="text-[10px] text-text-dim">Business Dashboard</div>
              </div>
            )}
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-1">
          <div className="text-[10px] font-semibold text-teal uppercase tracking-widest px-3 mb-3">
            {sidebarOpen ? 'Reports' : ''}
          </div>
          {tabs.map(tab => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left transition-all ${
                  isActive
                    ? 'bg-teal-glow text-teal'
                    : 'text-text-dim hover:text-text hover:bg-bg-card-hover'
                }`}
              >
                <Icon size={18} className={isActive ? 'text-teal' : ''} />
                {sidebarOpen && (
                  <div>
                    <div className="text-sm font-medium">{tab.label}</div>
                    <div className="text-[10px] opacity-60">{tab.sublabel}</div>
                  </div>
                )}
                {isActive && <div className="ml-auto w-1.5 h-1.5 rounded-full bg-teal" />}
              </button>
            )
          })}
        </nav>

        {/* Data status */}
        <div className="p-3 border-t border-border-dark">
          {sidebarOpen && (
            <div className="text-[10px] text-text-dim space-y-1">
              {dataDate && <div>Data: <span className="text-teal">{dataDate}</span></div>}
              {lastLoaded && <div>Loaded: {lastLoaded.toLocaleTimeString()}</div>}
            </div>
          )}
          <button
            onClick={fetchData}
            disabled={loading}
            className="mt-2 w-full flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-medium text-teal bg-teal-glow rounded-lg hover:bg-teal/20 transition-colors disabled:opacity-50"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
            {sidebarOpen && 'Refresh Data'}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        {/* Top bar */}
        <header className="sticky top-0 z-40 bg-bg-dark/80 backdrop-blur-xl border-b border-border-dark px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-text-bright">
                {tabs.find(t => t.id === activeTab)?.label}
              </h1>
              <p className="text-xs text-text-dim">
                {tabs.find(t => t.id === activeTab)?.sublabel} — {dataDate || 'No data loaded'}
              </p>
            </div>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="lg:hidden p-2 text-text-dim hover:text-text rounded-lg"
            >
              <BarChart3 size={18} />
            </button>
          </div>
        </header>

        <div className="p-6">
          {loading && !data && (
            <div className="flex items-center justify-center py-20">
              <RefreshCw size={24} className="animate-spin text-teal" />
              <span className="ml-3 text-text-dim">Loading data...</span>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-4 bg-red-glow text-red rounded-xl mb-6 border border-red/20">
              <AlertCircle size={16} />
              <span className="text-sm">{error}</span>
            </div>
          )}

          {data && (
            <>
              {activeTab === 'economics' && <EconomicsTab data={data} />}
              {activeTab === 'insights' && <InsightsTab data={data} />}
              {activeTab === 'keywords' && <KeywordsTab data={data} />}
              {activeTab === 'experiments' && <ExperimentsTab data={data} />}
            </>
          )}
        </div>
      </main>
    </div>
  )
}
