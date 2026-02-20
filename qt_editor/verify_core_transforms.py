import bpy
from RZMenu.qt_editor import core

def verify_core_transforms():
    print("\n" + "="*60)
    print("STARTING RZE CORE VERIFICATION")
    print("="*60)
    
    # 0. SETUP
    # Clear existing elements to start fresh
    print("[0] Clearing Scene...")
    while len(bpy.context.scene.rzm.elements) > 0:
        core.delete_elements([e.id for e in bpy.context.scene.rzm.elements])
        
    # 1. CREATE HIERARCHY
    print("[1] Creating Hierarchy: Parent -> Child")
    parent_id = core.create_element("CONTAINER", parent_id=-1)
    child_id = core.create_element("BUTTON", parent_id=parent_id)
    
    core.set_element_position(parent_id, 100, 100, mode='LOCAL')
    core.set_element_position(child_id, 50, 50, mode='LOCAL') # Relative to parent
    
    # Verify Global Pos of Child
    # Parent (100, 100) + Child (50, 50) = (150, 150)
    elements = bpy.context.scene.rzm.elements
    elem_map = {e.id: e for e in elements}
    child = elem_map[child_id]
    
    gx, gy = core.get_global_pos(child, elem_map)
    print(f"Child Global Pos: ({gx}, {gy}) - Expected: (150, 150)")
    assert gx == 150 and gy == 150, "Global Position Calc Failed!"
    
    # 2. TEST REPARENTING (Anti-Teleport)
    print("[2] Testing Reparenting (Preserve Global)")
    # Move child to Root (-1). It should stay at (150, 150) globally.
    # Since Root is (0,0), its Local pos should become (150, 150).
    
    core.reparent_element(child_id, -1)
    
    new_local_x = child.position[0]
    new_local_y = child.position[1]
    
    print(f"Child New Local (Root): ({new_local_x}, {new_local_y}) - Expected: (150, 150)")
    assert new_local_x == 150 and new_local_y == 150, "Reparent Teleportation Fix Failed!"
    
    # 3. TEST SET GLOBAL POSITION
    print("[3] Testing Set Global Position")
    # Move Parent to (200, 200)
    core.set_element_position(parent_id, 200, 200, mode='GLOBAL')
    
    # Reparent Child back to Parent
    # Child is at (150, 150). Parent is at (200, 200).
    # Child is theoretically "outside" parent to the top-left?
    # RZMenu coordinates: Y Down is usually Qt, but Blender stores raw Ints.
    # Assuming positive X, Y.
    
    core.reparent_element(child_id, parent_id)
    # Child Global should still be (150, 150).
    # Parent Global is (200, 200).
    # New Local should be (150 - 200, 150 - 200) = (-50, -50).
    
    nlx, nly = child.position[0], child.position[1]
    print(f"Child New Local (in Parent): ({nlx}, {nly}) - Expected: (-50, -50)")
    assert nlx == -50 and nly == -50, "Global Set / Reparent Math Failed!"
    
    print("\n" + "="*60)
    print("VERIFICATION SUCCESSFUL: CORE MATH IS ROBUST")
    print("="*60)

if __name__ == "__main__":
    try:
        verify_core_transforms()
    except AssertionError as e:
        print(f"\n!!! VERIFICATION FAILED: {e} !!!")
    except Exception as e:
        print(f"\n!!! RUNTIME ERROR: {e} !!!")
