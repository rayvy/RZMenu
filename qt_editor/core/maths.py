# RZMenu/qt_editor/maths.py
def to_qt_coords(blender_x, blender_y):
    """ Blender (Y Up) -> Qt (Y Down) """
    return float(blender_x), float(-blender_y)

def to_blender_delta(qt_dx, qt_dy):
    """ Qt Delta -> Blender Delta """
    return float(qt_dx), float(-qt_dy)