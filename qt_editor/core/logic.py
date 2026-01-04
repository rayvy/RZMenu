# RZMenu/qt_editor/core/logic.py
import re
import math

class FormulaEvaluator:
    """
    Handles parsing and evaluation of element formulas (e.g., "$Button1 + 20").
    """

    # Safe dictionary for eval()
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
        Returns: Dict {id: {final_x, final_y, final_w, final_h}}
        """
        # 1. Build Lookup Map by Name (for $Variable) and ID
        name_map = {}
        id_map = {}

        # Output state
        resolved_state = {}

        for el in elements_data:
            # Clean name for variable usage and normalize to lowercase
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '', el['name']).lower()
            name_map[safe_name] = el['id']
            id_map[el['id']] = el

            # Initialize with static values
            resolved_state[el['id']] = {
                'x': el['pos_x'],
                'y': el['pos_y'],
                'w': el['width'],
                'h': el['height'],
                'is_resolved': False
            }

        # 2. Iterate to resolve formulas
        MAX_PASSES = 5

        for _ in range(MAX_PASSES):
            changes_made = False

            for el in elements_data:
                rid = el['id']
                state = resolved_state[rid]

                # Context for eval() - rebuilt every item to get latest values
                eval_context = FormulaEvaluator._build_eval_context(resolved_state, name_map)

                # --- Width/Height First ---
                if el['size_is_formula']:
                    new_w = FormulaEvaluator._eval_safe(el['formula_w'], eval_context, state['w'])
                    new_h = FormulaEvaluator._eval_safe(el['formula_h'], eval_context, state['h'])

                    if new_w != state['w'] or new_h != state['h']:
                        state['w'] = int(new_w)
                        state['h'] = int(new_h)
                        changes_made = True

                # --- Position ---
                if el['pos_is_formula']:
                    new_x = FormulaEvaluator._eval_safe(el['formula_x'], eval_context, state['x'])
                    new_y = FormulaEvaluator._eval_safe(el['formula_y'], eval_context, state['y'])

                    if new_x != state['x'] or new_y != state['y']:
                        state['x'] = int(new_x)
                        state['y'] = int(new_y)
                        changes_made = True

            if not changes_made:
                break

        return resolved_state

    @staticmethod
    def _build_eval_context(resolved_state, name_map):
        """Creates the dictionary of flat variables available inside formula."""
        ctx = FormulaEvaluator.SAFE_MATH.copy()

        for name, eid in name_map.items():
            if eid in resolved_state:
                s = resolved_state[eid]
                # Inject keys normalized to lowercase
                ctx[f"{name}positionx"] = s['x']
                ctx[f"{name}positiony"] = s['y']
                ctx[f"{name}sizex"] = s['w']
                ctx[f"{name}sizey"] = s['h']

        return ctx

    @staticmethod
    def _eval_safe(expression, context, default_val):
        """
        Parses string, replaces $Var with Var, evaluates case-insensitively.
        """
        if not expression or not isinstance(expression, str):
            return default_val

        try:
            # 1. Normalize to lowercase for case-insensitivity
            expr = expression.lower()

            # 2. Replace $Var with Var
            sanitized = re.sub(r'\$([a-zA-Z0-9_]+)', r'\1', expr)

            # 3. Eval
            res = eval(sanitized, {"__builtins__": {}}, context)
            return float(res)
        except Exception:
            # On error (syntax, cycle, missing var), return current static val
            return default_val
