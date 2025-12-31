# RZMenu/qt_editor/main_window.py
from PySide6 import QtWidgets, QtCore

# --- Backend ---
from .backend.repository import RZRepository
from .backend.commands import SceneService

# --- UI Views ---
from .ui.viewport_view import ViewportView
from .ui.outliner_view import OutlinerView
from .ui.inspector_view import InspectorView
from .ui.viewport_items import RZElementItem

# --- Middle/Presenters ---
from .middle.viewport_presenter import ViewportPresenter
from .middle.main_presenter import MainPresenter

class RZMEditorWindow(QtWidgets.QWidget):
    """
    The main window for the RZMenu editor.
    This class initializes and connects all the MVP components.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RZMenu Editor")
        self.resize(1200, 800)

        # 1. Initialize Backend Components (Model)
        self.repo = RZRepository()
        self.service = SceneService()

        # 2. Initialize UI Components (View)
        self.outliner = OutlinerView()
        self.inspector = InspectorView()
        self.viewport = ViewportView()

        # 3. Initialize Presenters (Middle)
        self.vp_presenter = ViewportPresenter(self.viewport.scene(), self.repo, self.service)
        self.main_presenter = MainPresenter(self.outliner, self.inspector, self.repo, self.service)

        # 4. Setup Layout
        self._setup_layout()

        # 5. Wire up presenters and main sync loop
        self._connect_components()

        # 6. Start the synchronization timer
        self.sync_timer = QtCore.QTimer(self)
        self.sync_timer.timeout.connect(self.sync_all)
        self.sync_timer.start(100) # Sync every 100ms

    def _setup_layout(self):
        """Creates the QSplitter layout."""
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        
        left_panel = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        left_panel.addWidget(self.outliner)
        left_panel.addWidget(self.inspector)
        left_panel.setSizes([400, 400]) # Initial sizes

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(self.viewport)
        main_splitter.setSizes([300, 900])

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(main_splitter)
        self.setLayout(layout)

    def _connect_components(self):
        """Connects presenters to each other and sets up the main sync callback."""
        # When the main presenter changes selection, tell the viewport presenter
        self.main_presenter.outliner.selection_changed.connect(
            lambda ids: self.vp_presenter.set_selection(ids, self.main_presenter.active_id)
        )
        
        # When a property is changed, the MainPresenter needs to trigger a global sync
        self.main_presenter.set_full_sync_callback(self.sync_all)

        # When the scene selection changes (e.g., via rubber band in viewport),
        # tell the main presenter.
        self.viewport.scene().selectionChanged.connect(self._on_viewport_selection_changed)

    def sync_all(self):
        """The main synchronization function, called by the QTimer."""
        self.main_presenter.full_sync()
        self.vp_presenter.sync()
        # After syncing, ensure viewport selection is also up to date
        self.vp_presenter.set_selection(self.main_presenter.selected_ids, self.main_presenter.active_id)

    def _on_viewport_selection_changed(self):
        """Handles selection changes originating from the viewport (e.g. rubber-band)."""
        if self.vp_presenter._is_syncing:
             return # Ignore selection changes triggered by the sync itself
             
        selected_items = self.viewport.scene().selectedItems()
        selected_ids = {item.uid for item in selected_items if isinstance(item, RZElementItem)}
        
        # Update the main presenter's state
        self.main_presenter.selected_ids = selected_ids
        if self.main_presenter.active_id not in selected_ids:
             self.main_presenter.active_id = next(iter(selected_ids), None)
             
        # Manually trigger a sync of the panels to reflect the new selection
        self.main_presenter.full_sync()
        
    def closeEvent(self, event):
        """Stops the timer when the window is closed."""
        self.sync_timer.stop()
        super().closeEvent(event)
