# RZMenu/operators/image_ops.py
import bpy
import os
import json
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

                if ext not in ['.png', '.jpg', '.jpeg', '.dds', '.tga', '.bmp', '.svg', '.gif', '.mp4', '.webm', '.avi', '.mov', '.mkv']:
                    continue
                
                print(f"[IconsDebug] Detected File: {filename}")

                # [OMITTED ID PARSING LOGIC - KEEP AS IS]
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

                # If no prefix, we still load it!
                if parsed_id == -1:
                    if any(img.display_name == display_name for img in rzm_images if img.source_type == 'BASE'):
                        continue
                    
                    from ..core.utils import get_next_image_id
                    parsed_id = get_next_image_id(rzm_images)

                if parsed_id in existing_base_ids:
                    continue
                
                try:
                    filepath = os.path.join(assets_dir, filename)
                    
                    new_item = rzm_images.add()
                    new_item.id = parsed_id
                    new_item.display_name = display_name
                    new_item.source_type = 'BASE' if ext != '.svg' else 'VECTOR'
                    
                    if ext == '.svg':
                        # For SVG, we generate a preview just like Add Image does
                        from ..core.svg_loader import render_svg_to_pixels
                        from ..core.animated_loader import frames_to_blender_images
                        
                        res = 512
                        pixels = render_svg_to_pixels(filepath, res, res)
                        if pixels is not None:
                            bl_preview_list = frames_to_blender_images([{'pixels': pixels, 'size': (res, res)}], display_name + "_svg_preview")
                            bl_image = bl_preview_list[0]
                            bl_image.pack()
                            new_item.image_pointer = bl_image
                        
                        new_item.anim_source_path = filepath
                    else:
                        bl_image = bpy.data.images.load(filepath)
                        bl_image.pack()
                        new_item.image_pointer = bl_image
                    
                    loaded_count += 1
                    existing_base_ids.add(parsed_id)
                    print(f"[IconsDebug] Successfully loaded: {filename} as ID {parsed_id}")
                except Exception as e:
                    print(f"[IconsDebug] Error loading icon {filename}: {e}")

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

        # --- ЧЕСТНЫЙ ПОИСК ИСПОЛЬЗУЕМЫХ ID И КОНФИГУРАЦИЙ ---
        used_image_ids = set()
        # svg_render_configs Key: (img_id, scale, off_x, off_y, color_key)
        # Value: {'element_ids': set(element_ids), 'config_key': str, ...}
        svg_render_configs = {} 

        # 0. Clear existing variations before processing
        for img in rzm.images:
            img.svg_variations.clear()
        
        print(f"[RZM] Updating atlas layout. Elements: {len(rzm.elements)}, Images: {len(rzm.images)}")

        for elem in rzm.elements:
            # We check all potential SVG sources for this element
            sources = [
                ('MAIN', elem.image_id),
                ('HOVER', elem.hover_image_id),
            ]
            if hasattr(elem, 'extramap_image_id'):
                sources.append(('EXTRA', elem.extramap_image_id))
            
            for cond_img in elem.conditional_images:
                sources.append(('COND', cond_img.image_id))
            
            for source_tag, img_id in sources:
                if img_id == -1: continue
                
                img = next((i for i in rzm.images if i.id == img_id), None)
                if not img: continue
                
                if img.source_type == 'VECTOR':
                    # SVGs are tracked strictly by Element ID grouping + Resolution
                    res_w, res_h = elem.size
                    render_w = int(min(res_w, 1024))
                    render_h = int(min(res_h, 1024))
                    
                    scale = round(elem.svg_scale, 2)
                    # Convert normalized offset to pixels to match svg_loader and viewport logic
                    off_x_px = round(elem.svg_offset[0] * render_w, 2)
                    off_y_px = round(elem.svg_offset[1] * render_h, 2)
                    
                    color_key = "ORIG"
                    if not img.svg_preserve_color:
                        if elem.color[3] > 0.01:
                            r, g, b = [int(elem.color[i] * 255) for i in range(3)]
                            color_key = f"{r:02x}{g:02x}{b:02x}"
                    
                    # Unified config_key (Param-aware)
                    config_key = f"SVG_{img_id}_{render_w}x{render_h}_{scale}_{off_x_px}_{off_y_px}_{color_key}"
                    
                    # For grouping in the image library, we must decide if we group across different source tags.
                    # Usually, if visual parameters are same, they can share the atlas spot.
                    # BUT for Element ID mapping, we need to know WHICH elements use WHICH variation.
                    
                    if config_key not in svg_render_configs:
                        print(f"  [DEBUG] New Variation Config: {config_key} (Color: {color_key})")
                        svg_render_configs[config_key] = {
                            'element_ids': set(),
                            'img_id': img_id,
                            'res': (render_w, render_h),
                            'scale': scale,
                            'offset': (off_x_px, off_y_px),
                            'color_key': color_key,
                            'config_key': config_key
                        }
                    svg_render_configs[config_key]['element_ids'].add(elem.id)
                    print(f"    - Adding element {elem.id} to {config_key}")


                else:
                    used_image_ids.add(img_id)

        # Собираем размеры для упаковки.
        image_sizes_to_pack = {}
        
        from ..core.animated_loader import load_animated_advanced

        for img in rzm.images:
            # Check if this image is used as a standard image anywhere
            if img.id in used_image_ids:
                if img.source_type == 'ANIMATED':
                    if not img.anim_source_path or not os.path.exists(img.anim_source_path):
                        continue
                    
                    try:
                        unique_frames, sequence = load_animated_advanced(
                            img.anim_source_path,
                            preset=img.anim_export_preset,
                            start_frame=img.anim_start_frame,
                            end_frame=img.anim_end_frame,
                            max_source_frames=img.anim_max_frames
                        )
                        
                        img.anim_frames.clear()
                        img.anim_sequence.clear()
                        
                        for f in unique_frames:
                            it = img.anim_frames.add()
                            it.w, it.h = f['size']
                        
                        last_idx = -1
                        for seq_item in sequence:
                            it = img.anim_sequence.add()
                            it.frame_index = seq_item['idx']
                            it.duration = seq_item['duration']
                            it.is_unique = (seq_item['idx'] != last_idx)
                            last_idx = seq_item['idx']

                        img.anim_frame_count = len(unique_frames)
                        img.anim_total_duration = sum(s['duration'] for s in sequence)

                        for n, f in enumerate(unique_frames):
                            frame_key = f"{img.display_name}_anim_{n:04d}"
                            image_sizes_to_pack[frame_key] = f['size']
                    except Exception as e:
                        print(f"[RZM] Animation error: {e}")
                        continue
                elif img.source_type == 'VECTOR':
                    pass # Handled by svg_render_configs
                elif img.image_pointer:
                    w, h = img.image_pointer.size
                    if w > 0 and h > 0:
                        image_sizes_to_pack[img.display_name] = (w, h)
        
        # Add Unique SVGs to packing list
        for var_tuple, cfg in svg_render_configs.items():
            base_w, base_h = cfg['res']
            # We don't multiply by scale here because svg_scale should not reduce resolution, only the vector content.
            # We pack at full element resolution.
            render_w = int(min(base_w, 1024))
            render_h = int(min(base_h, 1024))
            image_sizes_to_pack[cfg['config_key']] = (render_w, render_h)

        if not image_sizes_to_pack:
            self.report({'WARNING'}, "No used images found to create a layout.")
            return {'CANCELLED'}

        print(f"[RZM] Packing {len(image_sizes_to_pack)} items into atlas...")
        (atlas_w, atlas_h), uv_data = calculate_atlas_layout(image_sizes_to_pack)

        rzm.atlas_size = (atlas_w, atlas_h)

        # Обновляем UV данные стандартных изображений
        updated_count = 0
        for rzm_image in rzm.images:
            if rzm_image.source_type == 'ANIMATED' and rzm_image.id in used_image_ids:
                for n in range(rzm_image.anim_frame_count):
                    frame_key = f"{rzm_image.display_name}_anim_{n:04d}"
                    if frame_key in uv_data:
                        coords = uv_data[frame_key]['uv_coords']
                        size = uv_data[frame_key]['uv_size']
                        rzm_image.anim_frames[n].x = coords[0]
                        rzm_image.anim_frames[n].y = coords[1]
                        rzm_image.anim_frames[n].w = size[0]
                        rzm_image.anim_frames[n].h = size[1]
                
                if rzm_image.anim_frames:
                    rzm_image.uv_coords = (rzm_image.anim_frames[0].x, rzm_image.anim_frames[0].y)
                    rzm_image.uv_size = (rzm_image.anim_frames[0].w, rzm_image.anim_frames[0].h)
                updated_count += 1

            elif rzm_image.display_name in uv_data:
                data = uv_data[rzm_image.display_name]
                rzm_image.uv_coords = data['uv_coords']
                rzm_image.uv_size = data['uv_size']
                updated_count += 1
        
        # Обновляем UV данные для SVG вариаций
        print(f"[RZM] Found {len(svg_render_configs)} SVG variations.")
        for var_tuple, cfg in svg_render_configs.items():
            config_key = cfg['config_key']
            if config_key in uv_data:
                data = uv_data[config_key]
                img_id = cfg['img_id']
                
                # We need to find the correct image object in scene
                for rzm_image in rzm.images:
                    if rzm_image.id == img_id:
                        var = rzm_image.svg_variations.add()
                        var.element_ids_str = ",".join(map(str, sorted(list(cfg['element_ids']))))
                        var.uv_coords = data['uv_coords']
                        var.uv_size = data['uv_size']
                        
                        # Save variation parameters for persistence
                        var.scale = cfg['scale']
                        var.offset_x = cfg['offset'][0]
                        var.offset_y = cfg['offset'][1]
                        var.color_key = cfg['color_key']
                        var.config_key = cfg['config_key']
                        
                        print(f"  > Linked variation {config_key} for ImageID {img_id} to elements: {var.element_ids_str}")

                
                # Backwards compat for element viewport
                for elem_id in cfg['element_ids']:
                    elem = next((e for e in rzm.elements if e.id == elem_id), None)
                    if elem:
                        elem.uv_coords = data['uv_coords']
                        elem.uv_size = data['uv_size']

                updated_count += 1

        self.report({'INFO'}, f"Layout updated for {updated_count} groups. Atlas size: {atlas_w}x{atlas_h}")
        rzm.export_settings.atlas_is_dirty = False
        return {'FINISHED'}

