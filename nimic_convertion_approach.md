# Convertion Nim code to nimic from [filename].nim to [filename].py
Translate line-for-line [filename].nim from compiler to nimic [filename].py in ncompiler folder following the nimic_translation_rules.md in the project root. Also an example of such translated nimic project is located in tests/nraytracer or other files in ncompiler folder. At the end of [filename].py add some tests after the added line of code:

```python
if comptime(__name__ == "__main__"):
```
make sure the tests pass, if needed, add missing functionality to the nimic.std modules (according to the corresponding Nim modules). If during the translation there was a new feature introduced currently not supported in nimic, the new feature should be properly implemented in nimic following the project rules in nimic_add_feature.md. 

Transpile the converted Python code back to Nim using `transpiler.unparse` (use examples are in nimic/__init__.py) and confirm that the transpiled code is valid Nim code by inspection, not necessary to complile it yet, as it could have many dependencies.

Additionally, do not use extra module qualification if the original Nim source did not use it. For example, if Nim uses `Table` (from `std/tables`) or `hash` (from `std/hashes`) directly, import them directly in Python (e.g., `from nimic.std.tables import Table` and `from nimic.std.hashes import hash, Hash`) instead of using qualified names like `std.tables.Table` or `std.hashes.hash`.
For example, the specific translation rules:
- Do not use extra module qualifications if the original Nim source did not use it. For example, if Nim uses `Table`, `AbsoluteDir`, or `TNoteKind` directly without module prefixes, import them directly in Python using `from module import *` or explicit imports instead of using qualified names like `std.tables.Table`, `pathutils.AbsoluteDir`, or `lineinfos.TNoteKind`.
- There is no need to declare `result = Type()` if the result is defined by the very next line. Initialize it directly with its value.
- To express inclusive ranges like `{low(TNoteKind)..high(TNoteKind)}`, use the `inrange` function: `Tset[TNoteKind](inrange(low(TNoteKind), high(TNoteKind)))`.
- Convert Nim loops as Python loops, do not use Python expressions or idioms.
