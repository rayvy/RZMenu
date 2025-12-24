# rz_gui_constructor/operators.py
import bpy
import string
import json
import os
import zipfile
import tempfile
from pathlib import Path
from .properties import RZMCaptureSettings
from .helpers import get_next_available_id, find_toggle_def, get_next_image_id
from .rzm_serialization import rzm_to_dict, dict_to_rzm
from .rzm_history import history_manager
from .rzm_atlas import calculate_atlas_layout, create_atlas_pixels
from . import captures

try:
    from PySide6 import QtWidgets
    from .ui.viewer import RZMViewerWindow
    from .ui.inspector import RZMInspectorWindow
    pyside_ok = True
except ImportError:
    pyside_ok = False
    QtWidgets, RZMViewerWindow, RZMInspectorWindow = None, None, None

qt_app, viewer_window, inspector_window = None, None, None

# --- Система Истории (Undo/Redo) ---
class RZM_OT_RecordHistoryState(bpy.types.Operator):
    """Внутренний оператор: делает слепок rzm и сохраняет в историю."""
    bl_idname = "rzm.record_history_state"
    bl_label = "RZM Record History"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        current_state = rzm_to_dict(context.scene.rzm)
        history_manager.push_state(current_state)
        return {'FINISHED'}

class RZM_OT_Undo(bpy.types.Operator):
    bl_idname = "rzm.undo"
    bl_label = "RZM Undo"
    
    @classmethod
    def poll(cls, context):
        return history_manager.can_undo()
        
    def execute(self, context):
        state_to_restore = history_manager.undo()
        if state_to_restore:
            dict_to_rzm(state_to_restore, context.scene.rzm)
        return {'FINISHED'}

class RZM_OT_Redo(bpy.types.Operator):
    bl_idname = "rzm.redo"
    bl_label = "RZM Redo"

    @classmethod
    def poll(cls, context):
        return history_manager.can_redo()

    def execute(self, context):
        state_to_restore = history_manager.redo()
        if state_to_restore:
            dict_to_rzm(state_to_restore, context.scene.rzm)
        return {'FINISHED'}

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
                rzm.images.clear()
                rzm.elements.clear()
                rzm.rzm_values.clear()
                rzm.toggle_definitions.clear()
                rzm.conditions.clear()
                rzm.shapes.clear()
                rzm.addons.tw_texture_configs.clear()
                rzm.addons.tw_textures.clear()
                rzm.addons.tw_resources.clear()
                rzm.addons.tw_overrides.clear()
                
                dict_to_rzm(data_to_load, rzm)
                
                lost_image_ids = set()
                assets_dir = os.path.join(os.path.dirname(__file__), 'base_icons')
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
        
        context.scene.rzm_active_element_index = 0
        context.scene.rzm_active_value_index = 0
        context.scene.rzm_active_toggle_def_index = 0
        context.scene.rzm_active_image_index = 0
        history_manager.clear()
        bpy.ops.rzm.record_history_state()
        self.report({'INFO'}, "RZM scene has been reset.")
        return {'FINISHED'}

class RZM_OT_CaptureImage(bpy.types.Operator):
    bl_idname = "rzm.capture_image"
    bl_label = "Capture Image"
    bl_description = "Renders the viewport and adds it as a 'Captured' image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.rzm_capture_settings
        
        # Передаем False для force_framing, чтобы уважать ручные настройки
        rendered_image = captures.execute_capture(context, settings, force_framing=False)

        if not rendered_image:
            self.report({'ERROR'}, "Capture failed. Check system console for details.")
            return {'CANCELLED'}

        # ... (остальная логика оператора по созданию/перезаписи RZMenuImage без изменений) ...
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
                    except (TypeError, ValueError): pass
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

        original_settings = {k: getattr(scene.rzm_capture_settings, k) for k in scene.rzm_capture_settings.bl_rna.properties.keys() if k != 'rna_type'}
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
                
                # Теперь передаем True для force_framing
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
                try: setattr(scene.rzm_capture_settings, key, value)
                except: pass
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selected:
                obj.select_set(True)
            context.view_layer.objects.active = original_active

        self.report({'INFO'}, f"Auto-Capture finished. Created {captured_count} icons.")
        if captured_count > 0:
            bpy.ops.rzm.record_history_state()
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    for region in area.regions:
                        if region.type == 'UI':
                            region.tag_redraw()
        return {'FINISHED'}

