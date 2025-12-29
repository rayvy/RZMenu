# RZMenu/data/p_logic.py
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty

class ValueLinkProperty(bpy.types.PropertyGroup):
    """Хранит одну строку value link с диапазоном."""
    value_name: StringProperty(name="Link", description="Привязка к ($) Value, (@) Toggle или (#) Shape")
    value_min: FloatProperty(name="Min Value", default=0.0)
    value_max: FloatProperty(name="Max Value", default=1.0)

class ValueProperty(bpy.types.PropertyGroup):
    value_name: StringProperty(name="Name"); value_type: EnumProperty(name="Type", items=[('INT', "Integer", ""), ('FLOAT', "Float", "")], default='INT')
    int_value: IntProperty(name="Integer Value"); float_value: FloatProperty(name="Float Value")

class ToggleDefinition(bpy.types.PropertyGroup):
    toggle_name: StringProperty(name="Toggle Name", description="Уникальное имя, e.g., ToggleA")
    toggle_length: IntProperty(name="Length", default=8, min=1, max=32)
    toggle_is_expanded: BoolProperty(name="Expanded", default=False)
    show_occupancy: BoolProperty(
        name="Show Slot Occupancy", 
        default=False, 
        description="Показать, какие объекты используют биты этого тоггла"
    )

class BitProperty(bpy.types.PropertyGroup): value: BoolProperty(name="Bit")

class AssignedToggle(bpy.types.PropertyGroup):
    toggle_name: StringProperty(name="Toggle Name"); bits: CollectionProperty(type=BitProperty)

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
    input_range_min: FloatProperty(name="Input Min", default=0.0, min=0.0, max=1.0)
    input_range_max: FloatProperty(name="Input Max", default=1.0, min=0.0, max=1.0)
    multiplier: FloatProperty(name="Multiplier", default=1.0)
    anim_type_index: IntProperty(name="Type Index", default=0)
    anim_start_frame: FloatProperty(name="Start Frame", default=0.0, min=0.0, max=1.0)
    anim_end_frame: FloatProperty(name="End Frame", default=1.0, min=0.0, max=1.0)

class RZMShape(bpy.types.PropertyGroup):
    """Определяет одну переменную типа Shape, которая может управлять несколькими шейп-ключами."""
    shape_name: StringProperty(name="Shape Name", description="Уникальное имя переменной шейпа, e.g., #MyShape")
    shape_type: EnumProperty(name="Type", items=[('Linear', "Linear", ""), ('Anim', "Anim", "")], default='Linear')
    anim_condition: StringProperty(
        name="Anim Condition",
        description="Условие для проигрывания анимации (e.g., $var > 0). Пустое поле = всегда активно."
    )
    shape_keys: CollectionProperty(type=RZMShapeKey)