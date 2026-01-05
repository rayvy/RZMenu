# RZMenu/qt_editor/core/logic.py
import re
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

                # --- A. Size Calculation ---
                new_w, new_h = state['w'], state['h']
                if el['size_is_formula']:
                    # Size formulas are independent of position hierarchy
                    new_w = FormulaEvaluator._eval_safe(el['formula_w'], eval_context, el['width'])
                    new_h = FormulaEvaluator._eval_safe(el['formula_h'], eval_context, el['height'])

                if int(new_w) != int(state['w']) or int(new_h) != int(state['h']):
                    state['w'] = int(new_w)
                    state['h'] = int(new_h)
                    changes_made = True

                # --- B. Position Calculation (Hierarchy vs Absolute) ---
                # Blender local position is the source
                local_x, local_y = el['pos_x'], el['pos_y']

                if el['pos_is_formula']:
                    # Formula is treated as ABSOLUTE (defines global position)
                    calc_x = FormulaEvaluator._eval_safe(el['formula_x'], eval_context, local_x)
                    calc_y = FormulaEvaluator._eval_safe(el['formula_y'], eval_context, local_y)
                    
                    final_x, final_y = calc_x, calc_y
                else:
                    # If NO formula, coords are relative to parent's global pos
                    final_x, final_y = local_x, local_y
                    if parent_id != -1 and parent_id in resolved_state:
                        parent_state = resolved_state[parent_id]
                        final_x += parent_state['x']
                        final_y += parent_state['y']

                if int(final_x) != int(state['x']) or int(final_y) != int(state['y']):
                    state['x'] = int(final_x)
                    state['y'] = int(final_y)
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

            # 2. Remove '$' sign
            clean_expr = expr_lower.replace('$', '')

            # 3. Eval
            res = eval(clean_expr, {"__builtins__": {}}, context)
            return float(res)
        except Exception:
            return default_val
