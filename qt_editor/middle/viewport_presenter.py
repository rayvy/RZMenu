# RZMenu/qt_editor/middle/viewport_presenter.py

from typing import Dict, List
from PySide6 import QtWidgets

# Backend (Model) imports
from ..backend.repository import RZRepository
from ..backend.commands import SceneService
from ..backend.dtos import RZElement

# Frontend (View) imports
from ..ui.viewport_items import RZElementItem

class ViewportPresenter:
    """
    The Presenter for the main viewport. It connects the View (QGraphicsScene)
    with the Model (Repository and Service).

    - Reads data from RZRepository.
    - Creates/updates/deletes RZElementItem instances in the QGraphicsScene.
    - Listens to signals from RZElementItem (e.g., move, resize).
    - Calls SceneService to persist changes back to Blender.
    """

    def __init__(self, scene: QtWidgets.QGraphicsScene, repository: RZRepository, service: SceneService):
        self.scene = scene
        self.repository = repository
        self.service = service

        # A map to hold references to the Qt items, keyed by their ID
        self._items: Dict[int, RZElementItem] = {}
        
        # Flags to prevent signal feedback loops
        self._is_user_interacting = False
        self._is_syncing = False

    def sync(self):
        """
        Synchronizes the state of the QGraphicsScene with the data from the repository.
        This is the main reconciliation loop (Diffing).
        """
        if self._is_user_interacting:
            return  # Don't update UI while the user is actively dragging/resizing

        self._is_syncing = True

        # 1. Get the desired state from the model
        all_elements: List[RZElement] = self.repository.get_all_elements()
        dto_map: Dict[int, RZElement] = {dto.id: dto for dto in all_elements}
        
        # 2. Get the current state of the view
        current_item_ids = set(self._items.keys())
        desired_item_ids = set(dto_map.keys())

        # 3. Diffing: Remove items that no longer exist in the model
        ids_to_remove = current_item_ids - desired_item_ids
        for item_id in ids_to_remove:
            item_to_remove = self._items.pop(item_id)
            self.scene.removeItem(item_to_remove)
            # Python's garbage collector will handle deletion

        # 4. Diffing: Add new items or update existing ones
        for dto in all_elements:
            if dto.id not in self._items:
                # This is a new element, create a corresponding item
                new_item = RZElementItem(dto)
                self._items[dto.id] = new_item
                self.scene.addItem(new_item)
                # Connect signals from the new item to the presenter's slots
                self._connect_item_signals(new_item)
            else:
                # This is an existing element, update its visual state
                existing_item = self._items[dto.id]
                existing_item.update_from_dto(dto)

        # 5. Handle parenting after all items are created/updated
        for dto in all_elements:
            item = self._items[dto.id]
            parent_item = self._items.get(dto.parent_id) if dto.parent_id != -1 else None
            
            if item.parentItem() is not parent_item:
                item.setParentItem(parent_item)

        self._is_syncing = False

    def set_selection(self, selected_ids: set, active_id: int):
        """Updates the selection state of the items in the scene."""
        if self._is_syncing:
            return
            
        for item_id, item in self._items.items():
            is_selected = item_id in selected_ids
            item.setSelected(is_selected)
            item.set_handles_visible(is_selected)
            
            if item_id == active_id:
                item.setZValue(10)
            else:
                item.setZValue(1)


    def _connect_item_signals(self, item: RZElementItem):
        """Connects an item's signals to the presenter's handler slots."""
        item.moved.connect(self._on_item_moved)
        item.resized.connect(self._on_item_resized)
        # item.selected.connect(self._on_item_selected)
        item.interaction_started.connect(self._on_interaction_started)
        item.interaction_finished.connect(self._on_interaction_finished)

    # --- SLOTS FOR HANDLING UI INTERACTIONS ---

    def _on_item_moved(self, item_id: int, blender_x: float, blender_y: float):
        """Handles when an item is moved by the user in the view."""
        if self._is_syncing: return

        # The item's signal already converted coords to Blender's system (Y-up)
        # We just need to get the current size to pass to the service
        item = self._items.get(item_id)
        if item:
            rect = item.rect()
            self.service.update_transform(item_id, blender_x, blender_y, rect.width(), rect.height())

    def _on_item_resized(self, item_id: int, blender_x: float, blender_y: float, width: float, height: float):
        """Handles when an item is resized by the user in the view."""
        if self._is_syncing: return
        
        # Signal provides all necessary data in Blender's coordinate system
        self.service.update_transform(item_id, blender_x, blender_y, width, height)

    def _on_interaction_started(self, item_id: int):
        """Pauses scene synchronization when the user starts an interaction."""
        self._is_user_interacting = True

    def _on_interaction_finished(self, item_id: int):
        """Resumes scene synchronization after user interaction ends."""
        self._is_user_interacting = False
        # Optional: you might want to trigger an immediate sync here
        # self.sync()
