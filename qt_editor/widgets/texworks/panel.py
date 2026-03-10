# RZMenu/qt_editor/widgets/texworks/panel.py

from PySide6 import QtWidgets, QtCore, QtGui
import bpy
from ..panel_base import RZEditorPanel
from ..lib.widgets import RZLabel
from ...core.signals import SIGNALS
from . import tabs

class RZTexWorksAnchorBar(QtWidgets.QFrame):
    clicked = QtCore.Signal(str)
    def __init__(self, tabs_info, parent=None):
        super().__init__(parent)
        self.setFixedHeight(28)
        self.layout = QtWidgets.QHBoxLayout(self); self.layout.setContentsMargins(4, 2, 4, 2); self.layout.setSpacing(4)
        self.buttons = {}
        for label, tab_id in tabs_info:
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True); btn.setMinimumWidth(80); btn.setFixedHeight(22)
            btn.clicked.connect(lambda _, tid=tab_id: self.clicked.emit(tid))
            self.layout.addWidget(btn); self.buttons[tab_id] = btn
        self.layout.addStretch()

    def set_active(self, tab_id):
        for tid, btn in self.buttons.items():
            btn.blockSignals(True); btn.setChecked(tid == tab_id); btn.blockSignals(False)

class TexWorksManager(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0); self.layout.setSpacing(0)
        self.tabs_info = [
            ("Main", "tab_main"), ("Resources", "tab_res"), 
            ("Overrides", "tab_over"), ("Materials", "tab_mat"),
            ("Test", "tab_test"), ("Test2(Slots)", "tab_test2")
        ]
        self.anchor_bar = RZTexWorksAnchorBar(self.tabs_info); self.anchor_bar.clicked.connect(self._on_tab_clicked); self.layout.addWidget(self.anchor_bar)
        self.stack = QtWidgets.QStackedWidget(); self.layout.addWidget(self.stack)
        
        self.tab_widgets = {
            "tab_main": tabs.TexWorksMainTab(), 
            "tab_res": tabs.TexWorksResourcesTab(), 
            "tab_over": tabs.TexWorksOverridesTab(), 
            "tab_mat": tabs.TexWorksMaterialsTab(),
            "tab_test": tabs.TexWorksTestTab(),
            "tab_test2": tabs.TexWorksTestSlotsTab()
        }
        for label, tab_id in self.tabs_info: self.stack.addWidget(self.tab_widgets[tab_id])
        self.anchor_bar.set_active("tab_main"); self.stack.setCurrentWidget(self.tab_widgets["tab_main"])
        SIGNALS.structure_changed.connect(self.refresh_current)

    def _on_tab_clicked(self, tab_id):
        self.anchor_bar.set_active(tab_id); self.stack.setCurrentWidget(self.tab_widgets[tab_id]); self.refresh_current()

    def refresh_current(self):
        w_curr = self.stack.currentWidget()
        if w_curr and hasattr(w_curr, 'update_ui'): w_curr.update_ui()

    def on_activate(self): self.refresh_current()

class RZMTexWorksPanel(RZEditorPanel):
    PANEL_ID = "TEXWORKS_TEST"; PANEL_NAME = "TexWorks (Test)"; PANEL_ICON = "image"
    def __init__(self, parent=None):
        super().__init__(parent); self.layout = QtWidgets.QVBoxLayout(self); self.layout.setContentsMargins(0, 0, 0, 0)
        self.manager = TexWorksManager(); self.layout.addWidget(self.manager)
    def on_activate(self): self.manager.on_activate()
    def update_theme_styles(self): pass
