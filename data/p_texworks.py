# RZMenu/data/p_texworks.py
import bpy
from bpy.props import StringProperty, IntProperty, BoolProperty, EnumProperty, PointerProperty, IntVectorProperty, CollectionProperty

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