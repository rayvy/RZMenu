# RZMenu/operators/image_ops.py
import bpy
import os
from pathlib import Path
from ..core.utils import get_next_image_id
from ..core.atlas_algo import calculate_atlas_layout, create_atlas_pixels, inject_paintnet_metadata, inject_metadata_profile

class RZM_OT_LoadBaseIcons(bpy.types.Operator):
    """Scans the 'base_icons' folder and loads standard images."""
    bl_idname = "rzm.load_base_icons"
    bl_label = "Load Base Icons"
    bl_description = "Loads standard images from the addon's 'base_icons' folder"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        addon_name = __package__.split(".")[0] if "." in __package__ else __package__
        print(f"[IconsDebug] Addon Name: {addon_name}")
        prefs = context.preferences.addons.get(addon_name)
        if prefs:
            prefs = prefs.preferences
            print(f"[IconsDebug] Found Prefs: {prefs}")
        else:
            print(f"[IconsDebug] WARNING: Could not find addon preferences for {addon_name}")
        
        addon_dir = os.path.dirname(os.path.dirname(__file__))
        base_dir = os.path.join(addon_dir, 'base_icons')
        custom_dir = getattr(prefs, "custom_asset_library", "")
        
        print(f"[IconsDebug] Base Dir: {base_dir} (Exists: {os.path.exists(base_dir)})")
        print(f"[IconsDebug] Custom Dir: '{custom_dir}' (Exists: {os.path.exists(custom_dir) if custom_dir else 'N/A'})")
        
        scan_dirs = []
        if os.path.exists(base_dir):
            scan_dirs.append(base_dir)
        if custom_dir and os.path.isdir(custom_dir):
            scan_dirs.append(custom_dir)
            
        print(f"[IconsDebug] Final Scan Dirs: {scan_dirs}")
            
        rzm_images = context.scene.rzm.images
        existing_base_ids = {img.id for img in rzm_images if img.source_type == 'BASE'}
        
        loaded_count = 0
        for assets_dir in scan_dirs:
            print(f"[IconsDebug] --- Scanning: {assets_dir} ---")
            for filename in os.listdir(assets_dir):
                base_name, ext = os.path.splitext(filename)
                ext = ext.lower()

                if ext not in ['.png', '.jpg', '.jpeg', '.dds', '.tga', '.bmp']:
                    continue
                
                print(f"[IconsDebug] Detected File: {filename}")

                parsed_id = -1
                display_name = base_name

                # Try to extract 9xxx prefix
                if base_name.startswith('9') and len(base_name) >= 4 and base_name[:4].isdigit():
                    try:
                        parsed_id = int(base_name[:4])
                        if '_' in base_name:
                            display_name = base_name.split('_', 1)[1]
                        else:
                            display_name = ""
                    except ValueError:
                        parsed_id = -1

                # Check if it exists by ID
                if parsed_id != -1 and parsed_id in existing_base_ids:
                    print(f"[IconsDebug] Skipping '{filename}': ID {parsed_id} already loaded.")
                    continue

                # Check if it exists by Display Name
                if any(img.display_name == display_name for img in rzm_images if img.source_type == 'BASE'):
                    print(f"[IconsDebug] Skipping '{filename}': Display name already exists.")
                    continue

                # Generate a new ID if needed
                if parsed_id == -1:
                    from ..core.utils import get_next_image_id
                    parsed_id = get_next_image_id(rzm_images)
                    print(f"[IconsDebug] Auto-generated ID {parsed_id} for '{display_name}'")

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
                    existing_base_ids.add(parsed_id)
                    print(f"[IconsDebug] Successfully loaded: {filename} as ID {parsed_id}")
                except Exception as e:
                    import traceback
                    print(f"[IconsDebug] Error loading icon {filename}: {e}\n{traceback.format_exc()}")

        self.report({'INFO'}, f"Loaded {loaded_count} icons from {len(scan_dirs)} source(s).")
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
    """Exports the final atlas 'icons.png'"""
    bl_idname = "rzm.export_atlas"
    bl_label = "Export Atlas Image"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bpy.ops.rzm.update_atlas_layout()
        rzm = context.scene.rzm
        export_settings = rzm.export_settings  # Восстанавливаем доступ к настройкам
        
        # --- ЛОГИКА ОПРЕДЕЛЕНИЯ КОРНЕВОЙ ПАПКИ ---
        root_path = ""
        
        # 1. Если стоит галочка "Использовать XXMI путь"
        if export_settings.use_xxmi_path:
            if hasattr(context.scene, 'xxmi') and getattr(context.scene.xxmi, 'destination_path', ''):
                root_path = context.scene.xxmi.destination_path
                # print(f"DEBUG: Using XXMI Path: {root_path}")
            else:
                self.report({'WARNING'}, "XXMI path selected but not found. Falling back...")
        
        # 2. Если галочка снята — используем Custom Path
        else:
            if export_settings.custom_path:
                root_path = export_settings.custom_path
                # print(f"DEBUG: Using Custom Path: {root_path}")
        
        # 3. Если путь всё ещё пуст (или не найден) — берем путь текущего .blend файла
        if not root_path:
            if bpy.data.filepath:
                root_path = os.path.dirname(bpy.data.filepath)
            else:
                root_path = str(Path.home()) # Если файл даже не сохранен

        # --- НОРМАЛИЗАЦИЯ И ФИНАЛИЗАЦИЯ ---
        
        # os.path.abspath делает магию:
        # 1. Превращает "G:/Mods/FM/" (со слэшем) в "G:\Mods\FM" (без слэша)
        # 2. Исправляет прямые/обратные слэши под Windows
        # Теперь это точно ПАПКА, и dirname не нужен
        root_path = os.path.abspath(root_path)
        
        # Добавляем заветную папку /res
        export_path = os.path.join(root_path, "res")

        # Отладка для спокойствия души
        print(f"DEBUG PATH: Resolved Root='{root_path}' -> Final Export='{export_path}'")

        if not os.path.exists(export_path):
            os.makedirs(export_path, exist_ok=True)

        # ... ДАЛЕЕ ТВОЙ КОД РЕНДЕРА (без изменений) ...

        images_to_render = {
            img.display_name: img.image_pointer
            for img in rzm.images
            if img.image_pointer and any(img.uv_size)
        }
        
        if not images_to_render:
            return {'CANCELLED'}
            
        atlas_w, atlas_h = rzm.atlas_size
        uv_data = {
            img.display_name: {'uv_coords': list(img.uv_coords), 'uv_size': list(img.uv_size)}
            for img in rzm.images if any(img.uv_size)
        }

        # 1. Генерируем пиксели С УЧЕТОМ ГАММЫ (если SRGB)
        atlas_pixels = create_atlas_pixels(
            images_to_render, 
            atlas_w, 
            atlas_h, 
            uv_data, 
            profile=export_settings.icc_profile
        )

        if atlas_pixels.size > 0:
            temp_image = bpy.data.images.new("RZ_Atlas_Temp", width=atlas_w, height=atlas_h, alpha=True)
            
            temp_image.pixels.foreach_set(atlas_pixels)
            
            final_filepath = os.path.join(export_path, "icons.png")
            temp_image.filepath_raw = final_filepath
            temp_image.file_format = 'PNG'
            temp_image.save()
            
            bpy.data.images.remove(temp_image)
            
            #inject_paintnet_metadata(final_filepath)
            inject_metadata_profile(final_filepath, profile=export_settings.icc_profile)
            
            self.report({'INFO'}, f"Atlas exported: {final_filepath}")
        else:
            return {'CANCELLED'}

        return {'FINISHED'}

class RZM_OT_AddImage(bpy.types.Operator):
    """Adds an image to the project library and packs it."""
    bl_idname = "rzm.add_image"
    bl_label = "Add Image to Library"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.png;*.jpg;*.jpeg;*.dds;*.tga;*.bmp", options={'HIDDEN'})

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
