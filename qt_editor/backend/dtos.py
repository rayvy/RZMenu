# RZMenu/qt_editor/backend/dtos.py
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class RZElement:
    """
    Data Transfer Object for an element in the RZMenu scene.
    This is a pure data container with no logic.
    """
    id: int
    name: str
    elem_type: str
    
    pos_x: float
    pos_y: float
    width: float
    height: float
    
    parent_id: int
    
    is_hidden: bool
    is_locked: bool
    is_selectable: bool

    image_id: Optional[int] = None
    style: Dict[str, Any] = field(default_factory=dict)
    
    # This field is for building the hierarchy later.
    children: List['RZElement'] = field(default_factory=list, repr=False)

    # Extra properties that might be present on some elements
    text_content: Optional[str] = None
    grid_cell_size: Optional[int] = None
    grid_rows: Optional[int] = None
    grid_cols: Optional[int] = None
    grid_gap: Optional[int] = None
    grid_padding: Optional[int] = None


@dataclass
class SceneMetadata:
    """
    Data Transfer Object for scene-level metadata.
    """
    element_count: int
    scene_name: str
    grid_size: int = 20 # Example, we can get this from a scene property later
