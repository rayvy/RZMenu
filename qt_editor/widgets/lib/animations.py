# RZMenu/qt_editor/widgets/lib/animations.py
"""
Premium animation effects and physics-based interpolation.
Part of Phase 2.2: Apple Magic & UX Refinement.
"""
from PySide6 import QtCore
import time

class SpringAnimation(QtCore.QObject):
    """
    Physics-based spring interpolation (Hooke's Law with Damping).
    Used for that organic 'snappy' movement.
    """
    value_changed = QtCore.Signal(float)
    finished = QtCore.Signal()

    def __init__(self, stiffness=100.0, damping=10.0, mass=1.0, parent=None):
        super().__init__(parent)
        self.stiffness = stiffness
        self.damping = damping
        self.mass = mass
        
        self._target = 0.0
        self._current = 0.0
        self._velocity = 0.0
        
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._step)
        self._last_time = 0.0
        self._precision = 0.001

    def set_target(self, value):
        self._target = value
        if not self._timer.isActive():
            self._last_time = time.time()
            self._timer.start(16) # ~60fps

    def set_current(self, value):
        self._current = value
        self._velocity = 0.0

    def stop(self):
        self._timer.stop()

    def _step(self):
        now = time.time()
        dt = min(now - self._last_time, 0.1) # Cap dt to prevent explosion
        self._last_time = now
        
        # F = -k*x - d*v
        displacement = self._current - self._target
        spring_force = -self.stiffness * displacement
        damping_force = -self.damping * self._velocity
        
        acceleration = (spring_force + damping_force) / self.mass
        self._velocity += acceleration * dt
        self._current += self._velocity * dt
        
        self.value_changed.emit(self._current)
        
        # Stop if settled
        if abs(displacement) < self._precision and abs(self._velocity) < self._precision:
            self._current = self._target
            self._velocity = 0.0
            self._timer.stop()
            self.value_changed.emit(self._current)
            self.finished.emit()

