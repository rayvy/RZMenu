import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty, PointerProperty

def update_native_shape_sync(self, context):
    """Updates Blender shape key values across all affected objects in real-time."""
    val = self.sync_value
    sk_name = self.shape_name
    
    for ref in self.affected_objects:
        obj = ref.obj
        if not obj and ref.obj_name:
            obj = bpy.data.objects.get(ref.obj_name)
        
        if obj and obj.data and hasattr(obj.data, 'shape_keys') and obj.data.shape_keys:
            kb = obj.data.shape_keys.key_blocks.get(sk_name)
            if kb:
                kb.value = val

class RZMTierRef(bpy.types.PropertyGroup):
    """A single tier reference stored as part of a CollectionProperty on elements/shapes/values."""
    tier_id: StringProperty(name="Tier ID", default="")

class ValueLinkProperty(bpy.types.PropertyGroup):
    """Хранит одну строку value link с диапазоном."""
    value_name: StringProperty(name="Link", description="Привязка к ($) Value, (@) Toggle или (#) Shape")
    value_min: FloatProperty(name="Min Value", default=0.0)
    value_max: FloatProperty(name="Max Value", default=1.0)

# ─── PROFILE VALUE ────────────────────────────────────────────────────────────

class RZMProfileValue(bpy.types.PropertyGroup):
    """Значение переменной в конкретном in-game профиле.
    Хранится как CollectionProperty на ValueProperty / ToggleDefinition / RZMShape.
    Индекс в коллекции = индекс профиля.
    """
    int_value:   IntProperty(name="Value (Int)", default=0)
    float_value: FloatProperty(name="Value (Float)", default=0.0)
    # Примечание: тип данных наследуется от родительской переменной.
    # Для тогглов используется int_value (индекс слота в длине тоггла).

# ─── RUN LINK ─────────────────────────────────────────────────────────────────

class RZMRunLink(bpy.types.PropertyGroup):
    """Именованный CommandList — вызываемая «функция» мода.
    Может быть привязан к элементам UI (по integer id), Keybind-ам,
    pre/post snippet-ам и другим событиям.
    """
    id:          IntProperty(name="Run Link ID", default=-1,
                              description="Уникальный целочисленный ID. Не меняется при переименовании.")
    name:        StringProperty(name="Name", default="MyAction",
                                description="Имя CommandList-а в .ini (= [MyAction])")
    description: StringProperty(name="Description", default="",
                                description="Краткое описание того, что делает этот CommandList")
    body:        StringProperty(name="Body", default="",
                                description="Тело CommandList-а. Многострочный ввод поддерживается нативно.")

# ─── KEYBIND ──────────────────────────────────────────────────────────────────

class RZMKeybind(bpy.types.PropertyGroup):
    """Горячая клавиша игры (3DMigoto [Key...] секция), привязанная к RunLink."""

    name: StringProperty(name="Keybind Name", default="",
                         description="Имя секции, e.g. 'KeyToggleTop' → [KeyToggleTop]")

    # Клавиши
    key:  StringProperty(name="Primary Key", default="",
                         description="Первичная клавиша, e.g. 'no_modifiers y' или 'alt 7'")
    back: StringProperty(name="Back Key", default="",
                         description="Клавиша для обратного направления цикла (опционально)")

    # Тип нажатия
    type: EnumProperty(
        name="Type",
        items=[
            ('activate', "Activate", "Срабатывает один раз при нажатии"),
            ('hold',     "Hold",     "Активно пока зажато"),
            ('toggle',   "Toggle",   "Переключает между 0 и 1"),
            ('cycle',    "Cycle",    "Циклически перебирает значения"),
        ],
        default='cycle'
    )

    # Условие
    condition:        StringProperty(name="Condition", default="",
                                     description="Произвольное условие 3DMigoto. Если пусто — всегда активно")
    only_menu_active: BoolProperty(
        name="Only When Menu Active",
        default=True,
        description="Авто-добавляет условие '$active == 1' на стороне шаблона. "
                    "Если condition тоже заполнен — объединяется через &&"
    )

    # Привязка к RunLink
    run_id: StringProperty(
        name="Run Link ID",
        default="",
        description="Имя (name) RZMRunLink, который вызывается при срабатывании клавиши"
    )

    # ── Резервные поля (для будущих версий 3DMigoto, пока не используются активно) ──
    delay:                   IntProperty(name="Delay", default=0, min=0,
                                          description="Задержка перед срабатыванием (мс)")
    release_delay:           IntProperty(name="Release Delay", default=0, min=0)
    wrap:                    BoolProperty(name="Wrap", default=False,
                                          description="Зациклить значения при достижении края")
    smart:                   BoolProperty(name="Smart", default=False)
    transition:              IntProperty(name="Transition", default=0, min=0,
                                          description="Количество кадров для плавного перехода")
    release_transition:      IntProperty(name="Release Transition", default=0, min=0)
    transition_type:         EnumProperty(
        name="Transition Type",
        items=[('linear', "Linear", ""), ('cosine', "Cosine", "")],
        default='linear'
    )
    release_transition_type: EnumProperty(
        name="Release Transition Type",
        items=[('linear', "Linear", ""), ('cosine', "Cosine", "")],
        default='linear'
    )

