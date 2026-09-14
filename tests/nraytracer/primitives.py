# Python NDSL Raytracer
# Copyright (c) 2025 Dmytro Makogon, see LICENSE (MIT or Apache 2.0, as an option)
# The project is mostly a port of Trace of Radiance (https://github.com/mratsim/trace-of-radiance, see below)
# /// nimic
#
# ///

from nimic.ntypes import *
from safe_math import *
from rays import *
from vec3s import *
from point3s import *
from colors import *
from canvas import *
from timing import *

import safe_math
import rays
import vec3s
import point3s
import colors
import canvas
import timing

with export:
    safe_math, rays, vec3s, point3s, colors, canvas, timing

# Trace of Radiance
# Copyright (c) 2020 Mamy André-Ratsimbazafy
# Licensed and distributed under either of
#   * MIT license (license terms in the root directory or at http://opensource.org/licenses/MIT).
#   * Apache v2 license (license terms in the root directory or at http://www.apache.org/licenses/LICENSE-2.0).
# at your option. This file may not be copied, modified, or distributed except according to those terms.

# import primitives/[
#   safe_math, rays,
#   vec3s, point3s, colors,
#   canvas, time
# ]

# export
#   safe_math, rays,
#   vec3s, point3s, colors,
#   canvas, time