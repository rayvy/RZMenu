# RZMenu/data/p_texworks.py
import bpy
from bpy.props import (StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, 
                       PointerProperty, IntVectorProperty, FloatVectorProperty, CollectionProperty)

# --- 1. CORE RESOURCES (Теперь включают параметры формата) ---

class TexResource(bpy.types.PropertyGroup):
    name: StringProperty(name="Resource Name")
    type: EnumProperty(name="Type", items=[
        ('EMPTY', "Empty", ""), 
        ('ON_DISK', "On Disk (Physical)", ""), 
        ('VIRTUAL', "Virtual (Canvas)", "")
    ], default='ON_DISK')
    
    qt_tag: StringProperty(name="Tag", description="Visual tag for organization")
    qt_favorite: BoolProperty(name="Favorite", default=False)
    
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

class TexOverrideBinding(bpy.types.PropertyGroup):
    tex_type: StringProperty(
        name="Tex Type",
        description="Preset slot name or custom target, e.g. Diffuse, NormalMap, ps-t0",
        default="Diffuse"
    )
    resource_name: StringProperty(name="Resource Name")
    custom_target: BoolProperty(
        name="Custom",
        description="Write tex_type as a raw target instead of Resource\\ZZMI\\<Preset>",
        default=False
    )


class TexOverride(bpy.types.PropertyGroup):
    name: StringProperty(name="Override Name")
    hash: StringProperty(name="Hash")
    resource_name: StringProperty(name="Resource Name")
    override_mode: EnumProperty(
        name="Mode",
        items=[
            ('TEX_DIRECT', "TEX_DIRECT", "Classic TextureOverride replacement via this = Resource"),
            ('IB_DIRECT', "IB_DIRECT", "Bind a TexWorks resource to a ZZMI slot or a raw ps-tN slot"),
        ],
        default='TEX_DIRECT'
    )
    slot_target: StringProperty(
        name="Slot",
        description="IB_DIRECT target: Diffuse, NormalMap, LightMap, MaterialMap, or ps-tN",
        default="Diffuse"
    )
    bindings: CollectionProperty(type=TexOverrideBinding)
    active_binding_index: IntProperty()
    qt_tag: StringProperty(name="Tag", description="Visual tag for organization")
    qt_favorite: BoolProperty(name="Favorite", default=False)

# --- 2. MATERIALS (Поведение) ---

class TexWorksMaterial(bpy.types.PropertyGroup):
    name: StringProperty(name="Material Name", default="NewMaterial")
    material: PointerProperty(type=bpy.types.Material)
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

    # UV Calculator Settings
    calc_res_x: IntProperty(name="Res X", default=2048, min=1)
    calc_res_y: IntProperty(name="Res Y", default=2048, min=1)
    calc_padding: IntProperty(name="Padding", default=4, min=0)

    # HSV: Теперь одна ссылка на Векторную переменную
    hsv_enabled: BoolProperty(default=False)
    hsv_only: BoolProperty(name="HSV Only", default=False)
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

    # Shared Config (Config/Warp)
    use_shared_config: BoolProperty(
        name="Use Shared Config",
        description="Don't generate config/warp resources, use from another block/component",
        default=False
    )
    shared_config_block: StringProperty(
        name="Source Block",
        description="Name of the block to take config from"
    )
    shared_config_component: StringProperty(
        name="Source Component",
        description="Name of the component to take config from"
    )

    # UI State
    tw_is_expanded: BoolProperty(name="UI Expanded", default=False)

    slots: CollectionProperty(type=TexWorksSlot)
    active_slot_index: IntProperty()

    # HSV (Component level)
    hsv_enabled: BoolProperty(default=False)
    hsv_mask_enabled: BoolProperty(name="Use HSV Mask", default=False)
    hsv_link: StringProperty(name="HSV Variable", description="Link to a VECTOR value ($MyVar)")
    hsv_base: FloatVectorProperty(name="HSV Base", size=4, default=(0.0, 0.0, 0.0, 1.0))


