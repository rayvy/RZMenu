# RZMenu/rzm_serialization.py
import bpy
# Добавим импорты на случай, если они понадобятся для обработки специфичных типов данных
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