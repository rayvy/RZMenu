# RZMenu/qt_editor/widgets/configurator_panel.py
from PySide6 import QtWidgets
from .panel_base import RZEditorPanel
from .configurator import RZConfiguratorManager

class RZMConfiguratorPanel(RZEditorPanel):
    """
    Panel for Global Configuration and Addons.
    """
    PANEL_ID = "CONFIGURATOR"
    PANEL_NAME = "Configurator"
    PANEL_ICON = "preferences"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.manager = RZConfiguratorManager()
        self.layout.addWidget(self.manager)
        
    @classmethod
    def get_panel_info(cls):
        return {
            "id": cls.PANEL_ID,
            "name": "Configurator",
            "icon": "preferences" 
        }

    def on_activate(self):
        self.manager.on_activate()
        
    def update_theme_styles(self):
        self.manager.apply_theme()

    def enterEvent(self, event):
        from ..context import RZContextManager
        RZContextManager.get_instance().update_input(
             self.cursor().pos(), 
             (0,0), 
             "CONFIGURATOR"
        )
        super().enterEvent(event)
