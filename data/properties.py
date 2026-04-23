# RZMenu/data/properties.py
import bpy
from bpy.props import (
    StringProperty, IntProperty, FloatProperty, BoolProperty,
    IntVectorProperty, CollectionProperty, PointerProperty, EnumProperty,
)

# Импорт из под-модулей в той же папке data
from .p_images import RZMCaptureSettings, RZMenuImage, ConditionalImage, RZMenuAnimationFrame, RZMenuAnimationSequence, RZMenuSVGVariation
from .p_logic import (
    ValueLinkProperty, ValueProperty, ToggleDefinition,
    BitProperty, AssignedToggle, RZMCondition,
    RZMShapeKey, RZMShape, RZMTierRef,
    RZMProfileValue, RZMRunLink, RZMKeybind,
    RZMObjectRef, ShapeKeyConfig
)
from .p_texworks import (
    TexResource, TexOverride, TexWorksMaterial, 
    TexWorksDecalLayer, TexWorksSlot, TexWorksComponent, TexWorksMainBlock
)
from .p_ui import (
    FXProperty, FNProperty, CustomProperty, RZMenuElement, RZPresetReference, RZHelperReference, ConditionalText, RZFontSlotSettings, RZMenuStyle
)
from .p_settings import (
    RZMenuConfig, DependencyStatus, RZMCustomScript, RZMExportSettings, RZMenuAddonSettings, RZMGameSettings, RZMMetaDataSettings, 
    RZMCreditItem, RZMFeatureItem, RZM_AddonPreferences, RZMAutoMenuSettings, RZMTierDefinition,
    RZM_ContactItem, RZM_BuildProfile, RZMCollectionPointer
)
from .p_blend_resize import RZMBResizeBakedBone, RZMBResizeBakedLayer, RZMComponentMapping, RZMBoneResizeGroup, RZMBResizeSettings
from ..operators import custom_draw_ops

# --- ГЛАВНЫЙ КЛАСС (ROOT) ---
class RZMenuProperties(bpy.types.PropertyGroup):
    game: PointerProperty(type=RZMGameSettings)
    version: StringProperty(name="Version", default="3.9.2")
    config: PointerProperty(type=RZMenuConfig)
    meta_data: PointerProperty(type=RZMMetaDataSettings)
    export_settings: PointerProperty(type=RZMExportSettings)
    auto_menu: PointerProperty(type=RZMAutoMenuSettings)

    images: CollectionProperty(type=RZMenuImage)
    atlas_size: IntVectorProperty(name="Atlas Size", size=2)
    rzm_values: CollectionProperty(type=ValueProperty)
    toggle_definitions: CollectionProperty(type=ToggleDefinition)
    styles: CollectionProperty(type=RZMenuStyle)
    styles_index: IntProperty(default=0)
    elements: CollectionProperty(type=RZMenuElement)
    element_to_add_class: EnumProperty(name="Class", items=[('CONTAINER', "Container", ""), ('GRID_CONTAINER', "Grid Container", ""), ('ANCHOR', "Anchor", ""), ('BUTTON', "Button", ""), ('SLIDER', "Slider", ""), ('TEXT', "Text", ""), ('VECTOR_BOX', "Vector Box", "")], default='CONTAINER')
    export_texture_slots: BoolProperty(name="textureSlots", default=True)
    export_toggle_swap_mode: EnumProperty(name="toggleSwapMode", items=[('None', "None", ""), ('DToggle', "DToggle", ""), ('RToggle', "RToggle", "")], default='None')
    addons: PointerProperty(type=RZMenuAddonSettings)

    @property
    def author_name_global(self):
        from .p_settings import RZM_AddonPreferences
        addon_name = __package__.split(".")[0]
        prefs = bpy.context.preferences.addons.get(addon_name)
        if prefs and prefs.preferences:
            return prefs.preferences.author_name
        return "UNKNOWN"
    
    conditions: CollectionProperty(type=RZMShape)
    shapes: CollectionProperty(type=RZMShape)
    
    # --- New ShapeKeyConfig System ---
    shape_configs: CollectionProperty(type=ShapeKeyConfig)
    shape_discovery_collections: CollectionProperty(type=RZMCollectionPointer)
    
    dependency_statuses: CollectionProperty(type=DependencyStatus)
    fonts: CollectionProperty(type=RZFontSlotSettings)

    master_shape_value: FloatProperty(
        name="Master Shape Value",
        description="Value to apply globally to all discovered shape keys",
        min=0.0, max=1.0,
        default=0.0
    )

    # ─── Run Links (named CommandLists / API actions) ───────────────────────────
    run_links: CollectionProperty(
        type=RZMRunLink,
        name="Run Links",
        description="Именованные CommandList-ы мода — вызываемые функции."
    )

    # ─── Keybinds ──────────────────────────────────────────────────────────────
    keybinds: CollectionProperty(
        type=RZMKeybind,
        name="Keybinds",
        description="Горячие клавиши игры, привязанные к RunLink-ам."
    )

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

    # ─── Text Mapping (Persistent) ───
    # Stores JSON-serialized mapping of element keys to (text_id, length)
    text_mapping_json: StringProperty(name="Text Mapping JSON", default="{}")

    # ─── Image Mapping (Persistent) ───
    # Stores JSON-serialized mapping of image sources (ID/Animation/SVG) to buffer indices
    image_mapping_json: StringProperty(name="Image Mapping JSON", default="{}")

    @property
    def text_mapping(self):
        import json
        defaults = {"single": {}, "conditional": {}}
        try:
            data = json.loads(self.text_mapping_json)
            if isinstance(data, dict):
                defaults.update(data)
        except:
            pass
        return defaults

    @property
    def image_mapping(self):
        import json
        defaults = {"static": {}, "animated": {}, "vector": {}, "elements": {}}
        try:
            data = json.loads(self.image_mapping_json)
            if isinstance(data, dict):
                defaults.update(data)
        except:
            pass
        return defaults

