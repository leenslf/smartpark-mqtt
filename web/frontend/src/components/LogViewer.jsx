import { useEffect, useRef, useState } from 'react'

const LOG_OPTIONS = [
  { key: 'controller', label: 'Controller' },
  { key: 'experiments', label: 'Experiments' },
  { key: 'e10_e12', label: 'E10–E12 (loss)' },
]

export default function LogViewer({ dark }) {
  const [active, setActive] = useState('experiments')
  const [lines, setLines] = useState([])
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const bottomRef = useRef(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(`/api/logs/${active}`)
      .then(r => r.json())
      .then(d => {
        if (d.error) setError(d.error)
        else setLines(d.lines || [])
        setLoading(false)
      })
      .catch(e => { setError(String(e)); setLoading(false) })
  }, [active])

  useEffect(() => {
    if (autoScroll) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, autoScroll])

  const termBg  = dark ? '#0d0f14' : '#1e2228'
  const termBdr = dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.15)'
  const btnAct  = dark ? '#334155' : '#475569'
  const btnIdle = dark ? '#1e2228' : '#f1f5f9'
  const btnActTx = '#ffffff'
  const btnIdlTx = dark ? '#64748b' : '#94a3b8'

  function lineColor(line) {
    if (/error|exception|traceback|failed/i.test(line)) return '#f87171'
    if (/warn/i.test(line)) return '#fbbf24'
    if (/done|success|complete|100%/i.test(line)) return '#34d399'
    if (/\[E\d+\]|run_id|qos/i.test(line)) return '#38bdf8'
    return dark ? '#94a3b8' : '#cbd5e1'
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {LOG_OPTIONS.map(o => (
          <button key={o.key} onClick={() => setActive(o.key)}
            className="px-3 py-1 rounded-lg text-xs font-medium transition-all"
            style={{ background: active===o.key ? btnAct : btnIdle, color: active===o.key ? btnActTx : btnIdlTx }}>
            {o.label}
          </button>
        ))}
        <label className="ml-auto flex items-center gap-1.5 text-xs cursor-pointer" style={{ color: btnIdlTx }}>
          <input type="checkbox" checked={autoScroll} onChange={e => setAutoScroll(e.target.checked)} className="accent-sky-500" />
          Auto-scroll
        </label>
      </div>

      <div className="rounded-xl h-80 overflow-y-auto font-mono text-xs p-4 space-y-0.5"
        style={{ background: termBg, border: `1px solid ${termBdr}` }}>
        {loading && <p className="text-slate-600 animate-pulse">Loading…</p>}
        {error && <p className="text-red-400">{error}</p>}
        {!loading && !error && lines.length === 0 && (
          <p className="text-slate-600">
            {active === 'controller'
              ? 'ctrl.log is empty — the controller writes here only when started via run_stack.py. Switch to Experiments for live log data.'
              : 'Log file is empty.'}
          </p>
        )}
        {lines.map((line, i) => (
          <div key={i} style={{ color: lineColor(line) }}>{line}</div>
        ))}
        <div ref={bottomRef} />
      </div>

      <p className="text-xs" style={{ color: dark ? '#334155' : '#9ca3af' }}>{lines.length} lines shown (last 500)</p>
    </div>
  )
}
