# RZMenu/qt_editor/backend/repository.py
import bpy
from typing import List, Dict

from .dtos import RZElement, SceneMetadata

class RZRepository:
    """
    Provides read-only access to RZMenu data stored in the Blender scene.
    It returns data in the form of pure DTOs (Data Transfer Objects).
    This class is not aware of any UI.
    """

    def get_all_elements(self) -> List[RZElement]:
        """
        Reads all RZMenu elements from the current scene and returns them
        as a flat list of RZElement DTOs.
        """
        results: List[RZElement] = []
        if not hasattr(bpy.context, 'scene') or not hasattr(bpy.context.scene, 'rzm'):
            return results

        for elem in bpy.context.scene.rzm.elements:
            # Safely get attributes with defaults
            style = {}
            if hasattr(elem, "color"):
                color_list = list(elem.color)
                if len(color_list) == 3:
                    color_list.append(1.0)
                style["color"] = color_list

            dto = RZElement(
                id=elem.id,
                name=elem.element_name,
                elem_type=elem.elem_class,
                pos_x=elem.position[0],
                pos_y=elem.position[1],
                width=elem.size[0],
                height=elem.size[1],
                parent_id=getattr(elem, "parent_id", -1),
                is_hidden=getattr(elem, "qt_hide", False),
                is_locked=getattr(elem, "qt_locked", False),
                is_selectable=getattr(elem, "qt_selectable", True),
                image_id=getattr(elem, "image_id", -1),
                text_content=getattr(elem, "text_string", elem.element_name),
                style=style,
            )
            results.append(dto)
            
        return results

    def build_hierarchy(self, elements: List[RZElement]) -> List[RZElement]:
        """
        Organizes a flat list of RZElement DTOs into a hierarchy.
        It populates the `children` field of each element.

        Returns a list of root elements (those with no parent).
        """
        element_map: Dict[int, RZElement] = {elem.id: elem for elem in elements}
        root_elements: List[RZElement] = []

        for elem in elements:
            if elem.parent_id in element_map:
                parent = element_map[elem.parent_id]
                parent.children.append(elem)
            else:
                root_elements.append(elem)
        
        return root_elements

    def get_scene_metadata(self) -> SceneMetadata:
        """
        Retrieves scene-level metadata.
        """
        if not hasattr(bpy.context, 'scene') or not hasattr(bpy.context.scene, 'rzm'):
            return SceneMetadata(element_count=0, scene_name="No Scene")

        rzm = bpy.context.scene.rzm
        return SceneMetadata(
            element_count=len(rzm.elements),
            scene_name=bpy.context.scene.name,
        )