class RZModProducerSettings(bpy.types.PropertyGroup):
    build_suffix: StringProperty(
        name="Build Suffix",
        description="Suffix for this build (e.g., Premium_NSFW)",
        default=""
    )
    active_tiers: StringProperty(
        name="Active Tiers",
        description="Comma-separated tier IDs active for this build",
        default=""
    )

classes_to_register = [
    # ─ RZMTierRef FIRST: used by CollectionProperty in ValueProperty, RZMShape, RZMenuElement ─
    RZMTierRef,
    # ─ RZMProfileValue BEFORE ValueProperty / ToggleDefinition / RZMShape ──────────────────
    RZMProfileValue,
    RZMenuStyle, RZMCaptureSettings, RZMenuAnimationFrame, RZMenuAnimationSequence, RZMenuSVGVariation, RZMenuImage, FXProperty, FNProperty, CustomProperty, RZMenuConfig,
    ValueProperty, ToggleDefinition, BitProperty, AssignedToggle, ConditionalImage,
    ValueLinkProperty, RZPresetReference, RZHelperReference, ConditionalText, RZFontSlotSettings, RZMenuElement,
    TexResource, TexOverride, TexWorksMaterial,
    TexWorksDecalLayer, TexWorksSlot, TexWorksComponent, TexWorksMainBlock,
    RZMShapeKey, RZMShape,
    RZMObjectRef, ShapeKeyConfig,
    # ─ New API classes: RunLink and Keybind AFTER RZMShape ───────────────────────────
    RZMRunLink,
    RZMKeybind,
    # --- Register BlendResize before settings that point to it ---
    RZMBResizeBakedBone, RZMBResizeBakedLayer, RZMComponentMapping, RZMBoneResizeGroup, RZMBResizeSettings,
    RZMenuAddonSettings, RZMCondition, DependencyStatus, RZMCustomScript, RZMExportSettings, RZMGameSettings, RZMCreditItem, RZMFeatureItem, RZMMetaDataSettings,
    # ─ Tier system: RZMTierDefinition must be registered BEFORE RZM_AddonPreferences ─
    RZMTierDefinition,
    RZM_ContactItem,
    RZM_BuildProfile,
    RZMCollectionPointer,
    RZM_AddonPreferences,
    RZMAutoMenuSettings, RZMenuProperties,
    RZModProducerSettings,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.rzm = PointerProperty(type=RZMenuProperties)
    bpy.types.Scene.rzm_mod_producer = PointerProperty(type=RZModProducerSettings)
    bpy.types.Object.rzm_tier_list = CollectionProperty(
        type=RZMTierRef,
        name="Export Tiers",
        description="Тиры Mod Producer для этого мэша. Пусто = все тиры."
    )
    custom_draw_ops.register()
    # Регистрация scene properties
    bpy.types.Scene.rzm_active_element_index = IntProperty(name="Active Element Index")
    bpy.types.Scene.rzm_active_image_index = IntProperty(name="Active Image Index")
    bpy.types.Scene.rzm_active_value_index = IntProperty(name="Active Value Index")
    bpy.types.Scene.rzm_active_toggle_def_index = IntProperty(name="Active Toggle Definition Index")
    bpy.types.Scene.rzm_active_shape_index = IntProperty(name="Active Shape Index")
    bpy.types.Scene.rzm_active_shape_key_index = IntProperty(name="Active Shape Key Index")
    bpy.types.Scene.rzm_active_shape_config_index = IntProperty(name="Active Shape Config Index")
    bpy.types.Scene.rzm_active_shape_coll_index = IntProperty(name="Active Shape Collection Index")
    bpy.types.Scene.rzm_active_run_link_index = IntProperty(name="Active Run Link Index")
    bpy.types.Scene.rzm_active_keybind_index = IntProperty(name="Active Keybind Index")
    
    # --- BlendResize Active Indices ---
    bpy.types.Scene.rzm_active_br_group_index = IntProperty(name="Active BR Group Index", default=-1)
    bpy.types.Scene.rzm_active_br_comp_index = IntProperty(name="Active BR Component Index", default=-1)
    bpy.types.Scene.rzm_active_br_bone_index = IntProperty(name="Active BR Bone Index", default=-1)
    bpy.types.Scene.rzm_editor_mode = EnumProperty(name="Editor Mode", items=[('LIGHT', "Light", ""), ('PRO', "Pro", "")], default='LIGHT')
    bpy.types.Scene.rzm_show_debug_panel = BoolProperty(name="Show Debug Panel", default=False)
    bpy.types.Scene.rzm_capture_settings = PointerProperty(type=RZMCaptureSettings)
    bpy.types.Scene.rzm_capture_overwrite_id = IntProperty(name="Overwrite ID", default=-1)
    bpy.types.Scene.rzm_show_captures_preview = BoolProperty(name="Show Captures Preview", default=True)
    bpy.types.Scene.rzm_show_capture_tools = BoolProperty(name="Show Capture Tools", default=False)
    bpy.types.Scene.rzm_toolbox_tab = EnumProperty(
        name="Toolbox Tab",
        items=[
            ('TOGGLES',   "Toggles",   "Manage object toggles"),
            ('VARIABLES', "Variables", "Manage global project values"),
            ('SHAPES',    "Shapes (Legacy)", "Manage legacy manual shape keys"),
            ('NATIVE_SHAPES', "Native Shapes", "Manage discovered Blender shape keys"),
            ('KEYBINDS',  "Keybinds",  "Manage in-game hotkeys and RunLinks"),
            ('BLEND_RESIZE', "Blend Resize", "Manage bone-based resizing"),
        ],
        default='TOGGLES'
    )
    
    bpy.types.WindowManager.rzm_context_atlas_index = IntProperty(default=-1)
    bpy.types.WindowManager.rzm_dependency_install_status = StringProperty()

def unregister():
    del bpy.types.WindowManager.rzm_dependency_install_status
    del bpy.types.WindowManager.rzm_context_atlas_index
    del bpy.types.Scene.rzm_show_captures_preview
    del bpy.types.Scene.rzm_show_capture_tools
    del bpy.types.Scene.rzm_toolbox_tab
    del bpy.types.Scene.rzm_editor_mode
    del bpy.types.Scene.rzm_show_debug_panel
    del bpy.types.Scene.rzm_capture_settings
    del bpy.types.Scene.rzm_capture_overwrite_id
    del bpy.types.Scene.rzm_mod_producer
    del bpy.types.Scene.rzm
    del bpy.types.Scene.rzm_active_run_link_index
    del bpy.types.Scene.rzm_active_keybind_index
    if hasattr(bpy.types.Object, "rzm_tier_list"):
        del bpy.types.Object.rzm_tier_list
    custom_draw_ops.unregister()
    del bpy.types.Scene.rzm_active_element_index
    del bpy.types.Scene.rzm_active_image_index
    del bpy.types.Scene.rzm_active_value_index
    del bpy.types.Scene.rzm_active_toggle_def_index
    
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)