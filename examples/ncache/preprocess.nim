import ncode/pystd/math
import ncode/pydefs
import ncode/nimpy
import ncode/nimpy/raw_buffers
import ncode/nimpy/py_types

proc nearest_neighbour_compute_source_index*(scale: float64, out_index: nint, input_size: nint): nint =
  result = min(nint(floor(float64(out_index) * scale)), input_size - 1)
  return result

proc hwc2chw_resize_simple*(inpRawData_ptr: ptr uint8, outRawData_ptr: ptr float32, inpH: nint, inpW: nint, outH: nint, outW: nint, C: nint=3, mean_array: array[3, float32]=array[3, float32]([0'f32, 0'f32, 0'f32]), std_array: array[3, float32]=array[3, float32]([1'f32, 1'f32, 1'f32]), reverse_channels: bool=false) =
  let
    reverse_channels = nint(reverse_channels)
  let
    inpRawData = cast[ptr UncheckedArray[uint8]](inpRawData_ptr)
    outRawData = cast[ptr UncheckedArray[float32]](outRawData_ptr)
  let
    scale_h = float64(inpH) / float64(outH)
    scale_w = float64(inpW) / float64(outW)
  for h in range(outH):
    for w in range(outW):
      for c in range(C):
        let
          src_h = nearest_neighbour_compute_source_index(scale=scale_h, out_index=h, input_size=inpH)
          src_w = nearest_neighbour_compute_source_index(scale=scale_w, out_index=w, input_size=inpW)
        var
          inp_f32 = float32(inpRawData[src_h * inpW * C + src_w * C + (1 - reverse_channels) * c + reverse_channels * (C - 1 - c)]) / 255'f32
        inp_f32 = (inp_f32 - mean_array[(1 - reverse_channels) * c + reverse_channels * (C - 1 - c)]) / (std_array[(1 - reverse_channels) * c + reverse_channels * (C - 1 - c)] + 1e-05'f32)
        outRawData[c * outH * outW + h * outW + w] = inp_f32

proc preprocessPipeline_nim*(image: PyObject, output: PyObject, reverse_channels: bool=false) {.exportpy.} =
  var
    image_buf: RawPyBuffer
  getBuffer(image, image_buf, PyBUF_SIMPLE or PyBUF_ND)
  var
    output_buf: RawPyBuffer
  getBuffer(output, output_buf, PyBUF_WRITABLE or PyBUF_ND)
  let
    rawData_ptr = cast[ptr uint8](image_buf.buf)
    output_ptr = cast[ptr float32](output_buf.buf)
  let
    H = nint(cast[ptr UncheckedArray[Py_ssize_t]](image_buf.shape)[0])
    W = nint(cast[ptr UncheckedArray[Py_ssize_t]](image_buf.shape)[1])
    C = nint(cast[ptr UncheckedArray[Py_ssize_t]](image_buf.shape)[2])
    outH = nint(cast[ptr UncheckedArray[Py_ssize_t]](output_buf.shape)[1])
    outW = nint(cast[ptr UncheckedArray[Py_ssize_t]](output_buf.shape)[2])
    C_out = nint(cast[ptr UncheckedArray[Py_ssize_t]](output_buf.shape)[0])
  assert C == C_out
  doAssert(C == 3, "Expected No of channels to be 3" + " but got " + $(C))
  hwc2chw_resize_simple(inpRawData_ptr=rawData_ptr, outRawData_ptr=output_ptr, inpH=H, inpW=W, outH=outH, outW=outW, C=C, reverse_channels=bool(reverse_channels))
  image_buf.release()
  output_buf.release()