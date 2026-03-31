# RZMenu/qt_editor/core/logic.py
import re
import bpy
import math

class FormulaEvaluator:
    """
    Handles parsing and evaluation of element formulas (e.g., "$Button1PositionX + 20").
    Supports flat 3DMigoto style variables and Hierarchy logic.
    """
    
    SAFE_MATH = {
        'min': min, 'max': max, 'abs': abs, 'round': round, 
        'sin': math.sin, 'cos': math.cos, 'tan': math.tan, 
        'pi': math.pi, 'int': int, 'float': float
    }

    @staticmethod
    def resolve_layout(elements_data):
        """
        Iterative resolution of elements.
        elements_data: list of dicts (from get_viewport_data).
        Returns: Dict {id: {final_x, final_y, final_w, final_h}} in GLOBAL coordinates.
        """
        # 1. Build Lookup Map by ID
        id_map = {el['id']: el for el in elements_data}
        
        # State holds current FINAL GLOBAL calculated values. x,y are global.
        resolved_state = {} 

        for el in elements_data:
            # Clean name for variable usage and normalize to lowercase
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '', el['name']).lower()
            
            # Initial guess: treat Blender local as global for start
            resolved_state[el['id']] = {
                'x': el['pos_x'],
                'y': el['pos_y'],
                'w': el['width'],
                'h': el['height'],
                'name_safe': safe_name
            }

        # 2. Iterative Resolution (Multi-pass)
        MAX_PASSES = 5

        for _ in range(MAX_PASSES):
            changes_made = False

            # Context for eval() - rebuilt every pass to get latest global values
            eval_context = FormulaEvaluator._build_flat_context(resolved_state)

            for el in elements_data:
                rid = el['id']
                state = resolved_state[rid]
                parent_id = el['parent_id']

                # Prepare Local Variable Context for this element
                # If has parent -> use parent global values. If no parent -> use static local values.
                local_vars = {}
                if parent_id != -1 and parent_id in resolved_state:
                    p_state = resolved_state[parent_id]
                    local_vars['positionx'] = p_state['x']
                    local_vars['positiony'] = p_state['y']
                    local_vars['sizex'] = p_state['w']
                    local_vars['sizey'] = p_state['h']
                else:
                    # Fallback to own static data
                    local_vars['positionx'] = el['pos_x']
                    local_vars['positiony'] = el['pos_y']
                    local_vars['sizex'] = el['width']
                    local_vars['sizey'] = el['height']
                
                # Merge local vars into local_context for this element's evaluation
                local_eval_context = {**eval_context, **local_vars}

                # --- A. Size Calculation ---
                new_w, new_h = state['w'], state['h']
                if el['size_is_formula']:
                    new_w = FormulaEvaluator._eval_safe(el['formula_w'], local_eval_context, el['width'])
                    new_h = FormulaEvaluator._eval_safe(el['formula_h'], local_eval_context, el['height'])

                if new_w != state['w'] or new_h != state['h']:
                    state['w'] = new_w
                    state['h'] = new_h
                    changes_made = True

                # --- B. Position Calculation (Hierarchy vs Absolute) ---
                local_x, local_y = el['pos_x'], el['pos_y']

                if el['pos_is_formula']:
                    # Formula is treated as ABSOLUTE (defines global position)
                    calc_x = FormulaEvaluator._eval_safe(el['formula_x'], local_eval_context, local_x)
                    calc_y = FormulaEvaluator._eval_safe(el['formula_y'], local_eval_context, local_y)
                    
                    final_x, final_y = calc_x, calc_y
                else:
                    # If NO formula, coords are relative to parent's global pos
                    final_x, final_y = local_x, local_y
                    if parent_id != -1 and parent_id in resolved_state:
                        parent_state = resolved_state[parent_id]
                        final_x += parent_state['x']
                        final_y += parent_state['y']

                if final_x != state['x'] or final_y != state['y']:
                    state['x'] = final_x
                    state['y'] = final_y
                    changes_made = True

            if not changes_made:
                break

        return resolved_state

    @staticmethod
    def _build_flat_context(resolved_state):
        """
        Creates a dictionary of flattened, lowercase variables.
        $Button1PositionX -> mapped to Button1's current global X.
        """
        ctx = FormulaEvaluator.SAFE_MATH.copy()

        for rid, data in resolved_state.items():
            name = data['name_safe']
            if not name: continue
            
        # Inject keys normalized to lowercase
            ctx[f"{name}positionx"] = data['x']
            ctx[f"{name}positiony"] = data['y']
            ctx[f"{name}sizex"] = data['w']
            ctx[f"{name}sizey"] = data['h']

        # Add Global RZM Values, Toggles, and Shapes
        if bpy.context and bpy.context.scene:
            rzm = bpy.context.scene.rzm
            
            # Values ($)
            for val in rzm.rzm_values:
                # Value names like "$MyVar" -> "myvar"
                clean_name = val.value_name.lower().replace('$','')
                if val.value_type == 'INT':
                    ctx[clean_name] = val.int_value
                else:
                    ctx[clean_name] = val.float_value
            
            # Toggles (@) - Map to 1.0 (True) or 0.0 (False) if we had state. 
            # For now mapping to 0.0 as default existence for layout resolution.
            # Real runtime value comes from game engine, but here we just need valid parsing.
            for toggle in rzm.toggle_definitions:
                clean_name = toggle.toggle_name.lower().replace('@', '')
                ctx[clean_name] = 0.0
                
            # Shapes (#)
            for shape in rzm.shapes:
                clean_name = shape.shape_name.lower().replace('#', '')
                ctx[clean_name] = 0.0

        return ctx

    @staticmethod
    def _eval_safe(expression, context, default_val):
        """
        Parses string, handles case-insensitivity, flattening, and eval.
        """
        if not expression or not isinstance(expression, str):
            return default_val

        try:
            # 1. Normalize expression to lowercase
            expr_lower = expression.lower()

            # 2. Remove '$', '@', '#' signs
            clean_expr = expr_lower.replace('$', '').replace('@', '').replace('#', '')

            # 3. Eval with recursive resolution for unknown names
            while True:
                try:
                    res = eval(clean_expr, {"__builtins__": {}}, context)
                    return float(res)
                except NameError as ne:
                    # e.g. name 'w23' is not defined
                    parts = str(ne).split("'")
                    if len(parts) >= 2:
                        missing_name = parts[1]
                        if missing_name in context: 
                            raise ne
                        context[missing_name] = 0.0
                        continue
                    raise ne
                except Exception:
                    return default_val
        except Exception:
            return default_val
