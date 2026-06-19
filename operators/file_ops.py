# RZMenu/operators/file_ops.py
import bpy
import json
import os
import zipfile
import tempfile
import shutil
from pathlib import Path

# FIX IMPORTS: Linking to the new core modules
from ..core.serialization import RZTemplateEngine, rzm_to_dict, dict_to_rzm

# --- Helper для надежного сохранения изображения ---
def robust_save_image(bl_image, save_path):
    """
    Пытается сохранить изображение любым доступным способом.
    Приоритет:
    1. Если упаковано -> сохраняем сырые байты (самый надежный способ).
    2. Если есть путь на диске -> копируем файл.
    3. Если есть данные в памяти -> используем image.save().
    """
    try:
        # Способ 1: Изображение упаковано в blend-файл
        if bl_image.packed_file:
            with open(save_path, 'wb') as f:
                f.write(bl_image.packed_file.data)
            return True

        # Способ 2: Стандартное сохранение (Raw bytes)
        # save() надежнее save_render(), так как не зависит от Color Management
        if bl_image.has_data:
            try:
                # Временно меняем filepath, чтобы сохранить куда нам надо, затем возвращаем
                old_filepath = bl_image.filepath
                try:
                    bl_image.filepath_raw = save_path
                    bl_image.save()
                finally:
                    bl_image.filepath_raw = old_filepath
                return True
            except:
                pass # Если не вышло, пробуем save_render

            # Fallback: Save Render
            bl_image.save_render(save_path)
            return True

        # Способ 3: Копирование исходного файла, если он существует
        source_path = bpy.path.abspath(bl_image.filepath)
        if source_path and os.path.exists(source_path) and os.path.isfile(source_path):
            shutil.copy2(source_path, save_path)
            return True
            
    except Exception as e:
        print(f"[RZM] Image Save Error ({bl_image.name}): {e}")
    
    return False

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
                images_saved = 0
                with tempfile.TemporaryDirectory() as tmpdir:
                    print(f"[RZM] Processing {len(context.scene.rzm.images)} images...")
                    
                    for img in context.scene.rzm.images:
                        # Сохраняем и CUSTOM и CAPTURED, если есть поинтер
                        if img.source_type in {'CUSTOM', 'CAPTURED'}:
                            if not img.image_pointer:
                                continue
                            
                            bl_image = img.image_pointer
                            
                            # Определяем формат
                            fmt = bl_image.file_format or 'PNG'
                            ext = fmt.lower().replace('jpeg', 'jpg')
                            if ext not in {'png', 'jpg', 'tga', 'bmp', 'tiff'}: ext = 'png'
                            
                            # Имя файла внутри архива: ID_Name.ext
                            # Очищаем имя от недопустимых символов для файловой системы
                            safe_name = "".join([c for c in img.display_name if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
                            if not safe_name: safe_name = "image"
                            
                            filename = f"{img.id}_{safe_name}.{ext}"
                            save_path = os.path.join(tmpdir, filename)
                            
                            if robust_save_image(bl_image, save_path):
                                if os.path.getsize(save_path) > 0:
                                    zf.write(save_path, arcname=f'images/{filename}')
                                    images_saved += 1
                                else:
                                    print(f"[RZM] Warning: Saved file {filename} is empty.")
                            else:
                                print(f"[RZM] Warning: Could not save data for '{img.display_name}'")
                
                print(f"[RZM] Total images saved to archive: {images_saved}")

            self.report({'INFO'}, f"RZM Scene saved to {self.filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to save .rzm file: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
        return {'FINISHED'}


class RZM_OT_LoadTemplate(bpy.types.Operator):
    """Загружает структуру RZM из .rzm (zip) архива."""
    bl_idname = "rzm.load_template"
    bl_label = "Load RZM Scene"
    bl_options = {'REGISTER', 'UNDO'} 
    
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
                
                # 2. Pre-load images
                loaded_images_map = {} # KEY = ID (int) -> Value = bpy.types.Image
                loaded_images_by_name = {} # KEY = CleanName -> Value = bpy.types.Image (Fallback)

                # Проверяем обе возможные папки (старая и новая структура)
                possible_folders = ['images', 'assets']
                found_images_folder = False
                
                for folder_name in possible_folders:
                    images_path = os.path.join(tmpdir, folder_name)
                    if not os.path.exists(images_path):
                        continue
                        
                    found_images_folder = True
                    image_files = os.listdir(images_path)
                    print(f"[RZM] Found {len(image_files)} files in '{folder_name}'...")
                    
                    for filename in image_files:
                        if filename.startswith('.'): continue
                        
                        try:
                            full_path = os.path.join(images_path, filename)
                            
                            # Попытка распарсить ID
                            img_id = -1
                            # Вариант 1: "123_Name.png"
                            parts = filename.split('_', 1)
                            if len(parts) >= 2 and parts[0].isdigit():
                                img_id = int(parts[0])
                            # Вариант 2: "asset_123.png" (из partial export)
                            elif filename.startswith("asset_"):
                                name_part = filename.split('.')[0] # убрать расширение
                                id_part = name_part.replace("asset_", "")
                                if id_part.isdigit():
                                    img_id = int(id_part)
                            
                            # Загрузка
                            bl_image = bpy.data.images.load(full_path, check_existing=False)
                            # Важно: Сразу пакуем, чтобы данные остались в памяти после удаления tmp
                            bl_image.pack() 
                            
                            if img_id != -1:
                                loaded_images_map[img_id] = bl_image
                            
                            # Сохраняем также по имени (без расширения и ID) для фоллбэка
                            clean_name = os.path.splitext(filename)[0]
                            # Если имя вида "100_MyImage", сохраним "MyImage"
                            if '_' in clean_name and clean_name.split('_')[0].isdigit():
                                clean_name = clean_name.split('_', 1)[1]
                            
                            loaded_images_by_name[clean_name] = bl_image
                            loaded_images_by_name[filename] = bl_image # и полное имя тоже
                                
                        except Exception as e:
                            print(f"[RZM] Error loading image {filename}: {e}")

                if not found_images_folder:
                    print("[RZM] Info: No 'images' or 'assets' folder found in archive.")

                # 3. Load JSON Data
                json_path = os.path.join(tmpdir, 'scene.json')
                # Fallback для partial templates, которые могут называться template_data.json
                if not os.path.exists(json_path):
                    json_path = os.path.join(tmpdir, 'template_data.json')

                if not os.path.exists(json_path):
                    self.report({'ERROR'}, "Invalid RZM file: json data missing")
                    return {'CANCELLED'}

                with open(json_path, 'r', encoding='utf-8') as f:
                    data_to_load = json.load(f)

                # --- 3.5.0 SMART MIGRATION ---
                def version_to_tuple(v_str):
                    try: return tuple(map(int, str(v_str).split('.')))
                    except: return (0, 0, 0)

                file_version = version_to_tuple(data_to_load.get("version", "0.0.0"))
                target_version = (3, 5, 0)

                if file_version < target_version:
                    print(f"[RZM] Legacy version {data_to_load.get('version')} detected. Migrating to 3.5.0...")
                    
                    addons_data = data_to_load.get("addons", {})
                    
                    # 1. Migrate Resources
                    if "tw_resources" in addons_data and not data_to_load.get("tw_resources"):
                        new_res = []
                        for old_res in addons_data["tw_resources"]:
                            new_res.append({
                                "name": old_res.get("tex_name", "Unnamed"),
                                "type": old_res.get("tex_resource_type", "ON_DISK"),
                                "path": old_res.get("tex_path", ""),
                                "resolution": [4096, 4096],
                                "format": 'DXGI_FORMAT_R8G8B8A8_TYPELESS'
                            })
                        data_to_load["tw_resources"] = new_res
                    
                    # 2. Migrate Overrides
                    if "tw_overrides" in addons_data and not data_to_load.get("tw_overrides"):
                        new_over = []
                        for old_over in addons_data["tw_overrides"]:
                            new_over.append({
                                "name": old_over.get("tex_name", "Override"),
                                "hash": old_over.get("tex_hash", ""),
                                "resource_name": old_over.get("tex_resource_name", "")
                            })
                        data_to_load["tw_overrides"] = new_over
                        
                    # 3. Create Migration Block
                    if "tw_textures" in addons_data and not data_to_load.get("tw_blocks"):
                        migration_block = {
                            "name": "Legacy Migration",
                            "resource_name": "", # Можно оставить пустым
                            "components": []
                        }
                        for old_tex in addons_data["tw_textures"]:
                            comp = {
                                "name": old_tex.get("tw_name", "Component"),
                                "resource_name": old_tex.get("tw_base_resource_name", ""),
                                "rect": [*old_tex.get("tw_position", [0, 0]), *old_tex.get("tw_size", [1024, 1024])],
                                "slots": []
                            }
                            # Создаем базовый слот для диффуза
                            comp["slots"].append({
                                "name": "Diffuse (Migrated)",
                                "active": True,
                                "material_index": 0,
                                "image_id": -1,
                                "rect": [0, 0, 1024, 1024]
                            })
                            migration_block["components"].append(comp)
                        
                        data_to_load["tw_blocks"] = [migration_block]
                    
                    # Cleanup old addon keys to avoid dict_to_rzm errors or clutter
                    for k in ["tw_resources", "tw_overrides", "tw_texture_configs", "tw_textures"]:
                        if k in addons_data: del addons_data[k]
                
                rzm = context.scene.rzm
                
                # 4. Clear existing RZM data
                collections_to_clear = [
                    rzm.elements, rzm.rzm_values, rzm.toggle_definitions, rzm.images,
                    rzm.conditions, rzm.shapes, rzm.dependency_statuses,
                    rzm.tw_resources, rzm.tw_overrides,
                    rzm.tw_materials, rzm.tw_blocks,
                    rzm.tw_mc_files, rzm.tw_mc_mask_files, rzm.tw_mc_skipped
                ]
                for coll in collections_to_clear:
                    coll.clear()
                
                # 5. Populate Data
                dict_to_rzm(data_to_load, rzm)
                
                # 6. Relink Images
                lost_image_ids = set()
                addon_dir = Path(__file__).parent.parent
                base_icons_dir = addon_dir / "base_icons"

                for rzm_image in rzm.images:
                    if rzm_image.source_type in {'CUSTOM', 'CAPTURED'}:
                        found = False
                        
                        # Стратегия 1: Поиск по ID
                        if rzm_image.id in loaded_images_map:
                            rzm_image.image_pointer = loaded_images_map[rzm_image.id]
                            found = True
                        
                        # Стратегия 2: Поиск по Display Name (Fallback)
                        if not found and rzm_image.display_name:
                            # Пробуем прямое совпадение
                            if rzm_image.display_name in loaded_images_by_name:
                                rzm_image.image_pointer = loaded_images_by_name[rzm_image.display_name]
                                found = True
                                print(f"[RZM] Relinked by NAME: {rzm_image.display_name}")
                            # Пробуем очищенное имя (если в display_name было расширение)
                            elif os.path.splitext(rzm_image.display_name)[0] in loaded_images_by_name:
                                name_key = os.path.splitext(rzm_image.display_name)[0]
                                rzm_image.image_pointer = loaded_images_by_name[name_key]
                                found = True
                                print(f"[RZM] Relinked by CLEAN NAME: {name_key}")

                        if not found:
                            # Проверка: вдруг это asset_ID.png, который не попал в мапу
                            # Например rzm_image.display_name = "asset_3.png"
                            if rzm_image.display_name in loaded_images_by_name:
                                rzm_image.image_pointer = loaded_images_by_name[rzm_image.display_name]
                                found = True
                        
                        if not found:
                            print(f"[RZM] Failed to relink ID {rzm_image.id} ({rzm_image.display_name})")
                            lost_image_ids.add(rzm_image.id)
                    
                    elif rzm_image.source_type == 'BASE':
                        print(f"[RZM] Relinking BASE image: {rzm_image.display_name} (ID: {rzm_image.id})")
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

            self.report({'INFO'}, f"RZM Scene loaded. {len(lost_image_ids)} images missed.")

        except Exception as e:
            self.report({'ERROR'}, f"Failed to load: {e}")
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
        
        # 1. Clear Global Collections in RZM
        collections_to_clear = [
            rzm.elements, rzm.rzm_values, rzm.toggle_definitions, rzm.images, 
            rzm.conditions, rzm.shapes, rzm.dependency_statuses,
            rzm.tw_resources, rzm.tw_overrides,
            rzm.tw_materials, rzm.tw_blocks,
            rzm.tw_mc_files, rzm.tw_mc_mask_files, rzm.tw_mc_skipped,
            rzm.fonts,      # NEW
            rzm.run_links,  # NEW
            rzm.keybinds    # NEW
        ]
        for coll in collections_to_clear:
            coll.clear()
        
        # 2. Clear Nested Collections
        rzm.meta_data.credits_list.clear() # NEW
        rzm.meta_data.features_list.clear() # NEW
        rzm.export_settings.custom_scripts.clear() # NEW
        
        # 3. Clear tiers on ALL objects in the file
        # We search through bpy.data.objects instead of context.scene.objects
        # to ensure even hidden/unassigned objects are cleaned if they have RZM data.
        for obj in bpy.data.objects:
            if hasattr(obj, "rzm_tier_list"):
                obj.rzm_tier_list.clear()

        # 4. Reset All Active Indices on Scene
        context.scene.rzm_active_element_index = 0
        context.scene.rzm_active_value_index = 0
        context.scene.rzm_active_toggle_def_index = 0
        context.scene.rzm_active_image_index = 0
        
        # New indices from 3.5.0+
        if hasattr(context.scene, "rzm_active_shape_index"):
            context.scene.rzm_active_shape_index = 0
        if hasattr(context.scene, "rzm_active_shape_key_index"):
            context.scene.rzm_active_shape_key_index = 0
        if hasattr(context.scene, "rzm_active_run_link_index"):
            context.scene.rzm_active_run_link_index = 0
        if hasattr(context.scene, "rzm_active_keybind_index"):
            context.scene.rzm_active_keybind_index = 0
            
        # Reset nested indices
        rzm.meta_data.credits_list_index = 0
        rzm.meta_data.features_list_index = 0
        rzm.export_settings.custom_scripts_index = 0
        
        # Reset capture helper
        context.scene.rzm_capture_overwrite_id = -1
        
        self.report({'INFO'}, "RZM scene has been completely reset.")
        return {'FINISHED'}
    
class RZM_OT_ExportPartialTemplate(bpy.types.Operator):
    """Экспортирует ВЫБРАННЫЙ элемент (и его детей) в .rzmt шаблон."""
    bl_idname = "rzm.export_partial_template"
    bl_label = "Export Template (.rzmt)"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.rzmt", options={'HIDDEN'})
    
    def invoke(self, context, event):
        # Предлагаем имя файла по имени активного элемента
        rzm = context.scene.rzm
        idx = context.scene.rzm_active_element_index
        
        if 0 <= idx < len(rzm.elements):
            active_el = rzm.elements[idx]
            self.filepath = f"{active_el.element_name or 'template'}.rzmt"
        else:
            self.filepath = "template.rzmt"
            
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        rzm = context.scene.rzm
        idx = context.scene.rzm_active_element_index
        
        # Определяем, что экспортировать.
        # Берем активный элемент как корень.
        if 0 <= idx < len(rzm.elements):
            root_id = rzm.elements[idx].id
            root_ids = [root_id] # Передаем списком
            
            # Инициализируем движок
            engine = RZTemplateEngine(context)
            
            # Запуск (имя файла, имя шаблона берем из файла)
            if engine.export_template(root_ids, self.filepath, meta_name=os.path.basename(self.filepath)):
                self.report({'INFO'}, f"Template exported: {self.filepath}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, "Export failed (Check console)")
                return {'CANCELLED'}
        else:
            self.report({'WARNING'}, "No active RZM element selected to export.")
            return {'CANCELLED'}


class RZM_OT_ImportPartialTemplate(bpy.types.Operator):
    """Импортирует .rzmt шаблон, добавляя его в текущую сцену."""
    bl_idname = "rzm.import_partial_template"
    bl_label = "Import Template (.rzmt)"
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.rzmt", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        engine = RZTemplateEngine(context)
        
        # Куда вставлять? 
        # Если выбран элемент -> делаем его родителем для импортированного
        # Если ничего не выбрано -> кидаем в корень (-1)
        rzm = context.scene.rzm
        idx = context.scene.rzm_active_element_index
        parent_id = -1
        
        # Можно раскомментировать, если хочешь чтобы импорт падал ВНУТРЬ выбранного элемента
        # if 0 <= idx < len(rzm.elements):
        #     parent_id = rzm.elements[idx].id
            
        # Оффсет: просто немного сдвинем, чтобы не накладывалось 1 в 1, или можно 0,0
        # В идеале можно передавать координаты курсора, но пока хардкод для теста
        offset = (20, 20) 

        if engine.import_template(self.filepath, position_offset=offset, parent_id=parent_id):
            self.report({'INFO'}, "Template imported successfully.")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Import failed.")
            return {'CANCELLED'}

class RZM_OT_ExportConfig(bpy.types.Operator):
    """Экспортирует конфигурационный блок в формате .rzmc"""
    bl_idname = "rzm.export_config"
    bl_label = "Export Configuration (.rzmc)"
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.rzmc", options={'HIDDEN'})
    
    config_type: bpy.props.EnumProperty(
        name="Configuration Type",
        items=[
            ('BLEND_RESIZE', "Blend Resize", ""),
            ('SHAPE_KEY_CONFIG', "Shape Key Config", ""),
        ]
    )
    
    def invoke(self, context, event):
        self.filepath = f"config_{self.config_type.lower()}.rzmc"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        
    def execute(self, context):
        engine = RZTemplateEngine(context)
        
        target_prop = None
        if self.config_type == 'BLEND_RESIZE':
            target_prop = context.scene.rzm.addons.blend_resize
            
        if self.config_type != 'SHAPE_KEY_CONFIG' and not target_prop:
            self.report({'ERROR'}, f"Target property for {self.config_type} not found.")
            return {'CANCELLED'}
            
        if engine.export_config(self.filepath, self.config_type, target_prop):
            self.report({'INFO'}, f"Config {self.config_type} exported successfully.")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Config export failed.")
            return {'CANCELLED'}

class RZM_OT_ImportConfig(bpy.types.Operator):
    """Импортирует конфигурационный блок из формата .rzmc"""
    bl_idname = "rzm.import_config"
    bl_label = "Import Configuration (.rzmc)"
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.rzmc", options={'HIDDEN'})
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
        
    def execute(self, context):
        engine = RZTemplateEngine(context)
        
        if engine.import_config(self.filepath):
            self.report({'INFO'}, "Configuration imported successfully.")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Configuration import failed or was invalid type.")
            return {'CANCELLED'}


class RZM_OT_ExportShapeKeyConfig(bpy.types.Operator):
    """Экспортирует конфигурацию ShapeKey в .rzmc (настройки, без объектных ссылок)"""
    bl_idname = "rzm.export_shape_key_config"
    bl_label = "Export Shape Key Config (.rzmc)"
    bl_description = "Save current Shape Key configurations to a .rzmc file"
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.rzmc", options={'HIDDEN'})
    filename_ext = ".rzmc"
    
    def invoke(self, context, event):
        self.filepath = "shape_key_config.rzmc"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        rzm = context.scene.rzm
        if not rzm.shape_configs:
            self.report({'WARNING'}, "No Shape Key configurations to export.")
            return {'CANCELLED'}
        
        engine = RZTemplateEngine(context)
        if engine.export_config(self.filepath, 'SHAPE_KEY_CONFIG'):
            self.report({'INFO'}, f"Shape Key Config exported: {len(rzm.shape_configs)} entries.")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Shape Key Config export failed.")
            return {'CANCELLED'}


class RZM_OT_ImportShapeKeyConfig(bpy.types.Operator):
    """Импортирует конфигурацию ShapeKey из .rzmc (merge — обновляет только существующие)"""
    bl_idname = "rzm.import_shape_key_config"
    bl_label = "Import Shape Key Config (.rzmc)"
    bl_description = "Load Shape Key configurations from a .rzmc file (updates existing keys only)"
    bl_options = {'REGISTER', 'UNDO'}
    
    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.rzmc", options={'HIDDEN'})
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        engine = RZTemplateEngine(context)
        if engine.import_config(self.filepath):
            self.report({'INFO'}, "Shape Key Config imported (existing keys updated).")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Import failed: invalid .rzmc or no matching shape keys.")
            return {'CANCELLED'}


classes_to_register = [
    RZM_OT_SaveTemplate,
    RZM_OT_LoadTemplate,
    RZM_OT_ResetScene,
    RZM_OT_ExportPartialTemplate,
    RZM_OT_ImportPartialTemplate,
    RZM_OT_ExportConfig,
    RZM_OT_ImportConfig,
    RZM_OT_ExportShapeKeyConfig,
    RZM_OT_ImportShapeKeyConfig,
]
