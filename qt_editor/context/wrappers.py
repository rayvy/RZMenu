# RZMenu/qt_editor/context/wrappers.py
import bpy
from typing import Optional, List, Any

class RZElementWrapper:
    """
    A lightweight wrapper around a Blender Element ID.
    Provides dot-access properties to the underlying Blender data.
    """
    __slots__ = ('_id',)

    def __init__(self, uid: int):
        self._id = uid

    @property
    def id(self) -> int:
        return self._id

    def _get_bl_element(self) -> Any:
        """
        Retrieves the actual Blender element object from the Scene.
        Returns None if the element no longer exists.
        """
        # Note: Accessing bpy directly here is efficient for single-property access.
        # If optimization is needed for bulk operations, read.py strategies are preferred.
        if not bpy.context or not bpy.context.scene:
            return None
            
        # Linear search is standard for Blender collection props; 
        # usually fast enough for UI element counts (<1000).
        # Could be optimized with a lookup map if scene.rzm.elements grows large.
        for elem in bpy.context.scene.rzm.elements:
            if elem.id == self._id:
                return elem
        return None

    @property
    def exists(self) -> bool:
        return self._get_bl_element() is not None

    @property
    def name(self) -> str:
        el = self._get_bl_element()
        return el.element_name if el else ""

    @property
    def class_type(self) -> str:
        el = self._get_bl_element()
        return el.elem_class if el else "UNKNOWN"

    @property
    def pos_x(self) -> float:
        el = self._get_bl_element()
        return el.position[0] if el else 0.0

    @property
    def pos_y(self) -> float:
        el = self._get_bl_element()
        return el.position[1] if el else 0.0

    @property
    def width(self) -> float:
        el = self._get_bl_element()
        return el.size[0] if el else 0.0

    @property
    def height(self) -> float:
        el = self._get_bl_element()
        return el.size[1] if el else 0.0

    @property
    def is_hidden(self) -> bool:
        el = self._get_bl_element()
        return getattr(el, "qt_hide", False) if el else False

    @property
    def is_locked(self) -> bool:
        el = self._get_bl_element()
        return getattr(el, "qt_locked", False) if el else False

    @property
    def is_selectable(self) -> bool:
        el = self._get_bl_element()
        return getattr(el, "qt_selectable", True) if el else False

    def __repr__(self):
        return f"<RZElementWrapper id={self._id} name='{self.name}'>"

    def __eq__(self, other):
        if isinstance(other, RZElementWrapper):
            return self._id == other.id
        return False

    def __hash__(self):
        return hash(self._id)