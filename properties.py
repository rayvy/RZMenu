# rz_gui_constructor/properties.py
import bpy
from bpy.props import (
    StringProperty, IntProperty, FloatProperty, BoolProperty,
    IntVectorProperty, FloatVectorProperty,
    CollectionProperty, PointerProperty, EnumProperty,
)

# --- Вспомогательные типы (без изменений) ---
FX_COMMANDS = [('CommandListCoreFxBoxRound', "Box Round", "Скруглённые углы"), ('CommandListCoreFxBoxCircle', "Box Circle", "Форма круга/эллипса"), ('CommandListCoreFxGradient', "Gradient", "Градиентная заливка"), ('CommandListCoreFxShadow', "Shadow", "Тень под элементом"), ('CommandListCoreFxBlur', "Blur", "Размытие (блюр)"), ('CommandListCoreFxOutline', "Outline", "Обводка"), ('CommandListCoreFxHover', "Hover", "Эффект при наведении (2D)"), ('CommandListCoreFxHover3D', "Hover 3D", "Эффект при наведении (3D)"), ('CommandListCoreFxGpuAnimRotate', "GPU Anim Rotate", "Анимация вращения на GPU")]
FN_COMMANDS = [('CommandListCoreFnCenterXY', "Center XY", "Центрировать по X и Y"), ('CommandListCoreFnCenterX', "Center X", "Центрировать по X"), ('CommandListCoreFnCenterY', "Center Y", "Центрировать по Y"), ('CommandListCoreFnLeft', "Align Left", "Выровнять по левому краю"), ('CommandListCoreFnRight', "Align Right", "Выровнять по правому краю"), ('CommandListCoreFnBottom', "Align Bottom", "Выровнять по нижнему краю"), ('CommandListCoreFnTop', "Align Top", "Выровнять по верхнему краю"), ('CommandListCoreFnFixRatio', "Fix Ratio", "Сохранять пропорции")]

class RZMCaptureSettings(bpy.types.PropertyGroup):
    """Настройки для оператора захвата изображений."""
    shading_mode: EnumProperty(
        name="Shading Mode",
        items=[('SOLID', "Solid", ""), ('FLAT', "Flat", ""), ('MATERIAL', "Material Preview", ""), ('RENDERED', "Rendered", "")],
        default='MATERIAL',
        description="Режим отображения вьюпорта для создания иконки"
    )
    add_temp_light: BoolProperty(name="Add Temporary Sun Light", default=True, description="Для режима 'Rendered': добавить временный источник света 'Sun'")
    camera_mode: EnumProperty(name="Camera Source", items=[('VIEW', "From Viewport", ""), ('SCENE', "From Scene Camera", "")], default='VIEW', description="Источник, из которого будет производиться захват")
    use_overlays: BoolProperty(name="Use Overlays", default=False, description="Включить оверлеи в итоговое изображение")
    resolution: IntProperty(name="Resolution", default=128, min=32, max=1024, description="Разрешение итогового квадратного изображения")

class RZMenuImage(bpy.types.PropertyGroup):
    """Хранит информацию об одном изображении в проекте."""
    id: IntProperty(name="Unique ID")
    display_name: StringProperty(name="Display Name")
    source_type: EnumProperty(name="Source Type", items=[('CUSTOM', "Custom", ""), ('BASE', "Base", ""), ('CAPTURED', "Captured", "")], default='CUSTOM')
    image_pointer: PointerProperty(name="Blender Image", type=bpy.types.Image)
    uv_coords: IntVectorProperty(name="Atlas UV Coords", size=2)
    uv_size: IntVectorProperty(name="Atlas UV Size", size=2)
    captured_toggles: StringProperty(name="Captured Toggles State", description="Состояние тогглов на активном объекте в момент захвата")

class ConditionalImage(bpy.types.PropertyGroup):
    condition: StringProperty(name="Condition", description="e.g., $varA > 5 and @ToggleB[1]")
    image_id: IntProperty(name="Image ID", default=-1)

class ValueLinkProperty(bpy.types.PropertyGroup):
    """Хранит одну строку value link с диапазоном."""
    value_name: StringProperty(name="Link", description="Привязка к ($) Value, (@) Toggle или (#) Shape")
    value_min: FloatProperty(name="Min Value", default=0.0)
    value_max: FloatProperty(name="Max Value", default=1.0)

class FXProperty(bpy.types.PropertyGroup): value: EnumProperty(name="Effect", items=FX_COMMANDS)
class FNProperty(bpy.types.PropertyGroup): function_name: EnumProperty(name="Function", items=FN_COMMANDS)
class CustomProperty(bpy.types.PropertyGroup):
    key: StringProperty(name="Key"); value_type: EnumProperty(name="Type", items=[('STRING', "String", ""), ('INT', "Integer", ""), ('FLOAT', "Float", "")], default='STRING')
    string_value: StringProperty(name="String Value"); int_value: IntProperty(name="Int Value"); float_value: FloatProperty(name="Float Value")
