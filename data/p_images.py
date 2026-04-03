# RZMenu/data/p_images.py
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, PointerProperty, IntVectorProperty, CollectionProperty

def mark_atlas_dirty_img(self, context):
    """Sets the atlas dirty flag to True when an image-related property changes."""
    # self can be RZMenuImage or ConditionalImage
    # Both are within rzm properties
    if hasattr(context.scene, "rzm"):
        context.scene.rzm.export_settings.atlas_is_dirty = True

class RZMenuAnimationFrame(bpy.types.PropertyGroup):
    """Уникальный текстурный кадр в атласе."""
    x: IntProperty(name="X")
    y: IntProperty(name="Y")
    w: IntProperty(name="W")
    h: IntProperty(name="H")

class RZMenuAnimationSequence(bpy.types.PropertyGroup):
    """Запись в таймлайне: какой уникальный кадр показывать и как долго."""
    frame_index: IntProperty(name="Unique Frame Index", description="Индекс в коллекции anim_frames")
    duration: FloatProperty(name="Duration", default=0.0416, description="Длительность показа этого кадра в секундах")
    is_unique: BoolProperty(name="Is Unique Start", default=True, description="Является ли этот кадр началом нового уникального блока")

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
    source_type: EnumProperty(
        name="Source Type",
        items=[
            ('CUSTOM',   "Custom",   "Загружено пользователем вручную"),
            ('BASE',     "Base",     "Базовая иконка из библиотеки"),
            ('CAPTURED', "Captured", "Захвачено из вьюпорта"),
            ('ANIMATED', "Animated", "GIF или видеофайл с автоматической нарезкой кадров"),
        ],
        default='CUSTOM'
    )
    image_pointer: PointerProperty(name="Blender Image", type=bpy.types.Image, update=mark_atlas_dirty_img)
    uv_coords: IntVectorProperty(name="Atlas UV Coords", size=2)
    uv_size: IntVectorProperty(name="Atlas UV Size", size=2)
    captured_toggles: StringProperty(name="Captured Toggles State", description="Состояние тогглов на активном объекте в момент захвата")

    # ─── Animated-специфичные поля ─────────────────────────────────────────────
    anim_source_path: StringProperty(
        name="Source File",
        description="Путь к исходному GIF/MP4 файлу",
        subtype='FILE_PATH',
        default=""
    )
    anim_frame_count: IntProperty(
        name="Frame Count",
        description="Количество уникальных кадров после дедупликации",
        default=0,
        min=0
    )
    anim_total_duration: FloatProperty(
        name="Total Duration (sec)",
        description="Суммарная длительность всех кадров в секундах",
        default=0.0,
        min=0.0
    )
    anim_frame_coords: StringProperty(
        name="Frame UV Data (JSON)",
        description="JSON-массив: [[x, y, w, h, frametime_seconds], ...] — UV координаты и время показа каждого кадра"
    )
    anim_frames: CollectionProperty(type=RZMenuAnimationFrame)
    anim_sequence: CollectionProperty(type=RZMenuAnimationSequence)
    
    anim_paused: BoolProperty(
        name="Paused in Editor",
        description="Остановить анимацию в редакторе",
        default=True
    )
    anim_max_frames: IntProperty(
        name="Source Max Frames",
        description="Лимит кадров при чтении из файла",
        default=256,
        min=1,
        max=4096
    )
    anim_export_preset: EnumProperty(
        name="Export Preset",
        items=[
            ('ECONOMY',       "Economy",         "МАКСИМУМ 4 уникальных кадров"),
            ('ADAPTIVE_LIGHT',"Adaptive Light",  "Легкая оптимизация (бывший Adaptive)"),
            ('ADAPTIVE',      "Adaptive",        "Умная оптимизация (бывший Adaptive+)"),
            ('ADAPTIVE_HEAVY',"Adaptive Heavy",  "Максимальное качество (без Double-Pass)")
        ],
        default='ADAPTIVE',
        update=mark_atlas_dirty_img
    )
    anim_start_frame: IntProperty(name="Start Frame", default=0, min=0, update=mark_atlas_dirty_img)
    anim_end_frame: IntProperty(name="End Frame", default=0, min=0, update=mark_atlas_dirty_img)
    
    anim_speed_multiplier: FloatProperty(
        name="Speed Multiplier",
        description="Множитель скорости воспроизведения (1.0 = оригинальная скорость)",
        default=1.0,
        min=0.01,
        max=16.0,
        update=mark_atlas_dirty_img
    )

class ConditionalImage(bpy.types.PropertyGroup):
    condition: StringProperty(name="Condition", description="e.g., $varA > 5 and @ToggleB[1]")
    image_id: IntProperty(name="Image ID", default=-1, update=mark_atlas_dirty_img)