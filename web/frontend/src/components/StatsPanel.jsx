export default function StatsPanel({ summary, connected, events, dark }) {
  const { free = 0, occupied = 0, reserved = 0, total = 0 } = summary
  const freeP  = total ? Math.round(free     / total * 100) : 0
  const occP   = total ? Math.round(occupied / total * 100) : 0
  const resvP  = total ? Math.round(reserved / total * 100) : 0

  const text   = dark ? '#e2e8f0' : '#0f172a'
  const muted  = dark ? '#94a3b8' : '#64748b'
  const divCol = dark ? '#1e2228' : '#e5e7eb'

  return (
    <div className="space-y-5">

      {/* broker status */}
      <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-semibold"
        style={{
          background: connected ? (dark?'rgba(34,197,94,0.08)':'rgba(34,197,94,0.1)') : (dark?'rgba(239,68,68,0.08)':'rgba(239,68,68,0.1)'),
          border: `1px solid ${connected ? (dark?'rgba(34,197,94,0.25)':'rgba(34,197,94,0.4)') : (dark?'rgba(239,68,68,0.25)':'rgba(239,68,68,0.4)')}`,
          color: connected ? '#22c55e' : '#ef4444',
        }}>
        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
        {connected ? 'Live — broker connected' : 'Offline — broker unreachable'}
      </div>

      {/* big free count */}
      <div className="text-center py-2">
        <div className="text-5xl font-black font-mono" style={{ color: text }}>{free}</div>
        <div className="text-xs uppercase tracking-widest mt-1" style={{ color: muted }}>spaces available</div>
        {total > 0 && <div className="text-xs mt-0.5" style={{ color: dark?'#334155':'#d1d5db' }}>of {total} total</div>}
      </div>

      {/* ring chart */}
      {total > 0 && <OccupancyRing occupied={occupied} reserved={reserved} total={total} dark={dark} />}

      {/* stat bars */}
      <div className="space-y-2.5">
        <StatRow icon="●" label="Free"     value={free}     pct={freeP}  color="#22c55e" dark={dark} />
        <StatRow icon="■" label="Occupied" value={occupied} pct={occP}   color="#ef4444" dark={dark} />
        <StatRow icon="◆" label="Reserved" value={reserved} pct={resvP}  color="#f97316" dark={dark} />
      </div>

      <div style={{ borderTop: `1px solid ${divCol}` }} />

      {/* events */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold uppercase tracking-wider" style={{ color: muted }}>Live Events</span>
          <span className="text-xs" style={{ color: dark?'#334155':'#d1d5db' }}>{events.length}</span>
        </div>
        <EventList events={events} dark={dark} />
      </div>
    </div>
  )
}

function OccupancyRing({ occupied, reserved, total, dark }) {
  const sz = 96; const sw = 9; const r = (sz - sw) / 2
  const circ   = 2 * Math.PI * r
  const occD   = (occupied / total) * circ
  const resvD  = (reserved / total) * circ
  const pct    = Math.round(occupied / total * 100)
  const col    = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#22c55e'
  return (
    <div className="flex justify-center">
      <div className="relative">
        <svg width={sz} height={sz} className="-rotate-90">
          <circle cx={sz/2} cy={sz/2} r={r} fill="none" stroke={dark?'#1e2228':'#e5e7eb'} strokeWidth={sw} />
          <circle cx={sz/2} cy={sz/2} r={r} fill="none" stroke={col} strokeWidth={sw}
            strokeLinecap="round"
            strokeDasharray={`${occD} ${circ}`}
            className="transition-all duration-700" />
          {reserved > 0 && (
            <circle cx={sz/2} cy={sz/2} r={r} fill="none" stroke="#f97316" strokeWidth={sw}
              strokeLinecap="round"
              strokeDasharray={`${resvD} ${circ}`}
              strokeDashoffset={`${-occD}`}
              className="transition-all duration-700" />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-sm font-black font-mono" style={{ color: col }}>{pct}%</span>
          <span className="text-[9px]" style={{ color: dark?'#475569':'#9ca3af' }}>full</span>
        </div>
      </div>
    </div>
  )
}

function StatRow({ icon, label, value, pct, color, dark }) {
  const muted   = dark ? '#64748b' : '#94a3b8'
  const trackBg = dark ? '#1e2228' : '#f1f5f9'
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px]" style={{ color }}>{icon}</span>
          <span className="text-xs" style={{ color: muted }}>{label}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-bold font-mono" style={{ color }}>{value}</span>
          <span className="text-[10px]" style={{ color: dark?'#334155':'#d1d5db' }}>{pct}%</span>
        </div>
      </div>
      <div className="w-full h-1.5 rounded-full" style={{ background: trackBg }}>
        <div className="h-full rounded-full transition-all duration-500" style={{ width:`${pct}%`, background: color }} />
      </div>
    </div>
  )
}

function EventList({ events, dark }) {
  const muted = dark ? '#64748b' : '#94a3b8'
  if (!events.length) return <p className="text-xs text-center py-3" style={{ color: muted }}>No events yet</p>
  return (
    <div className="space-y-px max-h-44 overflow-y-auto">
      {events.map((e, i) => {
        const dot   = e.state==='FREE' ? '#22c55e' : e.state==='OCCUPIED' ? '#ef4444' : '#f97316'
        const label = e.state==='FREE' ? '#22c55e' : e.state==='OCCUPIED' ? '#ef4444' : '#f97316'
        const rowBg = i===0 ? (dark?'rgba(255,255,255,0.04)':'rgba(0,0,0,0.04)') : 'transparent'
        return (
          <div key={i} className="flex items-center gap-2 px-2 py-1 rounded text-xs" style={{ background: rowBg }}>
            <div className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: dot, opacity: i===0?1:0.5 }} />
            <span className="font-mono text-[10px] shrink-0" style={{ color: dark?'#475569':'#9ca3af' }}>{e.ts}</span>
            <span className="text-[10px] truncate" style={{ color: muted }}>{e.slot_id.replace('slot_','S')}</span>
            <span className="font-bold text-[10px] shrink-0" style={{ color: label }}>{e.state.slice(0,3)}</span>
          </div>
        )
      })}
    </div>
  )
}
