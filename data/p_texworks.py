# RZMenu/data/p_texworks.py
import bpy
from bpy.props import (StringProperty, IntProperty, BoolProperty, EnumProperty, 
                       PointerProperty, IntVectorProperty, FloatVectorProperty, CollectionProperty)

# --- 1. CORE RESOURCES (Теперь включают параметры формата) ---

class TexResource(bpy.types.PropertyGroup):
    name: StringProperty(name="Resource Name")
    type: EnumProperty(name="Type", items=[
        ('EMPTY', "Empty", ""), 
        ('ON_DISK', "On Disk (Physical)", ""), 
        ('VIRTUAL', "Virtual (Canvas)", "")
    ], default='ON_DISK')
    
    path: StringProperty(name="Path", subtype='FILE_PATH')
    
    # Эти параметры для VIRTUAL задаются вручную, 
    # а для ON_DISK в будущем будут парситься из файла
    resolution: IntVectorProperty(name="Resolution", size=2, default=(4096, 4096))
    format: EnumProperty(
        name="Format",
        items=[
            ('DXGI_FORMAT_R8G8B8A8_TYPELESS', "RGBA8 Typeless", ""),
            ('DXGI_FORMAT_R8G8B8A8_UNORM', "RGBA8 UNORM", ""),
            ('DXGI_FORMAT_R8G8B8A8_UNORM_SRGB', "RGBA8 UNORM SRGB", ""),
            ('DXGI_FORMAT_R8G8_TYPELESS', "R8G8 Typeless (NormalMap)", ""),
            ('DXGI_FORMAT_R32_FLOAT', "R32 Float", ""),
            ('DXGI_FORMAT_BC7_UNORM', "BC7 UNORM", ""),
        ],
        default='DXGI_FORMAT_R8G8B8A8_TYPELESS'
    )

class TexOverride(bpy.types.PropertyGroup):
    name: StringProperty(name="Override Name")
    hash: StringProperty(name="Hash")
    resource_name: StringProperty(name="Resource Name")

# --- 2. MATERIALS (Поведение) ---

class TexWorksMaterial(bpy.types.PropertyGroup):
    name: StringProperty(name="Material Name", default="NewMaterial")
    use_diffuse: BoolProperty(name="Use Diffuse", default=True)
    use_normalmap: BoolProperty(name="Use NormalMap", default=False)
    use_materialmap: BoolProperty(name="Use MaterialMap", default=False)
    
    diffuse_blend_mode: EnumProperty(
        name="Diffuse Blend",
        items=[('LERP', "Lerp", ""), ('ADD', "Add", ""), ('MULTIPLY', "Multiply", ""), ('OVERLAY', "Overlay", "")],
        default='LERP'
    )

# --- 3. SLOTS & DECAL LAYERS ---

class TexWorksDecalLayer(bpy.types.PropertyGroup):
    name: StringProperty(name="Material Name", default="Tattoo")
    index: IntProperty(name="Index", default=0)
    active: BoolProperty(default=True)

class TexWorksSlot(bpy.types.PropertyGroup):
    name: StringProperty(name="Slot Name", default="Arm")
    active: BoolProperty(default=True)
    
    # Слои декалей (Tattoo, Fluid, Blood и т.д.)
    decal_layers: CollectionProperty(type=TexWorksDecalLayer)
    active_layer_index: IntProperty()
    
    # Координаты X, Y, W, H
    rect: IntVectorProperty(name="Rect (X, Y, W, H)", size=4, default=(0, 0, 1024, 1024))
    
    # Маскирование
    mask_source: EnumProperty(
        items=[('TEXTURE_ALPHA', "Source Alpha", ""), ('SEPARATE_MASK', "Separate Mask", ""), ('CHANNEL_R', "R", ""), ('CHANNEL_G', "G", ""), ('CHANNEL_B', "B", "")],
        default='TEXTURE_ALPHA'
    )

    # Зеркалирование и Оффсеты (Buffer Data: offset_x, offset_y, mirror, flip)
    mirror_mode: EnumProperty(
        name="Mirror Mode",
        items=[
            ('NONE', "None", ""),
            ('DUPLICATE', "Duplicate (Sync)", ""),
            ('INDIVIDUAL', "Individual (L/R)", "")
        ],
        default='NONE'
    )
    mirror_data: FloatVectorProperty(name="Mirror Data", size=4, default=(0.0, 0.0, 0.0, 1.0))

    # HSV: Теперь одна ссылка на Векторную переменную
    hsv_enabled: BoolProperty(default=False)
    hsv_link: StringProperty(name="HSV Variable", description="Link to a VECTOR value ($MyVar)")
    hsv_base: FloatVectorProperty(name="HSV Base", size=4, default=(0.0, 0.0, 0.0, 1.0))

    condition: StringProperty(name="Condition")

# --- 4. COMPONENTS & MAIN BLOCKS ---

class TexWorksComponent(bpy.types.PropertyGroup):
    name: StringProperty(name="Component Name", default="NewComponent")
    resource_name: StringProperty(name="Resource Name", description="Link to a resource (Physical/Virtual)")
    rect: IntVectorProperty(name="Rect (X, Y, W, H)", size=4, default=(0, 0, 4096, 4096))
    slots: CollectionProperty(type=TexWorksSlot)
    active_slot_index: IntProperty()


class TexWorksMainBlock(bpy.types.PropertyGroup):
    name: StringProperty(name="Block Name", default="MainBlock")
    resource_name: StringProperty(name="Output Resource", description="Virtual texture for this block")
    
    # Список имен ресурсов, которые являются атласами (VIRTUAL ресурсы)
    output_atlases: CollectionProperty(type=bpy.types.PropertyGroup) # Можно сделать коллекцию StringProperty
    
    components: CollectionProperty(type=TexWorksComponent)
    active_component_index: IntProperty()