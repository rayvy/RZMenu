# RZMenu/data/properties.py
import bpy
from bpy.props import (
    StringProperty, IntProperty, FloatProperty, BoolProperty,
    IntVectorProperty, FloatVectorProperty, CollectionProperty, PointerProperty, EnumProperty,
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
    FXProperty, FNProperty, CustomProperty, RZMenuElement, RZPresetReference, RZHelperReference, ConditionalText, RZFontSlotSettings, RZMenuStyle, RZMLocalizedText
)
from .p_settings import (
    RZMenuConfig, DependencyStatus, RZMCustomScript, RZMExportSettings, RZMenuAddonSettings, RZMGameSettings, RZMMetaDataSettings, 
    RZMCreditItem, RZMFeatureItem, RZM_AddonPreferences, RZMAutoMenuSettings, RZMTierDefinition,
    RZM_ContactItem, RZM_BuildProfile, RZMCollectionPointer, RZMLanguage
)
from .p_blend_resize import RZMBResizeBakedBone, RZMBResizeBakedLayer, RZMComponentMapping, RZMBoneResizeGroup, RZMBResizeSettings
from .p_component_manager import RZMCM_PartDonor, RZMCM_Part, RZMCM_Component, RZMComponentManagerSettings
from ..operators import custom_draw_ops

class RZMVFXVertexCount(bpy.types.PropertyGroup):
    component_name: StringProperty(name="Component Name")
    vertex_count: IntProperty(name="Vertex Count", default=0)

