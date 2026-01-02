# RZMenu/data/p_settings.py
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty, IntVectorProperty

# Импорт зависимостей для CollectionProperty
from .p_texworks import TexResource, TexOverride, TexWorksTextureConfig, TexWorksTexture

class RZMenuConfig(bpy.types.PropertyGroup): canvas_size: IntVectorProperty(name="Canvas Size", size=2, default=(1920, 1080))

class DependencyStatus(bpy.types.PropertyGroup):
    """Holds the status of a single dependency."""
    name: StringProperty(name="Name")
    status: EnumProperty(
        name="Status",
        items=[
            ('UNKNOWN', "Unknown", "Status not checked yet"),
            ('NOT_FOUND', "Not Found", "Dependency is not installed"),
            ('OUTDATED', "Outdated", "An older version is installed"),
            ('OK', "OK", "Required version is installed"),
            ('NEWER', "Newer", "A newer version is installed"),
            ('INSTALLING', "Installing", "Installation in progress"),
        ],
        default='UNKNOWN'
    )
    installed_version: StringProperty(name="Installed Version")
    target_version: StringProperty(name="Target Version")
    is_optional: BoolProperty(name="Is Optional")
    install_progress: FloatProperty(name="Install Progress", subtype='PERCENTAGE', min=0, max=100, default=0.0)

class RZMExportSettings(bpy.types.PropertyGroup):
    mod_name: StringProperty(
        name="Mod Name", 
        default="My New Mod",
        description="Имя мода для ReadMe файла"
    )
    use_xxmi_path: BoolProperty(
        name="Use XXMI Path",
        default=True,
        description="Пытаться взять путь из настроек аддона XXMI Tools"
    )
    custom_path: StringProperty(
        name="Custom Path", 
        subtype='DIR_PATH',
        description="Запасной путь, если XXMI не найден"
    )
    overwrite_scripts: BoolProperty(
        name="Overwrite Scripts",
        default=False,
        description="ВНИМАНИЕ: Перезапишет скрипты (ini/py) в целевой папке"
    )

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