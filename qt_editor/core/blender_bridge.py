# RZMenu/qt_editor/blender_bridge.py
import shutil
from pathlib import Path
import os
import bpy
from ...core.serialization import RZTemplateEngine

def get_stable_context():
    if bpy.context.area and bpy.context.area.type == 'VIEW_3D':
        return bpy.context.copy()
    
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if not region and area.regions: region = area.regions[0]
                return {
                    'window': window, 'screen': screen, 'area': area, 
                    'region': region, 'scene': window.scene, 'workspace': window.workspace
                }
    return {}

def exec_in_context(op_func, **kwargs):
    # (yellow) Context Manager: Логика прописана намертво. 
    # Пытается найти VIEW_3D, но если оператор требует другого контекста (например, Image Editor), это упадет.
    ctx = get_stable_context()
    if not ctx: return {'CANCELLED'}
    try:
        if hasattr(bpy.context, "temp_override"):
            with bpy.context.temp_override(**ctx): return op_func(**kwargs)
        else:
            return op_func(ctx, **kwargs)
    except Exception as e:
        print(f"RZM Context Error: {e}")
        return {'CANCELLED'}

def refresh_viewports():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D': area.tag_redraw()

def safe_undo_push(message):
    exec_in_context(bpy.ops.ed.undo_push, message=message)
    refresh_viewports()

def get_template_search_paths():
    """Возвращает список путей для поиска шаблонов."""
    paths = []
    
    # 1. Встроенные шаблоны (Base Templates)
    # Правильный расчет пути:
    # __file__ = .../RZMenu/qt_editor/core/blender_bridge.py
    # dirname  = .../RZMenu/qt_editor/core
    # dirname  = .../RZMenu/qt_editor
    # dirname  = .../RZMenu
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    addon_root = os.path.dirname(os.path.dirname(current_dir)) # Поднимаемся на 2 уровня вверх от core
    
    base_dir = os.path.join(addon_root, "base_templates")
    if os.path.exists(base_dir):
        paths.append(base_dir)
        
    # 2. Локальные шаблоны (rzm_assets рядом с .blend)
    if bpy.data.is_saved:
        project_dir = os.path.dirname(bpy.data.filepath)
        local_assets = os.path.join(project_dir, "rzm_assets")
        if os.path.exists(local_assets):
            paths.append(local_assets)
            
    return paths

def get_base_templates_dir():
    """Возвращает путь к папке base_templates внутри аддона."""
    # Используем Path для точности.
    # Файл: .../RZMenu/qt_editor/core/blender_bridge.py
    
    bridge_file = Path(__file__).resolve()
    
    # .parent (core) -> .parent (qt_editor) -> .parent (RZMenu)
    addon_root = bridge_file.parent.parent.parent
    
    # Формируем путь к папке с шаблонами
    base_dir = addon_root / "base_templates"
    
    # Конвертируем в строку для совместимости с os.path и shutil
    base_dir_str = str(base_dir)
    
    if not os.path.exists(base_dir_str):
        try:
            os.makedirs(base_dir_str)
            print(f"[RZM] Created base_templates directory at: {base_dir_str}")
        except Exception as e:
            print(f"[RZM] Error creating base_templates dir: {e}")
            
    return base_dir_str

def import_asset_from_dialog():
    """Открывает диалог для импорта Картинок или Шаблонов."""
    from PySide6 import QtWidgets
    from .signals import SIGNALS
    
    # 1. Выбор файлов
    files, _ = QtWidgets.QFileDialog.getOpenFileNames(
        None, "Select Assets", "", 
        "All Assets (*.png *.jpg *.jpeg *.tga *.bmp *.rzmt);;Images (*.png *.jpg *.jpeg *.tga *.bmp);;Templates (*.rzmt)"
    )
    
    if not files: return

    # 2. Получаем папку назначения
    target_dir = get_base_templates_dir()
    print(f"[Bridge] Target directory for templates: {target_dir}") # <-- DEBUG PRINT
    
    has_changes = False

    for path in files:
        ext = os.path.splitext(path)[1].lower()
        filename = os.path.basename(path)
        
        # A. SHABLON -> COPY
        if ext == '.rzmt':
            dest_path = os.path.join(target_dir, filename)
            try:
                shutil.copy2(path, dest_path)
                print(f"[Bridge] Copied template to: {dest_path}")
                has_changes = True
            except Exception as e:
                print(f"[Bridge] Error copying template: {e}")

        # B. IMAGE -> IMPORT
        elif ext in ['.png', '.jpg', '.jpeg', '.tga', '.bmp']:
            if hasattr(bpy.ops.rzm, "add_image"):
                try:
                    bpy.ops.rzm.add_image(filepath=path)
                    has_changes = True
                except Exception as e:
                    print(f"[Bridge] Blender Operator Error: {e}")
            else:
                print("[Bridge] rzm.add_image operator missing!")

    if has_changes:
        SIGNALS.structure_changed.emit()