# --- ГЛАВНЫЙ КЛАСС (ROOT) ---
class RZMenuProperties(bpy.types.PropertyGroup):
    game: PointerProperty(type=RZMGameSettings)
    version: StringProperty(name="Version", default="4.0.0")
    config: PointerProperty(type=RZMenuConfig)
    meta_data: PointerProperty(type=RZMMetaDataSettings)
    export_settings: PointerProperty(type=RZMExportSettings)
    auto_menu: PointerProperty(type=RZMAutoMenuSettings)
    component_manager: PointerProperty(type=RZMComponentManagerSettings)

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
    vfx_vertex_counts: CollectionProperty(type=RZMVFXVertexCount)

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
    ValueLinkProperty, RZPresetReference, RZHelperReference, RZMLocalizedText, ConditionalText, RZFontSlotSettings, RZMenuElement,
    TexResource, TexOverride, TexWorksMaterial,
    TexWorksDecalLayer, TexWorksSlot, TexWorksComponent, TexWorksMainBlock,
    RZMShapeKey, RZMShape,
    RZMObjectRef, ShapeKeyConfig,
    # ─ New API classes: RunLink and Keybind AFTER RZMShape ───────────────────────────
    RZMRunLink,
    RZMKeybind,
    # --- Register BlendResize before settings that point to it ---
    RZMBResizeBakedBone, RZMBResizeBakedLayer, RZMComponentMapping, RZMBoneResizeGroup, RZMBResizeSettings,
    RZMenuAddonSettings, RZMCondition, DependencyStatus, RZMCustomScript, RZMExportSettings, RZMGameSettings, RZMCreditItem, RZMFeatureItem, RZMLanguage, RZMMetaDataSettings,
    # ─ Tier system: RZMTierDefinition must be registered BEFORE RZM_AddonPreferences ─
    RZMTierDefinition,
    RZM_ContactItem,
    RZM_BuildProfile,
    RZMCollectionPointer,
    RZM_AddonPreferences,
    RZMAutoMenuSettings,
    RZMCM_PartDonor, RZMCM_Part, RZMCM_Component, RZMComponentManagerSettings,
    RZMVFXVertexCount,
    RZMenuProperties,
    RZModProducerSettings,
]
# Getter/Setter helper functions for VFX Curve properties to sync with custom ID-properties
def ensure_vfx_properties_initialized(self):
    if not self.get("RZM.CURVE_VFX"):
        return

    # If already migrated/initialized, skip to avoid overwriting edits
    if "RZM.CURVE_VFX.PARTICLE_SIZE_BASE" in self:
        return

    # Perform migration from legacy properties
    legacy_start = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_START")
    legacy_mesh_base = self.get("RZM.CURVE_VFX.MESH_FX_SIZE_BASE")
    legacy_base_size = self.get("RZM.CURVE_VFX.BASE_SIZE")

    # 1. Determine base size
    base_val = 0.05
    if legacy_start is not None:
        base_val = legacy_start
    elif legacy_mesh_base is not None:
        base_val = legacy_mesh_base
    elif legacy_base_size is not None:
        base_val = legacy_base_size

    self["RZM.CURVE_VFX.PARTICLE_SIZE_BASE"] = base_val

    # 2. Determine start scale (always 1.0 on migration, since base_val took its absolute value)
    self["RZM.CURVE_VFX.PARTICLE_SIZE_START"] = 1.0

    # 3. Determine end scale
    legacy_end = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_END")
    if legacy_end is not None:
        if base_val > 0.0:
            self["RZM.CURVE_VFX.PARTICLE_SIZE_END"] = legacy_end / base_val
        else:
            self["RZM.CURVE_VFX.PARTICLE_SIZE_END"] = 0.2
    else:
        self["RZM.CURVE_VFX.PARTICLE_SIZE_END"] = 0.2

    # 4. Initialize timeline positions
    if "RZM.CURVE_VFX.TIMELINE_START_POS" not in self:
        self["RZM.CURVE_VFX.TIMELINE_START_POS"] = 0.0
    if "RZM.CURVE_VFX.TIMELINE_MID_POS" not in self:
        self["RZM.CURVE_VFX.TIMELINE_MID_POS"] = 0.5
    if "RZM.CURVE_VFX.TIMELINE_END_POS" not in self:
        self["RZM.CURVE_VFX.TIMELINE_END_POS"] = 1.0

    # 5. Initialize other properties so they appear in custom properties immediately
    for key, default in [
        ("RZM.CURVE_VFX.PARTICLE_COUNT", 1),
        ("RZM.CURVE_VFX.DISPERSION_SCALE", 1.0),
        ("RZM.CURVE_VFX.CYCLE_DURATION", 2.0),
        ("RZM.CURVE_VFX.PHASE_RANDOMNESS", 1.0),
        ("RZM.CURVE_VFX.POS_RANDOMNESS", 0.0),
        ("RZM.CURVE_VFX.SIZE_RAND_MIN", 1.0),
        ("RZM.CURVE_VFX.SIZE_RAND_MAX", 1.0),
        ("RZM.CURVE_VFX.VISIBILITY_CONDITION", ""),
    ]:
        if key not in self:
            self[key] = default
            
    legacy_uv_min = self.get("RZM.CURVE_VFX.UV_MIN")
    legacy_uv_max = self.get("RZM.CURVE_VFX.UV_MAX")
    if "RZM.CURVE_VFX.UV_OFFSET" not in self:
        if legacy_uv_min is not None:
            self["RZM.CURVE_VFX.UV_OFFSET"] = list(legacy_uv_min)
        else:
            self["RZM.CURVE_VFX.UV_OFFSET"] = [0.0, 0.0]
    if "RZM.CURVE_VFX.UV_SCALE" not in self:
        if legacy_uv_min is not None and legacy_uv_max is not None:
            self["RZM.CURVE_VFX.UV_SCALE"] = [legacy_uv_max[0] - legacy_uv_min[0], legacy_uv_max[1] - legacy_uv_min[1]]
        else:
            self["RZM.CURVE_VFX.UV_SCALE"] = [1.0, 1.0]

    if "RZM.CURVE_VFX.MESH_FX_TYPE" not in self:
        self["RZM.CURVE_VFX.MESH_FX_TYPE"] = "0"

def get_vfx_enabled(self):
    return bool(self.get("RZM.CURVE_VFX", False))
def set_vfx_enabled(self, value):
    self["RZM.CURVE_VFX"] = value
    if value:
        ensure_vfx_properties_initialized(self)

