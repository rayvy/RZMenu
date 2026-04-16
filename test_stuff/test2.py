import os
import re
from collections import defaultdict

# Настройки те же
TRIGGER_PHRASE = ";[META-INFO] [START] [MOD-BLOCK]"
WHITELIST_PREFIXES = ('$', 'run', 'post run', 'pre run', 'x', 'y', 'z', 'w')
BLACKLIST_VARS = {'$positionx', '$positiony', '$sizex', '$sizey'}

def get_all_vars(line):
    return re.findall(r'\$[a-zA-Z0-9_.]+', line)

def real_compression():
    target = None
    for file in os.listdir('.'):
        if file.lower().endswith('.ini') and not any(x in file.lower() for x in ["archived", "disabled"]):
            target = file
            break
    
    if not target: return

    with open(target, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # --- 1. Сбор Глобалок ---
    global_vars = set()
    in_constants = False
    for line in lines:
        raw = line.strip().lower()
        if raw == "[constants]": in_constants = True
        elif in_constants and raw.startswith('['): in_constants = False
        if in_constants and raw.startswith("global"):
            for v in get_all_vars(raw): global_vars.add(v.lower())

    # --- 2. Поиск паттернов ---
    elements = {}
    current_elem = None
    in_zone = False
    section_re = re.compile(r'^\[(CommandListElement.+)\]', re.IGNORECASE)

    for line in lines:
        if TRIGGER_PHRASE in line: in_zone = True
        if not in_zone: continue
        match = section_re.match(line.strip())
        if match:
            current_elem = match.group(1)
            elements[current_elem] = []
        elif current_elem and line.strip() and not line.strip().startswith('['):
            elements[current_elem].append(line.strip())

    patterns = defaultdict(list)
    for name, content in elements.items():
        i = 0
        while i < len(content):
            chunk = []
            j = i
            while j < len(content):
                line = content[j].strip()
                line_low = line.lower()
                if any(line_low.startswith(p) for p in WHITELIST_PREFIXES):
                    vars_in_line = get_all_vars(line_low)
                    if not vars_in_line or all(v in global_vars for v in vars_in_line):
                        if not (vars_in_line and vars_in_line[0] in BLACKLIST_VARS):
                            chunk.append(line)
                            j += 1
                            continue
                break 
            if len(chunk) >= 2:
                patterns[tuple(chunk)].append(name)
                i = j
            else: i += 1

    # --- 3. Подготовка замены ---
    valid_replacements = {}
    idx_attr, idx_cmd = 0, 0
    
    for block, owners in patterns.items():
        if (len(block) * len(owners)) - (len(owners) + 1 + len(block)) > 0:
            is_attr = all(l.startswith('$') for l in block)
            new_name = f"CommandListGetDeduplicated{'Attribute' if is_attr else 'CommandList'}.{idx_attr if is_attr else idx_cmd}"
            if is_attr: idx_attr += 1 
            else: idx_cmd += 1
            valid_replacements[block] = new_name

    # --- 4. Генерация нового контента ---
    new_lines = []
    skip_lines = 0
    in_zone = False

    i = 0
    while i < len(lines):
        line = lines[i]
        if TRIGGER_PHRASE in line: in_zone = True
        
        # Если мы в зоне инквизиции и нашли начало элемента
        match = section_re.match(line.strip())
        if in_zone and match:
            new_lines.append(line)
            # Берем весь контент элемента
            elem_name = match.group(1)
            content = elements.get(elem_name, [])
            
            j = 0
            while j < len(content):
                found_match = False
                # Ищем, не начинается ли текущая позиция с одного из паттернов (от длинных к коротким)
                for block, new_name in sorted(valid_replacements.items(), key=lambda x: len(x[0]), reverse=True):
                    if tuple(content[j:j+len(block)]) == block:
                        new_lines.append(f"    run = {new_name}\n")
                        j += len(block)
                        found_match = True
                        break
                if not found_match:
                    new_lines.append(f"    {content[j]}\n")
                    j += 1
            
            # Пропускаем строки оригинального файла до следующей секции
            i += 1
            while i < len(lines) and not re.match(r'^\[.+\]', lines[i].strip()):
                i += 1
            continue
        
        new_lines.append(line)
        i += 1

    # Добавляем новые блоки в конец
    new_lines.append("\n; --- DEDUPLICATED BLOCKS START ---\n")
    for block, name in valid_replacements.items():
        new_lines.append(f"\n[{name}]\n")
        for bl in block:
            new_lines.append(f"    {bl}\n")

    # --- 5. Запись ---
    backup = target + ".bak"
    with open(backup, 'w', encoding='utf-8') as b: b.writelines(lines)
    with open(target, 'w', encoding='utf-8') as f: f.writelines(new_lines)
    
    print(f"[+] Успех! Файл {target} оптимизирован.")
    print(f"[+] Создано новых блоков: {len(valid_replacements)}")
    print(f"[!] Бэкап сохранен в {backup}")

if __name__ == "__main__":
    real_compression()