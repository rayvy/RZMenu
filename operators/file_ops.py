# RZMenu/operators/file_ops.py
import bpy
import json
import os
import zipfile
import tempfile
from pathlib import Path
from ..rzm_serialization import rzm_to_dict, dict_to_rzm
from ..rzm_history import history_manager

# --- Сохранение / Загрузка / Сброс ---
class RZM_OT_SaveTemplate(bpy.types.Operator):
    """Сохраняет всю структуру RZM в .rzm (zip) архив."""
    bl_idname = "rzm.save_template"
    bl_label = "Save RZM Scene"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.rzm", options={'HIDDEN'})
    
    def invoke(self, context, event):
        self.filepath = "rzm_scene.rzm"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        
    def execute(self, context):
        try:
            with zipfile.ZipFile(self.filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('scene.json', json.dumps(rzm_to_dict(context.scene.rzm), indent=2, ensure_ascii=False))
                with tempfile.TemporaryDirectory() as tmpdir:
                    for img in context.scene.rzm.images:
                        if img.source_type in {'CUSTOM', 'CAPTURED'} and img.image_pointer:
                            bl_image = img.image_pointer
                            bl_image.file_format = bl_image.file_format or 'PNG'
                            ext = bl_image.file_format.lower().replace('jpeg', 'jpg')
                            filename = f"{img.display_name}.{ext}"
                            save_path = os.path.join(tmpdir, filename)
                            bl_image.save_render(save_path)
                            zf.write(save_path, arcname=f'images/{filename}')
            self.report({'INFO'}, f"RZM Scene saved to {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save .rzm file: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


class RZM_OT_LoadTemplate(bpy.types.Operator):
    """Загружает структуру RZM из .rzm (zip) архива."""
    bl_idname = "rzm.load_template"
    bl_label = "Load RZM Scene"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.rzm", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        
    def execute(self, context):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(self.filepath, 'r') as zf:
                    zf.extractall(tmpdir)
                
                loaded_images_map = {}
                images_path = os.path.join(tmpdir, 'images')
                if os.path.exists(images_path):
                    for filename in os.listdir(images_path):
                        try:
                            bl_image = bpy.data.images.load(os.path.join(images_path, filename), check_existing=True)
                            bl_image.pack()
                            loaded_images_map[Path(filename).stem] = bl_image
                        except Exception as e:
                            print(f"WARNING: Could not load image {filename}: {e}")
                
                with open(os.path.join(tmpdir, 'scene.json'), 'r', encoding='utf-8') as f:
                    data_to_load = json.load(f)

                rzm = context.scene.rzm
                # Clear all collections
                collections_to_clear = [
                    rzm.images, rzm.elements, rzm.rzm_values, rzm.toggle_definitions,
                    rzm.conditions, rzm.shapes, rzm.addons.tw_texture_configs,
                    rzm.addons.tw_textures, rzm.addons.tw_resources, rzm.addons.tw_overrides
                ]
                for coll in collections_to_clear:
                    coll.clear()
                
                dict_to_rzm(data_to_load, rzm)
                
                lost_image_ids = set()
                assets_dir = os.path.join(os.path.dirname(__file__), '..', 'base_icons')
                for rzm_image in rzm.images:
                    if rzm_image.source_type in {'CUSTOM', 'CAPTURED'}:
                        if rzm_image.display_name in loaded_images_map:
                            rzm_image.image_pointer = loaded_images_map[rzm_image.display_name]
                        else:
                            lost_image_ids.add(rzm_image.id)
                    elif rzm_image.source_type == 'BASE':
                        filename_base = f"{rzm_image.id}_{rzm_image.display_name}" if rzm_image.display_name else f"{rzm_image.id}"
                        found_file = False
                        for ext in ['.png', '.jpg', '.jpeg', '.tga', '.bmp']:
                            filepath = os.path.join(assets_dir, filename_base + ext)
                            if os.path.exists(filepath):
                                try:
                                    bl_image = bpy.data.images.load(filepath, check_existing=True)
                                    bl_image.pack()
                                    rzm_image.image_pointer = bl_image
                                    found_file = True
                                    break
                                except Exception as e:
                                    print(f"ERROR: Found BASE icon file '{filepath}', but failed to load: {e}")
                        if not found_file:
                            lost_image_ids.add(rzm_image.id)
                
                if lost_image_ids:
                    for elem in rzm.elements:
                        if elem.image_mode == 'SINGLE' and elem.image_id in lost_image_ids:
                            elem.image_id = -9999
                        else:
                            for cond_img in elem.conditional_images:
                                if cond_img.image_id in lost_image_ids:
                                    cond_img.image_id = -9999
            
            history_manager.clear()
            bpy.ops.rzm.record_history_state()
            self.report({'INFO'}, f"RZM Scene loaded from {self.filepath}")

        except Exception as e:
            self.report({'ERROR'}, f"Failed to load .rzm file: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
            
        return {'FINISHED'}


class RZM_OT_ResetScene(bpy.types.Operator):
    """Полностью очищает все данные RZM в текущей сцене."""
    bl_idname = "rzm.reset_scene"
    bl_label = "Reset RZM Scene"
    bl_description = "Completely clears all RZM data. This action cannot be undone by Blender's native undo"
    bl_options = {'REGISTER'}
    
    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        rzm = context.scene.rzm
        collections_to_clear = [
            rzm.elements, rzm.rzm_values, rzm.toggle_definitions, rzm.images, 
            rzm.conditions, rzm.shapes, rzm.addons.tw_texture_configs, 
            rzm.addons.tw_textures, rzm.addons.tw_resources, rzm.addons.tw_overrides
        ]
        for coll in collections_to_clear:
            coll.clear()
        
        # Reset indices
        context.scene.rzm_active_element_index = 0
        context.scene.rzm_active_value_index = 0
        context.scene.rzm_active_toggle_def_index = 0
        context.scene.rzm_active_image_index = 0
        
        history_manager.clear()
        bpy.ops.rzm.record_history_state()
        self.report({'INFO'}, "RZM scene has been reset.")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_SaveTemplate,
    RZM_OT_LoadTemplate,
    RZM_OT_ResetScene,
]
