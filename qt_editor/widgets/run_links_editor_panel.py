# RZMenu/qt_editor/widgets/run_links_editor_panel.py
"""
Panel wrapper for RunLinks + Keybinds manager.
Registered as PANEL_ID = "RUN_LINKS" in PanelFactory.
"""
from PySide6 import QtWidgets
from .panel_base import RZEditorPanel
from .run_links_panel import RZRunLinksManager


class RZMRunLinksPanel(RZEditorPanel):
    """
    Qt Editor panel for RunLinks (named CommandLists) and Keybinds.
    Accessible via the area tabs in the Qt window.
    """
    PANEL_ID   = "RUN_LINKS"
    PANEL_NAME = "Run Links"
    PANEL_ICON = "icon_run_links"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Wrap in a scroll area so that long keybind/body lists are scrollable
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.manager = RZRunLinksManager()
        self._scroll.setWidget(self.manager)
        layout.addWidget(self._scroll)

    @classmethod
    def get_panel_info(cls):
        return {
            "id":   cls.PANEL_ID,
            "name": cls.PANEL_NAME,
            "icon": cls.PANEL_ICON,
        }

    def on_activate(self):
        self.manager.on_activate()

    def update_theme_styles(self):
        self.manager.apply_theme()

    def enterEvent(self, event):
        try:
            from ..context import RZContextManager
            RZContextManager.get_instance().update_input(
                self.cursor().pos(), (0, 0), "RUN_LINKS"
            )
        except Exception:
            pass
        super().enterEvent(event)
