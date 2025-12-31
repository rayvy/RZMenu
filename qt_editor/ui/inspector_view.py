# RZMenu/qt_editor/ui/inspector_view.py
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Signal
from typing import Optional

from ..backend.dtos import RZElement

class RZColorButton(QtWidgets.QPushButton):
    """A simple color picker button."""
    colorChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = [1.0, 1.0, 1.0, 1.0]
        self.clicked.connect(self._pick_color)
        self.update_style()

    def set_color(self, rgba: list):
        if not rgba or len(rgba) < 3: rgba = [1.0, 1.0, 1.0, 1.0]
        if len(rgba) == 3: rgba = list(rgba) + [1.0]
        self._color = rgba
        self.update_style()

    def update_style(self):
        r, g, b, _ = [int(c * 255) for c in self._color]
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        text_color = "black" if luminance > 128 else "white"
        self.setStyleSheet(f"background-color: rgb({r},{g},{b}); color: {text_color}; border: 1px solid #555;")

    def _pick_color(self):
        current_qcolor = QtGui.QColor.fromRgbF(*self._color)
        dialog = QtWidgets.QColorDialog(current_qcolor, self)
        dialog.setOption(QtWidgets.QColorDialog.ColorDialogOption.ShowAlphaChannel, True)
        if dialog.exec():
            c = dialog.selectedColor()
            new_rgba = [c.redF(), c.greenF(), c.blueF(), c.alphaF()]
            self.set_color(new_rgba)
            self.colorChanged.emit(new_rgba)


class InspectorView(QtWidgets.QWidget):
    """
    A "dumb" view for displaying and editing the properties of a single RZElement.
    It is populated by a DTO and emits signals when values are changed by the user.
    """
    property_changed = Signal(int, str, object)  # id, key, value

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_id: Optional[int] = None
        self._block_signals = False
        
        self._setup_ui()
        self.set_selection(None) # Start in a disabled state

    def _setup_ui(self):
        """Initializes all the input widgets."""
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # --- Identity ---
        group_ident = QtWidgets.QGroupBox("Identity")
        form_ident = QtWidgets.QFormLayout(group_ident)
        self.lbl_id = QtWidgets.QLabel("N/A")
        self.name_edit = QtWidgets.QLineEdit()
        form_ident.addRow("ID:", self.lbl_id)
        form_ident.addRow("Name:", self.name_edit)
        main_layout.addWidget(group_ident)

        # --- Transform ---
        group_trans = QtWidgets.QGroupBox("Transform")
        form_trans = QtWidgets.QFormLayout(group_trans)
        self.spin_x = QtWidgets.QSpinBox()
        self.spin_y = QtWidgets.QSpinBox()
        self.spin_w = QtWidgets.QSpinBox()
        self.spin_h = QtWidgets.QSpinBox()
        for spin in [self.spin_x, self.spin_y, self.spin_w, self.spin_h]:
            spin.setRange(-10000, 10000)
            spin.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons) # Compact view
        form_trans.addRow("Pos X:", self.spin_x)
        form_trans.addRow("Pos Y:", self.spin_y)
        form_trans.addRow("Width:", self.spin_w)
        form_trans.addRow("Height:", self.spin_h)
        main_layout.addWidget(group_trans)
        
        # --- Style ---
        group_style = QtWidgets.QGroupBox("Style")
        form_style = QtWidgets.QFormLayout(group_style)
        self.btn_color = RZColorButton()
        form_style.addRow("Color:", self.btn_color)
        main_layout.addWidget(group_style)

        main_layout.addStretch()

        # --- Connect Signals ---
        self.name_edit.editingFinished.connect(lambda: self._emit_change('name', self.name_edit.text()))
        self.spin_x.editingFinished.connect(lambda: self._emit_change('pos_x', self.spin_x.value()))
        self.spin_y.editingFinished.connect(lambda: self._emit_change('pos_y', self.spin_y.value()))
        self.spin_w.editingFinished.connect(lambda: self._emit_change('width', self.spin_w.value()))
        self.spin_h.editingFinished.connect(lambda: self._emit_change('height', self.spin_h.value()))
        self.btn_color.colorChanged.connect(lambda c: self._emit_change('style', {'color': c}))

    def set_selection(self, element: Optional[RZElement]):
        """Populates the inspector fields from a DTO or clears them."""
        self._block_signals = True
        
        is_valid = element is not None
        self.setEnabled(is_valid)

        if not is_valid:
            self._current_id = None
            self.lbl_id.setText("N/A")
            self.name_edit.clear()
            self.spin_x.clear()
            self.spin_y.clear()
            self.spin_w.clear()
            self.spin_h.clear()
            self.btn_color.set_color([])
        else:
            self._current_id = element.id
            self.lbl_id.setText(str(element.id))
            self.name_edit.setText(element.name)
            self.spin_x.setValue(int(element.pos_x))
            self.spin_y.setValue(int(element.pos_y))
            self.spin_w.setValue(int(element.width))
            self.spin_h.setValue(int(element.height))
            self.btn_color.set_color(element.style.get('color', []))

        self._block_signals = False

    def _emit_change(self, key: str, value: object):
        """Emits the property_changed signal if not blocked."""
        if self._block_signals or self._current_id is None:
            return
        self.property_changed.emit(self._current_id, key, value)
