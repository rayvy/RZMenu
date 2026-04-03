# RZMenu/core/serialization.py
import bpy
import json
import os
import zipfile
import tempfile
from mathutils import Vector, Color, Euler, Quaternion

def rzm_to_dict(val):
    """
    Универсальный конвертер данных Blender в JSON-совместимые типы.
    Обрабатывает PropertyGroup, ID-properties, коллекции и математические типы.
    """
    # 1. Простые типы (уже совместимы с JSON)
    if isinstance(val, (int, float, str, bool, type(None))):
        return val
    
    # 1.1 Защита от методов и функций
    if callable(val):
        return str(val)

    # 2. Обработка PropertyGroup (зарегистрированные свойства через bpy.props)
    if isinstance(val, bpy.types.PropertyGroup):
        res = {}
        for prop_def in val.bl_rna.properties:
            key = prop_def.identifier
            if key in {'rna_type'}: continue
            
            # Пропускаем указатели на объекты данных (Mesh, Image и т.д.), 
            # но оставляем указатели на вложенные группы настроек
            if isinstance(prop_def, bpy.types.PointerProperty):
                attr = getattr(val, key)
                if not isinstance(attr, bpy.types.PropertyGroup):
                    continue
            
            res[key] = rzm_to_dict(getattr(val, key))
            
        # Дополнительно проверяем ID-properties внутри PropertyGroup (те самые "кастомные" ключи)
        if hasattr(val, "keys"):
            for k in val.keys():
                if k not in res:
                    res[k] = rzm_to_dict(val[k])
        return res

    # 3. Обработка коллекций и списков (bpy_prop_collection, IDPropertyArray, list, tuple)
    if isinstance(val, (list, tuple, bpy.types.bpy_prop_collection, bpy.types.bpy_prop_array)):
        return [rzm_to_dict(item) for item in val]

    # 4. Обработка ID-свойств (IDPropertyGroup), которые ведут себя как словари
    if hasattr(val, "keys") and hasattr(val, "items"):
        return {k: rzm_to_dict(v) for k, v in val.items()}

    # 5. Математические типы Blender (Vector, Color и т.д.)
    if isinstance(val, (Vector, Color, Euler, Quaternion)):
        return list(val)
        
    # 6. Если это массив (например, FloatVectorProperty)
    if hasattr(val, "to_list"):
        return val.to_list()

    # Если мы не знаем что это, пробуем привести к строке если это не системный объект Blender
    if hasattr(val, "bl_rna"):
        return str(val)
    return val

def dict_to_rzm(data_dict, blender_prop):
    """
    Рекурсивно применяет данные из словаря Python к свойствам объекта Blender.
    """
    if not isinstance(data_dict, dict):
        return

    for key, value in data_dict.items():
        # Если это ID-property (через квадратные скобки), а не зарегистрированное свойство
        if not hasattr(blender_prop, key) and hasattr(blender_prop, "__setitem__"):
            try:
                blender_prop[key] = value
                continue
            except: pass

        if not hasattr(blender_prop, key):
            continue

        target_prop = getattr(blender_prop, key)

        # Коллекции
        if isinstance(target_prop, bpy.types.bpy_prop_collection) and isinstance(value, list):
            target_prop.clear()
            for item_dict in value:
                new_item = target_prop.add()
                dict_to_rzm(item_dict, new_item)

        # Вложенные группы
        elif isinstance(target_prop, bpy.types.PropertyGroup) and isinstance(value, dict):
            dict_to_rzm(value, target_prop)
            
        # Простые типы
        else:
            try:
                setattr(blender_prop, key, value)
            except Exception as e:
                print(f"RZ-Constructor Warning: Could not set property '{key}'. Reason: {e}")