class RZM_OT_ExportAtlas(bpy.types.Operator):
    """Exports the final atlas 'icons.png'"""
    bl_idname = "rzm.export_atlas"
    bl_label = "Export Atlas Image"
    bl_options = {'REGISTER'}

    def execute(self, context):
        from ..utils.export_timing import measure

        rzm = context.scene.rzm
        export_settings = rzm.export_settings
        
        if export_settings.atlas_is_dirty:
            with measure("atlas.update_layout"):
                bpy.ops.rzm.update_atlas_layout()
        else:
            print("[RZM] Atlas is not dirty, skipping layout update.")
        
        # --- ЛОГИКА ОПРЕДЕЛЕНИЯ КОРНЕВОЙ ПАПКИ ---
        from .export_manager import get_target_path
        root_path = get_target_path(context)
        
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

        # --- СБОР ИСПОЛЬЗУЕМЫХ ID И КОНФИГУРАЦИЙ (КАК В UPDATE LAYOUT) ---
        used_image_ids = set()
        svg_render_configs = {} # Key: unique_svg_key, Value: list of (element, image_id)
        
        for elem in rzm.elements:
            sources = [
                ('MAIN', elem.image_id),
                ('HOVER', elem.hover_image_id),
            ]
            if hasattr(elem, 'extramap_image_id'):
                sources.append(('EXTRA', elem.extramap_image_id))
            
            for cond_img in elem.conditional_images:
                sources.append(('COND', cond_img.image_id))
            
            for source_tag, img_id in sources:
                if img_id == -1: continue
                
                img = next((i for i in rzm.images if i.id == img_id), None)
                if not img: continue
                
                if img.source_type == 'VECTOR':
                    res_w, res_h = elem.size
                    render_w = int(min(res_w, 1024))
                    render_h = int(min(res_h, 1024))
                    
                    scale = round(elem.svg_scale, 2)
                    off_x_px = round(elem.svg_offset[0] * render_w, 2)
                    off_y_px = round(elem.svg_offset[1] * render_h, 2)
                    
                    color_key = "ORIG"
                    tint_color = None
                    if not img.svg_preserve_color:
                        # Smart Tint: match viewport fallback
                        if elem.color[3] > 0.01:
                            r, g, b = [int(elem.color[i] * 255) for i in range(3)]
                            color_key = f"{r:02x}{g:02x}{b:02x}"
                            tint_color = f"#{color_key}"
                    
                    config_key = f"SVG_{img_id}_{render_w}x{render_h}_{scale}_{off_x_px}_{off_y_px}_{color_key}"
                    if config_key not in svg_render_configs:
                        svg_render_configs[config_key] = {
                            'elem': elem, 
                            'image_id': img_id,
                            'res': (render_w, render_h),
                            'scale': scale, 
                            'offset': (off_x_px, off_y_px),
                            'tint': tint_color,
                            'path': bpy.path.abspath(img.anim_source_path) if img.anim_source_path else ""
                        }
                else:
                    used_image_ids.add(img_id)

        # Собираем все изображения, которые нужно отрендерить в атлас
        from ..core.animated_loader import load_animated_advanced, frames_to_blender_images

        images_to_render = {} # Key: unique_frame_key, Value: bpy.data.Image (temporary)
        temp_bl_images = []

        for img in rzm.images:
            if img.id not in used_image_ids: continue

            if img.source_type == 'ANIMATED':
                try:
                    # Снова извлекаем на лету
                    unique_frames, _ = load_animated_advanced(
                        img.anim_source_path,
                        preset=img.anim_export_preset,
                        start_frame=img.anim_start_frame,
                        end_frame=img.anim_end_frame,
                        max_source_frames=img.anim_max_frames
                    )
                    
                    # Создаем временные Blender-картинки для рендера
                    bl_frames = frames_to_blender_images(unique_frames, f"TEMP_{img.display_name}", colorspace='Non-Color')
                    temp_bl_images.extend(bl_frames)
                    
                    for n, bl_img in enumerate(bl_frames):
                        frame_key = f"{img.display_name}_anim_{n:04d}"
                        images_to_render[frame_key] = bl_img
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to load animated image '{img.display_name}': {e}")
                    print(f"[RZM] Animated image load error for '{img.display_name}': {e}")
                    continue
            
            elif img.source_type == 'VECTOR':
                # SVG are now handled via svg_render_configs
                pass

            elif img.image_pointer and any(img.uv_size):
                images_to_render[img.display_name] = img.image_pointer
        
        # Render Unique SVGs
        from ..core.svg_loader import render_svg_to_pixels
        from ..core.animated_loader import frames_to_blender_images
        
        for config_key, cfg in svg_render_configs.items():
            res_w, res_h = cfg['res']
            render_w = int(min(res_w, 1024))
            render_h = int(min(res_h, 1024))
            if render_w <= 0 or render_h <= 0: continue
            
            pixels = render_svg_to_pixels(
                cfg['path'], render_w, render_h, 
                tint_color=cfg['tint'],
                scale=cfg['scale'],
                offset=cfg['offset']
            )
            
            if pixels is not None:
                # Direct pixel ingestion bypassing Blender temporary image overhead
                images_to_render[config_key] = pixels
        
        if not images_to_render:
            return {'CANCELLED'}
            
        atlas_w, atlas_h = rzm.atlas_size
        
        # 2. Собираем UV-данные всех элементов (включая кадры анимации)
        uv_data = {}
        for img in rzm.images:
            if img.source_type == 'ANIMATED':
                # Повторяем логику формирования ключей:
                for n, frame in enumerate(img.anim_frames):
                    frame_key = f"{img.display_name}_anim_{n:04d}"
                    uv_data[frame_key] = {
                        'uv_coords': [frame.x, frame.y],
                        'uv_size': [frame.w, frame.h]
                    }
            elif any(img.uv_size):
                uv_data[img.display_name] = {
                    'uv_coords': list(img.uv_coords),
                    'uv_size': list(img.uv_size)
                }
        
        # UV for unique SVGs (from any element in that config group)
        for config_key, cfg in svg_render_configs.items():
            elem = cfg['elem']
            uv_data[config_key] = {
                'uv_coords': list(elem.uv_coords),
                'uv_size': list(elem.uv_size)
            }

        # 3. Determine effective profiles based on game presets
        # Genshin/ZZZ/HSR -> Forced sRGB
        # Arknights -> Forced Linear
        # Others (WW, Emulator) -> Manual (Plan B)
        game_selection = rzm.game.selection
        effective_icc = export_settings.icc_profile
        effective_dds = export_settings.dds_profile
        preset_tag = ""

        if game_selection in ('GenshinImpact', 'HonkaiStarRail'):
            effective_icc = 'SRGB'
            effective_dds = 'BC7_UNORM_SRGB'
            preset_tag = " (Hoyo sRGB Preset)"
        elif game_selection == 'ArknightsEndfield':
            effective_icc = 'LINEAR'
            effective_dds = 'BC7_UNORM'
            preset_tag = " (Endfield Linear Preset)"
        elif game_selection == 'ZenlessZoneZero':
            effective_icc = 'LINEAR'
            effective_dds = 'BC7_UNORM'
            preset_tag = " (ZZZ Linear Preset)"
        else:
            effective_icc = 'LINEAR'
            effective_dds = 'BC7_UNORM'
            preset_tag = " (UKNOWN-GAME LINEAR PRESET)"

        # 4. Генерируем пиксели
        with measure("atlas.create_pixels"):
            atlas_pixels = create_atlas_pixels(
                images_to_render,
                atlas_w,
                atlas_h,
                uv_data
            )

        if atlas_pixels.size > 0:
            intended_format = export_settings.atlas_format
            exported_success = False
            final_filepath = ""

            # Attempt DDS if selected
            if intended_format == 'DDS':
                from ..core.dds_packer import pack_to_dds
                final_filepath = os.path.join(export_path, "icons.dds")
                with measure("atlas.write_dds"):
                    success, msg = pack_to_dds(atlas_pixels, atlas_w, atlas_h, final_filepath, dds_format=effective_dds)
                if success:
                    exported_success = True
                    export_settings.last_exported_format = "DDS"
                    self.report({'INFO'}, f"Atlas exported as DDS{preset_tag}: {final_filepath}")
                else:
                    self.report({'WARNING'}, f"DDS Export failed: {msg}. Falling back to PNG.")
                    intended_format = 'PNG' # Fallback
            
            # Export as PNG (either by choice or fallback)
            if intended_format == 'PNG':
                with measure("atlas.write_png"):
                    temp_image = bpy.data.images.new("RZ_Atlas_Temp", width=atlas_w, height=atlas_h, alpha=True)
                    
                    # Use Non-Color space to ensure bit-exact saving without Blender's gamma correction
                    temp_image.colorspace_settings.name = 'Non-Color'
                    
                    temp_image.pixels.foreach_set(atlas_pixels)
                    
                    final_filepath = os.path.join(export_path, "icons.png")
                    temp_image.filepath_raw = final_filepath
                    temp_image.file_format = 'PNG'
                    temp_image.save()
                    
                    bpy.data.images.remove(temp_image)
                    
                    # Inject metadata for PNG
                    inject_metadata_profile(final_filepath, profile=effective_icc)
                
                export_settings.last_exported_format = "PNG"
                exported_success = True
                self.report({'INFO'}, f"Atlas exported as PNG{preset_tag}: {final_filepath}")

            # Clean up temporary frames anyway
            for bl_img in temp_bl_images:
                try: bpy.data.images.remove(bl_img)
                except: pass
            
            try: context.view_layer.update()
            except: pass
            
            if not exported_success:
                return {'CANCELLED'}
        else:
            return {'CANCELLED'}

        return {'FINISHED'}

