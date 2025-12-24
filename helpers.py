import bpy

def get_next_available_id(elements):
    """Находит наименьший свободный ID, заполняя пробелы."""
    existing_ids = {elem.id for elem in elements}
    new_id = 0
    while new_id in existing_ids: new_id += 1
    return new_id

def get_next_image_id(images_collection):
    """Находит наименьший свободный числовой ID для изображения."""
    existing_ids = {img.id for img in images_collection}
    new_id = 0
    while new_id in existing_ids:
        new_id += 1
    print(f"DEBUG: Found next available image ID: {new_id}")
    return new_id

def get_assignable_toggles(context):
    """
    ИЗМЕНЕНО: Генерирует список имен тогглов для назначения, учитывая префикс 'rzm.Toggle.'.
    """
    if not context.active_object:
        return []
    
    obj = context.active_object
    
    # Все тогглы, определенные в проекте (например, "A", "Hat", "Bikini")
    project_toggles = context.scene.rzm.toggle_definitions
    project_toggle_names = {toggle_def.toggle_name for toggle_def in project_toggles}
    
    # Находим все свойства на объекте, которые начинаются с 'rzm.Toggle.'
    existing_toggles_on_obj = set()
    for key in obj.keys():
        if key.startswith("rzm.Toggle."):
            # Извлекаем чистое имя тоггла (например, из "rzm.Toggle.Hat" получаем "Hat")
            base_name = key.replace("rzm.Toggle.", "", 1)
            existing_toggles_on_obj.add(base_name)
    
    # Возвращаем те имена из проекта, которых еще нет на объекте
    return sorted(list(project_toggle_names - existing_toggles_on_obj))


def find_toggle_def(context, name):
    """Находит определение тоггла по имени."""
    for toggle_def in context.scene.rzm.toggle_definitions:
        if toggle_def.toggle_name == name:
            return toggle_def
    return None