class RZM_OT_LoadBaseIcons(bpy.types.Operator):
    """Сканирует папку 'base_icons' и загружает стандартные изображения."""
    bl_idname = "rzm.load_base_icons"
    bl_label = "Load Base Icons"
    bl_description = "Loads standard images from the addon's 'base_icons' folder"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # Путь к папке аддона -> base_icons
        addon_dir = os.path.dirname(__file__)
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

            # НОВАЯ ЛОГИКА: Парсим ID из имени файла
            if base_name.startswith('9') and len(base_name) >= 4 and base_name[:4].isdigit():
                parsed_id = int(base_name[:4])
                # Если есть подчеркивание, используем текст после него как имя
                if '_' in base_name:
                    display_name = base_name.split('_', 1)[1]
                else:
                    display_name = "" # Или можно оставить ID как имя

            if parsed_id != -1:
                if parsed_id in existing_base_ids:
                    continue # Пропускаем уже загруженные иконки
                
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
                    print(f"DEBUG BASE ICONS: Loaded '{filename}' as BASE with parsed ID {parsed_id}")
                except Exception as e:
                    print(f"WARNING: Failed to load base asset '{filename}': {e}")
            else:
                print(f"DEBUG BASE ICONS: Skipping '{filename}' (does not match '9xxx_name' pattern).")

        self.report({'INFO'}, f"Loaded {loaded_count} new base icons.")
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_UpdateAtlasLayout(bpy.types.Operator):
    """
    (Быстро) Рассчитывает расположение используемых изображений на атласе
    и обновляет их UV-координаты и ОБЩИЙ РАЗМЕР АТЛАСА в сцене.
    """
    bl_idname = "rzm.update_atlas_layout"
    bl_label = "Update Atlas Layout"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rzm = context.scene.rzm
        print("\n--- DEBUG UPDATE LAYOUT: Operator Started ---")

        # 1. Сбросить старые UV-данные и размер атласа
        rzm.atlas_size = (0, 0)
        for img in rzm.images:
            img.uv_coords, img.uv_size = (0, 0), (0, 0)

        # 2. Собрать словарь размеров
        used_image_ids = set()
        for elem in rzm.elements:
            if elem.image_mode == 'SINGLE' and elem.image_id != -1:
                used_image_ids.add(elem.image_id)
            else:
                for cond_img in elem.conditional_images:
                    if cond_img.image_id != -1:
                        used_image_ids.add(cond_img.image_id)

        image_sizes_to_pack = {}
        for rzm_image in rzm.images:
            if rzm_image.id in used_image_ids and rzm_image.image_pointer:
                image_sizes_to_pack[rzm_image.display_name] = rzm_image.image_pointer.size

        if not image_sizes_to_pack:
            self.report({'WARNING'}, "No used images found to create a layout.")
            return {'CANCELLED'}

        # 3. Вызвать быструю функцию расчета, ПОЛУЧАЯ РАЗМЕР АТЛАСА
        (atlas_w, atlas_h), uv_data = calculate_atlas_layout(image_sizes_to_pack)

        # 4. СОХРАНИТЬ РАЗМЕР АТЛАСА В СВОЙСТВО СЦЕНЫ
        rzm.atlas_size = (atlas_w, atlas_h)
        print(f"DEBUG UPDATE LAYOUT: Stored atlas size in scene: {rzm.atlas_size[:]}" )

        # 5. Обновить UV-данные в Blender
        updated_count = 0
        for rzm_image in rzm.images:
            if rzm_image.display_name in uv_data:
                data = uv_data[rzm_image.display_name]
                rzm_image.uv_coords = data['uv_coords']
                rzm_image.uv_size = data['uv_size']
                updated_count += 1
        
        self.report({'INFO'}, f"Layout updated for {updated_count} images. Atlas size: {atlas_w}x{atlas_h}")
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}


