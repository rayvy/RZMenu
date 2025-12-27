from PySide6.QtWidgets import QWidget

class BaseEditorMode(QWidget):
    def __init__(self, context):
        super().__init__()
        self.context = context

    def on_activate(self):
        """ Method called when tab is switched to this mode. """
        pass

    def on_deactivate(self):
        """ Method called when tab is switched away. """
        pass