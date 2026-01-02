# RZMenu/data/p_images.py
import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, PointerProperty, IntVectorProperty

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