import { useState } from 'react'
import { useSmartPark } from './hooks/useSmartPark'
import ParkingLot      from './components/ParkingLot'
import StatsPanel      from './components/StatsPanel'
import AlertBanner     from './components/AlertBanner'
import ExperimentsTable from './components/ExperimentsTable'
import LogViewer       from './components/LogViewer'

const TABS = [
  { id: 'dashboard',   label: 'Live Simulation' },
  { id: 'experiments', label: 'Experiments'     },
  { id: 'logs',        label: 'Logs'            },
]

export default function App() {
  const [tab,  setTab]  = useState('dashboard')
  const [dark, setDark] = useState(true)
  const { slots, summary, connected, events } = useSmartPark()

  // ── theme tokens ──────────────────────────────────────────────────────
  const bg       = dark ? '#0a0b0f' : '#f1f5f9'
  const navBg    = dark ? '#0d0f14' : '#ffffff'
  const navBdr   = dark ? '#1e2228' : '#e2e8f0'
  const cardBg   = dark ? '#0d0f14' : '#ffffff'
  const cardBdr  = dark ? '#1e2228' : '#e2e8f0'
  const text     = dark ? '#e2e8f0' : '#0f172a'
  const muted    = dark ? '#94a3b8' : '#64748b'
  const tabAct   = dark ? '#1e2228' : '#e2e8f0'
  const tabActTx = dark ? '#f1f5f9' : '#0f172a'
  const tabIdl   = 'transparent'
  const tabIdlTx = dark ? '#64748b' : '#94a3b8'

  return (
    <div className="min-h-screen flex flex-col" style={{ background: bg, color: text }}>

      {/* ── Navbar ─────────────────────────────────────────────────────── */}
      <header className="flex items-center gap-5 px-6 py-3 shrink-0"
        style={{ background: navBg, borderBottom: `1px solid ${navBdr}` }}>

        {/* logo */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl flex items-center justify-center font-black text-sm text-white"
            style={{ background: 'linear-gradient(135deg,#0ea5e9,#6366f1)' }}>P</div>
          <div>
            <div className="text-sm font-bold leading-none" style={{ color: text }}>SmartPark MQTT</div>
            <div className="text-[10px] mt-0.5" style={{ color: muted }}>BBM 460 · QoS Performance Research</div>
          </div>
        </div>

        {/* tabs */}
        <nav className="flex items-center gap-1 ml-6">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className="px-4 py-1.5 rounded-lg text-sm font-medium transition-all"
              style={{
                background:   tab===t.id ? tabAct   : tabIdl,
                color:        tab===t.id ? tabActTx : tabIdlTx,
                borderBottom: `2px solid ${tab===t.id ? '#0ea5e9' : 'transparent'}`,
              }}>
              {t.label}
            </button>
          ))}
        </nav>

        {/* right side */}
        <div className="ml-auto flex items-center gap-4">

          {/* broker status */}
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
            <span className="text-xs font-semibold" style={{ color: connected ? '#22c55e' : '#ef4444' }}>
              {connected ? 'BROKER CONNECTED' : 'BROKER OFFLINE'}
            </span>
          </div>

          {/* theme toggle */}
          <button onClick={() => setDark(d => !d)}
            className="w-9 h-9 rounded-xl flex items-center justify-center text-base transition-all"
            style={{
              background: dark ? '#1e2228' : '#e2e8f0',
              color: dark ? '#fbbf24' : '#6366f1',
              border: `1px solid ${navBdr}`,
            }}
            title={dark ? 'Switch to light theme' : 'Switch to dark theme'}>
            {dark ? '☀' : '☽'}
          </button>
        </div>
      </header>

      {/* ── Content ────────────────────────────────────────────────────── */}
      <main className="flex-1 p-5 overflow-auto">

        {/* ─── DASHBOARD ─── */}
        {tab === 'dashboard' && (
          <div className="space-y-4 max-w-screen-xl mx-auto">

            <AlertBanner summary={summary} dark={dark} />

            <div className="flex gap-5 items-start">

              {/* parking lot card */}
              <div className="flex-1 min-w-0">
                <div className="rounded-2xl overflow-hidden"
                  style={{ background: cardBg, border: `1px solid ${cardBdr}` }}>
                  <div className="flex items-center justify-between px-5 py-3.5"
                    style={{ borderBottom: `1px solid ${cardBdr}` }}>
                    <div>
                      <h2 className="text-sm font-bold" style={{ color: text }}>Live Parking Simulation</h2>
                      <p className="text-xs mt-0.5" style={{ color: muted }}>Real-time slot states via MQTT WebSocket</p>
                    </div>
                    <div className="flex items-center gap-1.5 text-xs font-mono" style={{ color: muted }}>
                      <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse inline-block" />
                      LIVE
                    </div>
                  </div>
                  <div className="p-4">
                    <ParkingLot slots={slots} dark={dark} />
                  </div>
                </div>
              </div>

              {/* stats panel */}
              <div className="w-64 shrink-0">
                <div className="rounded-2xl p-5"
                  style={{ background: cardBg, border: `1px solid ${cardBdr}` }}>
                  <h2 className="text-xs font-bold uppercase tracking-widest mb-4" style={{ color: muted }}>
                    System Status
                  </h2>
                  <StatsPanel summary={summary} connected={connected} events={events} dark={dark} />
                </div>
              </div>

            </div>
          </div>
        )}

        {/* ─── EXPERIMENTS ─── */}
        {tab === 'experiments' && (
          <div className="max-w-screen-xl mx-auto rounded-2xl p-6"
            style={{ background: cardBg, border: `1px solid ${cardBdr}` }}>
            <div className="mb-6">
              <h2 className="text-lg font-bold" style={{ color: text }}>Experiment Results</h2>
              <p className="text-sm mt-1" style={{ color: muted }}>
                12 controlled experiments · QoS 0 / 1 / 2 · clean network and 5% packet loss
              </p>
            </div>
            <ExperimentsTable dark={dark} />
          </div>
        )}

        {/* ─── LOGS ─── */}
        {tab === 'logs' && (
          <div className="max-w-screen-xl mx-auto rounded-2xl p-6"
            style={{ background: cardBg, border: `1px solid ${cardBdr}` }}>
            <div className="mb-6">
              <h2 className="text-lg font-bold" style={{ color: text }}>System Logs</h2>
              <p className="text-sm mt-1" style={{ color: muted }}>Controller output · experiment runs · error traces</p>
            </div>
            <LogViewer dark={dark} />
          </div>
        )}

      </main>
    </div>
  )
}
