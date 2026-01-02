# RZMenu/qt_editor/widgets/lib/widgets.py
from PySide6 import QtWidgets, QtCore, QtGui
from ...context import RZContextManager
from .theme import get_current_theme


class RZContextAwareWidget(QtWidgets.QWidget):
    """
    Base widget that automatically reports mouse enter/leave events to ContextManager.
    """

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
    """
    Base widget with theming support. Automatically applies theme colors.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.apply_theme()

    def apply_theme(self):
        """Override this method to apply theme-specific styling."""
        pass


class RZPanelWidget(RZStyledWidget):
    """
    Base panel widget with common panel styling (borders, background).
    """

    def __init__(self, object_name="", parent=None):
        super().__init__(parent)
        if object_name:
            self.setObjectName(object_name)

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
    """
    Themed group box with consistent styling.
    """

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
    """
    Themed push button with consistent styling.
    """

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
    """
    Themed label with consistent text color.
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.apply_theme()

    def apply_theme(self):
        theme = get_current_theme()
        self.setStyleSheet(f"color: {theme.get('text_main', '#E0E2E4')};")


class RZSpinBox(QtWidgets.QSpinBox):
    """
    Themed spin box with consistent styling.
    """

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
            QSpinBox:focus {{
                border: 1px solid {theme.get('accent', '#5298D4')};
            }}
        """)


class RZDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """
    Themed double spin box with consistent styling.
    """

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
            QDoubleSpinBox:focus {{
                border: 1px solid {theme.get('accent', '#5298D4')};
            }}
        """)


class RZComboBox(QtWidgets.QComboBox):
    """
    Themed combo box with consistent styling.
    """

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
            QComboBox:focus {{
                border: 1px solid {theme.get('accent', '#5298D4')};
            }}
            QComboBox::drop-down {{
                border-left: 1px solid {theme.get('border_input', '#4A505A')};
            }}
        """)


class RZLineEdit(QtWidgets.QLineEdit):
    """
    Themed line edit with consistent styling.
    """

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
            QLineEdit:focus {{
                border: 1px solid {theme.get('accent', '#5298D4')};
            }}
        """)