# ─── VALUE PROPERTY ───────────────────────────────────────────────────────────

class ValueProperty(bpy.types.PropertyGroup):
    value_name: StringProperty(name="Name")
    value_type: EnumProperty(
        name="Type",
        items=[('INT', "Integer", ""), ('FLOAT', "Float", ""), ('VECTOR', "Vector (Float4)", "")],
        default='INT'
    )
    int_value:    IntProperty(name="Integer Value")
    float_value:  FloatProperty(name="Float Value")
    vector_value: bpy.props.FloatVectorProperty(name="Vector Value", size=4, default=(0.0, 0.0, 0.0, 1.0))
    force_export: BoolProperty(name="Force Export", default=False)
    export_tiers: CollectionProperty(
        type=RZMTierRef,
        name="Export Tiers",
        description="Тиры для которых этот элемент будет включён в Mod Producer. Пусто = все тиры."
    )

    # ── Randomization ────────────────────────────────────────────────────────
    val_min:     FloatProperty(name="Min Value", default=0.0,
                                description="Минимальное значение для рандомизатора и слайдера")
    val_max:     FloatProperty(name="Max Value", default=10.0,
                                description="Максимальное значение для рандомизатора и слайдера")
    mark_random: BoolProperty(name="Include in Randomize", default=True,
                               description="Включить эту переменную в CommandListRZRandomize")

    # ── In-Game Profiles ─────────────────────────────────────────────────────
    in_game_profiles: CollectionProperty(
        type=RZMProfileValue,
        name="In-Game Profile Values",
        description="Значения переменной для каждого профиля. "
                    "Индекс = номер профиля (0-based). Синхронизируется через оператор Sync Profiles."
    )
    # NOTE: run_link_id lives on RZMenuElement, NOT on ValueProperty.
    # Binding RunLink to a variable would create circular dependencies.

# ─── TOGGLE DEFINITION ────────────────────────────────────────────────────────

class ToggleDefinition(bpy.types.PropertyGroup):
    toggle_name:        StringProperty(name="Toggle Name", description="Уникальное имя, e.g., ToggleA")
    toggle_length:      IntProperty(name="Length", default=8, min=1, max=32)
    toggle_start_index: IntProperty(name="Start Index", default=0, min=0, max=999)
    toggle_is_expanded: BoolProperty(name="Expanded", default=False)
    show_occupancy:     BoolProperty(
        name="Show Slot Occupancy",
        default=False,
        description="Показать, какие объекты используют биты этого тоггла"
    )
    force_export: BoolProperty(name="Force Export", default=False)

    # ── Randomization ────────────────────────────────────────────────────────
    mark_random: BoolProperty(
        name="Include in Randomize",
        default=True,
        description="Включить этот тоггл в CommandListRZRandomize. "
                    "Границы берутся из toggle_start_index и toggle_start_index + toggle_length - 1"
    )

    # ── In-Game Profiles ─────────────────────────────────────────────────────
    in_game_profiles: CollectionProperty(
        type=RZMProfileValue,
        name="In-Game Profile Values",
        description="Значения тоггла (int_value = индекс) для каждого профиля."
    )

# ─── BIT / ASSIGNED TOGGLE ────────────────────────────────────────────────────

class BitProperty(bpy.types.PropertyGroup): value: BoolProperty(name="Bit")

class AssignedToggle(bpy.types.PropertyGroup):
    toggle_name: StringProperty(name="Toggle Name"); bits: CollectionProperty(type=BitProperty)

class RZMCondition(bpy.types.PropertyGroup):
    condition_name: StringProperty(name="Name"); condition_hash: StringProperty(name="Hash")

# ─── SHAPE KEY / SHAPE ────────────────────────────────────────────────────────

