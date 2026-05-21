import bpy
from bpy.props import StringProperty, BoolProperty, CollectionProperty, EnumProperty

class RZMCM_Part(bpy.types.PropertyGroup):
    name: StringProperty(name="Name")
    enabled: BoolProperty(name="Enabled", default=False)

class RZMCM_Component(bpy.types.PropertyGroup):
    name: StringProperty(name="Name")
    blend_copy_enabled: BoolProperty(name="Blend Copy", default=False)
    parts: CollectionProperty(type=RZMCM_Part)

class RZMComponentManagerSettings(bpy.types.PropertyGroup):
    dump_path: StringProperty(
        name="Dump Path", 
        description="Path to the mod dump folder containing hash.json or metadata.json",
        subtype='DIR_PATH'
    )
    components: CollectionProperty(type=RZMCM_Component)
    active_tab: EnumProperty(
        name="Tab",
        items=[
            ('BLEND_COPY', "BlendCopy", ""),
            ('TEST_SUBCOMP', "TestSubComp", "")
        ],
        default='BLEND_COPY'
    )
