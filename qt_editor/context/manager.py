# RZMenu/qt_editor/context/manager.py
from typing import Set, Tuple, TYPE_CHECKING
from PySide6.QtCore import QPoint

from ..core import SIGNALS 
if TYPE_CHECKING:
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
        
        self._state_tags: Set[str] = set()
        self._initialized = True

    @property
    def active_id(self) -> int: return self._active_id
    
    @property
    def selected_ids(self) -> Set[int]: return self._selected_ids

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

    def update_input(self, screen_pos: QPoint, scene_pos: Tuple[float, float], area: str = "NONE"):
        self._mouse_screen_pos = screen_pos
        self._mouse_scene_pos = scene_pos
        
        # Если зона изменилась, сообщаем UI (футеру)
        if self._hover_area != area:
            self._hover_area = area
            SIGNALS.context_updated.emit()

    def add_tag(self, tag: str): self._state_tags.add(tag)
    def remove_tag(self, tag: str): 
        if tag in self._state_tags: self._state_tags.remove(tag)
    def clear_tags(self): self._state_tags.clear()

    def get_snapshot(self) -> 'RZContext':
        from .snapshot import RZContext
        return RZContext(self)
    
    def get_debug_string(self) -> str:
        # Импорт внутри метода, чтобы избежать circular import, так как враппер тоже может ссылаться на что-то
        # Или используем snapshot, который у нас уже есть. 
        # Но для чистоты в manager.py лучше получить данные "сырыми" или через snapshot.
        
        # Давай создадим временный snapshot прямо тут, чтобы использовать мощь Wrappers
        snap = self.get_snapshot()
        
        active_info = "None"
        if snap.active_element and snap.active_element.exists:
            active_info = f"{snap.active_element.class_type} ('{snap.active_element.name}') [ID: {snap.active_id}]"
        elif self._active_id != -1:
            active_info = f"ID {self._active_id} (Not Found)"
        
        hover_info = "None"
        if snap.hover_element and snap.hover_element.exists:
            # ВОТ ОНО! Читаем класс и имя через обертку
            hover_info = f"{snap.hover_element.class_type} ('{snap.hover_element.name}')"
        elif self._hover_id != -1:
            hover_info = f"ID {self._hover_id} (Not Found)"

        return (
            f"--- RZ CONTEXT ---\n"
            f"State:     {self._current_state.name}\n"
            f"Area:      {self._hover_area}\n"
            f"Active:    {active_info}\n"
            f"Hover:     {hover_info}\n"
            f"Selected:  {list(self._selected_ids)}\n"
            f"Scene Pos: ({self._mouse_scene_pos[0]:.1f}, {self._mouse_scene_pos[1]:.1f})"
        )