import os
from vtracer import convert

def convert_to_svg(input_folder, output_folder):
    # Создаем папку вывода, если её нет
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            input_path = os.path.join(input_folder, filename)
            # Убираем старое расширение и добавляем .svg
            output_filename = os.path.splitext(filename)[0] + ".svg"
            output_path = os.path.join(output_folder, output_filename)

            print(f"Обработка: {filename}...")

            # Настройки трассировки
            convert(
                input_path,
                output_path,
                mode='spline',      # Режим: 'polygon' или 'spline' (для плавных иконок)
                clustering=True,    # Группировка цветов
                iteration_count=10, # Точность (чем больше, тем детальнее)
                filter_speckle=4,   # Убирает мелкий визуальный шум
                color_precision=6   # Точность цветопередачи
            )
            print(f"Готово: {output_path}")

if __name__ == "__main__":
    # Укажи свои пути здесь
    convert_to_svg("input_icons", "output_svgs")