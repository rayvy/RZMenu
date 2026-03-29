import winreg
import os

def get_windows_fonts():
    fonts = {}
    try:
        # Открываем ветку реестра со списком всех установленных шрифтов
        registry_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
        
        # Получаем количество записей (шрифтов)
        count = winreg.QueryInfoKey(registry_key)[1]
        
        for i in range(count):
            name, value, _ = winreg.EnumValue(registry_key, i)
            
            # value — это обычно имя файла (например, "arialbd.ttf") или полный путь
            if not os.path.isabs(value):
                # Если путь не полный, значит он в папке C:\Windows\Fonts\
                fonts_dir = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')
                value = os.path.join(fonts_dir, value)
                
            fonts[name] = value
            
        winreg.CloseKey(registry_key)
    except Exception as e:
        print(f"Ошибка при чтении реестра: {e}")
        
    return fonts

if __name__ == "__main__":
    print("Загрузка списка шрифтов Windows...\n")
    system_fonts = get_windows_fonts()
    
    # Спрашиваем пользователя, что он хочет найти
    search_query = input("Введите часть названия шрифта для поиска (например, 'Arial' или 'Bahnschrift') или нажмите Enter для вывода всех: ").lower()
    
    print("\n--- НАЙДЕННЫЕ ШРИФТЫ ---")
    found = 0
    for font_name, font_path in system_fonts.items():
        if search_query in font_name.lower():
            print(f"Название: {font_name}")
            print(f"Путь:     {font_path}")
            print("-" * 40)
            found += 1
            
    print(f"Всего найдено: {found}")
    
    # Пример, как можно скопировать путь для первого скрипта
    print("\nПодсказка:")
    print("Скопируй строку 'Путь' нужного шрифта (сохраняя слэши) и вставь в скрипт генерации атласа:")
    print("Например: font_file = r'C:\\Windows\\Fonts\\bahnschrift.ttf'")