# /// nimic
#
# ///
# nimic port of the nim code for a Python module example for preprocessing from this blog post:
# https://ramanlabs.in/static/blog/Generate_Python_extensions_using_Nim_language.html

from __future__ import annotations
from math import floor
from nimic.ntypes import *
from nimic.nimpy import *
from nimic.nimpy.raw_buffers import RawPyBuffer, getBuffer
from nimic.nimpy.py_types import Py_ssize_t, PyBUF_SIMPLE, PyBUF_ND, PyBUF_WRITABLE


# nearest neighbour based routine to calculate the correponding input source index, given the output index.
def nearest_neighbour_compute_source_index(scale: float64, out_index: nint, input_size: nint) -> nint:
    result = min(nint(floor(float64(out_index) * scale)), input_size - 1)
    return result


def hwc2chw_resize_simple(inpRawData_ptr: ptr[uint8], outRawData_ptr: ptr[float32],
                          inpH: nint, inpW: nint, outH: nint, outW: nint,
                          C: nint = 3,
                          mean_array: array[3, float32] = array[3, float32]([f32(0), f32(0), f32(0)]),
                          std_array: array[3, float32] = array[3, float32]([f32(1), f32(1), f32(1)]),
                          reverse_channels: bool = False):

    with let:
        reverse_channels = nint(reverse_channels) #0/1

    with let:
        inpRawData = cast[ptr[UncheckedArray[uint8]]](inpRawData_ptr)
        outRawData = cast[ptr[UncheckedArray[float32]]](outRawData_ptr)

    with let:
        scale_h = float64(inpH) / float64(outH)
        scale_w = float64(inpW) / float64(outW)

    #For each position in output image/array, get the correponding input pixel value.
    for h in range(outH):
      for w in range(outW):
        for c in range(C):
          with let:
              src_h = nearest_neighbour_compute_source_index(scale=scale_h, out_index=h, input_size=inpH) #logical index
              src_w = nearest_neighbour_compute_source_index(scale=scale_w, out_index=w, input_size=inpW) #logical index

          #if reverse_channels is true, we get (C-1-c)'th channel, otherwise c'th channel.
          with var:
              inp_f32 = float32(inpRawData[src_h * inpW * C + src_w * C + (1 - reverse_channels) * c + reverse_channels * (C - 1 - c)]) / f32(255)

          #minus correponding mean and divide by standard deviation.
          inp_f32 = (inp_f32 - mean_array[(1 - reverse_channels) * c + reverse_channels * (C - 1 - c)]) / (std_array[(1 - reverse_channels) * c + reverse_channels * (C - 1 - c)] + f32(1e-5))

          #update corresponding memory-location for output array by converting logical indices to array indices.
          outRawData[c * outH * outW + h * outW + w] = inp_f32


def preprocessPipeline_nim(image: PyObject, output: PyObject, reverse_channels: bool = False):
    """{.exportpy.}"""

    with var:
        image_buf = RawPyBuffer()
    getBuffer(image, image_buf, PyBUF_SIMPLE | PyBUF_ND)

    with var:
        output_buf = RawPyBuffer()
    getBuffer(output, output_buf, PyBUF_WRITABLE | PyBUF_ND)

    #access to rawData
    with let:
        rawData_ptr = cast[ptr[uint8]](image_buf.buf)
        output_ptr = cast[ptr[float32]](output_buf.buf)

    #get dimensions of our input image.
    with let:
        H = nint(cast[ptr[UncheckedArray[Py_ssize_t]]](image_buf.shape)[0])
        W = nint(cast[ptr[UncheckedArray[Py_ssize_t]]](image_buf.shape)[1])
        C = nint(cast[ptr[UncheckedArray[Py_ssize_t]]](image_buf.shape)[2])

        outH = nint(cast[ptr[UncheckedArray[Py_ssize_t]]](output_buf.shape)[1])
        outW = nint(cast[ptr[UncheckedArray[Py_ssize_t]]](output_buf.shape)[2])
        C_out = nint(cast[ptr[UncheckedArray[Py_ssize_t]]](output_buf.shape)[0])

    assert C == C_out
    doAssert(C == 3, "Expected No of channels to be 3" + " but got " + str(C))

    hwc2chw_resize_simple(
        inpRawData_ptr=rawData_ptr,
        outRawData_ptr=output_ptr,
        inpH=H,
        inpW=W,
        outH=outH,
        outW=outW,
        C=C,
        reverse_channels=bool(reverse_channels)
    )

    #release the buffers reference for Python GC.
    image_buf.release()
    output_buf.release()
