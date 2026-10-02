import ncompiler.platform as p
t = p.Target()
print("Assigning via super:")
super(p.Target, t).__setattr__('hostCPU', p.TSystemCPU.cpuArm64)
print("Dict value:", repr(t.__dict__['hostCPU']))
