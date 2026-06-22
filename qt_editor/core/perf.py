# RZMenu/qt_editor/core/perf.py
"""Small opt-in performance and event revision monitor for the Qt editor.

The monitor is intentionally passive: it records timings and signal activity
without changing refresh behavior. Enable with environment variable
``RZM_QT_PERF=1`` before launching Blender.
"""

from __future__ import annotations

from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass
import os
import time


def _env_enabled() -> bool:
    return os.environ.get("RZM_QT_PERF", "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class PerfStats:
    count: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    last_ms: float = 0.0

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0


class PerfMonitor:
    _instance: "PerfMonitor | None" = None

    def __init__(self):
        self.enabled = _env_enabled()
        self.threshold_ms = float(os.environ.get("RZM_QT_PERF_THRESHOLD_MS", "8.0"))
        self.revision = 0
        self._stats: dict[str, PerfStats] = defaultdict(PerfStats)
        self._slow_events = deque(maxlen=80)
        self._signal_events = deque(maxlen=120)
        self._signal_counts: dict[str, int] = defaultdict(int)
        self._signal_monitor_installed = False
        self._last_print = 0.0

    @classmethod
    def instance(cls) -> "PerfMonitor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)

    def reset(self):
        self.revision = 0
        self._stats.clear()
        self._slow_events.clear()
        self._signal_events.clear()
        self._signal_counts.clear()

    @contextmanager
    def scope(self, name: str, detail: str | None = None):
        if not self.enabled:
            yield
            return

        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.record_duration(name, elapsed_ms, detail)

    def record_duration(self, name: str, elapsed_ms: float, detail: str | None = None):
        if not self.enabled:
            return

        stats = self._stats[name]
        stats.count += 1
        stats.total_ms += elapsed_ms
        stats.last_ms = elapsed_ms
        if elapsed_ms > stats.max_ms:
            stats.max_ms = elapsed_ms

        if elapsed_ms >= self.threshold_ms:
            self._slow_events.append((time.time(), name, elapsed_ms, detail or ""))

    def record_signal(self, name: str):
        if not self.enabled:
            return

        self.revision += 1
        self._signal_counts[name] += 1
        self._signal_events.append((time.time(), self.revision, name))

    def install_signal_monitor(self, signals):
        if self._signal_monitor_installed:
            return

        signal_names = (
            "structure_changed",
            "transform_changed",
            "data_changed",
            "selection_changed",
            "context_updated",
            "isolation_changed",
            "config_changed",
            "theme_changed_signal",
            "status_message",
            "styles_changed",
            "panel_switch_request",
        )

        for signal_name in signal_names:
            sig = getattr(signals, signal_name, None)
            if sig is None:
                continue
            try:
                sig.connect(lambda *args, _name=signal_name: self.record_signal(_name))
            except Exception:
                pass

        self._signal_monitor_installed = True

    def summary_lines(self, limit: int = 10) -> list[str]:
        if not self.enabled:
            return ["Perf: disabled (set RZM_QT_PERF=1 before Blender launch)"]

        lines = [f"Perf rev={self.revision}"]
        if self._signal_counts:
            signal_summary = ", ".join(
                f"{name}:{count}"
                for name, count in sorted(
                    self._signal_counts.items(), key=lambda item: item[1], reverse=True
                )[:6]
            )
            lines.append(f"Signals: {signal_summary}")

        hot = sorted(self._stats.items(), key=lambda item: item[1].total_ms, reverse=True)[:limit]
        for name, stats in hot:
            lines.append(
                f"{name}: n={stats.count} last={stats.last_ms:.2f} "
                f"avg={stats.avg_ms:.2f} max={stats.max_ms:.2f} total={stats.total_ms:.1f}"
            )

        if self._slow_events:
            _, name, elapsed_ms, detail = self._slow_events[-1]
            suffix = f" {detail}" if detail else ""
            lines.append(f"Last slow: {name} {elapsed_ms:.2f}ms{suffix}")

        return lines


MONITOR = PerfMonitor.instance()


def enabled() -> bool:
    return MONITOR.enabled


def set_enabled(value: bool):
    MONITOR.set_enabled(value)


def reset():
    MONITOR.reset()


def install_signal_monitor(signals):
    MONITOR.install_signal_monitor(signals)


def record_signal(name: str):
    MONITOR.record_signal(name)


@contextmanager
def scope(name: str, detail: str | None = None):
    with MONITOR.scope(name, detail):
        yield


def summary_lines(limit: int = 10) -> list[str]:
    return MONITOR.summary_lines(limit)


def traced(name: str, detail_fn=None):
    """Decorator for coarse function timings.

    ``detail_fn`` is optional and should be cheap; it receives the same
    positional/keyword arguments as the wrapped function.
    """
    def _decorator(func):
        def _wrapped(*args, **kwargs):
            detail = None
            if MONITOR.enabled and detail_fn is not None:
                try:
                    detail = detail_fn(*args, **kwargs)
                except Exception:
                    detail = None
            with MONITOR.scope(name, detail):
                return func(*args, **kwargs)
        return _wrapped
    return _decorator
