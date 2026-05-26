import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, ReferenceLine, Cell
} from 'recharts'

const QOS_COLORS = {
  0: { badge: 'bg-sky-500/20 text-sky-300 border-sky-500/40',   chart: '#38bdf8' },
  1: { badge: 'bg-violet-500/20 text-violet-300 border-violet-500/40', chart: '#a78bfa' },
  2: { badge: 'bg-rose-500/20 text-rose-300 border-rose-500/40', chart: '#fb7185' },
}

function latColor(ms) {
  if (ms == null) return '#64748b'
  if (ms < 5)  return '#34d399'
  if (ms < 50) return '#fbbf24'
  return '#f87171'
}

function netBadge(net, dark) {
  if (net === '5% loss') return dark
    ? 'bg-red-500/20 text-red-300 border border-red-500/40'
    : 'bg-red-100 text-red-700 border border-red-300'
  return dark
    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
    : 'bg-emerald-100 text-emerald-700 border border-emerald-300'
}

const CustomTooltip = ({ active, payload, label, dark }) => {
  if (!active || !payload?.length) return null
  const bg = dark ? '#1e2228' : '#fff'
  const border = dark ? '#334155' : '#e2e8f0'
  const text = dark ? '#e2e8f0' : '#0f172a'
  const sub  = dark ? '#94a3b8' : '#64748b'
  return (
    <div className="rounded-xl px-4 py-3 text-sm shadow-xl" style={{ background: bg, border: `1px solid ${border}`, color: text }}>
      <p className="font-bold mb-1">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: <span className="font-mono font-bold">{p.value} ms</span>
        </p>
      ))}
    </div>
  )
}