class RZM_OT_ExportAtlas(bpy.types.Operator):
    """
    (Медленно) Обновляет расположение изображений и экспортирует итоговый
    атлас 'icons.png' в приоритетную папку.
    """
    bl_idname = "rzm.export_atlas"
    bl_label = "Export Atlas Image"
    bl_options = {'REGISTER'}

    def execute(self, context):
        print("\n--- DEBUG EXPORT ATLAS: Operator Started ---")
        
        # 1. Сначала всегда обновляем layout, как и было запрошено
        bpy.ops.rzm.update_atlas_layout()
        
        rzm = context.scene.rzm

        # 2. Определяем путь для экспорта по правилам
        export_path = ""
        # Правило 1: xxmi.destination_path
        if hasattr(context.scene, 'xxmi') and hasattr(context.scene.xxmi, 'destination_path') and context.scene.xxmi.destination_path:
            export_path = os.path.join(context.scene.xxmi.destination_path, "res")
            print(f"DEBUG EXPORT: Found export path via XXMI addon: {export_path}")
        # Правило 2: Папка .blend файла
        elif bpy.data.filepath:
            export_path = os.path.dirname(bpy.data.filepath)
            print(f"DEBUG EXPORT: Using .blend file directory: {export_path}")
        # Правило 3: Домашняя директория пользователя
        else:
            export_path = str(Path.home())
            print(f"DEBUG EXPORT: Fallback to user home directory: {export_path}")
            
        if not os.path.exists(export_path):
            try:
                os.makedirs(export_path, exist_ok=True)
            except Exception as e:
                self.report({'ERROR'}, f"Could not create export directory: {e}")
                return {'CANCELLED'}

        # 3. Собираем изображения, у которых теперь есть UV-данные
        images_to_render = {}
        for rzm_image in rzm.images:
            if rzm_image.image_pointer and any(rzm_image.uv_size):
                images_to_render[rzm_image.display_name] = rzm_image.image_pointer
        
        if not images_to_render:
            self.report({'WARNING'}, "No packed images to export.")
            return {'CANCELLED'}
            
        # 4. Рассчитываем итоговый размер атласа на основе готовых UV
        max_w = max(img.uv_coords[0] + img.uv_size[0] for img in rzm.images if any(img.uv_size))
        max_h = max(img.uv_coords[1] + img.uv_size[1] for img in rzm.images if any(img.uv_size))
        atlas_w = (max_w + 3) & ~3
        atlas_h = (max_h + 3) & ~3
        
        # 5. Собираем UV данные для медленной функции
        uv_data = {img.display_name: {'uv_coords': list(img.uv_coords), 'uv_size': list(img.uv_size)} for img in rzm.images if any(img.uv_size)}

        # 6. Вызываем медленную функцию генерации пикселей
        atlas_pixels = create_atlas_pixels(images_to_render, atlas_w, atlas_h, uv_data)

        # 7. Сохраняем файл
        if atlas_pixels.size > 0:
            temp_image = bpy.data.images.new("RZ_Atlas_Export_Temp", width=atlas_w, height=atlas_h, alpha=True)
            temp_image.pixels = atlas_pixels
            
            final_filepath = os.path.join(export_path, "icons.png")
            temp_image.filepath_raw = final_filepath
            temp_image.file_format = 'PNG'
            temp_image.save()
            
            bpy.data.images.remove(temp_image)
            self.report({'INFO'}, f"Atlas exported to {final_filepath}")
            print(f"--- DEBUG EXPORT ATLAS: Successfully saved to {final_filepath} ---")
        else:
            self.report({'ERROR'}, "Failed to generate atlas pixels.")
            return {'CANCELLED'}

        return {'FINISHED'}

