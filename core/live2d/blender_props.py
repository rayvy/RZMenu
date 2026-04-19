import bpy
from bpy.props import (
    StringProperty, IntProperty, FloatProperty, BoolProperty,
    FloatVectorProperty, CollectionProperty, PointerProperty, EnumProperty,
)

class RZBoneProp(bpy.types.PropertyGroup):
    name: StringProperty(name="Bone Name", default="Bone")
    parent_name: StringProperty(name="Parent", default="")
    pos: FloatVectorProperty(name="Position", size=2, default=(0.0, 0.0))
    rot: FloatProperty(name="Rotation", default=0.0)
    scale: FloatVectorProperty(name="Scale", size=2, default=(1.0, 1.0))
    pivot: FloatVectorProperty(name="Pivot", size=2, default=(0.0, 0.0))

class RZKeyframeProp(bpy.types.PropertyGroup):
    time: FloatProperty(name="Time", default=0.0)
    pos: FloatVectorProperty(name="Position", size=2, default=(0.0, 0.0))
    rot: FloatProperty(name="Rotation", default=0.0)
    scale: FloatVectorProperty(name="Scale", size=2, default=(1.0, 1.0))
    easing: EnumProperty(
        name="Easing",
        items=[
            ('LINEAR', "Linear", ""),
            ('EASE', "Ease In/Out", ""),
            ('BEZIER', "Bezier", "")
        ],
        default='LINEAR'
    )
    cp: FloatVectorProperty(name="Control Points", size=4, default=(0.25, 0.25, 0.75, 0.75))

class RZBoneTrackProp(bpy.types.PropertyGroup):
    bone_name: StringProperty(name="Bone Name")
    keyframes: CollectionProperty(type=RZKeyframeProp)

class RZAnimationProp(bpy.types.PropertyGroup):
    name: StringProperty(name="Animation Name", default="New Animation")
    duration: FloatProperty(name="Duration", default=2.0)
    loop: BoolProperty(name="Loop", default=True)
    tracks: CollectionProperty(type=RZBoneTrackProp)

class RZSkeletonProp(bpy.types.PropertyGroup):
    skeleton_name: StringProperty(name="Skeleton Name", default="Main Skeleton")
    bones: CollectionProperty(type=RZBoneProp)
    animations: CollectionProperty(type=RZAnimationProp)
    active_bone_index: IntProperty(default=-1)
    active_anim_index: IntProperty(default=-1)

class RZMeshVertexProp(bpy.types.PropertyGroup):
    pos: FloatVectorProperty(name="Pos", size=2)
    uv: FloatVectorProperty(name="UV", size=2)

class RZMeshWeightProp(bpy.types.PropertyGroup):
    # IDs: b0, b1, b2, b3
    bone_ids: FloatVectorProperty(name="Bone IDs", size=4, default=(-1.0, -1.0, -1.0, -1.0))
    # Weights: w0, w1, w2, w3
    weights: FloatVectorProperty(name="Weights", size=4, default=(0.0, 0.0, 0.0, 0.0))

class RZMeshProp(bpy.types.PropertyGroup):
    cols: IntProperty(name="Columns", default=4, min=2)
    rows: IntProperty(name="Rows", default=4, min=2)
    vertices: CollectionProperty(type=RZMeshVertexProp)
    weights: CollectionProperty(type=RZMeshWeightProp)
    mesh_offset: IntProperty(name="Mesh Offset", default=0) # Index in big GPU buffer

def register():
    bpy.utils.register_class(RZBoneProp)
    bpy.utils.register_class(RZKeyframeProp)
    bpy.utils.register_class(RZBoneTrackProp)
    bpy.utils.register_class(RZAnimationProp)
    bpy.utils.register_class(RZSkeletonProp)
    bpy.utils.register_class(RZMeshVertexProp)
    bpy.utils.register_class(RZMeshWeightProp)
    bpy.utils.register_class(RZMeshProp)

def unregister():
    bpy.utils.unregister_class(RZMeshProp)
    bpy.utils.unregister_class(RZMeshWeightProp)
    bpy.utils.unregister_class(RZMeshVertexProp)
    bpy.utils.unregister_class(RZSkeletonProp)
    bpy.utils.unregister_class(RZAnimationProp)
    bpy.utils.unregister_class(RZBoneTrackProp)
    bpy.utils.unregister_class(RZKeyframeProp)
    bpy.utils.unregister_class(RZBoneProp)
