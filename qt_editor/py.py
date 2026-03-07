import os
from collections import Counter

def analyze_codebase(root_dir):
    all_lines = []
    file_stats = {}

    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = [line.strip() for line in f.readlines() if line.strip()]
                    file_stats[path] = len(lines)
                    all_lines.extend(lines)

    # Статистика
    total_lines = sum(file_stats.values())
    line_counts = Counter(all_lines)
    
    # Считаем только те, что встречаются более 1 раза
    duplicates = {line: count for line, count in line_counts.items() if count > 1}
    total_duplicate_lines = sum(duplicates.values()) - len(duplicates)

    print(f"Всего файлов: {len(file_stats)}")
    print(f"Всего строк кода: {total_lines}")
    print(f"Уникальных строк: {len(line_counts)}")
    print(f"Повторяющихся строк (избыточность): {total_duplicate_lines}")

# Запуск в текущей папке
analyze_codebase('.')