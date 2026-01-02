# RZMenu/qt_editor/context/snapshot.py
from typing import Set, Tuple, List, Optional, TYPE_CHECKING
from .wrappers import RZElementWrapper
from .states import RZInteractionState

if TYPE_CHECKING:
    from .manager import RZContextManager

class RZContext:
    def __init__(self, manager: 'RZContextManager'):
        self._active_id = manager._active_id
        self._selected_ids = set(manager._selected_ids)
        
        self._state = manager._current_state
        self._hover_id = manager._hover_id
        self._hover_area = manager._hover_area
        
        self._mouse_screen = manager._mouse_screen_pos 
        self._mouse_scene = manager._mouse_scene_pos
        self._tags = set(manager._state_tags)

    # Standard Props
    @property
    def active_id(self) -> int: return self._active_id
    @property
    def selected_ids(self) -> Set[int]: return frozenset(self._selected_ids)
    @property
    def active_element(self) -> Optional[RZElementWrapper]:
        return RZElementWrapper(self._active_id) if self._active_id != -1 else None
    @property
    def selected_elements(self) -> List[RZElementWrapper]:
        return [RZElementWrapper(uid) for uid in self._selected_ids]
    
    # Hover Props
    @property
    def hover_id(self) -> int: return self._hover_id
    @property
    def hover_element(self) -> Optional[RZElementWrapper]:
        return RZElementWrapper(self._hover_id) if self._hover_id != -1 else None
    @property
    def hover_area(self) -> str: return self._hover_area

    # State & Input Props
    @property
    def state(self) -> RZInteractionState:
        return self._state
    
    @property
    def mouse_screen_pos(self): return self._mouse_screen
    @property
    def mouse_scene_pos(self) -> Tuple[float, float]: return self._mouse_scene

    def has_tag(self, tag: str) -> bool: return tag in self._tags