# RZMenu/qt_editor/widgets/lib/widgets.py
from PySide6 import QtWidgets, QtCore, QtGui
from ...context import RZContextManager
from .theme import get_current_theme

# --- RZColorButton (Moved from inspector.py & Upgraded) ---
class RZColorButton(QtWidgets.QPushButton):
    """
    Универсальная кнопка цвета.
    Input: set_color() принимает list [r,g,b] (0-1) ИЛИ string "#HEX" / "rgba(...)".
    Output: colorChanged emit list [r,g,b,a] (0-1) для совместимости с инспектором.
    """
    colorChanged = QtCore.Signal(list)

    def __init__(self, text=""):
        super().__init__(text)
        self._qcolor = QtGui.QColor(255, 255, 255) # Internal state is always QColor
        self.clicked.connect(self._pick_color)
        self.update_style()

    def set_color(self, color_data):
        """Smart setter that handles both Blender floats and CSS strings."""
        if not color_data:
            return

        if isinstance(color_data, str):
            # Handle Hex/CSS String
            self._qcolor.setNamedColor(color_data)
            # Fallback for complex css like rgba() if setNamedColor fails, try ctor
            if not self._qcolor.isValid():
                 self._qcolor = QtGui.QColor(color_data)
        
        elif isinstance(color_data, (list, tuple)):
            # Handle Blender Float List [1.0, 0.5, 0.0]
            if len(color_data) >= 3:
                r, g, b = color_data[0], color_data[1], color_data[2]
                a = color_data[3] if len(color_data) > 3 else 1.0
                self._qcolor.setRgbF(r, g, b, a)

        if not self._qcolor.isValid():
            self._qcolor = QtGui.QColor(255, 0, 255) # Debug Pink

        self.update_style()

    def update_style(self):
        """Update style using the internal QColor."""
        if not self._qcolor.isValid(): return

        r, g, b, a = self._qcolor.red(), self._qcolor.green(), self._qcolor.blue(), self._qcolor.alpha()
        
        # Calculate luminance for text contrast
        luminance = (0.299 * r + 0.587 * g + 0.114 * b)
        
        theme = get_current_theme()
        # Fallback if theme is not fully loaded yet
        text_bright = theme.get('text_bright', '#FFFFFF')
        text_main = theme.get('text_main', '#000000')
        border_col = theme.get('border_input', '#444')

        contrast_color = text_main if luminance > 128 else text_bright
        
        # Format as rgba for CSS
        bg_style = f"rgba({r},{g},{b},{a})"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_style};
                color: {contrast_color};
                border: 1px solid {border_col};
                border-radius: 3px;
                padding: 4px 8px;
            }}
        """)

    def _pick_color(self):
        dialog = QtWidgets.QColorDialog(self._qcolor, self)
        dialog.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, True)
        
        if dialog.exec():
            c = dialog.selectedColor()
            self._qcolor = c
            self.update_style()
            # Emit as float list [r, g, b, a] (0.0 - 1.0)
            self.colorChanged.emit([c.redF(), c.greenF(), c.blueF(), c.alphaF()])


# --- Existing Widgets (No changes below, just re-exporting) ---

class RZContextAwareWidget(QtWidgets.QWidget):
    def __init__(self, area_name, parent=None):
        super().__init__(parent)
        self.area_name = area_name
        self.setObjectName(f"RZContextWidget_{area_name}")

    def enterEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(), (0, 0), area=self.area_name
        )
        super().enterEvent(event)

    def leaveEvent(self, event):
        RZContextManager.get_instance().update_input(
            QtGui.QCursor.pos(), (0, 0), area="NONE"
        )
        super().leaveEvent(event)


class RZStyledWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
    def apply_theme(self): pass

class RZPanelWidget(RZStyledWidget):
    def __init__(self, object_name="", parent=None):
        super().__init__(parent)
        if object_name: self.setObjectName(object_name)
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            {self.objectName()} {{
                background-color: {theme.get('bg_panel', '#2C313A')};
                border: 1px solid {theme.get('border_main', '#3A404A')};
                border-radius: 4px;
            }}
        """)

class RZGroupBox(QtWidgets.QGroupBox):
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QGroupBox {{
                background-color: {theme.get('bg_panel', '#2C313A')};
                border: 1px solid {theme.get('border_main', '#3A404A')};
                border-radius: 4px;
                margin-top: 6px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                left: 10px;
                background-color: {theme.get('bg_panel', '#2C313A')};
                color: {theme.get('text_dark', '#9DA5B4')};
            }}
        """)

class RZPushButton(QtWidgets.QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.get('bg_header', '#3A404A')};
                color: {theme.get('text_main', '#E0E2E4')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background-color: {theme.get('accent_hover', '#6AACDE')};
                color: {theme.get('accent_text', '#FFFFFF')};
            }}
            QPushButton:pressed {{
                background-color: {theme.get('accent', '#5298D4')};
            }}
            QPushButton:disabled {{
                color: {theme.get('text_disabled', '#6A717C')};
                background-color: {theme.get('bg_input', '#252930')};
            }}
        """)

class RZLabel(QtWidgets.QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"color: {theme.get('text_main', '#E0E2E4')};")

class RZSpinBox(QtWidgets.QSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QSpinBox {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QSpinBox:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
        """)

class RZDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QDoubleSpinBox:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
        """)

class RZComboBox(QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QComboBox {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QComboBox:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
            QComboBox::drop-down {{ border-left: 1px solid {theme.get('border_input', '#4A505A')}; }}
        """)

class RZLineEdit(QtWidgets.QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()
    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"""
            QLineEdit {{
                background-color: {theme.get('bg_input', '#252930')};
                border: 1px solid {theme.get('border_input', '#4A505A')};
                border-radius: 3px;
                padding: 3px;
                color: {theme.get('text_main', '#E0E2E4')};
            }}
            QLineEdit:focus {{ border: 1px solid {theme.get('accent', '#5298D4')}; }}
        """)