class RZM_OT_AddImage(bpy.types.Operator):
    """Adds an image to the project library and packs it."""
    bl_idname = "rzm.add_image"
    bl_label = "Add Image to Library"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.png;*.jpg;*.jpeg;*.dds;*.tga;*.bmp;*.svg", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        rzm = context.scene.rzm
        rzm_images = rzm.images
        filepath = bpy.path.abspath(self.filepath)
        
        if not os.path.isfile(filepath):
            self.report({'ERROR'}, f"File not found: {filepath}")
            return {'CANCELLED'}

        display_name = Path(filepath).stem
        ext = Path(filepath).suffix.lower()

        if ext == ".svg":
            # Специальная обработка для SVG
            from ..core.svg_loader import render_svg_to_pixels
            from ..core.animated_loader import frames_to_blender_images
            
            res = 512 # Default for library preview
            pixels = render_svg_to_pixels(filepath, res, res)
            
            if pixels is None:
                self.report({'ERROR'}, "Failed to render SVG preview.")
                return {'CANCELLED'}
            
            # Создаем Blender Image для превью в редакторе (используем Non-Color для точности)
            bl_preview_list = frames_to_blender_images(
                [{'pixels': pixels, 'size': (res, res)}], 
                display_name + "_svg_preview",
                colorspace='Non-Color'
            )
            bl_image = bl_preview_list[0]
            bl_image.pack()

            new_rzm_image = rzm_images.add()
            new_rzm_image.id = get_next_image_id(rzm_images)
            new_rzm_image.display_name = display_name
            new_rzm_image.source_type = 'VECTOR'
            new_rzm_image.anim_source_path = filepath
            new_rzm_image.image_pointer = bl_image
        else:
            # Обычные растровые изображения
            try:
                bl_image = bpy.data.images.load(filepath)
                bl_image.pack()
            except Exception as e:
                self.report({'ERROR'}, f"Could not load image: {e}")
                return {'CANCELLED'}

            new_rzm_image = rzm_images.add()
            new_rzm_image.id = get_next_image_id(rzm_images)
            new_rzm_image.display_name = display_name
            new_rzm_image.image_pointer = bl_image
            new_rzm_image.source_type = 'CUSTOM'
        
        context.scene.rzm_active_image_index = len(rzm_images) - 1
        self.report({'INFO'}, f"Image '{display_name}' added as {new_rzm_image.source_type}.")
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
                try: context.view_layer.update()
                except: pass
            
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

