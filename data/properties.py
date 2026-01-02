# RZMenu/data/properties.py
import bpy
from bpy.props import (
    StringProperty, IntProperty, FloatProperty, BoolProperty,
    IntVectorProperty, CollectionProperty, PointerProperty, EnumProperty,
)

# Импорт из под-модулей в той же папке data
from .p_images import RZMCaptureSettings, RZMenuImage, ConditionalImage
from .p_logic import (
    ValueLinkProperty, ValueProperty, ToggleDefinition, 
    BitProperty, AssignedToggle, RZMCondition, 
    RZMShapeKey, RZMShape
)
from .p_texworks import (
    TexResource, TexOverride, TexWorksAtlasConfig, 
    TexWorksTextureConfig, DecalConfig, AlternativeTexture, 
    TexWorksTexture
)
from .p_ui import (
    FXProperty, FNProperty, CustomProperty, RZMenuElement
)
from .p_settings import (
    RZMenuConfig, DependencyStatus, RZMExportSettings, RZMenuAddonSettings
)

# --- ГЛАВНЫЙ КЛАСС (ROOT) ---
class RZMenuProperties(bpy.types.PropertyGroup):
    version: StringProperty(name="Version", default="3.0.1")
    config: PointerProperty(type=RZMenuConfig)
    export_settings: PointerProperty(type=RZMExportSettings)
    images: CollectionProperty(type=RZMenuImage)
    atlas_size: IntVectorProperty(name="Atlas Size", size=2)
    rzm_values: CollectionProperty(type=ValueProperty)
    toggle_definitions: CollectionProperty(type=ToggleDefinition)
    elements: CollectionProperty(type=RZMenuElement)
    element_to_add_class: EnumProperty(name="Class", items=[('CONTAINER', "Container", ""), ('GRID_CONTAINER', "Grid Container", ""), ('ANCHOR', "Anchor", ""), ('BUTTON', "Button", ""), ('SLIDER', "Slider", ""), ('TEXT', "Text", "")], default='CONTAINER')
    export_texture_slots: BoolProperty(name="textureSlots", default=True)
    export_orfix_slots: BoolProperty(name="orfixSlots", default=False)
    export_toggle_swap_mode: EnumProperty(name="toggleSwapMode", items=[('None', "None", ""), ('DToggle', "DToggle", ""), ('RToggle', "RToggle", "")], default='None')
    addons: PointerProperty(type=RZMenuAddonSettings)
    conditions: CollectionProperty(type=RZMCondition)
    shapes: CollectionProperty(type=RZMShape)
    dependency_statuses: CollectionProperty(type=DependencyStatus)

classes_to_register = [
    RZMCaptureSettings, RZMenuImage, FXProperty, FNProperty, CustomProperty, RZMenuConfig, 
    ValueProperty, ToggleDefinition, BitProperty, AssignedToggle, ConditionalImage,
    ValueLinkProperty, RZMenuElement, TexResource, TexOverride, DecalConfig,
    AlternativeTexture, TexWorksAtlasConfig, TexWorksTextureConfig, TexWorksTexture, 
    RZMShapeKey, RZMShape, RZMenuAddonSettings, RZMCondition, DependencyStatus, RZMExportSettings, RZMenuProperties
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.rzm = PointerProperty(type=RZMenuProperties)
    # Регистрация scene properties
    bpy.types.Scene.rzm_active_element_index = IntProperty(name="Active Element Index")
    bpy.types.Scene.rzm_active_image_index = IntProperty(name="Active Image Index")
    bpy.types.Scene.rzm_active_value_index = IntProperty(name="Active Value Index")
    bpy.types.Scene.rzm_active_toggle_def_index = IntProperty(name="Active Toggle Definition Index")
    bpy.types.Scene.rzm_editor_mode = EnumProperty(name="Editor Mode", items=[('LIGHT', "Light", ""), ('PRO', "Pro", "")], default='LIGHT')
    bpy.types.Scene.rzm_show_debug_panel = BoolProperty(name="Show Debug Panel", default=False)
    bpy.types.Scene.rzm_capture_settings = PointerProperty(type=RZMCaptureSettings)
    bpy.types.Scene.rzm_capture_overwrite_id = IntProperty(name="Overwrite ID", default=-1)
    bpy.types.Scene.rzm_show_captures_preview = BoolProperty(name="Show Captures Preview", default=True)
    
    bpy.types.WindowManager.rzm_context_atlas_index = IntProperty(default=-1)
    bpy.types.WindowManager.rzm_dependency_install_status = StringProperty()

def unregister():
    del bpy.types.WindowManager.rzm_dependency_install_status
    del bpy.types.WindowManager.rzm_context_atlas_index
    del bpy.types.Scene.rzm_show_captures_preview
    del bpy.types.Scene.rzm_editor_mode
    del bpy.types.Scene.rzm_show_debug_panel
    del bpy.types.Scene.rzm_capture_settings
    del bpy.types.Scene.rzm_capture_overwrite_id
    del bpy.types.Scene.rzm
    del bpy.types.Scene.rzm_active_element_index
    del bpy.types.Scene.rzm_active_image_index
    del bpy.types.Scene.rzm_active_value_index
    del bpy.types.Scene.rzm_active_toggle_def_index
    
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)