def reload_base_icons():
    """Triggers rzm.load_base_icons operator and refreshes UI."""
    from .signals import SIGNALS
    try:
        if hasattr(bpy.ops.rzm, "load_base_icons"):
            bpy.ops.rzm.load_base_icons()
            SIGNALS.structure_changed.emit()
        else:
            print("BlenderBridge: rzm.load_base_icons not found")
    except Exception as e:
        print(f"BlenderBridge: Failed to reload base icons: {e}")

def export_template_direct(ids_list, filepath):
    """Экспорт списка ID в .rzmt файл."""
    if not ids_list: return False
    
    # Получаем контекст Блендера
    # Можно использовать get_stable_context(), но для RZTemplateEngine достаточно bpy.context,
    # так как он работает с данными сцены, а не операторами.
    engine = RZTemplateEngine(bpy.context)
    
    meta_name = os.path.basename(filepath).replace(".rzmt", "")
    return engine.export_template(ids_list, filepath, meta_name=meta_name)

def get_template_search_paths():
    """Возвращает список путей, где искать шаблоны."""
    paths = []
    
    # 1. Встроенные шаблоны (Base Templates) внутри аддона
    # Путь: RZMenu/base_templates
    # Вычисляем относительно текущего файла bridge.py
    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    base_dir = os.path.join(addon_dir, "base_templates")
    if os.path.exists(base_dir):
        paths.append(base_dir)
        
    # 2. Локальные шаблоны проекта (рядом с .blend)
    if bpy.data.is_saved:
        project_dir = os.path.dirname(bpy.data.filepath)
        local_assets = os.path.join(project_dir, "rzm_assets")
        if os.path.exists(local_assets):
            paths.append(local_assets)
            
    # 3. (Опционально) Глобальные шаблоны пользователя
    # user_dir = os.path.join(bpy.utils.user_resource('SCRIPTS'), "presets", "rzm_templates")
    # if os.path.exists(user_dir): paths.append(user_dir)
    
    return paths

def get_all_templates():
    """Сканирует все папки и возвращает список доступных шаблонов."""
    templates = []
    seen_names = set()
    
    search_paths = get_template_search_paths()
    
    for folder in search_paths:
        if not os.path.exists(folder): continue
        
        for f in os.listdir(folder):
            if f.endswith(".rzmt"):
                name = os.path.splitext(f)[0]
                # Избегаем дубликатов (локальные перекрывают базовые, если имена совпадают)
                if name not in seen_names:
                    templates.append({
                        "name": name,
                        "filepath": os.path.join(folder, f),
                        "type": "TEMPLATE"
                    })
                    seen_names.add(name)
    return templates

def import_template_direct(filepath, offset=(0,0), parent_id=-1):
    """Прямой вызов движка импорта."""
    if not os.path.exists(filepath):
        print(f"[Bridge] Error: Template file not found: {filepath}")
        return False
        
    print(f"[Bridge] Importing template: {filepath} at {offset}")
    try:
        # ВАЖНО: передаем bpy.context
        engine = RZTemplateEngine(bpy.context)
        success = engine.import_template(filepath, position_offset=offset, parent_id=parent_id)
        
        if success:
            # Обновляем UI сигналом
            from .signals import SIGNALS
            SIGNALS.structure_changed.emit()
            return True
    except Exception as e:
        print(f"[Bridge] Import Exception: {e}")
        
    return False

def get_templates_list(folder_path):
    """Сканирует папку на наличие .rzmt файлов для Ассет Браузера."""
    templates = []
    if os.path.exists(folder_path):
        for f in os.listdir(folder_path):
            if f.endswith(".rzmt"):
                templates.append({
                    "name": f.replace(".rzmt", ""),
                    "filepath": os.path.join(folder_path, f),
                    "type": "TEMPLATE"
                })
    return templates

