# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from __future__ import annotations
from nimic.ntypes import *

@dispatch
def foo[T](x: T) -> seq[T]:
    result = seq[T]()
    result.add(x)
    print(T)
    return result

class ChannelDescriptor[T](Object):
    buffer: ptr[UncheckedArray[T]]
    stride: int32

@dispatch
def initChannelDesc[T](buffer: mut @ T, width: SomeInteger) -> ChannelDescriptor[T]:
    """
    {.inline.}
    """
    result = ChannelDescriptor[T]()
    result.buffer = cast[ptr[UncheckedArray[T]]](addr(buffer))
    result.stride = int32(width)
    return result

@dispatch
def initChannelDesc[T](buffer: ptr[UncheckedArray[T]], width: SomeInteger) -> ChannelDescriptor[T]:
    """
    {.inline.}
    """
    result = ChannelDescriptor[T]()
    result.buffer = buffer
    result.stride = int32(width)
    return result

@dispatch
def initChannelDesc[T: not UncheckedArray](buffer: ptr[T], width: SomeInteger) -> ChannelDescriptor[T]:
    """
    {.inline.}
    """
    result = ChannelDescriptor[T]()
    result.buffer = cast[ptr[UncheckedArray[T]]](buffer)
    result.stride = int32(width)
    return result

class ChannelY(Object):
    buffer: ptr[UncheckedArray[uint8]]

with let:
    Width = 1024

with var:
    Y = ChannelY()
    yD  = initChannelDesc(Y.buffer, Width)

foo(1)
foo(1.0)