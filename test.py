import os

def count_clean_lines(filepath):
    """
    Считает количество строк кода в файле, исключая
    пустые строки и однострочные комментарии (#).
    """
    lines_count = 0
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                stripped_line = line.strip()
                # Если строка не пустая И не начинается с #
                if stripped_line and not stripped_line.startswith('#'):
                    lines_count += 1
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return lines_count

def scan_directory():
    root_dir = os.getcwd()  # Текущая директория запуска
    total_loc = 0
    total_files = 0
    
    # Папки, которые нужно игнорировать (чтобы не считать библиотеки)
    ignore_dirs = {
        'venv', '.venv', 'env', 
        '.git', '.idea', '.vscode', 
        '__pycache__', 'build', 'dist', 'migrations'
    }
    
    # Имя текущего скрипта, чтобы не считать его самого
    current_script = os.path.basename(__file__)

    print(f"--- Сканирование проекта: {root_dir} ---\n")
    print(f"{'Файл':<50} | {'Строк кода':<10}")
    print("-" * 65)

    for root, dirs, files in os.walk(root_dir):
        # Удаляем игнорируемые папки из списка обхода
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            if file.endswith(".py") and file != current_script:
                filepath = os.path.join(root, file)
                loc = count_clean_lines(filepath)
                
                # Выводим относительный путь для краткости
                rel_path = os.path.relpath(filepath, root_dir)
                
                print(f"{rel_path[:50]:<50} | {loc:<10}")
                
                total_loc += loc
                total_files += 1

    print("-" * 65)
    print(f"Всего файлов .py: {total_files}")
    print(f"Всего чистых строк кода: {total_loc}")

if __name__ == "__main__":
    scan_directory()
    input("\nНажмите Enter, чтобы выйти...")