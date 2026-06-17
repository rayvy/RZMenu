import json
import queue
import select
import socket
import threading
import time

import bpy


_client = None
_timer_registered = False


def _drain_messages():
    global _timer_registered

    client = _client
    if not client or not client.is_running:
        _timer_registered = False
        return None

    drained = False
    while True:
        try:
            payload = client.inbox.get_nowait()
        except queue.Empty:
            break

        drained = True
        kind = payload.get("type", "message")
        text = payload.get("message", "")
        if kind == "signal":
            print(f"[RZM Bridge] SIGNAL: {text}")
        elif kind == "handshake_ack":
            print(f"[RZM Bridge] HANDSHAKE ACK: {text}")
        else:
            print(f"[RZM Bridge] {kind}: {text or payload}")

    if drained:
        return 0.1
    return 0.2


class BridgeClient:
    def __init__(self, host="127.0.0.1", port=39393):
        self.host = host
        self.port = int(port)
        self.inbox = queue.Queue()
        self._sock = None
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._buffer = b""
        self._last_heartbeat = 0.0
        self.is_running = False

    def start(self):
        self.stop()
        self._stop.clear()

        last_error = None
        sock = None
        for _ in range(20):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect((self.host, self.port))
                break
            except Exception as exc:
                last_error = exc
                try:
                    sock.close()
                except Exception:
                    pass
                sock = None
                time.sleep(0.25)

        if sock is None:
            raise ConnectionError(f"Bridge unavailable at {self.host}:{self.port} ({last_error})")

        sock.settimeout(None)
        self._sock = sock
        self.is_running = True
        self._last_heartbeat = time.monotonic()
        self._send_object({
            "type": "handshake",
            "client": "RZMenu",
            "message": "Blender bridge connected",
        })
        self._thread = threading.Thread(target=self._reader_loop, name="RZMenuBridgeClient", daemon=True)
        self._thread.start()

        global _timer_registered
        if not _timer_registered:
            bpy.app.timers.register(_drain_messages, persistent=True)
            _timer_registered = True

    def stop(self):
        self.is_running = False
        self._stop.set()

        sock = self._sock
        self._sock = None
        if sock:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                sock.close()
            except Exception:
                pass

        thread = self._thread
        self._thread = None
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def send_signal(self, message):
        self._send_object({
            "type": "signal",
            "message": message,
        })

    def send_heartbeat(self):
        self._send_object({
            "type": "heartbeat",
            "message": "ping",
            "time": time.time(),
        })

    def _send_object(self, obj):
        sock = self._sock
        if not sock or not self.is_running:
            return False

        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        with self._lock:
            try:
                sock.sendall(data)
                return True
            except Exception as exc:
                self.inbox.put({"type": "error", "message": str(exc)})
                self._stop.set()
                self.is_running = False
                return False

    def _reader_loop(self):
        try:
            while not self._stop.is_set() and self._sock:
                readable, _, _ = select.select([self._sock], [], [], 0.2)
                if readable:
                    chunk = self._sock.recv(4096)
                    if not chunk:
                        self.inbox.put({"type": "error", "message": "Bridge disconnected"})
                        break
                    self._buffer += chunk
                    while b"\n" in self._buffer:
                        line, self._buffer = self._buffer.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            payload = json.loads(line.decode("utf-8"))
                        except Exception as exc:
                            self.inbox.put({"type": "error", "message": f"Bad JSON: {exc}"})
                            continue
                        self.inbox.put(payload)

                now = time.monotonic()
                if now - self._last_heartbeat >= 1.0:
                    self._last_heartbeat = now
                    self.send_heartbeat()
        finally:
            self.is_running = False
            self._stop.set()


def get_client():
    return _client


def connect(host="127.0.0.1", port=39393):
    global _client
    if _client and _client.is_running:
        _client.stop()
    _client = BridgeClient(host=host, port=port)
    _client.start()
    return _client


def disconnect():
    global _client
    if _client:
        _client.stop()
        _client = None


def send_signal(message):
    client = _client
    if not client or not client.is_running:
        return False
    return client.send_signal(message)