class RZM_OT_AddImage(bpy.types.Operator):
    """Добавляет изображение в библиотеку проекта и упаковывает его в .blend файл."""
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
            self.report({'ERROR'}, f"Could not load image: {e}"); return {'CANCELLED'}

        # ИСПРАВЛЕНО: Исправлена логика генерации ID для предотвращения дубликатов
        # 1. Сначала вычисляем ID на основе ТЕКУЩЕГО состояния коллекции
        new_id = get_next_image_id(rzm_images)
        
        # 2. Потом добавляем новый элемент
        new_rzm_image = rzm_images.add()
        
        # 3. Присваиваем ему уже вычисленный ID и остальные свойства
        new_rzm_image.id = new_id
        new_rzm_image.display_name = display_name
        new_rzm_image.image_pointer = bl_image
        new_rzm_image.source_type = 'CUSTOM'
        
        context.scene.rzm_active_image_index = len(rzm_images) - 1
        print(f"DEBUG ADD IMG: Added '{display_name}', assigned ID: {new_rzm_image.id}")
        self.report({'INFO'}, f"Image '{display_name}' added with ID {new_rzm_image.id}.")
        
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_RemoveImage(bpy.types.Operator):
    """Удаляет изображение из библиотеки проекта и из .blend файла."""
    bl_idname = "rzm.remove_image"
    bl_label = "Remove Image from Library"
    bl_options = {'REGISTER', 'UNDO'}

    image_id_to_remove: bpy.props.IntProperty(name="Image ID to Remove", default=-1)

    @classmethod
    def poll(cls, context):
        return len(context.scene.rzm.images) > 0

    # --- ЗАМЕНИТЕ ВЕСЬ МЕТОД EXECUTE НА ЭТОТ ---
    def execute(self, context):
        rzm = context.scene.rzm
        index_to_remove = -1

        # ИСПРАВЛЕНО: Безопасно получаем ID, чтобы избежать AttributeError
        # getattr(object, attribute, default_value)
        image_id = getattr(self, 'image_id_to_remove', -1)

        # Новая логика: ищем по ID, если он был передан
        if image_id != -1:
            for i, img in enumerate(rzm.images):
                if img.id == image_id:
                    index_to_remove = i
                    break
        # Старая логика: если ID не передан, используем активный индекс
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
                
            bpy.ops.rzm.record_history_state()
            
            # Обновляем UI, чтобы превью исчезло
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

class RZM_OT_LaunchViewer(bpy.types.Operator):
    bl_idname = "rzm.launch_viewer"; bl_label = "Open Viewer"
    @classmethod
    def poll(cls, context): return pyside_ok
    def execute(self, context):
        global qt_app, viewer_window
        qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        if viewer_window: viewer_window.load_from_blender()
        else: viewer_window = RZMViewerWindow(context)
        viewer_window.show(); viewer_window.activateWindow()
        return {'FINISHED'}

class RZM_OT_LaunchInspector(bpy.types.Operator):
    bl_idname = "rzm.launch_inspector"; bl_label = "Open Inspector"
    @classmethod
    def poll(cls, context): return pyside_ok
    def execute(self, context):
        global qt_app, inspector_window
        qt_app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        if inspector_window: inspector_window.load_from_blender()
        else: inspector_window = RZMInspectorWindow(context)
        inspector_window.show(); inspector_window.activateWindow()
        return {'FINISHED'}

class RZM_OT_AddElement(bpy.types.Operator):
    bl_idname = "rzm.add_element"; bl_label = "Add UI Element"
    def execute(self, context):
        rzm = context.scene.rzm
        elements = rzm.elements
        active_idx = context.scene.rzm_active_element_index
        
        new_element = elements.add()
        new_id = get_next_available_id(elements)
        new_element.id = new_id
        new_element.elem_class = rzm.element_to_add_class
        new_element.element_name = f"{new_element.elem_class.capitalize()}{new_id}"
        # Гарантия: всегда будут coords и size
        if not new_element.position or len(new_element.position) < 2:
            new_element.position = (0, 0)
        if not new_element.size or len(new_element.size) < 2:
            new_element.size = (0, 0)
        
        if 0 <= active_idx < len(elements):
            parent_element = elements[active_idx]
            new_element.parent_id = parent_element.id
        else:
            new_element.parent_id = -1
            
        if new_element.elem_class == 'GRID_CONTAINER':
            new_element.grid_min_cells = (1, 1)
            new_element.grid_max_cells = (5, 5)
            new_element.grid_cell_size = 64
        
        return {'FINISHED'}

class RZM_OT_RemoveElement(bpy.types.Operator):
    bl_idname = "rzm.remove_element"; bl_label = "Remove UI Element"; bl_options = {'REGISTER', 'UNDO'}
    
    # ИСПРАВЛЕНО: Добавлен poll метод
    @classmethod
    def poll(cls, context):
        idx = context.scene.rzm_active_element_index
        return 0 <= idx < len(context.scene.rzm.elements)

    def execute(self, context):
        elements = context.scene.rzm.elements; index = context.scene.rzm_active_element_index
        if index < len(elements):
            elements.remove(index)
            if index > 0: context.scene.rzm_active_element_index = index - 1
        return {'FINISHED'}

