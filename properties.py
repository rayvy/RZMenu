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
    # ИЗМЕНЕНО: Режимы теперь основаны на типе шейдинга, а не на движке
    shading_mode: EnumProperty(
        name="Shading Mode",
        items=[
            ('SOLID', "Solid", "Захват со стандартным Solid шейдингом"),
            ('FLAT', "Flat", "Захват с плоским 'Flat' шейдингом и цветом текстуры"),
            ('MATERIAL', "Material Preview", "Захват из режима предпросмотра материалов (использует текущие настройки HDRI)"),
            ('RENDERED', "Rendered", "Захват из режима Rendered (использует освещение сцены)")
        ],
        default='MATERIAL',
        description="Режим отображения вьюпорта для создания иконки"
    )
    
    add_temp_light: BoolProperty(
        name="Add Temporary Sun Light",
        default=True,
        description="Для режима 'Rendered': добавить временный источник света 'Sun'"
    )
    
    # Это свойство больше не используется в UI, но может быть полезно для Auto-Capture
    camera_mode: EnumProperty(
        name="Camera Source",
        items=[('VIEW', "From Viewport", ""), ('SCENE', "From Scene Camera", "")],
        default='VIEW',
        description="Источник, из которого будет производиться захват"
    )

    use_overlays: BoolProperty(
        name="Use Overlays",
        default=False,
        description="Включить оверлеи (сетка, выделение и т.д.) в итоговое изображение"
    )

    resolution: IntProperty(
        name="Resolution",
        default=128,
        min=32, max=1024,
        description="Разрешение итогового квадратного изображения (в пикселях)"
    )

class RZMenuImage(bpy.types.PropertyGroup):
    """Хранит информацию об одном изображении в проекте."""
    id: IntProperty(name="Unique ID")
    display_name: StringProperty(name="Display Name")
    
    source_type: EnumProperty(
        name="Source Type",
        items=[
            ('CUSTOM', "Custom", "Изображение, добавленное пользователем"),
            ('BASE', "Base", "Изображение из стандартной библиотеки"),
            ('CAPTURED', "Captured", "Изображение, созданное в Blender")
        ],
        default='CUSTOM'
    )
    
    image_pointer: PointerProperty(name="Blender Image", type=bpy.types.Image)
    uv_coords: IntVectorProperty(name="Atlas UV Coords", size=2)
    uv_size: IntVectorProperty(name="Atlas UV Size", size=2)

    captured_toggles: StringProperty(
        name="Captured Toggles State",
        description="Состояние тогглов на активном объекте в момент захвата (для будущей сортировки)"
    )

class FXProperty(bpy.types.PropertyGroup): value: EnumProperty(name="Effect", items=FX_COMMANDS)
class FNProperty(bpy.types.PropertyGroup): function_name: EnumProperty(name="Function", items=FN_COMMANDS)
class CustomProperty(bpy.types.PropertyGroup):
    key: StringProperty(name="Key")
    value_type: EnumProperty(name="Type", items=[('STRING', "String", ""), ('INT', "Integer", ""), ('FLOAT', "Float", "")], default='STRING')
    string_value: StringProperty(name="String Value"); int_value: IntProperty(name="Int Value"); float_value: FloatProperty(name="Float Value")
class RZMenuConfig(bpy.types.PropertyGroup): canvas_size: IntVectorProperty(name="Canvas Size", size=2, default=(1920, 1080))
class ValueProperty(bpy.types.PropertyGroup):
    value_name: StringProperty(name="Name"); value_type: EnumProperty(name="Type", items=[('INT', "Integer", ""), ('FLOAT', "Float", "")], default='INT')
    int_value: IntProperty(name="Integer Value"); float_value: FloatProperty(name="Float Value")
class ToggleDefinition(bpy.types.PropertyGroup):
    toggle_name: StringProperty(name="Toggle Name", description="Уникальное имя, e.g., ToggleA")
    toggle_length: IntProperty(name="Length", default=8, min=1, max=32)
    toggle_is_expanded: BoolProperty(name="Expanded", default=False)
class BitProperty(bpy.types.PropertyGroup): value: BoolProperty(name="Bit")
class AssignedToggle(bpy.types.PropertyGroup):
    toggle_name: StringProperty(name="Toggle Name")
    bits: CollectionProperty(type=BitProperty)

class TexWorksAtlasConfig(bpy.types.PropertyGroup):
    """НОВОЕ: Хранит настройки для одного конкретного атласа."""
    tw_width: IntProperty(name="Width", default=4096, min=256)
    tw_height: IntProperty(name="Height", default=4096, min=256)
    tw_format: StringProperty(name="Format", default="DXGI_FORMAT_R8G8B8A8_TYPELESS")
    tw_array: IntProperty(name="Array", default=1, min=1)
    tw_msaa: IntProperty(name="MSAA", default=1, min=1)
    tw_mips: IntProperty(name="Mips", default=1, min=1)
    
