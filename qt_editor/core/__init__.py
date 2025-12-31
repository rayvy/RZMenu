# RZMenu/qt_editor/__init__.py
# Facade for the core module.
# This makes "import core" work just like before.

from .signals import SIGNALS, IS_UPDATING_FROM_QT
from .maths import to_qt_coords, to_blender_delta
from .context import get_stable_context, exec_in_context, refresh_viewports, safe_undo_push

from .read import (
    get_all_elements_list,
    get_selection_details,
    get_viewport_data,
    get_structure_signature, # Stubs
    get_element_signature,
    get_viewport_signature,
    get_scene_info,
    get_active_object_safe,
    get_selected_objects_safe
)

from .transform import (
    resize_element,
    move_elements_delta,
    align_elements
)

from .structure import (
    get_next_available_id,
    create_element,
    delete_elements,
    reorder_elements,
    reparent_element,
    duplicate_elements,
    commit_history
)

from .props import (
    update_property_multi,
    toggle_editor_flag,
    unhide_all_elements
)

from .clipboard import (
    copy_elements,
    paste_elements
)