class RZM_OT_DuplicateElement(bpy.types.Operator):
    """Создает дубликат активного элемента с небольшим смещением."""
    bl_idname = "rzm.duplicate_element"
    bl_label = "Duplicate UI Element"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        idx = context.scene.rzm_active_element_index
        return 0 <= idx < len(context.scene.rzm.elements)

    def execute(self, context):
        rzm = context.scene.rzm
        elements = rzm.elements
        active_idx = context.scene.rzm_active_element_index
        
        source_elem = elements[active_idx]
        new_elem = elements.add()
        
        for prop in source_elem.bl_rna.properties:
            if prop.identifier == 'id' or prop.is_readonly:
                continue
            try:
                setattr(new_elem, prop.identifier, getattr(source_elem, prop.identifier))
            except:
                pass 

        for sub_item in source_elem.fx:
            new_sub = new_elem.fx.add(); new_sub.value = sub_item.value
        for sub_item in source_elem.fn:
            new_sub = new_elem.fn.add(); new_sub.function_name = sub_item.function_name
        for sub_item in source_elem.properties:
            new_sub = new_elem.properties.add()
            new_sub.key = sub_item.key; new_sub.value_type = sub_item.value_type
            new_sub.string_value = sub_item.string_value; new_sub.int_value = sub_item.int_value
            new_sub.float_value = sub_item.float_value

        new_elem.id = get_next_available_id(elements)
        new_elem.element_name = f"{source_elem.element_name}_Copy"
        
        new_pos = list(source_elem.position)
        new_pos[0] += 25
        new_elem.position = new_pos
        
        return {'FINISHED'}

class RZM_OT_DeselectElement(bpy.types.Operator):
    """Снимает выделение с активного элемента в списке."""
    bl_idname = "rzm.deselect_element"
    bl_label = "Deselect Element"
    bl_options = {'REGISTER'}

    # ИСПРАВЛЕНО: Добавлен poll метод
    @classmethod
    def poll(cls, context):
        return context.scene.rzm_active_element_index != -1

    def execute(self, context):
        context.scene.rzm_active_element_index = -1
        return {'FINISHED'}

class RZM_OT_MoveElementUp(bpy.types.Operator):
    """Меняет ID активного элемента с элементом выше."""
    bl_idname = "rzm.move_element_up"
    bl_label = "Move Element Up"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.scene.rzm_active_element_index > 0

    def execute(self, context):
        scene = context.scene
        elements = scene.rzm.elements
        idx = scene.rzm_active_element_index
        
        elem_a = elements[idx]; elem_b = elements[idx - 1] 
        id_a, id_b = elem_a.id, elem_b.id
        
        elem_a.id, elem_b.id = id_b, id_a
        
        for elem in elements:
            if elem.parent_id == id_a: elem.parent_id = id_b
            elif elem.parent_id == id_b: elem.parent_id = id_a
        
        elements.move(idx, idx - 1)
        scene.rzm_active_element_index = idx - 1
        
        return {'FINISHED'}

class RZM_OT_MoveElementDown(bpy.types.Operator):
    """Меняет ID активного элемента с элементом ниже."""
    bl_idname = "rzm.move_element_down"
    bl_label = "Move Element Down"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        idx = context.scene.rzm_active_element_index
        return 0 <= idx < len(context.scene.rzm.elements) - 1

    def execute(self, context):
        scene = context.scene
        elements = scene.rzm.elements
        idx = scene.rzm_active_element_index
        
        elem_a = elements[idx]; elem_b = elements[idx + 1]
        id_a, id_b = elem_a.id, elem_b.id
        
        elem_a.id, elem_b.id = id_b, id_a
        
        for elem in elements:
            if elem.parent_id == id_a: elem.parent_id = id_b
            elif elem.parent_id == id_b: elem.parent_id = id_a
                
        elements.move(idx, idx + 1)
        scene.rzm_active_element_index = idx + 1
        
        return {'FINISHED'}

class RZM_OT_ListAction(bpy.types.Operator):
    bl_idname = "rzm.list_action"; bl_label = "RZMenu List Action"
    action: bpy.props.EnumProperty(items=(('ADD', 'Add', ''), ('REMOVE', 'Remove', '')))
    collection: bpy.props.StringProperty()
    def execute(self, context):
        elem = context.scene.rzm.elements[context.scene.rzm_active_element_index]
        prop_collection = getattr(elem, self.collection)
        if self.action == 'ADD': prop_collection.add()
        elif self.action == 'REMOVE' and len(prop_collection) > 0:
            prop_collection.remove(len(prop_collection) - 1)
        return {'FINISHED'}
    
