# RZMenu/qt_editor/utils/string_utils.py
import re
import difflib

def find_common_pattern(strings):
    """
    Находит общие статические сегменты и возвращает паттерн с '...'.
    Учитывает наличие динамических промежутков во всех строках.
    """
    print(f"\n[SCAN] find_common_pattern input: {strings}")
    if not strings:
        return "", []
    
    strings = [s for s in strings if s]
    if not strings: 
        print("[SCAN] All strings are empty or None.")
        return "...", []
    if len(strings) == 1:
        return strings[0], [strings[0]]

    # 1. Поиск общих подстрок
    segments = find_all_common_substrings(strings)
    
    # 2. Фильтрация шума
    filtered_segments = []
    for seg in segments:
        # Увеличиваем минимальную длину для алфавитно-цифровых сегментов до 3
        # Но оставляем структурные символы (даже по 1)
        if len(seg) >= 3 or (len(seg) >= 1 and any(c in "_-. $/\\" for c in seg)):
            filtered_segments.append(seg)
            
    segments = filtered_segments
    print(f"[SCAN] Filtered static segments: {segments}")

    if not segments:
        print("[SCAN] No structural segments found, returning '...'")
        return "...", []
        
    # 3. Сборка паттерна с проверкой промежутков во ВСЕХ строках
    pattern_parts = []
    
    # Проверяем, есть ли что-то ДО первого сегмента
    has_leading_gap = any(not s.startswith(segments[0]) for s in strings)
    if has_leading_gap:
        pattern_parts.append("...")
        
    for i in range(len(segments)):
        pattern_parts.append(segments[i])
        
        if i < len(segments) - 1:
            # Проверяем, есть ли промежуток между текущим и следующим сегментом в любой из строк
            seg_curr = segments[i]
            seg_next = segments[i+1]
            has_gap = False
            for s in strings:
                pos_curr = s.find(seg_curr)
                pos_next = s.find(seg_next, pos_curr + len(seg_curr))
                if pos_next > pos_curr + len(seg_curr):
                    has_gap = True
                    break
            if has_gap:
                pattern_parts.append("...")
                
    # Проверяем, есть ли что-то ПОСЛЕ последнего сегмента
    last_seg = segments[-1]
    has_trailing_gap = any(not s.endswith(last_seg) for s in strings)
    if has_trailing_gap:
        pattern_parts.append("...")
        
    pattern = "".join(pattern_parts)
    # Удаляем лишние точки
    pattern = re.sub(r'\.\.\.(\.\.\.)+', '...', pattern)
    
    print(f"[SCAN] Resulting Pattern to UI: '{pattern}'")
    return pattern, segments

def apply_pattern_change(original_strings, old_pattern, new_pattern):
    """
    Применяет изменения паттерна к оригинальным строкам через Regex для надежности.
    """
    print(f"\n{'!'*40}")
    print(f"[APPLY] STARTING TRANSFORMATION")
    print(f"[APPLY] Original strings (snapshot): {original_strings}")
    print(f"[APPLY] Old Pattern: '{old_pattern}'")
    print(f"[APPLY] New Pattern: '{new_pattern}'")

    def normalize_dots(s):
        if not s: return ""
        s = s.replace('\u2026', '...')
        s = re.sub(r'\.\.\.+', '...', s)
        return s

    old_pattern = normalize_dots(old_pattern)
    new_pattern = normalize_dots(new_pattern)

    # 1. Извлекаем статические части старого паттерна
    old_static = old_pattern.split('...')
    new_static = new_pattern.split('...')
    
    # 2. Создаем Regex для захвата динамики
    # Регулярка будет вида ^Prefix(.*?)Middle(.*?)Suffix$
    regex_parts = []
    if old_pattern.startswith('...'):
        regex_parts.append('(.*?)')
        
    filtered_old_static = [s for s in old_static if s]
    for i, stat in enumerate(filtered_old_static):
        regex_parts.append(re.escape(stat))
        if i < len(filtered_old_static) - 1 or old_pattern.endswith('...'):
            regex_parts.append('(.*?)')
            
    regex_str = "^" + "".join(regex_parts) + "$"
    print(f"[APPLY] Extraction Regex: {regex_str}")
    
    results = []
    for s in original_strings:
        print(f"  > Item: '{s}'")
        match = re.match(regex_str, s)
        if match:
            dynamic_parts = list(match.groups())
            print(f"    > Extracted Dynamic (Regex): {dynamic_parts}")
        else:
            # Фолбэк на старый метод, если регулярка не совпала (например, из-за неточного совпадения статических частей)
            print(f"    [WARN] Regex match failed for '{s}', falling back to fuzzy extraction.")
            dynamic_parts = extract_dynamic_parts_fuzzy(s, filtered_old_static)
            print(f"    > Extracted Dynamic (Fuzzy): {dynamic_parts}")

        # 3. Реконструкция
        rebuilt = ""
        for i in range(len(new_static)):
            rebuilt += new_static[i]
            if i < len(new_static) - 1:
                # Вставляем динамику. Если динамики больше, чем дырок в новом паттерне - сшиваем остаток
                if i == len(new_static) - 2:
                    merged = "".join(dynamic_parts[i:])
                    rebuilt += merged
                    if len(dynamic_parts[i:]) > 1:
                         print(f"    > [ALERT] Merging tail dynamics: {dynamic_parts[i:]}")
                elif i < len(dynamic_parts):
                    rebuilt += dynamic_parts[i]
        
        print(f"    > Rebuilt result: '{rebuilt}'")
        results.append(rebuilt)
    
    print(f"{'!'*40}\n")
    return results

def extract_dynamic_parts_fuzzy(s, static_segments):
    """Метод-предохранитель для извлечения динамики, если статический сегмент слегка изменился."""
    dynamic = []
    curr_pos = 0
    for seg in static_segments:
        # Пытаемся найти сегмент. Если не нашли - ищем ближайший похожий? 
        # Пока просто пропускаем и фиксируем как динамику до следующего.
        pos = s.find(seg, curr_pos)
        if pos == -1:
            print(f"    [DEBUG_FUZZY] Segment '{seg}' not found, skipping...")
            continue
            
        if pos > curr_pos:
            dynamic.append(s[curr_pos:pos])
        curr_pos = pos + len(seg)
        
    if curr_pos < len(s):
        dynamic.append(s[curr_pos:])
    return dynamic

def find_all_common_substrings(strings):
    if not strings: return []
    current_common = [strings[0]]
    for s in strings[1:]:
        next_common = []
        for part in current_common:
            matches = get_ordered_matches(part, s)
            next_common.extend(matches)
        current_common = next_common
    return [c for c in current_common if c]

def get_ordered_matches(s1, s2):
    sm = difflib.SequenceMatcher(None, s1, s2)
    return [s1[m.a : m.a + m.size] for m in sm.get_matching_blocks() if m.size > 0]