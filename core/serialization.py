# RZMenu/core/serialization.py
import bpy
import json
import os
import zipfile
import tempfile
from mathutils import Vector, Color, Euler, Quaternion

def rzm_to_dict(blender_property):
    """
    ОБНОВЛЕННАЯ ВЕРСИЯ: Рекурсивно конвертирует PropertyGroup, CollectionProperty
    или любой другой тип данных Blender в JSON-совместимый словарь или список.
    """
    if isinstance(blender_property, bpy.types.PropertyGroup):
        result_dict = {}
        for prop_def in blender_property.bl_rna.properties:
            key = prop_def.identifier
            
            # ИСПРАВЛЕНИЕ: Пропускаем служебные свойства И PointerProperty
            if key in ['rna_type'] or isinstance(prop_def, bpy.types.PointerProperty):
                continue
                
            value = getattr(blender_property, key)
            result_dict[key] = rzm_to_dict(value)
        return result_dict

    elif isinstance(blender_property, bpy.types.bpy_prop_collection):
        result_list = []
        for item in blender_property:
            result_list.append(rzm_to_dict(item))
        return result_list

    elif isinstance(blender_property, bpy.types.bpy_prop_array):
        return list(blender_property)
        
    elif isinstance(blender_property, (Vector, Color, Euler, Quaternion)):
        return list(blender_property)

    else:
        return blender_property

def dict_to_rzm(data_dict, blender_prop):
    """
    ОБНОВЛЕННАЯ ВЕРСИЯ: Рекурсивно применяет данные из словаря Python (data_dict)
    к свойствам объекта Blender (blender_prop). Основано на рабочем примере.
    """
    # Итерируем по всем ключам и значениям в нашем словаре из JSON
    for key, value in data_dict.items():
        
        # Проверяем, существует ли такое свойство в объекте Blender.
        # Это делает загрузку безопасной, даже если JSON от другой версии аддона.
        if not hasattr(blender_prop, key):
            continue

        target_prop = getattr(blender_prop, key)

        # Обработка Коллекций (bpy_prop_collection)
        if isinstance(target_prop, bpy.types.bpy_prop_collection) and isinstance(value, list):
            # 1. Очищаем существующую коллекцию в Blender
            target_prop.clear()
            # 2. Итерируем по списку словарей из нашего JSON
            for item_dict in value:
                # 3. Добавляем новый, пустой элемент в коллекцию Blender
                new_item = target_prop.add()
                # 4. РЕКУРСИВНЫЙ ВЫЗОВ: заполняем этот новый элемент данными
                dict_to_rzm(item_dict, new_item)

        # Обработка вложенных PropertyGroup
        elif isinstance(target_prop, bpy.types.PropertyGroup) and isinstance(value, dict):
            # РЕКУРСИВНЫЙ ВЫЗОВ: просто "проваливаемся" глубже для заполнения
            dict_to_rzm(value, target_prop)
            
        # Обработка простых типов и векторов
        else:
            try:
                # setattr - это универсальная команда Python для установки атрибута.
                # API Blender достаточно умён, чтобы автоматически преобразовать
                # список Python (например, [1, 2, 3]) в IntVectorProperty или FloatVectorProperty.
                setattr(blender_prop, key, value)
            except Exception as e:
                # Выводим предупреждение, если какое-то свойство не удалось установить
                print(f"RZ-Constructor Warning: Could not set property '{key}'. Reason: {e}")

