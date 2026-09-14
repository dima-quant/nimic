import subprocess
import time

from nimic import ntranspile
import preprocess

start = time.time()
ntranspile([preprocess])
print(f"transpiled in {time.time() - start}")

cd1 = "cd /Users/dima/Documents/Scripts/Ndsl/examples/ncache && "
compile_str = f"nim c --app:lib --threads:on --out:{preprocess.__name__}.so {preprocess.__name__}"
# nim c [-d:danger] --app:lib --threads:on


print("start compiling")
process = subprocess.Popen(cd1 + compile_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
stdout, stderr = process.communicate()
print(stdout)
print(stderr)

pass