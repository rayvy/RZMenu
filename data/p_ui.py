# RZMenu/data/p_ui.py
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty, IntVectorProperty, FloatVectorProperty

# Импорт констант и зависимых типов из соседних файлов data
from .constants import FX_COMMANDS, FN_COMMANDS
from .p_images import ConditionalImage, mark_atlas_dirty_img
from .p_logic import ValueLinkProperty, AssignedToggle, RZMTierRef

class FXProperty(bpy.types.PropertyGroup): value: EnumProperty(name="Effect", items=FX_COMMANDS)
class FNProperty(bpy.types.PropertyGroup): function_name: EnumProperty(name="Function", items=FN_COMMANDS)

def mark_atlas_dirty(self, context):
    """Sets the atlas dirty flag to True when an image-related property changes."""
    if hasattr(context.scene, "rzm"):
        context.scene.rzm.export_settings.atlas_is_dirty = True

class RZFontSlotSettings(bpy.types.PropertyGroup):
    font_source: EnumProperty(
        name="Font Source",
        items=[
            ('DEFAULT', "Windows Arial (Default)", ""),
            ('CUSTOM', "Custom / System Search", ""),
            # Legacy keys (for compatibility with old .blend files)
            ('ARIAL', "Arial (Legacy)", ""),
            ('CONSOLAS', "Consolas (Legacy)", ""),
            ('SEGOE', "Segoe UI (Legacy)", ""),
            ('SYSTEM', "System (Legacy)", "")
        ],
        default='DEFAULT'
    )
    custom_path: StringProperty(name="Font Path", subtype='FILE_PATH', description="Path to .ttf, .otf, or .ttc file")
    font_style_name: StringProperty(name="Font Style", default="Regular", description="Style variant (e.g. 'Bold', 'Condensed Light', 'Italic')")
    font_index: IntProperty(name="Font Index", default=0, min=0, max=99, description="Font index within .ttc collections (0 = first font)")
    cell_size: IntProperty(name="Cell Size", min=16, max=256, default=32)
    density: FloatProperty(name="Density", min=0.1, max=1.0, default=0.88)

class CustomProperty(bpy.types.PropertyGroup):
    key: StringProperty(name="Key"); value_type: EnumProperty(name="Type", items=[('STRING', "String", ""), ('INT', "Integer", ""), ('FLOAT', "Float", "")], default='STRING')
    string_value: StringProperty(name="String Value"); int_value: IntProperty(name="Int Value"); float_value: FloatProperty(name="Float Value")

class RZPresetReference(bpy.types.PropertyGroup):
    preset_id: IntProperty(name="Preset ID")

class RZHelperReference(bpy.types.PropertyGroup):
    helper_id: IntProperty(name="Helper ID")

class ConditionalText(bpy.types.PropertyGroup):
    text_id: StringProperty(name="Text", default="New Text")
    condition: StringProperty(name="Condition", description="Condition to show this text (e.g. $var > 0)")

class RZMenuStyle(bpy.types.PropertyGroup):
    name: StringProperty(name="Style Name", default="New Style")
    
    use_shadow: BoolProperty(name="Drop Shadow", default=False)
    shadow_offset: FloatVectorProperty(name="Offset X/Y", size=2, default=(2.0, 2.0))
    shadow_blur: FloatProperty(name="Blur", default=4.0)
    shadow_color: FloatVectorProperty(name="Color", subtype='COLOR', size=4, min=0, max=1, default=(0.0, 0.0, 0.0, 0.8))

    use_glow: BoolProperty(name="Outer Glow", default=False)
    glow_radius: FloatProperty(name="Radius", default=10.0)
    glow_intensity: FloatProperty(name="Intensity", default=2.0)
    glow_color: FloatVectorProperty(name="Color", subtype='COLOR', size=4, min=0, max=1, default=(0.0, 0.5, 1.0, 1.0))

    use_outline: BoolProperty(name="Outline", default=False)
    outline_thickness: FloatProperty(name="Thickness", default=1.0)
    outline_color: FloatVectorProperty(name="Color", subtype='COLOR', size=4, min=0, max=1, default=(1.0, 1.0, 1.0, 1.0))

    use_grayscale: BoolProperty(name="Grayscale", default=False)
    grayscale_amount: FloatProperty(name="Amount", default=1.0, min=0.0, max=1.0)

    use_chromatic: BoolProperty(name="Chromatic Aberration", default=False)
    chromatic_offset: FloatProperty(name="Offset", default=2.0)

    use_gradient: BoolProperty(name="Gradient Overlay", default=False)
    grad_color_1: FloatVectorProperty(name="Color 1", subtype='COLOR', size=4, min=0, max=1, default=(1.0, 1.0, 1.0, 1.0))
    grad_color_2: FloatVectorProperty(name="Color 2", subtype='COLOR', size=4, min=0, max=1, default=(0.0, 0.0, 0.0, 0.8))
    grad_angle: FloatProperty(name="Angle (Deg)", default=90.0)

    anim_hover_resize: BoolProperty(name="Hover Resize", default=False)
    hover_scale_factor: FloatProperty(name="Expand Scale", default=1.125)

    anim_hover_sheen: BoolProperty(name="Hover Sheen", default=False)
    sheen_speed: FloatProperty(name="Speed", default=1.0)
    sheen_width: FloatProperty(name="Width", default=0.2)
    sheen_color: FloatVectorProperty(name="Color", subtype='COLOR', size=4, min=0, max=1, default=(1.0, 1.0, 1.0, 0.5))

    anim_rotate: BoolProperty(name="Constant Map Rotation", default=False)
    rotate_speed: FloatProperty(name="Speed", default=1.0)

    use_blur: BoolProperty(name="Enable Blur", default=False)
    blur_strength: FloatProperty(name="Blur Strength", default=1.0, min=0.0, max=10.0)
    use_blur_mask: BoolProperty(name="Blur Mask Mode", default=False)

    fn_fix_ratio: BoolProperty(name="Fix Image Aspect Ratio", default=False)


