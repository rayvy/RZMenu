# RZMenu/qt_editor/main_window.py
from PySide6 import QtWidgets, QtCore, QtGui

# --- Backend ---
from .backend.repository import RZRepository
from .backend.commands import SceneService

# --- UI Views ---
from .ui.viewport_view import ViewportView
from .ui.outliner_view import OutlinerView
from .ui.inspector_view import InspectorView
from .ui.viewport_items import RZElementItem
from .ui import keymap_editor

# --- Middle/Presenters ---
from .middle.viewport_presenter import ViewportPresenter
from .middle.main_presenter import MainPresenter

# --- Systems ---
from .systems.input_manager import RZInputController
from .actions import RZActionManager

class RZMEditorWindow(QtWidgets.QWidget):
    """
    The main window for the RZMenu editor.
    Connects MVP components and restores Toolbar/Footer logic.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RZMenu Editor (MVP Architecture)")
        self.resize(1200, 800)

        # 1. Initialize Backend
        self.repo = RZRepository()
        self.service = SceneService()

        # 2. Initialize UI
        self.outliner = OutlinerView()
        self.inspector = InspectorView()
        self.viewport = ViewportView()

        # 3. Initialize Presenters
        self.vp_presenter = ViewportPresenter(self.viewport.scene(), self.repo, self.service)
        self.main_presenter = MainPresenter(self.outliner, self.inspector, self.repo, self.service)

        # 4. Initialize Systems (Actions & Inputs)
        self.action_manager = RZActionManager(self)
        self.input_controller = RZInputController(self)
        
        # Connect Input Controller signals to footer
        self.input_controller.context_changed.connect(self.update_footer_context)
        self.input_controller.operator_executed.connect(self.update_footer_op)

        # 5. Setup Layout (Toolbar + Splitter + Footer)
        self._setup_layout()

        # 6. Wire components
        self._connect_components()

        # 7. Start Timer
        self.sync_timer = QtCore.QTimer(self)
        self.sync_timer.timeout.connect(self.sync_all)
        self.sync_timer.start(100)

    def _setup_layout(self):
        # Root Layout
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(0,0,0,0)
        
        # --- Toolbar ---
        self.toolbar = QtWidgets.QHBoxLayout()
        self.toolbar.setContentsMargins(5,5,5,5)
        root_layout.addLayout(self.toolbar)
        self._setup_toolbar_buttons()

        # --- Main Splitter ---
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        
        left_panel = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        left_panel.addWidget(self.outliner)
        left_panel.addWidget(self.inspector)
        left_panel.setSizes([400, 400])

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(self.viewport)
        main_splitter.setSizes([300, 900])
        
        root_layout.addWidget(main_splitter)

        # --- Footer ---
        self._setup_footer(root_layout)

    def _setup_toolbar_buttons(self):
        def add_btn(text, op_id):
            btn = QtWidgets.QPushButton(text)
            self.toolbar.addWidget(btn)
            self.action_manager.connect_button(btn, op_id)
            return btn

        add_btn("Refresh", "rzm.refresh")
        self.toolbar.addSpacing(20)
        add_btn("Undo", "rzm.undo")
        add_btn("Redo", "rzm.redo")
        self.toolbar.addSpacing(20)
        add_btn("Delete", "rzm.delete")
        
        self.toolbar.addStretch()
        
        btn_settings = QtWidgets.QPushButton("Settings")
        btn_settings.setStyleSheet("border: none; color: #888;") 
        btn_settings.clicked.connect(self.open_settings)
        self.toolbar.addWidget(btn_settings)

    def _setup_footer(self, parent_layout):
        self.footer_layout = QtWidgets.QHBoxLayout()
        self.footer_layout.setContentsMargins(5, 2, 5, 2)
        
        footer_bg = QtWidgets.QWidget()
        footer_bg.setStyleSheet("background-color: #222; border-top: 1px solid #333;")
        footer_bg.setLayout(self.footer_layout)
        parent_layout.addWidget(footer_bg) 
        
        self.lbl_context = QtWidgets.QLabel("Context: GLOBAL")
        self.lbl_context.setStyleSheet("color: #aaa; font-weight: bold;")
        self.footer_layout.addWidget(self.lbl_context)
        
        sep = QtWidgets.QLabel("|")
        sep.setStyleSheet("color: #444; margin: 0 10px;")
        self.footer_layout.addWidget(sep)
        
        self.lbl_last_op = QtWidgets.QLabel("Last Op: None")
        self.lbl_last_op.setStyleSheet("color: #888;")
        self.footer_layout.addWidget(self.lbl_last_op)
        
        self.footer_layout.addStretch()

    def update_footer_context(self, ctx_name):
        self.lbl_context.setText(f"Context: {ctx_name}")
        if ctx_name == "VIEWPORT":
             self.lbl_context.setStyleSheet("color: #4772b3; font-weight: bold;") 
        elif ctx_name == "OUTLINER":
             self.lbl_context.setStyleSheet("color: #ffae00; font-weight: bold;") 
        else:
             self.lbl_context.setStyleSheet("color: #aaa; font-weight: bold;")

    def update_footer_op(self, op_name):
        self.lbl_last_op.setText(f"Last Op: {op_name}")

    def open_settings(self):
        dlg = keymap_editor.RZKeymapEditor(self)
        dlg.exec() 

    def _connect_components(self):
        # Presenter Logic
        self.main_presenter.outliner.selection_changed.connect(
            lambda ids: self.vp_presenter.set_selection(ids, self.main_presenter.active_id)
        )
        self.main_presenter.set_full_sync_callback(self.sync_all)
        
        # Viewport Selection -> Main Presenter
        self.viewport.scene().selectionChanged.connect(self._on_viewport_selection_changed)

    def sync_all(self):
        self.main_presenter.full_sync()
        self.vp_presenter.sync()
        self.vp_presenter.set_selection(self.main_presenter.selected_ids, self.main_presenter.active_id)

    def _on_viewport_selection_changed(self):
        if self.vp_presenter._is_syncing: return
             
        selected_items = self.viewport.scene().selectedItems()
        selected_ids = {item.uid for item in selected_items if isinstance(item, RZElementItem)}
        
        self.main_presenter.selected_ids = selected_ids
        if self.main_presenter.active_id not in selected_ids:
             self.main_presenter.active_id = next(iter(selected_ids), None)
             
        self.main_presenter.full_sync()
        
    def closeEvent(self, event):
        self.sync_timer.stop()
        super().closeEvent(event)