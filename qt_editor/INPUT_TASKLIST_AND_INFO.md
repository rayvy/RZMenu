# Viewport & Interaction Analysis

## 1. Group Movement "Snap Back"
**Symptoms**: Visuals work during drag. On release, non-active elements jump back.
**Cause**: The "Commit Loop" in `mouseReleaseEvent` commits items one by one.
`Item A -> Core Update -> Signal -> Viewport Refresh`.
The refresh re-reads Blender data. Item B hasn't been saved yet, so it is reset to its old position.
**Solution**: **Batch Commit**.
We need `core.transform.set_multiple_element_positions({id: (x,y), ...})`. This will write all data to Blender *first*, then emit ONE signal.

## 2. Resize "Blocked by Hidden"
**Symptoms**: Resize handles don't work when "Page 2" exists (even if hidden).
**Cause**:
1.  **Z-Index**: Handles might be drawn below the "Page 2" container.
2.  **Hidden State**: If "Hidden" means `Opacity=0` but `Visible=True`, the item still consumes mouse events.
**Solution**:
1.  Ensure Handles have `ZValue(9999)`.
2.  Ensure Hidden elements have `setVisible(False)` or `setEnabled(False)`.
3.  Check `RZHandleItem` parent. If it's a child of the element, it usually sits on top. But if the element is inside a "Page" that is below another "Page"... wait.
    If Page 2 covers Page 1, interactions on Page 1 are blocked.
    If Page 2 is hidden, it should not block.

## 3. Snapping Issues
**Cause**: The Snap Solver likely uses `item.pos()` (Local) for calculations, treating (0,0) as the anchor.
**Solution**: Pass `item.scenePos()` (Global) to the Snap Solver.

## Plan
1.  **Core**: Add `set_multiple_element_positions` to `transform.py`.
2.  **Viewport**: Update `mouseReleaseEvent` to collect all changes and call the batch function.
3.  **Viewport**: Update `RZHandleItem` Z-Index logic.
4.  **Viewport**: Audit `setVisible` logic for hidden elements.