class RZM_OT_AddConditionalImage(bpy.types.Operator):
    """Добавляет элемент в список условных изображений."""
    bl_idname = "rzm.add_conditional_image"
    bl_label = "Add Conditional Image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_idx = context.scene.rzm_active_element_index
        elements = context.scene.rzm.elements
        if 0 <= active_idx < len(elements):
            elements[active_idx].conditional_images.add()
        return {'FINISHED'}

class RZM_OT_RemoveConditionalImage(bpy.types.Operator):
    """Удаляет элемент из списка условных изображений."""
    bl_idname = "rzm.remove_conditional_image"
    bl_label = "Remove Conditional Image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_idx = context.scene.rzm_active_element_index
        elements = context.scene.rzm.elements
        if 0 <= active_idx < len(elements):
            cond_images = elements[active_idx].conditional_images
            if len(cond_images) > 0:
                cond_images.remove(len(cond_images) - 1)
        return {'FINISHED'}

class RZM_OT_AddValue(bpy.types.Operator):
    bl_idname = "rzm.add_value"; bl_label = "Add Value"
    def execute(self, context):
        values = context.scene.rzm.rzm_values
        values.add().value_name = f"$NewValue_{len(values)}"
        context.scene.rzm_active_value_index = len(values) - 1
        return {'FINISHED'}

class RZM_OT_RemoveValue(bpy.types.Operator):
    bl_idname = "rzm.remove_value"; bl_label = "Remove Value"
    def execute(self, context):
        values = context.scene.rzm.rzm_values
        index = context.scene.rzm_active_value_index
        if index < len(values):
            values.remove(index)
            if index > 0: context.scene.rzm_active_value_index = index - 1
        return {'FINISHED'}

class RZM_OT_AddProjectToggle(bpy.types.Operator):
    bl_idname = "rzm.add_project_toggle"; bl_label = "Add Project Toggle"; bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        toggle_defs = context.scene.rzm.toggle_definitions
        existing_names = {t.toggle_name for t in toggle_defs}
        for char in string.ascii_uppercase:
            name = f"Toggle{char}"
            if name not in existing_names:
                new_toggle = toggle_defs.add(); new_toggle.toggle_name = name
                context.scene.rzm_active_toggle_def_index = len(toggle_defs) - 1
                break
        return {'FINISHED'}

class RZM_OT_RemoveProjectToggle(bpy.types.Operator):
    bl_idname = "rzm.remove_project_toggle"; bl_label = "Remove Project Toggle"; bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        toggle_defs = context.scene.rzm.toggle_definitions; index = context.scene.rzm_active_toggle_def_index
        if index < len(toggle_defs):
            toggle_defs.remove(index)
            if index > 0: context.scene.rzm_active_toggle_def_index = index - 1
        return {'FINISHED'}
    
class RZM_OT_AssignObjectToggle(bpy.types.Operator):
    bl_idname = "rzm.assign_object_toggle"; bl_label = "Assign Toggle"; bl_options = {'REGISTER', 'UNDO'}
    toggle_name: bpy.props.StringProperty() 
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj: self.report({'WARNING'}, "No active object selected"); return {'CANCELLED'}
        
        toggle_def = find_toggle_def(context, self.toggle_name)
        if not toggle_def: return {'CANCELLED'}
        
        prop_name = f"rzm.Toggle.{self.toggle_name}"
        target_obj[prop_name] = [0] * toggle_def.toggle_length
        return {'FINISHED'}


class RZM_OT_RemoveObjectToggle(bpy.types.Operator):
    bl_idname = "rzm.remove_object_toggle"; bl_label = "Remove Assigned Toggle"; bl_options = {'REGISTER', 'UNDO'}
    toggle_name: bpy.props.StringProperty() 
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj: return {'CANCELLED'}
        
        if self.toggle_name in target_obj:
            del target_obj[self.toggle_name]
        return {'FINISHED'}

