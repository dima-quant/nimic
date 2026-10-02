import re

with open("ncompiler/options.py", "r") as f:
    content = f.read()

# Replace explicit imports with star imports
content = re.sub(r'import ncompiler\.lineinfos as lineinfos', r'from ncompiler.lineinfos import *', content)
content = re.sub(r'import ncompiler\.platform as platform', r'from ncompiler.platform import *', content)
content = re.sub(r'import ncompiler\.prefixmatches as prefixmatches', r'from ncompiler.prefixmatches import *', content)
content = re.sub(r'import ncompiler\.pathutils as pathutils', r'from ncompiler.pathutils import *', content)
content = re.sub(r'import ncompiler\.nimpaths as nimpaths', r'from ncompiler.nimpaths import *', content)

# Remove module prefixes
content = re.sub(r'\blineinfos\.', '', content)
content = re.sub(r'\bplatform\.', '', content)
content = re.sub(r'\bprefixmatches\.', '', content)
content = re.sub(r'\bpathutils\.', '', content)
content = re.sub(r'\bnimpaths\.', '', content)

with open("ncompiler/options.py", "w") as f:
    f.write(content)