class RZMShapeKey(bpy.types.PropertyGroup):
    """Определяет один шейп-ключ внутри RZMShape и его поведение."""
    key_name: IntProperty(name="Keyframe", description="Номер кадра для этого ключа")
    mode: EnumProperty(
        name="Mode",
        items=[
            ('SIMPLE',   "Simple",   "Прямое влияние переменной на ключ (0-1 -> 0-1)"),
            ('ADVANCED', "Advanced", "Настройка диапазона и множителя")
        ],
        default='SIMPLE',
        description="Режим влияния основной переменной на этот ключ"
    )
    input_range_min: FloatProperty(name="Input Min", default=0.0, min=0.0, max=1.0)
    input_range_max: FloatProperty(name="Input Max", default=1.0, min=0.0, max=1.0)
    multiplier:      FloatProperty(name="Multiplier", default=1.0)
    anim_type_index: IntProperty(name="Type Index", default=0)
    anim_start_frame: FloatProperty(name="Start Frame", default=0.0, min=0.0, max=1.0)
    anim_end_frame:   FloatProperty(name="End Frame",   default=1.0, min=0.0, max=1.0)

class RZMShape(bpy.types.PropertyGroup):
    """Defines a single Shape variable that can control multiple shape keys."""
    shape_name: StringProperty(name="Shape Name", description="Unique shape variable name, e.g. #MyShape")
    shape_type: EnumProperty(name="Type", items=[('Linear', "Linear", ""), ('Anim', "Anim", "")], default='Linear')
    anim_condition: StringProperty(
        name="Anim Condition",
        description="Condition for animation playback (e.g. $var > 0). Empty = always active."
    )
    disable_export: BoolProperty(name="Disable Export",
                                  description="If active, this shape variable will not be exported to templates",
                                  default=False)
    force_export: BoolProperty(name="Force Export", default=False)
    export_tiers: CollectionProperty(
        type=RZMTierRef,
        name="Export Tiers",
        description="Тиры для которых этот шейп экспортируется. Пусто = все тиры."
    )
    shape_keys: CollectionProperty(type=RZMShapeKey)

    # ── Randomization ────────────────────────────────────────────────────────
    val_min:     FloatProperty(name="Min Value", default=0.0,
                                description="Минимальное значение шейпа для рандомизатора")
    val_max:     FloatProperty(name="Max Value", default=1.0,
                                description="Максимальное значение шейпа для рандомизатора")
    mark_random: BoolProperty(name="Include in Randomize", default=True,
                               description="Включить этот шейп в CommandListRZRandomize")

    # ── In-Game Profiles ─────────────────────────────────────────────────────
    in_game_profiles: CollectionProperty(
        type=RZMProfileValue,
        name="In-Game Profile Values",
        description="Значения шейпа для каждого профиля (float_value)."
    )

# ─── DISCOVERED SHAPE KEY CONFIG ──────────────────────────────────────────────

class RZMObjectRef(bpy.types.PropertyGroup):
    """Reference to a Blender Object by name."""
    obj_name: StringProperty(name="Object Name")
    obj: PointerProperty(type=bpy.types.Object, name="Object")

def update_anim_start(self, context):
    if self.anim_start_frame > self.anim_t2:
        self.anim_t2 = self.anim_start_frame
    if self.anim_t2 > self.anim_t3:
        self.anim_t3 = self.anim_t2
    if self.anim_t3 > self.anim_end_frame:
        self.anim_end_frame = self.anim_t3

def update_anim_t2(self, context):
    if self.anim_t2 < self.anim_start_frame:
        self.anim_start_frame = self.anim_t2
    if self.anim_t2 > self.anim_t3:
        self.anim_t3 = self.anim_t2
    if self.anim_t3 > self.anim_end_frame:
        self.anim_end_frame = self.anim_t3

def update_anim_t3(self, context):
    if self.anim_t3 < self.anim_t2:
        self.anim_t2 = self.anim_t3
    if self.anim_t2 < self.anim_start_frame:
        self.anim_start_frame = self.anim_t2
    if self.anim_t3 > self.anim_end_frame:
        self.anim_end_frame = self.anim_t3

def update_anim_end(self, context):
    if self.anim_end_frame < self.anim_t3:
        self.anim_t3 = self.anim_end_frame
    if self.anim_t3 < self.anim_t2:
        self.anim_t2 = self.anim_t3
    if self.anim_t2 < self.anim_start_frame:
        self.anim_start_frame = self.anim_t2

