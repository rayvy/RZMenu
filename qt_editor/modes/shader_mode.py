#RZMenu/qt_editor/modes/shader_mode.py
from PySide6.QtWidgets import QLabel, QVBoxLayout
from .base_mode import BaseEditorMode

class ShaderMode(BaseEditorMode):
    def __init__(self, context):
        super().__init__(context)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("SHADER MODE (ADDONS)"))
        self.setLayout(layout)