class RZM_OT_AddAnimatedImage(bpy.types.Operator):
    """Load a GIF or video file as an animated RZMenu image."""
    bl_idname = "rzm.add_animated_image"
    bl_label = "Add Animated Image"
    bl_description = "Load a GIF or video file (MP4/WebM/AVI). Frames are auto-deduplicated to save atlas space."
    bl_options = {'REGISTER', 'UNDO'}

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="Path to GIF or video file",
        subtype='FILE_PATH'
    )
    filter_glob: bpy.props.StringProperty(
        default="*.gif;*.mp4;*.webm;*.avi;*.mov;*.mkv",
        options={'HIDDEN'}
    )
    max_frames: bpy.props.IntProperty(
        name="Max Source Frames",
        description="Maximum frames to read from source before deduplication",
        default=128,
        min=1,
        max=2048
    )
    dedupe_threshold: bpy.props.FloatProperty(
        name="Dedupe Threshold",
        description="MAE threshold for frame deduplication (0=strict, 0.1=loose)",
        default=0.04,
        min=0.0,
        max=0.5
    )

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from ..core.animated_loader import load_animated_advanced, frames_to_blender_images

        rzm = context.scene.rzm
        filepath = bpy.path.abspath(self.filepath)

        if not os.path.isfile(filepath):
            self.report({'ERROR'}, f"File not found: {filepath}")
            return {'CANCELLED'}

        # --- ГИГИЕНИЧНЫЙ ИМПОРТ: грузим только превью (1-й кадр) ---
        try:
            # Читаем только 1 первый кадр для превью
            unique_frames, _ = load_animated_advanced(filepath, preset='ADAPTIVE', max_source_frames=1)
            if not unique_frames:
                raise ValueError("No frames could be extracted for preview.")
            
            bl_preview_images = frames_to_blender_images(unique_frames, Path(filepath).stem + "_preview")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to load preview: {e}")
            return {'CANCELLED'}

        base_name = Path(filepath).stem
        existing = next((img for img in rzm.images if img.display_name == base_name), None)
        if existing and existing.source_type == 'ANIMATED':
            rzm_image = existing
        else:
            rzm_image = rzm.images.add()
            rzm_image.id = get_next_image_id(rzm.images)

        rzm_image.display_name = base_name
        rzm_image.source_type = 'ANIMATED'
        rzm_image.anim_source_path = filepath
        rzm_image.anim_max_frames = self.max_frames
        
        # Сбрасываем коллекции — они заполнятся при Update Atlas Layout
        rzm_image.anim_frames.clear()
        rzm_image.anim_sequence.clear()
        
        # Привязываем image_pointer к первому кадру (для превью в редакторе)
        if bl_preview_images:
            rzm_image.image_pointer = bl_preview_images[0]
            bl_preview_images[0].pack()

        self.report({'INFO'}, f"Loaded '{base_name}' thumbnail. Run 'Update Atlas Layout' to process full animation.")
        return {'FINISHED'}


classes_to_register = [
    RZM_OT_LoadBaseIcons,
    RZM_OT_UpdateAtlasLayout,
    RZM_OT_ExportAtlas,
    RZM_OT_AddImage,
    RZM_OT_RemoveImage,
    RZM_OT_AddAnimatedImage,
]
