"""Web server - Starlette ASGI with WebSocket for real-time agent visibility."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from gamba.interfaces.base import BaseInterface
from gamba.core.message_bus import EventType, Event

if TYPE_CHECKING:
    from gamba.core.message_bus import MessageBus
    from gamba.state.schemas import Config

logger = logging.getLogger(__name__)


class WebServer(BaseInterface):
    """Starlette web server with WebSocket for real-time updates."""

    def __init__(self, bus: "MessageBus", config: "Config") -> None:
        super().__init__(bus, config)
        iface = config.interfaces.get("web")
        self.port = iface.port if iface else 8420
        self._ws_clients: set = set()
        self._app = None

    async def start(self) -> None:
        try:
            from starlette.applications import Starlette
            from starlette.routing import Route, WebSocketRoute
            from starlette.responses import HTMLResponse, JSONResponse, FileResponse
            from starlette.websockets import WebSocket
            from starlette.staticfiles import StaticFiles
            import uvicorn
        except ImportError:
            logger.error("starlette/uvicorn not installed. Run: pip install starlette uvicorn")
            return

        server_self = self

        async def homepage(request):
            """Serve the web UI or a minimal fallback."""
            dist_dir = Path(__file__).parent.parent.parent.parent / "web-ui" / "dist"
            index = dist_dir / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return HTMLResponse(_FALLBACK_HTML)

        async def api_chat(request):
            body = await request.json()
            message = body.get("message", "")
            if not message:
                return JSONResponse({"error": "No message"}, status_code=400)
            await server_self.send_user_input(message, source="web")
            return JSONResponse({"status": "sent"})

        async def api_agents(request):
            return JSONResponse({"agents": list(server_self._agent_names())})

        async def ws_endpoint(websocket: WebSocket):
            await websocket.accept()
            server_self._ws_clients.add(websocket)
            logger.info(f"WebSocket client connected ({len(server_self._ws_clients)} total)")
            try:
                while True:
                    data = await websocket.receive_text()
                    msg = json.loads(data)
                    if msg.get("type") == "chat":
                        await server_self.send_user_input(
                            msg.get("message", ""), source="web"
                        )
            except Exception:
                pass
            finally:
                server_self._ws_clients.discard(websocket)
                logger.info(f"WebSocket client disconnected ({len(server_self._ws_clients)} total)")

        routes = [
            Route("/", homepage),
            Route("/api/chat", api_chat, methods=["POST"]),
            Route("/api/agents", api_agents),
            WebSocketRoute("/ws", ws_endpoint),
        ]

        # Serve static files from web-ui/dist if it exists
        dist_dir = Path(__file__).parent.parent.parent.parent / "web-ui" / "dist"
        if dist_dir.exists():
            routes.append(Route("/{path:path}", homepage))

        app = Starlette(routes=routes)
        self._app = app

        # Subscribe to all events for WebSocket broadcast
        self.bus.subscribe_all(self._broadcast_event)

        config = uvicorn.Config(app, host="0.0.0.0", port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        logger.info(f"Web server starting on http://0.0.0.0:{self.port}")
        await server.serve()

    def _agent_names(self):
        """Get agent names - walk up to find orchestrator."""
        return []

    async def _broadcast_event(self, event: Event) -> None:
        """Send all bus events to WebSocket clients as JSON."""
        if not self._ws_clients:
            return
        payload = json.dumps({
            "type": str(event.type),
            "source": event.source,
            "data": {k: str(v)[:500] for k, v in event.data.items()},
            "timestamp": event.timestamp.isoformat(),
        })
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    async def on_response(self, event: Event) -> None:
        pass  # Handled by _broadcast_event

    async def on_agent_step(self, event: Event) -> None:
        pass

    async def on_agent_message(self, event: Event) -> None:
        pass


_FALLBACK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GAMBA</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #09090b; color: #e4e4e7; font-family: 'SF Mono', 'Fira Code', monospace; }
  #app { max-width: 800px; margin: 0 auto; padding: 20px; height: 100vh; display: flex; flex-direction: column; }
  h1 { color: #06b6d4; margin-bottom: 4px; font-size: 1.5rem; }
  .subtitle { color: #71717a; margin-bottom: 20px; font-size: 0.85rem; }
  #log { flex: 1; overflow-y: auto; padding: 12px; background: #18181b; border-radius: 8px;
         border: 1px solid #27272a; margin-bottom: 12px; font-size: 0.85rem; line-height: 1.6; }
  .event { margin-bottom: 4px; }
  .event .ts { color: #52525b; }
  .event .src { color: #06b6d4; font-weight: bold; }
  .event .msg { color: #a1a1aa; }
  .event.response .msg { color: #e4e4e7; }
  .event.step .src { color: #71717a; }
  .event.delegation .src { color: #eab308; }
  .event.error .msg { color: #ef4444; }
  #input-row { display: flex; gap: 8px; }
  #input { flex: 1; background: #18181b; border: 1px solid #27272a; border-radius: 6px;
           color: #e4e4e7; padding: 10px 14px; font-family: inherit; font-size: 0.9rem; outline: none; }
  #input:focus { border-color: #06b6d4; }
  #send { background: #06b6d4; color: #09090b; border: none; border-radius: 6px;
          padding: 10px 20px; font-weight: bold; cursor: pointer; font-family: inherit; }
  #send:hover { background: #22d3ee; }
  #status { color: #52525b; font-size: 0.75rem; margin-top: 8px; text-align: center; }
  .connected { color: #22c55e !important; }
</style>
</head>
<body>
<div id="app">
  <h1>GAMBA</h1>
  <p class="subtitle">Multi-Agent Framework</p>
  <div id="log"></div>
  <div id="input-row">
    <input id="input" type="text" placeholder="Type a message..." autocomplete="off" />
    <button id="send">Send</button>
  </div>
  <p id="status">Connecting...</p>
</div>
<script>
const log = document.getElementById('log');
const input = document.getElementById('input');
const send = document.getElementById('send');
const status = document.getElementById('status');
let ws;

function connect() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => { status.textContent = 'Connected'; status.classList.add('connected'); };
  ws.onclose = () => { status.textContent = 'Disconnected - reconnecting...'; status.classList.remove('connected'); setTimeout(connect, 3000); };
  ws.onmessage = (e) => {
    const evt = JSON.parse(e.data);
    addEvent(evt);
  };
}

function addEvent(evt) {
  const div = document.createElement('div');
  const ts = new Date(evt.timestamp).toLocaleTimeString();
  let cls = 'event';
  let msg = '';

  switch(evt.type) {
    case 'orchestrator.response':
      cls += ' response';
      msg = evt.data.response || '';
      break;
    case 'orchestrator.plan':
      cls += ' delegation';
      msg = 'Delegating: ' + (evt.data.plan || '');
      break;
    case 'agent.spawned':
      msg = 'Started: ' + (evt.data.task || '');
      break;
    case 'agent.step':
      cls += ' step';
      msg = evt.data.action || ('step ' + (evt.data.step || '') + ': ' + (evt.data.response || '').slice(0,100));
      break;
    case 'agent.message':
      cls += ' delegation';
      msg = '-> ' + (evt.data.target || '') + ': ' + (evt.data.message || '');
      break;
    case 'agent.completed':
      msg = 'Done: ' + (evt.data.answer || '').slice(0,100);
      break;
    case 'agent.error':
      cls += ' error';
      msg = 'Error: ' + (evt.data.error || '');
      break;
    default:
      msg = evt.data.message || JSON.stringify(evt.data).slice(0,200);
  }

  div.className = cls;
  div.innerHTML = `<span class="ts">${ts}</span> <span class="src">[${evt.source}]</span> <span class="msg">${escapeHtml(msg)}</span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function escapeHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function sendMsg() {
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== 1) return;
  ws.send(JSON.stringify({ type: 'chat', message: text }));
  const div = document.createElement('div');
  div.className = 'event';
  div.innerHTML = `<span class="ts">${new Date().toLocaleTimeString()}</span> <span class="src">[you]</span> <span class="msg">${escapeHtml(text)}</span>`;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
  input.value = '';
}

send.onclick = sendMsg;
input.onkeydown = (e) => { if (e.key === 'Enter') sendMsg(); };
connect();
input.focus();
</script>
</body>
</html>"""