class TexWorksMainBlock(bpy.types.PropertyGroup):
    name: StringProperty(name="Block Name", default="MainBlock")
    resource_name: StringProperty(name="Output Resource", description="Virtual texture for this block")
    create_block_resource: BoolProperty(
        name="Create Block Resource",
        description="Emit a RWTexture2D resource for this block even when it is not listed in global TexWorks resources",
        default=False,
    )
    block_resource_size: IntVectorProperty(
        name="Block Size",
        description="RWTexture2D size for generated block resources",
        size=2,
        default=(4096, 4096),
        min=1,
    )
    
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

    shader_config: FloatVectorProperty(
        name="Shader Config (x46)", 
        size=4, 
        default=(1.0, 1.0, 1.0, 1.0)
    )

    shader_overlay: FloatVectorProperty(
        name="Shader Overlay (x47)", 
        size=4, 
        default=(0.0, 0.0, 0.0, 0.0)
    )

    use_shared_textures: BoolProperty(
        name="Use Shared Textures",
        description="Don't generate resources, use textures from another block",
        default=False
    )
    shared_textures_block: StringProperty(
        name="Source Block",
        description="Name of the block to take textures from"
    )

    uv_rescale: FloatProperty(
        name="UV Rescale",
        description="Global UV rescale factor for future map optimizations (e.g. 4k -> 2k)",
        default=1.0
    )

    components: CollectionProperty(type=TexWorksComponent)
    active_component_index: IntProperty()


class TexWorksMCFile(bpy.types.PropertyGroup):
    name: StringProperty(name="Entry Name")
    material_name: StringProperty(name="Material")
    material_key: StringProperty(name="Material Key")
    slot_name: StringProperty(name="Slot")
    resource_name: StringProperty(name="Resource")
    relative_path: StringProperty(name="Relative Path")
    block_name: StringProperty(name="Block")
    resolution: IntVectorProperty(name="Resolution", size=2, default=(0, 0))


class TexWorksMCSettings(bpy.types.PropertyGroup):
    enabled: BoolProperty(
        name="Enable MC",
        description="Enable the material-cluster TexWorks bridge",
        default=True,
    )
    output_subdir: StringProperty(
        name="Output Folder",
        description="Relative folder inside the mod export path for generated PNG clusters",
        default="Textures/DynAtlas",
    )
    default_resolution: IntVectorProperty(
        name="Fallback Resolution",
        description="Used when a material slot has no image texture and must be generated from a solid color",
        size=2,
        default=(512, 512),
        min=1,
    )
    reference_slot: EnumProperty(
        name="Reference Slot",
        description="Texture slot used to derive cluster pixel density when possible",
        items=[
            ('AUTO', "Auto", "Diffuse, then first available image slot, then fallback resolution"),
            ('Diffuse', "Diffuse", ""),
            ('LightMap', "LightMap", ""),
            ('MaterialMap', "MaterialMap", ""),
            ('NormalMap', "NormalMap", ""),
            ('Extra', "Extra", ""),
        ],
        default='AUTO',
    )
    vertex_margin_px: IntProperty(
        name="Island Margin",
        description="Extra pixel gutter around UV islands, used for packing and color dilation",
        default=4,
        min=0,
        max=128,
    )
    pack_gap_px: IntProperty(
        name="Pack Gap",
        description="Extra spacing between packed island groups",
        default=8,
        min=0,
        max=512,
    )
    max_atlas_size: IntProperty(
        name="Max Size",
        description="Hard limit for generated cluster PNG dimensions",
        default=8192,
        min=64,
        max=32768,
    )
    max_raster_pixels: IntProperty(
        name="Max Raster Pixels",
        description="Safety limit for CPU texture rasterization. Larger layouts fail fast instead of freezing Blender",
        default=16777216,
        min=1048576,
        max=268435456,
    )
    power_of_two_output: BoolProperty(
        name="Power Of Two",
        description="Round generated cluster PNG dimensions up to powers of two",
        default=False,
    )
    sync_blocks: BoolProperty(
        name="Sync Blocks",
        description="Also create/update TexWorks block/component data for packed cluster rects",
        default=True,
    )
    y_origin: EnumProperty(
        name="Y Origin",
        description="Manifest coordinate convention for rect data",
        items=[
            ('IMAGE_TOP_LEFT', "Image Top Left", "Y=0 is the top of the image"),
            ('UV_BOTTOM_LEFT', "UV Bottom Left", "Y=0 is the bottom of the UV space"),
        ],
        default='UV_BOTTOM_LEFT',
    )
