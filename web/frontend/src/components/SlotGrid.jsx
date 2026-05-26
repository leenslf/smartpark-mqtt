export default function SlotGrid({ slots }) {
  const entries = Object.entries(slots).sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))

  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-slate-500">
        <svg className="w-10 h-10 mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 00-3.213-9.193 2.056 2.056 0 00-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 00-10.026 0 1.106 1.106 0 00-.987 1.106v7.635m12-6.677v6.677m0 4.5v-4.5m0 0h-12" />
        </svg>
        <p className="text-sm">Waiting for sensor data…</p>
        <p className="text-xs mt-1 opacity-60">Start an experiment or the parking controller</p>
      </div>
    )
  }

  const cols = entries.length <= 10 ? 5 : entries.length <= 25 ? 7 : 10

  return (
    <div
      className="grid gap-2"
      style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
    >
      {entries.map(([slot_id, state]) => (
        <SlotCell key={slot_id} slot_id={slot_id} state={state} />
      ))}
    </div>
  )
}

function SlotCell({ slot_id, state }) {
  const cfg = {
    FREE:     { bg: 'bg-emerald-500/20', border: 'border-emerald-500/60', dot: 'bg-emerald-400', label: 'FREE',     text: 'text-emerald-300' },
    OCCUPIED: { bg: 'bg-red-500/20',     border: 'border-red-500/60',     dot: 'bg-red-400',     label: 'OCC',      text: 'text-red-300' },
    RESERVED: { bg: 'bg-orange-500/20',  border: 'border-orange-500/60',  dot: 'bg-orange-400',  label: 'RESV',     text: 'text-orange-300' },
  }[state] ?? { bg: 'bg-slate-700/30', border: 'border-slate-600/40', dot: 'bg-slate-500', label: state, text: 'text-slate-400' }

  const shortId = slot_id.replace('slot_', '').replace('parking_slot_', '')

  return (
    <div className={`relative rounded-lg border ${cfg.bg} ${cfg.border} p-2 flex flex-col items-center gap-1 transition-all duration-300 hover:scale-105`}>
      {/* parking space lines */}
      <div className="absolute inset-x-0 top-0 h-0.5 bg-current opacity-10 rounded-t-lg" />
      <div className="absolute inset-x-0 bottom-0 h-0.5 bg-current opacity-10 rounded-b-lg" />
      <span className="text-[10px] font-mono text-slate-500 leading-none">{shortId.padStart(2,'0')}</span>
      <div className={`w-2.5 h-2.5 rounded-full ${cfg.dot} shadow-lg`} style={{ boxShadow: `0 0 8px 2px ${cfg.dot.includes('emerald') ? '#34d399' : cfg.dot.includes('red') ? '#f87171' : '#fb923c'}40` }} />
      <span className={`text-[9px] font-bold tracking-wider ${cfg.text}`}>{cfg.label}</span>
    </div>
  )
}
