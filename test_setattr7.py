import ncompiler.platform as p
t = p.Target()
print("Dict before:", t.__dict__)
super(p.Target.__mro__[2], t).__setattr__('hostCPU', p.TSystemCPU.cpuArm64)
print("Dict after super(2):", t.__dict__)
super(p.Target.__mro__[1], t).__setattr__('hostCPU', p.TSystemCPU.cpuArm64)
print("Dict after super(1):", t.__dict__)
