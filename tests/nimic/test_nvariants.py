# -*- coding: utf-8 -*-
"""Unit tests for nimic.nvariants (pure AST; no nimic types)."""
from __future__ import annotations
import unittest

from nimic.nvariants import NBranch, NCase, NField, NRecord, NVariantLayout, parse_class_source

NODE_SRC = '''
class NodeObj(Object):
    """docstring"""
    info: nint
    kind: int
    match kind:
        case 0:
            intVal: nint
        case 1 | 2:
            leftOp: Node
            rightOp: Node
        case 3:
            cond: Node
            hasElse: bool
            match hasElse:
                case True:
                    elsePart: Node
                case False:
                    pass
    tail: nint

    def method(self) -> None:
        pass
'''


def layout(src: str) -> NVariantLayout:
    return NVariantLayout(parse_class_source(src), eval_value=eval, ordinal=int)


class TestRecordParser(unittest.TestCase):

    def test_common_fields_before_and_after_case(self):
        rec = parse_class_source(NODE_SRC)
        self.assertTrue(rec.is_variant)
        self.assertEqual(rec.items[0], NField("info", "nint"))
        self.assertIsInstance(rec.items[1], NCase)
        self.assertEqual(rec.items[2], NField("tail", "nint"))
        self.assertEqual(len(rec.items), 3)

    def test_all_fields_declaration_order(self):
        rec = parse_class_source(NODE_SRC)
        self.assertEqual(list(rec.all_fields()),
                         ["info", "kind", "intVal", "leftOp", "rightOp", "cond", "hasElse", "elsePart", "tail"])
        self.assertEqual(list(rec.discriminators()), ["kind", "hasElse"])

    def test_multi_field_branch_and_or_pattern(self):
        case = parse_class_source(NODE_SRC).items[1]
        self.assertEqual(case.discriminator, NField("kind", "int"))
        add_sub = case.branches[1]
        self.assertEqual(add_sub.values, ("1", "2"))
        self.assertEqual(add_sub.items, (NField("leftOp", "Node"), NField("rightOp", "Node")))

    def test_nested_case_and_singletons(self):
        nested = parse_class_source(NODE_SRC).items[1].branches[2].items[1]
        self.assertIsInstance(nested, NCase)
        self.assertEqual([b.values for b in nested.branches], [("True",), ("False",)])
        self.assertEqual(nested.branches[1].items, ())

    def test_case_else(self):
        rec = parse_class_source('''
class V(Object):
    k: int
    match k:
        case 0:
            a: int
        case _:
            b: int
''')
        self.assertIsNone(rec.items[0].branches[1].values)

    def test_case_else_must_be_last(self):
        with self.assertRaises(TypeError):
            parse_class_source('''
class V(Object):
    k: int
    match k:
        case _:
            b: int
        case 0:
            a: int
''')

    def test_duplicate_field_names(self):
        with self.assertRaises(TypeError) as cm:
            parse_class_source('''
class V(Object):
    k: int
    match k:
        case 0:
            a: int
        case 1:
            a: float
''')
        self.assertIn("'a'", str(cm.exception))

    def test_unsupported_statements_in_branch(self):
        for body in ("x = 1", "def f(self): pass"):
            with self.subTest(body=body), self.assertRaises(TypeError):
                parse_class_source(f'''
class V(Object):
    k: int
    match k:
        case 0:
            {body}
''')
        for case_line in ("case 0 if True:", "case [x]:", "case Foo():"):
            with self.subTest(case=case_line), self.assertRaises(TypeError):
                parse_class_source(f'''
class V(Object):
    k: int
    match k:
        {case_line}
            a: int
''')

    def test_legacy_dummy_default_on_discriminator(self):
        rec = parse_class_source('''
class Material(Object):
    kind: MaterialKind = None
    match kind:
        case MaterialKind.kMetal:
            fMetal: Metal
        case MaterialKind.kLambertian:
            fLambertian: Lambertian
''')
        case = rec.items[0]
        self.assertEqual(case.discriminator, NField("kind", "MaterialKind"))
        self.assertEqual(case.branches[0].values, ("MaterialKind.kMetal",))

    def test_plain_object_is_not_variant(self):
        rec = parse_class_source("class P(Object):\n    x: int\n    y: float = 1.0\n")
        self.assertFalse(rec.is_variant)
        self.assertEqual(list(rec.all_fields()), ["x", "y"])

    def test_map_annotations(self):
        rec = parse_class_source('''
class Node[K, V](Object):
    keys: array[M, K]
    isInternal: bool
    match isInternal:
        case False:
            vals: array[M, V]
        case True:
            links: array[M, Node[K, V]]
''')
        spec = rec.map_annotations(lambda a: a.replace("K", "str").replace("V", "int"))
        self.assertEqual(spec.all_fields()["vals"].annotation, "array[M, int]")
        self.assertEqual(spec.all_fields()["links"].annotation, "array[M, Node[str, int]]")
        self.assertEqual(rec.all_fields()["vals"].annotation, "array[M, V]")  # original untouched


