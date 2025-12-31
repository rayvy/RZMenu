# RZMenu/qt_editor/maths.py
def to_qt_coords(blender_x, blender_y):
    """ Blender (Y Up) -> Qt (Y Down) """
    return int(blender_x), int(-blender_y)

def to_blender_delta(qt_dx, qt_dy):
    """ Qt Delta -> Blender Delta """
    return int(qt_dx), int(-qt_dy)