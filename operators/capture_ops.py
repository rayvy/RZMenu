# RZMenu/operators/capture_ops.py
import bpy
from .. import captures
from ..helpers import get_next_image_id

class RZM_OT_CaptureImage(bpy.types.Operator):
    bl_idname = "rzm.capture_image"
    bl_label = "Capture Image"
    bl_description = "Renders the viewport and adds it as a 'Captured' image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.rzm_capture_settings
        
        # Pass False for force_framing to respect manual view settings
        rendered_image = captures.execute_capture(context, settings, force_framing=False)

        if not rendered_image:
            self.report({'ERROR'}, "Capture failed. Check system console for details.")
            return {'CANCELLED'}

        active_obj = context.active_object
        toggles_state = ""
        if active_obj:
            states = []
            for key in sorted(active_obj.keys()):
                if key.startswith("rzm.Toggle."):
                    base_name = key.replace("rzm.Toggle.", "", 1)
                    try:
                        bits_str = "".join(str(bit) for bit in active_obj[key])
                        states.append(f"{base_name}:{bits_str}")
                    except (TypeError, ValueError):
                        pass
            toggles_state = ";".join(states)

        overwrite_id = scene.rzm_capture_overwrite_id
        rzm_images = scene.rzm.images
        target_image = next((img for img in rzm_images if img.id == overwrite_id), None)
        
        if target_image:
            old_bl_image = target_image.image_pointer
            target_image.image_pointer = rendered_image
            target_image.captured_toggles = toggles_state
            target_image.source_type = 'CAPTURED' 
            if old_bl_image and old_bl_image != rendered_image and old_bl_image.users == 0:
                bpy.data.images.remove(old_bl_image)
            self.report({'INFO'}, f"Image ID {overwrite_id} overwritten.")
        else:
            new_id = get_next_image_id(rzm_images)
            new_rzm_image = rzm_images.add()
            new_rzm_image.id = new_id
            new_rzm_image.display_name = f"Capture_{new_id}"
            new_rzm_image.image_pointer = rendered_image
            new_rzm_image.source_type = 'CAPTURED'
            new_rzm_image.captured_toggles = toggles_state
            context.scene.rzm_active_image_index = len(rzm_images) - 1
            self.report({'INFO'}, f"Created new captured image with ID {new_id}.")

        scene.rzm_capture_overwrite_id = -1
        bpy.ops.rzm.record_history_state()
        
        # Redraw UI
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'UI':
                            region.tag_redraw()
        return {'FINISHED'}


class RZM_OT_AutoCapture(bpy.types.Operator):
    bl_idname = "rzm.auto_capture"
    bl_label = "Auto Capture Toggle Objects"
    bl_description = "Automatically captures icons for all objects with assigned toggles"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        
        target_objects = [
            obj for obj in scene.objects if any(k.startswith("rzm.Toggle.") for k in obj.keys())
        ]

        if not target_objects:
            self.report({'WARNING'}, "No objects with assigned RZ-Toggles found.")
            return {'CANCELLED'}

        original_settings = {
            k: getattr(scene.rzm_capture_settings, k) 
            for k in scene.rzm_capture_settings.bl_rna.properties.keys() if k != 'rna_type'
        }
        original_active = context.view_layer.objects.active
        original_selected = context.selected_objects[:]
        
        capture_settings = scene.rzm_capture_settings
        capture_settings.shading_mode = 'MATERIAL'
        capture_settings.use_overlays = False
        capture_settings.resolution = 128
        
        captured_count = 0
        
        try:
            for obj in target_objects:
                print(f"AUTO-CAPTURE: Processing '{obj.name}'...")
                
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                context.view_layer.objects.active = obj
                
                # Pass True for force_framing to center the object
                rendered_image = captures.execute_capture(context, capture_settings, force_framing=True)
                
                if rendered_image:
                    rzm_images = scene.rzm.images
                    new_id = get_next_image_id(rzm_images)
                    new_rzm_image = rzm_images.add()
                    new_rzm_image.id = new_id
                    new_rzm_image.display_name = f"Auto_{obj.name}_{new_id}"
                    new_rzm_image.image_pointer = rendered_image
                    new_rzm_image.source_type = 'CAPTURED'
                    new_rzm_image.captured_toggles = ""
                    captured_count += 1
        finally:
            print("AUTO-CAPTURE: Restoring original state...")
            for key, value in original_settings.items():
                try:
                    setattr(scene.rzm_capture_settings, key, value)
                except:
                    pass
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selected:
                obj.select_set(True)
            context.view_layer.objects.active = original_active

        self.report({'INFO'}, f"Auto-Capture finished. Created {captured_count} icons.")
        if captured_count > 0:
            bpy.ops.rzm.record_history_state()
            
        # Redraw UI
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'UI':
                            region.tag_redraw()
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_CaptureImage,
    RZM_OT_AutoCapture,
]
