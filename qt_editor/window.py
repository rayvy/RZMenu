# RZMenu/qt_editor/window.py
"""
Main Editor Window for RZMenu.

ARCHITECTURE (Phase 8.3):
- Window manages RZAreaWidget containers, NOT specific panels
- Panels are AUTONOMOUS - they subscribe to core.SIGNALS themselves
- No direct panel references are stored (prevents RuntimeError on panel swap)
"""
import datetime
from PySide6 import QtWidgets, QtCore, QtGui

from . import core, actions
from .systems import input_manager
from .widgets import preferences
from .widgets import outliner, inspector, viewport
from .widgets.panel_factory import PanelFactory
from .widgets.area import RZAreaWidget
from .context import RZContextManager
from .widgets.lib import theme
from .widgets.lib.widgets import RZContextAwareWidget
from .core.signals import SIGNALS


class RZMEditorWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("RZMEditorWindow")
        self.setWindowTitle("RZMenu Editor (Context Driven)")
        self.resize(1100, 600)

        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        
        # --- THEME & STYLING ---
        self.setStyleSheet(theme.generate_stylesheet())
        
        # --- REGISTER PANELS ---
        self._register_panels()
        
        # --- UI LAYOUT ---
        root_layout = QtWidgets.QVBoxLayout(self) 
        root_layout.setContentsMargins(5,5,5,5)
        root_layout.setSpacing(5)
        
        # --- INIT ACTIONS ---
        self.action_manager = actions.RZActionManager(self)

        # 1. TOOLBAR (HEADER)
        self.toolbar_container = RZContextAwareWidget("HEADER", self)
        self.toolbar_layout = QtWidgets.QHBoxLayout(self.toolbar_container)
        self.toolbar_layout.setContentsMargins(5,5,5,5)
        self.setup_toolbar() 
        root_layout.addWidget(self.toolbar_container)
        
        # 2. CONTENT (Splitter with RZAreaWidgets)
        # Areas are autonomous - they manage their own panels
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root_layout.addWidget(self.splitter)
        
        # Area 1: Outliner (default)
        self.area_outliner = RZAreaWidget(initial_panel_id="OUTLINER")
        self.splitter.addWidget(self.area_outliner)
        
        # Area 2: Viewport (default)
        self.area_viewport = RZAreaWidget(initial_panel_id="VIEWPORT")
        self.splitter.addWidget(self.area_viewport)
        
        # Area 3: Inspector (default)
        self.area_inspector = RZAreaWidget(initial_panel_id="INSPECTOR")
        self.splitter.addWidget(self.area_inspector)
        
        self.splitter.setSizes([200, 600, 300])

        # 3. FOOTER
        self.footer_container = RZContextAwareWidget("FOOTER", self)
        self.footer_layout = QtWidgets.QHBoxLayout(self.footer_container)
        self.footer_layout.setContentsMargins(5, 2, 5, 2)
        self.setup_footer() 
        root_layout.addWidget(self.footer_container)

        # --- SYSTEMS ---
        self.input_controller = input_manager.RZInputController(self)
        
        # Connect alt_mode to area (which will proxy to current panel if it's a viewport)
        if hasattr(self.input_controller, "alt_mode_changed"):
            self.input_controller.alt_mode_changed.connect(self._broadcast_alt_mode)
        
        self.input_controller.operator_executed.connect(self.update_footer_op)

        # === WINDOW-LEVEL SIGNAL CONNECTIONS ===
        # Only connect signals that the WINDOW needs to handle
        # Panels handle their own data subscriptions autonomously
        
        SIGNALS.context_updated.connect(self.on_context_area_changed)
        SIGNALS.config_changed.connect(self.on_config_changed)
        SIGNALS.selection_changed.connect(self._on_selection_changed)
        
        # --- DEBUG OVERLAY ---
        self.setup_debug_overlay()
        
        # Initial trigger - panels will respond to this signal
        self._trigger_initial_refresh()

    def _register_panels(self):
        """Register all panel classes with the PanelFactory."""
        PanelFactory.register(outliner.RZMOutlinerPanel)
        PanelFactory.register(inspector.RZMInspectorPanel)
        PanelFactory.register(viewport.RZViewportPanel)

    def _trigger_initial_refresh(self):
        """Trigger initial data load by emitting structure_changed signal."""
        # Panels are autonomous and will respond to this signal
        SIGNALS.structure_changed.emit()

    def _broadcast_alt_mode(self, active):
        """Broadcast alt_mode to all viewport panels in all areas."""
        for area in [self.area_outliner, self.area_viewport, self.area_inspector]:
            panel = area.get_current_panel()
            if panel and hasattr(panel, 'set_alt_mode'):
                panel.set_alt_mode(active)

    def _on_selection_changed(self):
        """Update action manager UI state when selection changes."""
        self.action_manager.update_ui_state()

    def sync_from_blender(self):
        """Called externally to sync data from Blender."""
        if not self.isVisible():
            return
        # Check if any viewport is in user interaction mode
        for area in [self.area_outliner, self.area_viewport, self.area_inspector]:
            panel = area.get_current_panel()
            if panel and hasattr(panel, 'rz_scene'):
                if panel.rz_scene._is_user_interaction:
                    return
        # Trigger refresh via signals - panels handle themselves
        SIGNALS.structure_changed.emit()

    def full_refresh(self):
        """Trigger a full refresh of all panels via signals."""
        SIGNALS.structure_changed.emit()

    # -------------------------------------------------------------------------
    # UI SETUP
    # -------------------------------------------------------------------------
    def setup_toolbar(self):
        def add_btn(text, op_id):
            btn = QtWidgets.QPushButton(text)
            self.toolbar_layout.addWidget(btn)
            self.action_manager.connect_button(btn, op_id)
            return btn

        add_btn("Refresh", "rzm.refresh")
        self.toolbar_layout.addSpacing(20)
        add_btn("Undo", "rzm.undo")
        add_btn("Redo", "rzm.redo")
        self.toolbar_layout.addSpacing(20)
        self.btn_del = add_btn("Delete", "rzm.delete") 
        self.toolbar_layout.addStretch()
        
        btn_settings = QtWidgets.QPushButton("Preferences")
        btn_settings.setObjectName("BtnSpecial")
        btn_settings.clicked.connect(self.open_settings)
        self.toolbar_layout.addWidget(btn_settings)

    def setup_footer(self):
        self.lbl_context = QtWidgets.QLabel("Context: NONE")
        self.footer_layout.addWidget(self.lbl_context)
        
        sep = QtWidgets.QLabel("|")
        sep.setObjectName("FooterSeparator")
        self.footer_layout.addWidget(sep)
        
        self.lbl_last_op = QtWidgets.QLabel("Last Op: None")
        self.lbl_last_op.setObjectName("FooterLastOp")
        self.footer_layout.addWidget(self.lbl_last_op)
        
        self.footer_layout.addStretch()
        self.on_context_area_changed() 

    # --- FOOTER UPDATES ---
    def on_context_area_changed(self):
        ctx = RZContextManager.get_instance().get_snapshot()
        area = ctx.hover_area
        t = theme.get_current_theme()
        
        self.lbl_context.setText(f"Context: {area}")
        
        color = t.get(f"ctx_{area.lower()}", t['text_dark'])
        self.lbl_context.setStyleSheet(f"color: {color}; font-weight: bold;")

    def update_footer_op(self, op_name):
        self.lbl_last_op.setText(f"Last Op: {op_name}")

    def open_settings(self):
        dlg = preferences.RZPreferencesDialog(self)
        dlg.exec() 

    def on_config_changed(self, section):
        """React to global config changes."""
        if section == "appearance":
            qss = theme.generate_stylesheet()
            self.apply_global_theme(qss)

    def apply_global_theme(self, qss):
        """Deep update of the Main Window and all areas."""
        self.setStyleSheet(qss)

        # Update all Areas (they will update their current panels)
        for area in [self.area_outliner, self.area_viewport, self.area_inspector]:
            if hasattr(area, 'update_theme_styles'):
                area.update_theme_styles()

        # Footer
        self.on_context_area_changed()
        
        # Trigger refresh for visual updates
        SIGNALS.structure_changed.emit()

    # -------------------------------------------------------------------------
    # DEBUG OVERLAY
    # -------------------------------------------------------------------------
    def setup_debug_overlay(self):
        t = theme.get_current_theme()
        self.debug_label = QtWidgets.QLabel(self)
        self.debug_label.setStyleSheet(f"""
            background-color: {t['debug_bg']};
            color: {t['debug_text']};
            font-family: Consolas, monospace;
            font-size: 11px;
            padding: 5px;
            border: 1px solid {t['debug_border']};
        """)
        self.debug_label.setVisible(False)
        self.debug_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents) 
        self.debug_timer = QtCore.QTimer(self)
        self.debug_timer.timeout.connect(self._update_debug_text)
        self.debug_label.move(10, self.height() - 130) 
        self.debug_label.resize(300, 110)
        
        # Ensure it stays on top of the viewport
        self.debug_label.raise_()

    def resizeEvent(self, event):
        if hasattr(self, 'debug_label'):
            self.debug_label.move(10, self.height() - 130)
        super().resizeEvent(event)

    def toggle_debug_panel(self):
        is_visible = not self.debug_label.isVisible()
        self.debug_label.setVisible(is_visible)
        if is_visible:
            self.debug_label.raise_()
            self.debug_timer.start(50) 
            self._update_debug_text()
        else:
            self.debug_timer.stop()

    def _update_debug_text(self):
        txt = RZContextManager.get_instance().get_debug_string()
        self.debug_label.setText(txt)
        self.debug_label.adjustSize()
