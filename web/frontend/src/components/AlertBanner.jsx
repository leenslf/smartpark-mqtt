import { useEffect, useState } from 'react'

const THRESHOLD = 0.9

export default function AlertBanner({ summary, dark }) {
  const { free = 0, occupied = 0, total = 0 } = summary
  const [dismissed, setDismissed] = useState(false)

  const ratio     = total > 0 ? occupied / total : 0
  const isAlert   = ratio >= THRESHOLD
  const isCrit    = ratio >= 0.98
  const pct       = Math.round(ratio * 100)

  useEffect(() => { if (!isAlert) setDismissed(false) }, [isAlert])

  if (!isAlert || dismissed || total === 0) return null

  const bg      = isCrit
    ? (dark ? 'rgba(127,29,29,0.5)' : 'rgba(254,226,226,0.95)')
    : (dark ? 'rgba(120,53,15,0.45)': 'rgba(255,251,235,0.95)')
  const bdr     = isCrit ? (dark ? '#991b1b' : '#fca5a5') : (dark ? '#92400e' : '#fcd34d')
  const hd      = isCrit ? (dark ? '#fca5a5' : '#991b1b') : (dark ? '#fcd34d' : '#92400e')
  const sub     = dark ? '#94a3b8' : '#6b7280'
  const barFill = isCrit ? '#ef4444' : '#f59e0b'

  return (
    <div className="relative overflow-hidden rounded-xl px-5 py-3 flex items-center gap-4"
      style={{ background: bg, border: `1px solid ${bdr}` }}>
      <div className="absolute inset-0 opacity-5 animate-pulse" style={{ background: barFill }} />
      <div className="shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-xl"
        style={{ background: `${barFill}22`, color: barFill }}>⚠</div>
      <div className="flex-1 relative z-10">
        <p className="text-sm font-bold" style={{ color: hd }}>
          {isCrit ? 'CRITICAL — Parking lot nearly full' : 'HIGH OCCUPANCY ALERT'}
        </p>
        <p className="text-xs mt-0.5" style={{ color: sub }}>
          {occupied} of {total} spaces occupied ({pct}%) — {free} free space{free !== 1 ? 's' : ''} remaining
        </p>
      </div>
      <div className="hidden sm:flex flex-col items-end gap-1 relative z-10">
        <span className="text-xl font-black font-mono" style={{ color: barFill }}>{pct}%</span>
        <div className="w-20 h-1.5 rounded-full" style={{ background: dark ? '#1e2228' : '#e5e7eb' }}>
          <div className="h-full rounded-full transition-all duration-500" style={{ width:`${pct}%`, background: barFill }} />
        </div>
      </div>
      <button onClick={() => setDismissed(true)}
        className="relative z-10 w-7 h-7 rounded-full flex items-center justify-center text-lg transition-colors"
        style={{ color: sub }}>×</button>
    </div>
  )
}
