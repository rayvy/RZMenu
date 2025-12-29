# RZMenu/operators/file_ops.py
import bpy
import json
import os
import zipfile
import tempfile
from pathlib import Path

# FIX IMPORTS: Linking to the new core modules
from ..core.serialization import rzm_to_dict, dict_to_rzm

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
                # 1. Save JSON structure
                zf.writestr('scene.json', json.dumps(rzm_to_dict(context.scene.rzm), indent=2, ensure_ascii=False))
                
                # 2. Save Images
                with tempfile.TemporaryDirectory() as tmpdir:
                    for img in context.scene.rzm.images:
                        # Only save Custom or Captured images that have actual data
                        if img.source_type in {'CUSTOM', 'CAPTURED'} and img.image_pointer:
                            bl_image = img.image_pointer
                            
                            if not bl_image.has_data:
                                continue
                                
                            # Ensure format
                            bl_image.file_format = bl_image.file_format or 'PNG'
                            ext = bl_image.file_format.lower().replace('jpeg', 'jpg')
                            if not ext: ext = 'png'
                            
                            filename = f"{img.display_name}.{ext}"
                            save_path = os.path.join(tmpdir, filename)
                            
                            try:
                                bl_image.save_render(save_path)
                                zf.write(save_path, arcname=f'images/{filename}')
                            except Exception as e:
                                print(f"Warning: Failed to save image {img.display_name}: {e}")

            self.report({'INFO'}, f"RZM Scene saved to {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save .rzm file: {e}")
            return {'CANCELLED'}
        return {'FINISHED'}


class RZM_OT_LoadTemplate(bpy.types.Operator):
    """Загружает структуру RZM из .rzm (zip) архива."""
    bl_idname = "rzm.load_template"
    bl_label = "Load RZM Scene"
    bl_options = {'REGISTER', 'UNDO'} # Standard undo is enabled
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.rzm", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        
    def execute(self, context):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # 1. Extract ZIP
                with zipfile.ZipFile(self.filepath, 'r') as zf:
                    zf.extractall(tmpdir)
                
                # 2. Pre-load images from the 'images' subfolder
                loaded_images_map = {}
                images_path = os.path.join(tmpdir, 'images')
                if os.path.exists(images_path):
                    for filename in os.listdir(images_path):
                        try:
                            full_path = os.path.join(images_path, filename)
                            bl_image = bpy.data.images.load(full_path, check_existing=True)
                            bl_image.pack() # Pack into .blend immediately
                            # Use stem (filename without extension) as key
                            loaded_images_map[Path(filename).stem] = bl_image
                        except Exception as e:
                            print(f"WARNING: Could not load image {filename}: {e}")
                
                # 3. Load JSON Data
                json_path = os.path.join(tmpdir, 'scene.json')
                if not os.path.exists(json_path):
                    self.report({'ERROR'}, "Invalid RZM file: scene.json missing")
                    return {'CANCELLED'}

                with open(json_path, 'r', encoding='utf-8') as f:
                    data_to_load = json.load(f)

                rzm = context.scene.rzm
                
                # 4. Clear existing RZM data
                collections_to_clear = [
                    rzm.images, rzm.elements, rzm.rzm_values, rzm.toggle_definitions,
                    rzm.conditions, rzm.shapes, rzm.addons.tw_texture_configs,
                    rzm.addons.tw_textures, rzm.addons.tw_resources, rzm.addons.tw_overrides
                ]
                for coll in collections_to_clear:
                    coll.clear()
                
                # 5. Populate Data
                dict_to_rzm(data_to_load, rzm)
                
                # 6. Relink Images (Connect loaded/existing images to RZM data)
                lost_image_ids = set()
                
                # Determine path to base icons (assuming structure: RZMenu/operators/file_ops.py -> ... -> RZMenu/base_icons)
                addon_dir = Path(__file__).parent.parent
                base_icons_dir = addon_dir / "base_icons"

                for rzm_image in rzm.images:
                    if rzm_image.source_type in {'CUSTOM', 'CAPTURED'}:
                        # Try to find in the loaded zip images
                        if rzm_image.display_name in loaded_images_map:
                            rzm_image.image_pointer = loaded_images_map[rzm_image.display_name]
                        else:
                            lost_image_ids.add(rzm_image.id)
                    
                    elif rzm_image.source_type == 'BASE':
                        # Try to find in base_icons folder
                        found_file = False
                        if base_icons_dir.exists():
                            # Pattern usually: "9001_Arrow.png" or just "9001.png"
                            filename_base = f"{rzm_image.id}_{rzm_image.display_name}" if rzm_image.display_name else f"{rzm_image.id}"
                            
                            # Simple search
                            for ext in ['.png', '.jpg', '.jpeg', '.tga']:
                                filepath = base_icons_dir / (filename_base + ext)
                                if filepath.exists():
                                    try:
                                        bl_image = bpy.data.images.load(str(filepath), check_existing=True)
                                        bl_image.pack()
                                        rzm_image.image_pointer = bl_image
                                        found_file = True
                                        break
                                    except Exception:
                                        pass
                        
                        if not found_file:
                            lost_image_ids.add(rzm_image.id)
                
                # 7. Handle Broken Links (Optional visual indication)
                if lost_image_ids:
                    print(f"RZM Info: {len(lost_image_ids)} images could not be relinked.")
                    for elem in rzm.elements:
                        if elem.image_mode == 'SINGLE' and elem.image_id in lost_image_ids:
                            elem.image_id = -9999 # Visual error flag
                        else:
                            for cond_img in elem.conditional_images:
                                if cond_img.image_id in lost_image_ids:
                                    cond_img.image_id = -9999
            
            self.report({'INFO'}, f"RZM Scene loaded successfully from {os.path.basename(self.filepath)}")

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
    bl_description = "Completely clears all RZM data."
    bl_options = {'REGISTER', 'UNDO'}
    
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
        
        self.report({'INFO'}, "RZM scene has been reset.")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_SaveTemplate,
    RZM_OT_LoadTemplate,
    RZM_OT_ResetScene,
]