# RZMenu/qt_editor/widgets/variables_panel.py
from PySide6 import QtWidgets
from .panel_base import RZEditorPanel
from .variables_manager import RZVariablesManager

class RZMVariablesPanel(RZEditorPanel):
    """
    Panel wrapping the Variables Manager.
    """
    PANEL_ID = "VARIABLES"
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.manager = RZVariablesManager()
        self.layout.addWidget(self.manager)
        
    @classmethod
    def get_panel_info(cls):
        return {
            "id": cls.PANEL_ID,
            "name": "Variables",
            "icon": "icon_variables" # Placeholder
        }

    def on_activate(self):
        self.manager.on_activate()
        
    def update_theme_styles(self):
        self.manager.apply_theme()
