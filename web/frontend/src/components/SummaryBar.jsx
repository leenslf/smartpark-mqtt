export default function SummaryBar({ summary, connected }) {
  const total = summary.total || 0
  const free = summary.free || 0
  const occupied = summary.occupied || 0
  const reserved = summary.reserved || 0
  const freePercent = total ? Math.round((free / total) * 100) : 0

  return (
    <div className="flex items-center gap-4 flex-wrap">
      <Stat label="Free" value={free} color="text-emerald-400" icon="●" />
      <Stat label="Occupied" value={occupied} color="text-red-400" icon="■" />
      <Stat label="Reserved" value={reserved} color="text-orange-400" icon="◆" />
      <Stat label="Total" value={total} color="text-slate-300" icon="○" />
      {total > 0 && (
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-xs text-slate-500">Availability</span>
          <div className="w-24 h-2 bg-slate-700 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-500"
              style={{ width: `${freePercent}%` }}
            />
          </div>
          <span className="text-xs font-mono text-emerald-400">{freePercent}%</span>
        </div>
      )}
      <div className="flex items-center gap-1.5">
        <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
        <span className={`text-xs font-medium ${connected ? 'text-emerald-400' : 'text-red-400'}`}>
          {connected ? 'LIVE' : 'OFFLINE'}
        </span>
      </div>
    </div>
  )
}

function Stat({ label, value, color, icon }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`text-xs ${color} opacity-70`}>{icon}</span>
      <span className={`text-lg font-bold font-mono ${color}`}>{value}</span>
      <span className="text-xs text-slate-500 uppercase tracking-wider">{label}</span>
    </div>
  )
}
