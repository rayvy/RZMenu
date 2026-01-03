# RZMenu/qt_editor/widgets/panel_factory.py
"""
Factory for creating and managing editor panels.
Implements the registry pattern for modular panel instantiation.
"""
from typing import Type, Optional
from .panel_base import RZEditorPanel


class PanelFactory:
    """
    Singleton factory for registering and creating editor panels.
    
    Usage:
        # Register panels
        PanelFactory.register(RZMOutlinerPanel)
        PanelFactory.register(RZMInspectorPanel)
        
        # Create panel instances
        outliner = PanelFactory.create_panel("OUTLINER")
        inspector = PanelFactory.create_panel("INSPECTOR", parent=some_widget)
    """
    
    _registry: dict[str, Type[RZEditorPanel]] = {}
    _instance: Optional["PanelFactory"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def register(cls, panel_cls: Type[RZEditorPanel]) -> None:
        """
        Register a panel class with the factory.
        
        Args:
            panel_cls: A class that inherits from RZEditorPanel
            
        Raises:
            ValueError: If panel_cls doesn't have required PANEL_ID
            TypeError: If panel_cls doesn't inherit from RZEditorPanel
        """
        if not issubclass(panel_cls, RZEditorPanel):
            raise TypeError(
                f"Panel class {panel_cls.__name__} must inherit from RZEditorPanel"
            )
        
        panel_id = getattr(panel_cls, "PANEL_ID", None)
        if not panel_id or panel_id == "UNDEFINED":
            raise ValueError(
                f"Panel class {panel_cls.__name__} must define a valid PANEL_ID"
            )
        
        if panel_id in cls._registry:
            # Allow re-registration (useful for hot-reload scenarios)
            pass
        
        cls._registry[panel_id] = panel_cls
    
    @classmethod
    def create_panel(cls, panel_id: str, parent=None) -> Optional[RZEditorPanel]:
        """
        Create a new instance of a registered panel.
        
        Args:
            panel_id: The PANEL_ID of the panel to create
            parent: Optional parent widget
            
        Returns:
            A new instance of the requested panel, or None if not found
            
        Raises:
            KeyError: If no panel with the given ID is registered
        """
        if panel_id not in cls._registry:
            raise KeyError(
                f"No panel registered with ID '{panel_id}'. "
                f"Available panels: {list(cls._registry.keys())}"
            )
        
        panel_cls = cls._registry[panel_id]
        return panel_cls(parent=parent) if parent else panel_cls()
    
    @classmethod
    def get_available_panels(cls) -> list[dict]:
        """
        Get information about all registered panels.
        
        Returns:
            List of dicts with 'id', 'name', and 'icon' keys
        """
        return [
            panel_cls.get_panel_info()
            for panel_cls in cls._registry.values()
        ]
    
    @classmethod
    def is_registered(cls, panel_id: str) -> bool:
        """Check if a panel ID is registered."""
        return panel_id in cls._registry
    
    @classmethod
    def get_panel_class(cls, panel_id: str) -> Optional[Type[RZEditorPanel]]:
        """Get the panel class for a given ID without instantiating."""
        return cls._registry.get(panel_id)
    
    @classmethod
    def clear_registry(cls) -> None:
        """Clear all registered panels (useful for testing)."""
        cls._registry.clear()

