# RZMenu/data/p_ui.py
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty, IntVectorProperty, FloatVectorProperty

# Импорт констант и зависимых типов из соседних файлов data
from .constants import FX_COMMANDS, FN_COMMANDS
from .p_images import ConditionalImage
from .p_logic import ValueLinkProperty, AssignedToggle

class FXProperty(bpy.types.PropertyGroup): value: EnumProperty(name="Effect", items=FX_COMMANDS)
class FNProperty(bpy.types.PropertyGroup): function_name: EnumProperty(name="Function", items=FN_COMMANDS)

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

class ConditionalText(bpy.types.PropertyGroup):
    text_id: StringProperty(name="Text", default="New Text")
    condition: StringProperty(name="Condition", description="Condition to show this text (e.g. $var > 0)")

class RZMenuElement(bpy.types.PropertyGroup):
    element_name: StringProperty(name="Name"); id: IntProperty(name="Unique ID"); parent_id: IntProperty(name="Parent ID", default=-1)
    is_preset: BoolProperty(name="Is Preset", default=False)
    priority: IntProperty(name="Priority", default=0); tag: StringProperty(name="Tag")
    qt_priority: IntProperty(name="QT Priority", default=0)
    elem_class: EnumProperty( name="Class", items=[('CONTAINER', "Container", ""), ('GRID_CONTAINER', "Grid Container", ""), ('ANCHOR', "Anchor", ""), ('BUTTON', "Button", ""), ('SLIDER', "Slider", ""), ('TEXT', "Text", "")], default='CONTAINER')
    visibility_mode: EnumProperty(name="Visibility", items=[('ALWAYS', "Always Visible", ""), ('CONDITIONAL', "Conditional", ""), ('HIDED', "Hided", "")], default='ALWAYS')
    visibility_condition: StringProperty(name="Condition", description="e.g., $var > 0 or @ToggleA[1]")
    position_is_formula: BoolProperty(name="Position Formula Mode")
    position: IntVectorProperty(name="Position", size=2, default=(0, 0))
    position_formula_x: StringProperty(name="X Formula"); position_formula_y: StringProperty(name="Y Formula")
    size_is_formula: BoolProperty(name="Size Formula Mode")
    size: IntVectorProperty(name="Size", size=2, default=(100, 30))
    size_formula_x: StringProperty(name="W Formula"); size_formula_y: StringProperty(name="H Formula")
    transform_is_formula: BoolProperty(name="Transform Formula Mode")
    transform_formula: StringProperty(name="Transform formula", description="Raw code transformation, not affect to position and size formula", default="")
    alignment: EnumProperty(name="Alignment", items=[('BOTTOM_LEFT', "Bottom Left", ""), ('BOTTOM_CENTER', "Bottom Center", ""), ('BOTTOM_RIGHT', "Bottom Right", ""), ('CENTER_LEFT', "Center Left", ""), ('CENTER', "Center", ""), ('CENTER_RIGHT', "Center Right", ""), ('TOP_LEFT', "Top Left", ""), ('TOP_CENTER', "Top Center", ""), ('TOP_RIGHT', "Top Right", "")], default='BOTTOM_LEFT')
    text_align: EnumProperty(name="Text Align", items=[('LEFT', "Left", ""), ('CENTER', "Center", ""), ('RIGHT', "Right", "")], default='LEFT')
    image_mode: EnumProperty(name="Image Mode", items=[('SINGLE', "Single", ""), ('CONDITIONAL_LIST', "Conditional List", ""), ('INDEX_LIST', "Index List", "")], default='SINGLE')
    image_blending_mode: EnumProperty(name="Blending Mode",description="Determines how color parameters affect the image",items=[('NONE', "None", "Color parameters have no effect on the image"),('OVERLAY', "Overlay", "Standard Overlay blending (Photoshop style)"),('COLOR', "Color_HUE", "Forces target Hue while preserving Saturation and Value (similar to Blender Color mode)")],default='NONE')
    image_id: IntProperty(name="Image ID",description="ID изображения (-1 = нет)",default=-1)
    hover_image_id: IntProperty(name="Hover Image ID", description="ID изображения при наведении (-1 = нет)", default=-1)
    flip_x: BoolProperty(name="Flip X", default=False)
    flip_y: BoolProperty(name="Flip Y", default=False)
    conditional_images: CollectionProperty(type=ConditionalImage)
    text_mode: EnumProperty(name="Text Mode",items=[('SINGLE', "Single", "Обычный одиночный текст"),('CONDITIONAL_LIST', "Conditional List", "Список текстов, меняющихся по условию"),('INDEX_LIST', "Index List", "Список, выбираемый по индексу (пока резерв)")],default='SINGLE')
    text_id: StringProperty(name="Text ID"); hover_text_id: StringProperty(name="Hover Text ID")
    conditional_texts: CollectionProperty(type=ConditionalText)
    tile_uv: IntVectorProperty(name="Tile UV", size=2); tile_size: IntVectorProperty(name="Tile Size", size=2)
    color_is_formula: BoolProperty(name="Color Formula Mode", default=False)
    color: FloatVectorProperty(name="Color", subtype='COLOR', size=4, min=0, max=1, default=(0.0, 0.0, 0.0, 0.0))
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
    preset_ids: CollectionProperty(type=RZPresetReference)
    underlayer_preset_ids: CollectionProperty(type=RZPresetReference)
    qt_hide: BoolProperty(name="Hide in QT Editor", default=False)
    qt_preset_hide: BoolProperty(name="Hide Presets in Editor", default=False)
    qt_lock_pos: BoolProperty(name="Lock Position QT Editor", default=False)
    qt_lock_size: BoolProperty(name="Lock Size in QT Editor", default=False)
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
    font_slot: IntProperty(name="Font Slot", min=0, max=3, default=0, description="Which font configuration slot to use (0-3)")