class RZTemplateEngine:
    def __init__(self, context):
        self.context = context
        self.scene = context.scene
        self.rzm = self.scene.rzm

    def get_element_hierarchy(self, root_ids):
        process_queue = [e for e in self.rzm.elements if e.id in root_ids]
        collected = []
        processed_ids = set()
        while process_queue:
            elem = process_queue.pop(0)
            if elem.id in processed_ids: continue
            processed_ids.add(elem.id)
            collected.append(elem)
            children = [e for e in self.rzm.elements if getattr(e, "parent_id", -1) == elem.id]
            process_queue.extend(children)
        return collected

    def export_template(self, root_ids, filepath, meta_name="Template"):
        print(f"[RZM] Exporting Template '{meta_name}' to {filepath}...")
        
        target_elements = self.get_element_hierarchy(root_ids)
        print(f"[RZM] Found {len(target_elements)} elements in hierarchy.")
        if not target_elements:
            print("[RZM] Error: No elements to export.")
            return False

        data = {
            "meta": {"version": "1.1", "name": meta_name},
            "elements": [],
            "dependencies": {"values": [], "toggles": [], "images": [], "shapes": [], "conditions": []},
            "scene_settings": {},
            "assets_map": {},
            "offset_origin": [0, 0]
        }

        # Сбор глобальных настроек rzm_
        for prop_name in dir(self.scene):
            if prop_name.startswith("rzm_") and prop_name != "rzm": # rzm отдельно как элементы
                try:
                    val = getattr(self.scene, prop_name)
                    data["scene_settings"][prop_name] = rzm_to_dict(val)
                except: continue
        
        # Сбор ID-properties сцены (динамические данные)
        for key in self.scene.keys():
            if key.startswith("rzm_"):
                data["scene_settings"][key] = rzm_to_dict(self.scene[key])

        # Координаты
        min_x = min([e.position[0] for e in target_elements])
        min_y = min([e.position[1] for e in target_elements])
        data["offset_origin"] = [min_x, min_y]

        deps_ids = {"values": set(), "toggles": set(), "images": set(), "shapes": set(), "conditions": set()}

        for elem in target_elements:
            d = rzm_to_dict(elem)
            d["_temp_original_id"] = elem.id
            data["elements"].append(d)
            
            # Scan Value Links
            if hasattr(elem, "value_link"):
                for link in elem.value_link:
                    name = link.value_name
                    if not name: continue
                    if name.startswith('@'): deps_ids["toggles"].add(name[1:])
                    elif name.startswith('#'): deps_ids["shapes"].add(name[1:])
                    elif not name.startswith('#'): deps_ids["values"].add(name.replace('$', ''))
            
            # Scan Images
            if hasattr(elem, "image_id") and elem.image_id != -1:
                deps_ids["images"].add(elem.image_id)
            if hasattr(elem, "conditional_images"):
                for ci in elem.conditional_images:
                    if ci.image_id != -1: deps_ids["images"].add(ci.image_id)
            # Hover и extramap тоже пакуются в экспорт
            if hasattr(elem, 'hover_image_id') and elem.hover_image_id != -1:
                deps_ids["images"].add(elem.hover_image_id)
            if hasattr(elem, 'extramap_image_id') and elem.extramap_image_id != -1:
                deps_ids["images"].add(elem.extramap_image_id)

        # Scan TexWorks dependencies
        for block in self.rzm.tw_blocks:
            for comp in block.components:
                # Component level: Morph link
                if comp.tex_morph_enabled and comp.tex_morph_link:
                    field = comp.tex_morph_link
                    if field.startswith('@'): deps_ids["toggles"].add(field[1:])
                    elif field.startswith('#'): deps_ids["shapes"].add(field[1:])
                    elif field.startswith('$'): deps_ids["values"].add(field[1:])
                
                for slot in comp.slots:
                    # Slot level: HSV link
                    if slot.hsv_enabled and slot.hsv_link:
                        field = slot.hsv_link
                        if field.startswith('@'): deps_ids["toggles"].add(field[1:])
                        elif field.startswith('#'): deps_ids["shapes"].add(field[1:])
                        elif field.startswith('$'): deps_ids["values"].add(field[1:])

        for name in deps_ids["values"]:
            obj = next((v for v in self.rzm.rzm_values if v.value_name == name or v.value_name == f"${name}"), None)
            if obj: data["dependencies"]["values"].append(rzm_to_dict(obj))
            
        for name in deps_ids["toggles"]:
            obj = next((t for t in self.rzm.toggle_definitions if t.toggle_name == name), None)
            if obj: data["dependencies"]["toggles"].append(rzm_to_dict(obj))

        for name in deps_ids["shapes"]:
            obj = next((s for s in self.rzm.shapes if s.shape_name == name or s.shape_name == f"#{name}"), None)
            if obj: data["dependencies"]["shapes"].append(rzm_to_dict(obj))
            
        for name in deps_ids["conditions"]:
            obj = next((c for c in self.rzm.conditions if c.condition_name == name), None)
            if obj: data["dependencies"]["conditions"].append(rzm_to_dict(obj))

        # Сохранение
        view_settings = self.scene.view_settings
        old_transform = view_settings.view_transform
        view_settings.view_transform = 'Standard'

        try:
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                with tempfile.TemporaryDirectory() as tmpdir:
                    for img_id in deps_ids["images"]:
                        rzm_img = next((img for img in self.rzm.images if img.id == img_id), None)
                        if not rzm_img: continue
                        
                        bl_image = getattr(rzm_img, "image_pointer", None) or bpy.data.images.get(rzm_img.display_name)
                        
                        # --- FIX START: Robust Image Check ---
                        if not bl_image: continue
                        
                        # Определяем формат
                        fmt = bl_image.file_format or 'PNG'
                        ext = fmt.lower().replace('jpeg', 'jpg')
                        if ext not in ['jpg', 'png', 'tga', 'bmp']: ext = 'png'
                        
                        archive_fname = f"asset_{img_id}.{ext}"
                        save_path = os.path.join(tmpdir, archive_fname)
                        
                        success = False
                        try:
                            # 1. Packed Check
                            if bl_image.packed_file:
                                with open(save_path, 'wb') as f:
                                    f.write(bl_image.packed_file.data)
                                success = True
                            # 2. Has Data Check
                            elif bl_image.has_data:
                                try:
                                    bl_image.save(filepath=save_path)
                                    success = True
                                except:
                                    bl_image.save_render(save_path)
                                    success = True
                            # 3. Filepath Check
                            elif os.path.exists(bl_image.filepath):
                                try:
                                    bl_image.reload()
                                    bl_image.save(filepath=save_path)
                                    success = True
                                except: pass
                                
                            if success and os.path.exists(save_path):
                                zf.write(save_path, arcname=f"assets/{archive_fname}")
                                data["assets_map"][str(img_id)] = archive_fname
                                # Важно: обновляем данные в JSON, чтобы ссылка на картинку была
                                img_data = rzm_to_dict(rzm_img)
                                data["dependencies"]["images"].append(img_data)
                        except Exception as e:
                            print(f"[RZM] Error saving template image {bl_image.name}: {e}")
                        # --- FIX END ---

                # Save JSON
                json_str = json.dumps(data, indent=2, ensure_ascii=False)
                zf.writestr('template_data.json', json_str)
                print(f"[RZM] template_data.json written ({len(json_str)} bytes)")

        except Exception as e:
            print(f"[RZM] Critical Export Error: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        print("[RZM] Export finished successfully.")
        return True

    def import_template(self, filepath, position_offset=(0, 0), parent_id=-1):
        if not os.path.exists(filepath): return False
        extract_dir = os.path.join(tempfile.gettempdir(), "rzm_imports")
        if not os.path.exists(extract_dir): os.makedirs(extract_dir)

        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                if 'template_data.json' not in zf.namelist(): return False
                data = json.loads(zf.read('template_data.json'))

                # Восстановление настроек сцены
                scene_settings = data.get("scene_settings", {})
                for key, value in scene_settings.items():
                    if hasattr(self.scene, key):
                        target = getattr(self.scene, key)
                        if isinstance(target, (bpy.types.PropertyGroup, dict)):
                            dict_to_rzm(value, target)
                        else:
                            try: setattr(self.scene, key, value)
                            except: pass
                    else:
                        self.scene[key] = value

                assets_map = data.get("assets_map", {})
                img_remap = {} 
                for old_id_str, fname in assets_map.items():
                    old_id = int(old_id_str)
                    arc_path = f"assets/{fname}"
                    if arc_path in zf.namelist():
                        target = os.path.join(extract_dir, fname)
                        with open(target, 'wb') as f: f.write(zf.read(arc_path))
                        new_id = self.load_image_asset(target)
                        img_remap[old_id] = new_id

                self.inject_vars(data.get("dependencies", {}))
                self.create_elements(data, img_remap, parent_id, position_offset)
            return True
        except Exception as e:
            print(f"[RZM] Import Error: {e}")
            return False

    def load_image_asset(self, filepath):
        bl_image = next((img for img in bpy.data.images if img.filepath == filepath), None)
        if not bl_image:
            try:
                bl_image = bpy.data.images.load(filepath)
                bl_image.alpha_mode = 'STRAIGHT'
            except: return -1

        for rzm_img in self.rzm.images:
            if getattr(rzm_img, "image_pointer", None) == bl_image:
                return rzm_img.id

        new_img = self.rzm.images.add()
        ids = {i.id for i in self.rzm.images}
        new_id = 1
        while new_id in ids:
            new_id += 1
            
        new_img.id = new_id
        new_img.display_name = bl_image.name
        new_img.source_type = 'CUSTOM'
        new_img.image_pointer = bl_image
        return new_id

    def inject_vars(self, deps):
        # Rayvich: Improved injection with logging for troubleshooting
        for d in deps.get("values", []):
            name = d.get("value_name")
            if not any(v.value_name == name for v in self.rzm.rzm_values):
                dict_to_rzm(d, self.rzm.rzm_values.add())
            else:
                print(f"[RZM] Skip Value Import: '{name}' already exists in scene.")
                
        for d in deps.get("toggles", []):
            name = d.get("toggle_name")
            if not any(t.toggle_name == name for t in self.rzm.toggle_definitions):
                dict_to_rzm(d, self.rzm.toggle_definitions.add())
            else:
                print(f"[RZM] Skip Toggle Import: '{name}' already exists in scene.")
                
        for d in deps.get("shapes", []):
            name = d.get("shape_name")
            if not any(s.shape_name == name for s in self.rzm.shapes):
                dict_to_rzm(d, self.rzm.shapes.add())
            else:
                print(f"[RZM] Skip Shape Import: '{name}' already exists in scene.")
                
        for d in deps.get("conditions", []):
            name = d.get("condition_name")
            if not any(c.condition_name == name for c in self.rzm.conditions):
                dict_to_rzm(d, self.rzm.conditions.add())
            else:
                print(f"[RZM] Skip Condition Import: '{name}' already exists in scene.")

    def create_elements(self, data, img_remap, root_parent_id, offset):
        """
        Смарт-импорт элементов с сохранением оригинальных ID, если они свободны.
        При конфликте находит ближайший свободный ID.
        """
        existing_ids = {e.id for e in self.rzm.elements}
        id_map = {} # KEY = Old ID (int) -> Value = New ID (int)
        elements_data = data.get("elements", [])
        
        # --- ФАЗА 1: Определение маппинга ID ---
        # Сначала резервируем те, что точно свободны
        for el in elements_data:
            old_id = el.get("_temp_original_id")
            if old_id is None: continue
            
            if old_id not in existing_ids and old_id not in id_map.values():
                id_map[old_id] = old_id
        
        # Для остальных (конфликтных) ищем замену
        next_id = 1
        for el in elements_data:
            old_id = el.get("_temp_original_id")
            if old_id is None or old_id in id_map: continue
            
            while next_id in existing_ids or next_id in id_map.values():
                next_id += 1
            
            id_map[old_id] = next_id
            next_id += 1

        # Ремаппинг ссылок на картинки в данных элементов перед созданием
        for el in elements_data:
            if "image_id" in el and el["image_id"] in img_remap:
                el["image_id"] = img_remap[el["image_id"]]
            if "conditional_images" in el:
                for ci in el["conditional_images"]:
                    if ci.get("image_id") in img_remap:
                        ci["image_id"] = img_remap[ci["image_id"]]
            # Hover и extramap: тоже ремапируем при импорте
            if "hover_image_id" in el and el["hover_image_id"] in img_remap:
                el["hover_image_id"] = img_remap[el["hover_image_id"]]
            if "extramap_image_id" in el and el.get("extramap_image_id") in img_remap:
                el["extramap_image_id"] = img_remap[el["extramap_image_id"]]

        origin = data.get("offset_origin", [0, 0])

        # --- ФАЗА 2: Создание элементов ---
        for el_data in elements_data:
            new_el = self.rzm.elements.add()
            old_temp_id = el_data.get("_temp_original_id")
            
            # Определяем ремаппированные ID
            safe_new_id = id_map.get(old_temp_id, 999) 
            
            # Ремаппинг родителя
            original_pid = el_data.get("parent_id", -1)
            safe_new_pid = id_map.get(original_pid, root_parent_id)
            
            # Заливаем данные (включая коллекции типа value_link)
            dict_to_rzm(el_data, new_el)
            
            # --- ФИКС: Принудительно устанавливаем ремаппированные ID после dict_to_rzm ---
            # dict_to_rzm перезаписывает id на тот, что был в el_data (старый).
            # Мы возвращаем правильный новый ID.
            new_el.id = safe_new_id
            new_el.parent_id = safe_new_pid
            
            # Если это корневой элемент шаблона (нет родителя в шаблоне), применяем оффсет
            if original_pid not in id_map:
                cur_x, cur_y = new_el.position
                new_el.position = (int(cur_x - origin[0] + offset[0]), int(cur_y - origin[1] + offset[1]))