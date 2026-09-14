import sys
sys.path.insert(0, 'tests/nraytracer')
from h264 import *

import converter_ppm_to_mp4
try:
    converter_ppm_to_mp4.main()
except Exception as e:
    pass

encoder = init(H264Encoder, 512, 288, None)
