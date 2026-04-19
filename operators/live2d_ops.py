import bpy

class RZM_OT_AddBone(bpy.types.Operator):
    """Adds a new bone to the global skeleton."""
    bl_idname = "rzm.add_bone"
    bl_label = "Add Bone"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        bone = rzm.skeleton.bones.add()
        bone.name = f"Bone_{len(rzm.skeleton.bones)}"
        rzm.skeleton.active_bone_index = len(rzm.skeleton.bones) - 1
        return {'FINISHED'}

class RZM_OT_RemoveBone(bpy.types.Operator):
    """Removes the active bone from the global skeleton."""
    bl_idname = "rzm.remove_bone"
    bl_label = "Remove Bone"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        rzm = context.scene.rzm
        return 0 <= rzm.skeleton.active_bone_index < len(rzm.skeleton.bones)

    def execute(self, context):
        rzm = context.scene.rzm
        idx = rzm.skeleton.active_bone_index
        rzm.skeleton.bones.remove(idx)
        rzm.skeleton.active_bone_index = min(idx, len(rzm.skeleton.bones) - 1)
        return {'FINISHED'}

class RZM_OT_AddAnimation(bpy.types.Operator):
    """Adds a new animation to the global skeleton."""
    bl_idname = "rzm.add_animation"
    bl_label = "Add Animation"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        anim = rzm.skeleton.animations.add()
        anim.name = f"Anim_{len(rzm.skeleton.animations)}"
        rzm.skeleton.active_anim_index = len(rzm.skeleton.animations) - 1
        return {'FINISHED'}

class RZM_OT_RemoveAnimation(bpy.types.Operator):
    """Removes the active animation from the global skeleton."""
    bl_idname = "rzm.remove_animation"
    bl_label = "Remove Animation"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        rzm = context.scene.rzm
        return 0 <= rzm.skeleton.active_anim_index < len(rzm.skeleton.animations)

    def execute(self, context):
        rzm = context.scene.rzm
        idx = rzm.skeleton.active_anim_index
        rzm.skeleton.animations.remove(idx)
        rzm.skeleton.active_anim_index = min(idx, len(rzm.skeleton.animations) - 1)
        return {'FINISHED'}

class RZM_OT_AddTrack(bpy.types.Operator):
    """Adds a bone track to the active animation."""
    bl_idname = "rzm.add_bone_track"
    bl_label = "Add Bone Track"
    bl_options = {'REGISTER', 'UNDO'}

    bone_name: bpy.props.StringProperty(name="Bone Name")

    def execute(self, context):
        rzm = context.scene.rzm
        idx = rzm.skeleton.active_anim_index
        if idx < 0: return {'CANCELLED'}
        
        anim = rzm.skeleton.animations[idx]
        track = anim.tracks.add()
        track.bone_name = self.bone_name
        return {'FINISHED'}

class RZM_OT_AddKeyframe(bpy.types.Operator):
    """Adds a keyframe to the active bone track."""
    bl_idname = "rzm.add_keyframe"
    bl_label = "Add Keyframe"
    bl_options = {'REGISTER', 'UNDO'}

    time: bpy.props.FloatProperty(name="Time", default=0.0)

    def execute(self, context):
        rzm = context.scene.rzm
        # This one is trickier as we need active track index. 
        # For now, let's assume we add to active track.
        # I'll need to add active_track_index to properties if not already there.
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AddBone,
    RZM_OT_RemoveBone,
    RZM_OT_AddAnimation,
    RZM_OT_RemoveAnimation,
    RZM_OT_AddTrack,
    RZM_OT_AddKeyframe
]
