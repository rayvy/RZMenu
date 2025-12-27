from PySide6.QtWidgets import QLabel, QVBoxLayout
from .base_mode import BaseEditorMode

class VariableMode(BaseEditorMode):
    def __init__(self, context):
        super().__init__(context)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("VARIABLE MODE"))
        self.setLayout(layout)