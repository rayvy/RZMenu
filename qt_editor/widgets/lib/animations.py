# RZMenu/qt_editor/widgets/lib/animations.py
"""
Premium animation effects and physics-based interpolation.
Part of Phase 2.2: Apple Magic & UX Refinement.
"""
from PySide6 import QtCore, QtGui, QtWidgets
import math
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


class LiquidFillEffect(QtCore.QObject):
    """
    Simulates a 'liquid' filling an area with organic waves.
    Useful for progress bars, element filling, or selection highlights.
    """
    update_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0 # 0.0 to 1.0
        self._phase = 0.0
        self._amplitude = 4.0
        self._frequency = 0.05
        
        self._spring = SpringAnimation(stiffness=150, damping=15, parent=self)
        self._spring.value_changed.connect(self._on_spring_progress)
        
        self._wave_timer = QtCore.QTimer(self)
        self._wave_timer.timeout.connect(self._tick_wave)
        self._wave_timer.start(33) # ~30fps for organic waves

    def set_progress(self, val):
        self._spring.set_target(val)

    def _on_spring_progress(self, val):
        self._progress = val
        self.update_requested.emit()

    def _tick_wave(self):
        if self._progress > 0.0 and self._progress < 1.0:
            self._phase += 0.2
            self.update_requested.emit()

    def draw(self, painter: QtGui.QPainter, rect: QtCore.QRectF, color: QtGui.QColor):
        """
        Draw the liquid within the given rect.
        """
        if self._progress <= 0:
            return
            
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Create clip path for the waves
        path = QtGui.QPainterPath()
        
        fill_height = rect.height() * self._progress
        top = rect.bottom() - fill_height
        
        # Generate wave points
        path.moveTo(rect.left(), rect.bottom())
        
        # If filling or mostly full, draw waves at the top edge
        if self._progress < 1.0:
            steps = 20
            w = rect.width()
            for i in range(steps + 1):
                x = rect.left() + (i / steps) * w
                # Organic wave formula: Sin(x*freq + phase) * amplitude
                y_off = math.sin(x * self._frequency + self._phase) * self._amplitude
                # Add a secondary wave for more liquid feel
                y_off += math.cos(x * self._frequency * 0.5 - self._phase * 0.7) * (self._amplitude * 0.5)
                
                path.lineTo(x, top + y_off)
        else:
            path.lineTo(rect.left(), rect.top())
            path.lineTo(rect.right(), rect.top())
            
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        
        painter.setBrush(color)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawPath(path)
        
        # Optional: Add a 'gloss' or secondary highlight at the wave surface
        if 0.0 < self._progress < 1.0:
            highlight = QtGui.QColor(255, 255, 255, 40)
            painter.setPen(QtGui.QPen(highlight, 1.5))
            # Just draw the top wave path again as a line
            # (Reuse path or re-generate only the top part)
            pass 

        painter.restore()

