export default function EventFeed({ events }) {
  if (events.length === 0) {
    return <p className="text-slate-600 text-sm text-center py-6">No events yet</p>
  }

  return (
    <div className="space-y-0.5 overflow-y-auto max-h-64 font-mono text-xs">
      {events.map((e, i) => {
        const color = e.state === 'FREE' ? 'text-emerald-400' : e.state === 'OCCUPIED' ? 'text-red-400' : 'text-orange-400'
        const bg = i === 0 ? 'bg-slate-700/40' : ''
        return (
          <div key={i} className={`flex items-center gap-2 px-2 py-1 rounded ${bg}`}>
            <span className="text-slate-600 shrink-0">{e.ts}</span>
            <span className="text-slate-400 shrink-0">{e.slot_id}</span>
            <span className={`font-bold ${color}`}>→ {e.state}</span>
          </div>
        )
      })}
    </div>
  )
}
