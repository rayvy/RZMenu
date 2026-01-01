# RZMenu/qt_editor/context/manager.py
from typing import Set, Tuple
from PySide6.QtCore import QPoint

from ..core import SIGNALS # Убедись что signals импортирован корректно (через core или ..signals)
from .snapshot import RZContext
from .states import RZInteractionState

class RZContextManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RZContextManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized: return
        
        self._selected_ids: Set[int] = set()
        self._active_id: int = -1
        self._hover_id: int = -1
        
        self._current_state: RZInteractionState = RZInteractionState.IDLE
        self._hover_area: str = "NONE"
        
        self._mouse_screen_pos: QPoint = QPoint(0, 0)
        self._mouse_scene_pos: Tuple[float, float] = (0.0, 0.0)
        self._modifiers: Set[str] = set()
        
        self._state_tags: Set[str] = set()
        self._initialized = True

    @classmethod
    def get_instance(cls) -> 'RZContextManager':
        if cls._instance is None: cls()
        return cls._instance

    # --- Setters ---

    def set_selection(self, selected_ids: Set[int], active_id: int):
        if not isinstance(selected_ids, set): selected_ids = set(selected_ids)
        if (self._selected_ids != selected_ids) or (self._active_id != active_id):
            self._selected_ids = selected_ids
            self._active_id = active_id
            SIGNALS.selection_changed.emit()

    def set_state(self, state: RZInteractionState):
        if self._current_state != state:
            self._current_state = state
            # Можно добавить SIGNALS.context_updated.emit(), если футер показывает State

    def set_hover_id(self, uid: int):
        self._hover_id = uid

    def update_input(self, screen_pos: QPoint, scene_pos: Tuple[float, float], modifiers: Set[str], area: str = "NONE"):
        self._mouse_screen_pos = screen_pos
        self._mouse_scene_pos = scene_pos
        self._modifiers = modifiers
        
        # Если зона изменилась, сообщаем UI (футеру)
        if self._hover_area != area:
            self._hover_area = area
            SIGNALS.context_updated.emit()

    def add_tag(self, tag: str): self._state_tags.add(tag)
    def remove_tag(self, tag: str): 
        if tag in self._state_tags: self._state_tags.remove(tag)
    def clear_tags(self): self._state_tags.clear()

    def get_snapshot(self) -> RZContext:
        return RZContext(self)
    
    def get_debug_string(self) -> str:
        return (
            f"--- RZ CONTEXT ---\n"
            f"State:     {self._current_state.name}\n"
            f"Area:      {self._hover_area}\n"
            f"Hover ID:  {self._hover_id}\n"
            f"Selected:  {list(self._selected_ids)}\n"
            f"Scene Pos: ({self._mouse_scene_pos[0]:.1f}, {self._mouse_scene_pos[1]:.1f})\n"
            f"Modifiers: {list(self._modifiers)}\n"
        )