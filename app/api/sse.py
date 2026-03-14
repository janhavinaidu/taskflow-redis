import json
import queue
import threading
from flask import Response, stream_with_context


class EventBus:
    """
    Central pub/sub bus. Workers publish events here.
    SSE endpoint subscribes and streams them to the browser.
    """
    def __init__(self):
        self._listeners: list[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q = queue.Queue(maxsize=50)
        with self._lock:
            self._listeners.append(q)
        return q

    def unsubscribe(self, q: queue.Queue):
        with self._lock:
            if q in self._listeners:
                self._listeners.remove(q)

    def publish(self, event_type: str, data: dict):
        payload = json.dumps({"event": event_type, "data": data})
        with self._lock:
            dead = []
            for q in self._listeners:
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._listeners.remove(q)


def sse_stream(event_bus: EventBus):
    """Generator that yields SSE-formatted events to the client."""
    q = event_bus.subscribe()
    try:
        while True:
            try:
                payload = q.get(timeout=20)
                yield f"data: {payload}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"  # keep connection alive
    except GeneratorExit:
        event_bus.unsubscribe(q)


def create_sse_blueprint(event_bus: EventBus):
    from flask import Blueprint
    bp = Blueprint("sse", __name__)

    @bp.route("/events")
    def events():
        return Response(
            stream_with_context(sse_stream(event_bus)),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            }
        )

    return bp