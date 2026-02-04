# RZMenu/qt_editor/blender_bridge.py
import bpy

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

def import_image_from_dialog():
    """Open QFileDialog to select and import images into Blender."""
    from PySide6 import QtWidgets
    from .signals import SIGNALS
    
    files, _ = QtWidgets.QFileDialog.getOpenFileNames(
        None, "Select Images to Import", "", 
        "Images (*.png *.jpg *.jpeg *.tga *.bmp);;All Files (*)"
    )
    
    if not files:
        return

    # Importing images into Blender
    for path in files:
        if hasattr(bpy.ops.rzm, "add_image"):
            bpy.ops.rzm.add_image(filepath=path)
        else:
            print(f"BlenderBridge: rzm.add_image not found for {path}")
            
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

def import_image(filepath):
    """
    Import image from filepath into RZMenu.
    Returns (image_id, image_name) if successful, else (None, None).
    """
    import os
    if not os.path.exists(filepath):
        print(f"BlenderBridge: File not found: {filepath}")
        return None, None

    try:
        # We need to capture the ID of the newly created image.
        # rzm.add_image operator doesn't return ID directly. 
        # But it adds to the end of the list? Not necessarily if we recycle IDs?
        # Let's assume it appends for now or check the list diff.
        
        # Snapshot existing IDs
        from . import read
        pre_images = {img['id'] for img in read.get_available_images()}
        
        # Execute operator
        with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
            res = bpy.ops.rzm.add_image(filepath=filepath)
        
        if 'FINISHED' not in res:
            print("BlenderBridge: Failed to add image operator.")
            return None, None
            
        # Find new ID
        post_images = read.get_available_images()
        new_img = None
        for img in post_images:
            if img['id'] not in pre_images:
                new_img = img
                break
                
        if new_img:
            from .signals import SIGNALS
            SIGNALS.structure_changed.emit()
            return new_img['id'], new_img['name']
            
    except Exception as e:
        print(f"BlenderBridge: Error importing image {filepath}: {e}")
        
    return None, None

def create_image_element(image_id, x, y):
    """
    Create a new element of type 'IMAGE' with the specified image_id.
    """
    try:
        # Create element
        with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
            res = bpy.ops.rzm.add_element(type='IMAGE')
            
        if 'FINISHED' not in res:
            return None
            
        # Get active element (newly created)
        # We assume add_element selects the new element
        active_id = bpy.context.scene.rzm_active_element_id
        
        # Update properties
        # We can use core.update_property_multi or operators
        # Let's use operators for safety/undo
        
        # Set Position
        # Note: default creation might be at 0,0. We update to x,y.
        # Convert QT coords to Blender if needed? 
        # The args x,y passed here are usually Viewport (Qt) coords relative to canvas?
        # If they are Scene coords, we just set them.
        # Let's assume caller provides correct values.
        
        bpy.ops.rzm.update_property(prop_name="pos_x", val_str=str(int(x)))
        bpy.ops.rzm.update_property(prop_name="pos_y", val_str=str(int(y)))
        
        # Set Image ID
        bpy.ops.rzm.update_property(prop_name="image_id", val_str=str(image_id))
        
        from .signals import SIGNALS
        SIGNALS.structure_changed.emit()
        return active_id

    except Exception as e:
        print(f"BlenderBridge: Error creating image element: {e}")
        return None