def get_vfx_profile(self):
    val = self.get("RZM.CURVE_VFX.COORDINATE_REMAP_PROFILE", "AUTO")
    mapping = {"AUTO": 0, "NONE": 1, "ZENLESS_ZONE_ZERO": 2, "GENSHIN_IMPACT": 3}
    return mapping.get(val, 0)
def set_vfx_profile(self, value):
    mapping_rev = {0: "AUTO", 1: "NONE", 2: "ZENLESS_ZONE_ZERO", 3: "GENSHIN_IMPACT"}
    if isinstance(value, int):
        val_str = mapping_rev.get(value, "AUTO")
    else:
        val_str = str(value)
    self["RZM.CURVE_VFX.COORDINATE_REMAP_PROFILE"] = val_str

def get_vfx_size_base(self):
    val = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_BASE")
    if val is not None and val > 0.0:
        return float(val)
    # Compute from pixel size if available
    px = getattr(self, "rzm_curve_vfx_particle_size_px", 32)
    tex_w = getattr(self, "rzm_curve_vfx_texture_size", (512, 512))[0]
    if px and tex_w:
        return float(px) / max(int(tex_w), 1)
    # Fallback to legacy
    fallback = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_START")
    if fallback is None:
        fallback = self.get("RZM.CURVE_VFX.MESH_FX_SIZE_BASE")
        if fallback is None:
            fallback = self.get("RZM.CURVE_VFX.BASE_SIZE", 0.05)
    return float(fallback)

