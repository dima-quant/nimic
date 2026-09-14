#from nimic.nast import *
# import sitecustomize1
import os

from nimic import ntranspile
#import trace_of_radiance as tor
# import converter_ppm_to_mp4 as tor
# import colors
# import rng
# import hittables_variants
# import core
# import canvas
import trace_of_radiance_animation as tor

import time

start = time.time()
ntranspile([tor])
print(f"transpiled in {time.time() - start}")

# git clone https://github.com/mratsim/trace-of-radiance
# cd trace-of-radiance
# git checkout v0.1.0
# nim c -d:danger --outdir:build trace_of_radiance.nim
# ./build/trace_of_radiance > image.ppm

module_path = tor.__file__
module_dir = os.path.dirname(module_path)
ncache_dir = os.path.join(module_dir, "ncache/")
cd1 = "cd " + ncache_dir + " && "
compile_str = f"nim c -d:danger --outdir:build {tor.__name__}.nim"
run_str = f"./build/{tor.__name__}" # > image.ppm"

import subprocess

print("start compiling")
process = subprocess.Popen(cd1 + compile_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
stdout, stderr = process.communicate()
print(stdout)
print(stderr)

if "SuccessX" in stderr:
    print("running ...")
    process = subprocess.Popen(cd1 + run_str, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    stdout_run, stderr_run = process.communicate()
    print(stdout_run)
    print(stderr_run)
pass

# py:
# 0.41070690647689456 0.5237837148087416 0.696455731995717
# 0.34488628477866196 0.43883365934509216 0.5203491247803547
# 0.41173493508898157 0.531155878058918 0.6593532905028939
# 0.3743537812157073 0.47268580437095037 0.669272252089443
# 0.23635444067697178 0.3389989225244305 0.4638044569971889
# 0.6089987346383633 0.6945907275160861 0.8264322461991755
# 0.5822868471283492 0.6913243709806394 0.8323890837354628
# 0.4701500229176295 0.6087515706462867 0.6835610727197908
# 0.7139033304017423 0.84248551601019 1.0
# 0.7088210571269229 0.8399919822012838 1.0
# 0.715511097354994 0.843276938718721 1.0
# 0.7108796192961522 0.8410004742946825 1.0
# nim:
# 0.410706914398404950.52378372215026360.6964557374564471
# 0.344886292736324650.438833667179064750.5203491321479399
# 0.41173494300802190.53115588534286950.6593532964550758
# 0.374353789188051570.472685812047920.6692722579145696
# 0.236354448066278140.33899893047275990.4638044647205932
# 0.60899874118460620.6945907330025620.8264322496139547
# 0.58228685395353860.69132437651194430.8323890870452803
# 0.470150030608228960.60875157719522910.683561078356298
# 0.71390333561641020.84248551913999761.0
# 0.70882106241422990.83999198537579391.0
# 0.71551110254651910.8432769418343071.0
# 0.71087962455413170.84100047745113231.0