class TexWorksTextureConfig(bpy.types.PropertyGroup):
    """Определяет глобальный тип текстуры (имя, цветовое пространство и настройки атласа)."""
    tw_config_name: StringProperty(name="Name", default="Body_Albedo")
    tw_color_space: EnumProperty(name="Color Space", items=[('SRGB', "sRGB", ""), ('Linear', "Linear", "")], default='SRGB')
    # НОВОЕ: У каждого типа текстуры теперь свои настройки атласа
    tw_atlas_settings: PointerProperty(type=TexWorksAtlasConfig)

class TexWorksTexture(bpy.types.PropertyGroup):
    """Определяет одну текстуру в атласе TexWorks с расширенным функционалом."""
    tw_name: StringProperty(name="Texture Name", default="TextureName")
    tw_position: IntVectorProperty(name="Position", size=2, default=(0, 0))
    tw_size: IntVectorProperty(name="Size", size=2, default=(1024, 1024))
    tw_is_expanded: BoolProperty(name="Expanded", default=True) # Для удобства UI

    # --- НОВЫЕ ФУНКЦИИ ---
    # 1. Decals
    tw_use_decal_tattoo: BoolProperty(name="Use Tattoo Decal", default=False)
    tw_use_decal_cum: BoolProperty(name="Use Cum Decal", default=False)
    
    # 2. HSV
    tw_use_hsv: BoolProperty(name="Use HSV", default=False)
    tw_hsv_mode: EnumProperty(name="HSV Mode", items=[('UNMASKED', "Unmasked", ""), ('MASKED', "Masked", "")], default='UNMASKED')
    tw_hsv_value_link: StringProperty(name="HSV Value Link", description="Привязка к ($) или (@). Пусто = авто-переменная")
    
    # 3. Morph
    tw_use_morph: BoolProperty(name="Use Morph", default=False)
    tw_morph_target_name: StringProperty(name="Morph Target Texture", description="Имя текстуры-цели для морфинга")
    tw_morph_value_link: StringProperty(name="Morph Value Link", description="Привязка к ($) или (@). Пусто = авто-переменная")

# --- СВОЙСТВА ДЛЯ АДДОНОВ ---
class RZMenuAddonSettings(bpy.types.PropertyGroup):
    debugger_info: BoolProperty(name="DebuggerInfo", default=False)
    
    # НОВЫЙ АДДОН TEXWORKS
    tex_works: BoolProperty(name="TexWorks", default=False)
    
    # Остальные аддоны
    vfx: BoolProperty(name="VFX", default=False)
    shape_morph: BoolProperty(name="ShapeMorph", default=False)
    shape_morph_anim: BoolProperty(name="ShapeMorphAnim", default=False)
    shape_morph_jiggle: BoolProperty(name="ShapeMorphJiggle", default=False)
    dtoggle_compute: BoolProperty(name="DToggleCompute", default=False)
    rtoggle_compute: BoolProperty(name="RToggleCompute", default=False)
    sandevistan_gi: BoolProperty(name="Sandevistan_GI", default=False)
    sandevistan_zzz: BoolProperty(name="Sandevistan_ZZZ", default=False)
    sandevistan_hsr: BoolProperty(name="Sandevistan_HSR", default=False)
    sandevistan_wuwa: BoolProperty(name="Sandevistan_WUWA", default=False)
    
    # Настройки TexWorks
    tw_texture_configs: CollectionProperty(type=TexWorksTextureConfig)
    tw_textures: CollectionProperty(type=TexWorksTexture)

# --- НОВЫЕ СПЕЦИАЛЬНЫЕ ПЕРЕМЕННЫЕ ---
class RZMCondition(bpy.types.PropertyGroup):
    condition_name: StringProperty(name="Name")
    condition_hash: StringProperty(name="Hash")

class RZMShape(bpy.types.PropertyGroup):
    name: StringProperty(name="Shape Name")
    shape_type: EnumProperty(name="Type", items=[('Linear', "Linear", ""), ('Anim', "Anim", ""), ('Jiggle', "Jiggle", "")], default='Linear')
    keyframes: IntProperty(name="Keyframes", default=1, min=1)

