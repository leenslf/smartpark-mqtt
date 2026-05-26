"""SmartPark MQTT — FastAPI backend with WebSocket bridge."""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ── paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent.parent
DB_PATH = ROOT / "data" / "experiment.db"
LOG_FILES = {
    "controller": ROOT / "data" / "ctrl.log",
    "experiments": ROOT / "data" / "experiment_run.log",
    "e10_e12": ROOT / "data" / "e10_e12_run.log",
}

# ── app ────────────────────────────────────────────────────────────────────
app = FastAPI(title="SmartPark MQTT API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("smartpark")

# ── websocket manager ──────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)


manager = ConnectionManager()

# ── slot state cache ───────────────────────────────────────────────────────
slot_states: dict[str, str] = {}
summary_state: dict[str, int] = {"free": 0, "occupied": 0, "reserved": 0, "total": 0}
loop: asyncio.AbstractEventLoop | None = None

# ── mqtt bridge ────────────────────────────────────────────────────────────
def on_connect(client: mqtt.Client, userdata: Any, flags: Any, rc: int, props: Any = None) -> None:
    log.info("MQTT connected rc=%s", rc)
    client.subscribe("parking/telemetry/#", qos=0)
    client.subscribe("parking/system/summary", qos=0)


def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
    global loop
    try:
        payload = json.loads(msg.payload.decode())
    except Exception:
        return

    if msg.topic.startswith("parking/telemetry/"):
        slot_id = payload.get("slot_id", msg.topic.split("/")[-1])
        state = payload.get("state", "FREE")
        slot_states[slot_id] = state
        event = {"type": "slot", "slot_id": slot_id, "state": state}
    elif msg.topic == "parking/system/summary":
        summary_state.update(payload)
        event = {"type": "summary", **payload}
    else:
        return

    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(manager.broadcast(event), loop)


def start_mqtt() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect("localhost", 1883, 60)
        client.loop_forever()
    except Exception as exc:
        log.warning("MQTT unavailable: %s", exc)


@app.on_event("startup")
async def startup() -> None:
    global loop
    loop = asyncio.get_event_loop()
    t = threading.Thread(target=start_mqtt, daemon=True)
    t.start()


# ── websocket endpoint ─────────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await manager.connect(ws)
    # send current snapshot immediately on connect
    await ws.send_json({"type": "snapshot", "slots": slot_states, "summary": summary_state})
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── REST: experiment results ───────────────────────────────────────────────
def _read_db() -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        runs = conn.execute(
            "SELECT run_id, qos, n_slots, transition_rate, duration_s, "
            "network_condition, loss_pct FROM runs ORDER BY started_at"
        ).fetchall()
        results = []
        for run in runs:
            rid = run["run_id"]
            sent = conn.execute("SELECT COUNT(*) FROM sent WHERE run_id=?", (rid,)).fetchone()[0]
            rrows = conn.execute(
                "SELECT msg_id, sent_ts, recv_ts, is_duplicate FROM received WHERE run_id=?",
                (rid,),
            ).fetchall()
            first: dict[str, Any] = {}
            dupes = 0
            for r in rrows:
                if r["is_duplicate"]:
                    dupes += 1
                first.setdefault(r["msg_id"], r)
            unique = len(first)
            lats = [r["recv_ts"] - r["sent_ts"] for r in first.values() if r["recv_ts"] and r["sent_ts"]]
            avg_lat = round(sum(lats) / len(lats), 1) if lats else None
            p95 = round(sorted(lats)[int(0.95 * (len(lats) - 1))], 1) if lats else None
            results.append({
                "run_id": rid,
                "qos": run["qos"],
                "n_slots": run["n_slots"],
                "rate_hz": run["transition_rate"],
                "network": run["network_condition"].replace("loss_5pct", "5% loss"),
                "duration_s": run["duration_s"],
                "sent": sent,
                "delivered": unique,
                "delivery_pct": 100.0 if sent > 0 else 0,
                "avg_latency_ms": avg_lat,
                "p95_latency_ms": p95,
                "duplicates": dupes,
                "out_of_order": 0,
            })
        return results
    finally:
        conn.close()


@app.get("/api/experiments")
def get_experiments():
    return _read_db()


# ── REST: logs ─────────────────────────────────────────────────────────────
@app.get("/api/logs/{name}")
def get_log(name: str):
    path = LOG_FILES.get(name)
    if not path or not path.exists():
        return {"lines": [], "error": f"Log '{name}' not found"}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"lines": lines[-500:]}  # last 500 lines


@app.get("/api/logs")
def list_logs():
    return [{"name": k, "exists": v.exists()} for k, v in LOG_FILES.items()]


# ── REST: summary ──────────────────────────────────────────────────────────
@app.get("/api/summary")
def get_summary():
    return summary_state


@app.get("/api/slots")
def get_slots():
    return slot_states
