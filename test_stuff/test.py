import os
import re

def find_target_file():
    for file in os.listdir('.'):
        if file.lower().endswith('.ini'):
            fn = file.lower()
            if "archived" not in fn and "disabled" not in fn:
                return file
    return None

def inquisitor_cleanup():
    target = find_target_file()
    if not target:
        print("[-] Файл не найден.")
        return

    with open(target, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # Паттерны для поиска
    section_pattern = re.compile(r'^\[(.+)\]')
    # Ищем вызовы: run = CommandList... ИЛИ run = CommandListElement...
    run_pattern = re.compile(r'run\s*=\s*(CommandList(?:Element)?)(.+)', re.IGNORECASE)
    
    trigger_phrase = ";[META-INFO] [START] [MOD-BLOCK]"
    
    # 1. Сбор "Белого списка" (используемые блоки)
    used_blocks = set()
    for line in lines:
        active_part = line.split(';')[0].split('#')[0]
        call = run_pattern.search(active_part)
        if call:
            prefix = call.group(1) # CommandList или CommandListElement
            name = call.group(2).strip().lower()
            used_blocks.add(f"{prefix.lower()}{name}")

    new_lines = []
    in_purge_zone = False
    removed_empty = 0
    removed_comments = 0
    removed_blocks = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        raw_line = line.strip()

        # Проверяем триггер начала инквизиции
        if trigger_phrase in line:
            in_purge_zone = True
            new_lines.append(line)
            i += 1
            continue

        if not in_purge_zone:
            # До триггера просто копируем всё как есть
            new_lines.append(line)
            i += 1
            continue

        # --- ЗОНА ИНКВИЗИЦИИ ---
        
        # 1. Удаление пустых строк
        if not raw_line:
            removed_empty += 1
            i += 1
            continue

        # 2. Удаление линий, начинающихся на ;
        if raw_line.startswith(';'):
            removed_comments += 1
            i += 1
            continue

        # 3. Ювелирная чистка CommandList / CommandListElement
        match = section_pattern.match(raw_line)
        if match:
            section_full = match.group(1).lower()
            
            # Проверяем, относится ли секция к нашим типам
            is_cmd = section_full.startswith("commandlist")
            is_elem = section_full.startswith("commandlistelement")
            
            if is_cmd or is_elem:
                # Определяем ключ для проверки в used_blocks
                # Если это Element, проверяем его целиком, если обычный - тоже.
                if section_full in used_blocks:
                    # Оставляем блок
                    new_lines.append(line)
                    i += 1
                    # Копируем содержимое блока до следующей секции
                    while i < len(lines) and not section_pattern.match(lines[i].strip()):
                        content_line = lines[i]
                        # Внутри блока тоже проводим чистку от пустых строк и комментариев
                        if content_line.strip() and not content_line.strip().startswith(';'):
                            new_lines.append(content_line)
                        else:
                            if not content_line.strip(): removed_empty += 1
                            else: removed_comments += 1
                        i += 1
                    continue
                else:
                    # Блок не используется - сжигаем
                    removed_blocks += 1
                    i += 1
                    while i < len(lines) and not section_pattern.match(lines[i].strip()):
                        i += 1
                    continue

        # Если это не блок коммандлиста, но мы в зоне инквизиции (например, TextureOverride)
        new_lines.append(line)
        i += 1

    # Результаты
    if removed_blocks + removed_empty + removed_comments > 0:
        backup_name = target + ".bak"
        with open(backup_name, 'w', encoding='utf-8') as b:
            b.writelines(lines)
        
        with open(target, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"[+] Инквизиция окончена для: {target}")
        print(f"    - Удалено пустых строк: {removed_empty}")
        print(f"    - Удалено чистых комментариев: {removed_comments}")
        print(f"    - Удалено неиспользуемых блоков: {removed_blocks}")
        print(f"[!] Бэкап: {backup_name}")
    else:
        print("[~] Файл уже идеально чист.")

if __name__ == "__main__":
    inquisitor_cleanup()