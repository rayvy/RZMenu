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
    TexResource, TexOverride, TexWorksMaterial, 
    TexWorksDecalLayer, TexWorksSlot, TexWorksComponent, TexWorksMainBlock
)
from .p_ui import (
    FXProperty, FNProperty, CustomProperty, RZMenuElement, RZPresetReference, ConditionalText, RZFontSlotSettings
)
from .p_settings import (
    RZMenuConfig, DependencyStatus, RZMCustomScript, RZMExportSettings, RZMenuAddonSettings, RZMGameSettings, RZMMetaDataSettings, RZMCreditItem, RZMFeatureItem, RZM_AddonPreferences, 
)
from ..operators import custom_draw_ops

# --- ГЛАВНЫЙ КЛАСС (ROOT) ---
class RZMenuProperties(bpy.types.PropertyGroup):
    game: PointerProperty(type=RZMGameSettings)
    version: StringProperty(name="Version", default="3.5.0")
    config: PointerProperty(type=RZMenuConfig)
    meta_data: PointerProperty(type=RZMMetaDataSettings)
    export_settings: PointerProperty(type=RZMExportSettings)

    images: CollectionProperty(type=RZMenuImage)
    atlas_size: IntVectorProperty(name="Atlas Size", size=2)
    rzm_values: CollectionProperty(type=ValueProperty)
    toggle_definitions: CollectionProperty(type=ToggleDefinition)
    elements: CollectionProperty(type=RZMenuElement)
    element_to_add_class: EnumProperty(name="Class", items=[('CONTAINER', "Container", ""), ('GRID_CONTAINER', "Grid Container", ""), ('ANCHOR', "Anchor", ""), ('BUTTON', "Button", ""), ('SLIDER', "Slider", ""), ('TEXT', "Text", "")], default='CONTAINER')
    export_texture_slots: BoolProperty(name="textureSlots", default=True)
    export_toggle_swap_mode: EnumProperty(name="toggleSwapMode", items=[('None', "None", ""), ('DToggle', "DToggle", ""), ('RToggle', "RToggle", "")], default='None')
    addons: PointerProperty(type=RZMenuAddonSettings)
    conditions: CollectionProperty(type=RZMCondition)
    shapes: CollectionProperty(type=RZMShape)
    dependency_statuses: CollectionProperty(type=DependencyStatus)
    fonts: CollectionProperty(type=RZFontSlotSettings)

    # --- TexWorks Core ---
    tw_resources: CollectionProperty(type=TexResource)
    tw_overrides: CollectionProperty(type=TexOverride)
    tw_materials: CollectionProperty(type=TexWorksMaterial)
    tw_blocks: CollectionProperty(type=TexWorksMainBlock)
    
    active_tw_block_index: IntProperty()
    active_tw_resource_index: IntProperty()
    active_tw_material_index: IntProperty()
    tw_active_tab: EnumProperty(
        name="Tab",
        items=[
            ('RESOURCES', "Resources", ""),
            ('OVERRIDES', "Overrides", ""),
            ('MATERIALS', "Materials", ""),
            ('BLOCKS', "Blocks", "")
        ],
        default='RESOURCES'
    )
    tw_show_tags: BoolProperty(name="Show Tags", default=True)
    tw_show_res_details: BoolProperty(name="Show Details", default=False)

classes_to_register = [
    RZMCaptureSettings, RZMenuImage, FXProperty, FNProperty, CustomProperty, RZMenuConfig, 
    ValueProperty, ToggleDefinition, BitProperty, AssignedToggle, ConditionalImage,
    ValueLinkProperty, RZPresetReference, ConditionalText, RZFontSlotSettings, RZMenuElement, 
    TexResource, TexOverride, TexWorksMaterial, 
    TexWorksDecalLayer, TexWorksSlot, TexWorksComponent, TexWorksMainBlock,
    RZMShapeKey, RZMShape, RZMenuAddonSettings, RZMCondition, DependencyStatus, RZMCustomScript, RZMExportSettings, RZMGameSettings, RZMCreditItem, RZMFeatureItem, RZMMetaDataSettings, RZM_AddonPreferences, RZMenuProperties, 
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.rzm = PointerProperty(type=RZMenuProperties)
    custom_draw_ops.register()
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
    bpy.types.Scene.rzm_show_capture_tools = BoolProperty(name="Show Capture Tools", default=False)
    
    bpy.types.WindowManager.rzm_context_atlas_index = IntProperty(default=-1)
    bpy.types.WindowManager.rzm_dependency_install_status = StringProperty()

def unregister():
    del bpy.types.WindowManager.rzm_dependency_install_status
    del bpy.types.WindowManager.rzm_context_atlas_index
    del bpy.types.Scene.rzm_show_captures_preview
    del bpy.types.Scene.rzm_show_capture_tools
    del bpy.types.Scene.rzm_editor_mode
    del bpy.types.Scene.rzm_show_debug_panel
    del bpy.types.Scene.rzm_capture_settings
    del bpy.types.Scene.rzm_capture_overwrite_id
    del bpy.types.Scene.rzm
    custom_draw_ops.unregister()
    del bpy.types.Scene.rzm_active_element_index
    del bpy.types.Scene.rzm_active_image_index
    del bpy.types.Scene.rzm_active_value_index
    del bpy.types.Scene.rzm_active_toggle_def_index
    
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)