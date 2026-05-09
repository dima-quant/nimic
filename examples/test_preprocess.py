# nimic port of the nim code for a Python module example for preprocessing from this blog post:
# https://ramanlabs.in/static/blog/Generate_Python_extensions_using_Nim_language.html

import numpy as np
import preprocess as pipeline

#wrap this into a simple function, for easy usage.minimal extra latency in form of function call overhead.
def preprocess(image, output_shape:tuple, reverse_channels:bool=False):
    """ Takes an input image of uint8 , HWC format, returns resized image float32[0-1] with format CHW"""

    #image: numpy nd array of uint8 data-type of shape [H, W, C]
    #output_shape: (out_height, out_width)

    #returns: np.array of shape [C, out_height, out_width]
    inpH = image.shape[0]
    inpW = image.shape[1]
    C = image.shape[2]

    outH = output_shape[0]
    outW = output_shape[1]
    #output would be updated in-place.
    output = np.empty((C, outH, outW), dtype=np.float32)
    pipeline.preprocessPipeline_nim(image, output, reverse_channels=reverse_channels)

    return output

if __name__ == "__main__":
    # frame = cv2.imread("test.jpg") #Uint8 HWC format [576,768,3]
    frame = np.arange(0, 4 * 8 * 3, dtype=np.uint8).reshape((4, 8, 3))
    output = preprocess(frame, output_shape=(2, 4), reverse_channels=False)
    output_reversed = preprocess(frame, output_shape=(2, 4), reverse_channels=True)
    assert np.array_equal(output, output_reversed[::-1, :, :])
    assert np.allclose(255 * output[2, 1, :], 50 + 6*np.arange(4), atol=1e-6)

#This preprocessed output, can be directly used as an input to computer-vision model.
