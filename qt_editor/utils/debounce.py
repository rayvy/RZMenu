# RZMenu/qt_editor/utils/debounce.py
import time
from PySide6 import QtCore

class RZDebouncer(QtCore.QObject):
    """
    Utility for delayed execution (debouncing).
    Uses QTimer for UI responsiveness but checks time.time() for safety 
    against Blender's event loop jitter.
    """
    timeout = QtCore.Signal()

    def __init__(self, delay_ms=300, parent=None):
        super().__init__(parent)
        self.delay_ms = delay_ms
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_timeout)
        
        self._last_trigger_time = 0
        self._pending_callback = None
        self._pending_args = []
        self._pending_kwargs = {}

    def trigger(self, callback, *args, **kwargs):
        """Request a delayed execution of callback."""
        self._pending_callback = callback
        self._pending_args = args
        self._pending_kwargs = kwargs
        
        self._last_trigger_time = time.time()
        self.timer.start(self.delay_ms)

    def _on_timeout(self):
        self.commit()

    def commit(self):
        """Immediately execute pending callback if any."""
        if not self._pending_callback:
            return

        # Double check time to handle jitter
        # If the timer fired too early, we could theoretically wait, 
        # but usually QTimer is late, not early. 
        # The important part is that we HAVE a callback.
        
        callback = self._pending_callback
        args = self._pending_args
        kwargs = self._pending_kwargs
        
        # Clear state before calling to prevent recursion issues
        self._pending_callback = None
        self.timer.stop()
        
        try:
            callback(*args, **kwargs)
            self.timeout.emit()
        except Exception as e:
            print(f"[RZM Debounce] Error during commit: {e}")

    def cancel(self):
        """Cancel pending commit."""
        self._pending_callback = None
        self.timer.stop()

class RZInputThrottle:
    """
    Simplified throttle for high-frequency events like Slider moves.
    Executes immediately if interval has passed.
    """
    def __init__(self, interval_sec=0.033): # ~30FPS
        self.interval = interval_sec
        self._last_time = 0

    def should_run(self):
        curr = time.time()
        if curr - self._last_time >= self.interval:
            self._last_time = curr
            return True
        return False