class RZMenuElement(bpy.types.PropertyGroup):
    element_name: StringProperty(name="Name"); id: IntProperty(name="Unique ID"); parent_id: IntProperty(name="Parent ID", default=-1)
    is_preset: BoolProperty(name="Is Preset", default=False)
    is_helper: BoolProperty(name="Is Helper", default=False, description="Marks this element as a helper (functional supplement, not just visual). Helpers are exported as full elements with offset IDs and support ~ParentValue substitution")
    is_template_prefab: BoolProperty(name="Is Template Prefab", default=False, description="Marks this element as a template prefab for menu auto-generation")
    template_prefab: EnumProperty(name="Prefab Type", items=[
        ('MAIN_BLOCK', "Main Block", "Root container prefab for the main menu block"),
        ('PAGE_BLOCK', "Page Block", "Container prefab for a page/tab block"),
        ('BUTTONS', "Buttons", "Prefab for a button group or single button"),
    ], default='MAIN_BLOCK')
    priority: IntProperty(name="Priority", default=0); tag: StringProperty(name="Tag")
    qt_priority: IntProperty(name="QT Priority", default=0)
    elem_class: EnumProperty( name="Class", items=[('CONTAINER', "Container", ""), ('GRID_CONTAINER', "Grid Container", ""), ('ANCHOR', "Anchor", ""), ('BUTTON', "Button", ""), ('SLIDER', "Slider", ""), ('TEXT', "Text", ""), ('VECTOR_BOX', "Vector Box", "")], default='CONTAINER')
    visibility_mode: EnumProperty(name="Visibility", items=[('ALWAYS', "Always Visible", ""), ('CONDITIONAL', "Conditional", ""), ('HIDED', "Hided", "")], default='ALWAYS')
    visibility_condition: StringProperty(name="Condition", description="e.g., $var > 0 or @ToggleA[1]")
    # Transform - Formula flags
    position_is_formula: BoolProperty(name="Position Formula Mode")
    size_is_formula: BoolProperty(name="Size Formula Mode")
    rotation_is_formula: BoolProperty(name="Rotation Formula Mode")
    transform_is_formula: BoolProperty(name="Transform Formula Mode")

    # Vector Box Options
    disable_default_xy: BoolProperty(name="Disable Default XY", description="Disables default X/Y slider-like logic for Vector Box tracker", default=False)

    # Transform - Static Values
    position: IntVectorProperty(name="Position", size=2, default=(0, 0))
    size: IntVectorProperty(name="Size", size=2, default=(100, 30))
    rotation: FloatProperty(name="Rotation", default=0.0)

    # Transform - Formulas
    position_formula_x: StringProperty(name="X Formula")
    position_formula_y: StringProperty(name="Y Formula")
    size_formula_x: StringProperty(name="W Formula")
    size_formula_y: StringProperty(name="H Formula")
    rotation_formula: StringProperty(name="Rotation Formula")
    transform_formula: StringProperty(name="Transform formula", description="Raw code transformation, not affect to position and size formula", default="")
    alignment: EnumProperty(name="Alignment", items=[('BOTTOM_LEFT', "Bottom Left", ""), ('BOTTOM_CENTER', "Bottom Center", ""), ('BOTTOM_RIGHT', "Bottom Right", ""), ('CENTER_LEFT', "Center Left", ""), ('CENTER', "Center", ""), ('CENTER_RIGHT', "Center Right", ""), ('TOP_LEFT', "Top Left", ""), ('TOP_CENTER', "Top Center", ""), ('TOP_RIGHT', "Top Right", "")], default='BOTTOM_LEFT')
    text_align: EnumProperty(name="Text Align", items=[('LEFT', "Left", ""), ('CENTER', "Center", ""), ('RIGHT', "Right", ""), ('FREE_LEFT', "Free Left", ""), ('FREE_CENTER', "Free Center", ""), ('FREE_RIGHT', "Free Right", "")], default='LEFT')
    image_mode: EnumProperty(name="Image Mode", items=[('SINGLE', "Single", ""), ('CONDITIONAL_LIST', "Conditional List", ""), ('INDEX_LIST', "Index List", "")], default='SINGLE')
    image_blending_mode: EnumProperty(
        name="Blending Mode",
        description="Determines how color parameters affect the image",
        items=[
            ('NONE',          "None",            "Takes atlas color as is, no alpha influence from element color"),
            ('OVERLAY',       "Overlay",         "Multiplies atlas color by element color (Tint)"),
            ('OVERLAY_ALPHA', "Overlay (Alpha)", "Overlay vertex color considering texture alpha"),
            ('COLOR_REPLACE', "Color Replace",   "Forces target color replacing greyscale intensity"),
            ('HSV',           "HSV Shift",       "Vertex R=H, G=S, B=V offsets for atlas colors"),
            ('INVERSION',     "Invert",          "Inverts atlas colors")
        ],
        default='NONE'
    )
    image_id: IntProperty(name="Image ID",description="ID изображения (-1 = нет)",default=-1, update=mark_atlas_dirty)
    hover_image_id: IntProperty(name="Hover Image ID", description="ID изображения при наведении (-1 = нет). Имеет высокий приоритет — заменяет любой image_mode при ховере.", default=-1, update=mark_atlas_dirty)
    extramap_image_id: IntProperty(name="ExtraMap Image ID", description="ID изображения для extra map (-1 = нет). Функционал шейдера в разработке.", default=-1, update=mark_atlas_dirty)
    flip_x: BoolProperty(name="Flip X", default=False)
    flip_y: BoolProperty(name="Flip Y", default=False)
    
    # Vector Modifiers (SVG)
    svg_scale: FloatProperty(name="SVG Scale", default=1.0, update=mark_atlas_dirty)
    svg_offset: FloatVectorProperty(name="SVG Offset", size=2, default=(0.0, 0.0), update=mark_atlas_dirty)
    
    # Atlas Rendering Result (For VECTOR elements)
    uv_coords: IntVectorProperty(name="UV Coords", size=2, default=(0, 0))
    uv_size: IntVectorProperty(name="UV Size", size=2, default=(0, 0))

    conditional_images: CollectionProperty(type=ConditionalImage)
    text_mode: EnumProperty(name="Text Mode",items=[('SINGLE', "Single", "Обычный одиночный текст"),('CONDITIONAL_LIST', "Conditional List", "Список текстов, меняющихся по условию"),('INDEX_LIST', "Index List", "Список, выбираемый по индексу (пока резерв)")],default='SINGLE')
    text_id: StringProperty(name="Text ID"); hover_text_id: StringProperty(name="Hover Text ID")
    text_id_is_data: BoolProperty(name="Text ID is Data Key", description="If true, text_id is treated as a runtime data key (e.g. a variable name) rather than a literal string", default=False)
    text_id_data_length: IntProperty(name="Text Data Length", default=1, min=0, max=1024)
    hover_text_id_is_data: BoolProperty(name="Hover Text ID is Data Key", description="If true, hover_text_id is treated as a runtime data key rather than a literal string", default=False)
    hover_text_id_data_length: IntProperty(name="Hover Data Length", default=1, min=0, max=1024)
    conditional_texts: CollectionProperty(type=ConditionalText)
    tile_uv: IntVectorProperty(name="Tile UV", size=2); tile_size: IntVectorProperty(name="Tile Size", size=2)
    color_is_formula: BoolProperty(name="Color Formula Mode", default=False)
    color: FloatVectorProperty(name="Color", subtype='COLOR', size=4, min=0, max=1, default=(1.0, 1.0, 1.0, 1.0), update=mark_atlas_dirty)

    color_formula_r: StringProperty(name="Color R Formula", default="1")
    color_formula_g: StringProperty(name="Color G Formula", default="1")
    color_formula_b: StringProperty(name="Color B Formula", default="1")
    color_formula_a: StringProperty(name="Color A Formula", default="1")
    value_link_is_formula: BoolProperty(name="Color Formula Mode", default=False)
    value_link: CollectionProperty(type=ValueLinkProperty)
    value_link_formula: StringProperty(name="Value link formula", description="Raw code executed when clicked (e.g. run = CommandList...)", default="")
    hover_event_enabled: BoolProperty(name="Custom Hover Event", default=False)
    hover_event_formula: StringProperty(name="Hover Formula", description="Custom code executed on mouse hover",default="")
    click_event_enabled: BoolProperty(name="Custom Click Event", default=False)
    click_event_formula: StringProperty(name="Click Formula", description="Custom code executed on mouse click",default="")
    is_main_window: BoolProperty(name="Is Main Window")
    is_tab_container: BoolProperty(name="Is Page (Isolation)", description="Treat this as an isolation root (page) in the viewport", default=False)
    page_color: FloatVectorProperty(name="Page Color", subtype='COLOR', size=4, min=0, max=1, default=(0.5, 0.5, 0.5, 1.0))
    grid_cell_size: IntProperty(name="Cell Size", default=64); grid_min_cells: IntVectorProperty(name="Min Cells (X, Y)", size=2, default=(1, 1))
    grid_max_cells: IntVectorProperty(name="Max Cells (X, Y)", size=2, default=(10, 10))
    grid_wrap_mode: EnumProperty(name="Wrap Mode", items=[('SCROLL', "Scroll", ""), ('PAGINATE', "Paginate", "")], default='SCROLL')
    toggles: CollectionProperty(type=AssignedToggle)
    fx: CollectionProperty(type=FXProperty); fn: CollectionProperty(type=FNProperty); properties: CollectionProperty(type=CustomProperty)
    style_id: IntProperty(name="Style ID", description="Стиль из глобального реестра (-1 = нет)", default=-1)
    preset_ids: CollectionProperty(type=RZPresetReference)
    underlayer_preset_ids: CollectionProperty(type=RZPresetReference)
    helper_ids: CollectionProperty(type=RZHelperReference)
    qt_hide: BoolProperty(name="Hide in QT Editor", default=False)
    qt_preset_hide: BoolProperty(name="Hide Presets in Editor", default=False)
    qt_lock_pos: BoolProperty(name="Lock Position QT Editor", default=False)
    qt_lock_size: BoolProperty(name="Lock Size in QT Editor", default=False)
    qt_lock_ratio: BoolProperty(name="Lock Aspect Ratio", default=False, description="Enforce aspect ratio during resizing")
    qt_selectable: BoolProperty(name="Selectable in QT Editor", default=True)
    qt_test_value_int: IntProperty(name="QT Int Value", default=0)
    qt_test_value_float: FloatProperty(name="QT Float Value", default=0.0)
    qt_test_value_bool: BoolProperty(name="QT Bool Value", default=False)
    disable_button_nums: BoolProperty(name="Disable Button Nums", default=False)
    disable_button_popup: BoolProperty(name="Disable Button Popup", default=False)
    disable_slider_nums: BoolProperty(name="Disable Slider Nums", default=False)
    disable_slider_blur: BoolProperty(name="Disable Slider Blur", default=False)
    disable_slider_prebuild_render: BoolProperty(name="Force Standard Render", default=False)
    disable_export: BoolProperty(name="Disable Export", description="If active, this element will not be exported to templates", default=False)
    trackable: BoolProperty(name="Trackable", description="Enable tracking/persistence for this element", default=False)
    export_tiers: CollectionProperty(
        type=RZMTierRef,
        name="Export Tiers",
        description="Тиры для которых этот элемент экспортируется. Пусто = все тиры."
    )
    font_slot: IntProperty(name="Font Slot", min=0, max=3, default=0, description="Which font configuration slot to use (0-3)")

    # ── API / Run Link ────────────────────────────────────────────────────────
    run_link_id: IntProperty(
        name="Run Link ID",
        default=-1,
        description="ID of an RZMRunLink to execute when this element is activated. "
                    "-1 = no run link. Stable across RunLink renames."
    )

    # SVG Modifiers (Element-level)
    svg_scale: FloatProperty(name="SVG Scale", default=1.0, min=0.01, max=10.0, update=mark_atlas_dirty)
    svg_offset: FloatVectorProperty(name="SVG Offset", size=2, default=(0.0, 0.0), update=mark_atlas_dirty)
