import os
import shutil

# Папка, где запущен скрипт
root_dir = os.getcwd()
output_dir = os.path.join(root_dir, "outputs")

# Создаём папку outputs, если её нет
os.makedirs(output_dir, exist_ok=True)

# Проходим по всем файлам в корневой папке
for filename in os.listdir(root_dir):
    if filename.endswith(".j2"):
        source_path = os.path.join(root_dir, filename)
        new_filename = os.path.splitext(filename)[0] + ".txt"
        dest_path = os.path.join(output_dir, new_filename)
        
        # Копируем содержимое
        shutil.copyfile(source_path, dest_path)
        print(f"✅ {filename} → outputs/{new_filename}")

print("\nГотово! Все файлы .j2 скопированы в outputs как .txt")
