# RZMenu/qt_editor/window.py
from .systems import input_manager
from PySide6 import QtWidgets, QtCore
from . import core, actions
from .widgets import outliner, inspector, viewport

class RZMEditorWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RZMenu Editor (Unified Ops)")
        self.resize(1100, 600)
        
        # --- STATE ---
        self.selected_ids = set()
        self.active_id = -1
        
        self._sig_viewport = None
        self._sig_outliner = None
        self._sig_inspector = None
        
        # --- UI LAYOUT ---
        root_layout = QtWidgets.QVBoxLayout(self) # Меняем на VBox, чтобы добавить Toolbar сверху
        root_layout.setContentsMargins(0,0,0,0)
        
        # 1. TOOLBAR AREA (Пример кнопок)
        self.toolbar = QtWidgets.QHBoxLayout()
        self.toolbar.setContentsMargins(5,5,5,5)
        root_layout.addLayout(self.toolbar)
        
        # 2. MAIN CONTENT
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        root_layout.addWidget(splitter)
        
        # ... Создание панелей (Outliner, Viewport, Inspector) оставляем как было ...
        self.panel_outliner = outliner.RZMOutlinerPanel()
        self.panel_outliner.setProperty("RZ_CONTEXT", "OUTLINER")

        self.panel_outliner.selection_changed.connect(self.handle_outliner_selection)
        self.panel_outliner.items_reordered.connect(self.on_reorder)
        splitter.addWidget(self.panel_outliner)
        
        self.panel_viewport = viewport.RZViewportPanel()
        self.panel_viewport.setProperty("RZ_CONTEXT", "VIEWPORT")
        self.panel_viewport.parent_window = self 

        self.panel_viewport.rz_scene.item_moved_signal.connect(self.on_viewport_move_delta)
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
        # Инициализируем менеджер. Он сам создаст скрытые QActions и привяжет хоткеи к окну
        self.action_manager = actions.RZActionManager(self)
        
        # --- BUILD TOOLBAR (Привязка кнопок) ---
        self.setup_toolbar()
        self.input_controller = input_manager.RZInputController(self)

        # Это гарантирует, что пользователь увидит данные МГНОВЕННО при открытии.
        QtCore.QTimer.singleShot(0, self.brute_force_refresh)

    def setup_toolbar(self):
        """Создаем кнопки, ссылаясь на ID операторов"""
        
        # Функция-хелпер для создания кнопок
        def add_btn(text, op_id):
            btn = QtWidgets.QPushButton(text)
            self.toolbar.addWidget(btn)
            # Магия здесь: связываем кнопку с логикой
            self.action_manager.connect_button(btn, op_id)
            return btn

        add_btn("Refresh", "rzm.refresh")
        self.toolbar.addSpacing(20)
        add_btn("Undo", "rzm.undo")
        add_btn("Redo", "rzm.redo")
        self.toolbar.addSpacing(20)
        self.btn_del = add_btn("Delete", "rzm.delete") # Сохраним ссылку, если захотим менять стиль
        
        self.toolbar.addStretch()

    # --- SELECTION MANAGEMENT ---

    def clear_selection(self):
        self.selected_ids.clear()
        self.active_id = -1
        self.sync_selection_ui()

    def set_selection_multi(self, ids_set, active_id):
        """Главный метод установки выделения"""
        self.selected_ids = set(ids_set)
        
        # Если active_id не в списке, берем первый попавшийся или -1
        if active_id != -1 and active_id not in self.selected_ids:
            active_id = -1
            
        if active_id == -1 and self.selected_ids:
            # Берем любой, если список не пуст
            active_id = next(iter(self.selected_ids))
            
        self.active_id = active_id
        self.sync_selection_ui()

    def handle_outliner_selection(self, ids_list, active_id):
        # Сигнал от Аутлайнера (список, активный)
        self.set_selection_multi(ids_list, active_id)

    def handle_viewport_selection(self, active_id, modifiers):
        # Сигнал от Вьюпорта (клик по элементу)
        # modifiers: 'CTRL', 'SHIFT' or None
        
        new_selection = self.selected_ids.copy()
        
        if active_id == -1:
            # Клик в пустоту
            if modifiers != 'SHIFT': 
                new_selection.clear()
            active = -1
        else:
            if modifiers == 'SHIFT':
                # Toggle logic
                if active_id in new_selection:
                    new_selection.remove(active_id)
                    # Если удалили активный, ставим новый активный
                    active = -1 if not new_selection else next(iter(new_selection))
                else:
                    new_selection.add(active_id)
                    active = active_id
            else:
                # Replace logic
                new_selection = {active_id}
                active = active_id
                
        self.set_selection_multi(new_selection, active)

    def sync_selection_ui(self):
        self.panel_outliner.set_selection_silent(self.selected_ids, self.active_id)
        self.refresh_viewport(force=True)
        self.refresh_inspector(force=True)
        
        # НОВОЕ: Обновляем состояние Action Manager (например, кнопка Delete станет серой)
        self.action_manager.update_ui_state()

    # --- LOGIC HANDLERS ---
    
    def on_reorder(self, target_id, insert_after_id):
        core.reorder_elements(target_id, insert_after_id)
        # Таймер сам обновит UI

    def on_interaction_start(self):
        self.panel_viewport.rz_scene._is_user_interaction = True

    def on_interaction_end(self):
        core.commit_history("RZM Transformation")
        self.panel_viewport.rz_scene._is_user_interaction = False
        self.refresh_viewport(force=True)
        self.refresh_inspector(force=True)

    def on_viewport_move_delta(self, delta_x, delta_y):
        # Двигаем ВСЕ выделенные элементы на дельту
        if not self.selected_ids: return
        core.move_elements_delta(self.selected_ids, delta_x, delta_y)

    def on_property_edited(self, key, val, idx):
        # Inspector применяет изменения ко ВСЕМ выбранным
        core.update_property_multi(self.selected_ids, key, val, idx)

    # --- REFRESH LOOP ---
    
    def brute_force_refresh(self):
        if not self.isVisible(): return
        self.refresh_outliner()
        self.refresh_viewport()
        self.refresh_inspector()

    def refresh_outliner(self):
        new_sig = core.get_structure_signature()
        if new_sig != self._sig_outliner:
            data = core.get_all_elements_list()
            self.panel_outliner.update_ui(data)
            self._sig_outliner = new_sig
            # Восстанавливаем выделение после перерисовки (ВАЖНО: два аргумента!)
            self.panel_outliner.set_selection_silent(self.selected_ids, self.active_id)

    def refresh_viewport(self, force=False):
        new_sig = core.get_viewport_signature()
        if force or (new_sig != self._sig_viewport):
            data = core.get_viewport_data()
            self.panel_viewport.rz_scene.update_scene(data, self.selected_ids, self.active_id)
            self._sig_viewport = new_sig

    def refresh_inspector(self, force=False):
        # Проверяем подпись АКТИВНОГО элемента
        new_sig = core.get_element_signature(self.active_id)
        
        # Если активный элемент удален или ничего не выбрано
        if self.active_id == -1 or new_sig == "DELETED":
            if self.selected_ids:
                # Fallback: Если активный удален, но есть другие выделенные -> сброс к первому
                 self.active_id = next(iter(self.selected_ids))
                 new_sig = "RESET_NEEDED"
            else:
                if self._sig_inspector != "EMPTY":
                    self.panel_inspector.update_ui(None)
                    self._sig_inspector = "EMPTY"
                return

        if force or (new_sig != self._sig_inspector):
            details = core.get_selection_details(self.selected_ids, self.active_id)
            self.panel_inspector.update_ui(details)
            self._sig_inspector = new_sig