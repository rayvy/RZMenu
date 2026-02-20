import re
import difflib

def find_common_pattern(strings):
    """
    Находит общие статические сегменты и возвращает паттерн с '...'.
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
        if len(seg) >= 2 or seg in "_-. $/\\":
            filtered_segments.append(seg)
            
    segments = filtered_segments
    print(f"[SCAN] Filtered static segments: {segments}")

    if not segments:
        print("[SCAN] No structural segments found, returning '...'")
        return "...", []
        
    # 3. Сборка паттерна
    pattern_parts = []
    first_str = strings[0]
    curr_pos = 0
    
    for seg in segments:
        pos = first_str.find(seg, curr_pos)
        if pos == -1: continue 
        
        if pos > curr_pos:
            pattern_parts.append("...")
            
        pattern_parts.append(seg)
        curr_pos = pos + len(seg)
        
    if curr_pos < len(first_str):
        pattern_parts.append("...")
        
    pattern = "".join(pattern_parts)
    
    if segments and not first_str.startswith(segments[0]) and not pattern.startswith("..."):
        pattern = "..." + pattern
        
    pattern = re.sub(r'\.\.\.(\.\.\.)+', '...', pattern)
    print(f"[SCAN] Resulting Pattern to UI: '{pattern}'")
    
    return pattern, segments

def apply_pattern_change(original_strings, old_pattern, new_pattern):
    """
    Применяет изменения паттерна к оригинальным строкам.
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

    old_static = old_pattern.split('...')
    new_static = new_pattern.split('...')
    print(f"[APPLY] Old Static parts: {old_static}")
    print(f"[APPLY] New Static parts: {new_static}")
    
    results = []
    for s in original_strings:
        print(f"  > Item: '{s}'")
        # 2. Извлечение динамики
        dynamic_parts = extract_dynamic_parts_v2(s, old_static)
        print(f"    > Extracted Dynamic: {dynamic_parts}")
        
        # 3. Реконструкция
        rebuilt = ""
        for i in range(len(new_static)):
            rebuilt += new_static[i]
            
            if i < len(new_static) - 1:
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

def extract_dynamic_parts_v2(s, static_segments):
    dynamic = []
    curr_pos = 0
    # Убираем пустые строки, которые возникают от ... по краям
    active_segments = [seg for seg in static_segments if seg]
    
    print(f"    [DEBUG_EXTRACT] Using segments: {active_segments}")
    for seg in active_segments:
        pos = s.find(seg, curr_pos)
        if pos == -1:
            print(f"    [DEBUG_EXTRACT] !! Segment '{seg}' NOT FOUND in '{s}' after index {curr_pos}")
            continue
        
        if pos > curr_pos:
            dyn = s[curr_pos:pos]
            dynamic.append(dyn)
        
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