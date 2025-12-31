# RZMenu/qt_editor/window.py
from .systems import input_manager
from .ui import keymap_editor 
from PySide6 import QtWidgets, QtCore
from . import core, actions
from .widgets import outliner, inspector, viewport
import datetime

class RZMEditorWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RZMenu Editor (Event Driven)")
        self.resize(1100, 600)
        
        # --- STATE ---
        self.selected_ids = set()
        self.active_id = -1
        
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

        # === THE BIG CHANGE: CONNECTING SIGNALS ===
        # Вместо Polling мы слушаем Nerve System из core
        core.SIGNALS.structure_changed.connect(self.refresh_outliner)
        core.SIGNALS.structure_changed.connect(self.refresh_viewport) # Новые объекты надо рисовать
        
        core.SIGNALS.transform_changed.connect(self.refresh_viewport)
        core.SIGNALS.transform_changed.connect(self.refresh_inspector) # Координаты в инспекторе
        
        core.SIGNALS.data_changed.connect(self.refresh_inspector)
        core.SIGNALS.data_changed.connect(self.refresh_outliner) # Имена/Флаги
        core.SIGNALS.data_changed.connect(self.refresh_viewport) # Цвета/Текст

        # Первичная инициализация
        self.full_refresh()

    def sync_from_blender(self):
        """
        Вызывается из __init__.py только при Undo/Redo (внешние изменения).
        """
        if not self.isVisible(): return
        if self.panel_viewport.rz_scene._is_user_interaction: return
        self.full_refresh()

    def full_refresh(self):
        self.refresh_outliner()
        self.refresh_viewport(force=True)
        self.refresh_inspector(force=True)

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
    
    # --- SELECTION MANAGEMENT ---
    def clear_selection(self):
        self.selected_ids.clear()
        self.active_id = -1
        self.sync_selection_ui()

    def set_selection_multi(self, ids_set, active_id):
        self.selected_ids = set(ids_set)
        if active_id != -1 and active_id not in self.selected_ids: active_id = -1
        if active_id == -1 and self.selected_ids: active_id = next(iter(self.selected_ids))
        self.active_id = active_id
        self.sync_selection_ui()

    def handle_outliner_selection(self, ids_list, active_id):
        self.set_selection_multi(ids_list, active_id)

    def handle_viewport_selection(self, target_data, modifiers):
        new_selection = self.selected_ids.copy()
        new_active = -1
        if isinstance(target_data, list):
            items_ids = set(target_data)
            if modifiers == 'SHIFT': new_selection.update(items_ids)
            elif modifiers == 'CTRL': new_selection.difference_update(items_ids)
            else: new_selection = items_ids
            if items_ids: new_active = list(items_ids)[0]
            elif new_selection: new_active = next(iter(new_selection))
        else:
            active_id = target_data
            if active_id == -1:
                if modifiers != 'SHIFT' and modifiers != 'CTRL': new_selection.clear()
                new_active = -1
            else:
                if modifiers == 'SHIFT':
                    if active_id in new_selection:
                        new_selection.remove(active_id)
                        new_active = -1 if not new_selection else next(iter(new_selection))
                    else:
                        new_selection.add(active_id)
                        new_active = active_id
                elif modifiers == 'CTRL':
                    if active_id in new_selection: new_selection.remove(active_id)
                else:
                    new_selection = {active_id}
                    new_active = active_id
        self.set_selection_multi(new_selection, new_active)

    def sync_selection_ui(self):
        self.panel_outliner.set_selection_silent(self.selected_ids, self.active_id)
        self.refresh_viewport(force=False) # Не форсим, только селект
        self.refresh_inspector(force=True)
        self.action_manager.update_ui_state()

    # --- LOGIC HANDLERS ---
    def on_reorder(self, target_id, insert_after_id):
        core.reorder_elements(target_id, insert_after_id)
    def on_interaction_start(self):
        self.panel_viewport.rz_scene._is_user_interaction = True
    def on_interaction_end(self):
        # Когда отпустили мышь - фиксируем историю и делаем ОДИН полный рефреш,
        # чтобы убедиться, что Blender и Qt в точности совпадают.
        core.commit_history("RZM Transformation")
        self.panel_viewport.rz_scene._is_user_interaction = False
        self.refresh_viewport(force=True)
        self.refresh_inspector(force=True)
    def on_viewport_move_delta(self, delta_x, delta_y):
        if not self.selected_ids: return
        # SILENT=TRUE! 
        # Мы говорим ядру: "Обнови цифры в Blender, но не триггери перерисовку UI".
        # Viewport сам уже подвинул QGraphicsItem через item.moveBy()
        core.move_elements_delta(self.selected_ids, delta_x, delta_y, silent=True)
        
        # Опционально: можно обновить Inspector точечно, если очень хочется видеть бегущие цифры,
        # но это тоже может вызвать лаги. Пока оставим выключенным для скорости.
        # Если нужны бегущие цифры в инспекторе без лагов - это делается через сигналы Qt напрямую, минуя core.

    def on_viewport_resize(self, uid, x, y, w, h):
        # То же самое для ресайза
        core.resize_element(uid, x, y, w, h, silent=True)
    def on_viewport_resize(self, uid, x, y, w, h):
        core.resize_element(uid, x, y, w, h)
    def on_property_edited(self, key, val, idx):
        core.update_property_multi(self.selected_ids, key, val, idx)

    def refresh_outliner(self):
        # t = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        # print(f"[{t}] >>> [EVENT] UI UPDATE: Outliner")
        
        data = core.get_all_elements_list()
        self.panel_outliner.update_ui(data)
        self.panel_outliner.set_selection_silent(self.selected_ids, self.active_id)

    def refresh_viewport(self, force=False):
        # t = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        # print(f"[{t}] >>> [EVENT] UI UPDATE: Viewport")
        
        data = core.get_viewport_data()
        self.panel_viewport.rz_scene.update_scene(data, self.selected_ids, self.active_id)

    def refresh_inspector(self, force=False):
        # t = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        # print(f"[{t}] >>> [EVENT] UI UPDATE: Inspector")
        
        details = core.get_selection_details(self.selected_ids, self.active_id)
        self.panel_inspector.update_ui(details)