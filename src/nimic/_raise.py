import sys
import os

def raise_at_line(target_file, target_line, exception_text):
    target_file = os.path.abspath(target_file)

    def tracer(frame, event, arg):
        # Check if we are in the right file and at the right line
        if event == 'line' and frame.f_lineno == target_line:
            # Check filename (handling potential path mismatches)
            current_file = os.path.abspath(frame.f_code.co_filename)
            if current_file == target_file:
                # Remove the tracer so we don't loop or interfere further
                sys.settrace(None)
                raise Exception(f"Constraint Violation at line {target_line}: {exception_text}")
        return tracer

    sys.settrace(tracer)

# --- Usage Example ---
# Suppose your inspection found an error in 'user_module.py' at line 42
raise_at_line('user_module.py', 42, "Unauthorized API call detected.")

# Now, when the code calls a function inside user_module that hits line 42:
# import user_module
# user_module.some_function()  <-- VS Code debugger will break here