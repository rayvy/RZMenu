# RZMenu/qt_editor/maths.py
def to_qt_coords(blender_x, blender_y):
    """ Blender (Y Up) -> Qt (Y Down) """
    return float(blender_x), float(-blender_y)

def to_blender_delta(qt_dx, qt_dy):
    """ Qt Delta -> Blender Delta """
    return float(qt_dx), float(-qt_dy)

def get_global_pos(element, elem_map):
    """
    Recursively calculate global position from a Blender element.
    :param element: The RZMElement object
    :param elem_map: Dict {id: element} for fast parent lookup
    :return: (x, y) tuple of integers (Global Space)
    """
    if not element: return 0, 0
    
    current_x = element.position[0]
    current_y = element.position[1]
    
    parent_id = getattr(element, "parent_id", -1)
    
    # Safety: Max depth to prevent infinite loops in broken hierarchies
    depth = 0
    while parent_id != -1 and depth < 50:
        parent = elem_map.get(parent_id)
        if not parent: 
            break
            
        current_x += parent.position[0]
        current_y += parent.position[1]
        
        parent_id = getattr(parent, "parent_id", -1)
        depth += 1
        
    return current_x, current_y

def get_local_pos_from_global(global_x, global_y, parent_id, elem_map):
    """
    Calculate required Local Position to achieve a specific Global Position
    under a given parent.
    :param global_x: Target Global X
    :param global_y: Target Global Y
    :param parent_id: ID of the intended parent
    :param elem_map: Dict {id: element}
    :return: (local_x, local_y)
    """
    if parent_id == -1:
        return global_x, global_y
        
    parent = elem_map.get(parent_id)
    if not parent:
        return global_x, global_y
        
    parent_global_x, parent_global_y = get_global_pos(parent, elem_map)
    
    local_x = global_x - parent_global_x
    local_y = global_y - parent_global_y
    
    return local_x, local_y