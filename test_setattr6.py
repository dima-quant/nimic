import ncompiler.platform as p
import ctypes
t = p.Target()
def my_setattr(self, name, value):
    print("my_setattr called", name, value, type(value))
    object.__setattr__(self, name, value)
p.Target.__setattr__ = my_setattr
t.hostCPU = p.TSystemCPU.cpuArm64
print("After:", t.hostCPU)
