# RZMenu/qt_editor/context/snapshot.py
from typing import Set, Tuple, List, Optional, TYPE_CHECKING
from .wrappers import RZElementWrapper

if TYPE_CHECKING:
    from .manager import RZContextManager
    from PySide6.QtCore import QPoint

class RZContext:
    """
    An immutable snapshot of the application state.
    """
    def __init__(self, manager: 'RZContextManager'):
        self._active_id: int = manager._active_id
        self._selected_ids: Set[int] = set(manager._selected_ids)
        
        # NEW: Hover state
        self._hover_id: int = manager._hover_id
        self._hover_area: str = manager._hover_area
        self._mouse_screen_pos = manager._mouse_screen_pos 
        self._mouse_scene_pos: Tuple[float, float] = manager._mouse_scene_pos
        
        self._state_tags: Set[str] = set(manager._state_tags)

    @property
    def active_id(self) -> int:
        return self._active_id

    @property
    def selected_ids(self) -> Set[int]:
        return frozenset(self._selected_ids)

    @property
    def active_element(self) -> Optional[RZElementWrapper]:
        if self._active_id == -1: return None
        return RZElementWrapper(self._active_id)

    @property
    def selected_elements(self) -> List[RZElementWrapper]:
        return [RZElementWrapper(uid) for uid in self._selected_ids]

    @property
    def hover_id(self) -> int:
        return self._hover_id

    @property
    def hover_element(self) -> Optional[RZElementWrapper]:
        if self._hover_id == -1: return None
        return RZElementWrapper(self._hover_id)

    @property
    def hover_area(self) -> str:
        return self._hover_area

    @property
    def mouse_screen_pos(self):
        return self._mouse_screen_pos

    @property
    def mouse_scene_pos(self) -> Tuple[float, float]:
        return self._mouse_scene_pos

    def has_tag(self, tag: str) -> bool:
        return tag in self._state_tags