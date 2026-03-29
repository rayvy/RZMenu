import os
from PIL import Image, ImageDraw, ImageFont

def create_font_atlas(font_path, output_path, cell_size=128):
    # Константы из шейдера
    grid_size = 16
    num_chars = 95  # ASCII от 32 до 126
    rows_glyphs = 6 # 6 рядов по 16 ячеек = 96 (хватает для 95 символов)
    rows_meta = 1   # 1 ряд снизу для хранения пикселей с метаданными
    
    # Размеры итоговой картинки
    img_w = grid_size * cell_size
    img_h = (rows_glyphs + rows_meta) * cell_size
    
    # Y-координата (в пикселях), где начинаются метаданные
    meta_y = rows_glyphs * cell_size
    
    atlas = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    
    try:
        # Размер шрифта подбираем так, чтобы он помещался в ячейку (70% от размера ячейки)
        font_size = int(cell_size * 0.88)
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        print(f"Ошибка: Не удалось загрузить шрифт '{font_path}'. Проверьте путь.")
        return

    # Позиция "пера" внутри каждой ячейки (отступ слева и базовая линия)
    pen_x = int(cell_size * 0.1)
    pen_y = int(cell_size * 0.75) # Базовая линия выравнивания
    
    for i in range(num_chars):
        char_code = i + 32
        char = chr(char_code)
        
        col = i % grid_size
        row = i // grid_size
        
        # Временная картинка размером с одну ячейку для точного измерения
        temp_img = Image.new("RGBA", (cell_size, cell_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(temp_img)
        
        # Рисуем символ белым цветом (шейдер читает R-канал: rawTexture.r)
        # anchor="ls" означает выравнивание по левому краю и базовой линии (Left-baseline)
        draw.text((pen_x, pen_y), char, font=font, fill=(255, 255, 255, 255), anchor="ls")
        
        # Получаем реальные границы пикселей нарисованного символа (bbox)
        bbox = temp_img.getbbox()
        
        # Advance (насколько курсор сдвигается вправо после этого символа)
        advance = font.getlength(char)
        
        if bbox:
            off_x, off_y, right, bottom = bbox
            glyph_w = right - off_x
            glyph_h = bottom - off_y
            
            # Вставляем отрендеренную ячейку в общий атлас
            atlas.paste(temp_img, (col * cell_size, row * cell_size), temp_img)
        else:
            # Для пробела (и невидимых символов) bbox возвращает None
            off_x, off_y, glyph_w, glyph_h = 0, 0, 0, 0
            
        # ==========================================
        # КОДИРОВАНИЕ МЕТАДАННЫХ (Обратная математика из шейдера)
        # Шейдер: m.advance = d1.r*2*cs  -> d1_r = (advance / (2*cs)) * 255
        # Шейдер: m.offX = (d1.b*2-1)*cs -> d1_b = ((offX / cs + 1) / 2) * 255
        # ==========================================
        
        d1_r = int(round((advance / (2 * cell_size)) * 255))
        d1_g = int(round((glyph_w / (2 * cell_size)) * 255))
        d1_b = int(round(((off_x / cell_size + 1) / 2) * 255))
        d1_a = int(round(((off_y / cell_size + 1) / 2) * 255))
        
        d2_r = int(round((glyph_h / (2 * cell_size)) * 255))
        d2_g = 0
        d2_b = 0
        d2_a = 255
        
        # Защита от выхода за пределы (0-255)
        d1_r, d1_g, d1_b, d1_a =[max(0, min(255, v)) for v in (d1_r, d1_g, d1_b, d1_a)]
        d2_r = max(0, min(255, d2_r))
        
        # Запись метаданных в пиксели текстуры
        # Шейдер читает пиксели: int3(idx % w, metaY + (idx/w)*2, 0)
        # Так как ширина текстуры больше 95, то idx % w это просто i.
        atlas.putpixel((i, meta_y), (d1_r, d1_g, d1_b, d1_a))
        atlas.putpixel((i, meta_y + 1), (d2_r, d2_g, d2_b, d2_a))
        
    atlas.save(output_path)
    print(f"Атлас успешно сгенерирован и сохранен как: {output_path}")

if __name__ == "__main__":
    # Укажи правильный путь к твоему TTF файлу и имя выходного PNG
    font_file = "Crimson-Bold.ttf" # Положи файл шрифта рядом со скриптом
    out_file = "font_atlas.png"
    
    # Размер ячейки можно менять, но 128 отлично подходит под математику шейдера (128.0/7.5)
    create_font_atlas(font_file, out_file, cell_size=32)