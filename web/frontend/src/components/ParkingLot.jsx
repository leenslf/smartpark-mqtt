const SPACES_PER_ROW = (total) => {
  if (total <= 10) return 5
  if (total <= 20) return 5
  if (total <= 30) return 6
  return 10
}

function Car({ state, dark }) {
  const body   = state === 'OCCUPIED' ? '#dc2626' : '#ea580c'
  const shine  = state === 'OCCUPIED' ? 'rgba(255,100,100,0.18)' : 'rgba(255,160,80,0.18)'
  const glass  = dark ? 'rgba(15,20,30,0.7)' : 'rgba(10,15,25,0.65)'
  const wheel  = dark ? '#111' : '#1a1a1a'
  const light1 = state === 'OCCUPIED' ? '#fde68a' : '#fed7aa'

  return (
    <svg viewBox="0 0 32 56" className="drop-shadow-md" style={{ width: '52%', height: '52%' }}>
      {/* shadow under car */}
      <ellipse cx="16" cy="52" rx="12" ry="3" fill="rgba(0,0,0,0.28)" />
      {/* body */}
      <rect x="3" y="6" width="26" height="44" rx="7" fill={body} />
      {/* roof shine */}
      <rect x="7" y="10" width="18" height="22" rx="4" fill={shine} />
      {/* windshield */}
      <rect x="7" y="10" width="18" height="12" rx="3" fill={glass} />
      {/* rear window */}
      <rect x="7" y="34" width="18" height="9"  rx="3" fill={glass} />
      {/* front lights */}
      <rect x="4"  y="6"  width="6" height="3" rx="1.5" fill={light1} opacity="0.9" />
      <rect x="22" y="6"  width="6" height="3" rx="1.5" fill={light1} opacity="0.9" />
      {/* rear lights */}
      <rect x="4"  y="47" width="6" height="3" rx="1.5" fill="#f87171" opacity="0.85" />
      <rect x="22" y="47" width="6" height="3" rx="1.5" fill="#f87171" opacity="0.85" />
      {/* wheels */}
      <rect x="0"  y="11" width="4" height="10" rx="2" fill={wheel} />
      <rect x="28" y="11" width="4" height="10" rx="2" fill={wheel} />
      <rect x="0"  y="35" width="4" height="10" rx="2" fill={wheel} />
      <rect x="28" y="35" width="4" height="10" rx="2" fill={wheel} />
      {/* center line detail */}
      <rect x="14" y="24" width="4" height="7" rx="1" fill="rgba(0,0,0,0.12)" />
    </svg>
  )
}

