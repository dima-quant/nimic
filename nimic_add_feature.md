# Adding a feature to nimic
A new feature introduced, for example, during Nim to nimic translation should be added according to the following steps:
- first add a few tests for the desired behaviour in `tests/nimic/test_ntypes.py`
- then implement the feature in `src/nimic/ntypesystem.py` and check the tests pass
- finally, update the `nimic_translation_rules.md` with the new feature if it is a feature that should be exposed to the user of the `nimic` DSL

Example for adding test_keyword_dispatch:
- the tests are implemented in `test_keyword_dispatch` in `tests/nimic/test_ntypes.py` 
- the dispatch is implemented in `fn_dispatch` subfunction in `src/nimic/ntypesystem.py` for non-empty kwargs
- the rule is added to `nimic_translation_rules.md` table in the corresponding section (Functions and Arguments)


