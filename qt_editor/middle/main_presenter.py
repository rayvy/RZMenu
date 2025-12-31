# RZMenu/qt_editor/middle/main_presenter.py
from PySide6.QtCore import QObject, Slot
from typing import Set, Optional

# Backend (Model)
from ..backend.repository import RZRepository
from ..backend.commands import SceneService

# Frontend (View)
from ..ui.outliner_view import OutlinerView
from ..ui.inspector_view import InspectorView

class MainPresenter(QObject):
    """
    Coordinates state between different UI panels (Outliner, Inspector)
    and the backend (Repository, Service).
    It is the central authority for selection management.
    """

    def __init__(self, 
                 outliner: OutlinerView, 
                 inspector: InspectorView, 
                 repository: RZRepository, 
                 service: SceneService,
                 parent=None):
        super().__init__(parent)

        # Keep references to the components it coordinates
        self.outliner = outliner
        self.inspector = inspector
        self.repository = repository
        self.service = service

        # --- State ---
        self.selected_ids: Set[int] = set()
        self.active_id: Optional[int] = None
        self._full_sync_callback = None

        # --- Connect signals from views to presenter's slots ---
        self.outliner.selection_changed.connect(self._on_outliner_selection_changed)
        self.outliner.visibility_toggled.connect(self._on_visibility_toggled)
        self.outliner.lock_toggled.connect(self._on_lock_toggled)
        self.outliner.element_reparented.connect(self._on_element_reparented)
        self.inspector.property_changed.connect(self._on_inspector_property_changed)

    def set_full_sync_callback(self, callback):
        """
        Sets a callback function to be called when a full UI refresh is needed.
        This is used to trigger the main sync loop in the window.
        """
        self._full_sync_callback = callback
    
    def _trigger_full_sync(self):
        """Requests a full synchronization of all presenters."""
        if self._full_sync_callback:
            self._full_sync_callback()

    @Slot(set)
    def _on_outliner_selection_changed(self, selected_ids: Set[int]):
        """
        Handles a selection change from the Outliner.
        Updates the internal state and tells the Inspector to update.
        """
        self.selected_ids = selected_ids
        
        # Determine the "active" element (the one shown in the inspector)
        new_active_id = None
        if self.active_id in self.selected_ids:
            new_active_id = self.active_id # Keep active if still selected
        elif self.selected_ids:
            new_active_id = next(iter(self.selected_ids), None) # Pick the first one
        
        self.active_id = new_active_id

        if self.active_id is None:
            self.inspector.set_selection(None)
        else:
            # In a larger app, we'd cache this. For now, we fetch it.
            all_elements = self.repository.get_all_elements()
            active_element_dto = next((el for el in all_elements if el.id == self.active_id), None)
            self.inspector.set_selection(active_element_dto)
        
        # We also need to inform other parts of the UI, like the Viewport,
        # so it can draw selection highlights. This will be handled by having
        # the main window pass the selection state to the ViewportPresenter.

    @Slot(int, str, object)
    def _on_inspector_property_changed(self, item_id: int, key: str, value: object):
        """Handles a property change from the Inspector and calls the backend service."""
        # Here we could map simple properties to more complex service calls
        if key in ['pos_x', 'pos_y', 'width', 'height', 'name']:
             self.service.update_property(item_id, key, value)
        elif key == 'style':
             # The DTO uses a 'style' dict, so we update sub-keys
             if 'color' in value:
                 self.service.update_property(item_id, 'color', value['color'])
        
        # After a change, request a full UI sync to ensure consistency
        self._trigger_full_sync()

    @Slot(int)
    def _on_visibility_toggled(self, item_id: int):
        """Handles a click on the Outliner's visibility icon."""
        # This is a simplified call. A real service might have a dedicated method.
        # For now, we reuse update_property.
        all_elements = self.repository.get_all_elements()
        element = next((el for el in all_elements if el.id == item_id), None)
        if element:
            self.service.update_property(item_id, 'qt_hide', not element.is_hidden)
            self._trigger_full_sync()

    @Slot(int)
    def _on_lock_toggled(self, item_id: int):
        """Handles a click on the Outliner's lock icon."""
        all_elements = self.repository.get_all_elements()
        element = next((el for el in all_elements if el.id == item_id), None)
        if element:
            self.service.update_property(item_id, 'qt_locked', not element.is_locked)
            self._trigger_full_sync()

    @Slot(int, int)
    def _on_element_reparented(self, child_id: int, new_parent_id: int):
        """Handles drag-and-drop reparenting from the Outliner."""
        self.service.set_parent(child_id, new_parent_id)
        self._trigger_full_sync()

    def full_sync(self):
        """Synchronizes all managed views with the current state."""
        # Sync Outliner
        root_elements = self.repository.build_hierarchy(self.repository.get_all_elements())
        self.outliner.update_tree(root_elements)
        self.outliner.set_selection_from_ids(self.selected_ids)

        # Sync Inspector
        active_element_dto = None
        if self.active_id is not None:
             all_elements = self.repository.get_all_elements()
             active_element_dto = next((el for el in all_elements if el.id == self.active_id), None)
        self.inspector.set_selection(active_element_dto)
