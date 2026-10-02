import sys

with open('src/nimic/ntypesystem.py', 'r') as f:
    code = f.read()

target = """            if hasattr(other, "_n_register_type"):
                other._n_register_type()
            ptr_type = make_pointer_type(other, class_name=original_name)"""

replacement = """            ptr_type = make_pointer_type(other, class_name=original_name)
            if hasattr(other, "_n_register_type"):
                other._n_register_type()"""

if target in code:
    code = code.replace(target, replacement)
    with open('src/nimic/ntypesystem.py', 'w') as f:
        f.write(code)
    print("Applied _SomeRefClass patch.")
else:
    print("Target not found.")