function ParkingSpace({ slot_id, state, dark }) {
  const num = slot_id.replace(/[^0-9]/g, '') || slot_id

  // dark theme colours
  const dk = {
    FREE:     { bg: '#181d18', border: 'rgba(255,255,255,0.07)', glow: 'none', numCol: 'rgba(255,255,255,0.18)' },
    OCCUPIED: { bg: '#1f1414', border: 'rgba(239,68,68,0.25)',   glow: 'inset 0 0 10px rgba(239,68,68,0.15)', numCol: 'rgba(239,68,68,0.5)' },
    RESERVED: { bg: '#1f1a12', border: 'rgba(249,115,22,0.3)',   glow: 'inset 0 0 10px rgba(249,115,22,0.15)', numCol: 'rgba(249,115,22,0.5)' },
  }

  // light theme colours
  const lt = {
    FREE:     { bg: '#e8ede8', border: 'rgba(0,0,0,0.12)',       glow: 'none', numCol: 'rgba(0,0,0,0.25)' },
    OCCUPIED: { bg: '#fde8e8', border: 'rgba(220,38,38,0.35)',   glow: 'inset 0 0 10px rgba(220,38,38,0.1)',  numCol: 'rgba(220,38,38,0.6)' },
    RESERVED: { bg: '#fef0e4', border: 'rgba(234,88,12,0.35)',   glow: 'inset 0 0 10px rgba(234,88,12,0.1)',  numCol: 'rgba(234,88,12,0.6)' },
  }

  const theme = dark ? dk : lt
  const c = theme[state] ?? (dark ? dk.FREE : lt.FREE)

  return (
    <div
      className="relative flex flex-col items-center justify-between transition-all duration-400"
      style={{
        minHeight: '88px',
        background: c.bg,
        borderLeft:   `1px solid ${c.border}`,
        borderRight:  `1px solid ${c.border}`,
        boxShadow:    c.glow,
      }}
    >
      {/* top painted line */}
      <div className="w-full" style={{ height: '2px', background: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.12)' }} />

      {/* content area */}
      <div className="flex-1 flex flex-col items-center justify-center w-full gap-0.5 py-1">
        {state !== 'FREE'
          ? <Car state={state} dark={dark} />
          : (
            <div className="flex flex-col items-center gap-1">
              <div className="w-5 h-5 rounded-full flex items-center justify-center"
                style={{ border: '1.5px solid rgba(34,197,94,0.4)' }}>
                <div className="w-1.5 h-1.5 rounded-full" style={{ background: 'rgba(34,197,94,0.5)' }} />
              </div>
            </div>
          )
        }
        {state === 'RESERVED' && (
          <span className="text-[8px] font-bold mt-0.5" style={{ color: 'rgba(234,88,12,0.8)' }}>RESERVED</span>
        )}
      </div>

      {/* slot number */}
      <div className="w-full text-center pb-1 text-[9px] font-mono font-semibold"
        style={{ color: c.numCol }}>
        {num.padStart(2, '0')}
      </div>

      {/* bottom painted line */}
      <div className="w-full" style={{ height: '2px', background: dark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.12)' }} />
    </div>
  )
}

function Lane({ dark }) {
  const asphalt = dark ? '#111315' : '#c8cdd3'
  const dashCol = dark ? 'rgba(250,204,21,0.22)' : 'rgba(180,130,0,0.35)'
  return (
    <div className="relative w-full flex items-center" style={{ height: '34px', background: asphalt }}>
      {/* dashed yellow centre */}
      <div className="relative w-full flex items-center gap-1.5 px-3">
        {Array.from({ length: 30 }).map((_, i) => (
          <div key={i} className="flex-1 rounded-full" style={{ height: '2px', background: dashCol }} />
        ))}
      </div>
    </div>
  )
}

export default function ParkingLot({ slots, dark }) {
  const entries = Object.entries(slots).sort(([a], [b]) =>
    a.localeCompare(b, undefined, { numeric: true })
  )

  const outerBg     = dark ? '#141618' : '#b8bfc7'
  const cardBorder  = dark ? '#1e2228' : '#9aa3ae'
  const headerBg    = dark ? '#0f1011' : '#d0d6dc'
  const headerBorder= dark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.1)'
  const textMuted   = dark ? '#64748b' : '#6b7280'
  const textDim     = dark ? '#334155' : '#9ca3af'

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4" style={{ color: textMuted }}>
        <svg className="w-12 h-12 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 00-3.213-9.193 2.056 2.056 0 00-1.58-.86H14.25" />
        </svg>
        <div className="text-center">
          <p className="font-semibold">Waiting for sensor data</p>
          <p className="text-sm mt-1 opacity-60">Run an experiment or start the parking controller</p>
          <code className="mt-3 block text-xs rounded-lg px-4 py-2"
            style={{ background: dark ? '#1e2228' : '#e2e8f0', color: '#0ea5e9', border: `1px solid ${cardBorder}` }}>
            .venv\Scripts\python.exe -m experiments.experiment_controller --qos 0 --n-slots 10 --duration 120
          </code>
        </div>
      </div>
    )
  }

  const perRow = SPACES_PER_ROW(entries.length)
  const rows = []
  for (let i = 0; i < entries.length; i += perRow) rows.push(entries.slice(i, i + perRow))

  const sections = []
  for (let i = 0; i < rows.length; i++) {
    sections.push({ type: 'row', data: rows[i] })
    if (i < rows.length - 1) sections.push({ type: 'lane' })
  }

  return (
    <div className="rounded-xl overflow-hidden"
      style={{ background: outerBg, border: `1px solid ${cardBorder}` }}>

      {/* header */}
      <div className="flex items-center justify-between px-4 py-2"
        style={{ background: headerBg, borderBottom: `1px solid ${headerBorder}` }}>
        <div className="flex items-center gap-1.5 text-[10px] font-mono font-bold tracking-widest uppercase" style={{ color: '#22c55e' }}>
          <span>▶</span> ENTRANCE
        </div>
        <div className="text-[10px] font-mono" style={{ color: textDim }}>{entries.length} spaces</div>
        <div className="flex items-center gap-1.5 text-[10px] font-mono font-bold tracking-widest uppercase" style={{ color: '#ef4444' }}>
          EXIT <span>▶</span>
        </div>
      </div>

      {/* lot */}
      <div className="p-2.5 space-y-0">
        {sections.map((s, i) =>
          s.type === 'lane'
            ? <Lane key={`lane-${i}`} dark={dark} />
            : (
              <div key={`row-${i}`} className="grid"
                style={{ gridTemplateColumns: `repeat(${perRow}, minmax(0, 1fr))` }}>
                {s.data.map(([slot_id, state]) => (
                  <ParkingSpace key={slot_id} slot_id={slot_id} state={state} dark={dark} />
                ))}
                {Array.from({ length: perRow - s.data.length }).map((_, j) => (
                  <div key={`empty-${j}`} style={{ minHeight: '88px', background: outerBg }} />
                ))}
              </div>
            )
        )}
      </div>

      {/* footer legend */}
      <div className="flex items-center justify-center gap-6 px-4 py-2"
        style={{ background: headerBg, borderTop: `1px solid ${headerBorder}` }}>
        <LegendDot color="#22c55e" label="Free"     dim={textDim} />
        <LegendDot color="#dc2626" label="Occupied" dim={textDim} />
        <LegendDot color="#ea580c" label="Reserved" dim={textDim} />
      </div>
    </div>
  )
}

function LegendDot({ color, label, dim }) {
  return (
    <div className="flex items-center gap-1.5 text-[10px] font-medium" style={{ color: dim }}>
      <div className="w-2 h-2 rounded-full" style={{ background: color }} />
      {label}
    </div>
  )
}
