import { useEffect, useRef, useState, useCallback } from 'react'

const WS_URL = `ws://${window.location.host}/ws`

export function useSmartPark() {
  const [slots, setSlots] = useState({})
  const [summary, setSummary] = useState({ free: 0, occupied: 0, reserved: 0, total: 0 })
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState([])
  const ws = useRef(null)
  const reconnectTimer = useRef(null)

  const addEvent = useCallback((slot_id, state) => {
    const ts = new Date().toLocaleTimeString('en-GB', { hour12: false })
    setEvents(prev => [{slot_id, state, ts}, ...prev].slice(0, 80))
  }, [])

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return
    const socket = new WebSocket(WS_URL)

    socket.onopen = () => setConnected(true)

    socket.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'snapshot') {
        setSlots(msg.slots || {})
        setSummary(msg.summary || {})
      } else if (msg.type === 'slot') {
        setSlots(prev => ({ ...prev, [msg.slot_id]: msg.state }))
        addEvent(msg.slot_id, msg.state)
      } else if (msg.type === 'summary') {
        setSummary({ free: msg.free, occupied: msg.occupied, reserved: msg.reserved, total: msg.total })
      }
    }

    socket.onclose = () => {
      setConnected(false)
      reconnectTimer.current = setTimeout(connect, 2000)
    }

    socket.onerror = () => socket.close()
    ws.current = socket
  }, [addEvent])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      ws.current?.close()
    }
  }, [connect])

  return { slots, summary, connected, events }
}