class RZMenuElement(bpy.types.PropertyGroup):
    element_name: StringProperty(name="Name"); id: IntProperty(name="Unique ID"); parent_id: IntProperty(name="Parent ID", default=-1)
    priority: IntProperty(name="Priority", default=0); tag: StringProperty(name="Tag")
    elem_class: EnumProperty( name="Class", items=[('CONTAINER', "Container", ""), ('GRID_CONTAINER', "Grid Container", ""), ('ANCHOR', "Anchor", ""), ('BUTTON', "Button", ""), ('SLIDER', "Slider", "")], default='CONTAINER')
    visibility_mode: EnumProperty(name="Visibility", items=[('ALWAYS', "Always Visible", ""), ('CONDITIONAL', "Conditional", "")], default='ALWAYS')
    visibility_condition: StringProperty(name="Condition", description="e.g., $var > 0 or @ToggleA[1]")
    position_is_formula: BoolProperty(name="Position Formula Mode")
    position: IntVectorProperty(name="Position", size=2, default=(0, 0))
    position_formula_x: StringProperty(name="X Formula"); position_formula_y: StringProperty(name="Y Formula")
    size_is_formula: BoolProperty(name="Size Formula Mode"); size: IntVectorProperty(name="Size", size=2, default=(100, 30))
    size_formula_x: StringProperty(name="W Formula"); size_formula_y: StringProperty(name="H Formula")
    image_id: IntProperty(name="Image ID",description="ID изображения из библиотеки проекта (-1 = нет)",default=-1)
    text_id: StringProperty(name="Text ID"); hover_text_id: StringProperty(name="Hover Text ID")
    tile_uv: IntVectorProperty(name="Tile UV", size=2); tile_size: IntVectorProperty(name="Tile Size", size=2)
    color: FloatVectorProperty(name="Color", subtype='COLOR', size=4, min=0, max=1, default=(0.0, 0.0, 0.0, 0.0))
    value_link: StringProperty(name="Value Link", description="Привязка к ($) или тогглу (@)")
    value_link_max: FloatProperty(name="Max Value", default=100.0)
    is_main_window: BoolProperty(name="Is Main Window")
    grid_cell_size: IntProperty(name="Cell Size", default=64)
    grid_min_cells: IntVectorProperty(name="Min Cells (X, Y)", size=2, default=(1, 1))
    grid_max_cells: IntVectorProperty(name="Max Cells (X, Y)", size=2, default=(10, 10))
    grid_wrap_mode: EnumProperty(name="Wrap Mode", items=[('SCROLL', "Scroll", ""), ('PAGINATE', "Paginate", "")], default='SCROLL')
    toggles: CollectionProperty(type=AssignedToggle)
    fx: CollectionProperty(type=FXProperty); fn: CollectionProperty(type=FNProperty); properties: CollectionProperty(type=CustomProperty)
    qt_hide: BoolProperty(name="Hide in QT Editor", default=False)

class RZMenuProperties(bpy.types.PropertyGroup):
    version: StringProperty(name="Version", default="2.9.1")
    config: PointerProperty(type=RZMenuConfig)
    images: CollectionProperty(type=RZMenuImage)
    atlas_size: IntVectorProperty(
        name="Atlas Size",
        description="Calculated size (W, H) of the texture atlas after packing",
        size=2
    )
    rzm_values: CollectionProperty(type=ValueProperty)
    toggle_definitions: CollectionProperty(type=ToggleDefinition)
    elements: CollectionProperty(type=RZMenuElement)
    element_to_add_class: EnumProperty(name="Class", items=[('CONTAINER', "Container", ""), ('GRID_CONTAINER', "Grid Container", ""), ('ANCHOR', "Anchor", ""), ('BUTTON', "Button", ""), ('SLIDER', "Slider", "")], default='CONTAINER')

    # --- НОВЫЕ ГЛОБАЛЬНЫЕ НАСТРОЙКИ ---
    export_texture_slots: BoolProperty(name="textureSlots", default=True)
    export_orfix_slots: BoolProperty(name="orfixSlots", default=False)
    export_toggle_swap_mode: EnumProperty(name="toggleSwapMode", items=[('None', "None", ""), ('DToggle', "DToggle", ""), ('RToggle', "RToggle", "")], default='None')

    # --- НОВЫЕ СЕКЦИИ ---
    addons: PointerProperty(type=RZMenuAddonSettings)
    conditions: CollectionProperty(type=RZMCondition)
    shapes: CollectionProperty(type=RZMShape)


classes_to_register = [
    RZMCaptureSettings, RZMenuImage, FXProperty, FNProperty, CustomProperty, RZMenuConfig, 
    ValueProperty, ToggleDefinition, BitProperty, AssignedToggle, RZMenuElement,
    # Обновленные и новые классы для TexWorks
    TexWorksAtlasConfig, TexWorksTextureConfig, TexWorksTexture, 
    RZMenuAddonSettings, RZMCondition, RZMShape,
    RZMenuProperties
]

def register():
    for cls in classes_to_register: bpy.utils.register_class(cls)
    bpy.types.Scene.rzm = PointerProperty(type=RZMenuProperties)
    bpy.types.Scene.rzm_active_element_index = IntProperty(name="Active Element Index")
    bpy.types.Scene.rzm_active_image_index = IntProperty(name="Active Image Index")
    bpy.types.Scene.rzm_active_value_index = IntProperty(name="Active Value Index")
    bpy.types.Scene.rzm_active_toggle_def_index = IntProperty(name="Active Toggle Definition Index")
    bpy.types.Scene.rzm_editor_mode = EnumProperty(name="Editor Mode", items=[('LIGHT', "Light", ""), ('PRO', "Pro", "")], default='LIGHT')
    bpy.types.Scene.rzm_show_debug_panel = BoolProperty(name="Show Debug Panel", default=False)
    bpy.types.Scene.rzm_capture_settings = PointerProperty(type=RZMCaptureSettings)
    bpy.types.Scene.rzm_capture_overwrite_id = IntProperty(name="Overwrite ID", default=-1, description="ID изображения для перезаписи. -1 для создания нового.")
    bpy.types.Scene.rzm_show_captures_preview = BoolProperty(name="Show Captures Preview", default=True)


def unregister():
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
    for cls in reversed(classes_to_register): bpy.utils.unregister_class(cls)