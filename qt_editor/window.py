# RZMenu/qt_editor/window.py
"""
Main Editor Window for RZMenu.

ARCHITECTURE (Phase 8.3):
- Window manages RZAreaWidget containers, NOT specific panels
- Panels are AUTONOMOUS - they subscribe to core.SIGNALS themselves
- No direct panel references are stored (prevents RuntimeError on panel swap)
"""
import datetime
import os
from PySide6 import QtWidgets, QtCore, QtGui

from . import core, actions
from .systems import input_manager
from .systems.layout_manager import LayoutManager
from .widgets import preferences
from .widgets import (
    outliner, inspector, viewport, asset_browser, 
    variables_panel, configurator_panel, texworks_panel, texworks, PanelFactory
)
from .widgets.area import RZAreaWidget
from .context import RZContextManager
from .widgets.lib import theme
from .widgets.lib.widgets import RZContextAwareWidget
from .utils.icons import IconManager
from .core.signals import SIGNALS
from .conf.manager import get_config, set_config_value

class RZMEditorWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("RZMEditorWindow")
        self.setWindowTitle("RZMenu Editor (Pizdec edition)")
        icon_path = "rayvich.ico"
        self.setWindowIcon(QtGui.QIcon(icon_path))
        self.resize(1100, 650)

        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        
        # --- THEME & STYLING ---
        self.setStyleSheet(theme.generate_stylesheet())
        
        # --- REGISTER PANELS ---
        self._register_panels()
        
        # --- INIT SYSTEMS ---
        self.layout_manager = LayoutManager()
        self.action_manager = actions.RZActionManager(self)
        self.input_controller = input_manager.RZInputController(self)
        
        # --- UI LAYOUT ---
        self.root_layout = QtWidgets.QVBoxLayout(self) 
        self.root_layout.setContentsMargins(2, 2, 2, 2)
        self.root_layout.setSpacing(2)
        
        # 1. TOOLBAR (HEADER)
        self.toolbar_container = RZContextAwareWidget("HEADER", self)
        self.toolbar_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.toolbar_container.setFixedHeight(28) # +4px polish
        self.toolbar_layout = QtWidgets.QHBoxLayout(self.toolbar_container)
        self.toolbar_layout.setContentsMargins(4, 0, 4, 0) # No vertical margin
        self.toolbar_layout.setSpacing(4)
        self.setup_toolbar() 
        self.root_layout.addWidget(self.toolbar_container)
        
        # 2. FOOTER
        self.footer_container = RZContextAwareWidget("FOOTER", self)
        self.footer_container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.footer_container.setFixedHeight(18) # Minimal height
        self.footer_layout = QtWidgets.QHBoxLayout(self.footer_container)
        self.footer_layout.setContentsMargins(8, 0, 4, 0)
        self.footer_layout.setSpacing(8)
        self.setup_footer() 
        self.root_layout.addWidget(self.footer_container)

        # 3. CONTENT (Dynamic Splitter & Config Load)
        self.splitter = None 
        
        # Читаем конфиг
        last_layout = get_config().get("system", {}).get("last_layout", "Default")
        
        # Применяем лайаут (он вставится по индексу 1)
        self.apply_layout(last_layout)
        self._update_layout_tabs(select_name=last_layout)

        # Connect alt_mode to areas
        if hasattr(self.input_controller, "alt_mode_changed"):
            self.input_controller.alt_mode_changed.connect(self._broadcast_alt_mode)
        
        self.input_controller.operator_executed.connect(self.update_footer_op)

        # === WINDOW-LEVEL SIGNAL CONNECTIONS ===
        SIGNALS.context_updated.connect(self.on_context_area_changed)
        SIGNALS.config_changed.connect(self.on_config_changed)
        SIGNALS.selection_changed.connect(self._on_selection_changed)
        
        # --- DEBUG OVERLAY ---
        self.setup_debug_overlay()
        
        # Initial trigger
        self._trigger_initial_refresh()

    def _register_panels(self):
        """Register all panel classes with the PanelFactory."""
        PanelFactory.register(outliner.RZMOutlinerPanel)
        PanelFactory.register(inspector.RZMInspectorPanel)
        PanelFactory.register(viewport.RZViewportPanel)
        PanelFactory.register(asset_browser.RZAssetBrowserPanel)
        PanelFactory.register(variables_panel.RZMVariablesPanel)
        PanelFactory.register(configurator_panel.RZMConfiguratorPanel)
        PanelFactory.register(texworks_panel.RZMTexWorksPanel)
        PanelFactory.register(texworks.RZMTexWorksPanel)

    def _trigger_initial_refresh(self):
        SIGNALS.structure_changed.emit()

    def _get_all_areas(self):
        if self.splitter:
            return self.splitter.findChildren(RZAreaWidget)
        return []

    def _broadcast_alt_mode(self, active):
        for area in self._get_all_areas():
            panel = area.get_current_panel()
            if panel and hasattr(panel, 'set_alt_mode'):
                panel.set_alt_mode(active)

    def _on_selection_changed(self):
        self.action_manager.update_ui_state()

    def sync_from_blender(self):
        if not self.isVisible(): return
        for area in self._get_all_areas():
            panel = area.get_current_panel()
            if panel and hasattr(panel, 'rz_scene'):
                if panel.rz_scene._is_user_interaction: return
        SIGNALS.structure_changed.emit()

    def full_refresh(self):
        SIGNALS.structure_changed.emit()

    def apply_layout(self, layout_name):
        """Safely switch to a new layout."""
        try:
            print(f"[WINDOW] Applying layout: {layout_name}")
            data = self.layout_manager.get_layout_data(layout_name)
            
            # 1. Build new layout FIRST to ensure it works
            new_splitter = self.layout_manager.build_layout(data)
            if not new_splitter:
                 print("[WINDOW] Failed to build layout.")
                 return

            # 2. Safely remove old splitter
            if self.splitter:
                # Disconnect or block signals to prevent refreshes on dying widgets
                self.splitter.blockSignals(True)
                for area in self._get_all_areas():
                    panel = area.get_current_panel()
                    if panel:
                        panel.blockSignals(True)
                        if hasattr(panel, 'on_deactivate'):
                            panel.on_deactivate()
                
                self.root_layout.removeWidget(self.splitter)
                self.splitter.setParent(None)
                self.splitter.deleteLater()
            
            # 3. Insert new layout
            self.splitter = new_splitter
            self.root_layout.insertWidget(1, self.splitter, stretch=1)
            
            # 4. Trigger refresh after a safe delay
            QtCore.QTimer.singleShot(100, self.full_refresh)
            
        except Exception as e:
            import traceback
            print(f"[CRITICAL] Error applying layout: {e}")
            traceback.print_exc()
            # If everything fails, try to restore a safe default
            if layout_name != "Default":
                self.apply_layout("Default")

    def _on_full_export(self):
        """Triggers the full export operator in Blender."""
        import bpy
        try:
            bpy.ops.rzm.full_export()
            print("[QT] Export Complete.")
        except Exception as e:
            print(f"[QT] Export Failed: {e}")

    def save_current_layout(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "Save Layout", "Layout Name:")
        if ok and name:
            self.layout_manager.save_layout(name, self.splitter)
            self._update_layout_tabs(select_name=name)

    def reset_layout(self):
        self.apply_layout("Default")
        self._update_layout_tabs(select_name="Default")

    def _update_layout_tabs(self, select_name=None):
        self.layout_tabs.blockSignals(True)
        # QTabBar has no .clear() - remove tabs in a loop
        while self.layout_tabs.count() > 0:
            self.layout_tabs.removeTab(0)
            
        names = self.layout_manager.get_layout_names()
        for name in names:
            self.layout_tabs.addTab(name)
        
        if select_name and select_name in names:
            idx = names.index(select_name)
            self.layout_tabs.setCurrentIndex(idx)
        self.layout_tabs.blockSignals(False)

    def _on_layout_tab_changed(self, index):
        name = self.layout_tabs.tabText(index)
        self.apply_layout(name)
        set_config_value("system", "last_layout", name)

    def _show_layout_tabs_menu(self, pos):
        index = self.layout_tabs.tabAt(pos)
        if index < 0: return
        
        layout_name = self.layout_tabs.tabText(index)
        if layout_name == "Default": return # Cannot delete default

        menu = QtWidgets.QMenu(self)
        act_del = menu.addAction(IconManager.get_instance().get_icon("circle_x"), f"Delete Layout '{layout_name}'")
        act_del.triggered.connect(lambda: self._delete_layout(layout_name))
        menu.exec(self.layout_tabs.mapToGlobal(pos))

    def _delete_layout(self, name):
        if self.layout_manager.delete_layout(name):
            # Switch to default if we deleted active one
            if self.layout_tabs.tabText(self.layout_tabs.currentIndex()) == name:
                self.reset_layout()
            else:
                self._update_layout_tabs()

    def setup_toolbar(self):
        def add_btn(icon_name, op_id, tooltip=None, special=False):
            icon = IconManager.get_instance().get_icon(icon_name)
            btn = QtWidgets.QPushButton(icon, "")
            btn.setFixedSize(24, 24) # Reduced from 36
            btn.setIconSize(QtCore.QSize(14, 14)) # Reduced icons
            if tooltip: btn.setToolTip(tooltip)
            if special: btn.setObjectName("BtnSpecial")
            self.toolbar_layout.addWidget(btn)
            self.action_manager.connect_button(btn, op_id)
            return btn

        add_btn("rotate", "rzm.refresh", "Refresh All Data")
        self.toolbar_layout.addSpacing(10)
        add_btn("arrow_left", "rzm.undo", "Undo Action")
        add_btn("arrow_right", "rzm.redo", "Redo Action")
        self.toolbar_layout.addSpacing(10)
        add_btn("circle_x", "rzm.delete", "Delete Selected") 
        
        self.toolbar_layout.addSpacing(10)
        btn_exp = add_btn("export", "rzm.full_export", "Full Export (rzm.full_export)", special=True)
        btn_exp.clicked.connect(self._on_full_export)
        
        self.toolbar_layout.addStretch()

        # --- LAYOUT TABS (TOP ALIGNED) ---
        self.layout_tabs = QtWidgets.QTabBar()
        self.layout_tabs.setObjectName("LayoutTabBar")
        self.layout_tabs.setFixedHeight(26) # Match polished header
        self.layout_tabs.setExpanding(False)
        self.layout_tabs.setDrawBase(False)
        self.layout_tabs.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.layout_tabs.customContextMenuRequested.connect(self._show_layout_tabs_menu)
        self.layout_tabs.currentChanged.connect(self._on_layout_tab_changed)
        self.toolbar_layout.addWidget(self.layout_tabs)

        # Move Save/Reset here
        self.toolbar_layout.addSpacing(4)
        btn_save = QtWidgets.QPushButton(IconManager.get_instance().get_icon("circle_+"), "")
        btn_save.setFixedSize(20, 20)
        btn_save.setIconSize(QtCore.QSize(12, 12))
        btn_save.setToolTip("Save Current Layout")
        btn_save.clicked.connect(self.save_current_layout)
        self.toolbar_layout.addWidget(btn_save)

        btn_reset = QtWidgets.QPushButton(IconManager.get_instance().get_icon("rotate"), "")
        btn_reset.setFixedSize(20, 20)
        btn_reset.setIconSize(QtCore.QSize(12, 12))
        btn_reset.setToolTip("Reset to Default")
        btn_reset.clicked.connect(self.reset_layout)
        self.toolbar_layout.addWidget(btn_reset)

        self.toolbar_layout.addStretch()
        
        btn_pref = add_btn("gear", "rzm.open_preferences", "Editor Preferences", special=True)
        btn_pref.clicked.connect(self.open_settings)

    def setup_footer(self):
        self.lbl_context = QtWidgets.QLabel("Context: NONE")
        self.lbl_context.setStyleSheet("font-size: 9px;")
        self.footer_layout.addWidget(self.lbl_context)
        
        sep = QtWidgets.QLabel("|")
        sep.setObjectName("FooterSeparator")
        sep.setStyleSheet("color: #444; font-size: 9px;")
        self.footer_layout.addWidget(sep)
        
        self.lbl_last_op = QtWidgets.QLabel("Last Op: None")
        self.lbl_last_op.setObjectName("FooterLastOp")
        self.lbl_last_op.setStyleSheet("font-size: 9px;")
        self.footer_layout.addWidget(self.lbl_last_op)
        
        self.footer_layout.addStretch()

        self.on_context_area_changed() 

    def on_context_area_changed(self):
        ctx = RZContextManager.get_instance().get_snapshot()
        area = ctx.hover_area
        t = theme.get_current_theme()
        self.lbl_context.setText(f"Context: {area}")
        color = t.get(f"ctx_{area.lower()}", t.get('text_dark', '#888'))
        self.lbl_context.setStyleSheet(f"color: {color}; font-weight: bold;")

    def update_footer_op(self, op_name):
        self.lbl_last_op.setText(f"Last Op: {op_name}")

    def open_settings(self):
        dlg = preferences.RZPreferencesDialog(self)
        dlg.exec() 

    def on_config_changed(self, section):
        if section == "appearance":
            qss = theme.generate_stylesheet()
            self.apply_global_theme(qss)

    def apply_global_theme(self, qss):
        self.setStyleSheet(qss)
        for area in self._get_all_areas():
            if hasattr(area, 'update_theme_styles'):
                area.update_theme_styles()
        self.on_context_area_changed()
        SIGNALS.structure_changed.emit()

    def setup_debug_overlay(self):
        t = theme.get_current_theme()
        self.debug_label = QtWidgets.QLabel(self)
        self.debug_label.setStyleSheet(f"background-color: {t.get('debug_bg', 'rgba(0,0,0,150)')}; color: {t.get('debug_text', '#0F0')}; font-family: monospace; font-size: 10px; padding: 5px; border-radius: 4px;")
        self.debug_label.setVisible(False)
        self.debug_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents) 
        self.debug_timer = QtCore.QTimer(self)
        self.debug_timer.timeout.connect(self._update_debug_text)
        self.debug_label.move(15, self.height() - 140) 
        self.debug_label.raise_()

    def resizeEvent(self, event):
        if hasattr(self, 'debug_label'):
            self.debug_label.move(15, self.height() - 140)
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

