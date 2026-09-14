import sys

with open('src/nimic/ntypesystem.py', 'r') as f:
    code = f.read()

target = """                resolved._n_register_type()  # should be performed in __class_getitem__
                return resolved
        raise NameError(f"Type '{t_name}' not found")"""

replacement = """                resolved._n_register_type()  # should be performed in __class_getitem__
                return resolved
        try:
            type_obj = eval(t_name, caller_globals or {})
            if isinstance(type_obj, type):
                return type_obj
        except Exception:
            pass
        raise NameError(f"Type '{t_name}' not found")"""

if target in code:
    code = code.replace(target, replacement)
    with open('src/nimic/ntypesystem.py', 'w') as f:
        f.write(code)
    print('Applied get_or_eval_type eval fallback patch.')
else:
    print('Target not found in eval fallback patch')
