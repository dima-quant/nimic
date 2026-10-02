from nimic.ntypesystem import _n_registry

print("EVAL INT:", _n_registry.get_or_eval_type("int", globals()))
