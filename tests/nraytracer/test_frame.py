from h264 import H264Encoder
from nimic.ntypesystem import DICT_OF_TYPES
enc = H264Encoder()
print("enc.frame type is:", type(enc.frame))
try:
    print("enc.frame.is_nil:", enc.frame.is_nil)
except Exception as e:
    print("Error:", e)