class RZMenuConfig(bpy.types.PropertyGroup): canvas_size: IntVectorProperty(name="Canvas Size", size=2, default=(1920, 1080))
class ValueProperty(bpy.types.PropertyGroup):
    value_name: StringProperty(name="Name"); value_type: EnumProperty(name="Type", items=[('INT', "Integer", ""), ('FLOAT', "Float", "")], default='INT')
    int_value: IntProperty(name="Integer Value"); float_value: FloatProperty(name="Float Value")
class ToggleDefinition(bpy.types.PropertyGroup):
    toggle_name: StringProperty(name="Toggle Name", description="Уникальное имя, e.g., ToggleA")
    toggle_length: IntProperty(name="Length", default=8, min=1, max=32); toggle_is_expanded: BoolProperty(name="Expanded", default=False)
class BitProperty(bpy.types.PropertyGroup): value: BoolProperty(name="Bit")
class AssignedToggle(bpy.types.PropertyGroup):
    toggle_name: StringProperty(name="Toggle Name"); bits: CollectionProperty(type=BitProperty)

class TexResource(bpy.types.PropertyGroup):
    tex_name: StringProperty(name="Resource Name", description="Уникальное имя ресурса в проекте")
    tex_resource_type: EnumProperty(name="Type", items=[('EMPTY', "Empty", ""), ('ON_DISK', "On Disk", ""), ('VIRTUAL', "Virtual", "")], default='ON_DISK', description="Тип текстурного ресурса")
    tex_path: StringProperty(name="Path", description="Путь к файлу текстуры", subtype='FILE_PATH')

class TexOverride(bpy.types.PropertyGroup):
    tex_name: StringProperty(name="Override Name", description="Имя слота для удобства")
    tex_hash: StringProperty(name="Hash", description="Хэш ресурса для перехвата")
    tex_resource_name: StringProperty(name="Resource Name", description="Имя ресурса из списка TexWorks Resources")

class TexWorksAtlasConfig(bpy.types.PropertyGroup):
    tw_width: IntProperty(name="Width", default=4096, min=256); tw_height: IntProperty(name="Height", default=4096, min=256)
    tw_format: StringProperty(name="Format", default="DXGI_FORMAT_R8G8B8A8_TYPELESS")

class TexWorksTextureConfig(bpy.types.PropertyGroup):
    tw_config_name: StringProperty(name="Name", default="Body_Albedo")
    tw_color_space: EnumProperty(name="Color Space", items=[('SRGB', "sRGB", ""), ('Linear', "Linear", "")], default='SRGB')
    tw_atlas_settings: PointerProperty(type=TexWorksAtlasConfig)

class DecalConfig(bpy.types.PropertyGroup): pass

class AlternativeTexture(bpy.types.PropertyGroup):
    tex_condition: StringProperty(name="Condition", description="Условие, при котором эта текстура будет активна")
    tex_resource_name: StringProperty(name="Resource Name", description="Имя ресурса из TexWorks для использования")

class TexWorksTexture(bpy.types.PropertyGroup):
    tw_name: StringProperty(name="Texture Name", default="MyVirtualTexture")
    tw_base_resource_name: StringProperty(name="Base Resource", description="Имя основного ресурса для этой текстуры")
    tw_position: IntVectorProperty(name="Position", size=2, default=(0, 0)); tw_size: IntVectorProperty(name="Size", size=2, default=(1024, 1024))
    tw_is_expanded: BoolProperty(name="Expanded", default=True)
    tw_alternatives: CollectionProperty(type=AlternativeTexture)
    tw_use_decal_tattoo: BoolProperty(name="Use Tattoo Decal", default=False)
    tw_use_decal_derma: BoolProperty(name="Use Derma Decal", default=False)
    tw_use_decal_fluid: BoolProperty(name="Use Fluid Decal", default=False)
    tw_decal_settings: PointerProperty(type=DecalConfig)
    tw_use_hsv: BoolProperty(name="Use HSV", default=False)
    tw_hsv_mode: EnumProperty(name="HSV Mode", items=[('UNMASKED', "Unmasked", ""), ('MASKED', "Masked", "")], default='UNMASKED')
    tw_hsv_value_link: StringProperty(name="HSV Value Link", description="Привязка к ($) или (@). Пусто = авто-переменная")
    tw_use_morph: BoolProperty(name="Use Morph", default=False)
    tw_morph_target_name: StringProperty(name="Morph Target Texture", description="Имя текстуры-цели для морфинга")
    tw_morph_value_link: StringProperty(name="Morph Value Link", description="Привязка к ($) или (@). Пусто = авто-переменная")