class RZM_OT_ToggleObjectBit(bpy.types.Operator):
    bl_idname = "rzm.toggle_object_bit"; bl_label = "Toggle Bit"; bl_options = {'REGISTER', 'UNDO'}
    toggle_name: bpy.props.StringProperty() 
    bit_index: bpy.props.IntProperty()
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj or self.toggle_name not in target_obj: return {'CANCELLED'}
        
        arr = target_obj[self.toggle_name]
        new_arr = list(arr)
        new_arr[self.bit_index] = 1 - new_arr[self.bit_index]
        target_obj[self.toggle_name] = new_arr
        return {'FINISHED'}
    
class RZM_OT_SetValueLink(bpy.types.Operator):
    """Добавляет значение в список value_link активного UI элемента."""
    bl_idname = "rzm.set_value_link"
    bl_label = "Add Value Link"
    bl_options = {'REGISTER', 'UNDO'}

    link_target: bpy.props.StringProperty()

    def execute(self, context):
        active_idx = context.scene.rzm_active_element_index
        elements = context.scene.rzm.elements
        if 0 <= active_idx < len(elements):
            elem = elements[active_idx]
            new_link = elem.value_link.add()
            new_link.value_name = self.link_target  # ИЗМЕНЕНО
        else:
            self.report({'WARNING'}, "No active UI element selected.")
            return {'CANCELLED'}
        return {'FINISHED'}

class RZM_OT_RemoveValueLink(bpy.types.Operator):
    """Удаляет элемент из списка value_link."""
    bl_idname = "rzm.remove_value_link"
    bl_label = "Remove Value Link"
    bl_options = {'REGISTER', 'UNDO'}
    
    index_to_remove: bpy.props.IntProperty()

    def execute(self, context):
        active_idx = context.scene.rzm_active_element_index
        elements = context.scene.rzm.elements
        if 0 <= active_idx < len(elements):
            links = elements[active_idx].value_link  # ИЗМЕНЕНО
            if 0 <= self.index_to_remove < len(links):
                links.remove(self.index_to_remove)
        return {'FINISHED'}

# --- ОПЕРАТОРЫ ДЛЯ TEXWORKS ---
class RZM_OT_SetTwFormat(bpy.types.Operator):
    """Внутренний оператор для установки формата DXGI из меню."""
    bl_idname = "rzm.set_tw_format"
    bl_label = "Set TexWorks Format"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    format_to_set: bpy.props.StringProperty()
    
    def execute(self, context):
        # Пытаемся получить индекс из временной переменной
        atlas_index = getattr(context.window_manager, 'rzm_context_atlas_index', -1)
        
        if atlas_index != -1:
            try:
                # Находим нужный конфиг по индексу и меняем формат
                configs = context.scene.rzm.addons.tw_texture_configs
                target_config = configs[atlas_index]
                target_config.tw_atlas_settings.tw_format = self.format_to_set
            except (IndexError, AttributeError) as e:
                print(f"ERROR: Could not set TW format. Index: {atlas_index}, Error: {e}")
            finally:
                # Обязательно удаляем временную переменную, чтобы не было мусора
                del context.window_manager.rzm_context_atlas_index
        else:
            self.report({'WARNING'}, "Could not determine context for setting format.")

        return {'FINISHED'}