class ShapeKeyConfig(bpy.types.PropertyGroup):
    """Configuration for a discovered Blender ShapeKey name.
    Generated automatically based on shape keys found in selected collections.
    """
    shape_name: StringProperty(
        name="Shape Name",
        description="Name of the Shape Key in Blender (e.g. 'Sport')"
    )
    name: StringProperty(name="Config Name") # Used for search/UI
    shape_type: EnumProperty(
        name="Type",
        items=[('Linear', "Linear", ""), ('Anim', "Anim", "")],
        default='Linear'
    )
    sync_value: FloatProperty(
        name="Global Sync",
        description="Force this value on all Blender objects containing this shape key",
        min=0.0, max=1.0,
        default=0.0,
        update=update_native_shape_sync
    )
    condition: StringProperty(
        name="Condition",
        description="Condition for this shape key. Empty = always active."
    )
    fallback_value: FloatProperty(
        name="Fallback Value",
        description="Fallback value if the condition is not active",
        default=0.0
    )
    override_switch_condition: StringProperty(
        name="Override Condition",
        description="If active, Anim shape behaves as Linear, using Override Value Link."
    )
    override_switch_value_link: StringProperty(
        name="Override Value Link",
        description="Variable to use when Override Condition is active."
    )
    disable_export: BoolProperty(
        name="Disable Export",
        description="If active, this shape key will not be exported",
        default=False
    )
    bake_weights: BoolProperty(
        name="Bake Weights",
        description="Enable weight morphing (BlendWorks Phase 1) for this shape key",
        default=False
    )
    sparse_vertex_count: IntProperty(
        name="Sparse Vertex Count",
        description="Number of vertices affected by this shape key in the baked sparse buffer",
        default=0
    )
    parent_shape: StringProperty(
        name="Parent Shape",
        description="Optional parent shape key. If set, this shape key's deltas (positions/weights) will be calculated relative to the parent.",
        default=""
    )
    force_export: BoolProperty(
        name="Force Export",
        default=False
    )
    export_tiers: CollectionProperty(
        type=RZMTierRef,
        name="Export Tiers",
        description="Tiers for which this shape key is exported."
    )

    # ── Animation Settings ───────────────────────────────────────────────────
    multiplier: FloatProperty(name="Multiplier", default=1.0)
    inverse: BoolProperty(name="Inverse", description="If active, Final = 1.0 - (Value * Multiplier)", default=False)
    input_range_min: FloatProperty(
        name="Input Range Min",
        description="Start of the input sub-range that maps to 0.0 output. "
                    "Values below this are clamped to 0. "
                    "Use together with Input Range Max to make this shape respond only to a portion of the shared variable.",
        min=0.0, max=1.0, default=0.0, step=1, precision=3
    )
    input_range_max: FloatProperty(
        name="Input Range Max",
        description="End of the input sub-range that maps to 1.0 output. "
                    "Values above this are clamped to 1. "
                    "E.g. Min=0.5 Max=1.0 means 'only activate in the top half of the slider'.",
        min=0.0, max=1.0, default=1.0, step=1, precision=3
    )
    anim_type_index: IntProperty(name="Type Index", default=0)
    anim_start_frame: FloatProperty(name="Start Frame", default=0.0, min=0.0, max=1.0, update=update_anim_start)
    anim_end_frame:   FloatProperty(name="End Frame",   default=1.0, min=0.0, max=1.0, update=update_anim_end)
    anim_t2:          FloatProperty(name="Rise End",    default=0.5, min=0.0, max=1.0, update=update_anim_t2)
    anim_t3:          FloatProperty(name="Fall Start",  default=0.5, min=0.0, max=1.0, update=update_anim_t3)

    # ── Range & Randomization ────────────────────────────────────────────────
    slider_min: FloatProperty(
        name="Min",
        default=0.0,
        description="Minimum value for the in-game slider and randomizer"
    )
    slider_max: FloatProperty(
        name="Max",
        default=1.0,
        description="Maximum value for the in-game slider and randomizer"
    )
    mark_random: BoolProperty(
        name="Include in Randomize",
        default=True,
        description="Include this shape key in RZRandomize logic"
    )

    # ── Value Link ───────────────────────────────────────────────────────────
    value_link: StringProperty(
        name="Value Link",
        description="Link to a manual Shape (#), Value ($), or Toggle (@). "
                    "If set, this shape key will be driven by the linked variable."
    )

    # ── In-Game Profiles ─────────────────────────────────────────────────────
    in_game_profiles: CollectionProperty(
        type=RZMProfileValue,
        name="In-Game Profile Values",
        description="Per-profile override values for this shape key."
    )

    # ── Affected Objects ─────────────────────────────────────────────────────
    affected_objects: CollectionProperty(
        type=RZMObjectRef,
        name="Affected Objects",
        description="List of objects that contain this shape key name."
    )
    export_runtime_disabled: BoolProperty(
        name="Runtime Export Disabled",
        description="Prepared export-only disabled state after lock/mute/value-link filtering.",
        default=True,
        options={'HIDDEN'}
    )
    export_runtime_affected_objects: CollectionProperty(
        type=RZMObjectRef,
        name="Runtime Export Objects",
        description="Prepared export-only affected object list after lock/mute filtering.",
        options={'HIDDEN'}
    )
