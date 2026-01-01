# RZMenu/qt_editor/window.py
import datetime
from PySide6 import QtWidgets, QtCore

from . import core, actions
from .systems import input_manager
from .ui import keymap_editor 
from .widgets import outliner, inspector, viewport
from .context import RZContextManager

class RZMEditorWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RZMenu Editor (Context Driven)")
        self.resize(1100, 600)
        
        # --- UI LAYOUT ---
        root_layout = QtWidgets.QVBoxLayout(self) 
        root_layout.setContentsMargins(0,0,0,0)
        
        # 1. TOOLBAR
        self.toolbar = QtWidgets.QHBoxLayout()
        self.toolbar.setContentsMargins(5,5,5,5)
        root_layout.addLayout(self.toolbar)
        
        # 2. CONTENT
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root_layout.addWidget(splitter)
        
        self.panel_outliner = outliner.RZMOutlinerPanel()
        self.panel_outliner.setProperty("RZ_CONTEXT", "OUTLINER")
        self.panel_outliner.selection_changed.connect(self.handle_outliner_selection)
        self.panel_outliner.items_reordered.connect(self.on_reorder)
        self.panel_outliner.req_toggle_hide.connect(lambda uid: self.action_manager.run("rzm.toggle_hide", override_ids=[uid]))
        self.panel_outliner.req_toggle_selectable.connect(lambda uid: self.action_manager.run("rzm.toggle_selectable", override_ids=[uid]))
        splitter.addWidget(self.panel_outliner)
        
        self.panel_viewport = viewport.RZViewportPanel()
        self.panel_viewport.setProperty("RZ_CONTEXT", "VIEWPORT")
        self.panel_viewport.parent_window = self 
        self.panel_viewport.rz_scene.item_moved_signal.connect(self.on_viewport_move_delta)
        self.panel_viewport.rz_scene.element_resized_signal.connect(self.on_viewport_resize)
        
        self.panel_viewport.rz_scene.interaction_start_signal.connect(self.on_interaction_start)
        self.panel_viewport.rz_scene.interaction_end_signal.connect(self.on_interaction_end)
        self.panel_viewport.rz_scene.selection_changed_signal.connect(self.handle_viewport_selection)
        splitter.addWidget(self.panel_viewport)
        
        self.panel_inspector = inspector.RZMInspectorPanel()
        self.panel_inspector.setProperty("RZ_CONTEXT", "INSPECTOR")
        self.panel_inspector.property_changed.connect(self.on_property_edited)
        splitter.addWidget(self.panel_inspector)
        
        splitter.setSizes([200, 600, 300])

        # --- INIT ACTIONS ---
        self.action_manager = actions.RZActionManager(self)
        self.setup_toolbar()
        
        self.input_controller = input_manager.RZInputController(self)
        if hasattr(self.input_controller, "alt_mode_changed"):
            self.input_controller.alt_mode_changed.connect(self.panel_viewport.set_alt_mode)
        
        self.setup_footer()
        self.input_controller.context_changed.connect(self.update_footer_context)
        self.input_controller.operator_executed.connect(self.update_footer_op)

        # === SIGNAL CONNECTIONS ===
        # 1. Data Changes (Blender -> UI)
        core.SIGNALS.structure_changed.connect(self.refresh_outliner)
        core.SIGNALS.structure_changed.connect(self.refresh_viewport)
        
        core.SIGNALS.transform_changed.connect(self.refresh_viewport)
        core.SIGNALS.transform_changed.connect(self.refresh_inspector)
        
        core.SIGNALS.data_changed.connect(self.refresh_inspector)
        core.SIGNALS.data_changed.connect(self.refresh_outliner)
        core.SIGNALS.data_changed.connect(self.refresh_viewport)

        # 2. Context Changes (Internal Logic -> UI)
        # When the Manager changes selection, we update all panels.
        core.SIGNALS.selection_changed.connect(self.on_context_selection_changed)

        # Initial Refresh
        self.full_refresh()

    def sync_from_blender(self):
        """Called by __init__.py on Undo/Redo/External changes."""
        if not self.isVisible(): return
        if self.panel_viewport.rz_scene._is_user_interaction: return
        self.full_refresh()

    def full_refresh(self):
        self.refresh_outliner()
        self.refresh_viewport(force=True)
        # Inspector refresh depends on selection, which relies on the ContextManager
        # We trigger the context update explicitly to ensure UI sync
        self.on_context_selection_changed()

    # -------------------------------------------------------------------------
    # UI SETUP
    # -------------------------------------------------------------------------
    def setup_toolbar(self):
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
        self.btn_del = add_btn("Delete", "rzm.delete") 
        self.toolbar.addStretch()
        btn_settings = QtWidgets.QPushButton("Settings")
        btn_settings.setStyleSheet("border: none; color: #888;") 
        btn_settings.clicked.connect(self.open_settings)
        self.toolbar.addWidget(btn_settings)

    def setup_footer(self):
        self.footer_layout = QtWidgets.QHBoxLayout()
        self.footer_layout.setContentsMargins(5, 2, 5, 2)
        footer_bg = QtWidgets.QWidget()
        footer_bg.setStyleSheet("background-color: #222; border-top: 1px solid #333;")
        footer_bg.setLayout(self.footer_layout)
        self.layout().addWidget(footer_bg) 
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
        if ctx_name == "VIEWPORT": self.lbl_context.setStyleSheet("color: #4772b3; font-weight: bold;") 
        elif ctx_name == "OUTLINER": self.lbl_context.setStyleSheet("color: #ffae00; font-weight: bold;") 
        else: self.lbl_context.setStyleSheet("color: #aaa; font-weight: bold;")

    def update_footer_op(self, op_name):
        self.lbl_last_op.setText(f"Last Op: {op_name}")

    def open_settings(self):
        dlg = keymap_editor.RZKeymapEditor(self)
        dlg.exec() 

    # -------------------------------------------------------------------------
    # SELECTION & CONTEXT HANDLERS
    # -------------------------------------------------------------------------

    def on_context_selection_changed(self):
        """
        Triggered when RZContextManager emits selection_changed.
        Updates all UI panels to reflect the new state.
        """
        ctx = RZContextManager.get_instance().get_snapshot()
        
        # 1. Outliner
        self.panel_outliner.set_selection_silent(ctx.selected_ids, ctx.active_id)
        
        # 2. Viewport (Visuals only, avoiding full rebuild)
        if hasattr(self.panel_viewport.rz_scene, 'update_selection_visuals'):
            self.panel_viewport.rz_scene.update_selection_visuals(ctx.selected_ids, ctx.active_id)
        else:
            self.refresh_viewport(force=False)
            
        # 3. Inspector
        self.refresh_inspector()
        
        # 4. Actions
        self.action_manager.update_ui_state()

    def handle_outliner_selection(self, ids_list, active_id):
        """User clicked in Outliner -> Update Manager."""
        RZContextManager.get_instance().set_selection(set(ids_list), active_id)

    def handle_viewport_selection(self, target_data, modifiers):
        """
        User clicked in Viewport -> Calculate new selection logic -> Update Manager.
        """
        ctx = RZContextManager.get_instance().get_snapshot()
        current_selection = set(ctx.selected_ids)
        current_active = ctx.active_id
        
        new_selection = current_selection.copy()
        new_active = -1

        # target_data can be a list (RubberBand) or int (Single Click)
        if isinstance(target_data, list):
            items_ids = set(target_data)
            if modifiers == 'SHIFT': 
                new_selection.update(items_ids)
            elif modifiers == 'CTRL': 
                new_selection.difference_update(items_ids)
            else: 
                new_selection = items_ids
            
            if items_ids:
                new_active = list(items_ids)[0]
            elif new_selection:
                new_active = next(iter(new_selection))
        else:
            clicked_id = target_data
            if clicked_id == -1:
                # Clicked on empty space
                if modifiers != 'SHIFT' and modifiers != 'CTRL': 
                    new_selection.clear()
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
                    if clicked_id in new_selection: 
                        new_selection.remove(clicked_id)
                else:
                    new_selection = {clicked_id}
                    new_active = clicked_id

        RZContextManager.get_instance().set_selection(new_selection, new_active)

    # -------------------------------------------------------------------------
    # CORE INTERACTION LOGIC
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
        # Silent update to Blender data
        core.move_elements_delta(ctx.selected_ids, delta_x, delta_y, silent=True)

    def on_viewport_resize(self, uid, x, y, w, h):
        core.resize_element(uid, x, y, w, h, silent=True)

    def on_property_edited(self, key, val, idx):
        ctx = RZContextManager.get_instance().get_snapshot()
        core.update_property_multi(ctx.selected_ids, key, val, idx)

    # -------------------------------------------------------------------------
    # REFRESH HANDLERS
    # -------------------------------------------------------------------------

    def refresh_outliner(self):
        # t = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        # print(f"[{t}] >>> [EVENT] UI UPDATE: Outliner")
        data = core.get_all_elements_list()
        
        ctx = RZContextManager.get_instance().get_snapshot()
        self.panel_outliner.update_ui(data)
        self.panel_outliner.set_selection_silent(ctx.selected_ids, ctx.active_id)

    def refresh_viewport(self, force=False):
        # t = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        # print(f"[{t}] >>> [EVENT] UI UPDATE: Viewport")
        data = core.get_viewport_data()
        
        ctx = RZContextManager.get_instance().get_snapshot()
        self.panel_viewport.rz_scene.update_scene(data, ctx.selected_ids, ctx.active_id)

    def refresh_inspector(self, force=False):
        # t = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        # print(f"[{t}] >>> [EVENT] UI UPDATE: Inspector")
        ctx = RZContextManager.get_instance().get_snapshot()
        
        details = core.get_selection_details(ctx.selected_ids, ctx.active_id)
        self.panel_inspector.update_ui(details)