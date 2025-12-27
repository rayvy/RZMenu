# qt_editor/utils/parser.py
import bpy

def parse_scene_elements(context):
    """
    Iterates over the elements in the scene and returns a list of dictionaries.
    """
    elements_data = []
    # Ensure context.scene.rzm.elements is accessible and iterable
    if hasattr(context.scene, 'rzm') and hasattr(context.scene.rzm, 'elements'):
        for element in context.scene.rzm.elements:
            elements_data.append({
                'id': getattr(element, 'id', 'N/A'),
                'name': getattr(element, 'name', 'N/A'),
                'type': getattr(element, 'type', 'N/A'),
                'pos_x': getattr(element, 'pos_x', 0),
                'pos_y': getattr(element, 'pos_y', 0),
                'width': getattr(element, 'width', 100),
                'height': getattr(element, 'height', 50),
                'parent_id': getattr(element, 'parent_id', 'N/A'),
            })
    return elements_data