class RZMenuAddonSettings(bpy.types.PropertyGroup):
    debugger_info: BoolProperty(name="DebuggerInfo", default=False)
    tex_works: BoolProperty(name="TexWorks", default=False)
    tw_resources: CollectionProperty(type=TexResource)
    tw_overrides: CollectionProperty(type=TexOverride)
    tw_texture_configs: CollectionProperty(type=TexWorksTextureConfig)
    tw_textures: CollectionProperty(type=TexWorksTexture)
    vfx: BoolProperty(name="VFX", default=False)
    shape_morph: BoolProperty(name="ShapeMorph", default=False)
    shape_morph_anim: BoolProperty(name="ShapeMorphAnim", default=False)
    dtoggle_compute: BoolProperty(name="DToggleCompute", default=False)
    rtoggle_compute: BoolProperty(name="RToggleCompute", default=False)
    frame_trace: BoolProperty(name="FrameTrace", default=False)

class RZMCondition(bpy.types.PropertyGroup):
    condition_name: StringProperty(name="Name"); condition_hash: StringProperty(name="Hash")

class RZMShapeKey(bpy.types.PropertyGroup):
    """Определяет один шейп-ключ внутри RZMShape и его поведение."""
    key_name: IntProperty(name="Keyframe", description="Номер кадра для этого ключа")

    mode: EnumProperty(
        name="Mode",
        items=[
            ('SIMPLE', "Simple", "Прямое влияние переменной на ключ (0-1 -> 0-1)"),
            ('ADVANCED', "Advanced", "Настройка диапазона и множителя")
        ],
        default='SIMPLE',
        description="Режим влияния основной переменной на этот ключ"
    )
    
    # Эти свойства используются, только если mode == 'ADVANCED'
    input_range_min: FloatProperty(name="Input Min", default=0.0, min=0.0, max=1.0)
    input_range_max: FloatProperty(name="Input Max", default=1.0, min=0.0, max=1.0)
    multiplier: FloatProperty(name="Multiplier", default=1.0)

    # Для Anim типа
    anim_type_index: IntProperty(name="Type Index", default=0)
    anim_start_frame: FloatProperty(name="Start Frame", default=0.0, min=0.0, max=1.0)
    anim_end_frame: FloatProperty(name="End Frame", default=1.0, min=0.0, max=1.0)

class RZMShape(bpy.types.PropertyGroup):
    """Определяет одну переменную типа Shape, которая может управлять несколькими шейп-ключами."""
    shape_name: StringProperty(name="Shape Name", description="Уникальное имя переменной шейпа, e.g., #MyShape")
    shape_type: EnumProperty(name="Type", items=[('Linear', "Linear", ""), ('Anim', "Anim", "")], default='Linear')
    
    # НОВАЯ ПЕРЕМЕННАЯ
    anim_condition: StringProperty(
        name="Anim Condition",
        description="Условие для проигрывания анимации (e.g., $var > 0). Пустое поле = всегда активно."
    )
    
    shape_keys: CollectionProperty(type=RZMShapeKey)

