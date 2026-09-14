# Review of the converted Nim code to nimic from [filename].nim to [filename].py
Execute the following steps sequentially:

# 1. Log file. 
Create a review file review_[filename].md in the same directory as [filename].py to store the results of the review. Fill it with information found during the review process below.

# 2. Review the code conversion.
Verify line-for-line that the converted code in [filename].py has a direct correspondence in[filename].nim such that a transpiler can restore the original nim code or equivalent. Check that the conversion was done following nimic_convertion_approach.md in accordance with nimic_translation_rules.md. If there is some Python code that has no or incorrect correspondence in the original nim code, such import of a Python built-in module, or functionality implemented using Python buil-in modules instead of the corresponding modules in nimic.std, make a note in the review file review_[filename].md. An example of correctly translated nimic project is located in tests/nraytracer. Perform the verification of the whole file till the end, only logging the observations about possible issues to the review file, without undertaking any corrections or fixes. By reaching the end of file, write the results to the review file and go to the next step.

# 3. Check test cases. 
Check some other scripts importing this module (listed between square brackets in dep_tree.md in compiler folder) and how they typically use its functionality. Check if the test cases at the end of the file following the line with `if comptime(__name__ == "__main__"):` cover the most important and nontrivial functionality of the translated module. If they don't, add new test cases to cover the missing functionality. Check if the tests pass. If the tests fails, make a note in the review file, idicating the details of the failer but without attempting to fix the tests. By reaching the end of file, write the results to the review file and go to the next step. 

# 4. Resolve issues or propose fixes. 
If there are any isuues found in steps 2-3 and logged in the review file, start fixing them following the nimic_convertion_approach.md in accordance with nimic_translation_rules.md. Write the progress in the review file after each fix. If an issue is rather complex, present several possible fixes with pros and cons of each. If a fix is not working, revert the fix and write in the review file what was done and why the fix is not working. If theere are no issues found, write this in the review file.