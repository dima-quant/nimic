import math
import nimpy
import nimpy / [raw_buffers, py_types]


# nearest neighbour based routine to calculate the correponding input source index, given the output index.
proc nearest_neighbour_compute_source_index(scale:float, out_index:int, input_size:int):int=
    return min( int( floor(out_index.float * scale)), input_size-1 )

proc hwc2chw_resize_simple(inpRawData_ptr:ptr uint8, outRawData_ptr:ptr float32, inpH:int, inpW:int, outH:int, outW:int, C=3, mean_array:array[3, float32]=[0'f32,0,0], std_array:array[3, float32]=[1'f32,1,1], reverse_channels:bool=false)=

    let reverse_channels = int(reverse_channels) #0/1
    let
        inpRawData = cast[ptr UncheckedArray[uint8]](inpRawData_ptr)
        outRawData = cast[ptr UncheckedArray[float32]](outRawData_ptr)

    let
        scale_h:float = inpH.float/outH.float
        scale_w:float = inpW.float/outW.float

    #For each position in output image/array, get the correponding input pixel value.
    for h in 0..<outH:
      for w in 0..<outW:
        for c in 0..<C:
          let src_h = nearest_neighbour_compute_source_index(scale=scale_h, out_index=h, input_size=inpH) #logical index
          let src_w = nearest_neighbour_compute_source_index(scale=scale_w, out_index=w, input_size=inpW) #logical index

          #if reverse_channels is true, we get (C-1-c)'th channel, otherwise c'th channel.
          var inp_f32 = float32(inpRawData[src_h*inpW*C + src_w*C + (1-reverse_channels)*c + reverse_channels*(C-1-c)])/255'f32

          #minus correponding mean and divide by standard deviation.
          inp_f32 = (inp_f32 - mean_array[(1-reverse_channels)*c + reverse_channels*(C-1-c)])/(std_array[(1-reverse_channels)*c + reverse_channels*(C-1-c)] + 1e-5'f32)

          #update corresponding memory-location for output array by converting logical indices to array indices.
          outRawData[c*outH*outW + h*outW + w] = inp_f32


proc preprocessPipeline_nim(image:PyObject, output:PyObject, reverse_channels:bool=false){.exportpy.}=

  var image_buf:RawPyBuffer
  image.getBuffer(image_buf, PyBUF_SIMPLE or PyBUF_ND)

  var output_buf:RawPyBuffer
  output.getBuffer(output_buf, PyBUF_WRITABLE or PyBUF_ND)


  #access to rawData
  let rawData_ptr = cast[ptr uint8](image_buf.buf)
  let output_ptr =  cast[ptr float32](output_buf.buf)

  #get dimensions of our input image.
  let
      H = cast[ptr UncheckedArray[Py_ssize_t]](image_buf.shape)[0].int
      W = cast[ptr UncheckedArray[Py_ssize_t]](image_buf.shape)[1].int
      C = cast[ptr UncheckedArray[Py_ssize_t]](image_buf.shape)[2].int

      outH = cast[ptr UncheckedArray[Py_ssize_t]](output_buf.shape)[1].int
      outW = cast[ptr UncheckedArray[Py_ssize_t]](output_buf.shape)[2].int
      C_out = cast[ptr UncheckedArray[Py_ssize_t]](output_buf.shape)[0].int

  assert C == C_out
  doAssert C == 3,"Expected No of channels to be 3" & " but got " & $C


  hwc2chw_resize_simple(
    inpRawData_ptr = rawData_ptr,
    outRawData_ptr = output_ptr,
    inpH = H,
    inpW = W,
    outH = outH,
    outW = outW,
    C = C,
    reverse_channels = bool(reverse_channels)
  )


  #release the buffers reference for Python GC.
  image_buf.release()
  output_buf.release()