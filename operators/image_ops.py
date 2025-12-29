# RZMenu/operators/image_ops.py
import bpy
import os
from pathlib import Path
from ..core.utils import get_next_image_id
from ..core.atlas_algo import calculate_atlas_layout, create_atlas_pixels

class RZM_OT_LoadBaseIcons(bpy.types.Operator):
    """Scans the 'base_icons' folder and loads standard images."""
    bl_idname = "rzm.load_base_icons"
    bl_label = "Load Base Icons"
    bl_description = "Loads standard images from the addon's 'base_icons' folder"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        assets_dir = os.path.join(addon_dir, 'base_icons')
        
        if not os.path.exists(assets_dir):
            self.report({'WARNING'}, f"'base_icons' folder not found at: {assets_dir}")
            return {'CANCELLED'}
            
        print(f"DEBUG BASE ICONS: Scanning folder: {assets_dir}")
        rzm_images = context.scene.rzm.images
        existing_base_ids = {img.id for img in rzm_images if img.source_type == 'BASE'}
        
        loaded_count = 0
        for filename in os.listdir(assets_dir):
            base_name, ext = os.path.splitext(filename)
            ext = ext.lower()

            if ext not in ['.png', '.jpg', '.jpeg', '.dds']:
                continue

            parsed_id = -1
            display_name = base_name

            if base_name.startswith('9') and len(base_name) >= 4 and base_name[:4].isdigit():
                parsed_id = int(base_name[:4])
                if '_' in base_name:
                    display_name = base_name.split('_', 1)[1]
                else:
                    display_name = ""

            if parsed_id != -1:
                if parsed_id in existing_base_ids:
                    continue
                
                if ext == '.dds':
                    print(f"INFO: DDS support is in development. Skipping '{filename}'.")
                    continue
                
                try:
                    filepath = os.path.join(assets_dir, filename)
                    bl_image = bpy.data.images.load(filepath)
                    bl_image.pack()

                    new_item = rzm_images.add()
                    new_item.id = parsed_id
                    new_item.display_name = display_name
                    new_item.image_pointer = bl_image
                    new_item.source_type = 'BASE'
                    loaded_count += 1
                except Exception as e:
                    print(f"WARNING: Failed to load base asset '{filename}': {e}")
            else:
                print(f"DEBUG BASE ICONS: Skipping '{filename}' (does not match '9xxx_name' pattern).")

        self.report({'INFO'}, f"Loaded {loaded_count} new base icons.")
        if loaded_count > 0: # This line was missing an indented block. Added pass to fix.
            pass
            
        return {'FINISHED'}

class RZM_OT_UpdateAtlasLayout(bpy.types.Operator):
    """Calculates the layout of used images on the atlas and updates their UVs."""
    bl_idname = "rzm.update_atlas_layout"
    bl_label = "Update Atlas Layout"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        
        rzm.atlas_size = (0, 0)
        for img in rzm.images:
            img.uv_coords, img.uv_size = (0, 0), (0, 0)

        used_image_ids = set()
        for elem in rzm.elements:
            if elem.image_mode == 'SINGLE' and elem.image_id != -1:
                used_image_ids.add(elem.image_id)
            else:
                for cond_img in elem.conditional_images:
                    if cond_img.image_id != -1:
                        used_image_ids.add(cond_img.image_id)

        image_sizes_to_pack = {
            img.display_name: img.image_pointer.size
            for img in rzm.images
            if img.id in used_image_ids and img.image_pointer
        }

        if not image_sizes_to_pack:
            self.report({'WARNING'}, "No used images found to create a layout.")
            return {'CANCELLED'}

        (atlas_w, atlas_h), uv_data = calculate_atlas_layout(image_sizes_to_pack)

        rzm.atlas_size = (atlas_w, atlas_h)

        updated_count = 0
        for rzm_image in rzm.images:
            if rzm_image.display_name in uv_data:
                data = uv_data[rzm_image.display_name]
                rzm_image.uv_coords = data['uv_coords']
                rzm_image.uv_size = data['uv_size']
                updated_count += 1
        
        self.report({'INFO'}, f"Layout updated for {updated_count} images. Atlas size: {atlas_w}x{atlas_h}")
        
        return {'FINISHED'}

