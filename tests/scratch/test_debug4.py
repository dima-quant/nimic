import sys
sys.path.insert(0, 'tests/nraytracer')
from h264 import H264Encoder

# Add some prints in _n_set_value through monkey patch
import nimic.ntypesystem as nsys
orig_set_value = nsys._Object._n_set_value

def patched_set_value(self, other):
    print("Called set_value on", type(self).__name__)
    python_fields = getattr(self.__class__, '_n_python_fields', set())
    print("python_fields:", python_fields)
    for name in self._n_fields:
        print("name:", name)
    orig_set_value(self, other)

nsys._Object._n_set_value = patched_set_value

enc = H264Encoder()
print('has_c_type:', enc._n_has_c_type)
print('hasattr needCropping:', hasattr(enc, 'needCropping'))