def set_vfx_size_base(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.PARTICLE_SIZE_BASE"] = value

def get_vfx_size_start(self):
    val = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_START")
    if val is not None:
        base = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_BASE")
        if base is None:
            return 1.0
        return val
    return 1.0
def set_vfx_size_start(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.PARTICLE_SIZE_START"] = value

def get_vfx_size_end(self):
    val = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_END")
    base = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_BASE")
    if base is None:
        # Legacy file: return end_abs / start_abs
        end_abs = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_END")
        if end_abs is None:
            return 0.2
        start_abs = self.get("RZM.CURVE_VFX.PARTICLE_SIZE_START")
        if start_abs is None:
            start_abs = self.get("RZM.CURVE_VFX.MESH_FX_SIZE_BASE", 0.05)
        if start_abs > 0.0:
            return end_abs / start_abs
        return 0.2
    
    if val is not None:
        return val
    return 0.2
def set_vfx_size_end(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.PARTICLE_SIZE_END"] = value

def get_vfx_tl_start(self):
    return self.get("RZM.CURVE_VFX.TIMELINE_START_POS", 0.0)
def set_vfx_tl_start(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.TIMELINE_START_POS"] = value

def get_vfx_tl_mid(self):
    return self.get("RZM.CURVE_VFX.TIMELINE_MID_POS", 0.5)
def set_vfx_tl_mid(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.TIMELINE_MID_POS"] = value

def get_vfx_tl_end(self):
    return self.get("RZM.CURVE_VFX.TIMELINE_END_POS", 1.0)
def set_vfx_tl_end(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.TIMELINE_END_POS"] = value

def get_vfx_dispersion_scale(self):
    return self.get("RZM.CURVE_VFX.DISPERSION_SCALE", 1.0)
def set_vfx_dispersion_scale(self, value):
    self["RZM.CURVE_VFX.DISPERSION_SCALE"] = value

def get_vfx_cycle_duration(self):
    val = self.get("RZM.CURVE_VFX.CYCLE_DURATION")
    if val is None:
        speed = self.get("RZM.CURVE_VFX.SPEED")
        if speed is not None and speed != 0.0:
            val = 1.0 / speed
        else:
            val = 2.0
    return val
def set_vfx_cycle_duration(self, value):
    self["RZM.CURVE_VFX.CYCLE_DURATION"] = value

def get_vfx_phase_randomness(self):
    return self.get("RZM.CURVE_VFX.PHASE_RANDOMNESS", 1.0)
def set_vfx_phase_randomness(self, value):
    self["RZM.CURVE_VFX.PHASE_RANDOMNESS"] = value

def get_vfx_pos_randomness(self):
    return self.get("RZM.CURVE_VFX.POS_RANDOMNESS", 0.0)
def set_vfx_pos_randomness(self, value):
    self["RZM.CURVE_VFX.POS_RANDOMNESS"] = value

def get_vfx_size_rand_min(self):
    return self.get("RZM.CURVE_VFX.SIZE_RAND_MIN", 1.0)
def set_vfx_size_rand_min(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.SIZE_RAND_MIN"] = value

def get_vfx_size_rand_max(self):
    return self.get("RZM.CURVE_VFX.SIZE_RAND_MAX", 1.0)
def set_vfx_size_rand_max(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.SIZE_RAND_MAX"] = value

def get_vfx_uv_offset(self):
    val = self.get("RZM.CURVE_VFX.UV_OFFSET", (0.0, 0.0))
    if len(val) < 2:
        val = list(val) + [0.0] * (2 - len(val))
    return tuple(float(x) for x in val[:2])
def set_vfx_uv_offset(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.UV_OFFSET"] = list(value)

def get_vfx_uv_scale(self):
    val = self.get("RZM.CURVE_VFX.UV_SCALE", (1.0, 1.0))
    if len(val) < 2:
        val = list(val) + [1.0] * (2 - len(val))
    return tuple(float(x) for x in val[:2])
def set_vfx_uv_scale(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.UV_SCALE"] = list(value)

def get_vfx_visibility_condition(self):
    return self.get("RZM.CURVE_VFX.VISIBILITY_CONDITION", "")
def set_vfx_visibility_condition(self, value):
    ensure_vfx_properties_initialized(self)
    self["RZM.CURVE_VFX.VISIBILITY_CONDITION"] = value

def get_vfx_type(self):
    val = self.get("RZM.CURVE_VFX.MESH_FX_TYPE", 0)
    try:
        val = int(val)
    except (ValueError, TypeError):
        val = 0
    if val not in {0, 1, 2, 3}:
        return 0
    return val
def set_vfx_type(self, value):
    try:
        self["RZM.CURVE_VFX.MESH_FX_TYPE"] = int(value)
    except (ValueError, TypeError):
        self["RZM.CURVE_VFX.MESH_FX_TYPE"] = 0

def get_vfx_particle_count(self):
    return self.get("RZM.CURVE_VFX.PARTICLE_COUNT", 1)
def set_vfx_particle_count(self, value):
    self["RZM.CURVE_VFX.PARTICLE_COUNT"] = value

def get_vfx_weight_indices(self):
    val = self.get("RZM.CURVE_VFX.WEIGHT_INDICES", (-1, -1, -1, -1))
    if len(val) < 4:
        val = list(val) + [-1] * (4 - len(val))
    return tuple(int(x) for x in val[:4])
def set_vfx_weight_indices(self, value):
    self["RZM.CURVE_VFX.WEIGHT_INDICES"] = list(value)

def get_vfx_weight_values(self):
    val = self.get("RZM.CURVE_VFX.WEIGHT_VALUES", (0.0, 0.0, 0.0, 0.0))
    if len(val) < 4:
        val = list(val) + [0.0] * (4 - len(val))
    return tuple(float(x) for x in val[:4])
def set_vfx_weight_values(self, value):
    self["RZM.CURVE_VFX.WEIGHT_VALUES"] = list(value)



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
    
    # --- RZM VFX Curve Properties ---
    bpy.types.Object.rzm_curve_vfx_enabled = BoolProperty(
        name="VFX Enabled",
        description="Enable VFX on this curve object",
        get=get_vfx_enabled,
        set=set_vfx_enabled
    )
    bpy.types.Object.rzm_curve_vfx_coordinate_remap_profile = EnumProperty(
        name="Coordinate Remap",
        description="How curve coordinates should be remapped",
        items=[
            ("AUTO", "Auto", "Use the current RZM game selection"),
            ("NONE", "None", "Do not remap curve coordinates"),
            ("ZENLESS_ZONE_ZERO", "Zenless Zone Zero", "Swap Y/Z for ZZZ buffer space"),
            ("GENSHIN_IMPACT", "Genshin Impact", "Swap Y/Z, then rotate around point 0 by X Euler -90 degrees"),
        ],
        get=get_vfx_profile,
        set=set_vfx_profile
    )
    bpy.types.Object.rzm_curve_vfx_particle_size_base = FloatProperty(
        name="Base Size",
        description="Base particle size (in meters)",
        min=0.0,
        precision=6,
        get=get_vfx_size_base,
        set=set_vfx_size_base
    )
    bpy.types.Object.rzm_curve_vfx_particle_size_start = FloatProperty(
        name="Start Size Scale",
        description="Particle size scale factor at start (e.g. 1.0 = 100%, 2.0 = 200%)",
        min=0.0,
        max=2.0,
        precision=6,
        get=get_vfx_size_start,
        set=set_vfx_size_start
    )
    bpy.types.Object.rzm_curve_vfx_particle_size_end = FloatProperty(
        name="End Size Scale",
        description="Particle size scale factor at end (e.g. 0.2 = 20%, 2.0 = 200%)",
        min=0.0,
        max=2.0,
        precision=6,
        get=get_vfx_size_end,
        set=set_vfx_size_end
    )
    bpy.types.Object.rzm_curve_vfx_timeline_start_pos = FloatProperty(
        name="Timeline Start Time",
        description="Time fraction (0.0 to 1.0) when the particle starts moving from the path start",
        min=0.0,
        max=1.0,
        precision=6,
        get=get_vfx_tl_start,
        set=set_vfx_tl_start
    )
    bpy.types.Object.rzm_curve_vfx_timeline_mid_pos = FloatProperty(
        name="Timeline Mid Time",
        description="Time fraction (0.0 to 1.0) when the particle reaches 50% of the path",
        min=0.0,
        max=1.0,
        precision=6,
        get=get_vfx_tl_mid,
        set=set_vfx_tl_mid
    )
    bpy.types.Object.rzm_curve_vfx_timeline_end_pos = FloatProperty(
        name="Timeline End Time",
        description="Time fraction (0.0 to 1.0) when the particle reaches the path end and fades out",
        min=0.0,
        max=1.0,
        precision=6,
        get=get_vfx_tl_end,
        set=set_vfx_tl_end
    )
    bpy.types.Object.rzm_curve_vfx_dispersion_scale = FloatProperty(
        name="Dispersion Scale",
        description="Overall scale multiplier for curve control point radius",
        min=0.0,
        precision=6,
        get=get_vfx_dispersion_scale,
        set=set_vfx_dispersion_scale
    )
    bpy.types.Object.rzm_curve_vfx_cycle_duration = FloatProperty(
        name="Cycle Duration",
        description="Duration of a full animation cycle in seconds",
        min=0.01,
        precision=6,
        get=get_vfx_cycle_duration,
        set=set_vfx_cycle_duration
    )
    bpy.types.Object.rzm_curve_vfx_phase_randomness = FloatProperty(
        name="Phase Randomness",
        description="Randomness of particle birth phases (0 = clump/beam, 1 = continuous stream)",
        min=0.0,
        max=1.0,
        precision=6,
        get=get_vfx_phase_randomness,
        set=set_vfx_phase_randomness
    )
    bpy.types.Object.rzm_curve_vfx_pos_randomness = FloatProperty(
        name="Position Randomness",
        description="Intensity of chaotic position noise / jitter",
        min=0.0,
        precision=6,
        get=get_vfx_pos_randomness,
        set=set_vfx_pos_randomness
    )
    bpy.types.Object.rzm_curve_vfx_size_rand_min = FloatProperty(
        name="Size Randomness Min",
        description="Minimum random size multiplier (e.g. 0.5 = 50% minimum scale)",
        min=0.0,
        max=2.0,
        precision=6,
        get=get_vfx_size_rand_min,
        set=set_vfx_size_rand_min
    )
    bpy.types.Object.rzm_curve_vfx_size_rand_max = FloatProperty(
        name="Size Randomness Max",
        description="Maximum random size multiplier (e.g. 1.5 = 150% maximum scale)",
        min=0.0,
        max=2.0,
        precision=6,
        get=get_vfx_size_rand_max,
        set=set_vfx_size_rand_max
    )
    bpy.types.Object.rzm_curve_vfx_uv_offset = FloatVectorProperty(
        name="UV Offset",
        description="UV coordinates offset (U, V)",
        size=2,
        precision=6,
        get=get_vfx_uv_offset,
        set=set_vfx_uv_offset
    )
    bpy.types.Object.rzm_curve_vfx_uv_scale = FloatVectorProperty(
        name="UV Scale",
        description="UV coordinates scale (U, V)",
        size=2,
        precision=6,
        get=get_vfx_uv_scale,
        set=set_vfx_uv_scale
    )
    bpy.types.Object.rzm_curve_vfx_visibility_condition = StringProperty(
        name="Visibility Condition",
        description="Optional visibility condition (e.g. $active_anim == 1) to wrap the drawindexed command",
        get=get_vfx_visibility_condition,
        set=set_vfx_visibility_condition
    )
    bpy.types.Object.rzm_curve_vfx_mesh_fx_type = EnumProperty(
        name="Mesh FX Type",
        items=[
            ("0", "Triangle",    "3 verts, 1 triangle"),
            ("1", "Quad",        "4 verts, 2 triangles"),
            ("2", "Circle",      "7 verts, 6 triangles (hexagon fan)"),
            ("3", "Custom Mesh", "Use an arbitrary mesh object as particle shape (Stage 2)"),
        ],
        get=get_vfx_type,
        set=set_vfx_type
    )
    bpy.types.Object.rzm_curve_vfx_particle_count = IntProperty(
        name="Particle Count",
        description="How many particles this curve object should emit",
        min=0,
        get=get_vfx_particle_count,
        set=set_vfx_particle_count
    )
    bpy.types.Object.rzm_curve_vfx_weight_indices = IntVectorProperty(
        name="Weight Indices",
        description="Up to 4 technical bind indices; -1 means unused",
        size=4,
        min=-1,
        max=999999,
        get=get_vfx_weight_indices,
        set=set_vfx_weight_indices
    )
    bpy.types.Object.rzm_curve_vfx_weight_values = FloatVectorProperty(
        name="Weight Values",
        description="Up to 4 technical bind weights",
        size=4,
        min=0.0,
        max=1.0,
        precision=6,
        get=get_vfx_weight_values,
        set=set_vfx_weight_values
    )
    bpy.types.Object.rzm_curve_vfx_weight_reference = PointerProperty(
        name="Weight Reference Mesh",
        description="Reference mesh to copy weights from via closest vertex lookup",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
    )
    bpy.types.Object.rzm_curve_vfx_custom_mesh = PointerProperty(
        name="Custom Particle Mesh",
        description="(Stage 2) Arbitrary mesh to use as particle shape. When set, particle_size_base and UV settings are ignored.",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
    )
    bpy.types.Object.rzm_curve_vfx_texture_size = IntVectorProperty(
        name="Texture Size",
        description="Particle texture dimensions in pixels (W, H). Used to compute Base Size float.",
        size=2,
        default=(512, 512),
        min=1
    )
    bpy.types.Object.rzm_curve_vfx_particle_size_px = IntProperty(
        name="Particle Size (px)",
        description="Particle size in pixels. Converted to float: px / Texture Width. Set Base Size > 0 to override.",
        default=32,
        min=1
    )
    bpy.types.Object.rzm_curve_vfx_uv_px_offset = IntVectorProperty(
        name="UV Sprite Offset (px)",
        description="Top-left corner of the sprite in the atlas, in pixels (U, V)",
        size=2,
        default=(0, 0),
        min=0
    )
    bpy.types.Object.rzm_curve_vfx_uv_px_size = IntVectorProperty(
        name="UV Sprite Size (px)",
        description="Width and height of the sprite in the atlas, in pixels",
        size=2,
        default=(32, 32),
        min=1
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
    
    # --- Component Manager Active Indices ---
    bpy.types.Scene.rzm_cm_active_comp_index = IntProperty(name="Active CM Comp Index", default=-1)
    bpy.types.Scene.rzm_cm_active_part_index = IntProperty(name="Active CM Part Index", default=-1)

    bpy.types.Scene.rzm_editor_mode = EnumProperty(name="Editor Mode", items=[('LIGHT', "Light", ""), ('PRO', "Pro", "")], default='LIGHT')
    bpy.types.Scene.rzm_show_debug_panel = BoolProperty(name="Show Debug Panel", default=False)
    bpy.types.Scene.rzm_capture_settings = PointerProperty(type=RZMCaptureSettings)
    bpy.types.Scene.rzm_capture_overwrite_id = IntProperty(name="Overwrite ID", default=-1)
    bpy.types.Scene.rzm_show_captures_preview = BoolProperty(name="Show Captures Preview", default=True)
    bpy.types.Scene.rzm_show_capture_tools = BoolProperty(name="Show Capture Tools", default=False)
    bpy.types.Scene.rzm_show_component_manager = BoolProperty(name="Show Component Manager", default=False)
    bpy.types.Scene.rzm_show_material_transfer = BoolProperty(name="Show Material Transfer", default=False)
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
    del bpy.types.Scene.rzm_cm_active_comp_index
    del bpy.types.Scene.rzm_cm_active_part_index
    if hasattr(bpy.types.Object, "rzm_tier_list"):
        del bpy.types.Object.rzm_tier_list
        
    for attr in [
        "rzm_curve_vfx_enabled",
        "rzm_curve_vfx_coordinate_remap_profile",
        "rzm_curve_vfx_mesh_fx_size_base",
        "rzm_curve_vfx_particle_size_base",
        "rzm_curve_vfx_particle_size_start",
        "rzm_curve_vfx_particle_size_end",
        "rzm_curve_vfx_timeline_start_pos",
        "rzm_curve_vfx_timeline_mid_pos",
        "rzm_curve_vfx_timeline_end_pos",
        "rzm_curve_vfx_dispersion_scale",
        "rzm_curve_vfx_cycle_duration",
        "rzm_curve_vfx_phase_randomness",
        "rzm_curve_vfx_pos_randomness",
        "rzm_curve_vfx_size_rand_min",
        "rzm_curve_vfx_size_rand_max",
        "rzm_curve_vfx_uv_offset",
        "rzm_curve_vfx_uv_scale",
        "rzm_curve_vfx_visibility_condition",
        "rzm_curve_vfx_tri_aspect",
        "rzm_curve_vfx_speed",
        "rzm_curve_vfx_mesh_fx_type",
        "rzm_curve_vfx_particle_count",
        "rzm_curve_vfx_weight_indices",
        "rzm_curve_vfx_weight_values",
        "rzm_curve_vfx_weight_reference",
        "rzm_curve_vfx_custom_mesh",
        "rzm_curve_vfx_texture_size",
        "rzm_curve_vfx_particle_size_px",
        "rzm_curve_vfx_uv_px_offset",
        "rzm_curve_vfx_uv_px_size",
        "rzm_curve_vfx_start_radius",
        "rzm_curve_vfx_end_radius",
        "rzm_curve_vfx_curve_right",
        "rzm_curve_vfx_curve_up"
    ]:
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)

    custom_draw_ops.unregister()
    del bpy.types.Scene.rzm_active_element_index
    del bpy.types.Scene.rzm_active_image_index
    del bpy.types.Scene.rzm_active_value_index
    del bpy.types.Scene.rzm_active_toggle_def_index
    
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)