from __future__ import annotations
import unittest
from nimic.inliner import template, template_expand

# Mock untyped for the purpose of the test, as it acts as a marker
class untyped:
    pass

class TestInliner(unittest.TestCase):

    def test_basic_template_expansion(self):
        """Test basic template expansion and parameter substitution."""
        
        # Define a global template for this test context (simulated)
        @template
        def add_helper(a, b, res) -> untyped:
            res.append(a + b)

        @template_expand
        def calculate():
            result = []
            add_helper(1, 2, result)
            add_helper(10, 20, result)
            return result

        self.assertEqual(calculate(), [3, 30])

    def test_dirty_template_outer_scope(self):
        """Test that templates can access variables from the outer scope (dirty)."""
        
        @template_expand
        def outer_scope_access():
            multiplier = 2
            result = []
            
            @template
            def apply_mult(val) -> untyped:
                # 'multiplier' and 'result' come from outer scope
                result.append(val * multiplier)
            
            apply_mult(10)
            apply_mult(20)
            return result

        self.assertEqual(outer_scope_access(), [20, 40])

    def test_complex_parameter_substitution(self):
        """Test substituting parameters with complex expressions."""
        
        @template_expand
        def expression_sub():
            out = []
            
            @template
            def log_calc(val) -> untyped:
                out.append(val)
                
            x = 10
            log_calc(x * 2 + 5)
            return out
            
        self.assertEqual(expression_sub(), [25])

    def test_multiple_templates(self):
        """Test using multiple different templates in one function."""
        
        @template_expand
        def multiple():
            res = []
            
            @template
            def t1(x) -> untyped:
                res.append(x)
                
            @template
            def t2(x) -> untyped:
                res.append(x * 2)
                
            t1(1)
            t2(1)
            return res
            
        self.assertEqual(multiple(), [1, 2])
        
    def test_return_behavior(self):
         """Test that 'return' inside a template returns from the expanded function."""
         
         @template_expand
         def check_ret(val):
             @template
             def ret_if_zero(x) -> untyped:
                 if x == 0:
                     return "Zero"
            
             ret_if_zero(val)
             return "Not Zero"
             
         self.assertEqual(check_ret(0), "Zero")
         self.assertEqual(check_ret(1), "Not Zero")

if __name__ == '__main__':
    unittest.main()
