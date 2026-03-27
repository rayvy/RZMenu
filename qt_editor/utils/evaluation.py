# RZMenu/qt_editor/utils/evaluation.py
import re
import math
import logging

logger = logging.getLogger(__name__)

# Allowed functions for safe evaluation
SAFE_NAMES = {
    'abs': abs,
    'min': min,
    'max': max,
    'round': round,
    'math': math,
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'sqrt': math.sqrt,
    'pow': pow,
}

def safe_eval(expr, context=None):
    """
    Very primitive and safer-than-plain-eval evaluation for math formulas.
    Supports basic arithmetic and white-listed math functions.
    """
    if not expr: return None
    if context is None: context = {}
    
    # Sanitize: only allow numbers, operators, dots, underscores, and alphanumeric names
    # Also allow $, @, # for our variables, and ^, % for math
    cleaned_expr = str(expr).strip()
    if not cleaned_expr: return None
    
    if not re.match(r'^[a-zA-Z0-9_\.\s\+\-\*\/\(\)\,\$@#%^]+$', cleaned_expr):
        logger.warning(f"safe_eval: Invalid characters in expression: {cleaned_expr}")
        return None

    try:
        # Create a restricted environment
        eval_globals = {"__builtins__": {}}
        eval_globals.update(SAFE_NAMES)
        
        # Inject context variables
        eval_locals = {}
        for k, v in context.items():
            # Ensure keys are safe
            safe_k = re.sub(r'[^a-zA-Z0-9_]', '_', str(k))
            eval_locals[safe_k] = v
            
        processed_expr = str(expr)
        
        # Power Alias: Replace ^ with ** (common for math users)
        processed_expr = processed_expr.replace('^', '**')
        
        # Sort keys by length DESC to avoid partial replacement (e.g. $var1 vs $var)
        sorted_keys = sorted(context.keys(), key=len, reverse=True)
        for k in sorted_keys:
            safe_k = re.sub(r'[^a-zA-Z0-9_]', '_', str(k))
            # Use regex to match only full variable names (avoid matching $v in $v1)
            # Escape k for regex
            pattern = re.escape(k) + r'(?![a-zA-Z0-9_])'
            processed_expr = re.sub(pattern, safe_k, processed_expr)

        result = eval(processed_expr, eval_globals, eval_locals)
        # print(f"safe_eval result: {result} type: {type(result)}") # Debug
        return result
    except Exception as e:
        logger.error(f"safe_eval: Error evaluating '{expr}': {e}")
        return None

def get_formula_preview(expr, active_element_data=None):
    """
    High-level helper to get a preview result for a formula.
    Integrates with RZMenu element context.
    """
    if not expr: return ""
    
    # 1. Build context from active element and general scene info
    context = {
        "$WindowWidth": 1920, # Default stubs or real view size
        "$WindowHeight": 1080,
    }
    
    if active_element_data:
        # Inject active element properties as variables
        # $ParentWidth, $ParentHeight, $X, $Y, etc.
        # Note: Actual RZMenu variable names usually depend on element names.
        # This is just for local immediate feedback.
        context.update({
            "$Width": active_element_data.get('width', 0),
            "$Height": active_element_data.get('height', 0),
            "$X": active_element_data.get('pos_x', 0),
            "$Y": active_element_data.get('pos_y', 0),
        })
        
    res = safe_eval(expr, context)
    if isinstance(res, (int, float)):
        # Format nicely
        if isinstance(res, float):
            return f"{res:.2f}"
        return str(res)
    return str(res)