class RZM_OT_AddTwResource(bpy.types.Operator):
    bl_idname = "rzm.add_tw_resource"
    bl_label = "Add TexWorks Resource"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_resources.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwResource(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_resource"
    bl_label = "Remove TexWorks Resource"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_resources
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
        return {'FINISHED'}

class RZM_OT_AddTwOverride(bpy.types.Operator):
    bl_idname = "rzm.add_tw_override"
    bl_label = "Add TexWorks Override"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_overrides.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwOverride(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_override"
    bl_label = "Remove TexWorks Override"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_overrides
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
        return {'FINISHED'}

class RZM_OT_AddTwConfig(bpy.types.Operator):
    bl_idname = "rzm.add_tw_config"
    bl_label = "Add TexWorks Config"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_texture_configs.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwConfig(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_config"
    bl_label = "Remove TexWorks Config"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_texture_configs
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
        return {'FINISHED'}

class RZM_OT_AddTwTexture(bpy.types.Operator):
    bl_idname = "rzm.add_tw_texture"
    bl_label = "Add TexWorks Texture"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_textures.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwTexture(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_texture"
    bl_label = "Remove TexWorks Texture"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_textures
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
        return {'FINISHED'}

class RZM_OT_AddTwAlternative(bpy.types.Operator):
    bl_idname = "rzm.add_tw_alternative"
    bl_label = "Add TexWorks Alternative"
    bl_options = {'REGISTER', 'UNDO'}
    texture_index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.addons.tw_textures[self.texture_index].tw_alternatives.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwAlternative(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_alternative"
    bl_label = "Remove TexWorks Alternative"
    bl_options = {'REGISTER', 'UNDO'}
    texture_index: bpy.props.IntProperty()
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_textures[self.texture_index].tw_alternatives
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
        return {'FINISHED'}

# --- ОПЕРАТОРЫ ДЛЯ SPECIAL VARIABLES ---
class RZM_OT_AddCondition(bpy.types.Operator):
    bl_idname = "rzm.add_condition"
    bl_label = "Add Condition"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.conditions.add()
        return {'FINISHED'}

class RZM_OT_RemoveCondition(bpy.types.Operator):
    bl_idname = "rzm.remove_condition"
    bl_label = "Remove Condition"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.conditions
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
        return {'FINISHED'}

class RZM_OT_AddShape(bpy.types.Operator):
    bl_idname = "rzm.add_shape"
    bl_label = "Add Shape"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.shapes.add()
        return {'FINISHED'}

class RZM_OT_RemoveShape(bpy.types.Operator):
    bl_idname = "rzm.remove_shape"
    bl_label = "Remove Shape"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.shapes
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
        return {'FINISHED'}

class RZM_OT_AddShapeKey(bpy.types.Operator):
    bl_idname = "rzm.add_shape_key"
    bl_label = "Add Shape Key"
    bl_options = {'REGISTER', 'UNDO'}
    shape_index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.shapes[self.shape_index].shape_keys.add()
        return {'FINISHED'}

class RZM_OT_RemoveShapeKey(bpy.types.Operator):
    bl_idname = "rzm.remove_shape_key"
    bl_label = "Remove Shape Key"
    bl_options = {'REGISTER', 'UNDO'}
    shape_index: bpy.props.IntProperty()
    def execute(self, context):
        coll = context.scene.rzm.shapes[self.shape_index].shape_keys
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
        return {'FINISHED'}


classes_to_register = [
    RZM_OT_RecordHistoryState, RZM_OT_Undo, RZM_OT_Redo,
    RZM_OT_SaveTemplate, RZM_OT_LoadTemplate, RZM_OT_ResetScene,
    RZM_OT_LaunchViewer, RZM_OT_LaunchInspector,
    RZM_OT_CaptureImage, RZM_OT_AutoCapture, RZM_OT_LoadBaseIcons,
    RZM_OT_UpdateAtlasLayout, RZM_OT_ExportAtlas, RZM_OT_AddImage, RZM_OT_RemoveImage,
    RZM_OT_AddElement, RZM_OT_RemoveElement, RZM_OT_DuplicateElement, RZM_OT_DeselectElement,
    RZM_OT_MoveElementUp, RZM_OT_MoveElementDown,
    RZM_OT_AddConditionalImage, RZM_OT_RemoveConditionalImage,
    RZM_OT_ListAction,
    RZM_OT_SetValueLink, RZM_OT_RemoveValueLink,
    RZM_OT_AddValue, RZM_OT_RemoveValue,
    RZM_OT_AddProjectToggle, RZM_OT_RemoveProjectToggle,
    RZM_OT_AssignObjectToggle, RZM_OT_RemoveObjectToggle, RZM_OT_ToggleObjectBit,
    # Новые и обновленные операторы
    RZM_OT_SetTwFormat,
    RZM_OT_AddTwResource, RZM_OT_RemoveTwResource,
    RZM_OT_AddTwOverride, RZM_OT_RemoveTwOverride,
    RZM_OT_AddTwConfig, RZM_OT_RemoveTwConfig,
    RZM_OT_AddTwTexture, RZM_OT_RemoveTwTexture,
    RZM_OT_AddTwAlternative, RZM_OT_RemoveTwAlternative,
    RZM_OT_AddCondition, RZM_OT_RemoveCondition,
    RZM_OT_AddShape, RZM_OT_RemoveShape,
    RZM_OT_AddShapeKey, RZM_OT_RemoveShapeKey,
]
def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)