class RZTemplateEngine:
    def __init__(self, context):
        self.context = context
        self.scene = context.scene
        self.rzm = self.scene.rzm

    # -----------------------------------------------------------------------------
    #  EXPORT LOGIC
    # -----------------------------------------------------------------------------
    
    def get_element_hierarchy(self, root_ids):
        """Собирает элементы и всех их детей рекурсивно."""
        process_queue = [e for e in self.rzm.elements if e.id in root_ids]
        collected = []
        processed_ids = set()
        
        while process_queue:
            elem = process_queue.pop(0)
            if elem.id in processed_ids: continue
            
            processed_ids.add(elem.id)
            collected.append(elem)
            
            # Ищем детей
            children = [e for e in self.rzm.elements if getattr(e, "parent_id", -1) == elem.id]
            process_queue.extend(children)
            
        return collected

    def export_template(self, root_ids, filepath, meta_name="Template"):
        print(f"[RZM] Exporting Template '{meta_name}' to {filepath}...")
        
        # 1. Сбор данных
        target_elements = self.get_element_hierarchy(root_ids)
        if not target_elements:
            print("[RZM] Error: No elements to export.")
            return False

        # Структура JSON
        data = {
            "meta": {
                "version": "1.0",
                "name": meta_name
            },
            "elements": [],
            "dependencies": {"values": [], "toggles": [], "images": []},
            "assets_map": {}, # id -> filename
            "offset_origin": [0, 0]
        }

        # Вычисляем Offset (чтобы при импорте вставить относительно курсора/центра)
        min_x = min([e.position[0] for e in target_elements])
        min_y = min([e.position[1] for e in target_elements])
        data["offset_origin"] = [min_x, min_y]

        # Сбор зависимостей
        deps_ids = {"values": set(), "toggles": set(), "images": set()}

        for elem in target_elements:
            # Сериализуем элемент
            d = rzm_to_dict(elem)
            d["_temp_original_id"] = elem.id # Сохраняем старый ID для связей
            data["elements"].append(d)
            
            # Ищем переменные и тогглы в ссылках
            if hasattr(elem, "value_link"):
                for link in elem.value_link:
                    name = link.value_name
                    if not name: continue
                    if name.startswith('@'): deps_ids["toggles"].add(name[1:])
                    elif not name.startswith('#'): deps_ids["values"].add(name.replace('$', ''))
            
            # Ищем картинки
            if hasattr(elem, "image_id") and elem.image_id != -1:
                deps_ids["images"].add(elem.image_id)
            if hasattr(elem, "conditional_images"):
                for ci in elem.conditional_images:
                    if ci.image_id != -1: deps_ids["images"].add(ci.image_id)

        # Сериализуем зависимости
        for name in deps_ids["values"]:
            obj = next((v for v in self.rzm.rzm_values if v.value_name == name or v.value_name == f"${name}"), None)
            if obj: data["dependencies"]["values"].append(rzm_to_dict(obj))
            
        for name in deps_ids["toggles"]:
            obj = next((t for t in self.rzm.toggle_definitions if t.toggle_name == name), None)
            if obj: data["dependencies"]["toggles"].append(rzm_to_dict(obj))

        # 2. Упаковка в ZIP + FIX COLOR MANAGEMENT
        # Переключаем сцену в Standard, чтобы пиксели сохранились как есть (255->255)
        view_settings = self.scene.view_settings
        old_transform = view_settings.view_transform
        view_settings.view_transform = 'Standard'

        try:
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                with tempfile.TemporaryDirectory() as tmpdir:
                    
                    # Сохраняем картинки
                    for img_id in deps_ids["images"]:
                        rzm_img = next((img for img in self.rzm.images if img.id == img_id), None)
                        if not rzm_img: continue

                        # Берем поинтер (безопасно)
                        bl_image = getattr(rzm_img, "image_pointer", None)
                        if not bl_image: # Fallback по имени
                            bl_image = bpy.data.images.get(rzm_img.display_name)
                        
                        if not bl_image or not bl_image.has_data: continue

                        # Формат файла
                        fmt = bl_image.file_format or 'PNG'
                        ext = fmt.lower().replace('jpeg', 'jpg')
                        if ext not in ['jpg', 'png', 'tga', 'bmp']: ext = 'png'
                        
                        archive_fname = f"asset_{img_id}.{ext}"
                        save_path = os.path.join(tmpdir, archive_fname)
                        
                        try:
                            bl_image.save_render(save_path) # Сохраняем рендер (теперь безопасно из-за Standard)
                            if os.path.exists(save_path):
                                zf.write(save_path, arcname=f"assets/{archive_fname}")
                                data["assets_map"][str(img_id)] = archive_fname
                                # Добавляем мета-данные картинки в JSON
                                data["dependencies"]["images"].append(rzm_to_dict(rzm_img))
                        except Exception as e:
                            print(f"[RZM] Error saving image {bl_image.name}: {e}")

                # Пишем JSON
                zf.writestr('template_data.json', json.dumps(data, indent=2))
                
        except Exception as e:
            print(f"[RZM] Critical Export Error: {e}")
            return False
        finally:
            # Всегда возвращаем настройки цвета обратно!
            view_settings.view_transform = old_transform

        return True

    # -----------------------------------------------------------------------------
    #  IMPORT LOGIC
    # -----------------------------------------------------------------------------

    def import_template(self, filepath, position_offset=(0, 0), parent_id=-1):
        if not os.path.exists(filepath): return False
        
        extract_dir = os.path.join(tempfile.gettempdir(), "rzm_imports")
        if not os.path.exists(extract_dir): os.makedirs(extract_dir)

        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                if 'template_data.json' not in zf.namelist(): return False
                
                data = json.loads(zf.read('template_data.json'))
                assets_map = data.get("assets_map", {})
                
                # 1. Загрузка Assets (Images)
                # Remap: {Old_ID_in_JSON : New_ID_in_Scene}
                img_remap = {} 
                
                for old_id_str, fname in assets_map.items():
                    old_id = int(old_id_str)
                    arc_path = f"assets/{fname}"
                    if arc_path in zf.namelist():
                        target = os.path.join(extract_dir, fname)
                        with open(target, 'wb') as f: f.write(zf.read(arc_path))
                        
                        new_id = self.load_image_asset(target)
                        img_remap[old_id] = new_id

                # 2. Внедрение переменных (если таких нет)
                self.inject_vars(data.get("dependencies", {}))

                # 3. Создание элементов с ремаппингом ID
                self.create_elements(data, img_remap, parent_id, position_offset)
                
            return True
        except Exception as e:
            print(f"[RZM] Import Error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_image_asset(self, filepath):
        """Грузит картинку, избегая дубликатов, возвращает ID RZM Image."""
        # Пытаемся найти уже загруженную картинку по пути
        bl_image = None
        for img in bpy.data.images:
            if img.filepath == filepath:
                bl_image = img
                break
        
        if not bl_image:
            try:
                bl_image = bpy.data.images.load(filepath)
                bl_image.alpha_mode = 'STRAIGHT' # Важно для UI
            except: return -1

        # Ищем соответствующий RZM Image
        for rzm_img in self.rzm.images:
            if getattr(rzm_img, "image_pointer", None) == bl_image:
                return rzm_img.id

        # Создаем новый
        new_img = self.rzm.images.add()
        ids = {i.id for i in self.rzm.images}
        new_id = (max(ids) + 1) if ids else 1
        new_img.id = new_id
        new_img.display_name = bl_image.name
        new_img.source_type = 'CUSTOM'
        new_img.image_pointer = bl_image # SET POINTER
        return new_id

    def inject_vars(self, deps):
        # Добавляем переменные, только если их нет (по имени)
        for d in deps.get("values", []):
            name = d.get("value_name")
            if not any(v.value_name == name for v in self.rzm.rzm_values):
                dict_to_rzm(d, self.rzm.rzm_values.add())
                
        for d in deps.get("toggles", []):
            name = d.get("toggle_name")
            if not any(t.toggle_name == name for t in self.rzm.toggle_definitions):
                dict_to_rzm(d, self.rzm.toggle_definitions.add())

    def create_elements(self, data, img_remap, root_parent_id, offset):
        # Рассчитываем стартовый ID (чтобы не пересечься с существующими)
        max_id = max({e.id for e in self.rzm.elements} or {0})
        
        # Карта перевода ID: {ID_из_шаблона : Новый_ID_в_сцене}
        id_map = {}
        
        elements_data = data.get("elements", [])
        
        # Шаг 1: Генерируем новые ID
        for idx, el in enumerate(elements_data):
            old = el.get("_temp_original_id")
            new = max_id + 1 + idx
            if old is not None: id_map[old] = new
            
            # Обновляем ссылки на картинки внутри JSON данных перед созданием
            if "image_id" in el and el["image_id"] in img_remap:
                el["image_id"] = img_remap[el["image_id"]]
            
            if "conditional_images" in el:
                for ci in el["conditional_images"]:
                    if ci.get("image_id") in img_remap:
                        ci["image_id"] = img_remap[ci["image_id"]]

        origin = data.get("offset_origin", [0, 0])

        # Шаг 2: Создаем элементы
        for el_data in elements_data:
            new_el = self.rzm.elements.add()
            
            # Установка ID
            old_temp_id = el_data.get("_temp_original_id")
            new_el.id = id_map.get(old_temp_id, max_id + 999)
            
            # Установка Parent
            original_pid = el_data.get("parent_id", -1)
            
            # Если родитель был внутри этого же шаблона -> ремапим
            if original_pid in id_map:
                new_el.parent_id = id_map[original_pid]
            else:
                # Если родитель внешний (или это корень шаблона)
                # Привязываем к тому, что указали при импорте (root_parent_id)
                new_el.parent_id = root_parent_id
                
                # Применяем оффсет координат только к корневым элементам шаблона
                # (дети сместятся автоматически относительно родителя)
                dict_to_rzm(el_data, new_el) # Сначала заливаем данные
                
                # Корректируем позицию
                cur_x, cur_y = new_el.position
                new_el.position = (
                    int(cur_x - origin[0] + offset[0]), 
                    int(cur_y - origin[1] + offset[1])
                )
                continue # Пропускаем стандартную заливку ниже, т.к. уже сделали
            
            # Заливка данных для обычных детей
            dict_to_rzm(el_data, new_el)