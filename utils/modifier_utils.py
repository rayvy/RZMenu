import time
import bpy

def apply_modifiers_for_object_with_shape_keys(context, originalObject, selectedModifiers, disable_armatures=True):
    """
    EFMI Algorithm adapted for RZMenu:
    Apply a list of modifiers to an object while preserving shape keys.
    """
    if len(selectedModifiers) == 0:
        return (True, None)

    list_properties = []
    properties = ["interpolation", "mute", "name", "relative_key", "slider_max", "slider_min", "value", "vertex_group"]
    shapesCount = 0
    vertCount = -1
    startTime = time.time()
    
    # Inspect modifiers for hints used in error message if needed.
    contains_mirror_with_merge = False
    for modifier in originalObject.modifiers:
        if modifier.name in selectedModifiers:
            if modifier.type == 'MIRROR' and modifier.use_mirror_merge == True:
                contains_mirror_with_merge = True

    # Disable armature modifiers.
    disabled_armature_modifiers = []
    if disable_armatures:
        for modifier in originalObject.modifiers:
            if modifier.name not in selectedModifiers and modifier.type == 'ARMATURE' and modifier.show_viewport == True:
                disabled_armature_modifiers.append(modifier)
                modifier.show_viewport = False
    
    # Calculate shape keys count.
    if originalObject.data.shape_keys:
        shapesCount = len(originalObject.data.shape_keys.key_blocks)
    
    # If there are no shape keys, just apply modifiers.
    if(shapesCount == 0):
        for modifierName in selectedModifiers:
            try:
                bpy.ops.object.modifier_apply(modifier=modifierName)
            except Exception as e:
                print(f"[RZM Mod Utils] Failed to apply {modifierName}: {e}")
        return (True, None)
    
    # We want to preserve original object, so all shapes will be joined to it.
    bpy.ops.object.select_all(action='DESELECT')
    originalObject.select_set(True)
    context.view_layer.objects.active = originalObject
    
    # Copy object which will holds all shape keys.
    bpy.ops.object.duplicate_move()
    copyObject = context.view_layer.objects.active
    copyObject.select_set(False)
    
    # Return selection to originalObject.
    context.view_layer.objects.active = originalObject
    originalObject.select_set(True)
    
    # Save key shape properties
    for i in range(0, shapesCount):
        key_b = originalObject.data.shape_keys.key_blocks[i]
        properties_object = {p:None for p in properties}
        properties_object["name"] = key_b.name
        properties_object["mute"] = key_b.mute
        properties_object["interpolation"] = key_b.interpolation
        properties_object["relative_key"] = key_b.relative_key.name if key_b.relative_key else ""
        properties_object["slider_max"] = key_b.slider_max
        properties_object["slider_min"] = key_b.slider_min
        properties_object["value"] = key_b.value
        properties_object["vertex_group"] = key_b.vertex_group
        list_properties.append(properties_object)

    # Handle base shape in "originalObject"
    bpy.ops.object.shape_key_remove(all=True)
    for modifierName in selectedModifiers:
        try:
            bpy.ops.object.modifier_apply(modifier=modifierName)
        except Exception as e:
            print(f"[RZM Mod Utils - Base Shape] Failed to apply {modifierName}: {e}")
            
    vertCount = len(originalObject.data.vertices)
    bpy.ops.object.shape_key_add(from_mix=False)
    originalObject.select_set(False)
    
    # Handle other shape-keys: copy object, get right shape-key, apply modifiers and merge with originalObject.
    for i in range(1, shapesCount):
        context.view_layer.objects.active = copyObject
        copyObject.select_set(True)
        
        # Copy temp object.
        bpy.ops.object.duplicate_move()
        tmpObject = context.view_layer.objects.active
        bpy.ops.object.shape_key_remove(all=True)
        copyObject.select_set(True)
        copyObject.active_shape_key_index = i
        
        # Get right shape-key.
        bpy.ops.object.shape_key_transfer()
        context.object.active_shape_key_index = 0
        bpy.ops.object.shape_key_remove()
        bpy.ops.object.shape_key_remove(all=True)
        
        # Time to apply modifiers.
        for modifierName in selectedModifiers:
            try:
                bpy.ops.object.modifier_apply(modifier=modifierName)
            except Exception as e:
                pass
        
        # Verify number of vertices.
        if vertCount != len(tmpObject.data.vertices):
            errorInfoHint = ""
            if contains_mirror_with_merge == True:
                errorInfoHint = "There is mirror modifier with 'Merge' property enabled. This may cause a problem."
            if errorInfoHint:
                errorInfoHint = "\n\nHint: " + errorInfoHint
            errorInfo = ("Shape keys ended up with different number of vertices!\n"
                         "All shape keys needs to have the same number of vertices after modifier is applied.\n"
                         "Otherwise joining such shape keys will fail!%s" % errorInfoHint)
            return (False, errorInfo)
    
        # Join with originalObject
        copyObject.select_set(False)
        context.view_layer.objects.active = originalObject
        originalObject.select_set(True)
        bpy.ops.object.join_shapes()
        originalObject.select_set(False)
        context.view_layer.objects.active = tmpObject
        
        # Remove tmpObject
        tmpMesh = tmpObject.data
        bpy.ops.object.delete(use_global=False)
        bpy.data.meshes.remove(tmpMesh)
    
    # Restore shape key properties like name, mute etc.
    context.view_layer.objects.active = originalObject
    for i in range(0, shapesCount):
        key_b = context.view_layer.objects.active.data.shape_keys.key_blocks[i]
        key_b.name = list_properties[i]["name"]
        
    for i in range(0, shapesCount):
        key_b = context.view_layer.objects.active.data.shape_keys.key_blocks[i]
        key_b.interpolation = list_properties[i]["interpolation"]
        key_b.mute = list_properties[i]["mute"]
        key_b.slider_max = list_properties[i]["slider_max"]
        key_b.slider_min = list_properties[i]["slider_min"]
        key_b.value = list_properties[i]["value"]
        key_b.vertex_group = list_properties[i]["vertex_group"]
        rel_key = list_properties[i]["relative_key"]
    
        if rel_key:
            for j in range(0, shapesCount):
                key_brel = context.view_layer.objects.active.data.shape_keys.key_blocks[j]
                if rel_key == key_brel.name:
                    key_b.relative_key = key_brel
                    break
    
    # Remove copyObject.
    originalObject.select_set(False)
    context.view_layer.objects.active = copyObject
    copyObject.select_set(True)
    tmpMesh = copyObject.data
    bpy.ops.object.delete(use_global=False)
    bpy.data.meshes.remove(tmpMesh)
    
    # Select originalObject.
    context.view_layer.objects.active = originalObject
    context.view_layer.objects.active.select_set(True)
    
    if disable_armatures:
        for modifier in disabled_armature_modifiers:
            modifier.show_viewport = True
    
    return (True, None)