class RZMenuElement(bpy.types.PropertyGroup):
    element_name: StringProperty(name="Name"); id: IntProperty(name="Unique ID"); parent_id: IntProperty(name="Parent ID", default=-1)
    priority: IntProperty(name="Priority", default=0); tag: StringProperty(name="Tag")
    elem_class: EnumProperty( name="Class", items=[('CONTAINER', "Container", ""), ('GRID_CONTAINER', "Grid Container", ""), ('ANCHOR', "Anchor", ""), ('BUTTON', "Button", ""), ('SLIDER', "Slider", ""), ('TEXT', "Text", "")], default='CONTAINER')
    visibility_mode: EnumProperty(name="Visibility", items=[('ALWAYS', "Always Visible", ""), ('CONDITIONAL', "Conditional", "")], default='ALWAYS')
    visibility_condition: StringProperty(name="Condition", description="e.g., $var > 0 or @ToggleA[1]")
    position_is_formula: BoolProperty(name="Position Formula Mode")
    position: IntVectorProperty(name="Position", size=2, default=(0, 0))
    position_formula_x: StringProperty(name="X Formula"); position_formula_y: StringProperty(name="Y Formula")
    size_is_formula: BoolProperty(name="Size Formula Mode"); size: IntVectorProperty(name="Size", size=2, default=(100, 30))
    size_formula_x: StringProperty(name="W Formula"); size_formula_y: StringProperty(name="H Formula")
    alignment: EnumProperty(name="Alignment", items=[('BOTTOM_LEFT', "Bottom Left", ""), ('BOTTOM_CENTER', "Bottom Center", ""), ('BOTTOM_RIGHT', "Bottom Right", ""), ('CENTER_LEFT', "Center Left", ""), ('CENTER', "Center", ""), ('CENTER_RIGHT', "Center Right", ""), ('TOP_LEFT', "Top Left", ""), ('TOP_CENTER', "Top Center", ""), ('TOP_RIGHT', "Top Right", "")], default='BOTTOM_LEFT')
    text_align: EnumProperty(name="Text Align", items=[('LEFT', "Left", ""), ('CENTER', "Center", ""), ('RIGHT', "Right", "")], default='LEFT')
    image_mode: EnumProperty(name="Image Mode", items=[('SINGLE', "Single", ""), ('CONDITIONAL_LIST', "Conditional List", ""), ('INDEX_LIST', "Index List", "")], default='SINGLE')
    image_id: IntProperty(name="Image ID",description="ID изображения (-1 = нет)",default=-1)
    conditional_images: CollectionProperty(type=ConditionalImage)
    text_id: StringProperty(name="Text ID"); hover_text_id: StringProperty(name="Hover Text ID")
    tile_uv: IntVectorProperty(name="Tile UV", size=2); tile_size: IntVectorProperty(name="Tile Size", size=2)
    color: FloatVectorProperty(name="Color", subtype='COLOR', size=4, min=0, max=1, default=(0.0, 0.0, 0.0, 0.0))
    value_link: CollectionProperty(type=ValueLinkProperty)
    is_main_window: BoolProperty(name="Is Main Window")
    grid_cell_size: IntProperty(name="Cell Size", default=64); grid_min_cells: IntVectorProperty(name="Min Cells (X, Y)", size=2, default=(1, 1))
    grid_max_cells: IntVectorProperty(name="Max Cells (X, Y)", size=2, default=(10, 10))
    grid_wrap_mode: EnumProperty(name="Wrap Mode", items=[('SCROLL', "Scroll", ""), ('PAGINATE', "Paginate", "")], default='SCROLL')
    toggles: CollectionProperty(type=AssignedToggle)
    fx: CollectionProperty(type=FXProperty); fn: CollectionProperty(type=FNProperty); properties: CollectionProperty(type=CustomProperty)
    qt_hide: BoolProperty(name="Hide in QT Editor", default=False)
    disable_button_nums: BoolProperty(name="Disable Button Nums", default=False)
    disable_button_popup: BoolProperty(name="Disable Button Popup", default=False)

class RZMenuProperties(bpy.types.PropertyGroup):
    version: StringProperty(name="Version", default="3.0.1")
    config: PointerProperty(type=RZMenuConfig)
    images: CollectionProperty(type=RZMenuImage)
    atlas_size: IntVectorProperty(name="Atlas Size", description="Calculated size (W, H) of the texture atlas", size=2)
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

classes_to_register = [
    RZMCaptureSettings, RZMenuImage, FXProperty, FNProperty, CustomProperty, RZMenuConfig, 
    ValueProperty, ToggleDefinition, BitProperty, AssignedToggle, ConditionalImage,
    ValueLinkProperty, RZMenuElement, TexResource, TexOverride, DecalConfig,
    AlternativeTexture, TexWorksAtlasConfig, TexWorksTextureConfig, TexWorksTexture, 
    RZMShapeKey, RZMShape, RZMenuAddonSettings, RZMCondition, RZMenuProperties
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)
        
    bpy.types.Scene.rzm = PointerProperty(type=RZMenuProperties)
    bpy.types.Scene.rzm_active_element_index = IntProperty(name="Active Element Index")
    bpy.types.Scene.rzm_active_image_index = IntProperty(name="Active Image Index")
    bpy.types.Scene.rzm_active_value_index = IntProperty(name="Active Value Index")
    bpy.types.Scene.rzm_active_toggle_def_index = IntProperty(name="Active Toggle Definition Index")
    bpy.types.Scene.rzm_editor_mode = EnumProperty(name="Editor Mode", items=[('LIGHT', "Light", ""), ('PRO', "Pro", "")], default='LIGHT')
    bpy.types.Scene.rzm_show_debug_panel = BoolProperty(name="Show Debug Panel", default=False)
    bpy.types.Scene.rzm_capture_settings = PointerProperty(type=RZMCaptureSettings)
    bpy.types.Scene.rzm_capture_overwrite_id = IntProperty(name="Overwrite ID", default=-1)
    bpy.types.Scene.rzm_show_captures_preview = BoolProperty(name="Show Captures Preview", default=True)
    
    # НОВОЕ: Регистрация временного свойства для передачи контекста в меню
    bpy.types.WindowManager.rzm_context_atlas_index = IntProperty(
        name="RZM TW Context Index", 
        description="Internal: Used to pass context to the TW format menu",
        default=-1
    )

def unregister():
    # Удаляем временное свойство
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