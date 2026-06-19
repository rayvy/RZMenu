import time
from contextlib import contextmanager


_current_profiler = None


class ExportProfiler:
    """Lightweight console profiler for Blender export operators."""

    def __init__(self, title="RZM Export Timing"):
        self.title = title
        self._events = []
        self._start = time.perf_counter()
        self._stack = []

    @contextmanager
    def measure(self, name):
        start = time.perf_counter()
        self._stack.append(name)
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self._events.append((name, elapsed))
            self._stack.pop()
            print(f"[RZM Timing] {name}: {elapsed:.3f}s")

    def add(self, name, elapsed):
        self._events.append((name, float(elapsed)))
        print(f"[RZM Timing] {name}: {float(elapsed):.3f}s")

    def report(self):
        total = time.perf_counter() - self._start
        print("")
        print(f"[RZM Timing] ===== {self.title} =====")
        print("[RZM Timing] Note: nested phases are listed independently; percentages may overlap.")
        if not self._events:
            print("[RZM Timing] No timed phases were recorded.")
        else:
            width = max(len(name) for name, _elapsed in self._events)
            for name, elapsed in sorted(self._events, key=lambda x: x[1], reverse=True):
                share = (elapsed / total * 100.0) if total > 0 else 0.0
                print(f"[RZM Timing] {name:<{width}}  {elapsed:8.3f}s  {share:5.1f}%")
        print(f"[RZM Timing] {'TOTAL':<24}  {total:8.3f}s  100.0%")
        print("[RZM Timing] ===============================")
        print("")


def set_current_profiler(profiler):
    global _current_profiler
    _current_profiler = profiler


def get_current_profiler():
    return _current_profiler


@contextmanager
def measure(name):
    profiler = get_current_profiler()
    if profiler is None:
        yield
    else:
        with profiler.measure(name):
            yield
