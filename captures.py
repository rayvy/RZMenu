# rz_gui_constructor/captures.py
import bpy
import os
import tempfile
import time

def execute_capture(context: bpy.types.Context, settings: bpy.types.PropertyGroup, force_framing=False):
    """
    Основная функция-исполнитель.
    force_framing используется для Auto-Capture, чтобы всегда кадрировать объект.
    """
    scene = context.scene

    # 1. Проверка контекста: находим активный 3D вьюпорт
    area = next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)
    if not area:
        print("RZM CAPTURE ERROR: Active 3D Viewport not found!")
        return None
        
    space = next((s for s in area.spaces if s.type == 'VIEW_3D'), None)
    if not space:
        print("RZM CAPTURE ERROR: 3D Viewport space data not found!")
        return None
        
    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
    if not region:
        print("RZM CAPTURE ERROR: 3D Viewport window region not found!")
        return None
        
    region_3d = space.region_3d

    # 2. Сохранение оригинальных настроек
    shading = space.shading
    overlay = space.overlay
    original = {
        "res_x": scene.render.resolution_x, "res_y": scene.render.resolution_y,
        "film_transparent": scene.render.film_transparent,
        "shading_type": shading.type, "use_scene_world": shading.use_scene_world,
        "show_overlays": overlay.show_overlays,
        "view_location": region_3d.view_location.copy(),
        "view_distance": region_3d.view_distance,
        "view_matrix": region_3d.view_matrix.copy(),
        "view_perspective": region_3d.view_perspective
    }
    
    temp_light, output_image = None, None
    entered_local_view = False
    is_already_local = (space.local_view is not None)
    
    temp_dir = tempfile.gettempdir()
    temp_filepath = os.path.join(temp_dir, f"rzm_capture_{int(time.time())}.png")

    try:
        # ИСПОЛЬЗУЕМ 'with context.temp_override' - ЭТО ПРАВИЛЬНЫЙ СПОСОБ
        with context.temp_override(window=context.window, area=area, region=region, screen=context.screen):
            # 3. Управление Local View и Кадрированием
            if context.selected_objects and not is_already_local:
                bpy.ops.view3d.localview()
                entered_local_view = True

            if force_framing:
                region_3d.view_perspective = 'ORTHO'
                bpy.ops.view3d.view_axis(type='FRONT')
                bpy.ops.view3d.view_selected()

            # 4. Применение настроек рендера
            scene.render.resolution_x = settings.resolution
            scene.render.resolution_y = settings.resolution
            scene.render.film_transparent = True
            scene.render.image_settings.file_format = 'PNG'
            scene.render.filepath = temp_filepath
            overlay.show_overlays = settings.use_overlays
            
            # 5. Применение настроек шейдинга
            shading_mode = settings.shading_mode
            shading.use_scene_world = original['use_scene_world']
            
            if shading_mode == 'SOLID': shading.type = 'SOLID'
            elif shading_mode == 'MATERIAL':
                shading.type = 'MATERIAL'
                shading.use_scene_world = False
            elif shading_mode == 'RENDERED':
                shading.type = 'RENDERED'
                if settings.add_temp_light:
                    bpy.ops.object.light_add(type='SUN', radius=1, align='WORLD', location=(0, 0, 0))
                    temp_light = context.active_object
                    temp_light.data.energy = 3

            # 6. Выполнение рендера
            context.view_layer.update()
            bpy.ops.render.opengl(write_still=True)
            
            # 7. Загрузка результата
            if os.path.exists(temp_filepath):
                output_image = bpy.data.images.load(temp_filepath, check_existing=False)
                output_image.pack()
            else:
                print("RZM CAPTURE ERROR: Rendered file not found.")

    except Exception as e:
        print(f"RZM CAPTURE CRITICAL ERROR: {e}")
        import traceback; traceback.print_exc()
        return None

    finally:
        # 8. ГАРАНТИРОВАННАЯ ОЧИСТКА
        print("RZM CAPTURE: Cleaning up...")

        if entered_local_view:
            # Для выхода из local view также используем override
            with context.temp_override(window=context.window, area=area, region=region, screen=context.screen):
                bpy.ops.view3d.localview()

        if temp_light and temp_light.name in bpy.data.objects:
            data = temp_light.data
            bpy.data.objects.remove(temp_light, do_unlink=True)
            if data and data.users == 0: bpy.data.lights.remove(data)
        
        try:
            for key, value in original.items():
                if hasattr(region_3d, key): setattr(region_3d, key, value)
                elif hasattr(scene.render, key): setattr(scene.render, key, value)
                elif hasattr(shading, key): setattr(shading, key, value)
                elif hasattr(overlay, key): setattr(overlay, key, value)
        except Exception as e:
            print(f"RZM CAPTURE ERROR during cleanup: {e}")

        if os.path.exists(temp_filepath):
            try: os.remove(temp_filepath)
            except Exception: pass
            
        print("RZM CAPTURE: Cleanup complete.")
    
    return output_image