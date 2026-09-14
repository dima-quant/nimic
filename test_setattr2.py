import ncompiler.platform as p
t = p.Target()
def my_setattr(self, name, value):
    print("my_setattr called", name, value)
    super(p.Target, self).__setattr__(name, value)
p.Target.__setattr__ = my_setattr
t.hostCPU = p.TSystemCPU.cpuArm64
print("After:", t.hostCPU)
