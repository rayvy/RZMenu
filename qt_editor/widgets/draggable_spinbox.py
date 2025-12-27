# RZMenu/qt_editor/widgets/draggable_spinbox.py

from PySide6 import QtWidgets, QtCore, QtGui

class DraggableSpinBox(QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        # [FIX] Включаем стрелочки
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.UpDownArrows)
        
        self.setRange(-999999, 999999)
        # Курсор, намекающий на драг, появляется только при наведении
        self.setCursor(QtCore.Qt.SizeHorCursor) 
        self.setStyleSheet("""
            QSpinBox {
                background: #1e1e1e; 
                border: 1px solid #333; 
                color: #ddd; 
                selection-background-color: #555;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 15px;
                background: #2a2a2a;
            }
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: #444;
            }
        """)
        
        self._dragging = False
        self._start_pos = None
        self._last_x = 0
        self._last_y = 0
        self._drag_sensitivity = 0.5 

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._start_pos = event.globalPosition()
            self._last_x = self._start_pos.x()
            self._last_y = self._start_pos.y()
            self._dragging = False # Пока не уверены, это клик или драг
        
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            if self._dragging:
                # Завершаем драг
                self._dragging = False
                self.setCursor(QtCore.Qt.SizeHorCursor)
                # Возвращаем курсор мыши (если скрывали)
                QtWidgets.QApplication.restoreOverrideCursor()
            else:
                # Это был просто клик - даем фокус для ввода текста
                pass
                
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & QtCore.Qt.LeftButton:
            if not self._dragging:
                # Проверяем, сдвинулись ли мы достаточно для начала драга (3px)
                dist = (event.globalPosition() - self._start_pos).manhattanLength()
                if dist > 3:
                    self._dragging = True
                    # Опционально: можно скрыть курсор как в фотошопе
                    # QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.BlankCursor)
            
            if self._dragging:
                curr_x = event.globalPosition().x()
                curr_y = event.globalPosition().y()
                
                delta_x = curr_x - self._last_x
                delta_y = self._last_y - curr_y 
                
                # Приоритет движению
                delta = delta_x if abs(delta_x) > abs(delta_y) else delta_y
                
                if delta != 0:
                    modifiers = QtWidgets.QApplication.keyboardModifiers()
                    step = 1
                    if modifiers & QtCore.Qt.ShiftModifier: step = 10
                    elif modifiers & QtCore.Qt.ControlModifier: step = 0.1
                    
                    change = int(delta * self._drag_sensitivity * step)
                    
                    # Если изменение слишком мелкое (из-за step 0.1 для int), копим его или игнорируем
                    # Для int SpinBox лучше просто реагировать на pixel delta
                    if change == 0 and abs(delta) > 2:
                        change = 1 if delta > 0 else -1

                    if change != 0:
                        self.setValue(self.value() + change)
                        self._last_x = curr_x
                        self._last_y = curr_y
                        self.editingFinished.emit()
                
                event.accept()
                return # Не передаем событие дальше, чтобы не выделять текст

        super().mouseMoveEvent(event)