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
    # x46 parameters in shader
    parameters: FloatVectorProperty(name="Parameters (x46)", size=4, default=(0.0, 0.0, 0.0, 1.0))
    
    diffuse_blend_mode: EnumProperty(
        name="Diffuse Blend",
        items=[('LERP', "Lerp", ""), ('ADD', "Add", ""), ('MULTIPLY', "Multiply", ""), ('OVERLAY', "Overlay", "")],
        default='LERP'
    )

# --- 3. SLOTS & DECAL LAYERS ---

class TexWorksDecalLayer(bpy.types.PropertyGroup):
    name: StringProperty(name="Material Name", default="Tattoo")
    index: IntProperty(name="Index", default=0)
    count: IntProperty(name="Total Textures", default=1, min=1)
    active: BoolProperty(default=True)

class TexWorksSlot(bpy.types.PropertyGroup):
    name: StringProperty(name="Slot Name", default="Arm")
    active: BoolProperty(default=True)
    
    # Transform
    rotation: bpy.props.IntProperty(name="Rotation")
    dummy: bpy.props.IntProperty(name="Dummy")
    mirror: bpy.props.BoolProperty(name="Mirror")
    flip: bpy.props.BoolProperty(name="Flip")

    # Слои декалей (Tattoo, Fluid, Blood и т.д.)
    decal_layers: CollectionProperty(type=TexWorksDecalLayer)
    active_layer_index: IntProperty()
    
    # Координаты X, Y, W, H на атласе компонента
    rect: IntVectorProperty(name="Rect (X, Y, W, H)", size=4, default=(0, 0, 1024, 1024))
    
    # Маскирование
    mask_enabled: BoolProperty(name="Use Mask", default=False)
    mask_source: EnumProperty(
        items=[('TEXTURE_ALPHA', "Source Alpha", ""), ('SEPARATE_MASK', "Separate Mask", ""), ('CHANNEL_R', "R", ""), ('CHANNEL_G', "G", ""), ('CHANNEL_B', "B", "")],
        default='TEXTURE_ALPHA'
    )
    
    # Управление маской в мультипассе
    pass0_use_mask: BoolProperty(name="Mask Pass 0", default=True)
    pass1_use_mask: BoolProperty(name="Mask Pass 1", default=False)

    # Мультипасс (бывший Mirror)
    multi_pass_mode: EnumProperty(
        name="Pass Mode",
        items=[
            ('NONE', "Single Pass", ""),
            ('DUPLICATE', "Duplicate (Sync)", ""),
            ('INDIVIDUAL', "Individual (L/R)", "")
        ],
        default='NONE'
    )
    multi_pass_data: FloatVectorProperty(name="Pass Data", size=4, default=(0.0, 0.0, 0.0, 1.0))
    
    # New Multi-pass data (Normalized)
    multi_pass_rect: IntVectorProperty(name="Pass Rect (X, Y, W, H)", size=4, default=(0, 0, 1024, 1024))
    multi_pass_rotation: IntProperty(name="Pass Rotation")
    multi_pass_dummy: IntProperty(name="Pass Dummy")
    multi_pass_mirror: BoolProperty(name="Pass Mirror")
    multi_pass_flip: BoolProperty(name="Pass Flip")

    # Warp (Lattice 3x3)
    warp_p0_enabled: BoolProperty(name="Warp Pass 0", default=False)
    warp_p0_debug: BoolProperty(name="Debug Mode P0", default=False)
    # 18 floats = 9 points (x, y)
    warp_p0_grid: FloatVectorProperty(name="Lattice P0", size=18, default=(0.0,)*18)

    warp_p1_enabled: BoolProperty(name="Warp Pass 1", default=False)
    warp_p1_debug: BoolProperty(name="Debug Mode P1", default=False)
    warp_p1_grid: FloatVectorProperty(name="Lattice P1", size=18, default=(0.0,)*18)

    # HSV: Теперь одна ссылка на Векторную переменную
    hsv_enabled: BoolProperty(default=False)
    hsv_mask_enabled: BoolProperty(name="Use HSV Mask", default=False)
    hsv_link: StringProperty(name="HSV Variable", description="Link to a VECTOR value ($MyVar)")
    hsv_base: FloatVectorProperty(name="HSV Base", size=4, default=(0.0, 0.0, 0.0, 1.0))

# --- 4. COMPONENTS & MAIN BLOCKS ---

class TexWorksComponent(bpy.types.PropertyGroup):
    name: StringProperty(name="Component Name", default="NewComponent")
    # Базовый ресурс (исходная текстура кожи/одежды)
    base_resource_name: StringProperty(name="Base Resource", description="Original texture for the canvas")
    base_rect: IntVectorProperty(name="Base Rect (X, Y, W, H)", size=4, default=(0, 0, 1024, 1024))
    
    rect: IntVectorProperty(name="Rect (X, Y, W, H)", size=4, default=(0, 0, 4096, 4096))
    mask_enabled: BoolProperty(name="Use Component Mask", default=False)
    
    # TexMorph
    tex_morph_enabled: BoolProperty(name="TexMorph", default=False)
    tex_morph_resource_name: StringProperty(name="Morph Resource", description="Second texture for morphing")
    tex_morph_link: StringProperty(name="Morph Variable", description="Link to a FLOAT value ($MyVar)")

    # UI State
    tw_is_expanded: BoolProperty(name="UI Expanded", default=False)

    slots: CollectionProperty(type=TexWorksSlot)
    active_slot_index: IntProperty()


class TexWorksMainBlock(bpy.types.PropertyGroup):
    name: StringProperty(name="Block Name", default="MainBlock")
    resource_name: StringProperty(name="Output Resource", description="Virtual texture for this block")
    
    # Подложка (Backdrop) - инициализируется один раз
    backdrop_enabled: BoolProperty(name="Use Backdrop", default=False)
    backdrop_resource_name: StringProperty(name="Backdrop Res", description="Global podlozhka for the block")
    backdrop_rect: IntVectorProperty(name="Backdrop Rect", size=4, default=(0, 0, 4096, 4096))

    shader_type: EnumProperty(
        name="Shader Type",
        items=[
            ('DIFFUSE', "Diffuse (decal_draw.hlsl)", ""),
            ('MATERIAL', "Material (decal_draw_material.hlsl)", ""),
            ('NORMAL', "Normal (decal_draw_material.hlsl)", ""),
        ],
        default='DIFFUSE'
    )

    components: CollectionProperty(type=TexWorksComponent)
    active_component_index: IntProperty()