class RZM_OT_ExportAtlas(bpy.types.Operator):
    """Exports the final atlas 'icons.png' to the destination folder."""
    bl_idname = "rzm.export_atlas"
    bl_label = "Export Atlas Image"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.rzm.update_atlas_layout()
        
        rzm = context.scene.rzm
        export_path = ""
        
        if hasattr(context.scene, 'xxmi') and getattr(context.scene.xxmi, 'destination_path', ''):
            export_path = os.path.join(context.scene.xxmi.destination_path, "res")
        elif bpy.data.filepath:
            export_path = os.path.dirname(bpy.data.filepath)
        else:
            export_path = str(Path.home())
            
        if not os.path.exists(export_path):
            try:
                os.makedirs(export_path, exist_ok=True)
            except Exception as e:
                self.report({'ERROR'}, f"Could not create export directory: {e}")
                return {'CANCELLED'}

        images_to_render = {
            img.display_name: img.image_pointer
            for img in rzm.images
            if img.image_pointer and any(img.uv_size)
        }
        
        if not images_to_render:
            self.report({'WARNING'}, "No packed images to export.")
            return {'CANCELLED'}
            
        atlas_w, atlas_h = rzm.atlas_size
        uv_data = {
            img.display_name: {'uv_coords': list(img.uv_coords), 'uv_size': list(img.uv_size)}
            for img in rzm.images if any(img.uv_size)
        }

        atlas_pixels = create_atlas_pixels(images_to_render, atlas_w, atlas_h, uv_data)

        if atlas_pixels.size > 0:
            temp_image = bpy.data.images.new("RZ_Atlas_Export_Temp", width=atlas_w, height=atlas_h, alpha=True)
            temp_image.pixels = atlas_pixels
            
            final_filepath = os.path.join(export_path, "icons.png")
            temp_image.filepath_raw = final_filepath
            temp_image.file_format = 'PNG'
            temp_image.save()
            
            bpy.data.images.remove(temp_image)
            self.report({'INFO'}, f"Atlas exported to {final_filepath}")
        else:
            self.report({'ERROR'}, "Failed to generate atlas pixels.")
            return {'CANCELLED'}

        return {'FINISHED'}

class RZM_OT_AddImage(bpy.types.Operator):
    """Adds an image to the project library and packs it."""
    bl_idname = "rzm.add_image"
    bl_label = "Add Image to Library"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.png;*.jpg;*.jpeg;*.tga;*.bmp", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        rzm_images = context.scene.rzm.images
        display_name = Path(self.filepath).stem
        
        try:
            bl_image = bpy.data.images.load(self.filepath)
            bl_image.pack()
        except Exception as e:
            self.report({'ERROR'}, f"Could not load image: {e}")
            return {'CANCELLED'}

        new_id = get_next_image_id(rzm_images)
        new_rzm_image = rzm_images.add()
        
        new_rzm_image.id = new_id
        new_rzm_image.display_name = display_name
        new_rzm_image.image_pointer = bl_image
        new_rzm_image.source_type = 'CUSTOM'
        
        context.scene.rzm_active_image_index = len(rzm_images) - 1
        self.report({'INFO'}, f"Image '{display_name}' added with ID {new_rzm_image.id}.")
        
        
        return {'FINISHED'}

class RZM_OT_RemoveImage(bpy.types.Operator):
    """Removes an image from the project library."""
    bl_idname = "rzm.remove_image"
    bl_label = "Remove Image from Library"
    bl_options = {'REGISTER', 'UNDO'}

    image_id_to_remove: bpy.props.IntProperty(name="Image ID to Remove", default=-1)

    @classmethod
    def poll(cls, context):
        return len(context.scene.rzm.images) > 0

    def execute(self, context):
        rzm = context.scene.rzm
        index_to_remove = -1
        image_id = getattr(self, 'image_id_to_remove', -1)

        if image_id != -1:
            for i, img in enumerate(rzm.images):
                if img.id == image_id:
                    index_to_remove = i
                    break
        else:
            if context.scene.rzm_active_image_index < len(rzm.images):
                 index_to_remove = context.scene.rzm_active_image_index

        if index_to_remove != -1:
            rzm_image_to_remove = rzm.images[index_to_remove]
            bl_image_to_remove = rzm_image_to_remove.image_pointer
            
            rzm.images.remove(index_to_remove)
            
            if bl_image_to_remove and bl_image_to_remove.users == 0:
                bpy.data.images.remove(bl_image_to_remove)
            
            active_idx = context.scene.rzm_active_image_index
            if active_idx >= index_to_remove and active_idx > 0:
                context.scene.rzm_active_image_index = active_idx - 1
                
            
            
            # Redraw UI
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        for region in area.regions:
                            if region.type == 'UI':
                                region.tag_redraw()
        else:
            self.report({'WARNING'}, "Image to remove not found.")
            return {'CANCELLED'}

        return {'FINISHED'}

classes_to_register = [
    RZM_OT_LoadBaseIcons,
    RZM_OT_UpdateAtlasLayout,
    RZM_OT_ExportAtlas,
    RZM_OT_AddImage,
    RZM_OT_RemoveImage,
]
