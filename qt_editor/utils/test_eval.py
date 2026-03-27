
import re
import math

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
    if not expr: return None
    if context is None: context = {}
    
    # The regex from evaluation.py
    # if not re.match(r'^[a-zA-Z0-9_\.\s\+\-\*\/\(\)\,\$@#%^]+$', str(expr)):
    #     return 'Invalid Characters'

    try:
        eval_globals = {'__builtins__': {}}
        eval_globals.update(SAFE_NAMES)
        eval_locals = {}
        for k, v in context.items():
            safe_k = re.sub(r'[^a-zA-Z0-9_]', '_', str(k))
            eval_locals[safe_k] = v
            
        processed_expr = str(expr)
        processed_expr = processed_expr.replace('^', '**')
        
        sorted_keys = sorted(context.keys(), key=len, reverse=True)
        for k in sorted_keys:
            safe_k = re.sub(r'[^a-zA-Z0-9_]', '_', str(k))
            pattern = re.escape(k) + r'(?![a-zA-Z0-9_])'
            processed_expr = re.sub(pattern, safe_k, processed_expr)

        result = eval(processed_expr, eval_globals, eval_locals)
        return result
    except Exception as e:
        return f'Error: {str(e)}'

print(f'Test "500 - 100": {safe_eval("500 - 100")}')
print(f'Test "500-100": {safe_eval("500-100")}')
print(f'Test "2^3": {safe_eval("2^3")}')
print(f'Test "10/2": {safe_eval("10/2")}')
