import ncompiler.platform as p
t = p.Target()
print("Assigning:", repr(p.TSystemCPU.cpuArm64))
t.hostCPU = p.TSystemCPU.cpuArm64
print("Dict value:", repr(t.__dict__['hostCPU']))
