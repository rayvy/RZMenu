# RZMenu/qt_editor/context/manager.py
from typing import Set, Tuple, Optional
from PySide6.QtCore import QPoint

# FIXED: Relative import to prevent ModuleNotFoundError
from ..core import SIGNALS
from .snapshot import RZContext

class RZContextManager:
    """
    Singleton. The Single Source of Truth for the UI Selection and State.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RZContextManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        # Core State
        self._selected_ids: Set[int] = set()
        self._active_id: int = -1
        self._hover_id: int = -1  # NEW: Element ID under mouse
        
        # Mouse / Interaction State
        self._hover_area: str = "NONE"
        self._mouse_screen_pos: QPoint = QPoint(0, 0)
        self._mouse_scene_pos: Tuple[float, float] = (0.0, 0.0)
        
        # Meta State
        self._state_tags: Set[str] = set()
        
        self._initialized = True

    @classmethod
    def get_instance(cls) -> 'RZContextManager':
        if cls._instance is None:
            cls()
        return cls._instance

    # -------------------------------------------------------------------------
    # State Mutators
    # -------------------------------------------------------------------------

    def set_selection(self, selected_ids: Set[int], active_id: int):
        if not isinstance(selected_ids, set):
            selected_ids = set(selected_ids)

        selection_changed = (self._selected_ids != selected_ids)
        active_changed = (self._active_id != active_id)

        if selection_changed or active_changed:
            self._selected_ids = selected_ids
            self._active_id = active_id
            SIGNALS.selection_changed.emit()

    def set_hover_id(self, uid: int):
        """Sets the ID of the element currently under the mouse."""
        self._hover_id = uid

    def update_mouse(self, screen_pos: QPoint, scene_pos: Tuple[float, float], area: str = "NONE"):
        self._mouse_screen_pos = screen_pos
        self._mouse_scene_pos = scene_pos
        self._hover_area = area

    def add_tag(self, tag: str):
        self._state_tags.add(tag)

    def remove_tag(self, tag: str):
        if tag in self._state_tags:
            self._state_tags.remove(tag)

    def clear_tags(self):
        self._state_tags.clear()

    # -------------------------------------------------------------------------
    # Snapshot Factory
    # -------------------------------------------------------------------------

    def get_snapshot(self) -> RZContext:
        return RZContext(self)