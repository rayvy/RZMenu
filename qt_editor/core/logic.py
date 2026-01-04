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
            # Clean name for variable usage
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '', el['name'])
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
        # We run multiple passes to handle dependencies (A depends on B).
        # Max passes = 5 to prevent infinite loops / lag.
        MAX_PASSES = 5

        for _ in range(MAX_PASSES):
            changes_made = False

            for el in elements_data:
                rid = el['id']
                state = resolved_state[rid]

                # Context for eval() - rebuilt every item to get latest values
                eval_context = FormulaEvaluator._build_eval_context(resolved_state, name_map)

                # --- Width/Height First (Position might depend on Size) ---
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
        """Creates the dictionary of variables available inside formula."""
        ctx = FormulaEvaluator.SAFE_MATH.copy()

        # Add elements as objects: $Name.x, $Name.w
        class MockObj:
            def __init__(self, d):
                self.x = d['x']
                self.y = d['y']
                self.w = d['w']
                self.h = d['h']
                self.width = d['w']
                self.height = d['h']
                # Aliases often used
                self.left = d['x']
                self.right = d['x'] + d['w']
                self.top = d['y'] + d['h']
                self.bottom = d['y']

        for name, eid in name_map.items():
            if eid in resolved_state:
                # Add variable with $ prefix logic (handled by regex before eval,
                # but here we populate the lookup for the replaced name)
                # Actually, standard python eval doesn't like '$'.
                # parser will strip '$'. So we register "Name"
                ctx[name] = MockObj(resolved_state[eid])

        return ctx

    @staticmethod
    def _eval_safe(expression, context, default_val):
        """
        Parses string, replaces $Var with Var, evaluates.
        """
        if not expression or not isinstance(expression, str):
            return default_val

        try:
            # 1. Replace $Var with Var
            # Regex: match $ followed by alphanum
            sanitized = re.sub(r'\$([a-zA-Z0-9_]+)', r'\1', expression)

            # 2. Eval
            res = eval(sanitized, {"__builtins__": {}}, context)
            return float(res)
        except Exception:
            # On error (syntax, cycle, missing var), return current static val
            return default_val