export default function ExperimentsTable({ dark }) {
  const [data, setData]     = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState('all')
  const [view, setView]       = useState('charts') // 'charts' | 'table'

  useEffect(() => {
    fetch('/api/experiments')
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const official = data.filter(r => /^E\d+/.test(r.run_id))
  const filtered = filter === 'all' ? official : official.filter(r => String(r.qos) === filter)

  const text   = dark ? '#e2e8f0' : '#0f172a'
  const muted  = dark ? '#94a3b8' : '#64748b'
  const border = dark ? '#1e2228' : '#e2e8f0'
  const cardBg = dark ? '#0d0f14' : '#fff'
  const rowAlt = dark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.02)'
  const rowHov = dark ? '#1a1f2e' : '#f8fafc'

  if (loading) return <p className="text-center py-12 animate-pulse" style={{ color: muted }}>Loading experiment data…</p>
  if (!official.length) return <p className="text-center py-12" style={{ color: muted }}>No experiment data found.</p>

  // ── chart data ──────────────────────────────────────────────────────────
  const lossRuns  = official.filter(r => r.network === '5% loss').sort((a,b) => a.qos - b.qos)
  const cleanRuns = official.filter(r => r.network === 'clean')

  // latency under loss (E10/E11/E12)
  const lossChart = lossRuns.map(r => ({
    name:    `QoS ${r.qos}`,
    'Avg Latency': r.avg_latency_ms,
    'P95 Latency': r.p95_latency_ms,
    qos: r.qos,
  }))

  // grouped: clean vs loss by QoS
  const compareChart = [0, 1, 2].map(q => {
    const clean = official.find(r => r.qos === q && r.network === 'clean' && r.n_slots === 10)
    const loss  = official.find(r => r.qos === q && r.network === '5% loss')
    return {
      name:   `QoS ${q}`,
      Clean:  clean?.avg_latency_ms ?? 0,
      '5% Loss': loss?.avg_latency_ms ?? 0,
      qos: q,
    }
  })

  // delivery rate (should all be 100%)
  const deliveryChart = official.slice(0,12).map(r => ({
    name: r.run_id.replace('_rep1',''),
    rate: r.delivery_pct,
    qos:  r.qos,
  }))

  const axisStyle = { fill: muted, fontSize: 11 }
  const gridCol   = dark ? '#1e2228' : '#f1f5f9'

  return (
    <div className="space-y-6">

      {/* ── top controls ── */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs uppercase tracking-wider font-bold" style={{ color: muted }}>Filter</span>
        {['all','0','1','2'].map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition-all ${
              filter === f
                ? f==='all'
                  ? (dark ? 'bg-slate-200 text-slate-900 border-slate-300' : 'bg-slate-800 text-white border-slate-700')
                  : QOS_COLORS[+f].badge
                : (dark ? 'border-slate-700 text-slate-400 hover:border-slate-500' : 'border-slate-300 text-slate-500 hover:border-slate-400')
            } bg-transparent`}>
            {f==='all' ? 'All' : `QoS ${f}`}
          </button>
        ))}
        <div className="ml-auto flex items-center rounded-lg overflow-hidden" style={{ border: `1px solid ${border}` }}>
          {['charts','table'].map(v => (
            <button key={v} onClick={() => setView(v)}
              className="px-3 py-1.5 text-xs font-medium capitalize transition-colors"
              style={{
                background: view===v ? (dark ? '#334155' : '#e2e8f0') : 'transparent',
                color: view===v ? text : muted,
              }}>
              {v === 'charts' ? '📊 Charts' : '📋 Table'}
            </button>
          ))}
        </div>
      </div>

      {/* ── KEY FINDINGS CARDS ── */}
      <div className="grid grid-cols-3 gap-4">
        <FindingCard color="#22c55e" label="Delivery Rate" value="100%" sub="All QoS · all conditions" dark={dark} />
        <FindingCard color="#38bdf8" label="Clean Network" value="< 1 ms" sub="Avg latency, all QoS levels" dark={dark} />
        <FindingCard color="#fb7185" label="QoS 2 under 5% loss" value="1.8×" sub="Slower than QoS 0 (79.7 vs 44.6 ms)" dark={dark} />
      </div>

      {/* ── CHARTS VIEW ── */}
      {view === 'charts' && (
        <div className="space-y-6">

          {/* row 1: two charts */}
          <div className="grid grid-cols-2 gap-4">

            {/* Latency under loss */}
            <ChartCard title="Avg Latency Under 5% Packet Loss" sub="E10 / E11 / E12 · 50 slots · 1 Hz" dark={dark}>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={lossChart} barSize={44}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridCol} vertical={false} />
                  <XAxis dataKey="name" tick={axisStyle} axisLine={false} tickLine={false} />
                  <YAxis tick={axisStyle} axisLine={false} tickLine={false} unit=" ms" width={52} />
                  <Tooltip content={<CustomTooltip dark={dark} />} cursor={{ fill: dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
                  <ReferenceLine y={50} stroke={dark ? '#334155' : '#cbd5e1'} strokeDasharray="4 4"
                    label={{ value: '50 ms', position: 'right', fill: muted, fontSize: 10 }} />
                  <Bar dataKey="Avg Latency" radius={[6,6,0,0]}>
                    {lossChart.map((e,i) => <Cell key={i} fill={QOS_COLORS[e.qos].chart} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* P95 under loss */}
            <ChartCard title="P95 Latency Under 5% Packet Loss" sub="Worst-case tail latency · 95th percentile" dark={dark}>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={lossChart} barSize={44}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridCol} vertical={false} />
                  <XAxis dataKey="name" tick={axisStyle} axisLine={false} tickLine={false} />
                  <YAxis tick={axisStyle} axisLine={false} tickLine={false} unit=" ms" width={52} />
                  <Tooltip content={<CustomTooltip dark={dark} />} cursor={{ fill: dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
                  <ReferenceLine y={220} stroke={dark ? '#334155' : '#cbd5e1'} strokeDasharray="4 4"
                    label={{ value: '220 ms', position: 'right', fill: muted, fontSize: 10 }} />
                  <Bar dataKey="P95 Latency" radius={[6,6,0,0]}>
                    {lossChart.map((e,i) => <Cell key={i} fill={QOS_COLORS[e.qos].chart} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          {/* row 2: clean vs loss comparison */}
          <ChartCard title="Clean Network vs 5% Packet Loss — Avg Latency" sub="Direct comparison across all QoS levels" dark={dark}>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={compareChart} barSize={32} barGap={6}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridCol} vertical={false} />
                <XAxis dataKey="name" tick={axisStyle} axisLine={false} tickLine={false} />
                <YAxis tick={axisStyle} axisLine={false} tickLine={false} unit=" ms" width={52} />
                <Tooltip content={<CustomTooltip dark={dark} />} cursor={{ fill: dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }} />
                <Legend wrapperStyle={{ fontSize: 11, color: muted, paddingTop: 8 }} />
                <Bar dataKey="Clean" fill="#34d399" radius={[4,4,0,0]} />
                <Bar dataKey="5% Loss" fill="#f87171" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          {/* row 3: delivery rate all experiments */}
          <ChartCard title="Delivery Rate — All 12 Experiments" sub="100% across all conditions — QoS level had no effect on reliability" dark={dark}>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={deliveryChart} barSize={26}>
                <CartesianGrid strokeDasharray="3 3" stroke={gridCol} vertical={false} />
                <XAxis dataKey="name" tick={{ ...axisStyle, fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis domain={[99, 100.2]} tick={axisStyle} axisLine={false} tickLine={false} unit="%" width={40} />
                <Tooltip cursor={{ fill: dark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' }}
                  formatter={(v) => [`${v}%`, 'Delivery Rate']}
                  contentStyle={{ background: dark ? '#1e2228' : '#fff', border: `1px solid ${border}`, borderRadius: 12, fontSize: 12, color: text }} />
                <ReferenceLine y={100} stroke="#22c55e" strokeDasharray="4 4"
                  label={{ value: '100%', position: 'right', fill: '#22c55e', fontSize: 10 }} />
                <Bar dataKey="rate" radius={[4,4,0,0]}>
                  {deliveryChart.map((e,i) => <Cell key={i} fill={QOS_COLORS[e.qos]?.chart ?? '#64748b'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {/* ── TABLE VIEW ── */}
      {view === 'table' && (
        <div className="overflow-x-auto rounded-xl" style={{ border: `1px solid ${border}` }}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider" style={{ color: muted, borderBottom: `1px solid ${border}` }}>
                {['Run','QoS','Slots','Rate','Network','Sent','Delivered','Delivery','Avg Lat','P95 Lat','Dupes'].map(h => (
                  <th key={h} className={`px-4 py-3 ${['Sent','Delivered','Delivery','Avg Lat','P95 Lat','Dupes'].includes(h) ? 'text-right' : 'text-left'} font-semibold`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.run_id}
                  className="transition-colors"
                  style={{ background: i%2===0 ? 'transparent' : rowAlt }}
                  onMouseEnter={e => e.currentTarget.style.background = rowHov}
                  onMouseLeave={e => e.currentTarget.style.background = i%2===0 ? 'transparent' : rowAlt}
                >
                  <td className="px-4 py-3 font-mono font-bold" style={{ color: text }}>{row.run_id.replace('_rep1','')}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-bold border ${QOS_COLORS[row.qos].badge}`}>
                      QoS {row.qos}
                    </span>
                  </td>
                  <td className="px-4 py-3" style={{ color: muted }}>{row.n_slots}</td>
                  <td className="px-4 py-3 font-mono" style={{ color: muted }}>{row.rate_hz} Hz</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${netBadge(row.network, dark)}`}>
                      {row.network}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: muted }}>{row.sent}</td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: muted }}>{row.delivered}</td>
                  <td className="px-4 py-3 text-right">
                    <span className="font-bold font-mono text-emerald-500">{row.delivery_pct.toFixed(0)}%</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold" style={{ color: latColor(row.avg_latency_ms) }}>
                    {row.avg_latency_ms != null ? `${row.avg_latency_ms} ms` : '—'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-semibold" style={{ color: latColor(row.p95_latency_ms) }}>
                    {row.p95_latency_ms != null ? `${row.p95_latency_ms} ms` : '—'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono" style={{ color: muted }}>{row.duplicates}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function ChartCard({ title, sub, children, dark }) {
  const bg     = dark ? '#111318' : '#f8fafc'
  const border = dark ? '#1e2228' : '#e2e8f0'
  const text   = dark ? '#e2e8f0' : '#0f172a'
  const muted  = dark ? '#64748b' : '#94a3b8'
  return (
    <div className="rounded-xl p-4" style={{ background: bg, border: `1px solid ${border}` }}>
      <p className="text-sm font-bold mb-0.5" style={{ color: text }}>{title}</p>
      <p className="text-xs mb-4" style={{ color: muted }}>{sub}</p>
      {children}
    </div>
  )
}

function FindingCard({ color, label, value, sub, dark }) {
  const bg     = dark ? '#111318' : '#f8fafc'
  const border = dark ? '#1e2228' : '#e2e8f0'
  const muted  = dark ? '#64748b' : '#94a3b8'
  return (
    <div className="rounded-xl p-5" style={{ background: bg, border: `1px solid ${border}`, borderTop: `3px solid ${color}` }}>
      <p className="text-xs uppercase tracking-wider font-semibold mb-2" style={{ color: muted }}>{label}</p>
      <p className="text-3xl font-black font-mono mb-1" style={{ color }}>{value}</p>
      <p className="text-xs" style={{ color: muted }}>{sub}</p>
    </div>
  )
}