class TestVariantLayout(unittest.TestCase):

    def test_active_fields_per_branch(self):
        lay = layout(NODE_SRC)
        self.assertEqual(lay.active_fields({"kind": 0}), ("info", "kind", "intVal", "tail"))
        self.assertEqual(lay.active_fields({"kind": 2}), ("info", "kind", "leftOp", "rightOp", "tail"))

    def test_active_fields_nested(self):
        lay = layout(NODE_SRC)
        self.assertEqual(lay.active_fields({"kind": 3, "hasElse": True}),
                         ("info", "kind", "cond", "hasElse", "elsePart", "tail"))
        self.assertEqual(lay.active_fields({"kind": 3, "hasElse": False}),
                         ("info", "kind", "cond", "hasElse", "tail"))
        self.assertTrue(lay.is_active("elsePart", {"kind": 3, "hasElse": True}))
        self.assertFalse(lay.is_active("elsePart", {"kind": 0, "hasElse": True}))

    def test_branch_key(self):
        lay = layout(NODE_SRC)
        self.assertEqual(lay.branch_key({"kind": 1}), lay.branch_key({"kind": 2}))
        self.assertNotEqual(lay.branch_key({"kind": 1}), lay.branch_key({"kind": 0}))
        self.assertNotEqual(lay.branch_key({"kind": 3, "hasElse": True}),
                            lay.branch_key({"kind": 3, "hasElse": False}))
        # a nested discriminator outside its active branch does not affect the key
        self.assertEqual(lay.branch_key({"kind": 0, "hasElse": True}),
                         lay.branch_key({"kind": 0, "hasElse": False}))

    def test_else_branch_and_no_match(self):
        lay = layout('''
class V(Object):
    k: int
    match k:
        case 0:
            a: int
        case _:
            b: int
''')
        self.assertEqual(lay.active_fields({"k": 7}), ("k", "b"))
        no_else = layout("class W(Object):\n    k: int\n    match k:\n        case 0:\n            a: int\n")
        self.assertEqual(no_else.active_fields({"k": 7}), ("k",))

    def test_owner_case_and_exhaustiveness(self):
        lay = layout(NODE_SRC)
        self.assertIs(lay.owner_case("elsePart"), lay.record.items[1].branches[2].items[1])
        self.assertIsNone(lay.owner_case("info"))
        self.assertIsNone(lay.owner_case("kind"))
        case = lay.record.items[1]
        self.assertTrue(lay.is_exhaustive(case, range(4)))
        self.assertFalse(lay.is_exhaustive(case, range(5)))

    def test_values_evaluated_lazily_once(self):
        calls = []

        def ev(src):
            calls.append(src)
            return eval(src)
        lay = NVariantLayout(parse_class_source(NODE_SRC), eval_value=ev, ordinal=int)
        self.assertEqual(calls, [])
        lay.active_fields({"kind": 0})
        n = len(calls)
        lay.active_fields({"kind": 1})
        self.assertEqual(len(calls), n)


if __name__ == "__main__":
    unittest.main()
