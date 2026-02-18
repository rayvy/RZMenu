import os

def analyze_texworks_module():
    # Путь к папке скрипта
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Исключения
    exclude_dirs = {'.git', '0-assets', '__pycache__', 'blood'} # blood часто пустой или системный, но оставим в коде
    exclude_files = {'.hlsl', '.txt', '.py'}

    # 1. Собираем маски из корня
    root_files = os.listdir(root_dir)
    masks = [f for f in root_files if f.lower().endswith('.mask.png')]

    # 2. Структура для хранения данных о слотах
    # { 'слот_lower': { 'original_name': 'имя', 'materials': { 'material_name': count }, 'mask': 'имя_маски' } }
    unique_slots = {}

    # Получаем список материалов (папок первого уровня)
    materials = [d for d in os.listdir(root_dir) 
                 if os.path.isdir(os.path.join(root_dir, d)) and d not in exclude_dirs]

    for mat in materials:
        mat_path = os.path.join(root_dir, mat)
        # Получаем список слотов в этом материале
        slots_in_mat = [s for s in os.listdir(mat_path) 
                        if os.path.isdir(os.path.join(mat_path, s)) and s != '0-assets']

        for slot in slots_in_mat:
            slot_key = slot.lower()
            slot_path = os.path.join(mat_path, slot)
            
            # Считаем количество декалей (.png)
            decal_count = len([f for f in os.listdir(slot_path) if f.lower().endswith('.png')])

            if slot_key not in unique_slots:
                # Ищем маску для этого слота (по частичному совпадению имени)
                found_mask = "НЕТ"
                for mask in masks:
                    if slot_key in mask.lower():
                        found_mask = mask
                        break
                
                unique_slots[slot_key] = {
                    'display_name': slot,
                    'materials': {mat: decal_count},
                    'mask': found_mask
                }
            else:
                # Если такой слот уже был найден в другом материале
                unique_slots[slot_key]['materials'][mat] = decal_count

    # --- ВЫВОД РЕЗУЛЬТАТОВ ---
    print(f"--- АНАЛИЗ МОДУЛЯ: {os.path.basename(root_dir)} ---")
    print(f"Найдено масок в корне: {len(masks)}")
    print("-" * 60)
    print(f"{'СЛОТ (UNIQUE)':<20} | {'МАСКА':<20} | {'РАСПОЛОЖЕНИЕ (ДЕКАЛИ)':<30}")
    print("-" * 60)

    for s_key in sorted(unique_slots.keys()):
        data = unique_slots[s_key]
        
        # Формируем строку расположения: Material(X) Material2(Y)
        location_str = ", ".join([f"{m}({c})" for m, c in data['materials'].items()])
        
        # Если слот есть в нескольких материалах, выделим это
        is_duplicate = " [!] Дубликат" if len(data['materials']) > 1 else ""
        
        print(f"{data['display_name']:<20} | {data['mask']:<20} | {location_str}{is_duplicate}")

    print("-" * 60)
    
    # Считаем общую статистику
    total_unique = len(unique_slots)
    total_physical_folders = sum(len(d['materials']) for d in unique_slots.values())

    print(f"ИТОГО:")
    print(f"- Уникальных слотов: {total_unique}")
    print(f"- Всего папок слотов во всех материалах: {total_physical_folders}")
    if total_physical_folders > total_unique:
        print(f"- Обнаружено совпадений имен: {total_physical_folders - total_unique}")
    print("=" * 60)

if __name__ == "__main__":
    analyze_texworks_module()