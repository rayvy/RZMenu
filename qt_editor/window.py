# RZMenu/qt_editor/window.py
import datetime
from PySide6 import QtWidgets, QtCore, QtGui

from . import core, actions
from .systems import input_manager
from .widgets import preferences # NEW IMPORT
from .widgets import outliner, inspector, viewport
from .context import RZContextManager
from .widgets.lib import theme
from .widgets.lib.widgets import RZContextAwareWidget

# RZContextContainer moved to widgets.lib.widgets as RZContextAwareWidget


class RZMEditorWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("RZMEditorWindow")
        self.setWindowTitle("RZMenu Editor (Context Driven)")
        self.resize(1100, 600)
        
        # --- THEME & STYLING ---
        self.setStyleSheet(theme.generate_stylesheet())
        
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
        
        # 2. CONTENT (Splitter)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root_layout.addWidget(splitter)
        
        # Outliner
        self.panel_outliner = outliner.RZMOutlinerPanel()
        splitter.addWidget(self.panel_outliner)
        
        # Viewport
        self.panel_viewport = viewport.RZViewportPanel()
        self.panel_viewport.parent_window = self # Link for context menu
        splitter.addWidget(self.panel_viewport)
        
        # Inspector
        self.panel_inspector = inspector.RZMInspectorPanel()
        splitter.addWidget(self.panel_inspector)
        
        splitter.setSizes([200, 600, 300])

        # 3. FOOTER
        self.footer_container = RZContextAwareWidget("FOOTER", self)
        self.footer_layout = QtWidgets.QHBoxLayout(self.footer_container)
        self.footer_layout.setContentsMargins(5, 2, 5, 2)
        self.setup_footer() 
        root_layout.addWidget(self.footer_container)

        # --- SYSTEMS ---
        self.input_controller = input_manager.RZInputController(self)
        if hasattr(self.input_controller, "alt_mode_changed"):
            self.input_controller.alt_mode_changed.connect(self.panel_viewport.set_alt_mode)
        
        self.input_controller.operator_executed.connect(self.update_footer_op)

        # === SIGNAL CONNECTIONS ===
        self.panel_outliner.selection_changed.connect(self.handle_outliner_selection)
        self.panel_outliner.items_reordered.connect(self.on_reorder)
        self.panel_outliner.req_toggle_hide.connect(lambda uid: self.action_manager.run("rzm.toggle_hide", override_ids=[uid]))
        self.panel_outliner.req_toggle_selectable.connect(lambda uid: self.action_manager.run("rzm.toggle_selectable", override_ids=[uid]))
        
        self.panel_viewport.rz_scene.item_moved_signal.connect(self.on_viewport_move_delta)
        self.panel_viewport.rz_scene.element_resized_signal.connect(self.on_viewport_resize)
        self.panel_viewport.rz_scene.interaction_start_signal.connect(self.on_interaction_start)
        self.panel_viewport.rz_scene.interaction_end_signal.connect(self.on_interaction_end)
        self.panel_viewport.rz_scene.selection_changed_signal.connect(self.handle_viewport_selection)
        
        self.panel_inspector.property_changed.connect(self.on_property_edited)

        core.SIGNALS.structure_changed.connect(self.refresh_outliner)
        core.SIGNALS.structure_changed.connect(self.refresh_viewport)
        
        core.SIGNALS.transform_changed.connect(self.refresh_viewport)
        core.SIGNALS.transform_changed.connect(self.refresh_inspector)
        
        core.SIGNALS.data_changed.connect(self.refresh_inspector)
        core.SIGNALS.data_changed.connect(self.refresh_outliner)
        core.SIGNALS.data_changed.connect(self.refresh_viewport)

        core.SIGNALS.selection_changed.connect(self.on_context_selection_changed)
        core.SIGNALS.context_updated.connect(self.on_context_area_changed)
        
        # --- DEBUG OVERLAY ---
        self.setup_debug_overlay()
        
        # Initial Refresh
        self.full_refresh()

    def sync_from_blender(self):
        if not self.isVisible(): return
        if self.panel_viewport.rz_scene._is_user_interaction: return
        self.full_refresh()

    def full_refresh(self):
        self.refresh_outliner()
        self.refresh_viewport(force=True)
        self.on_context_selection_changed()

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
        btn_settings.setObjectName("BtnSpecial") # Use ID for special styling
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
        self.on_context_area_changed() # Initial style update

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
        # UPDATED: Now opens the full Preferences Dialog
        dlg = preferences.RZPreferencesDialog(self)
        
        # DIRTY HACK connection:
        # При смене темы в диалоге мы получаем готовый QSS и применяем его ко всему окну
        dlg.req_global_stylesheet_update.connect(self.apply_global_theme)
        
        dlg.exec() 

    def apply_global_theme(self, qss):
        """
        Slot to hot-reload the theme for the main window and its children.
        Triggered by the Preferences dialog.
        """
        self.setStyleSheet(qss)
        
        # Обновляем специфичные виджеты, которые кэшируют кисти или стили
        # Например Viewport использует QGraphicsScene с закешированными Brush/Pen
        self.panel_viewport.rz_scene._init_background() # Re-read theme colors
        self.panel_viewport.rz_scene.update()           # Force redraw
        
        # Перерисовываем футер (он меняет цвета динамически в коде)
        self.on_context_area_changed()
        
        # Принудительно обновляем вьюпорт (хендлы, сетки)
        self.refresh_viewport(force=True)

    # -------------------------------------------------------------------------
    # SELECTION & CONTEXT HANDLERS
    # -------------------------------------------------------------------------

    def on_context_selection_changed(self):
        ctx = RZContextManager.get_instance().get_snapshot()
        
        self.panel_outliner.set_selection_silent(ctx.selected_ids, ctx.active_id)
        
        if hasattr(self.panel_viewport.rz_scene, 'update_selection_visuals'):
            self.panel_viewport.rz_scene.update_selection_visuals(ctx.selected_ids, ctx.active_id)
        else:
            self.refresh_viewport(force=False)
            
        self.refresh_inspector()
        self.action_manager.update_ui_state()

    def handle_outliner_selection(self, ids_list, active_id):
        RZContextManager.get_instance().set_selection(set(ids_list), active_id)

    def handle_viewport_selection(self, target_data, modifiers):
        ctx = RZContextManager.get_instance().get_snapshot()
        current_selection = set(ctx.selected_ids)
        new_selection = current_selection.copy()
        new_active = -1

        if isinstance(target_data, list):
            items_ids = set(target_data)
            if modifiers == 'SHIFT': new_selection.update(items_ids)
            elif modifiers == 'CTRL': new_selection.difference_update(items_ids)
            else: new_selection = items_ids
            if items_ids: new_active = list(items_ids)[0]
            elif new_selection: new_active = next(iter(new_selection))
        else:
            clicked_id = target_data
            if clicked_id == -1:
                if modifiers not in ['SHIFT', 'CTRL']: new_selection.clear()
                new_active = -1
            else:
                if modifiers == 'SHIFT':
                    if clicked_id in new_selection:
                        new_selection.remove(clicked_id)
                        new_active = -1 if not new_selection else next(iter(new_selection))
                    else:
                        new_selection.add(clicked_id)
                        new_active = clicked_id
                elif modifiers == 'CTRL':
                    if clicked_id in new_selection: new_selection.remove(clicked_id)
                else:
                    new_selection = {clicked_id}
                    new_active = clicked_id
        RZContextManager.get_instance().set_selection(new_selection, new_active)

    # -------------------------------------------------------------------------
    # LOGIC HANDLERS
    # -------------------------------------------------------------------------

    def on_reorder(self, target_id, insert_after_id):
        core.reorder_elements(target_id, insert_after_id)

    def on_interaction_start(self):
        self.panel_viewport.rz_scene._is_user_interaction = True

    def on_interaction_end(self):
        core.commit_history("RZM Transformation")
        self.panel_viewport.rz_scene._is_user_interaction = False
        self.refresh_viewport(force=True)
        self.refresh_inspector(force=True)

    def on_viewport_move_delta(self, delta_x, delta_y):
        ctx = RZContextManager.get_instance().get_snapshot()
        if not ctx.selected_ids: return
        core.move_elements_delta(ctx.selected_ids, delta_x, delta_y, silent=True)

    def on_viewport_resize(self, uid, x, y, w, h):
        core.resize_element(uid, x, y, w, h, silent=True)

    def on_property_edited(self, key, val, idx):
        ctx = RZContextManager.get_instance().get_snapshot()
        core.update_property_multi(ctx.selected_ids, key, val, idx)

    # -------------------------------------------------------------------------
    # REFRESH
    # -------------------------------------------------------------------------

    def refresh_outliner(self):
        data = core.get_all_elements_list()
        ctx = RZContextManager.get_instance().get_snapshot()
        self.panel_outliner.update_ui(data)
        self.panel_outliner.set_selection_silent(ctx.selected_ids, ctx.active_id)

    def refresh_viewport(self, force=False):
        data = core.get_viewport_data()
        ctx = RZContextManager.get_instance().get_snapshot()
        self.panel_viewport.rz_scene.update_scene(data, ctx.selected_ids, ctx.active_id)

    def refresh_inspector(self, force=False):
        ctx = RZContextManager.get_instance().get_snapshot()
        details = core.get_selection_details(ctx.selected_ids, ctx.active_id)
        self.panel_inspector.update_ui(details)
    
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

        self.debug_label.move(10, self.height() - 120) 
        self.debug_label.resize(300, 110)

    def resizeEvent(self, event):
        if hasattr(self, 'debug_label'):
            self.debug_label.move(10, self.height() - 130)
        super().resizeEvent(event)

    def toggle_debug_panel(self):
        is_visible = not self.debug_label.isVisible()
        self.debug_label.setVisible(is_visible)
        if is_visible:
            self.debug_timer.start(50) 
            self._update_debug_text()
        else:
            self.debug_timer.stop()

    def _update_debug_text(self):
        txt = RZContextManager.get_instance().get_debug_string()
        self.debug_label.setText(txt)
        self.debug_label.adjustSize()