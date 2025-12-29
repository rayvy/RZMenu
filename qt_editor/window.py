# RZMenu/qt_editor/window.py
from PySide6 import QtWidgets, QtCore
from . import core
from .widgets import outliner, inspector, viewport

class RZMEditorWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RZMenu Editor (Fixed)")
        self.resize(1100, 600)
        
        main_layout = QtWidgets.QHBoxLayout(self)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 1. Outliner
        self.panel_outliner = outliner.RZMOutlinerPanel()
        self.panel_outliner.selection_changed.connect(self.set_selection_from_ui)
        splitter.addWidget(self.panel_outliner)
        
        # 2. Viewport
        self.panel_viewport = viewport.RZViewportPanel()
        # Движение (Drag) -> Быстрое обновление
        self.panel_viewport.rz_scene.item_moved_signal.connect(self.on_viewport_move)
        # Начало драга -> Ставим флаг "Не обновлять из блендера"
        self.panel_viewport.rz_scene.interaction_start_signal.connect(self.on_interaction_start)
        # Конец драга -> Undo Push и снимаем флаг
        self.panel_viewport.rz_scene.interaction_end_signal.connect(self.on_interaction_end)
        
        self.panel_viewport.rz_scene.selection_changed_signal.connect(self.set_selection_from_ui)
        splitter.addWidget(self.panel_viewport)
        
        # 3. Inspector
        self.panel_inspector = inspector.RZMInspectorPanel()
        self.panel_inspector.property_changed.connect(self.on_property_edited)
        splitter.addWidget(self.panel_inspector)
        
        splitter.setSizes([200, 600, 300])
        
        self.selected_id = -1
        self._sig_viewport = None
        self._sig_outliner = None
        self._sig_inspector = None

    # --- HANDLERS ---
    
    def on_interaction_start(self):
        # Сообщаем сцене, что юзер трогает её руками
        self.panel_viewport.rz_scene._is_user_interaction = True

    def on_interaction_end(self):
        # Юзер отпустил мышь.
        # 1. Фиксируем историю
        core.commit_history("RZM Viewport Move")
        # 2. Разрешаем обновления
        self.panel_viewport.rz_scene._is_user_interaction = False
        # 3. Форсируем обновление, чтобы данные синхронизировались идеально
        self.refresh_viewport(force=True)
        self.refresh_inspector(force=True)

    def on_viewport_move(self, uid, x, y):
        # Используем FAST update (без undo_push, без проверок контекста)
        core.update_property_fast(uid, 'position', int(x), 0)
        core.update_property_fast(uid, 'position', int(y), 1)
        # Примечание: Инспектор обновлять не обязательно в реальном времени, 
        # если это тормозит, но можно попробовать:
        # self.refresh_inspector(force=True) 

    def on_property_edited(self, key, val, idx):
        # В инспекторе изменения точечные, можно сразу с Undo
        # НО! Нужно использовать safe_undo_push внутри update_property
        # Давай лучше разделим и здесь, если используем DraggableNumber
        # Но пока оставим старый метод для одиночных кликов.
        # Для DraggableNumber лучше реализовать логику start/end drag тоже,
        # но для простоты пусть пока пишет каждый раз, там частота меньше.
        # ВАЖНО: нужно обновить core.update_property чтобы он использовал safe_undo_push
        core.update_property_fast(self.selected_id, key, val, idx)
        core.commit_history(f"RZM Property {key}")

    def set_selection_from_ui(self, elem_id):
        if self.selected_id == elem_id: return
        self.selected_id = elem_id
        self.panel_outliner.set_selection_silent(elem_id)
        self.refresh_viewport(force=True)
        self.refresh_inspector(force=True)

    # --- REFRESH ---
    
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
            self.panel_outliner.set_selection_silent(self.selected_id)

    def refresh_viewport(self, force=False):
        # Внутри update_scene теперь есть проверка _is_user_interaction,
        # так что можно вызывать смело.
        new_sig = core.get_viewport_signature()
        if force or (new_sig != self._sig_viewport):
            data = core.get_viewport_data()
            self.panel_viewport.rz_scene.update_scene(data, self.selected_id)
            self._sig_viewport = new_sig

    def refresh_inspector(self, force=False):
        # (Код инспектора без изменений)
        if self.selected_id == -1:
            if self._sig_inspector != "EMPTY":
                self.panel_inspector.update_ui(None)
                self._sig_inspector = "EMPTY"
            return
        
        new_sig = core.get_element_signature(self.selected_id)
        if new_sig == "DELETED":
            self.selected_id = -1
            self.panel_inspector.update_ui(None)
            self._sig_inspector = "EMPTY"
            return

        if force or (new_sig != self._sig_inspector):
            details = core.get_element_details(self.selected_id)
            self.panel_inspector.update_ui(details)
            self._sig_inspector = new_sig